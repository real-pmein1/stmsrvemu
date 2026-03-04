from __future__ import annotations
import struct
import logging

from steam3.Types.steamid import SteamID
from steam3.Types.emsg import EMsg

log = logging.getLogger("MSGClientJoinChat")


class MSGClientJoinChat:
    """
    Client request to join a chatroom.
    Exactly matches the C++ MsgClientJoinChat structure.
    
    Fields:
        chatGlobalId (int): Steam ID of the chatroom to join
        voiceSpeaker (bool): Whether joining as voice speaker
    """
    
    def __init__(self, client_obj, data: bytes | None = None, version: int | None = None):
        self.client_obj = client_obj
        self.version = version or 1
        
        # Initialize fields with defaults matching C++
        self.chatGlobalId = 0
        self.voiceSpeaker = False
        
        if data:
            self.deserialize(data)
    
    def deserialize(self, data: bytes):
        """
        Deserialize binary data exactly matching C++ structure.
        
        Binary format (little-endian):
        - chatGlobalId: 8 bytes (uint64)
        - voiceSpeaker: 1 byte (bool)
        """
        if len(data) < 9:
            raise ValueError("Insufficient data for ClientJoinChat")
        
        # Use struct.unpack_from as required by CLAUDE.md
        self.chatGlobalId, voice_byte = struct.unpack_from('<QB', data, 0)
        self.voiceSpeaker = (voice_byte != 0)
        
        log.debug(f"Parsed JoinChat: chatGlobalId={self.chatGlobalId}, "
                 f"voiceSpeaker={self.voiceSpeaker}")
    
    def to_clientmsg(self):
        """Build CMResponse for sending to client"""
        from steam3.cm_packet_utils import CMResponse
        
        packet = CMResponse(EMsg.ClientJoinChat, self.client_obj)
        
        # Pack data exactly matching C++ structure
        packet.data = struct.pack('<QB',
                                 self.chatGlobalId,
                                 1 if self.voiceSpeaker else 0)
        packet.length = len(packet.data)
        
        return packet
    
    def to_protobuf(self):
        """Return protobuf message if available"""
        raise NotImplementedError("Protobuf version not implemented for JoinChat")
    
    def __repr__(self):
        return (f"MSGClientJoinChat(chatGlobalId={self.chatGlobalId}, "
               f"voiceSpeaker={self.voiceSpeaker})")
    
    def __str__(self):
        return self.__repr__()