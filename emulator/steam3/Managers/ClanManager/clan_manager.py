"""
Clan Manager - Comprehensive clan management matching C++ Steam API functionality
Implements clan creation, member management, permissions, events, and modern chat groups
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

log = logging.getLogger("ClanManager")


class ClanRank(IntEnum):
    """Clan rank hierarchy matching C++ enum"""
    none = 0x00
    owner = 0x01
    officer = 0x02
    member = 0x03
    moderator = 0x04


class ClanPermission(IntEnum):
    """Clan permission levels matching C++ enum"""
    nobody = 0
    owner = 1
    officer = 2
    ownerAndOfficer = 3
    member = 4
    allMembers = 7


class EventType(IntEnum):
    """Clan event types matching C++ enum"""
    chatEvent = 0
    gameEvent = 1
    otherEvent = 2
    partyEvent = 3
    meetingEvent = 4
    specialCauseEvent = 5
    musicAndArtsEvent = 6
    sportsEvent = 7
    tripEvent = 8


class ClanMember:
    """Represents a clan member"""
    
    def __init__(self, steam_id: int, relationship: ChatRelationship, rank: ClanRank):
        self.steam_id = steam_id
        self.relationship = relationship
        self.rank = rank
        self.joined_at = datetime.now()
    
    def get_permission_level(self) -> ClanPermission:
        """Get permission level based on rank"""
        if self.rank == ClanRank.owner:
            return ClanPermission.allMembers  # Owner has all permissions
        elif self.rank == ClanRank.officer or self.rank == ClanRank.moderator:
            return ClanPermission.ownerAndOfficer
        elif self.rank == ClanRank.member:
            return ClanPermission.member
        else:
            return ClanPermission.nobody


class ClanEvent:
    """Represents a clan event or announcement"""
    
    def __init__(self, event_id: int, clan_id: int, name: str, event_type: EventType,
                 start_time: datetime = None, description: str = "", game_id: int = 0,
                 game_server: str = "", game_server_pass: str = "", is_announcement: bool = False):
        self.event_id = event_id
        self.clan_id = clan_id
        self.name = name
        self.event_type = event_type
        self.start_time = start_time or datetime.now()
        self.description = description
        self.game_id = game_id
        self.game_server = game_server
        self.game_server_pass = game_server_pass
        self.is_announcement = is_announcement
        self.created_at = datetime.now()
        
        # Event attendance tracking
        self.attendance: Dict[int, int] = {}  # steam_id -> attendance_status


class Clan:
    """
    Represents a clan, matching C++ CommunityClan functionality
    """
    
    def __init__(self, clan_id: int, name: str, tag: str, owner_id: int, is_public: bool = True):
        self.clan_id = clan_id
        self.steam_id = self._generate_steam_id(clan_id)
        self.name = name
        self.tag = tag
        self.owner_id = owner_id
        self.is_public = is_public
        self.player_of_the_week_id = 0
        self.created_at = datetime.now()
        
        # Permission settings (default to public clan permissions)
        self.permission_edit_profile = ClanPermission.allMembers
        self.permission_make_officer = ClanPermission.owner
        self.permission_add_event = ClanPermission.ownerAndOfficer
        self.permission_choose_potw = ClanPermission.ownerAndOfficer
        self.permission_invite_member = ClanPermission.allMembers
        self.permission_kick_member = ClanPermission.ownerAndOfficer
        
        # Members: steam_id -> ClanMember
        self.members: Dict[int, ClanMember] = {}
        
        # Events: event_id -> ClanEvent
        self.events: Dict[int, ClanEvent] = {}
        self.next_event_id = 1
        
        # Thread safety
        self.lock = threading.RLock()
    
    def _generate_steam_id(self, clan_id: int) -> int:
        """Generate Steam ID for clan"""
        steam_id = SteamID()
        steam_id.set_from_identifier(clan_id, EUniverse.PUBLIC, EType.CLAN, EInstanceFlag.ALL)
        return int(steam_id)
    
    def add_member(self, player_id: int, relationship: ChatRelationship, 
                   rank: ClanRank = ClanRank.member) -> bool:
        """Add member to clan"""
        with self.lock:
            if player_id in self.members:
                # Update existing member
                member = self.members[player_id]
                member.relationship = relationship
                member.rank = rank
            else:
                # Add new member
                member = ClanMember(player_id, relationship, rank)
                self.members[player_id] = member
            
            log.debug(f"Added member {player_id} to clan {self.clan_id} (rank={rank})")
            return True
    
    def remove_member(self, player_id: int) -> Tuple[bool, Optional[int]]:
        """
        Remove member from clan
        Returns (clan_closed, new_owner_id)
        """
        with self.lock:
            if player_id not in self.members:
                return False, None
            
            member = self.members[player_id]
            del self.members[player_id]
            
            # Reset Player of the Week if needed
            if self.player_of_the_week_id == player_id:
                self.player_of_the_week_id = 0
            
            # Check if owner left
            if member.rank == ClanRank.owner:
                if self.members:
                    # Try to find a new owner (prioritize officers, then members)
                    new_owner = self._find_potential_new_owner()
                    if new_owner:
                        self.members[new_owner].rank = ClanRank.owner
                        self.owner_id = new_owner
                        return False, new_owner
                    else:
                        # No suitable replacement, clan will be deleted
                        return True, None
                else:
                    # No members left, close clan
                    return True, None
            
            return False, None
    
    def _find_potential_new_owner(self) -> Optional[int]:
        """Find potential new owner - prioritize officers, then members"""
        # First try officers
        for steam_id, member in self.members.items():
            if member.rank == ClanRank.officer and member.relationship == ChatRelationship.member:
                return steam_id
        
        # Then try regular members
        for steam_id, member in self.members.items():
            if member.rank == ClanRank.member and member.relationship == ChatRelationship.member:
                return steam_id
        
        return None
    
    def get_member_permission_level(self, player_id: int) -> ClanPermission:
        """Get player's permission level in clan"""
        with self.lock:
            member = self.members.get(player_id)
            if not member or member.relationship != ChatRelationship.member:
                return ClanPermission.nobody
            
            return member.get_permission_level()
    
    def is_allowed(self, player_id: int, permission_type: str) -> bool:
        """Check if player is allowed to perform action"""
        player_permission_level = self.get_member_permission_level(player_id)
        required_permission = getattr(self, f"permission_{permission_type}", ClanPermission.nobody)
        
        return (required_permission & player_permission_level) != 0
    
    def invite_member(self, inviter_id: int, invitee_id: int) -> EResult:
        """Invite player to clan"""
        with self.lock:
            if not self.is_allowed(inviter_id, "invite_member"):
                return EResult.AccessDenied
            
            # Check if player is already a member or invited
            existing = self.members.get(invitee_id)
            if existing and existing.relationship in (ChatRelationship.member, ChatRelationship.invited):
                return EResult.InvalidState
            
            # For public clans, anyone can join. For private clans, invitation is required
            if self.is_public:
                # Public clan - add as member directly
                self.add_member(invitee_id, ChatRelationship.member, ClanRank.member)
            else:
                # Private clan - add as invited
                self.add_member(invitee_id, ChatRelationship.invited, ClanRank.none)
            
            return EResult.OK
    
    def join_clan(self, player_id: int) -> EResult:
        """Handle player joining clan"""
        with self.lock:
            existing = self.members.get(player_id)
            
            if self.is_public:
                # Public clan - anyone can join
                if existing and existing.relationship == ChatRelationship.member:
                    return EResult.InvalidState  # Already a member
                
                self.add_member(player_id, ChatRelationship.member, ClanRank.member)
                return EResult.OK
            else:
                # Private clan - must be invited
                if not existing or existing.relationship != ChatRelationship.invited:
                    return EResult.AccessDenied
                
                # Promote from invited to member
                existing.relationship = ChatRelationship.member
                existing.rank = ClanRank.member
                return EResult.OK
    
    def kick_member(self, kicker_id: int, kicked_id: int) -> EResult:
        """Kick member from clan"""
        with self.lock:
            if not self.is_allowed(kicker_id, "kick_member"):
                return EResult.AccessDenied
            
            kicked_member = self.members.get(kicked_id)
            if not kicked_member:
                return EResult.InvalidState
            
            # Cannot kick owner or self
            if kicked_member.rank == ClanRank.owner or kicked_id == kicker_id:
                return EResult.AccessDenied
            
            # For public clans, kick is not allowed
            if self.is_public:
                return EResult.AccessDenied
            
            # Set as kicked
            kicked_member.relationship = ChatRelationship.kicked
            kicked_member.rank = ClanRank.none
            
            return EResult.OK
    
    def change_member_rank(self, changer_id: int, target_id: int, new_rank: ClanRank) -> EResult:
        """Change member rank"""
        with self.lock:
            if not self.is_allowed(changer_id, "make_officer"):
                return EResult.AccessDenied
            
            target_member = self.members.get(target_id)
            if not target_member or target_member.relationship != ChatRelationship.member:
                return EResult.InvalidState
            
            # Cannot change owner rank or promote to owner
            if target_member.rank == ClanRank.owner or new_rank == ClanRank.owner:
                return EResult.AccessDenied
            
            target_member.rank = new_rank
            return EResult.OK
    
    def create_event(self, creator_id: int, name: str, event_type: EventType,
                    start_time: datetime = None, description: str = "",
                    game_id: int = 0, game_server: str = "", game_server_pass: str = "",
                    is_announcement: bool = False) -> Optional[int]:
        """Create clan event or announcement"""
        with self.lock:
            if not self.is_allowed(creator_id, "add_event"):
                return None
            
            event_id = self.next_event_id
            self.next_event_id += 1
            
            event = ClanEvent(
                event_id, self.clan_id, name, event_type, start_time,
                description, game_id, game_server, game_server_pass, is_announcement
            )
            
            self.events[event_id] = event
            return event_id
    
    def set_player_of_the_week(self, setter_id: int, player_id: int) -> EResult:
        """Set player of the week"""
        with self.lock:
            if not self.is_allowed(setter_id, "choose_potw"):
                return EResult.AccessDenied
            
            # Verify target is a clan member
            if player_id != 0 and (player_id not in self.members or 
                                 self.members[player_id].relationship != ChatRelationship.member):
                return EResult.InvalidState
            
            self.player_of_the_week_id = player_id
            return EResult.OK
    
    def get_member_list(self) -> List[ClanMember]:
        """Get list of clan members"""
        with self.lock:
            return [member for member in self.members.values() 
                   if member.relationship == ChatRelationship.member]
    
    def get_member_count(self) -> int:
        """Get count of active clan members"""
        return len(self.get_member_list())
    
    def is_large_clan(self) -> bool:
        """Check if this is a large clan (>50 members)"""
        return self.get_member_count() > 50


class ClanManager:
    """
    Manages clans, matching C++ CommunityClan functionality
    Implements clan creation, member management, permissions, and events
    """
    
    def __init__(self, database=None):
        self.clans: Dict[int, Clan] = {}  # clan_id -> Clan
        self.next_clan_id = 3000000  # Start high to avoid conflicts
        self.lock = threading.RLock()
        self.database = database
    
    def register_clan(self, owner_id: int, name: str, tag: str, is_public: bool = True,
                     template_name: str = 'public_clan') -> int:
        """
        Register a new clan - matches C++ registerClan functionality
        Returns clan Steam ID or 0 on failure
        """
        with self.lock:
            try:
                # Validate name and tag
                if not self._is_valid_clan_name(name):
                    log.warning(f"Invalid clan name: '{name}'")
                    return 0
                
                if not self._is_valid_clan_tag(tag):
                    log.warning(f"Invalid clan tag: '{tag}'")
                    return 0
                
                # Check availability
                if not self.database._is_clan_name_available(name):
                    log.warning(f"Clan name '{name}' not available")
                    return 0
                
                if not self.database._is_clan_tag_available(tag):
                    log.warning(f"Clan tag '{tag}' not available")
                    return 0
                
                # Generate clan ID
                clan_id = self.next_clan_id
                self.next_clan_id += 1
                
                # Create clan
                clan = Clan(clan_id, name, tag, owner_id, is_public)
                
                # Set permissions based on template
                if not is_public:
                    template_name = 'private_clan'
                self._apply_permission_template(clan, template_name)
                
                # Add owner as first member
                clan.add_member(owner_id, ChatRelationship.member, ClanRank.owner)
                
                # Store in memory
                self.clans[clan_id] = clan
                
                # Persist to database
                db_clan_id = self.database.register_clan(owner_id, name, tag, is_public, template_name)
                
                if db_clan_id == 0:
                    log.warning(f"Failed to persist clan {clan_id} to database")
                
                log.info(f"Created clan {clan_id}: '{name}' ['{tag}'] (owner={owner_id})")
                return clan.steam_id
                
            except Exception as e:
                log.error(f"Failed to create clan: {e}")
                return 0
    
    def _is_valid_clan_name(self, name: str) -> bool:
        """Validate clan name"""
        return 1 <= len(name) <= 64 and name.strip() == name
    
    def _is_valid_clan_tag(self, tag: str) -> bool:
        """Validate clan tag - matches C++ isClanTagValid"""
        return 1 <= len(tag) <= 8 and tag.strip() == tag
    
    def _apply_permission_template(self, clan: Clan, template_name: str):
        """Apply permission template to clan"""
        if template_name == 'private_clan':
            clan.permission_edit_profile = ClanPermission.ownerAndOfficer
            clan.permission_make_officer = ClanPermission.owner
            clan.permission_add_event = ClanPermission.ownerAndOfficer
            clan.permission_choose_potw = ClanPermission.owner
            clan.permission_invite_member = ClanPermission.ownerAndOfficer
            clan.permission_kick_member = ClanPermission.ownerAndOfficer
        # Public clan permissions are already set as defaults
    
    def get_clan(self, clan_steam_id: int) -> Optional[Clan]:
        """Get clan by Steam ID"""
        # Extract clan ID from Steam ID
        steam_id_obj = SteamID.from_raw(clan_steam_id)
        clan_id = steam_id_obj.get_accountID()
        
        with self.lock:
            return self.clans.get(clan_id)
    
    def get_clan_by_id(self, clan_id: int) -> Optional[Clan]:
        """Get clan by internal ID"""
        with self.lock:
            return self.clans.get(clan_id)
    
    def invite_to_clan(self, clan_steam_id: int, inviter_id: int, invitee_id: int) -> EResult:
        """Invite player to clan"""
        clan = self.get_clan(clan_steam_id)
        if not clan:
            return EResult.InvalidParam
        
        result = clan.invite_member(inviter_id, invitee_id)
        
        # Update database
        if result == EResult.OK:
            clan_id = SteamID.from_raw(clan_steam_id).get_accountID()
            relationship = ChatRelationship.member if clan.is_public else ChatRelationship.invited
            rank = ClanRank.member if clan.is_public else ClanRank.none
            self.database.set_clan_membership(clan_id, invitee_id, relationship, int(rank))
        
        return result
    
    def join_clan(self, clan_steam_id: int, player_id: int) -> EResult:
        """Join clan"""
        clan = self.get_clan(clan_steam_id)
        if not clan:
            return EResult.InvalidParam
        
        result = clan.join_clan(player_id)
        
        # Update database
        if result == EResult.OK:
            clan_id = SteamID.from_raw(clan_steam_id).get_accountID()
            self.database.set_clan_membership(clan_id, player_id, ChatRelationship.member, int(ClanRank.member))
        
        return result
    
    def leave_clan(self, clan_steam_id: int, player_id: int) -> Tuple[bool, Optional[int]]:
        """Leave clan"""
        clan = self.get_clan(clan_steam_id)
        if not clan:
            return False, None
        
        # Leave clan
        clan_closed, new_owner = clan.remove_member(player_id)
        
        # Update database
        clan_id = SteamID.from_raw(clan_steam_id).get_accountID()
        
        if clan_closed:
            # Remove clan entirely
            with self.lock:
                if clan_id in self.clans:
                    del self.clans[clan_id]
            self._delete_clan_from_db(clan_id)
        else:
            # Update membership in database
            self.database.set_clan_membership(clan_id, player_id, ChatRelationship.none, int(ClanRank.none))
            
            # Update new owner if needed
            if new_owner:
                self.database.set_clan_membership(clan_id, new_owner, ChatRelationship.member, int(ClanRank.owner))
        
        return clan_closed, new_owner
    
    def kick_from_clan(self, clan_steam_id: int, kicker_id: int, kicked_id: int) -> EResult:
        """Kick member from clan"""
        clan = self.get_clan(clan_steam_id)
        if not clan:
            return EResult.InvalidParam
        
        result = clan.kick_member(kicker_id, kicked_id)
        
        # Update database
        if result == EResult.OK:
            clan_id = SteamID.from_raw(clan_steam_id).get_accountID()
            self.database.set_clan_membership(clan_id, kicked_id, ChatRelationship.kicked, int(ClanRank.none))
        
        return result
    
    def change_member_rank(self, clan_steam_id: int, changer_id: int, target_id: int, new_rank: ClanRank) -> EResult:
        """Change member rank"""
        clan = self.get_clan(clan_steam_id)
        if not clan:
            return EResult.InvalidParam
        
        result = clan.change_member_rank(changer_id, target_id, new_rank)
        
        # Update database
        if result == EResult.OK:
            clan_id = SteamID.from_raw(clan_steam_id).get_accountID()
            self.database.set_clan_membership(clan_id, target_id, ChatRelationship.member, int(new_rank))
        
        return result
    
    def create_clan_event(self, clan_steam_id: int, creator_id: int, name: str, event_type: EventType,
                         start_time: datetime = None, description: str = "", game_id: int = 0,
                         game_server: str = "", game_server_pass: str = "", is_announcement: bool = False) -> Optional[int]:
        """Create clan event or announcement"""
        clan = self.get_clan(clan_steam_id)
        if not clan:
            return None
        
        event_id = clan.create_event(creator_id, name, event_type, start_time, description,
                                   game_id, game_server, game_server_pass, is_announcement)
        
        # Persist to database
        if event_id:
            # Implementation would persist to CommunityClanEvents table
            pass
        
        return event_id
    
    def set_player_of_the_week(self, clan_steam_id: int, setter_id: int, player_id: int) -> EResult:
        """Set player of the week"""
        clan = self.get_clan(clan_steam_id)
        if not clan:
            return EResult.InvalidParam
        
        result = clan.set_player_of_the_week(setter_id, player_id)
        
        # Update database
        if result == EResult.OK:
            # Implementation would update clan record
            pass
        
        return result
    
    def get_clan_members(self, clan_steam_id: int) -> List[Dict]:
        """Get clan member list"""
        clan = self.get_clan(clan_steam_id)
        if not clan:
            return []
        
        members = []
        for member in clan.get_member_list():
            member_data = {
                'steam_id': member.steam_id,
                'relationship': int(member.relationship),
                'rank': int(member.rank),
                'joined_at': member.joined_at.isoformat()
            }
            members.append(member_data)
        
        return members
    
    def _delete_clan_from_db(self, clan_id: int):
        """Delete clan and all associated data from database"""
        # Implementation would delete from all clan-related tables
        pass
    
    def search_clans(self, name_filter: str = "", tag_filter: str = "", limit: int = 50) -> List[Dict]:
        """Search for clans by name or tag"""
        results = []
        
        with self.lock:
            for clan in self.clans.values():
                if name_filter and name_filter.lower() not in clan.name.lower():
                    continue
                if tag_filter and tag_filter.lower() not in clan.tag.lower():
                    continue
                
                clan_data = {
                    'clan_id': clan.clan_id,
                    'steam_id': clan.steam_id,
                    'name': clan.name,
                    'tag': clan.tag,
                    'owner_id': clan.owner_id,
                    'is_public': clan.is_public,
                    'member_count': clan.get_member_count(),
                    'is_large_clan': clan.is_large_clan(),
                    'created_at': clan.created_at.isoformat()
                }
                results.append(clan_data)
                
                if len(results) >= limit:
                    break
        
        return results


# Global instance will be created in steam3.__init__.py