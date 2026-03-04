import struct
from steam3.Types.chat_types import ChatRoomType
from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse

class MsgClientChatInvite:
    """
    Python version of MsgClientChatInvite
    Fields (body.*):
      - invitedSteamID: int
      - chatroomSteamID: int
      - patronSteamID: int
      - chat_room_type: int
      - friend_chat_global_id: int
      - chat_room_name: Optional[str]
      - game_id: int
    """
    def __init__(self, client_obj):
        self.client_obj = client_obj
        # defaults
        self.invitedSteamID = 0
        self.chatroomSteamID = 0
        self.patronSteamID = 0
        self.chat_room_type = ChatRoomType.none
        self.friend_chat_global_id = 0
        self.chat_room_name = None
        self.game_id = 0

    @classmethod
    def deserialize(cls, client_obj, raw_data: bytes):
        inst = cls(client_obj)
        idx = 0

        # 1) invitedGlobalId (8 bytes)
        inst.invitedSteamID, = struct.unpack_from('<Q', raw_data, idx)
        idx += 8

        # 2) chatGlobalId (8 bytes)
        inst.chatroomSteamID, = struct.unpack_from('<Q', raw_data, idx)
        idx += 8

        # 3) patronGlobalId (8 bytes)
        inst.patronSteamID, = struct.unpack_from('<Q', raw_data, idx)
        idx += 8

        # 4) chatRoomType (4 bytes)
        inst.chat_room_type, = struct.unpack_from('<I', raw_data, idx)
        idx += 4

        # 5) friendChatGlobalId (8 bytes)
        inst.friend_chat_global_id, = struct.unpack_from('<Q', raw_data, idx)
        idx += 8

        # 6) optional: chatRoomName + gameId
        if inst.chat_room_type != ChatRoomType.none:
            # read length prefix (4 bytes)
            name_len, = struct.unpack_from('<I', raw_data, idx)
            idx += 4

            # read the name bytes
            name_bytes = raw_data[idx:idx + name_len]
            inst.chat_room_name = name_bytes.rstrip(b'\x00').decode('ascii')
            idx += name_len

            # read gameId (8 bytes)
            inst.game_id, = struct.unpack_from('<Q', raw_data, idx)
            idx += 8

        return inst

    def to_clientmsg(self):
        """
        Build a CMResponse packet with the serialized body.
        """
        packet = CMResponse(
            eMsgID=EMsg.ClientChatInvite,
            client_obj=self.client_obj
        )

        parts = []
        # invitedGlobalId, chatGlobalId, patronGlobalId
        parts.append(struct.pack('<Q', self.invitedSteamID))
        parts.append(struct.pack('<Q', self.chatroomSteamID))
        parts.append(struct.pack('<Q', self.patronSteamID))

        # chatRoomType
        parts.append(struct.pack('<I', self.chat_room_type))

        # friendChatGlobalId
        parts.append(struct.pack('<Q', self.friend_chat_global_id))

        # optional section
        if self.chat_room_type != ChatRoomType.none:
            # chatRoomName length + bytes
            name_bytes = (self.chat_room_name or "").encode('ascii')
            # null-terminated?
            name_bytes += b'\x00'
            parts.append(struct.pack('<I', len(name_bytes)))
            parts.append(name_bytes)
            # gameId
            parts.append(struct.pack('<Q', self.game_id))

        data = b"".join(parts)
        packet.data = data
        packet.length = len(data)
        return packet

    def __str__(self):
        base = (
            f"MsgClientChatInvite:\n"
            f"  InvitedGlobalId: {self.invitedSteamID}\n"
            f"  ChatGlobalId:    {self.chatroomSteamID}\n"
            f"  PatronGlobalId:  {self.patronSteamID}\n"
            f"  ChatRoomType:    {self.chat_room_type}\n"
            f"  FriendChatId:    {self.friend_chat_global_id}\n"
        )
        if self.chat_room_type != ChatRoomType.none:
            base += (
                f"  ChatRoomName:    {self.chat_room_name!r}\n"
                f"  GameId:          {self.game_id}\n"
            )
        return base
