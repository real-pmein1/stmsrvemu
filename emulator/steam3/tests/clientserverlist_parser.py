import struct
from io import BytesIO
from enum import IntEnum
import socket

class EServerType(IntEnum):
    Other_Util = -2
    Other_Client = -3
    Other_CServer = -4
    Other_CEconBase = -5
    Invalid = -1
    Shell = 0
    GM = 1
    BUM = 2
    AM = 3
    BS = 4
    VS = 5
    ATS = 6
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
    DP = 17
    WG = 18
    SM = 19
    SLC = 20
    UFS = 21
    Util = 23
    DSS = 24
    Community = 24
    P2PRelayOBSOLETE = 25
    AppInformation = 26
    Spare = 27
    FTS = 28
    SiteLicense = 29
    PS = 30
    IS = 31
    CCS = 32
    DFS = 33
    LBS = 34
    MDS = 35
    CS = 36
    GC = 37
    NS = 38
    OGS = 39
    WebAPI = 40
    UDS = 41
    MMS = 42
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
    Quest = 63
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

def parse_clientserverlist(buffer: bytes):
    """Parses a buffer containing a list of servers and returns their details."""
    stream = BytesIO(buffer)

    # Read the first 4 bytes to get the server list count
    server_list_count = struct.unpack('<I', stream.read(4))[0]
    print(f"Number of servers: {server_list_count}")

    server_list = []

    # Each server entry is composed of:
    # - 4 byte server type (integer)
    # - 4 byte IP address (network order)
    # - 2 byte port (network order)

    for _ in range(server_list_count):
        # Read the server type (4 bytes)
        server_type_int = struct.unpack('<I', stream.read(4))[0]
        server_type = EServerType(server_type_int) if server_type_int in EServerType.__members__.values() else EServerType.Invalid

        # Read the IP address (4 bytes) and convert it from network byte order
        ip_bytes = stream.read(4)
        ip_address = socket.inet_ntoa(ip_bytes)

        # Read the port (2 bytes) and convert it from network byte order
        port_bytes = stream.read(2)
        port = struct.unpack('!H', port_bytes)[0]

        # Add the server details to the list
        server_list.append({
            "server_type": server_type,
            "ip_address": ip_address,
            "port": port
        })

    return server_list

# Example usage
buffer = struct.pack('<I', 2) + \
         struct.pack('<I', 7) + socket.inet_aton("192.168.0.1") + struct.pack('!H', 27015) + \
         struct.pack('<I', 15) + socket.inet_aton("10.0.0.1") + struct.pack('!H', 27016)

packet = b'p\x03\x00\x00$\x02\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xefmw\xea\x02\x01\x00\x10\x01\xfc\xdf\x8b\x00\x01\x00\x00\x00\x15\x00\x00\x00\x9b=\xa5H\x8ai'

servers = parse_clientserverlist(packet[36:])
for server in servers:
    print(f"Server Type: {server['server_type'].name}, IP: {server['ip_address']}, Port: {server['port']}")