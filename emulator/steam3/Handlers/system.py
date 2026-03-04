import copy
import struct
import time
import threading

import globalvars
from steam3.ClientManager import Client_Manager
from steam3.ClientManager.client import Client
from steam3.Types.community_types import RequestedPersonaStateFlags_inFriendsList_friend
from steam3.Types.steam_types import NatTypes, EResult
from steam3.cm_packet_utils import CMPacket
from steam3.Responses.general_responses import build_General_response, build_ClientRequestValidationMail_Response
from steam3.Responses.friends_responses import build_persona_message
from steam3.Responses.chat_responses import build_send_friendsmsg
from utilities import sendmail
from utilities.impsocket import MessageInfo

# Module-level state for batched stale client checks
# Using time-based interval instead of random to ensure consistent behavior
_last_stale_check_time = 0.0
_stale_check_interval = 60.0  # Check every 60 seconds instead of randomly per heartbeat
_stale_check_lock = threading.Lock()


def handle_Heartbeat(cmserver_obj, packet, client_obj):
    """
    Process a heartbeat/datagram (type 0x07) from a client and respond with any pending updates.

    Datagram packets (type 0x07) are special:
    - They have sequence_num = 0 (don't consume sequence numbers)
    - They still carry valid ACKs in last_recv_seq field
    - We should process their ACK to update our tracking
    """

    if isinstance(client_obj, Client):
        # Update the last heartbeat timestamp for this client
        client_obj.renew_heartbeat()

        # Process the client's ACK even though this is a datagram
        # Datagrams have seq=0 but still carry valid acknowledgements
        if hasattr(packet, 'last_recv_seq') and packet.last_recv_seq > 0:
            client_obj.update_client_sequence(
                client_seq=0,  # Datagrams don't have sequence numbers
                client_ack=packet.last_recv_seq
            )

    if not packet.is_tcp:
        if isinstance(client_obj, tuple):
            client_address = client_obj
        else:
            client_address = client_obj.ip_port

        cm_packet_reply = copy.copy(packet)
        cm_packet_reply.packetid = b'\x07'
        cm_packet_reply.size = 0
        cm_packet_reply.data_len = 0
        cm_packet_reply.destination_id = packet.source_id
        cm_packet_reply.source_id = packet.destination_id
        # ACK the last DATA packet we received (not the datagram's seq=0)
        if isinstance(client_obj, Client):
            cm_packet_reply.last_recv_seq = client_obj.last_recvd_sequence
        else:
            cm_packet_reply.last_recv_seq = 0
        cm_packet_reply.sequence_num = 0  # Datagrams don't consume sequence numbers
        cm_packet_reply.split_pkt_cnt = 0
        cm_packet_reply.seq_of_first_pkt = 0
        cm_packet_reply.data = b''

        cmidreply = cm_packet_reply.serialize()
        msg_info = MessageInfo(packet_type="Datagram/Heartbeat")
        cmserver_obj.serversocket.sendto(cmidreply, client_address, msg_info=msg_info)

    if isinstance(client_obj, Client):
        # Retrieve pending status updates and messages for this client
        updates = client_obj.get_heartbeat_updates()
        if updates:
            status_updates, pending_messages = updates

            # Send any pending status changes
            for friend_account_id, _status, _appid, _ip, _port, _username in status_updates:
                packet = build_persona_message(
                    client_obj,
                    RequestedPersonaStateFlags_inFriendsList_friend,
                    [friend_account_id],
                )
                cmserver_obj.sendReply(client_obj, [packet])

            # Send any pending chat messages
            for msg in pending_messages:
                cmserver_obj.sendReply(client_obj, [build_send_friendsmsg(client_obj, msg)])

        # Check for pending client update news (for all heartbeats - TCP and UDP)
        from steam3.news_update_manager import news_update_manager
        if news_update_manager.has_client_update_pending():
            news_packet = news_update_manager.create_client_update_message(client_obj)
            if news_packet:
                cmserver_obj.sendReply(client_obj, [news_packet])


    # Cleanup stale clients periodically using time-based interval
    # This is more efficient than checking on every heartbeat or using random
    global _last_stale_check_time
    current_time = time.time()

    # Use non-blocking check to avoid contention
    should_check = False
    with _stale_check_lock:
        if current_time - _last_stale_check_time >= _stale_check_interval:
            _last_stale_check_time = current_time
            should_check = True

    if should_check:
        exclude_account = client_obj.accountID if isinstance(client_obj, Client) else None
        Client_Manager.check_and_remove_stale_clients(exclude_account_id=exclude_account)

        # Periodically log any unacked packets for debugging
        if isinstance(client_obj, Client):
            unacked = client_obj.get_unacked_packets(timeout_seconds=30.0)
            if unacked:
                cmserver_obj.log.warning(
                    f"Client {client_obj.ip_port} has {len(unacked)} unacked packets: "
                    f"{[(seq, info) for seq, _, info in unacked]}"
                )

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
        print(f"Byte Array: {public_key} (Look at you, unpacking bytes like a pro..)")
    else:
        print("Third integer is a zero.")

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


def handle_RequestValidationMail(cmserver_obj, packet: CMPacket, client_obj: Client):
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved Mail Validation Request")
    if globalvars.config['auto_verify_steam3_email'].lower() == 'true':
        client_obj.set_email_verified()
    elif globalvars.config['smtp_enabled'].lower() == 'true':
        cmserver_obj.log.debug(f"({client_address[0]}:{client_address[1]}): Sending E-Mail Validation Email")
        validation_dict = client_obj.generate_verification_code()
        sendmail.send_verification_email(validation_dict['email'], validation_dict['verification_code'], client_address, client_obj.username)

    return build_ClientRequestValidationMail_Response(client_obj, EResult.OK)
