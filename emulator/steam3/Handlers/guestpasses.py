import struct

from steam3.ClientManager.client import Client
from steam3.Responses.guestpass_responses import build_SendAckGuestPassResponse, build_SendGuestPassResponse
from steam3.Types.steam_types import EResult
from steam3.cm_packet_utils import CMPacket


def handle_SendGuestPass(cmserver_obj, packet: CMPacket, client_obj: Client):
    """packetid: 739
    b'\x00\x00\x00\x00\x00\x00\x00\x00 GID
    \x00 isResend
    \xff\xff\xff\xff accountid
    shefben@gmail.com\x00'"""
    request = packet.CMRequest
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved Send Guest Pass Request")
    client_obj.logoff_User(cmserver_obj)
    unpack_fmt = "<QBI"
    giftID, isResend, accountID = struct.unpack_from(unpack_fmt, request.data, 0)

    emailAddr = request.data[struct.calcsize(unpack_fmt):-1]

    # TODO send guestpass email!

    return [build_SendGuestPassResponse(client_obj, EResult.OK)]


def handle_AckGuestPass(cmserver_obj, packet: CMPacket, client_obj: Client):
    """packetid: 739
    b'\x00\x00\x00\x00\x00\x00\x00\x00 GID
    \x00 isResend
    \xff\xff\xff\xff accountid
    shefben@gmail.com\x00'"""
    request = packet.CMRequest
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved Guest Pass Acknowledgment")
    client_obj.logoff_User(cmserver_obj)
    unpack_fmt = "<Q"
    guestpassKey = struct.unpack_from(unpack_fmt, request.data, 0)

    # TODO do something with the guestpass key

    return [build_SendAckGuestPassResponse(client_obj, EResult.OK)]

def handle_RedeemGuestPass(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    struct MsgClientRedeemGuestPass_t
    {
      GID_t m_gidGuestPassID;
    };
    """
    request = packet.CMRequest
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved Guest Pass Redemption Request")
    client_obj.logoff_User(cmserver_obj)
    unpack_fmt = "<Q"
    guestpassID = struct.unpack_from(unpack_fmt, request.data, 0)

    # TODO grab packageID from database using guestpassID

    return [build_SendAckGuestPassResponse(client_obj, EResult.OK)]