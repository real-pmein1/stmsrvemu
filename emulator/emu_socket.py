import binascii, socket, struct, zlib, os, sys, logging
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA
from Crypto.Cipher import AES


from steamemu.config import read_config
config = read_config()

def decodeIP(string) :
    (oct1, oct2, oct3, oct4, port) = struct.unpack("<BBBBH", string)
    ip = "%d.%d.%d.%d" % (oct1, oct2, oct3, oct4)
    return ip, port


def encodeIP((ip, port)) :
    if type(port) == str :
        port = int(port)
    oct = ip.split(".")
    string = struct.pack("<BBBBH", int(oct[0]), int(oct[1]), int(oct[2]), int(oct[3]), port)
    return string


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
            logging.debug("Command header not long enough, should be 4, is " + str(len(lengthstr)))
            return "\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00" #DUMMY RETURN FOR FILESERVER
        else :
            length = struct.unpack(">L", lengthstr)[0]
            data = self.recv_all(length, False)
            logging.debug(str(self.address) + ": Received data with length  - " + binascii.b2a_hex(lengthstr) + " " + binascii.b2a_hex(data))
            return data
