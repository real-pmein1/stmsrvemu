import threading, logging, struct, binascii, time, socket, ipaddress, os.path, ast
import os
import steam
import config
import steamemu.logger
import globalvars

from steamemu.config import read_config

config = read_config()

class trackerserver(threading.Thread):

    def __init__(self, host, port):
        #threading.Thread.__init__(self)
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def start(self):
        
        self.socket.bind((self.host, self.port))

        while True:
            #recieve a packet
            data, address = self.socket.recvfrom(1280)
            # Start a new thread to process each packet
            threading.Thread(target=self.process_packet, args=(data, address)).start()

    def process_packet(self, data, address):
        log = logging.getLogger("trkserv")
        clientid = str(address) + ": "
        log.info(clientid + "Connected to Tracker Server")
        log.debug(clientid + ("Received message: %s, from %s" % (data, address)))

        #self.socket.close()
        log.info (clientid + "Disconnected from Tracker Server")
