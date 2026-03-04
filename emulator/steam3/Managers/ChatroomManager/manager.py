"""
ChatroomManager - Comprehensive chatroom management matching C++ Steam functionality

This implementation supports:
- Full moderation (kick, ban, unban, mute, close, lock/unlock)
- Member state change broadcasts
- Invite persistence for offline users
- Lobby compatibility (lobbies ARE chatrooms with type=lobby)
- Database persistence for non-lobby rooms
"""

import logging
import threading
from datetime import datetime
from typing import Dict, Optional, List, Set, Tuple

from steam3.Types.steamid import SteamID
from steam3.Types.steam_types import EResult, EType, EInstanceFlag, EUniverse
from steam3.Types.chat_types import (
    ChatRoomType, ChatPermission, ChatRoomFlags, ChatAction, ChatActionResult,
    ChatRoomEnterResponse, ChatEntryType, ChatMemberStateChange, ChatInfoType,
    DEFAULT_MAX_MEMBERS_COUNT
)
from steam3.ClientManager.client import Client

log = logging.getLogger("ChatroomMgr")


class ChatMember:
    """Represents a member in a chatroom"""

    def __init__(self, steam_id: int, permissions: int = 0):
        self.steam_id = steam_id
        self.permissions = permissions
        self.voice_speaking = False
        self.muted = False
        self.joined_at = datetime.now()


class Chatroom:
    """
    Represents a chatroom, matching C++ CMServerCommunityChatRoom functionality

    Supports all Steam chatroom operations including moderation, invites, and metadata.
    """

    def __init__(self, chat_id: int, room_type: ChatRoomType, owner_id: int,
                 name: str = "", game_id: int = 0, clan_id: int = 0,
                 manager: 'ChatroomManager' = None):
        self.chat_id = chat_id
        self.steam_id = self._generate_steam_id(chat_id, room_type)
        self.room_type = room_type
        self.owner_id = owner_id
        self.name = name
        self.game_id = game_id
        self.clan_id = clan_id
        self.manager = manager  # Reference to manager for persistence

        # Permissions
        self.officer_permission = ChatPermission.officerDefault
        self.member_permission = ChatPermission.memberDefault
        self.all_permission = ChatPermission.everyoneDefault

        # Settings
        self.max_members = DEFAULT_MAX_MEMBERS_COUNT
        self.flags = ChatRoomFlags.none
        self.locked = False
        self.created_at = datetime.now()

        # Members: steam_id -> ChatMember
        self.members: Dict[int, ChatMember] = {}

        # Moderation lists
        self.banned_users: Set[int] = set()  # Steam IDs of banned users
        self.muted_users: Set[int] = set()   # Steam IDs of muted users
        self.moderators: Set[int] = set()    # Steam IDs of moderators/officers

        # Pending invites: invitee_steam_id -> inviter_steam_id
        self.pending_invites: Dict[int, int] = {}

        # Thread safety
        self.lock = threading.RLock()

    def _generate_steam_id(self, chat_id: int, room_type: ChatRoomType) -> int:
        """
        Generate Steam ID for chatroom with proper instance flags for 2008 client compatibility.

        Based on 2008 client decompiled analysis:
        - Regular chatrooms: EType.Chat with EInstanceFlag.ChatRoom
        - Lobby chatrooms: EType.Chat with EInstanceFlag.LOBBY
        - Clan chatrooms: EType.Chat with EInstanceFlag.CLAN
        """
        if room_type == ChatRoomType.lobby:
            instance = EInstanceFlag.LOBBY
        elif room_type == ChatRoomType.clan:
            instance = EInstanceFlag.CLAN
        else:
            instance = EInstanceFlag.ALL

        steam_id = SteamID()
        steam_id.set_from_identifier(chat_id, EUniverse.PUBLIC, EType.CHAT, instance)
        return int(steam_id)

    def enter_chatroom(self, player_id: int, voice_speaker: bool = False) -> ChatRoomEnterResponse:
        """Handle a player entering the chatroom"""
        # Ensure player_id is an int (convert SteamID objects if needed)
        player_id = int(player_id) if hasattr(player_id, '__int__') and not isinstance(player_id, int) else player_id

        with self.lock:
            # Check if already a member
            if player_id in self.members:
                return ChatRoomEnterResponse.success

            # Check if this player is the owner FIRST (compare account IDs)
            # Owner should ALWAYS be allowed to enter their own room
            # player_id is a 64-bit Steam ID, owner_id is a 32-bit account ID
            player_steam_id = SteamID.from_raw(player_id)
            player_account_id = int(player_steam_id.get_accountID())
            is_owner = player_account_id == self.owner_id

            # DEBUG: Log entry attempt details
            log.debug(f"enter_chatroom: player_id={player_id:016x}, player_account_id={player_account_id}")
            log.debug(f"  owner_id={self.owner_id}, is_owner={is_owner}")
            log.debug(f"  flags=0x{self.flags:02x}, locked={self.locked}")
            log.debug(f"  members={len(self.members)}, max_members={self.max_members}")

            # Check if banned (owner cannot be banned from their own room)
            if player_id in self.banned_users and not is_owner:
                return ChatRoomEnterResponse.banned

            # Check if room is full
            if len(self.members) >= self.max_members:
                return ChatRoomEnterResponse.full

            # Check if room is locked/unjoinable - OWNER BYPASSES THESE CHECKS
            if not is_owner:
                if self.flags & ChatRoomFlags.unjoinable:
                    log.debug(f"  Denied: room is unjoinable")
                    return ChatRoomEnterResponse.notAllowed

                if self.locked and player_id not in self.pending_invites:
                    log.debug(f"  Denied: room is locked and player not invited")
                    return ChatRoomEnterResponse.notAllowed

            # Add member with appropriate permissions (owner gets owner permissions)
            if is_owner:
                member = ChatMember(player_id, ChatPermission.ownerDefault)
                log.debug(f"  Assigned OWNER permissions: 0x{ChatPermission.ownerDefault:04x}")
            else:
                member = ChatMember(player_id, self.member_permission)
                log.debug(f"  Assigned MEMBER permissions: 0x{self.member_permission:04x}")
            member.voice_speaking = voice_speaker
            self.members[player_id] = member

            # Remove from pending invites if was invited
            if player_id in self.pending_invites:
                del self.pending_invites[player_id]

            # Persist to database if manager available, but NOT for game lobbies (temporary rooms)
            if self.manager and self.manager.database and self.room_type != ChatRoomType.lobby:
                try:
                    self.manager.database.persist_chatroom_member_join(self.chat_id, player_id, member.permissions)
                except Exception as e:
                    log.warning(f"Failed to persist member join: {e}")

            log.debug(f"Player {player_id} entered chatroom {self.chat_id}")
            return ChatRoomEnterResponse.success

    def leave_chatroom(self, player_id: int) -> Tuple[bool, Optional[int]]:
        """
        Handle player leaving chatroom.
        Returns (room_closed, new_owner_id)
        """
        # Ensure player_id is an int (convert SteamID objects if needed)
        player_id = int(player_id) if hasattr(player_id, '__int__') and not isinstance(player_id, int) else player_id

        with self.lock:
            if player_id not in self.members:
                return False, None

            del self.members[player_id]

            # Remove from muted/moderators
            self.muted_users.discard(player_id)
            self.moderators.discard(player_id)

            # Persist to database if manager available, but NOT for game lobbies (temporary rooms)
            if self.manager and self.manager.database and self.room_type != ChatRoomType.lobby:
                try:
                    self.manager.database.persist_chatroom_member_leave(self.chat_id, player_id)
                except Exception as e:
                    log.warning(f"Failed to persist member leave: {e}")

            # Check if owner left (extract accountID for comparison)
            player_account_id = int(SteamID.from_raw(player_id).get_accountID())
            if player_account_id == self.owner_id:
                if self.members:
                    # Transfer ownership to first remaining member
                    new_owner_steam_id = next(iter(self.members.keys()))
                    new_owner_account_id = int(SteamID.from_raw(new_owner_steam_id).get_accountID())
                    self.owner_id = new_owner_account_id  # Store as 32-bit accountID
                    return False, new_owner_steam_id  # Return 64-bit Steam ID for compatibility
                else:
                    # No members left, close room
                    return True, None

            return False, None

    def send_message(self, from_player_id: int, entry_type: ChatEntryType,
                    message_data: bytes) -> EResult:
        """Validate message sending permission"""
        with self.lock:
            if from_player_id not in self.members:
                return EResult.AccessDenied

            # Check if muted
            if from_player_id in self.muted_users:
                return EResult.AccessDenied

            # Check talk permission
            member = self.members[from_player_id]
            if not (member.permissions & ChatPermission.talk):
                return EResult.AccessDenied

            return EResult.OK

    def perform_action(self, actor_id: int, target_id: int, action: ChatAction) -> ChatActionResult:
        """
        Perform chat action (kick, ban, mute, etc.)

        Implements full C++ ChatAction enum support.
        """
        with self.lock:
            if actor_id not in self.members:
                return ChatActionResult.error

            actor = self.members[actor_id]

            # Handle different actions
            if action == ChatAction.kick:
                return self._do_kick(actor_id, target_id, actor)

            elif action == ChatAction.ban:
                return self._do_ban(actor_id, target_id, actor)

            elif action == ChatAction.unBan:
                return self._do_unban(actor_id, target_id, actor)

            elif action == ChatAction.lockChat:
                return self._do_lock(actor_id, actor)

            elif action == ChatAction.unlockChat:
                return self._do_unlock(actor_id, actor)

            elif action == ChatAction.closeChat:
                return self._do_close(actor_id, actor)

            elif action == ChatAction.setJoinable:
                return self._do_set_joinable(actor_id, actor, True)

            elif action == ChatAction.setUnjoinable:
                return self._do_set_joinable(actor_id, actor, False)

            elif action == ChatAction.setOwner:
                return self._do_set_owner(actor_id, target_id, actor)

            elif action == ChatAction.setModerated:
                return self._do_set_moderated(actor_id, actor, True)

            elif action == ChatAction.setUnmoderated:
                return self._do_set_moderated(actor_id, actor, False)

            elif action == ChatAction.inviteChat:
                return self._do_invite(actor_id, target_id, actor)

            elif action == ChatAction.startVoiceSpeak:
                return self._do_voice_speak(actor_id, target_id, True)

            elif action == ChatAction.endVoiceSpeak:
                return self._do_voice_speak(actor_id, target_id, False)

            elif action == ChatAction.setInvisibleToFriends:
                return self._do_set_visibility(actor_id, actor, False)

            elif action == ChatAction.setVisibleToFriends:
                return self._do_set_visibility(actor_id, actor, True)

            return ChatActionResult.error

    def _check_permission(self, actor: ChatMember, required_permission: int) -> bool:
        """Check if actor has required permission"""
        return bool(actor.permissions & required_permission)

    def _do_kick(self, actor_id: int, target_id: int, actor: ChatMember) -> ChatActionResult:
        """Kick a member from the chatroom"""
        if not self._check_permission(actor, ChatPermission.kick):
            return ChatActionResult.notPermitted

        # Extract accountID from target Steam ID for comparison
        target_account_id = int(SteamID.from_raw(target_id).get_accountID())
        if target_account_id == self.owner_id:
            return ChatActionResult.notAllowedOnChatOwner

        if target_id == actor_id:
            return ChatActionResult.notAllowedOnSelf

        if target_id not in self.members:
            return ChatActionResult.error

        # Remove the member
        del self.members[target_id]
        self.muted_users.discard(target_id)
        self.moderators.discard(target_id)

        log.info(f"Player {target_id} was kicked from chatroom {self.chat_id} by {actor_id}")
        return ChatActionResult.success

    def _do_ban(self, actor_id: int, target_id: int, actor: ChatMember) -> ChatActionResult:
        """Ban a user from the chatroom"""
        if not self._check_permission(actor, ChatPermission.ban):
            return ChatActionResult.notPermitted

        # Extract accountID from target Steam ID for comparison
        target_account_id = int(SteamID.from_raw(target_id).get_accountID())
        if target_account_id == self.owner_id:
            return ChatActionResult.notAllowedOnChatOwner

        if target_id == actor_id:
            return ChatActionResult.notAllowedOnSelf

        if target_id in self.banned_users:
            return ChatActionResult.notAllowedOnBannedUser

        # Add to banned list
        self.banned_users.add(target_id)

        # Remove from room if present
        if target_id in self.members:
            del self.members[target_id]
            self.muted_users.discard(target_id)
            self.moderators.discard(target_id)

        # Remove pending invite
        self.pending_invites.pop(target_id, None)

        log.info(f"Player {target_id} was banned from chatroom {self.chat_id} by {actor_id}")
        return ChatActionResult.success

    def _do_unban(self, actor_id: int, target_id: int, actor: ChatMember) -> ChatActionResult:
        """Unban a user from the chatroom"""
        if not self._check_permission(actor, ChatPermission.ban):
            return ChatActionResult.notPermitted

        if target_id not in self.banned_users:
            return ChatActionResult.error

        self.banned_users.discard(target_id)

        log.info(f"Player {target_id} was unbanned from chatroom {self.chat_id} by {actor_id}")
        return ChatActionResult.success

    def _do_lock(self, actor_id: int, actor: ChatMember) -> ChatActionResult:
        """Lock the chatroom (invite-only)"""
        # Extract accountID from actor Steam ID for comparison
        actor_account_id = int(SteamID.from_raw(actor_id).get_accountID())
        if actor_account_id != self.owner_id and not self._check_permission(actor, ChatPermission.changeAccess):
            return ChatActionResult.notPermitted

        self.locked = True
        self.flags |= ChatRoomFlags.locked

        log.info(f"Chatroom {self.chat_id} was locked by {actor_id}")
        return ChatActionResult.success

    def _do_unlock(self, actor_id: int, actor: ChatMember) -> ChatActionResult:
        """Unlock the chatroom"""
        # Extract accountID from actor Steam ID for comparison
        actor_account_id = int(SteamID.from_raw(actor_id).get_accountID())
        if actor_account_id != self.owner_id and not self._check_permission(actor, ChatPermission.changeAccess):
            return ChatActionResult.notPermitted

        self.locked = False
        self.flags &= ~ChatRoomFlags.locked

        log.info(f"Chatroom {self.chat_id} was unlocked by {actor_id}")
        return ChatActionResult.success

    def _do_close(self, actor_id: int, actor: ChatMember) -> ChatActionResult:
        """Close the chatroom"""
        # Extract accountID from actor Steam ID for comparison
        actor_account_id = int(SteamID.from_raw(actor_id).get_accountID())
        if actor_account_id != self.owner_id and not self._check_permission(actor, ChatPermission.close):
            return ChatActionResult.notPermitted

        # Mark for closing - manager will handle cleanup
        log.info(f"Chatroom {self.chat_id} was closed by {actor_id}")
        return ChatActionResult.success

    def _do_set_joinable(self, actor_id: int, actor: ChatMember, joinable: bool) -> ChatActionResult:
        """Set chatroom joinable/unjoinable"""
        # Extract accountID from actor Steam ID for comparison
        actor_account_id = int(SteamID.from_raw(actor_id).get_accountID())
        if actor_account_id != self.owner_id and not self._check_permission(actor, ChatPermission.changeAccess):
            return ChatActionResult.notPermitted

        if joinable:
            self.flags &= ~ChatRoomFlags.unjoinable
        else:
            self.flags |= ChatRoomFlags.unjoinable

        log.info(f"Chatroom {self.chat_id} joinable set to {joinable} by {actor_id}")
        return ChatActionResult.success

    def _do_set_owner(self, actor_id: int, target_id: int, actor: ChatMember) -> ChatActionResult:
        """Transfer ownership to another member"""
        # Extract accountID from actor Steam ID for comparison
        actor_account_id = int(SteamID.from_raw(actor_id).get_accountID())
        if actor_account_id != self.owner_id:
            return ChatActionResult.notPermitted

        if target_id not in self.members:
            return ChatActionResult.error

        # Transfer ownership - store accountID, not full Steam ID
        old_owner = self.owner_id
        target_account_id = int(SteamID.from_raw(target_id).get_accountID())
        self.owner_id = target_account_id

        # Update permissions - need to reconstruct old owner's Steam ID for lookup
        old_owner_steam_id = None
        for member_id in self.members.keys():
            if int(SteamID.from_raw(member_id).get_accountID()) == old_owner:
                old_owner_steam_id = member_id
                break

        if old_owner_steam_id and old_owner_steam_id in self.members:
            self.members[old_owner_steam_id].permissions = self.member_permission
        self.members[target_id].permissions = ChatPermission.ownerDefault

        log.info(f"Chatroom {self.chat_id} ownership transferred from {old_owner} to {target_id}")
        return ChatActionResult.success

    def _do_set_moderated(self, actor_id: int, actor: ChatMember, moderated: bool) -> ChatActionResult:
        """Set chatroom moderated/unmoderated"""
        # Extract accountID from actor Steam ID for comparison
        actor_account_id = int(SteamID.from_raw(actor_id).get_accountID())
        if actor_account_id != self.owner_id and not self._check_permission(actor, ChatPermission.changeAccess):
            return ChatActionResult.notPermitted

        if moderated:
            self.flags |= ChatRoomFlags.moderated
        else:
            self.flags &= ~ChatRoomFlags.moderated

        log.info(f"Chatroom {self.chat_id} moderated set to {moderated} by {actor_id}")
        return ChatActionResult.success

    def _do_invite(self, actor_id: int, target_id: int, actor: ChatMember) -> ChatActionResult:
        """Invite a user to the chatroom"""
        if not self._check_permission(actor, ChatPermission.invite):
            return ChatActionResult.notPermitted

        if target_id in self.banned_users:
            return ChatActionResult.notAllowedOnBannedUser

        if target_id in self.members:
            return ChatActionResult.error  # Already a member

        if len(self.members) >= self.max_members:
            return ChatActionResult.chatFull

        # Add to pending invites
        self.pending_invites[target_id] = actor_id

        # Persist invite for offline delivery
        if self.manager and self.manager.database:
            try:
                self.manager._persist_invite(self.chat_id, target_id, actor_id)
            except Exception as e:
                log.warning(f"Failed to persist invite: {e}")

        log.info(f"Player {target_id} was invited to chatroom {self.chat_id} by {actor_id}")
        return ChatActionResult.success

    def _do_voice_speak(self, actor_id: int, target_id: int, speaking: bool) -> ChatActionResult:
        """Start/end voice speaking"""
        if target_id not in self.members:
            return ChatActionResult.error

        # Only allow self or owner to control voice
        # Extract accountID from actor Steam ID for comparison
        actor_account_id = int(SteamID.from_raw(actor_id).get_accountID())
        if actor_id != target_id and actor_account_id != self.owner_id:
            return ChatActionResult.notPermitted

        self.members[target_id].voice_speaking = speaking
        return ChatActionResult.success

    def _do_set_visibility(self, actor_id: int, actor: ChatMember, visible: bool) -> ChatActionResult:
        """Set chatroom visibility to friends"""
        # Extract accountID from actor Steam ID for comparison
        actor_account_id = int(SteamID.from_raw(actor_id).get_accountID())
        if actor_account_id != self.owner_id:
            return ChatActionResult.notPermitted

        if visible:
            self.flags &= ~ChatRoomFlags.invisible
        else:
            self.flags |= ChatRoomFlags.invisible

        log.info(f"Chatroom {self.chat_id} visibility set to {visible} by {actor_id}")
        return ChatActionResult.success

    def mute_member(self, actor_id: int, target_id: int) -> ChatActionResult:
        """Mute a member (custom action)"""
        if actor_id not in self.members:
            return ChatActionResult.error

        actor = self.members[actor_id]
        if not self._check_permission(actor, ChatPermission.mute):
            return ChatActionResult.notPermitted

        # Extract accountID from target Steam ID for comparison
        target_account_id = int(SteamID.from_raw(target_id).get_accountID())
        if target_account_id == self.owner_id:
            return ChatActionResult.notAllowedOnChatOwner

        if target_id not in self.members:
            return ChatActionResult.error

        self.muted_users.add(target_id)
        log.info(f"Player {target_id} was muted in chatroom {self.chat_id} by {actor_id}")
        return ChatActionResult.success

    def unmute_member(self, actor_id: int, target_id: int) -> ChatActionResult:
        """Unmute a member (custom action)"""
        if actor_id not in self.members:
            return ChatActionResult.error

        actor = self.members[actor_id]
        if not self._check_permission(actor, ChatPermission.mute):
            return ChatActionResult.notPermitted

        self.muted_users.discard(target_id)
        log.info(f"Player {target_id} was unmuted in chatroom {self.chat_id} by {actor_id}")
        return ChatActionResult.success

    def get_member_list(self) -> List[ChatMember]:
        """Get list of current members"""
        with self.lock:
            return list(self.members.values())

    def get_member_steam_ids(self) -> List[int]:
        """Get list of member Steam IDs"""
        with self.lock:
            return list(self.members.keys())

    def is_member(self, steam_id: int) -> bool:
        """Check if user is a member"""
        return steam_id in self.members

    def is_banned(self, steam_id: int) -> bool:
        """Check if user is banned"""
        return steam_id in self.banned_users

    def is_muted(self, steam_id: int) -> bool:
        """Check if user is muted"""
        return steam_id in self.muted_users


class ChatroomManager:
    """
    Manages chatrooms, matching C++ CMServerCommunity chatroom functionality

    Supports:
    - Chatroom lifecycle (create, join, leave, close)
    - Member management and moderation
    - Invite persistence for offline users
    - Broadcasting to members
    - Database persistence
    """

    def __init__(self, database=None):
        self.chatrooms: Dict[int, Chatroom] = {}  # chat_id -> Chatroom
        self.lock = threading.RLock()

        # Database connection through steam3 database object
        self.database = database

        # Initialize next_chat_id from database to avoid duplicate key errors
        self.next_chat_id = self._get_next_chat_id_from_db()

        # Pending invites for offline users: user_steam_id -> list of (chat_id, inviter_id)
        self.offline_invites: Dict[int, List[Tuple[int, int]]] = {}

    def _get_next_chat_id_from_db(self) -> int:
        """
        Query the database to find the maximum existing chat ID and return the next available ID.
        Falls back to 1000000 if the database is unavailable or empty.
        """
        if self.database:
            try:
                max_id = self.database.get_max_chatroom_id()
                if max_id is not None and max_id >= 1000000:
                    next_id = max_id + 1
                    log.info(f"ChatroomManager: Initialized next_chat_id to {next_id} from database")
                    return next_id
            except Exception as e:
                log.warning(f"ChatroomManager: Failed to get max chatroom ID from database: {e}")

        log.info("ChatroomManager: Using default next_chat_id = 1000000")
        return 1000000  # Default starting ID

    def register_chatroom(self, owner_id: int, room_type: ChatRoomType, name: str,
                         clan_id: int = 0, game_id: int = 0,
                         officer_permission: int = ChatPermission.officerDefault,
                         member_permission: int = ChatPermission.memberDefault,
                         all_permission: int = ChatPermission.everyoneDefault,
                         max_members: int = DEFAULT_MAX_MEMBERS_COUNT,
                         flags: int = ChatRoomFlags.none,
                         friend_chat_id: int = 0, invited_id: int = 0) -> int:
        """
        Register a new chatroom, matching C++ registerChatRoom functionality.
        Returns chatroom Steam ID or 0 on failure.
        """
        with self.lock:
            try:
                chat_id = self.next_chat_id
                self.next_chat_id += 1

                # Create chatroom
                chatroom = Chatroom(chat_id, room_type, owner_id, name, game_id, clan_id, self)
                chatroom.officer_permission = officer_permission
                chatroom.member_permission = member_permission
                chatroom.all_permission = all_permission
                chatroom.max_members = max_members if max_members > 0 else DEFAULT_MAX_MEMBERS_COUNT
                chatroom.flags = flags
                chatroom.locked = bool(flags & ChatRoomFlags.locked)

                # DEBUG: Log chatroom creation details
                log.debug(f"register_chatroom: Created chatroom {chat_id}:")
                log.debug(f"  room_type: {room_type}")
                log.debug(f"  owner_id (accountID): {owner_id}")
                log.debug(f"  officer_permission: 0x{officer_permission:04x}")
                log.debug(f"  member_permission: 0x{member_permission:04x}")
                log.debug(f"  all_permission: 0x{all_permission:04x}")
                log.debug(f"  flags: 0x{chatroom.flags:02x}, locked: {chatroom.locked}")
                log.debug(f"  max_members: {chatroom.max_members}")
                log.debug(f"  chatroom.steam_id: {chatroom.steam_id:016x}")

                # Store in memory
                self.chatrooms[chat_id] = chatroom

                # Persist to database if available, but NOT for game lobbies (temporary rooms)
                if self.database and room_type != ChatRoomType.lobby:
                    try:
                        self.database.persist_chatroom(
                            chatroom.chat_id, int(chatroom.room_type), chatroom.owner_id,
                            chatroom.clan_id, chatroom.game_id, chatroom.name, chatroom.created_at,
                            chatroom.flags, chatroom.officer_permission, chatroom.member_permission,
                            chatroom.all_permission, chatroom.max_members
                        )
                    except Exception as e:
                        log.warning(f"Failed to persist chatroom to database: {e}")

                # Handle initial invite if specified
                if invited_id != 0:
                    chatroom.pending_invites[invited_id] = owner_id
                    self._persist_invite(chat_id, invited_id, owner_id)

                log.info(f"Created chatroom {chat_id}: '{name}' (type={room_type}, owner={owner_id})")
                return chatroom.steam_id

            except Exception as e:
                log.error(f"Failed to create chatroom: {e}")
                return 0

    def get_chatroom(self, chat_steam_id: int, lock_chatroom: bool = True) -> Optional[Chatroom]:
        """
        Get chatroom by Steam ID.
        Returns chatroom object or None if not found.
        """
        # Extract chat ID from Steam ID
        steam_id_obj = SteamID.from_raw(chat_steam_id)
        # get_accountID() returns an AccountID wrapper, convert to int for dict lookup
        chat_id = int(steam_id_obj.get_accountID())

        with self.lock:
            return self.chatrooms.get(chat_id)

    def get_chatroom_by_id(self, chat_id: int) -> Optional[Chatroom]:
        """Get chatroom by internal ID (not Steam ID)"""
        with self.lock:
            return self.chatrooms.get(chat_id)

    def remove_chatroom(self, chat_id: int):
        """Remove chatroom from manager"""
        with self.lock:
            if chat_id in self.chatrooms:
                chatroom = self.chatrooms.pop(chat_id)

                # Remove from database if available
                if self.database:
                    try:
                        self.database.remove_chatroom_from_db(chat_id)
                    except Exception as e:
                        log.warning(f"Failed to remove chatroom from database: {e}")

                log.info(f"Removed chatroom {chat_id}")

    def send_message_to_chatroom(self, chat_steam_id: int, from_player_id: int,
                                entry_type: ChatEntryType, message_data: bytes,
                                exclude_player_id: int = 0) -> EResult:
        """Send message to all members of a chatroom"""
        chatroom = self.get_chatroom(chat_steam_id)
        if not chatroom:
            return EResult.InvalidParam

        # Validate sender has permission
        result = chatroom.send_message(from_player_id, entry_type, message_data)
        if result != EResult.OK:
            return result

        # Persist message to database, but NOT for game lobbies (temporary rooms)
        if self.database and chatroom.room_type != ChatRoomType.lobby:
            try:
                self.database.persist_chatroom_message(chatroom.chat_id, from_player_id, message_data)
            except Exception as e:
                log.warning(f"Failed to persist message: {e}")

        # Broadcast to all members except excluded player
        self._broadcast_chat_message(chatroom, from_player_id, entry_type,
                                     message_data, exclude_player_id)

        return EResult.OK

    def _broadcast_chat_message(self, chatroom: Chatroom, from_player_id: int,
                               entry_type: ChatEntryType, message_data: bytes,
                               exclude_player_id: int = 0):
        """Broadcast chat message to all chatroom members"""
        from steam3.ClientManager import Client_Manager
        from steam3.messages.MsgClientChatMsg import MsgClientChatMsg

        for member_steam_id in chatroom.members.keys():
            if member_steam_id == exclude_player_id:
                continue

            target_client = Client_Manager.get_client_by_steamid(member_steam_id)
            if target_client:
                try:
                    msg = MsgClientChatMsg(target_client)
                    msg.chatGlobalId = chatroom.steam_id
                    msg.memberGlobalId = SteamID.from_raw(from_player_id)
                    msg.entryType = entry_type
                    msg.data = message_data
                    target_client.sendReply([msg.to_clientmsg()])
                except Exception as e:
                    log.warning(f"Failed to send chat message to {member_steam_id}: {e}")

    def broadcast_member_state_change(self, chatroom: Chatroom, member_steam_id: int,
                                     state_change: ChatMemberStateChange,
                                     actor_steam_id: int = None):
        """Broadcast member state change to all chatroom members"""
        from steam3.ClientManager import Client_Manager
        from steam3.messages.MsgClientChatMemberInfo import MsgClientChatMemberInfo
        from steam3.Types.MessageObject.ChatMemberInfo import ChatMemberInfo

        if actor_steam_id is None:
            actor_steam_id = member_steam_id

        log.debug(f"Broadcasting state change {state_change.name} for member {member_steam_id:016x} "
                 f"in chatroom {chatroom.chat_id} to {len(chatroom.members)} members")

        # Prepare memberInfo for entered state change (required by tinserver protocol)
        member_info = None
        if state_change == ChatMemberStateChange.entered and member_steam_id in chatroom.members:
            member = chatroom.members[member_steam_id]
            member_info = ChatMemberInfo()
            member_info.set_SteamID(member_steam_id)
            member_info.set_Permissions(member.permissions)
            member_info.set_Details(0)  # Reserved for future use

        sent_count = 0
        for target_steam_id in list(chatroom.members.keys()):
            # Skip sending "entered" notification to the member who just entered
            # They already know they joined (from ChatEnter response)
            if state_change == ChatMemberStateChange.entered and target_steam_id == member_steam_id:
                log.debug(f"  Skipping self-notification for {target_steam_id:016x}")
                continue

            target_client = Client_Manager.get_client_by_steamid(target_steam_id)
            if target_client:
                try:
                    msg = MsgClientChatMemberInfo(target_client)
                    msg.chat_id = SteamID.from_raw(chatroom.steam_id)
                    msg.info_type = ChatInfoType.stateChange
                    msg.user_steam_id = SteamID.from_raw(member_steam_id)
                    msg.state_change = state_change
                    msg.target_steam_id = SteamID.from_raw(actor_steam_id)
                    # Include memberInfo for entered state change (tinserver protocol)
                    if member_info:
                        msg.member_info = member_info
                    target_client.sendReply([msg.to_clientmsg()])
                    sent_count += 1
                    log.debug(f"  Sent state change to {target_steam_id:016x}")
                except Exception as e:
                    log.warning(f"Failed to send state change to {target_steam_id}: {e}")
            else:
                log.debug(f"  Client not found for {target_steam_id:016x}")

        log.debug(f"Broadcast complete: sent to {sent_count} clients")

    def broadcast_room_info_change(self, chatroom: Chatroom, actor_steam_id: int):
        """Broadcast room info change (flags like lock/unlock) to all chatroom members"""
        from steam3.ClientManager import Client_Manager
        from steam3.messages.responses.MsgClientChatRoomInfo import MsgClientChatRoomInfo

        log.debug(f"Broadcasting room info change for chatroom {chatroom.chat_id} "
                 f"(flags=0x{chatroom.flags:02x}) to {len(chatroom.members)} members")

        sent_count = 0
        for target_steam_id in list(chatroom.members.keys()):
            target_client = Client_Manager.get_client_by_steamid(target_steam_id)
            if target_client:
                try:
                    msg = MsgClientChatRoomInfo(target_client)
                    msg.chat_id = SteamID.from_raw(chatroom.steam_id)
                    msg.info_type = ChatInfoType.infoUpdate
                    msg.flags = chatroom.flags
                    msg.steam_id_making_change = SteamID.from_raw(actor_steam_id)
                    target_client.sendReply([msg.to_clientmsg()])
                    sent_count += 1
                    log.debug(f"  Sent room info change to {target_steam_id:016x}")
                except Exception as e:
                    log.warning(f"Failed to send room info change to {target_steam_id}: {e}")
            else:
                log.debug(f"  Client not found for {target_steam_id:016x}")

        log.debug(f"Room info broadcast complete: sent to {sent_count} clients")

    def invite_user_to_chatroom(self, chat_steam_id: int, inviter_id: int,
                               invitee_id: int) -> ChatActionResult:
        """Invite a user to a chatroom"""
        chatroom = self.get_chatroom(chat_steam_id)
        if not chatroom:
            return ChatActionResult.chatDoesntExist

        # Perform invite action
        result = chatroom.perform_action(inviter_id, invitee_id, ChatAction.inviteChat)

        if result == ChatActionResult.success:
            # Send invite message to online user
            self._send_invite_to_user(chatroom, inviter_id, invitee_id)

        return result

    def _send_invite_to_user(self, chatroom: Chatroom, inviter_id: int, invitee_id: int):
        """
        Send invite message to a user (online or persist for offline).

        Note: inviter_id and invitee_id can be either:
        - 32-bit accountIDs (when coming from pending_invites storage)
        - 64-bit steamIDs (when called directly from invite_user_to_chatroom)

        This method handles both cases by using the client's actual steamID when available
        and converting accountIDs to full steamIDs for the message.
        """
        from steam3.ClientManager import Client_Manager
        from steam3.messages.responses.MsgClientChatInvite import MsgClientChatInvite

        # get_client_by_steamid handles both accountIDs and steamIDs (extracts accountID internally)
        target_client = Client_Manager.get_client_by_steamid(invitee_id)

        if target_client:
            # User is online - send invite immediately
            try:
                msg = MsgClientChatInvite(target_client)
                msg.chatroomSteamID = chatroom.steam_id
                msg.chat_room_type = chatroom.room_type

                # Use target client's actual steamID (64-bit) instead of potentially raw accountID
                msg.invitedSteamID = int(target_client.steamID)

                # Convert inviter_id to full steamID if it's an accountID
                # If inviter_id is small (< 2^32), it's likely an accountID
                if inviter_id < 0x100000000:
                    inviter_steam_id = int(SteamID.createSteamIDFromAccountID(inviter_id))
                else:
                    inviter_steam_id = inviter_id

                msg.patronSteamID = inviter_steam_id
                msg.friend_chat_global_id = inviter_steam_id
                msg.chat_room_name = chatroom.name
                msg.game_id = chatroom.game_id
                target_client.sendReply([msg.to_clientmsg()])
                log.debug(f"Sent invite to online user {int(target_client.steamID):016x} for chatroom {chatroom.chat_id}")
            except Exception as e:
                log.warning(f"Failed to send invite to {invitee_id}: {e}")
        else:
            # User is offline - persist invite for later delivery
            self._persist_invite(chatroom.chat_id, invitee_id, inviter_id)
            log.debug(f"Persisted invite for offline user {invitee_id} for chatroom {chatroom.chat_id}")

    def _persist_invite(self, chat_id: int, invitee_id: int, inviter_id: int):
        """Persist invite for offline user"""
        # In-memory storage
        if invitee_id not in self.offline_invites:
            self.offline_invites[invitee_id] = []

        # Avoid duplicates
        invite_tuple = (chat_id, inviter_id)
        if invite_tuple not in self.offline_invites[invitee_id]:
            self.offline_invites[invitee_id].append(invite_tuple)

        # Persist to database if available
        if self.database:
            try:
                # Use the chatroom member table with invited status
                from steam3.Types.chat_types import ChatMemberStatus, ChatMemberRankDetails

                # Extract accountIDs from 64-bit SteamIDs for database storage
                # The friendRegistryID and inviterAccountID columns are INT (32-bit)
                invitee_account_id = int(SteamID.from_raw(invitee_id).get_accountID())
                inviter_account_id = int(SteamID.from_raw(inviter_id).get_accountID())

                self.database.set_chatroom_member(
                    chat_id, invitee_account_id,
                    int(ChatMemberStatus.TO_BE_INVITED),
                    int(ChatMemberRankDetails.NONE),
                    inviterAccountID=inviter_account_id
                )
            except Exception as e:
                log.warning(f"Failed to persist invite to database: {e}")

    def send_pending_invites_to_user(self, user_steam_id: int):
        """Send all pending invites to a user who just came online"""
        # Check in-memory invites
        pending = self.offline_invites.pop(user_steam_id, [])

        # Also check database
        if self.database:
            try:
                db_invites = self.database.get_pending_invites(user_steam_id)
                for chat_id, inviter_id in db_invites:
                    if (chat_id, inviter_id) not in pending:
                        pending.append((chat_id, inviter_id))
            except Exception as e:
                log.warning(f"Failed to get pending invites from database: {e}")

        # Send all pending invites
        for chat_id, inviter_id in pending:
            chatroom = self.get_chatroom_by_id(chat_id)
            if chatroom:
                self._send_invite_to_user(chatroom, inviter_id, user_steam_id)

    def handle_client_disconnect(self, player_steam_id: int):
        """
        Handle client disconnection - remove from all chatrooms and notify members.
        """
        rooms_to_remove = []

        with self.lock:
            for chat_id, chatroom in list(self.chatrooms.items()):
                if player_steam_id in chatroom.members:
                    room_closed, new_owner = chatroom.leave_chatroom(player_steam_id)

                    # Broadcast disconnect to remaining members
                    self.broadcast_member_state_change(
                        chatroom, player_steam_id,
                        ChatMemberStateChange.disconnected
                    )

                    if room_closed:
                        rooms_to_remove.append(chat_id)
                    elif new_owner:
                        # Broadcast ownership change
                        log.info(f"Chatroom {chat_id}: Ownership transferred to {new_owner}")

            # Clean up closed rooms
            for chat_id in rooms_to_remove:
                self.remove_chatroom(chat_id)

    def clear_cache(self):
        """Clear all cached chatrooms"""
        with self.lock:
            self.chatrooms.clear()
            log.info("Chatroom cache cleared")

    def list_chatrooms(self) -> List[Chatroom]:
        """Lists all active chatrooms"""
        with self.lock:
            return list(self.chatrooms.values())

    # Legacy methods for compatibility with old code
    def create_chatroom(self, chat_type: int, owner_accountID: int, name: str, motd: str,
                        applicationID: int, member_limit: int, allPermissions, memberPermissions,
                        officerPermissions, chatStartedWithSteamID: SteamID, inviteUserSteamID: SteamID):
        """Legacy create_chatroom method for compatibility"""
        chat_steam_id = self.register_chatroom(
            owner_id=owner_accountID,
            room_type=ChatRoomType(chat_type),
            name=name,
            game_id=applicationID,
            officer_permission=officerPermissions,
            member_permission=memberPermissions,
            all_permission=allPermissions,
            max_members=member_limit,
            friend_chat_id=int(chatStartedWithSteamID),
            invited_id=int(inviteUserSteamID)
        )
        # Return chatroom object for compatibility
        return self.get_chatroom(chat_steam_id)
