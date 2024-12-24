from __future__ import annotations
import copy
import logging
import struct
import sys
import time
import traceback
from collections import defaultdict, deque
from config import read_config
from steam3.ClientManager import Client_Manager
from steam3.ClientManager.client import Client
from steam3.Handlers.connection import create_channel_encryption_request, create_conn_acceptresponse, handle_challengerequest
from steam3.Handlers.system import handle_Heartbeat
from steam3.Types.wrappers import ConnectionID
from steam3.cm_crypto import symmetric_decrypt, symmetric_encrypt
from steam3.cm_packet_utils import CMPacket, CMProtoResponse, ExtendedMsgHdr, MsgHdr_deprecated, MsgMulti, deprecated_responsehdr
from steam3.cmserver_base import CMServer_Base
from utilities import encryption
from utilities.encryption import calculate_crc32_bytes
from utilities.networkhandler import TCPNetworkHandler, TCPNetworkHandlerCM
from utilities.socket import ImpSocket

config = read_config()

class CMServerTCP(CMServer_Base):
    # Add a class-level dictionary to track IP attempts
    # If you want per-instance instead, do this in __init__ instead.
    connection_attempts = defaultdict(deque)
    def handle_client(self, socket, address):
        ip = address[0]  # Extract the IP from the client address

        # Record this attempt
        now = time.time()
        attempts = self.connection_attempts[ip]
        attempts.append(now)

        # Remove attempts older than 2 seconds
        two_seconds_ago = now - 2
        while attempts and attempts[0] < two_seconds_ago:
            attempts.popleft()

        # Check if attempts exceed the threshold
        if len(attempts) > 5:
            self.log.warning(f"{ip}: Too many connection attempts. Blocking IP.")
            socket.block_ip()
            socket.close()
            return

        try:
            clientid = str(address) + ": "
            self.log.info(f"{clientid}Connected to TCP CM Server")

            #send encryption request
            #recieve key
            #send OK
            #recieve normal messages

            packet = CMPacket(is_tcp=True)

            conn_type = "encrypted" if self.is_encrypted else "unencrypted"

            if self.is_encrypted:
                self.log.info(f"{clientid}[{conn_type}] Sending Encryption Handshake Request To Client")
                cmidreply = create_channel_encryption_request(packet, packet, self.connectionid_count)
                socket.send(cmidreply, to_log = False)
            client = Client(ip_port = address, connectionid = self.connectionid_count)
            client_obj = Client_Manager.add_or_update_client(client)
            client_obj.socket = socket
            self.connectionid_count += 1

            data = socket.recv(16288)

            cm_packet = packet.parse(data, True)
            cm_packet_reply = copy.deepcopy(cm_packet)
            if isinstance(cm_packet.data, int):
                socket.close()
                return

            if b"\x18\x05" == cm_packet.data[:2]:
                # we decrypt the aes session key here
                encrypted_message = cm_packet.data[28:156]
                encrypted_message_crc32 = cm_packet.data[156:160]
                self.log.debug(f"encrypted response: {cm_packet}")
                key = encryption.get_aes_key(encrypted_message, encryption.network_key)
                self.log.debug(f"Encrypted Session Key: {key}")
                verification_local = calculate_crc32_bytes(encrypted_message)
                verification_result = "Pass" if verification_local == encrypted_message_crc32 else "Fail"
                self.log.debug(f"CRC32 Verification Result: packet crc: {encrypted_message_crc32}\nlocally verified crc: {verification_local}\nResult: {verification_result}")

                client_obj.set_symmetric_key(key)
                client_obj.hmac_key = key[:16]

                # send ChannelEncryptResult result = OK
                cm_packet_reply.data = b'\x19\x05\x00\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\x01\x00\x00\x00'
                cm_packet_reply.size = len(cm_packet_reply.data)
                handshake_confirmation = MsgHdr_deprecated(eMsgID = 0x1905,
                                                           accountID = 0xffffffff,
                                                           clientId2 = 0xffffffff,
                                                           sessionID = 0xffffffff,
                                                           data = b'\x01\x00\x00\x00'  # eResult, 01 is OK
                                                           )

                # cm_packet_reply.data = handshake_confirmation.serialize()

                cmidreply = cm_packet_reply.serialize()
                socket.send(cmidreply, to_log = False)
            while True:
                try:
                    data = socket.recv(16288)
                    cm_packet = packet.parse(data,  True)

                    self.handle_CMPacket(cm_packet, client_obj)
                except:
                    socket.close()
                    return

        except Exception as e:
            traceback.print_exc()
            self.log.error(f"(CM Handle_Client) thread exception: {e}")
            tb = sys.exc_info()[2]
            self.log.error(''.join(traceback.format_tb(tb)))

    def sendReply(self, client_obj, response_packet_list: [list, ExtendedMsgHdr | CMProtoResponse | deprecated_responsehdr | MsgMulti], packetID = None, priority_level = 1):
        """ Send a reply to a client. Takes a list of packets to send, and handles splitting the packets if necessary. """
        try:
            if not response_packet_list:
                return

            # Prepare the CMPacket for reply
            reply_packet = CMPacket(is_tcp=True)
            reply_packet.magic = 0x31305456 #VT01

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

                    # Data fits in a single packet
                    reply_packet.size = data_len
                    packets_to_send = [reply_packet]
                else:
                    self.log.error(f"(response missing .data) No data in response packet for client {client_obj.ip_port[0]} {reply_packet.data}")
                    return  # No data to send
            else:
                self.log.error(f"(no response in list) No data in response packet for client {client_obj.ip_port[0]} {reply_packet.data}")
                return

            # Serialize and send each packet
            for packet in packets_to_send:
                serialized_packet = packet.serialize()
                client_obj.socket.send(serialized_packet, to_log = True)
                #self.serversocket.send(serialized_packet, to_log = False)
        except Exception as e:
            tb = sys.exc_info()[2]  # Get the original traceback
            self.log.error(f"CM Server Sendreply error: {e}")
            self.log.error(''.join(traceback.format_tb(tb)))  # Logs traceback up to this point
            raise e.with_traceback(tb)  # Re-raise with the original traceback
class CMServerTCP_27017(TCPNetworkHandlerCM, CMServerTCP):
    """		// the tcp packet header is considerably less complex than the udp one
		// it only consists of the packet length, followed by the "VT01" magic"""
    def __init__(self, port, config, master_server):
        CMServerTCP.__init__(self, port, config)
        TCPNetworkHandlerCM.__init__(self, config, port)
        self.is_encrypted = True
        self.is_tcp = True
        self.server_type = "CMServerTCP_27017"
        self.log = logging.getLogger("CMTCP27017")
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
        self.log = logging.getLogger("CMTCP27014")
        self.master_server = master_server  # Store the reference to MasterServer

    def handle_client(self, socket, address):
        super().handle_client(socket, address)  # Call the base class implementation