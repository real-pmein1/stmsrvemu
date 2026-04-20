import binascii
import logging
import os
import struct
import chardet
from datetime import datetime

import globalvars
from config import get_config as read_config
from utilities.custom_neutering import (
    do_neuter,
    parse_json,
    check_appinfo_configs_changed,
    invalidate_appinfo_cache,
    update_appinfo_config_tracking
)
from utilities.filesig_neuter import FileSignatureModifier
from utilities.packages import Package
from utilities.filesystem_utils import normalize_path
from utilities.custom_neuter_tracker import (
    save_mod_pkg_tracking,
    get_tracking_file_path,
    get_mod_pkg_files_with_crc
)


logging.getLogger('chardet').setLevel(logging.CRITICAL)


ips_to_replace = [
    b"207.173.177.11:27030 207.173.177.12:27030 69.28.151.178:27038 69.28.153.82:27038 68.142.88.34:27038 68.142.72.250:27038",
    b"207.173.177.11:27030 207.173.177.12:27030",
    b"72.165.61.189:27030 72.165.61.190:27030 69.28.151.178:27038 69.28.153.82:27038 68.142.88.34:27038 68.142.72.250:27038",
    b"72.165.61.189:27030 72.165.61.190:27030 69.28.151.178:27038 69.28.153.82:27038 87.248.196.194:27038 68.142.72.250:27038",
    b"127.0.0.1:27030 127.0.0.1:27030 127.0.0.1:27030 127.0.0.1:27030 127.0.0.1:27030 127.0.0.1:27030",
    b"208.64.200.189:27030 208.64.200.190:27030 208.64.200.191:27030 208.78.164.7:27038"
]
config = read_config()

pkgadd_filelist = []
log = logging.getLogger("neuter")


def neuter_file(file, server_ip, server_port, filename, islan, isappinfo = False):

    # file = replace_bytes_in_file(file, b"WS2_32.dll", b"WS3_32.dll", filename)
    """if isinstance(filename, str):
        filename = filename.encode("latin-1")
    if file.startswith(b"\x3C\x68\x74\x6D\x6C\x3E"):
        file_temp = binascii.b2a_hex(file)
        i = 0
        file_new = b""
        for byte_index in range(0, len(file_temp), 2):
            byte_hex = file_temp[i:i + 2]
            if byte_hex == b"00":
                byte_hex = b""
            file_new += byte_hex
            i += 2
        file = binascii.a2b_hex(file_new)"""
    if islan:
        server_ip = globalvars.server_ip
    else:
        server_ip = globalvars.public_ip

    if not isappinfo:
        # Assuming replace_in_file is a function that takes the file, filename, search pattern, server_ip, server_port, and an index
        for index, search in enumerate(ips_to_replace):
            file = replace_dirip_in_file(file, filename, search, server_ip, server_port, index % 5)

    if islan or config["public_ip"] == "0.0.0.0":
        # If islan is True and the filename is SteamNewLAN.exe, use the server IP
        fullstring1 = globalvars.replace_string(True)
    else:
        # In all other cases, use the public IP
        fullstring1 = globalvars.replace_string(False)

    file = config_replace_in_file(file, filename, fullstring1, 1)

    if islan:
        fullstring2 = globalvars.replace_string_name_space(True)
        fullstring3 = globalvars.replace_string_name(True)
    elif config["public_ip"] != "0.0.0.0" or not islan:
        fullstring2 = globalvars.replace_string_name_space(False)
        fullstring3 = globalvars.replace_string_name(False)
    else:
        fullstring2 = globalvars.replace_string_name_space(False)
        fullstring3 = globalvars.replace_string_name(False)

    file = config_replace_in_file(file, filename, fullstring2, 2, True)
    file = config_replace_in_file(file, filename, fullstring3, 3)

    file = replace_ips_in_file(file, filename, globalvars.ip_addresses, server_ip, islan)

    if not config["server_ip"] == "127.0.0.1":
        file = replace_ips_in_file(file, filename, globalvars.loopback_ips, server_ip, islan)
    return file


def neuter_file_vdf(file, server_ip, server_port, filename, islan, isappinfo = False):

    # file = replace_bytes_in_file(file, b"WS2_32.dll", b"WS3_32.dll", filename)
    """if isinstance(filename, str):
        filename = filename.encode("latin-1")
    if file.startswith(b"\x3C\x68\x74\x6D\x6C\x3E"):
        file_temp = binascii.b2a_hex(file)
        i = 0
        file_new = b""
        for byte_index in range(0, len(file_temp), 2):
            byte_hex = file_temp[i:i + 2]
            if byte_hex == b"00":
                byte_hex = b""
            file_new += byte_hex
            i += 2
        file = binascii.a2b_hex(file_new)"""
    if islan:
        server_ip = globalvars.server_ip
    else:
        server_ip = globalvars.public_ip

    if not isappinfo:
        # Assuming replace_in_file is a function that takes the file, filename, search pattern, server_ip, server_port, and an index
        for index, search in enumerate(ips_to_replace):
            file = replace_dirip_in_file(file, filename, search, server_ip, server_port, index % 5)

    #file = replace_ips_in_file(file, filename, globalvars.ip_addresses, server_ip, islan)

    #if not config["server_ip"] == "127.0.0.1":
    #    file = replace_ips_in_file(file, filename, globalvars.loopback_ips, server_ip, islan)

    if islan or config["public_ip"] == "0.0.0.0":
        # If islan is True and the filename is SteamNewLAN.exe, use the server IP
        fullstring1 = globalvars.replace_string(True)
    else:
        # In all other cases, use the public IP
        fullstring1 = globalvars.replace_string(False)

    file = config_replace_in_file_vdf(file, filename, fullstring1, 1)

    if islan:
        fullstring2 = globalvars.replace_string_name_space(True)
        fullstring3 = globalvars.replace_string_name(True)
    elif config["public_ip"] != "0.0.0.0" or not islan:
        fullstring2 = globalvars.replace_string_name_space(False)
        fullstring3 = globalvars.replace_string_name(False)
    else:
        fullstring2 = globalvars.replace_string_name_space(False)
        fullstring3 = globalvars.replace_string_name(False)

    file = config_replace_in_file_vdf(file, filename, fullstring2, 2, True)
    file = config_replace_in_file_vdf(file, filename, fullstring3, 3)

    file = replace_ips_in_file(file, filename, globalvars.ip_addresses, server_ip, islan)

    if not config["server_ip"] == "127.0.0.1":
        file = replace_ips_in_file(file, filename, globalvars.loopback_ips, server_ip, islan)
    return file


def public_res_replace_in_file(file, filename, replacement_strings):
    if isinstance(filename, str):
        filename = filename.encode("latin-1")
    result = chardet.detect(file)
    encoding = result['encoding'].lower()
    file = file.decode(encoding)
    for search, replace, info in replacement_strings:
        search = search.decode()
        replace = replace.decode()
        try:
            if file.find(search) != -1:
                file = file.replace(search, replace)
                log.debug(f"{filename.decode()}: Replaced {info.decode()}")
        except Exception as e:
            log.error(f"Resource File line not found: {e} {filename.decode()}")
    file = file.encode(encoding)
    return file


def neuter_public_file(file, filename, islan):
    if islan:
        # print(f"neuter_file: replace with lan true")
        publicneuter_str = globalvars.replace_string_resfiles(True)
    elif config["public_ip"] != "0.0.0.0" or not islan:
        # print(f"neuter_file: replace with lan false")
        publicneuter_str = globalvars.replace_string_resfiles(False)
    else:
        publicneuter_str = globalvars.replace_string_resfiles(False)

    file = public_res_replace_in_file(file, filename, publicneuter_str)
    return file


def is_text_file(filename):
    """Check if filename indicates a text-based file that should use space padding instead of null bytes."""
    if isinstance(filename, str):
        filename = filename.encode("latin-1")

    text_extensions = (b'.txt', b'.htm', b'.html', b'.css', b'.js', b'.vdf', b'.res', b'.layout',
                      b'.cfg', b'.ini', b'.inf', b'.xml')
    text_names = (b'steamui_', b'steamnew_')

    filename_lower = filename.lower()
    return (filename_lower.endswith(text_extensions) or
            any(name in filename_lower for name in text_names))

def replace_ips_in_file(file, filename, ip_list, replacement_ip, islan):
    if isinstance(filename, str):
        filename = filename.encode("latin-1")

    # Determine padding character based on file type
    use_space_padding = is_text_file(filename)
    padding_char = b"\x20" if use_space_padding else b"\x00"

    for ip in ip_list:
        loc = file.find(ip)
        if loc != -1:
            if islan:
                # For LAN, always use server_ip
                replacement_ip = config["server_ip"].encode() + (padding_char * (16 - len(config["server_ip"])))
            else:
                replacement_ip = config["public_ip"].encode() + (padding_char * (16 - len(config["public_ip"])))

            file = file[:loc] + replacement_ip + file[loc + 16:]
            log.debug(f"{filename.decode()}: Found and replaced IP {ip.decode():>16} at location {loc:08x} (padding: {'space' if use_space_padding else 'null'})")
    return file


def config_replace_in_file(file, filename, replacement_strings, config_num, use_space = False):
    if isinstance(filename, str):
        filename = filename.encode("latin-1")

    # Auto-detect text files if use_space wasn't explicitly set
    if not use_space:
        use_space = is_text_file(filename)

    for search, replace, info in replacement_strings:
        try:
            if file.find(search) != -1:
                if search == b"StorefrontURL1" and ":2004" in config["store_url"]:
                    file = file.replace(search, replace)
                    log.debug(f"{filename.decode()}: Replaced {info.decode()}")
                else:
                    missing_length = len(search) - len(replace)
                    if missing_length < 0:
                        log.warning(f"Replacement text {replace.decode()} is too long!")
                    elif missing_length == 0:
                        file = file.replace(search, replace)
                        log.debug(f"{filename.decode()}: Replaced {info.decode()}")
                    else:
                        padding = b'\x20' if use_space else b'\x00'
                        replace_padded = replace + (padding * missing_length)
                        file = file.replace(search, replace_padded)
                        log.debug(f"{filename.decode()}: Replaced {info.decode()} (padding: {'space' if use_space else 'null'})")
        except Exception as e:
            log.error(f"Config {config_num} line not found: {e} {filename.decode()}")

    return file


def config_replace_in_file_vdf(file, filename, replacement_strings, config_num, use_space = False):
    if isinstance(filename, str):
        filename = filename.encode("latin-1")

    # Auto-detect text files if use_space wasn't explicitly set
    if not use_space:
        use_space = is_text_file(filename)

    for search, replace, info in replacement_strings:
        try:
            if file.find(search) != -1:
                if search == b"StorefrontURL1" and ":2004" in config["store_url"]:
                    file = file.replace(search, replace)
                    log.debug(f"{filename.decode()}: Replaced {info.decode()}")
                else:
                    missing_length = len(search) - len(replace)
                    if missing_length < 0:
                        log.warning(f"Replacement text {replace.decode()} is too long!")
                    elif missing_length == 0:
                        file = file.replace(search, replace)
                        log.debug(f"{filename.decode()}: Replaced {info.decode()}")
                    else:
                        # VDF files should use space padding when needed
                        padding = b'\x20' if use_space else b'\x00'
                        replace_padded = replace + (padding * missing_length)
                        file = file.replace(search, replace_padded)
                        log.debug(f"{filename.decode()}: Replaced {info.decode()} (padding: {'space' if use_space else 'null'})")
        except Exception as e:
            log.error(f"Config {config_num} line not found: {e} {filename.decode()}")

    return file


def replace_dirip_in_file(file, filename, search, server_ip, server_port, dirgroup):
    if isinstance(filename, str):
        filename = filename.encode("latin-1")

    # Determine padding character based on file type
    use_space_padding = is_text_file(filename)
    padding_char = b"\x20" if use_space_padding else b"\x00"

    ip = (server_ip + ":" + server_port + " ").encode() # we only replace 1, this fixes any issues with the length being incorrect!

    searchlength = len(search)
    iplength = len(ip)
    numtoreplace = searchlength // iplength
    ips = ip * numtoreplace
    replace = ips + (padding_char * (searchlength - len(ips)))
    if file.find(search) != -1:
        file = file.replace(search, replace)
        log.debug(f"{filename.decode()}: Replaced directory server IP group {dirgroup} (padding: {'space' if use_space_padding else 'null'})")
    return file


def get_filenames():
    if config["enable_steam3_servers"] == "true":
        return (b"HldsUpdateToolNew.exe", b"SteamNew.exe", b"Steam.dll", b"SteamUI.dll", b"platform.dll", b"steam\\SteamUIConfig.vdf", b"steam\\SubPanelWelcomeCreateNewAccount.res",
        b"GameOverlayRenderer.dll", b"GameOverlayUI.exe", b"steam\\SteamUI.dll", b"friends\\servers.vdf", b"servers\\MasterServers.vdf", b"servers\\ServerBrowser.dll",
        b"bin\\ServerBrowser.dll", b"caserver.exe", b"cacdll.dll", b"CASClient.exe", b"unicows.dll", b"GameUI.dll", b"steamclient.dll", b"steamclient64.dll",
        b"friendsUI.dll", b"bin\\friendsUI.dll", b"bin\\p2pcore.dll", b"bin\\steamservice.dll", b"bin\\steamservice.exe", b"bin\\FileSystem_Steam.dll",
        b"bin\\gameoverlayui.dll", b"bin\\x64launcher.exe", b"bin\\vgui.dll", b"bin\\nattypeprobe.dll", b"crashhandler.dll", b"CSERHelper.dll", b"GameOverlayRenderer64.dll",
        b"steamerrorreporter.exe", b"tier0_s.dll", b"tier0_s64.dll", b"vstdlib_s.dll", b"vstdlib_s64.dll", b"resource\\layout\\steamrootdialog.layout")
    else:
        return (b"HldsUpdateToolNew.exe", b"SteamNew.exe", b"Steam.dll", b"SteamUI.dll", b"platform.dll", b"steam\\SteamUIConfig.vdf", b"steam\\SubPanelWelcomeCreateNewAccount.res",
        b"steam\\SteamUI.dll", b"friends\\servers.vdf", b"servers\\MasterServers.vdf", b"servers\\ServerBrowser.dll", b" valvesoftware\\privacy.htm", b"caserver.exe",
        b"cacdll.dll", b"CASClient.exe", b"unicows.dll", b"GameUI.dll")


def create_steam_config_file():
    # Define the file path
    file_path = os.path.join("files", "mod_pkg", "steam", "global", "Steam.cfg")

    # Create directories if they don't exist
    os.makedirs(os.path.dirname(file_path), exist_ok = True)
    sdk_cs_ip_port = config["sdk_ip"] + ':' + config["sdk_port"]
    # Define the file contents
    file_contents = f"""#
    # *********** (C) Copyright 2008 Valve, L.L.C. All rights reserved. ***********
    #
    # Steam Client SDK configuration-override file
    #
    # This file is read by the Steam engine.  This file should be located
    # in the same folder as steam.exe
    #

    #
    # Use this value to specify the dot-notation IP address or hostname
    # of the Steam Content Server for development/test.
    # Use "127.0.0.1" to specify the primary NIC of current host.
    #
    # If you need to run multiple content servers, you can specify
    # multiple addresses on this line separated by a space character
    # (e.g. "11.22.33.44 11.22.33.45")
    #
    SdkContentServerAdrs = {sdk_cs_ip_port}

    #
    # Enable the manifest fingerprint check at cache startup.
    # In general, this should always be enabled if your client is connecting
    # to an SDK content server.
    #
    ManifestFingerprintCheck = enable


    #
    # Tell Steam to only connect to your local CS when downloading
    #
    CacheServerSessions = 1
    """

    with open(file_path, 'w') as h:
        h.write(file_contents)


def neuter(pkg_in, pkg_out, server_ip, server_port, islan):
    version_id = pkg_in.split('_')[-1].split('.')[0]  # Extract version id from package filename

    f = open(pkg_in, "rb")
    pkg = Package(f.read())
    f.close()

    # SDK and mod_pkg operations first
    if config["use_sdk"].lower() == "true" and config["sdk_ip"] != "0.0.0.0" and config["sdk_ip"] != "" and config["use_sdk_as_cs"].lower() == "false":
        create_steam_config_file()
        cache_pkg = os.path.join("files", "cache", f"Steam_{globalvars.steam_ver}.pkg")
        if os.path.isfile(cache_pkg):
            os.remove(cache_pkg)
    else:
        steam_cfg = os.path.join("files", "mod_pkg", "steam", "global", "Steam.cfg")
        if os.path.isfile(steam_cfg):
            cache_pkg = os.path.join("files", "cache", f"Steam_{globalvars.steam_ver}.pkg")
            try:
                os.remove(cache_pkg)
            except Exception:
                pass
            os.remove(steam_cfg)

    # Determine pkg type for tracking BEFORE any modifications
    pkg_type_for_tracking = 'steamui' if ('SteamUI_' in pkg_in or 'PLATFORM_' in pkg_in) else 'steam'

    # Capture CRCs of mod_pkg files BEFORE any neutering/modifications
    # This ensures we hash the original files, not neutered versions
    pre_neuter_mod_pkg_crcs = {}
    try:
        pre_neuter_mod_pkg_crcs = get_mod_pkg_files_with_crc(pkg_type_for_tracking, int(version_id))
    except Exception as e:
        log.warning(f"Failed to pre-compute mod_pkg CRCs: {e}")

    if os.path.isdir("files/mod_pkg"):
        log.debug("Found mod_pkg folder")
        if os.path.isdir("files/mod_pkg/steamui/") and ("SteamUI_" in pkg_in):
            log.debug("Found steamui folder")
            base_path = os.path.join("files", "mod_pkg", "steamui")
            mod_pkg(base_path, pkg, version_id, "SteamUI")
        elif os.path.isdir(os.path.join("files", "mod_pkg", "steam")) and ("Steam_" in pkg_in):
            log.debug("Found steam folder")
            base_path = os.path.join("files", "mod_pkg", "steam")
            mod_pkg(base_path, pkg, version_id, "Steam")

    # Custom File neutering and modifications
    specified_filenames = get_filenames()
    allowed_extensions   = (b'.txt', b'.htm', b'.html', b'.res')
    neuter_type          = 'pkgsteamui' if "SteamUI_" in pkg_in else 'pkgsteam'
    parsedjson = parse_json(neuter_type, version_id)
    if parsedjson is not None:
        custom_tags, custom_repls = parsedjson
        # apply *all* JSON-driven rules in one go (per-file filtering now in do_neuter)
        for fname in pkg.filenames:
            data = pkg.get_file(fname)
            data = do_neuter(custom_tags, data, fname, custom_repls, islan)
            pkg.put_file(fname, data)

    # Your existing hardcoded loops
    for filename in pkg.filenames:
        # Process files in the Public/ folder with neuter_public_file()
        if isinstance(filename, str):
            filename = filename.encode()

        if (filename.startswith(b"Public")
            or filename.startswith(b"resource")
            or filename.startswith(b"steam")) \
           and filename.lower().endswith(allowed_extensions):
            file = pkg.get_file(filename)
            file = neuter_public_file(file, filename, islan)
            pkg.put_file(filename, file)

        # Process only the files that are in the specified_filenames list with neuter_file()
        elif filename in specified_filenames:
            file = pkg.get_file(filename)
            file = neuter_file(file, server_ip, server_port, filename, islan)
            if filename.lower().endswith((b'.dll', b'.exe')):
                modifier = FileSignatureModifier(file)
                file = modifier.modify_file()
            pkg.put_file(filename, file)

    # Capture the list of added files before clearing
    added_files_snapshot = list(pkgadd_filelist) if pkgadd_filelist else []

    if len(pkgadd_filelist) > 0:
        del pkgadd_filelist[:]

    # Write the modified package to the output file
    with open(pkg_out, "wb") as f:
        f.write(pkg.pack())

    # Save tracking data with CRCs of files added from mod_pkg
    # Uses pre-computed CRCs from BEFORE neutering to ensure we track original file hashes
    pkg_type, pkg_version = get_tracking_file_path(pkg_out)
    if pkg_type:
        tracking_data = {}
        if added_files_snapshot and pre_neuter_mod_pkg_crcs:
            for rel_path in added_files_snapshot:
                # Normalize path separators
                normalized = rel_path.replace('\\', '/')
                if normalized in pre_neuter_mod_pkg_crcs:
                    _, crc = pre_neuter_mod_pkg_crcs[normalized]
                    tracking_data[normalized] = crc
        save_mod_pkg_tracking(pkg_type, pkg_version, tracking_data)



def mod_pkg(base_path, pkg, version_id, folder_type):
    """
    Modifies a package by adding files from global, range, and version-specific directories.

    :param base_path: Base path where the directories are located.
    :param pkg: Package object to which files will be added.
    :param version_id: The version ID being processed.
    :param folder_type: The type of folder being processed (e.g., "steamui").
    """
    global_dir = os.path.join(base_path, "global/")
    version_specific_dir = os.path.join(base_path, str(version_id))

    # Ensure version_id is treated as an integer for proper comparison
    try:
        version_id = int(version_id)
    except ValueError:
        log.error(f"Invalid version ID: {version_id}")
        return

    # Process global directory first
    if os.path.isdir(global_dir):
        recursive_pkg(global_dir, global_dir)
    else:
        log.debug(f"No global directory found at {global_dir}.")

    # Handle version range directories
    matching_range_dirs = []
    version_range_dirs = [
        d for d in os.listdir(base_path)
        if os.path.isdir(os.path.join(base_path, d)) and '-' in d
    ]

    for range_dir in version_range_dirs:
        try:
            start, end = map(int, range_dir.split('-'))
            if start <= version_id <= end:
                matching_range_dirs.append(os.path.join(base_path, range_dir))
        except ValueError:
            log.error(f"Invalid range folder name: {range_dir}")

    # Process all matching range directories
    if matching_range_dirs:
        for range_dir_path in matching_range_dirs:
            recursive_pkg(range_dir_path, range_dir_path)
    else:
        log.debug(f"No matching range directories found for version {version_id}.")

    # Process version-specific directory last
    if os.path.isdir(version_specific_dir):
        recursive_pkg(version_specific_dir, version_specific_dir)
    else:
        log.debug(f"No version-specific directory found for version {version_id} at {version_specific_dir}.")

    # Add files to the package
    log.debug(f"Number of files to add to {folder_type} {version_id} PKG: {str(len(pkgadd_filelist))}")
    for relative_path in pkgadd_filelist:
        corrected_path = None

        # Check if the file exists in the global directory first
        global_path = os.path.join(global_dir, relative_path)
        if os.path.exists(global_path):
            corrected_path = global_path
        else:
            # Check range directories for the file
            for range_dir_path in matching_range_dirs:
                range_path = os.path.join(range_dir_path, relative_path)
                if os.path.exists(range_path):
                    corrected_path = range_path
                    break

            # Finally check the version-specific directory
            if not corrected_path:
                version_specific_path = os.path.join(version_specific_dir, relative_path)
                if os.path.exists(version_specific_path):
                    corrected_path = version_specific_path

        # If a file was found, add it to the package
        if corrected_path:
            try:
                with open(corrected_path, "rb") as file2:
                    filedata = file2.read()
                pkg.put_file(relative_path, filedata)
            except Exception as e:
                log.error(f"Failed to add file {relative_path} from {corrected_path}: {e}")
        else:
            log.error(f"File not found in global, range, or version-specific directories: {relative_path}")


def recursive_pkg(dir_in, path_to_remove):
    global pkgadd_filelist
    files = os.listdir(dir_in)
    for filename in files:
        full_path = os.path.join(dir_in, filename)
        if os.path.isfile(full_path):
            # Calculate relative path with respect to the base path to remove
            relative_path = os.path.relpath(full_path, path_to_remove)
            pkgadd_filelist.append(relative_path)
        elif os.path.isdir(full_path):
            recursive_pkg(full_path, path_to_remove)


def find_closest_appinfo_dated_subfolder(base_path, target_date):
    """
    Finds the subfolder with the closest match to the target_date.
    Subfolder names follow the format MM-DD-YYYY_hh-mm.
    """
    closest_folder = None
    closest_time_diff = float('inf')

    for folder_name in os.listdir(base_path):
        try:
            folder_date = datetime.strptime(folder_name, "%Y-%m-%d_%H-%M")
            time_diff = abs((folder_date - target_date).total_seconds())  # target_date is now datetime
            if time_diff < closest_time_diff:
                closest_folder = folder_name
                closest_time_diff = time_diff
        except ValueError:
            # Skip folders that don't match the naming scheme
            continue

    return closest_folder


def process_appinfo_files(input_source, output_path, islan):
    """
    Processes either:
      ? ALL .vdf files in a directory (input_source is a str path), or
      ? A specific list of files (input_source is a list of (_, file_path) tuples).

    Applies your existing neutering logic and then patches
    the 4-byte changeid at 0x0C?0x0F *only* for v2 files, where
    v2 is detected by the input path being under
      files/appcache/2009_2010
    and the changeid is deterministically generated from
    the output folder?s name.
    """
    from utilities.appinfo_utils import create_4byte_id_from_date
    os.makedirs(output_path, exist_ok=True)


    # build a flat list of file paths
    if isinstance(input_source, str):
        file_paths = [
            os.path.join(input_source, fn)
            for fn in os.listdir(input_source)
            if fn.lower().endswith(".vdf")
        ]
    else:
        file_paths = [fp for (_, fp) in input_source]

    # path indicator for v2 files
    v2_prefix = os.path.normpath(os.path.join("files", "appcache", "2009_2010"))

    for file_path in file_paths:
        file_name = os.path.basename(file_path)

        with open(file_path, "rb") as f:
            raw = f.read()

        # --- your existing custom neutering ---
        # Extract appid from filename format: app_<appid>.vdf or appinfo_<appid>.vdf
        base_name = file_name.rsplit('.', 1)[0]  # Remove .vdf extension
        if base_name.startswith("app_"):
            appid = base_name[4:]  # "app_220" -> "220"
        elif base_name.startswith("appinfo_"):
            appid = base_name[8:]  # "appinfo_220" -> "220"
        else:
            appid = base_name  # Fallback for other formats
        parsedjason = parse_json("appinfo", appid)
        if parsedjason:
            custom_tags, replacements = parsedjason
            if replacements:
                raw = do_neuter(custom_tags, raw, file_name, replacements, islan)

        # --- built-in VDF neuter ---
        web_ip   = globalvars.get_octal_ip(islan)
        neutered = neuter_file_vdf(
            raw,
            web_ip,
            "80",
            file_name.encode('latin-1'),
            islan
        )

        # --- patch the 4-byte changeid for v2 files only ---
        norm_path = os.path.normpath(file_path)
        if v2_prefix in norm_path:
            current_cdr_date = datetime.strptime(globalvars.CDDB_datetime, "%m/%d/%Y %H:%M:%S")
            current_changeid = create_4byte_id_from_date(current_cdr_date)
            neutered = neutered[:0x0C] + current_changeid + neutered[0x10:]
        # --- write out ---
        out_file = os.path.join(output_path, file_name)
        with open(out_file, "wb") as f:
            f.write(neutered)


def check_appinfo_cache():
    """
    Checks CDR date ranges and ensures the appropriate appinfo VDFs
    have been neutered into files/cache/appinfo/.../lan & /wan.

    Also checks if appinfo neuter configs have changed since last run,
    and invalidates the cache if so to force re-neutering with new configs.
    """
    from utilities.appinfo_utils import find_source_appid_files_2008, find_source_appid_files_2009
    current = datetime.strptime(globalvars.CDDB_datetime, "%m/%d/%Y %H:%M:%S")

    # Check if appinfo neuter configs have changed - if so, invalidate cache
    configs_changed = check_appinfo_configs_changed()
    if configs_changed:
        invalidate_appinfo_cache()

    # Track whether any processing was done (to update config hash at end)
    processing_done = False

    # 2008
    if datetime(2008, 3, 1) <= current < datetime(2009, 1, 1):
        base_in  = normalize_path("files/appcache/2008/")
        lan_out  = normalize_path("files/cache/appinfo/2008/", "lan/")
        wan_out  = normalize_path("files/cache/appinfo/2008/", "wan/")

        # Get list of source files that should exist
        file_list = find_source_appid_files_2008(base_in)
        if not file_list:
            log.debug("No source appinfo files found for 2008.")
        else:
            # Create directories if they don't exist
            os.makedirs(lan_out, exist_ok=True)
            os.makedirs(wan_out, exist_ok=True)

            # Process full folder if completely empty
            lan_empty = not os.path.exists(lan_out) or not any(os.scandir(lan_out))
            wan_empty = not os.path.exists(wan_out) or not any(os.scandir(wan_out))

            if lan_empty:
                log.debug("LAN folder for 2008 is empty, neutering appinfo files...")
                process_appinfo_files(base_in, lan_out, True)
                processing_done = True
            if wan_empty:
                log.debug("WAN folder for 2008 is empty, neutering appinfo files...")
                process_appinfo_files(base_in, wan_out, False)
                processing_done = True

            # Process any individually missing files (like 2009 does)
            missing_lan = [
                fp for _, fp in file_list
                if not os.path.exists(os.path.join(lan_out, os.path.basename(fp)))
            ]
            missing_wan = [
                fp for _, fp in file_list
                if not os.path.exists(os.path.join(wan_out, os.path.basename(fp)))
            ]
            if missing_lan:
                log.debug(f"Some LAN appinfo files missing for 2008 ({len(missing_lan)} files); neutering just those...")
                process_appinfo_files([(None, fp) for fp in missing_lan], lan_out, True)
                processing_done = True
            if missing_wan:
                log.debug(f"Some WAN appinfo files missing for 2008 ({len(missing_wan)} files); neutering just those...")
                process_appinfo_files([(None, fp) for fp in missing_wan], wan_out, False)
                processing_done = True

    # 2009?2010
    elif datetime(2009, 1, 1) <= current <= datetime(2010, 4, 26, 17, 58, 53):
        base_in  = normalize_path("files/appcache/2009_2010/")
        cache    = normalize_path("files/cache/appinfo/2009_2010/")
        lan_out  = normalize_path(cache, "lan/")
        wan_out  = normalize_path(cache, "wan/")

        file_list = find_source_appid_files_2009(globalvars.CDDB_datetime, base_in)
        folder    = find_closest_appinfo_dated_subfolder(base_in, current)
        if not folder:
            log.error("No matching 2009_2010 subfolder found.")
            return

        lan_path = normalize_path(lan_out, folder)
        wan_path = normalize_path(wan_out, folder)

        # process full folder if missing
        if not os.path.exists(lan_path):
            log.debug(f"LAN folder '{folder}' neutering appinfo?")
            process_appinfo_files(file_list, lan_path, True)
            processing_done = True
        if not os.path.exists(wan_path):
            log.debug(f"WAN folder '{folder}' neutering appinfo?")
            process_appinfo_files(file_list, wan_path, False)
            processing_done = True

        # process any individually missing files
        missing_lan = [
            fp for _, fp in file_list
            if not os.path.exists(os.path.join(lan_path, os.path.basename(fp)))
        ]
        missing_wan = [
            fp for _, fp in file_list
            if not os.path.exists(os.path.join(wan_path, os.path.basename(fp)))
        ]
        if missing_lan:
            log.debug("Some LAN appinfo files missing; neutering just those?")
            process_appinfo_files([(None, fp) for fp in missing_lan], lan_path, True)
            processing_done = True
        if missing_wan:
            log.debug("Some WAN appinfo files missing; neutering just those?")
            process_appinfo_files([(None, fp) for fp in missing_wan], wan_path, False)
            processing_done = True

    # 2010?2011
    elif datetime(2010, 4, 26, 17, 58, 54) <= current <= datetime(2011, 7, 12, 20, 7, 3):
        base_in = normalize_path("files/appcache/2010_2011/")
        lan_out = normalize_path("files/cache/appinfo/2010_2011/", "lan/")
        wan_out = normalize_path("files/cache/appinfo/2010_2011/", "wan/")

        lan_exists = os.path.exists(lan_out) and any(os.scandir(lan_out))
        wan_exists = os.path.exists(wan_out) and any(os.scandir(wan_out))

        if not lan_exists or not wan_exists:
            log.debug("Missing neutered VDF files for 2010?2011. Processing?")
            process_appinfo_files(base_in, lan_out, True)
            process_appinfo_files(base_in, wan_out, False)
            processing_done = True

    # Update config tracking hash after any processing or config change
    # This ensures we don't re-invalidate on next startup if nothing changed
    if processing_done or configs_changed:
        update_appinfo_config_tracking()


# ============================================================================
# CHUNK-LEVEL NEUTERING (for GCF/storage chunk processing)
# ============================================================================

def config_replace_in_chunk(chunk, filename, replacement_strings, config_num, use_space=False):
    """
    Replace strings in a chunk with padding. Simpler version for chunk-level processing.

    Unlike config_replace_in_file which auto-detects text files, this version is
    explicitly for binary chunk data and uses the use_space parameter directly.

    Args:
        chunk: The chunk data (bytes)
        filename: Filename for logging (bytes or str)
        replacement_strings: List of (search, replace, info) tuples
        config_num: Config number for logging
        use_space: If True, use space padding; otherwise use null bytes

    Returns:
        Modified chunk data
    """
    if isinstance(filename, str):
        filename = filename.encode("latin-1")

    for search, replace, info in replacement_strings:
        try:
            if chunk.find(search) != -1:
                search_len = len(search)
                replace_len = len(replace)

                if replace_len > search_len:
                    log.warning(
                        f"{globalvars.CURRENT_APPID_VERSION}{filename.decode()}: Replacement text '{replace.decode()}' (length: {replace_len}) is longer than allowed (max: {search_len})."
                    )
                else:
                    padding = b'\x00' if not use_space else b'\x20'
                    replace_padded = replace + (padding * (search_len - replace_len))
                    chunk = chunk.replace(search, replace_padded)
        except Exception as e:
            log.error(f"Config {config_num}: Error processing file {filename.decode()}: {e}")

    return chunk


def replace_cc_in_chunk(chunk):
    """
    Replace CC expiry date field in chunk to make it editable.

    This modifies a VDF field to change "editable" from "0" to "1",
    allowing expiration year combo box to be edited.
    """
    try:
        expiration_search = binascii.a2b_hex("2245787069726174696F6E59656172436F6D626F220D0A09092278706F7322090922323632220D0A09092279706F7322090922313634220D0A09092277696465220909223636220D0A09092274616C6C220909223234220D0A0909226175746F526573697A652209092230220D0A09092270696E436F726E65722209092230220D0A09092276697369626C652209092231220D0A090922656E61626C65642209092231220D0A090922746162506F736974696F6E2209092234220D0A0909227465787448696464656E2209092230220D0A0909226564697461626C65220909223022")
        expiration_replace = binascii.a2b_hex("2245787069726174696F6E59656172436F6D626F220D0A09092278706F7322090922323632220D0A09092279706F7322090922313634220D0A09092277696465220909223636220D0A09092274616C6C220909223234220D0A0909226175746F526573697A652209092230220D0A09092270696E436F726E65722209092230220D0A09092276697369626C652209092231220D0A090922656E61626C65642209092231220D0A090922746162506F736974696F6E2209092234220D0A0909227465787448696464656E2209092230220D0A0909226564697461626C65220909223122")
        chunk = chunk.replace(expiration_search, expiration_replace)
    except Exception as e:
        log.error(f"{globalvars.CURRENT_APPID_VERSION}Failed to replace CC expiry date in chunk: {e}")
    return chunk


def replace_dirip_in_chunk(chunk, search, server_ip, server_port, dirgroup):
    """
    Replace directory server IP patterns in chunk data.

    Args:
        chunk: The chunk data (bytes)
        search: The search pattern (bytes)
        server_ip: Server IP to use for replacement (bytes)
        server_port: Server port (bytes)
        dirgroup: Directory group number for logging

    Returns:
        Modified chunk data
    """
    ip = (server_ip + b":" + server_port + b" ")

    searchlength = len(search)
    iplength = len(ip)
    numtoreplace = searchlength // iplength
    ips = ip * numtoreplace
    replace = ips + (b'\x00' * (searchlength - len(ips)))
    if chunk.find(search) != -1:
        chunk = chunk.replace(search, replace)
    return chunk


def replace_ips_in_chunk(chunk, ip_list, replacement_ip, islan):
    """
    Replace IP addresses in chunk data.

    Args:
        chunk: The chunk data (bytes)
        ip_list: List of IP patterns to search for
        replacement_ip: Replacement IP (unused, overridden by config)
        islan: True for LAN, False for WAN

    Returns:
        Modified chunk data
    """
    for ip in ip_list:
        loc = chunk.find(ip)
        if loc != -1:
            if islan:
                replacement_ip = config["server_ip"].encode() + (b"\x00" * (16 - len(config["server_ip"])))
            else:
                replacement_ip = config["public_ip"].encode() + (b"\x00" * (16 - len(config["public_ip"])))
            chunk = chunk[:loc] + replacement_ip + chunk[loc + 16:]
    return chunk


def readchunk_neuter(chunk, appid, islan, is2003gcf):
    """
    Apply neutering to a storage chunk.

    This is the main entry point for chunk-level neutering, used when
    neutering GCF/storage files for serving to clients.

    Args:
        chunk: The chunk data (bytes)
        appid: Application ID
        islan: True for LAN, False for WAN
        is2003gcf: True if this is a 2003-era GCF format

    Returns:
        Neutered chunk data
    """
    # Load a custom neuter json file if present, otherwise we load global.json by default
    custom_data = parse_json("storage", str(appid))

    # Extract data
    if custom_data is not None:
        custom_tags, replacements = custom_data

        if islan or config["public_ip"] == "0.0.0.0":
            fullstring1 = globalvars.replace_string(True)
            # Custom Neutering comes first, in case the user wants to override something that gets neutered
            chunk = do_neuter(custom_tags, chunk, f"Appid: {appid}", replacements, True)
        else:
            fullstring1 = globalvars.replace_string(False)
            # Custom Neutering comes first, in case the user wants to override something that gets neutered
            chunk = do_neuter(custom_tags, chunk, f"Appid: {appid}", replacements, False)

    if islan or config["public_ip"] == "0.0.0.0":
        fullstring1 = globalvars.replace_string(True)
    else:
        fullstring1 = globalvars.replace_string(False)
    chunk = config_replace_in_chunk(chunk, b'chunk', fullstring1, 1)

    if islan:
        fullstring2 = globalvars.replace_string_name_space(True, is2003gcf)
        fullstring3 = globalvars.replace_string_name(True, is2003gcf)
    elif config["public_ip"] != "0.0.0.0" or not islan:
        fullstring2 = globalvars.replace_string_name_space(False, is2003gcf)
        fullstring3 = globalvars.replace_string_name(False, is2003gcf)
    else:
        fullstring2 = globalvars.replace_string_name_space(False, is2003gcf)
        fullstring3 = globalvars.replace_string_name(False, is2003gcf)

    chunk = config_replace_in_chunk(chunk, b'chunk', fullstring2, 2, True)
    chunk = config_replace_in_chunk(chunk, b'chunk', fullstring3, 3)

    if islan:
        server_ip = config["server_ip"].encode('latin-1')
    else:
        server_ip = config["public_ip"].encode('latin-1')

    if config["csds_ipport"]:
        if ":" in config["csds_ipport"]:
            server_ip = config["csds_ipport"][:config["csds_ipport"].index(":")].encode('latin-1')

    server_port = config["dir_server_port"].encode('latin-1')

    for index, search in enumerate(ips_to_replace):
        chunk = replace_dirip_in_chunk(chunk, search, server_ip, server_port, index % 5)

    chunk = replace_ips_in_chunk(chunk, globalvars.ip_addresses, server_ip, islan)

    chunk = replace_cc_in_chunk(chunk)

    return chunk


# ============================================================================
# STORAGE NEUTERING
# ============================================================================

def neuter_single_storage(appid: int, version: int) -> bool:
    """
    Apply custom neutering to a single storage (SDK depot).

    This function checks for custom neuter configs for the given appid/version
    and applies them to storage chunks, creating cached neutered files.

    Args:
        appid: The application ID
        version: The storage version

    Returns:
        True if neutering was successful or no neutering was needed,
        False if there was an error
    """
    import struct
    import zlib
    import os

    # Check for custom neuter config
    identifier = f"{appid}_{version}"
    parsedjson = parse_json("storage", identifier)

    if parsedjson is None:
        log.debug(f"No custom neuter config for storage {identifier}")
        return True  # No config = nothing to neuter, that's OK

    custom_tags, replacements = parsedjson

    if not replacements:
        log.debug(f"Custom neuter config for storage {identifier} has no replacements")
        return True

    log.info(f"Applying custom neuter config for storage {identifier} ({len(replacements)} replacement rules)")

    # Process for both LAN and WAN
    for islan in [True, False]:
        suffix = "_lan" if islan else "_wan"

        success = _neuter_storage_chunks(appid, version, custom_tags, replacements, islan, suffix)
        if not success:
            log.error(f"Failed to neuter storage {identifier} for {'LAN' if islan else 'WAN'}")
            return False

    log.info(f"Successfully applied custom neutering to storage {identifier}")
    return True


def _neuter_storage_chunks(appid: int, version: int, custom_tags: dict,
                           replacements: list, islan: bool, suffix: str) -> bool:
    """
    Internal function to neuter storage chunks for a specific network type.

    Args:
        appid: The application ID
        version: The storage version
        custom_tags: Custom tag definitions from config
        replacements: List of replacement rules
        islan: True for LAN, False for WAN
        suffix: "_lan" or "_wan"

    Returns:
        True if successful, False otherwise
    """
    import struct
    import zlib
    import os

    try:
        # Try to load the storage to get file/chunk info
        from utilities.storages import Steam2Storage
        from utilities import steam2_sdk_utils

        # Check if this is an SDK depot
        if not steam2_sdk_utils.check_for_entry(appid, version):
            log.debug(f"Storage {appid}_{version} is not an SDK depot, skipping")
            return True

        # Create cache directory
        cache_dir = os.path.join("files", "cache", f"{appid}_{version}")
        os.makedirs(cache_dir, exist_ok=True)

        # Initialize storage to get file info
        storage = Steam2Storage(appid, config["steam2sdkdir"], version, islan)

        # Track which files were modified
        modified_files = set()

        # Process each file in the storage
        for fileid, file_info in storage.file_data_info.items():
            checksums = file_info['checksums']
            dat_path = file_info['datfile']
            base_offset = file_info['offset']

            if dat_path is None:
                continue

            # Process each chunk in the file
            chunk_offset = base_offset
            modified_chunks = []
            file_modified = False

            for chunkid, (compr_size, checksum) in enumerate(checksums):
                # Read original compressed chunk
                with open(dat_path, "rb") as f:
                    f.seek(chunk_offset)
                    compressed_data = f.read(compr_size)

                chunk_offset += compr_size

                # Try to decompress
                try:
                    decompressed = zlib.decompress(compressed_data)
                except zlib.error:
                    # Not compressed or corrupt, use as-is
                    decompressed = compressed_data

                # Apply neutering to decompressed data
                original_data = decompressed
                neutered_data = do_neuter(
                    custom_tags,
                    decompressed,
                    f"{appid}_{fileid}_{chunkid}.chunk",  # synthetic filename for matching
                    replacements,
                    islan
                )

                if neutered_data != original_data:
                    file_modified = True
                    # Re-compress the neutered data
                    try:
                        recompressed = zlib.compress(neutered_data, 9)
                    except:
                        recompressed = neutered_data

                    modified_chunks.append((chunkid, recompressed))
                    log.debug(f"Neutered chunk {chunkid} of file {fileid} in storage {appid}_{version}")

            # If any chunks were modified, write cached file
            if file_modified and modified_chunks:
                modified_files.add(fileid)
                _write_neutered_chunks(cache_dir, appid, fileid, suffix,
                                       storage, modified_chunks, checksums, file_info)

        if modified_files:
            log.info(f"Neutered {len(modified_files)} files in storage {appid}_{version}{suffix}")
        else:
            log.debug(f"No modifications needed for storage {appid}_{version}{suffix}")

        return True

    except Exception as e:
        log.error(f"Error neutering storage {appid}_{version}: {e}", exc_info=True)
        return False


def _write_neutered_chunks(cache_dir: str, appid: int, fileid: int, suffix: str,
                           storage, modified_chunks: list, checksums: list,
                           file_info: dict) -> None:
    """
    Write neutered chunks to cache files.

    Creates per-file .data and .index files in the cache directory.
    """
    import struct
    import os

    data_path = os.path.join(cache_dir, f"{appid}_{fileid}{suffix}.data")
    index_path = os.path.join(cache_dir, f"{appid}_{storage.ver}{suffix}.index")

    # Build a map of modified chunks
    modified_map = {chunkid: data for chunkid, data in modified_chunks}

    # Read all chunks (modified or original)
    chunks = []
    dat_path = file_info['datfile']
    chunk_offset = file_info['offset']

    for chunkid, (compr_size, checksum) in enumerate(checksums):
        if chunkid in modified_map:
            chunks.append(modified_map[chunkid])
        else:
            # Read original chunk
            with open(dat_path, "rb") as f:
                f.seek(chunk_offset)
                chunks.append(f.read(compr_size))
        chunk_offset += compr_size

    # Write data file
    index_data = bytearray()
    current_offset = 0

    with open(data_path, "wb") as f:
        for chunk in chunks:
            f.write(chunk)
            index_data += struct.pack(">QQ", current_offset, len(chunk))
            current_offset += len(chunk)

    # Append to index file (or create if needed)
    # The index format includes fileid, num_chunks * 16, and filemode header
    index_header = struct.pack(">QQQ", fileid, len(chunks) * 16, file_info['filemode'])

    # Check if index file exists and append, otherwise create
    mode = "ab" if os.path.exists(index_path) else "wb"
    with open(index_path, mode) as f:
        f.write(index_header + index_data)


def check_storage_neuter_config(appid: int, version: int) -> bool:
    """
    Check if a storage has a custom neuter config that should be applied.

    Args:
        appid: The application ID
        version: The storage version

    Returns:
        True if a neuter config exists for this storage
    """
    identifier = f"{appid}_{version}"
    parsedjson = parse_json("storage", identifier)

    if parsedjson is not None:
        custom_tags, replacements = parsedjson
        if replacements:
            log.info(f"Found custom neuter config for storage {identifier} "
                     f"with {len(replacements)} replacement rules")
            return True

    return False

