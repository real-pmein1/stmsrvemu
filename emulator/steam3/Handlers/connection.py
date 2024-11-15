import struct
from utilities import encryption
from config import get_config


def create_channel_encryption_request(cm_packet, cm_packet_reply, connectionid):
    configuration = get_config()
    cm_packet_reply.packetid = b"\x06"
    cm_packet_reply.size = 28
    cm_packet_reply.source_id = cm_packet.destination_id
    cm_packet_reply.destination_id = connectionid
    cm_packet_reply.sequence_num = 3  # seq
    cm_packet_reply.last_recv_seq = 1  # ack
    cm_packet_reply.split_pkt_cnt = 1  # split
    cm_packet_reply.seq_of_first_pkt = 3
    cm_packet_reply.data_len = 28
    cm_packet_reply.data = (b'\x17\x05\x00\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff')# ChannelEncryptRequest 0x0517
    protocol_ver = b'\x01\x00\x00\x00'
    universe = int(configuration['universe']).to_bytes(4, 'little')   #b'\x01\x00\x00\x00'
    cm_packet_reply.data += protocol_ver + universe
    cmidreply = cm_packet_reply.serialize()
    return cmidreply


def handle_challengerequest(cm_packet, cm_packet_reply, client_address, connectionid):
    # Official Steam CM server's probably check to ensure the challenge response from the client is correct.
    # we do this by xoring their xored challenge of the first four bytes of the challenge we sent previously (0x12345678)
    xor_result = encryption.xor_data(cm_packet.data, 0xA426DF2B)

    if int.from_bytes(xor_result, 'little') != 0x12345678:
        # FIXME send something if the challenge doesnt match... unsure what, just close connection?
        return

    cm_packet_reply.packetid = b'\x04'
    cm_packet_reply.size = 0
    cm_packet_reply.message_len = 0
    cm_packet_reply.destination_id = connectionid
    cm_packet_reply.source_id = cm_packet.destination_id
    cm_packet_reply.last_recv_seq = cm_packet.sequence_num
    cm_packet_reply.sequence_num = 2
    cm_packet_reply.split_pkt_cnt = 1
    cm_packet_reply.seq_of_first_pkt = 2
    cm_packet_reply.data = b''
    cmidreply = cm_packet_reply.serialize()
    return cmidreply


def create_conn_acceptresponse(cm_packet, cm_packet_reply):
    cm_packet_reply.packetid = b'\x02'
    cm_packet_reply.size = 8  # Since this is NOT a CMPacket with MsgHdr_deprecated as the .message portion, we only set the size here and leave message_len 0
    cm_packet_reply.data_len = 0
    # Retrieves the chat entry as a dictionary
    cm_packet_reply.destination_id = cm_packet.source_id
    cm_packet_reply.source_id = cm_packet.destination_id
    cm_packet_reply.last_recv_seq = cm_packet.sequence_num
    cm_packet_reply.sequence_num = 1
    cm_packet_reply.split_pkt_cnt = 0
    cm_packet_reply.seq_of_first_pkt = 0
    cm_packet_reply.data = struct.pack('II', 0x12345678, 2) # first 4 bytes are challenge, second 4 are server load
    cmidreply = cm_packet_reply.serialize()
    return cmidreply