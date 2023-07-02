import threading, logging, time, os, os.path, msvcrt, sys
import utilities, globalvars, emu_socket
import steamemu.logger
import python_check
from command_input import InputManager
from steamemu.config import read_config
from steamemu.converter import convertgcf
from steamemu.directoryserver import directoryserver, manager as dirmanager
from steamemu.configserver import configserver
from steamemu.contentlistserver import contentlistserver, manager as csdsmanager
from steamemu.contentserver import contentserver
from steamemu.authserver import authserver
from steamemu.masterhl import masterhl
from steamemu.masterhl2 import masterhl2
from steamemu.messages import messagesserver
from steamemu.vttserver import vttserver
from steamemu.trackerserver import trackerserver
from steamemu.cserserver import cserserver
from steamemu.harvestserver import harvestserver
from steamemu.validationserver import validationserver
from steamemu.administrationservers import administrationservers
from steamemu.miscservers import miscservers
from steamemu.logstatusservers import logstatusservers

global dirmanager, csdsmanager

# Check the Python version
python_check.check_python_version()

class EmuInputManager(InputManager):
    def process_input(self, c):
        if c == '\r':
            if self.input_buffer.strip() == 'showdirlist':
                print(" ")
                dirmanager.print_dirserver_list()
            elif self.input_buffer.strip() == 'showcslist':
                print(" ")
                csdsmanager.print_contentserver_list()
            elif self.input_buffer.strip() == 'exit' or self.input_buffer.strip() == 'quit':
                os._exit(0)
            else :
                print("\n Unknown Command:  " + self.input_buffer)
            self.input_buffer = ''
        elif c == '\x08':
            if self.input_buffer:
                 # Clear the last character on the screen
                sys.stdout.write('\b ')
                sys.stdout.flush()
                # Remove the last character
                self.input_buffer = self.input_buffer[:-1]
        elif c == '\x1b':
            os._exit(0)
        else:
            self.input_buffer += c #this allows for more than 1 character at a time         

config = read_config()

#Set is dir server slave or master
globalvars.dir_ismaster = int(config["dir_ismaster"])
#Set emulator version
globalvars.emuversion = str(config["emu_version"])
#set the ip and port for id ticket validation server
globalvars.validation_ip = config["validation_ip"]
globalvars.validation_port = int(config["validation_server_port"])
globalvars.cs_region = config["cs_region"]

#check for a peer_password, otherwise generate one
new_password = utilities.check_peerpassword()

print("Steam 2004-2011 Server Emulator v" + globalvars.emuversion)
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

#check local ip and set globalvars.serverip
utilities.checklocalipnet()

#call this function to call the neuter stuff.
utilities.initialise()
time.sleep(0.2)

#launch directoryserver first so server can heartbeat the moment they launch
if globalvars.dir_ismaster == 1 :
    log.info("Steam Master General Directory Server listening on port " + str(config["dir_server_port"]))
else:
    log.info("Steam Slave General Directory Server listening on port " + str(config["dir_server_port"]))
    
directoryserver(int(config["dir_server_port"]), config).start()
time.sleep(1.0) #give us a little more time than usual to make sure we are initialized before servers start their heartbeat

threading.Thread(target=cserserver(globalvars.serverip, int(config["cser_server_port"])).start).start()
log.info("CSER Server listening on port " + str(config["cser_server_port"]))
time.sleep(0.5)

threading.Thread(target=harvestserver(globalvars.serverip, int(config["harvest_server_port"])).start).start()
log.info("MiniDump Harvest Server listening on port " + str(config["harvest_server_port"]))
time.sleep(0.5)

threading.Thread(target=masterhl(globalvars.serverip, int(config["masterhl1_server_port"])).start).start()
log.info("Master HL1 Server listening on port " + str(config["masterhl1_server_port"]))
time.sleep(0.5)

threading.Thread(target=masterhl2(globalvars.serverip, int(config["masterhl2_server_port"])).start).start()
log.info("Master HL2 Server listening on port " + str(config["masterhl2_server_port"]))
time.sleep(0.5)

threading.Thread(target=trackerserver(globalvars.serverip, int(config["tracker_server_port"])).start).start()
log.info("[2004-2007] Tracker Server listening on port " + str(config["tracker_server_port"])) 
globalvars.tracker = 1
time.sleep(0.5)

threading.Thread(target=messagesserver(globalvars.serverip, int(config["cm_server_port"])).start).start()
log.info("Client Messaging Server listening on port " + str(config["cm_server_port"]))
time.sleep(0.2)

configserver(int(config["config_server_port"]), config).start()
log.info("Steam Config Server listening on port " + str(config["config_server_port"]))
time.sleep(0.5)

contentlistserver(int(config["csd_server_port"]), config).start()
log.info("Steam Content Server Directory Server listening on port " + str(config["csd_server_port"]))
time.sleep(0.5)

contentserver(int(config["content_server_port"]), config).start()
log.info("Steam Content Server listening on port " + str(config["content_server_port"]))
time.sleep(0.5)

authserver(int(config["auth_server_port"]), config).start()
log.info("Steam Master Authentication Server listening on port " + str(config["auth_server_port"]))
time.sleep(0.5)

validationserver(int(config["validation_server_port"]), config).start()
log.info("Steam User ID Validation Server listening on port " + str(config["validation_server_port"]))
time.sleep(0.5)

vttserver(config["vtt_server_port1"], config).start()
log.info("Valve Time Tracking Server listening on port " + str(config["vtt_server_port1"]))
time.sleep(0.2)

vttserver(config["vtt_server_port2"], config).start()
log.info("Valve CyberCafe server listening on port " + str(config["vtt_server_port2"]))
time.sleep(0.2)

logstatusservers(int(config["status_server_port"]), config).start()
log.info("Valve Log & Status servers listening on port " + str(config["status_server_port"]) + " TCP & UDP")
time.sleep(0.2)

miscservers(int(config["misc_server_port"]), config).start()
log.info("Valve MISC servers listening on port " + str(config["misc_server_port"]) + " TCP & UDP")
time.sleep(0.2)

administrationservers(int(config["admin_server_port"]), config).start()
log.info("Valve Administration servers listening on port " + str(config["admin_server_port"]) + " TCP & UDP")
time.sleep(0.2)

if config["sdk_ip"] != "0.0.0.0" :
    log.info("Steamworks SDK Content Server configured on port " + str(config["sdk_port"]))
    time.sleep(0.2)
    
log.info("Steam Servers are ready.")

if new_password == 1 :
    log.info("New Peer Password Generated: \033[1;33m{}\033[0m".format(globalvars.peer_password))
    log.info("Make sure to give this password to any servers that may want to add themselves to your network!")

input_buffer = ""
print("Press Escape to exit...")
input_manager = EmuInputManager()
input_manager.start_input()