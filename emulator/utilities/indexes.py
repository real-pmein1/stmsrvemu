import os
import struct


def readindexes(filename):
    indexes = {}
    filemodes = {}

    if os.path.isfile(filename):
        with open(filename, "rb") as f:
            indexdata = f.read()

        indexptr = 0

        while indexptr < len(indexdata):

            (fileid, indexlen, filemode) = struct.unpack(">QQQ", indexdata[indexptr:indexptr + 24])

            if indexlen:
                indexes[fileid] = indexdata[indexptr + 24:indexptr + 24 + indexlen]
                filemodes[fileid] = filemode

            indexptr = indexptr + 24 + indexlen

    return indexes, filemodes


def readindexes_old(filename):
    indexes = {}
    filemodes = {}

    if os.path.isfile(filename):
        f = open(filename, "rb")
        indexdata = f.read()
        f.close()

        indexptr = 0

        while indexptr < len(indexdata):

            (fileid, indexlen, filemode) = struct.unpack(">LLL", indexdata[indexptr:indexptr + 12])

            if indexlen:
                indexes[fileid] = indexdata[indexptr + 12:indexptr + 12 + indexlen]
                filemodes[fileid] = filemode

            indexptr = indexptr + 12 + indexlen

    return indexes, filemodes


def readindexes_tane(filename):
    indexes = {}
    filemodes = {}

    if os.path.isfile(filename):
        f = open(filename, "rb")
        indexdata = f.read()
        f.close()

        indexptr = 0

        while indexptr < len(indexdata):

            (fileid, indexlen, filemode) = struct.unpack(">LLQ", indexdata[indexptr:indexptr + 16])

            if indexlen:
                indexes[fileid] = indexdata[indexptr + 16:indexptr + 16 + indexlen]
                filemodes[fileid] = filemode

            indexptr = indexptr + 16 + indexlen

    return indexes, filemodes