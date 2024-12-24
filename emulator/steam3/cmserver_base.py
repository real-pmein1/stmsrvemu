from __future__ import annotations

import copy
import datetime
import logging
import os
import sys
import threading
import traceback
from typing import Any, Callable, Dict, Union

from steam3 import Types, thread_local_data
from steam3.ClientManager import Client_Manager
from steam3.ClientManager.client import Client
from steam3.Handlers.DRM import handle_DRMProblemReport
from steam3.Handlers.UFS import handle_UFSGetFileListForApp
from steam3.Handlers.appinfo import handle_ClientAppInfoRequest,  handle_ClientAppInfoRequest_obsolete, handle_ClientAppInfoupdate
from steam3.Handlers.authentication import handle_AnonGameServerLogin, handle_AnonUserLogin, handle_ClientChangePassword, handle_ClientChangeStatus, handle_ClientLogOn_WithCredentials, handle_ClientLogOn_WithHash, handle_ClientLogin, handle_ClientLogin_PB, handle_CreateAccount, handle_CreateAccount2, handle_GetAppOwnershipTicket, handle_InformOfCreateAccount, handle_LogOff, handle_NewLoginKeyAccepted, handle_RegisterAuthTIcket
from steam3.Handlers.chat import handle_CreateChat, handle_FriendMessage, handle_JoinChat
from steam3.Handlers.friends import handle_AddFriend, handle_GetFriendsUserInfo, handle_InviteFriend, handle_RemoveFriend, handle_RequestFriendData, handle_SetIgnoreFriend
from steam3.Handlers.gameserver import handle_GS_DisconnectNotice, handle_GS_PlayerList, handle_GS_ServerType, handle_GS_StatusUpdate, handle_GS_UserPlaying, handle_GetUserAchievementStatus
from steam3.Handlers.guestpasses import handle_AckGuestPass, handle_RedeemGuestPass, handle_SendGuestPass
from steam3.Handlers.p2p import handle_P2PIntroducerMessage
from steam3.Handlers.purchase import handle_AckPurchaseReceipt, handle_CancelLicense, handle_CancelPurchase, handle_CompletePurchase, handle_GetFinalPrice, handle_GetGiftTargetList, handle_GetLegacyGameKey, handle_GetPurchaseReceipts, handle_GetVIPStatus, handle_InitPurchase, handle_RegisterKey
from steam3.Handlers.statistics import handle_AppUsageEvent, handle_ClientSteamUsageEvent, handle_ConnectionStats, handle_GamesPlayedStats, handle_GamesPlayedStats2, handle_GamesPlayedStats3, handle_GamesPlayedStats_deprecated, handle_GamesPlayedWithDataBlob, handle_GetUserStats, handle_NoUDPConnectivity
from steam3.Handlers.system import handle_Heartbeat,  handle_NatTraversalStatEvent, handle_ServiceCallResponse, handle_SystemIMAck, handle_VTTCert, handle_RequestValidationMail
from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMPacket,  ExtendedMsgHdr, GCMsgHdr, GCMsgHdrProto, MsgHdrProtoBuf, MsgHdr_deprecated

from steam3.utilities import getAccountId


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
            # print(msg)

            request_packet: Union[MsgHdr_deprecated, ExtendedMsgHdr, GCMsgHdr, MsgHdrProtoBuf, GCMsgHdrProto] = parsed_packet.parse_CMRequest()

            # The following is a check to determin if this is an extended/protobuf header or the deprecated-type header
            if type(request_packet) is not MsgHdr_deprecated:
                client_obj.is_newPacketType = True
                thread_local_data.extended_msg = copy.deepcopy(request_packet)

            if decrypted:
                print(f"packetid: {int(request_packet.eMsgID)} / {Types.get_enum_name(EMsg, request_packet.eMsgID)}")
                if not isinstance(request_packet, MsgHdrProtoBuf):
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
                    # EMsg.Multi:                                handle_MultiMessage,  # I do not believe the Steam Client EVER sends this type of message
                    EMsg.ClientLogon:                          handle_ClientLogin_PB,
                    EMsg.ClientLogOn_Deprecated:               handle_ClientLogin,
                    EMsg.ClientLogOnWithCredentials_Deprecated:handle_ClientLogOn_WithCredentials,
                    EMsg.ClientLogOnWithHash_Deprecated:       handle_ClientLogOn_WithHash,
                    EMsg.ClientAnonLogOn_Deprecated:           handle_AnonGameServerLogin,
                    EMsg.ClientLogOff:                         handle_LogOff,
                    EMsg.ClientInformOfCreateAccount:          handle_InformOfCreateAccount,
                    EMsg.ClientPasswordChange:                 handle_ClientChangePassword,
                    EMsg.ClientAnonUserLogOn_Deprecated:       handle_AnonUserLogin,
                    #EMsg.ClientAnonLogOn_Deprecated:           handle_AnonLogOn,

                    EMsg.ClientRegisterAuthTicketWithCM:       handle_RegisterAuthTIcket,
                    EMsg.ClientCreateAccount2:                 handle_CreateAccount2,
                    EMsg.ClientCreateAccount3:                 handle_CreateAccount,
                    EMsg.ClientRequestValidationMail:          handle_RequestValidationMail,

                    EMsg.ClientGamesPlayed:                    handle_GamesPlayedStats,
                    EMsg.ClientGamesPlayed_obsolete:           handle_GamesPlayedStats_deprecated,
                    EMsg.ClientGamesPlayed2_obsolete:          handle_GamesPlayedStats2,
                    EMsg.ClientGamesPlayed3_obsolete:          handle_GamesPlayedStats3,
                    EMsg.ClientConnectionStats:                handle_ConnectionStats,
                    EMsg.ClientNoUDPConnectivity:              handle_NoUDPConnectivity,
                    EMsg.ClientAppUsageEvent:                  handle_AppUsageEvent,
                    EMsg.ClientGetUserStats:                   handle_GetUserStats,

                    EMsg.ClientGamesPlayedWithDataBlob:        handle_GamesPlayedWithDataBlob,
                    EMsg.ClientRequestFriendData_deprecated:   handle_GetFriendsUserInfo,
                    EMsg.ClientSteamUsageEvent:                handle_ClientSteamUsageEvent,
                    EMsg.ClientNewLoginKeyAccepted:            handle_NewLoginKeyAccepted,

                    EMsg.ClientGameConnect_obsolete:           self.handle_unknown_command,  # client expects new ClientGameConnectToken handle_GameConnect, b'\xcf\x02\x00\x00 m\x88\x00\x01\x00\x10\x01-\xaa \x02\x01,\x92W\x1d\x00@\x01P\x00\x00\x00\\\x9e\xb6@\x87i\x01\x00\x14\x00\x00\x00}3\xa1"\xab\xdb\xf0\x91 m\x88\x00\x01\x00\x10\x01E\x1e@D'
                    EMsg.ClientGameEnded_obsolete:             self.handle_unknown_command,  # client expects NO response. handle_GameEnded, b'\xd1\x02\x00\x00 m\x88\x00\x01\x00\x10\x01-\xaa \x02\x01,\x92W\x1d\x00@\x01P\x00\x00\x00\\\x9e\xb6@\x87i\x01\x00\x14\x00\x00\x00e\x9eYD\x03"\x0f\xc5 m\x88\x00\x01\x00\x10\x01\x11\x1e@D'

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
                    #EMsg.ClientGetLicenses:                    build_LicenseResponse,
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
                    EMsg.GSGetUserAchievementStatus:           handle_GetUserAchievementStatus,

                    EMsg.ClientAppInfoRequest_obsolete:        handle_ClientAppInfoRequest_obsolete,
                    EMsg.ClientAppInfoRequest:                 handle_ClientAppInfoRequest,  # handle_AppInfoRequest,
                    EMsg.ClientAppInfoUpdate:                  handle_ClientAppInfoupdate,  # b'\x00\x00\x00\x00\x01'

                    EMsg.ClientHeartBeat:                      handle_Heartbeat,
                    EMsg.ClientSystemIMAck:                    handle_SystemIMAck,
                    EMsg.ClientServiceCallResponse:            handle_ServiceCallResponse,
                    EMsg.ClientVTTCert:                        handle_VTTCert,

                    EMsg.ClientP2PIntroducerMessage:           handle_P2PIntroducerMessage,
                    EMsg.ClientNatTraversalStatEvent:          handle_NatTraversalStatEvent,

                    EMsg.ClientUFSGetFileListForApp:           handle_UFSGetFileListForApp,

                    None:                                      self.handle_unknown_command  # Default handler for unknown commands
            }

            # Get handler
            handler = request_handlers.get(request_packet.eMsgID, self.handle_unknown_command)
            thread_local_copy = {"extended_msg": getattr(thread_local_data, "extended_msg", None)}

            def handler_thread(local_data):
                try:
                    # Copy thread-local data into the thread
                    thread_local_data.extended_msg = local_data["extended_msg"]

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
                        self.sendreply_thread(client_obj, reply_packets)
                except Exception as e:
                    traceback.print_exc()
                    self.log.error(f"Handler thread exception: {e}")
                    tb = sys.exc_info()[2]
                    self.log.error(''.join(traceback.format_tb(tb)))

            threading.Thread(target=handler_thread, args=(thread_local_copy,), daemon=True).start()

        except Exception as e:
            traceback.print_exc()
            self.log.error(f"cmserver exception: {e}")
            tb = sys.exc_info()[2]
            self.log.error(''.join(traceback.format_tb(tb)))
            raise e.with_traceback(tb)

    def sendreply_thread(self, client_obj, reply_packets):
        def thread_target():
            try:
                self.sendReply(client_obj, reply_packets)
            except Exception as e:
                traceback.print_exc()
                self.log.error(f"sendreply thread exception: {e}")
                tb = sys.exc_info()[2]
                self.log.error(''.join(traceback.format_tb(tb)))

        threading.Thread(target=thread_target, daemon=True).start()