import threading, logging, time, os, os.path, msvcrt
import utilities, globalvars, emu_socket
import steamemu.logger
import python_check

from steamemu.config import save_config_value
from steamemu.vttserver import vttserver
from steamemu.config import read_config

config = read_config()

# Check the Python version
python_check.check_python_version()

print("Steam 2004-2011 Valve CyberCafe Server Emulator v" + globalvars.emuversion)
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

vttserver(int("27046"), config).start()
log.info("Valve Time Tracking Server listening on port 27046")
time.sleep(0.2)

vttserver(int("27047"), config).start()
log.info("Valve CyberCafe server listening on port 27047")
time.sleep(0.2)

log.info("Steam CyberCafe Server's are ready.")

print("Press Escape to exit...")
while True:
    if msvcrt.kbhit() and ord(msvcrt.getch()) == 27:  # 27 is the ASCII code for Escape
        os._exit(0)

