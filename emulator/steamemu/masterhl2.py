import threading, logging, struct, binascii, time, atexit, socket, ipaddress, os.path, ast
import os
import config
import utilities
import steamemu.logger
import globalvars

from networkhandler import UDPNetworkHandler

class masterhl2(UDPNetworkHandler):

    def __init__(self, config, port):
        super(masterhl2, self).__init__(config, port)  # Create an instance of NetworkHandler
        
    def handle_client(self, *args):
        data, address = args
        log = logging.getLogger("hl2mstr")
        clientid = str(address) + ": "
        log.info(clientid + "Connected to HL2 Master Server")
        log.debug(clientid + ("Received message: %s, from %s" % (data, address)))

        if data.startswith("1") :
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
            self.socket.sendto(header + nullip + nullport, address)
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
            self.socket.sendto(header + challenge, address)
        elif data.startswith("0") :
            serverdata1 = data.split('\n')
            #print(serverdata1)
            serverdata2 = serverdata1[1]
            #print(serverdata2)
            ipstr = str(address)
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

        #self.socket.close()
        log.info (clientid + "Disconnected from HL2 Master Server")
