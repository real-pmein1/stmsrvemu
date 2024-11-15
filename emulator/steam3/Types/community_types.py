from enum import Enum, IntEnum, IntFlag

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
    lookingToTrade = 0x05 # Max for clients before 2010
    lookingToPlay = 0x06
    max = 0x07  # Assumed next sequence if max was meant to be inclusive

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

# The struct can be represented as a class in Python
class FriendRelation:
    def __init__(self, friendGlobalId: int, relationship: FriendRelationship):
        self.friendGlobalId = friendGlobalId
        self.relationship = relationship


class ClanRelationship(IntEnum):
    none = 0
    blocked = 1
    invited = 2
    member = 3
    kicked = 4

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

class ChatInfoType(IntEnum):
    stateChange = 1
    infoUpdate = 2
    memberLimitChange = 3

class ChatMemberStateChange(IntFlag):
    entered = 0x01
    left = 0x02
    disconnected = 0x04
    kicked = 0x08
    banned = 0x10
    startedVoiceSpeak = 0x1000
    endedVoiceSpeak = 0x2000

class ChatEntryType(IntEnum):
    invalid = 0x00
    chatMsg = 0x01
    typing = 0x02
    inviteGame = 0x03
    emote = 0x04
    lobbyGameStart = 0x05
    lobbyLeftConversation = 0x06

class ChatRoomType(IntEnum):
    none = 0
    friend = 1
    MUC = 2  # multi-user chat
    lobby = 3

class ChatPermission(IntFlag):
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

class ChatRoomEnterResponse(IntEnum):
    success = 1
    doesntExist = 2
    notAllowed = 3
    full = 4
    error = 5
    banned = 6

class ChatAction(IntEnum):
    inviteChat = 1
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

class ChatActionResult(Enum):
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

class Relation:
    def __init__(self, steamGlobalId: int, relationship: int):  # Using int for relationship type due to potential mixed usage
        self.steamGlobalId = steamGlobalId
        self.relationship = relationship

class ChatRoomFlags(IntFlag):
    none = 0
    locked = 1
    invisibleToFriends = 2
    moderated = 4
    unjoinable = 8

class LobbyIds:
    def __init__(self, appId: int, lobbyGlobalId: int):
        self.appId = appId
        self.lobbyGlobalId = lobbyGlobalId

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