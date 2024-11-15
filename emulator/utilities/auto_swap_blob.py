import os
import shutil
import logging
import sys
from datetime import datetime

import utilities.time
import utils
import globalvars
from config import get_config
from utilities.database import ccdb

config = get_config()

def swap_blobs():
    #print("Current datetime = " + str(datetime.now().strftime("%Y-%m-%d %H_%M_%S")))
    
    subtract_time = config["subtract_time"]
    
    years = subtract_time
    months = 0
    days = 0

    if ("y" or "m" or "d") in subtract_time:
        year_pos = subtract_time.find("y") + 1
        month_pos = subtract_time.find("m") + 1
        day_pos = subtract_time.find("d") + 1
        #print(year_pos)
        #print(month_pos)
        #print(day_pos)

        dct = {"y": year_pos, "m": month_pos, "d": day_pos}
        dct = dict(sorted(dct.items(), key=lambda item: item[1]))
        #print(dct)

        pos_list = list(dct.keys())

        if "y" in dct:
            pos = list(dct).index('y') #index
            if pos == 2:
                years = subtract_time[year_pos:]
            else:
                next_pos = (dct[pos_list[list(dct).index('y') + 1]] - 1) - year_pos
                years = subtract_time[year_pos:year_pos + next_pos]

        if "m" in dct:
            pos = list(dct).index('m') #index
            if pos == 2:
                months = subtract_time[month_pos:]
            else:
                next_pos = (dct[pos_list[list(dct).index('m') + 1]] - 1) - month_pos
                months = subtract_time[month_pos:month_pos + next_pos]

        if "d" in dct:
            pos = list(dct).index('d') #index
            if pos == 2:
                days = subtract_time[day_pos:]
            else:
                next_pos = (dct[pos_list[list(dct).index('d') + 1]] - 1) - day_pos
                days = subtract_time[day_pos:day_pos + next_pos]

    if years == "": years = 0
    if months == "": months = 0
    if days == "": days = 0

    try:
        newdate = utilities.time.sub_yrs(utilities.time.get_current_datetime_blob(), -abs(int(years)), -abs(int(months)), -abs(int(days)))[:-9].replace("-", "")
    except:
        print("WARN: invalid format, defaulting to current date")
        newdate = utilities.time.sub_yrs()[:-9].replace("-", "")

    if os.path.isdir(config["blobdir"] + "clientconfigrecords"):
        cdr_blob_path = config["blobdir"] + "clientconfigrecords"
        blobfilelist = sorted(os.listdir(cdr_blob_path))
        
        status = "bad"

        while status != "ok":
            for file in reversed(blobfilelist):
                if file.startswith("firstblob.bin."):
                    filedate = file[14:24].replace("-", "")
                    if filedate < newdate:
                        if not os.path.isfile("files/firstblob.bin"):
                            with open("files/firstblob.bin", 'w') as f:
                                pass

                        if os.path.getmtime(config["blobdir"] + "clientconfigrecords/" + file) != os.path.getmtime("files/firstblob.bin"):
                            print("Changing to ccdb: " + file)

                            try:
                                os.remove("files/firstblob.bin")
                            except:
                                pass
                            shutil.copy2(config["blobdir"] + "clientconfigrecords/" + file, "files/firstblob.bin")

                            ccdb.load_filesys_blob()

                        if globalvars.record_ver == 0:
                            steam_pkg_file = f"{config['packagedir']}betav1/Steam_{globalvars.steam_ver}.pkg"
                            if os.path.exists(steam_pkg_file):
                                status = "ok"
                            else:
                                status = "missing"
                        elif globalvars.record_ver == 1:
                            steam_pkg_file = f"{config['packagedir']}betav2/Steam_{globalvars.steam_ver}.pkg"
                            steamui_pkg_file = f"{config['packagedir']}betav2/PLATFORM_{globalvars.steamui_ver}.pkg"
                            if os.path.exists(steam_pkg_file):
                                status = "ok"
                                if os.path.exists(steamui_pkg_file):
                                    status = "ok"
                                else:
                                    status = "missing"
                            else:
                                status = "missing"
                        else:
                            steam_pkg_file = f"{config['packagedir']}Steam_{globalvars.steam_ver}.pkg"
                            steamui_pkg_file = f"{config['packagedir']}SteamUI_{globalvars.steamui_ver}.pkg"
                            if os.path.exists(steam_pkg_file):
                                status = "ok"
                                if os.path.exists(steamui_pkg_file):
                                    status = "ok"
                                else:
                                    status = "missing"
                            else:
                                status = "missing"
                        if status == "ok":
                            break
                        elif filedate == "20030113":
                            sys.exit("Last blob reached, no pkgs found")
    
    if os.path.isdir(config["blobdir"] + "contentdescriptionrecords"):
        cdr_blob_path = config["blobdir"] + "contentdescriptionrecords"
        blobfilelist = sorted(os.listdir(cdr_blob_path))

        for file in reversed(blobfilelist):
            if file.startswith("secondblob.bin."):
                filedate = file[15:25].replace("-", "")
                if filedate < newdate:
                    if not os.path.isfile("files/secondblob.bin"):
                        with open("files/secondblob.bin", 'w') as f:
                            pass

                    if os.path.getmtime(config["blobdir"] + "contentdescriptionrecords/" + file) != os.path.getmtime("files/secondblob.bin"):
                        print("Changing to cddb: " + file)
                        try:
                            os.remove("files/secondblob.bin")
                        except:
                            pass
                        try:
                            os.remove("files/cache/secondblob_lan.bin")
                        except:
                            pass
                        try:
                            os.remove("files/cache/secondblob_wan.bin")
                        except:
                            pass
                        shutil.copy2(config["blobdir"] + "contentdescriptionrecords/" + file, "files/secondblob.bin")
                    break