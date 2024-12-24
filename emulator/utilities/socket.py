import binascii
import logging
import socket as _socket
import struct
import threading
import time
from collections import deque, defaultdict
import select
from future.utils import old_div

from config import get_config as read_config

config = read_config()
real_socket = _socket
log = logging.getLogger("SOCKET")

class ImpSocketThread(threading.Thread):
    def __init__(self, imp_socket):
        super(ImpSocketThread, self).__init__()
        self.imp_socket = imp_socket

    def run(self):
        while True:
            self.imp_socket.run_frame()


class ImpSocket(object):
    error = real_socket.error

    def __init__(self, sock = None):
        if sock is None or sock == "tcp":
            self.s = real_socket.socket(real_socket.AF_INET, real_socket.SOCK_STREAM)
            self.s.setsockopt(real_socket.IPPROTO_TCP, real_socket.TCP_NODELAY, 1)
        elif sock == "udp":
            self.s = real_socket.socket(real_socket.AF_INET, real_socket.SOCK_DGRAM)
        else:
            self.s = sock
        self.socket_type = 'udp' if sock == 'udp' else 'tcp'
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
        self.thread = ImpSocketThread(self)
        self.use_whitelist = config["enable_whitelist"].lower() == "true"
        self.use_blacklist = config["enable_blacklist"].lower() == "true"
        # Existing initialization code...

        self.warning_log_limit = 3  # Max warnings to log for an IP within the timeframe
        self.warning_timeframe = 4  # Timeframe in seconds to track repeated issues
        self.block_threshold = 5  # Threshold for blocking IPs within the timeframe

        self.whitelist = self.load_ips_from_file(config['configsdir'] + '/' + config['ip_whitelist']) if self.use_whitelist else set()
        self.blacklist = self.load_ips_from_file(config['configsdir'] + '/' + config['ip_blacklist']) if self.use_blacklist else set()

        # Load the patterns from the text files
        self.START_PACKET_PATTERNS = self.load_patterns_from_file(config['configsdir'] + '/' + 'packet_beginning_patterns.txt')
        self.BAD_PACKET_PATTERNS = self.load_patterns_from_file(config['configsdir'] + '/' + 'packet_anywhere_patterns.txt')
        self.select_timeout = 0.1  # Adjust the timeout as needed for responsiveness

        self.conn_warnings = defaultdict(deque)
        self.conn_errors = defaultdict(deque)  # Tracks errors per IP
        self.error_log_limit = 3  # Max allowed errors before banning
        self.error_timeframe = 5  # Timeframe in seconds to track errors
        # Add server's ip address to whitelist to prevent infinite error scrolling
        self.server_ip = config['server_ip']
        if self.server_ip not in self.whitelist:
            self.whitelist.add(self.server_ip)
            #log.info(f"Added server IP {self.server_ip} to whitelist.")

    def inet_aton(self, packed_ip):
        # Call inet_ntoa from the socket module
        return real_socket.inet_aton(packed_ip)

    def inet_ntoa(self, ip_integer):
        return real_socket.inet_ntoa(ip_integer)

    @staticmethod
    def load_ips_from_file(filename):
        try:
            with open(filename, 'r') as f:
                ips = set(f.read().splitlines())
        except FileNotFoundError:
            ips = set()  # Return an empty set if the file does not exist
        return ips

    def load_patterns_from_file(self, filename):
        patterns = set()
        with open(filename, 'r') as f:
            for line in f:
                line = line.split('#', 1)[0].strip()  # Remove comments and strip whitespace
                if line:  # Ignore empty lines
                    patterns.add(line.encode('latin-1'))
        return patterns

    def block_ip(self):
        client_ip = self.getclientip()

        log.warning(f"IP {client_ip} is blocked due to malicious activity!")

        # Load existing IPs from the file into the set
        with open(config['configsdir'] + '/' + config['ip_blacklist'], 'r') as f:
            existing_ips = set(f.read().splitlines())

        # Add the new IP if it's not already in the set
        if client_ip not in existing_ips:
            self.blacklist.add(client_ip)
            self.s.close()  # Close the client socket
            with open(config['configsdir'] + '/' + config['ip_blacklist'], 'a') as f:
                f.write(client_ip + '\n')


    def is_ip_allowed(self, ip_address):
        if self.use_whitelist and ip_address not in self.whitelist:
            return False
        if self.use_blacklist and ip_address in self.blacklist:
            return False
        return True

    def start(self):
        self.thread.start()

    def ip_to_bytes(self, ip_address):
        ip_bytes = real_socket.inet_aton(ip_address)
        # Convert the bytes to a hex string
        hex_str = binascii.hexlify(ip_bytes).decode('ascii').upper()
        return hex_str

    def track_and_handle_errors(self, ip):
        """
        Tracks errors for the given IP and handles banning if the limit is exceeded.
        """
        now = time.time()
        errors = self.conn_errors[ip]

        # Add the current error timestamp
        errors.append(now)

        # Remove old errors outside the tracking timeframe
        while errors and now - errors[0] > self.error_timeframe:
            errors.popleft()

        # Check if the error limit is exceeded
        """if len(errors) > self.error_log_limit:
            if self.is_ip_allowed(ip):  # Check if the IP is not blacklisted
                self.block_ip()  # Block the IP if it isn't already
                log.warning(f"IP {ip} banned due to exceeding error limit ({self.error_log_limit} errors in {self.error_timeframe} seconds).")
            return False  # Suppress further logging for this IP"""
        return True

    def track_broken_connection(self, ip):
        """Track occurrences of broken connections and limit warnings."""
        now = time.time()
        warnings = self.conn_warnings[ip]

        # Add the current time to the deque
        warnings.append(now)

        # Remove old entries outside the timeframe
        while warnings and now - warnings[0] > self.warning_timeframe:
            warnings.popleft()

        # Log only if warnings are below the log limit
        if len(warnings) <= self.warning_log_limit:
            log.warning(f"Connection issue detected from IP: {ip}. Warning #{len(warnings)}")

        # Block IP if it exceeds the block threshold
        if len(warnings) > self.block_threshold:
            log.warning(f"Banning IP {ip} due to repeated issues ({len(warnings)} times in {self.warning_timeframe}s).")
            self.block_ip()


    def accept(self):
        if isinstance(self.s, real_socket.socket):
            try:
                (returned_socket, address) = self.s.accept()
                client_ip = address[0]

                if not self.is_ip_allowed(client_ip):
                    returned_socket.close()  # Close the client socket
                    if self.use_whitelist:
                        log.warning(f"Connection attempt from NON-Whitelisted IP {client_ip} blocked.")
                    else:
                        log.warning(f"Connection attempt from Blacklisted IP {client_ip} blocked.")
                    return None, None
                new_socket = ImpSocket(returned_socket)
                new_socket.address = address
                return new_socket, address
            except:
                pass
        else:
            log.error("Cannot accept on a non-socket")

    def bind(self, address):
        self.address = address
        self.s.bind(address)

    def connect(self, address):
        if isinstance(self.s, real_socket.socket):
            self.address = address
            self.s.connect(address)
            log.debug(f"{str(self.address)}: Connecting to address")
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

    def send(self, data, to_log=True):
        """
        Sends data over the socket and tracks connection errors.
        """
        ip = self.getclientip()  # Get the IP of the client
        if ip in self.blacklist:
            return 0  # Suppress further operations for blocked IPs
        if not self.s:
            return 0  # fuck this shiat
        try:
            sentbytes = self.s.send(data)
            self.bytes_sent += sentbytes
            self.bytes_sent_total += sentbytes
            if to_log:
                log.debug(f"{str(self.address)}: Sent data - {data}")
            if sentbytes != len(data):
                log.warning(f"NOTICE! Sent bytes ({sentbytes}) do not match data length ({len(data)}).")
            return sentbytes
        except Exception as e:
            log.error(f"Error sending data to {ip}: {e}")
            # Track and handle errors
            if not self.track_and_handle_errors(ip):
                return 0  # Suppress logging after ban
            raise

    def sendto(self, data, address, to_log = True):
        if not self.is_ip_allowed(self.address[0]):
            return 0
        sentbytes = self.s.sendto(data, address)
        self.bytes_sent += sentbytes
        self.bytes_sent_total += sentbytes
        # elapsed_time = int(time.time()) - self.start_time
        # if elapsed_time > 0 and self.bytes_sent > 0:
        #    outgoing_kbps = old_div(old_div(int(self.bytes_sent), int(elapsed_time)), 1024)
        # else:
        #    outgoing_kbps = 0
        if to_log:
            log.debug(f"{str(address)}: sendto Sent data - {data}")
        if sentbytes != len(data):
            log.warning(f"NOTICE!!! Number of bytes sent doesn\'t match what we tried to send {str(sentbytes)} {str(len(data))}")
        return sentbytes

    def send_withlen_short(self, data, to_log = True):
        lengthstr = struct.pack(">H", len(data))
        if to_log:
            log.debug(f"{str(self.address)}: Sent data with length - {binascii.b2a_hex(lengthstr).decode()} {data}")
        self.send(lengthstr + data, False)
        sentbytes = lengthstr + data
        return sentbytes

    def send_withlen(self, data, to_log = True):
        lengthstr = struct.pack(">L", len(data))
        if to_log:
            log.debug(f"{str(self.address)}: Sent data with length - {binascii.b2a_hex(lengthstr).decode()} {data}")
        totaldata = lengthstr + data
        totalsent = 0
        while totalsent < len(totaldata):
            sent = self.send(totaldata, False)
            if sent == 0:
                log.warning("Warning! Connection Lost!")
            totalsent = totalsent + sent

    def recv(self, length, to_log = True):
        try:
            data = self.s.recv(length)
            client_ip = self.getclientip()
            if not self.is_ip_allowed(client_ip):
                self.s.close()  # Close the client socket
                if self.use_whitelist:
                    log.warning(f"Connection attempt from NON-Whitelisted IP {client_ip} blocked.")
                else:
                    log.warning(f"Connection attempt from Blacklisted IP {client_ip} blocked.")
                return None, None  # Optionally handle this case as needed
        except:
            return b''
            #log.debug(f"{client_ip} Connection closed.")
        # Check if the packet starts with any of the defined start patterns
        if config["enable_blacklist"].lower() == 'true':
            try:
                if any(data.startswith(pattern) for pattern in self.START_PACKET_PATTERNS):
                    self.block_ip()
                    return -1

                # Check for bad patterns in the received data
                if any(pattern in data for pattern in self.BAD_PACKET_PATTERNS):
                    self.block_ip()
                    return -1
            except:
                return b''
        self.bytes_received += len(data)
        #elapsed_time = int(time.time()) - self.start_time
        #if elapsed_time > 0 and self.bytes_received > 0:
        #    incoming_kbps = old_div(old_div(self.bytes_received, int(elapsed_time)), 1024)
        #else:
        #    incoming_kbps = 0
        if to_log:
            log.debug(f"{str(self.address)}: Received data - {data}")
        return data

    def recvfrom(self, length, to_log = True):
        data, address = self.s.recvfrom(length)

        # Check if the IP is blocked before processing the data
        if not self.is_ip_allowed(address[0]):
            log.warning(f"Blocked IP {address[0]} attempted to send data. Dropping packet.")
            return None, address  # Return None to indicate the packet should be ignored

        if data is None:
            # The packet is from a blocked IP, skip further processing
            return b'', address
        self.bytes_received += len(data)
        self.bytes_received_total += len(data)
        #elapsed_time = int(time.time()) - self.start_time
        #if elapsed_time > 0 and self.bytes_received > 0:
        #    incoming_kbps = self.bytes_received // (elapsed_time * 1024)
        #else:
        #    incoming_kbps = 0
        if to_log:
            log.debug(f"{str(address)}: recvfrom Received data - {data}")
        return data, address

    def recv_all(self, length, to_log = True):
        data = b""
        while len(data) < length:
            chunk = self.recv(length - len(data), False)
            if chunk == None:
                return None
            if chunk == b'':
                log.warning(f"Socket connection broken during Recieve with {str(self.address)}")
                self.track_broken_connection(str(self.address[0]))
            data = data + chunk
        # FIXME why is there a log message here? it is already taken care of in self.recv()
        #if to_log:
        #    log.debug(f"{str(self.address)}: Received all data - {data}")
        return data

    def recv_withlen(self, to_log = True):
        lengthstr = self.recv(4, False)
        if lengthstr == None:
            return None
        if len(lengthstr) != 4:
            log.debug(f'Command header not long enough, should be 4, is {str(len(lengthstr))}')
            return b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"  # DUMMY RETURN FOR FILESERVER
        else:
            length = struct.unpack(">L", lengthstr)[0]
            data = self.recv_all(length, False)
            # FIXME figure out a way to move this to self.recv or the packet  will print twice
            log.debug(f"{str(self.address)}: Received data with length  - {binascii.b2a_hex(lengthstr).decode()} {data}")
            return data

    def recv_withlen_short(self, to_log = True):
        lengthstr = self.recv(2, False)
        if lengthstr == None:
            return None
        if len(lengthstr) != 2 :
            log.debug(f"Command header not long enough, should be 2, is {str(len(lengthstr))} data: {lengthstr}")
            #return "\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00" #DUMMY RETURN FOR FILESERVER
        else :
            length = struct.unpack(">H", lengthstr)[0]

            data = self.recv_all(length, False)
            # FIXME figure out a way to move this to self.recv or the packet  will print twice
            # if not data[0] == "\x07":
            log.debug(f"{str(self.address)}: Received data with length  - {binascii.b2a_hex(lengthstr).decode()} {data}")
            return data

    def get_outgoing_data_rate(self):
        elapsed_time = time.time() - self.start_time
        outgoing_kbps = old_div(old_div(self.bytes_sent, elapsed_time), 1024)
        return outgoing_kbps

    def get_incoming_data_rate(self):
        elapsed_time = time.time() - self.start_time
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

    def getclientip(self):
        if isinstance(self.s, real_socket.socket):
            try:
                client_ip = self.s.getpeername()[0]
                return client_ip
            except:

                log.debug("Tried getpeername() on a non-socket, blacklisted ip attempt?")
                return self.address
        else:
            raise ValueError("Cannot get client IP on a non-socket")

    def run_frame(self):
        while True:
            current_time = int(time.time())
            elapsed_time = current_time - self.start_time_minute

            # Create lists of sockets to monitor
            read_sockets = [self.s]  # Monitor this socket for incoming data
            write_sockets = []  # Monitor this socket for outgoing data

            # Use select to block until a socket becomes ready
            readable, writable, _ = select.select(read_sockets, write_sockets, [], self.select_timeout)

            if elapsed_time >= self.log_interval:
                # Calculate per-minute data rates
            #    outgoing_kbps_minute = old_div(old_div((self.bytes_sent - self.bytes_sent_minute), elapsed_time), 1024)
            #    incoming_kbps_minute = old_div(old_div((self.bytes_received - self.bytes_received_minute), elapsed_time), 1024)

                # Reset per-minute counters
                self.start_time_minute = current_time
                self.bytes_sent_minute = self.bytes_sent
                self.bytes_received_minute = self.bytes_received

                # Log statistics to a file
                # self.log_statistics(outgoing_kbps_minute, incoming_kbps_minute)

            # Add a sleep to avoid high CPU usage when no activity is happening
            time.sleep(self.select_timeout)

    def log_statistics(self, outgoing_kbps_minute, incoming_kbps_minute):
        if self.log_file is None:
            log_filename = time.strftime("logs/networklogs-%m-%d-%y.log")
            self.log_file = open(log_filename, "a")

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"{timestamp} Outgoing (KBps): {outgoing_kbps_minute:.2f}, Incoming (KBps): {incoming_kbps_minute:.2f}\n"
        self.log_file.write(log_message)
        self.log_file.flush()