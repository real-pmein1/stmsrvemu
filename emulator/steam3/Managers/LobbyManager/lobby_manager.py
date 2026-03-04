"""
Lobby Manager - Comprehensive lobby management matching C++ Steam API functionality
Implements advanced lobby search, metadata management, and lifecycle operations
"""

import logging
import threading
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from enum import IntEnum

from steam3.Types.steamid import SteamID
from steam3.Types.steam_types import EResult, EType, EInstanceFlag, EUniverse
from steam3.Types.chat_types import (
    ChatRoomType, ChatPermission, ChatRoomFlags, ChatAction, ChatActionResult,
    ChatRoomEnterResponse, ChatEntryType, ChatRelationship
)
# Remove import - will use database passed from steam3

log = logging.getLogger("LobbyManager")


class LobbyType(IntEnum):
    """Lobby types matching C++ enum"""
    private = 0          # Friends only
    friendsOnly = 1      # Friends only (same as private)
    public = 2           # Public lobby
    invisible = 3        # Invisible to friends


class LobbyFilter(IntEnum):
    """Lobby filter types for advanced search"""
    stringCompare = 0
    numericalCompare = 1
    nearValue = 2
    distance = 3
    slotsAvailable = 4
    maxResults = 5


class LobbyComparison(IntEnum):
    """Comparison operators for lobby filtering"""
    equal = -2
    notEqual = -1
    lessThan = -5
    lessThanOrEqual = -4
    greaterThan = -3
    greaterThanOrEqual = -6


class LobbyMember:
    """Represents a lobby member"""
    
    def __init__(self, steam_id: int, nickname: str = "", relationship: ChatRelationship = ChatRelationship.member):
        self.steam_id = steam_id
        self.nickname = nickname
        self.relationship = relationship
        self.joined_at = datetime.now()


class Lobby:
    """
    Represents a lobby, matching C++ CommunityLobby functionality.
    
    DEPRECATED APPROACH: Based on 2008 client analysis, lobbies should be implemented
    as chatrooms with ChatRoomType.lobby instead of separate objects.
    
    This class is maintained for compatibility with newer clients but delegates
    to the chatroom foundation for actual functionality.
    """
    
    def __init__(self, lobby_id: int, app_id: int, owner_id: int, lobby_type: LobbyType,
                 flags: int = 0, cell_id: int = 0, public_ip: int = 0, max_members: int = 4,
                 persistent: bool = True, chatroom_manager=None):
        self.lobby_id = lobby_id
        self.steam_id = self._generate_steam_id(lobby_id)
        self.app_id = app_id
        self.owner_id = owner_id
        self.lobby_type = lobby_type
        self.flags = flags
        self.cell_id = cell_id
        self.public_ip = public_ip
        self.max_members = max_members
        self.persistent = persistent
        self.created_at = datetime.now()
        self.chatroom_manager = chatroom_manager
        
        # For 2008 client compatibility: create underlying chatroom
        self._underlying_chatroom = None
        if self.chatroom_manager:
            self._create_underlying_chatroom()
        
        # Metadata: key -> value (global lobby metadata)
        self.metadata: Dict[str, str] = {}
        
        # Per-member metadata: steam_id -> {key -> value}
        self.member_metadata: Dict[int, Dict[str, str]] = {}
        
        # Thread safety
        self.lock = threading.RLock()
    
    def _generate_steam_id(self, lobby_id: int) -> int:
        """Generate Steam ID for lobby (matches chatroom Steam ID generation)"""
        steam_id = SteamID()
        steam_id.set_from_identifier(lobby_id, EUniverse.PUBLIC, EType.Chat, 
                                   EInstanceFlag.MMSLobby)  # Use proper lobby instance flag
        return int(steam_id)
    
    def _create_underlying_chatroom(self):
        """Create the underlying chatroom that powers this lobby"""
        try:
            chat_steam_id = self.chatroom_manager.register_chatroom(
                owner_id=self.owner_id,
                room_type=ChatRoomType.lobby,
                name=f"Lobby_{self.lobby_id}",
                clan_id=0,
                game_id=self.app_id,
                officer_permission=0,
                member_permission=0,
                all_permission=0,
                max_members=self.max_members,
                flags=self.flags,
                friend_chat_id=0,
                invited_id=0
            )
            
            if chat_steam_id != 0:
                self._underlying_chatroom = self.chatroom_manager.get_chatroom(chat_steam_id)
                # Ensure Steam IDs match
                self.steam_id = chat_steam_id
                log.debug(f"Created underlying chatroom {chat_steam_id:x} for lobby {self.lobby_id}")
            else:
                log.error(f"Failed to create underlying chatroom for lobby {self.lobby_id}")
                
        except Exception as e:
            log.error(f"Error creating underlying chatroom for lobby {self.lobby_id}: {e}")
    
    @property 
    def members(self):
        """Delegate to underlying chatroom for member management"""
        if self._underlying_chatroom:
            return self._underlying_chatroom.members
        return {}
    
    def get_member_list(self):
        """Get list of lobby members (delegate to chatroom)"""
        if self._underlying_chatroom:
            return self._underlying_chatroom.get_member_list()
        return []
    
    def join_lobby(self, player_id: int, nickname: str = "") -> ChatRoomEnterResponse:
        """Handle player joining lobby"""
        with self.lock:
            # Check if lobby is full
            if len(self.members) >= self.max_members:
                return ChatRoomEnterResponse.full
            
            # Check permissions
            if self.flags & ChatRoomFlags.unjoinable:
                return ChatRoomEnterResponse.notAllowed
            
            # Check lobby type restrictions
            if self.lobby_type == LobbyType.private or self.lobby_type == LobbyType.friendsOnly:
                # For private lobbies, player must be invited
                if player_id not in self.members or self.members[player_id].relationship != ChatRelationship.invited:
                    return ChatRoomEnterResponse.notAllowed
            
            # Add or update member
            member = LobbyMember(player_id, nickname, ChatRelationship.member)
            self.members[player_id] = member
            
            # Initialize member metadata
            if player_id not in self.member_metadata:
                self.member_metadata[player_id] = {}
            
            log.debug(f"Player {player_id} joined lobby {self.lobby_id}")
            return ChatRoomEnterResponse.success
    
    def leave_lobby(self, player_id: int) -> Tuple[bool, Optional[int]]:
        """
        Handle player leaving lobby
        Returns (lobby_closed, new_owner_id)
        """
        with self.lock:
            if player_id not in self.members:
                return False, None
            
            # Remove member and their metadata
            del self.members[player_id]
            if player_id in self.member_metadata:
                del self.member_metadata[player_id]
            
            # Check if owner left
            if player_id == self.owner_id:
                if self.members:
                    # Transfer ownership to first remaining member
                    new_owner = next(iter(self.members.keys()))
                    self.owner_id = new_owner
                    return False, new_owner
                else:
                    # No members left, close lobby
                    return True, None
            
            return False, None
    
    def set_metadata(self, key: str, value: str, player_id: int = 0):
        """Set lobby or member metadata"""
        with self.lock:
            if player_id == 0:
                # Global lobby metadata
                self.metadata[key] = value
            else:
                # Per-member metadata
                if player_id not in self.member_metadata:
                    self.member_metadata[player_id] = {}
                self.member_metadata[player_id][key] = value
    
    def get_metadata(self, key: str, player_id: int = 0) -> Optional[str]:
        """Get lobby or member metadata"""
        with self.lock:
            if player_id == 0:
                return self.metadata.get(key)
            else:
                return self.member_metadata.get(player_id, {}).get(key)
    
    def get_all_metadata(self, player_id: int = 0) -> Dict[str, str]:
        """Get all metadata for lobby or member"""
        with self.lock:
            if player_id == 0:
                return self.metadata.copy()
            else:
                return self.member_metadata.get(player_id, {}).copy()
    
    def get_member_list(self) -> List[LobbyMember]:
        """Get list of current members"""
        with self.lock:
            return list(self.members.values())


class LobbyManager:
    """
    Manages lobbies, matching C++ CommunityLobby functionality
    Implements advanced search, filtering, and lifecycle management
    """
    
    def __init__(self, database=None):
        self.lobbies: Dict[int, Lobby] = {}  # lobby_id -> Lobby
        self.next_lobby_id = 2000000  # Start high to avoid conflicts
        self.lock = threading.RLock()
        self.database = database
    
    def register_lobby(self, app_id: int, owner_id: int, owner_nickname: str,
                      lobby_type: LobbyType, flags: int = 0, cell_id: int = 0,
                      public_ip: int = 0, max_members: int = 4,
                      metadata: Optional[Dict[str, str]] = None, 
                      persistent: bool = True) -> int:
        """
        Register a new lobby - matches C++ registerLobby functionality
        Returns lobby Steam ID or 0 on failure
        """
        with self.lock:
            try:
                # Generate lobby ID
                lobby_id = self.next_lobby_id
                self.next_lobby_id += 1
                
                # Ensure flags are consistent with lobby type
                flags = self._ensure_flags(lobby_type, flags)
                
                # Create lobby
                lobby = Lobby(lobby_id, app_id, owner_id, lobby_type, flags, 
                            cell_id, public_ip, max_members, persistent)
                
                # Add initial metadata
                if metadata:
                    for key, value in metadata.items():
                        lobby.set_metadata(key, value)
                
                # Store in memory
                self.lobbies[lobby_id] = lobby
                
                # Only persist to database if lobby is persistent (named lobbies)
                db_lobby_id = 0
                if persistent:
                    # Persist to database - lobby registry AND chatroom registry for dual compatibility
                    db_lobby_id = self.database.register_lobby(
                        app_id, owner_id, int(lobby_type), flags, cell_id, public_ip, max_members
                    )
                    
                    # Also register as chatroom for compatibility with chat system
                    chatroom_name = f"Lobby_{lobby_id}"
                    chatroom_steam_id = self.database.register_chatroom(
                        owner_id=owner_id,
                        room_type=ChatRoomType.lobby,
                        name=chatroom_name,
                        clan_id=0,
                        game_id=app_id,
                        max_members=max_members,
                        flags=flags
                    )
                    
                    if db_lobby_id == 0:
                        log.warning(f"Failed to persist lobby {lobby_id} to database")
                else:
                    log.debug(f"Created temporary lobby {lobby_id} - not persisted to database")
                
                # Do NOT auto-join owner - let client send separate JoinLobby request
                # This matches the Steam client's expected sequence:
                # 1. CreateLobby -> CreateLobbyResponse (creation only)  
                # 2. JoinLobby -> JoinLobbyResponse (separate explicit join)
                
                # Persist initial metadata only for persistent lobbies
                if metadata and persistent:
                    for key, value in metadata.items():
                        self.database.set_lobby_metadata(lobby_id, 0, key, value)
                
                if persistent:
                    log.info(f"Created persistent lobby {lobby_id} for app {app_id} (owner={owner_id}) with dual chatroom registration")
                else:
                    log.info(f"Created temporary lobby {lobby_id} for app {app_id} (owner={owner_id})")
                return lobby.steam_id
                
            except Exception as e:
                log.error(f"Failed to create lobby: {e}")
                return 0
    
    def _ensure_flags(self, lobby_type: LobbyType, flags: int) -> int:
        """Ensure flags are consistent with lobby type - matches C++ logic"""
        if lobby_type == LobbyType.friendsOnly:
            flags |= ChatRoomFlags.locked
        elif lobby_type == LobbyType.invisible:
            flags |= ChatRoomFlags.invisibleToFriends
        return flags
    
    def get_lobby(self, lobby_steam_id: int) -> Optional[Lobby]:
        """Get lobby by Steam ID"""
        # Extract lobby ID from Steam ID
        steam_id_obj = SteamID.from_raw(lobby_steam_id)
        lobby_id = steam_id_obj.get_accountID()
        
        with self.lock:
            return self.lobbies.get(lobby_id)
    
    def join_lobby(self, lobby_steam_id: int, player_id: int, nickname: str = "") -> ChatRoomEnterResponse:
        """Join a lobby"""
        lobby = self.get_lobby(lobby_steam_id)
        if not lobby:
            return ChatRoomEnterResponse.doesntExist
        
        # Attempt to join
        result = lobby.join_lobby(player_id, nickname)
        
        # Persist to database if successful
        if result == ChatRoomEnterResponse.success:
            lobby_id = SteamID.from_raw(lobby_steam_id).get_accountID()
            self.database.set_lobby_membership(lobby_id, player_id, ChatRelationship.member)
        
        return result
    
    def leave_lobby(self, lobby_steam_id: int, player_id: int) -> Tuple[bool, Optional[int]]:
        """Leave a lobby"""
        lobby = self.get_lobby(lobby_steam_id)
        if not lobby:
            return False, None
        
        # Leave lobby
        lobby_closed, new_owner = lobby.leave_lobby(player_id)
        
        # Update database
        lobby_id = SteamID.from_raw(lobby_steam_id).get_accountID()
        
        if lobby_closed:
            # Remove lobby entirely
            with self.lock:
                if lobby_id in self.lobbies:
                    # Only delete from database if lobby was persistent
                    if lobby.persistent:
                        self.database.delete_lobby(lobby_id)
                    else:
                        log.debug(f"Temporary lobby {lobby_id} closed - not deleting from database")
                    del self.lobbies[lobby_id]
        else:
            # Update membership in database only for persistent lobbies
            if lobby.persistent:
                self.database.set_lobby_membership(lobby_id, player_id, ChatRelationship.none)
        
        return lobby_closed, new_owner
    
    def search_lobbies(self, app_id: int, filters: List[Dict], max_results: int = 50) -> List[Dict]:
        """
        Advanced lobby search with filtering - matches C++ _searchLobbies functionality
        
        Filter format: {
            'type': LobbyFilter,
            'key': str (for metadata filters),
            'value': Any,
            'operator': str (for comparison filters)
        }
        """
        # Use database for efficient searching
        db_results = self.database.search_lobbies(app_id, filters, max_results)
        
        # Enrich with in-memory data
        results = []
        for lobby_data in db_results:
            lobby_id = lobby_data['lobby_id']
            lobby = self.lobbies.get(lobby_id)
            
            if lobby:
                # Add current member count
                lobby_data['members_count'] = len(lobby.members)
                lobby_data['available_slots'] = lobby.max_members - len(lobby.members)
                
                # Add metadata if requested
                lobby_data['metadata'] = lobby.get_all_metadata()
            
            results.append(lobby_data)
        
        return results
    
    def set_lobby_metadata(self, lobby_steam_id: int, key: str, value: str, player_id: int = 0) -> bool:
        """Set lobby or member metadata"""
        lobby = self.get_lobby(lobby_steam_id)
        if not lobby:
            return False
        
        # Update in memory
        lobby.set_metadata(key, value, player_id)
        
        # Persist to database
        lobby_id = SteamID.from_raw(lobby_steam_id).get_accountID()
        return self.database.set_lobby_metadata(lobby_id, player_id, key, value)
    
    def get_lobby_metadata(self, lobby_steam_id: int, key: str = None, player_id: int = 0) -> Dict[str, str]:
        """Get lobby or member metadata"""
        lobby = self.get_lobby(lobby_steam_id)
        if not lobby:
            return {}
        
        if key:
            value = lobby.get_metadata(key, player_id)
            return {key: value} if value is not None else {}
        else:
            return lobby.get_all_metadata(player_id)
    
    def get_lobby_members(self, lobby_steam_id: int) -> List[Dict]:
        """Get lobby member list"""
        lobby = self.get_lobby(lobby_steam_id)
        if not lobby:
            return []
        
        members = []
        for member in lobby.get_member_list():
            member_data = {
                'steam_id': member.steam_id,
                'nickname': member.nickname,
                'relationship': int(member.relationship),
                'joined_at': member.joined_at.isoformat()
            }
            members.append(member_data)
        
        return members
    
    def delete_lobby(self, lobby_steam_id: int) -> bool:
        """Delete lobby"""
        lobby_id = SteamID.from_raw(lobby_steam_id).get_accountID()
        
        with self.lock:
            if lobby_id in self.lobbies:
                del self.lobbies[lobby_id]
        
        return self.database.delete_lobby(lobby_id)
    
    def get_lobbies_for_app(self, app_id: int, limit: int = 100) -> List[Dict]:
        """Get all lobbies for an application"""
        db_results = self.database.get_lobbies_by_app(app_id, limit)
        
        results = []
        for lobby_data in db_results:
            lobby_id = lobby_data['lobby_id']
            lobby = self.lobbies.get(lobby_id)
            
            if lobby:
                lobby_data['members_count'] = len(lobby.members)
                lobby_data['available_slots'] = lobby.max_members - len(lobby.members)
            
            results.append(lobby_data)
        
        return results
    
    def cleanup_expired_lobbies(self, max_age_hours: int = 24):
        """Clean up old empty lobbies"""
        current_time = datetime.now()
        expired_lobbies = []
        
        with self.lock:
            for lobby_id, lobby in self.lobbies.items():
                if len(lobby.members) == 0:
                    age = current_time - lobby.created_at
                    if age.total_seconds() > max_age_hours * 3600:
                        expired_lobbies.append(lobby_id)
        
        for lobby_id in expired_lobbies:
            self.delete_lobby(lobby.steam_id)
            log.info(f"Cleaned up expired lobby {lobby_id}")


# Global instance will be created in steam3.__init__.py