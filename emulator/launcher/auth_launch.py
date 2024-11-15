import logging
import msvcrt
import os
import threading
import time

import globalvars
import utils
from config import get_config as read_config
from globalvars import local_ver
from servers.authserver import authserver
# from servers.authserverv3 import authserverv3



# BEN NOTE: uncomment for realse
# clearConsole = lambda: os.system('cls' if os.name in ('nt', 'dos') else 'clear')
# clearConsole()

# logger.start_logging_thread() # Start Logger Thread
# ^ is technically not needed

def watchescape_thread():
    while True:
        time.sleep(0.1)
        if ord(msvcrt.getch()) == 27:
            os.exit(0)


thread2 = threading.Thread(target = watchescape_thread)
thread2.daemon = True
thread2.start()

config = read_config()

print("")
print("Steam 2003-2011 Server Emulator v" + local_ver)
print(("=" * 33) + ("=" * len(local_ver)))
print("")
print(" -== Steam 20th Anniversary Edition 2003-2023 ==-")
print("")

globalvars.aio_server = True
globalvars.cs_region = 'US' if config["override_ip_country_region"].lower() == 'false' else config["override_ip_country_region"].upper()
globalvars.dir_ismaster = "true"
globalvars.server_ip = config["server_ip"]

log = logging.getLogger('emulator')

utils.initialize()

log.info("...Starting Steam Server...")

utils.finalinitialize(log)

# check for a peer_password, otherwise generate one
new_password = utils.check_peerpassword()


authserver(int(config["auth_server_port"]), config).start()
log.info("Steam2 Master Authentication Server listening on port " + str(config["auth_server_port"]))

log.debug("TGT set to version " + globalvars.tgt_version)

log.info("...Steam Server ready...")

if new_password == 1:
    log.info("New Peer Password Generated: \033[1;33m{}\033[0m".format(globalvars.peer_password))
    log.info("Make sure to give this password to any servers that may want to add themselves to your network!")

# input_buffer = ""
# input_manager = DirInputManager()
# input_manager.start_input()
print("Press Escape to exit...")