import struct
from steam3.cm_packet_utils import CMResponse
from steam3.Types.emsg import EMsg


class MsgClientLBSSetScore:
    def __init__(self, buffer):
        self.buffer   = buffer
        self.app_id   = 0
        self.leaderboard = 0
        self.score    = 0
        self.details  = []
        self.method   = 0
        if buffer:
            self.deserialize()

    def deserialize(self):
        # I32 appId, I32 leaderboard, I32 score, I32 detailsLen
        header_fmt = '<I I I I'
        header_size = struct.calcsize(header_fmt)
        (self.app_id,
         self.leaderboard,
         self.score,
         details_len) = struct.unpack_from(header_fmt, self.buffer, 0)

        # read details array (each detail is I32)
        if details_len % 4:
            raise Exception("Invalid leaderboard score details length")
        cnt = details_len // 4
        offset = header_size
        self.details = []
        for _ in range(cnt):
            (val,) = struct.unpack_from('<I', self.buffer, offset)
            self.details.append(val)
            offset += 4

        # finally the upload method (I32)
        (self.method,) = struct.unpack_from('<i', self.buffer, offset)