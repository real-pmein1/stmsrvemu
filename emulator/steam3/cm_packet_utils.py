import logging
import struct
import io
import os
import importlib
import zlib
import observable
from types import GeneratorType as _GeneratorType
from typing import Union
from google.protobuf.message import Message as _ProtoMessageType
from google.protobuf import message as _message

import globalvars
from steam3 import Types, thread_local_data
from steam3.Types.emsg import EMsg
from steam3.Types.steamid import SteamID
from steam3.protobufs.steammessages_base_pb2 import CMsgProtoBufHeader  # Adjust as needed
from steam3.Types import get_enum_name
from steam3.protobufs import steammessages_base_pb2
from steam3.protobufs import gc_pb2

log = logging.getLogger(f"CMPKT")

# Utility functions and constants
protobuf_mask = 0x80000000
_list_types = (list, range, map, filter, _GeneratorType)
# Pre-load Protobuf classes at module import
proto_map = {}

def is_proto(emsg):
    return (int(emsg) & protobuf_mask) > 0

def set_proto_bit(emsg):
    return int(emsg) | protobuf_mask

def clear_proto_bit(emsg):
    return int(emsg) & ~protobuf_mask

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
        print(f"Message Type: {message}")
        #print(f"Parsed Proto: {proto}")
    return message


def _load_protobuf_classes():
    """
    Dynamically load all Protobuf message classes from the `protobufs` directory.
    """
    proto_map = {}
    proto_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "protobufs"))

    if not os.path.exists(proto_dir):
        raise FileNotFoundError(f"Protobuf directory not found: {proto_dir}")

    log.info(f"Loading Protobuf classes from: {proto_dir}")

    for filename in os.listdir(proto_dir):
        if filename.endswith("_pb2.py"):
            module_name = f"steam3.protobufs.{filename[:-3]}"
            try:
                # Dynamically import the Protobuf module
                module = importlib.import_module(module_name)
                # log.info(f"Loaded module: {module_name}")

                for name in dir(module):
                    if name.startswith("CMsg"):
                        cls = getattr(module, name)
                        if hasattr(cls, "DESCRIPTOR") and cls.DESCRIPTOR.name:
                            proto_map[name] = cls
                            # log.debug(f"Mapped Protobuf class: {name} -> {cls}")
            except Exception as e:
                log.error(f"Error loading Protobuf module {module_name}: {e}")

    return proto_map

# Load Protobuf classes once during module import
PROTO_MAP = _load_protobuf_classes()

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
    _size = struct.calcsize("<II")
    proto_map = PROTO_MAP  # Use the preloaded map

    def __init__(self, data = None, client_obj = None):
        self.eMsgID = EMsg.Invalid
        self.headerSize = MsgHdrProtoBuf._size
        self.headerVersion = 2  # Default header version
        self.targetJobID = 0
        self.sourceJobID = 0
        self.headerCanary = 239  # Example value, adjust as necessary
        self.accountID = 0
        self.clientId2 = 0
        self.sessionID = 0
        self.data = b''
        self.proto = CMsgProtoBufHeader()

        if client_obj:
            self.accountID = client_obj.steamID * 2
            self.clientId2 = client_obj.clientID2
            self.sessionID = client_obj.sessionID

        if data:
            self.load(data)

    def serialize(self):
        proto_data = self.proto.SerializeToString()
        return struct.pack("<II", set_proto_bit(self.eMsgID), len(proto_data)) + proto_data

    def load(self, data):
        # Parse header
        msg, proto_length = struct.unpack_from("<II", data)
        self.eMsgID = EMsg(clear_proto_bit(msg))
        size = MsgHdrProtoBuf._size
        full_size = size + proto_length
        header_data = data[size:full_size]

        # Parse the Protobuf header
        self.proto.ParseFromString(header_data)
        self._parse_protobuf_header(self.proto)

        # Remaining data is the message payload
        self.data = data[full_size:]
        print(f"Parsed Protobuf header for EMsg {self.eMsgID}: {self.proto}")
        #print(f"Message payload size: {len(self.data)} bytes")

    def _parse_protobuf_header(self, proto):
        """
        Parse the CMsgProtoBufHeader fields into class attributes.
        """
        self.steamid = proto.steamid if proto.HasField("steamid") else None
        self.sessionID = proto.client_sessionid if proto.HasField("client_sessionid") else None
        self.targetJobID = proto.jobid_target if proto.HasField("jobid_target") else None
        self.sourceJobID = proto.jobid_source if proto.HasField("jobid_source") else None
        self.eResult = proto.eresult if proto.HasField("eresult") else None
        self.errorMessage = proto.error_message if proto.HasField("error_message") else None
        self.accountID = self.steamid & 0xFFFFFFFF  # Lower 32 bits
        self.clientId2 = (self.steamid >> 32) & 0xFFFFFFFF  # Higher 32 bits
        print(f"Parsed header fields: steamid={self.steamid}\nsessionID={self.sessionID}\n"
              f"targetJobID={self.targetJobID}\nsourceJobID={self.sourceJobID}\neResult={self.eResult}\nerrorMessage={self.errorMessage}")

    def _resolve_protobuf_class(self, emsg):
        """
        Resolve the Protobuf class for the given EMsg using dynamic mapping or derived name.
        """
        # Attempt to resolve the class using the proto_map
        if emsg in MsgHdrProtoBuf.proto_map:
            #print(f"EMsg {emsg} found directly in proto_map")
            return MsgHdrProtoBuf.proto_map[emsg]

        # Dynamically derive the Protobuf class name
        emsg_name = get_enum_name(EMsg, emsg)
        if emsg_name:
            cmsg_name = f"CMsg{emsg_name}"  # Prepend 'CMsg' to the enum name
            #print(f"Derived Protobuf class name for EMsg {emsg}: {cmsg_name}")
        else:
            log.error(f"Could not derive Protobuf class name for EMsg {emsg}")
            return None

        # Look for the derived class in the proto_map
        for proto_cls_name, proto_cls in MsgHdrProtoBuf.proto_map.items():
            if proto_cls_name.lower() == cmsg_name.lower():
                #print(f"Resolved Protobuf class {cmsg_name} to {proto_cls.__name__}")
                return proto_cls

        log.error(f"Protobuf class {cmsg_name} not found in proto_map")
        return None

class CMProtoResponse:
    def __init__(self, eMsgID=0, client_obj=None):
        """
        Initialize a Protobuf-based response message.
        :param eMsgID: The EMsg ID for the response.
        :param client_obj: The client object associated with the response.
        """
        try:
            if client_obj.is_newPacketType is True:
                # Dynamically change the class to MsgHdrProtoBuf
                #self.__class__ = MsgHdrProtoBuf
                MsgHdrProtoBuf.__init__(self, client_obj=client_obj)
                self.eMsgID = eMsgID
                self.proto = CMsgProtoBufHeader()
                self.data = b''
                # Ensure thread_local_data.extended_msg is valid
                if not hasattr(thread_local_data, 'extended_msg') or not thread_local_data.extended_msg:
                    raise ValueError("thread_local_data.extended_msg is not properly set.")

                # Set header fields using thread_local_data.extended_msg
                extended_msg = thread_local_data.extended_msg
                if isinstance(extended_msg, MsgHdrProtoBuf):
                    self.proto.steamid = extended_msg.proto.steamid if extended_msg.proto.HasField("steamid") else 0
                    self.proto.client_sessionid = extended_msg.proto.client_sessionid if extended_msg.proto.HasField("client_sessionid") else 0
                    self.proto.routing_appid = extended_msg.proto.routing_appid if extended_msg.proto.HasField("routing_appid") else 0
                    self.proto.jobid_target = extended_msg.proto.jobid_source if extended_msg.proto.HasField("jobid_source") else 18446744073709551615
                    self.proto.jobid_source = extended_msg.proto.jobid_target if extended_msg.proto.HasField("jobid_target") else 18446744073709551615
                    #self.proto.target_job_name = extended_msg.proto.target_job_name if extended_msg.proto.HasField("target_job_name") else ""
                    #self.proto.header_size = extended_msg.header_Size
                    #self.proto.header_version = extended_msg.header_Version
                else:
                    raise TypeError("thread_local_data.extended_msg must be an instance of MsgHdrProtoBuf.")

                # Set AccountID and ClientID
                # self.proto.steamid = client_obj.steamID * 2 + client_obj.clientID2 # Ensure steamID is processed
                self.proto.client_sessionid = client_obj.sessionID

                # Protobuf response message payload
                self.response_message = None  # This will hold the payload message (e.g., CMsgClientLogonResponse)
            else:
                raise NotImplementedError("Only Protobuf responses are supported in this implementation.")
        except Exception as e:
            log.error(f"Error initializing CMProtoResponse: {e}")

    def set_response_message(self, message):
        """
        Set the Protobuf message payload.
        :param message: Protobuf message instance (e.g., CMsgClientLogonResponse).
        """
        self.response_message = message

    def serialize(self):
        """
        Serialize the response into bytes in the correct order:
        1. 8-byte header (eMsgID and header size)
        2. CMsgProtoBufHeader
        3. Protobuf response payload (if set)
        """
        try:
            # Serialize the CMsgProtoBufHeader
            proto_data = self.proto.SerializeToString()
            proto_size = len(proto_data)

            # Serialize the response message (if available)
            if self.response_message:
                response_data = self.response_message.SerializeToString()
            else:
                response_data = b''
            self.data = struct.pack("<II", set_proto_bit(self.eMsgID), proto_size) + proto_data + response_data

            # Combine all parts: header, CMsgProtoBufHeader, and message payload
            return self.data
        except Exception as e:
            log.error(f"Error serializing CMProtoResponse: {e}")
            return None

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
        self.proto = steammessages_base_pb2.CMsgProtoBufHeader()
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
            x = self._size
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



    def __repr__(self):
        return (f"deprecated_responsehdr(eMsgID={self.eMsgID}, length={self.length}, data={self.data}, "
                f"accountID={getattr(self, 'accountID', None)}, "
                f"clientID2={getattr(self, 'clientID2', None)}, "
                f"sessionID={getattr(self, 'sessionID', None)})")

class MsgMulti:
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
        self.jobIDTarget = struct.unpack('<Q', in_stream.read(8))[0]
        self.jobIDSource = struct.unpack('<Q', in_stream.read(8))[0]
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

        # Write the msg ID and job IDs to the buffer
        data_out.write(struct.pack('<I',1))
        data_out.write(struct.pack('<q', self.jobIDTarget))
        data_out.write(struct.pack('<q', self.jobIDSource))

        # Create a temporary buffer to hold the message data
        message_out = io.BytesIO()
        self.writeMessages(message_out)
        data_bytes = message_out.getvalue()

        # Handle compression if necessary
        if not self.compressed or len(data_bytes) < 1000:
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
        """
        Adds a message to the MsgMulti object.
        If the message is an ExtendedMsgHdr instance, it serializes the message and adds it to the body.
        """
        if isinstance(message, ExtendedMsgHdr):
            self.body['messages'].append(message)
        else:
            raise TypeError("Only ExtendedMsgHdr instances can be added as messages.")


# CM Response is from server to client
class CMResponse:
    def __init__(self, eMsgID=0, client_obj=None, is_tcp=False):
        if client_obj.is_newPacketType:
            self.__class__ = ExtendedMsgHdr
            ExtendedMsgHdr.__init__(self, eMsgID, client_obj)
            """self.headerSize = thread_local_data.extended_msg.headerSize
            self.headerVersion = thread_local_data.extended_msg.headerVersion"""
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
    def __init__(self, header=0, size=0, packetid=0, priority_level=0, destination_id=0, source_id=0, sequence_num=0, last_recv_seq=0, split_pkt_cnt=0, seq_of_first_pkt=0, data_len=0, data=b'', is_tcp=False):
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
        self.is_tcp = is_tcp
        self.is_proto = False
        self.CMRequest = None

    def parse(self, recvd_packet, is_tcp = False):
        packet = CMPacket(is_tcp=is_tcp)
        if packet.is_tcp:
            format_str = '<I4s'
            try:
                packet.size, packet.magic = struct.unpack_from(format_str, recvd_packet)
            except:
                packet.size = 0
                packet.magic = b""
            packet.data = recvd_packet[8:] if packet.size > 0 else 0
        else:
            format_str = 'I h c c I I I I I I i'
            fields = struct.unpack_from(format_str, recvd_packet)
            packet.magic, packet.size, packet.packetid, packet.priority_level, packet.destination_id, packet.source_id, packet.sequence_num, packet.last_recv_seq, packet.split_pkt_cnt, packet.seq_of_first_pkt, packet.data_len = fields
            packet.data = recvd_packet[36:] if packet.size > 0 else 0
        return packet

    def serialize(self):
        import sys
        import traceback
        if self.is_tcp:
            self.magic = b"VT01"
            self.size = len(self.data)
            packed_data = struct.pack('<I4s', self.size, self.magic)
        else:
            if isinstance(self.packetid, int):
                self.packetid = self.packetid.to_bytes(1, "little")
            if isinstance(self.priority_level, int):
                self.priority_level = self.priority_level.to_bytes(1, "little")
            format_str = 'I H c c I I I I I I I'
            try:
                packed_data = struct.pack(format_str, self.magic, self.size, self.packetid, self.priority_level, self.destination_id, self.source_id, self.sequence_num, self.last_recv_seq, self.split_pkt_cnt, self.seq_of_first_pkt, self.data_len)
            except Exception as e:
                tb = sys.exc_info()[2]  # Get the original traceback
                log.error(f"CMPacket serialize error: {e}")
                log.warning(f"size: {self.size}, packetid: {self.packetid}, priority_level: {self.priority_level}, destination_id: {self.destination_id}, source_id: {self.source_id}, sequence_num: {self.sequence_num}, last_recv_seq: {self.last_recv_seq}, split_pkt_cnt: {self.split_pkt_cnt}, seq_of_first_pkt: {self.seq_of_first_pkt}, data_len: {self.data_len}")
                log.error(''.join(traceback.format_tb(tb)))  # Logs traceback up to this point
                raise e.with_traceback(tb)  # Re-raise with the original traceback

        packed_data += self.data if self.size > 0 else b''
        return packed_data

    def parse_CMRequest(self):
        if self.data == 0 or len(self.data) < 4:
            log.error("Data too short to contain an EMsg!")
            return None
        # Read the first 4 bytes to get the EMsg
        emsg_value, = struct.unpack_from("<I", self.data)
        emsg = EMsg(clear_proto_bit(emsg_value))
        self.is_proto = is_proto(emsg_value)

        # Determine if it's a GC message
        gc_msg = emsg in (EMsg.ClientToGC, EMsg.ClientFromGC)

        print(f"packet: {Types.get_enum_name(EMsg, emsg)}\nis protobuf: {self.is_proto}\nis gc: {gc_msg}")
        if self.is_proto:
            if gc_msg:
                self.CMRequest = GCMsgHdrProto(emsg)
                self.CMRequest.load(self.data)
            else:
                self.CMRequest = MsgHdrProtoBuf(self.data)
                # self.CMRequest.load()
        else:
            if gc_msg:
                self.CMRequest = GCMsgHdr(emsg)
                self.CMRequest.load(self.data[4:])  # Skip the EMsg
            elif len(self.data) >= 16:
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
        return (self.str())