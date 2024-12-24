import struct, zlib, os

def readindexes(filename) :

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

class Storage :
    def __init__(self, storagename, path) :
        self.name = str(storagename)

        self.indexfile  = path + self.name + ".orig.index"
        self.datafile   = path + self.name + ".data"

        (self.indexes, self.filemodes) = readindexes(self.indexfile)
        
        self.f = False
        self.w = False

    def readchunk(self, fileid, chunkid) :
        index = self.indexes[fileid]

        if not self.f :
            self.f = open(self.datafile, "rb")

        pos = chunkid * 8

        (start, length) = struct.unpack(">LL", index[pos:pos+8])

        self.f.seek(start)
        file = self.f.read(length)

        return file, self.filemodes[fileid]

    def readchunks(self, fileid, chunkid, maxchunks) :

        filechunks = []
        index = self.indexes[fileid]

        if not self.f :
            self.f = open(self.datafile, "rb")

        indexstart = chunkid * 8

        for pos in range(indexstart, len(index), 8) :
            (start, length) = struct.unpack(">LL", index[pos:pos+8])

            self.f.seek(start)
            filechunks.append(self.f.read(length))

            maxchunks = maxchunks - 1

            if maxchunks == 0 :
                break

        return filechunks, self.filemodes[fileid]

    def readfile(self, fileid) :

        filechunks = []
        index = self.indexes[fileid]

        if not self.f :
            self.f = open(self.datafile, "rb")

        for pos in range(0, len(index), 8) :
            (start, length) = struct.unpack(">LL", index[pos:pos+8])

            self.f.seek(start)
            filechunks.append(self.f.read(length))

        return filechunks, self.filemodes[fileid]

    def writefile(self, fileid, filechunks, filemode, filechunks_wan, path, version, ) :

        if self.f :
            self.f.close()
            self.f = False
        if self.w :
            self.w.close()
            self.w = False
        if not os.path.isfile(path + self.name + "_" + str(fileid) + "_lan.data"):
            f = open(path + self.name + "_" + str(fileid) + "_lan.data", "a+b")
        if not os.path.isfile(path + self.name + "_" + str(fileid) + "_wan.data"):
            w = open(path + self.name + "_" + str(fileid) + "_wan.data", "a+b")
        fi = open(path + self.name + "_" + str(version) + "_lan.index", "ab")
        wi = open(path + self.name + "_" + str(version) + "_wan.index", "ab")

        f.seek(0,2)                                 # this is a hack to get the f.tell() to show the correct position
        w.seek(0,2)

        outindex = struct.pack(">LLL", fileid, len(filechunks) * 8, filemode)
        outindex_wan = struct.pack(">LLL", fileid, len(filechunks_wan) * 8, filemode)

        for chunk in filechunks :
            outfilepos = f.tell()
            outindex = outindex + struct.pack(">LL", outfilepos, len(chunk))
            f.write(chunk)

        for chunk_wan in filechunks_wan :
            outfilepos_wan = w.tell()
            outindex_wan = outindex_wan + struct.pack(">LL", outfilepos_wan, len(chunk_wan))
            w.write(chunk_wan)

        fi.write(outindex)
        wi.write(outindex_wan)

        f.close()
        fi.close()
        w.close()
        wi.close()

        self.indexes[fileid] = outindex[12:]
        self.filemodes[fileid] = filemode
        
    def close(self) :
        if self.f :
            self.f.close()
            self.f = False
        if self.w :
            self.w.close()
            self.w = False

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
        crc = struct.unpack("<I", self.checksumdata[start:start+4])[0]

        return crc

    def validate(self, fileid, chunkid, chunk) :

        crc = self.getchecksum(fileid, chunkid)
        crcb = zlib.adler32(chunk, 0) ^ zlib.crc32(chunk, 0)

        if crc != crcb :
            #logging.warning("CRC error: %i %s %s" %  (fileid, hex(crc), hex(crcb)))
            return False
        else :
            return True

    def validate_chunk(self, fileid, chunkid, chunk, checksums_filename):

        try:
            stored_crc = self.getchecksum(fileid, chunkid)
        except IndexError:
            #logging.error("Checksum error. Tried to check a chunkid that doesn't have a checksum. Chunk %s in file %s" % (chunkid, fileid))
            return False

        chunk_crc = zlib.adler32(chunk, 0) ^ zlib.crc32(chunk, 0)

        if stored_crc != chunk_crc:
            self.fix_crc(fileid, chunkid, chunk, checksums_filename)
            return False
        else:
            return True

    def fix_crc(self, fileid, chunkid, chunk, checksums_filename):
        #log = logging.getLogger("converter")
        clientid = ""
        f = open(checksums_filename, "rb")
        checksumdata = f.read()
        f.close()
        stored_crc = self.getchecksum(fileid, chunkid)
        chunk_crc = zlib.adler32(chunk, 0) ^ zlib.crc32(chunk, 0)

        (dummy, dummy2, numfiles, totalchecksums) = struct.unpack("<LLLL", checksumdata[:16])

        numfiles = numfiles
        totalchecksums = totalchecksums
        checksumliststart = numfiles * 8 + 16

        numchecksums = {}
        checksumstart = {}
        checksums = {}
        checksums_raw = {}
        checksumpointer = fileid * 8 + 16
        (numchecksums[fileid], checksumstart[fileid]) = struct.unpack("<LL", checksumdata[checksumpointer:checksumpointer + 8])

        filechecksums = []
        start = checksumliststart + checksumstart[fileid] * 4
        end = start + numchecksums[fileid] * 4
        checksums_raw[fileid] = checksumdata[start:end]
        checksumdatanew = checksumdata[0:start]
        checksumdatanew_temp = b""
        for i in range(numchecksums[fileid]):
            checksum = struct.unpack("<I", checksumdata[start:start + 4])[0]
            if checksum == stored_crc:
                checksumdatanew_temp = struct.pack("<I", chunk_crc)
                checksumdatanew = checksumdatanew + checksumdatanew_temp
            else:
                checksumdatanew_temp = struct.pack("<I", checksum)
                checksumdatanew = checksumdatanew + checksumdatanew_temp
            start += 4
        checksumdatanew = checksumdatanew + checksumdata[start:len(checksumdata)]

        f = open(checksums_filename, "wb")
        f.write(checksumdatanew)
        f.close()