import traceback
import io
import logging
import struct
from libs.CryptICE import IceKey

import globalvars

logger = logging.getLogger('trkrsrv')

ice = IceKey(1, [13, 85, 243, 211, 173, 6, 87, 71])

def di(s):
    return struct.unpack("<I", s)[0]

def ei(n):
    return struct.pack("<I", n)

def parse_size_prepended_value(s):
    size = struct.unpack("<H", s[0:2])[0]
    return s[2:size]

def parse_data(data, typed=False):
    bio = io.BytesIO(data)
    res = {}
    while True:
        datatype = bio.read(1)[0]
        if not datatype & 1:
            break
        key = b""
        while True:
            c = bio.read(1)
            if c == b"\x00":
                break
            key += c
        key = key.decode("utf8")
        sz, = struct.unpack("<H", bio.read(2))
        value = bio.read(sz)
        if datatype & 4 == 0:
            if value[-1] == 0:
                value = value[:-1]
            else:
                logger.error("non-null terminated string")
        if typed:
            res[key] = (datatype, value)
        else:
            res[key] = value
    return res

def write_data(res, typed=False):
    output = io.BytesIO()
    for key, item in res.items():
        if typed:
            datatype, value = item
            if not isinstance(datatype, int):
                raise ValueError(f"Data type for key '{key}' must be an integer.")
            if not isinstance(value, bytes):
                raise ValueError(f"Value for key '{key}' must be of type 'bytes'.")
        else:
            raise ValueError("Data type is required when 'typed' is False.")
        output.write(bytes([datatype]))
        key_bytes = key.encode('utf-8') + b'\x00'
        output.write(key_bytes)
        if (datatype & 4) == 0:
            if not value.endswith(b'\x00'):
                value += b'\x00'
        else:
            if value.endswith(b'\x00'):
                value = value[:-1]
        sz = len(value)
        output.write(struct.pack('<H', sz))
        output.write(value)
    output.write(bytes([0]))
    return output.getvalue()

def validate_msg(msg, mandatory, optional=()):
    for key in mandatory:
        if key not in msg:
            logger.error(f"Missing key {key}")
    for key in msg:
        if key != "_id" and key not in mandatory and key not in optional:
            logger.error(f"Unexpected key {key}")

class Message:
    def __init__(self, client, cmdid, ack=False):
        self.client = client
        self.sessionid = client.sessionid
        self.kv = {}
        self.msg = b""
        self.cmdid = cmdid
        self.seqnum = client.seqnum
        self.reply_to = client.r_seqnum
        self.padding = b""
        self.ack = ack
        self.unknownbyte = 0
        if globalvars.record_ver == 1 or globalvars.record_ver == 0:
            self.add_int("_id", cmdid)
        else:
            self.msg += struct.pack("<H", cmdid)

    def add_kv(self, mode, key, value):
        if key in self.kv:
            logger.warning(f"Duplicate key {key}")
        self.kv[key] = (mode, value)
        self.msg += bytes([mode])
        self.msg += bytes(key, "utf-8") + b"\x00"
        self.msg += struct.pack("<H", len(value))
        self.msg += value

    def add_bin(self, key, s):
        self.add_kv(5, key, s)

    def add_int(self, key, n):
        self.add_kv(5, key, ei(n))

    def add_pad(self):
        self.msg += b"\x00"

    def add_str(self, key, s):
        if s is None:
            self.add_kv(1, key, b"\x00")
            return
        if isinstance(s, str):
            s = s.encode('utf-8')
        try:
            self.add_kv(1, key, s + b"\x00")
        except Exception as e:
            logger.error("Error adding string to packet!\n %s", e)
            traceback.print_exc()

    def add_key(self, s):
        self.add_kv(5, "key", s)

    def getpacket_beta(self):
        logger.debug(f"preparing packet with id {self.cmdid:d}  clientid  {self.client.clientid:d}  sessionid {self.sessionid:d}  seqnum {self.seqnum:d}  replyto {self.reply_to:d}")
        logger.debug(f"keyvalues {self.kv}")
        data = struct.pack("<IIIIBB", self.client.clientid, self.sessionid, self.seqnum, self.reply_to, 1, 1)
        data += self.msg + b"\x00" + self.padding
        if not self.ack:
            while len(data) % 8 != 4:
                data += b"\x00"
        data = b"\x04\x16" + struct.pack("<H", len(data) + 4) + data
        if not self.ack:
            return b"\xfe\xff\xff\xff" + ice.Encrypt(data)
        else:
            return data

    def getpacket(self):
        logger.debug(f"preparing packet with id {self.cmdid:d}  clientid  {self.client.clientid:d}  sessionid {self.sessionid:d}  seqnum {self.seqnum:d}  replyto {self.reply_to:d}")
        logger.debug(f"keyvalues {self.kv}")
        data = b"\x05"
        data += struct.pack("<IIBBB", self.client.clientid, self.sessionid, self.seqnum, self.reply_to, self.unknownbyte)
        data += self.msg + b"\x00"
        padding_needed = (16 - len(data) % 16) % 16
        data += b"\x00" * padding_needed
        if not self.ack:
            return b"\xfe" + ice.Encrypt(data)
        else:
            return data

class Packet_Beta:
    def __init__(self, data):
        if data[0:4] == b"\xfe\xff\xff\xff":
            data = ice.Decrypt(data[4:])
            logger.debug(f"decrypted {data.hex()}")
        if data[0:2] != b"\x04\x16" or len(data) < 0x16:
            raise
        self.version, self.headersize, self.packetsize, self.clientid, self.sessionid, self.seqnum, self.seqack, self.packetnum, self.totalpackets = struct.unpack("<BBHIIIIBB", data[:0x16])
        if self.packetsize != len(data):
            logger.error("BAD SIZE Data:\n%s", repr(data))
            raise
        logger.debug("(Beta) decrypted\n%s", repr(data))
        data += b"\x00"
        self.data = data

class Packet:
    def __init__(self, data):
        self.headersize = 0
        self.packetsize = 0
        self.packetnum = 1
        encrypted_data = bytearray(data)
        self.data = ice.Decrypt(encrypted_data[1:]) + b"\x00"
        if self.data[0:1] != b"\x05" or len(data) < 0x0E:
            logger.error("BAD HEADER (2004) data:\n%s", data)
        (self.version, self.clientid, self.sessionid, self.seqnum, self.seqack, self.totalpackets) = struct.unpack("<BIIBBB", self.data[:0x0C])
        logger.warning("(Retail) decrypted:\n%s", repr(self.data))