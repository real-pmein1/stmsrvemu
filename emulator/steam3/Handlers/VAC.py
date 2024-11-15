import struct

from steam3.cm_packet_utils import CMResponse


def handle_VACResponse(cmserver_obj, packet, client_obj):
    client_address = client_obj.ip_port
    # respond with 753? or 770
    request = packet.CMRequest
    cmserver_obj.log.info(f"Client Requested vac response")
    packet = CMResponse()
    packet.eMsgID = 0x0302

    # Preparing packet data
    data = bytearray()
    data.extend(struct.pack('I', request.accountID))
    data.extend(struct.pack('I', request.clientId2))
    data.extend(struct.pack('I', request.sessionID))

    num_vac_bans = 1
    data.extend(struct.pack('I', num_vac_bans))

    packet.length = len(data)
    packet.data = bytes(data)

    return packet


def ClientVacStatusResponse(cmserver_obj, packet, client_obj):
    client_address = client_obj.ip_port
    return -1