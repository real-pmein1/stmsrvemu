import struct
from io import BytesIO
from steam3.Types.chat_types import ChatInfoType, ChatRoomFlags
from steam3.Types.steamid import SteamID
from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse


class MsgClientChatRoomInfo:
    """Represents MsgClientChatRoomInfo_t."""

    def __init__(self, client_obj):
        self.client_obj = client_obj
        self.chat_id = SteamID()
        self.info_type = ChatInfoType.stateChange
        self.flags = ChatRoomFlags.none
        self.steam_id_making_change = SteamID()
        self.member_id = SteamID()
        self.members_max = 0
        self.state_change_flags = 0

    def to_clientmsg(self) -> CMResponse:
        buf = BytesIO()
        buf.write(struct.pack("<QI", int(self.chat_id), int(self.info_type)))
        if self.info_type == ChatInfoType.infoUpdate:
            buf.write(struct.pack("<IQ", int(self.flags), int(self.steam_id_making_change)))
        elif self.info_type == ChatInfoType.memberLimitChange:
            buf.write(struct.pack("<QI", int(self.member_id), self.members_max))
        elif self.info_type == ChatInfoType.stateChange:
            buf.write(struct.pack("<I", self.state_change_flags))
        packet = CMResponse(eMsgID=EMsg.ClientChatRoomInfo, client_obj=self.client_obj)
        packet.data = buf.getvalue()
        packet.length = len(packet.data)
        return packet
