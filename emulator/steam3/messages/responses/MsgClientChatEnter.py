import struct
from steam3.Types.MessageObject.ChatMemberInfo import ChatMemberInfo
from steam3.cm_packet_utils import CMResponse
from steam3.Types.emsg import EMsg
from steam3.ClientManager.client import Client
from typing import List, Optional

from steam3.Types.chat_types import ChatRoomType, ChatRoomEnterResponse


class MsgClientChatEnter:
    def __init__(
        self,
        client_obj: Client,
        steam_id_chat: int,
        steam_id_friend_chat: int,
        chat_type: ChatRoomType,
        steam_id_owner: int,
        steam_id_clan: int,
        locked: bool,
        enter_response: ChatRoomEnterResponse,
        chat_room_name: str,
        member_infos: List[ChatMemberInfo] = None,
        members_max: Optional[int] = None,
    ):
        self.client_obj = client_obj
        self.steam_id_chat = steam_id_chat
        self.steam_id_friend_chat = steam_id_friend_chat
        self.chat_type = chat_type
        self.steam_id_owner = steam_id_owner
        self.steam_id_clan = steam_id_clan
        self.locked = locked
        self.enter_response = enter_response
        self.member_infos = member_infos
        # total count is inferred:
        self.members_total = len(member_infos)
        self.chat_room_name = chat_room_name
        self.members_max = members_max

    def __str__(self):
        lines = [
            f"ChatEnter:",
            f"  ChatID:       {self.steam_id_chat}",
            f"  FriendChatID: {self.steam_id_friend_chat}",
            f"  Type:         {self.chat_type.name}",
            f"  OwnerID:      {self.steam_id_owner}",
            f"  ClanID:       {self.steam_id_clan}",
            f"  Locked:       {self.locked}",
            f"  Response:     {self.enter_response.name}",
            f"  MembersTotal: {self.members_total}",
            f"  RoomName:     {self.chat_room_name!r}",
            f"  MembersMax:   {self.members_max}",
            "  Members:",
        ]
        for mi in self.member_infos:
            lines.append(f"    {mi}")
        return "\n".join(lines)

    def to_clientmsg(self) -> CMResponse:
        """
        Serialize back into a CMResponse for EMsg.ClientChatEnter.
        """
        # 1) pack the fixed struct (no padding, little-endian):
        data = struct.pack(
            '<Q Q I Q Q ? I I',
            self.steam_id_chat,
            self.steam_id_friend_chat,
            int(self.chat_type),
            self.steam_id_owner,
            self.steam_id_clan,
            self.locked,
            int(self.enter_response),
            self.members_total,
        )

        # 2) NUL-terminated room name (limit enforced by client code):
        name_bytes = self.chat_room_name.encode('utf-8') + b'\x00'
        data += name_bytes

        # 3) each ChatMemberInfo serializes itself into the same message stream
        if self.members_max:
            for member in self.member_infos:
                data += member.serialize()  # assumes ChatMemberInfo has to_msg()

        # 4) optional members_max
        if self.members_max is not None:
            data += struct.pack('<i', self.members_max)

        # 5) build the CMResponse
        packet = CMResponse(
            eMsgID=EMsg.ClientChatEnter,
            client_obj=self.client_obj
        )
        packet.data = data
        packet.length = len(data)
        return packet
