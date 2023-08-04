import sys
import binascii, ConfigParser, threading, logging, socket, time, os, shutil, zipfile, tempfile, types

import struct #for int to byte conversion

import steam
import dirs
import steamemu.logger
import globalvars

from steamemu.converter import convertgcf
from steamemu.config import read_config
from steamemu.directoryserver import directoryserver
from steamemu.configserver import configserver
from steamemu.contentlistserver import contentlistserver
from steamemu.fileserver import fileserver
from steamemu.authserver import authserver
#from steamemu.authserverv3 import authserverv3
from steamemu.udpserver import udpserver
from steamemu.masterhl import masterhl
from steamemu.masterhl2 import masterhl2
from steamemu.masterrdkf import masterrdkf
from steamemu.friends import friends
from steamemu.vttserver import vttserver
from steamemu.twosevenzeroonefour import twosevenzeroonefour
from steamemu.validationserver import validationserver

#from steamemu.udpserver import udpserver

from Steam2.package import Package
from Steam2.neuter import neuter_file

print("Steam 2004-2011 Server Emulator v0.72")
print("=====================================")
print

config = read_config()

print("**************************")
print("Server IP: " + config["server_ip"])
if config["public_ip"] != "0.0.0.0" :
    print("Public IP: " + config["public_ip"])
print("**************************")
print
log = logging.getLogger('emulator')

log.info("...Starting Steam Server...\n")

if config["server_ip"].startswith("10.") :
    globalvars.servernet = "('10."
elif config["server_ip"].startswith("172.16.") :
    globalvars.servernet = "('172.16."
elif config["server_ip"].startswith("172.17.") :
    globalvars.servernet = "('172.17."
elif config["server_ip"].startswith("172.18.") :
    globalvars.servernet = "('172.18."
elif config["server_ip"].startswith("172.19.") :
    globalvars.servernet = "('172.19."
elif config["server_ip"].startswith("172.20.") :
    globalvars.servernet = "('172.20."
elif config["server_ip"].startswith("172.21.") :
    globalvars.servernet = "('172.21."
elif config["server_ip"].startswith("172.22.") :
    globalvars.servernet = "('172.22."
elif config["server_ip"].startswith("172.23.") :
    globalvars.servernet = "('172.23."
elif config["server_ip"].startswith("172.24.") :
    globalvars.servernet = "('172.24."
elif config["server_ip"].startswith("172.25.") :
    globalvars.servernet = "('172.25."
elif config["server_ip"].startswith("172.26.") :
    globalvars.servernet = "('172.26."
elif config["server_ip"].startswith("172.27.") :
    globalvars.servernet = "('172.27."
elif config["server_ip"].startswith("172.28.") :
    globalvars.servernet = "('172.28."
elif config["server_ip"].startswith("172.29.") :
    globalvars.servernet = "('172.29."
elif config["server_ip"].startswith("172.30.") :
    globalvars.servernet = "('172.30."
elif config["server_ip"].startswith("172.31.") :
    globalvars.servernet = "('172.31."
elif config["server_ip"].startswith("192.168.") :
    globalvars.servernet = "('192.168."
    
#print(globalvars.servernet)

class listener(threading.Thread):
    def __init__(self, port, serverobject, config):
        self.port = int(port)
        self.serverobject = serverobject  
        self.config = config.copy()
        self.config["port"] = port
        threading.Thread.__init__(self)

    def run(self):
        serversocket = steam.ImpSocket()
        serversocket.bind((config["server_ip"], self.port))
        serversocket.listen(5)

        #print "TCP Server Listening on port " + str(self.port)

        while True :
            (clientsocket, address) = serversocket.accept()
            self.serverobject((clientsocket, address), self.config).start();

class udplistener(threading.Thread):
    def __init__(self, port, serverobject, config):
        self.port = int(port)
        self.serverobject = serverobject         
        self.config = config.copy()
        self.config["port"] = port
        threading.Thread.__init__(self)

    def run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        serversocket = steam.ImpSocket(sock)
        serversocket.bind((config["server_ip"], self.port))
        #serversocket.listen(5)

        #log.info("UDP Server Listening on port " + str(self.port))

        while True :
            #(clientsocket, address) = serversocket.accept()
            #self.serverobject((clientsocket, address), self.config).start();
            globalvars.data, globalvars.addr = serversocket.recvfrom(1280)
            #print("Received message: %s on port %s" % (globalvars.data, self.port))
            #self.serverobject(serversocket, self.config).start();
            if self.port == 27010 :
                log = logging.getLogger("hl1mstr")
                clientid = str(globalvars.addr) + ": "
                log.info(clientid + "Connected to HL Master Server")
                log.debug(clientid + ("Received message: %s, from %s" % (globalvars.data, globalvars.addr)))
                if globalvars.data.startswith("1") :
                    i = 0
                    header = bytearray()
                    header += b'\xFF\xFF\xFF\xFF\x66\x0A'
                    #header = b'\xFF\xFF\xFF\xFF\x66\x0A'
                    while i < 1000 : #also change in command "b" and in globalvars
                        if not isinstance(globalvars.hl1serverlist[i], int) :
                            #print(globalvars.hl1serverlist[i][0])
                            print(globalvars.hl1serverlist[i])
                            trueip = globalvars.hl1serverlist[i][0].split('.')
                            trueip_int = map(int, trueip)
                            header += struct.pack('>BBBB', trueip_int[0], trueip_int[1], trueip_int[2], trueip_int[3])
                            #print(globalvars.hl1serverlist[i][24])
                            trueport_int_temp = int(globalvars.hl1serverlist[i][24])
                            if not len(str(trueport_int_temp)) == 5 :
                                trueport_int = 27015
                            else :
                                trueport_int = trueport_int_temp
                            print(str(trueport_int))
                            header += struct.pack('>H', trueport_int)
                        i += 1
                    #trueip = struct.pack('>BBBB', 172, 20, 0, 23)
                    #trueport = struct.pack('>H', 27015)
                    nullip = struct.pack('>BBBB', 0, 0, 0, 0)
                    nullport = struct.pack('>H', 0)
                    #serversocket.sendto(nullip.encode(), globalvars.addr)
                    #serversocket.sendto(header + trueip + trueport + nullip + nullport, globalvars.addr)
                    serversocket.sendto(header + nullip + nullport, globalvars.addr)
                    #serversocket.close()
                elif globalvars.data.startswith("q") :
                    header = b'\xFF\xFF\xFF\xFF\x73\x0A'
                    ipstr = str(globalvars.addr)
                    ipstr1 = ipstr.split('\'')
                    ipactual = ipstr1[1]
                    portstr = ipstr1[2]
                    portstr1 = portstr.split(' ')
                    portstr2 = portstr1[1].split(')')
                    portactual_temp = portstr2[0]
                    if not str(len(portactual_temp)) == 5 :
                        portactual = "27015"
                    else :
                        portactual = str(portactual_temp)
                    registered = 0
                    for server in globalvars.hl1serverlist :
                        if len(str(server)) > 5 :
                            if server[0] == ipactual and (str(server[24]) == portactual or "27015" == portactual) :
                                log.info(clientid + "Already registered, sending challenge number %s" % str(server[4]))
                                challenge = struct.pack("I", int(server[4]))
                                registered = 1
                                break
                    if registered == 0 :
                        log.info(clientid + "Registering server, sending challenge number %s" % str(globalvars.hl1challengenum + 1))
                        challenge = struct.pack("I", globalvars.hl1challengenum + 1)
                        globalvars.hl1challengenum += 1
                    serversocket.sendto(header + challenge, globalvars.addr)
                elif globalvars.data.startswith("M") :
                    header = b'\xFF\xFF\xFF\xFF\x4E\x0A'
                    ipstr = str(globalvars.addr)
                    ipstr1 = ipstr.split('\'')
                    ipactual = ipstr1[1]
                    portstr = ipstr1[2]
                    portstr1 = portstr.split(' ')
                    portstr2 = portstr1[1].split(')')
                    portactual_temp = portstr2[0]
                    if not str(len(portactual_temp)) == 5 :
                        portactual = "27015"
                    else :
                        portactual = str(portactual_temp)
                    registered = 0
                    for server in globalvars.hl1serverlist :
                        if len(str(server)) > 5 :
                            if server[0] == ipactual and (str(server[24]) == portactual or "27015" == portactual) :
                                log.info(clientid + "Already registered, sending challenge number %s" % str(server[4]))
                                challenge = struct.pack("I", int(server[4]))
                                registered = 1
                                break
                    if registered == 0 :
                        log.info(clientid + "Registering server, sending challenge number %s" % str(globalvars.hl1challengenum + 1))
                        challenge = struct.pack("I", globalvars.hl1challengenum + 1)
                        globalvars.hl1challengenum += 1
                    serversocket.sendto(header + challenge, globalvars.addr)
                elif globalvars.data.startswith("0") :
                    serverdata1 = globalvars.data.split('\n')
                    serverdata2 = serverdata1[1]
                    ipstr = str(globalvars.addr)
                    ipstr1 = ipstr.split('\'')
                    serverdata3 = ipstr1[1] + serverdata2
                    tempserverlist = serverdata3.split('\\')
                    globalvars.hl1serverlist[int(tempserverlist[4])] = tempserverlist
                    log.debug(clientid + "This Challenge: %s" % tempserverlist[4])
                    log.debug(clientid + "Current Challenge: %s" % (globalvars.hl1challengenum))
                    #globalvars.hl1servernum += 1
                elif globalvars.data.startswith("b") :
                    ipstr = str(globalvars.addr)
                    ipstr1 = ipstr.split('\'')
                    ipactual = ipstr1[1]
                    portstr = ipstr1[2]
                    portstr1 = portstr.split(' ')
                    portstr2 = portstr1[1].split(')')
                    portactual_temp = portstr2[0]
                    if not str(len(portactual_temp)) == 5 :
                        portactual = "27015"
                    else :
                        portactual = str(portactual_temp)
                    i = 0
                    running = 0
                    while i < 1000 :
                        if not isinstance(globalvars.hl1serverlist[i], int) :
                            running += 1
                            #print(ipactual + ":" + portactual)
                            #print(type(ipactual))
                            #print(type(portactual))
                            #print(type(globalvars.hl1serverlist[i][0]))
                            #print(type(globalvars.hl1serverlist[i][24]))
                            if globalvars.hl1serverlist[i][0] == ipactual and (str(globalvars.hl1serverlist[i][24]) == portactual or "27015" == portactual) :
                                globalvars.hl1serverlist.pop(i)
                                print("Removed game server: %s:%s" % (ipactual, portactual))
                                running -= 1
                        i += 1
                    print("Running servers: %s" % str(running))
                else :
                    print("UNKNOWN MASTER SERVER COMMAND")
            elif self.port == 27011 :
                log = logging.getLogger("hl2mstr")
                clientid = str(globalvars.addr) + ": "
                log.info(clientid + "Connected to HL2 Master Server")
                log.debug(clientid + ("Received message: %s, from %s" % (globalvars.data, globalvars.addr)))
                if globalvars.data.startswith("1") :
                    i = 0
                    header = bytearray()
                    header += b'\xFF\xFF\xFF\xFF\x66\x0A'
                    while i < 1000 : #also change in command "b" and in globalvars
                        if not isinstance(globalvars.hl2serverlist[i], int) :
                            print(globalvars.hl2serverlist[i])
                            trueip = globalvars.hl2serverlist[i][0].split('.')
                            trueip_int = map(int, trueip)
                            header += struct.pack('>BBBB', trueip_int[0], trueip_int[1], trueip_int[2], trueip_int[3])
                            try :
                                trueport_int_temp = int(globalvars.hl2serverlist[i][24])
                            except :
                                trueport_int_temp = 1
                            if not len(str(trueport_int_temp)) == 5 :
                                trueport_int = 27015
                            else :
                                trueport_int = trueport_int_temp
                            print(str(trueport_int))
                            header += struct.pack('>H', trueport_int)
                        i += 1
                    nullip = struct.pack('>BBBB', 0, 0, 0, 0)
                    nullport = struct.pack('>H', 0)
                    serversocket.sendto(header + nullip + nullport, globalvars.addr)
                elif globalvars.data.startswith("q") :
                    header = b'\xFF\xFF\xFF\xFF\x73\x0A'
                    ipstr = str(globalvars.addr)
                    ipstr1 = ipstr.split('\'')
                    ipactual = ipstr1[1]
                    portstr = ipstr1[2]
                    portstr1 = portstr.split(' ')
                    portstr2 = portstr1[1].split(')')
                    portactual_temp = portstr2[0]
                    if not str(len(portactual_temp)) == 5 :
                        portactual = "27015"
                    else :
                        portactual = str(portactual_temp)
                    registered = 0
                    for server in globalvars.hl2serverlist :
                        if len(str(server)) > 5 :
                            if server[0] == ipactual and (str(server[24]) == portactual or "27015" == portactual) :
                                log.info(clientid + "Already registered, sending challenge number %s" % str(server[4]))
                                challenge = struct.pack("I", int(server[4]))
                                registered = 1
                                break
                    if registered == 0 :
                        log.info(clientid + "Registering server, sending challenge number %s" % str(globalvars.hl2challengenum + 1))
                        challenge = struct.pack("I", globalvars.hl2challengenum + 1)
                        globalvars.hl2challengenum += 1
                    serversocket.sendto(header + challenge, globalvars.addr)
                elif globalvars.data.startswith("0") :
                    serverdata1 = globalvars.data.split('\n')
                    #print(serverdata1)
                    serverdata2 = serverdata1[1]
                    #print(serverdata2)
                    ipstr = str(globalvars.addr)
                    ipstr1 = ipstr.split('\'')
                    serverdata3 = ipstr1[1] + serverdata2
                    #print(serverdata3)
                    tempserverlist = serverdata3.split('\\')
                    #print(tempserverlist)
                    globalvars.hl2serverlist[int(tempserverlist[4])] = tempserverlist
                    #print(tempserverlist[0])
                    #print(tempserverlist[1])
                    #print(tempserverlist[2])
                    #print(tempserverlist[3])
                    #print(tempserverlist[4])
                    #print(tempserverlist[5])
                    log.debug(clientid + "This Challenge: %s" % tempserverlist[4])
                    log.debug(clientid + "Current Challenge: %s" % (globalvars.hl2challengenum))
                elif globalvars.data.startswith("b") :
                    ipstr = str(globalvars.addr)
                    ipstr1 = ipstr.split('\'')
                    ipactual = ipstr1[1]
                    portstr = ipstr1[2]
                    portstr1 = portstr.split(' ')
                    portstr2 = portstr1[1].split(')')
                    portactual_temp = portstr2[0]
                    if not str(len(portactual_temp)) == 5 :
                        portactual = "27015"
                    else :
                        portactual = str(portactual_temp)
                    i = 0
                    running = 0
                    while i < 1000 :
                        if not isinstance(globalvars.hl2serverlist[i], int) :
                            running += 1
                            #print(ipactual + ":" + portactual)
                            #print(type(ipactual))
                            #print(type(portactual))
                            #print(type(globalvars.hl2serverlist[i][0]))
                            #print(type(globalvars.hl2serverlist[i][24]))
                            #for server in globalvars.hl2serverlist :
                                #print(server)
                            if globalvars.hl2serverlist[i][0] == ipactual and (str(globalvars.hl2serverlist[i][24]) == portactual or "27015" == portactual) :
                                #print(type(globalvars.hl2serverlist[i]))
                                #print(type(i))
                                #print(type(globalvars.hl2serverlist))
                                #print(globalvars.hl2serverlist[i][0])
                                #print(str(globalvars.hl2serverlist[i][24]))
                                globalvars.hl2serverlist.pop(i)
                                log.info(clientid + "Unregistered server: %s:%s" % (ipactual, portactual))
                                running -= 1
                        i += 1
                    print("Running servers: %s" % str(running))
                else :
                    print("UNKNOWN MASTER SERVER COMMAND")
            elif self.port == 27012 :
                log = logging.getLogger("rdkfmstr")
                clientid = str(globalvars.addr) + ": "
                log.info(clientid + "Connected to RDKF Master Server")
                log.debug(clientid + ("Received message: %s, from %s" % (globalvars.data, globalvars.addr)))
                if globalvars.data.startswith("1") :
                    i = 0
                    header = bytearray()
                    header += b'\xFF\xFF\xFF\xFF\x66\x0A'
                    while i < 1000 : #also change in command "b" and in globalvars
                        if not isinstance(globalvars.rdkfserverlist[i], int) :
                            print(globalvars.rdkfserverlist[i])
                            trueip = globalvars.rdkfserverlist[i][0].split('.')
                            trueip_int = map(int, trueip)
                            header += struct.pack('>BBBB', trueip_int[0], trueip_int[1], trueip_int[2], trueip_int[3])
                            try :
                                trueport_int_temp = int(globalvars.rdkfserverlist[i][24])
                            except :
                                trueport_int_temp = 1
                            if not len(str(trueport_int_temp)) == 5 :
                                trueport_int = 27015
                            else :
                                trueport_int = trueport_int_temp
                            print(str(trueport_int))
                            header += struct.pack('>H', trueport_int)
                        i += 1
                    nullip = struct.pack('>BBBB', 0, 0, 0, 0)
                    nullport = struct.pack('>H', 0)
                    serversocket.sendto(header + nullip + nullport, globalvars.addr)
                elif globalvars.data.startswith("q") :
                    header = b'\xFF\xFF\xFF\xFF\x73\x0A'
                    ipstr = str(globalvars.addr)
                    ipstr1 = ipstr.split('\'')
                    ipactual = ipstr1[1]
                    portstr = ipstr1[2]
                    portstr1 = portstr.split(' ')
                    portstr2 = portstr1[1].split(')')
                    portactual_temp = portstr2[0]
                    if not str(len(portactual_temp)) == 5 :
                        portactual = "27015"
                    else :
                        portactual = str(portactual_temp)
                    registered = 0
                    for server in globalvars.rdkfserverlist :
                        if len(str(server)) > 5 :
                            if server[0] == ipactual and (str(server[24]) == portactual or "27015" == portactual) :
                                log.info(clientid + "Already registered, sending challenge number %s" % str(server[4]))
                                challenge = struct.pack("I", int(server[4]))
                                registered = 1
                                break
                    if registered == 0 :
                        log.info(clientid + "Registering server, sending challenge number %s" % str(globalvars.rdkfchallengenum + 1))
                        challenge = struct.pack("I", globalvars.rdkfchallengenum + 1)
                        globalvars.rdkfchallengenum += 1
                    serversocket.sendto(header + challenge, globalvars.addr)
                elif globalvars.data.startswith("0") :
                    serverdata1 = globalvars.data.split('\n')
                    #print(serverdata1)
                    serverdata2 = serverdata1[1]
                    #print(serverdata2)
                    ipstr = str(globalvars.addr)
                    ipstr1 = ipstr.split('\'')
                    serverdata3 = ipstr1[1] + serverdata2
                    #print(serverdata3)
                    tempserverlist = serverdata3.split('\\')
                    #print(tempserverlist)
                    globalvars.rdkfserverlist[int(tempserverlist[4])] = tempserverlist
                    #print(tempserverlist[0])
                    #print(tempserverlist[1])
                    #print(tempserverlist[2])
                    #print(tempserverlist[3])
                    #print(tempserverlist[4])
                    #print(tempserverlist[5])
                    log.debug(clientid + "This Challenge: %s" % tempserverlist[4])
                    log.debug(clientid + "Current Challenge: %s" % (globalvars.rdkfchallengenum))
                elif globalvars.data.startswith("b") :
                    ipstr = str(globalvars.addr)
                    ipstr1 = ipstr.split('\'')
                    ipactual = ipstr1[1]
                    portstr = ipstr1[2]
                    portstr1 = portstr.split(' ')
                    portstr2 = portstr1[1].split(')')
                    portactual_temp = portstr2[0]
                    if not str(len(portactual_temp)) == 5 :
                        portactual = "27015"
                    else :
                        portactual = str(portactual_temp)
                    i = 0
                    running = 0
                    while i < 1000 :
                        if not isinstance(globalvars.rdkfserverlist[i], int) :
                            running += 1
                            #print(ipactual + ":" + portactual)
                            #print(type(ipactual))
                            #print(type(portactual))
                            #print(type(globalvars.rdkfserverlist[i][0]))
                            #print(type(globalvars.rdkfserverlist[i][24]))
                            #for server in globalvars.rdkfserverlist :
                                #print(server)
                            if globalvars.rdkfserverlist[i][0] == ipactual and (str(globalvars.rdkfserverlist[i][24]) == portactual or "27015" == portactual) :
                                #print(type(globalvars.rdkfserverlist[i]))
                                #print(type(i))
                                #print(type(globalvars.rdkfserverlist))
                                #print(globalvars.rdkfserverlist[i][0])
                                #print(str(globalvars.rdkfserverlist[i][24]))
                                globalvars.rdkfserverlist.pop(i)
                                log.info(clientid + "Unregistered server: %s:%s" % (ipactual, portactual))
                                running -= 1
                        i += 1
                    print("Running servers: %s" % str(running))
                else :
                    print("UNKNOWN MASTER SERVER COMMAND")
            elif self.port == 27013 :
                log = logging.getLogger("csersrv")
                clientid = str(globalvars.addr) + ": "
                log.info(clientid + "Connected to CSER Server")
                log.debug(clientid + ("Received message: %s, from %s" % (globalvars.data, globalvars.addr)))
                ipstr = str(globalvars.addr)
                ipstr1 = ipstr.split('\'')
                ipactual = ipstr1[1]
                if globalvars.data.startswith("e") : #65
                    message = binascii.b2a_hex(globalvars.data)
                    keylist = list(xrange(7))
                    vallist = list(xrange(7))
                    keylist[0] = "SuccessCount"
                    keylist[1] = "UnknownFailureCount"
                    keylist[2] = "ShutdownFailureCount"
                    keylist[3] = "UptimeCleanCounter"
                    keylist[4] = "UptimeCleanTotal"
                    keylist[5] = "UptimeFailureCounter"
                    keylist[6] = "UptimeFailureTotal"
                    try :
                        os.mkdir("clientstats")
                    except OSError as error :
                        log.debug("Client stats dir already exists")
                    if message.startswith("650a01537465616d2e657865") : #Steam.exe
                        vallist[0] = str(int(message[24:26], base=16))
                        vallist[1] = str(int(message[26:28], base=16))
                        vallist[2] = str(int(message[28:30], base=16))
                        vallist[3] = str(int(message[30:32], base=16))
                        vallist[4] = str(int(message[32:34], base=16))
                        vallist[5] = str(int(message[34:36], base=16))
                        vallist[6] = str(int(message[36:38], base=16))
                        f = open("clientstats\\" + str(ipactual) + ".steamexe.csv", "w")
                        f.write(str(binascii.a2b_hex(message[6:24])))
                        f.write("\n")
                        f.write(keylist[0] + "," + keylist[1] + "," + keylist[2] + "," + keylist[3] + "," + keylist[4] + "," + keylist[5] + "," + keylist[6])
                        f.write("\n")
                        f.write(vallist[0] + "," + vallist[1] + "," + vallist[2] + "," + vallist[3] + "," + vallist[4] + "," + vallist[5] + "," + vallist[6])
                        f.close()
                        log.info(clientid + "Received client stats")
                elif globalvars.data.startswith("c") : #63
                    message = binascii.b2a_hex(globalvars.data)
                    keylist = list(xrange(13))
                    vallist = list(xrange(13))
                    keylist[0] = "Unknown1"
                    keylist[1] = "Unknown2"
                    keylist[2] = "ModuleName"
                    keylist[3] = "FileName"
                    keylist[4] = "CodeFile"
                    keylist[5] = "ThrownAt"
                    keylist[6] = "Unknown3"
                    keylist[7] = "Unknown4"
                    keylist[8] = "AssertPreCondition"
                    keylist[9] = "Unknown5"
                    keylist[10] = "OsCode"
                    keylist[11] = "Unknown6"
                    keylist[12] = "Message"
                    try :
                        os.mkdir("crashlogs")
                    except OSError as error :
                        log.debug("Client crash reports dir already exists")
                    templist = binascii.a2b_hex(message)
                    templist2 = templist.split(b'\x00')
                    try :
                        vallist[0] = str(int(binascii.b2a_hex(templist2[0][2:4]), base=16))
                        vallist[1] = str(int(binascii.b2a_hex(templist2[1]), base=16))
                        vallist[2] = str(templist2[2])
                        vallist[3] = str(templist2[3])
                        vallist[4] = str(templist2[4])
                        vallist[5] = str(int(binascii.b2a_hex(templist2[5]), base=16))
                        vallist[6] = str(int(binascii.b2a_hex(templist2[7]), base=16))
                        vallist[7] = str(int(binascii.b2a_hex(templist2[10]), base=16))
                        vallist[8] = str(templist2[13])
                        vallist[9] = str(int(binascii.b2a_hex(templist2[14]), base=16))
                        vallist[10] = str(int(binascii.b2a_hex(templist2[15]), base=16))
                        vallist[11] = str(int(binascii.b2a_hex(templist2[18]), base=16))
                        vallist[12] = str(templist2[23])
                        f = open("crashlogs\\" + str(ipactual) + ".csv", "w")
                        f.write("SteamExceptionsData")
                        f.write("\n")
                        f.write(keylist[0] + "," + keylist[1] + "," + keylist[2] + "," + keylist[3] + "," + keylist[4] + "," + keylist[5] + "," + keylist[6] + "," + keylist[7] + "," + keylist[8] + "," + keylist[9] + "," + keylist[10] + "," + keylist[11] + "," + keylist[12])
                        f.write("\n")
                        f.write(vallist[0] + "," + vallist[1] + "," + vallist[2] + "," + vallist[3] + "," + vallist[4] + "," + vallist[5] + "," + vallist[6] + "," + vallist[7] + "," + vallist[8] + "," + vallist[9] + "," + vallist[10] + "," + vallist[11] + "," + vallist[12])
                        f.close()
                        log.info(clientid + "Received client crash report")
                    except :
                        log.debug(clientid + "Failed to receive client crash report")
                elif globalvars.data.startswith("q") : #71
                    print("Received encrypted ICE client stats - INOP")
                elif globalvars.data.startswith("a") : #61
                    print("Received app download stats - INOP")
                elif globalvars.data.startswith("i") : #69
                    print("Received unknown stats - INOP")
                elif globalvars.data.startswith("k") : #6b
                    print("Received app usage stats - INOP")
                else :
                    print("Unknown CSER command: %s" % globalvars.data)
            elif self.port == 27014 :
                log = logging.getLogger("27014")
                clientid = str(globalvars.addr) + ": "
                log.info(clientid + "Connected to 27014")
                log.debug(clientid + ("Received message: %s, from %s" % (globalvars.data, globalvars.addr)))
            elif self.port == 27017 :
                log = logging.getLogger("friends")
                clientid = str(globalvars.addr) + ": "
                log.info(clientid + "Connected to Chat Server")
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
            else :
                print("Who knows!")

config = read_config()

# create the Steam.exe file
f = open(config["packagedir"] + config["steampkg"], "rb")
pkg = Package(f.read())
f.close()
file = pkg.get_file("SteamNew.exe")
if config["public_ip"] != "0.0.0.0" :
    file = neuter_file(file, config["public_ip"], config["dir_server_port"])
else :
    file = neuter_file(file, config["server_ip"], config["dir_server_port"])
f = open("client/Steam.exe", "wb")
f.write(file)
f.close()

if config["hldsupkg"] != "" :
    g = open(config["packagedir"] + config["hldsupkg"], "rb")
    pkg = Package(g.read())
    g.close()
    file = pkg.get_file("HldsUpdateToolNew.exe")
    if config["public_ip"] != "0.0.0.0" :
        file = neuter_file(file, config["public_ip"], config["dir_server_port"])
    else :
        file = neuter_file(file, config["server_ip"], config["dir_server_port"])
    g = open("client/HldsUpdateTool.exe", "wb")
    g.write(file)
    g.close()
        
if os.path.isfile("files/1stcdr.py") :
    f = open("files/1stcdr.py", "r")
    firstblob = f.read()
    f.close()
else :
    f = open("files/firstblob.bin", "rb")
    firstblob_bin = f.read()
    f.close()
    if firstblob_bin[0:2] == "\x01\x43":
        firstblob_bin = zlib.decompress(firstblob_bin[20:])
    firstblob_unser = steam.blob_unserialize(firstblob_bin)
    firstblob = steam.blob_dump(firstblob_unser)

firstblob_list = firstblob.split("\n")
steam_hex = firstblob_list[2][25:41]
steam_ver = str(int(steam_hex[14:16] + steam_hex[10:12] + steam_hex[6:8] + steam_hex[2:4], 16))
steamui_hex = firstblob_list[3][25:41]
steamui_ver = int(steamui_hex[14:16] + steamui_hex[10:12] + steamui_hex[6:8] + steamui_hex[2:4], 16)

if steamui_ver < 61 : #guessing steamui version when steam client interface v2 changed to v3
    globalvars.tgt_version = "1"
else :
    globalvars.tgt_version = "2" #config file states 2 as default

if steamui_ver < 122 :
    if os.path.isfile("files/cafe/Steam.dll") :
        log.info("Cafe files found")
        g = open("files/cafe/Steam.dll", "rb")
        file = g.read()
        g.close()
        if config["public_ip"] != "0.0.0.0" :
            file = neuter_file(file, config["public_ip"], config["dir_server_port"])
        else :
            file = neuter_file(file, config["server_ip"], config["dir_server_port"])
        if os.path.isfile("files/cafe/CASpackage.zip") :
            shutil.copyfile("files/cafe/CASpackage.zip", "client/cafe_server/CASpackage.zip")
            with zipfile.ZipFile('client/cafe_server/CASpackage.zip', 'a') as zipped_f:
                zipped_f.writestr("Steam.dll", file)
            lsclient_line1 = "CAServerIP = " + config["server_ip"]
            lsclient_line2 = "ExitSteamAfterGame = true"
            lsclient_line3 = "AllowUserLogin = false"
            lsclient_line4 = "AllowCafeLogin = true"
            lsclient_lines = bytes(lsclient_line1 + "\n" + lsclient_line2 + "\n" + lsclient_line3 + "\n" + lsclient_line4)
            with zipfile.ZipFile('client/cafe_server/CASpackage.zip', 'a') as zipped_f:
                zipped_f.writestr("Client/lsclient.cfg", lsclient_lines)
            tempdir = tempfile.mkdtemp()
            try:
                tempname = os.path.join(tempdir, 'new.zip')
                with zipfile.ZipFile('client/cafe_server/CASpackage.zip', 'r') as zipread:
                    with zipfile.ZipFile(tempname, 'w') as zipwrite:
                        for item in zipread.infolist():
                            if item.filename not in 'CAServer.cfg':
                                data = zipread.read(item.filename)
                                zipwrite.writestr(item, data)
                shutil.move(tempname, 'client/cafe_server/CASpackage.zip')
            finally:
                shutil.rmtree(tempdir)
            caserver_line1 = "MasterServerIP = " + config["server_ip"]
            caserver_line2 = "MasterLogin = " + config["cafeuser"]
            caserver_line3 = "MasterPass = " + config["cafepass"]
            caserver_line4 = "IPRange1 = 192.168.0.1"
            caserver_line5 = "EnableTimedUpdates = disable"
            caserver_line6 = "UpdateStart = 2200"
            caserver_line7 = "UpdateEnd = 0200"
            caserver_lines = bytes(caserver_line1 + "\n" + caserver_line2 + "\n" + caserver_line3 + "\n" + caserver_line4 + "\n" + caserver_line5 + "\n" + caserver_line6 + "\n" + caserver_line7)
            with zipfile.ZipFile('client/cafe_server/CASpackage.zip', 'a') as zipped_f:
                zipped_f.writestr("CAServer.cfg", caserver_lines)
            passwords_line = bytes(config["cafeuser"] + "%" + config["cafepass"])
            with zipfile.ZipFile('client/cafe_server/CASpackage.zip', 'a') as zipped_f:
                zipped_f.writestr("passwords.txt", passwords_line)
            if os.path.isfile("files/cafe/README.txt") :
                g = open("files/cafe/README.txt", "rb")
                file = g.read()
                g.close()
                with zipfile.ZipFile('client/cafe_server/CASpackage.zip', 'a') as zipped_f:
                    zipped_f.writestr("README.txt", file)
            g = open("client/Steam.exe", "rb")
            file = g.read()
            g.close()
            with zipfile.ZipFile('client/cafe_server/CASpackage.zip', 'a') as zipped_f:
                zipped_f.writestr("Client/Steam.exe", file)
                
        else :
            g = open("client/cafe_server/Steam.dll", "wb")
            g.write(file)
            g.close()
        
if config["use_sdk"] == "1" :
    with open("files/pkg_add/steam/Steam.cfg", "w") as h :
        h.write('SdkContentServerAdrs = "' + config["sdk_ip"] + ':' + config["sdk_port"] + '"\n')
    if os.path.isfile("files/cache/Steam_" + steam_ver + ".pkg") :
        os.remove("files/cache/Steam_" + steam_ver + ".pkg")
else :
    if os.path.isfile("files/pkg_add/steam/Steam.cfg") :
        os.remove("files/cache/Steam_" + steam_ver + ".pkg")
        os.remove("files/pkg_add/steam/Steam.cfg")

if os.path.isfile("Steam.exe") :
    os.remove("Steam.exe")
if os.path.isfile("HldsUpdateTool.exe") :
    os.remove("HldsUpdateTool.exe")
if os.path.isfile("log.txt") :
    os.remove("log.txt")
if os.path.isfile("library.zip") :
    os.remove("library.zip")
if os.path.isfile("MSVCR71.dll") :
    os.remove("MSVCR71.dll")
if os.path.isfile("python24.dll") :
    os.remove("python24.dll")
if os.path.isfile("python27.dll") :
    os.remove("python27.dll")
if os.path.isfile("Steam.cfg") :
    os.remove("Steam.cfg")
if os.path.isfile("w9xpopen.exe") :
    os.remove("w9xpopen.exe")
#if os.path.isfile("submanager.exe") :
#    os.remove("submanager.exe")

if os.path.isfile("files/users.txt") :
    users = {} #REMOVE LEGACY USERS
    f = open("files/users.txt")
    for line in f.readlines() :
        if line[-1:] == "\n" :
            line = line[:-1]
        if line.find(":") != -1 :
            (user, password) = line.split(":")
            users[user] = user
    f.close()
    for user in users :
        if (os.path.isfile("files/users/" + user + ".py")) :
            os.rename("files/users/" + user + ".py", "files/users/" + user + ".legacy")
    os.rename("files/users.txt", "files/users.off")

log.info("Checking for gcf files to convert...")
convertgcf()

time.sleep(0.2)
cserlistener = udplistener(27013, udpserver, config)
cserlistener.start()
log.info("CSER Server listening on port 27013")
time.sleep(0.2)
hlmasterlistener = udplistener(27010, masterhl, config)
hlmasterlistener.start()
log.info("Master HL1 Server listening on port 27010")
time.sleep(0.2)
hl2masterlistener = udplistener(27011, masterhl2, config)
hl2masterlistener.start()
log.info("Master HL2 Server listening on port 27011")
time.sleep(0.2)
rdkfmasterlistener = udplistener(27012, masterrdkf, config)
rdkfmasterlistener.start()
log.info("Master RDKF Server listening on port 27012")
time.sleep(0.2)
#twosevenzeroonefourlistener = udplistener(27014, twosevenzeroonefour, config)
#twosevenzeroonefourlistener.start()
#log.info("Server listening on port 27014") #ANOTHER CHAT SERVER
#time.sleep(0.2)
if config["tracker_ip"] == "0.0.0.0" :
    #chatlistener = udplistener(27017, friends, config)
    #chatlistener.start()
    globalvars.tracker = 0
    #log.info("Chat Server listening on port 27017")
else :
    globalvars.tracker = 1
    log.info("Connected to TRACKER")
time.sleep(0.2)
dirlistener = listener(config["dir_server_port"], directoryserver, config)
dirlistener.start()
log.info("Steam General Directory Server listening on port " + str(config["dir_server_port"]))
time.sleep(0.2)
configlistener = listener(config["conf_server_port"], configserver, config)
configlistener.start()
log.info("Steam Config Server listening on port " + str(config["conf_server_port"]))
time.sleep(0.2)
contentlistener = listener(config["contlist_server_port"], contentlistserver, config)
contentlistener.start()
log.info("Steam Content List Server listening on port " + str(config["contlist_server_port"]))
time.sleep(0.2)
filelistener = listener(config["file_server_port"], fileserver, config)
filelistener.start()
log.info("Steam File Server listening on port " + str(config["file_server_port"]))
time.sleep(0.2)
authlistener = listener(config["auth_server_port"], authserver, config)
authlistener.start()
log.info("Steam Master Authentication Server listening on port " + str(config["auth_server_port"]))
time.sleep(0.2)
vttlistener = listener("27046", vttserver, config)
vttlistener.start()
log.info("Valve Time Tracking Server listening on port 27046")
time.sleep(0.2)
vttlistener2 = listener("27047", vttserver, config)
vttlistener2.start()
log.info("Valve CyberCafe Server listening on port 27047")
time.sleep(0.2)
vallistener = listener("27034", validationserver, config)
vallistener.start()
log.info("Steam User Validation Server listening on port 27034")
time.sleep(0.2)
if config["sdk_ip"] != "0.0.0.0" :
    log.info("Steamworks SDK Content Server configured on port " + str(config["sdk_port"]))
    time.sleep(0.2)
log.debug("TGT set to version " + globalvars.tgt_version)
log.info("Steam Server ready.")
authlistener.join()
