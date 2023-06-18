import threading, logging, struct, binascii, time, atexit, ipaddress, os.path, ast, csv
import socket as pysocket
import os
import config
import utilities
import steam
import globalvars
import emu_socket
import steamemu.logger
import serverlist_utilities
from serverlist_utilities import remove_from_dir, send_heartbeat

log = logging.getLogger("validationsrv")

class validationserver(threading.Thread):
    
    def __init__(self, port, config):
        threading.Thread.__init__(self)
        self.port = int(port)
        self.config = config
        self.socket = emu_socket.ImpSocket()
        self.server_type = "validationserver"
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

        command = clientsocket.recv(13)

        log.debug(":" + binascii.b2a_hex(command[1:5]) + ":")
        log.debug(":" + binascii.b2a_hex(command) + ":")

        if command[1:5] == "\x00\x00\x00\x04" :

            clientsocket.send("\x01" + pysocket.inet_aton(globalvars.serverip)) #CRASHES IF NOT 01

            command = clientsocket.recv_withlen()
            print(len(command))
            
            unknown1 = command[6:8] + command[4:6] + command[2:4] + command[0:2] + "\x01"
            tms = utilities.get_nanoseconds_since_time0()
            steamid = binascii.a2b_hex("0000" + "80808000" + "00000000") #CRASHES IF NOT 00
            unknown_data = bytearray(0x80)
            for ind in range(1, 9):
                start_index = (ind - 1) * 16
                value = (ind * 16) + ind
                unknown_data[start_index:start_index+16] = bytes([value] * 16)

            reply = unknown1 + str(tms) + steamid + unknown_data
            replylen = struct.pack(">H", len(reply))
            clientsocket.send(replylen + reply)