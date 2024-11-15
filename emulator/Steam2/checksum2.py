import struct, zlib, os.path, logging, ConfigParser
from steamemu.config import read_config

config = read_config()

class Checksum2:
    def __init__(self, arg, ver):
        if type(arg) == int:
            appId = arg
            verId = ver
            with open(self.filename(appId, verId), "rb") as f:
                self.checksumdata = f.read()
        else:
            self.checksumdata = arg
        
        (formatcode, dummy, numfiles, totalchecksums) = struct.unpack("<LLLL", self.checksumdata[:16])

        self.numfiles = numfiles
        self.totalchecksums = totalchecksums
        self.checksumliststart = numfiles * 8 + 16

    def numchecksums(self, fileid) :
        checksumpointer = fileid * 8 + 16
        return struct.unpack("<L", self.checksumdata[checksumpointer:checksumpointer + 4])[0]

    def getchecksum(self, fileid, chunkid) :
        checksumpointer = fileid * 8 + 16
        checksumstart = struct.unpack("<L", self.checksumdata[checksumpointer + 4:checksumpointer + 8])[0]
        start = self.checksumliststart + (checksumstart + chunkid) * 4
        return struct.unpack("<i", self.checksumdata[start:start+4])[0]
    
    def getchecksums_raw(self, fileid):
        checksumpointer = fileid * 8 + 16
        (numchecksums, checksumstart) = struct.unpack("<LL", self.checksumdata[checksumpointer:checksumpointer + 8])
        start = self.checksumliststart + checksumstart * 4
        return self.checksumdata[start:start + numchecksums * 4]

    def validate(self, fileid, chunkid, chunk):
        crc = self.getchecksum(fileid, chunkid)
        crcb = zlib.adler32(chunk,0) ^ zlib.crc32(chunk,0)

        if crc != crcb :
            logging.warning("CRC error: %i %s %s" %  (fileid, hex(crc), hex(crcb)))
            return False
        else :
            return True

    @classmethod
    def filename(cls, appId, verId):
        if os.path.isfile("files/cache/" + str(appId) + "_" + str(verId) + "/" + str(appId) + ".checksums") :
            return os.path.join("files/cache/" + str(appId) + "_" + str(verId) + "/", "%i.checksums" % (appId))
        elif os.path.isfile(os.path.join(config["storagedir"], "%i.checksums" % (appId))) :
            return os.path.join(config["storagedir"], "%i.checksums" % (appId))
        elif os.path.isdir(config["v3manifestdir2"]) :
            if os.path.isfile(os.path.join(config["v3storagedir2"], "%i.checksums" % (appId))) :
                return os.path.join(config["v3storagedir2"], "%i.checksums" % (appId))
            else :
                log.error("Checksums not found for %s %s " % (appId, appVersion))
        else :
            log.error("Checksums not found for %s %s " % (appId, appVersion))
