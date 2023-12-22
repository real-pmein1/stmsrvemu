import sys
import binascii, ConfigParser, threading, logging, socket, time, os, shutil, zipfile, tempfile, types, ast, filecmp, requests, subprocess, ipcalc, struct

import steam
import globalvars

from steamemu.config import read_config

config = read_config()

class cmenc(threading.Thread):
    def __init__(self, port, serverobject, config):
        self.port = int(port)
        self.serverobject = serverobject         
        self.config = config.copy()
        self.config["port"] = port
        threading.Thread.__init__(self)

    def run(self):
        log = logging.getLogger("cmsrv")
        clientid = str(config["server_ip"]) + ": "
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        serversocket = steam.ImpSocket(sock)
        serversocket.bind((config["server_ip"], self.port))
        #serversocket.listen(5)

        #log.info("UDP Server Listening on port " + str(self.port))

        while True :
            globalvars.data, globalvars.addr = serversocket.recvfrom(1280)
            #print("Received message: %s on port %s" % (globalvars.data, self.port))
            #self.serverobject(serversocket, self.config).start();
            dedsrv_port = globalvars.addr[1]
            #print(dedsrv_port)
            if self.port == 27017 :
                log = logging.getLogger("cmsecsrv")
                clientid = str(globalvars.addr) + ": "
                log.info(clientid + "Connected to CM Server (encrypted)")
                log.debug(clientid + ("Received message: %s, from %s" % (globalvars.data, globalvars.addr)))
                message = binascii.b2a_hex(globalvars.data)
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
                        serversocket.sendto(friendsmaskreply2, globalvars.addr)
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
                        serversocket.sendto(friendsidreply2, globalvars.addr)
                    elif friendsrecfamily == "07": #ProcessHeartbeat
                        if not friendsrecsize == "0000":
                            friendsreqreq = friendsrecdata[0:4]
                            friendsreqid = friendsrecdata[4:8]
                            friendsreqid2 = friendsrecdata[8:12]
                            friendsrequnknown = friendsrecdata[12:16]
                            friendsreqdata = friendsrecdata[16:]
                            friendsreqheader = friendsrecheader
                    
        log.info (clientid + "Disconnected from 27014 Server")
