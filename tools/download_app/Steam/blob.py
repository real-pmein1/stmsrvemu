import struct, zlib

def load_from_file(filename) :
    f = open(filename, "rb")
    blob_bin = f.read()
    f.close()
    
    if blob_bin[0:2] == "\x01\x43" :
        blob_bin = zlib.decompress(blob_bin[20:])

    return unserialize(blob_bin)

def unserialize(blobtext) :
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
            sub_blob = unserialize(data)
            blobdict[name] = sub_blob
        else :
            blobdict[name] = data
        index = index + 6 + namesize + datasize

    return blobdict

def serialize(blobdict) :

    blobtext = ""

    for (name, data) in blobdict.iteritems() :

        if name == "__slack__" :
            continue

        if type(data) == dict :

            data = serialize(data)

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

def dump(blob, sort = True, spacer = "") :

    text = spacer + "{\n"

    blobkeys = blob.keys()

    if sort :
        blobkeys.sort(sortfunc)

    for key in blobkeys :

        name = formatstring(key)
        data = blob[key]

        spacer2 = spacer + name + " "

        if type(data) == str :
            text += spacer2 + formatstring(data) + "\n"
        else :
            text += dump(data, sort, spacer2)

    text += spacer + "}\n"

    return text

def dump_to_dict(blob, sort = True, spacer = "") :

    text = spacer + "{"
    spacer2 = spacer + "    "

    blobkeys = blob.keys()

    if sort :
        blobkeys.sort(sortfunc)

    first = True
    for key in blobkeys :

        name = formatstring(key)
        data = blob[key]

        if type(data) == str :
            if not first :
                text += ","
            else :
                first = False

            text += "\n" + spacer2 + name + ": " + formatstring(data)
        else :
            if not first :
                text += ","
            else :
                first = False

            text += "\n" + spacer2 + name + ":\n" + dump_to_dict(data, sort, spacer2)

    text += "\n" + spacer + "}"

    return text

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

def formatstring(text) :
    if len(text) == 4 and text[2] == "\x00" :
        return ("'\\x%02x\\x%02x\\x%02x\\x%02x'") % (ord(text[0]), ord(text[1]), ord(text[2]), ord(text[3]))
    else :
        return repr(text)
