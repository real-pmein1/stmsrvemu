import sys
import binascii, ConfigParser, threading, logging, socket, time, os, shutil, zipfile, tempfile, types, ast, filecmp, requests, subprocess, ipcalc

import struct #for int to byte conversion
from collections import Counter
from tqdm import tqdm

import steam
import dirs

dirs.create_dirs()

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
from steamemu.clientupdateserver import clientupdateserver
from steamweb.steamweb import steamweb
from steamweb.steamweb import check_child_pid

#from steamemu.udpserver import udpserver

from Steam2.package import Package
from Steam2.neuter import neuter_file

local_ver = "0.73.1"
emu_ver = "0"
update_exception1 = ""
update_exception2 = ""
clear_config = False

try:
    mod_date_emu = os.path.getmtime("emulator.exe")
except:
    mod_date_emu = 0
try:
    mod_date_cach = os.path.getmtime("files/cache/emulator.ini.cache")
except:
    mod_date_cach = 0

clearConsole = lambda: os.system('cls' if os.name in ('nt', 'dos') else 'clear')
clearConsole()

if (mod_date_cach < mod_date_emu) and clear_config == True:
    #print("Config change detected, flushing cache...")
    try:
        shutil.rmtree("files/cache")
    except:
        pass
    #os.mkdir("files/cache")
    #shutil.copy("emulator.ini", "files/cache/emulator.ini.cache")
    #print

config = read_config()

print
print("Steam 2003-2011 Server Emulator v" + local_ver)
print(("=" * 33) + ("=" * len(local_ver)))
print
print(" -== Steam 20th Anniversary Edition 2003-2023 ==-")
print

if not config["emu_auto_update"] == "no":
    if sys.argv[0].endswith("emulator.exe"):
        try:
            if os.path.isfile("emulatorTmp.exe"):
                os.remove("emulatorTmp.exe")
            if os.path.isfile("emulatorNew.exe"):
                os.remove("emulatorNew.exe")
            # if clear_config == True :
                # print("Config change detected, flushing cache...")
                # shutil.rmtree("files/cache")
                # os.mkdir("files/cache")
                # shutil.copy("emulator.ini", "files/cache/emulator.ini.cache")
                # print
            if config["uat"] == "1":
                #url = "https://raw.githubusercontent.com/real-pmein1/stmemu-update-test/main/version"
                url = "https://raw.githubusercontent.com/real-pmein1/stmemu-update/main/version"
            else:
                url = "https://raw.githubusercontent.com/real-pmein1/stmemu-update/main/version"
            resp = requests.get(url)
            online_ver = resp.text

            for file in os.listdir("."):
                if file.endswith(".mst") or file.endswith(".out"):
                    emu_ver = file[7:-4]
                elif file.endswith(".pkg") or file.endswith(".srv"):
                    os.remove(file)
                    
            f = open("server_0.mst", "w")
            f.close()

            if not online_ver == emu_ver or not os.path.isfile("server_" + online_ver + ".mst"):
                shutil.copy("emulator.exe", "emulatorTmp.exe")
                print("Update found " + emu_ver + " -> " + online_ver + ", downloading...")
                if config["uat"] == "1":
                    #url = "https://raw.githubusercontent.com/real-pmein1/stmemu-update-test/main/server_" + online_ver + ".pkg"
                    url = "https://raw.githubusercontent.com/real-pmein1/stmemu-update/main/server_" + online_ver + ".pkg"
                else:
                    url = "https://raw.githubusercontent.com/real-pmein1/stmemu-update/main/server_" + online_ver + ".pkg"
                # Streaming, so we can iterate over the response.
                response = requests.get(url, stream=True)
                total_size_in_bytes= int(response.headers.get('content-length', 0))
                block_size = 1024 #1 Kilobyte
                progress_bar = tqdm(total=total_size_in_bytes, unit='iB', unit_scale=True, ncols=80)
                with open('server_' + online_ver + '.pkg', 'wb') as file:
                    for data in response.iter_content(block_size):
                        progress_bar.update(len(data))
                        file.write(data)
                progress_bar.close()
                if total_size_in_bytes != 0 and progress_bar.n != total_size_in_bytes:
                    print("ERROR, something went wrong")

                steam.package_unpack2('server_' + online_ver + '.pkg', ".", online_ver)

                for file in os.listdir("."):
                    if file.endswith(".mst") and file != "server_" + online_ver + ".mst" :
                        os.remove(file)
                    elif file.endswith(".out"):
                        os.remove(file)
                    elif file.endswith(".pkg"):
                        os.remove(file)
                subprocess.Popen("emulatorTmp.exe")
                sys.exit(0)

        except Exception as e:
            update_exception1 = e
            
        finally:
            if os.path.isfile("server_0.mst"): os.remove("server_0.mst")
    elif sys.argv[0].endswith("emulatorTmp.exe") and not os.path.isfile("emulatorNew.exe"):
        print("WAITING...")
        try:
            os.remove("emulator.exe")
            shutil.copy("emulatorTmp.exe", "emulator.exe")
            subprocess.Popen("emulator.exe")
            sys.exit(0)

        except Exception as e:
            update_exception2 = e
    else:
        print("WAITING...")
        try:
            os.remove("emulator.exe")
            shutil.copy("emulatorNew.exe", "emulator.exe")
            subprocess.Popen("emulator.exe")
            sys.exit(0)

        except Exception as e:
            update_exception2 = e
else:
    print("Skipping checking for updates (ini override)")

if config["http_port"].startswith(":"):
    print(config["http_port"])
    linenum = 0
    with open("emulator.ini", "r") as f:
        data = f.readlines()
    for line in data:
        if line.startswith("http_port"):
            break
        linenum += 1
    data[linenum] = "http_port=" + config["http_port"][1:] + "\n"
    with open("emulator.ini", "w") as g:
        g.writelines(data)
    if os.path.isfile("files/cache/emulator.ini.cache") :
        os.remove("files/cache/emulator.ini.cache")
    shutil.copy("emulator.exe", "emulatorTmp.exe")
    subprocess.Popen("emulatorTmp.exe")
    sys.exit(0)
    
if not os.path.isfile("files/cache/emulator.ini.cache") :
    print("Config change detected, flushing cache...")
    shutil.rmtree("files/cache")
    os.mkdir("files/cache")
    shutil.copy("emulator.ini", "files/cache/emulator.ini.cache")
    print
else :
    try:
        if filecmp.cmp("emulator.ini", "files/cache/emulator.ini.cache"): #false = different, true = same
            a=0
        else:
            print("Config change detected, flushing cache...")
            shutil.rmtree("files/cache")
            os.mkdir("files/cache")
            shutil.copy("emulator.ini", "files/cache/emulator.ini.cache")
            print
    except:
        print("Config change detected, flushing cache...")
        shutil.rmtree("files/cache")
        os.mkdir("files/cache")
        shutil.copy("emulator.ini", "files/cache/emulator.ini.cache")
        print

if len(config["public_ip"]) > len(config["server_ip"]):
    iplen = len(config["public_ip"])
else:
    iplen = len(config["server_ip"])

print(("*" * 11) + ("*" * iplen))
print("Server IP: " + config["server_ip"])
if config["public_ip"] != "0.0.0.0" :
    print("Public IP: " + config["public_ip"])
print(("*" * 11) + ("*" * iplen))
print
log = logging.getLogger('emulator')

if not update_exception1 == "":
    log.debug("Update1 error: " + str(update_exception1))
if not update_exception2 == "":
    log.debug("Update2 error: " + str(update_exception2))

try:
    socket.inet_aton(config["server_ip"])
except:
    log.debug("ERROR! The server ip is malformed, currently %s" % (config["server_ip"]))
    print("ERROR! The server ip is malformed, currently %s" % (config["server_ip"]))
    raw_input("Press Enter to exit...")
    quit()
try:
    socket.inet_aton(config["public_ip"])
except:
    log.debug("ERROR! The public ip is malformed, currently %s" % (config["public_ip"]))
    print("ERROR! The public ip is malformed, currently %s" % (config["public_ip"]))
    raw_input("Press Enter to exit...")
    quit()
try:
    socket.inet_aton(config["community_ip"])
except:
    log.debug("ERROR! The community ip is malformed, currently %s" % (config["community_ip"]))
    print("ERROR! The community ip is malformed, currently %s" % (config["community_ip"]))
    raw_input("Press Enter to exit...")
    quit()
    
server_ip_fail = False
counts=Counter(config["server_ip"])
if not counts['.'] == 3:
    log.debug("ERROR! The server ip is malformed, currently %s" % (config["server_ip"]))
    print("ERROR! The server ip is malformed, currently %s" % (config["server_ip"]))
    raw_input("Press Enter to exit...")
    quit()
for char in config["server_ip"]:
    if not (char >= '0' and char <= '9' or char == '.'):
        server_ip_fail = True
if server_ip_fail == True:
    log.debug("ERROR! The server ip is malformed, currently %s" % (config["server_ip"]))
    print("ERROR! The server ip is malformed, currently %s" % (config["server_ip"]))
    raw_input("Press Enter to exit...")
    quit()

if config["public_ip"] != "0.0.0.0" :
    public_ip_fail = False
    counts=Counter(config["public_ip"])
    if not counts['.'] == 3:
        log.debug("ERROR! The public ip is malformed, currently %s" % (config["public_ip"]))
        print("ERROR! The public ip is malformed, currently %s" % (config["public_ip"]))
        raw_input("Press Enter to exit...")
        quit()
    for char in config["public_ip"]:
        if not (char >= '0' and char <= '9' or char == '.'):
            public_ip_fail = True
    if public_ip_fail == True:
        log.debug("ERROR! The public ip is malformed, currently %s" % (config["public_ip"]))
        print("ERROR! The public ip is malformed, currently %s" % (config["public_ip"]))
        raw_input("Press Enter to exit...")
        quit()

if config["community_ip"] != "0.0.0.0" :
    public_ip_fail = False
    counts=Counter(config["community_ip"])
    if not counts['.'] == 3:
        log.debug("ERROR! The community ip is malformed, currently %s" % (config["community_ip"]))
        print("ERROR! The community ip is malformed, currently %s" % (config["community_ip"]))
        raw_input("Press Enter to exit...")
        quit()
    for char in config["community_ip"]:
        if not (char >= '0' and char <= '9' or char == '.'):
            public_ip_fail = True
    if public_ip_fail == True:
        log.debug("ERROR! The community ip is malformed, currently %s" % (config["community_ip"]))
        print("ERROR! The community ip is malformed, currently %s" % (config["community_ip"]))
        raw_input("Press Enter to exit...")
        quit()

log.info("...Starting Steam Server...")

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
            dedsrv_port = globalvars.addr[1]
            #print(dedsrv_port)
            if self.port == 27013 :
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
            #elif self.port == 27014 :
            #    log = logging.getLogger("27014")
            #    clientid = str(globalvars.addr) + ": "
            #    log.info(clientid + "Connected to 27014")
            #    log.debug(clientid + ("Received message: %s, from %s" % (globalvars.data, globalvars.addr)))
            elif self.port == 27014 : #was 27017
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
                log.debug(clientid + "Unconfigured UDP port requested: " + str(self.port))

config = read_config()

firstblob_eval = steam.load_ccdb()

#if firstblob_eval == "":
#    if os.path.isfile("files/1stcdr.py") :
#        with open("files/1stcdr.py", "r") as f:
#            firstblob = f.read()
#    elif os.path.isfile("files/firstblob.py") :
#        with open("files/firstblob.py", "r") as f:
#            firstblob = f.read()
#    else :
#        with open("files/firstblob.bin", "rb") as f:
#            firstblob_bin = f.read()
#        if firstblob_bin[0:2] == "\x01\x43":
#            firstblob_bin = zlib.decompress(firstblob_bin[20:])
#        firstblob_unser = steam.blob_unserialize(firstblob_bin)
#        firstblob = "blob = " + steam.blob_dump(firstblob_unser)

#    firstblob_eval = ast.literal_eval(firstblob[7:len(firstblob)])
globalvars.steam_ver = struct.unpack("<L", firstblob_eval["\x01\x00\x00\x00"])[0]
globalvars.steamui_ver = struct.unpack("<L", firstblob_eval["\x02\x00\x00\x00"])[0]
globalvars.record_ver = struct.unpack("<L", firstblob_eval["\x00\x00\x00\x00"])[0]

#globalvars.steam_ver = 2
#globalvars.steamui_ver = 2

# create the Steam.exe file
if globalvars.record_ver == 1 :
    #f = open(config["packagedir"] + "betav2/" + config["steampkg"], "rb")
    f = open(config["packagedir"] + "betav2/Steam_" + str(globalvars.steam_ver) + ".pkg", "rb")
else :
    #f = open(config["packagedir"] + config["steampkg"], "rb")
    f = open(config["packagedir"] + "Steam_" + str(globalvars.steam_ver) + ".pkg", "rb")
pkg = Package(f.read())
f.close()
if config["public_ip"] != "0.0.0.0" and not os.path.isdir("client/wan"):
    shutil.rmtree("client")
elif config["public_ip"] == "0.0.0.0" and os.path.isdir("client/wan"):
    shutil.rmtree("client")
dirs.create_dirs()
file = pkg.get_file("SteamNew.exe")
file2 = pkg.get_file("SteamNew.exe")
if config["public_ip"] != "0.0.0.0" :
    if not os.path.isdir("client/lan"): os.mkdir("client/lan")
    if not os.path.isdir("client/wan"): os.mkdir("client/wan")
    file = neuter_file(file, config["public_ip"], config["dir_server_port"], "SteamNew.exe", "wan")
    file2 = neuter_file(file2, config["server_ip"], config["dir_server_port"], "SteamNew.exe", "lan")
    f = open("client/wan/Steam.exe", "wb")
    f.write(file)
    f.close()
    g = open("client/lan/Steam.exe", "wb")
    g.write(file2)
    g.close()
else :
    file = neuter_file(file, config["server_ip"], config["dir_server_port"], "SteamNew.exe", "lan")
    f = open("client/Steam.exe", "wb")
    f.write(file)
    f.close()

if config["hldsupkg"] != "" :
    if globalvars.record_ver == 1 :
        g = open(config["packagedir"] + "betav2/" + config["hldsupkg"], "rb")
    else :
        g = open(config["packagedir"] + config["hldsupkg"], "rb")
    pkg = Package(g.read())
    g.close()
    file = pkg.get_file("HldsUpdateToolNew.exe")
    if config["public_ip"] != "0.0.0.0" :
        file = neuter_file(file, config["public_ip"], config["dir_server_port"], "HldsUpdateToolNew.exe", "wan")
    else :
        file = neuter_file(file, config["server_ip"], config["dir_server_port"], "HldsUpdateToolNew.exe", "lan")
    g = open("client/HldsUpdateTool.exe", "wb")
    g.write(file)
    g.close()

#NEED TO DEPRECATE THIS IN FAVOR OF PROTOCOL VERSIONING
if globalvars.steamui_ver < 61 : #guessing steamui version when steam client interface v2 changed to v3
    globalvars.tgt_version = "1"
else :
    globalvars.tgt_version = "2" #config file states 2 as default

if globalvars.steamui_ver < 122 : #guessing when CASPackage changed to cas_x.pkg
    if os.path.isfile("files/cafe/Steam.dll") :
        log.info("Cafe files found")
        g = open("files/cafe/Steam.dll", "rb")
        file = g.read()
        g.close()
        if config["public_ip"] != "0.0.0.0" :
            file_wan = neuter_file(file, config["public_ip"], config["dir_server_port"], "steam.dll", "wan")
            file_lan = neuter_file(file, config["server_ip"], config["dir_server_port"], "steam.dll", "lan")
            if os.path.isfile("files/cafe/CASpackage.zip") :
                shutil.copyfile("files/cafe/CASpackage.zip", "client/cafe_server/CASpackageWAN.zip")
                shutil.copyfile("files/cafe/CASpackage.zip", "client/cafe_server/CASpackageLAN.zip")
                with zipfile.ZipFile('client/cafe_server/CASpackageWAN.zip', 'a') as zipped_f:
                    zipped_f.writestr("Steam.dll", file_wan)
                with zipfile.ZipFile('client/cafe_server/CASpackageLAN.zip', 'a') as zipped_f:
                    zipped_f.writestr("Steam.dll", file_lan)
                    
                lsclient_line1 = "CAServerIP = " + config["public_ip"]
                lsclient_line2 = "ExitSteamAfterGame = true"
                lsclient_line3 = "AllowUserLogin = false"
                lsclient_line4 = "AllowCafeLogin = true"
                lsclient_lines = bytes(lsclient_line1 + "\n" + lsclient_line2 + "\n" + lsclient_line3 + "\n" + lsclient_line4)
                with zipfile.ZipFile('client/cafe_server/CASpackageWAN.zip', 'a') as zipped_f:
                    zipped_f.writestr("Client/lsclient.cfg", lsclient_lines)
                tempdir = tempfile.mkdtemp()
                try:
                    tempname = os.path.join(tempdir, 'new.zip')
                    with zipfile.ZipFile('client/cafe_server/CASpackageWAN.zip', 'r') as zipread:
                        with zipfile.ZipFile(tempname, 'w') as zipwrite:
                            for item in zipread.infolist():
                                if item.filename not in 'CAServer.cfg':
                                    data = zipread.read(item.filename)
                                    zipwrite.writestr(item, data)
                    shutil.move(tempname, 'client/cafe_server/CASpackageWAN.zip')
                finally:
                    shutil.rmtree(tempdir)
                    
                lsclient_line1 = "CAServerIP = " + config["server_ip"]
                lsclient_line2 = "ExitSteamAfterGame = true"
                lsclient_line3 = "AllowUserLogin = false"
                lsclient_line4 = "AllowCafeLogin = true"
                lsclient_lines = bytes(lsclient_line1 + "\n" + lsclient_line2 + "\n" + lsclient_line3 + "\n" + lsclient_line4)
                with zipfile.ZipFile('client/cafe_server/CASpackageLAN.zip', 'a') as zipped_f:
                    zipped_f.writestr("Client/lsclient.cfg", lsclient_lines)
                tempdir = tempfile.mkdtemp()
                try:
                    tempname = os.path.join(tempdir, 'new.zip')
                    with zipfile.ZipFile('client/cafe_server/CASpackageLAN.zip', 'r') as zipread:
                        with zipfile.ZipFile(tempname, 'w') as zipwrite:
                            for item in zipread.infolist():
                                if item.filename not in 'CAServer.cfg':
                                    data = zipread.read(item.filename)
                                    zipwrite.writestr(item, data)
                    shutil.move(tempname, 'client/cafe_server/CASpackageLAN.zip')
                finally:
                    shutil.rmtree(tempdir)
                    
                caserver_line1 = "MasterServerIP = " + config["public_ip"]
                caserver_line2 = "MasterLogin = " + config["cafeuser"]
                caserver_line3 = "MasterPass = " + config["cafepass"]
                caserver_line4 = "IPRange1 = 192.168.0.1"
                caserver_line5 = "EnableTimedUpdates = disable"
                caserver_line6 = "UpdateStart = 2200"
                caserver_line7 = "UpdateEnd = 0200"
                caserver_lines = bytes(caserver_line1 + "\n" + caserver_line2 + "\n" + caserver_line3 + "\n" + caserver_line4 + "\n" + caserver_line5 + "\n" + caserver_line6 + "\n" + caserver_line7)
                with zipfile.ZipFile('client/cafe_server/CASpackageWAN.zip', 'a') as zipped_f:
                    zipped_f.writestr("CAServer.cfg", caserver_lines)
                    
                caserver_line1 = "MasterServerIP = " + config["server_ip"]
                caserver_line2 = "MasterLogin = " + config["cafeuser"]
                caserver_line3 = "MasterPass = " + config["cafepass"]
                caserver_line4 = "IPRange1 = 192.168.0.1"
                caserver_line5 = "EnableTimedUpdates = disable"
                caserver_line6 = "UpdateStart = 2200"
                caserver_line7 = "UpdateEnd = 0200"
                caserver_lines = bytes(caserver_line1 + "\n" + caserver_line2 + "\n" + caserver_line3 + "\n" + caserver_line4 + "\n" + caserver_line5 + "\n" + caserver_line6 + "\n" + caserver_line7)
                with zipfile.ZipFile('client/cafe_server/CASpackageLAN.zip', 'a') as zipped_f:
                    zipped_f.writestr("CAServer.cfg", caserver_lines)
                    
                passwords_line = bytes(config["cafeuser"] + "%" + config["cafepass"])
                with zipfile.ZipFile('client/cafe_server/CASpackageWAN.zip', 'a') as zipped_f:
                    zipped_f.writestr("passwords.txt", passwords_line)
                    
                with zipfile.ZipFile('client/cafe_server/CASpackageLAN.zip', 'a') as zipped_f:
                    zipped_f.writestr("passwords.txt", passwords_line)
                    
                if os.path.isfile("files/cafe/README.txt") :
                    g = open("files/cafe/README.txt", "rb")
                    file = g.read()
                    g.close()
                    with zipfile.ZipFile('client/cafe_server/CASpackageWAN.zip', 'a') as zipped_f:
                        zipped_f.writestr("README.txt", file)
                    with zipfile.ZipFile('client/cafe_server/CASpackageLAN.zip', 'a') as zipped_f:
                        zipped_f.writestr("README.txt", file)
                        
                with open("client/wan/Steam.exe", "rb") as g:
                    file_wan = g.read()
                with open("client/lan/Steam.exe", "rb") as h:
                    file_lan = h.read()
                with zipfile.ZipFile('client/cafe_server/CASpackageWAN.zip', 'a') as zipped_f:
                    zipped_f.writestr("Client/wan/Steam.exe", file_wan)
                with zipfile.ZipFile('client/cafe_server/CASpackageLAN.zip', 'a') as zipped_f:
                    zipped_f.writestr("Client/wan/Steam.exe", file_lan)
        else :
            file = neuter_file(file, config["server_ip"], config["dir_server_port"], "steam.dll", "lan")
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
                if os.path.isfile("client/Steam.exe"):
                    g = open("client/Steam.exe", "rb")
                    file = g.read()
                    g.close()
                    with zipfile.ZipFile('client/cafe_server/CASpackage.zip', 'a') as zipped_f:
                        zipped_f.writestr("Client/Steam.exe", file)
                
        
if config["use_sdk"] == "1" :
    with open("files/pkg_add/steam/Steam.cfg", "w") as h :
        h.write('SdkContentServerAdrs = "' + config["sdk_ip"] + ':' + config["sdk_port"] + '"\n')
    if os.path.isfile("files/cache/Steam_" + str(globalvars.steam_ver) + ".pkg") :
        os.remove("files/cache/Steam_" + str(globalvars.steam_ver) + ".pkg")
else :
    if os.path.isfile("files/pkg_add/steam/Steam.cfg") :
        os.remove("files/cache/Steam_" + str(globalvars.steam_ver) + ".pkg")
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
log.info("Steam2 CSER Server listening on port 27013")
time.sleep(0.2)
dirlistener = listener(config["dir_server_port"], directoryserver, config)
dirlistener.start()
log.info("Steam2 General Directory Server listening on port " + str(config["dir_server_port"]))
time.sleep(0.2)
configlistener = listener(config["conf_server_port"], configserver, config)
configlistener.start()
log.info("Steam2 Config Server listening on port " + str(config["conf_server_port"]))
time.sleep(0.2)
authlistener = listener(config["auth_server_port"], authserver, config)
authlistener.start()
log.info("Steam2 Master Authentication Server listening on port " + str(config["auth_server_port"]))
time.sleep(0.2)
contentlistener = listener(config["contlist_server_port"], contentlistserver, config)
contentlistener.start()
log.info("Steam2 Content List Server listening on port " + str(config["contlist_server_port"]))
time.sleep(0.2)
filelistener = listener(config["file_server_port"], fileserver, config)
filelistener.start()
log.info("Steam2 Content Server listening on port " + str(config["file_server_port"]))
time.sleep(0.2)
clupdlistener = listener(config["clupd_server_port"], clientupdateserver, config)
clupdlistener.start()
log.info("Steam2 Client Update Server listening on port " + str(config["clupd_server_port"]))
time.sleep(0.2)
vallistener = listener(config["validation_port"], validationserver, config)
vallistener.start()
log.info("Steam2 User Validation Server listening on port " + str(config["validation_port"]))
time.sleep(0.2)
#hlmasterlistener = udplistener(27010, masterhl, config)
hlmasterlistener = masterhl(27010, masterhl, config)
hlmasterlistener.start()
log.info("Steam2 Master HL1 Server listening on port 27010")
time.sleep(0.2)
#hl2masterlistener = udplistener(27011, masterhl2, config)
hl2masterlistener = masterhl2(27011, masterhl2, config)
hl2masterlistener.start()
log.info("Steam2 Master HL2 Server listening on port 27011")
time.sleep(0.2)
#rdkfmasterlistener = udplistener(27012, masterrdkf, config)
rdkfmasterlistener = masterrdkf(27012, masterrdkf, config)
rdkfmasterlistener.start()
log.info("Steam2 Master RDKF Server listening on port 27012")
time.sleep(0.2)
if config["enable_steam3_servers"] == "1":
    twosevenzeroonefourlistener = udplistener(27014, twosevenzeroonefour, config)
    twosevenzeroonefourlistener.start()
    log.info("Steam3 CM Server 1 listening on port 27014")
    time.sleep(0.2)
if config["enable_steam3_servers"] == "1":
    chatlistener = udplistener(27017, friends, config)
    chatlistener.start()
    globalvars.tracker = 0
    log.info("Steam3 Chat Server listening on port 27017")
else:
    if globalvars.record_ver == 1 :
        globalvars.tracker = 1
        subprocess.Popen("trackerserver.exe")
        log.info("Started TRACKER server on port 1200")
    else :
        log.info("TRACKER unsupported on release client, not started")
time.sleep(0.2)
if config["use_webserver"] == "true" and os.path.isdir(config["apache_root"]):
    if globalvars.steamui_ver < 87 or config["http_port"] == "steam" or config["http_port"] == "0" :
        steamweb("80", config["http_ip"], config["apache_root"], config["web_root"])
        http_port = "80"
    else:
        steamweb(config["http_port"], config["http_ip"], config["apache_root"], config["web_root"])
        http_port = str(config["http_port"])#[1:]
    log.info("Steam Web Server listening on port " + http_port)
    find_child_pid_timer = threading.Timer(10.0, check_child_pid())  
    find_child_pid_timer.start() 
    time.sleep(0.2)
elif config["use_webserver"] == "true" and not os.path.isdir(config["apache_root"]):
    log.error("Cannot start Steam Web Server: apache folder is missing")
vttlistener = listener("27046", vttserver, config)
vttlistener.start()
log.info("Valve Time Tracking Server listening on port 27046")
time.sleep(0.2)
vttlistener2 = listener("27047", vttserver, config)
vttlistener2.start()
log.info("Valve CyberCafe Server listening on port 27047")
time.sleep(0.2)
if config["sdk_ip"] != "0.0.0.0" :
    log.info("Steamworks SDK Content Server configured on port " + str(config["sdk_port"]))
    time.sleep(0.2)
log.debug("TGT set to version " + globalvars.tgt_version)

if config["http_port"] == "steam" :
    log.info("...Steam Server ready using Steam DNS...")
else :
    log.info("...Steam Server ready...")
authlistener.join()
