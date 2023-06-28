import logging, struct, socket, binascii, sys

from Steam.impsocket import impsocket

class ConnectionError(Exception) :
    pass
        
class fileclient :
    def __init__(self, ipport, appid, version, loginpacket = None, retries = 5) :
        self.ipport = ipport
        self.appid = appid
        self.version = version
        self.loginpacket = loginpacket

        self.connected = False
        self.storageid = 0
        self.messageid = 0
        self.manifest = None
        self.checksums = None
        self.retries = retries
        self.retry_count = 0

        while self.retry_count < self.retries :
            try :        
                self.connect_and_open()
                break
            except socket.error :
                self.s.close()
                self.connected = False
                print "connection reset by peer, retrying"
                self.retry_count += 1

        if self.connected == False :
            raise ConnectionError
                
    def connect_and_open(self) :
        self.connect()
        self.setmode_storage()
        self.open_storage()
        self.download_manifest()
        self.download_checksums()
        self.connected = True

    def close_storage(self) :       # legacy, integrated into disconnect - remove later
        self.disconnect()
        
    def disconnect(self) :
        self.send_command(3)
        self.s.close()
        self.connected = False

    def connect(self) :
        self.s = impsocket()
        self.s.connect(self.ipport)

    def setmode_storage(self) :
        self.s.send("\x00\x00\x00\x07")
        self.s.recv_all(1)

        self.s.send_withlen("\x00\x00\x00\x00\x05")
        self.s.recv(16384)

    def download_manifest(self) :
        if self.manifest == None :
            self.manifest = self.get_metadata(4)
        return self.manifest

    def download_checksums(self) :
        if self.checksums == None :
            self.checksums = self.get_metadata(6)
        return self.checksums

    def recv_message(self, length) :
        reply = self.s.recv_all(8)
        (s_storageid, s_messageid) = struct.unpack(">LL", reply)

        if s_storageid != self.storageid :
            logging.error("StorageID doesn't match up: %i %i" % (s_storageid, self.storageid))
            sys.exit()

        if s_messageid != self.messageid :
            logging.error("MessageID doesn't match up: %i %i" % (s_messageid, self.messageid))
            sys.exit()

        reply = self.s.recv_all(length)

        return reply

    def send_command(self, command, extradata = "") :
        if command == 9 or command == 10 :
            self.storageid = 1

        message = struct.pack(">BLL", command, self.storageid, self.messageid) + extradata
        self.s.send_withlen(message)

        if command == 9 or command == 10 :
            self.storageid = 0x80000001

        reply = self.recv_message(1)
        return reply

    def receive_data(self, length) :
        data = ""

        while len(data) < length :
            reply = self.recv_message(4)
            partlength = struct.unpack(">L", reply)[0]

            package = self.s.recv_all(partlength, False)

            data += package

        return data

    def receive_data_withlen(self) :
        reply = self.recv_message(4)
        length = struct.unpack(">L", reply)[0]

        return self.receive_data(length)

    def open_storage(self) :
        appver = struct.pack(">LL", self.appid, self.version)

        if self.loginpacket :
            status = self.send_command(10, appver + self.loginpacket)
        else :
            status = self.send_command(9, appver)

        if status != "\x00" :
            logging.error("Content server refused connection for app %i version %i (%s)" % (self.appid, self.version, repr(status)))
            self.connected = False
            raise ConnectionError

        reply = self.s.recv_all(8)
        (s_storageid, s_checksum) = struct.unpack(">LL", reply)

        logging.debug("Checksum %s" % hex(s_checksum))

        self.storageid = s_storageid
        self.connected = True

    def get_version_diff(self, oldversion) :
        status = self.send_command(5, struct.pack(">L", oldversion))
        print "Status", ord(status)
        reply = self.s.recv_all(4)
        numdiffs = struct.unpack(">L", reply)[0]
        print "Numdiffs", numdiffs
        if status == "\x01" :
            return []
        reply = self.recv_message(4)
        totalsize = struct.unpack(">L", reply)[0]
        
        if totalsize != numdiffs * 4 :
            print "Totalsize doesn't match numdiffs!", totalsize, numdiffs
            sys.exit()
            
        differences = self.s.recv_all(totalsize)
        diffs = []
        for i in range(numdiffs) :
            diffs.append(struct.unpack("<L", differences[i*4:i*4+4])[0])
            print diffs[i],
        print
        
        return diffs
        
    def get_metadata(self, command) :
        self.send_command(command)

        reply = self.s.recv_all(4)
        fullsize = struct.unpack(">L", reply)[0]

        data = self.receive_data(fullsize)

        self.messageid = self.messageid + 1

        return data

    def get_file(self, fileid, totalchunks) :
        chunks_per_call = 2

        file = []
        filemode = 0xff  # not set
        for i in range(0, totalchunks, chunks_per_call) :

            chunks_to_get = totalchunks - i
            if chunks_to_get > chunks_per_call :
                chunks_to_get = chunks_per_call

            print "%i" % i,
            while self.retry_count < self.retries :
                try :
                    if self.connected == False :
                        self.connect_and_open()
                    (chunks, newfilemode) = self.get_chunks(fileid, i, chunks_to_get)
                    break
                except socket.error :
                    self.s.close()
                    self.connected = False
                    print "connection reset by peer, retrying"
                    self.retry_count += 1
                    
            if self.connected == False :
                raise ConnectionError
                
            if filemode == 0xff :
                filemode = newfilemode

            if filemode != newfilemode :
                logging.error("Filemodes don't match up on the same file: app %i ver %i file %i chunk %i: %i %i" % (self.appid, self.version, fileid, i, filemode, newfilemode))
                sys.exit()

            file.extend(chunks)

        return (file, filemode)

    def get_chunks(self, fileid, filestart, numchunks) :
        filedata = struct.pack(">LLLB", fileid, filestart, numchunks, 0x00)
        dummy1 = self.send_command(7, filedata)

        reply = self.s.recv_all(8)
        (replychunks, filemode) = struct.unpack(">LL", reply)

        logging.debug("Dummy1: %s   Filemode: %s" % (repr(dummy1), hex(filemode)))
        # the filemode is a dword that shows wether the block is encrypted or not, as far as I've seen
        # 0x1 - normal, no encryption
        # 0x2 - encrypted, compressed
        # 0x3 - encrypted, not compressed

        if filemode != 1 and filemode != 2 and filemode != 3:
            f = open("filemodes.bin", "ab")
            f.write(struct.pack(">LLLLb", self.appid, self.version, fileid, filestart, filemode))
            f.close()

        chunks = []
        for i in range(replychunks) :
            chunk = self.receive_data_withlen()
            chunks.append(chunk)

        self.messageid = self.messageid + 1

        return (chunks, filemode)
