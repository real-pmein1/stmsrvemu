import struct, sys, zlib, os, random, time, threading, queue, socket, binascii, configparser, copy, shutil
import traceback
import zipfile
from multiprocessing import Process
from tqdm import tqdm

import globalvars
# TODO MOVE TO EMU CODE

import logger
from utilities.vlvsig_replacement import FileSignatureModifier
from utilities.blobs import get_app_list
from utilities import encryption
from utilities.database.ccdb import read_secondblob

#from Steam.impsocket import impsocket
from Steam import oldsteam04
from Steam import oldsteam03
from Steam import oldsteam
from Steam.fileclient import *
from Steam.client import get_fileservers
#from Steam import contentblob
from Steam.neuter import readchunk_neuter
from Steam.manifest import Manifest

logger.init_logger()
log = logging.getLogger('NEUTER')

# config = {}
# exec(open("config.py").read(), config)

if len(sys.argv) < 4:
    sys.exit("This program cannot be run in DOS mode.")
if not sys.argv[1] == "load":
    sys.exit("This program cannot be run in DOS mode.")

from config import get_config

config = get_config()
#log.info("Config loaded successfully.")

app_id = None
app_ver = None

try:
    app_id = int(sys.argv[2])
    app_ver = int(sys.argv[3])
except:
    pass

#file neuter
if not sys.argv[2] == "app":
    if type(app_id) == int and type(app_ver) == int:
        pass
    else:
        print("Entering standalone mode")
        try:
            log.info(f"Opening file {sys.argv[2]} for neutering.")
            with open(sys.argv[2], 'rb') as f:
                file_to_neuter = f.read()
            islan = len(sys.argv) < 5 or sys.argv[4] == "islan"
            #log.debug(f"Neutering file with LAN mode set to {islan}.")
            globalvars.CURRENT_APPID_VERSION = f"file: {sys.argv[2]}: "
            processed_file = readchunk_neuter(file_to_neuter, islan, False)
            os.rename(sys.argv[2], sys.argv[2] + ".bak")
            print("Moved " + sys.argv[2] + " to " + sys.argv[2] + ".bak")
            with open(sys.argv[2], 'wb') as f:
                f.write(processed_file)
        except Exception as e:
            log.warning(f"An error occurred while neutering the file: {e}")
        finally:
            log.info("File neutering complete.")
            sys.exit()

#create folders
for directory in [config["storagedir"], config["manifestdir"]]:
    try:
        os.mkdir(directory)
        # log.info(f"Created directory: {directory}")
    except:
        pass

main_key_path = 'files/configs/main_key_1024.der'
network_key_path = 'files/configs/network_key_512.der'

# Check if both files exist
if not os.path.exists(main_key_path) and not os.path.exists(network_key_path):
    log.warning("Main and network keys not found. Generating new keys.")
    encryption.generate_and_export_rsa_keys()
else:
    log.debug("Main and network keys already exist.")

encryption.main_key, encryption.network_key = encryption.import_rsa_keys()
log.debug("RSA keys imported successfully.")
encryption.BERstring = encryption.network_key.public_key().export_key("DER")
encryption.signed_mainkey_reply = encryption.get_mainkey_reply()
log.info("RSA keys setup completed.")

def compare_and_write_file(filename, data):
    try:
        if os.path.isfile(filename):
            with open(filename, "rb") as f:
                old_data = f.read()
            if data == old_data:
                log.info(f"Files are identical: {os.path.basename(filename)}")
                print("Files are equal", os.path.basename(filename))
            else:
                timex = str(int(time.time()))
                os.rename(filename, filename + "." + timex + ".bak")
                log.warning(f"Files are different. Backup created: {filename}.{timex}.bak")
                print("Files are DIFFERENT", os.path.basename(filename))
                with open(filename, "wb") as f:
                    f.write(data)
        else:
            with open(filename, "wb") as f:
                f.write(data)
            log.info(f"New file written: {os.path.basename(filename)}")
    except Exception as e:
        log.warning(f"Error comparing or writing file {filename}: {e}")


def run_cpu_tasks_in_parallel(tasks):
    log.info("Starting CPU tasks in parallel.")
    running_tasks = [Process(target=task) for task in tasks]
    for running_task in running_tasks:
        running_task.start()
    for running_task in running_tasks:
        running_task.join()
    log.info("Completed all parallel CPU tasks.")

def is_port_in_use(ip_addr, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        in_use = s.connect_ex((ip_addr, port)) == 0
        log.debug(f"Port {port} on {ip_addr} is {'in use' if in_use else 'not in use'}.")
        return in_use

def download_app(appid, version, appname):
    try:
        cache_dir = f"files/cache/{appid}_{version}"
        if not os.path.isdir(cache_dir):
            os.mkdir(cache_dir)
            # log.info(f"Created cache directory for app {appid} version {version}.")
        else:
            print(appname.decode("UTF-8") + " v" + str(version) + " is already neutered.")
            log.info(f"{appname} v{version} is already neutered.")
            return

        storage_ver = 3
        numservers = 10
        #servers = client_tools.steam_get_fileservers(contentserver, appid, version, numservers)
        servers = get_fileservers(contentserver, appid, version, numservers)


        if not len(servers):
            log.warning(f"No servers found for app {appid} version {version}.")
            print("No servers for app %i ver %i found" % (appid, version))
            try:
                if os.path.isdir("files/cache/" + str(appid) + "_" + str(version)): os.remove("files/cache/" + str(appid) + "_" + str(version))
            except:
                pass
            return

        thisclient = False
        for server in servers:
            try:
                #print("Content server:", server)
                thisclient = fileclient(server[2], appid, version, None)
                #log.info(f"Connected to content server: {server[2]}")
                break
            except ConnectionError:
                log.warning(f"Refused connection for app {appid} version {version}.")
                if os.path.isdir("files/cache/" + str(appid) + "_" + str(version)): os.remove("files/cache/" + str(appid) + "_" + str(version))
                return

        while True:
            try:
                manifest_bin = thisclient.download_manifest()
                #log.debug(f"Manifest downloaded for app {appid}.")
                break
            except socket.error:
                log.warning("Connection reset by peer while downloading manifest.")
                print("Connection reset by peer?")
                if os.path.isdir("files/cache/" + str(appid) + "_" + str(version)): os.remove("files/cache/" + str(appid) + "_" + str(version))
                pass

        #manifest_filename = "files/cache/" + str(appid) + "_" + str(version) + "/" + str(appid) + "_" + str(version) + ".manifest"
        #compare_and_write_file(manifest_filename, manifest_bin)
        try:
            manif = Manifest(manifest_bin)

            filelist = set()  # Use a set for fast membership checks

            # Populate the set
            for dir_id in manif.dir_entries:
                entry = manif.dir_entries[dir_id]
                fileid = entry.fileid
                fullfilename = entry.fullfilename.decode('latin-1', errors='ignore')

                if fullfilename.lower().endswith(".exe") or fullfilename.lower().endswith(".dll"):
                    filelist.add(fileid)

            #log.info(f"Manifest processed for app {appid}.")

        except Exception as e:
            log.error(f"appid: {str(appid)} version: {str(version)}: Manifest for app {appid} is corrupt!")

        while True:
            try:
                storage_ver = thisclient.download_storage_ver()
                #log.debug(f"Storage version {storage_ver} downloaded for app {appid}.")
                break
            except socket.error:
                print("Connection reset by peer?")
                log.warning("Connection reset by peer while downloading storage.")
                if os.path.isdir("files/cache/" + str(appid) + "_" + str(version)): os.remove("files/cache/" + str(appid) + "_" + str(version))
                pass

        while True:
            try:
                checksums_bin = thisclient.download_checksums()
                #log.debug(f"Checksums downloaded for app {appid}.")
                break
            except socket.error:
                print("Connection reset by peer?")
                log.warning("Connection reset by peer while downloading checksum.")
                if os.path.isdir("files/cache/" + str(appid) + "_" + str(version)): os.remove("files/cache/" + str(appid) + "_" + str(version))
                pass

        checksums_filename = f"files/cache/{appid}_{version}/{appid}_{version}_lan.checksums"
        checksums_filename_wan = f"files/cache/{appid}_{version}/{appid}_{version}_wan.checksums"
        #log.debug(f"Writing LAN checksums to {checksums_filename}.")
        compare_and_write_file(checksums_filename, checksums_bin)
        #log.debug(f"Writing WAN checksums to {checksums_filename_wan}.")
        compare_and_write_file(checksums_filename_wan, checksums_bin)

        if storage_ver == 4:
            # storage = Storage(str(appid), "files/cache/" + str(appid) + "_" + str(version) + "/")
            # checksums = Checksum4(checksums_bin)
            #log.debug(f"Using storage version 4 for app {appid}.")
            storage = oldsteam04.Storage(str(appid), "files/cache/" + str(appid) + "_" + str(version) + "/")
            checksums = oldsteam04.Checksum(checksums_bin)
        elif storage_ver == 2:
            # storage = Storage(str(appid), "files/cache/" + str(appid) + "_" + str(version) + "/")
            # checksums = Checksum(checksums_bin)
            #log.debug(f"Using storage version 2 for app {appid}.")
            storage = oldsteam.Storage(str(appid), "files/cache/" + str(appid) + "_" + str(version) + "/")
            checksums = oldsteam.Checksum(checksums_bin)
        elif storage_ver == 0:
            log.error("appid: {str(appid)} version: {str(version)}: Manifest not found. Exiting.")
            sys.exit("Manifest not found")
        else:
            # storage = Storage(str(appid), "files/cache/" + str(appid) + "_" + str(version) + "/")
            # checksums = Checksum3(checksums_bin)
            #log.debug(f"Using default storage version (V3) for app {appid}.")
            storage = oldsteam03.Storage(str(appid), "files/cache/" + str(appid) + "_" + str(version) + "/")
            checksums = oldsteam03.Checksum(checksums_bin)

        tqdm_desc = appname.decode("UTF-8") + " (" + str(appid) + " v" + str(version) + ")"
        tqdm_desc = tqdm_desc + (" " * (40 - len(tqdm_desc)))

        for dir_id in tqdm(manif.dir_entries, unit=" files", desc=tqdm_desc, file=sys.stdout):
            fileid = manif.dir_entries[dir_id].fileid
            if fileid == 0xffffffff:
                log.debug(f"appid: {str(appid)} version: {str(version)}: Skipping invalid fileid {fileid}.")
                continue

            numchecksums = checksums.numchecksums(fileid)

            if numchecksums == 0:
                log.debug(f"appid: {str(appid)} version: {str(version)}: No checksums found for FileID {fileid}, skipping.")
                continue

            if fileid in storage.indexes:
                log.debug(f"appid: {str(appid)} version: {str(version)}: FileID {fileid} already exists in storage, skipping.")
                continue

            if numchecksums == 1 and checksums.getchecksum(fileid, 0) == 0:
                log.debug(f"appid: {str(appid)} version: {str(version)}: FileID {fileid} is an empty file, setting filemode to 1.")
                file = [""]
                filemode = 1
            else:
                (file, filemode) = thisclient.get_file(fileid, numchecksums)
                #log.info(f"Downloaded file for FileID {fileid} with mode {filemode}.")

            file_wan = copy.deepcopy(file)

            file_is_neutered = False

            if filemode == 1:
                # Retrieve old and new signatures if the fileid is in the DLL/EXE list
                old_signature = None
                new_signature = None
                if fileid in filelist:
                    full_buffer = b""
                    for chunk in file:
                        try:
                            full_buffer += zlib.decompress(chunk)
                        except zlib.error:
                            log.warning(f"Failed to decompress chunk for FileID {fileid}. Skipping.")
                            continue
                    full_buff = FileSignatureModifier(full_buffer)
                    try:
                        old_signature, new_signature = full_buff.get_signatures()
                    except:
                        pass # this file does not contain a signature

                goodchunks = 0
                for i in range(numchecksums):
                    data = file[i]
                    try:
                        if isinstance(data, str):
                            data = data.encode('latin-1', errors="ignore")
                        unpacked = zlib.decompress(data)
                        #log.debug(f"Decompressed chunk {i} for FileID {fileid}.")
                    except zlib.error:
                        log.warning(f"appid: {str(appid)} version: {str(version)}: Failed to decompress chunk {i} for FileID {fileid}.")
                        unpacked = b""

                    processed_data = readchunk_neuter(unpacked, True, True)

                    # If old and new signatures exist, replace the old signature
                    if old_signature and new_signature and i == 0:
                        if old_signature in processed_data:
                            log.info(f"Found and Replacing VLV Signature in FileID: {fileid}.")
                            processed_data = processed_data.replace(old_signature, new_signature)

                    if checksums.validate_chunk(fileid, i, processed_data, checksums_filename):
                        goodchunks += 1
                    #log.debug(f"Chunk {i} validated successfully for FileID {fileid}.")

                    if unpacked != processed_data:
                        log.info(f"appid: {str(appid)} version: {str(version)}: FileID {fileid} has been modified during neutering.")
                        file_is_neutered = True

                        processed_data_wan = readchunk_neuter(unpacked, False, True)

                        # Replace the old signature in processed_data_wan if it exists
                        if old_signature and new_signature and i == 0:
                            if old_signature in processed_data_wan:
                                log.info(f"Found and Replacing VLV Signature in FileID: {fileid}.")
                                processed_data_wan = processed_data_wan.replace(old_signature, new_signature)

                        checksums.validate_chunk(fileid, i, processed_data_wan, checksums_filename_wan)
                        file[i] = zlib.compress(processed_data, 9)
                        file_wan[i] = zlib.compress(processed_data_wan, 9)

            if file_is_neutered:
                #log.info(f"Writing neutered file for FileID {fileid}.")
                storage.writefile(fileid, file, filemode, file_wan, "files/cache/" + str(appid) + "_" + str(version) + "/", str(version))
                file_is_neutered = False

        #log.info(f"Disconnecting client for app {appid}.")
        thisclient.disconnect()
    except Exception as e:
        traceback.print_exc()
        log.error(f"Handler thread exception: {e}")
        tb = sys.exc_info()[2]
        log.error(''.join(traceback.format_tb(tb)))


def neuter_steamworks_SDK(islan):
    import Steam.neuter as neuter
    """ Neuters the steamworks SDK, specifically only the content tool at the moment"""
    # Determine the octal IP and create the replacement string.
    server_ip = config["server_ip"]
    public_ip = config["public_ip"]
    if islan:
        octal_ip = server_ip
    else:
        octal_ip = public_ip

    octal_ip = octal_ip.encode('latin-1')
    neuter_string = [
           (b"ftp.valvesoftware.com", octal_ip, b"SteamWorks SDK Content Tool FTP Address")
    ]

    # Define the path to the ContentTool.exe and the root directory.
    content_tool_path = 'files/steamworks_data/tools/ContentTool.exe'
    backup_path = 'files/steamworks_data/tools/ContentTool.exe.bak'
    steamworks_data_root = 'files/steamworks_data/'

    # Create a backup of the original ContentTool.exe
    if os.path.exists(content_tool_path):
        shutil.copy2(content_tool_path, backup_path)
        log.info(f"Backup created at {backup_path}")

        # Call config_replace_in_file using ContentTool.exe if it exists.
        with open(content_tool_path, 'rb') as f:
            file_data = f.read()
            modified_data = neuter.config_replace_in_file(
                    file_data,
                    content_tool_path,
                    neuter_string,
                    1
            )

        # Write the modified data back to the ContentTool.exe.
        with open(content_tool_path, 'wb') as f:
            f.write(modified_data)
        log.info(f"Neutered {content_tool_path} using the specified replacements.")

    # After neutering, zip the entire 'files/steamworks_data/' directory.
    zip_filename = f'client/steamworks_sdk_{"lan" if islan else "wan"}.zip'
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Walk through the steamworks_data_root directory and add all files to the zip.
        for root, dirs, files in os.walk(steamworks_data_root):
            for file in files:
                file_path = os.path.join(root, file)
                # Add the file to the zip archive, preserving its relative path.
                zipf.write(file_path, os.path.relpath(file_path, steamworks_data_root))

    log.info(f"SteamWorks SDK has been neutered and saved as {zip_filename}.")

try:
    if config['csds_ipport'] == "":
        contentserver = (bytes(config["server_ip"], "UTF-8"), int(config["contentdir_server_port"]))
        log.info(f"Using content server {config['server_ip']}:{config['contentdir_server_port']}.")
    else:
        # Example value of config['csds_ipport']
        csds_ipport = config['csds_ipport']  # Assuming this is '192.168.3.180:27037'

        # Split the string into IP and port
        ip, port = csds_ipport.split(':')

        # Convert the port to an integer
        port = int(port)
        contentserver = (ip, port)
        log.info(f"Using content server {ip}:{port}.")
except Exception as e:
    log.warning(f"Error reading content server config: {e}. Using default localhost server.")
    contentserver = (b"127.0.0.1", 27037)


if os.path.isfile("files/cache/secondblob_lan.bin.temp"):
    cblob = read_secondblob("files/cache/secondblob_lan.bin.temp")
elif os.path.isfile("files/cache/secondblob_lan.bin"):
    cblob = read_secondblob("files/cache/secondblob_lan.bin")
else:
    cblob = read_secondblob("files/secondblob.bin")

try:
    applist = get_app_list(cblob)
    log.info(f"Retrieved application list with {len(applist)} entries.")
    #applist = contentblob.get_app_list(cblob)
except:
    log.error(f"Failed to get applist from Content Directory Server!")
    sys.exit()

print("Waiting for content server...")

while is_port_in_use(config["server_ip"], int(config["content_server_port"])) == False:
    pass

clearConsole = lambda: os.system('cls' if os.name in ('nt', 'dos') else 'clear')
clearConsole()

if not sys.argv[2] == "app":
    if type(app_id) == int and type(app_ver) == int:
        print("Entering standalone mode")
        if app_id in applist:
            name = applist[app_id].name
            download_app(app_id, app_ver, name)
        else:
            download_app(app_id, app_ver, b"Unknown app")
        sys.exit("Complete.")

if not sys.argv[3] == ",8":
    sys.exit("This program cannot be run in DOS mode.")

subscribelist = []

neuter_applist = [0, 3, 5, 7, 8, 171, 200, 201, 205, 212, 216, 217, 222, 254, 256, 257, 263, 264, 310, 311, 313, 314, 317, 443, 501, 503, 511, 512, 521, 524, 531, 562, 552, 593, 594, 572, 624, 1000, 1304, 1314, 2131, 2144, 2401, 2403]

#neuter_applist_1 = [0, 3, 5]
#neuter_applist_2 = [7, 8]

#neuter_applist = sys.argv[2].split(",")
#neuter_applist = [eval(i) for i in neuter_applist]

#depots that error: 151, 538

#depots that dont need neutering: 363
#log.info("Console cleared. Starting neutering process.")

for app_id in neuter_applist:
    if app_id in applist:
        appid = app_id
        version = applist[appid].version
        betaversion = applist[appid].betaversion
        name = applist[appid].name
        log.info(f"Downloading and processing app {appid}: {name.decode('UTF-8')}, version {version}.")
        globalvars.CURRENT_APPID_VERSION = f"appid: {str(appid)} version: {str(version)}: "
        download_app(appid, version, name)
        if betaversion != version:
            download_app(appid, betaversion, name)

if os.path.isfile("files/cache/secondblob_lan.bin.temp"):
    try:
        os.remove("files/cache/secondblob_lan.bin")
    except:
        pass
    os.rename("files/cache/secondblob_lan.bin.temp", "files/cache/secondblob_lan.bin")

if os.path.isfile("files/cache/secondblob_wan.bin.temp"):
    try:
        os.remove("files/cache/secondblob_wan.bin")

    except:
        pass
    os.rename("files/cache/secondblob_wan.bin.temp", "files/cache/secondblob_wan.bin")

if os.path.isfile("files/cache/firstblob.bin"):
    if os.path.isfile("files/firstblob.bin"):
        try:
            os.remove("files/cache/firstblob.bin")
        except:
            pass

        if not os.path.isfile("files/cache/firstblob.bin"):
            shutil.copy2("files/firstblob.bin", "files/cache/firstblob.bin")

if os.path.isfile("files/cache/firstblob.bin.temp"):
    if os.path.isfile("files/cache/firstblob.bin"): os.remove("files/cache/firstblob.bin")
    shutil.move("files/cache/firstblob.bin.temp", "files/cache/firstblob.bin")
    log.info("Moved new firstblob.bin into place.")

if os.path.isfile("files/configs/.isneutering"):
    try:
        os.remove("files/configs/.isneutering")
        #log.info("Removed .isneutering file.")
    except Exception as e:
        log.warning(f"Failed to remove .isneutering file: {e}")

neuter_steamworks_SDK(islan = False)
neuter_steamworks_SDK(islan = True)