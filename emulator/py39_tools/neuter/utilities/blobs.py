import struct
import zlib

from utils import sortkey, formatstring


class Application:
    "Empty class that acts as a placeholder"
    pass


def get_app_list(blob) :
    subblob = blob[b"\x01\x00\x00\x00"]

    app_list = {}

    for appblob in subblob :
        app = Application()
        app.id          = struct.unpack("<L", appblob)[0]
        app.binid       = appblob
        app.version     = struct.unpack("<L", subblob[appblob][b"\x0b\x00\x00\x00"])[0]
        app.size        = struct.unpack("<L", subblob[appblob][b"\x05\x00\x00\x00"])[0]
        app.name        = subblob[appblob][b"\x02\x00\x00\x00"][:-1]

        if b"\x10\x00\x00\x00" in subblob[appblob] :
            if subblob[appblob][b"\x10\x00\x00\x00"] == b"\xff\xff\xff\xff" :
                app.betaversion = app.version
            else :
                app.betaversion = struct.unpack("<L", subblob[appblob][b"\x10\x00\x00\x00"])[0]
        else :
            app.betaversion = app.version

        app_list[app.id] = app

    return app_list


def blob_unserialize(blobtext):
    if blobtext[0:2] == b"\x01\x43":
        # print("decompress")
        blobtext = zlib.decompress(blobtext[20:])

    blobdict = {}
    (totalsize, slack) = struct.unpack("<LL", blobtext[2:10])

    if slack:
        blobdict[b"__slack__"] = blobtext[-slack:]
    if (totalsize + slack) != len(blobtext):
        raise NameError("Blob not correct length including slack space!")
    index = 10
    while index < totalsize:
        namestart = index + 6
        (namesize, datasize) = struct.unpack("<HL", blobtext[index:namestart])
        datastart = namestart + namesize
        name = blobtext[namestart:datastart]
        dataend = datastart + datasize
        data = blobtext[datastart:dataend]
        if len(data) > 1 and data[0:2] == b"\x01\x50":
            sub_blob = blob_unserialize(data)
            blobdict[name] = sub_blob
        else:
            blobdict[name] = data
        index = index + 6 + namesize + datasize

    return blobdict


def blob_dump(blob, spacer = ""):
    text = spacer + "{"
    spacer2 = spacer + "    "
    blobkeys = list(blob.keys())
    blobkeys.sort(key = sortkey)
    first = True
    for key in blobkeys:

        data = blob[key]
        if isinstance(data, dict):
            formatted_key = formatstring(key)
            formatted_data = blob_dump(data, spacer2)
        else:
            # Assuming formatstring handles other types appropriately
            formatted_key = formatstring(key)
            formatted_data = formatstring(data)

        if first:

            text += "" + spacer2 + formatted_key + ": " + formatted_data
            first = False
        else:
            text += "," + spacer2 + formatted_key + ": " + formatted_data

    text += spacer + "}"
    return text