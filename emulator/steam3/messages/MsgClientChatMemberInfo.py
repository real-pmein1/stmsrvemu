from __future__ import annotations
import struct
from typing import Optional
from steam3.Types.chat_types import ChatInfoType, ChatMemberStateChange
from steam3.Types.steamid import SteamID
from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse
from steam3.Types.MessageObject.ChatMemberInfo import ChatMemberInfo


class MsgClientChatMemberInfo:
    """Client request conveying chat member info changes."""

    def __init__(self, client_obj, data: bytes | None = None):
        self.client_obj = client_obj
        self.chat_id = SteamID()
        self.info_type = ChatInfoType.stateChange
        self.user_steam_id = SteamID()
        self.state_change = ChatMemberStateChange.entered
        self.target_steam_id = SteamID()
        self.member_limit = 0
        # ChatMemberInfo - required when state_change is entered or info_type is infoUpdate
        self.member_info: Optional[ChatMemberInfo] = None
        if data is not None:
            self.deserialize(data)

    def deserialize(self, data: bytes) -> None:
        offset = 0
        chat, info = struct.unpack_from("<QI", data, offset)
        offset += 12
        self.chat_id = SteamID.from_raw(chat)
        self.info_type = ChatInfoType(info)
        if self.info_type == ChatInfoType.stateChange:
            uid, change, target = struct.unpack_from("<QiQ", data, offset)
            self.user_steam_id = SteamID.from_raw(uid)
            self.state_change = ChatMemberStateChange(change)
            self.target_steam_id = SteamID.from_raw(target)
        elif self.info_type == ChatInfoType.memberLimitChange:
            uid, limit = struct.unpack_from("<Qi", data, offset)
            self.user_steam_id = SteamID.from_raw(uid)
            self.member_limit = limit

    def to_clientmsg(self) -> CMResponse:
        buf = bytearray()
        buf.extend(struct.pack("<QI", int(self.chat_id), int(self.info_type)))
        if self.info_type == ChatInfoType.stateChange:
            buf.extend(struct.pack("<QiQ", int(self.user_steam_id), int(self.state_change), int(self.target_steam_id)))
            # Include memberInfo when state_change is entered (per tinserver protocol)
            if self.state_change == ChatMemberStateChange.entered and self.member_info:
                buf.extend(self.member_info.serialize())
        elif self.info_type == ChatInfoType.memberLimitChange:
            buf.extend(struct.pack("<Qi", int(self.user_steam_id), self.member_limit))
        packet = CMResponse(eMsgID=EMsg.ClientChatMemberInfo, client_obj=self.client_obj)
        packet.data = bytes(buf)
        packet.length = len(packet.data)
        return packet
