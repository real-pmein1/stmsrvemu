import struct
from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMProtoResponse, CMResponse
#from steam3.protobufs.steammessages_clientserver_lbs_pb2 import CMsgClientLBSFindOrCreateLBResponse


class MsgFindOrCreateLBResponse:
    def __init__(self, client_obj):
        # mirror the C++ defaults
        self.result        = 0
        self.leaderboard   = 0
        self.entry_count   = 0
        self.sort_method   = 0
        self.display_type  = 0
        self.name          = ""
        self.client_obj    = client_obj

    def to_protobuf(self):
        pass

    def to_clientmsg(self):
        """
        Wrap as a legacy CMResponse + packed byte buffer.
        """
        packet = CMResponse(
            eMsgID    = EMsg.ClientLBSFindOrCreateLBResponse,
            client_obj = self.client_obj
        )
        # five I32 fields, then NUL-terminated UTF-8 string
        packet.data  = struct.pack(
            '<I I I I I',
            self.result,
            self.leaderboard,
            self.entry_count,
            self.sort_method,
            self.display_type
        )
        packet.data += self.name.encode('utf-8') + b'\x00'
        packet.length = len(packet.data)
        return packet