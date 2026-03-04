"""
MsgClientCreateLobbyResponse - Server response to lobby creation request
"""

import struct
import logging
from steam3.Types.steam_types import EResult
from steam3.Types.steamid import SteamID
from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse

log = logging.getLogger("MsgClientCreateLobbyResponse")


class MsgClientCreateLobbyResponse:
    """
    Server response to lobby creation request
    
    Fields:
        result (EResult): Success/failure result
        lobby_steam_id (int): Steam ID of created lobby (0 if failed)
        app_id (int): Application ID
        lobby_type (int): Type of lobby created
        max_members (int): Maximum members allowed
        cell_id (int): Cell ID for regional matching
        public_ip (int): Public IP of lobby creator
    """
    
    def __init__(self, client_obj, result: EResult = EResult.OK, lobby_steam_id: int = 0, 
                 app_id: int = 0, lobby_type: int = 0, max_members: int = 4, 
                 cell_id: int = 0, public_ip: int = 0):
        self.client_obj = client_obj
        self.result = result
        self.lobby_steam_id = lobby_steam_id
        self.app_id = app_id
        self.lobby_type = lobby_type
        self.max_members = max_members
        self.cell_id = cell_id
        self.public_ip = public_ip
    
    def to_clientmsg(self):
        """Build CMResponse packet"""
        packet = CMResponse(eMsgID=EMsg.ClientMMSCreateLobbyResponse, client_obj=self.client_obj)
        
        # Pack response data
        packet.data = struct.pack(
            '<IQQIIIHI',
            int(self.result),           # EResult
            self.lobby_steam_id,        # Created lobby Steam ID
            self.app_id,                # App ID
            self.lobby_type,            # Lobby type
            self.max_members,           # Max members
            self.cell_id,               # Cell ID
            0,                          # Padding
            self.public_ip              # Public IP
        )
        packet.length = len(packet.data)
        
        log.debug(f"Built CreateLobbyResponse: result={self.result}, lobby_id={self.lobby_steam_id:x}")
        return packet
    
    def __repr__(self):
        return (
            f"MsgClientCreateLobbyResponse("
            f"result={self.result}, "
            f"lobby_steam_id={self.lobby_steam_id:x}, "
            f"app_id={self.app_id}"
            f")"
        )