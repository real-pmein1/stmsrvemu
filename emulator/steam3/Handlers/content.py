"""
CM handlers for the Steam3 content system.

These are the two messages a client sends before it can talk to a content
server : one to get the AES key of a depot, and one to get the CDN auth token
it has to attach to its content server requests.
"""

import logging
import struct

from steam3.ClientManager.client import Client
from steam3.Responses.content_responses import build_GetCDNAuthTokenResponse, build_GetDepotDecryptionKeyResponse
from steam3.cm_packet_utils import CMPacket
from steam3.protobufs.steammessages_clientserver_2_pb2 import (CMsgClientGetCDNAuthToken,
                                                               CMsgClientGetDepotDecryptionKey)

log = logging.getLogger('CMContent')


def _get_repository():
    from utilities.steam3_content import get_repository
    return get_repository()


def handle_GetDepotDecryptionKey(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    EMsgClientGetDepotDecryptionKey - hands out the AES key of a Steam3 depot.
    """
    client_address = client_obj.ip_port
    request = packet.CMRequest
    is_proto = packet.is_proto

    if is_proto:
        message = CMsgClientGetDepotDecryptionKey()
        message.ParseFromString(request.data)
        depot_id = message.depot_id
        app_id = message.app_id
    else:
        # deprecated clients send the depot id, optionally followed by the app id
        depot_id = struct.unpack('<I', request.data[:4])[0]
        app_id = struct.unpack('<I', request.data[4:8])[0] if len(request.data) >= 8 else 0

    depot_key = _get_repository().get_depot_key(depot_id)

    if depot_key:
        cmserver_obj.log.info(f"{client_address} Depot Decryption Key Request for depot {depot_id} (app {app_id})")
    else:
        cmserver_obj.log.warning(
                f"{client_address} Depot Decryption Key Request for unknown depot {depot_id} (app {app_id})")

    return build_GetDepotDecryptionKeyResponse(client_obj, depot_id, depot_key, is_proto)


def handle_GetCDNAuthToken(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    EMsgClientGetCDNAuthToken - issues the token the client appends to its
    content server requests as a query string.
    """
    client_address = client_obj.ip_port
    request = packet.CMRequest
    is_proto = packet.is_proto

    host_name = ''

    if is_proto:
        message = CMsgClientGetCDNAuthToken()
        message.ParseFromString(request.data)
        depot_id = message.depot_id
        app_id = message.app_id
        host_name = message.host_name
    else:
        depot_id = struct.unpack('<I', request.data[:4])[0]
        app_id = struct.unpack('<I', request.data[4:8])[0] if len(request.data) >= 8 else 0
        remainder = request.data[8:].split(b'\x00', 1)[0]
        host_name = remainder.decode('latin-1', errors = 'replace')

    steam_id = client_obj.steamID.get_static_steam_global_id() if client_obj.steamID else 0

    token, expires = _get_repository().cdn_tokens.issue(steam_id, app_id, depot_id, host_name)

    cmserver_obj.log.info(
            f"{client_address} CDN Auth Token Request for depot {depot_id} (app {app_id}) on {host_name or 'any host'}")

    return build_GetCDNAuthTokenResponse(client_obj, token, expires, is_proto)
