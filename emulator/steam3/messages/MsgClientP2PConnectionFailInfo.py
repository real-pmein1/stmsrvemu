"""
MsgClientP2PConnectionFailInfo - P2P connection failure notification message
Matches C++ MsgClientP2PConnectionFailInfo structure exactly
"""

from __future__ import annotations
import struct
import logging

from steam3.Types.steamid import SteamID
from steam3.Types.steam_types import P2PSessionError
from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse

log = logging.getLogger("MsgClientP2PConnectionFailInfo")


class MsgClientP2PConnectionFailInfo:
    """
    Client P2P connection failure info message - matches C++ MsgClientP2PConnectionFailInfo structure
    
    Fields:
        destination_steam_id (SteamID): Target SteamID that failed to connect
        source_steam_id (SteamID): Source SteamID that attempted connection
        app_id (int): Application ID
        error_code (P2PSessionError): Specific error that occurred
        error_string (str): Human-readable error description
    """
    
    def __init__(self, client_obj, data: bytes | None = None, version: int | None = None):
        self.client_obj = client_obj
        self.version = version or 1
        
        # Initialize fields with defaults matching C++
        self.destination_steam_id = SteamID()
        self.source_steam_id = SteamID()
        self.app_id = 0
        self.error_code = P2PSessionError.none
        self.error_string = ""
        
        if data:
            self.deserialize(data)
    
    def deserialize(self, data: bytes):
        """
        Deserialize binary data exactly matching C++ structure
        
        Binary format (little-endian):
        - destination_steam_id: 8 bytes (uint64)
        - source_steam_id: 8 bytes (uint64)
        - app_id: 4 bytes (uint32)
        - error_code: 4 bytes (uint32)
        - error_string_len: 4 bytes (uint32)
        - error_string: variable length (UTF-8)
        """
        if len(data) < 28:  # Minimum size for headers
            raise ValueError("Insufficient data for P2PConnectionFailInfo")
        
        offset = 0
        
        # Use struct.unpack_from as required by CLAUDE.md
        dest_raw, = struct.unpack_from('<Q', data, offset)
        offset += 8
        self.destination_steam_id = SteamID.from_raw(dest_raw)
        
        source_raw, = struct.unpack_from('<Q', data, offset)
        offset += 8
        self.source_steam_id = SteamID.from_raw(source_raw)
        
        self.app_id, = struct.unpack_from('<I', data, offset)
        offset += 4
        
        error_code_raw, = struct.unpack_from('<I', data, offset)
        offset += 4
        self.error_code = P2PSessionError(error_code_raw)
        
        # Read error string if present
        if offset < len(data):
            error_string_len, = struct.unpack_from('<I', data, offset)
            offset += 4
            
            if offset + error_string_len <= len(data):
                self.error_string = data[offset:offset+error_string_len].decode('utf-8', errors='replace')
            else:
                log.warning("Error string length exceeds available data")
                self.error_string = ""
        
        log.debug(f"Parsed P2PConnectionFailInfo: dest={self.destination_steam_id}, "
                 f"source={self.source_steam_id}, app={self.app_id}, error={self.error_code}")
    
    def to_clientmsg(self):
        """Build CMResponse for sending to client"""
        packet = CMResponse(EMsg.ClientP2PConnectionFailInfo, self.client_obj)
        
        # Pack data exactly matching C++ structure
        data = struct.pack('<Q', int(self.destination_steam_id))
        data += struct.pack('<Q', int(self.source_steam_id))
        data += struct.pack('<I', self.app_id)
        data += struct.pack('<I', int(self.error_code))
        
        # Add error string with length prefix
        error_bytes = self.error_string.encode('utf-8')
        data += struct.pack('<I', len(error_bytes))
        data += error_bytes
        
        packet.data = data
        packet.length = len(packet.data)
        
        return packet
    
    def to_protobuf(self):
        """Return protobuf message if available"""
        raise NotImplementedError("Protobuf version not implemented for P2PConnectionFailInfo")
    
    def __repr__(self):
        return (f"MsgClientP2PConnectionFailInfo(dest={self.destination_steam_id}, "
               f"source={self.source_steam_id}, app={self.app_id}, error={self.error_code})")
    
    def __str__(self):
        return self.__repr__()