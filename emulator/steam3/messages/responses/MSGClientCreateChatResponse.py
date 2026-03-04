from __future__ import annotations
import struct
import logging

from steam3.Types.steamid import SteamID
from steam3.Types.emsg import EMsg
from steam3.Types.steam_types import EResult
from steam3.Types.chat_types import ChatRoomType

log = logging.getLogger("MSGClientCreateChatResponse")


class MSGClientCreateChatResponse:
    """
    Server response to client CreateChat request.
    Exactly matches the C++ MsgClientCreateChatResponse structure.
    
    Fields:
        result (EResult): Result of the operation
        chatGlobalId (int): Steam ID of the created chatroom (0 if failed)
        type (ChatRoomType): Type of chatroom created
        friendChatGlobalId (int): Friend chat Steam ID
    """
    
    def __init__(self, client_obj, data: bytes | None = None, version: int | None = None):
        self.client_obj = client_obj
        self.version = version or 1
        
        # Initialize fields with defaults matching C++
        self.result = EResult.Fail
        self.chatGlobalId = 0
        self.type = ChatRoomType.MUC
        self.friendChatGlobalId = 0
        
        if data:
            self.deserialize(data)
    
    def deserialize(self, data: bytes):
        """
        Deserialize binary data exactly matching C++ structure.
        
        Binary format (little-endian):
        - result: 4 bytes (int32) - ResultType
        - chatGlobalId: 8 bytes (uint64)
        - type: 4 bytes (int32) - ChatRoomType
        - friendChatGlobalId: 8 bytes (uint64)
        """
        if len(data) < 24:
            raise ValueError("Insufficient data for ClientCreateChatResponse")
        
        # Use struct.unpack_from as required by CLAUDE.md
        unpacked = struct.unpack_from('<iQiQ', data, 0)
        
        self.result = EResult(unpacked[0])
        self.chatGlobalId = unpacked[1]
        self.type = ChatRoomType(unpacked[2])
        self.friendChatGlobalId = unpacked[3]
        
        log.debug(f"Parsed CreateChatResponse: result={self.result}, "
                 f"chatGlobalId={self.chatGlobalId}, type={self.type}")
    
    def to_clientmsg(self):
        """Build CMResponse for sending to client"""
        from steam3.cm_packet_utils import CMResponse
        
        packet = CMResponse(EMsg.ClientCreateChatResponse, self.client_obj)
        
        # Pack data exactly matching C++ structure
        packet.data = struct.pack('<iQiQ',
                                 int(self.result),
                                 self.chatGlobalId,
                                 int(self.type),
                                 self.friendChatGlobalId)
        packet.length = len(packet.data)
        
        return packet
    
    def to_protobuf(self):
        """Return protobuf message if available"""
        raise NotImplementedError("Protobuf version not implemented for CreateChatResponse")
    
    def __repr__(self):
        return (f"MSGClientCreateChatResponse(result={self.result}, "
               f"chatGlobalId={self.chatGlobalId}, type={self.type})")
    
    def __str__(self):
        return self.__repr__()