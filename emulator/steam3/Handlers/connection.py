import logging
import struct
from utilities import encryption
from config import get_config

from steam3.messages.responses.MsgChannelEncryptRequest import MsgChannelEncryptRequest
from steam3.messages.responses.MsgChannelEncryptResult import MsgChannelEncryptResult, EResult
from steam3.messages.MsgChannelEncryptResponse import MsgChannelEncryptResponse
from steam3.messages.responses.SNetChallengeMsg import SNetChallengeMsg
from steam3.messages.responses.SNetConnectSuccessMsg import SNetConnectSuccessMsg
from steam3.messages.SNetMsgBase import (
    ESNetMsg, CHALLENGE_XOR_KEY, validate_challenge
)

log = logging.getLogger("ConnectionHandler")


class PacketValidationError(Exception):
    """Raised when packet validation fails."""
    pass


def validate_challenge_request(cm_packet) -> bool:
    """
    Validate a ChallengeReq packet (type 0x01) according to tinserver rules.

    From tinserver UdpNetServerSocket::onChallengeRequest:
        - length must be 0
        - sequence must be 1
        - ack must be 0
        - messagePacketsCount must be 0

    Args:
        cm_packet: The incoming CMPacket

    Returns:
        True if valid, False otherwise
    """
    # Check data length - should be 0 for ChallengeReq
    if cm_packet.size != 0 or (cm_packet.data and len(cm_packet.data) > 0):
        log.warning(f"ChallengeReq validation failed: length={cm_packet.size} (expected 0)")
        return False

    # Check sequence number - must be 1
    if cm_packet.sequence_num != 1:
        log.warning(f"ChallengeReq validation failed: sequence={cm_packet.sequence_num} (expected 1)")
        return False

    # Check ack - must be 0
    if cm_packet.last_recv_seq != 0:
        log.warning(f"ChallengeReq validation failed: ack={cm_packet.last_recv_seq} (expected 0)")
        return False

    # Check split packet count - must be 0 for ChallengeReq
    if cm_packet.split_pkt_cnt != 0:
        log.warning(f"ChallengeReq validation failed: split_pkt_cnt={cm_packet.split_pkt_cnt} (expected 0)")
        return False

    return True


def validate_connect_request(cm_packet) -> bool:
    """
    Validate a Connect packet (type 0x03) according to tinserver rules.

    From tinserver UdpNetServerSocket::onConnectionRequest:
        - length must be 4 (contains unmasked challenge)
        - sequence must be 1 or 2
        - ack must be 1
        - messagePacketsCount must be 1

    Args:
        cm_packet: The incoming CMPacket

    Returns:
        True if valid, False otherwise
    """
    # Check data length - should be 4 bytes (challenge value)
    if cm_packet.size != 4:
        log.warning(f"Connect validation failed: length={cm_packet.size} (expected 4)")
        return False

    if not cm_packet.data or len(cm_packet.data) < 4:
        log.warning(f"Connect validation failed: data too short ({len(cm_packet.data) if cm_packet.data else 0} bytes)")
        return False

    # Check sequence number - must be 1 or 2
    if cm_packet.sequence_num not in (1, 2):
        log.warning(f"Connect validation failed: sequence={cm_packet.sequence_num} (expected 1 or 2)")
        return False

    # Check ack - must be 1 (ACKing our Challenge packet)
    if cm_packet.last_recv_seq != 1:
        log.warning(f"Connect validation failed: ack={cm_packet.last_recv_seq} (expected 1)")
        return False

    # Check split packet count - must be 1 for Connect
    if cm_packet.split_pkt_cnt != 1:
        log.warning(f"Connect validation failed: split_pkt_cnt={cm_packet.split_pkt_cnt} (expected 1)")
        return False

    return True


def create_channel_encryption_request(cm_packet, cm_packet_reply, connectionid, client_obj=None):
    """
    Create ChannelEncryptRequest message to initiate encrypted channel handshake.

    This is sent as a Data (0x06) packet after the connection is established.
    The client will respond with MsgChannelEncryptResponse containing an
    RSA-encrypted session key.

    Message structure (28 bytes):
        MsgHdr_t (20 bytes): EMsg=0x517, targetJobID=-1, sourceJobID=-1
        MsgChannelEncryptRequest_t (8 bytes): protocol_version, universe

    Args:
        cm_packet: The incoming Connect packet (or None for TCP)
        cm_packet_reply: Reply packet to populate
        connectionid: Connection ID for the client
        client_obj: Client object for dynamic sequence tracking
    """
    configuration = get_config()

    # Create the message using the proper message class
    encrypt_request = MsgChannelEncryptRequest(
        protocol_version=1,  # Protocol version 1 is the max supported
        universe=int(configuration['universe'])
    )

    if cm_packet and not cm_packet.is_tcp:
        cm_packet_reply.packetid = bytes([ESNetMsg.Data])  # 0x06
        cm_packet_reply.size = MsgChannelEncryptRequest.TOTAL_SIZE  # 28 bytes
        cm_packet_reply.source_id = cm_packet.destination_id
        cm_packet_reply.destination_id = connectionid

        # Sequence handling for ChannelEncryptRequest
        # This comes after Accept (seq=2), so this is seq=3
        if client_obj:
            cm_packet_reply.sequence_num = client_obj.get_next_sequence_number()
            cm_packet_reply.last_recv_seq = client_obj.last_recvd_sequence
        else:
            # Fallback - should not happen in normal flow
            cm_packet_reply.sequence_num = 3
            cm_packet_reply.last_recv_seq = cm_packet.sequence_num if cm_packet else 0

        cm_packet_reply.split_pkt_cnt = 1
        cm_packet_reply.seq_of_first_pkt = cm_packet_reply.sequence_num
        cm_packet_reply.data_len = MsgChannelEncryptRequest.TOTAL_SIZE

    cm_packet_reply.data = encrypt_request.serialize()
    cmidreply = cm_packet_reply.serialize()
    return cmidreply


def create_channel_encryption_result(result: int = EResult.OK) -> bytes:
    """
    Create ChannelEncryptResult message to confirm encryption handshake.

    This is sent after successfully decrypting and validating the client's
    session key from MsgChannelEncryptResponse.

    Message structure (24 bytes):
        MsgHdr_t (20 bytes): EMsg=0x519, targetJobID=-1, sourceJobID=-1
        MsgChannelEncryptResult_t (4 bytes): result (1=OK)

    Args:
        result: EResult code (1=OK for success)

    Returns:
        Serialized 24-byte message
    """
    encrypt_result = MsgChannelEncryptResult(result=result)
    return encrypt_result.serialize()


def parse_channel_encryption_response(data: bytes) -> MsgChannelEncryptResponse:
    """
    Parse ChannelEncryptResponse message from client.

    The response contains the RSA-encrypted session key.

    Args:
        data: Raw packet data (starting after CMPacket header for UDP,
              or after VT01 header for TCP)

    Returns:
        Parsed MsgChannelEncryptResponse object

    Raises:
        ValueError: If data is too short or malformed
    """
    return MsgChannelEncryptResponse.deserialize(data)


def handle_connect_request(cm_packet, cm_packet_reply, client_address, connectionid):
    """
    Handle Connect request from client (type 0x03).

    The client sends the UNMASKED challenge value (4 bytes).
    We validate against current and previous challenge values.

    If valid, we respond with Accept (type 0x04) to confirm the connection.

    From tinserver UdpNetServerSocket::onConnectionRequest:
        - Validates packet fields first (done in validate_connect_request)
        - Extracts challenge as DWORD from data
        - Validates against getChallenge() and previousChallenge
        - Only creates connection AFTER validation passes
        - Sends Accept with seq=2, ack=client_seq

    Args:
        cm_packet: Incoming Connect packet from client
        cm_packet_reply: Reply packet to populate
        client_address: Client's network address
        connectionid: Connection ID to assign

    Returns:
        Serialized Accept packet, or None if validation fails
    """
    # First validate packet structure
    if not validate_connect_request(cm_packet):
        log.warning(f"Connect packet validation failed from {client_address}")
        return None

    # Extract the unmasked challenge value from the packet data
    # Client sends the raw challenge value (NOT XORed)
    challenge_from_client = struct.unpack('<I', cm_packet.data[:4])[0]

    # Validate against current and previous challenge
    if not validate_challenge(challenge_from_client):
        log.warning(f"Challenge validation failed from {client_address}: "
                   f"received 0x{challenge_from_client:08X}")
        return None

    log.info(f"Challenge validated successfully from {client_address}")

    # Create Accept response using message class
    connect_success = SNetConnectSuccessMsg()

    cm_packet_reply.packetid = bytes([ESNetMsg.Accept])  # 0x04
    cm_packet_reply.size = 0
    cm_packet_reply.data_len = 0
    cm_packet_reply.destination_id = connectionid
    cm_packet_reply.source_id = cm_packet.destination_id
    # ACK the client's Connect packet
    cm_packet_reply.last_recv_seq = cm_packet.sequence_num
    # Server's second packet in handshake (first was Challenge seq=1)
    cm_packet_reply.sequence_num = 2
    cm_packet_reply.split_pkt_cnt = 1
    cm_packet_reply.seq_of_first_pkt = 2
    cm_packet_reply.data = connect_success.serialize()

    cmidreply = cm_packet_reply.serialize()
    return cmidreply


# Keep old function name as alias for backwards compatibility
handle_challengerequest = handle_connect_request


def handle_challenge_request(cm_packet, cm_packet_reply):
    """
    Handle ChallengeReq from client (type 0x01) and respond with Challenge (type 0x02).

    From tinserver UdpNetServerSocket::onChallengeRequest:
        - Validates packet fields (length=0, seq=1, ack=0, messagePacketsCount=0)
        - Responds with Challenge containing masked challenge + server load
        - Challenge is seq=1, ack=1

    Args:
        cm_packet: Incoming ChallengeReq packet from client
        cm_packet_reply: Reply packet to populate

    Returns:
        Serialized Challenge packet, or None if validation fails
    """
    # Validate packet structure according to tinserver rules
    """if not validate_challenge_request(cm_packet):
        log.warning(f"ChallengeReq validation failed")
        return None"""

    # Create Challenge response using message class
    # SNetChallengeMsg now uses dynamic challenge generation
    challenge_msg = SNetChallengeMsg()  # Uses dynamic masked challenge

    cm_packet_reply.packetid = bytes([ESNetMsg.Challenge])  # 0x02
    cm_packet_reply.size = SNetChallengeMsg.PAYLOAD_SIZE  # 8 bytes
    cm_packet_reply.data_len = SNetChallengeMsg.PAYLOAD_SIZE
    cm_packet_reply.destination_id = cm_packet.source_id
    cm_packet_reply.source_id = cm_packet.destination_id
    # ACK the client's ChallengeReq (seq=1)
    cm_packet_reply.last_recv_seq = cm_packet.sequence_num  # Should be 1
    # Server's first packet is seq=1
    cm_packet_reply.sequence_num = 1
    cm_packet_reply.split_pkt_cnt = 0
    cm_packet_reply.seq_of_first_pkt = 0
    cm_packet_reply.data = challenge_msg.serialize()

    cmidreply = cm_packet_reply.serialize()
    log.debug(f"Sending Challenge with masked value 0x{challenge_msg.challenge:08X}")
    return cmidreply


# Keep old function name as alias for backwards compatibility
create_conn_acceptresponse = handle_challenge_request