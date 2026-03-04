import binascii
import logging
import os
import socket as _socket
import struct
import threading
import time
import select
from collections import deque, defaultdict
from dataclasses import dataclass, field
from typing import IO, Optional
from future.utils import old_div
from config import get_config as read_config
from utilities.firehol_filter import fireHOL_manager
from logger import DEBUGPLUS


@dataclass
class MessageInfo:
    """
    Metadata about a message being sent through ImpSocket.
    Used for enhanced logging in CM servers.
    """
    emsg_id: Optional[int] = None
    emsg_name: Optional[str] = None
    packet_type: Optional[str] = None  # "Data", "ACK", "Challenge", "Accept", "Disconnect", etc.
    is_encrypted: bool = False
    is_split: bool = False
    split_index: Optional[int] = None  # 0-based index
    split_total: Optional[int] = None  # Total number of split packets
    target_job_id: Optional[int] = None
    source_job_id: Optional[int] = None

    def format_log_prefix(self) -> str:
        """Format a log prefix string with message information."""
        parts = []

        # EMsg or packet type
        if self.emsg_name and self.emsg_id is not None:
            parts.append(f"[{self.emsg_name}({self.emsg_id})]")
        elif self.packet_type:
            parts.append(f"[{self.packet_type}]")

        # Split packet info
        if self.is_split and self.split_index is not None and self.split_total is not None:
            parts.append(f"[Split {self.split_index + 1}/{self.split_total}]")

        # Encryption status
        if self.is_encrypted:
            parts.append("[Encrypted]")

        # Job IDs (only if they're meaningful - not -1 or max uint64)
        job_parts = []
        if self.target_job_id is not None and self.target_job_id != -1 and self.target_job_id != 18446744073709551615:
            job_parts.append(f"target={self.target_job_id}")
        if self.source_job_id is not None and self.source_job_id != -1 and self.source_job_id != 18446744073709551615:
            job_parts.append(f"source={self.source_job_id}")
        if job_parts:
            parts.append(f"[Jobs: {', '.join(job_parts)}]")

        return " ".join(parts) if parts else ""

config = read_config()
real_socket = _socket
default_log = logging.getLogger("IMPSOCK")

wl_path = os.path.join("files", "configs", config['ip_whitelist'])
bl_path = os.path.join("files", "configs", config['ip_blacklist'])

def is_lan_ip(ip):
    """
    Returns True if the IP address is within a LAN/private range.
    Considers:
      - 10.0.0.0/8
      - 172.16.0.0/12
      - 192.168.0.0/16
      - 127.0.0.0/8 (loopback)
    """
    try:
        parts = ip.split('.')
        if len(parts) != 4:
            return False  # not a standard IPv4 address
        first = int(parts[0])
        second = int(parts[1])
        if first == 10:
            return True
        if first == 192 and second == 168:
            return True
        if first == 172 and 16 <= second <= 31:
            return True
        if first == 127:
            return True
    except Exception:
        return False
    return False


class ImpSocketThread(threading.Thread):
    def __init__(self, imp_socket):
        super(ImpSocketThread, self).__init__()
        self.imp_socket = imp_socket
        self.running = True

    def run(self):
        while self.running:
            try:
                if self.imp_socket.is_closed:
                    break
                ### FIX: Now `run_frame()` will do only *one iteration* instead of an infinite loop.
                self.imp_socket.run_frame()
            except real_socket.error as e:
                if not self.imp_socket.is_closed:
                    self.imp_socket.log_with_server(f"Socket error: {e}", level="debug")
                break

    def stop(self):
        self.running = False


class ImpSocket(object):
    error = None

    # === NEW: Class-level tracking for connection attempts ===
    connection_attempts = defaultdict(deque)
    connection_attempts_lock = threading.Lock()
    # ==========================================================

    # Class-level variables for whitelist and blacklist
    whitelist = set()
    blacklist = set()
    whitelist_lock = threading.Lock()
    blacklist_lock = threading.Lock()

    # Class-level packet patterns (loaded once, shared across all instances)
    _start_packet_patterns = None
    _bad_packet_patterns = None
    _patterns_lock = threading.Lock()

    def __init__(self, sock=None, disable_rate_limit=False):
        if sock is None or sock == "tcp":
            self.s = real_socket.socket(real_socket.AF_INET, real_socket.SOCK_STREAM)
            self.s.setsockopt(real_socket.IPPROTO_TCP, real_socket.TCP_NODELAY, 1)
            self.socket_type = 'tcp'
        elif sock == "udp":
            self.s = real_socket.socket(real_socket.AF_INET, real_socket.SOCK_DGRAM)
            self.socket_type = 'udp'
        else:
            self.s = sock
            # Attempt to infer type if a real socket
            if hasattr(self.s, 'type') and self.s.type == real_socket.SOCK_DGRAM:
                self.socket_type = 'udp'
            else:
                self.socket_type = 'tcp'

        self.start_time = int(time.time())
        self.address = None
        self.port = 0
        self.bytes_sent = 0
        self.bytes_received = 0
        self.bytes_sent_total = 0
        self.bytes_received_total = 0
        self.start_time_minute = int(time.time())
        self.bytes_sent_minute = 0
        self.bytes_received_minute = 0
        self.log_file = None
        self.log_interval = 300  # 5 minutes
        self.thread = None  # Lazy initialization - created only when start() is called

        self.use_whitelist = config["enable_whitelist"].lower() == "true"
        self.use_blacklist = config["enable_blacklist"].lower() == "true"

        self.warning_log_limit = 3  # Max warnings to log for an IP within the timeframe
        self.warning_timeframe = 4  # Timeframe in seconds to track repeated issues
        self.block_threshold = 5  # Threshold for blocking IPs within the timeframe
        self.disable_rate_limit = disable_rate_limit

        if self.use_whitelist:
            with ImpSocket.whitelist_lock:
                if not ImpSocket.whitelist:  # Load once
                    ImpSocket.whitelist = self.load_ips_from_file(wl_path)
        if self.use_blacklist:
            with ImpSocket.blacklist_lock:
                if not ImpSocket.blacklist:  # Load once
                    ImpSocket.blacklist = self.load_ips_from_file(bl_path)

        # Use class-level cached patterns instead of loading per-instance
        self._ensure_patterns_loaded()

        self.select_timeout = 0.1  # Adjust as needed

        self.conn_warnings = defaultdict(deque)
        self.conn_errors = defaultdict(deque)  # Tracks errors per IP
        self.error_log_limit = 3  # Max allowed errors before banning
        self.error_timeframe = 5  # Timeframe in seconds to track errors

        self.server_ip = config['server_ip']
        if self.server_ip not in ImpSocket.whitelist:
            ImpSocket.whitelist.add(self.server_ip)

        self.is_closed = False
        self._last_getpeername_warn = 0
        self._has_logged_send_closed = False
        self.log = default_log  # Default logger, will be updated when server context is known

    def _should_log_packets(self):
        """Check if packet logging is enabled for this server"""
        server_key = self._get_server_key()
        
        # Check CM servers first (both encrypted and unencrypted)
        if server_key in ['CM27014UDP', 'CM27014TCP', 'CM27017UDP', 'CM27017TCP']:
            return config.get('disable_impsocket_logging_cm_servers', 'false').lower() != 'true'
        
        # Check specific servers
        if 'ContentServer' in server_key:
            return config.get('disable_impsocket_logging_content_server', 'false').lower() != 'true'
        elif 'AuthServer' in server_key:
            return config.get('disable_impsocket_logging_auth_server', 'false').lower() != 'true'
        elif 'AdminServer' in server_key:
            return config.get('disable_impsocket_logging_admin_server', 'false').lower() != 'true'
        else:
            # All other servers
            return config.get('disable_impsocket_logging_other_servers', 'false').lower() != 'true'
    
    def _get_server_key(self):
        """Get the server name based on port configuration"""
        port_mappings = {
            'steamweb_port': 'SteamWeb',
            'tracker_server_port': 'TrackerServer',
            'masterhl1_server_port': 'MasterServer',
            'masterhl2_server_port': 'MasterServer',
            'masterrdkf_server_port': 'MasterServer',
            'vac_server_port': 'VAC1Server',
            'cser_server_port': 'CSERServer',
            'cm_unencrypted_server_port': 'CM27014',
            'cm_encrypted_server_port': 'CM27017',
            'content_server_port': 'ContentServer',
            'clupd_server_port': 'ClientUpdateServer',
            'harvest_server_port': 'HarvstServer',
            'config_server_port': 'ConfigServer',
            'contentdir_server_port': 'CSDServer',
            'dir_server_port': 'DirectorySRV',
            'auth_server_port': 'AuthServer',          
            'validation_port': 'ValidationSRV',
            'vtt_server_port': 'VTTServer',
            'cafe_server_port': 'CafeServer',
            'admin_server_port': 'AdminServer',
            'ping_server_port': 'PingServer'
        }
        
        for config_key, server_name in port_mappings.items():
            if config_key in config and str(config[config_key]) == str(self.port):
                # Add protocol suffix for CM servers
                if config_key in ['cm_unencrypted_server_port', 'cm_encrypted_server_port']:
                    protocol_suffix = self.socket_type.upper()
                    return f"{server_name}{protocol_suffix}"
                return server_name
                
        # Fallback to checking all config values
        for key, value in config.items():
            if str(value) == str(self.port) and 'port' in key.lower():
                # Convert config key to readable name
                if key in port_mappings:
                    server_name = port_mappings[key]
                    # Add protocol suffix for CM servers
                    if key in ['cm_unencrypted_server_port', 'cm_encrypted_server_port']:
                        protocol_suffix = self.socket_type.upper()
                        return f"{server_name}{protocol_suffix}"
                    return server_name
        return "Unknown"
    
    def _get_logger(self):
        """Get the appropriate logger for this socket's server"""
        if hasattr(self, '_cached_logger'):
            return self._cached_logger

        server_key = self._get_server_key()
        if server_key != "Unknown":
            self._cached_logger = logging.getLogger(server_key)
        else:
            self._cached_logger = default_log
        return self._cached_logger

    def _is_cm_udp(self):
        """Check if this is a UDP CM socket (cached)"""
        if hasattr(self, '_cached_is_cm_udp'):
            return self._cached_is_cm_udp
        server_key = self._get_server_key()
        self._cached_is_cm_udp = self.socket_type == 'udp' and server_key in ['CM27014UDP', 'CM27017UDP']
        return self._cached_is_cm_udp

    def _is_cm_tcp(self):
        """Check if this is a TCP CM socket (cached)"""
        if hasattr(self, '_cached_is_cm_tcp'):
            return self._cached_is_cm_tcp
        server_key = self._get_server_key()
        self._cached_is_cm_tcp = self.socket_type == 'tcp' and server_key in ['CM27014TCP', 'CM27017TCP']
        return self._cached_is_cm_tcp

    def log_with_server(self, message, level="error"):
        logger = self._get_logger()
        log_method = getattr(logger, level, logger.error)
        log_method(message)

    def getclientip(self):
        if self.is_closed:
            return self.address[0] if self.address else None
        if isinstance(self.s, real_socket.socket):
            try:
                client_ip = self.s.getpeername()[0]
                return client_ip
            except Exception:
                now = time.time()
                if now - self._last_getpeername_warn > 30:
                    self._get_logger().debug("getpeername() failed; returning stored address.")
                    self._last_getpeername_warn = now
                return self.address[0] if self.address else None
        else:
            raise ValueError("Cannot get client IP on a non-socket")

    def inet_aton(self, packed_ip):
        return real_socket.inet_aton(packed_ip)

    def inet_ntoa(self, ip_integer):
        return real_socket.inet_ntoa(ip_integer)

    @staticmethod
    def load_ips_from_file(filename):
        try:
            with open(filename, 'r') as f:
                ips = set(
                    line.strip() for line in f
                    if line.strip() and not is_lan_ip(line.strip())
                )
        except FileNotFoundError:
            ips = set()
        return ips

    def load_patterns_from_file(self, filename):
        patterns = set()
        try:
            with open(filename, 'r') as f:
                for line in f:
                    line = line.split('#', 1)[0].strip()
                    if line:
                        patterns.add(line.encode('latin-1'))
        except FileNotFoundError:
            # If these pattern files don't exist, just return empty sets
            return set()
        return patterns

    def _ensure_patterns_loaded(self):
        """Load packet patterns at class level if not already loaded."""
        with ImpSocket._patterns_lock:
            if ImpSocket._start_packet_patterns is None:
                start_patterns = os.path.join(config['configsdir'], 'packet_beginning_patterns.txt')
                ImpSocket._start_packet_patterns = self.load_patterns_from_file(start_patterns)
            if ImpSocket._bad_packet_patterns is None:
                bad_patterns = os.path.join(config['configsdir'], 'packet_anywhere_patterns.txt')
                ImpSocket._bad_packet_patterns = self.load_patterns_from_file(bad_patterns)

    @property
    def START_PACKET_PATTERNS(self):
        """Access class-level start packet patterns."""
        return ImpSocket._start_packet_patterns or set()

    @property
    def BAD_PACKET_PATTERNS(self):
        """Access class-level bad packet patterns."""
        return ImpSocket._bad_packet_patterns or set()

    @staticmethod
    def is_valid_ipv4(ip):
        """Return True if *ip* is a valid dotted quad IPv4 address."""
        try:
            parts = ip.split('.')
            if len(parts) != 4:
                return False
            for part in parts:
                if not part.isdigit():
                    return False
                value = int(part)
                if value < 0 or value > 255:
                    return False
            return True
        except Exception:
            return False

    @classmethod
    def get_whitelist(cls):
        """Return the current IP whitelist as a list of strings."""
        with cls.whitelist_lock:
            if not cls.whitelist:
                cls.whitelist = cls.load_ips_from_file(wl_path)
            return list(cls.whitelist)

    @classmethod
    def get_blacklist(cls):
        """Return the current IP blacklist as a list of strings."""
        with cls.blacklist_lock:
            if not cls.blacklist:
                cls.blacklist = cls.load_ips_from_file(bl_path)
            return list(cls.blacklist)

    @classmethod
    def add_to_whitelist(cls, ip):
        """Add *ip* to the whitelist and persist it to disk."""
        if is_lan_ip(ip):
            default_log.info(f"Skipping whitelist for LAN IP {ip}.")
            return False
        with cls.whitelist_lock:
            if ip in cls.whitelist:
                return False
            cls.whitelist.add(ip)
            try:
                with open(wl_path, 'a', encoding='latin-1') as f:
                    f.write(ip + '\n')
            except Exception as e:
                default_log.error(f"Failed to write {ip} to whitelist file: {e}")
                cls.whitelist.remove(ip)
                return False
        return True

    @classmethod
    def add_to_blacklist(cls, ip):
        """Add *ip* to the blacklist and persist it to disk."""
        if is_lan_ip(ip):
            default_log.info(f"Skipping blacklist for LAN IP {ip}.")
            return False
        with cls.blacklist_lock:
            if ip in cls.blacklist:
                return False
            cls.blacklist.add(ip)
            try:
                with open(bl_path, 'a', encoding='latin-1') as f:
                    f.write(ip + '\n')
            except Exception as e:
                default_log.error(f"Failed to write {ip} to blacklist file: {e}")
                cls.blacklist.remove(ip)
                return False
        return True

    @classmethod
    def remove_from_whitelist(cls, ip):
        """Remove *ip* from the whitelist and update the file."""
        with cls.whitelist_lock:
            if ip not in cls.whitelist:
                return False
            cls.whitelist.remove(ip)
            try:
                with open(wl_path, 'w', encoding='latin-1') as f:
                    for entry in sorted(cls.whitelist):
                        f.write(entry + '\n')
            except Exception as e:
                default_log.error(f"Failed to remove {ip} from whitelist file: {e}")
                return False
        return True

    @classmethod
    def remove_from_blacklist(cls, ip):
        """Remove *ip* from the blacklist and update the file."""
        with cls.blacklist_lock:
            if ip not in cls.blacklist:
                return False
            cls.blacklist.remove(ip)
            try:
                with open(bl_path, 'w', encoding='latin-1') as f:
                    for entry in sorted(cls.blacklist):
                        f.write(entry + '\n')
            except Exception as e:
                default_log.error(f"Failed to remove {ip} from blacklist file: {e}")
                return False
        return True

    def add_ip_to_blacklist(self):
        client_ip = self.getclientip()
        if not client_ip:
            return

        if is_lan_ip(client_ip):
            self._get_logger().info(f"Skipping block for LAN IP {client_ip}.")
            return

        with ImpSocket.blacklist_lock:
            if client_ip in ImpSocket.blacklist:
                return
        self._get_logger().warning(f"IP {client_ip} is blocked due to malicious activity!")
        with ImpSocket.blacklist_lock:
            ImpSocket.blacklist.add(client_ip)
            try:
                with open(bl_path, 'a', encoding='latin-1') as f:
                    f.write(client_ip + '\n')
            except Exception as e:
                self._get_logger().error(f"Failed to write {client_ip} to blacklist file: {e}")

    def close_socket_and_thread(self, block_ip=False):
        if block_ip:
            self.add_ip_to_blacklist()
        self.is_closed = True
        try:
            self.s.shutdown(real_socket.SHUT_RDWR)
        except Exception as e:
            self.log_with_server(f"Socket shutdown error: {e}", level="debug")
        finally:
            self.s.close()
        if self.thread is not None:
            self.thread.stop()

    def block_ip(self):
        self.close_socket_and_thread(block_ip=True)

    def is_ip_allowed(self, ip_address):
        if is_lan_ip(ip_address):
            return True
        if self.use_whitelist and ip_address not in ImpSocket.whitelist:
            return False
        elif ip_address in ImpSocket.whitelist:
            return True

        if fireHOL_manager.is_ip_blocked(ip_address) and config["enable_firehol"].lower() == "true":  # Check if the IP is blocked by fireHOL
            #log.debug("IP blocked by FireHOL")
            return False

        if self.use_blacklist and ip_address in ImpSocket.blacklist:
            return False
        return True

    def start(self):
        """Start the socket thread (creates thread lazily if not already created)."""
        if self.thread is None:
            self.thread = ImpSocketThread(self)
        self.thread.start()

    def ip_to_bytes(self, ip_address):
        ip_bytes = real_socket.inet_aton(ip_address)
        hex_str = binascii.hexlify(ip_bytes).decode('ascii').upper()
        return hex_str

    def track_and_handle_errors(self, ip):
        now = time.time()
        errors = self.conn_errors[ip]
        errors.append(now)
        while errors and now - errors[0] > self.error_timeframe:
            errors.popleft()
        return True

    def track_broken_connection(self, ip):
        if ip in ImpSocket.blacklist:
            return
        now = time.time()
        warnings = self.conn_warnings[ip]
        warnings.append(now)

        while warnings and now - warnings[0] > self.warning_timeframe:
            warnings.popleft()

        if len(warnings) <= self.warning_log_limit:
            self._get_logger().warning(f"Connection issue detected from IP: {ip}. Warning #{len(warnings)}")

        if len(warnings) > self.block_threshold and ip not in ImpSocket.blacklist:
            self._get_logger().warning(
                f"Banning IP {ip} due to repeated issues({len(warnings)} times in {self.warning_timeframe}s).")
            self.block_ip()

    def accept(self):
        if self.is_closed:
            return None, None
        if isinstance(self.s, real_socket.socket):
            try:
                (returned_socket, address) = self.s.accept()
                client_ip = address[0]

                #if not self.disable_rate_limit:
                #    with ImpSocket.connection_attempts_lock:
                #        now = time.time()
                #        attempts = ImpSocket.connection_attempts[client_ip]
                #        attempts.append(now)
                #        while attempts and now - attempts[0] > 20:
                #            attempts.popleft()
                #        if len(attempts) > 200:
                #            log.warning(f"IP {client_ip} has connected {len(attempts)} times in 20 seconds. Blacklisting.")
                #            try:
                #                returned_socket.close()
                #            except Exception as e:
                #                log.error(f"Error closing socket for overactive IP {client_ip}: {e}")
                #            with ImpSocket.blacklist_lock:
                #                ImpSocket.blacklist.add(client_ip)
                #            return None, None
                if not self.is_ip_allowed(client_ip):
                    returned_socket.close()
                    if self.use_whitelist:
                        self._get_logger().warning(f"Connection attempt from NON-Whitelisted IP {client_ip} blocked.")
                    else:
                        self._get_logger().warning(f"Connection attempt from Blacklisted IP {client_ip} blocked.")
                    return None, None
                new_socket = ImpSocket(returned_socket, disable_rate_limit=self.disable_rate_limit)
                new_socket.address = address
                new_socket.port = self.port
                # Clear cached logger so it gets recreated with the correct server name
                if hasattr(new_socket, '_cached_logger'):
                    delattr(new_socket, '_cached_logger')
                return new_socket, address
            except:
                pass
        else:
            default_log.error("Cannot accept on a non-socket")
        return None, None


    def bind(self, address):
        self.address = address
        self.s.bind(address)
        self.port = address[1]
        # Clear cached logger so it gets recreated with the correct server name
        if hasattr(self, '_cached_logger'):
            delattr(self, '_cached_logger')

    def connect(self, address):
        if isinstance(self.s, real_socket.socket):
            self.address = address
            self.s.connect(address)
            self._get_logger().debug(f"{str(self.address)}: Connecting to address")
        else:
            raise ValueError("Cannot connect on a non-socket")

    def close(self):
        if isinstance(self.s, real_socket.socket):
            self.s.close()

    def listen(self, connections):
        if isinstance(self.s, real_socket.socket):
            self.s.listen(connections)
        else:
            raise ValueError("Cannot listen on a non-socket")

    def settimeout(self, timeout_time):
        self.s.settimeout(timeout_time)

    def send(self, data, to_log=True, msg_info: Optional[MessageInfo] = None):
        if self.is_closed:
            return 0
        ip = self.getclientip()
        if ip in ImpSocket.blacklist:
            return 0
        if not self.s:
            return 0
        try:
            sentbytes = self.s.send(data)
            self.bytes_sent += sentbytes
            self.bytes_sent_total += sentbytes
            if to_log and self._should_log_packets():
                if msg_info:
                    prefix = msg_info.format_log_prefix()
                    if msg_info.is_split:
                        # For split packets: print summary to console (INFO), log full binary to debug
                        self._get_logger().info(f"{str(self.address)}: {prefix} Sent data")
                        self._get_logger().debug(f"{str(self.address)}: {prefix} Sent data - {data}")
                    else:
                        self._get_logger().debug(f"{str(self.address)}: {prefix} Sent data - {data}")
                else:
                    self._get_logger().debug(f"{str(self.address)}: Sent data - {data}")
            if sentbytes != len(data):
                self._get_logger().warning(f"NOTICE! Sent bytes ({sentbytes}) != data length ({len(data)}).")
            return sentbytes
        except Exception as e:
            if "10038" in str(e):
                if not self._has_logged_send_closed:
                    self._has_logged_send_closed = True
            else:
                self.log_with_server(f"Error sending data to {ip}: {e}")
                self.track_and_handle_errors(ip)
            return 0

    def sendall(self, data, to_log=True):
        """
        Send all of `data`, looping on self.send() until completion.
        Returns the total number of bytes sent (or 0 on failure).
        """
        if self.is_closed:
            return 0

        total_sent = 0
        length = len(data)
        # Only log once at the start if requested
        while total_sent < length:
            sent = self.send(data[total_sent:], to_log and total_sent == 0)
            if sent <= 0:
                # error or socket closed
                return total_sent
            total_sent += sent
        return total_sent

    def sendfile(self, file_obj, offset=0, count=None, to_log=True):
        """Send a file using zero-copy when available.

        Falls back to manual read/send when ``socket.sendfile`` is not
        implemented on the current platform. The file descriptor is closed
        after the transfer regardless of success.

        Args:
            file_obj (IO): Open file object to transmit.
            offset (int): Starting offset within the file.
            count (Optional[int]): Number of bytes to send; ``None`` sends the
                remainder of the file.
            to_log (bool): Whether to log the transfer.

        Returns:
            int: Number of bytes sent, or 0 on failure.
        """
        ip = self.getclientip()
        try:
            if self.is_closed or ip in ImpSocket.blacklist or not self.s:
                return 0

            if hasattr(self.s, "sendfile"):
                file_obj.seek(offset)
                sentbytes = self.s.sendfile(file_obj, offset, count)
            else:
                file_obj.seek(offset)
                remaining = count
                sentbytes = 0
                bufsize = 8192
                while True:
                    if remaining is not None and remaining <= 0:
                        break
                    read_size = bufsize if remaining is None else min(bufsize, remaining)
                    chunk = file_obj.read(read_size)
                    if not chunk:
                        break
                    sent = self.send(chunk, to_log and sentbytes == 0)
                    if sent <= 0:
                        break
                    sentbytes += sent
                    if remaining is not None:
                        remaining -= sent

            self.bytes_sent += sentbytes
            self.bytes_sent_total += sentbytes
            if to_log and self._should_log_packets():
                self._get_logger().debug(
                    f"{str(self.address)}: Sent file - {sentbytes} bytes")
            return sentbytes
        except Exception as e:
            self.log_with_server(f"Error sending file to {ip}: {e}")
            self.track_and_handle_errors(ip)
            return 0
        finally:
            try:
                file_obj.close()
            except Exception:
                pass

    def sendto(self, data, address, to_log=True, msg_info: Optional[MessageInfo] = None):
        if not self.is_ip_allowed(self.address[0]):
            return 0
        sentbytes = self.s.sendto(data, address)
        self.bytes_sent += sentbytes
        self.bytes_sent_total += sentbytes
        if to_log and self._should_log_packets():
            if msg_info:
                prefix = msg_info.format_log_prefix()
                # Use debugplus for heartbeat/datagram packets to reduce noise at DEBUG level
                is_heartbeat = msg_info.packet_type and ('Heartbeat' in msg_info.packet_type or 'Datagram' in msg_info.packet_type)
                if msg_info.is_split:
                    # For split packets: print summary to console (INFO), log full binary to debug
                    self._get_logger().info(f"{str(address)}: {prefix} Sent data")
                    self._get_logger().debug(f"{str(address)}: {prefix} Sent data - {data}")
                elif is_heartbeat:
                    self._get_logger().log(DEBUGPLUS, f"{str(address)}: {prefix} Sent data - {data}")
                else:
                    self._get_logger().debug(f"{str(address)}: {prefix} Sent data - {data}")
            else:
                self._get_logger().debug(f"{str(address)}: sendto Sent data - {data}")
        if sentbytes != len(data):
            self._get_logger().warning(f"NOTICE!!! bytes sent != tried to send {sentbytes} {len(data)}")
        return sentbytes

    def send_withlen(self, data, to_log=True, is_short=False, msg_info: Optional[MessageInfo] = None):
        if is_short:
            lengthstr = struct.pack(">H", len(data))
        else:
            lengthstr = struct.pack(">L", len(data))
        if to_log and self._should_log_packets():
            if msg_info:
                prefix = msg_info.format_log_prefix()
                self._get_logger().debug(f"{str(self.address)}: {prefix} Sent data with length - {binascii.b2a_hex(lengthstr).decode()} {data}")
            else:
                self._get_logger().debug(f"{str(self.address)}: Sent data with length - {binascii.b2a_hex(lengthstr).decode()} {data}")
        totaldata = lengthstr + data
        totalsent = 0
        while totalsent < len(totaldata):
            sent = self.send(totaldata[totalsent:], False, msg_info)
            if sent == 0:
                self.close_socket_and_thread(False)
                break
            totalsent += sent

    def recv(self, length, to_log=True):
        if self.is_closed:
            return b''
        try:
            data = self.s.recv(length)
            client_ip = self.getclientip()
            if not self.is_ip_allowed(client_ip):
                self.s.close()
                if self.use_whitelist:
                    self._get_logger().warning(f"Connection attempt from NON-Whitelisted IP {client_ip} blocked.")
                else:
                    self._get_logger().warning(f"Connection attempt from Blacklisted IP {client_ip} blocked.")
                return b''
        except Exception as e:
            return b''

        # Packet filtering
        if config["enable_blacklist"].lower() == 'true':
            try:
                if any(data.startswith(pattern) for pattern in self.START_PACKET_PATTERNS):
                    self.block_ip()
                    return b''
                if any(pattern in data for pattern in self.BAD_PACKET_PATTERNS):
                    self.block_ip()
                    return b''
            except:
                return b''

        self.bytes_received += len(data)
        if to_log and self._should_log_packets():
            self._get_logger().debug(f"{str(self.address)}: Received data - {data}")
        return data

    def recvfrom(self, length, to_log=True):
        if self.is_closed:
            return b'', None
        #try:
        data, address = self.s.recvfrom(length)
        """except Exception as e:
            if not self.is_closed:
                log.error(f"recvfrom error: {e}")
            return b'', None"""

        if not self.is_ip_allowed(address[0]):
            self._get_logger().warning(f"Blocked IP {address[0]} attempted to send data. Dropping packet.")
            return None, address

        if data is None:
            return b'', address
        self.bytes_received += len(data)
        self.bytes_received_total += len(data)
        if to_log and self._should_log_packets():
            # Check if this is a UDP CM heartbeat packet (byte 7 / index 6 is 0x07)
            if self._is_cm_udp() and len(data) > 6 and data[6] == 0x07:
                # Heartbeat packet - log to file only using debugplus level
                self._get_logger().debugplus(f"{str(address)}: recvfrom Received heartbeat data - {data}")
            else:
                # Regular packets - log with debug level
                self._get_logger().debug(f"{str(address)}: recvfrom Received data - {data}")
        return data, address

    def recv_all(self, length, to_log=True):
        data = b""
        while len(data) < length:
            chunk = self.recv(length - len(data), False)
            if not self.is_ip_allowed(self.address[0]):
                self._get_logger().warning(f"Blocked IP {self.address[0]} attempted to send data. Dropping packet.")
                return None
            if chunk is None:
                return None
            if chunk == b'':
                self._get_logger().warning(f"Socket connection broken during recv_all with {str(self.address)}")
                self.track_broken_connection(self.address[0] if self.address else "unknown")
                break
            data += chunk
        return data

    def recv_withlen(self, to_log=True, is_short=False):
        if is_short:
            lengthstr = self.recv(2, False)
            pkformat = ">H"
            min_str_len = 2
            dummy = None
        else:
            lengthstr = self.recv(4, False)
            pkformat = ">L"
            min_str_len = 4
            dummy = b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"

        if lengthstr is None:
            return None
        if len(lengthstr) != min_str_len:
            self._get_logger().debug(f'Command header not long enough, should be {min_str_len}, is {len(lengthstr)}')
            return dummy
        else:
            length = struct.unpack(pkformat, lengthstr)[0]
            data = self.recv_all(length, False)
            if to_log and self._should_log_packets() and data:
                # Check if this is a TCP CM heartbeat packet
                if self._is_cm_tcp() and data[0:4] == b'\x07\x00\x00\x00':
                    # Heartbeat packet - log to file only using debugplus level
                    self._get_logger().debugplus(f"{str(self.address)}: Received heartbeat data with length - {binascii.b2a_hex(lengthstr).decode()} {data}")
                else:
                    # Regular packets - log with debug level
                    # NOTE: Commented out to reduce log verbosity - uncomment for packet debugging
                    # self._get_logger().debug(f"{str(self.address)}: Received data with length - {binascii.b2a_hex(lengthstr).decode()} {data}")
                    pass
            return data

    def log_packet(self, address, direction: str, data: bytes, msg_info: Optional[MessageInfo] = None, is_heartbeat: bool = False):
        """
        Log packet data (decrypted) to console and debug file.
        Called from CM server after decryption (for receives) or before encryption (for sends).

        Args:
            address: The client address tuple (ip, port)
            direction: "Received" or "Sent"
            data: The decrypted/unencrypted packet data
            msg_info: Optional MessageInfo with message ID, name, job IDs, etc.
            is_heartbeat: If True, log only to file (debugplus level), not console
        """
        if not self._should_log_packets():
            return

        if msg_info:
            prefix = msg_info.format_log_prefix()
            log_msg = f"{str(address)}: {prefix} {direction} data - {data}"
        else:
            log_msg = f"{str(address)}: {direction} data - {data}"

        if is_heartbeat:
            # Heartbeat packets - log to file only (debugplus level)
            self._get_logger().debugplus(log_msg)
        else:
            # Regular packets - log to console (debug level)
            self._get_logger().debug(log_msg)

    def get_outgoing_data_rate(self):
        elapsed_time = time.time() - self.start_time
        if elapsed_time <= 0:
            return 0
        outgoing_kbps = old_div(old_div(self.bytes_sent, elapsed_time), 1024)
        return outgoing_kbps

    def get_incoming_data_rate(self):
        elapsed_time = time.time() - self.start_time
        if elapsed_time <= 0:
            return 0
        incoming_kbps = old_div(old_div(self.bytes_received, elapsed_time), 1024)
        return incoming_kbps

    def get_total_bytes_in(self):
        return self.bytes_received

    def get_total_bytes_out(self):
        return self.bytes_sent

    def get_port(self):
        return self.port

    def get_ip(self):
        return self.address

    def run_frame(self):
        ### CHANGED: Instead of `while True:`, do a single iteration.
        ### So now, ImpSocketThread.run() calls run_frame() repeatedly, but
        ### we don?t trap ourselves in an inner infinite loop.

        if self.is_closed:
            return

        current_time = int(time.time())
        elapsed_time = current_time - self.start_time_minute
        read_sockets = [self.s]
        write_sockets = []
        try:
            readable, writable, _ = select.select(read_sockets, write_sockets, [], self.select_timeout)
        except Exception as e:
            # If the socket is closed or invalid, we just stop
            self.log_with_server(f"Select error in run_frame(): {e}", level="debug")
            return

        if elapsed_time >= self.log_interval:
            self.start_time_minute = current_time
            self.bytes_sent_minute = self.bytes_sent
            self.bytes_received_minute = self.bytes_received
            # self.log_statistics(...) # optional

        # We can optionally do some idle logic here
        # time.sleep(self.select_timeout)

    def log_statistics(self, outgoing_kbps_minute, incoming_kbps_minute):
        if self.log_file is None:
            log_filename = time.strftime("logs/networklogs-%m-%d-%y.log")
            self.log_file = open(log_filename, "a")

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"{timestamp} Outgoing (KBps): {outgoing_kbps_minute:.2f}, Incoming (KBps): {incoming_kbps_minute:.2f}\n"
        self.log_file.write(log_message)
        self.log_file.flush()
