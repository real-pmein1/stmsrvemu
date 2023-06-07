import threading, logging, time, os, os.path, msvcrt
import utilities, globalvars, emu_socket

from steamemu.config import read_config
from steamemu.config import save_config_value
from steamemu.converter import convertgcf
from steamemu.directoryserver import directoryserver
from steamemu.configserver import configserver
from steamemu.contentlistserver import contentlistserver
from steamemu.contentserver import contentserver
from steamemu.authserver import authserver
from steamemu.masterhl import masterhl
from steamemu.masterhl2 import masterhl2
from steamemu.messages import messagesserver
from steamemu.vttserver import vttserver
from steamemu.trackerserver import trackerserver
from steamemu.cserserver import cserserver
from steamemu.harvestserver import harvestserver

import python_check
# Check the Python version
python_check.check_python_version()


new_password = 0


from steamemu.config import read_config
config = read_config()

class listener(threading.Thread):
    def __init__(self, port, serverobject, config):
        self.port = int(port)
        self.serverobject = serverobject  
        self.config = config.copy()
        self.config["port"] = port
        threading.Thread.__init__(self)

    def run(self):
        serversocket = emu_socket.ImpSocket()
        serversocket.bind((config["server_ip"], self.port))
        serversocket.listen(5)

        #print "TCP Server Listening on port " + str(self.port)

        while True :
            (clientsocket, address) = serversocket.accept()
            self.serverobject((clientsocket, address), self.config).start();

#this checks if there is a peer password, if not itll generate one
if "peer_password" in config and config["peer_password"]:
    # The peer_password is present and not empty
    globalvars.peer_password = config["peer_password"]
else:
    # The peer_password is missing or empty
    # Generate a new password
    globalvars.peer_password = utilities.generate_password()

    # Save the new password to the config file
    save_config_value("peer_password", globalvars.peer_password)
    new_password = 1

print("Steam 2004-2011 Server Emulator v0.60")
print("=====================================")
print
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

#set serverip for the servers to use, depends on which config option is used.
if ("server_ip" not in config or not config["server_ip"]) and ("public_ip" not in config or not config["public_ip"]):
    globalvars.serverip = "127.0.0.1"
elif "server_ip" in config and config["server_ip"]:
    globalvars.serverip = config["server_ip"]
else:
    globalvars.serverip = config["public_ip"]

#call this function to edit the steam.exe and set the steam_/steamui_/hldsut_/lhldsut_ verstion number variables.
utilities.initialise()
time.sleep(0.2)

#launch directoryserver first so servers can heartbeat the moment they launch
if "is_masterdir" in config :
    log.info("Steam Master General Directory Server listening on port " + str(config["dir_server_port"]))
    
    if config["is_masterdir"] == "0" :
        log.info("Steam Slave General Directory Server listening on port " + str(config["dir_server_port"]))
else:
    log.info("Steam Master General Directory Server listening on port " + str(config["dir_server_port"]))
dirlistener = listener(config["dir_server_port"], directoryserver, config)
dirlistener.start()
time.sleep(0.8) #give us a little more time than usual to make sure we are initialized before servers start their heartbeat

cserlistener = cserserver(globalvars.serverip, 27013)
cserthread = threading.Thread(target=cserlistener.start)
cserthread.start()
log.info("CSER Server listening on port 27013")
time.sleep(0.2)

harvestlistener = harvestserver(globalvars.serverip, 27055)
harvestthread = threading.Thread(target=harvestlistener.start)
harvestthread.start()
log.info("MiniDump Harvest Server listening on port 27055")
time.sleep(0.2)

hlmasterlistener = masterhl(globalvars.serverip, 27010)
hlmasterthread = threading.Thread(target=hlmasterlistener.start)
hlmasterthread.start()
log.info("Master HL1 Server listening on port 27010")
time.sleep(0.2)

hl2masterlistener = masterhl2(globalvars.serverip, 27011)
hl2masterthread = threading.Thread(target=hl2masterlistener.start)
hl2masterthread.start()
log.info("Master HL2 Server listening on port 27011")
time.sleep(0.2)

trackerlistener = trackerserver(globalvars.serverip, 27014)
trackerthread = threading.Thread(target=trackerlistener.start)
trackerthread.start()
log.info("[2004-2007] Tracker Server listening on port 27014") #old 2004 tracker/friends CHAT SERVER
globalvars.tracker = 1
time.sleep(0.2)

messageslistener = messagesserver(globalvars.serverip, 27017)
messagesthread = threading.Thread(target=messageslistener.start)
messagesthread.start()
log.info("Client Messaging Server listening on port 27017")
time.sleep(0.2)

configlistener = listener(config["conf_server_port"], configserver, config)
configlistener.start()
log.info("Steam Config Server listening on port " + str(config["conf_server_port"]))
time.sleep(0.2)

contentlistlistener = listener(config["csds_port"], contentlistserver, config)
contentlistlistener.start()
log.info("Steam Content Server Directory Server listening on port " + str(config["csds_port"]))
time.sleep(0.2)

contentlistener = listener(config["content_server_port"], contentserver, config)
contentlistener.start()
log.info("Steam Content Server listening on port " + str(config["content_server_port"]))
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
#authlistener.join()

if new_password == 1 :
    log.info("New Peer Password Generated: " + peer_password)
    log.info("Make sure to give this password to any servers that may want to add themselves to your network!")

print("Press Escape to exit...")
while True:
    if msvcrt.kbhit() and ord(msvcrt.getch()) == 27:  # 27 is the ASCII code for Escape
        os._exit(0)
