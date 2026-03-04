"""
MsgClientJoinLobbyResponse - Server response to ClientMMSJoinLobby request
Based on Steam3 MMS (Matchmaking Service) protocol
"""

import struct
import logging
from io import BytesIO
from steam3.Types.steam_types import EResult
from steam3.Types.steamid import SteamID
from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse

log = logging.getLogger("MsgClientJoinLobbyResponse")


class MsgClientJoinLobbyResponse:
    """
    Server response to ClientMMSJoinLobby request
    
    Fields:
        result (EResult): Success/failure result
        app_id (int): Application ID
        lobby_steam_id (int): Steam ID of the lobby
        chat_room_enter_response (int): Chat room entry response code
        max_members (int): Maximum lobby members
        lobby_type (int): Type of lobby
        lobby_flags (int): Lobby flags
        steam_id_owner (int): Steam ID of lobby owner
        metadata (bytes): Lobby metadata
        members (list): List of current lobby members
    """
    
    def __init__(self, client_obj, result: EResult = EResult.OK, app_id: int = 0,
                 lobby_steam_id: int = 0, chat_room_enter_response: int = 1,
                 max_members: int = 4, lobby_type: int = 2, lobby_flags: int = 0,
                 steam_id_owner: int = 0, metadata: bytes = b'', members: list = None):
        self.client_obj = client_obj
        self.result = result
        self.app_id = app_id
        self.lobby_steam_id = lobby_steam_id
        self.chat_room_enter_response = chat_room_enter_response  # 1 = success
        self.max_members = max_members
        self.lobby_type = lobby_type
        self.lobby_flags = lobby_flags
        self.steam_id_owner = steam_id_owner
        self.metadata = metadata or b''
        self.members = members or []
    
    def to_clientmsg(self):
        """Create CMResponse packet for ClientMMSJoinLobbyResponse"""
        packet = CMResponse(
            eMsgID=EMsg.ClientMMSJoinLobbyResponse,
            client_obj=self.client_obj
        )
        
        # Build response data
        data_buffer = BytesIO()
        
        # Write basic fields
        data_buffer.write(struct.pack('<I', self.app_id))                    # app_id (4 bytes)
        data_buffer.write(struct.pack('<Q', self.lobby_steam_id))            # lobby_steam_id (8 bytes)
        data_buffer.write(struct.pack('<I', self.chat_room_enter_response))  # enter_response (4 bytes)
        data_buffer.write(struct.pack('<I', self.max_members))               # max_members (4 bytes)
        data_buffer.write(struct.pack('<I', self.lobby_type))                # lobby_type (4 bytes)
        data_buffer.write(struct.pack('<I', self.lobby_flags))               # lobby_flags (4 bytes)
        data_buffer.write(struct.pack('<Q', self.steam_id_owner))            # owner_steam_id (8 bytes)
        
        # Write metadata length and data
        data_buffer.write(struct.pack('<I', len(self.metadata)))             # metadata_len (4 bytes)
        if self.metadata:
            data_buffer.write(self.metadata)                                 # metadata
        
        # Write member count and member data
        data_buffer.write(struct.pack('<I', len(self.members)))              # member_count (4 bytes)
        for member in self.members:
            # Each member: steam_id (8) + persona_name_len (4) + persona_name + metadata_len (4) + metadata
            steam_id = member.get('steam_id', 0)
            persona_name = member.get('persona_name', '').encode('utf-8', errors='replace')
            member_metadata = member.get('metadata', b'')
            
            data_buffer.write(struct.pack('<Q', steam_id))                   # member_steam_id (8 bytes)
            data_buffer.write(struct.pack('<I', len(persona_name)))          # persona_name_len (4 bytes)
            data_buffer.write(persona_name)                                  # persona_name
            data_buffer.write(struct.pack('<I', len(member_metadata)))       # member_metadata_len (4 bytes)
            if member_metadata:
                data_buffer.write(member_metadata)                           # member_metadata
        
        packet.data = data_buffer.getvalue()
        packet.length = len(packet.data)
        
        log.debug(f"Built JoinLobbyResponse: result={self.result}, lobby={self.lobby_steam_id:x}, "
                  f"members={len(self.members)}, data_len={packet.length}")
        
        return packet
    
    def __repr__(self):
        return (
            f"MsgClientJoinLobbyResponse("
            f"result={self.result}, app_id={self.app_id}, "
            f"lobby_steam_id={self.lobby_steam_id:x}, "
            f"members={len(self.members)}"
            f")"
        )