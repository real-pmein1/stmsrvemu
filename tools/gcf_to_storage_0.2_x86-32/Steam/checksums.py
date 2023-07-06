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
            #self.fix_crc(fileid, chunkid, chunk, filename)
            return False
        else :
            return True

    def fix_crc(self, fileid, chunkid, chunk, filename) :
        log = logging.getLogger("converter")
        clientid = ""
        f = open(filename, "rb")
        checksumdata = f.read()
        f.close()
        stored_crc = self.checksums[fileid][chunkid]
        chunk_crc = zlib.adler32(chunk,0) ^ zlib.crc32(chunk,0)
        log.debug("Fixing CRC from " + str(stored_crc) + " to " + str(chunk_crc) + " on FileID " + str(fileid))
        
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
        end   = start + numchecksums[fileid] * 4
        checksums_raw[fileid] = checksumdata[start:end]
        log.debug(len(checksumdata)) #132844
        log.debug(len(checksumdata[0:start])) #67192
        log.debug(len(checksumdata[start:start+4])) #4
        log.debug(len(checksumdata[start+4:len(checksumdata)])) #65648
        checksumdatanew = checksumdata[0:start]
        log.debug(len(checksumdatanew)) #67192
        checksumdatanew_temp = ""
        log.debug("Checksum count: " + str(range(numchecksums[fileid])))
        for i in range(numchecksums[fileid]) :
            checksum = struct.unpack("<i", checksumdata[start:start+4])[0]
            log.debug(struct.unpack("<i", checksumdata[start:start+4])) #1132535908
            log.debug("Checksum: " + str(checksum)) #1132535908
            if checksum == stored_crc :
                log.debug("CRC CHANGED!")
                #print(struct.pack("<i", chunk_crc)) #-1711041001
                #print(type((checksumdata[start:start+4])[0]))
                checksumdatanew_temp = struct.pack("<i", chunk_crc)
                log.debug(struct.unpack("<i", checksumdatanew_temp))
                log.debug(len(checksumdatanew_temp))
                checksumdatanew = checksumdatanew + checksumdatanew_temp
                log.debug(len(checksumdatanew))
            else :
                log.debug("Stored only")
                #print(struct.pack("<i", stored_crc)) #-1711041001
                #print(type((checksumdata[start:start+4])[0]))
                checksumdatanew_temp = struct.pack("<i", checksum)
                log.debug(struct.unpack("<i", checksumdatanew_temp))
                log.debug(len(checksumdatanew_temp))
                checksumdatanew = checksumdatanew + checksumdatanew_temp
                log.debug(len(checksumdatanew))
            #filechecksums.append(checksum)
            start += 4
        log.debug(len(checksumdatanew))
        log.debug(len(checksumdata[start:len(checksumdata)]))
        checksumdatanew = checksumdatanew + checksumdata[start:len(checksumdata)]
        log.debug(len(checksumdatanew))
        for i in range(numchecksums[fileid]) :
            checksum = struct.unpack("<i", checksumdatanew[start:start+4])
            if checksum == chunk_crc :
                print "Checksum validated"
            #filechecksums.append(checksum)
            start += 4
        
        if len(checksumdata) != len(checksumdatanew) :
            log.debug("Old and new checksums are different sizes: " + str(len(checksumdata)) + " to " + str(len(checksumdatanew)))
            sys.exit()
        else :
            log.debug("Old and new checksums are correct sizes.")
        
        f = open(filename, "wb")
        f.write(checksumdatanew)
        f.close()

