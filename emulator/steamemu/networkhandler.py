import threading
import logging
import socket
import time
import emu_socket

from serverlist_utilities import remove_from_dir, send_heartbeat

log = logging.getLogger("MasterNetworkHandler")

class NetworkHandler(threading.Thread):
    def __init__(self, socket, config, port, server_type=""):
        threading.Thread.__init__(self)
        self.socket = socket
        self.config = config
        self.port = int(port)
        if server_type != "":
            self.server_type = server_type
            self.server_info = {
                'ip_address': self.config['server_ip'],
                'port': self.port,
                'server_type': self.server_type,
                'timestamp': int(time.time())
            }
            self.start_heartbeat_thread()

    def start_heartbeat_thread(self):
        thread2 = threading.Thread(target=self.heartbeat_thread)
        thread2.daemon = True
        thread2.start()

    def heartbeat_thread(self):
        while True:
            send_heartbeat(self.server_info)
            time.sleep(1800)  # 30 minutes

    def handle_client(self, *args):
        raise NotImplementedError("handle_client method must be implemented in derived classes")

class TCPNetworkHandler(NetworkHandler):
    def __init__(self, config, port, server_type=""):
        NetworkHandler.__init__(self, emu_socket.ImpSocket(), config, port, server_type)

    def run(self):
        self.socket.bind((self.config['server_ip'], self.port))
        self.socket.listen(5)

        while True:
            (clientsocket, address) = self.socket.accept()
            server_thread = threading.Thread(target=self.handle_client, args=(clientsocket, address)).start()

class UDPNetworkHandler(NetworkHandler):
    def __init__(self, config, port, server_type=""):
        udpsocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        NetworkHandler.__init__(self, udpsocket, config, port, server_type)

    def run(self):
        self.socket.bind((self.config['server_ip'], self.port))

        while True:
            data, address = self.socket.recvfrom(2048)
            server_thread = threading.Thread(target=self.handle_client, args=(data, address)).start()
            
class TCPUDPNetworkHandler(TCPNetworkHandler, UDPNetworkHandler):
    def __init__(self, config, port, server_type=""):
        TCPNetworkHandler.__init__(self, config, port, server_type)
        UDPNetworkHandler.__init__(self, config, port, server_type)

    def handle_client(self, *args):
        if isinstance(args[0], socket.socket):
            # Handling TCP data
            clientsocket, address = args
            # Process TCP data using clientsocket and address

        elif isinstance(args[0], bytes):
            # Handling UDP data
            data, address = args
            # Process UDP data using data and address

        else:
            raise ValueError("Invalid argument type passed to handle_client")
