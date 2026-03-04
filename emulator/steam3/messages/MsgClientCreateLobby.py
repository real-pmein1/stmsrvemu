"""
MsgClientCreateLobby - Client request to create a new lobby (both MMS and regular lobbies)
Based on client decompilation and Steam API documentation
Handles both ClientCreateLobby and ClientMMSCreateLobby message formats
"""

import struct
import logging
from steam3.Types.steam_types import EResult
from steam3.Types.steamid import SteamID
from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse

log = logging.getLogger("MsgClientCreateLobby")


class MsgClientCreateLobby:
    """
    Client request to create a new lobby
    
    Fields:
        app_id (int): Application/Game ID
        lobby_type (int): Type of lobby (private, public, etc.)
        max_members (int): Maximum number of members allowed
        lobby_flags (int): Lobby configuration flags
        cell_id (int): Cell ID for regional matching
        public_ip (int): Public IP address of creator
        metadata_size (int): Size of initial metadata
        metadata (bytes): Initial lobby metadata (KeyValues format)
    """
    
    def __init__(self, client_obj, data: bytes = None):
        self.client_obj = client_obj
        
        # Initialize fields with defaults
        self.app_id = 0
        self.lobby_type = 0  # 0=private, 2=public
        self.max_members = 4
        self.lobby_flags = 0
        self.cell_id = 0
        self.public_ip = 0
        self.metadata_size = 0
        self.metadata = b''
        
        if data:
            self.deserialize(data)
    
    def deserialize(self, data: bytes):
        """Parse MsgClientCreateLobby from raw bytes"""
        try:
            if len(data) < 24:  # Minimum size for fixed fields
                raise ValueError(f"Data too short: {len(data)} < 24 bytes")
            
            # Parse fixed fields
            (self.app_id, self.lobby_type, self.max_members, 
             self.lobby_flags, self.cell_id, self.public_ip) = struct.unpack_from('<QIIIHI', data, 0)
            
            offset = 24
            
            # Parse metadata if present
            if len(data) > offset:
                self.metadata_size = struct.unpack_from('<I', data, offset)[0]
                offset += 4
                
                if self.metadata_size > 0 and len(data) >= offset + self.metadata_size:
                    self.metadata = data[offset:offset + self.metadata_size]
                    
            log.debug(f"Parsed CreateLobby: app_id={self.app_id}, type={self.lobby_type}, max_members={self.max_members}")
            
        except Exception as e:
            log.error(f"Failed to parse MsgClientCreateLobby: {e}")
            raise ValueError(f"Failed to parse MsgClientCreateLobby: {e}")
    
    def __repr__(self):
        return (
            f"MsgClientCreateLobby("
            f"app_id={self.app_id}, "
            f"lobby_type={self.lobby_type}, "
            f"max_members={self.max_members}, "
            f"flags={self.lobby_flags}, "
            f"metadata_size={self.metadata_size}"
            f")"
        )