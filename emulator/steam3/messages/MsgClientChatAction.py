from __future__ import annotations
import struct
from steam3.Types.chat_types import ChatAction
from steam3.Types.steamid import SteamID
from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse


class MsgClientChatAction:
    """Python representation of MsgClientChatAction_t.

    Fields:
        steam_id_chat (SteamID): Chat room global ID.
        steam_id_user_to_act_on (SteamID): Target user ID.
        action (ChatAction): Action to perform.
    """

    def __init__(self, client_obj, data: bytes | None = None):
        self.client_obj = client_obj
        self.steam_id_chat = SteamID()
        self.steam_id_user_to_act_on = SteamID()
        self.action = ChatAction.inviteChat
        if data is not None:
            self.deserialize(data)

    def deserialize(self, data: bytes) -> None:
        """Populate fields from raw packet data."""
        chat, acted, act = struct.unpack_from("<QQI", data, 0)
        self.steam_id_chat = SteamID.from_raw(chat)
        self.steam_id_user_to_act_on = SteamID.from_raw(acted)
        self.action = ChatAction(act)

    def to_clientmsg(self) -> CMResponse:
        """Serialize into a CMRequest for EMsg.ClientChatAction."""
        packet = CMResponse(eMsgID=EMsg.ClientChatAction, client_obj=self.client_obj)
        packet.data = struct.pack(
            "<QQI",
            int(self.steam_id_chat),
            int(self.steam_id_user_to_act_on),
            int(self.action),
        )
        packet.length = len(packet.data)
        return packet
