import binascii, socket, struct, zlib, os, sys, logging
from Crypto.Cipher import AES
from Steam import crypto

def package_unpack(infilename, outpath) :

    if not os.path.exists(outpath) :
        os.makedirs(outpath)

    infile = open(infilename, "rb")
    package = infile.read()
    infile.close()

    header = package[-9:]

    (pkg_ver, compress_level, numfiles) = struct.unpack("<BLL", package[-9:])

    index = len(package) - (9 + 16)

    for i in range(numfiles) :

        (unpacked_size, packed_size, file_start, filename_len) = struct.unpack("<LLLL", package[index:index + 16])

        filename = package[index - filename_len:index - 1]

        (filepath, basename) = os.path.split(filename)

        index = index - (filename_len + 16)

        file = ""

        while packed_size > 0 :

            compressed_len = struct.unpack("<L", package[file_start:file_start + 4])[0]

            compressed_start = file_start + 4
            compressed_end   = compressed_start + compressed_len

            compressed_data = package[compressed_start:compressed_end]

            file = file + zlib.decompress(compressed_data)

            file_start = compressed_end
            packed_size = packed_size - compressed_len

        outsubpath = os.path.join(outpath, filepath)

        if not os.path.exists(outsubpath) :
            os.makedirs(outsubpath)

        outfullfilename = os.path.join(outpath, filename)

        outfile = open(outfullfilename, "wb")
        outfile.write(file)
        outfile.close()

        #print filename, "written"

def package_pack(directory, outfilename) :

    filenames = []

    for root, dirs, files in os.walk(directory) :
        for name in files :
            if directory != root[0:len(directory)] :
                print "ERROR!!!!!!"
                sys.exit()

            filename = os.path.join(root, name)
            filename = filename[len(directory):] # crop off the basepath part of the filename

            filenames.append(filename)

    #print filenames

    outfileoffset = 0

    datasection = ""
    indexsection = ""
    numberoffiles = 0

    for filename in filenames :

        infile = open(directory + filename, "rb")
        filedata = infile.read()
        infile.close()

        index = 0
        packedbytes = 0

        for i in range(0, len(filedata), 0x8000) :

            chunk = filedata[i:i + 0x8000]

            packedchunk = zlib.compress(chunk, 9)

            packedlen = len(packedchunk)

            datasection = datasection + struct.pack("<L", packedlen) + packedchunk

            packedbytes = packedbytes + packedlen

        indexsection = indexsection + filename + "\x00" + struct.pack("<LLLL", len(filedata), packedbytes, outfileoffset, len(filename) + 1)

        outfileoffset = len(datasection)

        numberoffiles = numberoffiles + 1

        #print filename

    fulloutfile = datasection + indexsection + struct.pack("<BLL", 0, 9, numberoffiles)

    outfile = open(outfilename, "wb")
    outfile.write(fulloutfile)
    outfile.close()

def neuter_file(filename) :

    f = open(filename, "rb")
    file = f.read()
    f.close()

    oldfilelen = len(file)

    #print len(file)


    # let's first replace the IP addresses

    found = file.find("207.173.177.11:27030 207.173.177.12:27030 69.28.151.178:27038 69.28.153.82:27038 68.142.88.34:27038 68.142.72.250:27038 \x00")

    if found < 0 :
        print "Didn't find the IP address position"
        sys.exit()

    newstring =       "127.0.0.1:27030 127.0.0.1:27030 127.0.0.1:27030 127.0.0.1:27030 127.0.0.1:27030 127.0.0.1:27030                         "

    foundstring = file[found:found + 120]

    file = file.replace(foundstring, newstring)

    #print len(file)


    # then let's replace the hostnames

    found = file.find("gds1.steampowered.com:27030 gds2.steampowered.com:27030\x00")

    if found < 0 :
        print "Didn't find the hostnames position"
        sys.exit()

    newstring = "invalid00.example.com:27030 invalid00.example.com:27030"

    foundstring = file[found:found + 55]

    file = file.replace(foundstring, newstring)

    #print len(file)


    # then let's replace the public key

    found = file.find("30820120300d06092a864886f70d01010105000382010d00308201080282010100d1543176ee6741270dc1a32f4b04c3a304d499ad0570777dba31483d01eb5e639a05eb284f93cf9260b1ef9e159403ae5f7d3997e789646cfc70f26815169a9b4ba4dc5700ea4480f78466eae6d2bdf5e4181da076ca2e95b32b79c016eb91b5f158e8448d2dd5a42f883976a935dcccbbc611dc2bdf0ea3b88ca72fba919501fb8c6187b4ecddbbb6623d640e819302a6be35be74460cbad9bff0ab7dff0c5b4b8f4aff8252815989ec5fffb460166c5a75b81dd99d79b05f23d97476eb3a5d44c74dcd1136e776f5d2bb52e77f530fa2a5ad75f16c1fb5d8218d71b93073bddad930b3b4217989aa58b30566f1887907ca431e02defe51d19489486caf033d020111")

    if found < 0 :
        print "Didn't find the public key position"
        sys.exit()

    newstring = "30820120300d06092a864886f70d01010105000382010d0030820108028201010086724794f8a0fcb0c129b979e7af2e1e309303a7042503d835708873b1df8a9e307c228b9c0862f8f5dbe6f81579233db8a4fe6ba14551679ad72c01973b5ee4ecf8ca2c21524b125bb06cfa0047e2d202c2a70b7f71ad7d1c3665e557a7387bbc43fe52244e58d91a14c660a84b6ae6fdc857b3f595376a8e484cb6b90cc992f5c57cccb1a1197ee90814186b046968f872b84297dad46ed4119ae0f402803108ad95777615c827de8372487a22902cb288bcbad7bc4a842e03a33bd26e052386cbc088c3932bdd1ec4fee1f734fe5eeec55d51c91e1d9e5eae46cf7aac15b2654af8e6c9443b41e92568cce79c08ab6fa61601e4eed791f0436fdc296bb373020111"

    foundstring = file[found:found + 584]

    file = file.replace(foundstring, newstring)

    #print len(file)

    if oldfilelen != len(file) :
        print "File lengths don't match after neutering"
        sys.exit()

    f = open(filename, "wb")
    f.write(file)
    f.close()

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

class Storage :
    def __init__(self, storagename, path) :
        self.name = str(storagename)

        self.indexfile  = path + self.name + ".index"
        self.datafile   = path + self.name + ".data"

        (self.indexes, self.filemodes) = readindexes(self.indexfile)
        
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
        crcb = zlib.adler32(chunk, 0) ^ zlib.crc32(chunk, 0)

        if crc != crcb :
            logging.warning("CRC error: %i %s %s" %  (fileid, hex(crc), hex(crcb)))
            return False
        else :
            return True


        
def chunk_aes_decrypt(key, chunk) :
    cryptobj = AES.new(key, AES.MODE_ECB)
    output = ""
    lastblock = "\x00" * 16

    for i in range(0, len(chunk), 16) :
        block = chunk[i:i+16]
        block = block.ljust(16)
        key2 = cryptobj.encrypt(lastblock)
        output += crypto.binaryxor(block, key2)
        lastblock = block

    return output[:len(chunk)]


