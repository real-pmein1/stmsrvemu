from zlib import decompress
from struct import unpack

def formatstring(text) :
    if len(text) == 4 and text[2] == "\x00" :
        return ("'\\x%02x\\x%02x\\x%02x\\x%02x'") % (ord(text[0]), ord(text[1]), ord(text[2]), ord(text[3]))
    else :
        return repr(text)

def blob_dump(blob, spacer = "") :

    text = spacer + "{"
    spacer2 = spacer + "    "

    try:
        blobkeys = blob.keys()
    except:
        blobkeys = {blob}
    #blobkeys.sort(sortfunc)
    first = True
    for key in blobkeys :

        data = blob[key]


        if type(data) == str :
            if first :
                text = text + "\n" + spacer2 + formatstring(key) + ": " + formatstring(data)
                first = False
            else :
                text = text + ",\n" + spacer2 + formatstring(key) + ": " + formatstring(data)
        else :
            if first :
                text = text + "\n" + spacer2 + formatstring(key) + ":\n" + blob_dump(data, spacer2)
                first = False
            else :
                text = text + ",\n" + spacer2 + formatstring(key) + ":\n" + blob_dump(data, spacer2)

    text = text + "\n" + spacer + "}"

    return text

def blob_unserialize(blobtext) :
    blobdict = {}
    (totalsize, slack) = unpack("<LL", blobtext[2:10])

    if slack :
        blobdict["__slack__"] = blobtext[-(slack):]


    if (totalsize + slack) != len(blobtext) :
        raise NameError("Blob not correct length including slack space!")
    index = 10
    while index < totalsize :
        namestart = index + 6
        (namesize, datasize) = unpack("<HL", blobtext[index:namestart])
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

def Blob2Dict(filename):
    with open(filename, 'rb') as f:
        thebytes = f.read()
        data = thebytes
        if thebytes[0:2] == "\x01\x43":
            data = decompress(thebytes[20:])
        return blob_unserialize(data)

def ReadBytes(thebytes):
    data = thebytes
    if thebytes[0:2] == "\x01\x43":
        data = decompress(thebytes[20:])
    data = blob_unserialize(data)
    SteamVersion = int.from_bytes(data[b'\x01\x00\x00\x00'], byteorder='little')
    SteamUI = int.from_bytes(data[b'\x02\x00\x00\x00'], byteorder='little')
    return [SteamVersion, SteamUI]

def ReadBlob(file):
    with open(file, 'rb') as f:
        data = f.read()
        f.close()
        if data[0:2] == "\x01\x43":
            data = decompress(data[20:])
        data = blob_unserialize(data)
        SteamVersion = int.from_bytes(data[b'\x01\x00\x00\x00'], byteorder='little')
        SteamUI = int.from_bytes(data[b'\x02\x00\x00\x00'], byteorder='little')
        return [SteamVersion, SteamUI]
        
#ReadBlob('./files/blobs/firstblob.bin.2004-08-26 19_46_45 (C)')