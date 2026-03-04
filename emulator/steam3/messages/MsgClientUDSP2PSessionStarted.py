"""
MsgClientUDSP2PSessionStarted - UDS P2P session started notification message
Matches C++ MsgClientUDSP2PSessionStarted structure exactly
"""

from __future__ import annotations
import struct
import logging

from steam3.Types.steamid import SteamID
from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse

log = logging.getLogger("MsgClientUDSP2PSessionStarted")


class MsgClientUDSP2PSessionStarted:
    """
    Client UDS P2P session started message - matches C++ MsgClientUDSP2PSessionStarted structure
    
    Fields:
        source_steam_id (SteamID): SteamID that initiated the session
        dest_steam_id (SteamID): SteamID that accepted the session
        app_id (int): Application ID for this session
        session_id (int): Unique session identifier
        socket_id (int): Socket identifier for UDS communication
        session_flags (int): Session configuration flags
    """
    
    def __init__(self, client_obj, data: bytes | None = None, version: int | None = None):
        self.client_obj = client_obj
        self.version = version or 1
        
        # Initialize fields with defaults matching C++
        self.source_steam_id = SteamID()
        self.dest_steam_id = SteamID()
        self.app_id = 0
        self.session_id = 0
        self.socket_id = 0
        self.session_flags = 0
        
        if data:
            self.deserialize(data)
    
    def deserialize(self, data: bytes):
        """
        Deserialize binary data exactly matching C++ structure
        
        Binary format (little-endian):
        - source_steam_id: 8 bytes (uint64)
        - dest_steam_id: 8 bytes (uint64)
        - app_id: 4 bytes (uint32)
        - session_id: 4 bytes (uint32)
        - socket_id: 4 bytes (uint32)
        - session_flags: 4 bytes (uint32)
        """
        if len(data) < 32:  # Exact size for all fields
            raise ValueError("Insufficient data for UDSSessionStarted")
        
        offset = 0
        
        # Use struct.unpack_from as required by CLAUDE.md
        source_raw, = struct.unpack_from('<Q', data, offset)
        offset += 8
        self.source_steam_id = SteamID.from_raw(source_raw)
        
        dest_raw, = struct.unpack_from('<Q', data, offset)
        offset += 8
        self.dest_steam_id = SteamID.from_raw(dest_raw)
        
        self.app_id, = struct.unpack_from('<I', data, offset)
        offset += 4
        
        self.session_id, = struct.unpack_from('<I', data, offset)
        offset += 4
        
        self.socket_id, = struct.unpack_from('<I', data, offset)
        offset += 4
        
        self.session_flags, = struct.unpack_from('<I', data, offset)
        offset += 4
        
        log.debug(f"Parsed UDSSessionStarted: source={self.source_steam_id}, "
                 f"dest={self.dest_steam_id}, app={self.app_id}, session={self.session_id}")
    
    def to_clientmsg(self):
        """Build CMResponse for sending to client"""
        packet = CMResponse(EMsg.ClientUDSP2PSessionStarted, self.client_obj)
        
        # Pack data exactly matching C++ structure
        data = struct.pack('<Q', int(self.source_steam_id))
        data += struct.pack('<Q', int(self.dest_steam_id))
        data += struct.pack('<I', self.app_id)
        data += struct.pack('<I', self.session_id)
        data += struct.pack('<I', self.socket_id)
        data += struct.pack('<I', self.session_flags)
        
        packet.data = data
        packet.length = len(packet.data)
        
        return packet
    
    def to_protobuf(self):
        """Return protobuf message if available"""
        raise NotImplementedError("Protobuf version not implemented for UDSP2PSessionStarted")
    
    def __repr__(self):
        return (f"MsgClientUDSP2PSessionStarted(source={self.source_steam_id}, "
               f"dest={self.dest_steam_id}, app={self.app_id}, session={self.session_id})")
    
    def __str__(self):
        return self.__repr__()