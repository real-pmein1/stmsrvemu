"""
MsgClientP2PConnectionInfo - P2P connection candidate information message
Matches C++ MsgClientP2PConnectionInfo structure exactly
"""

from __future__ import annotations
import struct
import logging

from steam3.Types.steamid import SteamID
from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse

log = logging.getLogger("MsgClientP2PConnectionInfo")


class Candidate:
    """
    P2P connection candidate information matching C++ Candidate class
    """
    
    def __init__(self):
        self.name = ""              # Candidate identifier
        self.protocol = "UDP"       # Protocol (UDP/TCP)
        self.address = ""           # IP address
        self.port = 0               # Port number
        self.preference = 1.0       # Connection preference (1.0 default)
        self.username = ""          # Authentication username
        self.password = ""          # Authentication password
        self.type = "local"         # Candidate type (local/stun/relay)
        self.network_name = ""      # Network interface name
        self.generation = 0         # Generation counter
        self.nat_type = 0           # NAT type classification
    
    def serialize(self) -> bytes:
        """Serialize candidate to bytes for transmission"""
        # Simple serialization - in real implementation would use proper format
        data = struct.pack('<H', len(self.name)) + self.name.encode('utf-8')
        data += struct.pack('<H', len(self.protocol)) + self.protocol.encode('utf-8')
        data += struct.pack('<H', len(self.address)) + self.address.encode('utf-8')
        data += struct.pack('<H', self.port)
        data += struct.pack('<f', self.preference)
        data += struct.pack('<H', len(self.username)) + self.username.encode('utf-8')
        data += struct.pack('<H', len(self.password)) + self.password.encode('utf-8')
        data += struct.pack('<H', len(self.type)) + self.type.encode('utf-8')
        data += struct.pack('<H', len(self.network_name)) + self.network_name.encode('utf-8')
        data += struct.pack('<I', self.generation)
        data += struct.pack('<B', self.nat_type)
        return data
    
    def deserialize(self, data: bytes, offset: int = 0) -> int:
        """Deserialize candidate from bytes, returns new offset"""
        start_offset = offset
        
        try:
            # Read strings with length prefixes
            name_len, = struct.unpack_from('<H', data, offset)
            offset += 2
            self.name = data[offset:offset+name_len].decode('utf-8')
            offset += name_len
            
            protocol_len, = struct.unpack_from('<H', data, offset)
            offset += 2
            self.protocol = data[offset:offset+protocol_len].decode('utf-8')
            offset += protocol_len
            
            address_len, = struct.unpack_from('<H', data, offset)
            offset += 2
            self.address = data[offset:offset+address_len].decode('utf-8')
            offset += address_len
            
            self.port, = struct.unpack_from('<H', data, offset)
            offset += 2
            
            self.preference, = struct.unpack_from('<f', data, offset)
            offset += 4
            
            username_len, = struct.unpack_from('<H', data, offset)
            offset += 2
            self.username = data[offset:offset+username_len].decode('utf-8')
            offset += username_len
            
            password_len, = struct.unpack_from('<H', data, offset)
            offset += 2
            self.password = data[offset:offset+password_len].decode('utf-8')
            offset += password_len
            
            type_len, = struct.unpack_from('<H', data, offset)
            offset += 2
            self.type = data[offset:offset+type_len].decode('utf-8')
            offset += type_len
            
            network_len, = struct.unpack_from('<H', data, offset)
            offset += 2
            self.network_name = data[offset:offset+network_len].decode('utf-8')
            offset += network_len
            
            self.generation, = struct.unpack_from('<I', data, offset)
            offset += 4
            
            self.nat_type, = struct.unpack_from('<B', data, offset)
            offset += 1
            
        except (struct.error, UnicodeDecodeError) as e:
            log.error(f"Failed to deserialize candidate: {e}")
            return start_offset
        
        return offset


class MsgClientP2PConnectionInfo:
    """
    Client P2P connection info message - matches C++ MsgClientP2PConnectionInfo structure
    
    Fields:
        destination_steam_id (SteamID): Target SteamID
        source_steam_id (SteamID): Source SteamID  
        app_id (int): Application ID
        candidate (Candidate): Connection candidate information
    """
    
    def __init__(self, client_obj, data: bytes | None = None, version: int | None = None):
        self.client_obj = client_obj
        self.version = version or 1
        
        # Initialize fields with defaults matching C++
        self.destination_steam_id = SteamID()
        self.source_steam_id = SteamID()
        self.app_id = 0
        self.candidate = Candidate()
        
        if data:
            self.deserialize(data)
    
    def deserialize(self, data: bytes):
        """
        Deserialize binary data exactly matching C++ structure
        
        Binary format (little-endian):
        - destination_steam_id: 8 bytes (uint64)
        - source_steam_id: 8 bytes (uint64)
        - app_id: 4 bytes (uint32)
        - candidate: variable length serialized candidate data
        """
        if len(data) < 20:  # Minimum size for headers
            raise ValueError("Insufficient data for P2PConnectionInfo")
        
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
        
        # Deserialize candidate data
        if offset < len(data):
            self.candidate.deserialize(data, offset)
        
        log.debug(f"Parsed P2PConnectionInfo: dest={self.destination_steam_id}, "
                 f"source={self.source_steam_id}, app={self.app_id}")
    
    def to_clientmsg(self):
        """Build CMResponse for sending to client"""
        packet = CMResponse(EMsg.ClientP2PConnectionInfo, self.client_obj)
        
        # Pack data exactly matching C++ structure
        data = struct.pack('<Q', int(self.destination_steam_id))
        data += struct.pack('<Q', int(self.source_steam_id))
        data += struct.pack('<I', self.app_id)
        
        # Append serialized candidate data
        data += self.candidate.serialize()
        
        packet.data = data
        packet.length = len(packet.data)
        
        return packet
    
    def to_protobuf(self):
        """Return protobuf message if available"""
        raise NotImplementedError("Protobuf version not implemented for P2PConnectionInfo")
    
    def __repr__(self):
        return (f"MsgClientP2PConnectionInfo(dest={self.destination_steam_id}, "
               f"source={self.source_steam_id}, app={self.app_id})")
    
    def __str__(self):
        return self.__repr__()