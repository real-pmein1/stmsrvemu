import filecmp
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
import time
import traceback
from collections import Counter
from datetime import datetime, timedelta

import ipcalc
import requests
import xxhash
from future.utils import old_div
from tqdm import tqdm

import globalvars
#import utilities.database.userpy_to_db
#from utilities import auto_swap_blob
#from config import get_config as read_config, save_config_value
#from utilities import cafe_neutering, checksum_dict, neuter, packages
#from utilities.cdr_manipulator import cache_cdr
#from utilities.converter import convertgcf, ip_replacer
#from utilities.database import ccdb
#from utilities.name_suggestor import load_modifiers_from_files
#from utilities.neuter import config_replace_in_file
#from utilities.packages import Package

#config = read_config()
log = logging.getLogger('UTILS')


def to_hex_8bit(value):
    return bytes.fromhex(format(value, '02x'))


def to_hex_16bit(value):
    return bytes.fromhex(format(value, '04x'))


def to_hex_32bit(value):
    return bytes.fromhex(format(value, '08x'))


def hex_to_decimal(hex_string):
    return int(hex_string, 16)


def hex_to_string(hex_string):
    bytes_object = bytes.fromhex(hex_string)
    return bytes_object.decode("ASCII")


def hex_to_bytes(hex_string):
    return bytes.fromhex(hex_string)


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

    oldstringlist1 = (
        b'"hlmaster.valvesoftware.com:27010"', b'"half-life.east.won.net:27010"',
        b'"gridmaster.valvesoftware.com:27012"', b'"half-life.west.won.net:27010"',
        b'"207.173.177.10:27010"', b'gridmaster.valvesoftware.com:27012',
        b'hlmaster.valvesoftware.com:27010')
    oldstringlist2 = (b'"tracker.valvesoftware.com:1200"', b'"tracker.valvesoftware.com:1200"')
    oldstringlist3 = (
        b'207.173.177.10:7002', b'half-life.speakeasy-nyc.hlauth.net:27012',
        b'half-life.speakeasy-sea.hlauth.net:27012',
        b'half-life.speakeasy-chi.hlauth.net:27012')
    oldstringlist4 = (b'207.173.177.10:27010', b'207.173.177.10:27010')

    if net_type == "external":
        newstring1 = b'"' + config["public_ip"].encode('latin-1') + b':27010"'
    else:
        newstring1 = b'"' + config["server_ip"].encode('latin-1') + b':27010"'
    if net_type == "external":
        if config["tracker_ip"] != "":
            newstring2 = b'"' + config["tracker_ip"].encode('latin-1') + b':1200"'
        else:
            newstring2 = b'"' + config["public_ip"].encode('latin-1') + b':1200"'
    else:
        newstring2 = b'"' + config["server_ip"].encode('latin-1') + b':1200"'
    if net_type == "external":
        newstring3 = config["public_ip"].encode('latin-1') + b':' + config["validation_port"].encode('latin-1')
    else:
        newstring3 = config["server_ip"].encode('latin-1') + b':' + config["validation_port"].encode('latin-1')
    if net_type == "external":
        newstring4 = config["public_ip"].encode('latin-1') + b':27010'
    else:
        newstring4 = config["server_ip"].encode('latin-1') + b':27010'

    # Extract and decompress the file from the .dat file
    # with open(dat_file, 'rb') as f:
    # f.seek(dat_offset + offset)
    dat_file_handle.seek(dat_offset + offset)
    decompressed_data = dat_file_handle.read(length)
    for oldstring1 in oldstringlist1:
        if oldstring1 in decompressed_data:
            stringlen_diff1 = len(oldstring1) - len(newstring1)
            replacestring1 = newstring1 + (b"\x00" * stringlen_diff1)
            decompressed_data = decompressed_data.replace(oldstring1, replacestring1)
    for oldstring2 in oldstringlist2:
        if oldstring2 in decompressed_data:
            stringlen_diff2 = len(oldstring2) - len(newstring2)
            replacestring2 = newstring2 + (b"\x00" * stringlen_diff2)
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


def get_current_datetime():
    # Get the current datetime object
    current_datetime = datetime.now()
    # Format the datetime object as "mm/dd/yyyy hr:mn:sec"
    formatted_datetime = current_datetime.strftime("%m/%d/%Y %H:%M:%S")
    return formatted_datetime


def add_100yrs(dt_str):
    # Check if the date string is empty or invalid
    if not dt_str or dt_str == b'\xe0' * 7 + b'\x00':
        # Return the current datetime plus 100 years
        return (datetime.now() + timedelta(days=365 * 100)).strftime("%m/%d/%Y %H:%M:%S")

    try:
        date_format = "%m/%d/%Y %H:%M:%S"
        if isinstance(dt_str, bytes):
            datetime_object = datetime.strptime(dt_str.decode('latin-1').rstrip('\x00'), date_format)
        else:
            datetime_object = datetime.strptime(dt_str.rstrip('\x00'), date_format)
        newdatetime = datetime_object + timedelta(days=365 * 100)
        return newdatetime.strftime(date_format)
    except ValueError:
        # Handle invalid date format
        return (datetime.now() + timedelta(days=365 * 100)).strftime("%m/%d/%Y %H:%M:%S")


def get_current_datetime_blob():
    # Get the current datetime object
    current_datetime = datetime.now()
    # Format the datetime object as "mm/dd/yyyy hr:mn:sec"
    formatted_datetime = current_datetime.strftime("%Y-%m-%d %H_%M_%S")
    return formatted_datetime


def sub_yrs(dt_str = get_current_datetime_blob(), years = 0, months = 0, days = 0):
    try:
        date_format = "%Y-%m-%d %H_%M_%S"
        if isinstance(dt_str, bytes):
            datetime_object = datetime.strptime(dt_str.decode('latin-1').rstrip('\x00'), date_format)
        else:
            datetime_object = datetime.strptime(dt_str.rstrip('\x00'), date_format)
        newdatetime = datetime_object + timedelta(days=365.25 * years)
        if months != 0:
            newdatetime += timedelta(days=(365.25 / 12) * months)
        if days != 0:
            newdatetime += timedelta(days=days)
        return newdatetime.strftime(date_format)
    except ValueError:
        # Handle invalid date format
        # Return the current datetime
        return (datetime.now()).strftime("%Y-%m-%d %H_%M_%S")


def every(delay, task):
  next_time = time.time() + delay
  while True:
    time.sleep(max(0, next_time - time.time()))
    try:
      task()
    except Exception:
      traceback.print_exc()
      # in production code you might want to have this instead of course:
      # logger.exception("Problem while executing repetitive task.")
    # skip tasks if we are behind schedule:
    next_time += (time.time() - next_time) // delay * delay + delay



def steamtime_to_datetime(raw_bytes):
    steam_time = struct.unpack("<Q", raw_bytes)[0]
    unix_time = old_div(steam_time, 1000000) - 62135596800
    dt_object = datetime.utcfromtimestamp(unix_time)
    formatted_datetime = dt_object.strftime('%m/%d/%Y %H:%M:%S')
    return formatted_datetime


def datetime_to_steamtime(formatted_datetime):
    dt_object = datetime.strptime(formatted_datetime, '%m/%d/%Y %H:%M:%S')
    unix_time = int((dt_object - datetime(1970, 1, 1)).total_seconds())
    steam_time = (unix_time + 62135596800) * 1000000
    byte_array = struct.pack("<Q", steam_time)

    return byte_array


def steamtime_to_unixtime(steamtime_bin):
    steamtime = struct.unpack("<Q", steamtime_bin)[0]
    unixtime = steamtime / 1000000 - 62135596800
    return unixtime


def unixtime_to_steamtime(unixtime):
    steamtime = int((unixtime + 62135596800) * 1000000)  # Ensure steamtime is an integer
    steamtime_bin = struct.pack("<Q", steamtime)
    return steamtime_bin


def get_nanoseconds_since_time0():
    before_time0 = 62135596800
    current = int(time.time())
    now = current + before_time0
    nano = 1000000
    now *= nano
    return now


def is_datetime_older_than_15_minutes(date_time_str):
    # Convert the date/time string to a datetime object
    date_time_obj = datetime.strptime(date_time_str, "%d/%m/%Y %H:%M:%S")

    # Get the current datetime
    current_time = datetime.now()

    # Calculate the datetime that is 15 minutes before the current datetime
    time_15_minutes_ago = current_time - timedelta(minutes=15)

    # Check if the date_time_obj is older than 15 minutes
    return date_time_obj < time_15_minutes_ago


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


def check_secondblob_changed():
    cache_dir = 'files/cache'
    secondblob_paths = ['files/secondblob.bin', 'files/secondblob.py']
    blobhash_path = os.path.join(cache_dir, 'blobhash')
    hash_needs_update = False

    # Check if cache files exist
    if not os.path.exists(os.path.join(cache_dir, 'secondblob_lan.bin')) or \
       not os.path.exists(os.path.join(cache_dir, 'secondblob_wan.bin')):
        hash_needs_update = True
        cache_cdr(True)
        cache_cdr(False)

    # Determine which file (bin or py) exists for hashing
    for secondblob_path in secondblob_paths:
        if os.path.exists(secondblob_path):
            # Compute hash of the existing file
            with open(secondblob_path, 'rb') as file:
                file_data = file.read()
                current_hash = hashlib.sha256(file_data).hexdigest()
            break
    else:
        print("Neither secondblob.bin nor secondblob.py exists.")
        return

    # If the hash file doesn't exist or the cache files were just created, update the hash.
    if hash_needs_update or not os.path.exists(blobhash_path):
        with open(blobhash_path, 'wb') as file:
            file.write(current_hash.encode('utf-8'))

        if os.path.isfile("files/tools/neuter.exe") and globalvars.record_ver > 1:
            neuter1 = subprocess.Popen("start files/tools/neuter.exe load app ,8", shell=True)
            neuter1.wait()
        return  # Exit after updating to avoid redundant cache_cdr calls

    # Check hash and update if necessary
    with open(blobhash_path, 'rb') as file:
        saved_hash = file.read().decode('utf-8')

    if saved_hash != current_hash:
        with open(blobhash_path, 'wb') as file:
            file.write(current_hash.encode('utf-8'))
        cache_cdr(True)
        cache_cdr(False)
        print("Record ver = " + str(globalvars.record_ver))

        if os.path.isfile("files/tools/neuter.exe") and globalvars.record_ver > 1:
            neuter1 = subprocess.Popen("start files/tools/neuter.exe load app ,8", shell=True)
            neuter1.wait()


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
    if config["emu_auto_update"].lower() == "true":
        arguments = sys.argv[0]

        if arguments.endswith("emulator.exe"):
            try:
                if os.path.isfile("emulatorTmp.exe"):
                    os.remove("emulatorTmp.exe")
                if os.path.isfile("emulatorNew.exe"):
                    os.remove("emulatorNew.exe")
                # if clear_config == True:
                # print("Config change detected, flushing cache...")
                # shutil.rmtree("files/cache")
                # os.mkdir("files/cache")
                # shutil.copy("emulator.ini", "files/cache/emulator.ini.cache")
                # print
                if config["uat"] == "1":
                    url = "https://raw.githubusercontent.com/real-pmein1/stmemu-update-test/main/version"
                    # url = "https://raw.githubusercontent.com/real-pmein1/stmemu-update/main/version"
                else:
                    url = "https://raw.githubusercontent.com/real-pmein1/stmemu-update/main/version"
                resp = requests.get(url)

                line1end = resp.text.index((b'\n').decode("UTF-8")) + 1
                line2end = resp.text[line1end:].index((b'\n').decode("UTF-8")) + 1

                online_server_ver = resp.text[:line1end - 1]
                online_serverui_ver = resp.text[line1end:line1end + line2end - 1]
                online_mdb_ver = resp.text[line1end + line2end:]

                for file in os.listdir("."):
                    if file.startswith("Server_") and file.endswith(".mst"):
                        globalvars.emu_ver = file[7:-4]
                    elif file.startswith("ServerUI_") and file.endswith(".mst"):
                        globalvars.ui_ver = file[9:-4]
                    elif file.startswith("MDB_") and file.endswith(".mst"):
                        globalvars.mdb_ver = file[4:-4]
                    elif file.endswith(".pkg") or file.endswith(".srv") or file.endswith(".out"):
                        os.remove(file)

                if online_server_ver != globalvars.emu_ver or not os.path.isfile("Server_" + online_server_ver + ".mst"):
                    shutil.copy("emulator.exe", "emulatorTmp.exe")
                    print("Server update found " + globalvars.emu_ver + " -> " + online_server_ver + ", downloading...")
                    if config["uat"] == "1":
                        url = "https://raw.githubusercontent.com/real-pmein1/stmemu-update-test/main/Server_" + online_server_ver + ".pkg"
                        # url = "https://raw.githubusercontent.com/real-pmein1/stmemu-update/main/Server_" + online_server_ver + ".pkg"
                    else:
                        url = "https://raw.githubusercontent.com/real-pmein1/stmemu-update/main/Server_" + online_server_ver + ".pkg"
                    # Streaming, so we can iterate over the response.
                    response = requests.get(url, stream = True)
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
                        if (file.startswith("Server") or file.startswith("MDB_")) and file.endswith(".mst"):
                            if file.startswith("Server_") and file != "Server_" + online_server_ver + ".mst":
                                os.remove(file)
                        elif file.endswith(".out"):
                            os.remove(file)
                        elif file.endswith(".pkg"):
                            os.remove(file)
                        elif file.endswith(".mst"):
                            os.remove(file)
                    subprocess.Popen("emulatorTmp.exe")
                    sys.exit(0)
                
                if not online_serverui_ver == globalvars.ui_ver or not os.path.isfile("ServerUI_" + online_serverui_ver + ".mst"):
                    print("UI update found " + globalvars.ui_ver + " -> " + online_serverui_ver + ", downloading...")
                    if config["uat"] == "1":
                        url = "https://raw.githubusercontent.com/real-pmein1/stmemu-update-test/main/ServerUI_" + online_serverui_ver + ".pkg"
                        # url = "https://raw.githubusercontent.com/real-pmein1/stmemu-update/main/ServerUI_" + online_serverui_ver + ".pkg"
                    else:
                        url = "https://raw.githubusercontent.com/real-pmein1/stmemu-update/main/ServerUI_" + online_serverui_ver + ".pkg"
                    response = requests.get(url, stream = True)
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
                        if (file.startswith("Server") or file.startswith("MDB_")) and file.endswith(".mst"):
                            if file.startswith("ServerUI_") and file != "ServerUI_" + online_serverui_ver + ".mst":
                                os.remove(file)
                        elif file.endswith(".out"):
                            os.remove(file)
                        elif file.endswith(".pkg"):
                            os.remove(file)
                        elif file.endswith(".mst"):
                            os.remove(file)
                
                if not online_mdb_ver == globalvars.mdb_ver or not os.path.isfile("MDB_" + online_mdb_ver + ".mst"):
                    print("DB update found " + globalvars.mdb_ver + " -> " + online_mdb_ver + ", downloading...")
                    if config["uat"] == "1":
                        url = "https://raw.githubusercontent.com/real-pmein1/stmemu-update-test/main/MDB_" + online_mdb_ver + ".pkg"
                        # url = "https://raw.githubusercontent.com/real-pmein1/stmemu-update/main/MDB_" + online_mdb_ver + ".pkg"
                    else:
                        url = "https://raw.githubusercontent.com/real-pmein1/stmemu-update/main/MDB_" + online_mdb_ver + ".pkg"
                    response = requests.get(url, stream = True)
                    total_size_in_bytes = int(response.headers.get('content-length', 0))
                    block_size = 1024  # 1 Kilobyte
                    progress_bar = tqdm(total = total_size_in_bytes, unit = 'iB', unit_scale = True, ncols = 80, file=sys.stdout)
                    with open('MDB_' + online_mdb_ver + '.pkg', 'wb') as file:
                        for data in response.iter_content(block_size):
                            progress_bar.update(len(data))
                            file.write(data)
                    progress_bar.close()
                    if total_size_in_bytes != 0 and progress_bar.n != total_size_in_bytes:
                        print("ERROR, something went wrong")

                    packages.package_unpack2('MDB_' + online_mdb_ver + '.pkg', ".", online_mdb_ver, "MDB")

                    for file in os.listdir("."):
                        if (file.startswith("Server") or file.startswith("MDB_")) and file.endswith(".mst"):
                            if file.startswith("MDB_") and file != "MDB_" + online_mdb_ver + ".mst":
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
            # finally:
                # if os.path.isfile("server_0.mst"):
                    # os.remove("server_0.mst")
        elif arguments.endswith("emulatorTmp.exe") and not os.path.isfile("emulatorNew.exe"):
            print("WAITING...")
            try:

                os.remove("emulator.exe")
                shutil.copy("emulatorTmp.exe", "emulator.exe")
                subprocess.Popen("emulator.exe")
                sys.exit(0)

            except Exception as e:
                globalvars.update_exception2 = e
        else:
            print("WAITING...")
            try:
                os.remove("emulator.exe")
                shutil.copy("emulatorNew.exe", "emulator.exe")
                subprocess.Popen("emulator.exe")
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
        log.error(f"ERROR! The {ip_type} ip is malformed, currently {ip_address}")
        input("Press Enter to exit...")
        quit()


def checkip():
    check_ip_and_exit(config["server_ip"], "server")
    check_ip_and_exit(config["public_ip"], "public")
    check_ip_and_exit(config["community_ip"], "community")


def setserverip():
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
    iplen = max(len(config["server_ip"]), len(config["public_ip"]))

    # Printing the information
    print(("*" * 11) + ("*" * iplen))
    print(f"Server IP: {config['server_ip']}")
    if config["public_ip"] != "0.0.0.0":
        globalvars.public_ip = config['public_ip']
        globalvars.public_ip_b = globalvars.public_ip.encode("latin-1")
        print(f"Public IP: {globalvars.public_ip}")

    print(("*" * 11) + ("*" * iplen))
    print("")


def initialize():
    autoupdate()

    utilities.database.userpy_to_db.check_and_process_user_data()

    file_cleanup()

    if config["storage_check"].lower() == "true": # DISABLED CHECK UNTIL TESTED TO MAKE SURE NO I/O THRASHING
        log.info("--Starting Storage File Hash Check--")
        log.info("Starting Regular Storage Check")
        # check_files_checksums(checksum_dict.storage_crc_list, config["storagedir"])

        log.info("Starting V2 Storage Check")
        # check_files_checksums(checksum_dict.v2_storage_crc_list, config["v2storagedir"])
        # TODO CHECK v4 STORAGE HERE
        log.info("--Storage Hash Check Complete--")
    check_autoip_config()

    # Initial loading for ccdb for steam.exe neutering and placement.
    globalvars.firstblob_eval = ccdb.load_ccdb()

    for filename in os.listdir("files/cache/"):
        if globalvars.record_ver == 1 and "SteamUI_" in filename:
            os.remove("files/cache/" + filename)
            break
        elif globalvars.record_ver != 1 and "PLATFORM_" in filename:
            os.remove("files/cache/" + filename)
            break

    if os.path.isdir("files/cache/internal"):
        for filename in os.listdir("files/cache/internal/"):
            if globalvars.record_ver == 1 and "SteamUI_" in filename:
                os.remove("files/cache/internal/" + filename)
                break
            elif globalvars.record_ver != 1 and "PLATFORM_" in filename:
                os.remove("files/cache/internal/" + filename)
                break

    if os.path.isdir("files/cache/external"):
        for filename in os.listdir("files/cache/external/"):
            if globalvars.record_ver == 1 and "SteamUI_" in filename:
                os.remove("files/cache/external/" + filename)
                break
            elif globalvars.record_ver != 1 and "PLATFORM_" in filename:
                os.remove("files/cache/external/" + filename)
                break

    file_altered = False

    if not os.path.isfile("files/cache/emulator.ini.cache"):
        print("Config change detected, flushing cache...")
        shutil.rmtree("files/cache")
        os.mkdir("files/cache")
        shutil.copy("emulator.ini", "files/cache/emulator.ini.cache")
        print()
    else:
        try:
            with open("emulator.ini", 'r') as f:
                ini = f.readlines()
            with open("files/cache/emulator.ini.cache", 'r') as g:
                cache = g.readlines()
                
            for line1 in ini:
                if "port" in line1:
                    lineP1, lineP2 = line1.split("=")
                    for line2 in cache:
                        if lineP1 in line2:
                            if line1 != line2:
                                file_altered = True
                            break
                elif "ip" in line1:
                    lineP1, lineP2 = line1.split("=")
                    for line2 in cache:
                        if lineP1 in line2:
                            if line1 != line2:
                                file_altered = True
                            break
                
            if file_altered:
                print("Config change detected, flushing cache...")
                shutil.rmtree("files/cache")
                os.mkdir("files/cache")
                shutil.copy("emulator.ini", "files/cache/emulator.ini.cache")
                print()
        except: #FAILURE, ASSUME CACHE CORRUPTED
            print("Config change detected, flushing cache...")
            shutil.rmtree("files/cache")
            os.mkdir("files/cache")
            shutil.copy("emulator.ini", "files/cache/emulator.ini.cache")
            print()
    globalvars.server_net = ipaddress.IPv4Network(config["server_ip"] + '/' + config["server_sm"], strict = False)


def check_autoip_config():
    if config["auto_public_ip"].lower() == "true" or config["auto_server_ip"].lower() == "true":
        if config["auto_public_ip"].lower() == "true":
            globalvars.public_ip = get_external_ip()
            globalvars.public_ip_b = globalvars.public_ip.encode("latin-1")
        if config["auto_server_ip"].lower() == "true":
            globalvars.server_ip = get_internal_ip()
            globalvars.server_ip_b = globalvars.server_ip.encode("latin-1")
        setserverip()
    else:
        checkip()
        setserverip()


def finalinitialize(log):
    log.info("Caching CDDB")
    check_secondblob_changed()
    log.info("Finished Caching CDDB")
    #  modify the steam and hlsupdatetool binary files
    if globalvars.record_ver == 0:
        # beta 1 v0
        f = open(config["packagedir"] + "betav1/Steam_" + str(globalvars.steam_ver) + ".pkg", "rb")
    elif globalvars.record_ver == 1:
        f = open(config["packagedir"] + "betav2/Steam_" + str(globalvars.steam_ver) + ".pkg", "rb")
    else:
        f = open(config["packagedir"] + "Steam_" + str(globalvars.steam_ver) + ".pkg", "rb")
    pkg = Package(f.read())
    f.close()

    if config["reset_clears_client"].lower() == "true":
        shutil.rmtree("client")

    try:
        os.mkdir("client")
    except:
        pass

    try:
        os.mkdir("client/lan")
    except:
        pass

    try:
        os.mkdir("client/wan")
    except:
        pass
    try:
        file = pkg.get_file(b"SteamNew.exe")
        file2 = pkg.get_file(b"SteamNew.exe")

        file_wan = neuter.neuter_file(file, globalvars.public_ip, config["dir_server_port"], b"SteamNew.exe", False)
        file_lan = neuter.neuter_file(file2, globalvars.server_ip, config["dir_server_port"], b"SteamNew.exe", True)

        with open("client/wan/Steam.exe", "wb") as f:
            f.write(file_wan)
        with open("client/lan/Steam.exe", "wb") as g:
            g.write(file_lan)

        if globalvars.record_ver != 0 and config["hldsupkg"] != "":
            if globalvars.record_ver == 1:
                g = open(config["packagedir"] + "betav2/" + config["hldsupkg"], "rb")
            else:
                g = open(config["packagedir"] + config["hldsupkg"], "rb")
            pkg = Package(g.read())
            g.close()

            file = pkg.get_file(b"HldsUpdateToolNew.exe")
            file_wan = neuter.neuter_file(file, config["public_ip"], config["dir_server_port"], b"HldsUpdateToolNew.exe", False)
            file_lan = neuter.neuter_file(file, config["server_ip"], config["dir_server_port"], b"HldsUpdateToolNew.exe", True)

            with open("client/wan/HldsUpdateTool.exe", "wb") as f:
                f.write(file_wan)
            with open("client/lan/HldsUpdateTool.exe", "wb") as g:
                g.write(file_lan)
    except:
        log.error("Steam Client Unwriteable!")
        pass
    # TODO NEED TO DEPRECATE THIS IN FAVOR OF PROTOCOL VERSIONING
    if globalvars.steamui_ver < 61:  # guessing steamui version when steam client interface v2 changed to v3
        globalvars.tgt_version = "1"
    else:
        globalvars.tgt_version = "2"  # config file states 2 as default

    if globalvars.steamui_ver < 122:
        if os.path.isfile("files/cafe/Steam.dll"):
            log.info("Cafe files found")
            cafe_neutering.process_cafe_files(
                    "files/cafe/Steam.dll",
                    "files/cafe/CASpackage.zip",
                    "client/cafe_server/CASpackageWAN.zip",
                    "client/cafe_server/CASpackageLAN.zip",
                    "files/cafe/README.txt",
                    "client/Steam.exe",
                    config
            )

    if config["use_sdk"].lower == "true" and config["sdk_ip"] != "0.0.0.0" and config["use_sdk_as_cs"].lower == "false":
        with open(config["pkgadddir"] + "steam/Steam.cfg", "w") as h:
            h.write('SdkContentServerAdrs = "' + config["sdk_ip"] + ':' + config["sdk_port"] + '"\n')
        if os.path.isfile("files/cache/Steam_" + str(globalvars.steam_ver) + ".pkg"):
            os.remove("files/cache/Steam_" + str(globalvars.steam_ver) + ".pkg")
    else:
        if os.path.isfile(config["pkgadddir"] + "steam/Steam.cfg"):
            try:
                os.remove("files/cache/Steam_" + str(globalvars.steam_ver) + ".pkg")
            except:
                pass
            os.remove(config["pkgadddir"] + "steam/Steam.cfg")

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
    # if os.path.isfile("submanager.exe"):
    #    os.remove("submanager.exe")

    if os.path.isfile("files/users.txt"):
        users = {}  # REMOVE LEGACY USERS
        f = open("files/users.txt")
        for line in f.readlines():
            if line[-1:] == "\n":
                line = line[:-1]
            if line.find(":") != -1:
                (user, password) = line.split(":")
                users[user] = user
        f.close()
        for user in users:
            if os.path.isfile("files/users/" + user + ".py"):
                os.rename("files/users/" + user + ".py", "files/users/" + user + ".legacy")
        os.rename("files/users.txt", "files/users.off")


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
    try:
        # Check if there is a peer password, if not it'll generate one
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


def flush_cache():
    try:
        mod_date_emu = os.path.getmtime("emulator.exe")
    except:
        mod_date_emu = 0
    try:
        mod_date_cach = os.path.getmtime("files/cache/emulator.ini.cache")
    except:
        mod_date_cach = 0

    if (mod_date_cach < mod_date_emu) and globalvars.clear_config is True:
        print("Config change detected, flushing cache...")
        try:
            shutil.rmtree("files/cache")
        except:
            pass


def parent_initializer():
    log.info("---Starting Initialization---")

    globalvars.cs_region = config["server_region"].upper()
    globalvars.dir_ismaster = config["dir_ismaster"].lower()
    globalvars.use_file_blobs = config["use_file_blobs"].lower()
    globalvars.smtp_enable = config['smtp_enabled'].lower()
    globalvars.force_email_verification = config['force_email_verification'].lower()

    initialize()

    # IP Address variables must be set after initializer() incase user wants to use auto_ip and leave the server_ip or public_ip blank
    globalvars.server_ip = config["server_ip"]
    globalvars.server_ip_b = globalvars.server_ip.encode("latin-1")
    globalvars.public_ip = config["public_ip"]
    globalvars.public_ip_b = globalvars.public_ip.encode("latin-1")

    if not globalvars.update_exception1 == "":
        log.debug("Update1 error: " + str(globalvars.update_exception1))
    if not globalvars.update_exception2 == "":
        log.debug("Update2 error: " + str(globalvars.update_exception2))

    finalinitialize(log)


    log.info(f"Loading Suggested Names Modifiers from file and adding to default list")
    load_modifiers_from_files()
    log.info("---Initialization Complete---")
    print()

    # check for a peer_password, otherwise generate one
    return check_peerpassword()


def get_location(ip_address):
    # If the IP is a LAN IP then we grab the servers external IP, we assume the client and server both use the same external IP and we get the location information for the email!
    if str(ip_address) in ipcalc.Network(str(globalvars.server_net)):
        ip_address = get_external_ip(locationcheck = True)

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
    """Kills the MariaDB process identified by pid."""
    if os.name == 'nt':  # Windows
        subprocess.call(['taskkill', '/F', '/T', '/PID', str(pid)])
    else:  # Unix/Linux
        os.kill(pid, signal.SIGTERM)


def generate_secure_password(length=16):
    # Use only letters and digits, excluding symbols
    alphabet = string.ascii_letters + string.digits
    password = ''.join(secrets.choice(alphabet) for i in range(length))
    return password


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