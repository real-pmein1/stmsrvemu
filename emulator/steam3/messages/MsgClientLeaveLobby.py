"""
MsgClientLeaveLobby - Client request to leave a lobby
"""

import struct
import logging
from steam3.Types.steamid import SteamID

log = logging.getLogger("MsgClientLeaveLobby")


class MsgClientLeaveLobby:
    """
    Client request to leave a lobby
    
    Fields:
        lobby_steam_id (int): Steam ID of the lobby to leave
    """
    
    def __init__(self, client_obj, data: bytes = None):
        self.client_obj = client_obj
        
        # Initialize fields
        self.lobby_steam_id = 0
        
        if data:
            self.deserialize(data)
    
    def deserialize(self, data: bytes):
        """Parse MsgClientLeaveLobby from raw bytes"""
        try:
            if len(data) < 8:  # 8 bytes lobby ID
                raise ValueError(f"Data too short: {len(data)} < 8 bytes")
            
            # Parse lobby ID
            self.lobby_steam_id = struct.unpack_from('<Q', data, 0)[0]
            
            log.debug(f"Parsed LeaveLobby: lobby_id={self.lobby_steam_id:x}")
            
        except Exception as e:
            log.error(f"Failed to parse MsgClientLeaveLobby: {e}")
            raise ValueError(f"Failed to parse MsgClientLeaveLobby: {e}")
    
    def __repr__(self):
        return f"MsgClientLeaveLobby(lobby_steam_id={self.lobby_steam_id:x})"