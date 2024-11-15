import struct

from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse


def build_vacbanstatus(client_obj, firstappid, lastappid, is_version2 = False):
    """
    Build a chat eMsgID packet with eMsgID 0x030E.
    num_vac_bans IS uint numBans;
    """
    if is_version2:
        packet = CMResponse(eMsgID = EMsg.ClientVACBanStatus2, client_obj = client_obj)
    else:
        packet = CMResponse(eMsgID = EMsg.ClientVACBanStatus, client_obj = client_obj)

    packet.data = struct.pack('II',
                            firstappid,
                            lastappid) # appid 10-80 = goldsrc ban, 220-320 = src ban
    #data.extend(struct.pack('II', 220, 320)) # appid 10-80 = goldsrc ban, 220-320 = src ban

    return packet


def build_vacban_status_response(client_obj, serversocket):
    """
    Build a chat eMsgID packet with eMsgID 0x030E.
    num_vac_bans IS uint numBans;
    OR it might be a list of appid's at 4 byte integers
    """
    packet = CMResponse(eMsgID = 0x030E, client_obj = client_obj)

    num_vac_bans = 0

    packet.data = struct.pack('I',
                            num_vac_bans)

    return packet


def build_vacban_challenge(client_obj):
    #respond with 753? or 770
    print("Client Requested vac response")
    packet = CMResponse(eMsgID = 0x02f1, client_obj = client_obj)

    num_vac_bans = 0
    packet.data = struct.pack('I',
                            num_vac_bans)

    return packet