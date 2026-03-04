from __future__ import annotations
import copy
import logging
import sys
import time
import traceback
import threading
from typing import List, Optional

from steam3 import Types
from steam3.ClientManager import Client_Manager
from steam3.ClientManager.client import Client
from steam3.Handlers.connection import (
    create_channel_encryption_request,
    create_channel_encryption_result,
    handle_challenge_request,
    handle_connect_request,
    parse_channel_encryption_response,
    validate_challenge_request,
    validate_connect_request,
)
from steam3.Handlers.system import handle_Heartbeat
from steam3.messages.SNetMsgBase import ESNetMsg
from steam3.Types.emsg import EMsg
from steam3.Types.wrappers import ConnectionID
from steam3.cm_crypto import symmetric_decrypt, symmetric_encrypt
from steam3.cm_packet_utils import CMPacket, CMProtoResponse, ExtendedMsgHdr, MsgHdr_deprecated, MultiMsg, deprecated_responsehdr
from steam3.cmserver_base import CMServer_Base
from utilities import encryption
from utilities.encryption import calculate_crc32_bytes
from utilities.impsocket import MessageInfo
from utilities.networkhandler import UDPNetworkHandlerCM

capture_split_once = False

class CMServerUDP(CMServer_Base):
    is_tcp = False

    def send_ack_for_duplicate(self, cm_packet: CMPacket, client_obj: Client, address: tuple):
        """
        Send a bare ACK (Datagram packet with seq=0) for duplicate packets.

        Based on tinserver UdpNetSocket::validateSequence logic:
        When a duplicate packet is received, we send an ACK to confirm we
        received the original, but we don't process the duplicate.

        This uses a Datagram packet (0x07) with sequence=0, which is the
        standard ACK format in the Steam UDP protocol.
        """
        ack_packet = CMPacket()
        ack_packet.magic = 0x31305356
        ack_packet.packetid = bytes([ESNetMsg.Datagram])  # 0x07 - Datagram/ACK
        ack_packet.priority_level = b'\x04'  # Low priority for ACKs
        ack_packet.source_id = cm_packet.destination_id
        ack_packet.destination_id = cm_packet.source_id
        ack_packet.sequence_num = 0  # ACK packets use seq=0
        ack_packet.last_recv_seq = client_obj.last_recvd_sequence  # ACK up to what we've received
        ack_packet.split_pkt_cnt = 0
        ack_packet.seq_of_first_pkt = 0
        ack_packet.data_len = 0
        ack_packet.size = 0
        ack_packet.data = b''

        try:
            msg_info = MessageInfo(packet_type="ACK/Datagram")
            self.serversocket.sendto(ack_packet.serialize(), address, msg_info=msg_info)
            self.log.debug(f"Sent ACK for duplicate packet (client seq={cm_packet.sequence_num}, acking up to {client_obj.last_recvd_sequence})")
        except Exception as e:
            self.log.error(f"Failed to send duplicate ACK: {e}")

    def handle_client(self, data, address):
        try:
            clientid = str(address) + ": "
            self.log.info(f"{clientid}Connected to UDP CM Server")

            # keep an eye out for master server packets that get sent here:
            if data.startswith(b"\xff\xff\xff\xff"):
                self.master_server.handle_client(data, address, True)
                return

            packet = CMPacket(is_tcp=self.is_tcp)
            cm_packet = packet.parse(data)

            cm_packet_reply = copy.deepcopy(cm_packet)
            conn_type = "encrypted" if self.is_encrypted else "unencrypted"

            # UDP packet types (from tinserver analysis):
            # 0x01 = ChallengeReq: Client requests challenge (first packet)
            # 0x02 = Challenge: Server sends masked challenge (we send this, not receive)
            # 0x03 = Connect: Client sends unmasked challenge (creates connection)
            # 0x04 = Accept: Server confirms connection (we send this, not receive)
            # 0x05 = Disconnect
            # 0x06 = Data (encrypted messages)
            # 0x07 = Datagram (heartbeat)
            challenge_req_id = bytes([ESNetMsg.ChallengeReq])    # 0x01
            connect_id = bytes([ESNetMsg.Connect])                # 0x03
            disconnect_id = bytes([ESNetMsg.Disconnect])          # 0x05
            data_packet_id = bytes([ESNetMsg.Data])               # 0x06
            datagram_id = bytes([ESNetMsg.Datagram])              # 0x07

            if cm_packet.packetid == challenge_req_id:  # ChallengeReq (0x01)
                self.log.info(f"{clientid}[{conn_type}] Received ChallengeReq")
                self.log.debug(f"ChallengeReq packet: {cm_packet}")

                # Validate and respond with Challenge (0x02)
                cmidreply = handle_challenge_request(cm_packet, cm_packet_reply)
                if cmidreply is None:
                    self.log.warning(f"{clientid}ChallengeReq validation failed, ignoring")
                    return

                msg_info = MessageInfo(packet_type="Challenge")
                self.serversocket.sendto(cmidreply, address, msg_info=msg_info)
                self.log.debug(f"{clientid}Sent Challenge response")
                return

            elif cm_packet.packetid == connect_id:  # Connect (0x03)
                self.log.info(f"{clientid}[{conn_type}] Received Connect")
                self.log.debug(f"Connect packet: {cm_packet}")

                # Validate challenge and respond with Accept (0x04)
                cmidreply = handle_connect_request(cm_packet, cm_packet_reply, address, self.connectionid_count)
                if cmidreply is None:
                    self.log.warning(f"{clientid}Connect validation failed, ignoring")
                    return

                msg_info = MessageInfo(packet_type="Accept")
                self.serversocket.sendto(cmidreply, address, msg_info=msg_info)
                self.log.info(f"{clientid}Sent Accept, connection established")

                # Create client object AFTER challenge validation passes (like tinserver)
                client = Client(ip_port=address, connectionid=self.connectionid_count)
                client.objCMServer = self
                client.initialize_after_handshake()

                Client_Manager.add_or_update_client(client)
                self.connectionid_count += 1

                # For encrypted servers, queue the ChannelEncryptRequest
                # but DON'T send it immediately - wait for client to ACK Accept first
                # The client will send a Data packet or Datagram after ACKing Accept
                if self.is_encrypted:
                    # Store pending encryption request on client object
                    client.pending_encryption_request = True
                    self.log.debug(f"{clientid}Encryption request queued (will send on next client packet)")
                return

            elif cm_packet.packetid == disconnect_id:  # Disconnect (0x05)
                self.log.info(f"{clientid}Received Disconnect packet")
                client_obj = Client_Manager.get_client_by_identifier(address)
                if client_obj:
                    client_obj.socket = None

                cm_packet_reply.priority_level = b"\x04"
                cm_packet_reply.packetid = bytes([ESNetMsg.Disconnect])
                cm_packet_reply.size = 0
                cm_packet_reply.source_id = cm_packet.destination_id
                cm_packet_reply.destination_id = cm_packet.source_id
                # Use proper sequence tracking
                if client_obj:
                    cm_packet_reply.sequence_num = client_obj.get_next_sequence_number()
                else:
                    cm_packet_reply.sequence_num = cm_packet.sequence_num + 1
                cm_packet_reply.last_recv_seq = cm_packet.sequence_num
                cm_packet_reply.split_pkt_cnt = 1
                cm_packet_reply.seq_of_first_pkt = cm_packet_reply.sequence_num
                cm_packet_reply.data_len = 0
                cm_packet_reply.data = b"\x00"

                cmidreply = cm_packet_reply.serialize()
                msg_info = MessageInfo(packet_type="Disconnect")
                self.serversocket.sendto(cmidreply, address, msg_info=msg_info)

                if client_obj:
                    is_app_session = client_obj.is_in_app
                    if is_app_session:
                        client_obj.disconnect_Game(self)
                    else:
                        client_obj.logoff_User(self)

                return

            elif cm_packet.packetid == data_packet_id:  # Data packet (0x06)
                client_obj = Client_Manager.get_client_by_identifier(address)

                # Check if we have a pending encryption request to send
                # This implements the "wait for client ACK" behavior like tinserver
                if client_obj and hasattr(client_obj, 'pending_encryption_request') and client_obj.pending_encryption_request:
                    # Client has ACKed our Accept by sending a packet
                    # Now we can send the ChannelEncryptRequest
                    client_obj.pending_encryption_request = False

                    # Update client's received sequence before sending
                    # During handshake, we always process (no duplicate check needed)
                    client_obj.update_client_sequence(
                        client_seq=cm_packet.sequence_num,
                        client_ack=cm_packet.last_recv_seq
                    )

                    self.log.info(f"{clientid}[{conn_type}] Client ACKed Accept, sending ChannelEncryptRequest")
                    encrypt_request_reply = copy.deepcopy(cm_packet)
                    cmidreply = create_channel_encryption_request(cm_packet, encrypt_request_reply, client_obj.connectionid, client_obj)
                    msg_info = MessageInfo(emsg_id=EMsg.ChannelEncryptRequest, emsg_name="ChannelEncryptRequest")
                    self.serversocket.sendto(cmidreply, address, msg_info=msg_info)
                    return

                # Handle ChannelEncryptResponse (0x0518 = 1304)
                if b"\x18\x05" in data[36:39]:
                    # Decrypt the AES session key
                    encrypted_message = cm_packet.data[28:156]
                    encrypted_message_crc32 = cm_packet.data[156:160]
                    self.log.debug(f"Received ChannelEncryptResponse: {cm_packet}")
                    key = encryption.get_aes_key(encrypted_message, encryption.network_key)
                    self.log.debug(f"Decrypted Session Key: {key}")

                    verification_local = calculate_crc32_bytes(encrypted_message)
                    verification_result = "Pass" if verification_local == encrypted_message_crc32 else "Fail"
                    self.log.debug(f"CRC32 Verification: {verification_result}")

                    client_obj.set_symmetric_key(key)
                    client_obj.hmac_key = key[:16]

                    # Update sequence tracking
                    # During handshake, we always process (no duplicate check needed)
                    client_obj.update_client_sequence(
                        client_seq=cm_packet.sequence_num,
                        client_ack=cm_packet.last_recv_seq
                    )

                    # Send ChannelEncryptResult with result = OK
                    cm_packet_reply.priority_level = b"\x02"
                    cm_packet_reply.packetid = bytes([ESNetMsg.Data])
                    cm_packet_reply.size = 24
                    cm_packet_reply.source_id = cm_packet.destination_id
                    cm_packet_reply.destination_id = cm_packet.source_id
                    cm_packet_reply.sequence_num = client_obj.get_next_sequence_number()
                    cm_packet_reply.last_recv_seq = client_obj.last_recvd_sequence
                    cm_packet_reply.split_pkt_cnt = 1
                    cm_packet_reply.seq_of_first_pkt = cm_packet_reply.sequence_num
                    cm_packet_reply.data_len = 24
                    cm_packet_reply.data = create_channel_encryption_result()

                    cmidreply = cm_packet_reply.serialize()
                    msg_info = MessageInfo(emsg_id=EMsg.ChannelEncryptResult, emsg_name="ChannelEncryptResult")
                    self.serversocket.sendto(cmidreply, address, msg_info=msg_info)
                    self.log.info(f"{clientid}Encryption handshake complete")
                    return

                # Normal encrypted data packet
                if client_obj:
                    # Check for duplicate or out-of-order packets
                    should_process = client_obj.update_client_sequence(
                        client_seq=cm_packet.sequence_num,
                        client_ack=cm_packet.last_recv_seq
                    )

                    if not should_process:
                        # This is a duplicate packet - send ACK but don't process
                        self.log.debug(f"{clientid}Duplicate packet detected (seq={cm_packet.sequence_num}), sending ACK only")
                        self.send_ack_for_duplicate(cm_packet, client_obj, address)
                        return

                self.handle_CMPacket(cm_packet, client_obj)
                return

            elif cm_packet.packetid == datagram_id:  # Datagram/Heartbeat (0x07)
                self.log.debugplus(f"{clientid}Received Heartbeat")
                client_obj = Client_Manager.get_client_by_identifier(address)

                # Check for pending encryption request
                if client_obj and hasattr(client_obj, 'pending_encryption_request') and client_obj.pending_encryption_request:
                    # Client sent heartbeat after Accept, send encryption request
                    client_obj.pending_encryption_request = False

                    self.log.info(f"{clientid}[{conn_type}] Client ACKed Accept via heartbeat, sending ChannelEncryptRequest")
                    encrypt_request_reply = copy.deepcopy(cm_packet)
                    cmidreply = create_channel_encryption_request(cm_packet, encrypt_request_reply, client_obj.connectionid, client_obj)
                    msg_info = MessageInfo(emsg_id=EMsg.ChannelEncryptRequest, emsg_name="ChannelEncryptRequest")
                    self.serversocket.sendto(cmidreply, address, msg_info=msg_info)
                    # Continue to process heartbeat normally

                if client_obj is None:
                    return

                handle_Heartbeat(self, cm_packet, client_obj)
                return

            else:
                client_obj = Client_Manager.get_client_by_identifier(address)
                self.log.error(f"{clientid}Received Unknown Packet Type: {cm_packet.packetid}")
                self.handle_unknown_command(self, cm_packet, client_obj)
                return
        except Exception as e:
            traceback.print_exc()
            self.log.error(f"(CM Handle_Client) thread exception: {e}")
            tb = sys.exc_info()[2]
            self.log.error(''.join(traceback.format_tb(tb)))

    def handle_client_matchmaking(self, data: bytes, address: tuple) -> None:
        """
        Process an incoming matchmaking packet using a custom raw binary format.

        Incoming packet formats:
          - Registration (0x01):
              Byte 0:  0x01
              Bytes 1-2: Server UDP port (unsigned short, little-endian)
              Byte 3:  Length of server name (N)
              Bytes 4 to 4+N-1: Server name (ASCII)
              Bytes 4+N to 4+N+3: Current player count (unsigned int, little-endian)
              Bytes 4+N+4 to 4+N+7: Maximum player count (unsigned int, little-endian)
              Bytes 4+N+8 onward: Optional extra info (raw bytes)

          - Heartbeat (0x02):
              Byte 0:  0x02
              Optionally, Bytes 1R4: Current player count (unsigned int, little-endian)
              Optionally, Bytes 5-8: Maximum player count (unsigned int, little-endian)
              Optionally, Bytes 9 onward: Updated extra info (raw bytes)

          - Query (0x03):
              Byte 0:  0x03  (no further data)

          - Removal (0x04):
              Byte 0:  0x04
              Bytes 1-2: Server UDP port (unsigned short, little-endian)

        The method maintains an internal dictionary, self.matchmaking_servers,
        keyed by (server IP, server UDP port), with values as dictionaries containing:
          - ip: (string) server IP address
          - port: (int) server UDP port
          - name: (string) server name
          - current_players: (int)
          - max_players: (int)
          - extra_info: (bytes)
          - registration_time: (float) timestamp of registration
          - last_heartbeat: (float) timestamp of last heartbeat

        For a query (0x03), the method purges stale entries (no heartbeat in 90 seconds)
        and replies with a raw packet constructed as follows:
          - Byte 0: 0x03 (response type)
          - For each server entry:
              4 bytes: IP address (network order)
              2 bytes: UDP port (unsigned short, little-endian)
              1 byte: Length of server name (M)
              M bytes: Server name (ASCII)
              4 bytes: Current player count (unsigned int, little-endian)
              4 bytes: Maximum player count (unsigned int, little-endian)
              1 byte: Length of extra info (K)
              K bytes: Extra info (raw bytes)

        All errors and actions are logged in detail.
        """
        try:
            if not data or len(data) < 1:
                self.log.error(f"Empty matchmaking packet received from {address}")
                return

            # Read the matchmaking action type from the first byte.
            mm_type = data[0]
            current_time = time.time()
            # Ensure the internal server list exists.
            if not hasattr(self, "matchmaking_servers"):
                self.matchmaking_servers = {}

            if mm_type == 0x01:
                # Registration packet.
                # Minimum required length: 1 (type) + 2 (port) + 1 (name length) + 4 + 4 = 12 bytes.
                if len(data) < 12:
                    self.log.error(f"Registration packet from {address} is too short ({len(data)} bytes)")
                    return

                # Extract server port.
                server_port = int.from_bytes(data[1:3], "little")
                # Get server name length.
                name_len = data[3]
                if len(data) < 4 + name_len + 8:
                    self.log.error(f"Registration packet from {address} lacks sufficient data for server name and stats")
                    return
                # Decode server name.
                server_name = data[4:4 + name_len].decode("ascii", errors="replace")
                offset = 4 + name_len
                # Extract current and maximum player counts.
                current_players = int.from_bytes(data[offset:offset + 4], "little")
                offset += 4
                max_players = int.from_bytes(data[offset:offset + 4], "little")
                offset += 4
                # Optional extra info.
                extra_info = data[offset:] if offset < len(data) else b""

                # Store server info.
                key = (address[0], server_port)
                self.matchmaking_servers[key] = {
                    "ip": address[0],
                    "port": server_port,
                    "name": server_name,
                    "current_players": current_players,
                    "max_players": max_players,
                    "extra_info": extra_info,
                    "registration_time": current_time,
                    "last_heartbeat": current_time,
                    "address": address,
                }
                self.log.info(f"Registered matchmaking server '{server_name}' at {address[0]}:{server_port} "
                              f"({current_players}/{max_players} players)")

            elif mm_type == 0x02:
                # Heartbeat update.
                updated = False
                # Identify all registered servers from the sender's IP.
                for key, entry in self.matchmaking_servers.items():
                    if entry["ip"] == address[0]:
                        entry["last_heartbeat"] = current_time
                        # Optionally update player counts if data length permits.
                        if len(data) >= 9:
                            entry["current_players"] = int.from_bytes(data[1:5], "little")
                            entry["max_players"] = int.from_bytes(data[5:9], "little")
                            if len(data) > 9:
                                entry["extra_info"] = data[9:]
                        updated = True
                        self.log.debugplus(f"Heartbeat updated for server '{entry['name']}' at {entry['ip']}:{entry['port']}")
                if not updated:
                    self.log.warning(f"Received heartbeat from unregistered server {address}")

            elif mm_type == 0x03:
                # Query for server list.
                stale_threshold = 90  # seconds; remove servers with no heartbeat in this interval.
                stale_keys = [key for key, entry in self.matchmaking_servers.items()
                              if current_time - entry["last_heartbeat"] > stale_threshold]
                for key in stale_keys:
                    removed = self.matchmaking_servers.pop(key)
                    self.log.info(f"Purged stale server '{removed['name']}' at {removed['ip']}:{removed['port']}")

                # Build the response payload.
                response = bytearray()
                response.append(0x03)  # Response type.
                for entry in self.matchmaking_servers.values():
                    try:
                        ip_bytes =  self.serversocket.inet_aton(entry["ip"])
                    except Exception as e:
                        self.log.error(f"Invalid IP address '{entry['ip']}' in server list: {e}")
                        continue
                    port_bytes = entry["port"].to_bytes(2, "little")
                    name_bytes = entry["name"].encode("ascii", errors="replace")
                    name_length = len(name_bytes)
                    current_bytes = entry["current_players"].to_bytes(4, "little")
                    max_bytes = entry["max_players"].to_bytes(4, "little")
                    extra_bytes = entry["extra_info"]
                    extra_length = len(extra_bytes)
                    response.extend(ip_bytes)
                    response.extend(port_bytes)
                    response.append(name_length)
                    response.extend(name_bytes)
                    response.extend(current_bytes)
                    response.extend(max_bytes)
                    response.append(extra_length)
                    response.extend(extra_bytes)
                # Send the raw response.
                msg_info = MessageInfo(packet_type="MatchmakingServerList")
                self.serversocket.sendto(bytes(response), address, msg_info=msg_info)
                self.log.info(f"Sent matchmaking server list with {len(self.matchmaking_servers)} servers to {address}")

            elif mm_type == 0x04:
                # Removal packet.
                if len(data) < 3:
                    self.log.error(f"Removal packet from {address} is too short ({len(data)} bytes)")
                    return
                server_port = int.from_bytes(data[1:3], "little")
                key = (address[0], server_port)
                if key in self.matchmaking_servers:
                    removed = self.matchmaking_servers.pop(key)
                    self.log.info(f"Removed matchmaking server '{removed['name']}' at {removed['ip']}:{removed['port']}")
                else:
                    self.log.warning(f"Received removal packet from {address} for unregistered server on port {server_port}")

            else:
                self.log.error(f"Unknown matchmaking action type {mm_type} received from {address}")
        except Exception as e:
            self.log.error(f"Exception in handle_client_matchmaking from {address}: {e}", exc_info=True)

    def sendReply(self, client_obj, response_packet_list: [list, ExtendedMsgHdr | CMProtoResponse | deprecated_responsehdr | MultiMsg], packetID=None, priority_level=1):
        global capture_split_once

        if isinstance(response_packet_list, int) or response_packet_list is None:  #  we skip -1 and None packet types
            return

        # Validate client is still in the manager (not replaced by a newer connection)
        # This prevents sending to stale client objects that have been disconnected/reconnected
        # which would cause sequence number corruption and login/logoff loops
        current_client = Client_Manager.get_client_by_identifier(client_obj.ip_port)
        if current_client is not client_obj:
            self.log.debug(f"Client object for {client_obj.ip_port} is stale (replaced), skipping send")
            return

        # Initialize variables before lock so they're available after
        packets_to_send = []
        msg_info_list = []

        # Acquire send lock to ensure packets are prepared in sequence order
        # This prevents the race condition where Thread A gets seq=5, Thread B gets seq=6,
        # but Thread B's packet is sent first due to thread scheduling
        # Using RLock allows recursive calls (when processing multiple packets)
        with client_obj.send_lock:
            # If there are multiple packets, send them one-by-one using the exact same logic below.
            if len(response_packet_list) > 1:
                for pkt in response_packet_list:
                    # wrap in single-element list to hit the ?only support single-element responses? block
                    self.sendReply(client_obj, [pkt], packetID, priority_level)
                return

            try:
                if not response_packet_list:
                    return

                # Prepare the base reply packet.
                reply_packet = CMPacket()
                reply_packet.magic = 0x31305356
                reply_packet.packetid = b'\x06' if packetID is None else packetID
                reply_packet.priority_level = int(priority_level).to_bytes(1, 'little')
                reply_packet.source_id = client_obj.serverconnectionid
                reply_packet.destination_id = client_obj.connectionid
                reply_packet.last_recv_seq = client_obj.last_recvd_sequence

                # Only support single-element responses.
                if len(response_packet_list) == 1:
                    response_packet = response_packet_list[0]
                    if response_packet.data:
                        # Extract message info BEFORE encryption for logging
                        emsg_id = getattr(response_packet, 'eMsgID', None)
                        emsg_name = Types.get_enum_name(EMsg, emsg_id) if emsg_id is not None else None
                        target_job_id = getattr(response_packet, 'targetJobID', None)
                        source_job_id = getattr(response_packet, 'sourceJobID', None)
                        is_encrypted = self.is_encrypted and client_obj.symmetric_key is not None

                        # First, get the full unencrypted message (with header).
                        original_unencrypted = response_packet.serialize()

                        # Set the reply packet's data to the full unencrypted message.
                        reply_packet.data = original_unencrypted

                        # Log unencrypted packet through impsocket for centralized logging
                        msg_info = MessageInfo(
                            emsg_id=emsg_id,
                            emsg_name=emsg_name,
                            is_encrypted=is_encrypted,
                            target_job_id=target_job_id,
                            source_job_id=source_job_id
                        )
                        self.serversocket.log_packet(
                            address=client_obj.ip_port,
                            direction="Sent",
                            data=original_unencrypted,
                            msg_info=msg_info
                        )

                        # Encrypt the reply.
                        reply_packet.data = self.encrypt_packet(reply_packet, client_obj)
                        data_len = len(reply_packet.data)
                        max_data_size = 25000  # Maximum data size per UDP packet

                        packets_to_send = []
                        msg_info_list = []
                        if data_len > max_data_size:
                            if not capture_split_once:
                                # Log the full unencrypted message with its header in raw \x format.
                                try:
                                    with open("logs/unencrypted_split_messages.txt", "a", encoding="utf-8") as f:
                                        full_header_info = (
                                            "----- Full Unencrypted Reply -----\n"
                                            f"Magic: {hex(reply_packet.magic)}\n"
                                            f"PacketID: {reply_packet.packetid}\n"
                                            f"Priority: {int.from_bytes(reply_packet.priority_level, 'little')}\n"
                                            f"SourceID: {reply_packet.source_id}\n"
                                            f"DestinationID: {reply_packet.destination_id}\n"
                                            f"LastRecvSeq: {reply_packet.last_recv_seq}\n"
                                        )
                                        f.write(f'decryption key: {client_obj.symmetric_key}\n'
                                                f'hmac key: {client_obj.hmac_key}\n')
                                        f.write(full_header_info)
                                        f.write("Raw Full Message (serialized): " + repr(original_unencrypted) + "\n\n")

                                        # If the response packet is compressed, also log the uncompressed data
                                        if hasattr(response_packet, 'is_compressed') and response_packet.is_compressed:
                                            f.write(f"Compression: YES (uncompressed_size={response_packet.uncompressed_size})\n")
                                            # Get the uncompressed buffer (before compression was applied)
                                            if hasattr(response_packet, 'serialize_multimsg'):
                                                # For MultiMsg, get the raw uncompressed message buffer
                                                uncompressed_buffer = b""
                                                for msg in response_packet.messages:
                                                    length_bytes = len(msg).to_bytes(4, byteorder='little', signed=False)
                                                    uncompressed_buffer += length_bytes + msg
                                                f.write("Uncompressed Message Buffer: " + repr(uncompressed_buffer) + "\n\n")
                                        else:
                                            f.write("Compression: NO\n\n")

                                        f.write("----- Split Packets (if any) Below -----\n")
                                except Exception as log_e:
                                    self.log.error(f"Error logging full unencrypted message: {log_e}")

                            # If splitting is needed, record the full (encrypted) message length.
                            total_data_len = data_len
                            split_pkt_cnt = (total_data_len + max_data_size - 1) // max_data_size
                            seq_of_first_pkt = client_obj.sequence_number + 1

                            base_reply_packet = copy.copy(reply_packet)
                            base_reply_packet.split_pkt_cnt = split_pkt_cnt
                            base_reply_packet.seq_of_first_pkt = seq_of_first_pkt
                            base_reply_packet.data_len = total_data_len

                            data = reply_packet.data

                            # Split data into chunks.
                            for i in range(split_pkt_cnt):
                                # Use thread-safe sequence increment
                                sequence_num = client_obj.get_next_sequence_number()

                                start_index = i * max_data_size
                                end_index = min(start_index + max_data_size, total_data_len)
                                split_data = data[start_index:end_index]
                                split_data_len = len(split_data)

                                split_packet = CMPacket()
                                split_packet.magic = reply_packet.magic
                                split_packet.packetid = reply_packet.packetid
                                split_packet.priority_level = reply_packet.priority_level
                                split_packet.source_id = reply_packet.source_id
                                split_packet.destination_id = reply_packet.destination_id
                                split_packet.sequence_num = sequence_num
                                split_packet.last_recv_seq = reply_packet.last_recv_seq
                                split_packet.split_pkt_cnt = split_pkt_cnt
                                split_packet.seq_of_first_pkt = seq_of_first_pkt
                                split_packet.data_len = total_data_len
                                split_packet.size = split_data_len
                                split_packet.data = split_data

                                packets_to_send.append(split_packet)

                                # Create MessageInfo for this split packet
                                msg_info_list.append(MessageInfo(
                                    emsg_id=emsg_id,
                                    emsg_name=emsg_name,
                                    is_encrypted=is_encrypted,
                                    is_split=True,
                                    split_index=i,
                                    split_total=split_pkt_cnt,
                                    target_job_id=target_job_id,
                                    source_job_id=source_job_id
                                ))

                                # Log each split packet: header info and raw data (using repr for \x format)
                                if not capture_split_once:
                                    try:
                                        with open("logs/unencrypted_split_messages.txt", "a", encoding="utf-8") as f:
                                            split_header_info = (
                                                f"--- Split Packet {i+1} of {split_pkt_cnt} ---\n"
                                                f"Magic: {hex(split_packet.magic)}\n"
                                                f"PacketID: {split_packet.packetid}\n"
                                                f"Priority: {int.from_bytes(split_packet.priority_level, 'little')}\n"
                                                f"SourceID: {split_packet.source_id}\n"
                                                f"DestinationID: {split_packet.destination_id}\n"
                                                f"LastRecvSeq: {split_packet.last_recv_seq}\n"
                                                f"Sequence: {split_packet.sequence_num}\n"
                                                f"SplitPktCnt: {split_packet.split_pkt_cnt}\n"
                                                f"SeqOfFirstPkt: {split_packet.seq_of_first_pkt}\n"
                                                f"DataLen: {split_packet.data_len}\n"
                                                f"Size: {split_packet.size}\n"
                                            )
                                            f.write(split_header_info)
                                            f.write("Raw Data: " + repr(split_packet.data) + "\n\n")
                                    except Exception as log_e:
                                        self.log.error(f"Error logging split packet: {log_e}")
                            capture_split_once = True
                        else:
                            # Use thread-safe sequence increment
                            reply_packet.sequence_num = client_obj.get_next_sequence_number()
                            reply_packet.split_pkt_cnt = 1
                            reply_packet.seq_of_first_pkt = reply_packet.sequence_num
                            reply_packet.size = data_len
                            reply_packet.data_len = data_len
                            packets_to_send = [reply_packet]

                            # Create MessageInfo for this single packet
                            msg_info_list.append(MessageInfo(
                                emsg_id=emsg_id,
                                emsg_name=emsg_name,
                                is_encrypted=is_encrypted,
                                is_split=False,
                                target_job_id=target_job_id,
                                source_job_id=source_job_id
                            ))
                    else:
                        self.log.error(f"(response missing .data) No data in response packet for client {client_obj.ip_port[0]} {reply_packet.data}")
                        return
                else:
                    self.log.error(f"(no response in list) No data in response packet for client {client_obj.ip_port[0]} {reply_packet.data}")
                    return

                # Packets are now prepared with sequence numbers assigned
                # Store for sending after releasing the lock

            except Exception as e:
                tb = sys.exc_info()[2]
                self.log.error(f"CM Server Sendreply error: {e} \n Traceback: " + "".join(traceback.format_tb(tb)))
                raise e.with_traceback(tb)

        # Send packets OUTSIDE the lock to avoid blocking other threads during I/O
        # Sequence numbers are already assigned, so ordering is guaranteed
        # This significantly reduces lock contention for split packets with delays
        if packets_to_send:
            self._send_packets_sync(packets_to_send, client_obj.ip_port, msg_info_list)

    def _send_split_packets(self, packets, ip_port, msg_info_list: Optional[List[MessageInfo]] = None):
        """Helper method to send a list of split packets in order without blocking the main thread.
           Inserts a 1 second delay between sends to avoid overwhelming the socket buffers.
        """
        delay_between_packets = 0.1  # 1 second delay between split packets

        for i, packet in enumerate(packets):
            try:
                serialized_packet = packet.serialize()
                msg_info = msg_info_list[i] if msg_info_list and i < len(msg_info_list) else None
                self.serversocket.sendto(serialized_packet, ip_port, to_log=True, msg_info=msg_info)
            except Exception as e:
                self.log.error(f"Error sending split packet (seq {packet.sequence_num}): {e}")
            # pause before sending the next one
            time.sleep(delay_between_packets)

    def _send_packets_sync(self, packets, ip_port, msg_info_list: Optional[List[MessageInfo]] = None):
        """
        Send packets synchronously while holding the send lock.

        This ensures packets are sent in the exact order their sequence numbers
        were assigned, preventing the race condition where:
        - Thread A gets seq=5, Thread B gets seq=6
        - Thread B's packet is sent first due to thread scheduling
        - Client receives seq=6 then seq=5 (out of order)

        For single packets, no delay is needed.
        For multiple packets (split), a small delay prevents socket buffer overflow.
        """
        if not packets:
            return

        delay_between_packets = 0.05  # 50ms delay between split packets (smaller than async version)

        for i, packet in enumerate(packets):
            try:
                serialized_packet = packet.serialize()
                # Get message info for this packet if available
                msg_info = msg_info_list[i] if msg_info_list and i < len(msg_info_list) else None
                self.serversocket.sendto(serialized_packet, ip_port, to_log=True, msg_info=msg_info)
            except Exception as e:
                self.log.error(f"Error sending packet (seq {packet.sequence_num}): {e}")

            # Only delay between split packets, not after single packets
            if len(packets) > 1 and i < len(packets) - 1:
                time.sleep(delay_between_packets)


class CMServerUDP_27017(UDPNetworkHandlerCM, CMServerUDP):
    def __init__(self, port, in_config, master_server):
        CMServerUDP.__init__(self, port, in_config)
        UDPNetworkHandlerCM.__init__(self, in_config, port)
        self.server_type = "CMServerUDP_27017"
        # Server-specific initialization
        self.log = logging.getLogger("CM27017UDP")
        self.is_encrypted = True
        self.is_tcp = False
        self.master_server = master_server  # Store the reference to MasterServer

    def encrypt_packet(self, packet, client_obj: Client):
        # Override to implement specific encryption logic for 27017
        key = client_obj.symmetric_key
        encrypted_data = symmetric_encrypt(packet.data, key)
        return encrypted_data

    def decrypt_packet(self, packet, client_obj: Client):
        key = client_obj.symmetric_key
        try:
            packet.data = symmetric_decrypt(packet.data, key)
            # self.handle_decrypted(self, packet.data, client_obj)
        except:
            self.handle_unknown_command(self, packet.data, client_obj)
        return packet, True

    def handle_decryption_error(self, data, client_obj):
        with open("logs/decryption_error_cm_msgs.txt", 'a') as file:
            # Write the text to the file
            file.write(f'decryption key: {client_obj.symmetric_key}\n'
                       f'hmac key: {client_obj.hmac_key}'
                       f'data (raw): {data}\n')  # Adding a newline character to separate entries

    def handle_client(self, socket, address):
        super().handle_client(socket, address)  # Call the base class implementation


class CMServerUDP_27014(UDPNetworkHandlerCM, CMServerUDP):
    def __init__(self, port, in_config, master_server):
        CMServerUDP.__init__(self, port, in_config)
        UDPNetworkHandlerCM.__init__(self, in_config, port)
        self.server_type = "CMServerUDP_27014"
        self.log = logging.getLogger("CM27014UDP")
        self.is_encrypted = False
        self.is_tcp = False
        self.master_server = master_server  # Store the reference to MasterServer

    def handle_client(self, socket, address):
        super().handle_client(socket, address)  # Call the base class implementation