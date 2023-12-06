import os
from steamemu.config import read_config

config = read_config()

def create_dirs() :
#create folders
    try :
        os.mkdir(config["v2storagedir"])
    except :
        a = 0
    try :
        os.mkdir(config["v2manifestdir"])
    except :
        a = 0
    try :
        os.mkdir(config["storagedir"])
    except :
        a = 0
    try :
        os.mkdir(config["manifestdir"])
    except :
        a = 0
    try :
        os.mkdir(config["packagedir"])
    except :
        a = 0
    try :
        os.mkdir("logs")
        os.remove("emulator.log")
    except :
        a = 0
    try :
        os.mkdir("client")
    except :
        a = 0
    try :
        os.mkdir("files")
    except :
        a = 0
    try :
        os.mkdir("files/users")
    except :
        a = 0
    try :
        os.mkdir("files/temp")
    except :
        a = 0
    try :
        os.mkdir("files/convert")
    except :
        a = 0
    try :
        os.mkdir("files/cache")
    except :
        a = 0
    try :
        os.mkdir("client/cafe_server")
    except :
        a = 0