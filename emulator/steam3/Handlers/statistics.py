import struct

from steam3.ClientManager.client import Client
from steam3.Responses.statistics_responses import build_GetUserStatsResponse, build_GetUserStats_response, build_StoreUserStats_response, build_StatsUpdated_notification
from steam3.Types.GameID import GameID
from steam3.Types.Objects import hwsurvey
from steam3.Types.community_types import PlayerState
from steam3.Types.keyvalue_class import KeyValueClass
from steam3.Types.steam_types import EResult
from steam3.cm_packet_utils import CMPacket
from steam3.messages.MsgClientConnectionStats import MsgClientConnectionStats
from steam3.messages.MsgClientGamesPlayedWithDataBlob import MsgClientGamesPlayed_WithDataBlob
from steam3.messages.MsgClientNoUDPConnectivity import MsgClientNoUDPConnectivity
from steam3.messages.MsgClientStat2 import MsgClientStat2
from steam3.messages.MSGClientGetUserStats import MSGClientGetUserStats
from steam3.messages.MSGClientStoreUserStats import MSGClientStoreUserStats
from steam3.Managers.StatsManager import StatsManager
from steam3.utilities import reverse_bytes
from steam3.Responses.general_responses import build_GeneralAck
from utilities.database import statistics_db


def handle_ConnectionStats(cmserver_obj, packet: CMPacket, client_obj: Client):
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved Connection Stats Request")
    data = request.data

    try:
        stats = MsgClientConnectionStats(data)
        statistics_db.log_event('connection_stats', stats.__dict__)
    except Exception:
        try:
            attempts, successes, failures, dropped = struct.unpack_from('IIIIIII', data, 0)
            cmserver_obj.log.debug(f"Attempts: {attempts}, Successes: {successes}, Failures: {failures}, Dropped: {dropped}")
            statistics_db.log_event('connection_stats', {
                'attempts': attempts,
                'successes': successes,
                'failures': failures,
                'dropped': dropped
            })
        except Exception as e:
            cmserver_obj.log.error(f"connection stats: {e}")
            pass

    build_GeneralAck(client_obj,packet,client_address,cmserver_obj)

    return -1


def handle_GamesPlayedStats(cmserver_obj, packet: CMPacket, client_obj: Client):
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Games Played Stats Request")
    data = request.data
    first_part = '<QQIHHI'
    game_count, = struct.unpack_from('<I', data, 0)
    if game_count > 0:
        offset = 4
        for _ in range(game_count):
            try:
                steamid, gameid, server_ip, server_port, issecure, token_size = struct.unpack_from(first_part, data, offset)
                offset += struct.calcsize(first_part)
                token = data[offset:offset + token_size]
                offset += token_size
                cmserver_obj.log.debug(
                    f"steamid: {steamid}, gameid: {gameid}, server_ip: {server_ip}, server_port: {server_port}, token: {token}"
                )
                client_obj.update_status_info(cmserver_obj, PlayerState.online, gameid, server_ip, server_port, steamid)
                statistics_db.record_gameplay(gameid, steamid)
            except Exception:
                cmserver_obj.log.error(f"handle_GamesPlayedStats error: {data}")
                break
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
    if start:
        offset = 4
        for _ in range(start):
            try:
                appNB, unknown1, appID, unknown2 = struct.unpack_from('<IIII', data, offset)
                offset += struct.calcsize('<IIII')
                cmserver_obj.log.debug(f"appId: {appID}, unknown1: {unknown1}, unknown2: {unknown2}")
                statistics_db.record_gameplay(appID, client_obj.steamID)
            except Exception:
                break

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
        offset = 4
        for _ in range(game_count):
            try:
                steamid, gameid, server_ip, server_port, issecure, processID, token_size = struct.unpack_from(first_part, data, offset)
                offset += struct.calcsize(first_part)
                token = data[offset:offset + token_size]
                offset += token_size
                cmserver_obj.log.debug(
                    f"steamid: {steamid}, gameid: {gameid}, server_ip: {server_ip}, server_port: {server_port}, processID: {processID}, token: {token}"
                )
                client_obj.update_status_info(cmserver_obj, PlayerState.online, gameid, server_ip, server_port, steamid)
                statistics_db.record_gameplay(gameid, steamid)
                if processID:
                    statistics_db.log_event('gamesplayed2', {
                        'steamid': steamid,
                        'gameid': gameid,
                        'server_ip': server_ip,
                        'server_port': server_port,
                        'process_id': processID,
                    })
            except Exception:
                cmserver_obj.log.error(f"handle_GamesPlayedStats2 error: {data}")
                break
    else:
        client_obj.exit_app()

    build_GeneralAck(client_obj,packet,client_address,cmserver_obj)

    return -1


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
        if len(data) > 32 and token_size != 0:
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
    request = packet.CMRequest

    try:
        # Structure: int usage_type, uint64 game_id, bool offline, zero terminated string
        usage_type, game_id, offline = struct.unpack_from('<IQB', request.data, 0)
        message = request.data[13:].split(b"\x00", 1)[0].decode("latin-1")
    except struct.error as e:
        cmserver_obj.log.error(f"app usage event parse error: {e} {request.data}")
        return -1

    b = f"type:{usage_type} game:{game_id} offline:{offline} message:{message}\n"
    if usage_type == 1:
        cmserver_obj.log.info(f"{b}User is launching app")
        client_obj.update_status_info(cmserver_obj, PlayerState.online, game_id)

    elif usage_type == 2:
        if 'dedicated' in message.lower():
            cmserver_obj.log.info(f"{b}User is starting a dedicated server")
        else:
            cmserver_obj.log.info(f"{b}User is launching trial or tool app")
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

    #build_GeneralAck(client_obj,packet,client_address,cmserver_obj)
    return -1


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

            survey_data = {}
            for key, value in kv_parser.data.items():
                if key in ("SubKeyStart", "SubKeyEnd"):
                    continue
                if isinstance(value, tuple):
                    survey_data[key] = value[0]
                else:
                    survey_data[key] = value

            country_val = survey_data.get("country")
            if isinstance(country_val, int):
                country_bytes = country_val.to_bytes(4, "little")
                survey_data["country"] = country_bytes.split(b"\x00", 1)[0].decode("ascii", errors="ignore")

            statistics_db.record_s3surveydata(survey_data)

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
        deserializer = MsgClientGamesPlayed_WithDataBlob(data)
        payload = {k: v for k, v in deserializer.__dict__.items() if k != "buffer"}
        statistics_db.log_event("games_played_blob", payload)
    except Exception as e:
        cmserver_obj.log.error(f"games played with game blob: {e}")
        pass
    return -1


def handle_GetUserStats(cmserver_obj, packet: CMPacket, client_obj: Client):
    """Handles the ClientGetUserStats packet."""
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved User Stats Info")
    request = packet.CMRequest

    try:
        # Unpack: 8 bytes gameID, 4 bytes stats_crc, 4 bytes local_schema_version.
        gameID_int, stats_crc, local_schema_version = struct.unpack_from('<QII', request.data)
        steamid_raw = request.data[16:]
        cmserver_obj.log.debug(f"appId: {gameID_int}, version: {local_schema_version}, crc: {stats_crc}")
        result = EResult.OK
    except Exception as e:
        cmserver_obj.log.error(f"get user status error: {e}")
        result = EResult.Fail
        gameID_int = 0
        steamid_raw = b"\x00"
        local_schema_version = 0

    return build_GetUserStatsResponse(client_obj, result, gameID_int, steamid_raw, local_schema_version)


def handle_NoUDPConnectivity(cmserver_obj, packet, client_obj):
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved No UDP Connectivity Info")
    request = packet.CMRequest

    message = MsgClientNoUDPConnectivity(request.data)
    statistics_db.log_event('connection_stats', message.__dict__)

    """We do nothing, this is just the client telling us that NO UDP connectivity was possible..?"""
    #build_GeneralAck(client_obj,packet,client_address,cmserver_obj)
    return -1


def handle_ClientStat2(cmserver_obj, packet, client_obj):
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved Client Stats 2 Info")
    request = packet.CMRequest

    message = MsgClientStat2()
    message.parse(request.data)
    statistics_db.log_event('client_stat2', message.__dict__)

    build_GeneralAck(client_obj,packet,client_address,cmserver_obj)
    return -1


# Global stats manager instance
_stats_manager = None

def get_stats_manager():
    """Get or create the global stats manager instance"""
    global _stats_manager
    if _stats_manager is None:
        _stats_manager = StatsManager()
    return _stats_manager


def handle_ClientGetUserStats(cmserver_obj, packet: CMPacket, client_obj: Client):
    """Handle ClientGetUserStats packet (EMsg 818)"""
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received ClientGetUserStats")
    
    try:
        # Parse the request
        msg = MSGClientGetUserStats(client_obj, request.data)
        
        # Get the target steam ID (0 means requesting own stats)
        target_steamid = msg.steamGlobalId if msg.steamGlobalId != 0 else client_obj.steamID
        
        cmserver_obj.log.debug(f"GetUserStats: gameID={msg.gameID}, target_steamid={target_steamid}, "
                              f"local_version={msg.schemaLocalVersion}, crc={msg.statsCrc}")
        
        # Get stats manager and retrieve user stats
        stats_manager = get_stats_manager()
        try:
            user_stats = stats_manager.get_user_stats(target_steamid, msg.gameID)
        except Exception as e:
            cmserver_obj.log.error(f"Error getting user stats: {e}")
            user_stats = None
        
        if user_stats:
            # Always attach schema as raw binary data (don't parse it)
            # Compute current CRC
            try:
                user_stats.computeCrc()
                result = EResult.OK
            except Exception as e:
                cmserver_obj.log.error(f"Error computing CRC: {e}")
                result = EResult.Fail
        else:
            result = EResult.Fail
        
        # Get raw schema data to attach to response
        schema_data = stats_manager.get_raw_schema_data(msg.gameID)
        
        # Build and send response with schema data
        response = build_GetUserStats_response(client_obj, result, msg.gameID, user_stats, schema_data)

    except Exception as e:
        cmserver_obj.log.error(f"Error handling ClientGetUserStats: {e}")
        # Send failure response
        response = build_GetUserStats_response(client_obj, EResult.Fail, 0, None, b"")
        return response
    
    return response


def handle_ClientStoreUserStats(cmserver_obj, packet: CMPacket, client_obj: Client):
    """Handle ClientStoreUserStats packet (EMsg 820)"""
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received ClientStoreUserStats")
    
    try:
        # Parse the request
        msg = MSGClientStoreUserStats(client_obj, request.data)
        
        cmserver_obj.log.debug(f"StoreUserStats: gameID={msg.gameID}, statsCount={len(msg.stats)}, "
                              f"explicitReset={msg.explicitReset}")
        
        # Get stats manager and update user stats
        stats_manager = get_stats_manager()
        failed_validation_stats = {}
        
        result = stats_manager.update_user_stats(
            client_obj.steamID,
            msg.gameID, 
            msg.stats, 
            msg.explicitReset, 
            failed_validation_stats
        )
        
        # Get updated CRC
        stats_crc = stats_manager.get_stats_crc(client_obj.steamID, msg.gameID)
        
        # Build and send response
        response = build_StoreUserStats_response(
            client_obj, result, msg.gameID, stats_crc, failed_validation_stats
        )

        # If successful, notify any connected game servers
        if result != EResult.Fail:
            # Find game servers this player is connected to
            from steam3.Types.wrappers import GameID
            game_id_obj = GameID(msg.gameID)
            app_id = game_id_obj.getAppId()
            
            # TODO: Get list of servers player is connected to
            # For now, we'll skip the notification as we need the server connection tracking
            
            cmserver_obj.log.debug(f"Successfully stored stats for steamid {client_obj.steamID}, "
                                  f"gameID {msg.gameID}, new CRC: {stats_crc}")
        
    except Exception as e:
        cmserver_obj.log.error(f"Error handling ClientStoreUserStats: {e}")
        # Send failure response
        response = build_StoreUserStats_response(client_obj, EResult.Fail, 0, 0, {})
        return response
    
    return response


def handle_ClientStoreUserStats2(cmserver_obj, packet: CMPacket, client_obj: Client):
    """Handle ClientStoreUserStats2 packet (EMsg 5466) - newer version"""
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received ClientStoreUserStats2")
    
    # For now, treat it the same as the original StoreUserStats
    # The format might be slightly different but the logic should be similar
    return handle_ClientStoreUserStats(cmserver_obj, packet, client_obj)