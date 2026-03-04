import struct
from io import BytesIO
from steam3.Types.steamid import SteamID
from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse


class MsgClientGetLobbyMetadataResponse:
    """Server response for lobby metadata requests.

    Based on 2008 client analysis (CClientJobReceiveLobbyData), format is:
    - lobby_steam_id: 8 bytes (Q unsigned)
    - metadata_len: 4 bytes (I unsigned)
    - metadata_bytes: KeyValues binary format
    - members_max: 4 bytes (i signed) - optional, sent if non-zero
    - members: 4 bytes (i signed) - optional, sent if non-zero

    The client checks for remaining data after metadata before reading member counts.
    """

    def __init__(self, client_obj):
        self.client_obj = client_obj
        self.lobby_id = SteamID()
        self.metadata = b""  # Should be KeyValues binary serialized
        self.members_max = 0
        self.members = 0

    def to_clientmsg(self) -> CMResponse:
        buf = BytesIO()
        buf.write(struct.pack("<QI", int(self.lobby_id), len(self.metadata)))
        buf.write(self.metadata)
        # Client checks for remaining data - only send if we have member info
        if self.members_max or self.members:
            buf.write(struct.pack("<ii", self.members_max, self.members))
        packet = CMResponse(eMsgID=EMsg.ClientGetLobbyMetadataResponse, client_obj=self.client_obj)
        packet.data = buf.getvalue()
        packet.length = len(packet.data)
        return packet
