import myimports
import binascii, ConfigParser, threading, logging, socket, time, os, shutil, zipfile, tempfile, zlib, sys
import os.path, ast, csv
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA
from Crypto.Cipher import AES
import struct #for int to byte conversion
import steam
import csclient
import encryption, utilities, globalvars, emu_socket
import dirs
import steamemu.logger
import globalvars
import steamemu.logger
import blob_utilities
from steamemu.config import read_config

from steamemu.converter import convertgcf
from steamemu.config import read_config
from steamemu.directoryserver import directoryserver
from steamemu.configserver import configserver
from steamemu.contentlistserver import contentlistserver
from steamemu.fileserver import fileserver
from steamemu.authserver import authserver
from steamemu.masterhl import masterhl
from steamemu.masterhl2 import masterhl2
from steamemu.friends import friendserver
from steamemu.vttserver import vttserver
from steamemu.trackerserver import trackerserver
from steamemu.cserserver import cserserver
from steamemu.harvestserver import harvestserver

from Steam2.package import Package
from Steam2.neuter import neuter_file

print("Steam 2004-2011 Server Emulator v0.60")
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
    firstblob_unser = blob_utilities.blob_unserialize(firstblob_bin)
    firstblob = blob_utilities.blob_dump(firstblob_unser)

firstblob_list = firstblob.split("\n")
steam_hex = firstblob_list[2][25:41]
steam_ver = str(int(steam_hex[14:16] + steam_hex[10:12] + steam_hex[6:8] + steam_hex[2:4], 16))
steamui_hex = firstblob_list[3][25:41]
steamui_ver = int(steamui_hex[14:16] + steamui_hex[10:12] + steamui_hex[6:8] + steamui_hex[2:4], 16)

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

log.info("Checking for gcf files to convert...")
convertgcf()

if config["public_ip"] is not None :
    serverip = config["public_ip"]
else:
    serverip = config["server_ip"]
    
time.sleep(0.2)
cserlistener = cserserver(serverip, 27013)
cserthread = threading.Thread(target=cserlistener.start)
cserthread.start()
log.info("CSER Server listening on port 27013")
time.sleep(0.2)
harvestlistener = harvestserver(serverip, 27055)
harvestthread = threading.Thread(target=harvestlistener.start)
harvestthread.start()
log.info("MiniDump Harvest Server listening on port 27055")
time.sleep(0.2)
hlmasterlistener = masterhl(serverip, 27010)
hlmasterthread = threading.Thread(target=hlmasterlistener.start)
hlmasterthread.start()
log.info("Master HL1 Server listening on port 27010")
time.sleep(0.2)
hl2masterlistener = masterhl2(serverip, 27011)
hl2masterthread = threading.Thread(target=hl2masterlistener.start)
hl2masterthread.start()
log.info("Master HL2 Server listening on port 27011")
time.sleep(0.2)
trackerlistener = trackerserver(serverip, 27014)
trackerthread = threading.Thread(target=trackerlistener.start)
trackerthread.start()
log.info("[2004-2007] Tracker Server listening on port 27014") #old 2004 tracker/friends CHAT SERVER
time.sleep(0.2)
if config["tracker_ip"] == "0.0.0.0" :
    friendslistener = friendserver(serverip, 27017)
    friendsthread = threading.Thread(target=friendslistener.start)
    friendsthread.start()
    globalvars.tracker = 0
    log.info("[2007+] Friends Server listening on port 27017")
else :
    globalvars.tracker = 1
    log.info("Connected to [2007+] Friends")
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
log.info("Valve CyberCafe server listening on port 27047")
time.sleep(0.2)
if config["sdk_ip"] != "0.0.0.0" :
    log.info("Steamworks SDK Content Server configured on port " + str(config["sdk_port"]))
    time.sleep(0.2)
log.info("Steam Server ready.")
authlistener.join()
if keyboard.is_pressed('esc'):
    vttlistener2.stop()
