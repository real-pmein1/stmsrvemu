import struct
from steam3.Types.chat_types import ChatAction, ChatActionResult
from steam3.Types.steamid import SteamID
from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse


class MsgClientChatActionResult:
    """Server-to-client MsgClientChatActionResult_t."""

    def __init__(self, client_obj):
        self.client_obj = client_obj
        self.chat_id = SteamID()
        self.user_id = SteamID()
        self.action = ChatAction.inviteChat
        self.result = ChatActionResult.error

    @classmethod
    def deserialize(cls, client_obj, data: bytes):
        inst = cls(client_obj)
        chat, acted, act, res = struct.unpack_from("<QQII", data, 0)
        inst.chat_id = SteamID.from_raw(chat)
        inst.user_id = SteamID.from_raw(acted)
        inst.action = ChatAction(act)
        inst.result = ChatActionResult(res)
        return inst

    def to_clientmsg(self) -> CMResponse:
        packet = CMResponse(eMsgID=EMsg.ClientChatActionResult, client_obj=self.client_obj)
        packet.data = struct.pack(
            "<QQII",
            int(self.chat_id),
            int(self.user_id),
            int(self.action),
            int(self.result),
        )
        packet.length = len(packet.data)
        return packet
