import binascii, ConfigParser, threading, logging, socket, time, os, shutil, zipfile, tempfile, zlib, sys
import os.path, ast, csv, struct
import dirs

from steamemu.config import read_config
config = read_config()

class Checksum :

    def __init__(self, checksumdata = "") :
        self.checksumdata = checksumdata

        if len(checksumdata) :
            self.initialize()

    def loadfromfile(self, filename) :
        f = open(filename, "rb")
        self.checksumdata = f.read()
        f.close()

        self.initialize()

    def initialize(self) :
        (dummy, dummy2, numfiles, totalchecksums) = struct.unpack("<LLLL", self.checksumdata[:16])

        self.numfiles = numfiles
        self.totalchecksums = totalchecksums
        self.checksumliststart = numfiles * 8 + 16

    def numchecksums(self, fileid) :
        checksumpointer = fileid * 8 + 16
        (numchecksums, checksumstart) = struct.unpack("<LL", self.checksumdata[checksumpointer:checksumpointer + 8])

        return numchecksums

    def getchecksum(self, fileid, chunkid) :
        checksumpointer = fileid * 8 + 16
        (numchecksums, checksumstart) = struct.unpack("<LL", self.checksumdata[checksumpointer:checksumpointer + 8])
        start = self.checksumliststart + (checksumstart + chunkid) * 4
        crc = struct.unpack("<i", self.checksumdata[start:start+4])[0]

        return crc

    def validate(self, fileid, chunkid, chunk) :

        crc = self.getchecksum(fileid, chunkid)
        crcb = valvecrc.crc(chunk, 0) ^ zlib.crc32(chunk, 0)

        if crc != crcb :
            logging.warning("CRC error: %i %s %s" %  (fileid, hex(crc), hex(crcb)))
            return False
        else :
            return True
