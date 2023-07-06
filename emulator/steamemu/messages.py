import threading, logging, struct, binascii, time, socket, atexit, ipaddress, os.path, ast
import os
import config
import utilities
import steamemu.logger
import globalvars
import serverlist_utilities
from serverlist_utilities import send_heartbeat, remove_from_dir

class messagesserver(threading.Thread):

    def __init__(self, host, port):
        #threading.Thread.__init__(self)
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_type = "messagesserver"
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
        
    def heartbeat_thread(self):       
        while True:
            send_heartbeat(self.server_info)
            time.sleep(1800) # 30 minutes
            
    def start(self):        
        self.socket.bind((self.host, self.port))
        while True: # recieve a packet
            data, address = self.socket.recvfrom(1280) # Start a new thread to process each packet
            threading.Thread(target=self.process_packet, args=(data, address)).start()

    def process_packet(self, data, address):
        log = logging.getLogger("CMSRV")
        clientid = str(config["server_ip"]) + ": "
        log.info(clientid + "Connected to Message Server")
        log.debug(clientid + ("Received message: %s, from %s" % (data, address)))

        message = binascii.b2a_hex(data)
        if message.startswith("56533031") : # VS01
            friendsrecheader = message[0:8]
            friendsrecsize = message[8:12]
            friendsrecfamily = message[12:14]
            friendsrecversion = message[14:16]
            friendsrecto = message[16:24]
            friendsrecfrom = message[24:32]                    
            friendsrecsent = message[32:40]
            friendsrecreceived = message[40:48]
            friendsrecflag = message[48:56]
            friendsrecsent2 = message[56:64]
            friendsrecsize2 = message[64:72]
            friendsrecdata = message[72:]
            
        if friendsrecfamily == "01": #SendMask
            friendsrepheader = friendsrecheader
            friendsrepsize = 4
            friendsrepfamily = 2
            friendsrepversion = friendsrecversion
            friendsrepto = friendsrecfrom
            friendsrepfrom = friendsrecto
            friendsrepsent = 1
            friendsrepreceived = friendsrecsent
            friendsrepflag = 0
            friendsrepsent2 = 0
            friendsrepsize2 = 0
            friendsrepdata = 0 # data empty on this packet, size is from friendsrepsize (0004)
            friendsmaskreply1 = friendsrepheader + format(friendsrepsize, '04x') + format(friendsrepfamily, '02x') + friendsrepversion + friendsrepto + friendsrepfrom + format(friendsrepsent, '08x') + friendsrepreceived + format(friendsrepflag, '08x') + format(friendsrepsent2, '08x') + format(friendsrepsize2, '08x') + format(friendsrepdata, '08x')
            #print(friendsmaskreply1)
            friendsmaskreply2 = binascii.a2b_hex(friendsmaskreply1)
            #print(friendsmaskreply2)
            serversocket.sendto(friendsmaskreply2, address)
        elif friendsrecfamily == "03": #SendID
            friendsrepheader = friendsrecheader
            friendsrepsize = 0
            friendsrepfamily = 4
            friendsrepversion = friendsrecversion
            
            friendsrepid1 = int(round(time.time()))
            friendsrepid2 = struct.pack('>I', friendsrepid1)
            friendsrepto = binascii.b2a_hex(friendsrepid2)
            #friendsrepto = friendsrecfrom
            
            friendsrepfrom = friendsrecto
            friendsrepsent = 2
            friendsrepreceived = friendsrecsent
            friendsrepflag = 1
            friendsrepsent2 = 2
            friendsrepsize2 = 0
            friendsrepdata = 0
            
            friendsidreply1 = friendsrepheader + format(friendsrepsize, '04x') + format(friendsrepfamily, '02x') + friendsrepversion + friendsrepto + friendsrepfrom + format(friendsrepsent, '08x') + friendsrepreceived + format(friendsrepflag, '08x') + format(friendsrepsent2, '08x') + format(friendsrepsize2, '08x') + format(friendsrepdata, '08x')
            print(friendsidreply1)
            friendsidreply2 = binascii.a2b_hex(friendsidreply1)
            print(friendsidreply2)
            serversocket.sendto(friendsidreply2, address)
        elif friendsrecfamily == "07": #ProcessHeartbeat
            if not friendsrecsize == "0000":
                friendsreqreq = friendsrecdata[0:4]
                friendsreqid = friendsrecdata[4:8]
                friendsreqid2 = friendsrecdata[8:12]
                friendsrequnknown = friendsrecdata[12:16]
                friendsreqdata = friendsrecdata[16:]
                friendsreqheader = friendsrecheader
        #self.socket.close()
        log.info (clientid + "Disconnected from Message Server")         

