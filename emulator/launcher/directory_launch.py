import logging
import msvcrt
import os
import threading
import time

import globalvars
import utils
from config import get_config as read_config
from globalvars import local_ver
from servers.directoryserver import directoryserver


# BEN NOTE: uncomment for release
# clearConsole = lambda: os.system('cls' if os.name in ('nt', 'dos') else 'clear')
# clearConsole()

def watchescape_thread():
    while True:
        time.sleep(0.1)
        if ord(msvcrt.getch()) == 27:
            os.exit(0)


thread2 = threading.Thread(target = watchescape_thread).start()

config = read_config()

print("")
print(f"Steam 2003-2011 Directory Server Emulator v {local_ver}")
print(("=" * 33) + ("=" * len(local_ver)))
print("")
print(" -== Steam 20th Anniversary Edition 2003-2023 ==-")
print("")

globalvars.aio_server = False  # Always false unless launching all servers inside the same process (such as: emulator.py)
globalvars.cs_region = 'US' if config["override_ip_country_region"].lower() == 'false' else config["override_ip_country_region"].upper()
globalvars.dir_ismaster = config["dir_ismaster"].lower()
globalvars.server_ip = config["server_ip"]

log = logging.getLogger('[DIR]emulator')

# we skip initialize and final initialization because we dont need anything
# neutered by this server.

utils.checkip(log)
utils.setpublicip()

log.info("...Starting Steam Server...")

# check for a peer_password, otherwise generate one
new_password = utils.check_peerpassword()

directoryserver(int(config["dir_server_port"]), config).start()
# launch directoryserver first so server can heartbeat the moment they launch
if globalvars.dir_ismaster is "true":
    log.info(f"Steam Master General Directory Server listening on port {config['dir_server_port']}")
else:
    log.info(f"Steam Slave General Directory Server listening on port {config['dir_server_port']}")

if new_password == 1:
    log.info(f"New Peer Password Generated: \033[1;33m{globalvars.peer_password}\033[0m")
    log.info("Make sure to give this password to any servers that may want to add themselves to your network!")

# input_buffer = ""
# input_manager = DirInputManager()
# input_manager.start_input()
print("Press Escape to exit...")