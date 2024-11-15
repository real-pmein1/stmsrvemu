import socket
import struct

from steam3 import database
from steam3.ClientManager.client import Client
from steam3.Responses.gameserver_responses import build_GSResponse
from steam3.cm_packet_utils import CMPacket
from steam3.utilities import getAccountId


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
    format_str = '<IIIII'  # Corresponds to four DWORDs
    try:
        playercount, maxplayers, totalbots, unknown1, unknown2 = struct.unpack_from(format_str, data, 0)

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
        cmserver_obj.log.debug(f"playercount: {playercount}, maxplayers: {maxplayers}, totalbots: {totalbots}\n unknown1: {unknown1}, unknown2: {unknown2}, appName: {appName}, mapName: {mapName}")
        cmserver_obj.log.debug(f"Rest of packet: {data[mapName_end:]}")
    except Exception as e:
        cmserver_obj.log.error(f"gs status update: {e}")
        pass

    return [build_GSResponse(client_obj)]



def handle_GS_PlayerList(cmserver_obj, packet: CMPacket, client_obj: Client):
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved GS Player List")
    request = packet.CMRequest
    data = request.data

    # Define the struct format for a single player entry
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
        pass
    return -1

def handle_GS_UserPlaying(cmserver_obj, packet: CMPacket, client_obj: Client):
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved GS User Playing")
    request = packet.CMRequest
    # FIXME might only contain the following: steamID, public ip and game connect token; 'QII'
    # TODO EMSG GSUserplaying3 (GSUserPlaying = 905) AKA user connected to game server:
    #    CClientMsg<MsgGSUserPlaying3_t>::Body(&clientMsg)->m_unIPPublic = unIPPublic;
    #    CClientMsg<MsgGSUserPlaying3_t>::Body(&clientMsg)->m_cubGameConnectToken = cubCookie;
    #    CMsgBase_t<ExtendedClientMsgHdr_t>::AddVariableLenData(&clientMsg, pvCookie, cubCookie);
    return -1

def handle_GS_DisconnectNotice(cmserver_obj, packet: CMPacket, client_obj: Client):
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved GS Disconnect Notice")
    accountid = getAccountId(request)
    client_obj.disconnect_Game(cmserver_obj)
    return -1