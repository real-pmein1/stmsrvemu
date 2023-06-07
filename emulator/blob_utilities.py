import binascii, ConfigParser, zlib, sys
import os.path, ast, csv, struct, utilities

import dirs, globalvars
from Steam2.package import Package

def blob_dump(blob, spacer = "") :

    text = spacer + "{"
    spacer2 = spacer + "    "

    blobkeys = blob.keys()
    blobkeys.sort(utilities.sortfunc)
    first = True
    for key in blobkeys :

        data = blob[key]


        if type(data) == str :
            if first :
                text = text + "\n" + spacer2 + utilities.formatstring(key) + ": " + utilities.formatstring(data)
                first = False
            else :
                text = text + ",\n" + spacer2 + utilities.formatstring(key) + ": " + utilities.formatstring(data)
        else :
            if first :
                text = text + "\n" + spacer2 + utilities.formatstring(key) + ":\n" + blob_dump(data, spacer2)
                first = False
            else :
                text = text + ",\n" + spacer2 + utilities.formatstring(key) + ":\n" + blob_dump(data, spacer2)

    text = text + "\n" + spacer + "}"

    return text



def blob_unserialize(blobtext) :
    blobdict = {}
    (totalsize, slack) = struct.unpack("<LL", blobtext[2:10])

    if slack :
        blobdict["__slack__"] = blobtext[-(slack):]
    if (totalsize + slack) != len(blobtext) :
        raise NameError, "Blob not correct length including slack space!"
    index = 10
    while index < totalsize :
        namestart = index + 6
        (namesize, datasize) = struct.unpack("<HL", blobtext[index:namestart])
        datastart = namestart + namesize
        name = blobtext[namestart:datastart]
        dataend = datastart + datasize
        data = blobtext[datastart:dataend]
        if len(data) > 1 and data[0] == chr(0x01) and data[1] == chr (0x50) :
            sub_blob = blob_unserialize(data)
            blobdict[name] = sub_blob
        else :
            blobdict[name] = data
        index = index + 6 + namesize + datasize

    return blobdict

def blob_serialize(blobdict) :

    blobtext = ""

    for (name, data) in blobdict.iteritems() :

        if name == "__slack__" :
            continue

        if type(data) == dict :

            data = blob_serialize(data)

        namesize = len(name)

        datasize = len(data)

        subtext = struct.pack("<HL", namesize, datasize)

        subtext = subtext + name + data

        blobtext = blobtext + subtext

    if blobdict.has_key("__slack__") :
        slack = blobdict["__slack__"]
    else :
        slack = ""

    totalsize = len(blobtext) + 10

    sizetext = struct.pack("<LL", totalsize, len(slack))

    blobtext = chr(0x01) + chr(0x50) + sizetext + blobtext + slack

    return blobtext
