import logging
import msvcrt
import os

#import scalene

# from scalene import scalene_profiler
import dirs
import globalvars
import logger
from config import get_config as read_config
from globalvars import local_ver
from servers.authserver import authserver
from utils import parent_initializer

globalvars.aio_server = False

# create directories
dirs.create_dirs()

# TODO uncomment for release
# clear the console of any garbage from previous commands
# clearConsole = lambda: os.system('cls' if os.name in ('nt', 'dos') else 'clear')
# clearConsole()

# initialize logger
logger.init_logger()
log = logging.getLogger('emulator')

# read the configuration file (emulator.ini)
config = read_config()

print("")
print(f"Steam 2002-2011 Server Emulator v{local_ver}")
print(("=" * 33) + ("=" * len(local_ver)))
print()
print(" -== Steam 20th Anniversary Edition 2003-2023 ==-")
print()

new_password = parent_initializer()

authserver(int(config["auth_server_port"]), config).run()
log.info(f"Steam2 Master Authentication Server listening on port {str(config['auth_server_port'])}")

while True:
    if ord(msvcrt.getch()) == 27:
        scalene.scalene_profiler.stop()
        os._exit(0)