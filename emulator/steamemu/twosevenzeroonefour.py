import threading, logging, struct, binascii

import steam
import globalvars

from steamemu.config import read_config

config = read_config()

class twosevenzeroonefour(threading.Thread):
    def __init__(self, socket, config) :
        threading.Thread.__init__(self)
        self.socket = socket
        #self.address = address
        self.config = config

    def run(self):
        log = logging.getLogger("27014")
        clientid = str(config["server_ip"]) + ": "
        log.info(clientid + "Connected to 27014 Server")
        #data, addr = self.socket.recvfrom(1280)
        #log.info(clientid + ("Received message: %s, from %s" % (globalvars.data, globalvars.addr)))
        #self.socket.sendto(self.socket, "\x00", globalvars.addr)

        

        #self.socket.close()
        log.info (clientid + "Disconnected from 27014 Server")
