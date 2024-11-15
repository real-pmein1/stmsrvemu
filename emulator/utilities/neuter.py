import logging
import os

import globalvars
from config import get_config as read_config
from utilities import binary_patcher
from utilities.packages import Package


ips_to_replace = [
    b"207.173.177.11:27030 207.173.177.12:27030",
    b"207.173.177.11:27030 207.173.177.12:27030 69.28.151.178:27038 69.28.153.82:27038 68.142.88.34:27038 68.142.72.250:27038",
    b"72.165.61.189:27030 72.165.61.190:27030 69.28.151.178:27038 69.28.153.82:27038 68.142.88.34:27038 68.142.72.250:27038",
    b"72.165.61.189:27030 72.165.61.190:27030 69.28.151.178:27038 69.28.153.82:27038 87.248.196.194:27038 68.142.72.250:27038",
    b"127.0.0.1:27030 127.0.0.1:27030 127.0.0.1:27030 127.0.0.1:27030 127.0.0.1:27030 127.0.0.1:27030",
    b"208.64.200.189:27030 208.64.200.190:27030 208.64.200.191:27030 208.78.164.7:27038"
]
config = read_config()

pkgadd_filelist = []
log = logging.getLogger("neuter")


def neuter_file(file, server_ip, server_port, filename, islan):

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
    # Assuming replace_in_file is a function that takes the file, filename, search pattern, server_ip, server_port, and an index
    for index, search in enumerate(ips_to_replace):
        file = replace_dirip_in_file(file, filename, search, server_ip, server_port, index % 5)

    file = replace_ips_in_file(file, filename, globalvars.ip_addresses, server_ip, islan)

    if not config["server_ip"] == "127.0.0.1":
        file = replace_ips_in_file(file, filename, globalvars.loopback_ips, server_ip, islan)

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
    return file


def public_res_replace_in_file(file, filename, replacement_strings):
    if isinstance(filename, str):
        filename = filename.encode("latin-1")
    for search, replace, info in replacement_strings:
        try:
            if file.find(search) != -1:
                file = file.replace(search, replace)
                log.debug(f"{filename.decode()}: Replaced {info.decode()}")
        except Exception as e:
            log.error(f"Resource File line not found: {e} {filename.decode()}")
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


def replace_ips_in_file(file, filename, ip_list, replacement_ip, islan):
    if isinstance(filename, str):
        filename = filename.encode("latin-1")

    for ip in ip_list:
        loc = file.find(ip)
        if loc != -1:
            if islan:
                # For LAN, always use server_ip
                replacement_ip = config["server_ip"].encode() + (b"\x00" * (16 - len(config["server_ip"])))
            else:
                replacement_ip = config["public_ip"].encode() + (b"\x00" * (16 - len(config["public_ip"])))

            file = file[:loc] + replacement_ip + file[loc + 16:]
            log.debug(f"{filename.decode()}: Found and replaced IP {ip.decode():>16} at location {loc:08x}")
    return file


def config_replace_in_file(file, filename, replacement_strings, config_num, use_space = False):
    if isinstance(filename, str):
        filename = filename.encode("latin-1")
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
                        padding = b'\x00' if use_space is False else b'\x20'
                        replace_padded = replace + (padding * missing_length)
                        file = file.replace(search, replace_padded)
                        log.debug(f"{filename.decode()}: Replaced {info.decode()}")
        except Exception as e:
            log.error(f"Config {config_num} line not found: {e} {filename.decode()}")

    return file


def replace_dirip_in_file(file, filename, search, server_ip, server_port, dirgroup):
    if isinstance(filename, str):
        filename = filename.encode("latin-1")

    ip = (server_ip + ":" + server_port + " ").encode() # we only replace 1, this fixes any issues with the length being incorrect!

    searchlength = len(search)
    iplength = len(ip)
    numtoreplace = searchlength // iplength
    ips = ip * numtoreplace
    replace = ips + (b'\x00' * (searchlength - len(ips)))
    if file.find(search) != -1:
        file = file.replace(search, replace)
        log.debug(f"{filename.decode()}: Replaced directory server IP group {dirgroup}")
    return file


def get_filenames():
    if config["enable_steam3_servers"] == "true":
        return (b"SteamNew.exe", b"Steam.dll", b"SteamUI.dll", b"platform.dll", b"steam\SteamUIConfig.vdf", b"steam\SubPanelWelcomeCreateNewAccount.res", b"GameOverlayRenderer.dll", b"GameOverlayUI.exe", b"steam\SteamUI.dll", b"friends\servers.vdf", b"servers\MasterServers.vdf", b"servers\ServerBrowser.dll",  b"caserver.exe", b"cacdll.dll", b"CASClient.exe", b"unicows.dll", b"GameUI.dll", b"steamclient.dll", b"steamclient64.dll", b"friendsUI.dll", b"bin\p2pcore.dll", b"bin\steamservice.dll", b"bin\steamservice.exe")
    else:
        return (b"SteamNew.exe", b"Steam.dll", b"SteamUI.dll", b"platform.dll", b"steam\SteamUIConfig.vdf", b"steam\SubPanelWelcomeCreateNewAccount.res", b"steam\SteamUI.dll", b"friends\servers.vdf", b"servers\MasterServers.vdf", b"servers\ServerBrowser.dll", b" valvesoftware\privacy.htm", b"caserver.exe", b"cacdll.dll", b"CASClient.exe", b"unicows.dll", b"GameUI.dll")
    #b"steam\SteamUIConfig.vdf", b"Public\ssa_english.htm"
    #b"Public\SubPanelWelcomeCreateNewAccount.res", b"Public\SubPanelWelcomeCreateNewAccountEmailAlreadyUsed.res",
    #b"Public\SubPanelWelcomeCreateNewAccountEmail.res", b"Public\UseOfflineMode.res", b"Public\VACBanDialog.res",
    #b"Public\ConnectionIssuesDialog.res", b"Public\steamui_english.txt", b"Public\steamui_french.txt",
    #b"Public\steamui_german.txt", b"Public\steamui_italian.txt", b"Public\steamui_japanese.txt",
    #b"Public\steamui_korean.txt", b"Public\steamui_koreana.txt", b"Public\steamui_portuguese.txt",
    #b"Public\steamui_russian.txt", b"Public\steamui_schinese.txt", b"Public\steamui_tchinese.txt",
    #b"Public\steamui_spanish.txt", b"Public\steamui_thai.txt",b"Public\Account.html",
    #else:
    #return (b"SteamNew.exe", b"Steam.dll", b"SteamUI.dll", b"platform.dll", b"steam\SteamUI.dll", b"friends\servers.vdf", b"servers\MasterServers.vdf", b"servers\ServerBrowser.dll", b"Public\Account.html", b"caserver.exe", b"cacdll.dll", b"CASClient.exe", b"unicows.dll", b"GameUI.dll")  # b"steamclient.dll", b"GameOverlayUI.exe", b"serverbrowser.dll", b"gamoverlayui.dll", b"steamclient64.dll", b"AppOverlay.dll", b"AppOverlay64.dll", b"SteamService.exe", b"friendsUI.dll", b"SteamService.dll")


def create_steam_config_file():
    # Define the file path
    file_path = "files/mod_pkg/steam/global/Steam.cfg"

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

    # steamui_270 is when the rsa file signature check was enabled/added ( FIXME NEED TO VERIFY IT IS ACTUALLY 270! )
    if "SteamUI_" in pkg_in and int(version_id) > 270:
        steamui_signature = "83 c4 ?? 84 c0 75 08 83 c6 01"
        # replacement bytes for to replace the rsa function call with "mov eax, 1"
        replacement = "B8 01 00 00 00"
        num_nops = 0  # adjust based on how many nops need to be filled in to completely replace an instruction
    else:
        pass

    f = open(pkg_in, "rb")
    pkg = Package(f.read())
    f.close()

    # Retrieve the list of specific filenames to process
    specified_filenames = get_filenames()
    allowed_extensions = (b'.txt', b'.htm', b'.html', b'.res')

    for filename in pkg.filenames:
        # Process files in the Public/ folder with neuter_public_file()
        if (filename.startswith(b"Public") or filename.startswith(b"resource") or filename.startswith(b"steam")) and filename.lower().endswith(allowed_extensions):
            file = pkg.get_file(filename)
            file = neuter_public_file(file, filename, islan)
            pkg.put_file(filename, file)
        # Process only the files that are in the specified_filenames list with neuter_file()
        elif filename in specified_filenames:
            file = pkg.get_file(filename)
            # we patch steamui.dll to enable steamclient/steamclient64 dll neutering
            if b'SteamUI.dll' in filename and int(version_id) > 270:
                # FIXME deepcopy() doesnt seem to work either this still shows steamui.dll as not modified...
                #file_compare = copy.deepcopy(file)
                #log.debug("Found steamui.dll")
                file = binary_patcher.find_and_replace_pattern(file, filename, steamui_signature, replacement, -5, False)
                #if file == file_compare:
                #    log.error("SteamUI.dll not modified!!!")
            file = neuter_file(file, server_ip, server_port, filename, islan)
            pkg.put_file(filename, file)

    if len(pkgadd_filelist) > 0:
        del pkgadd_filelist[:]

    if config["use_sdk"].lower() == "true" and config["sdk_ip"] != "0.0.0.0" and config["sdk_ip"] != "" and config["use_sdk_as_cs"].lower() == "false":
        create_steam_config_file()
        if os.path.isfile("files/cache/Steam_" + str(globalvars.steam_ver) + ".pkg"):
            os.remove("files/cache/Steam_" + str(globalvars.steam_ver) + ".pkg")
    else:
        if os.path.isfile("files/mod_pkg/steam/global/Steam.cfg"):
            try:
                os.remove("files/cache/Steam_" + str(globalvars.steam_ver) + ".pkg")
            except:
                pass
            os.remove("files/mod_pkg/steam/global/Steam.cfg")

    if os.path.isdir("files/mod_pkg"):
        log.debug("Found mod_pkg folder")
        if os.path.isdir("files/mod_pkg/steamui/") and ("SteamUI_" in pkg_in):
            log.debug("Found steamui folder")
            base_path = "files/mod_pkg/steamui/"
            mod_pkg(base_path, pkg, version_id, "SteamUI")
        elif os.path.isdir("files/mod_pkg/steam/") and ("Steam_" in pkg_in):
            log.debug("Found steam folder")
            base_path = "files/mod_pkg/steam/"
            mod_pkg(base_path, pkg, version_id, "Steam")
    with open(pkg_out, "wb") as f:
        f.write(pkg.pack())


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

        # If the file was found, add it to the package
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