import struct
from steam3.cm_packet_utils import CMResponse
from steam3.Types.emsg import EMsg


class MsgClientLBSSetScoreResponse:
    def __init__(self, client_obj):
        self.result                  = 0
        self.leaderboard_entry_count = 0
        self.score_changed           = False
        self.previous_global_rank    = 0
        self.new_global_rank         = 0
        self.client_obj              = client_obj

    def to_protobuf(self):
        pass

    def to_clientmsg(self):
        """
        Wrap as a legacy CMResponse + packed byte buffer.
        """
        packet = CMResponse(
            eMsgID     = EMsg.ClientLBSSetScoreResponse,
            client_obj = self.client_obj
        )
        # I32 result, I32 count, bool, I32 prevRank, I32 newRank
        packet.data = struct.pack(
            '<I I ? I I',
            self.result,
            self.leaderboard_entry_count,
            self.score_changed,
            self.previous_global_rank,
            self.new_global_rank
        )
        packet.length = len(packet.data)
        return packet