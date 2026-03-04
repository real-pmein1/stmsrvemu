from steam3.Responses.leaderboard_responses import build_ClientLBSGetEntries_response, build_ClientLBSSetScore_Response, build_ClientLBSFindOrCreate_response
from steam3 import database
from steam3.ClientManager.client import Client
from steam3.cm_packet_utils import CMPacket
from steam3.messages.MsgClientLBSGetLBEntries import MsgClientLBSGetLBEntries
from steam3.messages.MsgClientLBSSetScore import MsgClientLBSSetScore
from steam3.messages.MsgClientLBSFindOrCreateLB import MsgFindOrCreateLB


def handle_ClientLBSFindOrCreate(cmserver_obj, packet: CMPacket, client_obj: Client):
    """packetid: ClientLBSFindOrCreateLB (5416)
       data (raw): b'\xf4\x01\x00\x00\x02\x00\x00\x00\x03\x00\x00\x00\x01l4d_hospital02_subway_holdout\x00'"""
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received Leaderboard Find or Create Request")
    parser = MsgFindOrCreateLB(request.data)

    # lookup or create
    lb = database.get_or_create_leaderboard(
        parser.app_id,
        parser.name,
        parser.sort_method,
        parser.display_type,
        True
    )
    is_proto = packet.is_proto
    if is_proto:
        # obj.some_variable exists
        _is_proto = True
    else:
        # it doesn?t exist
        _is_proto = False

    return build_ClientLBSFindOrCreate_response(client_obj, lb, _is_proto)


def handle_ClientLBSGetLBEntries(cmserver_obj, packet: CMPacket, client_obj):
    """packetid: ClientLBSGetLBEntries (EMsg.ClientLBSGetLBEntries)
       data (raw): packet.CMRequest.data"""
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received Leaderboard Get Entries Request")
    parser = MsgClientLBSGetLBEntries(request.data)
    is_proto = packet.is_proto
    if is_proto:
        # obj.some_variable exists
        _is_proto = True
    else:
        # it doesn?t exist
        _is_proto = False

    return build_ClientLBSGetEntries_response(client_obj,cmserver_obj,parser,request, _is_proto)


def handle_ClientLBSSetScore(cmserver_obj, packet: CMPacket, client_obj):
    """packetid: ClientLBSSetScore (EMsg.ClientLBSSetScore)
       data (raw): packet.CMRequest.data"""
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received Leaderboard Set Score Request")
    parser = MsgClientLBSSetScore(request.data)
    is_proto = packet.is_proto
    if is_proto:
        # obj.some_variable exists
        _is_proto = True
    else:
        # it doesn?t exist
        _is_proto = False

    return build_ClientLBSSetScore_Response(client_obj,parser,request, _is_proto)
