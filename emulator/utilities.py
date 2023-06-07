import binascii, ConfigParser, threading, logging, time, os, shutil, zipfile
import tempfile, zlib, os.path, ast, csv, sys, struct, string, random, logging
import blob_utilities

from Steam2.package import Package
from Steam2.neuter import neuter_file
from steamemu.converter import convertgcf
from steamemu.config import read_config
config = read_config()

def decodeIP(string) :
    (oct1, oct2, oct3, oct4, port) = struct.unpack("<BBBBH", string)
    ip = "%d.%d.%d.%d" % (oct1, oct2, oct3, oct4)
    return ip, port

def encodeIP((ip, port)) :
    if type(port) == str :
        port = int(port)
    oct = ip.split(".")
    string = struct.pack("<BBBBH", int(oct[0]), int(oct[1]), int(oct[2]), int(oct[3]), port)
    return string

def steamtime_to_unixtime(steamtime_bin) :
    steamtime = struct.unpack("<Q", steamtime_bin)[0]
    unixtime = steamtime / 1000000- 62135596800
    return unixtime

def unixtime_to_steamtime(unixtime) :
    steamtime = (unixtime + 62135596800) * 1000000
    steamtime_bin = struct.pack("<Q", steamtime)
    return steamtime_bin

def formatstring(text) :
    if len(text) == 4 and text[2] == "\x00" :
        return ("'\\x%02x\\x%02x\\x%02x\\x%02x'") % (ord(text[0]), ord(text[1]), ord(text[2]), ord(text[3]))
    else :
        return repr(text)

def generate_password():
    characters = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(random.choice(characters) for _ in range(16))
    return password


def encrypt(message, password):
    encrypted = ""
    for i in range(len(message)):
        char = message[i]
        key = password[i % len(password)]
        encrypted += chr(ord(char) ^ ord(key))
    return encrypted


def decrypt(encrypted, password):
    decrypted = ""
    for i in range(len(encrypted)):
        char = encrypted[i]
        key = password[i % len(password)]
        decrypted += chr(ord(char) ^ ord(key))
    return decrypted

def sortfunc(x, y) :

    if len(x) == 4 and x[2] == "\x00" :
        if len(y) == 4 and y[2] == "\x00" :
            numx = struct.unpack("<L", x)[0]
            numy = struct.unpack("<L", y)[0]
            return cmp(numx, numy)
        else :
            return -1
    else :
        if len(y) == 4 and y[2] == "\x00" :
            return 1
        else :
            return cmp(x, y)

def initialise():
    log = logging.getLogger('emulator')
# create the Steam.exe file
    f = open(config["packagedir"] + config["steampkg"], "rb")
    pkg = Package(f.read())
    f.close()
    file = pkg.get_file("SteamNew.exe")
    if config["public_ip"] != "0.0.0.0" :
        file = neuter_file(file, config["public_ip"], config["dir_server_port"])
    else :
        file = neuter_file(file, config["server_ip"], config["dir_server_port"])
    f = open("client/Steam.exe", "wb")
    f.write(file)
    f.close()

    if config["hldsupkg"] != "" :
        g = open(config["packagedir"] + config["hldsupkg"], "rb")
        pkg = Package(g.read())
        g.close()
        file = pkg.get_file("HldsUpdateToolNew.exe")
        if config["public_ip"] != "0.0.0.0" :
            file = neuter_file(file, config["public_ip"], config["dir_server_port"])
        else :
            file = neuter_file(file, config["server_ip"], config["dir_server_port"])
        g = open("client/HldsUpdateTool.exe", "wb")
        g.write(file)
        g.close()
            
    if os.path.isfile("files/1stcdr.py") :
        f = open("files/1stcdr.py", "r")
        firstblob = f.read()
        f.close()
    else :
        f = open("files/firstblob.bin", "rb")
        firstblob_bin = f.read()
        f.close()
        if firstblob_bin[0:2] == "\x01\x43":
            firstblob_bin = zlib.decompress(firstblob_bin[20:])
        firstblob_unser = blob_utilities.blob_unserialize(firstblob_bin)
        firstblob = blob_utilities.blob_dump(firstblob_unser)

    firstblob_list = firstblob.split("\n")
    steam_hex = firstblob_list[2][25:41]
    steam_ver = str(int(steam_hex[14:16] + steam_hex[10:12] + steam_hex[6:8] + steam_hex[2:4], 16))
    steamui_hex = firstblob_list[3][25:41]
    steamui_ver = int(steamui_hex[14:16] + steamui_hex[10:12] + steamui_hex[6:8] + steamui_hex[2:4], 16)

    if steamui_ver < 122 :
        if os.path.isfile("files/cafe/Steam.dll") :
            log.info("Cafe files found")
            g = open("files/cafe/Steam.dll", "rb")
            file = g.read()
            g.close()
            if config["public_ip"] != "0.0.0.0" :
                file = neuter_file(file, config["public_ip"], config["dir_server_port"])
            else :
                file = neuter_file(file, config["server_ip"], config["dir_server_port"])
            if os.path.isfile("files/cafe/CASpackage.zip") :
                shutil.copyfile("files/cafe/CASpackage.zip", "client/cafe_server/CASpackage.zip")
                with zipfile.ZipFile('client/cafe_server/CASpackage.zip', 'a') as zipped_f:
                    zipped_f.writestr("Steam.dll", file)
                lsclient_line1 = "CAServerIP = " + config["server_ip"]
                lsclient_line2 = "ExitSteamAfterGame = true"
                lsclient_line3 = "AllowUserLogin = false"
                lsclient_line4 = "AllowCafeLogin = true"
                lsclient_lines = bytes(lsclient_line1 + "\n" + lsclient_line2 + "\n" + lsclient_line3 + "\n" + lsclient_line4)
                with zipfile.ZipFile('client/cafe_server/CASpackage.zip', 'a') as zipped_f:
                    zipped_f.writestr("Client/lsclient.cfg", lsclient_lines)
                tempdir = tempfile.mkdtemp()
                try:
                    tempname = os.path.join(tempdir, 'new.zip')
                    with zipfile.ZipFile('client/cafe_server/CASpackage.zip', 'r') as zipread:
                        with zipfile.ZipFile(tempname, 'w') as zipwrite:
                            for item in zipread.infolist():
                                if item.filename not in 'CAServer.cfg':
                                    data = zipread.read(item.filename)
                                    zipwrite.writestr(item, data)
                    shutil.move(tempname, 'client/cafe_server/CASpackage.zip')
                finally:
                    shutil.rmtree(tempdir)
                caserver_line1 = "MasterServerIP = " + config["server_ip"]
                caserver_line2 = "MasterLogin = " + config["cafeuser"]
                caserver_line3 = "MasterPass = " + config["cafepass"]
                caserver_line4 = "IPRange1 = 192.168.0.1"
                caserver_line5 = "EnableTimedUpdates = disable"
                caserver_line6 = "UpdateStart = 2200"
                caserver_line7 = "UpdateEnd = 0200"
                caserver_lines = bytes(caserver_line1 + "\n" + caserver_line2 + "\n" + caserver_line3 + "\n" + caserver_line4 + "\n" + caserver_line5 + "\n" + caserver_line6 + "\n" + caserver_line7)
                with zipfile.ZipFile('client/cafe_server/CASpackage.zip', 'a') as zipped_f:
                    zipped_f.writestr("CAServer.cfg", caserver_lines)
                passwords_line = bytes(config["cafeuser"] + "%" + config["cafepass"])
                with zipfile.ZipFile('client/cafe_server/CASpackage.zip', 'a') as zipped_f:
                    zipped_f.writestr("passwords.txt", passwords_line)
                if os.path.isfile("files/cafe/README.txt") :
                    g = open("files/cafe/README.txt", "rb")
                    file = g.read()
                    g.close()
                    with zipfile.ZipFile('client/cafe_server/CASpackage.zip', 'a') as zipped_f:
                        zipped_f.writestr("README.txt", file)
                g = open("client/Steam.exe", "rb")
                file = g.read()
                g.close()
                with zipfile.ZipFile('client/cafe_server/CASpackage.zip', 'a') as zipped_f:
                    zipped_f.writestr("Client/Steam.exe", file)
                    
            else :
                g = open("client/cafe_server/Steam.dll", "wb")
                g.write(file)
                g.close()
            
    if config["use_sdk"] == "1" :
        with open("files/pkg_add/steam/Steam.cfg", "w") as h :
            h.write('SdkContentServerAdrs = "' + config["sdk_ip"] + ':' + config["sdk_port"] + '"\n')
        if os.path.isfile("files/cache/Steam_" + steam_ver + ".pkg") :
            os.remove("files/cache/Steam_" + steam_ver + ".pkg")
    else :
        if os.path.isfile("files/pkg_add/steam/Steam.cfg") :
            os.remove("files/cache/Steam_" + steam_ver + ".pkg")
            os.remove("files/pkg_add/steam/Steam.cfg")

    if os.path.isfile("Steam.exe") :
        os.remove("Steam.exe")
    if os.path.isfile("HldsUpdateTool.exe") :
        os.remove("HldsUpdateTool.exe")
    if os.path.isfile("log.txt") :
        os.remove("log.txt")
    if os.path.isfile("library.zip") :
        os.remove("library.zip")
    if os.path.isfile("MSVCR71.dll") :
        os.remove("MSVCR71.dll")
    if os.path.isfile("python24.dll") :
        os.remove("python24.dll")
    if os.path.isfile("python27.dll") :
        os.remove("python27.dll")
    if os.path.isfile("Steam.cfg") :
        os.remove("Steam.cfg")
    if os.path.isfile("w9xpopen.exe") :
        os.remove("w9xpopen.exe")

    log.info("Checking for gcf files to convert...")
    convertgcf()


   
