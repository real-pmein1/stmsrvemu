from __future__ import annotations

import copy
import datetime
import logging
import os
import sys
import threading
import traceback
from typing import Any, Callable, Dict, Union
from steam3.Handlers.lobbies import handle_ClientGetLobbyList_obsolete, handle_ClientGetNumberOfCurrentPlayers, handle_ClientGetLobbyMetadata, handle_ClientCreateLobby, handle_ClientJoinLobby

from steam3 import Types, thread_local_data
from steam3.ClientManager import Client_Manager
from steam3.ClientManager.client import Client
from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMPacket,  ExtendedMsgHdr, GCMsgHdr, GCMsgHdrProto, MsgHdrProtoBuf, MsgHdr_deprecated
from utilities.impsocket import MessageInfo
from steam3.Handlers.DRM import handle_DRMProblemReport, handle_DRMDownloadRequest, handle_FileXferRequest, handle_FileXferDataAck, handle_DFSDownloadStatus, handle_DFSEndSession
from steam3.Handlers.UFS import (
    handle_ClientUFSFileUploadRequest,
    handle_UFSGetFileListForApp,
    handle_ClientUFSLoginRequest,
    handle_ClientUFSDownloadRequest,
    handle_ClientUFSUploadFileChunk,
)
from steam3.Handlers.appinfo import handle_ClientAppInfoRequest,  handle_ClientAppInfoRequest_obsolete, handle_ClientAppInfoupdate
from steam3.Handlers.authentication import handle_AnonGameServerLogin, handle_AnonUserLogin, handle_ClientChangePassword,  handle_ClientLogOn_WithCredentials, handle_ClientLogOn_WithHash, handle_ClientLogin, handle_ClientLogin_PB, handle_CreateAccount, handle_CreateAccount2, handle_GetAppOwnershipTicket, handle_InformOfCreateAccount, handle_LogOff, handle_NewLoginKeyAccepted, handle_RegisterAuthTIcket
from steam3.Handlers.chat import (
    handle_ClientCreateChat, handle_ClientJoinChat, handle_ClientChatMsg, handle_ClientChatAction,
    handle_ClientChatInvite, handle_FriendMessage
)
from steam3.Handlers.clan import (
    handle_InviteUserToClan, handle_AcknowledgeClanInvite
)
from steam3.Handlers.friends import handle_AddFriend, handle_ClientChangeStatus, handle_GetFriendsUserInfo, handle_InviteFriend, handle_RemoveFriend, handle_RequestFriendData, handle_SetIgnoreFriend
from steam3.Handlers.gameserver import handle_ClientGameConnect_obsolete, handle_ClientGameEnded_obsolete, handle_GS_DisconnectNotice, handle_GS_PlayerList, handle_GS_ServerType, handle_GS_StatusUpdate, handle_GS_UserPlaying, handle_GS_UserPlaying2, handle_GS_GetUserAchievementStatus, handle_GS_AssociateWithClan
from steam3.Handlers.gameserver_items import (
    handle_GS_GetUserGroupStatus,
    handle_GS_LoadItems,
    handle_GS_GrantItem,
    handle_GS_CreateItem,
    handle_GS_DeleteTempItem,
    handle_GS_DeleteAllTempItems,
    handle_GS_UpdateItemQuantity,
    handle_GS_GetItemBlob,
    handle_GS_SetItemBlob,
)
from steam3.Handlers.guestpasses import handle_AckGuestPass, handle_RedeemGuestPass, handle_SendGuestPass
from steam3.Handlers.p2p import (
    handle_P2PIntroducerMessage,
    handle_P2PTrackerMessage,
    handle_P2PConnectionInfo,
    handle_P2PConnectionFailInfo,
    handle_UDSP2PSessionStarted,
    handle_UDSP2PSessionEnded,
    handle_VoiceCallPreAuthorize,
    handle_VoiceCallPreAuthorizeResponse,
)
from steam3.Handlers.purchase import handle_AckPurchaseReceipt, handle_CancelLicense, handle_CancelPurchase, handle_CompletePurchase, handle_GetFinalPrice, handle_GetGiftTargetList, handle_GetLegacyGameKey, handle_GetPurchaseReceipts, handle_GetVIPStatus, handle_InitPurchase, handle_RegisterKey, handle_ClientGetLicenses, handle_PurchaseWithMachineID, handle_LookupKey, handle_PreviousClickAndBuyAccount
from steam3.Handlers.statistics import handle_AppUsageEvent, handle_ClientStat2, handle_ClientSteamUsageEvent, handle_ConnectionStats, handle_GamesPlayedStats, handle_GamesPlayedStats2, handle_GamesPlayedStats3, handle_GamesPlayedStats_deprecated, handle_GamesPlayedWithDataBlob, handle_GetUserStats, handle_NoUDPConnectivity, handle_ClientGetUserStats, handle_ClientStoreUserStats, handle_ClientStoreUserStats2
from steam3.Handlers.system import handle_Heartbeat,  handle_NatTraversalStatEvent, handle_ServiceCallResponse, handle_SystemIMAck, handle_VTTCert, handle_RequestValidationMail
from steam3.Handlers.leaderboard import handle_ClientLBSFindOrCreate, handle_ClientLBSGetLBEntries, handle_ClientLBSSetScore
from steam3.Handlers.inventory import (
    handle_ClientLoadItems,
    handle_ClientUpdateInvPos,
    handle_ClientDropItem,
    handle_ClientGetItemBlob,
    handle_ClientSetItemBlob,
)


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
        self._max_users = 1000  # Used for the server load ONLY
        Client_Manager.cmserver_obj = self

        # Initialize the JobManager for job tracking and routing
        try:
            from steam3.Managers.JobManager import get_job_manager
            self.job_manager = get_job_manager()
            self.job_manager.start_cleanup_thread(interval_seconds=5.0)
            self.log.info("JobManager initialized and cleanup thread started")
        except Exception as e:
            self.log.warning(f"Failed to initialize JobManager: {e}")
            self.job_manager = None

    # === JOB MANAGEMENT METHODS ===

    def create_job(self, name: str, client_obj: 'Client', emsg: int = 0,
                   source_job_id: int = -1, timeout_seconds: float = 30.0):
        """
        Create a new job for tracking a request/response pair.

        Args:
            name: Name of the job for debugging.
            client_obj: The client this job is associated with.
            emsg: The EMsg type of the request.
            source_job_id: The sourceJobID from the request (for response routing).
            timeout_seconds: Timeout for this job.

        Returns:
            The created Job object, or None if JobManager is not available.
        """
        if self.job_manager is None:
            return None

        from steam3.Managers.JobManager import Job
        job = self.job_manager.create_job(
            name=name,
            client=client_obj,
            source_job_id=source_job_id,
            emsg=emsg,
            timeout_seconds=timeout_seconds
        )
        return job

    def register_pending_response(self, job, expected_emsg: int = 0,
                                   timeout_seconds: float = 30.0):
        """
        Register a job as waiting for a response message.

        Args:
            job: The Job object waiting for a response.
            expected_emsg: The EMsg expected in the response.
            timeout_seconds: Timeout for waiting.
        """
        if self.job_manager is None or job is None:
            return

        self.job_manager.register_pending_response(
            job=job,
            expected_emsg=expected_emsg,
            timeout_seconds=timeout_seconds
        )

    def route_incoming_message(self, target_job_id: int, packet, emsg: int = 0) -> bool:
        """
        Try to route an incoming message to a waiting job.

        Args:
            target_job_id: The targetJobID from the incoming message.
            packet: The received packet.
            emsg: The EMsg of the received packet.

        Returns:
            True if message was routed to a job, False otherwise.
        """
        if self.job_manager is None:
            return False

        return self.job_manager.route_message_to_job(
            target_job_id=target_job_id,
            packet=packet,
            emsg=emsg
        )

    def complete_job(self, job, result=None):
        """
        Mark a job as completed and remove it.

        Args:
            job: The Job object or job ID.
            result: Optional result data.
        """
        if self.job_manager is None:
            return

        if hasattr(job, 'job_id'):
            self.job_manager.complete_job(job.job_id, result)
        else:
            self.job_manager.complete_job(job, result)

    def fail_job(self, job, reason: str = "Unknown"):
        """
        Mark a job as failed and remove it.

        Args:
            job: The Job object or job ID.
            reason: Reason for failure.
        """
        if self.job_manager is None:
            return

        if hasattr(job, 'job_id'):
            self.job_manager.fail_job(job.job_id, reason)
        else:
            self.job_manager.fail_job(job, reason)

    def get_job_stats(self):
        """Get current job statistics."""
        if self.job_manager is None:
            return None
        return self.job_manager.get_stats()

    def get_current_user_count(self) -> int:
        """How many clients (TCP or UDP) are currently connected."""
        # Client_Manager holds every live connection in clients_by_connid
        from steam3.ClientManager import Client_Manager
        return len(Client_Manager.clients_by_connid)

    def get_connection_load(self) -> int:
        """
        0?100% based on current connections vs. self._max_users.
        """
        count = self.get_current_user_count()
        # integer percentage
        pct = (count * 100) // self._max_users
        # clamp to 0?100
        if pct < 0:
            return 0
        if pct > 100:
            return 100
        return pct

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

        # Ensure the directory exists
        os.makedirs("logs", exist_ok=True)

        # Open the file in append mode
        with open("logs/decrypted_cm_msgs.txt", 'a') as file:
            file.write(f'{datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S")}:\t\t'
                       f'Address: {client_address[0]}:{client_address[1]}\n'
                       f'packetid: {Types.get_enum_name(EMsg, request_packet.eMsgID)} ({request_packet.eMsgID})\n'
                       f'data (raw): {request_packet.data}\n'
                       f'data (hex): {bytes(request_packet.data).hex()}\n\n')  # Adding a newline character to separate entries
        return -1

    def handle_unknown_command(self, cmserver_obj, packet: CMPacket, client_obj: Client):
        request_packet = packet.CMRequest
        try:
            client_address = client_obj.ip_port
        except Exception as e:
            client_address = ["1.2.3.4", "9999"]

        try:
            emessageID = request_packet.eMsgID
        except Exception as e:
            emessageID = 0

        try:
            emessageData = request_packet.data
        except Exception as e:
            emessageData = 0
        
        self.log.critical(f"packetid: {Types.get_enum_name(EMsg, emessageID)} ({emessageID})\n"
                          f"data: {emessageData}\n")

        # Ensure the directory exists
        os.makedirs("logs", exist_ok=True)

        # Open the file in append mode
        with open("logs/unregistered_cm_msgs.txt", 'a') as file:
            file.write(f'{datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S")}:\t\t'
                       f'Address: {client_address[0]}:{client_address[1]}\n'
                       f'packetid: {Types.get_enum_name(EMsg, emessageID)} ({emessageID})\n'
                       f'data (raw): {emessageData}\n'
                       f'data (hex): {bytes(emessageData).hex()}\n\n')  # Adding a newline character to separate entries
        return -1

    def handle_CMPacket(self, parsed_packet, client_obj):
        try:
            if client_obj:
                client_obj.is_newPacketType = False
                parsed_packet, decrypted = self.decrypt_packet(parsed_packet, client_obj)
                parsed_packet.clientobj = client_obj
                # print(msg)

                request_packet: Union[MsgHdr_deprecated, ExtendedMsgHdr, GCMsgHdr, MsgHdrProtoBuf, GCMsgHdrProto] = parsed_packet.parse_CMRequest()

                # Check if packet parsing failed (e.g., empty data from client disconnect)
                if request_packet is None:
                    self.log.warning(f"Received empty or malformed packet from {client_obj.ip_port}, ignoring")
                    return -1

                # Log decrypted packet through impsocket's log_packet method
                emsg_id = request_packet.eMsgID
                emsg_name = Types.get_enum_name(EMsg, emsg_id)
                target_job = getattr(request_packet, 'targetJobID', None)
                source_job = getattr(request_packet, 'sourceJobID', None)

                msg_info = MessageInfo(
                    emsg_id=emsg_id,
                    emsg_name=emsg_name,
                    is_encrypted=self.is_encrypted,
                    target_job_id=target_job,
                    source_job_id=source_job
                )

                # Log through impsocket for centralized logging
                self.serversocket.log_packet(
                    address=client_obj.ip_port,
                    direction="Received",
                    data=parsed_packet.data,
                    msg_info=msg_info
                )

                if not self.is_tcp:
                    # === SEQUENCE NUMBER VALIDATION ===
                    # NOTE: Sequence validation and duplicate detection is now handled in
                    # cmserver_udp.py BEFORE calling handle_CMPacket. Duplicates are dropped
                    # and ACKed there. By the time we reach this point, the packet has already
                    # been validated as acceptable (in-order or within tolerance).
                    #
                    # The ACK field check below is still useful for debugging client issues.
                    if client_obj.sequence_number > 0 and parsed_packet.last_recv_seq > 0:
                        if parsed_packet.last_recv_seq > client_obj.sequence_number:
                            self.log.debug(
                                f"ACK too high from {client_obj.ip_port}: client ACKs {parsed_packet.last_recv_seq}, "
                                f"but we've only sent up to {client_obj.sequence_number}"
                            )
                    # === END SEQUENCE NUMBER VALIDATION ===

                if type(request_packet) is not MsgHdr_deprecated:
                    client_obj.is_newPacketType = True
                    thread_local_data.extended_msg = copy.deepcopy(request_packet)

                    # Create job context for proper job ID routing
                    # This is the new explicit job context system (TinServer-style)
                    if hasattr(client_obj, 'job_registry') and client_obj.job_registry:
                        emsg_name = Types.get_enum_name(EMsg, request_packet.eMsgID) or str(request_packet.eMsgID)
                        client_obj.job_registry.create_context(request_packet, handler_name=emsg_name)

                    # Cache the sourceJobID on the client for fallback job routing
                    # This ensures the response can find the correct targetJobID even if
                    # thread_local_data is not properly propagated
                    if hasattr(request_packet, 'sourceJobID') and request_packet.sourceJobID != -1:
                        client_obj.last_request_source_job_id = request_packet.sourceJobID
                        self.log.debug(f"Cached sourceJobID={request_packet.sourceJobID:#x} on client")
                    else:
                        client_obj.last_request_source_job_id = None

                """if decrypted:
                    print(f"packetid: {int(request_packet.eMsgID)} / {Types.get_enum_name(EMsg, request_packet.eMsgID)}")
                    if not isinstance(request_packet, MsgHdrProtoBuf):
                        print(request_packet.data)"""

                if client_obj:
                    if client_obj.steamID is None:
                        from steam3.Types.steamid import SteamID
                        client_obj.steamID = SteamID.from_raw(request_packet.steamID)
                        # Convert to int since get_accountID() returns an AccountID wrapper
                        client_obj.accountID = int(client_obj.steamID.get_accountID())
                        Client_Manager.update_list(client_obj)
                    # === SEQUENCE TRACKING UPDATE ===
                    # For UDP: Sequence tracking already handled in cmserver_udp.py before
                    # calling handle_CMPacket (including duplicate detection)
                    # For TCP: No sequence tracking needed (reliable transport)
                    #
                    # We only update serverconnectionid here, not sequence numbers
                    client_obj.serverconnectionid = parsed_packet.destination_id
                    client_obj.sessionID = request_packet.sessionID

                else:  # This means the client never went through the normal handshake process
                    self.log.error(f"[CMServer_Base:handle_CMPacket]: ({self.serversocket.getclientip()}) Connection attempted to send packets without proper handshake!!")
                    return

                request_handlers: Dict[EMsg, Callable[[Any, CMPacket, Client], list]] = {
                        EMsg.ClientLogon:                          handle_ClientLogin_PB,
                        EMsg.ClientLogOn_Deprecated:               handle_ClientLogin,
                        EMsg.ClientLogOnWithCredentials_Deprecated:handle_ClientLogOn_WithCredentials,
                        EMsg.ClientLogOnWithHash_Deprecated:       handle_ClientLogOn_WithHash,
                        EMsg.ClientAnonLogOn_Deprecated:           handle_AnonGameServerLogin,
                        EMsg.ClientLogOff:                         handle_LogOff,
                        EMsg.ClientInformOfCreateAccount:          handle_InformOfCreateAccount,
                        EMsg.ClientPasswordChange:                 handle_ClientChangePassword,
                        EMsg.ClientAnonUserLogOn_Deprecated:       handle_AnonUserLogin,

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
                        EMsg.ClientGetUserStats:                   handle_ClientGetUserStats,
                        EMsg.ClientStoreUserStats:                 handle_ClientStoreUserStats,
                        EMsg.ClientStoreUserStats2:                handle_ClientStoreUserStats2,
                        EMsg.ClientStat2:                          handle_ClientStat2,

                        EMsg.ClientGamesPlayedWithDataBlob:        handle_GamesPlayedWithDataBlob,
                        EMsg.ClientRequestFriendData_deprecated:   handle_GetFriendsUserInfo,
                        EMsg.ClientSteamUsageEvent:                handle_ClientSteamUsageEvent,
                        EMsg.ClientNewLoginKeyAccepted:            handle_NewLoginKeyAccepted,

                        EMsg.ClientGameConnect_obsolete:           handle_ClientGameConnect_obsolete,  # client expects new ClientGameConnectToken handle_GameConnect, b'\xcf\x02\x00\x00 m\x88\x00\x01\x00\x10\x01-\xaa \x02\x01,\x92W\x1d\x00@\x01P\x00\x00\x00\\\x9e\xb6@\x87i\x01\x00\x14\x00\x00\x00}3\xa1"\xab\xdb\xf0\x91 m\x88\x00\x01\x00\x10\x01E\x1e@D'
                        EMsg.ClientGameEnded_obsolete:             handle_ClientGameEnded_obsolete,  # client expects NO response. handle_GameEnded, b'\xd1\x02\x00\x00 m\x88\x00\x01\x00\x10\x01-\xaa \x02\x01,\x92W\x1d\x00@\x01P\x00\x00\x00\\\x9e\xb6@\x87i\x01\x00\x14\x00\x00\x00e\x9eYD\x03"\x0f\xc5 m\x88\x00\x01\x00\x10\x01\x11\x1e@D'

                        EMsg.ClientInviteFriend:                   handle_InviteFriend,
                        EMsg.ClientAddFriend_deprecated:           handle_AddFriend,
                        EMsg.ClientAddFriend:                      handle_AddFriend,
                        EMsg.ClientRemoveFriend:                   handle_RemoveFriend,
                        EMsg.ClientRequestFriendData:              handle_RequestFriendData,
                        EMsg.ClientChangeStatus:                   handle_ClientChangeStatus,
                        EMsg.ClientSetIgnoreFriend:                handle_SetIgnoreFriend,


                        EMsg.ClientFriendMsg:                      handle_FriendMessage,
                        EMsg.ClientChatMsg:                        handle_ClientChatMsg,
                        EMsg.ClientCreateChat:                     handle_ClientCreateChat,
                        EMsg.ClientChatAction:                     handle_ClientChatAction,
                        EMsg.ClientChatInvite:                     handle_ClientChatInvite,
                        EMsg.ClientJoinChat:                       handle_ClientJoinChat,
                        EMsg.ClientGetLobbyList_obsolete:          handle_ClientGetLobbyList_obsolete,
                        EMsg.ClientGetLobbyMetadata:               handle_ClientGetLobbyMetadata,
                        EMsg.ClientGetNumberOfCurrentPlayers:      handle_ClientGetNumberOfCurrentPlayers,
                        EMsg.ClientMMSCreateLobby:                 handle_ClientCreateLobby,
                        EMsg.ClientMMSJoinLobby:                   handle_ClientJoinLobby,

                        EMsg.ClientRegisterKey:                    handle_RegisterKey,
                        EMsg.ClientGetLegacyGameKey:               handle_GetLegacyGameKey,
                        EMsg.ClientGetLicenses:                    handle_ClientGetLicenses,
                        EMsg.ClientCancelLicense:                  handle_CancelLicense,

                        EMsg.ClientGetGiftTargetList:              handle_GetGiftTargetList,
                        EMsg.ClientInitPurchase:                   handle_InitPurchase,
                        EMsg.ClientGetVIPStatus:                   handle_GetVIPStatus,  # used for click and buy
                        EMsg.ClientGetAppOwnershipTicket:          handle_GetAppOwnershipTicket,

                        EMsg.ClientDRMProblemReport:               handle_DRMProblemReport,
                        EMsg.ClientDRMDownloadRequest:             handle_DRMDownloadRequest,
                        EMsg.FileXferRequest:                	   handle_FileXferRequest,
                        EMsg.FileXferDataAck:                      handle_FileXferDataAck,
                        EMsg.ClientDFSDownloadStatus:        	   handle_DFSDownloadStatus,
                        EMsg.ClientDFSEndSession:                  handle_DFSEndSession,

                        EMsg.ClientCompletePurchase:               handle_CompletePurchase,
                        EMsg.ClientCancelPurchase:                 handle_CancelPurchase,
                        EMsg.ClientGetPurchaseReceipts:            handle_GetPurchaseReceipts,
                        EMsg.ClientAckPurchaseReceipt:             handle_AckPurchaseReceipt,  # Only contains 64bit transactionID
                        EMsg.ClientPurchaseWithMachineID:          handle_PurchaseWithMachineID,
                        EMsg.ClientLookupKey:                      handle_LookupKey,
                        EMsg.ClientPreviousClickAndBuyAccount:     handle_PreviousClickAndBuyAccount,

                        EMsg.ClientGetFinalPrice:                  handle_GetFinalPrice,  # contains 64bit transactionID
                        #EMsg.ClientUpdateCardInfo:                 self.handle_unknown_command,  # handle_UpdateCardInfo,
                        #EMsg.ClientDeleteCard:                     self.handle_unknown_command,  # handle_DeleteCard,
                        #EMsg.ClientGetCardList:                    self.handle_unknown_command,  # handle_GetCardList,

                        EMsg.ClientRedeemGuestPass:                handle_RedeemGuestPass,
                        EMsg.ClientSendGuestPass:                  handle_SendGuestPass,
                        EMsg.ClientAckGuestPass:                   handle_AckGuestPass,

                        EMsg.ClientInviteUserToClan:               handle_InviteUserToClan,
                        EMsg.ClientAcknowledgeClanInvite:          handle_AcknowledgeClanInvite,

                        EMsg.GSPlayerList:                         handle_GS_PlayerList,
                        EMsg.GSUserPlaying:                        handle_GS_UserPlaying,
                        EMsg.GSUserPlaying2:                       handle_GS_UserPlaying2,
                        EMsg.GSDisconnectNotice:                   handle_GS_DisconnectNotice,
                        EMsg.GSStatusUpdate_Unused:                handle_GS_StatusUpdate,
                        EMsg.GSServerType:                         handle_GS_ServerType,
                        EMsg.GSGetUserAchievementStatus:           handle_GS_GetUserAchievementStatus,
                        EMsg.GSGetUserGroupStatus:                 handle_GS_GetUserGroupStatus,
                        EMsg.GSLoadItems:                          handle_GS_LoadItems,
                        EMsg.GSGrantItem:                          handle_GS_GrantItem,
                        EMsg.GSCreateItem:                         handle_GS_CreateItem,
                        EMsg.GSDeleteTempItem:                     handle_GS_DeleteTempItem,
                        EMsg.GSDeleteAllTempItems:                 handle_GS_DeleteAllTempItems,
                        EMsg.GSUpdateItemQuantity:                 handle_GS_UpdateItemQuantity,
                        EMsg.GSAssociateWithClan:                  handle_GS_AssociateWithClan,

                        EMsg.ClientAppInfoRequest_obsolete:        handle_ClientAppInfoRequest_obsolete,
                        EMsg.ClientAppInfoRequest:                 handle_ClientAppInfoRequest,
                        EMsg.ClientAppInfoUpdate:                  handle_ClientAppInfoupdate,

                        EMsg.ClientHeartBeat:                      handle_Heartbeat,
                        EMsg.ClientSystemIMAck:                    handle_SystemIMAck,
                        EMsg.ClientServiceCallResponse:            handle_ServiceCallResponse,
                        EMsg.ClientVTTCert:                        handle_VTTCert,

                        EMsg.ClientP2PIntroducerMessage:           handle_P2PIntroducerMessage,
                        EMsg.ClientP2PTrackerMessage:              handle_P2PTrackerMessage,
                        EMsg.ClientP2PConnectionInfo:              handle_P2PConnectionInfo,
                        EMsg.ClientP2PConnectionFailInfo:          handle_P2PConnectionFailInfo,
                        EMsg.ClientUDSP2PSessionStarted:           handle_UDSP2PSessionStarted,
                        EMsg.ClientUDSP2PSessionEnded:             handle_UDSP2PSessionEnded,
                        EMsg.ClientVoiceCallPreAuthorize:          handle_VoiceCallPreAuthorize,
                        EMsg.ClientVoiceCallPreAuthorizeResponse:  handle_VoiceCallPreAuthorizeResponse,
                        EMsg.ClientNatTraversalStatEvent:          handle_NatTraversalStatEvent,

                        EMsg.ClientUFSGetFileListForApp:           handle_UFSGetFileListForApp,
                        EMsg.ClientUFSLoginRequest:                handle_ClientUFSLoginRequest,
                        EMsg.ClientUFSUploadFileRequest:           handle_ClientUFSFileUploadRequest,
                        EMsg.ClientUFSDownloadRequest:             handle_ClientUFSDownloadRequest,
                        EMsg.ClientUFSUploadFileChunk:             handle_ClientUFSUploadFileChunk,

                        EMsg.ClientLBSFindOrCreateLB:              handle_ClientLBSFindOrCreate,
                        EMsg.ClientLBSGetLBEntries:                handle_ClientLBSGetLBEntries,
                        EMsg.ClientLBSSetScore:                    handle_ClientLBSSetScore,

                        EMsg.ClientLoadItems:                      handle_ClientLoadItems,
                        EMsg.ClientUpdateInvPos:                   handle_ClientUpdateInvPos,
                        EMsg.ClientDropItem:                       handle_ClientDropItem,
                        EMsg.ClientGetItemBlob:                    handle_ClientGetItemBlob,
                        EMsg.ClientSetItemBlob:                    handle_ClientSetItemBlob,

                        None:                                      self.handle_unknown_command  # Default handler for unknown commands
                }
                handler = request_handlers.get(request_packet.eMsgID, self.handle_unknown_command)

                # Log packet processing (use debugplus for heartbeat to reduce noise)
                handler_name = handler.__name__ if hasattr(handler, '__name__') else str(handler)
                if handler_name == 'handle_Heartbeat':
                    self.log.debugplus(f"PROCESSING: {handler_name}")
                else:
                    self.log.info(f"PROCESSING: {handler_name}")

                # Run handler directly in current thread (which is from the worker pool)
                # This eliminates the thread explosion that occurs with 3+ clients
                # The worker pool already provides concurrency bounds
                local_data = {"extended_msg": getattr(thread_local_data, "extended_msg", None)}
                self._run_handler(handler, parsed_packet, client_obj, local_data)
            else:
                self.log.error("No client object available for packet processing")
                self.handle_unknown_command(self, parsed_packet, client_obj)
        except Exception as e:
            traceback.print_exc()
            self.log.error(f"cmserver exception: {e}")
            tb = sys.exc_info()[2]
            self.log.error(''.join(traceback.format_tb(tb)))
            raise e.with_traceback(tb)

    def _run_handler(self, handler, parsed_packet, client_obj, local_data):
        try:
            thread_local_data.extended_msg = local_data.get("extended_msg")
            reply_packets = handler(self, parsed_packet, client_obj)

            # Log response packets
            if isinstance(reply_packets, list):
                for i, packet in enumerate(reply_packets):
                    response_type = f"Response_{i+1}"
                    emsg_id = None
                    if hasattr(packet, 'eMsgID'):
                        response_type = Types.get_enum_name(EMsg, packet.eMsgID)
                        emsg_id = packet.eMsgID
                    packet_data = getattr(packet, 'data', b'')
                    data_len = len(packet_data) if packet_data else 0
                    data_preview = packet_data[:32].hex().upper() if data_len > 0 else ""
                    if emsg_id:
                        self.log.info(f"SENDING: {response_type} ({emsg_id}) ({data_len} bytes) Data: {data_preview}")
                    else:
                        self.log.info(f"SENDING: {response_type} ({data_len} bytes) Data: {data_preview}")
            elif reply_packets != -1 and reply_packets is not None:
                response_type = "Response"
                emsg_id = None
                if hasattr(reply_packets, 'eMsgID'):
                    response_type = Types.get_enum_name(EMsg, reply_packets.eMsgID)
                    emsg_id = reply_packets.eMsgID
                packet_data = getattr(reply_packets, 'data', b'')
                data_len = len(packet_data) if packet_data else 0
                data_preview = packet_data[:32].hex().upper() if data_len > 0 else ""
                if emsg_id:
                    self.log.info(f"SENDING: {response_type} ({emsg_id}) ({data_len} bytes) Data: {data_preview}")
                else:
                    self.log.info(f"SENDING: {response_type} ({data_len} bytes) Data: {data_preview}")

            if isinstance(reply_packets, list):
                self.sendreply_thread(client_obj, reply_packets)
            elif reply_packets != -1:
                self.sendreply_thread(client_obj, [reply_packets])

            # Complete the job context after successful handler execution
            # This marks the context as completed and cleans up tracking
            if hasattr(client_obj, 'job_registry') and client_obj.job_registry:
                client_obj.job_registry.complete_context()

        except Exception as e:
            self.log.error(f"Handler exception: {e}")
            traceback.print_exc()
            self.log.error(f"Handler thread exception: {e}")
            tb = sys.exc_info()[2]
            self.log.error(''.join(traceback.format_tb(tb)))

            # Fail the job context on exception
            if hasattr(client_obj, 'job_registry') and client_obj.job_registry:
                client_obj.job_registry.fail_context(reason=str(e))

    def sendreply_thread(self, client_obj, reply_packets):
        """Send reply packets directly instead of spawning a thread.

        The name is kept for backward compatibility, but this no longer spawns a thread.
        This eliminates the third layer of thread spawning that caused instability
        with multiple clients. The worker pool already provides concurrency.
        """
        try:
            self.sendReply(client_obj, reply_packets)
        except Exception as e:
            traceback.print_exc()
            self.log.error(f"sendreply exception: {e}")
            tb = sys.exc_info()[2]
            self.log.error(''.join(traceback.format_tb(tb)))

    # === SERVER JOB HELPER METHODS ===

    def create_server_job(self, packet: CMPacket, client_obj: Client, name: str = "ServerJob"):
        """
        Create a ServerJob for long-running async operations.

        This is the recommended way to handle operations that:
          - Take significant time (database queries, file I/O, etc.)
          - Need to send multiple responses to the same request
          - Should be tracked and cancelled on client disconnect

        The ServerJob automatically handles job ID routing - all responses
        sent through it will have the correct targetJobID.

        Usage in handlers:
            def handle_LongOperation(cmserver_obj, packet, client_obj):
                job = cmserver_obj.create_server_job(packet, client_obj, "DataFetch")

                def do_work():
                    # ... perform async work ...
                    for chunk in data_chunks:
                        response = job.create_response(EMsg.DataChunk)
                        response.data = chunk
                        if not job.send_response(response):
                            return  # Client disconnected
                    job.complete()

                job.run_threaded(do_work)
                return -1  # No immediate response (job handles it)

        Args:
            packet: The incoming CMPacket
            client_obj: The client that sent the request
            name: Name for this job (for logging/debugging)

        Returns:
            A ServerJob ready for processing
        """
        from steam3.Managers.JobManager.server_job import ServerJob
        return ServerJob.from_request(packet, client_obj, name=name, cmserver=self)

    def get_job_context(self, client_obj: Client):
        """
        Get the active job context for a client.

        This allows handlers to access the current job context if they need
        explicit control over job routing.

        Args:
            client_obj: The client object

        Returns:
            The active JobContext, or None if no context is active
        """
        if hasattr(client_obj, 'job_registry') and client_obj.job_registry:
            return client_obj.job_registry.active_context
        return None

    def get_job_stats(self, client_obj: Client = None) -> dict:
        """
        Get job statistics.

        Args:
            client_obj: Optional specific client (if None, returns global stats)

        Returns:
            Dictionary of job statistics
        """
        stats = {}

        # Global job manager stats (if available)
        if self.job_manager:
            global_stats = self.job_manager.get_stats()
            if global_stats:
                stats['global'] = {
                    'current': global_stats.jobs_current,
                    'total': global_stats.jobs_total,
                    'completed': global_stats.jobs_completed,
                    'failed': global_stats.jobs_failed,
                    'timed_out': global_stats.jobs_timed_out,
                }

        # Client-specific stats
        if client_obj and hasattr(client_obj, 'job_registry') and client_obj.job_registry:
            stats['client'] = client_obj.job_registry.get_stats()

        return stats