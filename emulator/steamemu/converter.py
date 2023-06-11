import os, ConfigParser, threading, logging, socket, time
import globalvars
from gcf_to_storage import gcf2storage
from Steam.manifest import Manifest
from Steam2.neuter import neuter_file
from steamemu.config import read_config

config = read_config()

def convertgcf() :
    log = logging.getLogger("converter")
    makeenc = Manifest()
    #makeenc.make_encrypted("files/convert/206_1.manifest")
    #makeenc.make_encrypted("files/convert/207_1.manifest")
    #makeenc.make_encrypted("files/convert/208_1.manifest")
    #makeenc.make_encrypted("files/convert/221_0.manifest")
    #makeenc.make_encrypted("files/convert/281_0.manifest")
    for filename in os.listdir("files/convert/") :
        if str(filename.endswith(".gcf")) :
            dirname = filename[0:-4]
            if not os.path.isfile("files/cache/" + dirname + "/" + dirname + ".manifest") :
                log.info("Found " + filename + " to convert")
                log.info("Fixing files in " + dirname)
                print "****************************************"
                g = open("files/convert/" + dirname + ".gcf", "rb")
                file = g.read()
                g.close()
                if filename.startswith("0_") or filename.startswith("3_") or filename.startswith("5_") or filename.startswith("212_") :
                    if config["public_ip"] != "0.0.0.0" :
                        for (search, replace, info) in globalvars.replacestrings2003ext :
                            fulllength = len(search)
                            newlength = len(replace)
                            missinglength = fulllength - newlength
                            if missinglength < 0 :
                                print("WARNING: Cannot replace " + info + " " + search + " with " + replace + " as it's too long")
                            elif missinglength == 0 :
                                file = file.replace(search, replace)
                                print("Replaced " + info + " " + search + " with " + replace)
                            else :
                                file = file.replace(search, replace + ('\x00' * missinglength))
                                print("Replaced " + info + " " + search + " with " + replace)
                    else :
                        for (search, replace, info) in globalvars.replacestrings2003 :
                            fulllength = len(search)
                            newlength = len(replace)
                            missinglength = fulllength - newlength
                            if missinglength < 0 :
                                print("WARNING: Cannot replace " + info + " " + search + " with " + replace + " as it's too long")
                            elif missinglength == 0 :
                                file = file.replace(search, replace)
                                print("Replaced " + info + " " + search + " with " + replace)
                            else :
                                file = file.replace(search, replace + ('\x00' * missinglength))
                                print("Replaced " + info + " " + search + " with " + replace)
                else :
                    if config["public_ip"] != "0.0.0.0" :
                        for (search, replace, info) in globalvars.replacestringsext :
                            fulllength = len(search)
                            newlength = len(replace)
                            missinglength = fulllength - newlength
                            if missinglength < 0 :
                                print("WARNING: Cannot replace " + info + " " + search + " with " + replace + " as it's too long")
                            elif missinglength == 0 :
                                file = file.replace(search, replace)
                                print("Replaced " + info + " " + search + " with " + replace)
                            else :
                                file = file.replace(search, replace + ('\x00' * missinglength))
                                print("Replaced " + info + " " + search + " with " + replace)
                    else :
                        for (search, replace, info) in globalvars.replacestrings :
                            fulllength = len(search)
                            newlength = len(replace)
                            missinglength = fulllength - newlength
                            if missinglength < 0 :
                                print("WARNING: Cannot replace " + info + " " + search + " with " + replace + " as it's too long")
                            elif missinglength == 0 :
                                file = file.replace(search, replace)
                                print("Replaced " + info + " " + search + " with " + replace)
                            else :
                                file = file.replace(search, replace + ('\x00' * missinglength))
                                print("Replaced " + info + " " + search + " with " + replace)

                search = "207.173.177.11:27030 207.173.177.12:27030 69.28.151.178:27038 69.28.153.82:27038 68.142.88.34:27038 68.142.72.250:27038"
                if config["public_ip"] != "0.0.0.0" :
                    ip = config["public_ip"] + ":" + config["dir_server_port"] + " " + config["server_ip"] + ":" + config["dir_server_port"] + " "
                else :
                    ip = config["server_ip"] + ":" + config["dir_server_port"] + " "
                searchlength = len(search)
                iplength = len(ip)
                numtoreplace = searchlength // iplength
                ips = ip * numtoreplace
                replace = ips.ljust(searchlength, '\x00')
                if file.find(search) != -1 :
                    file = file.replace(search, replace)
                    print "Replaced directory server IP group 1"

                search = "207.173.177.11:27030 207.173.177.12:27030"
                if config["public_ip"] != "0.0.0.0" :
                    ip = config["public_ip"] + ":" + config["dir_server_port"] + " " + config["server_ip"] + ":" + config["dir_server_port"] + " "
                else :
                    ip = config["server_ip"] + ":" + config["dir_server_port"] + " "
                searchlength = len(search)
                iplength = len(ip)
                numtoreplace = searchlength // iplength
                ips = ip * numtoreplace
                replace = ips.ljust(searchlength, '\x00')
                if file.find(search) != -1 :
                    file = file.replace(search, replace)
                    print "Replaced directory server IP group 5"

                search = "hlmaster1.hlauth.net:27010"
                if config["public_ip"] != "0.0.0.0" :
                    ip = config["public_ip"] + ":27010"
                else :
                    ip = config["server_ip"] + ":27010"
                searchlength = len(search)
                iplength = len(ip)
                numtoreplace = searchlength // iplength
                ips = ip * numtoreplace
                replace = ips.ljust(searchlength, '\x00')
                if file.find(search) != -1 :
                    file = file.replace(search, replace)
                    print "Replaced default HL Master server DNS"

                search = "207.173.177.11:27010"
                if config["public_ip"] != "0.0.0.0" :
                    ip = config["public_ip"] + ":27010"
                else :
                    ip = config["server_ip"] + ":27010"
                searchlength = len(search)
                iplength = len(ip)
                numtoreplace = searchlength // iplength
                ips = ip * numtoreplace
                replace = ips.ljust(searchlength, '\x00')
                if file.find(search) != -1 :
                    file = file.replace(search, replace)
                    print "Replaced default HL Master server IP 1"

                search = "207.173.177.12:27010"
                if config["public_ip"] != "0.0.0.0" :
                    ip = config["public_ip"] + ":27010"
                else :
                    ip = config["server_ip"] + ":27010"
                searchlength = len(search)
                iplength = len(ip)
                numtoreplace = searchlength // iplength
                ips = ip * numtoreplace
                replace = ips.ljust(searchlength, '\x00')
                if file.find(search) != -1 :
                    file = file.replace(search, replace)
                    print "Replaced default HL Master server IP 2"

                search = "207.173.177.11:27011"
                if config["public_ip"] != "0.0.0.0" :
                    ip = config["public_ip"] + ":27011"
                else :
                    ip = config["server_ip"] + ":27011"
                searchlength = len(search)
                iplength = len(ip)
                numtoreplace = searchlength // iplength
                ips = ip * numtoreplace
                replace = ips.ljust(searchlength, '\x00')
                if file.find(search) != -1 :
                    file = file.replace(search, replace)
                    print "Replaced default HL2 Master server IP 1"

                search = "207.173.177.12:27011"
                if config["public_ip"] != "0.0.0.0" :
                    ip = config["public_ip"] + ":27011"
                else :
                    ip = config["server_ip"] + ":27011"
                searchlength = len(search)
                iplength = len(ip)
                numtoreplace = searchlength // iplength
                ips = ip * numtoreplace
                replace = ips.ljust(searchlength, '\x00')
                if file.find(search) != -1 :
                    file = file.replace(search, replace)
                    print "Replaced default HL2 Master server IP 2"

                if config["tracker_ip"] != "0.0.0.0" :
                    search = "tracker.valvesoftware.com:1200"
                    ip = config["tracker_ip"] + ":1200"
                    searchlength = len(search)
                    iplength = len(ip)
                    numtoreplace = searchlength // iplength
                    ips = ip * numtoreplace
                    replace = ips.ljust(searchlength, '\x00')
                    if file.find(search) != -1 :
                        file = file.replace(search, replace)
                        print "Replaced Tracker Chat server DNS"

                if config["tracker_ip"] != "0.0.0.0" :
                    search = '"207.173.177.42:1200"'
                    ip = '"' + config["tracker_ip"] + ':1200"'
                    searchlength = len(search)
                    iplength = len(ip)
                    numtoreplace = searchlength // iplength
                    ips = ip * numtoreplace
                    replace = ips.ljust(searchlength, '\x00')
                    if file.find(search) != -1 :
                        file = file.replace(search, replace)
                        print "Replaced Tracker Chat server 1"

                if config["tracker_ip"] != "0.0.0.0" :
                    search = '"207.173.177.43:1200"'
                    ip = '"' + config["tracker_ip"] + ':1200"'
                    searchlength = len(search)
                    iplength = len(ip)
                    numtoreplace = searchlength // iplength
                    ips = ip * numtoreplace
                    replace = ips.ljust(searchlength, '\x00')
                    if file.find(search) != -1 :
                        file = file.replace(search, replace)
                        print "Replaced Tracker Chat server 2"

                if config["tracker_ip"] != "0.0.0.0" :
                    search = '"207.173.177.44:1200"'
                    ip = '"' + config["tracker_ip"] + ':1200"'
                    searchlength = len(search)
                    iplength = len(ip)
                    numtoreplace = searchlength // iplength
                    ips = ip * numtoreplace
                    replace = ips.ljust(searchlength, '\x00')
                    if file.find(search) != -1 :
                        file = file.replace(search, replace)
                        print "Replaced Tracker Chat server 3"

                if config["tracker_ip"] != "0.0.0.0" :
                    search = '"207.173.177.45:1200"'
                    ip = '"' + config["tracker_ip"] + ':1200"'
                    searchlength = len(search)
                    iplength = len(ip)
                    numtoreplace = searchlength // iplength
                    ips = ip * numtoreplace
                    replace = ips.ljust(searchlength, '\x00')
                    if file.find(search) != -1 :
                        file = file.replace(search, replace)
                        print "Replaced Tracker Chat server 4"
                    
                for extraip in globalvars.extraips :
                    loc = file.find(extraip)
                    if loc != -1 :
                        if config["public_ip"] != "0.0.0.0" :
                            server_ip = config["public_ip"]
                            replace_ip = server_ip.ljust(16, "\x00")
                            file = file[:loc] + replace_ip + file[loc+16:]
                            print "Found and replaced IP %s at location %08x" % (extraip, loc)
                        else :
                            server_ip = config["server_ip"]
                            replace_ip = server_ip.ljust(16, "\x00")
                            file = file[:loc] + replace_ip + file[loc+16:]
                            print "Found and replaced IP %s at location %08x" % (extraip, loc)
                    
                for ip in globalvars.ip_addresses :
                    loc = file.find(ip)
                    if loc != -1 :
                        if config["public_ip"] != "0.0.0.0" :
                            server_ip = config["public_ip"]
                            replace_ip = server_ip.ljust(16, "\x00")
                            file = file[:loc] + replace_ip + file[loc+16:]
                            print "Found and replaced IP %16s at location %08x" % (ip, loc)
                        else :
                            server_ip = config["server_ip"]
                            replace_ip = server_ip.ljust(16, "\x00")
                            file = file[:loc] + replace_ip + file[loc+16:]
                            print "Found and replaced IP %16s at location %08x" % (ip, loc)

                time.sleep(1)
                h = open("files/temp/" + dirname + ".neutered.gcf", "wb")
                h.write(file)
                h.close()
                time.sleep(1)
                gcf2storage("files/temp/" + dirname + ".neutered.gcf")
                time.sleep(1)
                os.remove("files/temp/" + dirname + ".neutered.gcf")
                print "****************************************"
