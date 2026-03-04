import struct
from steam3.cm_packet_utils import CMResponse
from steam3.Types.emsg import EMsg
#from steam3.protobufs.steammessages_clientserver_lbs_pb2 import CMsgClientLBSFindOrCreateLB


class MsgFindOrCreateLB:
    def __init__(self, buffer):
        # mirror the C++ defaults
        self.buffer              = buffer
        self.app_id              = 0
        self.sort_method         = 0
        self.display_type        = 0
        self.create_if_not_found = False
        self.name                = ""
        if buffer:
            self.deserialize()

    def deserialize(self):
        """
        Read fields out of buffer (legacy CMMessage body) and populate self.
        """
        data = self.buffer
        # first 4+4+4+1 = 13 bytes: I32, I32, I32, bool
        header_fmt = '<I I I ?'
        header_size = struct.calcsize(header_fmt)

        self.app_id, \
        self.sort_method, \
        self.display_type, \
        flag = struct.unpack(header_fmt, data[:header_size])

        self.create_if_not_found = bool(flag)

        # the rest is a NUL-terminated UTF-8 string
        name_bytes = data[header_size:]
        # split at the first NUL, decode up to there
        self.name = name_bytes.split(b'\x00', 1)[0].decode('utf-8')

    def to_protobuf(self):
        pass

    def to_clientmsg(self, client_obj):
        """
        Wrap as a legacy CMMessage + packed byte buffer.
        Note: This is typically not needed for request parsers, but kept for completeness.
        """
        packet = CMResponse(
            eMsgID    = EMsg.ClientLBSFindOrCreateLB,
            client_obj = client_obj
        )
        # I32, I32, I32, bool (1 byte), then NUL-terminated UTF-8 string
        packet.data  = struct.pack(
            '<I I I ?',
            self.app_id,
            self.sort_method,
            self.display_type,
            self.create_if_not_found
        )
        packet.data += self.name.encode('utf-8') + b'\x00'
        packet.length = len(packet.data)
        return packet
