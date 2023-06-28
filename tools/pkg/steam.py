import binascii, socket, struct, zlib, os, sys, logging
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA
from Crypto.Cipher import AES

main_key_sign = RSA.construct((
    # n
    0x86724794f8a0fcb0c129b979e7af2e1e309303a7042503d835708873b1df8a9e307c228b9c0862f8f5dbe6f81579233db8a4fe6ba14551679ad72c01973b5ee4ecf8ca2c21524b125bb06cfa0047e2d202c2a70b7f71ad7d1c3665e557a7387bbc43fe52244e58d91a14c660a84b6ae6fdc857b3f595376a8e484cb6b90cc992f5c57cccb1a1197ee90814186b046968f872b84297dad46ed4119ae0f402803108ad95777615c827de8372487a22902cb288bcbad7bc4a842e03a33bd26e052386cbc088c3932bdd1ec4fee1f734fe5eeec55d51c91e1d9e5eae46cf7aac15b2654af8e6c9443b41e92568cce79c08ab6fa61601e4eed791f0436fdc296bb373L,
    # e
    0x07e89acc87188755b1027452770a4e01c69f3c733c7aa5df8aac44430a768faef3cb11174569e7b44ab2951da6e90212b0822d1563d6e6abbdd06c0017f46efe684adeb74d4113798cec42a54b4f85d01e47af79259d4670c56c9c950527f443838b876e3e5ef62ae36aa241ebc83376ffde9bbf4aae6cabea407cfbb08848179e466bcb046b0a857d821c5888fcd95b2aae1b92aa64f3a6037295144aa45d0dbebce075023523bce4243ae194258026fc879656560c109ea9547a002db38b89caac90d75758e74c5616ed9816f3ed130ff6926a1597380b6fc98b5eeefc5104502d9bee9da296ca26b32d9094452ab1eb9cf970acabeecde6b1ffae57b56401L,
    # d
    0x11L,
))

network_key = RSA.construct((
    # n
    0xbf973e24beb372c12bea4494450afaee290987fedae8580057e4f15b93b46185b8daf2d952e24d6f9a23805819578693a846e0b8fcc43c23e1f2bf49e843aff4b8e9af6c5e2e7b9df44e29e3c1c93f166e25e42b8f9109be8ad03438845a3c1925504ecc090aabd49a0fc6783746ff4e9e090aa96f1c8009baf9162b66716059L,
    #int(config["net_key_n"], 16),
    # e
    0x11L,
    # d
    0x4ee3ec697bb34d5e999cb2d3a3f5766210e5ce961de7334b6f7c6361f18682825b2cfa95b8b7894c124ada7ea105ec1eaeb3c5f1d17dfaa55d099a0f5fa366913b171af767fe67fb89f5393efdb69634f74cb41cb7b3501025c4e8fef1ff434307c7200f197b74044e93dbcf50dcc407cbf347b4b817383471cd1de7b5964a9dL,
    #int(config["net_key_d"], 16),
))

network_key_sign = RSA.construct((
    # n
    0xbf973e24beb372c12bea4494450afaee290987fedae8580057e4f15b93b46185b8daf2d952e24d6f9a23805819578693a846e0b8fcc43c23e1f2bf49e843aff4b8e9af6c5e2e7b9df44e29e3c1c93f166e25e42b8f9109be8ad03438845a3c1925504ecc090aabd49a0fc6783746ff4e9e090aa96f1c8009baf9162b66716059L,
    #int(config["net_key_n"], 16),
    # e
    0x4ee3ec697bb34d5e999cb2d3a3f5766210e5ce961de7334b6f7c6361f18682825b2cfa95b8b7894c124ada7ea105ec1eaeb3c5f1d17dfaa55d099a0f5fa366913b171af767fe67fb89f5393efdb69634f74cb41cb7b3501025c4e8fef1ff434307c7200f197b74044e93dbcf50dcc407cbf347b4b817383471cd1de7b5964a9dL,
    #int(config["net_key_d"], 16),
    # d
    0x11L,
))

def decodeIP(string) :
    (oct1, oct2, oct3, oct4, port) = struct.unpack("<BBBBH", string)
    ip = "%d.%d.%d.%d" % (oct1, oct2, oct3, oct4)
    return ip, port

def encodeIP((ip, port)) :
    oct = ip.split(".")
    string = struct.pack("<BBBBH", int(oct[0]), int(oct[1]), int(oct[2]), int(oct[3]), port)
    return string

def blob_unserialize(blobtext) :
    blobdict = {}
    (totalsize, slack) = struct.unpack("<LL", blobtext[2:10])

    if slack :
        blobdict["__slack__"] = blobtext[-(slack):]

    print slack
    print totalsize
    print blobtext

    if (totalsize + slack) != len(blobtext) :
        raise NameError, "Blob not correct length including slack space!"
    index = 10
    while index < totalsize :
        namestart = index + 6
        (namesize, datasize) = struct.unpack("<HL", blobtext[index:namestart])
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

def blob_serialize(blobdict) :

    blobtext = ""

    for (name, data) in blobdict.iteritems() :

        if name == "__slack__" :
            continue

        if type(data) == dict :

            data = blob_serialize(data)

        namesize = len(name)

        datasize = len(data)

        subtext = struct.pack("<HL", namesize, datasize)

        subtext = subtext + name + data

        blobtext = blobtext + subtext

    if blobdict.has_key("__slack__") :
        slack = blobdict["__slack__"]
    else :
        slack = ""

    totalsize = len(blobtext) + 10

    sizetext = struct.pack("<LL", totalsize, len(slack))

    blobtext = chr(0x01) + chr(0x50) + sizetext + blobtext + slack

    return blobtext

def steam_download_package(fileserver, filename, outfilename) :
    s = ImpSocket()
    s.connect(fileserver)
    s.send("\x00\x00\x00\x03")
    s.recv(1)
    message = struct.pack(">LLL", 0, 0, len(filename)) + filename + "\x00\x00\x00\x05"

    s.send_withlen(message)

    response = s.recv(8)

    datalen = struct.unpack(">LL", response)[0]

    f = open(outfilename, "wb")

    while datalen :
        reply = s.recv(datalen)
        datalen = datalen - len(reply)
        f.write(reply)

    f.close()
    s.close()

def steam_get_fileservers(contentserver, app, ver, numservers) :
    command = "\x00\x00\x01" + struct.pack(">LLHL", app, ver, numservers, 0) + "\xff\xff\xff\xff\xff\xff\xff\xff"

    s = ImpSocket()
    s.connect(contentserver)
    s.send("\x00\x00\x00\x02")
    s.recv(1)
    s.send_withlen(command)
    reply = s.recv_withlen()

    s.close()

    numadds = struct.unpack(">H", reply[:2])[0]

    addresses = []
    for i in range(numadds) :
        start = i * 16 + 2
        serverid = struct.unpack(">L", reply[start:start+4])[0]
        server1 = decodeIP(reply[start+4:start+10])
        server2 = decodeIP(reply[start+10:start+16])

        addresses.append((serverid, server1, server2))

    return addresses

def steam_get_authserver(dirserver, namehash) :
    s = ImpSocket()
    s.connect(dirserver)
    s.send("\x00\x00\x00\x02")
    s.recv(1)
    s.send_withlen("\x00" + namehash)
    reply = s.recv_withlen()
    s.close()

    numadds = struct.unpack(">H", reply[:2])[0]

    addresses = []
    for i in range(numadds) :
        start = i * 6 + 2
        server = decodeIP(reply[start:start+6])

        addresses.append(server)

    return addresses



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

        print outfullfilename, "written"

def package_pack(directory, outfilename) :

    filenames = []
    print directory
    for root, dirs, files in os.walk(directory) :
        for name in files :
            if directory != root[0:len(directory)] :
                print "ERROR!!!!!!"
                sys.exit()

            filename = os.path.join(root, name)
            filename = filename[len(directory):] # crop off the basepath part of the filename

            filenames.append(filename)

    print filenames

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

        print filename

    fulloutfile = datasection + indexsection + struct.pack("<BLL", 0, 9, numberoffiles)

    outfile = open(outfilename, "wb")
    outfile.write(fulloutfile)
    outfile.close()

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

        self.indexfile  = path + self.name + ".index"
        self.datafile   = path + self.name + ".data"

        (self.indexes, self.filemodes) = readindexes(self.indexfile)

    def readchunk(self, fileid, chunkid) :
        index = self.indexes[fileid]

        f = open(self.datafile, "rb")

        pos = chunkid * 8

        (start, length) = struct.unpack(">LL", index[pos:pos+8])

        f.seek(start)
        file = f.read(length)

        f.close()

        return file, self.filemodes[fileid]

    def readchunks(self, fileid, chunkid, maxchunks) :

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

        f.close()

        return filechunks, self.filemodes[fileid]

    def readfile(self, fileid) :

        filechunks = []
        index = self.indexes[fileid]

        f = open(self.datafile, "rb")

        for pos in range(0, len(index), 8) :
            (start, length) = struct.unpack(">LL", index[pos:pos+8])

            f.seek(start)
            filechunks.append(f.read(length))

        f.close()

        return filechunks, self.filemodes[fileid]

    def writefile(self, fileid, filechunks, filemode) :

        if self.indexes.has_key(fileid) :
            print "FileID already exists!"
            sys.exit()

        f = open(self.datafile, "a+b")
        fi = open(self.indexfile, "ab")

        f.seek(0,2)                                 # this is a hack to get the f.tell() to show the correct position

        outindex = struct.pack(">LLL", fileid, len(filechunks) * 8, filemode)

        for chunk in filechunks :
            outfilepos = f.tell()

            outindex = outindex + struct.pack(">LL", outfilepos, len(chunk))

            f.write(chunk)

        fi.write(outindex)

        f.close()
        fi.close()

        self.indexes[fileid] = outindex[12:]

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



class ImpSocket :
    "improved socket class - this is REALLY braindead because the socket class doesn't let me override some methods, so I have to build from scratch"

    def __init__(self, sock = None) :
        if sock is None :
            self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        else :
            self.s = sock


    def accept(self) :
        (returnedsocket, address) = self.s.accept()
        newsocket = ImpSocket(returnedsocket)
        newsocket.address = address

        return newsocket, address


    def bind(self, address) :
        self.address = address
        self.s.bind(address)


    def connect(self, address) :
        self.address = address
        self.s.connect(address)

        logging.debug(str(self.address) + ": Connecting to address")


    def close(self) :
        self.s.close()


    def listen(self, connections) :
        self.s.listen(connections)


    def send(self, data, log = True) :
        sentbytes = self.s.send(data)

        if log :
            logging.debug(str(self.address) + ": Sent data - " + binascii.b2a_hex(data))

        if sentbytes != len(data) :
            logging.warning("NOTICE!!! Number of bytes sent doesn't match what we tried to send " + str(sentbytes) + " " + str(len(data)))

        return sentbytes

    def sendto(self, data, address, log = True) :
        sentbytes = self.s.sendto(data, address)

        if log :
            logging.debug(str(address) + ": sendto Sent data - " + binascii.b2a_hex(data))

        if sentbytes != len(data) :
            logging.warning("NOTICE!!! Number of bytes sent doesn't match what we tried to send " + str(sentbytes) + " " + str(len(data)))

        return sentbytes


    def send_withlen(self, data, log = True) :
        lengthstr = struct.pack(">L", len(data))

        if log :
            logging.debug(str(self.address) + ": Sent data with length - " + binascii.b2a_hex(lengthstr) + " " + binascii.b2a_hex(data))

        totaldata = lengthstr + data
        totalsent = 0
        while totalsent < len(totaldata) :
            sent = self.send(totaldata, False)
            if sent == 0:
                raise RuntimeError, "socket connection broken"
            totalsent = totalsent + sent


    def recv(self, length, log = True) :
        data = self.s.recv(length)

        if log :
            logging.debug(str(self.address) + ": Received data - " + binascii.b2a_hex(data))

        return data

    def recvfrom(self, length, log = True) :
        (data, address) = self.s.recvfrom(length)

        if log :
            logging.debug(str(address) + ": recvfrom Received data - " + binascii.b2a_hex(data))

        return (data, address)

    def recv_all(self, length, log = True) :
        data = ""
        while len(data) < length :
            chunk = self.recv(length - len(data), False)
            if chunk == '':
                raise RuntimeError, "socket connection broken"
            data = data + chunk

        if log :
            logging.debug(str(self.address) + ": Received all data - " + binascii.b2a_hex(data))

        return data

    def recv_withlen(self, log = True) :
        lengthstr = self.recv(4, False)
        if len(lengthstr) != 4 :
            print "HEADER NOT LONG ENOUGH"
        length = struct.unpack(">L", lengthstr)[0]

        data = self.recv_all(length, False)

        if log :
            logging.debug(str(self.address) + ": Received data with length  - " + binascii.b2a_hex(lengthstr) + " " + binascii.b2a_hex(data))

        return data


def get_aes_key(encryptedstring, rsakey) :

    decryptedstring = rsakey.decrypt(encryptedstring)

    if len(decryptedstring) != 127 :
        raise NameError, "RSAdecrypted string not the correct length!" + str(len(decryptedstring))

    firstpasschecksum = SHA.new(decryptedstring[20:127] + "\x00\x00\x00\x00" ).digest()

    secondpasskey = binaryxor(firstpasschecksum, decryptedstring[0:20])

    secondpasschecksum0 = SHA.new(secondpasskey + "\x00\x00\x00\x00" ).digest()
    secondpasschecksum1 = SHA.new(secondpasskey + "\x00\x00\x00\x01" ).digest()
    secondpasschecksum2 = SHA.new(secondpasskey + "\x00\x00\x00\x02" ).digest()
    secondpasschecksum3 = SHA.new(secondpasskey + "\x00\x00\x00\x03" ).digest()
    secondpasschecksum4 = SHA.new(secondpasskey + "\x00\x00\x00\x04" ).digest()
    secondpasschecksum5 = SHA.new(secondpasskey + "\x00\x00\x00\x05" ).digest()

    secondpasstotalchecksum = secondpasschecksum0 + secondpasschecksum1 + secondpasschecksum2 + secondpasschecksum3 + secondpasschecksum4 + secondpasschecksum5

    finishedkey = binaryxor(secondpasstotalchecksum[0:107], decryptedstring[20:127])

    controlchecksum = SHA.new("").digest()

    if finishedkey[0:20] != controlchecksum :
        raise NameError, "Control checksum didn't match!"

    return finishedkey[-16:]

def verify_message(key, message) :
    key = key + "\x00" * 48
    xor_a = "\x36" * 64
    xor_b = "\x5c" * 64
    key_a = binaryxor(key, xor_a)
    key_b = binaryxor(key, xor_b)
    phrase_a = key_a + message[:-20]
    checksum_a = SHA.new(phrase_a).digest()
    phrase_b = key_b + checksum_a
    checksum_b = SHA.new(phrase_b).digest()
    if checksum_b == message[-20:] :
        return True
    else:
        return False

def sign_message(key, message) :
    key = key + "\x00" * 48
    xor_a = "\x36" * 64
    xor_b = "\x5c" * 64
    key_a = binaryxor(key, xor_a)
    key_b = binaryxor(key, xor_b)
    phrase_a = key_a + message
    checksum_a = SHA.new(phrase_a).digest()
    phrase_b = key_b + checksum_a
    checksum_b = SHA.new(phrase_b).digest()
    return checksum_b

def rsa_sign_message(rsakey, message) :

    digest = SHA.new(message).digest()

    fulldigest = "\x00\x01" + ("\xff" * 90) + "\x00\x30\x21\x30\x09\x06\x05\x2b\x0e\x03\x02\x1a\x05\x00\x04\x14" + digest

    signature = rsakey.encrypt(fulldigest, 0)[0]

    signature = signature.rjust(128, "\x00") # we aren't guaranteed that RSA.encrypt will return a certain length, so we pad it

    return signature

def rsa_sign_message_1024(rsakey, message) :

    digest = SHA.new(message).digest()

    fulldigest = "\x00\x01" + ("\xff" * 218) + "\x00\x30\x21\x30\x09\x06\x05\x2b\x0e\x03\x02\x1a\x05\x00\x04\x14" + digest

    signature = rsakey.encrypt(fulldigest, 0)[0]

    signature = signature.rjust(256, "\x00") # we aren't guaranteed that RSA.encrypt will return a certain length, so we pad it

    return signature

def aes_decrypt(key, IV, message) :

    decrypted = ""

    cryptobj = AES.new(key, AES.MODE_CBC, IV)
    i = 0

    while i < len(message) :

        cipher = message[i:i+16]

        decrypted = decrypted + cryptobj.decrypt(cipher)

        i = i + 16

    return decrypted

def aes_encrypt(key, IV, message) :

    # pad the message
    overflow = len(message) % 16
    message = message + (16 - overflow) * chr(16 - overflow)

    encrypted = ""

    cryptobj = AES.new(key, AES.MODE_CBC, IV)
    i = 0

    while i < len(message) :

        cipher = message[i:i+16]

        encrypted = encrypted + cryptobj.encrypt(cipher)

        i = i + 16

    return encrypted

def binaryxor(stringA, stringB) :
    if len(stringA) != len(stringB) :
        print("binaryxor: string lengths doesn't match!!")
        sys.exit()

    outString =  ""
    for i in range( len(stringA) ) :
        valA = ord(stringA[i])
        valB = ord(stringB[i])
        valC = valA ^ valB
        outString = outString + chr(valC)
    return outString

class Application :
    "Empty class that acts as a placeholder"
    pass

def chunk_aes_decrypt(key, chunk) :
    cryptobj = AES.new(key, AES.MODE_ECB)
    output = ""
    lastblock = "\x00" * 16

    for i in range(0, len(chunk), 16) :
        block = chunk[i:i+16]
        block = block.ljust(16)
        key2 = cryptobj.encrypt(lastblock)
        output += binaryxor(block, key2)
        lastblock = block

    return output[:len(chunk)]


def get_apps_list(blob) :
    subblob = blob["\x01\x00\x00\x00"]

    apps = {}

    for appblob in subblob :

        app = Application()
        app.binid = appblob
        app.id = struct.unpack("<L", appblob)[0]
        app.version = struct.unpack("<L", subblob[appblob]["\x0b\x00\x00\x00"])[0]
        app.size = struct.unpack("<L", subblob[appblob]["\x05\x00\x00\x00"])[0]
        app.name = subblob[appblob]["\x02\x00\x00\x00"]

        apps[app.id] = app

    return apps


class Fileserver_Client :

    def __init__(self, ipport) :
        self.ipport = ipport
        self.connid = 0
        self.messageid = 0

        self.s = ImpSocket()
        self.s.connect(ipport)

    def setmode_storage(self) :
        self.s.send("\x00\x00\x00\x07")
        self.s.recv(1)

        self.s.send_withlen("\x00\x00\x00\x00\x05")
        self.s.recv(16384)

    def open_storage(self, app, version) :
        self.app = app
        self.version = version

        command = "\x09" + struct.pack(">LLLL", self.connid, self.messageid, app, version)
        self.s.send_withlen(command)
        reply = self.s.recv(9)
        (s_connid, s_messageid, s_dummy1) = struct.unpack(">LLb", reply)

        if s_dummy1 != 0 :
            logging.error("Content server did not have app %i %i" % (app,version))
            return -1

        reply = self.s.recv(8)
        (s_storageid, s_checksum) = struct.unpack(">LL", reply)

        if s_messageid != self.messageid :
            logging.error("MessageID doesn't match up: %i %i" % (s_messageid, self.messageid))
            return

        logging.debug("Connection IDs: %s %s" % (hex(self.connid), hex(s_connid)))
        logging.debug("Dummy1: %s  Checksum %s" % (hex(s_dummy1), hex(s_checksum)))

        self.messageid = self.messageid + 1
        self.connid = self.connid + 1

        return s_storageid

    def open_storage_withlogin(self, app, version, loginpacket) :
        self.app = app
        self.version = version

        command = "\x0a" + struct.pack(">LLLL", self.connid, self.messageid, app, version) + loginpacket
        self.s.send_withlen(command)
        reply = self.s.recv(9)
        (s_connid, s_messageid, s_dummy1) = struct.unpack(">LLb", reply)

        if s_dummy1 != 0 :
            logging.error("Content server did not have app %i %i" % (app,version))
            return -1

        reply = self.s.recv(8)
        (s_storageid, s_checksum) = struct.unpack(">LL", reply)

        if s_messageid != self.messageid :
            logging.error("MessageID doesn't match up: %i %i" % (s_messageid, self.messageid))
            return

        logging.debug("Connection IDs: %s %s" % (hex(self.connid), hex(s_connid)))
        logging.debug("Dummy1: %s  Checksum %s" % (hex(s_dummy1), hex(s_checksum)))

        self.messageid = self.messageid + 1
        self.connid = self.connid + 1

        return s_storageid

    def close_storage(self, storageid) :
        command = "\x03" + struct.pack(">LL", storageid, self.messageid)
        self.s.send_withlen(command)
        reply = self.s.recv(9)

        (s_storageid, s_messageid, dummy1) = struct.unpack(">LLb", reply)

        logging.debug("Dummy1: %s" % hex(dummy1))

        if s_storageid != storageid :
            logging.error("StorageID doesn't match up: %i %i" % (s_storageid, storageid))
            return

        if s_messageid != self.messageid :
            logging.error("MessageID doesn't match up: %i %i" % (s_messageid, self.messageid))
            return

        self.messageid = self.messageid + 1

    def disconnect(self) :
        self.s.close()

    def get_metadata(self, storageid, commandbyte) :
        command = commandbyte + struct.pack(">LL", storageid, self.messageid)
        self.s.send_withlen(command)

        reply = self.s.recv(13)

        (s_storageid, s_messageid, dummy1, fullsize) = struct.unpack(">LLbL", reply)

        if s_storageid != storageid :
            logging.error("StorageID doesn't match up: %i %i" % (s_storageid, storageid))
            return

        if s_messageid != self.messageid :
            logging.error("MessageID doesn't match up: %i %i" % (s_messageid, self.messageid))
            return

        logging.debug("Dummy1: %s" % hex(dummy1))

        data = ""

        while len(data) < fullsize :

            reply = self.s.recv(12)

            (s_storageid, s_messageid, partsize) = struct.unpack(">LLL", reply)

            if s_storageid != storageid :
                logging.error("StorageID doesn't match up: %i %i" % (s_storageid, storageid))
                return

            if s_messageid != self.messageid :
                logging.error("MessageID doesn't match up: %i %i" % (s_messageid, self.messageid))
                return

            package = self.s.recv_all(partsize, False)

            data = data + package

        self.messageid = self.messageid + 1

        return data

    def get_file(self, storageid, fileid, totalparts) :
        chunks_per_call = 1

        file = []

        for i in range(0, totalparts, chunks_per_call) :
            print "%i" % i,
            chunks = self.get_chunks(storageid, fileid, i, chunks_per_call)
            file.extend(chunks)

        return file

    def get_file_with_flag(self, storageid, fileid, totalparts) :
        chunks_per_call = 1

        file = []
        filemode = 0xff
        for i in range(0, totalparts, chunks_per_call) :
            print "%i" % i,
            (newfilemode, chunks) = self.get_chunks_with_flag(storageid, fileid, i, chunks_per_call)

            if filemode == 0xff :
                filemode = newfilemode

            if filemode != newfilemode :
                logging.error("Filemodes don't match up on the same file: %i %i" % (filemode, newfilemode))

            file.extend(chunks)

        return (filemode, file)


    def get_chunks(self, storageid, fileid, filepart, numparts) :
        command = "\x07" + struct.pack(">LLLLLB", storageid, self.messageid, fileid, filepart, numparts, 0x00)

        self.s.send_withlen(command)

        reply = self.s.recv(17)

        (s_storageid, s_messageid, dummy1, replyparts, filemode) = struct.unpack(">LLbLL", reply)

        logging.debug("Dummy1: %s   Filemode: %s" % (hex(dummy1), hex(filemode)))
        # the filemode is a dword that shows wether the block is encrypted or not, as far as I've seen
        # 0x1 - normal, no encryption
        # 0x2 - encrypted, compressed
        # 0x3 - encrypted, not compressed

        if filemode != 1 :
            foobar = open("filemodes.bin", "ab")
            foobar.write(struct.pack(">LLLLb", self.app, self.version, fileid, filepart, filemode))
            foobar.close()

        if s_storageid != storageid :
            logging.error("StorageID doesn't match up: %i %i" % (s_storageid, storageid))
            return

        if s_messageid != self.messageid :
            logging.error("MessageID doesn't match up: %i %i" % (s_messageid, self.messageid))
            return

        chunks = []
        for i in range(replyparts) :

            try :
                reply = self.s.recv(12)
            except socket.error :
                # connection reset by peer
                reply = struct.pack(">LLL", storageid, self.messageid, 0)

            (s_storageid, s_messageid, fullsize) = struct.unpack(">LLL", reply)

            if s_storageid != storageid :
                logging.error("StorageID doesn't match up: %i %i" % (s_storageid, storageid))
                return

            if s_messageid != self.messageid :
                logging.error("MessageID doesn't match up: %i %i" % (s_messageid, self.messageid))
                return

            data = ""

            while len(data) < fullsize :

                reply = self.s.recv(12)

                (s_storageid, s_messageid, partsize) = struct.unpack(">LLL", reply)

                if s_storageid != storageid :
                    logging.error("StorageID doesn't match up: %i %i" % (s_storageid, storageid))
                    return

                if s_messageid != self.messageid :
                    logging.error("MessageID doesn't match up: %i %i" % (s_messageid, self.messageid))
                    return

                package = self.s.recv_all(partsize, False)

                data = data + package

            chunks.append(data)

        self.messageid = self.messageid + 1

        return chunks

    def get_chunks_with_flag(self, storageid, fileid, filepart, numparts) :
        command = "\x07" + struct.pack(">LLLLLB", storageid, self.messageid, fileid, filepart, numparts, 0x00)

        self.s.send_withlen(command)

        reply = self.s.recv(17)

        (s_storageid, s_messageid, dummy1, replyparts, filemode) = struct.unpack(">LLbLL", reply)

        logging.debug("Dummy1: %s   Filemode: %s" % (hex(dummy1), hex(filemode)))
        # the filemode is a dword that shows wether the block is encrypted or not, as far as I've seen
        # 0x1 - normal, no encryption
        # 0x2 - encrypted, compressed
        # 0x3 - encrypted, not compressed

        if filemode != 1 :
            foobar = open("filemodes.bin", "ab")
            foobar.write(struct.pack(">LLLLb", self.app, self.version, fileid, filepart, filemode))
            foobar.close()

        if s_storageid != storageid :
            logging.error("StorageID doesn't match up: %i %i" % (s_storageid, storageid))
            return

        if s_messageid != self.messageid :
            logging.error("MessageID doesn't match up: %i %i" % (s_messageid, self.messageid))
            return

        chunks = []
        for i in range(replyparts) :

            try :
                reply = self.s.recv(12)
            except socket.error :
                # connection reset by peer
                reply = struct.pack(">LLL", storageid, self.messageid, 0)

            (s_storageid, s_messageid, fullsize) = struct.unpack(">LLL", reply)

            if s_storageid != storageid :
                logging.error("StorageID doesn't match up: %i %i" % (s_storageid, storageid))
                return

            if s_messageid != self.messageid :
                logging.error("MessageID doesn't match up: %i %i" % (s_messageid, self.messageid))
                return

            data = ""

            while len(data) < fullsize :

                reply = self.s.recv(12)

                (s_storageid, s_messageid, partsize) = struct.unpack(">LLL", reply)

                if s_storageid != storageid :
                    logging.error("StorageID doesn't match up: %i %i" % (s_storageid, storageid))
                    return

                if s_messageid != self.messageid :
                    logging.error("MessageID doesn't match up: %i %i" % (s_messageid, self.messageid))
                    return

                package = self.s.recv_all(partsize, False)

                data = data + package

            chunks.append(data)

        self.messageid = self.messageid + 1

        return (filemode, chunks)

def steamtime_to_unixtime(steamtime_bin) :
    steamtime = struct.unpack("<Q", steamtime_bin)[0]
    unixtime = steamtime / 1000000 - 62135596800
    return unixtime

def unixtime_to_steamtime(unixtime) :
    steamtime = (unixtime + 62135596800) * 1000000
    steamtime_bin = struct.pack("<Q", steamtime)
    return steamtime_bin

def sortfunc(x, y) :

    if len(x) == 4 and x[2] == "\x00" :
        if len(y) == 4 and y[2] == "\x00" :
            numx = struct.unpack("<L", x)[0]
            numy = struct.unpack("<L", y)[0]
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
