import logging
import os
import platform
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
from servers.clientupdateserver import clientupdateserver
globalvars.current_os = platform.system()
globalvars.aio_server = False

# Initialize parent and print server info. standalone_parent_initializer
# also loads the RSA keypair (main_key + network_key) so OfficialCSDSRegistrar
# has the keys it needs to sign the SSNet auth challenge and advertise the
# box identity in tag 6 of CContentServerStatusRecord.
# server_type=4 = ContentServer (skips AuthServer/CU-only init paths).
new_password = utils.standalone_parent_initializer(server_type=4)
print(f"\nSteam Content Server Emulator v{globalvars.local_ver}")
print("=" * (33 + len(globalvars.local_ver)))
print("\n -== Half-Life 2 20th Anniversary Celebration 2004-2024 ==-\n")
log.info("   ---Starting Steam Content Server---   ")

# Start the Content Server. Instantiating it kicks off the CSDS registrar
# daemon thread, which immediately starts the SSNet handshake against
# csds_official_host:csds_official_port (default 127.0.0.1:28097).
csserver = contentserver(int(config["content_server_port"]), config)
csserver.daemon = True
csserver.start()
log.info(f"Steam2 Content Server listening on port {config['content_server_port']}")

# Start the Client Update Server. In official-CSDS mode the CU does NOT
# register a separate SSNet session - the CS's registration already
# advertises this box as both a ClientContent peer (manifests/storages on
# port 27030) and a PublicContent peer (.pkg downloads). The CU just
# listens. In emulated-CSDS mode the CU runs its own legacy heartbeat.
log.info("   ---Starting Steam Client Update Server---   ")
cuserver = clientupdateserver(int(config["clupd_server_port"]), config)
cuserver.daemon = True
cuserver.start()
log.info(f"Steam2 Client Update Server listening on port {config['clupd_server_port']}")

log.info("...Steam Content + Update Servers ready...")

if new_password == 1:
    log.info(f"New Peer Password Generated: \033[1;33m{globalvars.peer_password}\033[0m")
    log.info("Make sure to give this password to any servers that may want to add themselves to your network!")

utils.print_stmserver_ipaddresses()

# Briefly let the CSDS handshake threads finish so their progress is visible
# before the "Press Escape" prompt scrolls into view.
time.sleep(2)

# Block on input so the daemon CS+CU threads keep running. Closing stdin
# (Ctrl+D / EOF) or hitting Enter exits.
try:
    input("Press Enter to exit...")
except (EOFError, KeyboardInterrupt):
    pass