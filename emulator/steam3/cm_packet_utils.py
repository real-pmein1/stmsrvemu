import logging
import struct
import io
import os
import importlib
import sys
import traceback
from types import GeneratorType as _GeneratorType
from typing import Union
from google.protobuf.message import Message as _ProtoMessageType
from zipfile import ZipFile, ZIP_DEFLATED
from steam3.Types.wrappers import ConnectionID

from steam3 import Types, thread_local_data
from steam3.Types.emsg import EMsg
from steam3.Types.steamid import SteamID
from steam3.protobufs.steammessages_base_pb2 import CMsgProtoBufHeader  # Adjust as needed
from steam3.Types import get_enum_name
from steam3.protobufs import steammessages_base_pb2
from steam3.protobufs import gc_pb2

log = logging.getLogger(f"CMProto")

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
                module = importlib.import_module(module_name)
                for name in dir(module):
                    if name.startswith("CMsg"):
                        cls = getattr(module, name)
                        if hasattr(cls, "DESCRIPTOR") and cls.DESCRIPTOR.name:
                            proto_map[name] = cls
            except Exception as e:
                log.error(f"Error loading Protobuf module {module_name}: {e}")

    return proto_map

# Load Protobuf classes once during module import
PROTO_MAP = _load_protobuf_classes()

# --- Base Classes for Inheritance ---

class BaseHeader:
    """
    Base class for headers with fixed structure.
    Child classes must define:
      - _format: struct format string
      - _fields: list of field names in order
      - _size: size of the fixed header
    """
    _format = None
    _fields = []
    _size = 0
    is_serialized = False

    def serialize(self):
        values = [getattr(self, field) for field in self._fields]
        serialized_data = struct.pack(self._format, *values) + self.data
        self.length = len(serialized_data)
        self.is_serialized = True
        return serialized_data

    def load(self, data):
        values = struct.unpack_from(self._format, data)
        for i, field in enumerate(self._fields):
            setattr(self, field, values[i])
        self.data = data[self._size:]
        return self

class BaseProtoHeader:
    """
    Base class for Protobuf-based headers with a common two-field prefix.
    """
    _base_format = "<II"
    _base_size = 8 #struct.calcsize("<II")

    def serialize(self):
        proto_data = self.proto.SerializeToString()
        return struct.pack(self._base_format, set_proto_bit(self.eMsgID), len(proto_data)) + proto_data

    def load(self, data):
        msg, proto_length = struct.unpack_from(self._base_format, data)
        self.eMsgID = EMsg(clear_proto_bit(msg))
        full_size = self._base_size + proto_length
        self.proto.ParseFromString(data[self._base_size:full_size])
        self.data = data[full_size:]
        print(f"Parsed Protobuf header for EMsg {self.eMsgID}: {self.proto}")
        return self

class BaseProtoHeader2:
    """
    Alternative base for Protobuf headers using a different fixed format.
    """
    _base_format = "<Ii"
    _base_size = 8 #struct.calcsize("<Ii")

    def serialize(self):
        proto_data = self.proto.SerializeToString()
        self.headerLength = len(proto_data)
        return struct.pack(self._base_format, set_proto_bit(self.msg), self.headerLength) + proto_data

    def load(self, data):
        msg, self.headerLength = struct.unpack_from(self._base_format, data)
        self.msg = clear_proto_bit(msg)
        if self.headerLength:
            self.proto.ParseFromString(data[self._base_size:self._base_size + self.headerLength])
        self.data = data[self._base_size + self.headerLength:]
        return self

class BasePacket:
    """
    Base class for packets.
    """
    def parse(self, recvd_packet, is_tcp=False):
        raise NotImplementedError

    def serialize(self):
        raise NotImplementedError

# --- Header Classes Using Inheritance ---

class MsgHdr_deprecated(BaseHeader):
    _format = '<IQI'
    _fields = ['eMsgID', 'steamID', 'sessionID']
    _size = 16

    def __init__(self, eMsgID=0x0, steamID=0xffffffffffffffff, sessionID=0xffffffff, data=b''):
        self.eMsgID = eMsgID
        self.sessionID = sessionID
        self.data = data
        self.length = 0
        self.is_newPacketType = False
        self.steamID: SteamID = SteamID.from_raw(steamID)

    def serialize(self):
        serialized_data = struct.pack(self._format, self.eMsgID, self.steamID.get_integer_format() & 0xFFFFFFFFFFFFFFFF, self.sessionID & 0xFFFFFFFF) + self.data
        self.length = len(serialized_data)
        return serialized_data

    def load(self, data):
        msg, steamID, self.sessionID = struct.unpack_from(self._format, data)
        self.steamID.from_integer(steamID)
        self.eMsgID = EMsg(msg)
        self.data = data[self._size:]
        return self

    def __repr__(self):
        return (f"deprecated_responsehdr(eMsgID={self.eMsgID}, data={self.data}, "
                f"steamID={self.steamID}, sessionID={self.sessionID})")

class MsgHdr(BaseHeader):
    _format = "<Iqq"
    _fields = ['eMsgID', 'targetJobID', 'sourceJobID']
    _size = 20 #struct.calcsize("<Iqq")

    def __init__(self, data=None):
        self.eMsgID = EMsg.Invalid
        self.targetJobID = -1
        self.sourceJobID = -1
        self.data = b''
        self.length = 0
        if data:
            self.load(data)

    def serialize(self):
        serialized_data = struct.pack(self._format, self.eMsgID, self.targetJobID, self.sourceJobID) + self.data
        self.length = len(serialized_data)
        return serialized_data

    def load(self, data):
        (msg, self.targetJobID, self.sourceJobID) = struct.unpack_from(self._format, data)
        self.eMsgID = EMsg(msg)
        self.data = data[self._size:]
        return self

    def __str__(self):
        return '\n'.join(["eMsgID: %s" % repr(self.eMsgID),
                          "targetJobID: %s" % self.targetJobID,
                          "sourceJobID: %s" % self.sourceJobID,
                          "data: %s" % self.data])

class ExtendedMsgHdr(BaseHeader):
    _format = "<IBHqqBQi"
    _fields = ['eMsgID', 'headerSize', 'headerVersion', 'targetJobID', 'sourceJobID',
               'headerCanary', 'steamID', 'sessionID']
    _size = 36

    def __init__(self, eMsgID=0, client_obj=None, data=None):
        self.eMsgID = eMsgID
        self.headerSize = 36
        self.headerVersion = 2
        self.targetJobID = -1
        self.sourceJobID = -1
        self.headerCanary = 239
        #self.accountID = -1
        self.steamID: SteamID = SteamID.from_integer(-1)
        #self.clientId2 = -1
        #self.clientID2 = self.clientId2
        self.sessionID = -1
        self.data = b''
        self.length = 0
        self.is_newPacketType = True
        self.is_serialized = False
        if client_obj:
            self.steamID = SteamID.from_raw(client_obj.steamID)
            self.sessionID = client_obj.sessionID if client_obj.sessionID is not None else 0
        if data:
            self.load(data)

    def serialize(self):
        # Ensure all values are proper integers for struct.pack
        sessionID = self.sessionID if self.sessionID is not None else 0
        targetJobID = self.targetJobID if self.targetJobID is not None else -1
        sourceJobID = self.sourceJobID if self.sourceJobID is not None else -1

        serialized_data = struct.pack(self._format,
                                      self.eMsgID,
                                      self.headerSize,
                                      self.headerVersion,
                                      targetJobID,
                                      sourceJobID,
                                      self.headerCanary,
                                      self.steamID.get_integer_format(),
                                      sessionID) + self.data
        self.length = len(serialized_data)
        self.is_serialized = True
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
         steamID,
         self.sessionID) = struct.unpack_from(self._format, data, 0)

        self.steamID = SteamID.from_integer(steamID)
        #print(f"steamid: {steamID}\n {self.steamID}\n bytes: {data[24:32]}")
        self.eMsgID = EMsg(eMsgID)
        self.data = data[self._size:]
        self.length = len(self.data)
        print(f"extended message full data with header: {data}")
        print(f"extended message data without header: {self.data}")
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
                          "steamID: %s" % self.steamID,
                          "sessionID: %s" % self.sessionID,
                          "data: %s" % self.data])

class MsgHdrProtoBuf(BaseProtoHeader):
    _size = 8 #struct.calcsize("<II")
    proto_map = PROTO_MAP  # Use the preloaded map

    def __init__(self, data=None, client_obj=None):
        self.eMsgID = EMsg.Invalid
        _size = 8
        self.headerSize = 8
        self.headerVersion = 2
        self.targetJobID = 0
        self.sourceJobID = 0
        self.headerCanary = 239
        self.steamID: SteamID = SteamID.from_integer(-1)
        self.sessionID = 0
        self.data = b''
        self.proto = CMsgProtoBufHeader()
        if client_obj:
            self.steamID = SteamID.from_raw(client_obj.steamID)
            self.sessionID = client_obj.sessionID if client_obj.sessionID is not None else 0
        if data:
            self.load(data)

    def serialize(self):
        proto_data = self.proto.SerializeToString()
        return struct.pack("<II", set_proto_bit(self.eMsgID), len(proto_data)) + proto_data

    def load(self, data):
        msg, proto_length = struct.unpack_from("<II", data)
        self.eMsgID = EMsg(clear_proto_bit(msg))
        size = self._size
        full_size = size + proto_length
        header_data = data[size:full_size]
        self.proto.ParseFromString(header_data)
        self._parse_protobuf_header(self.proto)
        self.data = data[full_size:]
        print(f"Parsed Protobuf header for EMsg {self.eMsgID}: {self.proto}")
        return self

    def _parse_protobuf_header(self, proto):
        self.steamID = proto.steamid if proto.HasField("steamid") else None
        self.sessionID = proto.client_sessionid if proto.HasField("client_sessionid") else None
        self.targetJobID = proto.jobid_target if proto.HasField("jobid_target") else None
        self.sourceJobID = proto.jobid_source if proto.HasField("jobid_source") else None
        self.eResult = proto.eresult if proto.HasField("eresult") else None
        self.errorMessage = proto.error_message if proto.HasField("error_message") else None
        self.steamID = self.steamID if self.steamID is not None else None
        print(f"Parsed header fields: steamid={self.steamID}\nsessionID={self.sessionID}\n"
              f"targetJobID={self.targetJobID}\nsourceJobID={self.sourceJobID}\n"
              f"eResult={self.eResult}\nerrorMessage={self.errorMessage}")

    def _resolve_protobuf_class(self, emsg):
        if emsg in MsgHdrProtoBuf.proto_map:
            return MsgHdrProtoBuf.proto_map[emsg]
        emsg_name = get_enum_name(EMsg, emsg)
        if emsg_name:
            cmsg_name = f"CMsg{emsg_name}"
        else:
            log.error(f"Could not derive Protobuf class name for EMsg {emsg}")
            return None
        for proto_cls_name, proto_cls in MsgHdrProtoBuf.proto_map.items():
            if proto_cls_name.lower() == cmsg_name.lower():
                return proto_cls
        log.error(f"Protobuf class {cmsg_name} not found in proto_map")
        return None

class GCMsgHdr(BaseHeader):
    _format = "<Hqq"
    _fields = ['headerVersion', 'targetJobID', 'sourceJobID']
    _size = 18 #struct.calcsize("<Hqq")

    def __init__(self, msg, data=None):
        self.msg = clear_proto_bit(msg)
        self.data = b''
        if data:
            self.load(data)

    def serialize(self):
        return struct.pack(self._format, self.headerVersion, self.targetJobID, self.sourceJobID) + self.data

    def load(self, data):
        (self.headerVersion, self.targetJobID, self.sourceJobID) = struct.unpack_from(self._format, data)
        self.data = data[self._size:]

    def __str__(self):
        return '\n'.join(["headerVersion: %s" % self.headerVersion,
                          "targetJobID: %s" % self.targetJobID,
                          "sourceJobID: %s" % self.sourceJobID,
                          "data: %s" % self.data])

class GCMsgHdrProto(BaseProtoHeader2):
    def __init__(self, msg, data=None):
        self.proto = steammessages_base_pb2.CMsgProtoBufHeader()
        self.msg = clear_proto_bit(msg)
        self.data = b''
        if data:
            self.load(data)

    def __str__(self):
        resp = ["msg: %s" % self.msg,
                "headerLength: %s" % self.headerLength]
        proto = str(self.proto)
        if proto:
            resp.append('-- proto --')
            resp.append(proto)
        return '\n'.join(resp)

class deprecated_responsehdr(BaseHeader):
    _format = '<IQI'
    _fields = ['eMsgID', 'steamID', 'sessionID']
    _size = 16

    def __init__(self, eMsgID=0, client_obj=None):
        self.eMsgID = eMsgID
        self.length = 0
        self.data = b''
        self.is_serialized = False
        self.serialized_buffer = b''
        if client_obj:
            self.steamID: SteamID = SteamID.from_raw(client_obj.steamID)
            self.sessionID = client_obj.sessionID if client_obj.sessionID is not None else 0

    def serialize(self):
        serialized_data = struct.pack(self._format, self.eMsgID, self.steamID.get_integer_format(), self.sessionID) + self.data
        self.length = len(serialized_data)
        self.is_serialized = True
        self.serialized_buffer = serialized_data
        return serialized_data

    def __repr__(self):
        return (f"deprecated_responsehdr(eMsgID={self.eMsgID}, length={self.length}, data={self.data}, "
                f"steamID={getattr(self, 'steamID', None)}, "
                f"sessionID={getattr(self, 'sessionID', None)})")

# --- Packet/Response Classes Using Inheritance ---

class MultiMsg(BasePacket):
    def __init__(self, targetJobID=-1, sourceJobID=-1):
        self.eMsgID = EMsg.Multi
        self.targetJobID = targetJobID
        self.sourceJobID = sourceJobID
        self.messages = []
        self.buffer = None
        self.length = 0
        self.data = b''
        self.serialized_messages = None
        self.is_compressed = False
        self.uncompressed_size = 0

    def set_compressed(self):
        self.is_compressed = True

    def add_message(self, msg: bytes):
        # If msg is not a bytes object, attempt to serialize it.
        if not isinstance(msg, bytes):
            # If the message is not yet serialized, call its serialize() method.
            if hasattr(msg, "is_serialized") and msg.is_serialized == False:
                msg = msg.serialize()
            else:
                raise Exception("Attempted to add a non-bytes and Non-CMPacket message to MultiMsg!")
        self.messages.append(msg)

    def serialize_multimsg(self) -> bytes:
        if self.is_compressed and self.buffer is not None:
            return self.buffer
        output = b""
        for msg in self.messages:
            length_bytes = len(msg).to_bytes(4, byteorder='little', signed=False)
            output += length_bytes + msg
        self.buffer = output
        return self.buffer

    def compress(self) -> None:
        if not self.buffer:
            self.serialize_multimsg()
        if not self.is_compressed:
            raw_data = self.buffer
            self.uncompressed_size = len(raw_data)
            zipbuffer = io.BytesIO()
            with ZipFile(zipbuffer, mode='w', compression=ZIP_DEFLATED) as zip_file:
                zip_file.writestr("zip", raw_data)
            self.buffer = zipbuffer.getvalue()
            self.is_compressed = True

    def serialize(self) -> bytes:
        header = struct.pack("<Iqq", self.eMsgID, self.targetJobID, self.sourceJobID)
        inner_data = self.serialize_multimsg()
        # If no inner data was generated, force a default non-empty buffer.
        if not inner_data:
            inner_data = b'\x00\x00\x00\x00'
            self.buffer = inner_data
        if self.is_compressed:
            self.compress()
        self.data = header + struct.pack("<I", self.uncompressed_size) + self.buffer
        self.length = len(self.data)
        return self.data

    def __repr__(self) -> str:
        status = "COMPRESSED" if self.is_compressed else "UNCOMPRESSED"
        return f"<MultiMsg ({status}), messages={len(self.messages)}>"

class CMProtoResponse:
    def __init__(self, eMsgID=0, client_obj=None):
        try:
            MsgHdrProtoBuf.__init__(self, client_obj=client_obj)
            self.eMsgID = eMsgID
            self.proto = CMsgProtoBufHeader()
            self.data = b''
            if not hasattr(thread_local_data, 'extended_msg') or not thread_local_data.extended_msg:
                raise ValueError("thread_local_data.extended_msg is not properly set.")
            extended_msg = thread_local_data.extended_msg
            if isinstance(extended_msg, MsgHdrProtoBuf):
                self.proto.steamid = extended_msg.proto.steamid if extended_msg.proto.HasField("steamid") else 0
                self.proto.client_sessionid = extended_msg.proto.client_sessionid if extended_msg.proto.HasField("client_sessionid") else 0
                self.proto.routing_appid = extended_msg.proto.routing_appid if extended_msg.proto.HasField("routing_appid") else 0
                self.proto.jobid_target = extended_msg.proto.jobid_source if extended_msg.proto.HasField("jobid_source") else 18446744073709551615
                self.proto.jobid_source = extended_msg.proto.jobid_target if extended_msg.proto.HasField("jobid_target") else 18446744073709551615
            else:
                raise TypeError("thread_local_data.extended_msg must be an instance of MsgHdrProtoBuf.")
            self.proto.client_sessionid = client_obj.sessionID
            self.response_message = None

        except Exception as e:
            log.error(f"Error initializing CMProtoResponse: {e}")

    def set_response_message(self, message):
        self.response_message = message

    def serialize(self):
        try:
            proto_data = self.proto.SerializeToString()
            proto_size = len(proto_data)
            if self.response_message:
                response_data = self.response_message.SerializeToString()
            else:
                response_data = b''
            self.data = struct.pack("<II", set_proto_bit(self.eMsgID), proto_size) + proto_data + response_data
            return self.data
        except Exception as e:
            log.error(f"Error serializing CMProtoResponse: {e}")
            return None

class CMResponse:
    """CM Response is from server to client.

    This class handles the automatic job ID routing that's critical for the
    Steam client's CJobMgr. When a client sends a request with sourceJobID=X,
    our response MUST have targetJobID=X for proper routing.

    Job ID Resolution Order:
    1. Client's job_registry.active_context (preferred - explicit tracking)
    2. thread_local_data.extended_msg (legacy - implicit via thread local)
    3. client_obj.last_request_source_job_id (fallback cache)
    4. Default -1 (unsolicited message)
    """
    def __init__(self, eMsgID=0, client_obj=None, is_tcp=False):
        if eMsgID == EMsg.Multi:
            self.__class__ = MultiMsg
            MultiMsg.__init__(self)
        else:
            if client_obj.is_newPacketType:
                self.__class__ = ExtendedMsgHdr
                ExtendedMsgHdr.__init__(self, eMsgID, client_obj)

                # Get job routing info - try multiple sources in order of preference
                target_job_id = -1
                source_job_id = -1
                header_canary = 239
                routing_source = "none"

                # 1. Try client's job registry (new explicit job context system)
                if hasattr(client_obj, 'job_registry') and client_obj.job_registry:
                    active_ctx = client_obj.job_registry.active_context
                    if active_ctx is not None and active_ctx.has_job_routing():
                        target_job_id = active_ctx.get_response_target_job_id()
                        source_job_id = -1  # We're not waiting for a response
                        active_ctx.increment_response_count()
                        routing_source = "job_registry"

                # 2. Fallback to thread_local_data.extended_msg (legacy)
                if routing_source == "none":
                    extended_msg = getattr(thread_local_data, 'extended_msg', None)
                    if extended_msg is not None:
                        # Swap job IDs: response targetJobID = request sourceJobID
                        if hasattr(extended_msg, 'sourceJobID') and extended_msg.sourceJobID != -1:
                            target_job_id = extended_msg.sourceJobID
                            source_job_id = extended_msg.targetJobID if hasattr(extended_msg, 'targetJobID') else -1
                            routing_source = "thread_local"
                        if hasattr(extended_msg, 'headerCanary'):
                            header_canary = extended_msg.headerCanary

                # 3. Fallback to client's cached request info
                if routing_source == "none":
                    if hasattr(client_obj, 'last_request_source_job_id') and client_obj.last_request_source_job_id is not None:
                        target_job_id = client_obj.last_request_source_job_id
                        source_job_id = -1
                        routing_source = "client_cache"

                # Apply the resolved job IDs
                self.targetJobID = target_job_id
                self.sourceJobID = source_job_id
                self.headerCanary = header_canary

                # Log for debugging (only when job routing is active)
                if target_job_id != -1:
                    log.debug(f"CMResponse for EMsg {eMsgID}: targetJobID={target_job_id:#x} "
                             f"(source: {routing_source})")

                self.steamID: SteamID = SteamID.from_raw(client_obj.steamID)
                self.sessionID = client_obj.sessionID if client_obj.sessionID is not None else 0
            else:
                self.__class__ = deprecated_responsehdr
                deprecated_responsehdr.__init__(self, eMsgID, client_obj)

class ChatMessage:
    def __init__(self, fromSteamID=0, toSteamID=0, type_=0, message=''):
        self.fromSteamID: SteamID = SteamID.from_raw(fromSteamID)
        self.toSteamID: SteamID = SteamID.from_raw(toSteamID)
        self.type = type_
        self.message = message

    @classmethod
    def parse(cls, fromSteamID, data):
        toSteamID, type_ = struct.unpack('<QI', data[:12])
        message = data[12:].split(b'\x00', 1)[0].decode('latin-1')
        return cls(fromSteamID=fromSteamID, toSteamID=toSteamID, type_=type_, message=message)

class CMPacket(BasePacket):
    def __init__(self, header=0, size=0, packetid=0, priority_level=0, destination_id=0, source_id=0,
                 sequence_num=0, last_recv_seq=0, split_pkt_cnt=0, seq_of_first_pkt=0, data_len=0, data=b'',
                 is_tcp=False):
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

    def parse(self, recvd_packet, is_tcp=False):
        packet = CMPacket(is_tcp=is_tcp)
        if packet.is_tcp:
            format_str = '<I4s'
            try:
                packet.size, packet.magic = struct.unpack_from(format_str, recvd_packet)
            except:
                packet.size = 0
                packet.magic = b""
            packet.data = recvd_packet[8:] if packet.size > 0 else b''
        else:
            format_str = '<I h c c I I I I I I i'
            fields = struct.unpack_from(format_str, recvd_packet)
            (packet.magic, packet.size, packet.packetid, packet.priority_level, packet.destination_id,
             packet.source_id, packet.sequence_num, packet.last_recv_seq, packet.split_pkt_cnt,
             packet.seq_of_first_pkt, packet.data_len) = fields
            packet.source_id = ConnectionID(packet.source_id)
            packet.destination_id = ConnectionID(packet.destination_id)
            packet.data = recvd_packet[36:] if packet.size > 0 else b''
        return packet

    def serialize(self):
        import sys, traceback

        # If self.data is None, treat it as an empty bytes object
        if self.data is None:
            self.data = b''

        self.data_len = len(self.data)

        # If it's TCP, prepend "VT01" and write size + magic
        if self.is_tcp:
            self.magic = b"VT01"
            self.size = self.data_len
            try:
                packed_data = struct.pack('<I4s', self.size, self.magic)
            except Exception as e:
                tb = sys.exc_info()[2]
                log.error(f"CMPacket serialize error (TCP): {e}")
                raise e.with_traceback(tb)
        else:
            # For UDP (or non-TCP), we have more fields:
            if isinstance(self.packetid, int):
                self.packetid = self.packetid.to_bytes(1, "little")
            if isinstance(self.priority_level, int):
                self.priority_level = self.priority_level.to_bytes(1, "little")

            # Make sure size/data_len are set safely
            # Recalculate lengths unconditionally

            # For both TCP and UDP, size == length of payload
            self.size = self.data_len #+ 36  # 36 is the size of the entire header


            format_str = '<I H c c I I I I I I I'
            try:
                packed_data = struct.pack(
                    format_str,
                    self.magic,
                    self.size,
                    self.packetid,
                    self.priority_level,
                    self.destination_id,
                    self.source_id,
                    self.sequence_num,
                    self.last_recv_seq,
                    self.split_pkt_cnt,
                    self.seq_of_first_pkt,
                    self.data_len
                )
            except Exception as e:
                tb = sys.exc_info()[2]
                log.error(f"CMPacket serialize error: {e}")
                log.warning(
                    f"size: {self.size}, packetid: {self.packetid}, priority_level: {self.priority_level}, "
                    f"destination_id: {self.destination_id}, source_id: {self.source_id}, "
                    f"sequence_num: {self.sequence_num}, last_recv_seq: {self.last_recv_seq}, "
                    f"split_pkt_cnt: {self.split_pkt_cnt}, seq_of_first_pkt: {self.seq_of_first_pkt}, "
                    f"data_len: {self.data_len}"
                )
                log.error(''.join(traceback.format_tb(tb)))
                raise e.with_traceback(tb)

        # Finally, append our payload only if there's actual data
        if self.size > 0:
            packed_data += self.data
        else:
            # No data; just append nothing
            packed_data += b''

        return packed_data


    def parse_CMRequest(self):
        if self.data == 0 or len(self.data) < 4:
            log.error(f"Data too short to contain an EMsg! Raw: {self.data!r}")
            return None
        emsg_value, = struct.unpack_from("<I", self.data)
        emsg = EMsg(clear_proto_bit(emsg_value))
        emsg_name = Types.get_enum_name(EMsg, emsg)
        self.is_proto = is_proto(emsg_value)
        gc_msg = emsg in (EMsg.ClientToGC, EMsg.ClientFromGC)
        log.debug(
            f"packet: {emsg_name} ({emsg}) | is protobuf: {self.is_proto} | is gc: {gc_msg}"
        )
        if self.is_proto:
            if gc_msg:
                self.CMRequest = GCMsgHdrProto(emsg)
                self.CMRequest.load(self.data)
            else:
                self.CMRequest = MsgHdrProtoBuf(self.data)
        else:
            if gc_msg:
                self.CMRequest = GCMsgHdr(emsg)
                self.CMRequest.load(self.data[4:])
            elif len(self.data) >= 16:
                try:
                    self.CMRequest = ExtendedMsgHdr()
                    try:
                        self.CMRequest.load(self.data)
                        self.CMRequest.data = self.data[36:]
                    except Exception as e:
                        format_str = '<IQI'
                        self.CMRequest = MsgHdr_deprecated()
                        if not self.data:
                            return 0
                        else:
                            try:
                                (self.CMRequest.eMsgID, steamID, self.CMRequest.sessionID) = struct.unpack_from(format_str, self.data)
                                self.CMRequest.steamID = SteamID.from_raw(steamID)
                                self.CMRequest.data = self.data[16:]
                            except struct.error as e:
                                log.error(
                                    f"Error unpacking packet data for {emsg_name} ({emsg}): {e}"
                                )
                                log.warning(f"Received data: {self.data!r}")
                    return self.CMRequest
                except Exception as e:
                    format_str = '<IQI'
                    self.CMRequest = MsgHdr_deprecated()
                    if self.data == 0:
                        return 0
                    else:
                        try:
                            (self.CMRequest.eMsgID, steamID, self.CMRequest.sessionID) = struct.unpack_from(format_str, self.data)
                            self.CMRequest.steamID = SteamID.from_raw(steamID)
                            self.CMRequest.data = self.data[16:]
                        except struct.error as e:
                            log.error(
                                f"Error unpacking packet data for {emsg_name} ({emsg}): {e}"
                            )
                            log.warning(f"Received data: {self.data!r}")
                    return self.CMRequest
            else:
                log.error(
                    f"Could not determine Packet Type from Header for {emsg_name} ({emsg})!\n data: {self.data!r}"
                )
                self.CMRequest = None
                return None
        return self.CMRequest

    def __str__(self):
        return (f"CMPacket(\n"
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
                f")")

    def __repr__(self):
        return self.__str__()
