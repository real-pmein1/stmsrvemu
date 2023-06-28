import struct

class Application :
    pass

def get_app_list(blob) :
    subblob = blob["\x01\x00\x00\x00"]

    app_list = {}

    for appblob in subblob :
        app = Application()
        app.id          = struct.unpack("<L", appblob)[0]
        app.binid       = appblob
        app.version     = struct.unpack("<L", subblob[appblob]["\x0b\x00\x00\x00"])[0]
        app.size        = struct.unpack("<L", subblob[appblob]["\x05\x00\x00\x00"])[0]
        app.name        = subblob[appblob]["\x02\x00\x00\x00"][:-1]

        if subblob[appblob]["\x10\x00\x00\x00"] == "\xff\xff\xff\xff" :
            app.betaversion = app.version
        else :
            app.betaversion = struct.unpack("<L", subblob[appblob]["\x10\x00\x00\x00"])[0]

        app_list[app.id] = app

    return app_list






