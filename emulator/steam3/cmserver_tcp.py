from __future__ import annotations
import copy
import logging
import struct
import sys
import threading
import time
import traceback
from typing import Optional

from config import get_config as read_config
from steam3 import Types
from steam3.ClientManager import Client_Manager
from steam3.ClientManager.client import Client
from steam3.Handlers.connection import (
    create_channel_encryption_request,
    create_channel_encryption_result,
    create_conn_acceptresponse,
    handle_challengerequest,
    parse_channel_encryption_response,
)
from steam3.Types.emsg import EMsg
from utilities import encryption
from utilities.encryption import calculate_crc32_bytes
from steam3.cm_crypto import symmetric_decrypt, symmetric_encrypt
from steam3.cm_packet_utils import CMPacket, CMProtoResponse, ExtendedMsgHdr, MultiMsg, deprecated_responsehdr
from steam3.cmserver_base import CMServer_Base
from utilities.networkhandler import TCPNetworkHandlerCM
from utilities.impsocket import ImpSocket, MessageInfo

config = read_config()

class CMServerTCP(CMServer_Base):
    def handle_client(self, client_socket, address):
        try:
            imp_socket = ImpSocket(sock=client_socket)
            imp_socket.address = address
        except Exception as e:
            self.log.error(f"Error initializing ImpSocket for {address[0]}: {e}")
            try:
                client_socket.close()
            except Exception as e_close:
                self.log.error(f"Error closing socket for {address[0]}: {e_close}")
            return

        try:
            clientid = f"{address}: "
            self.log.info(f"{clientid}Connected to TCP CM Server")
            packet = CMPacket(is_tcp=True)
            conn_type = "encrypted" if getattr(self, 'is_encrypted', False) else "unencrypted"
            if getattr(self, 'is_encrypted', False):
                self.log.info(f"{clientid}[{conn_type}] Sending Encryption Handshake Request To Client")
                cmidreply = create_channel_encryption_request(packet, packet, self.connectionid_count)
                msg_info = MessageInfo(emsg_id=EMsg.ChannelEncryptRequest, emsg_name="ChannelEncryptRequest")
                client_socket.send(cmidreply, to_log=True, msg_info=msg_info)
            client = Client(ip_port=address, connectionid=self.connectionid_count)
            client.objCMServer = self  # Store reference to this CM server for push messages
            client_obj = Client_Manager.add_or_update_client(client)
            client_obj.socket = client_socket
            self.connectionid_count += 1

            data = client_socket.recv(16288)
            if not data:
                client_socket.close()
                return
            cm_packet = packet.parse(data, True)
            cm_packet_reply = copy.deepcopy(cm_packet)
            if isinstance(cm_packet.data, int):
                client_socket.close()
                return

            if cm_packet.data.startswith(b"\x18\x05"):
                encrypted_message = cm_packet.data[28:156]
                encrypted_message_crc32 = cm_packet.data[156:160]
                self.log.debug(f"encrypted response: {cm_packet}")
                key = encryption.get_aes_key(encrypted_message, encryption.network_key)
                self.log.debug(f"Encrypted Session Key: {key}")
                verification_local = calculate_crc32_bytes(encrypted_message)
                verification_result = "Pass" if verification_local == encrypted_message_crc32 else "Fail"
                self.log.debug(f"CRC32 Verification Result: {verification_result}")
                client_obj.set_symmetric_key(key)
                client_obj.hmac_key = key[:16]
                cm_packet_reply.data = create_channel_encryption_result()  # EResult.OK = 1
                cm_packet_reply.size = len(cm_packet_reply.data)
                cmidreply = cm_packet_reply.serialize()
                msg_info = MessageInfo(emsg_id=EMsg.ChannelEncryptResult, emsg_name="ChannelEncryptResult")
                client_socket.send(cmidreply, to_log=True, msg_info=msg_info)
            while True:
                data = client_socket.recv(16288)
                if not data:
                    self.log.info(f"Connection closed by {address}")
                    break
                cm_packet = packet.parse(data, True)
                self.handle_CMPacket(cm_packet, client_obj)
        except Exception as e:
            traceback.print_exc()
            self.log.error(f"(CM Handle_Client) thread exception: {e}")
            tb = sys.exc_info()[2]
            self.log.error(''.join(traceback.format_tb(tb)))
        finally:
            try:
                client_socket.close()
            except Exception:
                pass

    def sendReply(self, client_obj, response_packet_list: list, *args):
        """ Send a reply to a client. Takes a list of packets to send, and handles splitting the packets if necessary. """
        if not response_packet_list:
            return

        # Validate client is still in the manager (not replaced by a newer connection)
        # This prevents sending to stale client objects that have been disconnected/reconnected
        current_client = Client_Manager.get_client_by_identifier(client_obj.ip_port)
        if current_client is not client_obj:
            self.log.debug(f"Client object for {client_obj.ip_port} is stale (replaced), skipping send")
            return

        # Acquire send lock to ensure packets are sent in order
        # This is less critical for TCP than UDP (TCP has its own ordering)
        # but still prevents issues with stale references during concurrent access
        with client_obj.send_lock:
            try:
                packets_to_send = []
                msg_info_list = []
                for idx, response_packet in enumerate(response_packet_list):
                    # Skip any empty or malformed entries
                    if not response_packet or not getattr(response_packet, 'data', None):
                        self.log.error(
                            f"(response {idx} missing .data) No data in response packet "
                            f"for client {client_obj.ip_port[0]}"
                        )
                        continue

                    # Extract message info BEFORE encryption for logging
                    emsg_id = getattr(response_packet, 'eMsgID', None)
                    emsg_name = Types.get_enum_name(EMsg, emsg_id) if emsg_id is not None else None
                    target_job_id = getattr(response_packet, 'targetJobID', None)
                    source_job_id = getattr(response_packet, 'sourceJobID', None)
                    is_encrypted = getattr(self, 'is_encrypted', False) and client_obj.symmetric_key is not None

                    # build a fresh CMPacket for each response
                    reply_packet = CMPacket(is_tcp=True)
                    reply_packet.magic = 0x31305456  # VT01

                    # serialize the high-level response into the CMPacket
                    reply_packet.data = response_packet.serialize()

                    # Log unencrypted packet through impsocket for centralized logging
                    msg_info = MessageInfo(
                        emsg_id=emsg_id,
                        emsg_name=emsg_name,
                        is_encrypted=is_encrypted,
                        target_job_id=target_job_id,
                        source_job_id=source_job_id
                    )
                    client_obj.socket.log_packet(
                        address=client_obj.ip_port,
                        direction="Sent",
                        data=reply_packet.data,
                        msg_info=msg_info
                    )

                    # encrypt and log if desired
                    reply_packet.data = self.encrypt_packet(reply_packet, client_obj)

                    # set size and collect
                    reply_packet.size = len(reply_packet.data)
                    packets_to_send.append(reply_packet)

                    # Reuse the msg_info we already created for log_packet
                    msg_info_list.append(msg_info)

                # now send each packet in the same order
                for i, reply_packet in enumerate(packets_to_send):
                    serialized = reply_packet.serialize()
                    msg_info = msg_info_list[i] if i < len(msg_info_list) else None
                    self._sendreply(client_obj, serialized, msg_info)

            except Exception as e:
                tb = sys.exc_info()[2]
                self.log.error(f"CM Server sendReply error: {e}")
                self.log.error(''.join(traceback.format_tb(tb)))
                raise e.with_traceback(tb)

    def _sendreply(self, client_obj, serialized_packet, msg_info: Optional[MessageInfo] = None):
        """ Send a reply to a client. Takes a list of packets to send, and handles splitting the packets if necessary. """
        client_obj.socket.send(serialized_packet, to_log=True, msg_info=msg_info)

class CMServerTCP_27017(TCPNetworkHandlerCM, CMServerTCP):
    """		// the tcp packet header is considerably less complex than the udp one
		// it only consists of the packet length, followed by the "VT01" magic"""
    def __init__(self, port, config, master_server):
        CMServerTCP.__init__(self, port, config)
        TCPNetworkHandlerCM.__init__(self, config, port)
        self.is_encrypted = True
        self.is_tcp = True
        self.server_type = "CMServerTCP_27017"
        self.log = logging.getLogger("CM27017TCP")
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

class CMServerTCP_27014(TCPNetworkHandlerCM, CMServerTCP):
    def __init__(self, port, config, master_server):
        CMServerTCP.__init__(self, port, config)
        TCPNetworkHandlerCM.__init__(self, config, port)
        self.server_type = "CMServerTCP_27014"
        self.is_encrypted = False
        self.is_tcp = True
        self.log = logging.getLogger("CM27014TCP")
        self.master_server = master_server  # Store the reference to MasterServer

    def handle_client(self, socket, address):
        super().handle_client(socket, address)  # Call the base class implementation