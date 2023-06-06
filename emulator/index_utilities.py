import os, struct

def readindexes(filename) :

    indexes = {}
    filemodes = {}

    if os.path.isfile(filename) :
        f = open(filename, "rb")
        indexdata = f.read()
        f.close()

        indexptr = 0

        while indexptr < len(indexdata) :

            (fileid, indexlen, filemode) = struct.unpack(">QQQ", indexdata[indexptr:indexptr+24])

            if indexlen :
                indexes[fileid] = indexdata[indexptr+24:indexptr+24+indexlen]
                filemodes[fileid] = filemode

            indexptr = indexptr + 24 + indexlen

    return indexes, filemodes
    
def readindexes_old(filename) :

    indexes = {}
    filemodes = {}

    if os.path.isfile(filename) :
        f = open(filename, "rb")
        indexdata = f.read()
        f.close()

        indexptr = 0

        while indexptr < len(indexdata) :

            (fileid, indexlen, filemode) = struct.unpack(">LLL", indexdata[indexptr:indexptr+12])

            if indexlen :
                indexes[fileid] = indexdata[indexptr+12:indexptr+12+indexlen]
                filemodes[fileid] = filemode

            indexptr = indexptr + 12 + indexlen

    return indexes, filemodes

