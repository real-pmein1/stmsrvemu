import threading, logging, struct, binascii, time, socket, atexit, ipaddress, os.path, ast
import os
import config
import utilities
import steamemu.logger
import globalvars

from networkhandler import UDPNetworkHandler

class masterhl(UDPNetworkHandler):
    def __init__(self, config, port):
        super(masterhl, self).__init__(config, port)  # Create an instance of NetworkHandler
        
        
    def handle_client(self, *args):
        data, address = args
        log = logging.getLogger("hl1mstr")
        clientid = str(address) + ": "
        log.info(clientid + "Connected to HL Master Server")
        log.debug(clientid + ("Received message: %s, from %s" % (data, address)))

        if data.startswith("1") :
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
            #self.socket.sendto(nullip.encode(), address)
            #self.socket.sendto(header + trueip + trueport + nullip + nullport, address)
            self.socket.sendto(header + nullip + nullport, address)
            #serversocket.close()
        elif data.startswith("q") :
            header = b'\xFF\xFF\xFF\xFF\x73\x0A'
            ipstr = str(address)
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
            self.socket.sendto(header + challenge, address)
        elif data.startswith("M") :
            header = b'\xFF\xFF\xFF\xFF\x4E\x0A'
            ipstr = str(address)
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
            self.socket.sendto(header + challenge, address)
        elif data.startswith("0") :
            serverdata1 = data.split('\n')
            serverdata2 = serverdata1[1]
            ipstr = str(address)
            ipstr1 = ipstr.split('\'')
            serverdata3 = ipstr1[1] + serverdata2
            tempserverlist = serverdata3.split('\\')
            globalvars.hl1serverlist[int(tempserverlist[4])] = tempserverlist
            print("This Challenge: %s" % tempserverlist[4])
            print("Current Challenge: %s" % (globalvars.hl1challengenum))
            #globalvars.hl1servernum += 1
        elif data.startswith("b") :
            ipstr = str(address)
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
            
        #self.socket.close()
        log.info (clientid + "Disconnected from HL1 Master Server")

