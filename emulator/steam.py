import myimports
import binascii, ConfigParser, threading, logging, socket, time, os, shutil, zipfile, tempfile, zlib, sys
import os.path, ast, csv, struct

from steamemu.config import read_config
config = read_config()

class Application :
    "Empty class that acts as a placeholder"
    pass


def get_apps_list(blob) :
    subblob = blob["\x01\x00\x00\x00"]

    apps = {}

    for appblob in subblob :

        app = Application()
        app.binid = appblob
        app.id = struct.unpack("<L", appblob)[0]
        app.version = struct.unpack("<L", subblob[appblob]["\x0b\x00\x00\x00"])[0]
        app.size = struct.unpack("<L", subblob[appblob]["\x05\x00\x00\x00"])[0]
        app.name = subblob[appblob]["\x02\x00\x00\x00"]

        apps[app.id] = app

    return apps


