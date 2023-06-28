import struct, zlib, logging, sys

class Checksums :
    def __init__(self, checksumdata = "") :
        if len(checksumdata) :
            self.checksumdata = checksumdata
            self.initialize()

    def load_from_file(self, filename) :
        f = open(filename, "rb")
        self.checksumdata = f.read()
        f.close()

        self.initialize()

    def initialize(self) :
        (dummy, dummy2, numfiles, totalchecksums) = struct.unpack("<LLLL", self.checksumdata[:16])

        self.numfiles = numfiles
        self.totalchecksums = totalchecksums
        self.checksumliststart = numfiles * 8 + 16
        
        self.numchecksums = {}
        self.checksumstart = {}
        self.checksums = {}
        self.checksums_raw = {}
        for fileid in range(self.numfiles) :
            checksumpointer = fileid * 8 + 16
            (self.numchecksums[fileid], self.checksumstart[fileid]) = struct.unpack("<LL", self.checksumdata[checksumpointer:checksumpointer + 8])
    
            filechecksums = []
            start = self.checksumliststart + self.checksumstart[fileid] * 4
            end   = start + self.numchecksums[fileid] * 4
            self.checksums_raw[fileid] = self.checksumdata[start:end]
            for i in range(self.numchecksums[fileid]) :
                checksum = struct.unpack("<i", self.checksumdata[start:start+4])[0]
                filechecksums.append(checksum)
                start += 4
                
            self.checksums[fileid] = filechecksums
            

    def validate(self, fileid, file) :
        if len(file) != self.numchecksums[fileid] :
            logging.error("Differing amount of chunks in file and checksum list. File: %s List: %s" % (len(file), self.numchecksums[fileid]))
            sys.exit()

        for chunkid in range(len(file)) :
            result = self.validate_chunk(fileid, chunkid, file[chunkid])
            if result == False :
                return False
            
        return True
        
    def validate_chunk(self, fileid, chunkid, chunk) :

        try :
            stored_crc = self.checksums[fileid][chunkid]
        except IndexError :
            logging.error("Checksum error. Tried to check a chunkid that doesn't have a checksum. Chunk %s in file %s" % (chunkid, fileid))
            return False

        chunk_crc = zlib.adler32(chunk,0) ^ zlib.crc32(chunk,0)

        if stored_crc != chunk_crc :
            logging.warning("CRC error: %i %i stored: %s chunk: %s" %  (fileid, chunkid, hex(stored_crc), hex(chunk_crc)))
            return False
        else :
            return True
        

