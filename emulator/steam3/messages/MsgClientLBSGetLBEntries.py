import struct
from steam3.cm_packet_utils import CMResponse
from steam3.Types.emsg import EMsg

# --- request parser for GetLBEntries -----------------------------------------

class MsgClientLBSGetLBEntries:
    def __init__(self, buffer):
        self.buffer             = buffer
        self.app_id             = 0
        self.leaderboard        = 0
        self.range_start        = 0
        self.range_end          = 0
        self.request            = 0
        if buffer:
            self.deserialize()

    def deserialize(self):
        # I32 appId, I32 leaderboard, I32 rangeStart, I32 rangeEnd, I32 request
        fmt = '<I I i i i'
        size = struct.calcsize(fmt)
        (self.app_id,
         self.leaderboard,
         self.range_start,
         self.range_end,
         self.request) = struct.unpack_from(fmt, self.buffer, 0)