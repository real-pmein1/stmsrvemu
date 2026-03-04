"""
MsgClientJoinLobby - Client request to join an existing lobby
Based on client decompilation
"""

import struct
import logging
from steam3.Types.steamid import SteamID
from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse

log = logging.getLogger("MsgClientJoinLobby")


class MsgClientJoinLobby:
    """
    Client request to join a lobby
    
    Fields:
        lobby_steam_id (int): Steam ID of the lobby to join
        app_id (int): Application ID (for validation)
    """
    
    def __init__(self, client_obj, data: bytes = None):
        self.client_obj = client_obj
        
        # Initialize fields
        self.lobby_steam_id = 0
        self.app_id = 0
        
        if data:
            self.deserialize(data)
    
    def deserialize(self, data: bytes):
        """Parse MsgClientJoinLobby from raw bytes"""
        try:
            if len(data) < 16:  # 8 bytes lobby ID + 8 bytes app ID
                raise ValueError(f"Data too short: {len(data)} < 16 bytes")
            
            # Parse fields
            self.lobby_steam_id, self.app_id = struct.unpack_from('<QQ', data, 0)
            
            log.debug(f"Parsed JoinLobby: lobby_id={self.lobby_steam_id:x}, app_id={self.app_id}")
            
        except Exception as e:
            log.error(f"Failed to parse MsgClientJoinLobby: {e}")
            raise ValueError(f"Failed to parse MsgClientJoinLobby: {e}")
    
    def __repr__(self):
        return (
            f"MsgClientJoinLobby("
            f"lobby_steam_id={self.lobby_steam_id:x}, "
            f"app_id={self.app_id}"
            f")"
        )