from __future__ import annotations
import struct
from steam3.Types.steamid import SteamID
from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse


class MsgClientGetLobbyMetadata:
    """Request lobby metadata."""

    def __init__(self, client_obj, data: bytes | None = None):
        self.client_obj = client_obj
        self.lobby_id = SteamID()
        if data is not None:
            self.deserialize(data)

    def deserialize(self, data: bytes) -> None:
        lobby, = struct.unpack_from("<Q", data, 0)
        self.lobby_id = SteamID.from_raw(lobby)

    def to_clientmsg(self) -> CMResponse:
        packet = CMResponse(eMsgID=EMsg.ClientGetLobbyMetadata, client_obj=self.client_obj)
        packet.data = struct.pack("<Q", int(self.lobby_id))
        packet.length = len(packet.data)
        return packet
