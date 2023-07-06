import threading, logging, struct, binascii, time, atexit, socket, ipaddress, os.path, ast, csv
import os
import config
import utilities
import steamemu.logger
import globalvars
import serverlist_utilities
from serverlist_utilities import send_heartbeat, remove_from_dir

class trackerserver(threading.Thread) :

    def __init__(self, host, port) :
        #threading.Thread.__init__(self)
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_type = "trackerserver"
        self.server_info = {
                    'ip_address': globalvars.serverip,
                    'port': int(self.port),
                    'server_type': self.server_type,
                    'timestamp': int(time.time())
                }
        # Register the cleanup function using atexit
        # atexit.register(remove_from_dir(globalvars.serverip, int(self.port), self.server_type))             
        thread2 = threading.Thread(target=self.heartbeat_thread)
        thread2.daemon = True
        thread2.start()
        
    def heartbeat_thread(self) :       
        while True :
            send_heartbeat(self.server_info)
            time.sleep(1800) # 30 minutes
            
    def start(self) :     
        self.socket.bind((self.host, self.port))
        while True : # recieve a packet
            data, address = self.socket.recvfrom(1280) # Start a new thread to process each packet
            threading.Thread(target=self.process_packet, args=(data, address)).start()

    def process_packet(self, data, address) :
        log = logging.getLogger("TrackerSRV")
        clientid = str(address) + ": "
        log.info(clientid + "Connected to Tracker Server")
        log.debug(clientid + ("Received message: %s, from %s" % (data, address)))
        ipstr = str(address)
        ipstr1 = ipstr.split('\'')
        ipactual = ipstr1[1]
        log.info(clientid + data)
        #if data.startswith("e"):  # 65
        #    self.socket.sendto("\xFF\xFF\xFF\xFF\x68\x01"+"thank you\n\0", address)
        #else:
        #    log.info("Unknown Harvester command: %s" % data)



