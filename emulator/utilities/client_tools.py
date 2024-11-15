import logging
import socket
import struct

from utilities.socket import ImpSocket
from utils import decodeIP


def steam_download_package(fileserver, filename, outfilename):
    s = ImpSocket()
    s.connect(fileserver)
    s.send("\x00\x00\x00\x03")
    s.recv(1)
    message = struct.pack(">LLL", 0, 0, len(filename)) + filename + b"\x00\x00\x00\x05"

    s.send_withlen(message)

    response = s.recv(8)

    datalen = struct.unpack(">LL", response)[0]

    f = open(outfilename, "wb")

    while datalen:
        reply = s.recv(datalen)
        datalen -= len(reply)
        f.write(reply)

    f.close()
    s.close()


def steam_get_fileservers(contentserver, app, ver, numservers):
    command = b"\x00\x00\x01" + struct.pack(">LLHL", app, ver, numservers, 0) + b"\xff\xff\xff\xff\xff\xff\xff\xff"

    s = ImpSocket()
    s.connect(contentserver)
    s.send("\x00\x00\x00\x02")
    s.recv(1)
    s.send_withlen(command)
    reply = s.recv_withlen()

    s.close()

    numadds = struct.unpack(">H", reply[:2])[0]

    addresses = []
    for i in range(numadds):
        start = i * 16 + 2
        serverid = struct.unpack(">L", reply[start:start + 4])[0]
        server1 = decodeIP(reply[start + 4:start + 10])
        server2 = decodeIP(reply[start + 10:start + 16])

        addresses.append((serverid, server1, server2))

    return addresses


def steam_get_authserver(dirserver, namehash):
    s = ImpSocket()
    s.connect(dirserver)
    s.send("\x00\x00\x00\x02")
    s.recv(1)
    s.send_withlen("\x00" + namehash)
    reply = s.recv_withlen()
    s.close()

    numadds = struct.unpack(">H", reply[:2])[0]

    addresses = []
    for i in range(numadds):
        start = i * 6 + 2
        server = decodeIP(reply[start:start + 6])

        addresses.append(server)

    return addresses


class Fileserver_Client:

    def __init__(self, ipport):
        self.ipport = ipport
        self.connid = 0
        self.messageid = 0
        self.app = None
        self.version = None
        self.s = ImpSocket()
        self.s.connect(ipport)

    def setmode_storage(self):
        self.s.send("\x00\x00\x00\x07")
        self.s.recv(1)

        self.s.send_withlen("\x00\x00\x00\x00\x05")
        self.s.recv(16384)

    def open_storage(self, app, version):
        self.app = app
        self.version = version

        command = "\x09" + struct.pack(">LLLL", self.connid, self.messageid, app, version)
        self.s.send_withlen(command)
        reply = self.s.recv(9)
        (s_connid, s_messageid, s_dummy1) = struct.unpack(">LLb", reply)

        if s_dummy1 != 0:
            logging.error("Content server did not have app %i %i" % (app, version))
            return -1

        reply = self.s.recv(8)
        (s_storageid, s_checksum) = struct.unpack(">LL", reply)

        if s_messageid != self.messageid:
            logging.error("MessageID doesn't match up: %i %i" % (s_messageid, self.messageid))
            return -1

        logging.debug("Connection IDs: %s %s" % (hex(self.connid), hex(s_connid)))
        logging.debug("Dummy1: %s  Checksum %s" % (hex(s_dummy1), hex(s_checksum)))

        self.messageid += 1
        self.connid += 1

        return s_storageid

    def open_storage_withlogin(self, app, version, loginpacket):
        self.app = app
        self.version = version

        command = b"\x0a" + struct.pack(">LLLL", self.connid, self.messageid, app, version) + loginpacket
        self.s.send_withlen(command)
        reply = self.s.recv(9)
        (s_connid, s_messageid, s_dummy1) = struct.unpack(">LLb", reply)

        if s_dummy1 != 0:
            logging.error("Content server did not have app %i %i" % (app, version))
            return -1

        reply = self.s.recv(8)
        (s_storageid, s_checksum) = struct.unpack(">LL", reply)

        if s_messageid != self.messageid:
            logging.error("MessageID doesn't match up: %i %i" % (s_messageid, self.messageid))
            return -1

        logging.debug("Connection IDs: %s %s" % (hex(self.connid), hex(s_connid)))
        logging.debug("Dummy1: %s  Checksum %s" % (hex(s_dummy1), hex(s_checksum)))

        self.messageid += 1
        self.connid += 1

        return s_storageid

    def close_storage(self, storageid):
        command = b"\x03" + struct.pack(">LL", storageid, self.messageid)
        self.s.send_withlen(command)
        reply = self.s.recv(9)

        (s_storageid, s_messageid, dummy1) = struct.unpack(">LLb", reply)

        logging.debug("Dummy1: %s" % hex(dummy1))

        if s_storageid != storageid:
            logging.error("StorageID doesn't match up: %i %i" % (s_storageid, storageid))
            return

        if s_messageid != self.messageid:
            logging.error("MessageID doesn't match up: %i %i" % (s_messageid, self.messageid))
            return

        self.messageid += 1

    def disconnect(self):
        self.s.close()

    def get_metadata(self, storageid, commandbyte):
        command = commandbyte + struct.pack(">LL", storageid, self.messageid)
        self.s.send_withlen(command)

        reply = self.s.recv(13)

        (s_storageid, s_messageid, dummy1, fullsize) = struct.unpack(">LLbL", reply)

        if s_storageid != storageid:
            logging.error("StorageID doesn't match up: %i %i" % (s_storageid, storageid))
            return -1

        if s_messageid != self.messageid:
            logging.error("MessageID doesn't match up: %i %i" % (s_messageid, self.messageid))
            return -1

        logging.debug("Dummy1: %s" % hex(dummy1))

        data = ""

        while len(data) < fullsize:

            reply = self.s.recv(12)

            (s_storageid, s_messageid, partsize) = struct.unpack(">LLL", reply)

            if s_storageid != storageid:
                logging.error("StorageID doesn't match up: %i %i" % (s_storageid, storageid))
                return

            if s_messageid != self.messageid:
                logging.error("MessageID doesn't match up: %i %i" % (s_messageid, self.messageid))
                return

            package = self.s.recv_all(partsize, False)

            data = data + package

        self.messageid += 1

        return data

    def get_file(self, storageid, fileid, totalparts):
        chunks_per_call = 1

        file = []

        for i in range(0, totalparts, chunks_per_call):
            print("%i" % i, end = ' ')
            chunks = self.get_chunks(storageid, fileid, i, chunks_per_call)
            file.extend(chunks)

        return file

    def get_file_with_flag(self, storageid, fileid, totalparts):
        chunks_per_call = 1

        file = []
        filemode = 0xff
        for i in range(0, totalparts, chunks_per_call):
            print("%i" % i, end = ' ')
            (newfilemode, chunks) = self.get_chunks_with_flag(storageid, fileid, i, chunks_per_call)

            if filemode == 0xff:
                filemode = newfilemode

            if filemode != newfilemode:
                logging.error("Filemodes don't match up on the same file: %i %i" % (filemode, newfilemode))

            file.extend(chunks)

        return (filemode, file)

    def get_chunks(self, storageid, fileid, filepart, numparts):
        command = b"\x07" + struct.pack(">LLLLLB", storageid, self.messageid, fileid, filepart, numparts, 0x00)

        self.s.send_withlen(command)

        reply = self.s.recv(17)

        (s_storageid, s_messageid, dummy1, replyparts, filemode) = struct.unpack(">LLbLL", reply)

        logging.debug("Dummy1: %s   Filemode: %s" % (hex(dummy1), hex(filemode)))
        # the filemode is a dword that shows wether the block is encrypted or not, as far as I've seen
        # 0x1 - normal, no encryption
        # 0x2 - encrypted, compressed
        # 0x3 - encrypted, not compressed

        if filemode != 1:
            foobar = open("filemodes.bin", "ab")
            foobar.write(struct.pack(">LLLLb", self.app, self.version, fileid, filepart, filemode))
            foobar.close()

        if s_storageid != storageid:
            logging.error("StorageID doesn't match up: %i %i" % (s_storageid, storageid))
            return -1

        if s_messageid != self.messageid:
            logging.error("MessageID doesn't match up: %i %i" % (s_messageid, self.messageid))
            return -1

        chunks = []
        for i in range(replyparts):

            try:
                reply = self.s.recv(12)
            except socket.error:
                # connection reset by peer
                reply = struct.pack(">LLL", storageid, self.messageid, 0)

            (s_storageid, s_messageid, fullsize) = struct.unpack(">LLL", reply)

            if s_storageid != storageid:
                logging.error("StorageID doesn't match up: %i %i" % (s_storageid, storageid))
                return

            if s_messageid != self.messageid:
                logging.error("MessageID doesn't match up: %i %i" % (s_messageid, self.messageid))
                return

            data = ""

            while len(data) < fullsize:

                reply = self.s.recv(12)

                (s_storageid, s_messageid, partsize) = struct.unpack(">LLL", reply)

                if s_storageid != storageid:
                    logging.error("StorageID doesn't match up: %i %i" % (s_storageid, storageid))
                    return

                if s_messageid != self.messageid:
                    logging.error("MessageID doesn't match up: %i %i" % (s_messageid, self.messageid))
                    return

                package = self.s.recv_all(partsize, False)

                data = data + package

            chunks.append(data)

        self.messageid += 1

        return chunks

    def get_chunks_with_flag(self, storageid, fileid, filepart, numparts):
        command = b"\x07" + struct.pack(">LLLLLB", storageid, self.messageid, fileid, filepart, numparts, 0x00)

        self.s.send_withlen(command)

        reply = self.s.recv(17)

        (s_storageid, s_messageid, dummy1, replyparts, filemode) = struct.unpack(">LLbLL", reply)

        logging.debug("Dummy1: %s   Filemode: %s" % (hex(dummy1), hex(filemode)))
        # the filemode is a dword that shows wether the block is encrypted or not, as far as I've seen
        # 0x1 - normal, no encryption
        # 0x2 - encrypted, compressed
        # 0x3 - encrypted, not compressed

        if filemode != 1:
            foobar = open("filemodes.bin", "ab")
            foobar.write(struct.pack(">LLLLb", self.app, self.version, fileid, filepart, filemode))
            foobar.close()

        if s_storageid != storageid:
            logging.error("StorageID doesn't match up: %i %i" % (s_storageid, storageid))
            return -1

        if s_messageid != self.messageid:
            logging.error("MessageID doesn't match up: %i %i" % (s_messageid, self.messageid))
            return -1

        chunks = []
        for i in range(replyparts):

            try:
                reply = self.s.recv(12)
            except socket.error:
                # connection reset by peer
                reply = struct.pack(">LLL", storageid, self.messageid, 0)

            (s_storageid, s_messageid, fullsize) = struct.unpack(">LLL", reply)

            if s_storageid != storageid:
                logging.error("StorageID doesn't match up: %i %i" % (s_storageid, storageid))
                return

            if s_messageid != self.messageid:
                logging.error("MessageID doesn't match up: %i %i" % (s_messageid, self.messageid))
                return

            data = ""

            while len(data) < fullsize:

                reply = self.s.recv(12)

                (s_storageid, s_messageid, partsize) = struct.unpack(">LLL", reply)

                if s_storageid != storageid:
                    logging.error("StorageID doesn't match up: %i %i" % (s_storageid, storageid))
                    return

                if s_messageid != self.messageid:
                    logging.error("MessageID doesn't match up: %i %i" % (s_messageid, self.messageid))
                    return

                package = self.s.recv_all(partsize, False)

                data = data + package

            chunks.append(data)

        self.messageid += 1

        return (filemode, chunks)