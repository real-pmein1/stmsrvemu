import struct
from io import BytesIO
from typing import List
from steam3.Types.steamid import SteamID
from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse


class MsgClientGetLobbyListResponse:
    """Mirrors MsgClientGetLobbyListResponse_t."""

    def __init__(self, client_obj):
        self.client_obj = client_obj
        self.game_id = 0
        self.lobby_ids: List[SteamID] = []
        self.metadata_blocks = []  # list of tuples (steamid, members, members_max, metadata_bytes)

    def to_clientmsg(self) -> CMResponse:
        """
        Serialize lobby list response.

        Based on 2008 client analysis (UpdateLobbyMetadataFromLobbyListMsg), format is:
        - game_id: 8 bytes (Q unsigned)
        - lobby_count: 4 bytes (I unsigned)
        - lobby_ids: 8 bytes each (Q unsigned)
        - metadata_remaining_bytes: 4 bytes (i signed - client reads as signed)
        - Per lobby metadata: steamID (8), members (4 signed), max_members (4 signed),
                             metadata_len (4 signed), metadata_bytes
        """
        buf = BytesIO()
        buf.write(struct.pack("<QI", self.game_id, len(self.lobby_ids)))
        for sid in self.lobby_ids:
            buf.write(struct.pack("<Q", int(sid)))

        # Build metadata block
        meta_buf = BytesIO()
        if self.metadata_blocks:
            for sid, members, members_max, meta in self.metadata_blocks:
                # Use signed integers to match client's signed reads
                meta_buf.write(struct.pack("<Qiii", int(sid), members, members_max, len(meta)))
                meta_buf.write(meta)
        meta_data = meta_buf.getvalue()

        # Always write metadata size (signed, as client reads with signed int)
        buf.write(struct.pack("<i", len(meta_data)))
        buf.write(meta_data)

        packet = CMResponse(eMsgID=EMsg.ClientGetLobbyListResponse, client_obj=self.client_obj)
        packet.data = buf.getvalue()
        packet.length = len(packet.data)
        return packet
