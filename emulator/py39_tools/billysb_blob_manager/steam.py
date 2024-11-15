from filecmp import cmp
from struct import unpack

def blob_read(filepath):
    f = open(filepath, 'rb')
    data = f.read()
    f.close()

    return blob_dump(blob_unserialize(data))
    

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

def sortfunc(x, y) :

    if len(x) == 4 and x[2] == "\x00" :
        if len(y) == 4 and y[2] == "\x00" :
            numx = unpack("<L", x)[0]
            numy = unpack("<L", y)[0]
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

def blob_dump(blob, spacer = "") :

    text = spacer + "{"
    spacer2 = spacer + "    "

    blobkeys = blob.keys()
    blobkeys.sort(sortfunc)
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
