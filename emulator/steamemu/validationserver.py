import threading, logging, struct, binascii, os, time, atexit
import utilities
import steam
import globalvars
import serverlist_utilities
import emu_socket
import steamemu.logger
from serverlist_utilities import heartbeat, remove_from_dir

class validationserver(threading.Thread):
    log = logging.getLogger("validationsrv")
    
    def __init__(self, port, config):
        threading.Thread.__init__(self)
        self.port = int(port)
        self.config = config
        self.socket = emu_socket.ImpSocket()
        self.server_type = "validationserver"

        #add function for cleanup when program exits
        #atexit.register(remove_from_dir(globalvars.serverip, int(self.port), self.server_type))

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
            threading.Thread(target=self.handle_client, args=(clientsocket, address)).start

    def handle_client(self, clientsocket, address):
        clientid = str(address) + ": "
        log.info(clientid + "Connected to User ID Validation Server ")
    
        msg = clientsocket.recv(4)
        log.warning("Recieved message! " + binascii.b2a_hex(msg))


        clientsocket.close()
        log.info(clientid + "Disconnected from User ID Validation Server")
