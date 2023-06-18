import threading, logging, time, os, os.path, msvcrt
import utilities, globalvars, emu_socket
import steamemu.logger
import python_check

from steamemu.config import save_config_value
from steamemu.directoryserver import directoryserver
from steamemu.config import read_config

config = read_config()

# Check the Python version
python_check.check_python_version()

#check for a peer_password, otherwise generate one
new_password = utilities.check_peerpassword()

print("Steam 2004-2011 Directory Server Emulator v" + globalvars.emuversion)
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

#launch directoryserver first so servers can heartbeat the moment they launch
if globalvars.dir_ismaster == 1 :
    log.info("Steam Master General Directory Server listening on port " + str(config["dir_server_port"]))
else:
    log.info("Steam Slave General Directory Server listening on port " + str(config["dir_server_port"]))
    
directoryserver(int(config["dir_server_port"]), config).start()
#time.sleep(1.0) #give us a little more time than usual to make sure we are initialized before servers start their heartbeat
    
log.info("Steam Directory Server is ready.")

if new_password == 1 :
    log.info("New Peer Password Generated: \033[1;33m{}\033[0m".format(globalvars.peer_password))
    log.info("Make sure to give this password to any servers that may want to add themselves to your network!")

print("Press Escape to exit...")
while True:
    if msvcrt.kbhit() and ord(msvcrt.getch()) == 27:  # 27 is the ASCII code for Escape
        os._exit(0)

    