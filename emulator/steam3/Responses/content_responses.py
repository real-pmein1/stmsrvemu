import logging
import struct

from steam3.ClientManager.client import Client
from steam3.Types.emsg import EMsg
from steam3.Types.steam_types import EResult
from steam3.cm_packet_utils import CMProtoResponse, CMResponse
from steam3.protobufs.steammessages_clientserver_2_pb2 import (CMsgClientGetCDNAuthTokenResponse,
                                                               CMsgClientGetDepotDecryptionKeyResponse)

log = logging.getLogger('CMContent')


def build_GetDepotDecryptionKeyResponse(client_obj: Client, depot_id, depot_key, is_proto = True):
    """
    Answer EMsgClientGetDepotDecryptionKey with the AES key of a Steam3 depot.

    The key is what the client then uses to decrypt the manifest filenames and
    the depot chunks the content server hands it.
    """
    eresult = EResult.OK if depot_key else EResult.Blocked

    if is_proto:
        packet = CMProtoResponse(eMsgID = EMsg.ClientGetDepotDecryptionKeyResponse, client_obj = client_obj)

        response = CMsgClientGetDepotDecryptionKeyResponse()
        response.eresult = int(eresult)
        response.depot_id = int(depot_id)
        if depot_key:
            response.depot_encryption_key = depot_key

        packet.set_response_message(response)
        packet.data = response.SerializeToString()
        packet.length = len(packet.data)

        return packet

    # deprecated, non protobuf clients : eresult, depot id, then the raw key
    packet = CMResponse(eMsgID = EMsg.ClientGetDepotDecryptionKeyResponse, client_obj = client_obj)
    packet.data = struct.pack('<iI', int(eresult), int(depot_id))
    if depot_key:
        packet.data += depot_key
    packet.length = len(packet.data)

    return packet


def build_GetCDNAuthTokenResponse(client_obj: Client, token, expiration_time, is_proto = True):
    """
    Answer EMsgClientGetCDNAuthToken with the token the client has to append to
    its content server requests.
    """
    eresult = EResult.OK if token else EResult.Blocked

    if is_proto:
        packet = CMProtoResponse(eMsgID = EMsg.ClientGetCDNAuthTokenResponse, client_obj = client_obj)

        response = CMsgClientGetCDNAuthTokenResponse()
        response.eresult = int(eresult)
        response.token = token or ''
        response.expiration_time = int(expiration_time or 0)

        packet.set_response_message(response)
        packet.data = response.SerializeToString()
        packet.length = len(packet.data)

        return packet

    # deprecated, non protobuf clients : eresult, expiration, null terminated token
    packet = CMResponse(eMsgID = EMsg.ClientGetCDNAuthTokenResponse, client_obj = client_obj)
    packet.data = struct.pack('<iI', int(eresult), int(expiration_time or 0))
    packet.data += (token or '').encode('latin-1') + b'\x00'
    packet.length = len(packet.data)

    return packet
