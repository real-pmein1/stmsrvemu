from collections import defaultdict

from steam3.Types import SteamIntEnum


class SystemIMType(SteamIntEnum):
    rawText = 0
    invalidCard = 1
    recurringPurchaseFailed = 2
    cardWillExpire = 3
    subscriptionExpired = 4
    guestPassReceived = 5
    guestPassGranted = 6
    giftRevoked = 7
    max = 8

"""class EAccountFlags_2008:
    m_EAccountFlagNormalUser = 0x0
    k_EAccountFlagPersonaNameSet = 0x1
    k_EAccountFlagUnbannable = 0x2
    k_EAccountFlagPasswordSet = 0x4
    k_EAccountFlagSupport = 0x8
    k_EAccountFlagAdmin = 0x10
    k_EAccountFlagSupervisor = 0x20
    k_EAccountFlagAppEditor = 0x40
    k_EAccountFlagHWIDSet = 0x80
    k_EAccountFlagPersonalQASet = 0x100
    k_EAccountFlagVacBeta = 0x200
    k_EAccountFlagDebug = 0x400"""

class EResult(SteamIntEnum):
    """Doc: https://partner.steamgames.com/doc/api/steam_api#EResult"""
    Invalid = 0
    OK = 1                              #: success
    Fail = 2                            #: generic failure
    NoConnection = 3                    #: no/failed network connection
    NoConnectionRetry = 4               #: OBSOLETE - removed
    InvalidPassword = 5                 #: password/ticket is invalid
    LoggedInElsewhere = 6               #: same user logged in elsewhere
    InvalidProtocolVer = 7              #: protocol version is incorrect
    InvalidParam = 8                    #: a parameter is incorrect
    FileNotFound = 9                    #: file was not found
    Busy = 10                           #: called method busy - action not taken
    InvalidState = 11                   #: called object was in an invalid state
    InvalidName = 12                    #: name is invalid
    InvalidEmail = 13                   #: email is invalid
    DuplicateName = 14                  #: name is not unique
    AccessDenied = 15                   #: access is denied
    Timeout = 16                        #: operation timed out
    Banned = 17                         #: VAC2 banned
    AccountNotFound = 18                #: account not found
    InvalidSteamID = 19                 #: steamID is invalid
    ServiceUnavailable = 20             #: The requested service is currently unavailable
    NotLoggedOn = 21                    #: The user is not logged on
    Pending = 22                        #: Request is pending (may be in process, or waiting on third party)
    EncryptionFailure = 23              #: Encryption or Decryption failed
    InsufficientPrivilege = 24          #: Insufficient privilege
    LimitExceeded = 25                  #: Too much of a good thing
    Revoked = 26                        #: Access has been revoked (used for revoked guest passes)
    Expired = 27                        #: License/Guest pass the user is trying to access is expired
    AlreadyRedeemed = 28                #: Guest pass has already been redeemed by account, cannot be acked again
    DuplicateRequest = 29               #: The request_id is a duplicate and the action has already occurred in the past, ignored this time
    AlreadyOwned = 30                   #: All the games in this guest pass redemption request_id are already owned by the user
    IPNotFound = 31                     #: IP address not found
    PersistFailed = 32                  #: failed to write change to the message store
    LockingFailed = 33                  #: failed to acquire access lock for this operation
    LogonSessionReplaced = 34
    ConnectFailed = 35
    HandshakeFailed = 36
    IOFailure = 37
    RemoteDisconnect = 38
    ShoppingCartNotFound = 39           #: failed to find the shopping cart requested
    Blocked = 40                        #: a user didn't allow it
    Ignored = 41                        #: target is ignoring sender
    NoMatch = 42                        #: nothing matching the request_id found
    AccountDisabled = 43
    ServiceReadOnly = 44                #: this service is not accepting content changes right now
    AccountNotFeatured = 45             #: account doesn't have value, so this feature isn't available
    AdministratorOK = 46                #: allowed to take this action, but only because requester is admin
    ContentVersion = 47                 #: A Version mismatch in content transmitted within the Steam protocol.
    TryAnotherCM = 48                   #: The current CM can't service the user making a request_id, user should try another.
    PasswordRequiredToKickSession = 49  #: You are already logged in elsewhere, this cached credential login has failed.
    AlreadyLoggedInElsewhere = 50       #: You are already logged in elsewhere, you must wait
    Suspended = 51                      #: Long running operation (content download) suspended/paused
    Cancelled = 52                      #: Operation canceled (typically by user: content download)
    DataCorruption = 53                 #: Operation canceled because message is ill formed or unrecoverable
    DiskFull = 54                       #: Operation canceled - not enough disk space.
    RemoteCallFailed = 55               #: an remote call or IPC call failed
    PasswordUnset = 56                  #: Password could not be verified as it's unset server side
    ExternalAccountUnlinked = 57        #: External account (PSN, Facebook...) is not linked to a Steam account
    PSNTicketInvalid = 58               #: PSN ticket was invalid
    ExternalAccountAlreadyLinked = 59   #: External account (PSN, Facebook...) is already linked to some other account, must explicitly request_id to replace/delete the link first
    RemoteFileConflict = 60             #: The sync cannot resume due to a conflict between the local and remote files
    IllegalPassword = 61                #: The requested new password is not legal
    SameAsPreviousValue = 62            #: new value is the same as the old one ( secret question and answer )
    AccountLogonDenied = 63             #: account login denied due to 2nd factor authentication failure
    CannotUseOldPassword = 64           #: The requested new password is not legal
    InvalidLoginAuthCode = 65           #: account login denied due to auth code invalid
    AccountLogonDeniedNoMail = 66       #: account login denied due to 2nd factor auth failure - and no mail has been sent
    HardwareNotCapableOfIPT = 67
    IPTInitError = 68
    ParentalControlRestricted = 69      #: operation failed due to parental control restrictions for current user
    FacebookQueryError = 70             #: Facebook query returned an error
    ExpiredLoginAuthCode = 71           #: account login denied due to auth code expired
    IPLoginRestrictionFailed = 72
    AccountLockedDown = 73
    AccountLogonDeniedVerifiedEmailRequired = 74
    NoMatchingURL = 75
    BadResponse = 76                          #: parse failure, missing field, etc.
    RequirePasswordReEntry = 77               #: The user cannot complete the action until they re-enter their password
    ValueOutOfRange = 78                      #: the value entered is outside the acceptable range
    UnexpectedError = 79                      #: something happened that we didn't expect to ever happen
    Disabled = 80                             #: The requested service has been configured to be unavailable
    InvalidCEGSubmission = 81                 #: The set of files submitted to the CEG server are not valid !
    RestrictedDevice = 82                     #: The device being used is not allowed to perform this action
    RegionLocked = 83                         #: The action could not be complete because it is region restricted
    RateLimitExceeded = 84                    #: Temporary rate limit exceeded, try again later, different from k_EResultLimitExceeded which may be permanent
    AccountLoginDeniedNeedTwoFactor = 85      #: Need two-factor code to login
    ItemDeleted = 86                          #: The thing we're trying to access has been deleted
    AccountLoginDeniedThrottle = 87           #: login attempt failed, try to throttle response to possible attacker
    TwoFactorCodeMismatch = 88                #: two factor code mismatch
    TwoFactorActivationCodeMismatch = 89      #: activation code for two-factor didn't match
    AccountAssociatedToMultiplePartners = 90  #: account has been associated with multiple partners
    NotModified = 91                          #: message not modified
    NoMobileDevice = 92                       #: the account does not have a mobile device associated with it
    TimeNotSynced = 93                        #: the time presented is out of range or tolerance
    SMSCodeFailed = 94                        #: SMS code failure (no match, none pending, etc.)
    AccountLimitExceeded = 95                 #: Too many accounts access this resource
    AccountActivityLimitExceeded = 96         #: Too many changes to this account
    PhoneActivityLimitExceeded = 97           #: Too many changes to this phone
    RefundToWallet = 98                       #: Cannot refund to payment method, must use wallet
    EmailSendFailure = 99                     #: Cannot send an email
    NotSettled = 100                          #: Can't perform operation till payment has settled
    NeedCaptcha = 101                         #: Needs to provide a valid captcha
    GSLTDenied = 102                          #: a game server login token owned by this token's owner has been banned
    GSOwnerDenied = 103                       #: game server owner is denied for other reason (account lock, community ban, vac ban, missing phone)
    InvalidItemType = 104                     #: the type of thing we were requested to act on is invalid
    IPBanned = 105                            #: the ip address has been banned from taking this action
    GSLTExpired = 106                         #: this token has expired from disuse; can be reset for use
    InsufficientFunds = 107                   #: user doesn't have enough wallet funds to complete the action
    TooManyPending = 108                      #: There are too many of this thing pending already
    NoSiteLicensesFound = 109                 #: No site licenses found
    WGNetworkSendExceeded = 110               #: the WG couldn't send a response because we exceeded max network send size
    AccountNotFriends = 111
    LimitedUserAccount = 112
    CantRemoveItem = 113
    AccountHasBeenDeleted = 114
    AccountHasAnExistingUserCancelledLicense = 115


class EUniverse(SteamIntEnum):
    """Doc: https://partner.steamgames.com/doc/api/steam_api#EUniverse"""
    INVALID = 0
    PUBLIC = 1
    BETA = 2
    INTERNAL = 3
    DEV = 4
    RC = 5  #: doesn't exit anymore
    MAX = 6


class EType(SteamIntEnum):
    """Doc: https://partner.steamgames.com/doc/api/steam_api#EAccountType"""
    INVALID = 0         #: Used for invalid Steam IDs
    INDIVIDUAL = 1      #: single user account
    MULTISEAT = 2       #: multiseat (e.g. cybercafe) account
    GAMESERVER = 3      #: game server account
    ANONGAMESERVER = 4  #: anonymous game server account
    PENDING = 5         #: pending
    CONTENTSERVER = 6   #: content server
    CLAN = 7            #: Steam Group (clan)
    CHAT = 8            #: Steam group chat or lobby
    CONSOLEUSER = 9     #: Fake SteamID for local PSN account on PS3 or Live account on 360, etc
    ANONUSER = 10       #: Anonymous user account. (Used to create an account or reset a password)
    MAX = 11


class EInstanceFlag(SteamIntEnum):
    ALL = 0x00000
    OLDCLIENT = 1  # some 2006 clients (steam/steamui 14/147) use 1 for some reason
    MMSLOBBY = 0x20000
    LOBBY = 0x40000
    CLAN = 0x80000


class EVanityUrlType(SteamIntEnum):
    Individual = 1
    Group = 2
    GameGroup = 3

"""enum EServerType : __int32
{
  k_EServerTypeInvalid = 0xFFFFFFFF,
  k_EServerTypeShell = 0x0,
  k_EServerTypeGM = 0x1,
  k_EServerTypeDSObsolete = 0x2,
  k_EServerTypeAM = 0x3,
  k_EServerTypeBS = 0x4,
  k_EServerTypeVS = 0x5,
  k_EServerTypeATS = 0x6,
  k_EServerTypeCM = 0x7,
  k_EServerTypeFBS = 0x8,
  k_EServerTypeFG = 0x9,
  k_EServerTypeSS = 0xA,
  k_EServerTypeDRMS = 0xB,
  k_EServerTypeHubOBSOLETE = 0xC,
  k_EServerTypeConsole = 0xD,
  k_EServerTypeASB = 0xE,
  k_EServerTypeClient = 0xF,
  k_EServerTypeBootstrapOBSOLETE = 0x10,
  k_EServerTypeDP = 0x11,
  k_EServerTypeWG = 0x12,
  k_EServerTypeSM = 0x13,
  k_EServerTypeP2PTracker = 0x14,
  k_EServerTypeUFS = 0x15,
  k_EServerTypeP2PSuperSeeder = 0x16,
  k_EServerTypeUtil = 0x17,
  k_EServerTypeDSS = 0x18,
  k_EServerTypeP2PRelayOBSOLETE = 0x19,
  k_EServerTypeAppInformation = 0x1A,
  k_EServerTypeSpare = 0x1B,
  k_EServerTypeFTS = 0x1C,
  k_EServerTypeEPM = 0x1D,
  k_EServerTypePS = 0x1E,
  k_EServerTypeIS = 0x1F,
  k_EServerTypeCCS = 0x20,
  k_EServerTypeDFS = 0x21,
  k_EServerTypeMax = 0x22,
};
"""

class EServerType(SteamIntEnum):
    Other_Util = -2
    Other_Client = -3
    Other_CServer = -4
    Other_CEconBase = -5
    Invalid = -1
    Shell = 0
    GM = 1
    BUM = 2  # obsolete
    AM = 3  # community webserver
    BS = 4
    VS = 5
    ATS = 6  # stress test server
    CM = 7
    FBS = 8
    BoxMonitor = 9
    SS = 10
    DRMS = 11
    HubOBSOLETE = 12
    Console = 13
    PICS = 14
    Client = 15
    contentstats = 16
    DP = 17  # publisher stats
    WG = 18
    SM = 19
    SLC = 20
    UFS = 21  # file upload/cloud server
    Util = 23
    DSS = 24
    Community = 24
    P2PRelayOBSOLETE = 25
    AppInformation = 26  # app info server
    Spare = 27
    FTS = 28
    SiteLicense = 29
    PS = 30
    IS = 31
    CCS = 32
    DFS = 33
    LBS = 34  # Max for steam 2009
    MDS = 35
    CS = 36
    GC = 37
    NS = 38
    OGS = 39
    WebAPI = 40
    UDS = 41
    MMS = 42 # LOBBY
    GMS = 43
    KGS = 44
    UCM = 45
    RM = 46
    FS = 47
    Econ = 48
    Backpack = 49
    UGS = 50
    StoreFeature = 51
    MoneyStats = 52
    CRE = 53
    UMQ = 54
    Workshop = 55
    BRP = 56
    GCH = 57
    MPAS = 58
    Trade = 59
    Secrets = 60
    Logsink = 61
    Market = 62
    Quest = 63  #EMOTICONs
    WDS = 64
    ACS = 65
    PNP = 66
    TaxForm = 67
    ExternalMonitor = 68
    Parental = 69
    PartnerUpload = 70
    Partner = 71
    ES = 72
    DepotWebContent = 73
    ExternalConfig = 74
    GameNotifications = 75
    MarketRepl = 76
    MarketSearch = 77
    Localization = 78
    Steam2Emulator = 79
    PublicTest = 80
    SolrMgr = 81
    BroadcastIngester = 82
    BroadcastDirectory = 83
    VideoManager = 84
    TradeOffer = 85
    BroadcastChat = 86
    Phone = 87
    AccountScore = 88
    Support = 89
    LogRequest = 90
    LogWorker = 91
    EmailDelivery = 92
    InventoryManagement = 93
    Auth = 94
    StoreCatalog = 95
    HLTVRelay = 96
    IDLS = 97
    Perf = 98
    ItemInventory = 99
    Watchdog = 100
    AccountHistory = 101
    Chat = 102
    Shader = 103
    AccountHardware = 104
    WebRTC = 105
    Giveaway = 106
    ChatRoom = 107
    VoiceChat = 108
    QMS = 109
    Trust = 110
    TimeMachine = 111
    VACDBMaster = 112
    ContentServerConfig = 113
    Minigame = 114
    MLTrain = 115
    VACTest = 116
    TaxService = 117
    MLInference = 118
    UGSAggregate = 119
    TURN = 120
    RemoteClient = 121
    BroadcastOrigin = 122
    BroadcastChannel = 123
    SteamAR = 124
    China = 125
    CrashDump = 126
    Max = 127


class EOSType(SteamIntEnum):
    Unknown = -1
    Web = -700
    IOSUnknown = -600
    IOS1 = -599
    IOS2 = -598
    IOS3 = -597
    IOS4 = -596
    IOS5 = -595
    IOS6 = -594
    IOS6_1 = -593
    IOS7 = -592
    IOS7_1 = -591
    IOS8 = -590
    IOS8_1 = -589
    IOS8_2 = -588
    IOS8_3 = -587
    IOS8_4 = -586
    IOS9 = -585
    IOS9_1 = -584
    IOS9_2 = -583
    IOS9_3 = -582
    IOS10 = -581
    IOS10_1 = -580
    IOS10_2 = -579
    IOS10_3 = -578
    IOS11 = -577
    IOS11_1 = -576
    IOS11_2 = -575
    IOS11_3 = -574
    IOS11_4 = -573
    IOS12 = -572
    IOS12_1 = -571
    AndroidUnknown = -500
    Android6 = -499
    Android7 = -498
    Android8 = -497
    Android9 = -496
    UMQ = -400
    PS3 = -300
    MacOSUnknown = -102
    MacOS104 = -101
    MacOS105 = -100
    MacOS1058 = -99
    MacOS106 = -95
    MacOS1063 = -94
    MacOS1064_slgu = -93
    MacOS1067 = -92
    MacOS107 = -90
    MacOS108 = -89
    MacOS109 = -88
    MacOS1010 = -87
    MacOS1011 = -86
    MacOS1012 = -85
    Macos1013 = -84
    Macos1014 = -83
    Macos1015 = -82
    MacOSMax = -1
    LinuxUnknown = -203
    Linux22 = -202
    Linux24 = -201
    Linux26 = -200
    Linux32 = -199
    Linux35 = -198
    Linux36 = -197
    Linux310 = -196
    Linux316 = -195
    Linux318 = -194
    Linux3x = -193
    Linux4x = -192
    Linux41 = -191
    Linux44 = -190
    Linux49 = -189
    Linux414 = -188
    Linux419 = -187
    Linux5x = -186
    LinuxMax = -101
    WinUnknown = 0
    Win311 = 1
    Win95 = 2
    Win98 = 3
    WinME = 4
    WinNT = 5
    Win2000 = 6
    WinXP = 7
    Win2003 = 8
    WinVista = 9
    Windows7 = 10
    Win2008 = 11
    Win2012 = 12
    Windows8 = 13
    Windows81 = 14
    Win2012R2 = 15
    Windows10 = 16
    Win2016 = 17
    WinMAX = 18
    Max = 26


class EFriendRelationship(SteamIntEnum):
    NONE = 0
    Blocked = 1
    RequestRecipient = 2
    Friend = 3
    RequestInitiator = 4
    Ignored = 5
    IgnoredFriend = 6
    SuggestedFriend_DEPRECATED = 7
    Max = 8


class EAccountFlags(SteamIntEnum):
    NormalUser = 0
    PersonaNameSet = 1
    Unbannable = 2
    PasswordSet = 4
    Support = 8
    Admin = 16
    Supervisor = 32
    AppEditor = 64
    HWIDSet = 128
    PersonalQASet = 256
    VacBeta = 512
    Debug = 1024
    Disabled = 2048
    LimitedUser = 4096
    LimitedUserForce = 8192
    EmailValidated = 16384
    MarketingTreatment = 32768
    OGGInviteOptOut = 65536
    ForcePasswordChange = 131072
    ForceEmailVerification = 262144
    LogonExtraSecurity = 524288
    LogonExtraSecurityDisabled = 1048576
    Steam2MigrationComplete = 2097152
    NeedLogs = 4194304
    Lockdown = 8388608
    MasterAppEditor = 16777216
    BannedFromWebAPI = 33554432
    ClansOnlyFromFriends = 67108864
    GlobalModerator = 134217728
    ParentalSettings = 268435456
    ThirdPartySupport = 536870912
    NeedsSSANextSteamLogon = 1073741824


class EFriendFlags(SteamIntEnum):
    NONE = 0
    Blocked = 1
    FriendshipRequested = 2
    Immediate = 4
    ClanMember = 8
    OnGameServer = 16
    RequestingFriendship = 128
    RequestingInfo = 256
    Ignored = 512
    IgnoredFriend = 1024
    Suggested = 2048
    ChatMember = 4096
    FlagAll = 65535


class EPersonaState(SteamIntEnum):
    Offline = 0
    Online = 1
    Busy = 2
    Away = 3
    Snooze = 4
    LookingToTrade = 5
    LookingToPlay = 6
    Invisible = 7
    Max = 8


class EPersonaStateFlag(SteamIntEnum):
    HasRichPresence = 1
    InJoinableGame = 2
    Golden = 4
    RemotePlayTogether = 8
#   OnlineUsingWeb = 256 obsolete "renamed to ClientTypeWeb"
    ClientTypeWeb = 256
#   OnlineUsingMobile = 512 obsolete "renamed to ClientTypeMobile"
    ClientTypeMobile = 512
#   OnlineUsingBigPicture = 1024 obsolete "renamed to ClientTypeTenfoot"
    ClientTypeTenfoot = 1024
#   OnlineUsingVR = 2048 obsolete "renamed to ClientTypeVR"
    ClientTypeVR = 2048
    LaunchTypeGamepad = 4096
    LaunchTypeCompatTool = 8192


class EClientPersonaStateFlag(SteamIntEnum):
    Status = 1
    PlayerName = 2
    QueryPort = 4
    SourceID = 8
    Presence = 16
    Metadata = 32  # obsolete
    LastSeen = 64
    ClanInfo = 128
    GameExtraInfo = 256
    GameDataBlob = 512
    ClanTag = 1024
    Facebook = 2048
    RichPresence = 4096
    Broadcast = 8192
    Watching = 16384


class ELeaderboardDataRequest(SteamIntEnum):
    Global = 0
    GlobalAroundUser = 1
    Friends = 2
    Users = 3


class ELeaderboardSortMethod(SteamIntEnum):
    NONE = 0
    Ascending = 1
    Descending = 2


class ELeaderboardDisplayType(SteamIntEnum):
    NONE = 0
    Numeric = 1
    TimeSeconds = 2
    TimeMilliSeconds = 3


class ELeaderboardUploadScoreMethod(SteamIntEnum):
    NONE = 0
    KeepBest = 1
    ForceUpdate = 2


class ETwoFactorTokenType(SteamIntEnum):
    NONE = 0
    ValveMobileApp = 1
    ThirdParty = 2


class EChatEntryType(SteamIntEnum):
    """Doc: https://partner.steamgames.com/doc/api/steam_api#EChatEntryType"""
    Invalid = 0
    ChatMsg = 1             #: Normal text message from another user
    Typing = 2              #: Another user is typing (not used in multi-user chat)
    InviteGame = 3          #: Invite from other user into that users current game
    Emote = 4               #: text emote message (deprecated, should be treated as ChatMsg)
    LobbyGameStart = 5      #: lobby game is starting (dead - listen for LobbyGameCreated_t callback instead)
    LeftConversation = 6    #: user has left the conversation ( closed chat window )
    Entered = 7             #: user has entered the conversation (used in multi-user chat and group chat)
    WasKicked = 8           #: user was kicked (message: 64-bit steamID of actor performing the kick)
    WasBanned = 9           #: user was banned (message: 64-bit steamID of actor performing the ban)
    Disconnected = 10       #: user disconnected
    HistoricalChat = 11     #: a chat message from user's chat history or offilne message
    Reserved1 = 12          #: No longer used
    Reserved2 = 13          #: No longer used
    LinkBlocked = 14        #: a link was removed by the chat filter.


class EChatRoomEnterResponse(SteamIntEnum):
    """Doc: https://partner.steamgames.com/doc/api/steam_api#EChatRoomEnterResponse"""
    Success = 1              #: Success
    DoesntExist = 2          #: Chat doesn't exist (probably closed)
    NotAllowed = 3           #: General Denied - You don't have the permissions needed to join the chat
    Full = 4                 #: Chat room has reached its maximum size
    Error = 5                #: Unexpected Error
    Banned = 6               #: You are banned from this chat room and may not join
    Limited = 7              #: Joining this chat is not allowed because you are a limited user (no value on account)
    ClanDisabled = 8         #: Attempt to join a clan chat when the clan is locked or disabled
    CommunityBan = 9         #: Attempt to join a chat when the user has a community lock on their account
    MemberBlockedYou = 10    #: Join failed - some member in the chat has blocked you from joining
    YouBlockedMember = 11    #: Join failed - you have blocked some member already in the chat
    NoRankingDataLobby = 12  #: No longer used
    NoRankingDataUser = 13   #: No longer used
    RankOutOfRange = 14      #: No longer used
    RatelimitExceeded = 15   #: Join failed - to many join attempts in a very short period of time


class ECurrencyCode(SteamIntEnum):
    Invalid = 0
    USD = 1
    GBP = 2
    EUR = 3
    CHF = 4
    RUB = 5
    PLN = 6
    BRL = 7
    JPY = 8
    NOK = 9
    IDR = 10
    MYR = 11
    PHP = 12
    SGD = 13
    THB = 14
    VND = 15
    KRW = 16
    TRY = 17
    UAH = 18
    MXN = 19
    CAD = 20
    AUD = 21
    NZD = 22
    CNY = 23
    INR = 24
    CLP = 25
    PEN = 26
    COP = 27
    ZAR = 28
    HKD = 29
    TWD = 30
    SAR = 31
    AED = 32
    SEK = 33
    ARS = 34
    ILS = 35
    BYN = 36
    KZT = 37
    KWD = 38
    QAR = 39
    CRC = 40
    UYU = 41
    Max = 42


class EDepotFileFlag(SteamIntEnum):
    UserConfig = 1
    VersionedUserConfig = 2
    Encrypted = 4
    ReadOnly = 8
    Hidden = 16
    Executable = 32
    Directory = 64
    CustomExecutable = 128
    InstallScript = 256
    Symlink = 512


class EProtoAppType(SteamIntEnum):
    Invalid = 0
    Game = 1
    Application = 2
    Tool = 4
    Demo = 8
    Deprected = 16
    DLC = 32
    Guide = 64
    Driver = 128
    Config = 256
    Hardware = 512
    Franchise = 1024
    Video = 2048
    Plugin = 4096
    MusicAlbum = 8192
    Series = 16384
    Comic = 32768
    Beta = 65536
    Shortcut = 1073741824
    DepotOnly = -2147483648


class EPublishedFileInappropriateProvider(SteamIntEnum):
    Invalid = 0
    Google = 1
    Amazon = 2


class EPublishedFileInappropriateResult(SteamIntEnum):
    NotScanned = 0
    VeryUnlikely = 1
    Unlikely = 30
    Possible = 50
    Likely = 75
    VeryLikely = 100


class EPublishedFileQueryType(SteamIntEnum):
    RankedByVote = 0
    RankedByPublicationDate = 1
    AcceptedForGameRankedByAcceptanceDate = 2
    RankedByTrend = 3
    FavoritedByFriendsRankedByPublicationDate = 4
    CreatedByFriendsRankedByPublicationDate = 5
    RankedByNumTimesReported = 6
    CreatedByFollowedUsersRankedByPublicationDate = 7
    NotYetRated = 8
    RankedByTotalUniqueSubscriptions = 9
    RankedByTotalVotesAsc = 10
    RankedByVotesUp = 11
    RankedByTextSearch = 12
    RankedByPlaytimeTrend = 13
    RankedByTotalPlaytime = 14
    RankedByAveragePlaytimeTrend = 15
    RankedByLifetimeAveragePlaytime = 16
    RankedByPlaytimeSessionsTrend = 17
    RankedByLifetimePlaytimeSessions = 18
    RankedByInappropriateContentRating = 19


class EUserBadge(SteamIntEnum):
    Invalid = 0
    YearsOfService = 1
    Community = 2
    Portal2PotatoARG = 3
    TreasureHunt = 4
    SummerSale2011 = 5
    WinterSale2011 = 6
    SummerSale2012 = 7
    WinterSale2012 = 8
    CommunityTranslator = 9
    CommunityModerator = 10
    ValveEmployee = 11
    GameDeveloper = 12
    GameCollector = 13
    TradingCardBetaParticipant = 14
    SteamBoxBeta = 15
    Summer2014RedTeam = 16
    Summer2014BlueTeam = 17
    Summer2014PinkTeam = 18
    Summer2014GreenTeam = 19
    Summer2014PurpleTeam = 20
    Auction2014 = 21
    GoldenProfile2014 = 22
    TowerAttackMiniGame = 23
    Winter2015ARG_RedHerring = 24
    SteamAwards2016Nominations = 25
    StickerCompletionist2017 = 26
    SteamAwards2017Nominations = 27
    SpringCleaning2018 = 28
    Salien = 29
    RetiredModerator = 30
    SteamAwards2018Nominations = 31
    ValveModerator = 32
    WinterSale2018 = 33
    LunarNewYearSale2019 = 34
    LunarNewYearSale2019GoldenProfile = 35
    SpringCleaning2019 = 36
    SummerSale2019 = 37
    SummerSale2019_TeamHare = 38
    SummerSale2019_TeamTortoise = 39
    SummerSale2019_TeamCorgi = 40
    SummerSale2019_TeamCockatiel = 41
    SummerSale2019_TeamPig = 42
    SteamAwards2019Nominations = 43
    WinterSaleEvent2019 = 44


class WorkshopEnumerationType(SteamIntEnum):
    RankedByVote = 0
    Recent = 1
    Trending = 2
    FavoriteOfFriends = 3
    VotedByFriends = 4
    ContentByFriends = 5
    RecentFromFollowedUsers = 6


class EPublishedFileVisibility(SteamIntEnum):
    Public = 0
    FriendsOnly = 1
    Private = 2


class EWorkshopFileType(SteamIntEnum):
    First = 0
    Community	= 0
    Microtransaction	= 1
    Collection	= 2
    Art	= 3
    Video	= 4
    Screenshot	= 5
    Game	= 6
    Software	= 7
    Concept	= 8
    WebGuide	= 9
    IntegratedGuide	= 10
    Merch	= 11
    ControllerBinding	= 12
    SteamworksAccessInvite = 13
    SteamVideo = 14
    GameManagedItem = 15
    Max = 16

class EAppType(SteamIntEnum):
    Invalid = 0
    Game = 1
    Application = 2
    Tool = 4
    Demo = 8
    Deprected = 16
    DLC = 32
    Guide = 64
    Driver = 128
    Config = 256
    Hardware = 512
    Franchise = 1024
    Video = 2048
    Plugin = 4096
    Music = 8192
    Series = 16384
    Comic = 32768
    Beta = 65536

    Shortcut = 1073741824
    DepotOnly = -2147483648


class EClientUIMode(SteamIntEnum):
    Desktop = 0
    BigPicture = 1
    Mobile = 2
    Web = 3

class EPurchaseResultDetail(SteamIntEnum):
    NoDetail = 0
    AVSFailure = 1
    InsufficientFunds = 2
    ContactSupport = 3
    Timeout = 4
    InvalidPackage = 5
    InvalidPaymentMethod = 6
    InvalidData = 7
    OthersInProgress = 8
    AlreadyPurchased = 9
    WrongPrice = 10
    FraudCheckFailed = 11
    CancelledByUser = 12
    RestrictedCountry = 13
    BadActivationCode = 14
    DuplicateActivationCode = 15
    UseOtherPaymentMethod = 16
    UseOtherFunctionSource = 17
    InvalidShippingAddress = 18
    RegionNotSupported = 19
    AcctIsBlocked = 20
    AcctNotVerified = 21
    InvalidAccount = 22
    StoreBillingCountryMismatch = 23
    DoesNotOwnRequiredApp = 24
    CanceledByNewTransaction = 25
    ForceCanceledPending = 26
    FailCurrencyTransProvider = 27
    FailedCyberCafe = 28
    NeedsPreApproval = 29
    PreApprovalDenied = 30
    WalletCurrencyMismatch = 31
    EmailNotValidated = 32
    ExpiredCard = 33
    TransactionExpired = 34
    WouldExceedMaxWallet = 35
    MustLoginPS3AppForPurchase = 36
    CannotShipToPOBox = 37
    InsufficientInventory = 38
    CannotGiftShippedGoods = 39
    CannotShipInternationally = 40
    BillingAgreementCancelled = 41
    InvalidCoupon = 42
    ExpiredCoupon = 43
    AccountLocked = 44
    OtherAbortableInProgress = 45
    ExceededSteamLimit = 46
    OverlappingPackagesInCart = 47
    NoWallet = 48
    NoCachedPaymentMethod = 49
    CannotRedeemCodeFromClient = 50
    PurchaseAmountNoSupportedByProvider = 51
    OverlappingPackagesInPendingTransaction = 52
    RateLimited = 53
    OwnsExcludedApp = 54
    CreditCardBinMismatchesType = 55
    CartValueTooHigh = 56
    BillingAgreementAlreadyExists = 57
    POSACodeNotActivated = 58
    CannotShipToCountry = 59
    HungTransactionCancelled = 60
    PaypalInternalError = 61
    UnknownGlobalCollectError = 62
    InvalidTaxAddress = 63
    PhysicalProductLimitExceeded = 64
    PurchaseCannotBeReplayed = 65
    DelayedCompletion = 66
    BundleTypeCannotBeGifted = 67
    BlockedByUSGov = 68
    ItemsReservedForCommercialUse = 69
    GiftAlreadyOwned = 70
    GiftInvalidForRecipientRegion = 71
    GiftPricingImbalance = 72
    GiftRecipientNotSpecified = 73
    ItemsNotAllowedForCommercialUse = 74
    BusinessStoreCountryCodeMismatch = 75
    UserAssociatedWithManyCafes = 76
    UserNotAssociatedWithCafe = 77
    AddressInvalid = 78
    CreditCardNumberInvalid = 79
    CannotShipToMilitaryPostOffice = 80
    BillingNameInvalidResemblesCreditCard = 81
    PaymentMethodTemporarilyUnavailable = 82
    PaymentMethodNotSupportedForProduct = 83


class ELicenseFlags(SteamIntEnum):
    NONE = 0
    Renew = 0x01
    RenewalFailed = 0x02
    Pending = 0x04
    Expired = 0x08
    CancelledByUser = 0x10
    CancelledByAdmin = 0x20
    LowViolenceContent = 0x40
    ImportedFromSteam2 = 0x80
    ForceRunRestriction = 0x100
    RegionRestrictionExpired = 0x200
    CancelledByFriendlyFraudLock = 0x400
    NotActivated = 0x800


class ELicenseType(SteamIntEnum):
    NoLicense = 0
    SinglePurchase = 1
    SinglePurchaseLimitedUse = 2
    RecurringCharge = 3
    RecurringChargeLimitedUse = 4
    RecurringChargeLimitedUseWithOverages = 5
    RecurringOption = 6
    LimitedUseDelayedActivation = 7


class EBillingType(SteamIntEnum):
    NoCost = 0
    BillOnceOnly = 1
    BillMonthly = 2
    ProofOfPrepurchaseOnly = 3
    GuestPass = 4
    HardwarePromo = 5
    Gift = 6
    AutoGrant = 7
    OEMTicket = 8
    RecurringOption = 9
    BillOnceOrCDKey = 10
    Repurchaseable = 11
    FreeOnDemand = 12
    Rental = 13
    CommercialLicense = 14
    FreeCommercialLicense = 15
    NumBillingTypes = 16


class EPaymentMethod(SteamIntEnum):
    NONE = 0
    ActivationCode = 1
    CreditCard = 2
    Giropay = 3
    PayPal = 4
    Ideal = 5
    PaySafeCard = 6
    Sofort = 7
    GuestPass = 8
    WebMoney = 9
    MoneyBookers = 10
    AliPay = 11
    Yandex = 12
    Kiosk = 13
    Qiwi = 14
    GameStop = 15
    HardwarePromo = 16
    MoPay = 17
    BoletoBancario = 18
    BoaCompraGold = 19
    BancoDoBrasilOnline = 20
    ItauOnline = 21
    BradescoOnline = 22
    Pagseguro = 23
    VisaBrazil = 24
    AmexBrazil = 25
    Aura = 26
    Hipercard = 27
    MastercardBrazil = 28
    DinersCardBrazil = 29
    AuthorizedDevice = 30
    MOLPoints = 31
    ClickAndBuy = 32
    Beeline = 33
    Konbini = 34
    EClubPoints = 35
    CreditCardJapan = 36
    BankTransferJapan = 37
#   PayEasyJapan = 38 removed "renamed to PayEasy"
    PayEasy = 38
    Zong = 39
    CultureVoucher = 40
    BookVoucher = 41
    HappymoneyVoucher = 42
    ConvenientStoreVoucher = 43
    GameVoucher = 44
    Multibanco = 45
    Payshop = 46
#   Maestro = 47 removed "renamed to MaestroBoaCompra"
    MaestroBoaCompra = 47
    OXXO = 48
    ToditoCash = 49
    Carnet = 50
    SPEI = 51
    ThreePay = 52
    IsBank = 53
    Garanti = 54
    Akbank = 55
    YapiKredi = 56
    Halkbank = 57
    BankAsya = 58
    Finansbank = 59
    DenizBank = 60
    PTT = 61
    CashU = 62
    AutoGrant = 64
    WebMoneyJapan = 65
    OneCard = 66
    PSE = 67
    Exito = 68
    Efecty = 69
    Paloto = 70
    PinValidda = 71
    MangirKart = 72
    BancoCreditoDePeru = 73
    BBVAContinental = 74
    SafetyPay = 75
    PagoEfectivo = 76
    Trustly = 77
    UnionPay = 78
    BitCoin = 79
    Wallet = 128
    Valve = 129
#   SteamPressMaster = 130 removed "renamed to MasterComp"
    MasterComp = 130
#   StorePromotion = 131 removed "renamed to Promotional"
    Promotional = 131
    MasterSubscription = 134
    Payco = 135
    MobileWalletJapan = 136
    OEMTicket = 256
    Split = 512
    Complimentary = 1024


class EPackageStatus(SteamIntEnum):
    Available = 0
    Preorder = 1
    Unavailable = 2
    Invalid = 3

class NatTypes(SteamIntEnum):
    eNatTypeUntested = 0
    eNatTypeTestFailed = 1
    eNatTypeNoUDP = 2
    eNatTypeOpenInternet = 3
    eNatTypeFullCone = 4
    eNatTypeRestrictedCone = 5
    eNatTypePortRestrictedCone = 6
    eNatTypeUnspecified = 7
    eNatTypeSymmetric = 8
    eNatTypeSymmetricFirewall = 9
    eNatTypeCount = 10

class EIntroducerRouting(SteamIntEnum):
    k_eRouteP2PFileShare = 0x0
    k_eRouteP2PVoiceChat = 0x1
    k_eRouteP2PNetworking = 0x2

class AppInfoSections(SteamIntEnum):
    AppInfoSection_unknown = 0
    AppInfoSection_all = 1
    AppInfoSection_common = 2
    AppInfoSection_first = 2
    AppInfoSection_extended = 3
    AppInfoSection_config = 4
    AppInfoSection_stats = 5
    AppInfoSection_install = 6
    AppInfoSection_depots = 7
    AppInfoSection_VAC = 8
    AppInfoSection_DRM = 9
    AppInfoSection_UFS = 10
    AppInfoSection_OGG = 11
    AppInfoSection_items = 12
    AppInfoSection_policies = 13
    AppInfoSection_sysReqs = 14
    AppInfoSection_community = 15
    AppInfoSection_albummetadata = 16
    AppInfoSection_max = 17

class AppInfoSectionPropagationType(SteamIntEnum):
    AppInfoSectionPropagationType_invalid = 0
    AppInfoSectionPropagationType_public = 1
    AppInfoSectionPropagationType_OwnersOnly = 2
    AppInfoSectionPropagationType_ServerOnly = 3
    AppInfoSectionPropagationType_ClientOnly = 4
    AppInfoSectionPropagationType_ServerAndWGOnly = 5



class AppInfoRequest:
    def __init__(self):
        self.app_id = 0
        self.request_all_sections = False
        self.local_app_info_sections_crc32 = defaultdict(int)

    def __repr__(self):
        return (f"AppInfoRequest(app_id={self.app_id}, "
                f"request_all_sections={self.request_all_sections}, "
                f"local_app_info_sections_crc32={dict(self.local_app_info_sections_crc32)})")

    def __str__(self):
        crc32_str = ", ".join(f"{section}: {crc32}" for section, crc32 in self.local_app_info_sections_crc32.items())
        return (f"App Info Request:\n"
                f"  App ID: {self.app_id}\n"
                f"  Request All Sections: {self.request_all_sections}\n"
                f"  Local App Info Sections CRC32:\n    {crc32_str}")
class AppInfo:
    def __init__(self):
        self.app_id = 0
        self.last_change_number = 0
        self.app_info_sections = defaultdict(lambda: None)

    def __repr__(self):
        return (f"AppInfo(app_id={self.app_id}, "
                f"last_change_number={self.last_change_number}, "
                f"app_info_sections={dict(self.app_info_sections)})")

    def __str__(self):
        sections_str = "\n    ".join(f"{section}: {info}" for section, info in self.app_info_sections.items())
        return (f"App Info:\n"
                f"  App ID: {self.app_id}\n"
                f"  Last Change Number: {self.last_change_number}\n"
                f"  App Info Sections:\n    {sections_str}")


# Do not remove
from enum import EnumMeta

__all__ = [obj.__name__
           for obj in globals().values()
           if obj.__class__ is EnumMeta and obj.__name__ != 'SteamIntEnum'
           ]

del EnumMeta