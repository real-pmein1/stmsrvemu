import threading, logging, struct, binascii, os, time
import socket as pysocket
import utilities
import steam
import globalvars
import steamemu.logger

import emu_socket


log = logging.getLogger("AdminSRV")

class administrationservers(threading.Thread):
    def __init__(self, port, config):
        threading.Thread.__init__(self)
        self.port = int(port)
        self.config = config
        self.tcp_socket = emu_socket.ImpSocket()
        self.udp_socket = pysocket.socket(pysocket.AF_INET, pysocket.SOCK_DGRAM)
        self.server_type = "adminserver"
        self.server_info = {
            'ip_address': globalvars.serverip,
            'port': int(self.port),
            'server_type': self.server_type,
            'timestamp': int(time.time())
        }
        
        thread2 = threading.Thread(target=self.heartbeat_thread)
        thread2.daemon = True
        thread2.start()
        
    def heartbeat_thread(self):       
        while True:
            send_heartbeat(self.server_info)
            time.sleep(1800) # 30 minutes
            
    def run(self):        
        self.tcp_socket.bind((globalvars.serverip, self.port))
        self.tcp_socket.listen(5)

        while True:
            (clientsocket, address) = self.tcp_socket.accept()
            threading.Thread(target=self.handle_clientTCP, args=(clientsocket, address)).start()
            threading.Thread(target=self.handle_clientUDP).start()

    def handle_clientTCP(self, clientsocket, address):
        clientid = str(address) + ": "
        log.info(clientid + "Connected to Administration Server")
        
        msg = clientsocket.recv(1024)
        #clientsocket.send_withlen(reply)
        log.warning("Unknown message: " + binascii.b2a_hex(msg))

        clientsocket.close()
        log.info(clientid + "Disconnected from Administration Server")

    def handle_clientUDP(self):
        self.udp_socket.bind((globalvars.serverip, self.port))

        while True:
            msg, address = self.udp_socket.recvfrom(1024)
            
            clientid = str(address) + ": "
            log.info(clientid + "Connected to Administration Server")
            
            #clientsocket.send_withlen(reply)
            
            log.warning("Unknown message: " + binascii.b2a_hex(msg))
            
            #log.info(clientid + "Disconnected from Administration Server")
