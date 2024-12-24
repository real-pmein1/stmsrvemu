import ast
import binascii
import copy
import logging
import os
import pprint
import shutil
import struct
import zlib
import time

import mariadb
import xml.etree.ElementTree as ET

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from tzlocal import get_localzone

import globalvars
import utilities.blobs
from config import read_config
from utilities import blobs, encryption
from utilities.contentdescriptionrecord import ContentDescriptionRecord

config = read_config()
log = logging.getLogger('CDDB')


def read_blob(islan, is2003 = False):
    if islan and is2003:
        with open("files/cache/secondblob_lan_2003.bin", "rb") as f:
            blob = f.read()
    elif is2003:
        with open("files/cache/secondblob_wan_2003.bin", "rb") as f:
            blob = f.read()
    elif islan:
        with open("files/cache/secondblob_lan.bin", "rb") as f:
            blob = f.read()
    else:
        with open("files/cache/secondblob_wan.bin", "rb") as f:
            blob = f.read()
    return blob

def cache_cdr(islan):
    neuter_type = "LAN" if islan else "WAN"
    time.sleep(1)
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
        log.info(f"Creating {neuter_type} cached blob from ContentDescriptionDB...")
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

        conn2 = mariadb.connect(
            user=config["database_username"],
            password=config["database_password"],
            host=config["database_host"],
            port=int(config["database_port"]),
            database="ContentDescriptionDB"
        )

        file = construct_blob_from_cddb(config["database_host"], config["database_port"], config["database_username"], config["database_password"], timestamp, "files/cache/")
    except:# Exception as e:
        log.warn("Cached blob creation from ContentDescriptionDB failed")
        #log.debug("DB error:", e)
        log.info(f"Converting binary {neuter_type} CDDB blob file to cache...")

        if os.path.isfile("files/2ndcdr.py") or os.path.isfile("files/secondblob.py"):
            if os.path.isfile("files/2ndcdr.orig"):
                os.remove("files/2ndcdr.py")
                shutil.copy2("files/2ndcdr.orig", "files/secondblob.py")
                os.remove("files/2ndcdr.orig")
            if os.path.isfile("files/2ndcdr.py"):
                shutil.copy2("files/2ndcdr.py", "files/secondblob.py")
                os.remove("files/2ndcdr.py")
            with open("files/secondblob.py", "r") as g:
                file = g.read()
        else:
            if os.path.isfile("files/secondblob.orig"):
                os.remove("files/secondblob.bin")
                shutil.copy2("files/secondblob.orig", "files/secondblob.bin")
                os.remove("files/secondblob.orig")
            if not os.path.isfile("files/secondblob.bin"):
                log.warn("secondblob not found, waiting for file...")
                while True:
                    time.sleep(1)
                    if os.path.isfile("files/secondblob.bin"):
                        break
            with open("files/secondblob.bin", "rb") as g:
                blob = g.read()
            try:
                blob2 = blobs.blob_unserialize(blob)
                file = "blob = " + pprint.saferepr(blob2)
            except Exception as e:
                print(f"{e}")

    file = blobs.blob_replace(file, globalvars.replace_string_cdr(islan))
    execdict = {}
    #execdict_2003 = {}
    exec(file, execdict)
    #exec(file, execdict_2003)

    remove_de_restrictions(execdict)
    neuter_unlock_times(execdict)
    if globalvars.config['disable_steam3_purchasing'].lower() == 'true':
        disable_steam3_purchasing(execdict)

    integrate_customs_files(execdict, islan)

    # Optimize blob_serialize function
    blob = optimized_blob_serialize(execdict["blob"])

    if blob.startswith(b"\x01\x43"):
        blob = zlib.decompress(blob[20:])

    # Optimize the replacement loop
    blob = bytearray(blob)
    search_pattern = b"\x30\x81\x9d\x30\x0d\x06\x09\x2a"
    replacement = encryption.BERstring  # Ensure this is 160 bytes
    pattern_length = 160

    start = 0
    while True:
        index = blob.find(search_pattern, start)
        if index == -1:
            break
        blob[index:index + pattern_length] = replacement
        start = index + pattern_length

    blob = bytes(blob)

    #start_search = 0
    #while True:
    #    found = blob_2003.find(b"\x30\x81\x9d\x30\x0d\x06\x09\x2a", start_search)
    #    if found < 0:
    #        break

    #    foundstring = blob_2003[found:found + 160]
    #    blob_2003 = blob_2003.replace(foundstring, encryption.BERstring)
    #    start_search = found + 160

    compressed_blob = zlib.compress(blob, 9)
    blob = b"\x01\x43" + struct.pack("<QQH", len(compressed_blob) + 20, len(blob), 9) + compressed_blob

    #compressed_blob_2003 = zlib.compress(blob_2003, 9)
    #blob_2003 = b"\x01\x43" + struct.pack("<QQH", len(compressed_blob_2003) + 20, len(blob_2003), 9) + compressed_blob_2003

    if islan:
        with open("files/cache/secondblob_lan.bin.temp", "wb") as f:
            f.write(blob)
        #with open("files/cache/secondblob_lan_2003.bin", "wb") as f:
        #    f.write(blob_2003)
    else:
        with open("files/cache/secondblob_wan.bin.temp", "wb") as f:
            f.write(blob)
        #with open("files/cache/secondblob_wan_2003.bin", "wb") as f:
        #    f.write(blob_2003)
    log.info(f"CDDB neutering for {neuter_type} complete")

    return execdict["blob"]


def optimized_blob_serialize(blobdict):
    # Use shallow copy instead of deepcopy if possible

    subtext_list = []

    for name, data in blobdict.items():
        if name == b"__slack__":
            continue

        # Ensure name is a bytes object
        name_bytes = name.encode('ascii') if isinstance(name, str) else name

        if isinstance(data, dict):
            data = optimized_blob_serialize(data)

        # Ensure data is in bytes format
        if isinstance(data, str):
            data = data.encode('ascii')

        namesize = len(name_bytes)
        datasize = len(data)

        subtext = struct.pack("<HL", namesize, datasize) + name_bytes + data
        subtext_list.append(subtext)

    blobtext = b''.join(subtext_list)

    slack = blobdict.get(b"__slack__", b"")

    totalsize = len(blobtext) + 10
    sizetext = struct.pack("<LL", totalsize, len(slack))
    blobtext = b'\x01\x50' + sizetext + blobtext + slack
    return blobtext


def remove_de_restrictions(execdict):
    for sub_id_main in execdict["blob"][b"\x02\x00\x00\x00"]:

        if b"\x17\x00\x00\x00" in execdict["blob"][b"\x02\x00\x00\x00"][sub_id_main]:
            sub_key = execdict["blob"][b"\x02\x00\x00\x00"][sub_id_main][b"\x17\x00\x00\x00"]
            # print(sub_key)
            if b"AllowPurchaseFromRestrictedCountries" in sub_key:
                sub_key.pop(b"AllowPurchaseFromRestrictedCountries")  # print(sub_key)
            if b"PurchaseRestrictedCountries" in sub_key:
                sub_key.pop(b"PurchaseRestrictedCountries")  # print(sub_key)
            if b"RestrictedCountries" in sub_key:
                sub_key.pop(b"RestrictedCountries")  # print(sub_key)
            if b"OnlyAllowRestrictedCountries" in sub_key:
                sub_key.pop(b"OnlyAllowRestrictedCountries")  # print(sub_key)
            if b"onlyallowrunincountries" in sub_key:
                sub_key.pop(b"onlyallowrunincountries")
                # print(sub_key)
            if len(sub_key) == 0:
                execdict["blob"][b"\x02\x00\x00\x00"][sub_id_main].pop(b"\x17\x00\x00\x00")
    try:
        for sig in execdict["blob"][b"\x05\x00\x00\x00"]:  # replaces the old signature search, completes in less than 1 second now
            value = execdict["blob"][b"\x05\x00\x00\x00"][sig]
            # print(value)
            if len(value) == 160 and value.startswith(binascii.a2b_hex("30819d300d06092a")):
                execdict["blob"][b"\x05\x00\x00\x00"][sig] = encryption.BERstring
    except:
        pass


def neuter_unlock_times(execdict):
    if config["alter_preload_unlocks"].lower() == "true":
        log.info("Altering preload unlock dates")
        for app in execdict["blob"][b'\x01\x00\x00\x00']:
            if b'\x0e\x00\x00\x00' in execdict["blob"][b'\x01\x00\x00\x00'][app]:
                for info in execdict["blob"][b'\x01\x00\x00\x00'][app][b'\x0e\x00\x00\x00']:
                    if info == 'PreloadCountdownTextTime':
                        if b'days' in execdict["blob"][b'\x01\x00\x00\x00'][app][b'\x0e\x00\x00\x00'][info]:
                            preload_count = int(execdict["blob"][b'\x01\x00\x00\x00'][app][b'\x0e\x00\x00\x00'][info].decode()[:-6])
                    else:
                        preload_count = 5
                    if info == 'PreloadUnlockTime':
                        unlock_time = execdict["blob"][b'\x01\x00\x00\x00'][app][b'\x0e\x00\x00\x00'][info].decode()[:-1]
                        if ":" in unlock_time:
                            current_datetime = datetime.now()
                            new_datetime = current_datetime + timedelta(days=preload_count)
                            new_datetime = new_datetime.strftime("%Y:%m:%d:%H:%M").replace(":0", ":")
                        else:
                            current_datetime = int(datetime.now().timestamp())
                            new_datetime = current_datetime + (((preload_count * 24) * 60) * 60)
                        execdict["blob"][b'\x01\x00\x00\x00'][app][b'\x0e\x00\x00\x00'][info] = str(new_datetime).encode() + b'\x00'


def remove_keys_recursively(data_dict, target_keys):
    """Recursively remove specified keys from all levels of nested dictionaries."""
    keys_list = list(data_dict.keys())  # Get list of keys to avoid runtime modification issues
    for key in keys_list:
        if key in target_keys:
            # If key needs to be removed, it is removed here
            log.debug(f"Removing key: {key}")  # Debug print statement
            data_dict.pop(key, None)
        elif isinstance(data_dict[key], dict):
            # If the value is another dictionary, recurse into it
            #print(f"Descending into dictionary at key: {key}")  # Debug print statement
            remove_keys_recursively(data_dict[key], target_keys)
            # After recursion, check if the subdictionary is empty and remove if so


def disable_steam3_purchasing(execdict):
    """Disables Steam3 purchasing until the CM supports it. Some users may just want to use Steam2 anyway."""
    log.info("Disabling Steam3 Purchasing")

    target_keys = [
            # b"convar_bClientAllowHardwarePromos",
            # b"convar_bClientAllowPurchaseWizard",
            b"convar_bClientAllowSteam3ActivationCodes",
            b"convar_bClientAllowSteam3CCPurchase",
            b"convar_bClientCCPurchaseFallbackToSteam2",
            b"convar_bClientMakeAllCCPurchasesSteam3"
    ]

    # Call the recursive function to remove keys
    remove_keys_recursively(execdict, target_keys)

def update_subscription_id_in_xml(xml_file_path, old_id, new_id):
    if not os.path.exists(xml_file_path):
        log.warning(f"XML file '{xml_file_path}' not found.")
        return

    try:
        tree = ET.parse(xml_file_path)
        root = tree.getroot()
        old_id_str = str(old_id)
        new_id_str = str(new_id)

        # Replace <SubscriptionRecord SubscriptionId="{old_id_str}">
        for elem in root.iter('SubscriptionRecord'):
            if elem.get('SubscriptionId') == old_id_str:
                elem.set('SubscriptionId', new_id_str)

        # Replace <SubscriptionId>{old_id_str}</SubscriptionId>
        for elem in root.iter('SubscriptionId'):
            if elem.text == old_id_str:
                elem.text = new_id_str

        # Write the updated XML back to file
        tree.write(xml_file_path, encoding='utf-8', xml_declaration=True)
        log.info(f"Updated XML file '{xml_file_path}' with new subscription ID.")
    except ET.ParseError as e:
        log.warning(f"Error parsing XML file: {e}")


def integrate_customs_files(execdict, islan):
    from tkinter import messagebox
    import tkinter as tk
    execdict_temp_01 = {}
    execdict_temp_02 = {}
    # Initialize tkinter root for messagebox
    root = tk.Tk()
    root.withdraw()  # Hide the root window as we only need the messagebox

    for file in os.walk("files/mod_blob"):
        for customblobfile in file[2]:
            if (
                customblobfile.endswith((".py", ".bin", ".xml"))
                and customblobfile not in ["2ndcdr.py", "1stcdr.py"]
                and not customblobfile.startswith(("firstblob", "secondblob"))
            ):
                log.info("Found extra blob: " + customblobfile)
                execdict_update = {}

                if customblobfile.endswith(".bin"):
                    with open("files/mod_blob/" + customblobfile, "rb") as f:
                        blob = f.read()

                    if blob[0:2] == b"\x01\x43":
                        blob = zlib.decompress(blob[20:])
                    blob2 = blobs.blob_unserialize(blob)
                    blob3 = pprint.saferepr(blob2)
                    execdict_update = "blob = " + blob3

                    log.info("Integrating Custom Applications (bin)")
                    execdict_update = blobs.blob_replace(execdict_update, globalvars.replace_string_cdr(islan))

                elif customblobfile.endswith(".py"):
                    with open("files/mod_blob/" + customblobfile, 'r') as m:
                        userblobstr_upd = m.read()
                    log.info("Integrating Custom Applications (py)")
                    userblobstr_upd = blobs.blob_replace(userblobstr_upd, globalvars.replace_string_cdr(islan))
                    execdict_update = ast.literal_eval(userblobstr_upd[7:])

                elif customblobfile.endswith(".xml"):
                    contentdescriptionrecord_file = ContentDescriptionRecord.from_xml_file("files/mod_blob/" + customblobfile)
                    execdict_update = contentdescriptionrecord_file.to_dict(True)
                else:
                    return  # Fail gracefully if an unknown file is encountered

                execdict_update = utilities.blobs.convert_to_bytes_deep(execdict_update)

                # Integrate execdict_update into execdict["blob"]
                for k in execdict_update:
                    if k in execdict["blob"]:
                        # Existing key in execdict["blob"], need to handle duplicates
                        main_dict = execdict["blob"][k]

                        if k in [b"\x01\x00\x00\x00", b"\x02\x00\x00\x00"] and customblobfile.endswith(".xml"):  # Application or Subscription Records
                            # Get the set of existing keys as integers
                            main_keys_int = set(int.from_bytes(key, 'little') for key in main_dict.keys())
                            max_key = 30000  # Start from -1 if empty

                            # Prepare new entries to merge
                            new_entries = {}

                            for key, subdict in execdict_update[k].items():
                                if key in main_dict:
                                    # Key exists; generate a new unique key
                                    max_key += 1
                                    new_key_int = max_key
                                    new_key = new_key_int.to_bytes(4, 'little')
                                    # Get the subscription name from the subdictionary (b"\x02\x00\x00\x00")
                                    subscription_name = subdict.get(b"\x02\x00\x00\x00", b"").decode('latin-1').strip('\x00')

                                    # TODO Should probably do the same for applicationid's and update the publickey ids as well
                                    # Trigger message box to notify ID change, including subscription name
                                    old_key_int = int().from_bytes(key, 'little')
                                    new_key_int = int().from_bytes(new_key, 'little')
                                    messagebox.showinfo(
                                            "ID Changed",
                                            f"Subscription ID for key {old_key_int} has been changed to {new_key_int}.\nSubscription name: {subscription_name}"
                                    )

                                    # Update the b"\x01\x00\x00\x00" key in the subdictionary
                                    subdict[b"\x01\x00\x00\x00"] = new_key

                                    # Add the subdictionary with the new key to new_entries
                                    new_entries[new_key] = subdict

                                    # **Update the XML file with the new subscription ID**
                                    update_subscription_id_in_xml("files/mod_blob/" + customblobfile, old_key_int, new_key_int)
                                else:
                                    # Key does not exist; add it directly
                                    new_entries[key] = subdict

                            # Merge new entries into the main dictionary
                            main_dict.update(new_entries)
                            execdict["blob"][k] = main_dict
                        else:
                            # For other keys, update directly
                            execdict["blob"][k].update(execdict_update[k])
                    else:
                        # Key does not exist in execdict["blob"], add it directly
                        execdict["blob"][k] = execdict_update[k]


def get_db_version(db_host, db_port, db_user, db_pass):
    try:
        conn2 = mariadb.connect(
            user=db_user,
            password=db_pass,
            host=db_host,
            port=int(db_port),
            database="ContentDescriptionDB"

        )
        cur = conn2.cursor()
    
        cur.execute("select @@version as version;")
        for version in cur:
            log.debug("Found MariaDB version " + str(version[0]))
            return version[0]
    except mariadb.Error as e:
        log.error(f"Error connecting to MariaDB Platform: {e}")
        return

def construct_blob_from_cddb(db_host, db_port, db_user, db_pass, timestamp, working_dir):
    try:
        conn2 = mariadb.connect(
            user=db_user,
            password=db_pass,
            host=db_host,
            port=int(db_port),
            database="ContentDescriptionDB"

        )
    except mariadb.Error as e:
        log.error(f"Error connecting to MariaDB Platform: {e}")
        return
    conn2.autocommit = True

    cur = conn2.cursor()
    cur2 = conn2.cursor()
    cur3 = conn2.cursor()
    cur4 = conn2.cursor()
    cur.execute("SET time_zone = '+00:00'")
    cur2.execute("SET time_zone = '+00:00'")
    cur3.execute("SET time_zone = '+00:00'")
    cur4.execute("SET time_zone = '+00:00'")
    blob_dict = {}

    ##############  START  ##############
    #BLOB VERSION
    #print(f"SELECT version FROM blob_version FOR SYSTEM_TIME AS OF TIMESTAMP'{timestamp}'")
    cur.execute(f"SELECT version FROM blob_version FOR SYSTEM_TIME AS OF TIMESTAMP'{timestamp}'")
    for data in cur:
        blob_dict[b'\x00\x00\x00\x00'] = struct.pack('<H', data[0])

    #APPLICATIONS
    blob_dict[b'\x01\x00\x00\x00'] = {}

    # Fetch applications
    app_query = f"SELECT * FROM applications FOR SYSTEM_TIME AS OF TIMESTAMP '{timestamp}'"
    ext_info_query = f"SELECT * FROM apps_ext_info FOR SYSTEM_TIME AS OF TIMESTAMP'{timestamp}'"
    cur.execute(app_query)
    applications = cur.fetchall()

    # Organize applications data
    app_data = {}
    for row in applications:
        app_id = struct.pack('<i', row[0])
        app_data[app_id] = {
            b'\x01\x00\x00\x00': struct.pack('<i', row[1]), #alt_app_id
            b'\x02\x00\x00\x00': bytes(row[2], 'UTF-8') + b'\x00', #app_name
            b'\x03\x00\x00\x00': bytes(row[3], 'UTF-8') + b'\x00', #inst_dir
            b'\x04\x00\x00\x00': struct.pack('<i', row[4]), #min_size
            b'\x05\x00\x00\x00': struct.pack('<i', row[5]), #max_size
            b'\x06\x00\x00\x00': {}, #launch_options
            b'\x07\x00\x00\x00': {}, #empty
            b'\x08\x00\x00\x00': struct.pack('<i', row[6]), #on_first_launch
            b'\x09\x00\x00\x00': struct.pack('<B', row[7]), #app_bandwidth_greedy
            b'\x0a\x00\x00\x00': {}, #versions
            b'\x0b\x00\x00\x00': struct.pack('<i', row[8]), #current_ver
            b'\x0c\x00\x00\x00': {}, #depots
            b'\x0d\x00\x00\x00': struct.pack('<i', row[9]) #trickle_ver
        }
        if row[17] != None: app_data[app_id][b'\x0e\x00\x00\x00'] = {}
        if row[10] != None: app_data[app_id][b'\x0f\x00\x00\x00'] = bytes(row[10], 'UTF-8') + b'\x00'
        if row[11] != None: app_data[app_id][b'\x10\x00\x00\x00'] = struct.pack('<i', row[11])
        if row[12] != None: app_data[app_id][b'\x11\x00\x00\x00'] = bytes(row[12], 'UTF-8') + b'\x00'
        if row[13] != None: app_data[app_id][b'\x12\x00\x00\x00'] = struct.pack('<B', row[13])
        if row[14] != None: app_data[app_id][b'\x13\x00\x00\x00'] = struct.pack('<B', row[14])
        if row[15] != None: app_data[app_id][b'\x14\x00\x00\x00'] = struct.pack('<B', row[15])
        if row[16] != None: app_data[app_id][b'\x15\x00\x00\x00'] = struct.pack('<i', row[16])
        if row[18] != None: app_data[app_id][b'\x16\x00\x00\x00'] = {} #country_ext_info

    # Fetch launch options
    launch_query = f"SELECT * FROM apps_launch FOR SYSTEM_TIME AS OF TIMESTAMP '{timestamp}'"
    cur.execute(launch_query)
    launch_options = cur.fetchall()
    for row in launch_options:
        app_id = struct.pack('<i', row[0])
        launch_id = struct.pack('<i', row[1])
        if app_id in app_data:
            app_data[app_id][b'\x06\x00\x00\x00'][launch_id] = {
                b'\x01\x00\x00\x00': bytes(row[2], 'UTF-8') + b'\x00',
                b'\x02\x00\x00\x00': bytes(row[3], 'UTF-8') + b'\x00',
                b'\x03\x00\x00\x00': struct.pack('<i', row[4]),
                b'\x04\x00\x00\x00': struct.pack('<B', row[5]),
                b'\x05\x00\x00\x00': struct.pack('<B', row[6]),
                b'\x06\x00\x00\x00': struct.pack('<B', row[7]),
            }
            if row[8] != None: app_data[app_id][b'\x06\x00\x00\x00'][launch_id][b'\x07\x00\x00\x00'] = bytes(row[8], 'UTF-8') + b'\x00'

    # Fetch versions
    version_query = f"SELECT * FROM apps_versions FOR SYSTEM_TIME AS OF TIMESTAMP '{timestamp}' ORDER BY app_id, order_id"
    key_query = f"SELECT * FROM encryption_keys FOR SYSTEM_TIME AS OF TIMESTAMP '{timestamp}' ORDER BY app_id, key_id"
    launch_query = f"SELECT * FROM apps_launch_ids FOR SYSTEM_TIME AS OF TIMESTAMP '{timestamp}' ORDER BY app_id, order_id"
    cur.execute(version_query)
    versions = cur.fetchall()
    cur.execute(key_query)
    keys = cur.fetchall()
    keys_dict = {(row[0], row[2]): row[1] for row in keys}
    cur.execute(launch_query)
    launch_ids = cur.fetchall()
    launch_ids_dict = defaultdict(list)
    for row in launch_ids:
        launch_ids_dict[(row[0], row[1])].append(row[3])
    for row in versions:
        app_id = struct.pack('<i', row[0])
        order_id = struct.pack('<i', row[8])
        key = keys_dict.get((row[0], row[9]), None)
        launch_id_app = launch_ids_dict.get((row[0], row[8]), None)
        if app_id in app_data:
            launch_data = {}
            if launch_id_app != None:
                for launch_id in launch_id_app:
                    launch_data[struct.pack('<i', launch_id)] = b''
            version_data = {
                b'\x01\x00\x00\x00': bytes(row[1], 'UTF-8') + b'\x00',
                b'\x02\x00\x00\x00': struct.pack('<i', row[2]),
                b'\x03\x00\x00\x00': struct.pack('<B', row[3]),
                b'\x04\x00\x00\x00': launch_data,
                b'\x05\x00\x00\x00': b'\x00',
                b'\x06\x00\x00\x00': struct.pack('<B', row[4]),
                b'\x07\x00\x00\x00': struct.pack('<B', row[5])
            }
            if key != None: version_data[b'\x05\x00\x00\x00'] = bytes(key, 'UTF-8') + b'\x00'
            if row[6] != None: version_data[b'\x08\x00\x00\x00'] = struct.pack('<B', row[6])
            if row[7] != None: version_data[b"__slack__"] = b'\x00' * row[7]
            app_data[app_id][b'\x0a\x00\x00\x00'][order_id] = version_data

    # Fetch depots
    depot_query = f"SELECT * FROM apps_depots FOR SYSTEM_TIME AS OF TIMESTAMP '{timestamp}'"
    cur.execute(depot_query)
    depots = cur.fetchall()
    for row in depots:
        app_id = struct.pack('<i', row[0])
        depot_order = struct.pack('<i', row[4])
        if app_id in app_data:
            app_data[app_id][b'\x0c\x00\x00\x00'][depot_order] = {
                b'\x01\x00\x00\x00': struct.pack('<i', row[1]),
                b'\x02\x00\x00\x00': bytes(row[2], 'UTF-8') + b'\x00' if row[2] else b'\x00',
                b'\x03\x00\x00\x00': struct.pack('<B', row[3])
            }
            if row[5]: app_data[app_id][b'\x0c\x00\x00\x00'][depot_order][b'\x04\x00\x00\x00'] = bytes(row[5], 'UTF-8') + b'\x00'

    # Fetch extensions info
    ext_info_query = f"SELECT * FROM apps_ext_info FOR SYSTEM_TIME AS OF TIMESTAMP '{timestamp}'"
    cur.execute(ext_info_query)
    ext_infos = cur.fetchall()
    for row in ext_infos:
        app_id = struct.pack('<i', row[0])
        info_name = row[1]
        if app_id in app_data:
            app_data[app_id][b'\x0e\x00\x00\x00'][info_name] = bytes(row[2], 'UTF-8') + b'\x00'

    # Fetch country-specific info
    country_ext_info_query = f"SELECT * FROM apps_country_ext_info FOR SYSTEM_TIME AS OF TIMESTAMP '{timestamp}'"
    cur.execute(country_ext_info_query)
    country_ext_infos = cur.fetchall()
    country_ext_infos_dict = defaultdict(list)
    for row in country_ext_infos:
        country_ext_infos_dict[(row[0], row[1])].append((row[3], row[4]))
    for row in country_ext_infos:
        app_id = struct.pack('<i', row[1])
        order_id = struct.pack('<i', row[0])
        country_ext_infos_id_app = country_ext_infos_dict.get((row[0], row[1]), None)
        if b'\x16\x00\x00\x00' in app_data[app_id]:
            if app_id in app_data:
                country_ext_infos_data = {}
                if country_ext_infos_id_app != None:
                    for country_ext_infos_id in country_ext_infos_id_app:
                        country_ext_infos_data[country_ext_infos_id[0]] = (bytes(country_ext_infos_id[1], 'UTF-8')  + b'\x00')
                app_data[app_id][b'\x16\x00\x00\x00'][order_id] = {
                    b'\x01\x00\x00\x00': bytes(row[2], 'UTF-8') + b'\x00',
                    b'\x02\x00\x00\x00': country_ext_infos_data
                }

    # Copy data to blob_dict
    for app_id, data in app_data.items():
        blob_dict[b'\x01\x00\x00\x00'][app_id] = data

    #SUBSCRIPTIONS
    cur.execute(f"SELECT * FROM subscriptions FOR SYSTEM_TIME AS OF TIMESTAMP'{timestamp}'")
    cur2.execute(f"SELECT * FROM subs_discount FOR SYSTEM_TIME AS OF TIMESTAMP'{timestamp}'")
    cur3.execute(f"SELECT * FROM subs_qualifiers FOR SYSTEM_TIME AS OF TIMESTAMP'{timestamp}'")
    cur4.execute(f"SELECT * FROM subs_ext_info FOR SYSTEM_TIME AS OF TIMESTAMP'{timestamp}' ORDER BY sub_id")

    packed_values_cache = {}

    def get_packed_value(fmt, value):
        if (fmt, value) not in packed_values_cache:
            packed_values_cache[(fmt, value)] = struct.pack(fmt, value)
        return packed_values_cache[(fmt, value)]

    blob_dict[b'\x02\x00\x00\x00'] = {}

    sub_ext_infos = cur4.fetchall()
    sub_ext_infos_dict = defaultdict(list)
    for row in sub_ext_infos:
        sub_ext_infos_dict[(row[0])].append((row[1], row[2]))

    sub_discounts = cur2.fetchall()
    sub_discount_dict = defaultdict(list)
    for row in sub_discounts:
        sub_discount_dict[(row[1])].append((row[0], row[2], row[3]))

    sub_disc_qualifiers = cur3.fetchall()
    sub_disc_qualifiers_dict = defaultdict(list)
    for row in sub_disc_qualifiers:
        sub_disc_qualifiers_dict[(row[2])].append((row[0], row[1], row[3], row[4]))

    # Process the subscriptions
    subs_list = []
    for data in cur:
        sub_id = get_packed_value('<i', data[0])
        subs_list.append(data[0])

        sub_data = blob_dict[b'\x02\x00\x00\x00'][sub_id] = {}
        sub_data[b'\x01\x00\x00\x00'] = get_packed_value('<i', data[1])
        sub_data[b'\x02\x00\x00\x00'] = bytes(data[2], 'UTF-8') + b'\x00'
        sub_data[b'\x03\x00\x00\x00'] = get_packed_value('<H', data[3])
        sub_data[b'\x04\x00\x00\x00'] = get_packed_value('<i', data[4])
        sub_data[b'\x06\x00\x00\x00'] = {}
        sub_data[b'\x07\x00\x00\x00'] = get_packed_value('<i', data[6])
        sub_data[b'\x08\x00\x00\x00'] = get_packed_value('<i', data[7])
        if data[8] != None: sub_data[b'\x0b\x00\x00\x00'] = get_packed_value('<B', data[8])
        if data[9] != None: sub_data[b'\x0c\x00\x00\x00'] = get_packed_value('<B', data[9])
        if data[10] != None: sub_data[b'\x0d\x00\x00\x00'] = get_packed_value('<i', data[10])
        if data[11] != None: sub_data[b'\x0e\x00\x00\x00'] = get_packed_value('<i', data[11])
        if data[12] != None: sub_data[b'\x0f\x00\x00\x00'] = get_packed_value('<i', data[12])
        if data[13] != None: sub_data[b'\x10\x00\x00\x00'] = get_packed_value('<B', data[13])
        if data[14] != None: sub_data[b'\x11\x00\x00\x00'] = get_packed_value('<i', data[14])
        if data[15] != None: sub_data[b'\x12\x00\x00\x00'] = bytes(data[15], 'UTF-8') + b'\x00'
        if data[16] != None: sub_data[b'\x13\x00\x00\x00'] = get_packed_value('<B', data[16])
        if data[17] != None: sub_data[b'\x14\x00\x00\x00'] = get_packed_value('<B', data[17])
        if data[18] != None: sub_data[b'\x15\x00\x00\x00'] = get_packed_value('<i', data[18])
        if data[19] != None: sub_data[b'\x16\x00\x00\x00'] = get_packed_value('<B', data[19])
        if data[20] != None: sub_data[b'\x17\x00\x00\x00'] = {}

        # Process sub_appids
        if data[5]:
            sub_appids = data[5].split(',')
            sub_apps_dict = sub_data[b'\x06\x00\x00\x00']
            for app in sub_appids:
                app_id = get_packed_value('<i', int(app))
                sub_apps_dict[app_id] = b''

        # Fetch discount data for this subscription
        discounts = sub_discount_dict.get(str(data[0]), [])
        qualifiers = sub_disc_qualifiers_dict.get(str(data[0]), [])
        for discount in discounts:
            order_id = get_packed_value('<i', discount[0])
            discount_name = bytes(discount[1], 'UTF-8') + b'\x00'
            discount_price = get_packed_value('<i', discount[2])

            for qualifier in qualifiers:
                qualifier_dict = {
                    get_packed_value('<i', qualifier[1]): {
                        b'\x01\x00\x00\x00': bytes(qualifier[2], 'UTF-8') + b'\x00',
                        b'\x02\x00\x00\x00': get_packed_value('<i', qualifier[3])
                    }
                }

            discount_data = sub_data.setdefault(b'\x0a\x00\x00\x00', {})
            discount_data[order_id] = {
                b'\x01\x00\x00\x00': discount_name,
                b'\x02\x00\x00\x00': discount_price,
                b'\x03\x00\x00\x00': qualifier_dict
            }

    for row in sub_ext_infos:
        if row[0] in subs_list:
            sub_id = struct.pack('<i', row[0])
            sub_ext_infos_id_sub = sub_ext_infos_dict.get((row[0]), None)
            if b'\x17\x00\x00\x00' in blob_dict[b'\x02\x00\x00\x00'][sub_id]:
                sub_ext_infos_data = {}
                if sub_ext_infos_id_sub != None:
                    for sub_ext_infos_id in sub_ext_infos_id_sub:
                        sub_ext_infos_data[sub_ext_infos_id[0]] = (bytes(sub_ext_infos_id[1], 'UTF-8') + b'\x00')
                blob_dict[b'\x02\x00\x00\x00'][sub_id][b'\x17\x00\x00\x00'] = sub_ext_infos_data

    #BLOB_DATE
    cur.execute(f"SELECT date_time FROM blob_datetime FOR SYSTEM_TIME AS OF TIMESTAMP'{timestamp}'")
    for data in cur:
        data_temp = bytes.fromhex(data[0].replace('\\x', ''))
        blob_dict[b'\x03\x00\x00\x00'] = data_temp

    #APPS_SUBS
    blob_dict[b'\x04\x00\x00\x00'] = {}

    # Fetching max_count
    cur.execute(f"SELECT count FROM apps_count FOR SYSTEM_TIME AS OF TIMESTAMP'{timestamp}'")
    max_count = cur.fetchone()[0]

    # Fetch all relevant app_id and sub_id pairs
    cur.execute(f"""
        SELECT app_id, sub_id 
        FROM apps_subs 
        FOR SYSTEM_TIME AS OF TIMESTAMP'{timestamp}' 
        WHERE app_id BETWEEN 0 AND {max_count - 1}
    """)
    app_data = {}

    for app_id, sub_id in cur:
        if app_id not in app_data:
            app_data[app_id] = {}
        app_data[app_id][struct.pack('<i', sub_id)] = b''

    for app_id in range(max_count):
        app_id_packed = struct.pack('<i', app_id)
        blob_dict[b'\x04\x00\x00\x00'][app_id_packed] = app_data.get(app_id, {})

    #RSA_KEYS
    cur.execute(f"SELECT app_id, rsa_key FROM rsa_keys FOR SYSTEM_TIME AS OF TIMESTAMP'{timestamp}'")

    blob_dict[b'\x05\x00\x00\x00'] = {}

    hex_prefix = '\\x'

    for app_id, rsa_key_hex in cur:
        app_id_packed = struct.pack('<i', app_id)

        rsa_key = bytes.fromhex(rsa_key_hex.replace(hex_prefix, ''))

        blob_dict[b'\x05\x00\x00\x00'][app_id_packed] = rsa_key

    ##############  FINISH  ##############
    blob3 = pprint.saferepr(blob_dict)
    file = "blob = " + blob3

    ##FOR PY SAVING
    ##with open(working_dir + "output.py", 'w') as py_out: 
    ##    pprint.pprint(blob_dict, stream=py_out)

    #execdict = {}
    #exec(file, execdict)

    #blob = optimized_blob_serialize(execdict["blob"])

    ##FOR SAVING UNCOMPRESSED BLOB
    ##with open(working_dir + "output_uncomp.bin", 'wb') as bin_uncomp:
    ##    bin_uncomp.write(blob)

    #compressed_blob = zlib.compress(blob, 9)
    #blob = b"\x01\x43" + struct.pack("<QQH", len(compressed_blob) + 20, len(blob), 9) + compressed_blob

    ##FOR SAVING COMPRESSED BLOB
    ##with open(working_dir + "output_comp.bin", 'wb') as bin_comp:
    ##    bin_comp.write(blob)

    conn2.close()
    
    return file


def read_secondblob(filepath):
    with open(filepath, "rb") as f :
        blob = f.read( )
    if blob[0:2] == b"\x01\x43" :
        blob = zlib.decompress(blob[20 :])
    firstblob_unser = blobs.blob_unserialize(blob)
    firstblob = "blob = " + blobs.blob_dump(firstblob_unser)
    blob_dict = ast.literal_eval(firstblob[7:len(firstblob)])
    return blob_dict