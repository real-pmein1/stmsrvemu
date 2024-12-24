from __future__ import annotations
import copy
import logging
import sys
import traceback
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
from utilities.networkhandler import UDPNetworkHandlerCM


class CMServerUDP(CMServer_Base):
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
                self.serversocket.sendto(cmidreply, address)
                return

            elif cm_packet.packetid == challenge_request_id:  # challange Request
                self.log.info(f"{clientid}[{conn_type}] Recieved Challenge Request")
                self.log.debug(f"Challenge Request: {cm_packet}")
                cmidreply = handle_challengerequest(cm_packet, cm_packet_reply, address, self.connectionid_count)
                self.serversocket.sendto(cmidreply, address)
                if self.is_encrypted:
                    self.log.info(f"{clientid}[{conn_type}] Sending Encryption Handshake Request To Client")
                    cmidreply = create_channel_encryption_request(cm_packet, cm_packet_reply, self.connectionid_count)
                    self.serversocket.sendto(cmidreply, address)
                client = Client(ip_port = address, connectionid = self.connectionid_count)
                Client_Manager.add_or_update_client(client)
                self.connectionid_count += 1
                return

            elif cm_packet.packetid == disconnect_request_id:  # Disconnection
                self.log.info(f"{clientid}Recieved Disconnect packet")
                client_obj = Client_Manager.get_client_by_identifier(address)
                client_obj.socket = None
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

                    client_obj.set_symmetric_key(key)
                    client_obj.hmac_key = key[:16]

                    # send ChannelEncryptResult result = OK
                    cm_packet_reply.priority_level = b"\x02"
                    cm_packet_reply.packetid = b"\x06"
                    cm_packet_reply.size = 24
                    cm_packet_reply.source_id = cm_packet.destination_id
                    cm_packet_reply.destination_id = cm_packet.source_id
                    cm_packet_reply.sequence_num = 4  # seq
                    client_obj.sequence_number = 4
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
                    max_data_size = 0x04dc  # Maximum data size per packet

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
                    self.log.error(f"(response missing .data) No data in response packet for client {client_obj.ip_port[0]} {reply_packet.data}")
                    return  # No data to send
            else:
                self.log.error(f"(no response in list) No data in response packet for client {client_obj.ip_port[0]} {reply_packet.data}")
                return

            # Serialize and send each packet
            for packet in packets_to_send:
                serialized_packet = packet.serialize()
                self.serversocket.sendto(serialized_packet, client_obj.ip_port, to_log = True)
                #self.serversocket.send(serialized_packet, to_log = False)
        except Exception as e:
            tb = sys.exc_info()[2]  # Get the original traceback
            self.log.error(f"CM Server Sendreply error: {e}")
            self.log.error(''.join(traceback.format_tb(tb)))  # Logs traceback up to this point
            raise e.with_traceback(tb)  # Re-raise with the original traceback

class CMServerUDP_27017(UDPNetworkHandlerCM, CMServerUDP):
    def __init__(self, port, in_config, master_server):
        CMServerUDP.__init__(self, port, in_config)
        UDPNetworkHandlerCM.__init__(self, in_config, port)
        self.server_type = "CMServerUDP_27017"
        # Server-specific initialization
        self.log = logging.getLogger("CMUDP27017")
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
        #self.log.info(f"Handling client in CMServerUDP_27017")
        super().handle_client(socket, address)  # Call the base class implementation


class CMServerUDP_27014(UDPNetworkHandlerCM, CMServerUDP):
    def __init__(self, port, in_config, master_server):
        CMServerUDP.__init__(self, port, in_config)
        UDPNetworkHandlerCM.__init__(self, in_config, port)
        self.server_type = "CMServerUDP_27014"
        self.log = logging.getLogger("CMUDP27014")
        self.is_encrypted = False
        self.is_tcp = False
        self.master_server = master_server  # Store the reference to MasterServer

    def handle_client(self, socket, address):
        #self.log.info(f"Handling client in CMServerUDP_27014")
        super().handle_client(socket, address)  # Call the base class implementation