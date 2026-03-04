from __future__ import annotations
import struct
from steam3.Types.chat_types import ChatEntryType
from steam3.Types.steamid import SteamID
from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse

# Mirror the C++ constant
MSG_CLIENT_CHAT_MSG_MAX_LENGHT = 0x1000

class MsgClientChatMsg:
    """
    Python equivalent of the C++ MsgClientChatMsg.

    Fields:
      memberGlobalId (uint64)
      chatGlobalId   (uint64)
      entryType      (int32)        # ChatEntryType enum
      data           (bytes)        # payload of the chat message
    """
    def __init__(self, client_obj, data: bytes | None = None):
        self.memberGlobalId = SteamID()
        self.chatGlobalId = SteamID()
        self.entryType = ChatEntryType.chatMsg
        self.data = b""
        self.client_obj = client_obj

        if data is not None:
            self.deserialize(data)

    def deserialize(self, data: bytes):
        """
        Parse a byte buffer into:
          1) 8-byte little-endian unsigned memberGlobalId
          2) 8-byte little-endian unsigned chatGlobalId
          3) 4-byte little-endian signed entryType
          4) remaining bytes as `data`; length must not exceed MSG_CLIENT_CHAT_MSG_MAX_LENGHT
        """
        offset = 0
        self.memberGlobalId = SteamID.from_raw(struct.unpack_from('<Q', data, offset)[0])
        offset += 8
        self.chatGlobalId = SteamID.from_raw(struct.unpack_from('<Q', data, offset)[0])
        offset += 8
        self.entryType = ChatEntryType(struct.unpack_from('<i', data, offset)[0])
        offset += 4

        remaining = data[offset:]
        if len(remaining) > MSG_CLIENT_CHAT_MSG_MAX_LENGHT:
            raise ValueError("Invalid data length")
        self.data = remaining

    def to_protobuf(self):
        """
        Not implemented for this message type.
        """
        raise NotImplementedError("to_protobuf not implemented")

    def to_clientmsg(self):
        """
        Build a CMRequest packet with payload:
          1) 8-byte little-endian unsigned memberGlobalId
          2) 8-byte little-endian unsigned chatGlobalId
          3) 4-byte little-endian signed entryType
          4) `data` bytes

        The total `data` length must not exceed MSG_CLIENT_CHAT_MSG_MAX_LENGHT.
        """
        if len(self.data) > MSG_CLIENT_CHAT_MSG_MAX_LENGHT:
            raise ValueError("Invalid data length")

        packet = CMResponse(eMsgID=EMsg.ClientChatMsg, client_obj=self.client_obj)
        header = struct.pack(
            '<QQi',
            int(self.memberGlobalId),
            int(self.chatGlobalId),
            int(self.entryType),
        )
        packet.data = header + self.data
        packet.length = len(packet.data)
        return packet

    def __str__(self):
        return (
            f"{self.__class__.__name__}("
            f"memberGlobalId={self.memberGlobalId}, "
            f"chatGlobalId={self.chatGlobalId}, "
            f"entryType={self.entryType}, "
            f"data_length={len(self.data)}"
            f")"
        )
