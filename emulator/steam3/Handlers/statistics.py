import struct

from steam3.ClientManager.client import Client
from steam3.Types.Objects import hwsurvey
from steam3.Types.community_types import PlayerState
from steam3.Types.keyvalue_class import KeyValueClass
from steam3.cm_packet_utils import CMPacket
from steam3.messages.MsgClientConnectionStats import MsgClientConnectionStats
from steam3.messages.MsgClientGamesPlayedWithDataBlob import MsgClientGamesPlayed_WithDataBlob
from steam3.messages.MsgClientNoUDPConnectivity import MsgClientNoUDPConnectivity
from steam3.utilities import reverse_bytes
from steam3.Responses.general_responses import build_GeneralAck


def handle_ConnectionStats(cmserver_obj, packet: CMPacket, client_obj: Client):
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved Connection Stats Request")
    data = request.data

    # TODO store stats somewhere, add check for newer versions with more information
    try:
        stats = MsgClientConnectionStats(data)
        print(stats)
    except:
        try:
            attempts, successes, failures, dropped = struct.unpack_from('IIIIIII', data, 0)
            cmserver_obj.log.debug(f"Attempts: {attempts}, Successes: {successes}, Failures: {failures}, Dropped: {dropped}")
        except Exception as e:
            cmserver_obj.log.error(f"connection stats: {e}")
            pass

    build_GeneralAck(client_obj,packet,client_address,cmserver_obj)

    return -1


#packetid: 742
#b'\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x14\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
#or
# b'\x01\x00\x00\x00 \x00\x00\x00\x00\x00\x00\x00\x00 \xcd\x00\x00\x00\x00\x00\x00\x00 \x00\x00\x00\x00 \x00\x00 \x00\x00 \x00\x00\x00\x00 \x00'
# from launching tf2 dedicated server on steamui 484:
# handle_GamesPlayedStats error: b'\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x006\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
def handle_GamesPlayedStats(cmserver_obj, packet: CMPacket, client_obj: Client):
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Games Played Stats Request")
    data = request.data
    first_part = '<QQIHHI'
    game_count, = struct.unpack_from('<I', data, 0)
    if game_count > 0:
        # FIXME make it loop if more than 1 game is listen in the packet
        try:
            game_count, steamid, gameid, server_ip, server_port, issecure, token_size = struct.unpack_from(first_part, data, 4)
            size_body = struct.calcsize(first_part)
            token = data[size_body:] # FIXME can either be a 4 byte int or variable length blob, depending if gameid is a mod or not
            cmserver_obj.log.debug(f"game_count: {game_count}, steamid: {steamid}, gameid: {gameid}, server_ip: {server_ip}, server_port: {server_port}, issecure: {issecure}, token: {token}")
            client_obj.update_status_info(cmserver_obj, PlayerState.online, gameid, server_ip, server_port, steamid)
        except:
            cmserver_obj.log.error(f"handle_GamesPlayedStats error: {data}")
            pass
    else:
        client_obj.exit_app(cmserver_obj)

    build_GeneralAck(client_obj,packet,client_address,cmserver_obj)

    return -1


def handle_GamesPlayedStats_deprecated(cmserver_obj, packet: CMPacket, client_obj: Client):
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Games Played Stats Request")
    data = request.data
    start, = struct.unpack_from('<I', data, 0)
    # FIXME make it loop if more than 1 game is listen in the packet
    if start:
        # If 'start' is non-zero, unpack the remaining DWORDs
        appNB, unknown1, appID, unknown2 = struct.unpack_from('<IIII', data, 4)

        # TODO figure out the unknowns!
        print(f"number of apps: {appNB}, appId: {appID}, unknown1: {unknown1}, unknown2: {unknown2}")

    build_GeneralAck(client_obj,packet,client_address,cmserver_obj)

    return -1


def handle_GamesPlayedStats2(cmserver_obj, packet: CMPacket, client_obj: Client):
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved Games Played 2 stats")
    request = packet.CMRequest
    data = request.data
    first_part = '<QQIHHII'
    game_count, = struct.unpack_from('<I', data, 0)
    # TODO processID is only in 2009+ clients i think... could be that it ISNT used in gamesplayedstats (the non-deprecated version)
    if game_count > 0:
        try:
            steamid, gameid, server_ip, server_port, issecure, processID, token_size = struct.unpack_from(first_part, data, 4)
            size_body = struct.calcsize(first_part)
            token = data[size_body:] # FIXME can either be a 4 byte int or variable length blob, depending if gameid is a mod or not
            cmserver_obj.log.debug(f"game_count: {game_count}, steamid: {steamid}, gameid: {gameid}, server_ip: {server_ip}, server_port: {server_port}, issecure: {issecure}, processID: {processID}, toke: {token}")

            client_obj.update_status_info(cmserver_obj, PlayerState.online, gameid, server_ip, server_port, steamid)
        except:
            cmserver_obj.log.error(f"handle_GamesPlayedStats2 error: {data}")
            pass
    else:
        client_obj.exit_app()

    build_GeneralAck(client_obj,packet,client_address,cmserver_obj)

    return -1
#packetid: 738
# \xe2\x02\x00\x00
# \x10\x00\x00\x00
# \x01\x00\x10\x01
# \x00\x00\x00\x00
# b'\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00F\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
def handle_GamesPlayedStats3(cmserver_obj, packet: CMPacket, client_obj: Client):
    client_address = client_obj.ip_port
    request = packet.CMRequest

    # Assuming eMsgID.data is a bytes-like object containing the binary data.
    data = request.data
    token_or_blob = b''
    # Unpack the first DWORD (4 bytes) as unsigned int with little-endian format.
    start, = struct.unpack_from('<I', data, 0)

    if start:
        # Unpack the following DWORDs and WORDs according to their offsets.
        GSSteamID, appId, serverIp, serverPort, issecure, token_size = struct.unpack_from('<QQIHHI', data, 4)
        if data > 32 and token_size != 0:
            token_or_blob = data[32:]
        packedIp = struct.pack("!I", serverIp)

        print(f"iteration count: {int(start)} GSSteamID {GSSteamID}, appId: {appId}, serverIp {serverIp}, serverPort {serverPort}\n"
              f"is secure: {issecure}, token_size: {token_size}, Server IP: {cmserver_obj.serversocket.inet_ntoa(packedIp)}\n"
              f"token or blob: {token_or_blob}")

        client_obj.update_status_info(cmserver_obj, PlayerState.online, appId, serverIp, serverPort, GSSteamID)
    else:
        client_obj.exit_app(cmserver_obj)

    build_GeneralAck(client_obj,packet,client_address,cmserver_obj)
    return -1


def handle_AppUsageEvent(cmserver_obj, packet: CMPacket, client_obj):
    client_address = client_obj.ip_port
    # Unpack the first 8 bytes of eMsgID.data to get type and app
    request = packet.CMRequest
    usage_type, app = struct.unpack_from('<II', request.data, 0)
    message = request.data[13:].decode('latin-1')  # Assuming message encoding is Latin-1
    b = f"type:{usage_type} app:{app} message:{message}\n"
    if usage_type == 1:
        cmserver_obj.log.info(f"{b}User is launching app")
        client_obj.update_status_info(cmserver_obj, PlayerState.online, app)
    elif usage_type == 2:
        cmserver_obj.log.info(f"{b}User is launching trial or tool app") # FIXME this also triggers for 'tools' like dedicated servers
    elif usage_type == 3:
        cmserver_obj.log.info(f"{b}User is playing media")
    elif usage_type == 4:
        cmserver_obj.log.info(f"{b}User is starting preload")
    elif usage_type == 5:
        cmserver_obj.log.info(f"{b}User finished preload")
    elif usage_type == 6:
        cmserver_obj.log.info(f"{b}User seen marketing message (advertisement/news)")
    elif usage_type == 7:
        cmserver_obj.log.info(f"{b}User seen in-game advertisement")
    elif usage_type == 8:
        cmserver_obj.log.info(f"{b}User launched free weekend application")
    else:
        cmserver_obj.log.info(f"{b}Unknown user action")

    build_GeneralAck(client_obj,packet,client_address,cmserver_obj)
    return -1

# packetid: 842
# b'\x01\x00\x00\x002\x00\x00\x00\x00event\x00\x01msg\x00conflict_deniedops_presell\x00\x02sec\x00\x02\x00\x00\x00\x08\x08'
# b'\x01\x00\x00\x00%\x00\x00\x00\x00event\x00\x01msg\x00ej_corner_152\x00\x02sec\x00\x00\x00\x00\x00\x08\x08'
# survey:
#data: b'\x02\x00\x00\x00\xa1\x05\x00\x00\x00WizardData\x00\x02NetSpeed\x00\x00\x00\x00\x00\x05NetSpeedLabel\x00\x0b\x00\x00\x00D\x00o\x00n\x00\'\x00t\x00 \x00K\x00n\x00o\x00w\x00\x00\x00\x02Microphone\x00\xff\xff\xff\xff\x05MicrophoneLabel\x00\x0b\x00\x00\x00D\x00o\x00n\x00\'\x00t\x00 \x00k\x00n\x00o\x00w\x00\x00\x00\x01CPUVendor\x00GenuineIntel\x00\x02CPUSpeed\x00\xb8\x0b\x00\x00\x02LogicalProcessors\x00\x08\x00\x00\x00\x02PhysicalProcessors\x00\x08\x00\x00\x00\x02HyperThreading\x00\x00\x00\x00\x00\x02FCMOV\x00\x01\x00\x00\x00\x02SSE2\x00\x01\x00\x00\x00\x02SSE3\x00\x01\x00\x00\x00\x02SSE4\x00\x01\x00\x00\x00\x02SSE4a\x00\x00\x00\x00\x00\x02SSE41\x00\x01\x00\x00\x00\x02SSE42\x00\x01\x00\x00\x00\x01OSVersion\x00Windows\x00\x02Is64BitOS\x00\x01\x00\x00\x00\x02OSType\x00\x00\x00\x00\x00\x02NTFS\x00\x01\x00\x00\x00\x01AdapterDescription\x00NVIDIA GeForce RTX 3050\x00\x01DriverVersion\x0030.0.15.1179\x00\x01DriverDate\x002022-2-10\x00\x02VRAMSize\x00\xff\x1f\x00\x00\x02BitDepth\x00 \x00\x00\x00\x02RefreshRate\x00\xa5\x00\x00\x00\x02NumMonitors\x00\x02\x00\x00\x00\x02NumDisplayDevices\x00\x02\x00\x00\x00\x02MonitorWidthInPixels\x00\x00\n\x00\x00\x02MonitorHeightInPixels\x00\xa0\x05\x00\x00\x02DesktopWidthInPixels\x008\x0e\x00\x00\x02DesktopHeightInPixels\x00\x80\x07\x00\x00\x02MonitorWidthInMillimeters\x00\xb9\x02\x00\x00\x02MonitorHeightInMillimeters\x00\x88\x01\x00\x00\x02MonitorDiagonalInMillimeters\x00\x1f\x03\x00\x00\x01VideoCard\x00NVIDIA GeForce RTX 3050\x00\x01DXVideoCardDriver\x00nvldumd.dll\x00\x01DXVideoCardVersion\x0030.0.15.1179\x00\x02DXVendorID\x00\xde\x10\x00\x00\x02DXDeviceID\x00\x07%\x00\x00\x01MSAAModes\x002x 4x 8x \x00\x02MultiGPU\x00\x00\x00\x00\x00\x02NumSLIGPUs\x00\x01\x00\x00\x00\x02DisplayType\x00\x00\x00\x00\x00\x02BusType\x00\x03\x00\x00\x00\x02BusRate\x00\x08\x00\x00\x00\x02dell_oem\x00\x00\x00\x00\x00\x01AudioDeviceDescription\x00Speakers (Realtek(R) Audio)\x00\x02RAM\x00\xb9\x7f\x00\x00\x02LanguageId\x00\x00\x00\x00\x00\x02DriveType\x00\x02\x00\x00\x00\x02TotalHD\x00\x82\xab*\x01\x02FreeHD\x00\x17i\x08\x00\x02SteamHDUsage\x00/\x00\x00\x00\x01OSInstallDate\x001969-12-31\x00\x01GameController\x00None\x00\x02NonSteamApp_firefox\x00\x00\x00\x00\x00\x02NonSteamApp_openoffice\x00\x00\x00\x00\x00\x02NonSteamApp_wfw\x00\x00\x00\x00\x00\x02NonSteamApp_za\x00\x00\x00\x00\x00\x02NonSteamApp_f4m\x00\x00\x00\x00\x00\x02NonSteamApp_cog\x00\x00\x00\x00\x00\x02NonSteamApp_pd\x00\x00\x00\x00\x00\x02NonSteamApp_vmf\x00\x00\x00\x00\x00\x02NonSteamApp_grl\x00\x00\x00\x00\x00\x02NonSteamApp_fv\x00\x00\x00\x00\x00\x07machineid\x00\xb0dU"B\xfe\xc2H\x02version\x00\x10\x00\x00\x00\x02country\x00US\x00\x00\x00ownership\x00\x08\x08\x08',
def handle_ClientSteamUsageEvent(cmserver_obj, packet: CMPacket, client_obj: Client):
    """enum SteamUsageEvent
{
	SteamUsageEvent_marketingMessageView=1,
	SteamUsageEvent_hardwareSurvey=2,
	SteamUsageEvent_downloadStarted=3,
	SteamUsageEvent_localizedAudioChange=4
};"""
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received Steam Usage Event")
    request = packet.CMRequest

    data_length = len(request.data)
    cmserver_obj.log.info(f"Data Length: {data_length}")
    cmserver_obj.log.info(f"Data: {request.data}")

    if data_length >= 8:
        event_type, event_length = struct.unpack_from("<II", request.data, 0)
        cmserver_obj.log.info(f"Event Type: {event_type}, Event Length: {event_length}")
        if event_type == 2:
            survey_info = hwsurvey.WizardData(request.data[8:])

        if data_length >= event_length + 8:
            keyvalue_bin = request.data[8:event_length + 8]

            # Example processing (assuming KeyValueClass is defined)
            kv_parser = KeyValueClass()
            kv_parser.parse(keyvalue_bin)
            cmserver_obj.log.info(f"Parsed Data: {kv_parser.data}")

            # Acknowledge the packet (assuming build_GeneralAck is defined)
            build_GeneralAck(client_obj,packet,client_address,cmserver_obj)
        else:
            cmserver_obj.log.error("Data buffer is smaller than expected event length.")
    else:
        cmserver_obj.log.error("Data buffer is too small to unpack event type and length.")

    return -1

def handle_GamesPlayedWithDataBlob(cmserver_obj, packet: CMPacket, client_obj: Client):
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved Games Played (with blob) info")
    request = packet.CMRequest
    data = request.data
    try:
        # TODO DO SOMETHING WITH THIS INFORMATION!
        deserializer = MsgClientGamesPlayed_WithDataBlob(data)
        print(deserializer)
    except Exception as e:
        cmserver_obj.log.error(f"games played with game blob: {e}")
        pass
    return -1


def handle_GetUserStats(cmserver_obj, packet: CMPacket, client_obj: Client):
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved User Stats Info")
    request = packet.CMRequest

    # TODO This is supposed to have a key/value type of packet info
    # TODO this looks like it holds acheivement info and MUCH more info than that
    try:
        appId, version, crc = struct.unpack_from('<QII', request.data)
        cmserver_obj.log.debug(f"appId: {appId}, version: {version}, crc: {crc}")
    except Exception as e:
        cmserver_obj.log.error(f"get user status: {e}")
        pass

    build_GeneralAck(client_obj,packet,client_address,cmserver_obj)

    return -1


def handle_NoUDPConnectivity(cmserver_obj, packet, client_obj):
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved No UDP Connectivity Info")
    request = packet.CMRequest

    # FIXME store this information somewhere!
    message = MsgClientNoUDPConnectivity(request.data)
    print(message)

    """We do nothing, this is just the client telling us that NO UDP connectivity was possible..?"""
    build_GeneralAck(client_obj,packet,client_address,cmserver_obj)
    return -1
