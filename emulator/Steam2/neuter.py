import ConfigParser, os, logging, binascii

from package import Package
from steamemu.config import read_config
import globalvars

if globalvars.steamui_ver < 252: #last 2006 for now
    filenames = ("SteamNew.exe", "Steam.dll", "SteamUI.dll", "platform.dll", "steam\SteamUI.dll", "friends\servers.vdf", "servers\MasterServers.vdf", "servers\ServerBrowser.dll", "Public\Account.html", "caserver.exe", "cacdll.dll", "CASClient.exe", "unicows.dll", "GameUI.dll", "steamclient.dll", "steam\SteamUIConfig.vdf")
else:
    filenames = ("SteamNew.exe", "Steam.dll", "SteamUI.dll", "platform.dll", "steam\SteamUI.dll", "friends\servers.vdf", "servers\MasterServers.vdf", "servers\ServerBrowser.dll", "Public\Account.html", "caserver.exe", "cacdll.dll", "CASClient.exe", "unicows.dll", "GameUI.dll")#, "steamclient.dll", "GameOverlayUI.exe", "serverbrowser.dll", "gamoverlayui.dll", "steamclient64.dll", "AppOverlay.dll", "AppOverlay64.dll", "SteamService.exe", "friendsUI.dll", "SteamService.dll")

config = read_config()

pkgadd_filelist = []

def neuter_file(file, server_ip, server_port, filename, network) :
    log = logging.getLogger("neuter")
    if network == "lan" :
        #fullstring = globalvars.replacestrings
        fullstring = globalvars.replace_string("lan")
    #elif config["public_ip"] != "0.0.0.0" :
    elif network == "wan" :
        #fullstring = globalvars.replacestringsext
        fullstring = globalvars.replace_string("wan")
    else :
        #fullstring = globalvars.replacestrings
        fullstring = globalvars.replace_string("lan")
    
    for (search, replace, info) in fullstring :
        try :
            if file.find(search) != -1 :
                if search == "StorefrontURL1" :
                    if ":2004" in config["store_url"] :
                        file = file.replace(search, replace)
                        log.debug(filename + ": Replaced " + info)
                else :
                    fulllength = len(search)
                    newlength = len(replace)
                    missinglength = fulllength - newlength
                    if missinglength < 0 :
                        log.warn("WARNING: Replacement text " + replace + " is too long! Not replaced!")
                    elif missinglength == 0 :
                        file = file.replace(search, replace)
                        log.debug(filename + ": Replaced " + info)
                    else :
                        file = file.replace(search, replace + ('\x00' * missinglength))
                        log.debug(filename + ": Replaced " + info)
        except notfound :
            log.debug("Config line not found")

    if file.startswith("\x3C\x68\x74\x6D\x6C\x3E") :
        file_temp = binascii.b2a_hex(file)
        i = 0
        file_new = ""
        for byte_index in xrange(0, len(file_temp), 2):
            byte_hex = file_temp[i:i+2]
            if byte_hex == "00":
                byte_hex = ""
            file_new = file_new + byte_hex
            i += 2
        file = binascii.a2b_hex(file_new)

    search = "207.173.177.11:27030 207.173.177.12:27030"
    
    if network == "lan" :
        ip = server_ip + ":" + server_port + " "
    #elif config["public_ip"] != "0.0.0.0" :
    elif network == "wan" :
        ip = config["public_ip"] + ":" + server_port + " " + config["server_ip"] + ":" + server_port + " "
    else :
        ip = server_ip + ":" + server_port + " "
    searchlength = len(search)
    iplength = len(ip)
    numtoreplace = searchlength // iplength
    ips = ip * numtoreplace
    replace = ips.ljust(searchlength, '\x00')
    if file.find(search) != -1 :
        file = file.replace(search, replace)
        log.debug(filename + ": Replaced directory server IP group 0")

    search = "207.173.177.11:27030 207.173.177.12:27030 69.28.151.178:27038 69.28.153.82:27038 68.142.88.34:27038 68.142.72.250:27038"
    #ip = server_ip + ":" + server_port + " "
    #if len(ip) > 19 :
        #print "IP to replace with is too wide! This MIGHT result in problems!"
        #ips = ip * 5
    #else :
        #ips = ip * 6
    
    #replace = ips.ljust(119, " ")
    
    if network == "lan" :
        ip = server_ip + ":" + server_port + " "
    #elif config["public_ip"] != "0.0.0.0" :
    elif network == "wan" :
        ip = config["public_ip"] + ":" + server_port + " " + config["server_ip"] + ":" + server_port + " "
    else :
        ip = server_ip + ":" + server_port + " "
    searchlength = len(search)
    iplength = len(ip)
    numtoreplace = searchlength // iplength
    ips = ip * numtoreplace
    replace = ips.ljust(searchlength, '\x00')
    if file.find(search) != -1 :
        file = file.replace(search, replace)
        log.debug(filename + ": Replaced directory server IP group 1")

    search = "72.165.61.189:27030 72.165.61.190:27030 69.28.151.178:27038 69.28.153.82:27038 68.142.88.34:27038 68.142.72.250:27038 "
    #ip = server_ip + ":" + server_port + " "
    #if len(ip) > 19 :
        #print "IP to replace with is too wide! This MIGHT result in problems!"
        #ips = ip * 5
    #else :
        #ips = ip * 6

    #replace = ips.ljust(118, " ")
    
    if network == "lan" :
        ip = server_ip + ":" + server_port + " "
    #elif config["public_ip"] != "0.0.0.0" :
    elif network == "wan" :
        ip = config["public_ip"] + ":" + server_port + " " + config["server_ip"] + ":" + server_port + " "
    else :
        ip = server_ip + ":" + server_port + " "
    searchlength = len(search)
    iplength = len(ip)
    numtoreplace = searchlength // iplength
    ips = ip * numtoreplace
    replace = ips.ljust(searchlength, '\x00')
    if file.find(search) != -1 :
        file = file.replace(search, replace)
        log.debug(filename + ": Replaced directory server IP group 2")

    search = "72.165.61.189:27030 72.165.61.190:27030 69.28.151.178:27038 69.28.153.82:27038 87.248.196.194:27038 68.142.72.250:27038 "
    #ip = server_ip + ":" + server_port + " "
    #if len(ip) > 19 :
        #print "IP to replace with is too wide! This MIGHT result in problems!"
        #ips = ip * 5
    #else :
        #ips = ip * 6
    
    #replace = ips.ljust(120, " ")
    #replace = ips.ljust(119, " ")    119 breaks steamserver2008
    
    if network == "lan" :
        ip = server_ip + ":" + server_port + " "
    #elif config["public_ip"] != "0.0.0.0" :
    elif network == "wan" :
        ip = config["public_ip"] + ":" + server_port + " " + config["server_ip"] + ":" + server_port + " "
    else :
        ip = server_ip + ":" + server_port + " "
    searchlength = len(search)
    iplength = len(ip)
    numtoreplace = searchlength // iplength
    ips = ip * numtoreplace
    replace = ips.ljust(searchlength, '\x00')
    if file.find(search) != -1 :
        file = file.replace(search, replace)
        log.debug(filename + ": Replaced directory server IP group 3")
            
    search = "127.0.0.1:27030 127.0.0.1:27030 127.0.0.1:27030 127.0.0.1:27030 127.0.0.1:27030 127.0.0.1:27030"
    if network == "lan" :
        ip = server_ip + ":" + server_port + " "
    #elif config["public_ip"] != "0.0.0.0" :
    elif network == "wan" :
        ip = config["public_ip"] + ":" + server_port + " " + config["server_ip"] + ":" + server_port + " "
    else :
        ip = server_ip + ":" + server_port + " "
    searchlength = len(search)
    iplength = len(ip)
    numtoreplace = searchlength // iplength
    ips = ip * numtoreplace
    replace = ips.ljust(searchlength, '\x00')
    if file.find(search) != -1 :
        file = file.replace(search, replace)
        log.debug(filename + ": Replaced directory server IP group 4")
            
    search = "208.64.200.189:27030 208.64.200.190:27030 208.64.200.191:27030 208.78.164.7:27038"
    if network == "lan" :
        ip = server_ip + ":" + server_port + " "
    #elif config["public_ip"] != "0.0.0.0" :
    elif network == "wan" :
        ip = config["public_ip"] + ":" + server_port + " " + config["server_ip"] + ":" + server_port + " "
    else :
        ip = server_ip + ":" + server_port + " "
    searchlength = len(search)
    iplength = len(ip)
    numtoreplace = searchlength // iplength
    ips = ip * numtoreplace
    replace = ips.ljust(searchlength, '\x00')
    if file.find(search) != -1 :
        file = file.replace(search, replace)
        log.debug(filename + ": Replaced directory server IP group 5")

    for ip in globalvars.ip_addresses :
        loc = file.find(ip)
        if loc != -1 :
            if network == "lan" :
                replace_ip = server_ip.ljust(16, "\x00")
                file = file[:loc] + replace_ip + file[loc+16:]
                log.debug(filename + ": Found and replaced IP %16s at location %08x" % (ip, loc))
            #elif config["public_ip"] != "0.0.0.0" :
            elif network == "wan" :
                server_ip = config["public_ip"]
                replace_ip = server_ip.ljust(16, "\x00")
                file = file[:loc] + replace_ip + file[loc+16:]
                log.debug(filename + ": Found and replaced IP %16s at location %08x" % (ip, loc))
            else :
                replace_ip = server_ip.ljust(16, "\x00")
                file = file[:loc] + replace_ip + file[loc+16:]
                log.debug(filename + ": Found and replaced IP %16s at location %08x" % (ip, loc))
    
    if not config["server_ip"] == "127.0.0.1" :
        for ip in globalvars.loopback_ips :
            loc = file.find(ip)
            if loc != -1 :
                if network == "lan" :
                    replace_ip = server_ip.ljust(16, "\x00")
                    file = file[:loc] + replace_ip + file[loc+16:]
                    log.debug(filename + ": Found and replaced IP %16s at location %08x" % (ip, loc))
                #elif config["public_ip"] != "0.0.0.0" :
                elif network == "wan" :
                    server_ip = config["public_ip"]
                    replace_ip = server_ip.ljust(16, "\x00")
                    file = file[:loc] + replace_ip + file[loc+16:]
                    log.debug(filename + ": Found and replaced IP %16s at location %08x" % (ip, loc))
                else :
                    replace_ip = server_ip.ljust(16, "\x00")
                    file = file[:loc] + replace_ip + file[loc+16:]
                    log.debug(filename + ": Found and replaced IP %16s at location %08x" % (ip, loc))
            
    if not config["http_port"] == "steam" :
        if network == "lan" :
            #fullstring = globalvars.replacestrings_name_space
            fullstring = globalvars.replace_string_name_space("lan")
        #elif config["public_ip"] != "0.0.0.0" :
        elif network == "wan" :
            #fullstring = globalvars.replacestrings_name_space_ext
            fullstring = globalvars.replace_string_name_space("wan")
        else :
            #fullstring = globalvars.replacestrings_name_space
            fullstring = globalvars.replace_string_name_space("lan")
        
        for (search, replace, info) in fullstring :
            try :
                if file.find(search) != -1 :
                    if search == "StorefrontURL1" :
                        if ":2004" in config["store_url"] :
                            file = file.replace(search, replace)
                            log.debug(filename + ": Replaced " + info)
                    else :
                        fulllength = len(search)
                        newlength = len(replace)
                        missinglength = fulllength - newlength
                        if missinglength < 0 :
                            log.warn("WARNING: Replacement text " + replace + " is too long! Not replaced!")
                        elif missinglength == 0 :
                            file = file.replace(search, replace)
                            log.debug(filename + ": Replaced " + info)
                        else :
                            file = file.replace(search, replace + ('\x20' * missinglength))
                            log.debug(filename + ": Replaced " + info)
            except notfound :
                log.debug("Config line not found")
            
    if not config["http_port"] == "steam" :
        if network == "lan" :
            #fullstring = globalvars.replacestrings_name
            fullstring = globalvars.replace_string_name("lan")
        #elif config["public_ip"] != "0.0.0.0" :
        elif network == "wan" :
            #fullstring = globalvars.replacestrings_name_ext
            fullstring = globalvars.replace_string_name("wan")
        else :
            #fullstring = globalvars.replacestrings_name
            fullstring = globalvars.replace_string_name("lan")
        
        for (search, replace, info) in fullstring :
            try :
                if file.find(search) != -1 :
                    if search == "StorefrontURL1" :
                        if ":2004" in config["store_url"] :
                            file = file.replace(search, replace)
                            log.debug(filename + ": Replaced " + info)
                    else :
                        fulllength = len(search)
                        newlength = len(replace)
                        missinglength = fulllength - newlength
                        if missinglength < 0 :
                            log.warn("WARNING: Replacement text " + replace + " is too long! Not replaced!")
                        elif missinglength == 0 :
                            file = file.replace(search, replace)
                            log.debug(filename + ": Replaced " + info)
                        else :
                            file = file.replace(search, replace + ('\x00' * missinglength))
                            log.debug(filename + ": Replaced " + info)
            except notfound :
                log.debug("Config line not found")

    return file
    
def neuter(pkg_in, pkg_out, server_ip, server_port, network) :
    log = logging.getLogger("neuter")
    f = open(pkg_in, "rb")
    pkg = Package(f.read())
    f.close()
    
    for filename in filenames :
        if filename in pkg.filenames :
            file = pkg.get_file(filename)
            file = neuter_file(file, server_ip, server_port, filename, network)
            pkg.put_file(filename, file)
    if len(pkgadd_filelist) > 0 :
        del pkgadd_filelist[:]
        
    if (config["use_sdk"] == "0" and config["sdk_ip"] != "0.0.0.0") :
        sdk_line = 'SdkContentServerAdrs = "' + config["sdk_ip"] + ":" + config["sdk_port"] + '"'
        with open("files/pkg_add/steamui/Steam.cfg", "w") as f:
            f.write(sdk_line)
    else :
        try :
            os.remove("files/pkg_add/steamui/Steam.cfg")
        except :
            a = 1
            
    if os.path.isdir("files/pkg_add/") :
        log.debug("Found pkg_add folder")
        if os.path.isdir("files/pkg_add/steamui/") and ("SteamUI_" in pkg_in) :
            log.debug("Found steamui folder")
            path_to_remove = "files/pkg_add/steamui/"
            recursive_pkg("files/pkg_add/steamui/")
            log.debug("Number of files to add to SteamUI: " + str(len(pkgadd_filelist)))
            for filename_extra in pkgadd_filelist :
                file2 = open(filename_extra, "rb")
                filedata = file2.read()
                file2.close()
                filename_extra = filename_extra[len(path_to_remove):]
                pkg.put_file(filename_extra, filedata)
        elif os.path.isdir("files/pkg_add/steam/") and ("Steam_" in pkg_in) :
            log.debug("Found steam folder")
            path_to_remove = "files/pkg_add/steam/"
            recursive_pkg("files/pkg_add/steam/")
            log.debug("Number of files to add to Steam: " + str(len(pkgadd_filelist)))
            for filename_extra in pkgadd_filelist :
                file2 = open(filename_extra, "rb")
                filedata = file2.read()
                file2.close()
                filename_extra = filename_extra[len(path_to_remove):]
                pkg.put_file(filename_extra, filedata)

    f = open(pkg_out, "wb")
    f.write(pkg.pack())
    f.close()

def recursive_pkg(dir_in) :
    log = logging.getLogger("neuter")
    files = os.listdir(dir_in)
    for filename_extra in files:
        if os.path.isfile(os.path.join(dir_in,filename_extra)):
            pkgadd_filelist.append(os.path.join(dir_in,filename_extra))
        elif os.path.isdir(os.path.join(dir_in,filename_extra)):
            recursive_pkg(os.path.join(dir_in, filename_extra))
