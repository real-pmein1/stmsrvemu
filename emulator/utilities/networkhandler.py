import logging
import os
import threading
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
import time

import globalvars
import utilities.impsocket as emu_socket
from servers.managers import dirlistmanager
from servers.managers.serverlist_utilities import send_heartbeat

# Global variables to track incoming and outgoing data size
incoming_data_size = 0
outgoing_data_size = 0
# Server types that should not be added to the directory server
NO_DIR_ENTRY_SERVER_TYPES = {
    "",
    "masterdirserver",
    "ContentServer",
    "ClientUpdateServer",
    "VTTServer",
    "Beta1_AuthServer",
    "CafeServer",
    "CMServerUDP_27014",
    "CMServerUDP_27017",
    "CMServerTCP_27014",
    "CMServerTCP_27017",
}


# log = logging.getLogger("NetHandler")


class NetworkHandler(threading.Thread):

    # global manager
    def __init__(self, in_socket, in_config, port, server_type = ""):
        super().__init__()
        self.socket = in_socket
        self.config = in_config
        self._stop_event = threading.Event()  # Add an event to signal thread stopping
        self.port = port
        self.server_type = server_type
        # Initialize the logger with server_type if provided, otherwise use a default name
        if server_type:
            self.log = logging.getLogger(server_type)
        else:
            self.log = logging.getLogger("NetworkHandler")

        globalvars.servers.append(self)
        self.running = True

        if server_type not in NO_DIR_ENTRY_SERVER_TYPES:
            # Choose which IP to advertise based on public_ip setting.
            server_ip = globalvars.server_ip_b if globalvars.public_ip == "0.0.0.0" else globalvars.public_ip_b
            self.server_info = {
                    "wan_ip":     server_ip,
                    "lan_ip":     globalvars.server_ip_b,
                    "port":       int(self.port),
                    "server_type":self.server_type,
                    "timestamp":  int(time.time()),
            }
            if not globalvars.aio_server:
                self.log.info("Server is starting Heartbeat Thread, If this server is AIO (all servers built into a single program) Please report this message!")
                self.start_heartbeat_thread()
            else:
                addserver = dirlistmanager.manager.add_server_info(server_ip, globalvars.server_ip_b, int(self.port), self.server_type, 1)
                if addserver != -1:
                    self.log.debug("Server Added to Directory Server List: " + self.server_type)
                else:
                    self.log_with_server("Server Not added to list! Please contact support.")
                    return

    def _get_server_key(self):
        for key, value in self.config.items():
            if str(value) == str(self.port):
                return key
        return "unknown"

    def log_with_server(self, message, level="error", **kwargs):
        server_key = self._get_server_key()
        log_method = getattr(self.log, level, self.log.error)
        log_method(f"{message} [server {server_key} port {self.port}]", **kwargs)

    def run(self):
        try:
            super().run()  # Call the parent run method which contains the main loop
        except Exception:
            self.log_with_server(f"{self.__class__.__name__} Exception Occurred:", exc_info=True)

    def stop(self):
        """Stop the server gracefully."""
        self.log.info(f"Stopping {self.__class__.__name__} on port {self.port}")
        self._stop_event.set()  # Signal the thread to stop
        self.running = False

    def start_heartbeat_thread(self):
        heartbeat_thread = threading.Thread(target=self.heartbeat_thread, daemon=True)
        heartbeat_thread.start()

    def heartbeat_thread(self):
        while self.running:
            send_heartbeat(self.server_info)
            time.sleep(1800)  # 30 minutes

    def calculate_data_rates(self):
        outgoing = self.socket.get_outgoing_data_rate()
        incoming = self.socket.get_incoming_data_rate()
        return incoming, outgoing

    # print(f"Outgoing data rate: {outgoing_kbps:.2f} KB/s")
    # print(f"Incoming data rate: {incoming_kbps:.2f} KB/s")

    def start_monitoring(self):
        monitor_thread = threading.Thread(target = self.calculate_data_rates)
        monitor_thread.daemon = True  # Thread will exit when main program ends
        monitor_thread.start()

    def cleanup(self):
        """Generic cleanup routine"""
        self.socket.is_closed = True
        self.log.info(f"Cleaning up {self.server_type} server on port {self.port}")
        self.running = False
        if hasattr(self, 'socket'):
            self.socket.close()
        self.log.info(f"{self.server_type} server on port {self.port} cleaned up")

    @staticmethod
    def shutdown_all_pools():
        """Shutdown all worker thread pools gracefully."""
        # Shutdown UDP handler pool
        if UDPNetworkHandler._worker_pool:
            UDPNetworkHandler._worker_pool.shutdown(wait=False)
            UDPNetworkHandler._worker_pool = None
        # Shutdown CM UDP handler pool
        if UDPNetworkHandlerCM._worker_pool:
            UDPNetworkHandlerCM._worker_pool.shutdown(wait=False)
            UDPNetworkHandlerCM._worker_pool = None


class TCPNetworkHandler(NetworkHandler):
    def __init__(self, in_config, port, server_type = ""):
        disable_rate_limit_var=False

        if server_type == "ContentServer":
            disable_rate_limit_var=True

        self.serversocket = emu_socket.ImpSocket(disable_rate_limit=disable_rate_limit_var)

        NetworkHandler.__init__(self, self.serversocket, in_config, port, server_type)
        self.port = port
        self.config = in_config
        self.address = None

    def run(self):
        self.serversocket.bind((globalvars.server_ip, int(self.port)))
        self.serversocket.listen(5)
        while self.running and self.socket.is_closed is not True:
            try:
                client_socket, client_address = self.serversocket.accept()
            except:
                continue  # we ignore the attempted accept on closed socket
            if client_address is not None:
                server_thread = threading.Thread(target = self.handle_client, args = (client_socket, client_address))
                server_thread.start()


class UDPNetworkHandler(NetworkHandler):
    # Class-level thread pool shared across all UDP handlers
    _worker_pool = None
    _pool_lock = threading.Lock()

    @classmethod
    def _get_worker_pool(cls):
        """Get or create the shared worker thread pool."""
        if cls._worker_pool is None:
            with cls._pool_lock:
                if cls._worker_pool is None:
                    max_workers = min(16, (os.cpu_count() or 4) * 2)
                    cls._worker_pool = ThreadPoolExecutor(
                        max_workers=max_workers,
                        thread_name_prefix="udp_worker"
                    )
        return cls._worker_pool

    def __init__(self, in_config, port, server_type = ""):
        disable_rate_limit_var=False

        if server_type == "ContentServer":
            disable_rate_limit_var=True
        self.serversocket = emu_socket.ImpSocket("udp", disable_rate_limit=disable_rate_limit_var)


        super().__init__(self.serversocket, in_config, port, server_type)
        self.port = port
        self.config = in_config
        self.worker_pool = self._get_worker_pool()

    def run(self):
        self.serversocket.bind((globalvars.server_ip, int(self.port)))
        while self.running and self.socket.is_closed is not True:
            try:
                data, address = self.serversocket.recvfrom(16384)
            except Exception as e:
                time.sleep(0.1)
                continue  # we ignore the 'attempted recv on closed socket
            if address is not None:
                # Submit to thread pool instead of spawning threads
                try:
                    self.worker_pool.submit(self.handle_client, data, address)
                except Exception as e:
                    self.log.error(f"Failed to submit to worker pool: {e}")

    def handle_client(self, data, address):
        raise NotImplementedError("handle_client method must be implemented in derived classes")


class UDPNetworkHandlerCM(NetworkHandler):
    # Class-level thread pool shared across all CM UDP handlers
    # This prevents unbounded thread spawning that causes instability with 3+ clients
    _worker_pool = None
    _pool_lock = threading.Lock()

    @classmethod
    def _get_worker_pool(cls):
        """Get or create the shared worker thread pool."""
        if cls._worker_pool is None:
            with cls._pool_lock:
                if cls._worker_pool is None:  # Double-check after acquiring lock
                    # Pool size: 4x CPU cores, capped at 32 threads
                    max_workers = min(32, (os.cpu_count() or 4) * 4)
                    cls._worker_pool = ThreadPoolExecutor(
                        max_workers=max_workers,
                        thread_name_prefix="cm_udp_worker"
                    )
        return cls._worker_pool

    def __init__(self, in_config, port, server_type = ""):
        self.serversocket = emu_socket.ImpSocket("udp")
        super().__init__(self.serversocket, in_config, port, server_type)
        self.port = port
        self.config = in_config
        self.packet_buffer = {}
        # Get reference to shared worker pool
        self.worker_pool = self._get_worker_pool()

    def run(self):
        self.serversocket.bind((self.config['server_ip'], int(self.port)))
        while self.running:
            try:
                data, address = self.serversocket.recvfrom(16384)
            except Exception as e:
                time.sleep(0.1)
                continue  # we ignore the 'attempted recv on closed socket
            if address is not None:
                # Submit to thread pool instead of spawning new thread
                # This caps thread count and prevents thread explosion
                try:
                    self.worker_pool.submit(self.process_packet, data, address)
                except Exception as e:
                    self.log.error(f"Failed to submit packet to worker pool: {e}")

    def process_packet(self, data: bytes, address):
        from steam3.cm_packet_utils import CMPacket
        #self.serversocket.connect(address)
        if data.startswith(b'\xff\xff\xff\xff'):
            return # FIXME deal with the matchmaking packets!
        packet = CMPacket().parse(data)
        if packet.split_pkt_cnt > 1:
            self.handle_split_packet(packet, address)
        else:
            self.handle_client(data, address)

    def handle_split_packet(self, packet, address):
        from steam3.cm_packet_utils import CMPacket
        key = (address[0], packet.seq_of_first_pkt)

        if key not in self.packet_buffer:
            self.packet_buffer[key] = []

        self.packet_buffer[key].append(packet)

        total_data_len = sum(pkt.data_len for pkt in self.packet_buffer[key])
        total_packet_size = sum(len(pkt.data) for pkt in self.packet_buffer[key])

        if len(self.packet_buffer[key]) == packet.split_pkt_cnt and total_packet_size == packet.data_len:
            combined_data = b''.join(pkt.data for pkt in self.packet_buffer[key])
            complete_packet = CMPacket(
                    header = packet.magic,
                    size = packet.size,
                    packetid = packet.packetid,
                    priority_level = packet.priority_level,
                    destination_id = packet.destination_id,
                    source_id = packet.source_id,
                    sequence_num = packet.sequence_num,
                    last_recv_seq = packet.last_recv_seq,
                    split_pkt_cnt = 1,
                    seq_of_first_pkt = packet.sequence_num,
                    data_len = total_data_len,
                    data = combined_data
            )

            del self.packet_buffer[key]
            serialized_packet = complete_packet.serialize()
            self.handle_client(serialized_packet, address)


class TCPNetworkHandlerCM(NetworkHandler):
    # Class-level dictionary to track connection attempts
    connection_attempts = defaultdict(deque)
    attempts_lock = threading.Lock()  # Lock for thread safety
    blacklist_log_cache = defaultdict(float)  # Tracks last log time for each blacklisted IP

    def __init__(self, in_config, port, server_type = ""):
        # Initialize TCP socket instead of UDP
        self.serversocket = emu_socket.ImpSocket()
        super().__init__(self.serversocket, in_config, port, server_type)
        self.port = port
        self.config = in_config
        self.address = None
        self.packet_buffer = {}

    def run(self):
        # Bind and start listening for TCP connections
        self.serversocket.bind((self.config['server_ip'], int(self.port)))
        self.serversocket.listen(5)  # Listen for incoming connections

        while self.running:
            try:
                client_socket, client_address = self.serversocket.accept()  # Accept incoming connection
            except Exception as e:
                continue  # Ignore errors while accepting new connections

            if client_address is not None:
                server_thread = threading.Thread(target=self.handle_client_connection, args=(client_socket, client_address), daemon=True)
                server_thread.start()

    def handle_client_connection(self, client_socket, address):
        self.packet_buffer[address] = b''

        # Wrap the accepted socket in an ImpSocket for enhanced error handling.
        imp_sock = emu_socket.ImpSocket(client_socket)
        imp_sock.address = address

        self.log.info(f"Accepted connection from {address}")
        # Just call once
        self.handle_client(client_socket, address)
        # Once handle_client returns, the connection is closed
        client_socket.close()
        self.log.info(f"Connection to {address} closed")


    """def process_packet(self, data, address, client_socket):
        
        # Add received data to buffer
        self.packet_buffer[address] += data

        # Extract the packet length from the start of the buffer (e.g., first 4 bytes for length)
        if len(self.packet_buffer[address]) >= 4:
            total_packet_length = int.from_bytes(self.packet_buffer[address][:4], byteorder = 'little')

            # Check if we have received the full packet
            if len(self.packet_buffer[address]) >= total_packet_length:
                # Extract the complete packet (including TCP header if it's TCP)
                complete_packet = self.packet_buffer[address][:total_packet_length]
                remaining_data = self.packet_buffer[address][total_packet_length:]

                # Pass the complete packet (including TCP header) to handle_client
                self.handle_client(complete_packet, address)

                # Save any leftover data for future packets
                self.packet_buffer[address] = remaining_data"""