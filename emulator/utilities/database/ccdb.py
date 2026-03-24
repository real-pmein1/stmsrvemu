import ast
import logging
import os
import shutil
import struct
import zlib
import mariadb
import time
import hashlib
import io
import zipfile
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA1

from datetime import datetime, timedelta, timezone
from tzlocal import get_localzone

import utils

from config import get_config
from utilities import blobs, packages
from utilities.blobs import convert_to_bytes_deep
from utilities.database import dbengine  # Import the function to create database driver
from utilities.neuter import neuter_file
from utilities.filesig_neuter import FileSignatureModifier
import utilities.encryption as encryption

log = logging.getLogger("CCDB")

config = get_config()

# In-memory cache for firstblob to avoid per-connection disk reads
_firstblob_cache = {
    'blob': None,
    'serialized': None,
    'mtime': None
}


def process_date(date_str):
    for char in [":", "/", "\\", "-", "_"]:
        date_str = date_str.replace(char, "")
    print(date_str)
    return date_str


def process_time(time_str):
    time = time_str.replace(":", "")
    print(time)
    return time


def create_firstblob_from_row(row):
    firstblob = {}

    columns_with_null = [8, 10, 12, 14]  # columns that require a null character '\x00' appended to their value

    for i in range(1, 19):
        if row[i] != "":
            key = struct.pack("<L", i - 1)  # Column 1 is key 0, Column 2 is key 1, and so on
            if i in columns_with_null:
                # Append \x00 for columns_with_null
                value = str(row[i]) + "\x00"
            else:
                # Handle as integer for other columns
                value = struct.pack("<L", int(row[i])) if i <= 13 else row[i]
            firstblob[key] = value
    return firstblob


import globalvars
def load_blob_from_file(file_path):
    blob_context = {}
    with open(file_path, 'r', encoding='latin-1') as file:
        file_content = file.read()
        exec(file_content, {}, blob_context)
    return blob_context.get('blob', {})


def neuter_ccdb(req_type='dict'):
    date_separator = ["-", "/", "_", "."]
    time_separator = [":", "_"]
    new_date = False
    new_time = False
    with open("emulator.ini", 'r') as f:
        mainini = f.readlines()
    for line in mainini:
        if line.startswith("steam_date"):
            new_date = line[11:21]
        if line.startswith("steam_time"):
            new_time = line[11:19]
    try:
        log.info(f"Creating client configuration from ClientConfigurationDB...")
        # Check if new_date/new_time were found in config (not still False)
        if isinstance(new_date, bool) or isinstance(new_time, bool):
            # Check if blob files exist - if they do, raise error to use file-based loading
            blob_files_exist = (
                os.path.isfile("files/1stcdr.py") or
                os.path.isfile("files/firstblob.py") or
                os.path.isfile("files/firstblob.bin") or
                os.path.isfile("files/firstblob.xml") or
                os.path.isfile("files/secondblob.py") or
                os.path.isfile("files/secondblob.bin") or
                os.path.isfile("files/secondblob.xml")
            )
            if blob_files_exist:
                raise
            else:
                log.warn("First and second blob files are missing and steam_date and steam_time are missing from emulator.ini!!  Defaulting to August 28th Hl2 preload 1 Blob!")
                new_date = "2024-08-26"
                new_time = "19:46:45"
        for separator in date_separator:
            if separator in new_date:
                datetime.strptime(new_date, f"%Y{separator}%m{separator}%d")
                steam_date = new_date.replace(separator, "-")
        for separator in time_separator:
            if separator in new_time:
                datetime.strptime(new_time, f"%H{separator}%M{separator}%S")
                steam_time = new_time.replace(separator, "_")
        timestamp = steam_date + " " + steam_time
        local_tz = get_localzone()

        # ======== TIMEZONE CONVERSION ========
        # Parse the timestamp as UTC
        db_dt = datetime.strptime(timestamp, "%Y-%m-%d %H_%M_%S").replace(tzinfo = timezone.utc)

        # No conversion to local time is needed
        # Remove the timezone info if your database expects naive datetime in UTC
        # db_dt = db_dt.replace(tzinfo=None)

        # Format the timestamp for SQL query
        timestamp = db_dt.strftime('%Y-%m-%d %H_%M_%S')
        # =====================================

        if timestamp < "2002-02-25 07_42_30":
            timestamp = "2002-02-25 07_42_30"

        conn2 = mariadb.connect(
            user=config["database_username"],
            password=config["database_password"],
            host=config["database_host"],
            port=int(config["database_port"]),
            database="ClientConfigurationDB"
        )
        blob_dict = construct_blob_from_ccdb(config["database_host"], config["database_port"], config["database_username"], config["database_password"], timestamp)
        blob = blobs.blob_serialize(blob_dict)
        if timestamp >= "2013-01-23 23_10_34":
            if not os.path.isfile(os.path.join(config["web_root"], "client", "steam_client_lan32")) or not os.path.isfile(os.path.join(config["web_root"], "client", "steam_client_wan32")):
                try:
                    steam3_client_neuter(config["database_host"], config["database_port"], config["database_username"], config["database_password"], timestamp)
                except:
                    log.debug("No steam3 client found for this date") # don't really care if they don't have the steam3 client package
    except Exception as e:
        log.warn("Client configuration creation from ClientConfigurationDB failed")
        log.debug(f"DB error: {str(e)}")
        log.info("Using local firstblob file for client configuration")
        if os.path.isfile("files/1stcdr.py") or os.path.isfile("files/firstblob.py"):
            source_file = "files/1stcdr.py" if os.path.isfile("files/1stcdr.py") else "files/firstblob.py"

            if source_file == "files/1stcdr.py":
                shutil.copy2(source_file, "files/firstblob.py")
                os.remove(source_file)

            blob_dict = load_blob_from_file("files/firstblob.py")
            blob_dict = blobs.convert_to_bytes_deep(blob_dict)
            blob = blobs.blob_serialize(blob_dict)

            # Adjust this part to ensure compatibility
        else :
            if not os.path.isfile("files/firstblob.bin"):
                log.warn("firstblob not found, waiting for file...")
                while True:
                    time.sleep(1)
                    if os.path.isfile("files/firstblob.bin"):
                        break
            with open("files/firstblob.bin", "rb") as f:
                blob = f.read()
            if blob[0:2] == b"\x01\x43":
                blob = zlib.decompress(blob[20:])
            # OPTIMIZATION: Use blob_unserialize directly instead of blob_dump + ast.literal_eval
            blob_dict = blobs.blob_unserialize(blob)

    current_record_ver = globalvars.record_ver
    current_steam_ver = globalvars.steam_ver

    globalvars.record_ver = struct.unpack("<L", blob_dict[b"\x00\x00\x00\x00"])[0]
    globalvars.steam_ver = struct.unpack("<L", blob_dict[b"\x01\x00\x00\x00"])[0]
    if globalvars.record_ver == 0:
        globalvars.steamui_ver = '.'.join(str(x) for x in struct.unpack("<IIII", blob_dict[b"\x02\x00\x00\x00"][:16])) + "/" + '.'.join(str(x) for x in struct.unpack("<IIII", blob_dict[b"\x02\x00\x00\x00"][16:]))
    else:
        globalvars.steamui_ver = struct.unpack("<L", blob_dict[b"\x02\x00\x00\x00"])[0]

    # Check if bootstrapper needs to be created/recreated
    needs_bootstrapper = False
    version_changed = False

    if current_record_ver != globalvars.record_ver:
        log.debug(f"Record version changed: {current_record_ver} -> {globalvars.record_ver}")
        needs_bootstrapper = True
        version_changed = True
    elif current_steam_ver != globalvars.steam_ver:
        log.debug(f"Steam version changed: {current_steam_ver} -> {globalvars.steam_ver}")
        needs_bootstrapper = True
        version_changed = True
    elif not os.path.isfile(os.path.join("client", "lan", "Steam.exe")) or not os.path.isfile(os.path.join("client", "wan", "Steam.exe")):
        log.debug("Steam.exe missing from client folder")
        needs_bootstrapper = True
    elif not os.path.isfile(os.path.join("client", "lan", "HldsUpdateTool.exe")) or not os.path.isfile(os.path.join("client", "wan", "HldsUpdateTool.exe")):
        log.debug("HldsUpdateTool.exe missing from client folder")
        needs_bootstrapper = True

    # Only create if needed AND (version changed OR not already created this session)
    if needs_bootstrapper and (version_changed or not globalvars.bootstrapper_created):
        utils.create_bootstrapper()
        globalvars.bootstrapper_created = True

    log.debug("CCDB change detected, blob version is " + str(globalvars.record_ver))

    # Check if the files exist and log warning if they don't
    if globalvars.record_ver == 0:
        steam_pkg_file = os.path.join(
            config['packagedir'],
            'betav1',
            f"Steam_{globalvars.steam_ver}.pkg",
        )
        if not os.path.exists(steam_pkg_file):
            log.warning(f"The package {steam_pkg_file} is missing.")
    elif globalvars.record_ver == 1:
        steam_pkg_file = os.path.join(
            config['packagedir'],
            'betav2',
            f"Steam_{globalvars.steam_ver}.pkg",
        )
        steamui_pkg_file = os.path.join(
            config['packagedir'],
            'betav2',
            f"PLATFORM_{globalvars.steamui_ver}.pkg",
        )
        if not os.path.exists(steam_pkg_file):
            log.warning(f"The package {steam_pkg_file} is missing.")
        if not os.path.exists(steamui_pkg_file):
            log.warning(f"The package {steamui_pkg_file} is missing.")
    else:
        steam_pkg_file = os.path.join(
            config['packagedir'],
            f"Steam_{globalvars.steam_ver}.pkg",
        )
        steamui_pkg_file = os.path.join(
            config['packagedir'],
            f"SteamUI_{globalvars.steamui_ver}.pkg",
        )
        if not os.path.exists(steam_pkg_file):
            log.warning(f"The package {steam_pkg_file} is missing.")
        if not os.path.exists(steamui_pkg_file):
            log.warning(f"The package {steamui_pkg_file} is missing.")

    #utils.check_secondblob_changed()
    serialized_blob = blobs.blob_serialize(blob_dict)
    cache_dir = os.path.join("files", "cache")
    firstblob_temp = os.path.join(cache_dir, "firstblob.bin.temp")
    firstblob = os.path.join(cache_dir, "firstblob.bin")
    secondblob_lan_temp = os.path.join(cache_dir, "secondblob_lan.bin.temp")

    if os.path.isfile(secondblob_lan_temp):
        if not os.path.isfile(firstblob_temp):
            with open(firstblob_temp, 'wb') as blob_file:
                blob_file.write(serialized_blob)
    else:
        if os.path.isfile(firstblob):
            try:
                os.remove(firstblob)
            except:
                pass
        with open(firstblob, 'wb') as blob_file:
            blob_file.write(serialized_blob)

    if req_type == 'blob':
        return blob
    else:
        return serialized_blob


def load_ccdb(req_type='dict'):
    """Load the first blob (CCDB) with in-memory caching.

    The blob is cached in memory and only reloaded when the file on disk changes.
    """
    global _firstblob_cache

    cache_dir = os.path.join("files", "cache")
    firstblob_path = os.path.join(cache_dir, "firstblob.bin")

    # Check if we need to reload from disk
    current_mtime = None
    if os.path.isfile(firstblob_path):
        current_mtime = os.path.getmtime(firstblob_path)

    # Use cached values if file hasn't changed
    if (_firstblob_cache['mtime'] is not None and
        current_mtime is not None and
        current_mtime == _firstblob_cache['mtime'] and
        _firstblob_cache['blob'] is not None):
        log.debug("Using in-memory cached firstblob")
        if req_type == 'blob':
            return _firstblob_cache['blob']
        else:
            return _firstblob_cache['serialized']

    # Need to load from disk
    if os.path.isfile(firstblob_path):
        log.info("Loading firstblob from disk cache")
        with open(firstblob_path, 'rb') as blob_file:
            blob = blob_file.read()
        if blob[0:2] == b"\x01\x43":
            blob = zlib.decompress(blob[20:])
        # OPTIMIZATION: Use blob_unserialize directly instead of blob_dump + ast.literal_eval
        blob_dict = blobs.blob_unserialize(blob)
        serialized_blob = blobs.blob_serialize(blob_dict)

        globalvars.record_ver = struct.unpack("<L", blob_dict[b"\x00\x00\x00\x00"])[0]
        globalvars.steam_ver = struct.unpack("<L", blob_dict[b"\x01\x00\x00\x00"])[0]
        if globalvars.record_ver == 0:
            globalvars.steamui_ver = '.'.join(str(x) for x in struct.unpack("<IIII", blob_dict[b"\x02\x00\x00\x00"][:16])) + "/" + '.'.join(str(x) for x in struct.unpack("<IIII", blob_dict[b"\x02\x00\x00\x00"][16:]))
        else:
            globalvars.steamui_ver = struct.unpack("<L", blob_dict[b"\x02\x00\x00\x00"])[0]

        # Update cache
        _firstblob_cache['blob'] = blob
        _firstblob_cache['serialized'] = serialized_blob
        _firstblob_cache['mtime'] = current_mtime
    else:
        # Call neuter_ccdb once - it processes the CCDB and writes firstblob.bin
        serialized_blob = neuter_ccdb('dict')
        # Read the blob back from the cache file that was just written
        if os.path.isfile(firstblob_path):
            with open(firstblob_path, 'rb') as blob_file:
                blob = blob_file.read()
            # Update cache with newly created file
            _firstblob_cache['blob'] = blob
            _firstblob_cache['serialized'] = serialized_blob
            _firstblob_cache['mtime'] = os.path.getmtime(firstblob_path)
        else:
            # Fallback: serialize from the dict if file wasn't written
            blob = serialized_blob

    if req_type == 'blob':
        return blob
    else:
        return serialized_blob


def construct_blob_from_ccdb(db_host, db_port, db_user, db_pass, timestamp):
    conn2 = mariadb.connect(
    user=db_user,
    password=db_pass,
    host=db_host,
    port=int(db_port),
    database="ClientConfigurationDB"
    )
    cur = conn2.cursor()
    blob = {}
    cur.execute("SELECT ccr_blobdatetime FROM configurations ORDER BY ccr_blobdatetime DESC")
    chosen_datetime = datetime.strptime(timestamp, "%Y-%m-%d %H_%M_%S")
    blob_found = False
    for data in cur:
        blob_datetime = datetime.strptime(data[0], "%Y-%m-%d %H_%M_%S")
        if blob_datetime <= chosen_datetime:
            blob_found = True
            break
    if blob_found:
        cur.execute(f'SELECT * FROM configurations WHERE ccr_blobdatetime = "{data[0]}"')
        for data in cur:
            blob[b'\x00\x00\x00\x00'] = struct.pack('<i', int(data[1]))
            blob[b'\x01\x00\x00\x00'] = struct.pack('<i', int(data[2]))
            if int(data[1]) == 0:
                blob[b'\x02\x00\x00\x00'] = struct.pack('<IIIIIIII', int(data[3][0]), int(data[3][1]), int(data[3][2]), int(data[3][3]), int(data[3][4]), int(data[3][5]), int(data[3][6]), int(data[3][7]) )
            else:
                blob[b'\x02\x00\x00\x00'] = struct.pack('<i', int(data[3]))
            if data[4] != None: blob[b'\x03\x00\x00\x00'] = struct.pack('<i', int(data[4]))
            if data[5] != None: blob[b'\x04\x00\x00\x00'] = struct.pack('<i', int(data[5]))
            if data[6] != None: blob[b'\x05\x00\x00\x00'] = struct.pack('<i', int(data[6]))
            if data[7] != None: blob[b'\x06\x00\x00\x00'] = struct.pack('<i', int(data[7]))
            if data[8] != None: blob[b'\x07\x00\x00\x00'] = bytes(data[8], 'UTF-8') + b'\x00'
            if data[9] != None: blob[b'\x08\x00\x00\x00'] = struct.pack('<i', int(data[9]))
            if data[10] != None: blob[b'\x09\x00\x00\x00'] = bytes(data[10], 'UTF-8') + b'\x00'
            if data[11] != None: blob[b'\x0a\x00\x00\x00'] = struct.pack('<i', int(data[11]))
            if data[12] != None: blob[b'\x0b\x00\x00\x00'] = bytes(data[12], 'UTF-8') + b'\x00'
            if data[13] != None: blob[b'\x0c\x00\x00\x00'] = struct.pack('<i', int(data[13]))
            if data[14] != None: blob[b'\x0d\x00\x00\x00'] = bytes(data[14], 'UTF-8') + b'\x00'
            if data[15] != None or data[16] != None or data[17] != None: blob[b'\x0e\x00\x00\x00'] = {}
            if data[17] != None: blob[b'\x0e\x00\x00\x00'][b'SteamGameUpdater'] = struct.pack('<i', int(data[17]))
            if data[15] != None: blob[b'\x0e\x00\x00\x00'][b'cac'] = struct.pack('<i', int(data[15]))
            if data[16] != None: blob[b'\x0e\x00\x00\x00'][b'cas'] = struct.pack('<i', int(data[16]))
            if data[18] != None: blob[b'\x0f\x00\x00\x00'] = struct.pack('<i', int(data[18]))
    return blob


def set_sql_data(conn, filename, orig_checksum, new_checksum, new_size, connection_type):
    # Get Cursor
    cur = conn.cursor()

    client_manifest = {}
    cur.execute(f"update steam_client_win32 set checksum_{connection_type} = '{new_checksum}', size_{connection_type} = {new_size} where filename = '{filename}' and checksum = '{orig_checksum}'")
    conn.commit()


def unzip_modify_zip(conn, input_zip_path, input_zip: bytes, output_zip_path: str, connection_type):
    with zipfile.ZipFile(io.BytesIO(input_zip), 'r') as zip_in:
        zip_filename = input_zip_path
        if ".zip" in zip_filename:
            zip_filename = zip_filename.replace(".zip", "")
        if ".vz" in zip_filename:
            zip_filename = zip_filename.replace(".vz", "")
        if "\\" in zip_filename:
            zip_filename = zip_filename[zip_filename.rfind("\\") + 1:]
        if "/" in zip_filename:
            zip_filename = zip_filename[zip_filename.rfind("/") + 1:]
        if "." in zip_filename:
            zip_filename, orig_checksum = zip_filename.split(".")

        if connection_type == "lan":
            islan = True
        else:
            islan = False

        with io.BytesIO() as byte_io:
            with zipfile.ZipFile(byte_io, 'w', zipfile.ZIP_DEFLATED) as zip_out:
                for filename in zip_in.namelist():
                    file_content = zip_in.read(filename)
                    modified_content = neuter_file(file_content, config["server_ip"], config["dir_server_port"], filename, islan)

                    if filename.lower().endswith(('.dll', '.exe')):
                        modifier = FileSignatureModifier(modified_content)
                        modified_content = modifier.modify_file()

                    if filename.lower() == "steam.exe":
                        filename = "SteamTin.exe"

                    zip_out.writestr(filename, modified_content)

                if globalvars.CDDB_datetime is not None:
                    current = datetime.strptime(globalvars.CDDB_datetime, "%m/%d/%Y %H:%M:%S")
                else:
                    steam_date = ''.join('/' if c in ['-', '_'] else c for c in config["steam_date"])
                    steam_time = ''.join(':' if c in ['/', '_', '-'] else c for c in config["steam_time"])
                    current = datetime.strptime(steam_date + " " + steam_time, "%Y/%m/%d %H:%M:%S")
                if datetime(2013, 2, 14, 11, 23, 50) <= current < datetime(2016, 6, 30, 18, 12, 7):
                    tinfiledate = "2013"
                else:
                    tinfiledate = "2016"

                if os.path.isfile(f"files/mod_package/{tinfiledate}/TINserverClient.dll"):
                    zip_out.write(f"files/mod_package/{tinfiledate}/TINserverClient.dll", arcname="TINserverClient.dll")
                    if islan:
                        serverIP = config["tinserver_ip"]
                    else:
                        serverIP = config["public_ip"]
                    ini_content = f"""[steam]
commandLine=SteamTin.exe -console -windowed -no-browser
dll=TINserverClient.dll

[network]
serverIp={serverIP}

[logs]
level=info
console=false
                    """
                    zip_out.writestr("TINserverClient.ini", ini_content)

                if os.path.isfile(f"files/mod_package/{tinfiledate}/TINserverClient.exe"):
                    zip_out.write(f"files/mod_package/{tinfiledate}/TINserverClient.exe", arcname="Steam.exe")

            sha1_hash = hashlib.sha1(byte_io.getvalue()).hexdigest()
            set_sql_data(conn, zip_filename, orig_checksum, sha1_hash, len(byte_io.getvalue()), connection_type)

            with open(output_zip_path + sha1_hash + "_" + connection_type, 'wb') as f:
                f.write(byte_io.getvalue())


def steam3_client_neuter(db_host, db_port, db_user, db_pass, timestamp):
    #steam_date = "2013-05-09 20:59:12"
    try:
        conn = mariadb.connect(
            user=db_user,
            password=db_pass,
            host=db_host,
            port=int(db_port),
            database="ClientConfigurationDB"
        )
    except mariadb.Error as e:
        print(f"Error connecting to MariaDB Platform: {e}")
        sys.exit(1)

    # Get Cursor
    cur = conn.cursor()
    blob_datetime = datetime.strptime(timestamp, "%Y-%m-%d %H_%M_%S")

    # Neuter zips
    client_manifest = {}
    cur.execute(f"select version from versions where datetime <= '{blob_datetime}';")
    for data in cur:
        version = str(data[0])
    cur.execute(f"select * from steam_client_win32 where version = '{version}' order by manifest_order;")
    for data in cur:
        client_manifest[data[1]] = {'file': data[1] + '.' + data[2] + '.', 'checksum': data[3], 'size': str(data[4]), 'isbootstrapperpackage': data[5], 'checksum_lan': data[7], 'checksum_wan': data[8], 'size_lan': str(data[9]), 'size_wan': str(data[10])}

    for zip_file in client_manifest:
        if "steam_win32" in zip_file or "bins_win32" in zip_file: # Neuter steam.exe / dlls
            full_zip_name = client_manifest[zip_file]["file"] + client_manifest[zip_file]["checksum"]
            new_zip_name = client_manifest[zip_file]["file"]
            input_zip_path = os.path.join(config["web_root"], "client", full_zip_name)
            output_zip_path = os.path.join(config["web_root"], "client", new_zip_name)
            with open(input_zip_path, 'rb') as f:
                input_zip = f.read()
            unzip_modify_zip(conn, input_zip_path, input_zip, output_zip_path, "lan")
            unzip_modify_zip(conn, input_zip_path, input_zip, output_zip_path, "wan")

    # Create manifest
    client_manifest = {}
    cur.execute(f"select version from versions where datetime <= '{blob_datetime}';")
    for data in cur:
        version = str(data[0])
    cur.execute(f"select * from steam_client_win32 where version = '{version}' order by manifest_order;")
    for data in cur:
        client_manifest[data[1]] = {'file': data[1] + '.' + data[2] + '.', 'checksum': data[3], 'size': str(data[4]), 'isbootstrapperpackage': data[5], 'checksum_lan': data[7], 'checksum_wan': data[8], 'size_lan': str(data[9]), 'size_wan': str(data[10])}

    preserialized_db_lan = 'lan32\x00version' + version + '\x00'
    preserialized_db_wan = 'wan32\x00version' + version + '\x00'
    for file in client_manifest:
        preserialized_db_lan += (file + "\x00")
        if client_manifest[file]["checksum_lan"]:
            preserialized_db_lan += ("file" + client_manifest[file]["file"] + client_manifest[file]["checksum_lan"] + "_lan\x00")
            preserialized_db_lan += ("checksum" + client_manifest[file]["checksum_lan"][:-4] + "\x00")
        else:
            preserialized_db_lan += ("file" + client_manifest[file]["file"] + client_manifest[file]["checksum"] + "\x00")
            preserialized_db_lan += ("checksum" + client_manifest[file]["checksum"] + "\x00")
        if client_manifest[file]["size_lan"] != "None":
            preserialized_db_lan += ("size" + client_manifest[file]["size_lan"] + "\x00")
        else:
            preserialized_db_lan += ("size" + client_manifest[file]["size"] + "\x00")
        if client_manifest[file]["isbootstrapperpackage"] == "1":
            preserialized_db_lan += ("isbootstrapperpackage1\x00")
    for file in client_manifest:
        preserialized_db_wan += (file + "\x00")
        if client_manifest[file]["checksum_wan"]:
            preserialized_db_wan += ("file" + client_manifest[file]["file"] + client_manifest[file]["checksum_wan"] + "_wan\x00")
            preserialized_db_wan += ("checksum" + client_manifest[file]["checksum_wan"][:-4] + "\x00")
        else:
            preserialized_db_wan += ("file" + client_manifest[file]["file"] + client_manifest[file]["checksum"] + "\x00")
            preserialized_db_wan += ("checksum" + client_manifest[file]["checksum"] + "\x00")
        if client_manifest[file]["size_wan"] != "None":
            preserialized_db_wan += ("size" + client_manifest[file]["size_wan"] + "\x00")
        else:
            preserialized_db_wan += ("size" + client_manifest[file]["size"] + "\x00")
        if client_manifest[file]["isbootstrapperpackage"] == "1":
            preserialized_db_wan += ("isbootstrapperpackage1\x00")
    serialized_db_lan = bytes(preserialized_db_lan.encode())
    serialized_db_wan = bytes(preserialized_db_wan.encode())

    manifest_hash_lan = SHA1.new(serialized_db_lan)
    manifest_hash_wan = SHA1.new(serialized_db_wan)
    signature_bytes_lan = pkcs1_15.new(encryption.network_key).sign(manifest_hash_lan)
    signature_bytes_wan = pkcs1_15.new(encryption.network_key).sign(manifest_hash_wan)
    kvsignature_lan = signature_bytes_lan.hex()
    kvsignature_wan = signature_bytes_wan.hex()

    manifest_info_lan = preserialized_db_lan.split("\x00")
    manifest_file_lan = '"lan32"\n{\n\t'
    manifest_file_lan += '"version"\t\t"' + version + '"'

    for entry in manifest_info_lan:
        if entry.startswith("file"):
            if ".zip" in entry:
                temp_entry = entry.replace(".zip", "")
            if ".vz" in entry:
                temp_entry = entry.replace(".zip.vz", "")
                if "_" in temp_entry:
                    temp_entry = temp_entry[:temp_entry.index("_")]
            if "." in temp_entry:
                temp_entry = temp_entry[:temp_entry.index(".")]
            manifest_file_lan += '\n\t"' + temp_entry[4:] + '"\n\t{'
            manifest_file_lan += '\n\t\t"file"\t\t"' + entry[4:] + '"'
        elif entry.startswith("checksum"):
            manifest_file_lan += '\n\t\t"checksum"\t\t"' + entry[8:] + '"'
        elif entry.startswith("size"):
            manifest_file_lan += '\n\t\t"size"\t\t"' + entry[4:] + '"'
            manifest_file_lan += '\n\t}'
        elif entry.startswith("isbootstrapperpackage"):
            manifest_file_lan = manifest_file_lan[:-3]
            manifest_file_lan += '\n\t\t"IsBootstrapperPackage"\t\t"' + entry[-1:] + '"'
            manifest_file_lan += '\n\t}'

    manifest_file_lan += "\n}"
    manifest_file_lan += '\n"kvsignatures"\n{'
    manifest_file_lan += '\n\t"lan32"\t\t"' + kvsignature_lan + '"'
    manifest_file_lan += '\n}'

    manifest_info_wan = preserialized_db_wan.split("\x00")
    manifest_file_wan = '"wan32"\n{\n\t'
    manifest_file_wan += '"version"\t\t"' + version + '"'

    for entry in manifest_info_wan:
        if entry.startswith("file"):
            if ".zip" in entry:
                temp_entry = entry.replace(".zip", "")
            if ".vz" in entry:
                temp_entry = entry.replace(".zip.vz", "")
                if "_" in temp_entry:
                    temp_entry = temp_entry[:temp_entry.index("_")]
            if "." in temp_entry:
                temp_entry = temp_entry[:temp_entry.index(".")]
            manifest_file_wan += '\n\t"' + temp_entry[4:] + '"\n\t{'
            manifest_file_wan += '\n\t\t"file"\t\t"' + entry[4:] + '"'
        elif entry.startswith("checksum"):
            manifest_file_wan += '\n\t\t"checksum"\t\t"' + entry[8:] + '"'
        elif entry.startswith("size"):
            manifest_file_wan += '\n\t\t"size"\t\t"' + entry[4:] + '"'
            manifest_file_wan += '\n\t}'
        elif entry.startswith("isbootstrapperpackage"):
            manifest_file_wan = manifest_file_wan[:-3]
            manifest_file_wan += '\n\t\t"IsBootstrapperPackage"\t\t"' + entry[-1:] + '"'
            manifest_file_wan += '\n\t}'

    manifest_file_wan += "\n}"
    manifest_file_wan += '\n"kvsignatures"\n{'
    manifest_file_wan += '\n\t"wan32"\t\t"' + kvsignature_wan + '"'
    manifest_file_wan += '\n}'

    with open(os.path.join(config["web_root"], "client", "steam_client_lan32"), 'w') as f:
        f.write(manifest_file_lan)
    with open(os.path.join(config["web_root"], "client", "steam_client_wan32"), 'w') as f:
        f.write(manifest_file_wan)