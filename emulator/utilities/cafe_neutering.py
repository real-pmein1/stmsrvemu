import os
import shutil
import tempfile
import zipfile

import globalvars
from utilities.neuter import neuter_file


def create_zip_package(zip_file, steam_dll, config_lines, caserver_lines, passwords_line, readme, steam_exe):
    with zipfile.ZipFile(zip_file, 'a') as zipped_f:
        zipped_f.writestr("Steam.dll", steam_dll)
        zipped_f.writestr("Client/lsclient.cfg", config_lines)
        zipped_f.writestr("CAServer.cfg", caserver_lines)
        zipped_f.writestr("passwords.txt", passwords_line)
        if readme:
            zipped_f.writestr("README.txt", readme)
        if steam_exe:
            zipped_f.writestr("Client/Steam.exe", steam_exe)


def process_zip(zip_file):
    tempdir = tempfile.mkdtemp()
    try:
        tempname = os.path.join(tempdir, 'new.zip')
        with zipfile.ZipFile(zip_file, 'r') as zipread, zipfile.ZipFile(tempname, 'w') as zipwrite:
            for item in zipread.infolist():
                if item.filename not in 'CAServer.cfg':
                    data = zipread.read(item.filename)
                    zipwrite.writestr(item, data)
        shutil.move(tempname, zip_file)
    finally:
        shutil.rmtree(tempdir)


def read_file(filepath):
    with open(filepath, "rb") as file:
        return file.read()


def generate_config_lines(ip, user, passw, ip_range) :
    return bytes("\n".join([
        f"CAServerIP = {ip}",
        "ExitSteamAfterGame = true",
        "AllowUserLogin = false",
        "AllowCafeLogin = true",
        f"MasterServerIP = {ip}",
        f"MasterLogin = {user}",
        f"MasterPass = {passw}",
        f"IPRange1 = {ip_range}",
        "EnableTimedUpdates = disable",
        "UpdateStart = 2200",
        "UpdateEnd = 0200"
    ]), "latin-1")


def process_cafe_files(steam_dll_path, zip_path, wan_path, lan_path, read_me_path, steam_exe_path, config):
    try:
        os.mkdir("client/cafe_server")
    except:
        pass
    steam_dll = read_file(steam_dll_path)
    file_wan = neuter_file(steam_dll, config["public_ip"], config["dir_server_port"], "steam.dll", False)
    file_lan = neuter_file(steam_dll, config["server_ip"], config["dir_server_port"], "steam.dll", True)

    lsclient_lines_wan = generate_config_lines(config["public_ip"], config["cafeuser"], config["cafepass"], "192.168.0.1")
    lsclient_lines_lan = generate_config_lines(config["server_ip"], config["cafeuser"], config["cafepass"], "192.168.0.1")

    caserver_lines_wan = generate_config_lines(config["public_ip"], config["cafeuser"], config["cafepass"], "192.168.0.1")
    caserver_lines_lan = generate_config_lines(config["server_ip"], config["cafeuser"], config["cafepass"], "192.168.0.1")

    passwords_line = bytes(config["cafeuser"] + "%" + config["cafepass"], "latin-1")
    readme = read_file(read_me_path) if os.path.isfile(read_me_path) else None
    steam_exe = read_file(steam_exe_path) if os.path.isfile(steam_exe_path) else None

    if globalvars.public_ip != "0.0.0.0":
        shutil.copyfile(zip_path, wan_path)
        create_zip_package(wan_path, file_wan, lsclient_lines_wan, caserver_lines_wan, passwords_line, readme, steam_exe)
        process_zip(wan_path)

    shutil.copyfile(zip_path, lan_path)
    create_zip_package(lan_path, file_lan, lsclient_lines_lan, caserver_lines_lan, passwords_line, readme, steam_exe)
    process_zip(lan_path)