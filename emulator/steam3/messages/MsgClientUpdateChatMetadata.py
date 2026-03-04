from __future__ import annotations
import struct
from steam3.Types.steamid import SteamID
from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse


class MsgClientUpdateChatMetadata:
    """Client->server MsgClientUpdateChatMetadata_t."""

    def __init__(self, client_obj, data: bytes | None = None):
        self.client_obj = client_obj
        self.chat_id = SteamID()
        self.user_id = SteamID()
        self.metadata = b""
        if data is not None:
            self.deserialize(data)

    def deserialize(self, data: bytes) -> None:
        chat, user, length = struct.unpack_from("<QQI", data, 0)
        self.chat_id = SteamID.from_raw(chat)
        self.user_id = SteamID.from_raw(user)
        start = struct.calcsize("<QQI")
        self.metadata = data[start:start + length]

    def to_clientmsg(self) -> CMResponse:
        packet = CMResponse(eMsgID=EMsg.ClientUpdateChatMetadata, client_obj=self.client_obj)
        packet.data = struct.pack(
            "<QQI",
            int(self.chat_id),
            int(self.user_id),
            len(self.metadata),
        ) + self.metadata
        packet.length = len(packet.data)
        return packet
