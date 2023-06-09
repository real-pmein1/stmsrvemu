import threading, logging, struct, binascii

import steam

from steamemu.config import read_config

config = read_config()

class udpserver(threading.Thread):
    def __init__(self, socket, config) :
        threading.Thread.__init__(self)
        self.socket = socket
        self.config = config

    def run(self):
        log = logging.getLogger("csersrv")
        clientid = str(config["server_ip"]) + ": "
        log.info(clientid + "Connected to CSER Server")

        

        self.socket.close()
        log.info (clientid + "Disconnected from CSER Server")
