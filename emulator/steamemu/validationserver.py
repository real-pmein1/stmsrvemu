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

from serverlist_utilities import remove_from_dir, heartbeat
log = logging.getLogger("validationsrv")


class validationserver(threading.Thread):
    
    def __init__(self, port, config):
        self.server_type = "validationserver"
        threading.Thread.__init__(self)
        self.port = int(port)
        self.config = config
        self.socket = emu_socket.ImpSocket()

        # Register the cleanup function using atexit
        #atexit.register(send_removal(globalvars.serverip, int(self.port), globalvars.cs_region))
        
        thread2 = threading.Thread(target=self.heartbeat_thread)
        thread2.daemon = True
        thread2.start()

    def heartbeat_thread(self):       
        while True:
            heartbeat(globalvars.serverip, self.port, self.server_type )
            time.sleep(1800) # 30 minutes
            
    def run(self):        
        self.socket.bind((globalvars.serverip, self.port))
        self.socket.listen(5)

        while True:
            (clientsocket, address) = self.socket.accept()
            threading.Thread(target=self.handle_client, args=(clientsocket, address)).start()

    def handle_client(self, clientsocket, address):
        #threading.Thread.__init__(self)
        clientid = str(address) + ": "
         
        log.info(clientid + "Connected to Validation Server")
               
        msg = clientsocket.recv(256)
        log.debug(binascii.b2a_hex(msg))
        
       # if msg == "\x00\x3e\x7b\x11" :
           # clientsocket.send("\x01") # handshake confirmed
           # msg = clientsocket.recv(1024)
            
        command = msg[0]
        log.info(binascii.b2a_hex(command))
        log.info(binascii.b2a_hex(msg))
        reply = "\x0F" + utilities.encodeIP(address)
        clientsocket.send(reply)
        msg = clientsocket.recv(1512)
        log.debug(binascii.b2a_hex(msg))            
        command = msg[0]
        log.info(binascii.b2a_hex(command))
        log.info(binascii.b2a_hex(msg))
        #clientsocket.send(msg)
        #msg = clientsocket.recv(1512)
        #log.info(binascii.b2a_hex(command))
        #log.info(binascii.b2a_hex(msg))
        clientsocket.close()