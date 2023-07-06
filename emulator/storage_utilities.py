import binascii, ConfigParser, threading, logging, socket, time, os, shutil, zipfile, tempfile, zlib, sys
import os.path, ast, csv, struct
from index_utilities import readindexes, readindexes_old

from steamemu.config import read_config
config = read_config()

class Storage :
    def __init__(self, storagename, path, version) :
        self.name = str(storagename)
        self.ver = str(version)
        
        #if path.endswith("storages/") :
            #manifestpath = path[:-9] + "manifests/"
        manifestpathnew = config["manifestdir"]
        manifestpathold = config["v2manifestdir"]
        if os.path.isfile("files/cache/" + self.name + "_" + self.ver + "/" + self.name + "_" + self.ver + ".manifest") :
            self.indexfile  = "files/cache/" + self.name + "_" + self.ver + "/" + self.name + ".index"
            self.datafile   = "files/cache/" + self.name + "_" + self.ver + "/" + self.name + ".data"

            (self.indexes, self.filemodes) = readindexes(self.indexfile)
            self.new = True
        elif os.path.isfile(manifestpathold + self.name + "_" + self.ver + ".manifest") :
            self.indexfile  = config["v2storagedir"] + self.name + ".index"
            self.datafile   = config["v2storagedir"] + self.name + ".data"

            (self.indexes, self.filemodes) = readindexes_old(self.indexfile)
            self.new = False
        else :
            self.indexfile  = config["storagedir"] + self.name + ".index"
            self.datafile   = config["storagedir"] + self.name + ".data"

            (self.indexes, self.filemodes) = readindexes(self.indexfile)
            self.new = True
        self.f = False

    def readchunk(self, fileid, chunkid) :
        index = self.indexes[fileid]

        if not self.f :
            self.f = open(self.datafile, "rb")

        pos = chunkid * 16

        (start, length) = struct.unpack(">QQ", index[pos:pos+16])

        self.f.seek(start)
        file = self.f.read(length)

        return file, self.filemodes[fileid]

    def readchunks(self, fileid, chunkid, maxchunks) :

        if self.new :
            filechunks = []
            index = self.indexes[fileid]

            if not self.f :
                self.f = open(self.datafile, "rb")

            indexstart = chunkid * 16

            for pos in range(indexstart, len(index), 16) :
                (start, length) = struct.unpack(">QQ", index[pos:pos+16])

                self.f.seek(start)
                filechunks.append(self.f.read(length))

                maxchunks = maxchunks - 1

                if maxchunks == 0 :
                    break

            return filechunks, self.filemodes[fileid]
            
        else :
            filechunks = []
            index = self.indexes[fileid]

            f = open(self.datafile, "rb")

            indexstart = chunkid * 8

            for pos in range(indexstart, len(index), 8) :
                (start, length) = struct.unpack(">LL", index[pos:pos+8])

                f.seek(start)
                filechunks.append(f.read(length))

                maxchunks = maxchunks - 1

                if maxchunks == 0 :
                    break

            return filechunks, self.filemodes[fileid]

    def readfile(self, fileid) :

        filechunks = []
        index = self.indexes[fileid]

        if not self.f :
            self.f = open(self.datafile, "rb")

        for pos in range(0, len(index), 16) :
            (start, length) = struct.unpack(">QQ", index[pos:pos+16])

            self.f.seek(start)
            filechunks.append(self.f.read(length))

        return filechunks, self.filemodes[fileid]

    def writefile(self, fileid, filechunks, filemode) :

        if self.indexes.has_key(fileid) :
            print "FileID already exists!"
            sys.exit()

        if self.f :
            self.f.close()
            self.f = False
        f = open(self.datafile, "a+b")
        fi = open(self.indexfile, "ab")

        f.seek(0,2)                                 # this is a hack to get the f.tell() to show the correct position

        outindex = struct.pack(">QQQ", fileid, len(filechunks) * 16, filemode)

        for chunk in filechunks :
            outfilepos = f.tell()

            outindex = outindex + struct.pack(">QQ", outfilepos, len(chunk))

            f.write(chunk)

        fi.write(outindex)

        f.close()
        fi.close()

        self.indexes[fileid] = outindex[24:]
        self.filemodes[fileid] = filemode
        
    def close(self) :
        if self.f :
            self.f.close()
            self.f = False
