import ast
import logging
import os
import shutil
import struct
import zlib
import mariadb
import pprint
import time

from datetime import datetime, timedelta

import utils

from config import get_config
from utilities import blobs, packages
from utilities.blobs import convert_to_bytes_deep
from utilities.database import dbengine  # Import the function to create database driver

log = logging.getLogger("CCDB")

config = get_config()


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
        for separator in date_separator:
            if separator in new_date:
                datetime.strptime(new_date, f"%Y{separator}%m{separator}%d")
                steam_date = new_date.replace(separator, "-")
        for separator in time_separator:
            if separator in new_time:
                datetime.strptime(new_time, f"%H{separator}%M{separator}%S")
                steam_time = new_time.replace(separator, "_")
        timestamp = steam_date + " " + steam_time

        conn2 = mariadb.connect(
            user=config["database_username"],
            password=config["database_password"],
            host=config["database_host"],
            port=int(config["database_port"]),
            database="ContentDescriptionDB"
        )
        blob_dict = construct_blob_from_ccdb(config["database_host"], config["database_port"], config["database_username"], config["database_password"], timestamp)
        blob = blobs.blob_serialize(blob_dict)
    except:# Exception as e:
        log.warn("Client configuration creation from ClientConfigurationDB failed")
        #log.debug("DB error:", e)
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
            with open("files/firstblob.bin", "rb") as f :
                blob = f.read( )
            if blob[0:2] == b"\x01\x43" :
                blob = zlib.decompress(blob[20 :])
            firstblob_unser = blobs.blob_unserialize(blob)
            firstblob = "blob = " + blobs.blob_dump(firstblob_unser)
            blob_dict = ast.literal_eval(firstblob[7:len(firstblob)])

    current_record_ver = globalvars.record_ver

    globalvars.record_ver = struct.unpack("<L", blob_dict[b"\x00\x00\x00\x00"])[0]
    globalvars.steam_ver = struct.unpack("<L", blob_dict[b"\x01\x00\x00\x00"])[0]
    globalvars.steamui_ver = struct.unpack("<L", blob_dict[b"\x02\x00\x00\x00"])[0]

    if current_record_ver != globalvars.record_ver:
        utils.create_bootstrapper()
    elif not os.path.isfile("client/lan/Steam.exe") or not os.path.isfile("client/wan/Steam.exe"):
        utils.create_bootstrapper()
    elif not os.path.isfile("client/lan/HldsUpdateTool.exe") or not os.path.isfile("client/wan/HldsUpdateTool.exe"):
        utils.create_bootstrapper()

    log.debug("CCDB change detected, blob version is " + str(globalvars.record_ver))

    # Check if the files exist and log warning if they don't
    if globalvars.record_ver == 0:
        steam_pkg_file = f"{config['packagedir']}betav1/Steam_{globalvars.steam_ver}.pkg"
        if not os.path.exists(steam_pkg_file):
            log.warning(f"The package {steam_pkg_file} is missing.")
    elif globalvars.record_ver == 1:
        steam_pkg_file = f"{config['packagedir']}betav2/Steam_{globalvars.steam_ver}.pkg"
        steamui_pkg_file = f"{config['packagedir']}betav2/PLATFORM_{globalvars.steamui_ver}.pkg"
        if not os.path.exists(steam_pkg_file):
            log.warning(f"The package {steam_pkg_file} is missing.")
        if not os.path.exists(steamui_pkg_file):
            log.warning(f"The package {steamui_pkg_file} is missing.")
    else:
        steam_pkg_file = f"{config['packagedir']}Steam_{globalvars.steam_ver}.pkg"
        steamui_pkg_file = f"{config['packagedir']}SteamUI_{globalvars.steamui_ver}.pkg"
        if not os.path.exists(steam_pkg_file):
            log.warning(f"The package {steam_pkg_file} is missing.")
        if not os.path.exists(steamui_pkg_file):
            log.warning(f"The package {steamui_pkg_file} is missing.")

    #utils.check_secondblob_changed()
    serialized_blob = blobs.blob_serialize(blob_dict)
    if os.path.isfile("files/cache/secondblob_lan.bin.temp"):
        if not os.path.isfile("files/cache/firstblob.bin.temp"):
            with open("files/cache/firstblob.bin.temp", 'wb') as blob_file:
                blob_file.write(serialized_blob)
    else:
        if os.path.isfile("files/cache/firstblob.bin"):
            try:
                os.remove("files/cache/firstblob.bin")
            except:
                pass
        with open("files/cache/firstblob.bin", 'wb') as blob_file:
            blob_file.write(serialized_blob)

    if req_type == 'blob':
        return blob
    else:
        return serialized_blob


def load_ccdb(req_type='dict'):
    if os.path.isfile("files/cache/firstblob.bin"):
        log.info("Using cached firstblob file for client configuration")
        with open("files/cache/firstblob.bin", 'rb') as blob_file:
            blob = blob_file.read()
        if blob[0:2] == b"\x01\x43" :
            blob = zlib.decompress(blob[20 :])
        firstblob_unser = blobs.blob_unserialize(blob)
        firstblob = "blob = " + blobs.blob_dump(firstblob_unser)
        blob_dict = ast.literal_eval(firstblob[7:len(firstblob)])
        serialized_blob = blobs.blob_serialize(blob_dict)

        globalvars.record_ver = struct.unpack("<L", blob_dict[b"\x00\x00\x00\x00"])[0]
        globalvars.steam_ver = struct.unpack("<L", blob_dict[b"\x01\x00\x00\x00"])[0]
        globalvars.steamui_ver = struct.unpack("<L", blob_dict[b"\x02\x00\x00\x00"])[0]
    else:
        blob = neuter_ccdb('blob')
        serialized_blob = neuter_ccdb('dict')

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