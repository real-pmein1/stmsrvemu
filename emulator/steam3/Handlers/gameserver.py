import socket
import struct
from steam3.Types.Objects.PreProtoBuf.gameConnectToken import GameConnectToken
from steam3.Types.community_types import PlayerState
from steam3.Types.steamid import SteamID

from steam3 import database
from steam3.ClientManager.client import Client
from steam3.Responses.gameserver_responses import (
    build_GSApprove, build_GSDeny, build_GSGetUserAchievementStatusResponse,
    build_GSResponse, build_GSAssociateWithClanResponse
)
from steam3.cm_packet_utils import CMPacket
from steam3.messages.MsgGSApprove import MsgGSApprove
from steam3.messages.MsgGSUserPlaying2 import MsgGSUserPlaying2
from steam3.messages.MsgGSUserPlaying3 import MsgGSUserPlaying3
from steam3.messages.MsgClientGameConnect_obsolete import MsgClientGameConnect_obsolete
from steam3.messages.MsgClientGameEnded_obsolete import MsgClientGameEnded_obsolete
from utilities import server_stats
from utilities.database import statistics_db

# packetid: 908: GSServerType
# b'@\x01\x00\x00 \x02\x00\x00\x00 \x00\x00\x00\x00 \x87i hl2mp\x001.0.0.12\x00\x87i'
def handle_GS_ServerType(cmserver_obj, packet: CMPacket, client_obj: Client):
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved GS Server Type Information")
    # might contain the following:
    #   appid
    #   flags
    #   game ip
    #   game port

    # for sure contains the following:
    #   game dir
    #   version
    #   game server query port

    try:
        appId, server_flags, ipServer, portServer = struct.unpack_from('<IIIH', request.data, 0)
        # FIXME check if port and server are supposed to be in reverse positions

        # Calculate offset for the first string; it starts after the first 14 bytes
        offset = 14

        # Find null terminator for the appName string
        appName_end = request.data.index(b'\x00', offset)
        appName = request.data[offset:appName_end].decode('utf-8')

        # Calculate offset for the next string; it starts right after appName + null terminator
        offset = appName_end + 1

        # Find null terminator for the appVersion string
        appVersion_end = request.data.index(b'\x00', offset)
        appVersion = request.data[offset:appVersion_end].decode('utf-8')
        query_port, = struct.unpack_from('<H',request.data[appVersion_end:appVersion_end+2])
        cmserver_obj.log.debug(f"Remaining bytes: query port {query_port}")
        cmserver_obj.log.debug(f"appid: {appId}, appName: {appName}, appVersion: {appVersion}\n"
                            f"server_flags: {server_flags}, ipServer: {ipServer}, portServer: {portServer}")
    except Exception as e:
        cmserver_obj.log.error(f"gs servertype: {e}")
        pass

    return [build_GSResponse(client_obj)]


# packetid: 907: GSStatusUpdate_Unused
# b'\x00\x00\x00\x00 \x10\x00\x00\x00 \x00\x00\x00\x00 \x00\x00\x00\x00 Half-Life 2: Deathmatch dedicated server\x00dm_lockdown\x00'
# b'\x00\x00\x00\x00\x10\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00Half-Life 2: Deathmatch dedicated server\x00dm_lockdown\x00'
def handle_GS_StatusUpdate(cmserver_obj, packet: CMPacket, client_obj: Client):
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved GS Status Update")
    request = packet.CMRequest
    data = request.data
    format_str = '<IIII'  # Corresponds to four DWORDs
    try:
        playercount, maxplayers, totalbots, unknown1 = struct.unpack_from(format_str, data, 0)

        # Calculate the starting position of the appName string
        offset = 16  # After the first 3 DWORDs (4 bytes each)

        # Find null terminator for the appName string
        appName_end = data.index(b'\x00', offset)
        appName = data[offset:appName_end].decode('latin-1')

        # Calculate offset for the mapName string; it starts right after appName + null terminator
        offset = appName_end + 1

        # Find null terminator for the mapName string
        mapName_end = data.index(b'\x00', offset)
        mapName = data[offset:mapName_end].decode('latin-1')
        cmserver_obj.log.debug(f"playercount: {playercount}, maxplayers: {maxplayers}, totalbots: {totalbots}\n unknown1: {unknown1}, appName: {appName}, mapName: {mapName}")
        cmserver_obj.log.debug(f"Rest of packet: {data[mapName_end:]}")
    except Exception as e:
        cmserver_obj.log.error(f"gs status update error: {e}")
        pass

    return [build_GSResponse(client_obj)]


def handle_GS_PlayerList(cmserver_obj, packet: CMPacket, client_obj: Client):
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received GS Player List")

    request = packet.CMRequest
    data = request.data
    offset = 0  # Use an offset to track position in the binary data

    # Read the count of players (4 bytes, little-endian)
    count, = struct.unpack_from('<I', data, offset)
    offset += 4

    players = []  # List to store player information

    for _ in range(count):
        # Create a new player object
        player = {"playerGlobalId": (struct.unpack_from('<Q', data, offset))[0], "publicIp": None, "token": None}

        # Read player data
        offset += 8  # Move past 8 bytes (int64) and 4 bytes (int32)

        player["publicIp"], = struct.unpack_from('>I', data, offset)
        offset += 4

        # Read token length (4 bytes, little-endian)
        token_len, = struct.unpack_from('<I', data, offset)
        offset += 4

        if token_len:
            if token_len != GameConnectToken.SIZE:
                raise Exception("Invalid game connect token size")

            # Read the token (token_len bytes)
            player["token"] = data[offset:offset + token_len]
            offset += token_len  # Move past the token data

        # Add the player to the list
        players.append(player)

    cmserver_obj.log.info(f"Parsed {len(players)} players.")
    # Not sure how i came up with the code below...
    """# Define the struct format for a single player entry
    player_format = 'Qii'  # steamID (Q), ip (i), game connect token (i)
    player_size = struct.calcsize(player_format)  # Calculate the size of one player's data block

    # Initialize offset to start reading data
    offset = 0
    players = []
    try:
        # Loop through the data, reading one player entry at a time
        while offset + player_size <= len(data):  # Ensure there's enough data left to read another player
            # Unpack the data for one player from the current offset
            steamid, ip, game_token = struct.unpack_from(player_format, data, offset)
            offset += player_size  # Move the offset by the size of one player entry

            # Convert IP from int to standard dotted-quad string if necessary
            ip_address = socket.inet_ntoa(struct.pack('!I', ip))

            # Append the parsed data to the players list
            player_info = {
                'steamID': steamid,
                'ip': ip_address,
                'game_connect_token': game_token
            }
            players.append(player_info)

        # Log the number of players processed
        cmserver_obj.log.info(f"Processed {len(players)} players")
    except Exception as e:
        cmserver_obj.log.error(f"gs player list: {e}")
        pass"""
    return -1


def handle_GS_UserPlaying(cmserver_obj, packet: CMPacket, client_obj: Client):
    """Mark the user as playing on a game server (GSUserPlaying / GSUserPlaying3)."""
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received GS User Playing")
    request = packet.CMRequest
    userplaying_msg = MsgGSUserPlaying3()
    userplaying_msg.parse(request.data)

    tokens = server_stats.list_connection_tokens(userplaying_msg.game_connect_token.steamGlobalId)
    if any(t['token'] == userplaying_msg.game_connect_token.token for t in tokens):
        return build_GSApprove(client_obj, userplaying_msg.game_connect_token)
    return build_GSDeny(client_obj, userplaying_msg.game_connect_token.steamGlobalId, 1, "Invalid token")


def handle_GS_UserPlaying2(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Mark the user as playing on a game server (older GSUserPlaying2 format).

    This handler is for older Steam clients that send GSUserPlaying2 (EMsg 904)
    with a fixed-size token format instead of the variable-length format.
    """
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received GS User Playing 2 (legacy)")
    request = packet.CMRequest
    userplaying_msg = MsgGSUserPlaying2()
    userplaying_msg.parse(request.data)

    if userplaying_msg.game_connect_token is None:
        cmserver_obj.log.warning(f"GSUserPlaying2: No valid game connect token in message")
        return build_GSDeny(client_obj, 0, 1, "Invalid token")

    tokens = server_stats.list_connection_tokens(userplaying_msg.game_connect_token.steamGlobalId)
    if any(t['token'] == userplaying_msg.game_connect_token.token for t in tokens):
        return build_GSApprove(client_obj, userplaying_msg.game_connect_token)
    return build_GSDeny(client_obj, userplaying_msg.game_connect_token.steamGlobalId, 1, "Invalid token")


def handle_GS_DisconnectNotice(cmserver_obj, packet: CMPacket, client_obj: Client):
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved GS Disconnect Notice")
    accountID = request.accountID
    statistics_db.record_gameplay('disconnect', accountID)
    client_obj.disconnect_Game(cmserver_obj)
    return -1


def handle_GS_GetUserAchievementStatus(cmserver_obj, packet: CMPacket, client_obj: Client):
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved GS User Achievement Status Request")

    # Initialize offset to keep track of position in the buffer
    offset = 0

    # Parse Steam ID (8 bytes, little-endian)
    steamID, = SteamID.from_integer(struct.unpack_from('<Q', request.data, offset))
    offset += 8

    # Parse achievement string until null byte
    null_terminator_index = request.data.find(b'\x00', offset)
    if null_terminator_index == -1:
        cmserver_obj.log.error(f"Achievement string not null-terminated: {request.data}")

    achievement = request.data[offset:null_terminator_index].decode('utf-8')
    offset = null_terminator_index + 1  # Move past the null byte

    unlocked = statistics_db.get_user_achievement_status(steamID.as_64, client_obj.appID, achievement)
    return build_GSGetUserAchievementStatusResponse(client_obj, steamID, achievement, unlocked)


# packetid: 719: ClientGameConnect_obsolete
def handle_ClientGameConnect_obsolete(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle client notification of connecting to a game server.

    This is an obsolete message (EMsg 719) sent by older Steam clients to notify
    the CM server that they are initiating a connection to a game server.

    No response is required - this is a fire-and-forget notification.
    """
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received ClientGameConnect_obsolete")

    try:
        msg = MsgClientGameConnect_obsolete()
        msg.deserialize(request.data)

        cmserver_obj.log.debug(
            f"Client connecting to game server:\n"
            f"  Game Server SteamID: {msg.game_server_steam_id}\n"
            f"  Game Server IP: {msg.ip_to_string()}\n"
            f"  Game Server Port: {msg.game_server_port}\n"
            f"  Query Port: {msg.query_port}\n"
            f"  Secure: {msg.secure}\n"
            f"  Token Length: {msg.token_length}"
        )

        # Record the gameplay session start
        statistics_db.record_gameplay('connect', client_obj.accountID)

    except Exception as e:
        cmserver_obj.log.error(f"ClientGameConnect_obsolete parse error: {e}")

    # No response required for this message
    return -1


# packetid: 721: ClientGameEnded_obsolete
def handle_ClientGameEnded_obsolete(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle client notification of ending/disconnecting from a game server.

    This is an obsolete message (EMsg 721) sent by older Steam clients to notify
    the CM server that they have ended their session with a game server.

    No response is required - this is a fire-and-forget notification.
    """
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received ClientGameEnded_obsolete")

    try:
        msg = MsgClientGameEnded_obsolete()
        msg.deserialize(request.data)

        cmserver_obj.log.debug(
            f"Client ended game session:\n"
            f"  Game Server SteamID: {msg.game_server_steam_id}\n"
            f"  Game Server IP: {msg.ip_to_string()}\n"
            f"  Game Server Port: {msg.game_server_port}\n"
            f"  Query Port: {msg.query_port}\n"
            f"  Secure: {msg.secure}\n"
            f"  Token Length: {msg.token_length}"
        )

        # Record the gameplay session end
        statistics_db.record_gameplay('disconnect', client_obj.accountID)

        # Clean up client game state
        client_obj.disconnect_Game(cmserver_obj)

    except Exception as e:
        cmserver_obj.log.error(f"ClientGameEnded_obsolete parse error: {e}")

    # No response required for this message
    return -1


def handle_GS_AssociateWithClan(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle GSAssociateWithClan request (EMsg 938).

    Associates a game server with a specific Steam clan/group.
    This allows the clan to track game server activity and members.

    Binary format:
        - uint64 m_ulSteamIDClan (8 bytes) - Steam ID of the clan to associate with

    Returns GSAssociateWithClanResponse (EMsg 939) with result code.
    """
    from steam3.messages.MsgGSAssociateWithClan import MsgGSAssociateWithClan
    from steam3.Types.steam_types import EResult

    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received GSAssociateWithClan")

    try:
        msg = MsgGSAssociateWithClan()
        msg.deserialize(request.data)

        cmserver_obj.log.debug(f"Game server associating with clan: {msg.steam_id_clan:016x}")

        # Check if the clan exists (extract account ID from SteamID - low 32 bits)
        clan = database.get_clan_by_id(msg.steam_id_clan & 0xFFFFFFFF)

        if clan:
            # Store the association in the client object
            client_obj.associated_clan_id = msg.steam_id_clan
            cmserver_obj.log.info(f"Game server associated with clan {clan.clan_name} ({msg.steam_id_clan:016x})")
            return [build_GSAssociateWithClanResponse(client_obj, msg.steam_id_clan, EResult.OK)]
        else:
            cmserver_obj.log.warning(f"Clan {msg.steam_id_clan:016x} not found")
            return [build_GSAssociateWithClanResponse(client_obj, msg.steam_id_clan, EResult.Fail)]

    except Exception as e:
        cmserver_obj.log.error(f"GSAssociateWithClan error: {e}")
        return [build_GSAssociateWithClanResponse(client_obj, 0, EResult.Fail)]
