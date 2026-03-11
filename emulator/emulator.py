import logging
import os
import threading
import time
import sys
import platform
import shutil
import importlib.util
import traceback

# Force unbuffered stdout for Linux
if sys.platform != 'win32':
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
	
import globalvars
from utilities.thread_handler import start_server_thread, start_watchdog
import utilities.encryption as encryption
from utils import log_blob_information
from logger import init_test_logging, close_test_logging

try:
    # Delete the mariadb log at launch, this allows people to grab the log if it errors after shutting down, but also
    # keeps the hard-drive free of gb sized logs
    shutil.rmtree("logs/mariadb_general.log", ignore_errors = True)
except:
    pass

# Define the global thread exception handler
def global_thread_exception_handler(args):
    #logging.getLogger('threadhndl').error(
    #    f"Exception in thread '{args.thread.name}': {args.exc_type.__name__}: {args.exc_value}",
    #    exc_info=(args.exc_type, args.exc_value, args.exc_traceback)
    #)
    logger = logging.getLogger("threadhndl")

    formatted = "".join(
        traceback.format_exception(
            args.exc_type,
            args.exc_value,
            args.exc_traceback
        )
    )

    formatted = "" + formatted.split("Python39_code\\", 1)[1] if "Python39_code\\" in formatted else formatted

    logger.error(
        f"Exception in thread '{args.thread.name}':\n{formatted}"
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
encryption.init_network_key_reply()  # Precompute network key response for configserver


def stmserver_initialization():
    global config, log

    # operating system check
    globalvars.current_os = platform.system()
    globalvars.aio_server = True

    # from utilities.inputmanager import start_watchescape_thread
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
    from utils import parent_initializer, autoupdate
    from utilities.time import every, is_30_minutes_or_less

    # Check ticket expiration config to ensure it is set to a time higher than 30 minutes
    result = is_30_minutes_or_less(config['ticket_expiration_time_length'])
    if result:
        config['ticket_expiration_time_length'] = "0d0h45m0s"

    autoupdate()
    if config["subtract_time"] != "0":
        auto_swap_blob.swap_blobs()
        if config["auto_blobs"] == "true":
            print("Auto-blob rolling activated")
            threading.Thread(target = lambda:every(300, auto_swap_blob.swap_blobs)).start()

    # initialize logger, emulator.ini and mariadb if needed
    if not os.path.exists(os.path.join(config['configsdir'], '.initialized')):
        firstrun.check_initialization()
    config = read_config()
    #if config["uat"] != "1":
    #    clearConsole = lambda:os.system('cls' if os.name in ('nt', 'dos') else 'clear')
    #    clearConsole()

    # start watching for 'esc' keyboard key - MOVED
    # start_watchescape_thread()

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

override_path = os.path.join(os.path.dirname(sys.executable), "servers/contentserver2.py")

if os.path.exists(override_path):
    spec = importlib.util.spec_from_file_location("contentserver", override_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    contentserver = module.contentserver
    from servers.contentserver2 import contentserver
else:
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
#from servers.global_tracker_server import GlobalTrackerThread
from steamweb.steamweb import check_child_pid, steamweb
from utilities.filesystem_monitor import DirectoryMonitor
from utilities import filesystem_monitor
from servers.administrationserver import administrationserver


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
    # extra_args for CM servers that need master_server reference for restarts
    cm_extra_args = {'master_server': master_server}

    if config["run_all_servers"].lower() == "true":
        cmtcp27014_server = CMServerTCP_27014(27014, config, master_server)
        start_server_thread(cmtcp27014_server, 'CMTCP27014', 'Valve Connection Manager (CM) 1 TCP Server', cm_extra_args)
        cmudp27014_server = CMServerUDP_27014(27014, config, master_server)
        start_server_thread(cmudp27014_server, 'CMUDP27014', 'Valve Connection Manager (CM) 1 UDP Server', cm_extra_args)
        cmtcp27017_server = CMServerTCP_27017(27017, config, master_server)
        start_server_thread(cmtcp27017_server, 'CMTCP27017', 'Valve Connection Manager (CM) 2 TCP Server', cm_extra_args)
        cmudp27017_server = CMServerUDP_27017(27017, config, master_server)
        start_server_thread(cmudp27017_server, 'CMUDP27017', 'Valve Connection Manager (CM) 2 UDP Server', cm_extra_args)
    else:
        if globalvars.steamui_ver < 479:
            # 27014 only needs to be active for steamui versions below 479
            cmtcp27014_server = CMServerTCP_27014(27014, config, master_server)
            start_server_thread(cmtcp27014_server, 'CMTCP27014', 'Valve Connection Manager (CM) 1 TCP Server', cm_extra_args)
            cmudp27014_server = CMServerUDP_27014(27014, config, master_server)
            start_server_thread(cmudp27014_server, 'CMUDP27014', 'Valve Connection Manager (CM) 1 UDP Server', cm_extra_args)
        else:
            cmtcp27017_server = CMServerTCP_27017(27017, config, master_server)
            start_server_thread(cmtcp27017_server, 'CMTCP27017', 'Valve Connection Manager (CM) 2 TCP Server', cm_extra_args)
            cmudp27017_server = CMServerUDP_27017(27017, config, master_server)
            start_server_thread(cmudp27017_server, 'CMUDP27017', 'Valve Connection Manager (CM) 2 UDP Server', cm_extra_args)

if config["run_all_servers"].lower() == "true":
    # TODO finish global tracker server
    #if config.get("global_tracker", "false").lower() == "true":
    #    gt_thread = GlobalTrackerThread(int(config.get("global_tracker_port", 1300)))
    #    start_server_thread(gt_thread, 'GlobalTrackerServer', 'Global Tracker Server')

    tracker_server = TrackerServer(1200, config)
    start_server_thread(tracker_server, 'TrackerServer', 'Tracker Server')

    log.info("Made by ymgve Modified by STMServer Team")

    vac_server = VAC1Server(int(config["vac_server_port"]), config)
    start_server_thread(vac_server, 'VAC1Server', 'Valve Anti-Cheat V1 Server')

    beta1auth_server = Beta1_AuthServer(5273, config)
    start_server_thread(beta1auth_server, 'Beta1Server', 'Beta 1 (2002) Client Authentication Server')

    if config['enable_ftp'].lower() == "true":
        ftp_port = int(config['ftp_server_port'])
        ftp_server_thread = threading.Thread(
            target=create_ftp_server,
            args=(
                os.path.join("files", "temp"),
                os.path.join("files", "beta1_ftp"),
                globalvars.server_ip,
                ftp_port
            )
        )
        start_server_thread(ftp_server_thread, 'FTPUpdateServer', '2002 Beta 1 Update FTP Server', extra_args={'port': ftp_port})
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

            if config['enable_ftp'].lower() == "true":
                ftp_port = int(config['ftp_server_port'])
                ftp_server_thread = threading.Thread(
                    target=create_ftp_server,
                    args=(
                        os.path.join("files", "temp"),
                        os.path.join("files", "beta1_ftp"),
                        globalvars.server_ip,
                        ftp_port
                    )
                )
                start_server_thread(ftp_server_thread, 'FTPUpdateServer', '2002 Beta 1 Update FTP Server', extra_args={'port': ftp_port})

admin_server = administrationserver(config["admin_server_port"], config)
start_server_thread(admin_server, 'AdminServer', 'STMServer Administration Server')


apache_root_exists = os.path.isdir(config["apache_root"])

if globalvars.use_webserver and config["http_ip"] == "":
    if apache_root_exists:
        steamweb("80", config["server_ip"], config["apache_root"], config["web_root"])

        log.info(f"Steam Web Server listening on port 80")
        find_child_pid_timer = threading.Timer(1.0, check_child_pid)
        find_child_pid_timer.start()
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
    os.path.abspath(os.path.join('files', 'mod_blob')),
    os.path.abspath(os.path.join('files', 'configs', 'custom_neuter')),
}
# Monitor changes to secondblob.bin/py in the background while server is running
specific_files_to_watch = {
    os.path.abspath(os.path.join("files", "secondblob.bin")),
    os.path.abspath(os.path.join("files", "secondblob.py")),
    os.path.abspath("emulator.ini"),
    os.path.abspath(os.path.join('files', 'mod_blob')),
}
filesystem_monitor.specific_files_to_watch = specific_files_to_watch
paths_to_monitor = list(specific_files_to_watch) + list(directories_to_watch)
directory_monitor = DirectoryMonitor(paths = paths_to_monitor, directories_to_watch = directories_to_watch)
directory_monitor.start()

time.sleep(2)  # This is needed for the following line to show up AFTER the sever initialization information

if config["log_level"].split('.')[-1].upper() == "INFO":
    clearConsole = lambda:os.system('cls' if os.name in ('nt', 'dos') else 'clear')
    clearConsole()
    
print("")
print(f"Steam 2002-2011 Server Emulator v{globalvars.local_ver}")
print(("=" * 33) + ("=" * len(globalvars.local_ver)))
print()
# print(" -== Half-Life 2 20th Anniversary Celebration 2004-2024 ==-")

utils.print_stmserver_ipaddresses()

# Additional info for Steam versions and datetime of blobs
log_blob_information()

# Initialize test logging if enabled (captures all log levels to a single file)
init_test_logging()

if config["use_emu_console"].lower() == "true":
    # Start console manager for interactive commands
    globalvars.start_time = time.time()  # Track server start time for uptime calculation
    from utilities.console_manager import start_console_manager, get_console_manager, SimpleConsoleManager
    start_console_manager()

    # Get the console manager to check its type
    console_mgr = get_console_manager()

    # SimpleConsoleManager.start() is non-blocking (uses daemon thread), so we need to
    # keep the main thread alive. TUIConsoleManager.start() is blocking, so when it
    # returns the server is already shutting down.
    if isinstance(console_mgr, SimpleConsoleManager):
        try:
            # Wait for shutdown - let the console manager daemon thread handle input
            while console_mgr.running and not getattr(globalvars, 'shutdown_requested', False):
                time.sleep(1)
        except KeyboardInterrupt:
            log.info("Shutdown requested via keyboard interrupt")
        except Exception as e:
            log.error(f"Error in main loop: {e}")
        finally:
            log.info("Server shutting down...")
            close_test_logging()
    # For TUI console, start_console_manager() already blocked until exit, cleanup happens there
else:
    from utilities.inputmanager import start_watchescape_thread
    start_watchescape_thread()

    # Keep main thread alive - without this, the script ends and Python shuts down
    # the interpreter, killing all daemon threads and the ThreadPoolExecutor
    try:
        while not getattr(globalvars, 'shutdown_requested', False):
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Shutdown requested via keyboard interrupt")
    except Exception as e:
        log.error(f"Error in main loop: {e}")
    finally:
        log.info("Server shutting down...")
        close_test_logging()

log.info("...Steam Server ready...")