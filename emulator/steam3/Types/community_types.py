from enum import Enum, IntEnum, IntFlag
from steam3.Types.chat_types import (
    ClanRelationship, ChatEntryType, ChatRoomType, ChatPermission, 
    ChatRoomEnterResponse, ChatAction, ChatActionResult, ChatRoomFlags,
    ChatInfoType, ChatMemberStateChange, ChatMemberStatus, ChatMemberRankDetails, ChatRoomType2
)
from steam3.Types.steam_types import (
    ELeaderboardDataRequest as LeaderboardDataRequest,
    ELeaderboardSortMethod as LeaderboardSortMethod,
    ELeaderboardDisplayType as LeaderboardDisplayType,
    ELeaderboardUploadScoreMethod as LeaderboardUploadScoreMethod
)
# Removed LobbyIds import to avoid circular dependency

class FriendRelationship(IntEnum):
    none = 0
    ignored = 1
    requestRecipient = 2
    friend = 3
    requestInitiator = 4
    blocked = 5
    blockedByFriend = 6
    suggestedFriend = 7 # deprecated, used with facebook linking
    max = 8

class PlayerState(IntEnum):
    offline = 0x00
    online = 0x01
    busy = 0x02
    away = 0x03
    snooze = 0x04
    lookingToTrade = 0x05  # Max for clients before 2010
    lookingToPlay = 0x06
    invisible = 0x07  # Appears offline to friends but is actually online

class ClanRank(Enum):
    none = 0x00
    owner = 0x01
    officer = 0x02
    member = 0x03
    moderator = 0x04

"""enum EPersonaChange : __int32
{
  k_EPersonaChangeName = 0x1,
  k_EPersonaChangeStatus = 0x2,
  k_EPersonaChangeComeOnline = 0x4,
  k_EPersonaChangeGoneOffline = 0x8,
  k_EPersonaChangeGamePlayed = 0x10,
  k_EPersonaChangeGameServer = 0x20,
  k_EPersonaChangeAvatar = 0x40,
  k_EPersonaChangeJoinedSource = 0x80,
  k_EPersonaChangeLeftSource = 0x100,
  k_EPersonaChangeRelationshipChanged = 0x200,
  k_EPersonaChangeNameFirstSet = 0x400,
};"""


class PersonaStateFlags(IntFlag):
    none = 0x00
    status = 0x01
    playerName = 0x02
    queryPort = 0x04
    sourceId = 0x08 # clan or game server steamID
    presence = 0x10
    chatMetadata = 0x20
    lastSeen = 0x40
    clanInfo = 0x80
    extraInfo = 0x100
    gameDataBlob = 0x200
    clanTag = 0x400
    facebook = 0x800
    richPresence = 0x1000
    broadcastId = 0x2000
    gameLobbyId = 0x4000
    watchingBroadcast = 0x8000

# Flags shared by all the original sets
RequestedPersonaStateFlags_common = (
    PersonaStateFlags.playerName |
    PersonaStateFlags.queryPort |
    PersonaStateFlags.sourceId |
    PersonaStateFlags.presence |
    PersonaStateFlags.lastSeen |
    PersonaStateFlags.extraInfo |
    PersonaStateFlags.gameDataBlob |
    # PersonaStateFlags.facebook |  # Uncomment if needed
    PersonaStateFlags.richPresence |
    PersonaStateFlags.broadcastId |
    PersonaStateFlags.gameLobbyId
)

# Individual flag sets
RequestedPersonaStateFlags_self = (
    RequestedPersonaStateFlags_common |
    PersonaStateFlags.status
)

RequestedPersonaStateFlags_inFriendsList_friend = (
    RequestedPersonaStateFlags_common |
    PersonaStateFlags.status
)

RequestedPersonaStateFlags_inFriendsList_other = (
    RequestedPersonaStateFlags_common
)

RequestedPersonaStateFlags_clanMembers = (
    RequestedPersonaStateFlags_common |
    PersonaStateFlags.status |
    PersonaStateFlags.clanInfo
)

RequestedPersonaStateFlags_chatMembers = (
    RequestedPersonaStateFlags_common |
    PersonaStateFlags.status
    # | PersonaStateFlags.chatMetadata
)

RequestedPersonaStateFlags_gameServerMembers = (
    RequestedPersonaStateFlags_common |
    PersonaStateFlags.status
)

# The struct can be represented as a class in Python
class FriendRelation:
    def __init__(self, friendGlobalId: int, relationship: FriendRelationship):
        self.friendGlobalId = friendGlobalId
        self.relationship = relationship


class ClanRelation:
    def __init__(self, clanGlobalId: int, relationship: ClanRelationship):
        self.clanGlobalId = clanGlobalId
        self.relationship = relationship

class ClanPermission(IntEnum):
    nobody = 0
    owner = 1
    officer = 2
    ownerAndOfficer = 3
    member = 4
    allMembers = 7

class ClanStateFlags(IntFlag):
    name = 0x01
    userCounts = 0x02
    announcements = 0x04
    events = 0x08

class ClanAccountFlags(IntFlag):
    public = 0x01
    large = 0x02
    locked = 0x04
    disabled = 0x08




class LobbyType(Enum):
    none = 0
    friendsOnly = 1
    public = 2
    invisible = 3

class ChatRoomStateChange(Enum):
    none = 0
    closing = 1

class LobbyComparison(Enum):
    equalOrLessThan = -2
    lessThan = -1
    equal = 0
    greaterThan = 1
    equalOrGreaterThan = 2
    notEqual = 3

class LobbyDistanceFilter(Enum):
    close = 0
    default = 1
    far = 2
    worldWide = 3

class LobbyFilterType(Enum):
    stringCompare = 0
    numericalCompare = 1
    slotsAvailable = 2
    nearValue = 3
    distance = 4
    maxResults = 5

