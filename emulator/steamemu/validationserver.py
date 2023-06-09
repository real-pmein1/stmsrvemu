import threading
import logging
import struct
import binascii
import os
import time
import atexit
import utilities
import steam
import globalvars
import serverlist_utilities
import emu_socket
import steamemu.logger
import socket as pysocket

from serverlist_utilities import heartbeat, remove_from_dir

class validationserver(threading.Thread):
    log = logging.getLogger("validationsrv")
    
    def __init__(self, port, config):
        threading.Thread.__init__(self)
        self.port = int(port)
        self.config = config
        self.tcp_socket = emu_socket.ImpSocket()
        self.udp_socket = pysocket.socket(pysocket.AF_INET, pysocket.SOCK_DGRAM)

    def run(self):
        
        self.tcp_socket.bind((globalvars.serverip, self.port))
        self.tcp_socket.listen(5)
       
        self.handle_clientUDP()  # Call the UDP client handling within the run method

        while True:
            (clientsocket, address) = self.tcp_socket.accept()
            threading.Thread(target=self.handle_clientTCP, args=(clientsocket, address)).start()

    def handle_clientTCP(self, clientsocket, address):
        clientid = str(address) + ": "
        self.log.info(clientid + "Connected to Validation Server")
        
        msg = clientsocket.recv(1024)
        # clientsocket.send_withlen(reply)
        self.log.info("Unknown message: " + binascii.b2a_hex(msg))

        clientsocket.close()
        self.log.info(clientid + "Disconnected from Validation Server")

    def handle_clientUDP(self):
        self.udp_socket.bind((globalvars.serverip, self.port))

        while True:
            msg, address = self.udp_socket.recvfrom(1024)
            
            clientid = str(address) + ": "
            self.log.info(clientid + "Connected to Validation Server")
            self.log.info("Unknown message: " + binascii.b2a_hex(msg))
            # clientsocket.send_withlen(reply)

