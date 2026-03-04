import struct
import logging
from steam3.Types.steamid import SteamID
from steam3.Types.steam_types import EIntroducerRouting

from steam3.ClientManager import Client_Manager
from steam3.ClientManager.client import Client
from steam3.cm_packet_utils import CMPacket
from steam3.messages.MSGClientP2PIntroducerMessage import MSGClientP2PIntroducerMessage
from steam3.messages.MSGClientP2PTrackerMessage import MSGClientP2PTrackerMessage
from steam3.messages.MsgClientP2PConnectionInfo import MsgClientP2PConnectionInfo
from steam3.messages.MsgClientP2PConnectionFailInfo import MsgClientP2PConnectionFailInfo
from steam3.messages.MsgClientUDSP2PSessionStarted import MsgClientUDSP2PSessionStarted
from steam3.messages.MsgClientUDSP2PSessionEnded import MsgClientUDSP2PSessionEnded
from steam3.messages.MsgClientVoiceCallPreAuthorize import (
    MsgClientVoiceCallPreAuthorizeRequest,
    MsgClientVoiceCallPreAuthorizeResponseMsg,
)
from steam3.Managers.P2PManager.manager import P2P_Manager
from steam3.Types.Objects.VoiceIntroducerPackets import (
    VoiceIntroducerPacketType,
    AddCandidate,
    parse_voice_introducer_packet,
)

log = logging.getLogger("P2PHandler")


def handle_P2PIntroducerMessage(cmserver_obj, packet: CMPacket, client_obj: Client):
    """Forward a P2P introducer message to its intended recipient.

    For voice chat (k_eRouteP2PVoiceChat), we parse the inner VoiceIntroducer
    packet, swap the payload to flip local/remote identifiers, and forward
    the modified message to the target client.

    For other routing types, we extract the remote SteamID and forward
    the message unchanged.
    """
    client_address = client_obj.ip_port
    cmserver_obj.log.info(
        f"({client_address[0]}:{client_address[1]}): Received P2P Introducer Message"
    )

    msg = MSGClientP2PIntroducerMessage(client_obj, packet.CMRequest.data)

    cmserver_obj.log.debug(
        f"P2P Introducer: steam_id={msg.steam_id}, routing={msg.routing_type.name}, "
        f"payload_len={msg.payload_len}"
    )

    # Handle based on routing type
    if msg.routing_type == EIntroducerRouting.k_eRouteP2PVoiceChat:
        # Voice chat: parse inner packet and use swapPayload logic
        return _handle_voice_chat_introducer(cmserver_obj, msg, client_obj)
    else:
        # File share or networking: simple forward
        return _handle_simple_introducer(cmserver_obj, msg, client_obj)


def _handle_voice_chat_introducer(cmserver_obj, msg: MSGClientP2PIntroducerMessage, client_obj: Client):
    """
    Handle voice chat introducer messages with proper payload swapping.

    This implements the same logic as tinserver's MsgClientP2PIntroducerMessageHandler:
    1. Parse the AddCandidate packet from the introducer payload
    2. Find connections for the remote SteamID
    3. Swap the payload (flip local/remote identifiers)
    4. Create a new introducer message with swapped payload
    5. Forward to all remote connections
    """
    if not msg.payload or msg.payload_len < 10:
        cmserver_obj.log.warning("Voice chat introducer payload too short")
        return -1

    # Parse the inner VoiceIntroducer packet
    inner_packet = parse_voice_introducer_packet(msg.payload[:msg.payload_len])

    if inner_packet is None:
        # Fallback to simple forward if parsing fails
        cmserver_obj.log.warning("Failed to parse VoiceIntroducer packet, using simple forward")
        return _handle_simple_introducer(cmserver_obj, msg, client_obj)

    # Check if this is an AddCandidate packet
    if isinstance(inner_packet, AddCandidate):
        remote_steam_id = SteamID.from_raw(inner_packet.remote_steam_id)

        cmserver_obj.log.debug(
            f"Voice AddCandidate: local={inner_packet.local_steam_id}, "
            f"remote={remote_steam_id}, initiator={inner_packet.is_initiator}, "
            f"candidate_blob_size={len(inner_packet.candidate_blob) if inner_packet.candidate_blob else 0}"
        )

        # Find the target client
        # Note: get_accountID() returns AccountID wrapper, convert to int for dict lookup
        receiving_client = Client_Manager.clientsByAccountID.get(
            int(remote_steam_id.get_accountID())
        )

        if receiving_client:
            # Swap the payload - flip local/remote identifiers
            inner_packet.swap_payload()

            # Serialize the swapped packet
            swapped_payload = inner_packet.serialize()

            # Create forwarding message
            forward = MSGClientP2PIntroducerMessage(receiving_client)
            forward.steam_id = msg.steam_id  # Keep original steam_id
            forward.routing_type = msg.routing_type  # Keep routing type
            forward.payload = swapped_payload
            forward.payload_len = len(swapped_payload)

            # IMPORTANT: Use the recipient's CM server to send, not the sender's!
            if receiving_client.objCMServer:
                receiving_client.objCMServer.sendReply(receiving_client, [forward.to_clientmsg()])
            cmserver_obj.log.debug(f"Forwarded voice introducer to {remote_steam_id}")
        else:
            cmserver_obj.log.debug(f"Voice chat recipient {remote_steam_id} not connected")
    else:
        # Non-AddCandidate voice packet - forward unchanged
        cmserver_obj.log.debug(f"Voice packet type {inner_packet.packet_type.name}, forwarding unchanged")
        return _handle_simple_introducer(cmserver_obj, msg, client_obj)

    return -1


def _handle_simple_introducer(cmserver_obj, msg: MSGClientP2PIntroducerMessage, client_obj: Client):
    """
    Handle simple introducer messages by extracting remote SteamID and forwarding unchanged.

    The introducer payload contains the remote SteamID at byte offset 10
    (after packet_type (2 bytes) + local_steam_id (8 bytes)).
    """
    try:
        # Extract remote SteamID from payload at offset 10
        # Layout: packet_type(2) + local_steam_id(8) + remote_steam_id(8)
        target_raw, = struct.unpack_from("<Q", msg.payload, 10)
    except struct.error:
        cmserver_obj.log.warning("Introducer payload missing recipient SteamID")
        return -1

    receiver_id = SteamID.from_raw(target_raw)
    # Note: get_accountID() returns AccountID wrapper, convert to int for dict lookup
    receiving_client = Client_Manager.clientsByAccountID.get(
        int(receiver_id.get_accountID())
    )

    if receiving_client and receiving_client.objCMServer:
        forward = MSGClientP2PIntroducerMessage(receiving_client)
        forward.steam_id = msg.steam_id
        forward.routing_type = msg.routing_type
        forward.payload = msg.payload
        forward.payload_len = msg.payload_len
        # IMPORTANT: Use the recipient's CM server to send, not the sender's!
        receiving_client.objCMServer.sendReply(receiving_client, [forward.to_clientmsg()])
        cmserver_obj.log.debug(f"Forwarded P2P introducer to {receiver_id}")
    else:
        cmserver_obj.log.debug(f"P2P recipient {receiver_id} not connected")

    return -1


def handle_P2PTrackerMessage(cmserver_obj, packet: CMPacket, client_obj: Client):
    """Handle ``EMsg.ClientP2PTrackerMessage`` packets.

    The server currently only logs the message contents; real tracker
    handling is still undocumented.
    """
    msg = MSGClientP2PTrackerMessage(client_obj, packet.CMRequest.data)
    cmserver_obj.log.debug(
        "Received P2P tracker data (%d bytes) from %s",
        msg.payload_len,
        client_obj.steamID,
    )
    return -1


def handle_P2PConnectionInfo(cmserver_obj, packet: CMPacket, client_obj: Client):
    """Handle P2P connection info packets.

    Forward connection candidate information to the target client.
    """
    client_address = client_obj.ip_port
    cmserver_obj.log.info(
        f"({client_address[0]}:{client_address[1]}): Received P2P Connection Info"
    )

    msg = MsgClientP2PConnectionInfo(client_obj, packet.CMRequest.data)

    # Record connection attempt in P2P manager
    P2P_Manager.record_connection_attempt(
        msg.source_steam_id, msg.destination_steam_id, msg.app_id
    )

    # Find the target client
    # Note: get_accountID() returns AccountID wrapper, convert to int for dict lookup
    target_client = Client_Manager.clientsByAccountID.get(
        int(msg.destination_steam_id.get_accountID())
    )

    if target_client and target_client.objCMServer:
        # Forward the connection info to the target
        forward = MsgClientP2PConnectionInfo(target_client)
        forward.destination_steam_id = msg.destination_steam_id
        forward.source_steam_id = msg.source_steam_id
        forward.app_id = msg.app_id
        forward.candidate = msg.candidate

        # IMPORTANT: Use the recipient's CM server to send, not the sender's!
        target_client.objCMServer.sendReply(target_client, [forward.to_clientmsg()])
        cmserver_obj.log.debug(f"Forwarded P2P connection info to {msg.destination_steam_id}")
    else:
        cmserver_obj.log.debug(f"P2P target {msg.destination_steam_id} not connected")

    # Clean up expired sessions periodically
    P2P_Manager.cleanup_expired_sessions()

    return -1


def handle_P2PConnectionFailInfo(cmserver_obj, packet: CMPacket, client_obj: Client):
    """Handle P2P connection failure info packets.

    Forward connection failure information to the target client.
    """
    client_address = client_obj.ip_port
    cmserver_obj.log.info(
        f"({client_address[0]}:{client_address[1]}): Received P2P Connection Fail Info"
    )

    msg = MsgClientP2PConnectionFailInfo(client_obj, packet.CMRequest.data)

    # Record connection failure in P2P manager
    P2P_Manager.record_connection_failure(
        msg.source_steam_id, msg.destination_steam_id, msg.app_id, msg.error_code
    )

    # Find the target client
    # Note: get_accountID() returns AccountID wrapper, convert to int for dict lookup
    target_client = Client_Manager.clientsByAccountID.get(
        int(msg.destination_steam_id.get_accountID())
    )

    if target_client and target_client.objCMServer:
        # Forward the failure info to the target
        forward = MsgClientP2PConnectionFailInfo(target_client)
        forward.destination_steam_id = msg.destination_steam_id
        forward.source_steam_id = msg.source_steam_id
        forward.app_id = msg.app_id
        forward.error_code = msg.error_code
        forward.error_string = msg.error_string

        # IMPORTANT: Use the recipient's CM server to send, not the sender's!
        target_client.objCMServer.sendReply(target_client, [forward.to_clientmsg()])
        cmserver_obj.log.debug(f"Forwarded P2P connection failure to {msg.destination_steam_id}")
    else:
        cmserver_obj.log.debug(f"P2P target {msg.destination_steam_id} not connected")

    return -1


def handle_UDSP2PSessionStarted(cmserver_obj, packet: CMPacket, client_obj: Client):
    """Handle UDS P2P session started packets.

    Log session start and notify target client if needed.
    """
    client_address = client_obj.ip_port
    cmserver_obj.log.info(
        f"({client_address[0]}:{client_address[1]}): UDS P2P Session Started"
    )

    msg = MsgClientUDSP2PSessionStarted(client_obj, packet.CMRequest.data)

    # Start session in P2P manager
    session = P2P_Manager.start_session(
        msg.source_steam_id, msg.dest_steam_id, msg.app_id, msg.session_flags
    )

    if session:
        session.session_id = msg.session_id
        session.socket_id = msg.socket_id

    cmserver_obj.log.info(
        f"P2P session started: {msg.source_steam_id} -> {msg.dest_steam_id} "
        f"(app={msg.app_id}, session={msg.session_id})"
    )

    # Find the destination client to notify
    # Note: get_accountID() returns AccountID wrapper, convert to int for dict lookup
    dest_client = Client_Manager.clientsByAccountID.get(
        int(msg.dest_steam_id.get_accountID())
    )

    if dest_client and dest_client.objCMServer:
        # Notify the destination client about session start
        forward = MsgClientUDSP2PSessionStarted(dest_client)
        forward.source_steam_id = msg.source_steam_id
        forward.dest_steam_id = msg.dest_steam_id
        forward.app_id = msg.app_id
        forward.session_id = msg.session_id
        forward.socket_id = msg.socket_id
        forward.session_flags = msg.session_flags

        # IMPORTANT: Use the recipient's CM server to send, not the sender's!
        dest_client.objCMServer.sendReply(dest_client, [forward.to_clientmsg()])

    return -1


def handle_UDSP2PSessionEnded(cmserver_obj, packet: CMPacket, client_obj: Client):
    """Handle UDS P2P session ended packets.

    Log session end statistics and notify target client if needed.
    """
    client_address = client_obj.ip_port
    cmserver_obj.log.info(
        f"({client_address[0]}:{client_address[1]}): UDS P2P Session Ended"
    )

    msg = MsgClientUDSP2PSessionEnded(client_obj, packet.CMRequest.data)

    # End session in P2P manager and update statistics
    session = P2P_Manager.get_session(msg.source_steam_id, msg.dest_steam_id, msg.app_id)
    if session:
        session.bytes_sent = msg.bytes_sent
        session.bytes_received = msg.bytes_received
        session.session_duration = msg.session_duration

    P2P_Manager.end_session(
        msg.source_steam_id, msg.dest_steam_id, msg.app_id, msg.end_reason
    )

    cmserver_obj.log.info(
        f"P2P session ended: {msg.source_steam_id} -> {msg.dest_steam_id} "
        f"(app={msg.app_id}, session={msg.session_id}, reason={msg.end_reason}, "
        f"sent={msg.bytes_sent}, received={msg.bytes_received}, duration={msg.session_duration}ms)"
    )

    # Find the destination client to notify
    # Note: get_accountID() returns AccountID wrapper, convert to int for dict lookup
    dest_client = Client_Manager.clientsByAccountID.get(
        int(msg.dest_steam_id.get_accountID())
    )

    if dest_client and dest_client.objCMServer:
        # Notify the destination client about session end
        forward = MsgClientUDSP2PSessionEnded(dest_client)
        forward.source_steam_id = msg.source_steam_id
        forward.dest_steam_id = msg.dest_steam_id
        forward.app_id = msg.app_id
        forward.session_id = msg.session_id
        forward.socket_id = msg.socket_id
        forward.end_reason = msg.end_reason
        forward.bytes_sent = msg.bytes_sent
        forward.bytes_received = msg.bytes_received
        forward.session_duration = msg.session_duration

        # IMPORTANT: Use the recipient's CM server to send, not the sender's!
        dest_client.objCMServer.sendReply(dest_client, [forward.to_clientmsg()])

    return -1


def handle_VoiceCallPreAuthorize(cmserver_obj, packet: CMPacket, client_obj: Client):
    """Handle voice call pre-authorization request.

    Forward the pre-authorization request from the caller to the receiver.
    This is required before P2P voice candidates can be exchanged.
    """
    client_address = client_obj.ip_port
    cmserver_obj.log.info(
        f"({client_address[0]}:{client_address[1]}): Received Voice Call Pre-Authorize"
    )

    msg = MsgClientVoiceCallPreAuthorizeRequest(client_obj, packet.CMRequest.data)

    cmserver_obj.log.debug(
        f"Voice Pre-Auth: caller={msg.caller_steamid}, receiver={msg.receiver_steamid}, "
        f"caller_id={msg.caller_id}, hangup={msg.hangup}"
    )

    # Find the receiver client
    receiver_id = SteamID.from_raw(msg.receiver_steamid)
    receiving_client = Client_Manager.clientsByAccountID.get(
        int(receiver_id.get_accountID())
    )

    if receiving_client and receiving_client.objCMServer:
        # Forward the pre-authorization request to the receiver
        forward = MsgClientVoiceCallPreAuthorizeRequest(receiving_client)
        forward.caller_steamid = msg.caller_steamid
        forward.receiver_steamid = msg.receiver_steamid
        forward.caller_id = msg.caller_id
        forward.hangup = msg.hangup

        # IMPORTANT: Use the recipient's CM server to send, not the sender's!
        receiving_client.objCMServer.sendReply(receiving_client, [forward.to_clientmsg()])
        cmserver_obj.log.debug(f"Forwarded voice pre-auth request to {receiver_id}")
    else:
        cmserver_obj.log.debug(f"Voice call receiver {receiver_id} not connected")

    return -1


def handle_VoiceCallPreAuthorizeResponse(cmserver_obj, packet: CMPacket, client_obj: Client):
    """Handle voice call pre-authorization response.

    Forward the response from the receiver back to the caller.
    This completes the pre-authorization handshake and allows P2P candidates to be exchanged.
    """
    client_address = client_obj.ip_port
    cmserver_obj.log.info(
        f"({client_address[0]}:{client_address[1]}): Received Voice Call Pre-Authorize Response"
    )

    msg = MsgClientVoiceCallPreAuthorizeResponseMsg(client_obj, packet.CMRequest.data)

    cmserver_obj.log.debug(
        f"Voice Pre-Auth Response: caller={msg.caller_steamid}, receiver={msg.receiver_steamid}, "
        f"eresult={msg.eresult}, caller_id={msg.caller_id}"
    )

    # Find the caller client (response goes back to caller)
    caller_id = SteamID.from_raw(msg.caller_steamid)
    caller_client = Client_Manager.clientsByAccountID.get(
        int(caller_id.get_accountID())
    )

    if caller_client and caller_client.objCMServer:
        # Forward the response back to the caller
        forward = MsgClientVoiceCallPreAuthorizeResponseMsg(caller_client)
        forward.caller_steamid = msg.caller_steamid
        forward.receiver_steamid = msg.receiver_steamid
        forward.eresult = msg.eresult
        forward.caller_id = msg.caller_id

        # IMPORTANT: Use the recipient's CM server to send, not the sender's!
        caller_client.objCMServer.sendReply(caller_client, [forward.to_clientmsg()])
        cmserver_obj.log.debug(f"Forwarded voice pre-auth response to {caller_id}")
    else:
        cmserver_obj.log.debug(f"Voice call caller {caller_id} not connected")

    return -1
