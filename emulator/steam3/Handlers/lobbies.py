import struct
import logging
from steam3.ClientManager.client import Client
from steam3.Types.emsg import EMsg
from steam3.Types.steam_types import EInstanceFlag, EResult, EType
from steam3.Types.chat_types import ChatRoomType, ChatRoomEnterResponse
from steam3.cm_packet_utils import CMPacket, CMResponse
from steam3.messages.MsgClientGetLobbyList import MsgClientGetLobbyList
# Note: Lobbies use existing chat messages with lobby type
# from steam3.messages.MsgClientCreateLobby import MsgClientCreateLobby  # Not needed - uses ClientCreateChat
# from steam3.messages.MsgClientJoinLobby import MsgClientJoinLobby      # Not needed - uses ClientJoinChat
# from steam3.messages.MsgClientLeaveLobby import MsgClientLeaveLobby    # Not needed - implicit in chat leave
from steam3.messages.MsgClientGetLobbyMetadata import MsgClientGetLobbyMetadata
from steam3.messages.responses.MsgClientGetLobbyListResponse_Obsolete import GetLobbyListResponse_obsolete
from steam3.messages.responses.MsgClientCreateLobbyResponse import MsgClientCreateLobbyResponse
from steam3.Responses.lobby_responses import (
    build_GetLobbyListResponse, build_GetLobbyMetadataResponse
)
from steam3.Managers.LobbyManager.lobby_manager import LobbyManager as lobby_manager
from steam3.Managers.ChatroomManager.manager import ChatroomManager

log = logging.getLogger("LobbyHandlers")

def get_chatroom_manager():
    """Get the global chatroom manager instance from steam3"""
    import steam3
    return steam3.chatroom_manager

def get_lobby_manager():
    """Get the global lobby manager instance from steam3"""
    import steam3
    return steam3.lobby_manager
def handle_ClientGetNumberOfCurrentPlayers(cmserver_obj, packet: CMPacket, client_obj: Client):
    """packetid: ClientGetNumberOfCurrentPlayers (5436)
       data (raw): b'\xf4\x01\x00\x00\x00\x00\x00\x00'"""
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received GetNumberOfCurrentPlayers Request")
    appID = struct.unpack_from("<Q", request.data)[0]

    # Count how many users are currently playing this game
    from steam3.ClientManager import Client_Manager
    player_count = 0
    
    # Iterate through all connected clients
    for client in Client_Manager.clients_by_connid.values():
        # Check if client is in app and playing the requested game
        if (hasattr(client, 'is_in_app') and client.is_in_app and 
            hasattr(client, 'appID') and client.appID == appID):
            player_count += 1
    
    cmserver_obj.log.debug(f"Found {player_count} players currently playing appID {appID}")
    
    packet = CMResponse(
        eMsgID    = EMsg.ClientGetNumberOfCurrentPlayersResponse,
        client_obj = client_obj
    )
    # EResult and player count
    packet.data  = struct.pack(
        '<I I',
        EResult.OK,
        player_count
    )
    packet.length = len(packet.data)
    return packet


def handle_ClientGetLobbyList_obsolete(cmserver_obj, packet: CMPacket, client_obj: Client):
    """packetid: ClientGetLobbyList_obsolete (890)
       Handle lobby list request using advanced filtering"""
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received Get Lobby List (Obsolete) Request")
    
    try:
        parser = MsgClientGetLobbyList()
        parser.deserialize(request.data)
        
        cmserver_obj.log.debug(f"LobbySearch: gameId={parser.gameId}, "
                              f"requestedCount={parser.requestedLobbiesCount}, "
                              f"filters={len(parser.filters)}")
        
        # Convert filters to lobby manager format
        filters = []
        max_results = 50  # Default
        
        for lobby_filter in parser.filters:
            from steam3.Types.community_types import LobbyFilterType
            
            if lobby_filter.type == LobbyFilterType.stringCompare:
                filter_dict = {
                    'type': 'string_compare',
                    'key': lobby_filter.key,
                    'value': lobby_filter.value,
                    'operator': _get_sql_operator(lobby_filter.comparison)
                }
                filters.append(filter_dict)
            
            elif lobby_filter.type == LobbyFilterType.numericalCompare:
                filter_dict = {
                    'type': 'numerical_compare',
                    'key': lobby_filter.key,
                    'value': _parse_number(lobby_filter.value),
                    'operator': _get_sql_operator(lobby_filter.comparison)
                }
                filters.append(filter_dict)
            
            elif lobby_filter.type == LobbyFilterType.slotsAvailable:
                filter_dict = {
                    'type': 'slots_available',
                    'value': _parse_number(lobby_filter.value)
                }
                filters.append(filter_dict)
            
            elif lobby_filter.type == LobbyFilterType.maxResults:
                max_results = min(_parse_number(lobby_filter.value), 50)
                
            elif lobby_filter.type == LobbyFilterType.distance:
                # Distance filtering not implemented in emulated server
                cmserver_obj.log.debug(f"Distance filter ignored: {lobby_filter.value}")
            
            elif lobby_filter.type == LobbyFilterType.nearValue:
                # Near value filtering - treat as numerical comparison
                filter_dict = {
                    'type': 'numerical_compare',
                    'key': lobby_filter.key,
                    'value': _parse_number(lobby_filter.value),
                    'operator': '='  # Near value becomes equality check
                }
                filters.append(filter_dict)
        
        # Search lobbies - check both LobbyManager and ChatroomManager
        # Because lobbies created via ClientCreateChat go to ChatroomManager,
        # not LobbyManager (they're chatrooms with room_type=lobby)
        from steam3.Types.keyvaluesystem import KeyValuesSystem, KVS_TYPE_STRING

        packet = GetLobbyListResponse_obsolete(client_obj)
        packet.game_id = parser.gameId  # Set game_id for response

        lobbies_found = []

        # First, search ChatroomManager for lobbies (created via ClientCreateChat)
        chatroom_manager = get_chatroom_manager()
        for chatroom in chatroom_manager.list_chatrooms():
            if chatroom.room_type == ChatRoomType.lobby:
                # Check if game_id matches
                if hasattr(chatroom, 'game_id') and chatroom.game_id == parser.gameId:
                    # Query database for any custom metadata set via SetLobbyData
                    lobby_metadata = {}
                    try:
                        from utilities.database.cmdb import get_cmdb
                        from utilities.database.base_dbdriver import LobbyMetadata

                        cmdb = get_cmdb()
                        db_metadata = cmdb.session.query(LobbyMetadata).filter_by(
                            lobby_steam_id=chatroom.steam_id
                        ).all()
                        for entry in db_metadata:
                            if entry.metadata_key and entry.metadata_value is not None:
                                lobby_metadata[entry.metadata_key] = entry.metadata_value
                    except Exception as db_e:
                        cmserver_obj.log.debug(f"Could not query lobby metadata: {db_e}")

                    lobbies_found.append({
                        'steam_id': chatroom.steam_id,
                        'member_count': len(chatroom.members),
                        'max_members': chatroom.max_members if hasattr(chatroom, 'max_members') else 4,
                        'metadata': lobby_metadata,
                        'source': 'chatroom'
                    })

        # Also check LobbyManager for any directly registered lobbies
        try:
            lobby_manager_instance = get_lobby_manager()
            db_lobbies = lobby_manager_instance.search_lobbies(parser.gameId, filters, max_results)
            for lobby_data in db_lobbies:
                from steam3.Types.steamid import SteamID
                from steam3.Types.steam_types import EUniverse, EType, EInstanceFlag

                steam_id = SteamID()
                steam_id.set_from_identifier(lobby_data['lobby_id'], EUniverse.PUBLIC, EType.CHAT,
                                           EInstanceFlag.LOBBY)
                lobbies_found.append({
                    'steam_id': int(steam_id),
                    'member_count': lobby_data.get('members_count', 0),
                    'max_members': lobby_data.get('max_members', 4),
                    'metadata': lobby_data.get('metadata', {}),
                    'source': 'lobbymanager'
                })
        except Exception as e:
            cmserver_obj.log.debug(f"LobbyManager search error (expected if no db): {e}")

        # Build response with found lobbies (limit to max_results)
        for lobby_data in lobbies_found[:max_results]:
            lobby_steam_id = lobby_data['steam_id']
            packet.lobby_ids.append(lobby_steam_id)

            # Build metadata with KeyValues for proper client parsing
            kvs = KeyValuesSystem()
            metadata_dict = lobby_data.get('metadata', {})
            if metadata_dict:
                for key, value in metadata_dict.items():
                    kvs.root.set_value(key, KVS_TYPE_STRING, str(value))

            packet.metadata[lobby_steam_id] = {
                'members': lobby_data['member_count'],
                'max_members': lobby_data['max_members'],
                'kv': kvs
            }

        cmserver_obj.log.debug(f"Found {len(lobbies_found)} lobbies for gameId {parser.gameId}")
        return packet.to_clientmsg()
        
    except Exception as e:
        cmserver_obj.log.error(f"Error handling ClientGetLobbyList_obsolete: {e}")
        # Return empty list on error
        packet = GetLobbyListResponse_obsolete(client_obj)
        return packet.to_clientmsg()


def _get_sql_operator(comparison):
    """Convert LobbyComparison enum to SQL operator string"""
    from steam3.Types.community_types import LobbyComparison
    
    # Map comparison values to SQL operators
    operator_map = {
        LobbyComparison.equal: '=',
        LobbyComparison.lessThan: '<',
        LobbyComparison.greaterThan: '>',
        LobbyComparison.equalOrLessThan: '<=',
        LobbyComparison.equalOrGreaterThan: '>='
    }
    
    return operator_map.get(comparison, '=')


def _parse_number(value_str):
    """Parse string value as number, return 0 if invalid"""
    try:
        # Try integer first, then float
        if '.' in value_str:
            return float(value_str)
        else:
            return int(value_str)
    except (ValueError, TypeError):
        return 0


# Note: Lobby creation/joining is handled through the existing chat system
# ClientCreateChat with room_type=lobby creates lobbies
# ClientJoinChat is used to join lobbies  
# Lobby leave is handled implicitly when leaving chat


def handle_ClientGetLobbyMetadata(cmserver_obj, packet: CMPacket, client_obj: Client):
    """Handle ClientGetLobbyMetadata request

    Based on 2008 client analysis:
    - Client sends lobby Steam ID to get metadata for
    - Server responds with KeyValues binary metadata
    """
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received ClientGetLobbyMetadata")

    try:
        msg = MsgClientGetLobbyMetadata(client_obj, request.data)

        # Get lobby/chatroom data (lobbies are implemented as special chatrooms)
        chatroom_manager = get_chatroom_manager()
        chatroom = chatroom_manager.get_chatroom(int(msg.lobby_id))

        if chatroom and chatroom.room_type == ChatRoomType.lobby:
            # Get chatroom member info
            member_list = chatroom.get_member_list()

            # Build metadata dict from chatroom properties
            # This includes basic lobby info that the client may query
            metadata = {
                'name': chatroom.name if hasattr(chatroom, 'name') else '',
                'game_id': str(chatroom.game_id) if hasattr(chatroom, 'game_id') else '0',
                'max_members': str(chatroom.max_members) if hasattr(chatroom, 'max_members') else '0',
                'current_members': str(len(member_list)),
                'owner': str(chatroom.owner_id) if hasattr(chatroom, 'owner_id') else '0'
            }

            # Also query database for any custom metadata set via SetLobbyData
            try:
                from utilities.database.cmdb import get_cmdb
                from utilities.database.base_dbdriver import LobbyMetadata

                cmdb = get_cmdb()
                db_metadata = cmdb.session.query(LobbyMetadata).filter_by(
                    lobby_steam_id=int(msg.lobby_id)
                ).all()

                for entry in db_metadata:
                    if entry.metadata_key and entry.metadata_value is not None:
                        metadata[entry.metadata_key] = entry.metadata_value
                        cmserver_obj.log.debug(f"Got lobby metadata from DB: {entry.metadata_key}={entry.metadata_value}")
            except Exception as db_e:
                cmserver_obj.log.warning(f"Could not query lobby metadata from database: {db_e}")

            # Build response with proper KeyValues serialization (handled internally)
            response = build_GetLobbyMetadataResponse(
                client_obj,
                lobby_steam_id=int(msg.lobby_id),
                metadata_dict=metadata,
                members=len(member_list),
                members_max=chatroom.max_members if hasattr(chatroom, 'max_members') else 0
            )
        else:
            # Lobby not found - return empty response
            response = build_GetLobbyMetadataResponse(
                client_obj,
                lobby_steam_id=int(msg.lobby_id),
                metadata_dict={},
                members=0,
                members_max=0
            )

        cmserver_obj.send_client_packet(client_obj, response)

    except Exception as e:
        cmserver_obj.log.error(f"Error handling ClientGetLobbyMetadata: {e}")
        import traceback
        cmserver_obj.log.error(traceback.format_exc())
        # Send empty response on error
        response = build_GetLobbyMetadataResponse(
            client_obj,
            lobby_steam_id=0,
            metadata_dict={},
            members=0,
            members_max=0
        )
        cmserver_obj.send_client_packet(client_obj, response)

    return -1


def handle_ClientCreateLobby(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle ClientCreateLobby packet - Create a new lobby
    
    DEPRECATED: Based on 2008 client analysis, lobbies should be created via ClientCreateChat.
    This handler is for compatibility with newer clients that may use separate lobby messages.
    Early clients (2008) use ClientCreateChat with ChatRoomType.lobby instead.
    """
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received ClientCreateLobby (newer client)")
    
    try:
        # Import here to avoid circular imports
        from steam3.messages.MsgClientCreateLobby import MsgClientCreateLobby
        
        # Parse the lobby creation request
        msg = MsgClientCreateLobby(client_obj, request.data)
        
        cmserver_obj.log.debug(f"CreateLobby (newer): app_id={msg.app_id}, type={msg.lobby_type}, "
                              f"max_members={msg.max_members}, flags={msg.lobby_flags}")
        
        # Create lobby through the chatroom foundation (as 2008 clients do)
        # This ensures consistency across all client versions
        chatroom_manager = get_chatroom_manager()
        
        chat_steam_id = chatroom_manager.register_chatroom(
            owner_id=int(client_obj.steamID),
            room_type=ChatRoomType.lobby,  # This is a lobby
            name=f"Lobby_{int(client_obj.steamID)}",  # Generate default name
            clan_id=0,
            game_id=msg.app_id,
            officer_permission=0,  # Use defaults
            member_permission=0,
            all_permission=0,
            max_members=msg.max_members,
            flags=msg.lobby_flags,
            friend_chat_id=0,
            invited_id=0
        )
        
        if chat_steam_id != 0:
            # Success - create response
            response = MsgClientCreateLobbyResponse(
                client_obj=client_obj,
                result=EResult.OK,
                lobby_steam_id=chat_steam_id,
                app_id=msg.app_id,
                lobby_type=msg.lobby_type,
                max_members=msg.max_members,
                cell_id=msg.cell_id,
                public_ip=msg.public_ip
            )
            cmserver_obj.log.info(f"Created lobby {chat_steam_id:x} for app {msg.app_id} (via chatroom foundation)")
        else:
            # Failed to create lobby
            response = MsgClientCreateLobbyResponse(
                client_obj=client_obj,
                result=EResult.Fail,
                lobby_steam_id=0,
                app_id=msg.app_id,
                lobby_type=msg.lobby_type,
                max_members=msg.max_members,
                cell_id=msg.cell_id,
                public_ip=msg.public_ip
            )
            cmserver_obj.log.warning(f"Failed to create lobby for app {msg.app_id}")
        
        return response.to_clientmsg()
        
    except Exception as e:
        cmserver_obj.log.error(f"Error handling ClientCreateLobby: {e}")
        # Return failure response
        response = MsgClientCreateLobbyResponse(
            client_obj=client_obj,
            result=EResult.Fail,
            lobby_steam_id=0
        )
        return response.to_clientmsg()



def handle_ClientJoinLobby(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle ClientMMSJoinLobby packet - Join an existing lobby
    
    DEPRECATED: Based on 2008 client analysis, lobbies should be joined via ClientJoinChat.
    This handler is for compatibility with newer clients that may use separate lobby messages.
    Early clients (2008) use ClientJoinChat to join lobby chatrooms instead.
    """
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received ClientMMSJoinLobby (newer client)")
    
    try:
        # Import here to avoid circular imports
        from steam3.messages.MsgClientJoinLobby import MsgClientJoinLobby
        from steam3.messages.responses.MsgClientJoinLobbyResponse import MsgClientJoinLobbyResponse
        
        # Parse the lobby join request
        msg = MsgClientJoinLobby(client_obj, request.data)
        
        cmserver_obj.log.debug(f"JoinLobby (newer): lobby_id={int(msg.lobby_id):x}, app_id={msg.app_id}")
        
        # Join lobby through the chatroom foundation (as 2008 clients do)
        # This ensures consistency across all client versions
        chatroom_manager = get_chatroom_manager()
        chatroom = chatroom_manager.get_chatroom(int(msg.lobby_id))
        
        if chatroom and chatroom.room_type == ChatRoomType.lobby:
            # Attempt to join the lobby chatroom
            join_result = chatroom.enter_chatroom(int(client_obj.steamID), voice_speaker=False)
            
            if join_result == ChatRoomEnterResponse.success:
                # Success - build full response with lobby details
                member_list = chatroom.get_member_list()
                members = []
                for member_id in member_list:
                    # Get client for nickname (simplified)
                    members.append({
                        'steam_id': member_id,
                        'persona_name': f"Player_{member_id}",  # Simplified nickname
                        'metadata': b''  # Member-specific metadata (empty for now)
                    })
                
                response = MsgClientJoinLobbyResponse(
                    client_obj=client_obj,
                    result=EResult.OK,
                    app_id=msg.app_id,
                    lobby_steam_id=int(msg.lobby_id),
                    chat_room_enter_response=1,  # Success
                    max_members=chatroom.max_members,
                    lobby_type=0,  # Default lobby type
                    lobby_flags=chatroom.flags,
                    steam_id_owner=chatroom.owner_id,
                    metadata=b'',  # Global lobby metadata (empty for now)
                    members=members
                )
                cmserver_obj.log.info(f"Player {client_obj.steamID} joined lobby {int(msg.lobby_id):x} (via chatroom foundation)")
            else:
                # Failed to join
                response = MsgClientJoinLobbyResponse(
                    client_obj=client_obj,
                    result=EResult.Fail,
                    app_id=msg.app_id,
                    lobby_steam_id=int(msg.lobby_id),
                    chat_room_enter_response=join_result.value,  # Use actual error
                    max_members=0,
                    lobby_type=0,
                    lobby_flags=0,
                    steam_id_owner=0,
                    metadata=b'',
                    members=[]
                )
                cmserver_obj.log.warning(f"Failed to join lobby {int(msg.lobby_id):x} (via chatroom foundation): {join_result}")
        else:
            # Lobby not found
            response = MsgClientJoinLobbyResponse(
                client_obj=client_obj,
                result=EResult.Fail,
                app_id=msg.app_id,
                lobby_steam_id=int(msg.lobby_id),
                chat_room_enter_response=6,  # Error
                max_members=0,
                lobby_type=0,
                lobby_flags=0,
                steam_id_owner=0,
                metadata=b'',
                members=[]
            )
            cmserver_obj.log.warning(f"Lobby {int(msg.lobby_id):x} not found or not a lobby")
        
        return response.to_clientmsg()
        
    except Exception as e:
        cmserver_obj.log.error(f"Error handling ClientMMSJoinLobby: {e}")
        # Return failure response
        from steam3.messages.responses.MsgClientJoinLobbyResponse import MsgClientJoinLobbyResponse
        response = MsgClientJoinLobbyResponse(
            client_obj=client_obj,
            result=EResult.Fail,
            app_id=0,
            lobby_steam_id=0,
            chat_room_enter_response=6,  # Error
            max_members=0,
            lobby_type=0,
            lobby_flags=0,
            steam_id_owner=0
        )
        return response.to_clientmsg()




def handle_LeaveLobby_IClientMatchmaking(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle IClientMatchmaking LeaveLobby (dispatch ID 971) - Leave a lobby
    
    Based on 2008 client analysis, this delegates to chatroom leave functionality  
    since lobbies ARE chatrooms in the underlying implementation.
    
    This is NOT an MMS message - it's an IClientMatchmaking dispatch call.
    """
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received IClientMatchmaking LeaveLobby (dispatch ID 971)")
    
    try:
        # Parse lobby Steam ID from packet data (first 8 bytes)
        lobby_steam_id = struct.unpack_from("<Q", request.data, 0)[0]
        
        cmserver_obj.log.debug(f"LeaveLobby: lobby_id={lobby_steam_id:x}, user={client_obj.steamID}")
        
        # Leave lobby through the chatroom foundation (as 2008 clients expect)
        chatroom_manager = get_chatroom_manager()
        chatroom = chatroom_manager.get_chatroom(lobby_steam_id)
        
        if chatroom and chatroom.room_type == ChatRoomType.lobby:
            # Leave the lobby chatroom
            room_closed, new_owner_id = chatroom.leave_chatroom(int(client_obj.steamID))
            cmserver_obj.log.info(f"Player {client_obj.steamID} left lobby {lobby_steam_id:x}")
            
            # For 2008 IClientMatchmaking calls, there is no response message
            # The client gets notified through chatroom leave notifications
            return -1
            
        else:
            # Lobby not found or not a lobby
            cmserver_obj.log.warning(f"Lobby {lobby_steam_id:x} not found or not a lobby")
            return -1
            
    except Exception as e:
        cmserver_obj.log.error(f"Error handling IClientMatchmaking LeaveLobby: {e}")
        return -1


def handle_GetNumLobbyMembers_IClientMatchmaking(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle IClientMatchmaking GetNumLobbyMembers (dispatch ID 973) - Get lobby member count
    
    Based on 2008 client analysis, this gets the member count from the chatroom
    since lobbies ARE chatrooms in the underlying implementation.
    """
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received IClientMatchmaking GetNumLobbyMembers (dispatch ID 973)")
    
    try:
        # Parse lobby Steam ID from packet data (first 8 bytes)
        lobby_steam_id = struct.unpack_from("<Q", request.data, 0)[0]
        
        cmserver_obj.log.debug(f"GetNumLobbyMembers: lobby_id={lobby_steam_id:x}")
        
        # Get lobby member count through the chatroom foundation
        chatroom_manager = get_chatroom_manager()
        chatroom = chatroom_manager.get_chatroom(lobby_steam_id)
        
        member_count = 0
        if chatroom and chatroom.room_type == ChatRoomType.lobby:
            member_list = chatroom.get_member_list()  # Returns List[ChatMember]
            member_count = len(member_list)
            cmserver_obj.log.debug(f"Lobby {lobby_steam_id:x} has {member_count} members")
        else:
            cmserver_obj.log.warning(f"Lobby {lobby_steam_id:x} not found or not a lobby")
        
        # IClientMatchmaking calls expect the result serialized in bufRet
        # This follows the pattern from the decompiled dispatch function
        packet = CMResponse(
            eMsgID=packet.CMRequest.eMsgID,  # Echo back the original message ID
            client_obj=client_obj
        )
        packet.data = struct.pack('<i', member_count)
        packet.length = len(packet.data)
        return packet
        
    except Exception as e:
        cmserver_obj.log.error(f"Error handling IClientMatchmaking GetNumLobbyMembers: {e}")
        # Return 0 members on error
        packet = CMResponse(
            eMsgID=packet.CMRequest.eMsgID,
            client_obj=client_obj
        )
        packet.data = struct.pack('<i', 0)
        packet.length = len(packet.data)
        return packet


def handle_GetLobbyMemberByIndex_IClientMatchmaking(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle IClientMatchmaking GetLobbyMemberByIndex (dispatch ID 974) - Get lobby member by index
    
    Based on 2008 client analysis, this gets a member's Steam ID from the chatroom
    member list at the specified index.
    """
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received IClientMatchmaking GetLobbyMemberByIndex (dispatch ID 974)")
    
    try:
        # Parse lobby Steam ID (8 bytes) and member index (4 bytes) 
        lobby_steam_id = struct.unpack_from("<Q", request.data, 0)[0]
        member_index = struct.unpack_from("<i", request.data, 8)[0]
        
        cmserver_obj.log.debug(f"GetLobbyMemberByIndex: lobby_id={lobby_steam_id:x}, index={member_index}")
        
        # Get lobby member by index through the chatroom foundation
        chatroom_manager = get_chatroom_manager()
        chatroom = chatroom_manager.get_chatroom(lobby_steam_id)
        
        member_steam_id = 0
        if chatroom and chatroom.room_type == ChatRoomType.lobby:
            member_list = chatroom.get_member_list()  # Returns List[ChatMember]
            if 0 <= member_index < len(member_list):
                member_steam_id = member_list[member_index].steam_id
                cmserver_obj.log.debug(f"Member at index {member_index}: {member_steam_id}")
            else:
                cmserver_obj.log.warning(f"Member index {member_index} out of range for lobby {lobby_steam_id:x}")
        else:
            cmserver_obj.log.warning(f"Lobby {lobby_steam_id:x} not found or not a lobby")
        
        # Return the Steam ID of the member at the requested index
        packet = CMResponse(
            eMsgID=packet.CMRequest.eMsgID,
            client_obj=client_obj
        )
        packet.data = struct.pack('<Q', member_steam_id)
        packet.length = len(packet.data)
        return packet
        
    except Exception as e:
        cmserver_obj.log.error(f"Error handling IClientMatchmaking GetLobbyMemberByIndex: {e}")
        # Return invalid Steam ID on error
        packet = CMResponse(
            eMsgID=packet.CMRequest.eMsgID,
            client_obj=client_obj
        )
        packet.data = struct.pack('<Q', 0)
        packet.length = len(packet.data)
        return packet


def handle_GetLobbyData_IClientMatchmaking(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle IClientMatchmaking GetLobbyData (dispatch ID 975) - Get lobby metadata value
    
    Based on 2008 client analysis, this retrieves a metadata value by key.
    """
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received IClientMatchmaking GetLobbyData (dispatch ID 975)")
    
    try:
        # Parse lobby Steam ID (8 bytes) and key (null-terminated string)
        lobby_steam_id = struct.unpack_from("<Q", request.data, 0)[0]
        
        # Find null terminator for key
        key_start = 8
        key_end = key_start
        while key_end < len(request.data) and request.data[key_end] != 0:
            key_end += 1
        key = request.data[key_start:key_end].decode('utf-8', errors='ignore')
        
        cmserver_obj.log.debug(f"GetLobbyData: lobby_id={lobby_steam_id:x}, key='{key}'")
        
        # Get lobby metadata from database
        from utilities.database.cmdb import get_cmdb
        from utilities.database.base_dbdriver import LobbyMetadata
        
        cmdb = get_cmdb()
        value = ""
        
        try:
            # Query lobby metadata
            metadata_entry = cmdb.session.query(LobbyMetadata).filter_by(
                lobby_steam_id=lobby_steam_id,
                metadata_key=key
            ).first()
            
            if metadata_entry:
                value = metadata_entry.metadata_value or ""
                cmserver_obj.log.debug(f"Found metadata: {key}='{value}'")
            else:
                cmserver_obj.log.debug(f"No metadata found for key '{key}' in lobby {lobby_steam_id:x}")
                
        except Exception as db_e:
            cmserver_obj.log.error(f"Database error retrieving lobby metadata: {db_e}")
        
        # Return the metadata value as a null-terminated string
        packet = CMResponse(
            eMsgID=packet.CMRequest.eMsgID,
            client_obj=client_obj
        )
        packet.data = value.encode('utf-8') + b'\x00'
        packet.length = len(packet.data)
        return packet
        
    except Exception as e:
        cmserver_obj.log.error(f"Error handling IClientMatchmaking GetLobbyData: {e}")
        # Return empty string on error
        packet = CMResponse(
            eMsgID=packet.CMRequest.eMsgID,
            client_obj=client_obj
        )
        packet.data = b'\x00'  # Empty null-terminated string
        packet.length = 1
        return packet


def handle_SetLobbyData_IClientMatchmaking(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle IClientMatchmaking SetLobbyData (dispatch ID 976) - Set lobby metadata
    
    Based on 2008 client analysis, this sets a metadata key-value pair.
    Returns boolean success/failure.
    """
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received IClientMatchmaking SetLobbyData (dispatch ID 976)")
    
    try:
        # Parse lobby Steam ID (8 bytes), key and value (null-terminated strings)
        lobby_steam_id = struct.unpack_from("<Q", request.data, 0)[0]
        
        # Parse key string
        key_start = 8
        key_end = key_start
        while key_end < len(request.data) and request.data[key_end] != 0:
            key_end += 1
        key = request.data[key_start:key_end].decode('utf-8', errors='ignore')
        
        # Parse value string
        value_start = key_end + 1  # Skip null terminator
        value_end = value_start
        while value_end < len(request.data) and request.data[value_end] != 0:
            value_end += 1
        value = request.data[value_start:value_end].decode('utf-8', errors='ignore')
        
        cmserver_obj.log.debug(f"SetLobbyData: lobby_id={lobby_steam_id:x}, key='{key}', value='{value}'")
        
        # Verify the player is authorized to set lobby data
        chatroom_manager = get_chatroom_manager()
        chatroom = chatroom_manager.get_chatroom(lobby_steam_id)
        
        success = False
        
        if not chatroom or chatroom.room_type != ChatRoomType.lobby:
            cmserver_obj.log.warning(f"Lobby {lobby_steam_id:x} not found or not a lobby")
        else:
            # Check if user is lobby member (simplified authorization)
            member_list = chatroom.get_member_list()  # Returns List[ChatMember]
            member_steam_ids = {member.steam_id for member in member_list}
            if int(client_obj.steamID) not in member_steam_ids:
                cmserver_obj.log.warning(f"Player {client_obj.steamID} not authorized to set data for lobby {lobby_steam_id:x}")
            else:
                # Store metadata in database
                from utilities.database.cmdb import get_cmdb
                from utilities.database.base_dbdriver import LobbyMetadata
                from sqlalchemy.exc import SQLAlchemyError
                
                cmdb = get_cmdb()
                
                try:
                    # Insert or update metadata entry
                    existing_entry = cmdb.session.query(LobbyMetadata).filter_by(
                        lobby_steam_id=lobby_steam_id,
                        metadata_key=key
                    ).first()
                    
                    if existing_entry:
                        # Update existing
                        existing_entry.metadata_value = value
                    else:
                        # Create new entry
                        new_entry = LobbyMetadata(
                            lobby_steam_id=lobby_steam_id,
                            metadata_key=key,
                            metadata_value=value
                        )
                        cmdb.session.add(new_entry)
                    
                    cmdb.session.commit()
                    success = True
                    cmserver_obj.log.info(f"Set lobby metadata for {lobby_steam_id:x}: {key}='{value}'")
                    
                except SQLAlchemyError as exc:
                    cmdb.session.rollback()
                    cmserver_obj.log.error(f"Database error setting lobby metadata: {exc}")
        
        # Return boolean success result
        packet = CMResponse(
            eMsgID=packet.CMRequest.eMsgID,
            client_obj=client_obj
        )
        packet.data = struct.pack('<B', 1 if success else 0)  # Boolean as byte
        packet.length = len(packet.data)
        return packet
        
    except Exception as e:
        cmserver_obj.log.error(f"Error handling IClientMatchmaking SetLobbyData: {e}")
        # Return failure on error
        packet = CMResponse(
            eMsgID=packet.CMRequest.eMsgID,
            client_obj=client_obj
        )
        packet.data = struct.pack('<B', 0)  # False
        packet.length = 1
        return packet


