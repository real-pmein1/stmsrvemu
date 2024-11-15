import binascii
import logging

import globalvars
from config import get_config as read_config


ips_to_replace = [
    b"207.173.177.11:27030 207.173.177.12:27030",
    b"207.173.177.11:27030 207.173.177.12:27030 69.28.151.178:27038 69.28.153.82:27038 68.142.88.34:27038 68.142.72.250:27038",
    b"72.165.61.189:27030 72.165.61.190:27030 69.28.151.178:27038 69.28.153.82:27038 68.142.88.34:27038 68.142.72.250:27038",
    b"72.165.61.189:27030 72.165.61.190:27030 69.28.151.178:27038 69.28.153.82:27038 87.248.196.194:27038 68.142.72.250:27038",
    b"127.0.0.1:27030 127.0.0.1:27030 127.0.0.1:27030 127.0.0.1:27030 127.0.0.1:27030 127.0.0.1:27030",
    b"208.64.200.189:27030 208.64.200.190:27030 208.64.200.191:27030 208.78.164.7:27038"
]
config = read_config()
log = logging.getLogger('NEUTER')

def config_replace_in_file(file, filename, replacement_strings, config_num, use_space = False):
    if isinstance(filename, str):
        filename = filename.encode("latin-1")
    for search, replace, info in replacement_strings:
        try:
            if file.find(search) != -1:
                if search == b"StorefrontURL1" and ":2004" in config["store_url"]:
                    file = file.replace(search, replace)
                    log.debug(f"{globalvars.CURRENT_APPID_VERSION}{filename.decode()}: Replaced {info.decode()}")
                    #print(filename.decode() + ": Replaced " + info.decode())
                else:
                    missing_length = len(search) - len(replace)
                    if missing_length < 0:
                        log.warning(f"{globalvars.CURRENT_APPID_VERSION}Replacement text {replace.decode()} is too long!")
                        #print("Replacement text " + replace.decode() + " is too long!")
                        pass
                    elif missing_length == 0:
                        file = file.replace(search, replace)
                        log.debug(f"{globalvars.CURRENT_APPID_VERSION}{filename.decode()}: Replaced {info.decode()}")
                        #print(filename.decode() + ": Replaced " + info.decode())
                    else:
                        padding = b'\x00' if use_space is False else b'\x20'
                        replace_padded = replace + (padding * missing_length)
                        file = file.replace(search, replace_padded)
                        log.debug(f"{globalvars.CURRENT_APPID_VERSION}{filename.decode()}: Replaced {info.decode()}")
                        #print(filename.decode() + ": Replaced " + info.decode())
        except Exception as e:
            # logging.error(f"Config {config_num} line not found: {e} {filename.decode()}")
            print("Config " + str(config_num) + " line not found: " + filename.decode())

    return file


def readchunk_neuter(chunk, islan, is2003gcf):
    if islan or config["public_ip"] == "0.0.0.0":
        fullstring1 = globalvars.replace_string(True)
        # log.debug("Using LAN replacement string.")
    else:
        fullstring1 = globalvars.replace_string(False)
        # log.debug("Using public IP replacement string.")

    chunk = config_replace_in_file(chunk, b'chunk', fullstring1, 1)

    if islan:
        fullstring2 = globalvars.replace_string_name_space(True, is2003gcf)
        fullstring3 = globalvars.replace_string_name(True, is2003gcf)
    elif config["public_ip"] != "0.0.0.0" or not islan:
        fullstring2 = globalvars.replace_string_name_space(False, is2003gcf)
        fullstring3 = globalvars.replace_string_name(False, is2003gcf)
    else:
        fullstring2 = globalvars.replace_string_name_space(False, is2003gcf)
        fullstring3 = globalvars.replace_string_name(False, is2003gcf)

    chunk = config_replace_in_file(chunk, b'chunk', fullstring2, 2, True)
    chunk = config_replace_in_file(chunk, b'chunk', fullstring3, 3)

    if islan:
        server_ip = config["server_ip"].encode('latin-1')
        # log.debug("Using server IP for LAN.")
    else:
        server_ip = config["public_ip"].encode('latin-1')
        # log.debug("Using public IP.")

    if config["csds_ipport"]:
        if ":" in config["csds_ipport"]:
            server_ip = config["csds_ipport"][:config["csds_ipport"].index(":")].encode('latin-1')

    server_port = config["dir_server_port"].encode('latin-1')

    for index, search in enumerate(ips_to_replace):
        chunk = replace_dirip_in_chunk(chunk, search, server_ip, server_port, index % 5)
       #  log.debug(f"Replaced directory IP in chunk for search pattern {index}.")

    chunk = replace_ips_in_chunk(chunk, globalvars.ip_addresses, server_ip, islan)
    # log.debug("Replaced IP addresses in chunk.")

    chunk = replace_cc_in_chunk(chunk)
    # log.debug("Replaced CC details in chunk.")

    # log.info("Completed readchunk_neuter.")
    return chunk


def replace_cc_in_chunk(chunk):
    try:
        expiration_search = binascii.a2b_hex("2245787069726174696F6E59656172436F6D626F220D0A09092278706F7322090922323632220D0A09092279706F7322090922313634220D0A09092277696465220909223636220D0A09092274616C6C220909223234220D0A0909226175746F526573697A652209092230220D0A09092270696E436F726E65722209092230220D0A09092276697369626C652209092231220D0A090922656E61626C65642209092231220D0A090922746162506F736974696F6E2209092234220D0A0909227465787448696464656E2209092230220D0A0909226564697461626C65220909223022")
        expiration_replace = binascii.a2b_hex("2245787069726174696F6E59656172436F6D626F220D0A09092278706F7322090922323632220D0A09092279706F7322090922313634220D0A09092277696465220909223636220D0A09092274616C6C220909223234220D0A0909226175746F526573697A652209092230220D0A09092270696E436F726E65722209092230220D0A09092276697369626C652209092231220D0A090922656E61626C65642209092231220D0A090922746162506F736974696F6E2209092234220D0A0909227465787448696464656E2209092230220D0A0909226564697461626C65220909223122")
        chunk = chunk.replace(expiration_search, expiration_replace)
        # log.debug("Replaced CC expiry date field in chunk.")
    except Exception as e:
        log.error(f"{globalvars.CURRENT_APPID_VERSION}Failed to replace CC expiry date in chunk: {e}")
    return chunk


def replace_dirip_in_chunk(chunk, search, server_ip, server_port, dirgroup):
    ip = (server_ip + b":" + server_port + b" ") # we only replace 1, this fixes any issues with the length being incorrect!

    searchlength = len(search)
    iplength = len(ip)
    numtoreplace = searchlength // iplength
    ips = ip * numtoreplace
    replace = ips + (b'\x00' * (searchlength - len(ips)))
    if chunk.find(search) != -1:
        chunk = chunk.replace(search, replace)
       # log.debug(f"Replaced directory IP pattern {dirgroup} in chunk.")
    return chunk


def replace_ips_in_chunk(chunk, ip_list, replacement_ip, islan):

    for ip in ip_list:
        loc = chunk.find(ip)
        if loc != -1:
            if islan:
                # For LAN, always use server_ip
                replacement_ip = config["server_ip"].encode() + (b"\x00" * (16 - len(config["server_ip"])))
                # log.debug(f"Replacing IP with server IP for LAN at location {loc}.")
            else:
                replacement_ip = config["public_ip"].encode() + (b"\x00" * (16 - len(config["public_ip"])))
                # log.debug(f"Replacing IP with server IP for WAN at location {loc}.")
            chunk = chunk[:loc] + replacement_ip + chunk[loc + 16:]
    return chunk