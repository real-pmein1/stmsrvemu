import copy
import struct

from steam3.ClientManager.client import Client
from steam3.Types.steam_types import NatTypes
from steam3.cm_packet_utils import CMPacket


def handle_Heartbeat(cmserver_obj, packet, client_obj, isrequest=True):
    if isinstance(client_obj, tuple):
        client_address = client_obj
    else:
        client_address = client_obj.ip_port
    # cmserver_obj.log.info(f"{client_address}Recieved heartbeat Request")
    cm_packet_reply = copy.copy(packet)
    cm_packet_reply.packetid = b'\x07'
    cm_packet_reply.size = 0
    cm_packet_reply.data_len = 0
    cm_packet_reply.destination_id = packet.source_id
    cm_packet_reply.source_id = packet.destination_id
    cm_packet_reply.last_recv_seq = packet.sequence_num
    cm_packet_reply.sequence_num = 0
    cm_packet_reply.split_pkt_cnt = 0
    cm_packet_reply.seq_of_first_pkt = 0
    cm_packet_reply.data = struct.pack('I', 0x00000000)

    cmidreply = cm_packet_reply.serialize()
    #cmserver_obj.serversocket.send(cmidreply, to_log = False)
    cmserver_obj.serversocket.sendto(cmidreply, client_address)
    return -1


def handle_SystemIMAck(cmserver_obj, packet: CMPacket, client_obj: Client):
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved System Message Acknowledgement")
    # unpack 64bit messageid, this packet is just acknowledgement that it recieved the SystemIM, If the SystemIM had the ack flag set to true
    messageID = struct.unpack('<Q', request.data)
    return -1  # we do nothing here


def handle_VTTCert(cmserver_obj, packet: CMPacket, client_obj: Client):
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved VTTCert Message")

    request = packet.CMRequest
    # Validate input data length at minimum for 3 4-byte integers
    if len(request.data) < 12:
        raise ValueError("Even the simplest packet seems over your head. I've seen more bytes in a diet plan.")

    # Unpack the first three 4-byte integers
    try:
        total_num_certs, num_bad_certs, cert_found = struct.unpack('<III', request.data[:12])
    except struct.error:
        raise ValueError("Looks like someone's struggling with basic data structures.")

    # Apparently, displaying numbers is also a task, so here you go:
    print(f"Integer 1: {total_num_certs} (Congratulations, you managed to unpack an integer!)")
    print(f"Integer 2: {num_bad_certs} (Wow, two in a row, you're on a roll!)")
    print(f"Integer 3: {cert_found} (Thrice the charm, or just a lucky strike?)")

    # Check if the third integer is not 0 and you actually have more data
    if cert_found != 0:
        if len(request.data) < 12 + 0x8c:
            raise ValueError("Got excited and promised more bytes than you could handle, huh?")

        # Unpack the byte array of size 0x8c (140 bytes), since we're doing everything else
        public_key = struct.unpack(f'<{0x8c}s', request.data[12:12 + 0x8c])[0]
        print(f"Byte Array: {public_key} (Look at you, unpacking bytes like a pro... Not!)")
    else:
        print("Third integer is a zero, which is probably higher than your success rate in programming.")

    return -1


def handle_ServiceCallResponse(cmserver_obj, packet: CMPacket, client_obj: Client):
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved Service Call Response")
    request = packet.CMRequest

    try:
        CallHandle, CallResult = struct.unpack('<II', request.data[:8])
        parameters = 0
        if len(request.data[8:]) > 0:
            parameters = request.data[8:]

        parameters = max(parameters, 0)

        cmserver_obj.log.debug(f"({client_address[0]}: Call Handler: {CallHandle} Result {CallResult}\n Parameters: {parameters}")
    except:
        raise ValueError("Looks like someone's struggling with basic data structures.")

    return -1


def handle_NatTraversalStatEvent(cmserver_obj, packet: CMPacket, client_obj: Client):
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved Nat Traversal Stat Event")
    request = packet.CMRequest
    # packetid: 839, steamui 427
    # b'\x04\x00\x00\x00 \x02\x00\x00\x00 \x00\x00\x00\x00 \x00\x00 \x00\x00'
    eResult, localNatType, remoteNatType, MultiUserChat, Relay = struct.unpack('<IIIHH', request.data)
    localNatType = NatTypes(localNatType)
    remoteNatType = NatTypes(remoteNatType)
    cmserver_obj.log.debug(f"({client_address[0]}:{client_address[1]}): Result: {eResult}, NatTypes: {NatTypes}, MultiUserChat: {MultiUserChat}, Relay: {Relay}")
    return -1


def handle_MultiMessage(cmserver_obj, packet: CMPacket, client_obj: Client):
    pass