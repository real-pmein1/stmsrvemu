import logging
import os
import time
import sys

import dirs
from utilities.inputmanager import start_watchescape_thread

# Determine the application path
if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
else:
    application_path = os.path.dirname(os.path.abspath(__file__))

# Change the working directory to the directory of the executable
os.chdir(application_path)

import globalvars
import utils


dirs.create_dirs()

# Initial setup
utils.check_autoip_config()
globalvars.ORIGINAL_PYTHON_EXECUTABLE = sys.executable
globalvars.ORIGINAL_CMD_ARGS = sys.argv

import logger
from config import get_config as read_config

config = read_config()

# Initialize logger and configuration
logger.init_logger()
log = logging.getLogger('Content Server')

config = read_config()
if config["uat"] != "1":
    clear_console = lambda: os.system('cls' if os.name in ('nt', 'dos') else 'clear')
    clear_console()

# Start watching for 'esc' keyboard key
start_watchescape_thread()

from servers.contentserver import contentserver

globalvars.aio_server = False

# Initialize parent and print server info
new_password = utils.standalone_parent_initializer()
print(f"\nSteam Content Server Emulator v{globalvars.local_ver}")
print("=" * (33 + len(globalvars.local_ver)))
print("\n -== Half-Life 2 20th Anniversary Celebration 2004-2024 ==-\n")
log.info("   ---Starting Steam Content Server---   ")

# Start content server
csserver = contentserver(int(config["content_server_port"]), config)
csserver.daemon = False
csserver.start()
csserver.join()
log.info(f"Steam2 Content Server listening on port {config['content_server_port']}")

log.info("...Steam Content Server ready...")

if new_password == 1:
    log.info(f"New Peer Password Generated: \033[1;33m{globalvars.peer_password}\033[0m")
    log.info("Make sure to give this password to any servers that may want to add themselves to your network!")

utils.print_stmserver_ipaddresses()
time.sleep(1)  # This is needed for the following line to show up AFTER the server initialization information
input("Press Escape to exit...")