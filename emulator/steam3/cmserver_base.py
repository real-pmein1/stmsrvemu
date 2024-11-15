import asyncio
import copy
import datetime
import logging
import os
import struct
import traceback
from typing import Any, Callable, Dict, Union

import globalvars
from steam3 import Types, thread_local_data
from steam3.ClientManager import Client_Manager
from steam3.ClientManager.client import Client
from steam3.Handlers.DRM import handle_DRMProblemReport
from steam3.Handlers.appinfo import handle_ClientAppInfoRequest, handle_ClientAppInfoRequest_obsolete, handle_ClientAppInfoupdate
from steam3.Handlers.authentication import handle_AnonGameServerLogin, handle_AnonUserLogin, handle_ClientChangePassword, handle_ClientChangeStatus, handle_ClientLogOn_WithCredentials, handle_ClientLogin, handle_CreateAccount, handle_CreateAccount2, handle_GetAppOwnershipTicket, handle_InformOfCreateAccount, handle_LogOff, handle_RegisterAuthTIcket
from steam3.Handlers.chat import handle_CreateChat, handle_FriendMessage, handle_JoinChat
from steam3.Handlers.connection import create_channel_encryption_request, create_conn_acceptresponse, handle_challengerequest
from steam3.Handlers.friends import handle_AddFriend, handle_GetFriendsUserInfo, handle_InviteFriend, handle_RemoveFriend, handle_RequestFriendData, handle_SetIgnoreFriend
from steam3.Handlers.gameserver import handle_GS_DisconnectNotice, handle_GS_PlayerList, handle_GS_ServerType, handle_GS_StatusUpdate, handle_GS_UserPlaying
from steam3.Handlers.guestpasses import handle_AckGuestPass, handle_RedeemGuestPass, handle_SendGuestPass
from steam3.Handlers.p2p import handle_P2PIntroducerMessage
from steam3.Handlers.purchase import handle_AckPurchaseReceipt, handle_CancelLicense, handle_CancelPurchase, handle_CompletePurchase, handle_GetFinalPrice, handle_GetGiftTargetList, handle_GetLegacyGameKey, handle_GetPurchaseReceipts, handle_GetVIPStatus, handle_InitPurchase, handle_RegisterKey
from steam3.Handlers.statistics import handle_AppUsageEvent, handle_ClientSteamUsageEvent, handle_ConnectionStats, handle_GamesPlayedStats, handle_GamesPlayedStats2, handle_GamesPlayedStats3, handle_GamesPlayedStats_deprecated, handle_GamesPlayedWithDataBlob, handle_GetUserStats
from steam3.Handlers.system import handle_Heartbeat, handle_MultiMessage, handle_NatTraversalStatEvent, handle_ServiceCallResponse, handle_SystemIMAck, handle_VTTCert
from steam3.Responses.auth_responses import build_LicenseResponse
from steam3.Types.emsg import EMsg
from steam3.Types.wrappers import ConnectionID
from steam3.cm_packet_utils import CMPacket, ExtendedMsgHdr, GCMsgHdr, GCMsgHdrProto, MasterMsg, MsgHdrProtoBuf, MsgHdr_deprecated

from steam3.utilities import getAccountId
from utilities import encryption
from utilities.encryption import calculate_crc32_bytes



def log_to_file(filename, data, client_ip, log_type):
    # Ensure the log directory exists
    os.makedirs("logs", exist_ok = True)

    # Get current date and time in the required format
    timestamp = datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S")

    # Write the data to the log file
    with open(filename, 'ab') as log_file:
        log_file.write(f"{log_type} - Client IP: {client_ip}, Time: {timestamp}\n".encode('ascii'))
        log_file.write(repr(data).encode('latin-1'))
        if isinstance(data, bytes):
            log_file.write(b'\n\n')  # Append the raw byte data
        else:
            log_file.write('\n\n')  # Append the raw byte data


def log_split_packet(packet, client_ip):
    # Log human-readable packet header details
    header_info = (
            f"Header: {packet.magic}, "
            f"Packet ID: {packet.packetid}, "
            f"Priority: {packet.priority_level}, "
            f"Source ID: {packet.source_id}, "
            f"Destination ID: {packet.destination_id}, "
            f"Sequence Num: {packet.sequence_num}, "
            f"Split Pkt Count: {packet.split_pkt_cnt}, "
            f"Data Length: {packet.data_len}, "
            f"Size: {packet.size}"
    )

    # Ensure the log directory exists
    os.makedirs("logs", exist_ok = True)

    # Get current date and time
    timestamp = datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S")

    # Write the data to the log file
    with open("logs/split_serialized.txt", 'a') as log_file:
        log_file.write(f"Client IP: {client_ip}, Time: {timestamp}\n")
        log_file.write(f"{header_info}\n\n")
        log_file.write(f"Data: {repr(packet.data)}\n\n")


class CMServer_Base:
    def __init__(self, port, in_config):
        self.log = logging.getLogger(f"CMUDP{port}")
        self.online_user_ids = set()
        self.pending_messages = []
        self.connectionid_count = 1024
        Client_Manager.cmserver_obj = self

    def encrypt_packet(self, packet, client_obj):
        # Hook method for postprocessing (e.g., encryption) outgoing packets
        # By default, does nothing; subclasses can override
        return packet.data

    def decrypt_packet(self, packet, client_obj):
        # Hook method for preprocessing (e.g., decryption)
        # By default, does nothing; subclasses can override
        return packet, False

    def sendReply(self, client_obj, response_packet_list: [list, ExtendedMsgHdr], packetID = None, priority_level = 1):
        """ Send a reply to a client. Takes a list of packets to send, and handles splitting the packets if necessary. """
        try:
            if not response_packet_list:
                return

            # Prepare the CMPacket for reply
            reply_packet = CMPacket()
            reply_packet.magic = 0x31305356
            reply_packet.packetid = b'\x06' if packetID is None else packetID
            reply_packet.priority_level = int(priority_level).to_bytes(1, 'little')
            reply_packet.source_id = client_obj.serverconnectionid
            reply_packet.destination_id = client_obj.connectionid
            reply_packet.last_recv_seq = client_obj.last_recvd_sequence

            if len(response_packet_list) == 1:
                response_packet = response_packet_list[0]
                if response_packet.data:
                    # Log the data before encryption
                    #log_to_file("logs/before_encryption.txt", response_packet.serialize(), client_obj.ip_port[0], "Before Encryption")

                    reply_packet.data = response_packet.serialize()

                    print(f'packet sent to client: {reply_packet.data}')

                    # Encrypt the packet and log the encrypted data
                    reply_packet.data = self.encrypt_packet(reply_packet, client_obj)
                    #log_to_file("logs/encrypted_data.txt", reply_packet.data, client_obj.ip_port[0], "Encrypted Data")

                    data_len = len(reply_packet.data)
                    max_data_size = 0x0d60  # Maximum data size per packet

                    if data_len > max_data_size:
                        # Data needs to be split into multiple packets
                        total_data_len = data_len
                        split_pkt_cnt = (total_data_len + max_data_size - 1) // max_data_size
                        seq_of_first_pkt = client_obj.sequence_number + 1  # Sequence number of the first split packet

                        # Prepare the base packet with common header fields
                        base_reply_packet = copy.copy(reply_packet)
                        base_reply_packet.split_pkt_cnt = split_pkt_cnt
                        base_reply_packet.seq_of_first_pkt = seq_of_first_pkt
                        base_reply_packet.data_len = total_data_len

                        packets_to_send = []
                        data = reply_packet.data

                        for i in range(split_pkt_cnt):
                            # Increment sequence number for each split packet
                            client_obj.sequence_number += 1
                            sequence_num = client_obj.sequence_number

                            # Create a new split packet
                            split_packet = copy.copy(base_reply_packet)
                            split_packet.sequence_num = sequence_num

                            # Extract the appropriate data chunk
                            start_index = i * max_data_size
                            end_index = min(start_index + max_data_size, total_data_len)
                            split_data = data[start_index:end_index]
                            split_data_len = len(split_data)

                            # Create a new split packet
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

                            # Log split packet data after serialization
                            #log_split_packet(split_packet, client_obj.ip_port[0])

                            packets_to_send.append(split_packet)
                    else:
                        # Data fits in a single packet
                        client_obj.sequence_number += 1
                        reply_packet.sequence_num = client_obj.sequence_number
                        reply_packet.split_pkt_cnt = 1
                        reply_packet.seq_of_first_pkt = reply_packet.sequence_num
                        reply_packet.size = data_len
                        reply_packet.data_len = data_len
                        packets_to_send = [reply_packet]
                else:
                    return  # No data to send
            else:
                return
                """# Process as MsgMulti
                msg_multi = MsgMulti()
                for response_packet in response_packet_list:
                    msg_multi.add(response_packet)
                # Serialize MsgMulti
                data_out = io.BytesIO()
                msg_multi.serialize(data_out)
                serialized_msg_multi = data_out.getvalue()
                reply_packet.data = serialized_msg_multi
                reply_packet.data = self.encrypt_packet(reply_packet.data, client_obj)
                reply_packet.size = len(reply_packet.data)
                reply_packet.data_len = len(reply_packet.data)"""

            # Serialize and send each packet
            for packet in packets_to_send:
                serialized_packet = packet.serialize()
                self.serversocket.sendto(serialized_packet, client_obj.ip_port)
                #self.serversocket.send(serialized_packet, to_log = False)
        except Exception as e:
            self.log.error(f"CM Server Sendreply error: {e}")

    def handle_client(self, data, address):
        try:
            clientid = str(address) + ": "
            self.log.info(f"{clientid}Connected to UDP CM Server")

            # keep an eye out for master server packets that get sent here:
            if data.startswith(b"\xff\xff\xff\xff"):
                self.master_server.handle_client(data, address, True)
                return

            # Extract TCP Header if it's a TCP connection
            if self.is_tcp:
                # Extract TCP Header if it's a TCP connection
                tcp_header_size = 20  # Standard TCP header size
                tcp_header = data[:tcp_header_size]  # First 20 bytes as TCP header
                tcp_fields = struct.unpack('!HHLLBBHHH', tcp_header)  # Unpack TCP header fields
                source_port, dest_port, seq_num, ack_num, data_offset_reserved_flags, \
                    window, checksum, urgent_pointer = tcp_fields[:8]

                # Strip the TCP header from the data
                data = data[tcp_header_size:]  # Process remaining data (after TCP header)

            packet = CMPacket()
            packet.is_tcp = self.is_tcp
            cm_packet = packet.parse(data)

            cm_packet_reply = copy.deepcopy(cm_packet)
            conn_type = "encrypted" if self.is_encrypted else "unencrypted"

            if packet.is_tcp:
                # TCP: packetid is an integer
                connection_request_ids = {0x00, 0x01, 0x04}
                challenge_request_id = 0x03
                disconnect_request_id = 0x05
                normal_packet_id = 0x06
                heartbeat_id = 0x07
            else:
                # UDP: packetid is a byte
                connection_request_ids = {b"\x00", b"\x01", b"\x04"}
                challenge_request_id = b"\x03"
                disconnect_request_id = b"\x05"
                normal_packet_id = b"\x06"
                heartbeat_id = b"\x07"

            if cm_packet.packetid in connection_request_ids:  # connection Request
                self.log.info(f"{clientid}[{conn_type}] Recieved Connection Request")
                cmidreply = create_conn_acceptresponse(cm_packet, cm_packet_reply)
                self.log.debug(f"Connect Request: {cm_packet}")
                #self.serversocket.send(cmidreply, to_log = False)
                self.serversocket.sendto(cmidreply, address)
                return

            elif cm_packet.packetid == challenge_request_id:  # challange Request
                self.log.info(f"{clientid}[{conn_type}] Recieved Challenge Request")
                self.log.debug(f"Challenge Request: {cm_packet}")
                cmidreply = handle_challengerequest(cm_packet, cm_packet_reply, address, self.connectionid_count)
                #self.serversocket.send(cmidreply, to_log = False)
                self.serversocket.sendto(cmidreply, address)
                if self.is_encrypted:
                    self.log.info(f"{clientid}[{conn_type}] Sending Encryption Handshake Request To Client")
                    cmidreply = create_channel_encryption_request(cm_packet, cm_packet_reply, self.connectionid_count)
                    #self.serversocket.send(cmidreply, to_log = False)
                    self.serversocket.sendto(cmidreply, address)
                client = Client(ip_port = address, connectionid = self.connectionid_count)
                Client_Manager.add_or_update_client(client)
                self.connectionid_count += 1
                return

            elif cm_packet.packetid == disconnect_request_id:  # Disconnection
                self.log.info(f"{clientid}Recieved Disconnect packet")
                client_obj = Client_Manager.get_client_by_identifier(address)

                cm_packet_reply.priority_level = b"\x04"
                cm_packet_reply.packetid = b"\x05"
                cm_packet_reply.size = 0
                cm_packet_reply.source_id = cm_packet.destination_id
                cm_packet_reply.destination_id = cm_packet.source_id
                cm_packet_reply.sequence_num = cm_packet.sequence_num + 1  # seq
                cm_packet_reply.last_recv_seq = cm_packet.sequence_num  # ack
                cm_packet_reply.split_pkt_cnt = 1  # split
                cm_packet_reply.seq_of_first_pkt = cm_packet_reply.sequence_num
                cm_packet_reply.data_len = 0
                cm_packet_reply.data = b"\x00"

                cmidreply = cm_packet_reply.serialize()

                #self.serversocket.send(cmidreply, to_log = False)
                self.serversocket.sendto(cmidreply, address)

                if client_obj:
                    is_app_session = client_obj.is_in_app
                    if is_app_session:
                        # User closed app
                        client_obj.disconnect_Game(self)
                    else:
                        # User went offline
                        client_obj.logoff_User(self)

                return

            elif cm_packet.packetid == normal_packet_id:  # Normal Packet/messages See EMsg.py
                client_obj = Client_Manager.get_client_by_identifier(ConnectionID(cm_packet.source_id))

                if b"\x18\x05" in data[36:39]:
                    # we decrypt the aes session key here
                    encrypted_message = cm_packet.data[28:156]
                    encrypted_message_crc32 = cm_packet.data[156:160]
                    self.log.debug(f"encrypted response: {cm_packet}")
                    key = encryption.get_aes_key(encrypted_message, encryption.network_key)
                    self.log.debug(f"Encrypted Session Key: {key}")
                    verification_local = calculate_crc32_bytes(encrypted_message)
                    verification_result = "Pass" if verification_local == encrypted_message_crc32 else "Fail"
                    self.log.debug(f"CRC32 Verification Result: packet crc: {encrypted_message_crc32}\nlocally verified crc: {verification_local}\nResult: {verification_result}")

                    client_obj.symmetric_key = key
                    client_obj.hmac_key = key[:16]

                    # send ChannelEncryptResult result = OK
                    cm_packet_reply.priority_level = b"\x02"
                    cm_packet_reply.packetid = b"\x06"
                    cm_packet_reply.size = 24
                    cm_packet_reply.source_id = cm_packet.destination_id
                    cm_packet_reply.destination_id = cm_packet.source_id
                    cm_packet_reply.sequence_num = 4  # seq
                    cm_packet_reply.last_recv_seq = cm_packet.sequence_num  # ack
                    cm_packet_reply.split_pkt_cnt = 1  # split
                    cm_packet_reply.seq_of_first_pkt = 4
                    cm_packet_reply.data_len = 24
                    cm_packet_reply.data = b'\x19\x05\x00\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\x01\x00\x00\x00'
                    handshake_confirmation = MsgHdr_deprecated(eMsgID = 0x1905,
                                                               accountID = 0xffffffff,
                                                               clientId2 = 0xffffffff,
                                                               sessionID = 0xffffffff,
                                                               data = b'\x01\x00\x00\x00'  # eResult, 01 is OK
                                                               )

                    # cm_packet_reply.data = handshake_confirmation.serialize()

                    cmidreply = cm_packet_reply.serialize()
                    # cm_packet_reply.data = self.encrypt_packet(cm_packet_reply, client_obj)
                    # cm_packet_reply.data_len = cm_packet_reply.size = handshake_confirmation.length
                    # client_obj.steamID = 1
                    #self.serversocket.send(cmidreply, to_log = False)
                    self.serversocket.sendto(cmidreply, address)
                    # self.sendReply(client_obj, [handshake_confirmation])
                    # self.sendReply(client_obj, [handshake_confirmation], b'\x06', 2)

                    return

                self.handle_CMPacket(cm_packet, client_obj)
                return

            elif cm_packet.packetid == heartbeat_id:  # ProcessHeartbeat / Datagram
                self.log.info(f"{clientid}Recieved Heartbeat")
                # self.build_update_response(cm_packet, address)
                client_obj = Client_Manager.get_client_by_identifier(address)
                # client_obj.renew_heartbeat()
                if client_obj is None:
                    client_obj = address
                    self.log.warning(f"{address} client_obj not found while attempting heartbeat")
                else:
                    client_obj.renew_heartbeat()

                handle_Heartbeat(self, cm_packet, client_obj, False)
                return

            else:
                client_obj = Client_Manager.get_client_by_identifier(address)
                self.log.error(f"{clientid}Recieved Unknown Packet Type: {cm_packet.packetid}")
                self.handle_unknown_command(self, cm_packet, client_obj)
                return
        except Exception as e:
            self.log.error(f"CM Handle client error: {e}")

    def handle_decrypted(self, cmserver_obj, packet: CMPacket, client_obj: Client):
        request_packet = packet.CMRequest
        client_address = client_obj.ip_port
        self.log.critical(f"packetid: {Types.get_enum_name(EMsg, request_packet.eMsgID)} ({request_packet.eMsgID})\n"
                          f"data: {request_packet.data}\n")

        # FIXME find a better file location
        with open("logs/decrypted_cm_msgs.txt", 'a') as file:
            # Write the text to the file
            file.write(f'{datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S")}:\t\t'
                       f'Address: {client_address[0]}:{client_address[1]}\n'
                       f'packetid: {Types.get_enum_name(EMsg, request_packet.eMsgID)} ({request_packet.eMsgID})\n'
                       f'data (raw): {request_packet.data}\n'
                       f'data (hex): {bytes(request_packet.data).hex()}\n\n')  # Adding a newline character to separate entries
        return -1

    def handle_unknown_command(self, cmserver_obj, packet: CMPacket, client_obj: Client):
        request_packet = packet.CMRequest
        client_address = client_obj.ip_port
        self.log.critical(f"packetid: {Types.get_enum_name(EMsg, request_packet.eMsgID)} ({request_packet.eMsgID})\n"
                          f"data: {request_packet.data}\n")

        with open("logs/unregistered_cm_msgs.txt", 'a') as file:
            # Write the text to the file
            file.write(f'{datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S")}:\t\t'
                       f'Address: {client_address[0]}:{client_address[1]}\n'
                       f'packetid: {Types.get_enum_name(EMsg, request_packet.eMsgID)} ({request_packet.eMsgID})\n'
                       f'data (raw): {request_packet.data}\n'
                       f'data (hex): {bytes(request_packet.data).hex()}\n\n')  # Adding a newline character to separate entries
        return -1

    def handle_CMPacket(self, parsed_packet, client_obj):
        try:
            client_obj.is_newPacketType = False
            parsed_packet, decrypted = self.decrypt_packet(parsed_packet, client_obj)
            parsed_packet.clientobj = client_obj
            #msg = MasterMsg(parsed_packet.data)

            # print(msg)

            # The following is a check to determin if this is an extended header or the deprecated-type header
            """if globalvars.steamui_ver >= 479:  # FIXME if we find clients prior to 479, check if they use extended messages or not
                client_obj.is_newPacketType = True
                request_packet: ExtendedMsgHdr = parsed_packet.parse_ExtendedCMRequest()
                thread_local_data.extended_msg = copy.deepcopy(request_packet)
            else:
                request_packet: MsgHdr_deprecated = parsed_packet.parse_CMRequest()
            request_packet: MsgHdr_deprecated = parsed_packet.parse_CMRequest()"""
            request_packet: Union[MsgHdr_deprecated, ExtendedMsgHdr, GCMsgHdr, MsgHdrProtoBuf, GCMsgHdrProto] = parsed_packet.parse_CMRequest()

            if not isinstance(request_packet, MsgHdr_deprecated):
                client_obj.is_newPacketType = True
                thread_local_data.extended_msg = copy.deepcopy(request_packet)

            if decrypted:
                print(f"packetid: {int(request_packet.eMsgID)} / {Types.get_enum_name(EMsg, request_packet.eMsgID)}")
                print(request_packet.data)

            if client_obj:
                if client_obj.steamID is None:
                    client_obj.steamID = getAccountId(request_packet)
                    Client_Manager.update_list(client_obj)
                client_obj.sequence_number = parsed_packet.last_recv_seq  # NOTE: KEEP THIS THE WAY IT IS OR STEAM/CM WILL BREAK
                client_obj.last_recvd_sequence = parsed_packet.sequence_num
                client_obj.serverconnectionid = parsed_packet.destination_id
                client_obj.sessionID = request_packet.sessionID
                client_obj.clientID2 = request_packet.clientId2
            else:
                return  # This means the client never went through the normal handshake process

            request_handlers: Dict[EMsg, Callable[[Any, CMPacket, Client], list]] = {
                    EMsg.Multi:                                handle_MultiMessage,

                    EMsg.ClientLogOn_Deprecated:               handle_ClientLogin,
                    EMsg.ClientLogOnWithCredentials_Deprecated:handle_ClientLogOn_WithCredentials,
                    EMsg.ClientAnonLogOn_Deprecated:           handle_AnonGameServerLogin,
                    EMsg.ClientLogOff:                         handle_LogOff,
                    EMsg.ClientInformOfCreateAccount:          handle_InformOfCreateAccount,
                    EMsg.ClientPasswordChange:                 handle_ClientChangePassword,
                    EMsg.ClientAnonUserLogOn_Deprecated:       handle_AnonUserLogin,
                    #EMsg.ClientAnonLogOn_Deprecated:           handle_AnonLogOn,
                    EMsg.ClientRegisterAuthTicketWithCM:       handle_RegisterAuthTIcket,
                    EMsg.ClientCreateAccount2:                 handle_CreateAccount2,
                    EMsg.ClientCreateAccount3:                 handle_CreateAccount,

                    EMsg.ClientGamesPlayed:                    handle_GamesPlayedStats,
                    EMsg.ClientGamesPlayed_obsolete:           handle_GamesPlayedStats_deprecated,
                    EMsg.ClientGamesPlayed2_obsolete:          handle_GamesPlayedStats2,
                    EMsg.ClientGamesPlayed3_obsolete:          handle_GamesPlayedStats3,
                    EMsg.ClientConnectionStats:                handle_ConnectionStats,
                    EMsg.ClientAppUsageEvent:                  handle_AppUsageEvent,
                    EMsg.ClientGetUserStats:                   handle_GetUserStats,
                    EMsg.ClientGamesPlayedWithDataBlob:        handle_GamesPlayedWithDataBlob,
                    EMsg.ClientRequestFriendData_deprecated:   handle_GetFriendsUserInfo,
                    EMsg.ClientSteamUsageEvent:                handle_ClientSteamUsageEvent,

                    EMsg.ClientGameConnect_obsolete:           self.handle_unknown_command,  # handle_GameConnect,
                    EMsg.ClientGameEnded_obsolete:             self.handle_unknown_command,  # handle_GameEnded,

                    EMsg.ClientInviteFriend:                   handle_InviteFriend,
                    EMsg.ClientAddFriend_deprecated:           handle_AddFriend,
                    EMsg.ClientAddFriend:                      handle_AddFriend,
                    EMsg.ClientRemoveFriend:                   handle_RemoveFriend,
                    EMsg.ClientRequestFriendData:              handle_RequestFriendData,
                    EMsg.ClientChangeStatus:                   handle_ClientChangeStatus,
                    EMsg.ClientSetIgnoreFriend:                handle_SetIgnoreFriend,

                    EMsg.ClientFriendMsg:                      handle_FriendMessage,
                    #EMsg.ClientChatMsg:                        self.handle_unknown_command,  # handle_ChatMessage,  # TODO
                    EMsg.ClientCreateChat:                     handle_CreateChat,
                    #EMsg.ClientChatAction:                     self.handle_unknown_command,
                    #EMsg.ClientChatInvite:                     self.handle_unknown_command,  # handle_ChatInvite,
                    EMsg.ClientJoinChat:                       handle_JoinChat,

                    EMsg.ClientRegisterKey:                    handle_RegisterKey,
                    EMsg.ClientGetLegacyGameKey:               handle_GetLegacyGameKey,
                    EMsg.ClientGetLicenses:                    build_LicenseResponse,
                    # 2006 get licenses packet: b'\xd           8\x02\x00\x00\x02\x00\x00\x00\x01\x00\x10\x01\x00\x00\x00\x00\x00'
                    EMsg.ClientCancelLicense:                  handle_CancelLicense,

                    EMsg.ClientGetGiftTargetList:              handle_GetGiftTargetList,
                    EMsg.ClientInitPurchase:                   handle_InitPurchase,
                    EMsg.ClientGetVIPStatus:                   handle_GetVIPStatus,  # used for click and buy
                    EMsg.ClientGetAppOwnershipTicket:          handle_GetAppOwnershipTicket,

                    EMsg.ClientDRMProblemReport:               handle_DRMProblemReport,

                    EMsg.ClientCompletePurchase:               handle_CompletePurchase,
                    EMsg.ClientCancelPurchase:                 handle_CancelPurchase,
                    EMsg.ClientGetPurchaseReceipts:            handle_GetPurchaseReceipts,
                    # get purchase receipt 2006 packet: b'\xe0\x02\x00\x00\x02\x00\x00\x00\x01\x00\x10\x01\x00\x00\x00\x00\x01'
                    EMsg.ClientAckPurchaseReceipt:             handle_AckPurchaseReceipt,  # Only contains 64bit transactionID

                    EMsg.ClientGetFinalPrice:                  handle_GetFinalPrice,  # contains 64bit transactionID
                    #EMsg.ClientUpdateCardInfo:                 self.handle_unknown_command,  # handle_UpdateCardInfo,
                    #EMsg.ClientDeleteCard:                     self.handle_unknown_command,  # handle_DeleteCard,
                    #EMsg.ClientGetCardList:                    self.handle_unknown_command,  # handle_GetCardList,

                    EMsg.ClientRedeemGuestPass:                handle_RedeemGuestPass,
                    EMsg.ClientSendGuestPass:                  handle_SendGuestPass,
                    EMsg.ClientAckGuestPass:                   handle_AckGuestPass,

                    #EMsg.ClientInviteUserToClan:               self.handle_unknown_command,  # handle_InviteUserToClan,
                    #EMsg.ClientAcknowledgeClanInvite:          self.handle_unknown_command,  # handle_AcknowledgeClanInvite,

                    EMsg.GSPlayerList:                         handle_GS_PlayerList,
                    EMsg.GSUserPlaying:                        handle_GS_UserPlaying,
                    EMsg.GSDisconnectNotice:                   handle_GS_DisconnectNotice,
                    EMsg.GSStatusUpdate_Unused:                handle_GS_StatusUpdate,
                    EMsg.GSServerType:                         handle_GS_ServerType,

                    EMsg.ClientAppInfoRequest_obsolete:        handle_ClientAppInfoRequest_obsolete,
                    EMsg.ClientAppInfoRequest:                 handle_ClientAppInfoRequest,  # handle_AppInfoRequest,
                    EMsg.ClientAppInfoUpdate:                  handle_ClientAppInfoupdate,  # b'\x00\x00\x00\x00\x01'

                    EMsg.ClientHeartBeat:                      handle_Heartbeat,
                    EMsg.ClientSystemIMAck:                    handle_SystemIMAck,
                    EMsg.ClientServiceCallResponse:            handle_ServiceCallResponse,
                    EMsg.ClientVTTCert:                        handle_VTTCert,

                    EMsg.ClientP2PIntroducerMessage:           handle_P2PIntroducerMessage,
                    EMsg.ClientNatTraversalStatEvent:          handle_NatTraversalStatEvent,

                    None:                                      self.handle_unknown_command  # Default handler for unknown commands
            }
            try:
                handler = request_handlers.get(request_packet.eMsgID)
            except:
                self.handle_unknown_command(self, parsed_packet, client_obj)
            # print(request_packet.eMsgID)

            if handler:
                skip = 0
                reply_packets = handler(self, parsed_packet, client_obj)

                if isinstance(reply_packets, list):
                    packet_nb = len(reply_packets)
                else:
                    if reply_packets == -1:
                        skip = 1
                    else:
                        reply_packets = [reply_packets]
                if skip != 1:
                    self.sendReply(client_obj, reply_packets)
            else:
                self.handle_unknown_command(self, parsed_packet, client_obj)
        except Exception as e:
            traceback.print_exc()
            self.log.error(f"cmserver exception: {e}")