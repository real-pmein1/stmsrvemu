import threading, logging, struct, binascii, time, socket, ipaddress, os.path, ast, csv
import os
import steam
import config
import steamemu.logger
import globalvars
from steamemu.config import read_config

config = read_config()

class cserserver(threading.Thread):
    serversocket = None

    def __init__(self, host, port):
        #threading.Thread.__init__(self)
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        serversocket = self.socket

    def start(self):
        
        self.socket.bind((self.host, self.port))

        while True:
            #recieve a packet
            data, address = self.socket.recvfrom(1280)
            # Start a new thread to process each packet
            threading.Thread(target=self.process_packet, args=(data, address)).start()

    def process_packet(self, data, address):
        log = logging.getLogger("harvestsrv")
        # Process the received packet
        clientid = str(address) + ": "
        log.info(clientid + "Connected to Harvest MiniDump Collection Server")
        log.debug(clientid + ("Received message: %s, from %s" % (data, address)))
        ipstr = str(address)
        ipstr1 = ipstr.split('\'')
        ipactual = ipstr1[1]
        log.info(clientid + data)
        #if data.startswith("e"):  # 65
        #    self.socket.sendto("\xFF\xFF\xFF\xFF\x68\x01"+"thank you\n\0", address)
        #else:
        #    log.info("Unknown Harvester command: %s" % data)



