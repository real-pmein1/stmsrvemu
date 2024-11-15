import logging
import os
import threading
import time
import sys
import subprocess
import platform
import shutil
import globalvars
from utilities.thread_handler import start_server_thread, start_watchdog
import utilities.encryption as encryption

try:
    # Delete the mariadb log at launch, this allows people to grab the log if it errors after shutting down, but also
    # keeps the hard-drive free of gb sized logs
    shutil.rmtree("logs/mariadb_general.log", ignore_errors = True)
except:
    pass

# Define the global thread exception handler
def global_thread_exception_handler(args):
    logging.getLogger('threadhndl').error(
        f"Exception in thread '{args.thread.name}': {args.exc_type.__name__}: {args.exc_value}",
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback)
    )

# Set the threading.excepthook to the handler function
threading.excepthook = global_thread_exception_handler

# Create the dirs earlier for upgrading safety
import dirs
from config import get_config as read_config

config = read_config()
dirs.create_dirs()

if config['http_ip'] != "" and config["http_domainname"] != "":
    logging.error("Detected conflicting configurations:\n'http_ip' AND 'http_domainname' are set at the same time.\nPlease comment one out in order to run the server.\n")

# Check if both files exist AND if they match what the config says
if encryption.check_file_hashes() is False:
    # Generate and export the keys
    encryption.generate_and_export_rsa_keys()

encryption.main_key, encryption.network_key = encryption.import_rsa_keys()
encryption.BERstring = encryption.network_key.public_key().export_key("DER")
encryption.signed_mainkey_reply = encryption.get_mainkey_reply()


def stmserver_initialization():
    global config, log

    # operating system check
    globalvars.current_os = platform.system()
    globalvars.aio_server = True

    from utilities.inputmanager import start_watchescape_thread
    from utilities import auto_swap_blob

    if getattr(sys, 'frozen', False):
        # If the application is frozen (compiled with PyInstaller), this will be the path to the emulator.exe (not the temporary folder/drive that pyinstaller creates to run)
        application_path = os.path.dirname(sys.executable)
    else:
        application_path = os.path.dirname(os.path.abspath(__file__))

    # Change the working directory to the directory of the executable
    os.chdir(application_path)

    import utils
    duplicates = utils.check_ini_duplicates()

    import logger
    logger.init_logger()
    log = logging.getLogger('emulator')

    if duplicates:
        log.error("Duplicate lines found in emulator.ini: ", duplicates)
        input("Cannot continue, press ENTER to exit.")
        sys.exit(1)

    utils.check_autoip_config()
    globalvars.ORIGINAL_PYTHON_EXECUTABLE = sys.executable
    globalvars.ORIGINAL_CMD_ARGS = sys.argv

    # The following renames the custom folder to the blob_add
    # utils.rename_custom_folder()

    from utilities import firstrun
    from utilities.database.setup_mariadb import setup_mariadb
    # from utils import flush_cache, parent_initializer, autoupdate, every
    from utils import parent_initializer, autoupdate, is_30_minutes_or_less
    from utilities.time import every

    # Check ticket expiration config to ensure it is set to a time higher than 30 minutes
    result = is_30_minutes_or_less(config['ticket_expiration_time_length'])
    if result:
        config['ticket_expiration_time_length'] = "0d0h45m0s"

    autoupdate()
    if config["subtract_time"] != "0":
        auto_swap_blob.swap_blobs()
    if config["auto_blobs"] == "true":
        print("Auto-blob rolling activated")
        threading.Thread(target = lambda:every(60, auto_swap_blob.swap_blobs)).start()

    # initialize logger, emulator.ini and mariadb if needed
    if not os.path.exists(config['configsdir'] + '\\' + '.initialized'):
        firstrun.check_initialization()
    config = read_config()
    #if config["uat"] != "1":
    #    clearConsole = lambda:os.system('cls' if os.name in ('nt', 'dos') else 'clear')
    #    clearConsole()

    # start watching for 'esc' keyboard key
    start_watchescape_thread()

    # setup the built in mysql for the first time if it isnt already setup
    if config["use_builtin_mysql"].lower() == "true":
        setup_mariadb(config)
    return parent_initializer, utils


parent_initializer, utils = stmserver_initialization()

from servers.authserver import authserver
from servers.beta_authserver import Beta1_AuthServer
from servers.clientupdateserver import clientupdateserver
from steam3.cmserver_udp import CMServerUDP_27014, CMServerUDP_27017
from steam3.cmserver_tcp import CMServerTCP_27014, CMServerTCP_27017
from servers.configserver import configserver
from servers.contentlistserver import contentlistserver
from servers.contentserver import contentserver
from servers.cserserver import CSERServer
from servers.directoryserver import directoryserver
from servers.harvestserver import HarvestServer
from servers.masterserver import MasterServer
from servers.trackerserver_beta import TrackerServer
from servers.validationserver import validationserver
from servers.valve_anticheat1 import VAC1Server
from servers.vttserver import cafeserver, vttserver
from steamweb.ftp import create_ftp_server
from steamweb.steamweb import check_child_pid, steamweb
from utilities.filesystem_monitor import DirectoryMonitor
from utilities import filesystem_monitor
# TODO Finish this before .81
# from servers.administrationserver import administrationserver


# TEST LOGGING
# log.debug("LOG TEST - DEBUG")
# log.info("LOG TEST - INFO")
# log.warning("LOG TEST - WARNING")
# log.error("LOG TEST - ERROR")
# log.critical("LOG TEST - CRITICAL")

new_password = parent_initializer()

#if config["uat"] != "1":
#    clearConsole = lambda:os.system('cls' if os.name in ('nt', 'dos') else 'clear')
#    clearConsole()

log.info("---Starting Steam Server---")

# launch directoryserver first so server can heartbeat the moment they launch
dirserver = directoryserver(int(config["dir_server_port"]), config)
start_server_thread(dirserver, 'DirectoryServer', None)

# Print if Directoryserver is a slave or a master
if globalvars.dir_ismaster == "true":
    log.info(f"Steam Master General Directory Server listening on port {str(config['dir_server_port'])}")
else:
    log.info(f"Steam Slave General Directory Server listening on port {str(config['dir_server_port'])}")

cser_server = CSERServer(int(config["cser_server_port"]), config)
start_server_thread(cser_server, 'CSERServer', 'Client Stats & Error Reporting Server')

# Content List Server
content_list_server = contentlistserver(int(config["contentdir_server_port"]), config)
start_server_thread(content_list_server, 'ContentListServer', 'Content List Directory Server')

# Content Server
content_server = contentserver(int(config["content_server_port"]), config)
start_server_thread(content_server, 'ContentServer', 'Application Content Server')

# Other servers
client_update_server = clientupdateserver(int(config["clupd_server_port"]), config)
start_server_thread(client_update_server, 'ClientUpdateServer', 'Client Update Server')

# Start the watchdog after launching server threads
start_watchdog()

config_server = configserver(int(config["config_server_port"]), config)
start_server_thread(config_server, 'ConfigServer', 'Configuration Server')

auth_server = authserver(int(config["auth_server_port"]), config)
start_server_thread(auth_server, 'AuthServer', 'Authentication Server')

validation_server = validationserver(int(config["validation_port"]), config)
start_server_thread(validation_server, 'ValidationServer', 'Steam2 User Validation Server')

master_server = MasterServer(int(config["masterhl1_server_port"]), config)
start_server_thread(master_server, 'MasterServer', 'Master Server')

harvest_server = HarvestServer(int(config["harvest_server_port"]), config)
start_server_thread(harvest_server, 'HarvestServer', 'Harvest Server')

vtt_server = vttserver(config["vtt_server_port"], config)
start_server_thread(vtt_server, 'VTTServer', 'Valve Time Tracking Server')

cafe_server = cafeserver(config["cafe_server_port"], config)
start_server_thread(cafe_server, 'CafeServer', 'Valve CyberCafe Master Server')

if config["enable_steam3_servers"].lower() == "true":
    if config["run_all_servers"].lower() == "true":
        cmtcp27014_server = CMServerTCP_27014(27014, config, master_server)
        start_server_thread(cmtcp27014_server, 'CMTCP27014', 'Valve Connection Manager (CM) 1 TCP Server')
        cmudp27014_server = CMServerUDP_27014(27014, config, master_server)
        start_server_thread(cmudp27014_server, 'CMUDP27014', 'Valve Connection Manager (CM) 1 UDP Server')
        cmtcp27017_server = CMServerTCP_27017(27017, config, master_server)
        start_server_thread(cmtcp27017_server, 'CMTCP27017', 'Valve Connection Manager (CM) 2 TCP Server')
        cmudp27017_server = CMServerUDP_27017(27017, config, master_server)
        start_server_thread(cmudp27017_server, 'CMUDP27017', 'Valve Connection Manager (CM) 2 UDP Server')
    else:
        if globalvars.steamui_ver < 479:
            # 27014 only needs to be active for steamui versions below 479
            cmtcp27014_server = CMServerTCP_27014(27014, config, master_server)
            start_server_thread(cmtcp27014_server, 'CMTCP27014', 'Valve Connection Manager (CM) 1 TCP Server')
            cmudp27014_server = CMServerUDP_27014(27014, config, master_server)
            start_server_thread(cmudp27014_server, 'CMUDP27014', 'Valve Connection Manager (CM) 1 UDP Server')
        else:
            cmtcp27017_server = CMServerTCP_27017(27017, config, master_server)
            start_server_thread(cmtcp27017_server, 'CMTCP27017', 'Valve Connection Manager (CM) 2 TCP Server')
            cmudp27017_server = CMServerUDP_27017(27017, config, master_server)
            start_server_thread(cmudp27017_server, 'CMUDP27017', 'Valve Connection Manager (CM) 2 UDP Server')

if config["run_all_servers"].lower() == "true":
    tracker_server = TrackerServer(1200, config)
    start_server_thread(tracker_server, 'TrackerServer', 'Tracker Server')
    log.info("Made by ymgve Modified by STMServer Team")
    vac_server = VAC1Server(int(config["vac_server_port"]), config)
    start_server_thread(vac_server, 'VAC1Server', 'Valve Anti-Cheat V1 Server')
    if os.path.isfile("files/secondblob.bin"): # Leave until beta blobs are in the CDDB
        beta1auth_server = Beta1_AuthServer(5273, config)
        start_server_thread(beta1auth_server, 'Beta1Server', 'Beta 1 (2002) Client Authentication Server')
    ftp_server_thread = threading.Thread(target=create_ftp_server, args=("files/temp", "files/beta1_ftp", globalvars.server_ip, int(config['ftp_server_port'])))
    start_server_thread(ftp_server_thread, 'FTPUpdateServer', '2002 Beta 1 Update FTP Server')
else:
    if int(globalvars.steamui_ver) < 120:
        tracker_server = TrackerServer(1200, config)
        start_server_thread(tracker_server, 'TrackerServer', 'Tracker Server')
        log.info("Made by ymgve Modified by STMServer Team")

        if int(globalvars.steam_ver) <= 14:
            vac_server = VAC1Server(int(config["vac_server_port"]), config)
            start_server_thread(vac_server, 'VAC1Server', 'Valve Anti-Cheat V1 Server')

        if globalvars.record_ver == 0:
            beta1auth_server = Beta1_AuthServer(5273, config)
            start_server_thread(beta1auth_server, 'Beta1Server', 'Beta 1 (2002) Client Authentication Server')

            ftp_server_thread = threading.Thread(target=create_ftp_server, args=("files/temp", "files/beta1_ftp", globalvars.server_ip, int(config['ftp_server_port'])))
            start_server_thread(ftp_server_thread, 'FTPUpdateServer', '2002 Beta 1 Update FTP Server')

# TODO Finish this before .81
# admin_server = administrationserver(config["admin_server_port"], config)
# start_server_thread(admin_server, 'AdminServer', 'STMServer Administration Server')


apache_root_exists = True if os.path.isdir(config["apache_root"]) else False

if globalvars.use_webserver and config["http_ip"] == "":
    if apache_root_exists:
        steamweb("80", config["server_ip"], config["apache_root"], config["web_root"])

        log.info(f"Steam Web Server listening on port 80")
        find_child_pid_timer = threading.Timer(10.0, check_child_pid()).start()
    else:
        log.error("Cannot start Steam Web Server: apache folder is missing")
else:
    log.info("Steam web services configured to " + config["http_ip"])

if (config["use_sdk"].lower() != "false" or config["use_sdk_as_cs"].lower() != 'false'):
    # TODO Should we launch the steamworks sdk content server? or let the user launch it themselves?
    log.info(f"Steamworks SDK Content Server configured on port {str(config['sdk_port'])}")

if new_password == 1:
    log.info("New Peer Password Generated: \033[1;33m{}\033[0m".format(globalvars.peer_password))
    log.info("Make sure to give this password to any servers that may want to add themselves to your network!")

directories_to_watch = {
os.path.abspath('files/mod_blob'),
}
# Monitor changes to secondblob.bin/py in the background while server is running
specific_files_to_watch = {
    os.path.abspath("files/secondblob.bin"),
    os.path.abspath("files/secondblob.py"),
    os.path.abspath("emulator.ini"),
    os.path.abspath('files/mod_blob'),
}
filesystem_monitor.specific_files_to_watch = specific_files_to_watch
paths_to_monitor = list(specific_files_to_watch) + list(directories_to_watch)
directory_monitor = DirectoryMonitor(paths = paths_to_monitor, directories_to_watch = directories_to_watch)
directory_monitor.start()

time.sleep(1)  # This is needed for the following line to show up AFTER the sever initialization information

if config["log_level"] == "logging.INFO":
    clearConsole = lambda:os.system('cls' if os.name in ('nt', 'dos') else 'clear')
    clearConsole()
    
print("")
print(f"Steam 2002-2011 Server Emulator v{globalvars.local_ver}")
print(("=" * 33) + ("=" * len(globalvars.local_ver)))
print()
print(" -== Half-Life 2 20th Anniversary Celebration 2004-2024 ==-")
print()

utils.print_stmserver_ipaddresses()

log.info("...Steam Server ready...")

print("Press Escape to exit...")
print()
print()