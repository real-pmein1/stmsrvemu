import hashlib
import ipaddress
import logging
import os
import random
import re
import secrets
import shutil
import signal
import socket
import string
import struct
import subprocess
import sys
from threading import Thread, Event, RLock
import time
from datetime import datetime
import mariadb
from zipfile import ZipFile
from collections import Counter
import ipcalc
import psutil
import requests
import xxhash
from tqdm import tqdm

import config as configurations
import globalvars
import utilities.database.userpy_to_db
from config import get_config as read_config, save_config_value
from utilities.contentdescriptionrecord import ContentDescriptionRecord
from utilities import cafe_neutering, neuter, packages
from utilities.cdr_manipulator import (
    cache_cdr,
    cache_cdr_unified,
    check_and_merge_mod_blob_files,
    load_blobs_to_memory,
    cleanup_all_ephemeral_blobs
)
from utilities.database import ccdb
from utilities.database import cmsdb
from utilities.database import settings_db
from utilities.name_suggestor import load_modifiers_from_files
from utilities.neuter import check_appinfo_cache, config_replace_in_file
from utilities.packages import Package
from neuter import auto_neuter as new_neuter
import legacygamekeys

config = read_config()
log = logging.getLogger('UTILS')

neutering_done = Event()

# Initialize CDR blob lock for thread-safe memory access
if globalvars.CDR_BLOB_LOCK is None:
    globalvars.CDR_BLOB_LOCK = RLock()

def sync_settings_to_db() -> None:
    """Persist configuration values to the settings table.

    Uses batch operations to sync all settings in minimal DB round-trips.
    Keys containing ``"password"`` are skipped to avoid storing sensitive data.

    Returns:
        None: This function does not return anything.
    """

    if globalvars.settingsdb is None:
        globalvars.settingsdb = settings_db.settings_dbdriver()

    # Filter out password keys and batch sync in one operation
    settings_to_sync = {
        key: value
        for key, value in config.items()
        if "password" not in key.lower()
    }
    globalvars.settingsdb.batch_sync_settings(settings_to_sync)


def decodeIP(ipport_str):
    (oct1, oct2, oct3, oct4, port) = struct.unpack("<BBBBH", ipport_str)
    ip = "%d.%d.%d.%d" % (oct1, oct2, oct3, oct4)
    return ip, port


def encodeIP(ip_port):
    ip, port = ip_port  # Unpacking the tuple
    if isinstance(port, str):
        port = int(port)
    if isinstance(ip, str):
        ip = ip.encode("latin-1")
    octets = ip.split(b".")
    packed_string = struct.pack("<BBBBH", int(octets[0]), int(octets[1]), int(octets[2]), int(octets[3]), port)
    return packed_string

def encodeIP_bigendian(ip_port):
    ip, port = ip_port  # Unpacking the tuple
    if isinstance(port, str):
        port = int(port)
    octets = ip.split(".")
    # Use '>' for big-endian and include the port
    packed_string = struct.pack(">BBBBH", int(octets[0]), int(octets[1]), int(octets[2]), int(octets[3]), port)
    return packed_string

def readfile_beta(fileid, offset, length, index_data, dat_file_handle, net_type):
    # Load the index
    # with open(index_file, 'rb') as f:
    #    index_data = pickle.load(f)

    # Get file information from the index
    if fileid not in index_data:
        print("Error: File number not found in index.")
        return None

    file_info = index_data[fileid]
    # print(file_info)
    dat_offset, dat_size = file_info['offset'], file_info['length']

    # MASTER
    oldstringlist1 = (
        b'207.173.177.10:27010', b'"hlmaster.valvesoftware.com:27010"',
        b'"half-life.east.won.net:27010"', b'"half-life.west.won.net:27010"',
        b'"207.173.177.10:27010"', b'hlmaster.valvesoftware.com:27010',
        b'half-life.east.won.net:27010', b'half-life.west.won.net:27010',
        b'half-life.central.won.net:27010')
    # TRACKER
    oldstringlist2 = (b'"tracker.valvesoftware.com:1200"', b'"tracker.valvesoftware.com:1200"')
    # AUTH (VALIDATION)
    oldstringlist3 = (b'207.173.177.10:7002', b'half-life.east.won.net:7002',
    b'half-life.west.won.net:7002', b'half-life.central.won.net:7002')
    # SECURE (VAC1)
    oldstringlist4 = (
        b'"gridmaster.valvesoftware.com:27012"', b'gridmaster.valvesoftware.com:27012',
        b'half-life.speakeasy-nyc.hlauth.net:27012', b'half-life.speakeasy-sea.hlauth.net:27012',
        b'half-life.speakeasy-chi.hlauth.net:27012')

    # MASTER
    if net_type == "external":
        newstring1 = b'"' + config["public_ip"].encode('latin-1') + b':27010"'
        newstring5 = config["public_ip"].encode('latin-1') + b':27010'
    else:
        newstring1 = b'"' + config["server_ip"].encode('latin-1') + b':27010"'
        newstring5 = config["server_ip"].encode('latin-1') + b':27010'
    # TRACKER
    if net_type == "external":
        if config["tracker_ip"] != "":
            newstring2 = b'"' + config["tracker_ip"].encode('latin-1') + b':1200"'
        else:
            newstring2 = b'"' + config["public_ip"].encode('latin-1') + b':1200"'
    else:
        newstring2 = b'"' + config["server_ip"].encode('latin-1') + b':1200"'
    # AUTH (VALIDATION)
    if net_type == "external":
        newstring3 = config["public_ip"].encode('latin-1') + b':' + config["validation_port"].encode('latin-1')
    else:
        newstring3 = config["server_ip"].encode('latin-1') + b':' + config["validation_port"].encode('latin-1')
    # SECURE (VAC1)
    if net_type == "external":
        newstring4 = config["public_ip"].encode('latin-1') + b':27012'
    else:
        newstring4 = config["server_ip"].encode('latin-1') + b':27012'

    # Extract and decompress the file from the .dat file
    # with open(dat_file, 'rb') as f:
    # f.seek(dat_offset + offset)
    dat_file_handle.seek(dat_offset + offset)
    decompressed_data = dat_file_handle.read(length)
    for oldstring1 in oldstringlist1:
        if oldstring1 in decompressed_data:
            if oldstring1.startswith(b'"'):
                stringlen_diff1 = len(oldstring1) - len(newstring1)
                replacestring1 = newstring1 + (b" " * stringlen_diff1)
                decompressed_data = decompressed_data.replace(oldstring1, replacestring1)
            else:
                stringlen_diff1 = len(oldstring1) - len(newstring5)
                replacestring1 = newstring5 + (b" " * stringlen_diff1)
                decompressed_data = decompressed_data.replace(oldstring1, replacestring1)
    for oldstring2 in oldstringlist2:
        if oldstring2 in decompressed_data:
            stringlen_diff2 = len(oldstring2) - len(newstring2)
            replacestring2 = newstring2 + (b" " * stringlen_diff2)
            decompressed_data = decompressed_data.replace(oldstring2, replacestring2)
    for oldstring3 in oldstringlist3:
        if oldstring3 in decompressed_data:
            stringlen_diff3 = len(oldstring3) - len(newstring3)
            replacestring3 = newstring3 + (b" " * stringlen_diff3)
            decompressed_data = decompressed_data.replace(oldstring3, replacestring3)
    for oldstring4 in oldstringlist4:
        if oldstring4 in decompressed_data:
            stringlen_diff4 = len(oldstring4) - len(newstring4)
            replacestring4 = newstring4 + (b" " * stringlen_diff4)
            decompressed_data = decompressed_data.replace(oldstring4, replacestring4)  # decompressed_data = zlib.decompress(compressed_data)

    # print(len(decompressed_data[offset:offset + length]))
    # print(len(compressed_data[offset:offset + length]))

    # with open(str(FILE_COUNT) + ".file", "wb") as f:
    #    f.write(decompressed_data)

    return decompressed_data  # [offset:offset + length]


def readchunk_neuter(chunk, islan):
    if islan or config["public_ip"] == "0.0.0.0":
        # If islan is True and the filename is SteamNewLAN.exe, use the server IP
        fullstring1 = globalvars.replace_string(True)
    else:
        # In all other cases, use the public IP
        fullstring1 = globalvars.replace_string(False)

    chunk = config_replace_in_file(chunk, b'chunk', fullstring1, 1)

    if islan:
        fullstring2 = globalvars.replace_string_name_space(True)
        fullstring3 = globalvars.replace_string_name(True)
    elif config["public_ip"] != "0.0.0.0" or not islan:
        fullstring2 = globalvars.replace_string_name_space(False)
        fullstring3 = globalvars.replace_string_name(False)
    else:
        fullstring2 = globalvars.replace_string_name_space(False)
        fullstring3 = globalvars.replace_string_name(False)

    chunk = config_replace_in_file(chunk, b'chunk', fullstring2, 2, True)
    chunk = config_replace_in_file(chunk, b'chunk', fullstring3, 3)

    for ip in globalvars.extraips + globalvars.ip_addresses:
        chunk = ip_replacer(chunk, b'chunk', ip, config["server_ip"].encode('latin-1'))

    return chunk


def check_email(email_str):
    if re.match(r'^[\w\.-]+@[\w\.-]+$', email_str):
        return 0
    else:
        return 3


def check_username(username_str):
    if re.match(r'^[a-zA-Z0-9_]+$', username_str):
        return 0
    else:
        return 2


def reverse_ip_bytes(ip):
    # Convert IP address to a reversed byte order DWORD
    ip_parts = ip.split('.')
    reversed_ip = '.'.join(reversed(ip_parts))
    return struct.unpack("!I", socket.inet_aton(reversed_ip))[0]


def ip_to_int(ip_address):
    # Convert the IP address to 32-bit packed binary format
    packed_ip = socket.inet_aton(ip_address)

    # Unpack the binary data into a 4-byte integer
    ip_int = struct.unpack("!I", packed_ip)[0]

    return ip_int


def cmp(a, b):
    return (a > b) - (a < b)


def sortkey(x):
    if len(x) == 4 and x[2] == 0:
        return x[::-1]
    return x


def sortfunc(x, y):
    if len(x) == 4 and x[2] == 0:
        if len(y) == 4 and y[2] == 0:
            numx = struct.unpack("<I", x)[0]
            numy = struct.unpack("<I", y)[0]
            return cmp(numx, numy)
        else:
            return -1
    else:
        if len(y) == 4 and y[2] == 0:
            return 1
        else:
            return cmp(x, y)


def formatstring(text):
    if len(text) == 4 and text[2] == b"\x00":
        return (b"'\\x%02x\\x%02x\\x%02x\\x%02x'") % (ord(text[0]), ord(text[1]), ord(text[2]), ord(text[3]))
    else:
        return repr(text)


def sanitize_filename(filename):
    # Check if the input is a byte string and decode it to a string
    if isinstance(filename, bytes):
        try:
            filename = filename.decode('latin-1')  # Assuming UTF-8 encoding
        except UnicodeDecodeError:
            log.error("Filename encoding could not be decoded from bytes.")

    # Correctly check if the filename ends with either ".pkg" or ".pkg_rsa_signature"
    if not (filename.endswith(".pkg") or filename.endswith(".pkg_rsa_signature")):
        log.error(f"Invalid file extension: {filename}. Filename must end with '.pkg' or '.pkg_rsa_signature'.")
        return None  # Return None or handle error as appropriate


    # Normalize the path to remove any relative path components
    normalized_filename = os.path.normpath(filename)

    # Check for directory traversal attempts after normalization
    if normalized_filename.startswith(('/', '\\')) or '..' in normalized_filename:
        log.error("Directory traversal attempt detected.")

    # Return the sanitized filename
    return normalized_filename.encode('latin-1')


def neuter_worker(*args):
    try:
        new_neuter(*args)
    finally:
        # Signal that neutering is finished, even if it errored
        neutering_done.set()


def check_secondblob_changed():
    # Skip processing if shutdown is in progress to prevent ThreadPoolExecutor errors
    if getattr(globalvars, 'shutdown_requested', False):
        return

    from utilities.custom_neuter_tracker import check_all_cached_pkgs, check_custom_neuter_configs
    cache_dir = os.path.join('files', 'cache')
    secondblob_paths = [
        os.path.join('files', 'secondblob.bin'),
        os.path.join('files', 'secondblob.py'),
        os.path.join(cache_dir, 'secondblob_lan.bin')
    ]
    blobhash_path = os.path.join(cache_dir, 'blobhash')
    hash_needs_update = False

    # Check if cache files exist
    if not os.path.exists(os.path.join(cache_dir, 'secondblob_lan.bin')) or \
       not os.path.exists(os.path.join(cache_dir, 'secondblob_wan.bin')):
        hash_needs_update = True
    #    cache_cdr(True)
    #    cache_cdr(False)
    #    if os.path.isfile("files/cache/firstblob.bin"): os.remove("files/cache/firstblob.bin")
    #    ccdb.load_ccdb()

    # Check if ini has changed
    new_date = False
    new_time = False
    cache_date = False
    cache_time = False
    ignore_blobhash = False
    cache_ini_path = os.path.join(cache_dir, 'emulator.ini.cache')
    if os.path.isfile(cache_ini_path):
        with open('emulator.ini', 'r') as inifile:
            mainini = inifile.readlines()
        with open(cache_ini_path, 'r') as cachefile:
            cacheini = cachefile.readlines()
        for line in mainini:
            #if "steam_date" in line:
            if line.startswith("steam_date="):
                new_date = line[11:21]
            #elif "steam_time" in line:
            if line.startswith("steam_time="):
                new_time = line[11:19]
        for line in cacheini:
            #if "steam_date" in line:
            if line.startswith("steam_date="):
                cache_date = line[11:21]
            #elif "steam_time" in line:
            if line.startswith("steam_time="):
                cache_time = line[11:19]
        if new_date and new_time: # Separate for re-caching the blobs
            if new_date != config["steam_date"] or new_time != config["steam_time"]:
                hash_needs_update = True
                check_paths = [
                    os.path.join('files', 'firstblob.bin'),
                    os.path.join('files', 'firstblob.py'),
                    os.path.join('files', 'secondblob.bin'),
                    os.path.join('files', 'secondblob.py')
                ]
                for path in check_paths:
                    if os.path.isfile(path):
                        os.remove(path)
                #cache_cdr(True)
                #cache_cdr(False)
                #if os.path.isfile("files/cache/firstblob.bin"): os.remove("files/cache/firstblob.bin")
                config["steam_date"] = new_date
                config["steam_time"] = new_time
                #ccdb.load_ccdb()
                os.remove(cache_ini_path)
                #shutil.copy2('emulator.ini', cache_ini_path)
            elif new_date != cache_date or new_time != cache_time:
                hash_needs_update = True
                check_paths = [
                    os.path.join('files', 'firstblob.bin'),
                    os.path.join('files', 'firstblob.py'),
                    os.path.join('files', 'secondblob.bin'),
                    os.path.join('files', 'secondblob.py')
                ]
                for path in check_paths:
                    if os.path.isfile(path):
                        os.remove(path)
                config["steam_date"] = new_date
                config["steam_time"] = new_time
                os.remove(cache_ini_path)
                #shutil.copy2('emulator.ini', cache_ini_path)
            else: # Date/time match, setting flag to ignore blobhash
                ignore_blobhash = True
    else: # Assume cached blobs are invalid as there's no ini cache
        hash_needs_update = True

    shutil.copy2("emulator.ini", os.path.join("files", "cache", "emulator.ini.cache"))

    # Determine which file (bin or py) exists for hashing
    current_hash = None
    for secondblob_path in secondblob_paths:
        if os.path.exists(secondblob_path):
            # Compute hash of the existing file
            with open(secondblob_path, 'rb') as file:
                file_data = file.read()
                current_hash = hashlib.sha256(file_data).hexdigest()
            break

    # Check hash and update if necessary
    try:
        with open(blobhash_path, 'rb') as file:
            saved_hash = file.read().decode('utf-8')
    except:
        hash_needs_update = True
        saved_hash = None

    if saved_hash != current_hash:
        if current_hash != None:
            with open(blobhash_path, 'wb') as file:
                file.write(current_hash.encode('utf-8'))
        if not ignore_blobhash:
            hash_needs_update = True
    
    if hash_needs_update:
        log.info("Caching CDDB")
        # Process firstblob first to set record_ver before mod_blob merging in cache_cdr
        ccdb.neuter_ccdb()
        # OPTIMIZATION: Use unified function to build blob ONCE and create both LAN/WAN variants
        # This eliminates duplicate database queries and blob processing
        cache_cdr_unified(isAppApproval_merge=False)
        log.info("Finished caching CDDB")
    else:
        log.info("Using cached secondblob file for content description")
        # Check for new/modified files in mod_blob and merge without re-running neuter
        merged_count = check_and_merge_mod_blob_files()
        if merged_count > 0:
            log.info(f"Merged {merged_count} new/modified mod_blob file(s) into cache")

    # Check and update all cached pkgs against current mod_pkg state
    check_all_cached_pkgs()

    # Check for custom neuter config changes and invalidate affected caches
    check_custom_neuter_configs(is_cold_start=False)

    from utilities import blobs
    import zlib
    import pprint
    from utilities.time import steamtime_to_datetime

    # Load CDR blobs into memory
    # During neuter (hash_needs_update=True), .temp files exist and we need to read from them
    # After neuter or on normal startup, .bin files are used
    if hash_needs_update:
        # Read from .temp files during neutering process
        # These will be renamed to .bin after neuter completes
        try:
            with open(os.path.join("files", "cache", "secondblob_lan.bin.temp"), "rb") as g:
                lan_blob_bytes = g.read()
        except Exception:
            with open(os.path.join("files", "cache", "secondblob_lan.bin"), "rb") as g:
                lan_blob_bytes = g.read()

        try:
            with open(os.path.join("files", "cache", "secondblob_wan.bin.temp"), "rb") as g:
                wan_blob_bytes = g.read()
        except Exception:
            with open(os.path.join("files", "cache", "secondblob_wan.bin"), "rb") as g:
                wan_blob_bytes = g.read()

        # Store in memory (thread-safe)
        with globalvars.CDR_BLOB_LOCK:
            globalvars.CDR_BLOB_LAN = lan_blob_bytes
            globalvars.CDR_BLOB_WAN = wan_blob_bytes

            # Decompress and deserialize for CDR_DICTIONARY
            # OPTIMIZATION: Use blob_unserialize directly instead of pprint.saferepr + exec
            blob = lan_blob_bytes
            if blob.startswith(b"\x01\x43"):
                blob = zlib.decompress(blob[20:])
            blob_dict = blobs.blob_unserialize(blob)
            globalvars.CDR_DICTIONARY = blob_dict

            # Update related globals
            globalvars.CDR_obj = ContentDescriptionRecord(blob_dict)
            globalvars.subscription_pass_list = globalvars.CDR_obj.get_onpurchase_guest_passes_info()

            if b"\x03\x00\x00\x00" in blob_dict:
                globalvars.current_blob_datetime = steamtime_to_datetime(blob_dict[b"\x03\x00\x00\x00"])
                globalvars.CDDB_datetime = steamtime_to_datetime(blob_dict[b"\x03\x00\x00\x00"])
                config_datetime = steamtime_to_datetime(blob_dict[b"\x03\x00\x00\x00"])
                config["steam_date"] = config_datetime[0]
                config["steam_time"] = config_datetime[1]
    else:
        # Normal startup - load from finalized .bin files using the memory caching function
        # This also handles re-merging any ephemeral blobs from external content servers
        load_blobs_to_memory()

        # Update config with datetime from CDR_DICTIONARY
        if hasattr(globalvars.CDR_DICTIONARY, 'VersionNumber'):
            # CDR_DICTIONARY is a ContentDescriptionRecord object
            globalvars.CDDB_datetime = steamtime_to_datetime(globalvars.CDR_DICTIONARY.LastChangedExistingAppOrSubscriptionTime)
        else:
            # CDR_DICTIONARY is a raw dict
            globalvars.CDDB_datetime = steamtime_to_datetime(globalvars.CDR_DICTIONARY.get(b"\x03\x00\x00\x00"))
        config_datetime = globalvars.CDDB_datetime
        config["steam_date"] = config_datetime[0]
        config["steam_time"] = config_datetime[1]

    globalvars.ini_changed_by_server = False

    try:
        globalvars.settingsdb.set_setting('current_datetime', globalvars.CDDB_datetime)
    except Exception as e:
        log.error(f"Failed to store current_datetime: {e}")

    check_appinfo_cache()
    log_blob_information(True)

    if hash_needs_update:
        # Call the parent initializer, which sets most of the global vars during init.  this allows the server to load any changes made to the ini during blob or ini change.
        # parent_initializer(reinitialize = True)
        # Clear the event before starting new neutering process
        # This ensures handle_neutering_completion waits for the new neuter to complete
        neutering_done.clear()

        neuter_thread = Thread(target=neuter_worker, args=("load", "app", ",8"), daemon=True)
        neuter_thread.start()

        news_thread = Thread(target=handle_neutering_completion, daemon=True)
        news_thread.start()
    else:
        # recreate the client if it doesn't exist and not already created this session
        if not globalvars.bootstrapper_created:
            if not os.path.isfile(os.path.join("client", "lan", "Steam.exe")) or not os.path.isfile(os.path.join("client", "wan", "Steam.exe")):
                create_bootstrapper()
                globalvars.bootstrapper_created = True
            elif not os.path.isfile(os.path.join("client", "lan", "HldsUpdateTool.exe")) or not os.path.isfile(os.path.join("client", "wan", "HldsUpdateTool.exe")):
                create_bootstrapper()
                globalvars.bootstrapper_created = True
    # log_blob_information()
    # replace_installer_exes_thread()  # Function to call the installer steam.exe replacer for the website download

def launch_neuter_application_standalone():
    if os.path.isfile(globalvars.neuter_path):# and globalvars.record_ver > 1:
        with open(os.path.join('files', 'configs', '.isneutering'), 'w') as fp:
            pass
        if globalvars.IS_WINDOWS:
            if config["from_source"].lower() == "true":
                cmd = ["python", globalvars.neuter_path, "load", "app", ",8"]
            else:
                cmd = [globalvars.neuter_path, "load", "app", ",8"]
        else:
            cmd = ["python3", globalvars.neuter_path, "load", "app", ",8"]
        neuter1 = subprocess.Popen(cmd)
        neuter1.wait()
    else:
        rename_temp_blobs()


def handle_neutering_completion():
    try:
        log.debug("Waiting for neutering to complete...")
        # Wait until neutering_done is set by neuter_worker
        neutering_done.wait()
        log.debug("Neutering done event received")

        # Update CMS theme if CMS is enabled
        if config.get('use_cms', '').lower() == 'true':
            try:
                cmsdb.update_cms_theme()
            except Exception as e:
                log.error(f"Failed to update CMS theme: {e}")

        from steam3.news_update_manager import news_update_manager

        pkg_files_neutered = os.path.isfile(globalvars.neuter_path)
        news_update_manager.set_pkg_files_neutered(pkg_files_neutered)
        log.debug(f"Pkg files neutered: {pkg_files_neutered}")

        # CM server wait logic stays as-is
        cmserver_obj = None
        max_wait_time = 60
        wait_interval = 1
        waited_time = 0

        while waited_time < max_wait_time:
            try:
                from steam3.ClientManager import Client_Manager
                if hasattr(Client_Manager, 'cmserver_obj') and Client_Manager.cmserver_obj is not None:
                    cmserver_obj = Client_Manager.cmserver_obj
                    if getattr(cmserver_obj, 'is_running', False) or getattr(cmserver_obj, 'serversocket', None):
                        log.debug(f"Found CM server object after {waited_time}s")
                        break
            except Exception as e:
                log.debug(f"Exception while waiting for CM server: {e}")

            time.sleep(wait_interval)
            waited_time += wait_interval

        if cmserver_obj:
            log.info("Neutering completed, sending client update news to connected clients")
            news_update_manager.send_client_update_to_all_clients(cmserver_obj)
        else:
            log.warning(f"No CM server object available after waiting {max_wait_time} seconds - skipping news updates")

    except Exception as e:
        log.error(f"Error handling neutering completion: {e}")
        import traceback
        log.error(traceback.format_exc())


# The following functions are defunct because we have no way to insert the modified steam.exe/dll into the wise installer executable.
'''def replace_installer_exes():
    """
    Replace the Steam executable in the LAN and WAN installers.
    """
    neutering_flag_path = os.path.join('files', 'configs', '.isneutering')
    wait_for_neutering_to_complete(neutering_flag_path)

    try:
        copy_appropriate_installer()

        # Ensure webroot_path is normalized
        webroot_path = os.path.normpath(config['web_root'])

        # Use os.path.join and normalize all paths
        lan_installer = os.path.normpath(os.path.join(webroot_path, 'download', 'steaminstall_lan.exe'))
        wan_installer = os.path.normpath(os.path.join(webroot_path, 'download', 'steaminstall_wan.exe'))
        lan_steamexe_path = os.path.normpath(os.path.join('client', 'lan', 'steam.exe'))
        wan_steamexe_path = os.path.normpath(os.path.join('client', 'wan', 'steam.exe'))
        steamexe = os.path.normpath('STEAM.EXE')  # Normalizing in case the file system requires it

        replace_file_in_zip(lan_installer, steamexe, lan_steamexe_path)
        replace_file_in_zip(wan_installer, steamexe, wan_steamexe_path)
        log.info("Successfully replaced Steam executable in LAN and WAN installers.")
    except Exception as e:
        log.error(f"Error occurred while replacing installer exes: {e}")


def replace_installer_exes_thread():
    """
    Launch the replace_installer_exes function in its own thread.
    """
    thread = Thread(target=replace_installer_exes, name="ReplaceInstallerExesThread")
    thread.start()
    return thread'''


def quick_hash_file(file_path, sample_size=10*1024*1024):  # Sample size set to 10 MB
    file_size = os.path.getsize(file_path)
    hash_obj = xxhash.xxh64()

    with open(file_path, 'rb') as file:
        chunk = file.read(sample_size)
        hash_obj.update(chunk)

        if file_size > 2 * sample_size:
            file.seek(file_size // 2)
            chunk = file.read(sample_size)
            hash_obj.update(chunk)

        if file_size > sample_size:
            file.seek(-sample_size, os.SEEK_END)
            chunk = file.read(sample_size)
            hash_obj.update(chunk)

    return hash_obj.hexdigest()


def rename_temp_blobs():
    """
    Safely rename .temp blob files to their final names with retry logic.

    This function handles the atomic rename of temp blob files after neutering
    is complete. It includes proper error handling and retry logic to handle
    cases where files may be temporarily locked by other processes.
    """
    cache_dir = os.path.join("files", "cache")

    # List of blob files to rename: (temp_name, final_name)
    blob_files = [
        ("secondblob_lan.bin.temp", "secondblob_lan.bin"),
        ("secondblob_wan.bin.temp", "secondblob_wan.bin"),
        ("firstblob.bin.temp", "firstblob.bin"),
    ]

    for temp_name, final_name in blob_files:
        temp_path = os.path.join(cache_dir, temp_name)
        final_path = os.path.join(cache_dir, final_name)

        if not os.path.isfile(temp_path):
            continue

        # Retry up to 5 times with exponential backoff
        max_retries = 5
        for attempt in range(max_retries):
            try:
                # Try to remove existing file first
                if os.path.isfile(final_path):
                    try:
                        os.remove(final_path)
                    except PermissionError:
                        # File is locked, wait and retry
                        if attempt < max_retries - 1:
                            time.sleep(0.1 * (2 ** attempt))  # 100ms, 200ms, 400ms, 800ms
                            continue
                        else:
                            log.error(f"Cannot remove locked file {final_path} after {max_retries} attempts")
                            break
                    except OSError as e:
                        log.warning(f"Error removing {final_path}: {e}")

                # Perform the rename
                os.rename(temp_path, final_path)
                log.debug(f"Successfully renamed {temp_name} to {final_name}")
                break  # Success, exit retry loop

            except PermissionError as e:
                if attempt < max_retries - 1:
                    log.debug(f"Rename attempt {attempt + 1} failed for {temp_name}, retrying...")
                    time.sleep(0.1 * (2 ** attempt))
                else:
                    log.error(f"Failed to rename {temp_name} after {max_retries} attempts: {e}")
            except OSError as e:
                log.error(f"OS error renaming {temp_name} to {final_name}: {e}")
                break  # Don't retry on other OS errors

    # Clean up the .isneutering flag file
    neuter_flag = os.path.join('files', 'configs', '.isneutering')
    if os.path.isfile(neuter_flag):
        try:
            os.remove(neuter_flag)
        except Exception as e:
            log.warning(f"Failed to remove .isneutering flag: {e}")

    # Reload blobs into memory from the finalized cache files
    # This also re-merges any ephemeral blobs from external content servers
    try:
        load_blobs_to_memory()
    except Exception as e:
        log.error(f"Failed to load blobs to memory after rename: {e}")


def check_files_checksums(storage_crc_list, directory):
    for file_key in tqdm(storage_crc_list.keys(), desc="Checking files", file=sys.stdout):
        file_path = os.path.join(directory, f"{file_key}.data")
        if os.path.isfile(file_path):
            actual_checksum = quick_hash_file(file_path)
            if actual_checksum != storage_crc_list[file_key]:
                logging.error(f"Checksum mismatch for file: {file_path}")
        else:
            # File missing, move on
            continue


def autoupdate():
    try:
        conn = mariadb.connect(
                user=config['database_username'],
                password=config['database_password'],
                host=config['database_host'],
                database=config['database'],
                port=int(config['database_port'])
        )
        # Get Cursor
        cur = conn.cursor()

        try:
            cur.execute(f"SELECT * FROM version")
            if not cur.fetchall()[0][0] == 1:
                cur.execute("USE mysql")
                print(f"{config['database']} database schema out of date, dropping and rebuilding...")
                cur.execute(f"DROP DATABASE IF EXISTS {config['database']}")
        except Exception as e:
            if str(e) == f"Table '{config['database']}.version' doesn't exist" or str(e) == "list index out of range":
                try:
                    cur.execute("USE mysql")
                    print(f"{config['database']} database version missing, dropping and rebuilding...")
                    cur.execute(f"DROP DATABASE IF EXISTS {config['database']}")
                except Exception as e:
                    print(f"Error dropping emulator database: {e}")
            else:
                print(f"Error dropping emulator database: {e}")
        conn.close()
    except mariadb.Error as e:
        if not globalvars.mdb_ver == "0":
            print(f"Error connecting to MariaDB Platform: {e}")
        else:
            pass

    if not globalvars.IS_WINDOWS:
        logging.info("Auto-update is disabled on non-Windows platforms")
        return
    if config["emu_auto_update"].lower() == "true":
        arguments = sys.argv[0]

        if arguments.endswith("emulator.exe"):
            try:
                live_repo = "stmemu-update"
                test_repo = "stmemu-update-test"
                try:
                    uat_token = config["uat_key"]
                except:
                    uat_token = False
                if config["uat"] == "1" and uat_token:
                    repo = test_repo
                    headers = {"Authorization": f"Bearer {uat_token}", "Accept": "application/vnd.github.v3.raw"}
                else:
                    repo = live_repo
                    headers = {"Accept": "application/vnd.github.v3.raw"}
                url = f"https://api.github.com/repos/real-pmein1/{repo}/contents/"
                if os.path.isfile("emulatorTmp.exe"):
                    os.remove("emulatorTmp.exe")
                if os.path.isfile("emulatorNew.exe"):
                    os.remove("emulatorNew.exe")
                resp = requests.get(url + "version", headers=headers)

                keys = ["server", "serverui", "mdb", "serverweb"]
                lines = resp.text.strip().splitlines()
                result = {k: v for k, v in zip(keys, lines)}

                online_server_ver = result["server"]
                online_serverui_ver = result["serverui"]
                online_mdb_ver = result["mdb"]
                online_serverweb_ver = result["serverweb"]

                for file in os.listdir("."):
                    if file.startswith("Server_") and file.endswith(".mst"):
                        globalvars.emu_ver = file[7:-4]
                    elif file.startswith("ServerUI_") and file.endswith(".mst"):
                        globalvars.ui_ver = file[9:-4]
                    elif file.startswith("ServerDB_") and file.endswith(".mst"):
                        globalvars.mdb_ver = file[9:-4]
                    elif file.startswith("ServerWeb_") and file.endswith(".mst"):
                        globalvars.web_ver = file[10:-4]
                    elif file.endswith(".pkg") or file.endswith(".srv") or file.endswith(".out"):
                        os.remove(file)

                if online_server_ver != globalvars.emu_ver or not os.path.isfile("Server_" + online_server_ver + ".mst"):
                    shutil.copy("emulator.exe", "emulatorTmp.exe")
                    print("Server update found " + globalvars.emu_ver + " -> " + online_server_ver + ", downloading...")
                    response = requests.get(url + f"Server_{online_server_ver}.pkg", headers=headers, stream=True)
                    total_size_in_bytes = int(response.headers.get('content-length', 0))
                    block_size = 1024  # 1 Kilobyte
                    progress_bar = tqdm(total = total_size_in_bytes, unit = 'iB', unit_scale = True, ncols = 80, file=sys.stdout)
                    with open('Server_' + online_server_ver + '.pkg', 'wb') as file:
                        for data in response.iter_content(block_size):
                            progress_bar.update(len(data))
                            file.write(data)
                    progress_bar.close()
                    if total_size_in_bytes != 0 and progress_bar.n != total_size_in_bytes:
                        print("ERROR, something went wrong")

                    packages.package_unpack2('Server_' + online_server_ver + '.pkg', ".", online_server_ver, "Server")

                    for file in os.listdir("."):
                        if file.startswith("Server") and file.endswith(".mst"):
                            if file.startswith("Server_") and file != "Server_" + online_server_ver + ".mst":
                                os.remove(file)
                        elif file.endswith(".out"):
                            os.remove(file)
                        elif file.endswith(".pkg"):
                            os.remove(file)
                        elif file.endswith(".mst"):
                            os.remove(file)
                    if globalvars.emu_ver:
                        if int(globalvars.emu_ver, 16) <= 3: # For forcing cache flush from py27 to py39
                            print("Config change detected, flushing cache...")
                            cache_dir = os.path.join('files', 'cache')
                            shutil.rmtree(cache_dir)
                            os.mkdir(cache_dir)
                            os.mkdir(os.path.join(cache_dir, 'internal'))
                            os.mkdir(os.path.join(cache_dir, 'external'))
                            shutil.copy('emulator.ini', os.path.join(cache_dir, 'emulator.ini.cache'))
                            print
                    if globalvars.IS_WINDOWS:
                        subprocess.Popen("emulatorTmp.exe")
                    else:
                        subprocess.Popen([sys.executable, "emulator.py"])
                    sys.exit(0)
                
                if not online_serverui_ver == globalvars.ui_ver or not os.path.isfile("ServerUI_" + online_serverui_ver + ".mst"):
                    print("UI update found " + globalvars.ui_ver + " -> " + online_serverui_ver + ", downloading...")
                    response = requests.get(url + f"ServerUI_{online_serverui_ver}.pkg", headers=headers, stream=True)
                    total_size_in_bytes = int(response.headers.get('content-length', 0))
                    block_size = 1024  # 1 Kilobyte
                    progress_bar = tqdm(total = total_size_in_bytes, unit = 'iB', unit_scale = True, ncols = 80, file=sys.stdout)
                    with open('ServerUI_' + online_serverui_ver + '.pkg', 'wb') as file:
                        for data in response.iter_content(block_size):
                            progress_bar.update(len(data))
                            file.write(data)
                    progress_bar.close()
                    if total_size_in_bytes != 0 and progress_bar.n != total_size_in_bytes:
                        print("ERROR, something went wrong")

                    packages.package_unpack2('ServerUI_' + online_serverui_ver + '.pkg', ".", online_serverui_ver, "ServerUI")

                    for file in os.listdir("."):
                        if file.startswith("Server") and file.endswith(".mst"):
                            if file.startswith("ServerUI_") and file != "ServerUI_" + online_serverui_ver + ".mst":
                                os.remove(file)
                        elif file.endswith(".out"):
                            os.remove(file)
                        elif file.endswith(".pkg"):
                            os.remove(file)
                        elif file.endswith(".mst"):
                            os.remove(file)
                
                if not online_mdb_ver == globalvars.mdb_ver or not os.path.isfile("ServerDB_" + online_mdb_ver + ".mst"):
                    print("DB update found " + globalvars.mdb_ver + " -> " + online_mdb_ver + ", downloading...")
                    response = requests.get(url + f"ServerDB_{online_mdb_ver}.pkg", headers=headers, stream=True)
                    total_size_in_bytes = int(response.headers.get('content-length', 0))
                    block_size = 1024  # 1 Kilobyte
                    progress_bar = tqdm(total = total_size_in_bytes, unit = 'iB', unit_scale = True, ncols = 80, file=sys.stdout)
                    with open('ServerDB_' + online_mdb_ver + '.pkg', 'wb') as file:
                        for data in response.iter_content(block_size):
                            progress_bar.update(len(data))
                            file.write(data)
                    progress_bar.close()
                    if total_size_in_bytes != 0 and progress_bar.n != total_size_in_bytes:
                        print("ERROR, something went wrong")

                    packages.package_unpack2('ServerDB_' + online_mdb_ver + '.pkg', ".", online_mdb_ver, "ServerDB")
                    
                    if os.path.isfile('files/sql/ContentDescriptionDB.zip'):
                        with ZipFile('files/sql/ContentDescriptionDB.zip') as CDDB_ZIP:
                            CDDB_ZIP.extract('ContentDescriptionDB.sql', 'files/sql/')
                        os.remove('files/sql/ContentDescriptionDB.zip')

                    try:
                        conn = mariadb.connect(
                                user=config['database_username'],
                                password=config['database_password'],
                                host=config['database_host'],
                                database=config['database'],
                                port=int(config['database_port'])
                        )
                        # Get Cursor
                        cur = conn.cursor()

                        cur.execute(f"DELETE FROM executed_sql_files WHERE filename = 'ClientConfigurationDB.sql'")
                        cur.execute(f"DELETE FROM executed_sql_files WHERE filename = 'BetaContentDescriptionDB.sql'")
                        cur.execute(f"DELETE FROM executed_sql_files WHERE filename = 'ContentDescriptionDB.sql'")
                        cur.execute(f"DELETE FROM executed_sql_files WHERE filename = 'ProductInformationDB.sql'")
                        if os.path.isfile('files/sql/acheivement_master.sql') or os.path.isfile('files/sql/acheivements.sql'):
                            try:
                                os.remove('files/sql/acheivement_master.sql')
                            except:
                                pass
                            try:
                                os.remove('files/sql/acheivements.sql')
                            except:
                                pass
                            cur.execute(f"DELETE FROM executed_sql_files WHERE filename = 'acheivement_master.sql'")
                            cur.execute(f"DELETE FROM executed_sql_files WHERE filename = 'acheivements.sql'")
                            cur.execute(f"DROP TABLE achievement_master")
                            cur.execute(f"DROP TABLE achievement_percent")
                        conn.close()
                    except mariadb.Error as e:
                        if not globalvars.mdb_ver == "0":
                            print(f"Error connecting to MariaDB Platform: {e}")
                        else:
                            pass

                    for file in os.listdir("."):
                        if file.startswith("Server") and file.endswith(".mst"):
                            if file.startswith("ServerDB_") and file != "ServerDB_" + online_mdb_ver + ".mst":
                                os.remove(file)
                        elif file.endswith(".out"):
                            os.remove(file)
                        elif file.endswith(".pkg"):
                            os.remove(file)
                        elif file.endswith(".mst"):
                            os.remove(file)
                        elif file.startswith("MDB_"):
                            os.remove(file)
                
                if not online_serverweb_ver == globalvars.web_ver or not os.path.isfile("ServerWeb_" + online_serverweb_ver + ".mst"):
                    print("Web update found " + globalvars.web_ver + " -> " + online_serverweb_ver + ", downloading...")
                    response = requests.get(url + f"ServerWeb_{online_serverweb_ver}.pkg", headers=headers, stream=True)
                    total_size_in_bytes = int(response.headers.get('content-length', 0))
                    block_size = 1024  # 1 Kilobyte
                    progress_bar = tqdm(total = total_size_in_bytes, unit = 'iB', unit_scale = True, ncols = 80, file=sys.stdout)
                    with open('ServerWeb_' + online_serverweb_ver + '.pkg', 'wb') as file:
                        for data in response.iter_content(block_size):
                            progress_bar.update(len(data))
                            file.write(data)
                    progress_bar.close()
                    if total_size_in_bytes != 0 and progress_bar.n != total_size_in_bytes:
                        print("ERROR, something went wrong")

                    packages.package_unpack2('ServerWeb_' + online_serverweb_ver + '.pkg', ".", online_serverweb_ver, "ServerWeb")

                    for file in os.listdir("."):
                        if file.startswith("Server") and file.endswith(".mst"):
                            if file.startswith("ServerWeb_") and file != "ServerWeb_" + online_serverweb_ver + ".mst":
                                os.remove(file)
                        elif file.endswith(".out"):
                            os.remove(file)
                        elif file.endswith(".pkg"):
                            os.remove(file)
                        elif file.endswith(".mst"):
                            os.remove(file)

            except Exception as e:
                globalvars.update_exception1 = e
                print(e)
        elif arguments.endswith("emulatorTmp.exe") and not os.path.isfile("emulatorNew.exe"):
            print("WAITING...")
            try:

                os.remove("emulator.exe")
                shutil.copy("emulatorTmp.exe", "emulator.exe")
                if globalvars.IS_WINDOWS:
                    subprocess.Popen("emulator.exe")
                else:
                    subprocess.Popen([sys.executable, "python3", "emulator.py"])
                sys.exit(0)

            except Exception as e:
                globalvars.update_exception2 = e
        else:
            print("WAITING...")
            try:
                os.remove("emulator.exe")
                shutil.copy("emulatorNew.exe", "emulator.exe")
                if globalvars.IS_WINDOWS:
                    subprocess.Popen("emulator.exe")
                else:
                    subprocess.Popen([sys.executable, "python3", "emulator.py"])
                sys.exit(0)

            except Exception as e:
                globalvars.update_exception2 = e
    else:
        print("Skipping checking for updates (ini override)")
        return


def get_internal_ip():
    """Get the server's IP address."""
    try:
        # Connect to an external address (doesn't actually establish a connection)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))  # Google's DNS, used just to get the socket's name
            server_ip = s.getsockname()[0]
            save_config_value("server_ip", server_ip + "                     ; IP Address For Server to Bind/Listen On")
            return server_ip
    except Exception as e:
        print(f"Error obtaining IP address: {e}")

        return None


def get_external_ip(stun_server = 'stun.ekiga.net', stun_port = 3478, locationcheck = False):
    # STUN server request
    stun_request = b'\x00\x01' + b'\x00\x00' + b'\x21\x12\xA4\x42' + b'\x00' * 12

    # Create a UDP socket
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(2)

        # Resolve STUN server IP
        server_address = (socket.gethostbyname(stun_server), stun_port)

        try:
            # Send request to STUN server
            sock.sendto(stun_request, server_address)

            # Receive response
            data, _ = sock.recvfrom(1024)

            # Check for a valid response length
            if len(data) < 20:
                return 'Invalid response'

            # Check if it's a binding response message (success)
            msg_type, msg_len = struct.unpack_from('!HH', data, 0)
            if msg_type == 0x0101 and msg_len > 0:
                # Parse the response to get the external IP and port
                index = 20  # Start after header
                while index < len(data):
                    attr_type, attr_len = struct.unpack_from('!HH', data, index)
                    # Check for MappedAddress (0x0001) attribute
                    if attr_type == 0x0001 and attr_len >= 8:
                        # Unpack IP and convert to dotted-decimal notation
                        port, ip = struct.unpack_from('!xH4s', data[1:], index + 4)
                        ip = socket.inet_ntoa(ip)
                        if not locationcheck:
                            save_config_value("public_ip", ip + "                    ; External IP for allowing users to connect over the internet")
                        return ip
                    index += 4 + attr_len
        except socket.error:
            pass
    return 'Unable to determine external IP'


def is_valid_ip(ip_address):
    """Checks if the given IP address is valid."""
    try:
        socket.inet_aton(ip_address)
        return Counter(ip_address)['.'] == 3 and all(char.isdigit() or char == '.' for char in ip_address)
    except:
        return False


def check_ip_and_exit(ip_address, ip_type):
    """Checks an IP address, logs error and exits if invalid."""
    if ip_address != "0.0.0.0" and not is_valid_ip(ip_address):
        if len(ip_address) == 0:
            ip_address = "nothing"
        log.error(f"ERROR! The {ip_type} ip is malformed, currently: {ip_address}")
        time.sleep(1)
        input("Press Enter to exit...")
        quit()


def checkip():
    check_ip_and_exit(config["server_ip"], "server")
    check_ip_and_exit(config["public_ip"], "public")
    check_ip_and_exit(config["community_ip"], "community")


def setpublicip():
    # Define the IP prefixes and their corresponding network strings
    # ip_prefixes = {
    #    "10."    :"('10.",
    #    **{"172." + str(i) + ".":"('172." + str(i) + "." for i in range(16, 32)},
    #    "192.168.":"('192.168."
    # }

    # Check and set the server network based on IP prefixes
    # for prefix, network in ip_prefixes.items():
    #    if config["server_ip"].startswith(prefix):
    #        globalvars.servernet = network
    #        break

    # Determine the length for formatting

    if config["public_ip"] != "0.0.0.0":
        globalvars.public_ip = config['public_ip']
        globalvars.public_ip_b = globalvars.public_ip.encode("latin-1")


def setcommunityip():
    if config["community_ip"] == "":
        save_config_value("community_ip", config["server_ip"])


def print_stmserver_ipaddresses():
    iplen = max(len(config["server_ip"]), len(config["public_ip"]))
    print(("*" * 11) + ("*" * iplen))
    print(f"Server IP: {config['server_ip']}")
    if config["public_ip"] != "0.0.0.0":
        print(f"Public IP: {globalvars.public_ip}")
    print(("*" * 11) + ("*" * iplen))


def initialize(server_type: int = 0):
    if server_type in [0, 2]:
        utilities.database.userpy_to_db.check_and_process_user_data()

    file_cleanup()
    load_admin_ips()
    if config["override_ip_country_region"].lower() != 'false':
        if len(config["override_ip_country_region"]) != 2:
            print("Region code is not 2 characters.\n You MUST change server_region value to 2 characters exactly!")
            input("Press Enter to close server.")
            sys.exit(1)  # Exit the program with a non-zero status

    if config["storage_check"].lower() == "true" and server_type in [0, 4]:  # DISABLED CHECK UNTIL TESTED TO MAKE SURE NO I/O THRASHING
        log.info("--Starting Storage File Hash Check--")
        log.info("Starting Regular Storage Check")
        # check_files_checksums(checksum_dict.storage_crc_list, config["storagedir"])

        log.info("Starting V2 Storage Check")
        # check_files_checksums(checksum_dict.v2_storage_crc_list, config["v2storagedir"])
        # TODO CHECK v4 STORAGE HERE
        log.info("--Storage Hash Check Complete--")

    # Initial loading for ccdb for steam.exe neutering and placement.
    globalvars.firstblob_eval = ccdb.load_ccdb()

    if server_type in [0, 6]:
        cache_dir = os.path.join('files', 'cache')
        for filename in os.listdir(cache_dir):
            if globalvars.record_ver == 1 and "SteamUI_" in filename:
                os.remove(os.path.join(cache_dir, filename))
                break
            elif globalvars.record_ver != 1 and "PLATFORM_" in filename:
                os.remove(os.path.join(cache_dir, filename))
                break

        internal_cache = os.path.join(cache_dir, 'internal')
        if os.path.isdir(internal_cache):
            for filename in os.listdir(internal_cache):
                if globalvars.record_ver == 1 and "SteamUI_" in filename:
                    os.remove(os.path.join(internal_cache, filename))
                    break
                elif globalvars.record_ver != 1 and "PLATFORM_" in filename:
                    os.remove(os.path.join(internal_cache, filename))
                    break

        ext_cache_dir = os.path.join('files', 'cache', 'external')
        if os.path.isdir(ext_cache_dir):
            for filename in os.listdir(ext_cache_dir):
                if globalvars.record_ver == 1 and "SteamUI_" in filename:
                    os.remove(os.path.join(ext_cache_dir, filename))
                    break
                elif globalvars.record_ver != 1 and "PLATFORM_" in filename:
                    os.remove(os.path.join(ext_cache_dir, filename))
                    break

    file_altered = False

    cache_ini_path = os.path.join('files', 'cache', 'emulator.ini.cache')
    if not os.path.isfile(cache_ini_path):
        print("Config change detected, flushing cache...")
        cache_dir = os.path.join('files', 'cache')
        shutil.rmtree(cache_dir)
        try:
            os.mkdir(cache_dir)
            os.mkdir(os.path.join(cache_dir, 'internal'))
            os.mkdir(os.path.join(cache_dir, 'external'))
        except:
            pass # in case the folder itself isn't removed
        shutil.copy2('emulator.ini', cache_ini_path)
        print()
    else:
        try:
            with open('emulator.ini', 'r') as f:
                ini = f.readlines()
            with open(cache_ini_path, 'r') as g:
                cache = g.readlines()

            ini_list = []
            cache_list = []
            for line in ini:
                if ";" in line:
                    line = line[:line.index(";")]
                if "\t" in line:
                    line = line[:line.index("\t")]
                ini_list.append(line)
            for line in cache:
                if ";" in line:
                    line = line[:line.index(";")]
                if "\t" in line:
                    line = line[:line.index("\t")]
                cache_list.append(line)

            for line1 in ini_list:
                if "port" in line1 or "ip" in line1 or "http_domainname" in line1 or "enable_steam3_servers" in line1:
                    lineP1, lineP2 = line1.split("=")
                    for line2 in cache_list:
                        if (line2.startswith(lineP1 + "=") or line2.startswith(lineP1[1:] + "=")) and not line2.startswith(";" + lineP1[1:] + "="):
                            if line1 != line2:
                                file_altered = True
                            break

            if file_altered:
                print("Config change detected, flushing cache...")
                cache_dir = os.path.join('files', 'cache')
                shutil.rmtree(cache_dir)
                os.mkdir(cache_dir)
                os.mkdir(os.path.join(cache_dir, 'internal'))
                os.mkdir(os.path.join(cache_dir, 'external'))
                shutil.copy('emulator.ini', os.path.join(cache_dir, 'emulator.ini.cache'))
                print()
        except:  # FAILURE, ASSUME CACHE CORRUPTED
            print("Config change detected, flushing cache...")
            cache_dir = os.path.join('files', 'cache')
            shutil.rmtree(cache_dir)
            os.mkdir(cache_dir)
            os.mkdir(os.path.join(cache_dir, 'internal'))
            os.mkdir(os.path.join(cache_dir, 'external'))
            shutil.copy('emulator.ini', os.path.join(cache_dir, 'emulator.ini.cache'))
            print()
    globalvars.server_net = ipaddress.IPv4Network(
        config["server_ip"] + '/' + config["server_sm"], strict=False
    )
    globalvars.server_network = ipcalc.Network(str(globalvars.server_net))


def check_autoip_config():
    global config
    if config["auto_public_ip"].lower() == "true" or config["auto_server_ip"].lower() == "true":
        if config["auto_public_ip"].lower() == "true":
            globalvars.public_ip = get_external_ip()
            globalvars.public_ip_b = globalvars.public_ip.encode("latin-1")
        if config["auto_server_ip"].lower() == "true":
            globalvars.server_ip = get_internal_ip()
            globalvars.server_ip_b = globalvars.server_ip.encode("latin-1")
        #setcommunityip()
        setpublicip()
        # RELOAD THE CONFIG SO THE MEMORY CONTAINS THE LATEST CHANGES
        config = configurations.read_config()
    else:
        #setcommunityip()
        config = configurations.read_config()
        checkip()
        setpublicip()


def finalinitialize(log, server_type: int = 0):
    # Clean up any stale ephemeral blobs from previous runs (crash recovery)
    # This prevents accidentally merging old external content server blobs
    try:
        cleanup_all_ephemeral_blobs()
        log.debug("Cleaned up stale ephemeral blobs from previous session")
    except Exception as e:
        log.warning(f"Failed to cleanup ephemeral blobs on startup: {e}")

    # Cold-start check for custom neuter configs
    # Detects new/modified configs and invalidates affected caches before blob processing
    try:
        from utilities.custom_neuter_tracker import check_custom_neuter_configs
        result = check_custom_neuter_configs(is_cold_start=True)
        if result["new"] or result["modified"] or result["deleted"]:
            log.info(f"Custom neuter config changes detected on startup: "
                     f"new={result['new']}, modified={result['modified']}, deleted={result['deleted']}")
    except Exception as e:
        log.warning(f"Failed to check custom neuter configs on startup: {e}")

    check_secondblob_changed()

    # create_bootstrapper()

    # TODO NEED TO DEPRECATE THIS IN FAVOR OF PROTOCOL VERSIONING
    if isinstance(globalvars.steamui_ver, str):
        globalvars.tgt_version = "1"
    elif globalvars.steamui_ver < 61:  # guessing steamui version when steam client interface v2 changed to v3
        globalvars.tgt_version = "1"
    else:
        globalvars.tgt_version = "2"  # config file states 2 as default

    if not isinstance(globalvars.steamui_ver, str):
        if globalvars.steamui_ver < 122:
            if os.path.isfile("files/cafe/1.3/Steam.dll"):
                log.info("Cafe v1.3 files found")
                cafe_neutering.process_cafe_files(
                        "files/cafe/1.3/Steam.dll",
                        "files/cafe/1.3/CASpackage.zip",
                        "client/cafe_server/CASpackageWAN.zip",
                        "client/cafe_server/CASpackageLAN.zip",
                        "files/cafe/1.3/README.txt",
                        "client/Steam.exe",
                        config
                )
        elif globalvars.steamui_ver < 127:
            if os.path.isfile("files/cafe/1.4/Steam.dll"):
                log.info("Cafe v1.4 files found")
                cafe_neutering.process_cafe_files(
                        "files/cafe/1.4/Steam.dll",
                        "files/cafe/1.4/CASpackage.zip",
                        "client/cafe_server/CASpackageWAN.zip",
                        "client/cafe_server/CASpackageLAN.zip",
                        "files/cafe/1.4/README.txt",
                        "client/Steam.exe",
                        config
                )

    if os.path.isfile("Steam.exe"):
        os.remove("Steam.exe")
    if os.path.isfile("HldsUpdateTool.exe"):
        os.remove("HldsUpdateTool.exe")
    if os.path.isfile("log.txt"):
        os.remove("log.txt")
    if os.path.isfile("library.zip"):
        os.remove("library.zip")
    if os.path.isfile("MSVCR71.dll"):
        os.remove("MSVCR71.dll")
    if os.path.isfile("python24.dll"):
        os.remove("python24.dll")
    if os.path.isfile("python27.dll"):
        os.remove("python27.dll")
    if os.path.isfile("Steam.cfg"):
        os.remove("Steam.cfg")
    if os.path.isfile("w9xpopen.exe"):
        os.remove("w9xpopen.exe")
    if os.path.isfile("emulator.example.ini"):
        os.remove("emulator.example.ini")
    # if os.path.isfile("submanager.exe"):
    #    os.remove("submanager.exe")

    if os.path.isfile(os.path.join("files", "users.txt")):
        users = {}  # REMOVE LEGACY USERS
        f = open(os.path.join("files", "users.txt"))
        for line in f.readlines():
            if line[-1:] == "\n":
                line = line[:-1]
            if line.find(":") != -1:
                (user, password) = line.split(":")
                users[user] = user
        f.close()
        for user in users:
            user_py = os.path.join("files", "users", user + ".py")
            if os.path.isfile(user_py):
                os.rename(user_py, os.path.join("files", "users", user + ".legacy"))
        os.rename(os.path.join("files", "users.txt"), os.path.join("files", "users.off"))


def create_bootstrapper():
    # Note: The caller (ccdb.py) handles the logic for when to call this function,
    # including version changes. Do not add early return checks here.

    #  modify the steam and hlsupdatetool binary files
    try:
        if globalvars.record_ver == 0:
            f = open(
                os.path.join(
                    config["packagedir"],
                    "betav1",
                    f"Steam_{globalvars.steam_ver}.pkg",
                ),
                "rb",
            )
        elif globalvars.record_ver == 1:
            f = open(
                os.path.join(
                    config["packagedir"],
                    "betav2",
                    f"Steam_{globalvars.steam_ver}.pkg",
                ),
                "rb",
            )
        else:
            f = open(
                os.path.join(
                    config["packagedir"],
                    f"Steam_{globalvars.steam_ver}.pkg",
                ),
                "rb",
            )
    except:
        log.warning(f"Cannot Neuter, Package: Steam_{str(globalvars.steam_ver)}.pkg Not Present!")
        return

    pkg = Package(f.read())
    f.close()

    if config["reset_clears_client"].lower() == "true":
        shutil.rmtree("client")

    try:
        os.mkdir("client")
    except:
        pass

    try:
        os.mkdir(os.path.join("client", "lan"))
    except Exception:
        pass

    try:
        os.mkdir(os.path.join("client", "wan"))
    except Exception:
        pass

    #if not os.path.isfile("client/lan/Steam.exe") or not os.path.isfile("client/wan/Steam.exe"):
    try:
        file = pkg.get_file(b"SteamNew.exe")
        file2 = pkg.get_file(b"SteamNew.exe")

        file_wan = neuter.neuter_file(file, globalvars.public_ip, config["dir_server_port"], b"SteamNew.exe", False)
        file_lan = neuter.neuter_file(file2, globalvars.server_ip, config["dir_server_port"], b"SteamNew.exe", True)

        with open(os.path.join("client", "wan", "Steam.exe"), "wb") as f:
            f.write(file_wan)
        with open(os.path.join("client", "lan", "Steam.exe"), "wb") as g:
            g.write(file_lan)
        if globalvars.steamui_ver == "0.6.1.0/1.1.0.0":
            try:
                os.makedirs(os.path.join("files", "beta1_ftp", "0"))
            except:
                pass
            try:
                os.remove(os.path.join("files", "beta1_ftp", "0", "Steam1.exe"))
            except:
                pass
            if (config["public_ip"] != "0.0.0.0") or (config["public_ip"] != config["server_ip"]):
                with open(os.path.join("files", "beta1_ftp", "0", "Steam1.exe"), "wb") as h:
                    h.write(file_wan)
            else:
                with open(os.path.join("files", "beta1_ftp", "0", "Steam1.exe"), "wb") as i:
                    i.write(file_lan)
        else:
            try:
                os.remove(os.path.join("files", "beta1_ftp", "0", "Steam1.exe"))
            except:
                pass
            
    except:
        log.error("Steam Client Unwriteable!")
        pass

    #if not os.path.isfile("client/lan/HldsUpdateTool.exe") or not os.path.isfile("client/wan/HldsUpdateTool.exe"):
    try:
        if globalvars.record_ver != 0 and config["hldsupkg"] != "":
            if globalvars.record_ver == 1:
                g = open(
                    os.path.join(
                        config["packagedir"],
                        "betav2",
                        config["hldsupkg"],
                    ),
                    "rb",
                )
            else:
                g = open(
                    os.path.join(
                        config["packagedir"],
                        config["hldsupkg"],
                    ),
                    "rb",
                )
            pkg = Package(g.read())
            g.close()

            file = pkg.get_file(b"HldsUpdateToolNew.exe")
            file_wan = neuter.neuter_file(file, config["public_ip"], config["dir_server_port"], b"HldsUpdateToolNew.exe", False)
            file_lan = neuter.neuter_file(file, config["server_ip"], config["dir_server_port"], b"HldsUpdateToolNew.exe", True)

            with open(os.path.join("client", "wan", "HldsUpdateTool.exe"), "wb") as f:
                f.write(file_wan)
            with open(os.path.join("client", "lan", "HldsUpdateTool.exe"), "wb") as g:
                g.write(file_lan)
    except:
        log.error("HLDS Update Tool Unwriteable!")
        pass

    # Mark bootstrapper as created for this session
    globalvars.bootstrapper_created = True
    log.debug("Bootstrapper created successfully")


def generate_password():
    """
    Generate a random password consisting of letters (uppercase and lowercase),
    digits, and punctuation characters.

    Returns:
        str: The generated password.
    """
    characters = string.ascii_letters + string.digits # + string.punctuation
    password = ''.join(random.choice(characters) for _ in range(16))
    return password


def check_peerpassword():
    """Check if there is a peer password, if not it'll generate one"""
    try:
        if "peer_password" in config and config["peer_password"]:
            # The peer_password is present and not empty
            globalvars.peer_password = config["peer_password"]
            return 0
        else:
            # The peer_password is missing or empty
            # Generate a new password
            globalvars.peer_password = generate_password()

            # Save the new password to the config file
            save_config_value("peer_password", globalvars.peer_password)
            return 1
    except Exception as e:
        log.warning(f"An error occurred while checking/setting peer password: {e}")
        return -1


def parent_initializer( reinitialize = False):
    if reinitialize:
        log.info("---Starting Re-Initialization---")
    else:
        log.info("---Starting Initialization---")

    globalvars.cellid = int(config["cellid"])
    globalvars.dir_ismaster = config["dir_ismaster"].lower()
    # globalvars.use_file_blobs = config["use_file_blobs"].lower()
    globalvars.smtp_enable = config['smtp_enabled'].lower()
    globalvars.force_email_verification = config['force_email_verification'].lower()

    initialize()
    sync_settings_to_db()

    # IP Address variables must be set after initializer() incase user wants to use auto_ip and leave the server_ip or public_ip blank
    globalvars.server_ip = config["server_ip"]
    globalvars.server_ip_b = globalvars.server_ip.encode("latin-1")
    globalvars.public_ip = config["public_ip"]
    globalvars.public_ip_b = globalvars.public_ip.encode("latin-1")

    if not globalvars.update_exception1 == "":
        log.debug("Update1 error: " + str(globalvars.update_exception1))
    if not globalvars.update_exception2 == "":
        log.debug("Update2 error: " + str(globalvars.update_exception2))

    legacygamekeys.insert_gamekeys(config["database_host"], config["database_username"], config["database_password"], config["database_port"], config["database"])
    if not reinitialize:
        finalinitialize(log)

    log.info(f"Loading Suggested Names Modifiers from file and adding to default list")
    load_modifiers_from_files()
    if reinitialize:
        log.info("---Re-Initialization Complete---")
    else:
        log.info("---Initialization Complete---")
        print()

    # check for a peer_password, otherwise generate one
    return check_peerpassword()

def standalone_parent_initializer(server_type: int = 0):
    """
    This initializer is used for the standalone server launchers
    Server Types:
        1. Directory Server
        2. AuthServer
        3. CSDS
        4. Content Server
        5. Config Server
        6. Client Update Server
    """
    log.info("---Starting Initialization---")

    globalvars.cs_region = 'US' if config["override_ip_country_region"].lower() == 'false' else config["override_ip_country_region"].upper()
    globalvars.cellid = int(config["cellid"])
    globalvars.dir_ismaster = config["dir_ismaster"].lower()
    # globalvars.use_file_blobs = config["use_file_blobs"].lower()
    if server_type == 2:
        globalvars.smtp_enable = config['smtp_enabled'].lower()
        globalvars.force_email_verification = config['force_email_verification'].lower()

    initialize(server_type)
    sync_settings_to_db()

    # IP Address variables must be set after initializer() incase user wants to use auto_ip and leave the server_ip or public_ip blank
    globalvars.server_ip = config["server_ip"]
    globalvars.server_ip_b = globalvars.server_ip.encode("latin-1")
    globalvars.public_ip = config["public_ip"]
    globalvars.public_ip_b = globalvars.public_ip.encode("latin-1")

    """if not globalvars.update_exception1 == "":
        log.debug("Update1 error: " + str(globalvars.update_exception1))
    if not globalvars.update_exception2 == "":
        log.debug("Update2 error: " + str(globalvars.update_exception2))"""

    if server_type in [2, 6]:
        finalinitialize(log, server_type)

        if server_type == 2:
            log.info(f"Loading Suggested Names Modifiers from file and adding to default list")
            load_modifiers_from_files()
            log.info("---Initialization Complete---")
            print()

    # check for a peer_password, otherwise generate one
    return check_peerpassword()


def get_location(ip_address):
    """ This function is used only for more realistic warning emails for things like: attempted login with incorrect password.
    If the IP is a LAN IP then we grab the servers external IP, we assume the client and server both use the same external
    IP and we get the location information for the email!"""
    if str(ip_address) in globalvars.server_network:
        ip_address = get_external_ip(locationcheck=True)

    url = f'http://ip-api.com/json/{ip_address}'

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        if data['status'] == 'success':
            country = data.get('country', 'Unknown')
            region_name = data.get('regionName', 'Unknown')
            return country, region_name
        else:
            return 'Failed to retrieve data', 'Failed to retrieve data'
    except requests.RequestException as e:
        return f'Error: {e}', f'Error: {e}'


# This method is for killing any 'seperate' processes we may have started such as
# Apache or MariaDB
def kill_process(pid):
    """Kills the process identified by pid."""
    if globalvars.IS_WINDOWS:
        subprocess.call(['taskkill', '/F', '/T', '/PID', str(pid)])
    else:  # Unix/Linux
        os.kill(pid, signal.SIGTERM)


def generate_secure_password(length=16):
    # Use only letters and digits, excluding symbols
    alphabet = string.ascii_letters + string.digits
    password = ''.join(secrets.choice(alphabet) for i in range(length))
    return password


def generate_unique_server_id():
    import uuid
    return uuid.uuid4().bytes


def file_cleanup():
    try:
        os.remove("trackerserver.exe")
    except:
        pass
    try:
        os.remove("trackerserver.db")
    except:
        pass
    try:
        os.remove("client/Steam.exe")
    except:
        pass
    try:
        os.remove("client/HldsUpdateTool.exe")
    except:
        pass
    return


def get_derived_appids():
    expanded_numbers = []
    ranges = ["1-5", "11-25", "30-35", "40-45", "50-51", "56", "60-65", "70", "72-79", "81-89", "92", "104-111", "204", "205", "242-253", "0", "260", "80", "95", "100", "101-103", "200", "210", "241"]
    for r in ranges:
        if "-" in r:
            start, end = map(int, r.split("-"))
            expanded_numbers.extend(range(start, end + 1))
        else:
            expanded_numbers.append(int(r))

    return ",".join(map(str, expanded_numbers))


def load_admin_ips():
    try:
        with open('files/configs/admin_ip_list.txt', 'r') as file:
            for line in file:
                ip_address = line.strip()
                if ip_address:  # Make sure the line is not empty
                    globalvars.authenticated_ips[ip_address] = True
        log.info(f"Loaded {len(globalvars.authenticated_ips)} admin IPs from the config file.")
    except FileNotFoundError:
        log.warn("Admin IP list file not found.")
    except Exception as e:
        log.error(f"Error loading admin IPs: {e}")


def check_ini_duplicates():
    duplicate_lines = []
    with open("emulator.ini", 'r') as f:
        seen = set()
        for raw_line in f:
            line = raw_line.strip()

            # Ignore comments and blank lines
            if not line or line.startswith(";"):
                continue

            if "=" in line:
                key = line.split("=", 1)[0].strip().lower()

                if key in seen:
                    duplicate_lines.append(key)
                else:
                    seen.add(key)

    return duplicate_lines


def blink_text(text):
    while True:
        sys.stdout.write('\033[5m' + text + '\033[0m')
        sys.stdout.flush()
        time.sleep(0.5)
        sys.stdout.write('\r' + ' ' * len(text) + '\r')
        sys.stdout.flush()
        time.sleep(0.5)


def ip_replacer(file, filename, ip, server_ip):
    # Check if the length of `server_ip` is greater than `ip`
    if len(server_ip) > len(ip):
        # If `server_ip` is longer, just return the original file without changes
        return file

    loc = file.find(ip)
    if loc != -1:
        # Ensuring `server_ip` fills up to the length of `ip` with null bytes if shorter
        replace_ip = server_ip.ljust(len(ip), b"\x00")
        file = file[:loc] + replace_ip + file[loc + len(ip):]
        log.debug(f"{filename}: Found and replaced IP {ip} at location {loc:08x}")
    return file


def log_blob_information(silent=False):
    date_obj = datetime.strptime(globalvars.CDDB_datetime, "%m/%d/%Y %H:%M:%S")
    formatted_date = date_obj.strftime("%Y/%m/%d") # Changed date to Y/M/D to avoid confusion
    globalvars.formatted_date = formatted_date
    globalvars.formatted_underscore_date = date_obj.strftime("%Y-%m-%d") # For neutering
    if not silent:
        print()
        log.info("Steam Environment Information:")
        log.info(f"  Steam Version   : {globalvars.steam_ver}")
        if formatted_date < "2003/09/11":
            log.info(f"  Game Version    : {globalvars.steamui_ver}")
        else:
            log.info(f"  SteamUI Version : {globalvars.steamui_ver}")
        log.info(f"  Blob Timestamp  : {formatted_date}")
        print()
