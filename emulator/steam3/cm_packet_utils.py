import logging
import struct
import io
import zlib
from types import GeneratorType as _GeneratorType
from typing import Union

import observable
from google.protobuf.message import Message as _ProtoMessageType
from google.protobuf import message as _message

import globalvars
from steam3 import Types, thread_local_data
from steam3.Types.emsg import EMsg
from steam3.Types.steamid import SteamID
from steam3.protobufs import steammessages_base_pb2
from steam3.protobufs import gc_pb2

log = logging.getLogger(f"CMPKT")

# Utility functions and constants
protobuf_mask = 0x80000000

def is_proto(emsg):
    return (int(emsg) & protobuf_mask) > 0

def set_proto_bit(emsg):
    return int(emsg) | protobuf_mask

def clear_proto_bit(emsg):
    return int(emsg) & ~protobuf_mask

_list_types = (list, range, map, filter, _GeneratorType)

def proto_to_dict(message):
    if not isinstance(message, _ProtoMessageType):
        raise TypeError("Expected `message` to be an instance of protobuf message")

    data = {}

    for desc, field in message.ListFields():
        if desc.type == desc.TYPE_MESSAGE:
            if desc.label == desc.LABEL_REPEATED:
                data[desc.name] = [proto_to_dict(item) for item in field]
            else:
                data[desc.name] = proto_to_dict(field)
        else:
            data[desc.name] = list(field) if desc.label == desc.LABEL_REPEATED else field

    return data

def proto_fill_from_dict(message, data, clear=True):
    if not isinstance(message, _ProtoMessageType):
        raise TypeError("Expected `message` to be an instance of protobuf message")
    if not isinstance(data, dict):
        raise TypeError("Expected `data` to be of type `dict`")

    if clear:
        message.Clear()
    field_descs = message.DESCRIPTOR.fields_by_name

    for key, val in data.items():
        desc = field_descs[key]

        if desc.type == desc.TYPE_MESSAGE:
            if desc.label == desc.LABEL_REPEATED:
                if not isinstance(val, _list_types):
                    raise TypeError("Expected %s to be of type list, got %s" % (repr(key), type(val)))

                list_ref = getattr(message, key)

                if not clear:
                    del list_ref[:]

                for item in val:
                    item_message = list_ref.add()
                    proto_fill_from_dict(item_message, item)
            else:
                if not isinstance(val, dict):
                    raise TypeError("Expected %s to be of type dict, got %s" % (repr(key), type(dict)))

                proto_fill_from_dict(getattr(message, key), val)
        else:
            if isinstance(val, _list_types):
                list_ref = getattr(message, key)
                if not clear:
                    del list_ref[:]
                list_ref.extend(val)
            else:
                setattr(message, key, val)

    return message

# Deprecated Message header is from client to server
class MsgHdr_deprecated:
    _size = 16

    def __init__(self, eMsgID=0x0, accountID=0xffffffff, clientId2=0xffffffff, sessionID=0xffffffff, data=b''):
        self.eMsgID = eMsgID
        self.accountID = accountID
        self.clientId2 = clientId2
        self.sessionID = sessionID
        self.data = data
        self.length = 0

    def serialize(self):
        serialized_data = struct.pack('<IIII', self.eMsgID, self.accountID, self.clientId2, self.sessionID) + self.data
        self.length = len(serialized_data)
        return serialized_data

    def load(self, data):
        (msg, self.accountID, self.clientId2, self.sessionID) = struct.unpack_from("<IIII", data)
        self.eMsgID = EMsg(msg)
        self.data = data[self._size:]
        return self

    def __repr__(self):
        return (f"deprecated_responsehdr(eMsgID={self.eMsgID}, data={self.data}, "
                f"accountID={getattr(self, 'accountID', None)}, "
                f"clientID2={getattr(self, 'clientID2', None)}, "
                f"sessionID={getattr(self, 'sessionID', None)})")

# Message header is from server to client
class MsgHdr:
    _size = struct.calcsize("<Iqq")
    eMsgID = EMsg.Invalid
    targetJobID = -1
    sourceJobID = -1
    length = 0
    data = b''

    def __init__(self, data=None):
        if data:
            self.load(data)

    def serialize(self):
        serialized_data = struct.pack("<Iqq", self.eMsgID, self.targetJobID, self.sourceJobID) + self.data
        self.length = len(serialized_data)
        return serialized_data

    def load(self, data):
        (msg, self.targetJobID, self.sourceJobID) = struct.unpack_from("<Iqq", data)
        self.eMsgID = EMsg(msg)
        self.data = data[self._size:]

    def __str__(self):
        return '\n'.join(["eMsgID: %s" % repr(self.eMsgID),
                          "targetJobID: %s" % self.targetJobID,
                          "sourceJobID: %s" % self.sourceJobID,
                          "data: %s" % self.data,
                          ])

# Extended Message Headers are from client to server and server to client
class ExtendedMsgHdr:
    _size = 36
    eMsgID = EMsg.Invalid
    headerSize = 36
    headerVersion = 2
    targetJobID = -1
    sourceJobID = -1
    headerCanary = 239
    accountID = -1
    sessionID = -1
    clientId2 = -1
    data = b''
    length = 0

    def __init__(self, eMsgID=0, client_obj=None, data=None):
        self.eMsgID = eMsgID

        if client_obj:
            self.accountID = client_obj.steamID * 2
            self.clientId2 = client_obj.clientID2
            self.sessionID = client_obj.sessionID

        if data:
            self.load(data)

    def serialize(self):
        serialized_data = struct.pack("<IBHqqBIIi",
                                      self.eMsgID,
                                      self.headerSize,
                                      self.headerVersion,
                                      self.targetJobID,
                                      self.sourceJobID,
                                      self.headerCanary,
                                      self.accountID,
                                      self.clientId2,
                                      self.sessionID,
                                      ) + self.data
        self.length = len(serialized_data)
        return serialized_data

    def load(self, data):
        if len(data) < self._size:
            raise RuntimeError("Data too short to contain a valid header")

        (eMsgID,
         self.headerSize,
         self.headerVersion,
         self.targetJobID,
         self.sourceJobID,
         self.headerCanary,
         self.accountID,
         self.clientId2,
         self.sessionID) = struct.unpack_from("<IBHqqBIIi", data)

        self.eMsgID = EMsg(eMsgID)

        # Now ensure that we skip over the entire header when extracting the data
        self.data = data[self._size:]  # Slice the data after the header
        self.length = len(self.data)

        print(f"extended message full data with header: {data}")
        print(f"extended message data without header: {self.data}")

        # Validation: ensure that headerSize and headerVersion match expected values
        if self.headerSize != 36 or self.headerVersion != 2:
            raise ValueError("Failed to parse header")
        return self
    def __str__(self):
        return '\n'.join(["eMsgID: %s" % self.eMsgID,
                          "headerSize: %s" % self.headerSize,
                          "headerVersion: %s" % self.headerVersion,
                          "targetJobID: %s" % self.targetJobID,
                          "sourceJobID: %s" % self.sourceJobID,
                          "headerCanary: %s" % self.headerCanary,
                          "accountID: %s" % self.accountID,
                          "clientID2: %s" % self.clientId2,
                          "sessionID: %s" % self.sessionID,
                          "data: %s" % self.data,
                          ])

class MsgHdrProtoBuf:
    _size = _fullsize = struct.calcsize("<II")
    msg = EMsg.Invalid

    def __init__(self, data=None):
        self.proto = steammessages_base_pb2.CMsgProtoBufHeader()

        if data:
            self.load(data)

    def serialize(self):
        proto_data = self.proto.SerializeToString()
        return struct.pack("<II", set_proto_bit(self.msg), len(proto_data)) + proto_data

    def load(self, data):
        msg, proto_length = struct.unpack_from("<II", data)

        self.msg = EMsg(clear_proto_bit(msg))
        size = MsgHdrProtoBuf._size
        self._fullsize = size + proto_length
        self.proto.ParseFromString(data[size:self._fullsize])

class GCMsgHdr:
    _size = struct.calcsize("<Hqq")
    proto = None
    headerVersion = 1
    targetJobID = -1
    sourceJobID = -1
    length = 1
    data = b''

    def __init__(self, msg, data=None):
        self.msg = clear_proto_bit(msg)
        if data:
            self.load(data)

    def serialize(self):
        return struct.pack("<Hqq",
                           self.headerVersion,
                           self.targetJobID,
                           self.sourceJobID,
                           ) + self.data

    def load(self, data):
        (self.headerVersion,
         self.targetJobID,
         self.sourceJobID,
         ) = struct.unpack_from("<Hqq", data)
        self.data = data[self._size:]

    def __str__(self):
        return '\n'.join(["headerVersion: %s" % self.headerVersion,
                          "targetJobID: %s" % self.targetJobID,
                          "sourceJobID: %s" % self.sourceJobID,
                          "data: %s" % self.data,
                          ])

class GCMsgHdrProto:
    _size = struct.calcsize("<Ii")
    headerLength = 0

    def __init__(self, msg, data=None):
        self.proto = gc_pb2.CMsgProtoBufHeader()
        self.msg = clear_proto_bit(msg)

        if data:
            self.load(data)

    def serialize(self):
        proto_data = self.proto.SerializeToString()
        self.headerLength = len(proto_data)

        return struct.pack("<Ii",
                           set_proto_bit(self.msg),
                           self.headerLength,
                           ) + proto_data

    def load(self, data):
        (msg,
         self.headerLength,
         ) = struct.unpack_from("<Ii", data)

        self.msg = clear_proto_bit(msg)

        if self.headerLength:
            x = GCMsgHdrProto._size
            self.proto.ParseFromString(data[x:x + self.headerLength])
        self.data = data[self._size + self.headerLength:]

    def __str__(self):
        resp = ["msg: %s" % self.msg,
                "headerLength: %s" % self.headerLength,
                ]

        proto = str(self.proto)

        if proto:
            resp.append('-- proto --')
            resp.append(proto)

        return '\n'.join(resp)

class deprecated_responsehdr:

    def __init__(self, eMsgID=0, client_obj=None):
        self.eMsgID = eMsgID
        self.length = 0
        self.data = b''
        if client_obj:
            self.accountID = client_obj.steamID * 2
            self.clientID2 = client_obj.clientID2
            self.sessionID = client_obj.sessionID

    def serialize(self):
        serialized_data = struct.pack('<IIII', self.eMsgID, self.accountID, self.clientID2, self.sessionID) + self.data
        self.length = len(serialized_data)
        return serialized_data

    def __repr__(self):
        return (f"deprecated_responsehdr(eMsgID={self.eMsgID}, length={self.length}, data={self.data}, "
                f"accountID={getattr(self, 'accountID', None)}, "
                f"clientID2={getattr(self, 'clientID2', None)}, "
                f"sessionID={getattr(self, 'sessionID', None)})")


MSG_LARGE_MESSAGE_LIMIT = 1000  # As in the C++ code

class MsgMulti():
    def __init__(self):
        self.compressed = True
        self.jobIDTarget = -1
        self.jobIDSource = -1
        self.body = {
                'decompressedSize': 0,
                'messages': [],
                'unknownMessages': []
        }
        self.data = b''

    def deserialize(self, in_stream):
        self.jobIDTarget = struct.unpack('<Q', in_stream.read(4))[0]
        self.jobIDSource = struct.unpack('<Q', in_stream.read(4))[0]
        self.body['decompressedSize'] = struct.unpack('<I', in_stream.read(4))[0]
        self.compressed = self.body['decompressedSize'] != 0

        if self.compressed:
            compressed_data = in_stream.read()
            decompressed_data = zlib.decompress(compressed_data)
            data_in = io.BytesIO(decompressed_data)
            self.parseMessages(data_in)
        else:
            self.parseMessages(in_stream)

    def serialize(self):
        # Create a byte buffer instead of using out_stream
        data_out = io.BytesIO()

        # Write the job IDs to the buffer
        data_out.write(struct.pack('<Q', self.jobIDTarget))
        data_out.write(struct.pack('<Q', self.jobIDSource))

        # Create a temporary buffer to hold the message data
        message_out = io.BytesIO()
        self.writeMessages(message_out)
        data_bytes = message_out.getvalue()

        # Handle compression if necessary
        if not self.compressed or len(data_bytes) < MSG_LARGE_MESSAGE_LIMIT:
            data_out.write(struct.pack('<I', 0))  # No compression
            data_out.write(data_bytes)
        else:
            self.body['decompressedSize'] = len(data_bytes)
            data_out.write(struct.pack('<I', self.body['decompressedSize']))  # Compression header
            compressed_data = zlib.compress(data_bytes)
            data_out.write(compressed_data)

        # Store the complete byte string in self.data
        self.data = data_out.getvalue()

        # Return the serialized data
        return self.data

    def parseMessages(self, in_stream):
        self.body['messages'].clear()
        self.body['unknownMessages'].clear()
        in_stream.seek(0)
        total_length = len(in_stream.getvalue())

        while in_stream.tell() < total_length:
            message_length_bytes = in_stream.read(4)
            if len(message_length_bytes) < 4:
                break  # Not enough data

            message_length = struct.unpack('<I', message_length_bytes)[0]
            data = in_stream.read(message_length)

            if len(data) < message_length:
                break  # Not enough data

            try:
                # Create a new instance of ExtendedMsgHdr and load data into it
                message = ExtendedMsgHdr()
                message.load(data)
                self.body['messages'].append(message)
            except Exception as e:
                # If message parsing fails, store it as an unknown message
                self.body['unknownMessages'].append(data)

    def writeMessages(self, out_stream):
        for message in self.body['messages']:
            data = message.serialize()
            out_stream.write(struct.pack('<I', len(data)))
            out_stream.write(data)
        for unknown_data in self.body['unknownMessages']:
            out_stream.write(struct.pack('<I', len(unknown_data)))
            out_stream.write(unknown_data)

    def add(self, message):
        self.body['messages'].append(message)

# CM Response is from server to client
class CMResponse:
    def __init__(self, eMsgID=0, client_obj=None):
        if client_obj.is_newPacketType is True:
            self.__class__ = ExtendedMsgHdr
            ExtendedMsgHdr.__init__(self, eMsgID, client_obj)
            self.headerSize = thread_local_data.extended_msg.headerSize
            self.headerVersion = thread_local_data.extended_msg.headerVersion
            self.targetJobID = thread_local_data.extended_msg.sourceJobID
            self.sourceJobID = thread_local_data.extended_msg.targetJobID
            self.headerCanary = thread_local_data.extended_msg.headerCanary
            self.accountID = client_obj.steamID * 2
            self.clientId2 = client_obj.clientID2
            self.sessionID = client_obj.sessionID
        else:
            self.__class__ = deprecated_responsehdr
            deprecated_responsehdr.__init__(self, eMsgID, client_obj)

# MsgHdr_deprecated.data if request_cmd_id = chatmessage
class ChatMessage:
    def __init__(self, from_=0, to=0, clientid2=0, type_=0, message=''):
        self.from_ = from_
        self.to = to
        self.sessionID = clientid2
        self.type = type_
        self.message = message

    @classmethod
    def parse(cls, from_, data):
        to, clientId2, type_ = struct.unpack('<III', data[:12])
        message = data[12:].split(b'\x00', 1)[0].decode('latin-1')
        return cls(from_=from_, to=to, clientid2=clientId2, type_=type_, message=message)

class CMPacket:
    def __init__(self, header=0, size=0, packetid=0, priority_level=0, destination_id=0, source_id=0, sequence_num=0, last_recv_seq=0, split_pkt_cnt=0, seq_of_first_pkt=0, data_len=0, data=b''):
        self.magic = header

        self.size = size
        self.packetid = packetid
        self.priority_level = priority_level
        self.destination_id = destination_id
        self.source_id = source_id
        self.sequence_num = sequence_num
        self.last_recv_seq = last_recv_seq
        self.split_pkt_cnt = split_pkt_cnt
        self.seq_of_first_pkt = seq_of_first_pkt

        self.data_len = data_len
        self.data = data
        self.is_tcp = False
        self.CMRequest = None

    def parse(self, datagram):
        packet = CMPacket()
        pos = 0

        format_str = 'I H c c I I I I I I I'
        fields = struct.unpack_from(format_str, datagram)
        packet.magic, packet.size, packet.packetid, packet.priority_level, packet.destination_id, packet.source_id, packet.sequence_num, packet.last_recv_seq, packet.split_pkt_cnt, packet.seq_of_first_pkt, packet.data_len = fields

        packet.data = datagram[36:] if packet.size > 0 else 0

        return packet

    def serialize(self):
        if isinstance(self.packetid, int):
            self.packetid = self.packetid.to_bytes(1, "little")
        if isinstance(self.priority_level, int):
            self.priority_level = self.priority_level.to_bytes(1, "little")
        format_str = 'I H c c I I I I I I I'
        packed_data = struct.pack(format_str, self.magic, self.size, self.packetid, self.priority_level, self.destination_id, self.source_id, self.sequence_num, self.last_recv_seq, self.split_pkt_cnt, self.seq_of_first_pkt, self.data_len)
        packed_data += self.data if self.size > 0 else b''
        return packed_data

    def parse_CMRequest(self):
        if self.data == 0 or len(self.data) < 4:
            log.error("Data too short to contain an EMsg!")
            return None

        if len(self.data) >= 16:
            try:
                self.CMRequest = ExtendedMsgHdr()
                self.CMRequest.load(self.data)
                self.CMRequest.data = self.data[36:]

                return self.CMRequest
            except Exception:
                format_str = 'I I I I'
                self.CMRequest = MsgHdr_deprecated()

                if self.data == 0:
                    return 0
                else:
                    try:
                        self.CMRequest.eMsgID, self.CMRequest.accountID, self.CMRequest.clientId2, self.CMRequest.sessionID = struct.unpack_from(format_str, self.data)
                        self.CMRequest.data = self.data[16:]
                    except struct.error as e:
                        log.error(f"Error unpacking packet data: {e}")
                return self.CMRequest
        else:
            log.error("Could not determine Packet Type from Header!")
            self.CMRequest = None
            return None
        return self.CMRequest

    def __str__(self):
        return (
                f"CMPacket(\n"
                f"  header={self.magic},\n"
                f"  size={self.size},\n"
                f"  packetid={self.packetid},\n"
                f"  priority_level={self.priority_level},\n"
                f"  destination_id={self.destination_id},\n"
                f"  source_id={self.source_id},\n"
                f"  sequence_num={self.sequence_num},\n"
                f"  last_recv_seq={self.last_recv_seq},\n"
                f"  split_pkt_cnt={self.split_pkt_cnt},\n"
                f"  seq_of_first_pkt={self.seq_of_first_pkt},\n"
                f"  data_len={self.data_len},\n"
                f"  data={self.data},\n"
                f"  CMRequest={self.CMRequest}\n"
                f")"
        )

    def __repr__(self):
        return (
                f"CMPacket(\n"
                f"  header={self.magic},\n"
                f"  size={self.size},\n"
                f"  packetid={self.packetid},\n"
                f"  priority_level={self.priority_level},\n"
                f"  destination_id={self.destination_id},\n"
                f"  source_id={self.source_id},\n"
                f"  sequence_num={self.sequence_num},\n"
                f"  last_recv_seq={self.last_recv_seq},\n"
                f"  split_pkt_cnt={self.split_pkt_cnt},\n"
                f"  seq_of_first_pkt={self.seq_of_first_pkt},\n"
                f"  data_len={self.data_len},\n"
                f"  data={self.data!r},\n"
                f"  CMRequest={self.CMRequest!r}\n"
                f")"
        )

"""class CMPacket:
    def __init__(self, header=0, size=0, packetid=0, priority_level=0, destination_id=0, source_id=0, sequence_num=0, last_recv_seq=0, split_pkt_cnt=0, seq_of_first_pkt=0, data_len=0, data=b''):
        self.magic = header

        self.size = size
        self.packetid = packetid
        self.priority_level = priority_level
        self.destination_id = destination_id
        self.source_id = source_id
        self.sequence_num = sequence_num
        self.last_recv_seq = last_recv_seq
        self.split_pkt_cnt = split_pkt_cnt
        self.seq_of_first_pkt = seq_of_first_pkt

        self.data_len = data_len
        self.data = data
        self.is_tcp = False
        self.CMRequest = None

    def parse(self, datagram):
        packet = CMPacket()
        pos = 0

        format_str = 'I H c c I I I I I I I'
        fields = struct.unpack_from(format_str, datagram)
        packet.magic, packet.size, packet.packetid, packet.priority_level, packet.destination_id, packet.source_id, packet.sequence_num, packet.last_recv_seq, packet.split_pkt_cnt, packet.seq_of_first_pkt, packet.data_len = fields

        packet.data = datagram[36:] if packet.size > 0 else 0

        return packet

    def serialize(self):
        if isinstance(self.packetid, int):
            self.packetid = self.packetid.to_bytes(1, "little")
        if isinstance(self.priority_level, int):
            self.priority_level = self.priority_level.to_bytes(1, "little")
        format_str = 'I H c c I I I I I I I'
        packed_data = struct.pack(format_str, self.magic, self.size, self.packetid, self.priority_level, self.destination_id, self.source_id, self.sequence_num, self.last_recv_seq, self.split_pkt_cnt, self.seq_of_first_pkt, self.data_len)
        packed_data += self.data if self.size > 0 else b''
        return packed_data

    def parse_CMRequest(self):
        if self.data == 0 or len(self.data) < 4:
            log.error("Data too short to contain an EMsg!")
            return None

        # Read the first 4 bytes to get the EMsg
        emsg_value, = struct.unpack_from("<I", self.data)
        emsg = EMsg(clear_proto_bit(emsg_value))
        proto = is_proto(emsg_value)

        # Determine if it's a GC message
        gc_msg = emsg in (EMsg.ClientToGC, EMsg.ClientFromGC)

        print(f"packet: {Types.get_enum_name(EMsg, emsg)}\nis protobuf: {proto}  is gc: {gc_msg}")
        # Parse the header and body accordingly
        if gc_msg:
            # Handle GC messages
            if proto:
                self.CMRequest = GCMsgHdrProto(emsg)
                self.CMRequest.load(self.data)
            else:
                self.CMRequest = GCMsgHdr(emsg)
                self.CMRequest.load(self.data[4:])  # Skip the EMsg
        else:
            # Handle regular messages
            if proto:
                self.CMRequest = MsgHdrProtoBuf()
                self.CMRequest.load(self.data)
            else:
                # Determine if it's an extended header or deprecated header
                if len(self.data) >= 16:
                    try:
                        self.CMRequest = ExtendedMsgHdr()
                        self.CMRequest.load(self.data)
                        self.CMRequest.data = self.data[36:]

                        return self.CMRequest
                    except Exception:
                        format_str = 'I I I I'
                        self.CMRequest = MsgHdr_deprecated()

                        if self.data == 0:
                            return 0
                        else:
                            try:
                                self.CMRequest.eMsgID, self.CMRequest.accountID, self.CMRequest.clientId2, self.CMRequest.sessionID = struct.unpack_from(format_str, self.data)
                                self.CMRequest.data = self.data[16:]
                            except struct.error as e:
                                log.error(f"Error unpacking packet data: {e}")
                        return self.CMRequest
                else:
                    log.error("Could not determine Packet Type from Header!")
                    self.CMRequest = None
                    return None

        # Set the data attribute in CMRequest to the remaining data
        #self.CMRequest.data = self.data[self.CMRequest._size:]
        return self.CMRequest

    def __str__(self):
        return (
            f"CMPacket(\n"
            f"  header={self.magic},\n"
            f"  size={self.size},\n"
            f"  packetid={self.packetid},\n"
            f"  priority_level={self.priority_level},\n"
            f"  destination_id={self.destination_id},\n"
            f"  source_id={self.source_id},\n"
            f"  sequence_num={self.sequence_num},\n"
            f"  last_recv_seq={self.last_recv_seq},\n"
            f"  split_pkt_cnt={self.split_pkt_cnt},\n"
            f"  seq_of_first_pkt={self.seq_of_first_pkt},\n"
            f"  data_len={self.data_len},\n"
            f"  data={self.data},\n"
            f"  CMRequest={self.CMRequest}\n"
            f")"
        )

    def __repr__(self):
        return self.__str__()"""


"""class CMPacket:
    # UDP packets have the 'larger' header
    # TCP only contains a 4 byte size followed by the 4 byte vt01
    def __init__(self, magic=0, size=0, packetid=0, priority_level=0, destination_id=0, source_id=0, sequence_num=0, last_recv_seq=0, split_pkt_cnt=0, seq_of_first_pkt=0, data_len=0, data=b'', clientobj = None):

        self.magic = magic
        self.size = size
        self.packetid = packetid
        self.priority_level = priority_level
        self.destination_id = destination_id
        self.source_id = source_id
        self.sequence_num = sequence_num
        self.last_recv_seq = last_recv_seq
        self.split_pkt_cnt = split_pkt_cnt
        self.seq_of_first_pkt = seq_of_first_pkt
        self.data_len = data_len
        self.data = data
        self.is_tcp = False
        self.clientobj = clientobj

        if self.is_tcp:
            self._format_str = 'I I I'
            self.header_size = 8
        else:  # UDP
            self._format_str = 'I H c c I I I I I I I'
            self.header_size = 36

        self.CMRequest: Union[MsgHdr_deprecated, ExtendedMsgHdr, GCMsgHdr, MsgHdrProtoBuf, GCMsgHdrProto] = None

    def parse(self, raw_packet):
        packet = CMPacket()

        fields = struct.unpack_from(self._format_str, raw_packet)
        if self.is_tcp:
            packet.size, packet.magic, packet.packetid = fields
        else:
            packet.magic, packet.size, packet.packetid, packet.priority_level, packet.destination_id, packet.source_id, packet.sequence_num, packet.last_recv_seq, packet.split_pkt_cnt, packet.seq_of_first_pkt, packet.data_len = fields

        packet.data = raw_packet[self.header_size:] if packet.size > 0 else 0

        return packet

    def serialize(self):
        if isinstance(self.packetid, int):
            self.packetid = self.packetid.to_bytes(1, "little")
        if isinstance(self.priority_level, int):
            self.priority_level = self.priority_level.to_bytes(1, "little")
        if self.is_tcp:
            data = self.size, self.magic
        else:
            data = self.magic, self.size, self.packetid, self.priority_level, self.destination_id, self.source_id, self.sequence_num, self.last_recv_seq, self.split_pkt_cnt, self.seq_of_first_pkt, self.data_len
        packed_data = struct.pack(self._format_str, *data)
        packed_data += self.data if self.size > 0 else b''
        return packed_data

    # Added: Method to handle MasterMsg logic
    def parse_master_msg(self):
        if len(self.data) < self.header_size + 4:
            log.error("Data too short to contain an EMsg!")

        emsg, = struct.unpack_from("<I", self.data)
        msg = EMsg(clear_proto_bit(emsg))
        proto = is_proto(emsg)

        # Determine if it's a GC message
        gc_msg = msg in (EMsg.ClientToGC, EMsg.ClientFromGC)

        # Parse the header and body accordingly
        if gc_msg:
            # Handle GC messages
            if proto:
                self.CMRequest = GCMsgHdrProto(emsg, self.data)
            else:
                self.CMRequest = GCMsgHdr(emsg, self.data[4:])  # Skip the EMsg
        else:
            # Handle regular messages
            if proto:
                self.CMRequest = MsgHdrProtoBuf(self.data)
            else:
                # Determine if it's an extended header by trying to deserialize as ExtendedMsgHdr
                if len(self.data[self.header_size:]) >= MsgHdr_deprecated._size:
                    try:
                        # First try extended message type, if that raises an exception, then try the deprecated
                        # message type
                        self.CMRequest = ExtendedMsgHdr()
                        return self.CMRequest.load(self.data)
                    except:
                        # Extended message type raised an exception, try deprecated message type
                        self.CMRequest = MsgHdr_deprecated()
                        return self.CMRequest.load(self.data)
                        '''if globalvars.steamui_ver >= 479:
                            pass
                        else:
                            # we either have an issue or something else is not right in the code
                            log.error(f"Could not determine Packet Type from Header!")
                            self.CMRequest = None'''
                else:
                    # we either have an issue or something else is not right in the code
                    log.error(f"Could not determine Packet Type from Header!")
                    self.CMRequest = None
                    return 0
        return self.CMRequest

    def __str__(self):
        return (
                f"CMPacket(\n"
                f"  header={self.magic},\n"
                f"  size={self.size},\n"
                f"  packetid={self.packetid},\n"
                f"  priority_level={self.priority_level},\n"
                f"  destination_id={self.destination_id},\n"
                f"  source_id={self.source_id},\n"
                f"  sequence_num={self.sequence_num},\n"
                f"  last_recv_seq={self.last_recv_seq},\n"
                f"  split_pkt_cnt={self.split_pkt_cnt},\n"
                f"  seq_of_first_pkt={self.seq_of_first_pkt},\n"
                f"  data_len={self.data_len},\n"
                f"  data={self.data},\n"
                f"  CMRequest={self.CMRequest}\n"
                f")"
        )

    def __repr__(self):
        return (
                f"CMPacket(\n"
                f"  header={self.magic},\n"
                f"  size={self.size},\n"
                f"  packetid={self.packetid},\n"
                f"  priority_level={self.priority_level},\n"
                f"  destination_id={self.destination_id},\n"
                f"  source_id={self.source_id},\n"
                f"  sequence_num={self.sequence_num},\n"
                f"  last_recv_seq={self.last_recv_seq},\n"
                f"  split_pkt_cnt={self.split_pkt_cnt},\n"
                f"  seq_of_first_pkt={self.seq_of_first_pkt},\n"
                f"  data_len={self.data_len},\n"
                f"  data={self.data!r},\n"
                f"  CMRequest={self.CMRequest!r}\n"
                f")"
        )"""

# MasterMsg class that determines the message type and handles it accordingly
class MasterMsg:
    def __init__(self, data):
        self.data = data
        self.msg = None  # The EMsg
        self.header = None
        self.body = None
        self.proto = False  # Whether it's a protobuf message
        self.gc = False     # Whether it's a GC message

        self.parse_message()

    def parse_message(self):
        # First, try to read the EMsg
        if len(self.data) < 4:
            raise ValueError("Data too short to contain an EMsg")
        emsg, = struct.unpack_from("<I", self.data)
        self.msg = EMsg(clear_proto_bit(emsg))
        self.proto = is_proto(emsg)

        # Determine if it's a GC message
        if self.msg in (EMsg.ClientToGC, EMsg.ClientFromGC):
            self.gc = True

        # Now parse the header and body accordingly
        if self.gc:
            # Handle GC messages
            if self.proto:
                self.header = GCMsgHdrProto(emsg, self.data)
                self.body = self.header.data
            else:
                self.header = GCMsgHdr(emsg, self.data[4:])  # Skip the EMsg
                self.body = self.header.data
        else:
            # Handle regular messages
            if self.proto:
                self.header = MsgHdrProtoBuf(self.data)
                self.body = self.data[self.header._fullsize:]
            else:
                # Determine if it's an extended header
                if len(self.data) >= ExtendedMsgHdr._size:
                    # Try to parse as ExtendedMsgHdr
                    try:
                        self.header = ExtendedMsgHdr(data=self.data)
                        self.body = self.header.data
                    except Exception:
                        # Fallback to MsgHdr
                        self.header = MsgHdr(self.data)
                        self.body = self.header.data
                else:
                    self.header = MsgHdr(self.data)
                    self.body = self.header.data

    def __str__(self):
        return (
                f"MasterMsg(\n"
                f"  msg={self.msg},\n"
                f"  proto={self.proto},\n"
                f"  gc={self.gc},\n"
                f"  header={self.header},\n"
                f"  body={self.body}\n"
                f")"
        )

    def __repr__(self):
        return self.__str__()