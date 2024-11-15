import logging
import threading
import time

import globalvars
import utilities.socket as emu_socket
from listmanagers import dirlistmanager
from listmanagers.serverlist_utilities import send_heartbeat

# Global variables to track incoming and outgoing data size
incoming_data_size = 0
outgoing_data_size = 0


# log = logging.getLogger("NetHandler")


class NetworkHandler(threading.Thread):

    # global manager
    def __init__(self, in_socket, in_config, port, server_type = ""):

        threading.Thread.__init__(self)
        self.socket = in_socket
        self.config = in_config
        self._stop_event = threading.Event()  # Add an event to signal thread stopping
        self.port = port
        # Initialize the logger with server_type if provided, otherwise use a default name
        if server_type:
            self.log = logging.getLogger(server_type)
        else:
            self.log = logging.getLogger("NetworkHandler")

        globalvars.servers.append(self)
        self.running = True

        no_dir_entry_server_types = {
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

        if server_type in no_dir_entry_server_types:
            pass
        else:
            self.server_type = server_type
            if globalvars.public_ip == "0.0.0.0":
                server_ip = globalvars.server_ip_b
            else:
                server_ip = globalvars.public_ip_b
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
                    self.log.error("Server Not added to list! Please contact support.")
                    return

    def run(self):
        try:
            super().run()  # Call the parent run method which contains the main loop
        except Exception as e:
            self.log.error(f"{self.__class__.__name__} Exception Occurred:", exc_info = True)

    def stop(self):
        """Stop the server gracefully."""
        self.log.info(f"Stopping {self.__class__.__name__} on port {self.port}")
        self._stop_event.set()  # Signal the thread to stop
        self.running = False

    def start_heartbeat_thread(self):
        thread2 = threading.Thread(target = self.heartbeat_thread)
        thread2.daemon = True
        thread2.start()

    def heartbeat_thread(self):
        while True:
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
        self.log.info(f"Cleaning up {self.server_type} server on port {self.port}")
        self.running = False
        if hasattr(self, 'socket'):
            self.socket.close()
        self.log.info(f"{self.server_type} server on port {self.port} cleaned up")


class TCPNetworkHandler(NetworkHandler):
    def __init__(self, in_config, port, server_type = ""):
        self.serversocket_tcp = emu_socket.ImpSocket()
        NetworkHandler.__init__(self, self.serversocket_tcp, in_config, port, server_type)
        self.port = port
        self.config = in_config
        self.address = None

    def run(self):
        self.serversocket_tcp.bind((globalvars.server_ip, int(self.port)))
        self.serversocket_tcp.listen(5)

        while True:
            try:
                client_socket, client_address = self.serversocket_tcp.accept()
            except:
                continue  # we ignore the attempted accept on closed socket
            if client_address is not None:
                server_thread = threading.Thread(target = self.handle_client, args = (client_socket, client_address))
                server_thread.start()


class UDPNetworkHandler(NetworkHandler):
    def __init__(self, in_config, port, server_type = ""):
        self.serversocket = emu_socket.ImpSocket("udp")
        NetworkHandler.__init__(self, self.serversocket, in_config, port, server_type)
        self.port = port
        self.config = in_config

    def run(self):
        self.serversocket.bind((globalvars.server_ip, int(self.port)))
        while True:
            try:
                data, address = self.serversocket.recvfrom(16384)
            except Exception as e:
                continue  # we ignore the 'attempted recv on closed socket

            server_thread = threading.Thread(target = self.handle_client, args = (data, address))
            server_thread.start()

    def handle_client(self, data, address):
        raise NotImplementedError("handle_client method must be implemented in derived classes")


class UDPNetworkHandlerCM(NetworkHandler):
    def __init__(self, in_config, port, server_type = ""):
        self.serversocket = emu_socket.ImpSocket("udp")
        NetworkHandler.__init__(self, self.serversocket, in_config, port, server_type)
        self.port = port
        self.config = in_config
        self.packet_buffer = {}

    def run(self):
        self.serversocket.bind((self.config['server_ip'], int(self.port)))
        while True:
            try:
                data, address = self.serversocket.recvfrom(16384)
            except Exception as e:
                continue  # we ignore the 'attempted recv on closed socket
            if address is not None:
                server_thread = threading.Thread(target = self.process_packet, args = (data, address))
                server_thread.start()

    def process_packet(self, data, address):
        from steam3.cm_packet_utils import CMPacket
        #self.serversocket.connect(address)
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
    def __init__(self, in_config, port, server_type = ""):
        # Initialize TCP socket instead of UDP
        self.serversocket = emu_socket.ImpSocket("tcp")
        NetworkHandler.__init__(self, self.serversocket, in_config, port, server_type)
        self.port = port
        self.config = in_config
        self.packet_buffer = {}

    def run(self):
        # Bind and start listening for TCP connections
        self.serversocket.bind((self.config['server_ip'], int(self.port)))
        self.serversocket.listen(5)  # Listen for incoming connections

        while True:
            try:
                client_socket, address = self.serversocket.accept()  # Accept incoming connection
            except Exception as e:
                continue  # Ignore errors while accepting new connections

            if address is not None:
                server_thread = threading.Thread(target = self.handle_client_connection, args = (client_socket, address))
                server_thread.start()

    def handle_client_connection(self, client_socket, address):
        """ Handle incoming TCP data from a connected client. """
        self.packet_buffer[address] = b''  # Initialize buffer for this client

        while True:
            try:
                data = client_socket.recv(16384)
                if not data:
                    break  # Connection closed by the client
                self.process_packet(data, address, client_socket)
            except Exception as e:
                continue  # Ignore socket errors

        client_socket.close()

    def process_packet(self, data, address, client_socket):
        """ Process incoming data and handle split TCP packets. """
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
                self.packet_buffer[address] = remaining_data