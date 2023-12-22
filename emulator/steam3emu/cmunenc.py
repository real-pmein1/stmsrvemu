import sys
import binascii, ConfigParser, threading, logging, socket, time, os, shutil, zipfile, tempfile, types, ast, filecmp, requests, subprocess, ipcalc, struct

import steam
import globalvars

from steamemu.config import read_config

config = read_config()

class cmunenc(threading.Thread):
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
            if self.port == 27014 :
                log = logging.getLogger("cmsrv")
                clientid = str(globalvars.addr) + ": "
                log.info(clientid + "Connected to CM Server (unencrypted)")
                log.debug(clientid + ("Received message: %s, from %s" % (globalvars.data, globalvars.addr)))
                message = binascii.b2a_hex(globalvars.data)
                if message.startswith("56533031") : # VS01
                    cmrecheader = message[0:8]
                    cmrecsize = message[8:12]
                    cmrecfamily = message[12:14]
                    cmrecversion = message[14:16]
                    cmrecto = message[16:24]
                    cmrecfrom = message[24:32]                    
                    cmrecsent = message[32:40]
                    cmrecreceived = message[40:48]
                    cmrecflag = message[48:56]
                    cmrecsent2 = message[56:64]
                    cmrecsize2 = message[64:72]
                    cmrecdata = message[72:]
                    
                    if cmrecfamily == "01": #SendMask
                        cmrepheader = cmrecheader
                        cmrepsize = 4
                        cmrepfamily = 2
                        cmrepversion = cmrecversion
                        cmrepto = cmrecfrom
                        cmrepfrom = cmrecto
                        cmrepsent = 1
                        cmrepreceived = cmrecsent
                        cmrepflag = 0
                        cmrepsent2 = 0
                        cmrepsize2 = 0
                        cmrepdata = 0 # data empty on this packet, size is from cmrepsize (0004)
                        cmmaskreply1 = cmrepheader + format(cmrepsize, '04x') + format(cmrepfamily, '02x') + cmrepversion + cmrepto + cmrepfrom + format(cmrepsent, '08x') + cmrepreceived + format(cmrepflag, '08x') + format(cmrepsent2, '08x') + format(cmrepsize2, '08x') + format(cmrepdata, '08x')
                        #print(cmmaskreply1)
                        cmmaskreply2 = binascii.a2b_hex(cmmaskreply1)
                        #print(cmmaskreply2)
                        serversocket.sendto(cmmaskreply2, globalvars.addr)
                    elif cmrecfamily == "03": #SendID
                        cmrepheader = cmrecheader
                        cmrepsize = 0
                        cmrepfamily = 4
                        cmrepversion = cmrecversion
                        
                        cmrepid1 = int(round(time.time()))
                        cmrepid2 = struct.pack('>I', cmrepid1)
                        cmrepto = binascii.b2a_hex(cmrepid2)
                        #cmrepto = cmrecfrom
                        
                        cmrepfrom = cmrecto
                        cmrepsent = 2
                        cmrepreceived = cmrecsent
                        cmrepflag = 1
                        cmrepsent2 = 2
                        cmrepsize2 = 0
                        cmrepdata = 0
                        
                        cmidreply1 = cmrepheader + format(cmrepsize, '04x') + format(cmrepfamily, '02x') + cmrepversion + cmrepto + cmrepfrom + format(cmrepsent, '08x') + cmrepreceived + format(cmrepflag, '08x') + format(cmrepsent2, '08x') + format(cmrepsize2, '08x') + format(cmrepdata, '08x')
                        print(cmidreply1)
                        cmidreply2 = binascii.a2b_hex(cmidreply1)
                        print(cmidreply2)
                        serversocket.sendto(cmidreply2, globalvars.addr)
                    elif cmrecfamily == "07": #ProcessHeartbeat
                        #if not cmrecsize == "0000":
                        cmreqreq = cmrecdata[0:4]
                        cmreqid = cmrecdata[4:8]
                        cmreqid2 = cmrecdata[8:12]
                        cmrequnknown = cmrecdata[12:16]
                        cmreqdata = cmrecdata[16:]
                        cmreqheader = cmrecheader
                    
        log.info (clientid + "Disconnected from 27014 Server")
