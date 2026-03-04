"""
Steam chat-related types and enums based on the C++ implementation.
"""

from enum import IntEnum


class ChatRoomType(IntEnum):
    """
    Enum matching C++ ChatRoomType
    """
    none = 0        # not part of official steam, but found in chat room invites
    friend = 1      # deprecated, not supported anymore by steam client
    MUC = 2         # Multi-User Chat
    lobby = 3       # deprecated chat room based lobby
    clan = 4        # Clan/Group chat
	
class ChatRelationship(IntEnum):
    none = 0
    blocked = 1
    invited = 2
    member = 3
    kicked = 4
	
class ClanRelationship(IntEnum):
    none = 0
    blocked = 1
    invited = 2
    member = 3
    kicked = 4

class ChatEntryType(IntEnum):
    """
    Enum matching C++ ChatEntryType
    """
    invalid = 0
    chatMsg = 1
    typing = 2
    inviteGame = 3
    emote = 4
    lobbyGameStart = 5
    lobbyLeftConversation = 6


class ChatPermission(IntEnum):
    """
    Enum matching C++ ChatPermission - bit flags
    """
    close = 0x0001
    invite = 0x0002
    talk = 0x0008
    kick = 0x0010
    mute = 0x0020
    setMetadata = 0x0040
    changePermissions = 0x0080
    ban = 0x0100
    changeAccess = 0x0200
    everyoneNotInClanDefault = 0x0008
    everyoneDefault = 0x000a
    memberDefault = 0x011a
    officerDefault = 0x021a
    ownerDefault = 0x037b
    mask = 0x03fb


class ChatRoomFlags(IntEnum):
    """
    Enum matching C++ ChatRoomFlags - bit flags
    """
    none = 0x00
    locked = 0x01
    invisible = 0x02
    moderated = 0x04
    unjoinable = 0x08


class ChatAction(IntEnum):
    """
    Enum matching C++ ChatAction
    """
    inviteChat = 1      # not used by clients for sending an invitation
    kick = 2
    ban = 3
    unBan = 4
    startVoiceSpeak = 5
    endVoiceSpeak = 6
    lockChat = 7
    unlockChat = 8
    closeChat = 9
    setJoinable = 10
    setUnjoinable = 11
    setOwner = 12
    setInvisibleToFriends = 13
    setVisibleToFriends = 14
    setModerated = 15
    setUnmoderated = 16


class ChatActionResult(IntEnum):
    """
    Enum matching C++ ChatActionResult
    """
    success = 1
    error = 2
    notPermitted = 3
    notAllowedOnClanMember = 4
    notAllowedOnBannedUser = 5
    notAllowedOnChatOwner = 6
    notAllowedOnSelf = 7
    chatDoesntExist = 8
    chatFull = 9
    voiceSlotsFull = 10


class ChatRoomEnterResponse(IntEnum):
    """
    Enum matching C++ ChatRoomEnterResponse
    """
    success = 1
    doesntExist = 2
    notAllowed = 3
    full = 4
    error = 5
    banned = 6
    limited = 7
    clanDisabled = 8
    communityBan = 9
    memberLimitExceeded = 10
    ratelimitExceeded = 11


class ChatInfoType(IntEnum):
    """
    Enum matching C++ ChatInfoType
    """
    infoUpdate = 1
    memberLimitChange = 2
    stateChange = 3


class ChatMemberStateChange(IntEnum):
    """
    Enum matching C++ ChatMemberStateChange
    """
    entered = 1
    left = 2
    disconnected = 3
    kicked = 4
    banned = 5


class ChatMemberStatus(IntEnum):
    """
    Enum for chat member status/relationship
    """
    NONE = 0
    BLOCKED = 1
    TO_BE_INVITED = 2
    MEMBER = 3


class ChatMemberRankDetails(IntEnum):
    """
    Enum for chat member rank details
    """
    NONE = 0
    CLAN_MEMBER = 1
    CLAN_OWNER = 2
    CHAT_OWNER = 3


class ChatRoomType2(IntEnum):
    """
    Extended chat room type enum
    """
    MUC = 1
    clan = 2
    lobby = 3


# Default values from C++
DEFAULT_MAX_MEMBERS_COUNT = 100