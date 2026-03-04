"""
MsgClientUDSP2PSessionEnded - UDS P2P session ended notification message
Matches C++ MsgClientUDSP2PSessionEnded structure exactly
"""

from __future__ import annotations
import struct
import logging

from steam3.Types.steamid import SteamID
from steam3.Types.steam_types import P2PSessionError
from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse

log = logging.getLogger("MsgClientUDSP2PSessionEnded")


class MsgClientUDSP2PSessionEnded:
    """
    Client UDS P2P session ended message - matches C++ MsgClientUDSP2PSessionEnded structure
    
    Fields:
        source_steam_id (SteamID): SteamID that ended the session
        dest_steam_id (SteamID): SteamID that was disconnected
        app_id (int): Application ID for this session
        session_id (int): Session identifier that ended
        socket_id (int): Socket identifier for UDS communication
        end_reason (P2PSessionError): Reason for session termination
        bytes_sent (int): Total bytes sent during session
        bytes_received (int): Total bytes received during session
        session_duration (int): Duration in milliseconds
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
        self.end_reason = P2PSessionError.none
        self.bytes_sent = 0
        self.bytes_received = 0
        self.session_duration = 0
        
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
        - end_reason: 4 bytes (uint32)
        - bytes_sent: 8 bytes (uint64)
        - bytes_received: 8 bytes (uint64)
        - session_duration: 4 bytes (uint32)
        """
        if len(data) < 56:  # Exact size for all fields
            raise ValueError("Insufficient data for UDSSessionEnded")
        
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
        
        end_reason_raw, = struct.unpack_from('<I', data, offset)
        offset += 4
        self.end_reason = P2PSessionError(end_reason_raw)
        
        self.bytes_sent, = struct.unpack_from('<Q', data, offset)
        offset += 8
        
        self.bytes_received, = struct.unpack_from('<Q', data, offset)
        offset += 8
        
        self.session_duration, = struct.unpack_from('<I', data, offset)
        offset += 4
        
        log.debug(f"Parsed UDSSessionEnded: source={self.source_steam_id}, "
                 f"dest={self.dest_steam_id}, app={self.app_id}, session={self.session_id}, "
                 f"reason={self.end_reason}")
    
    def to_clientmsg(self):
        """Build CMResponse for sending to client"""
        packet = CMResponse(EMsg.ClientUDSP2PSessionEnded, self.client_obj)
        
        # Pack data exactly matching C++ structure
        data = struct.pack('<Q', int(self.source_steam_id))
        data += struct.pack('<Q', int(self.dest_steam_id))
        data += struct.pack('<I', self.app_id)
        data += struct.pack('<I', self.session_id)
        data += struct.pack('<I', self.socket_id)
        data += struct.pack('<I', int(self.end_reason))
        data += struct.pack('<Q', self.bytes_sent)
        data += struct.pack('<Q', self.bytes_received)
        data += struct.pack('<I', self.session_duration)
        
        packet.data = data
        packet.length = len(packet.data)
        
        return packet
    
    def to_protobuf(self):
        """Return protobuf message if available"""
        raise NotImplementedError("Protobuf version not implemented for UDSP2PSessionEnded")
    
    def __repr__(self):
        return (f"MsgClientUDSP2PSessionEnded(source={self.source_steam_id}, "
               f"dest={self.dest_steam_id}, app={self.app_id}, session={self.session_id}, "
               f"reason={self.end_reason})")
    
    def __str__(self):
        return self.__repr__()