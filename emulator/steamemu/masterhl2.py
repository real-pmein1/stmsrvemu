import sys
import binascii, ConfigParser, threading, logging, socket, time, os, shutil, zipfile, tempfile, types, ast, filecmp, requests, subprocess, ipcalc, struct

import steam
import globalvars

from steamemu.config import read_config

config = read_config()

class masterhl2(threading.Thread):
    def __init__(self, port, serverobject, config):
        self.port = int(port)
        self.serverobject = serverobject         
        self.config = config.copy()
        self.config["port"] = port
        threading.Thread.__init__(self)

    def run(self):
        log = logging.getLogger("hl2mstr")
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
            if self.port == 27011 :
                log = logging.getLogger("hl2mstr")
                clientid = str(globalvars.addr) + ": "
                log.info(clientid + "Connected to HL2 Master Server")
                log.debug(clientid + ("Received message: %s, from %s" % (globalvars.data, globalvars.addr)))
                if globalvars.data.startswith("1") : #31 QUERY
                    i = 0
                    srcdslist = []
                    #header = bytearray()
                    #header += b'\xFF\xFF\xFF\xFF\x66\x0A' #f
                    header = "\xff\xff\xff\xff\x66\x0a"
                    (a, b, c, d) = (globalvars.data[1], globalvars.data[2], globalvars.data[3], globalvars.data[4])
                    recv_ip = str(int(binascii.b2a_hex(a), 16)) + "." + str(int(binascii.b2a_hex(b), 16)) + "." + str(int(binascii.b2a_hex(c), 16)) + "." + str(int(binascii.b2a_hex(d), 16))
                    
                    reply = ""
                    for gameserver in globalvars.hl2serverlist:
                        if not isinstance(gameserver, int):
                            log.debug(clientid + ", ".join(gameserver))
                            if "proxy\\1" in globalvars.data and "hltv" in gameserver:
                                i = 0
                                ip_addr = struct.pack(">4B", int(gameserver[0].split(".")[0]), int(gameserver[0].split(".")[1]), int(gameserver[0].split(".")[2]), int(gameserver[0].split(".")[3]))
                                port = struct.pack(">H", 0)
                                for entry in gameserver:
                                    if gameserver[i] == "port":
                                        port = struct.pack(">H", int(gameserver[i+1]))
                                    i += 1
                                log.debug(clientid + "PROX_REQ")
                            elif "proxy\\1" in globalvars.data and not "hltv" in gameserver:
                                ip_addr = ""
                                port = ""
                                log.debug(clientid + "PROX_REQ_NO_DATA")
                            elif "hltv" in gameserver:
                                ip_addr = ""
                                port = ""
                                log.debug(clientid + "HLTV_ONLY")
                            else:
                                ip_addr = struct.pack(">4B", int(gameserver[0].split(".")[0]), int(gameserver[0].split(".")[1]), int(gameserver[0].split(".")[2]), int(gameserver[0].split(".")[3]))
                                log.debug(clientid + "NO_PROX")
                                i = 0
                                port = struct.pack(">H", 27015)
                                for entry in gameserver:
                                    if gameserver[i] == "port":
                                        port = struct.pack(">H", int(gameserver[i+1]))
                                    i += 1
                            reply = reply + ip_addr + port

                    reply = header + reply + struct.pack(">4BH", 0, 0, 0, 0, 0)
                    serversocket.sendto(reply, globalvars.addr)
                elif globalvars.data.startswith("q") : #71 SEND CHALLENGE NUM
                    header = b'\xFF\xFF\xFF\xFF\x73\x0A' #s
                    ipstr = str(globalvars.addr)
                    ipstr1 = ipstr.split('\'')
                    ipactual = ipstr1[1]
                    portstr = ipstr1[2]
                    portstr1 = portstr.split(' ')
                    portstr2 = portstr1[1].split(')')
                    portactual_temp = portstr2[0]
                    if not str(len(portactual_temp)) == 5 :
                        #portactual = "27015"
                        portactual = str(dedsrv_port)
                    else :
                        portactual = str(portactual_temp)
                    registered = 0
                    for server in globalvars.hl2serverlist :
                        if len(str(server)) > 5 :
                            #if server[0] == ipactual and (str(server[24]) == portactual or "27015" == portactual) :
                            if ipactual in server[0] and portactual in str(server[len(server) - 1]) :
                                log.info(clientid + "Already registered, sending challenge number %s" % str(server[4]))
                                challenge = struct.pack("I", int(server[4]))
                                registered = 1
                                break
                    if registered == 0 :
                        log.info(clientid + "Registering server, sending challenge number %s" % str(globalvars.hl2challengenum + 1))
                        challenge = struct.pack("I", globalvars.hl2challengenum + 1)
                        globalvars.hl2challengenum += 1
                    serversocket.sendto(header + challenge, globalvars.addr)
                elif globalvars.data.startswith("0") : #30 REGISTER/HEARTBEAT
                    serverdata1 = globalvars.data.split('\n')
                    serverdata2 = serverdata1[1]
                    ipstr = str(globalvars.addr)
                    ipstr1 = ipstr.split('\'')
                    ipstr1[2] = ipstr1[2][2:-1]
                    serverdata3 = ipstr1[1] + serverdata2 + "\\port\\" + str(ipstr1[2])
                    tempserverlist = serverdata3.split('\\')
                    globalvars.hl2serverlist[int(tempserverlist[4])] = tempserverlist
                    log.debug(clientid + "This Challenge: %s" % tempserverlist[4])
                    log.debug(clientid + "Current Challenge: %s" % (globalvars.hl2challengenum))
                elif globalvars.data.startswith("b") : #UNREGISTER
                    ipstr = str(globalvars.addr)
                    ipstr1 = ipstr.split('\'')
                    ipactual = ipstr1[1]
                    portstr = ipstr1[2]
                    portstr1 = portstr.split(' ')
                    portstr2 = portstr1[1].split(')')
                    portactual_temp = portstr2[0]
                    if not str(len(portactual_temp)) == 5 :
                        #portactual = "27015"
                        portactual = str(dedsrv_port)
                    else :
                        portactual = str(portactual_temp)
                    i = 0
                    running = 0
                    while i < 1000 :
                        if not isinstance(globalvars.hl2serverlist[i], int) :
                            running += 1
                            #if globalvars.hl2serverlist[i][0] == ipactual and (str(globalvars.hl2serverlist[i][24]) == portactual or "27015" == portactual) :
                            if ipactual in globalvars.hl2serverlist[i][0] and portactual in str(globalvars.hl2serverlist[i][len(globalvars.hl2serverlist[i]) - 1]) :
                                globalvars.hl2serverlist.pop(i)
                                log.info(clientid + "Unregistered server: %s:%s" % (ipactual, portactual))
                                running -= 1
                        i += 1
                    log.info(clientid + ("Running servers: %s" % str(running)))
                else :
                    log.warn(clientid + ("UNKNOWN MASTER SERVER COMMAND"))
            
        log.info(clientid + "Disconnected from HL2 Master Server")