import struct
from steam3.cm_packet_utils import CMResponse
from steam3.Types.emsg import EMsg


class MsgClientLBSGetLBEntriesResponse:
    def __init__(self, client_obj):
        self.leaderboard_entry_count = 0
        self.result                  = 0
        self.entries                 = []   # list of LeaderboardEntry-like objects
        self.client_obj              = client_obj

    def to_protobuf(self):
        pass

    def to_clientmsg(self):
        """
        Wrap as a legacy CMResponse + packed byte buffer.
        """
        packet = CMResponse(
            eMsgID     = EMsg.ClientLBSGetLBEntriesResponse,
            client_obj = self.client_obj
        )
        # I32 count, I32 entriesCount, I32 result
        packet.data = struct.pack(
            '<I I I',
            self.leaderboard_entry_count,
            len(self.entries),
            self.result
        )
        # each entry: Q steamGlobalId, I globalRank, I score, I detailsCount, then I * detailsCount
        for e in self.entries:
            packet.data += struct.pack(
                '<Q I I I',
                e.steam_global_id,
                e.global_rank,
                e.score,
                len(e.details)
            )
            for d in e.details:
                packet.data += struct.pack('<I', d)

        packet.length = len(packet.data)
        return packet
