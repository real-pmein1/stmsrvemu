import binascii
import logging
import os
import socket as pysocket
import struct
import threading
import time

import ipcalc

import globalvars
import utils
from listmanagers.contentlistmanager import manager
from servers.managers.latency_manager import latencyaggregater
from utilities import encryption
from utilities.encryption import peer_decrypt_message, peer_encrypt_message
from utilities.networkhandler import TCPNetworkHandler

csdsConnectionCount = 0


def expired_servers_thread():
    while True:
        time.sleep(3600)  # 1 hour
        manager.remove_old_entries()


class contentlistserver(TCPNetworkHandler):

    def __init__(self, port, config):
        self.server_type = "CSDServer"

        super(contentlistserver, self).__init__(config, int(port), self.server_type)  # Create an instance of NetworkHandler

        thread = threading.Thread(target = expired_servers_thread)  # Thread for removing servers older than 1 hour
        thread.daemon = True
        thread.start()

        # TODO Ben note: Figure out how to get the appid's and versions from the sdk contentserver.
        #  ideas include: if a packet exists for getting the app list, have csds send the packet and parse the response  # or put sdk contentserver in a folder within stmserver that we can parse through the files ourselves

        # if globalvars.use_sdk == "true" :  #      sdk_server_info = {  #     'ip_address': str(self.config["sdk_ip"]),  #     'port': int(self.config["sdk_port"]),  #     'region': globalvars.cs_region,  #     'timestamp': 1623276000  # }

    def handle_client(self, server_socket, client_address):
        global csdsConnectionCount

        reply = b""
        # TODO BEN NOTE: Add peering to this server!

        clientid = str(client_address) + ": "
        self.log.info(f"{clientid}Connected to Content Server Directory Server")

        # Determine if connection is local or external
        if str(client_address[0]) in ipcalc.Network(str(globalvars.server_net)):
            islan = True
        else:
            islan = False

        msg = server_socket.recv(1024)
        if msg[:4] == b"\x00\x4f\x8c\x11":
            self.acceptcontentservers(client_address, server_socket, islan, msg)
            return
        elif msg == b"\x00\x00\x00\x02":
            csdsConnectionCount += 1
        else:
            self.log.info(f"")

        server_socket.send(b"\x01")

        msg = server_socket.recv_withlen()

        if msg.startswith(b"\x03"):
            reply = self.packet_get_clupdate_list(clientid, islan)
        elif msg.startswith(b"\x00"):
            reply = self.get_general_server_list(clientid, islan, msg[1:], client_address)
        else:
            # Log the invalid message in hex format for debugging
            self.log.warning(f"{clientid}Invalid message! {binascii.b2a_hex(msg).decode()}")
            reply = b'\x00'

        server_socket.send_withlen(reply)
        server_socket.close()
        self.log.info(f"{clientid}Disconnected from Content Server Directory Server")


    def get_general_server_list(self, clientid, islan, msg, client_address):
        # Unpack the parameters from the message stream (msg)
        (for_specific_content, appid, appversion, nb_max_addresses, cell_id, unknown1) = struct.unpack(">HIIHII", msg[:20])

        self.log.debug(f"{clientid} Processing get content server group list request, Unknown1: {unknown1}")

        # Initialize response as an empty byte string
        response = b''

        unknown2 = 0
        if for_specific_content == 1:
            # Read unknown2 from the message if for_specific_content is 1
            unknown2 = struct.unpack(">I", msg[20:24])[0]
            #print(f"unknown 2: {unknown2}")
        elif for_specific_content not in [0, 1]:
            self.log.error(f"{clientid} Unknown 'forSpecificContent' value: {for_specific_content}")
            return b'\x00'

        # Get the server list based on the content flag
        if for_specific_content:
            servers, server_count = manager.get_content_server_groups_list(cell_id, appid, appversion, islan)
        else:
            servers, server_count = manager.get_content_server_groups_list(cell_id, islan = islan)

        # Prepare the response stream
        if server_count > 0:
            if for_specific_content:
                self.log.info(f"{clientid} Sending content server group list for App ID {appid} Version {appversion} ({server_count} entries)")
            else:
                self.log.info(f"{clientid} Sending content server group list ({server_count} entries)")
        else:
            if for_specific_content:
                self.log.warning(f"{clientid} No content server available for App ID {appid} Version {appversion}")
            else:
                self.log.warning(f"{clientid} No content server available")

        # If more than one content server is returned, use latency aggregator to select the best one
        if server_count > 1:
            # Extract client IP (without port)
            client_ip = client_address[0]

            # Extract content server IPs (without ports)
            content_server_ips = []
            for (cellid1, client_update_server, content_server) in servers:
                if content_server:
                    content_server_ips.append(content_server[0])

            # Initialize latency aggregator with content server IPs
            latency_aggregator_instance = latencyaggregater(content_server_ips)

            # Send client IP to latency aggregator to get the best server IP
            best_server_ip = latency_aggregator_instance.send_client_ip(client_ip)

            if best_server_ip:
                # Find the server in servers that has content_server[0] == best_server_ip
                best_server = next(
                        ((cellid1, client_update_server, content_server) for (cellid1, client_update_server, content_server) in servers
                         if content_server and content_server[0] == best_server_ip),
                        None
                )
                if best_server:
                    # Replace servers with only the best server
                    servers = [best_server]
                    server_count = 1
                    self.log.info(f"{clientid} Selected best content server {best_server_ip} based on latency")
                else:
                    self.log.warning(f"{clientid} Best server IP {best_server_ip} not found in server list")
                    # Proceed with original servers
            else:
                self.log.warning(f"{clientid} Latency aggregator did not return a best server, proceeding with original servers")
        else:
            # Only one server, proceed as is
            pass

        # Loop through servers and write data to the response stream
        cellid1 = 0  # Force to 0 in case of no available CS
        count = 0
        if server_count > 0:
            for i, (cellid1, client_update_server, content_server) in enumerate(servers):
                count += 1
                if i >= nb_max_addresses:
                    break
                # Ensure we have valid client and content server addresses
                if not client_update_server:
                    if islan:
                        client_update_server = (globalvars.server_ip, self.config['clupd_server_port'])
                    else:
                        client_update_server = (globalvars.public_ip, self.config['clupd_server_port'])
                if not content_server:
                    if islan:
                        content_server = (globalvars.server_ip, self.config['content_server_port'])
                    else:
                        content_server = (globalvars.public_ip, self.config['content_server_port'])

                self.log.info(f"{clientid} Sending content server cell ID {cellid1}: {client_update_server[0]}:{client_update_server[1]} / {content_server[0]}:{content_server[1]}")

                # Encode and append the server group info to the response
                bin_client_update_ip = utils.encodeIP(client_update_server)
                bin_content_server_ip = utils.encodeIP(content_server)

                # Append group info (group ID, client update server, content server)
                response += bin_client_update_ip  # Client update server IP and port
                response += bin_content_server_ip  # Content server IP and port
                if appid == None and appversion == None:
                    break

        if count == 2 and len(response) > 12: # FIXME do this properly!
            response = response[:12] # trim reply to expected clupd server length
            count = 1
        packet = struct.pack(">HI", count, cellid1)  # Group ID
        packet += response
        self.log.info(f"{clientid} Finished processing get content server group list request")

        return packet


    def packet_get_clupdate_list(self, clientid, islan):
        self.log.info(f"{clientid}Sending out Content Servers with packages (0x03)")
        all_results, all_count = manager.get_empty_or_no_applist_entries(islan)

        if all_count > 0:
            reply = struct.pack(">H", all_count)
            for ip, port in all_results:
                self.log.debug(f"{clientid}sending pkg update servers: {ip} {port}")
                ip_port_tuple = (ip, port)
                reply += utils.encodeIP(ip_port_tuple)
                break
        else:
            reply = struct.pack(">H", 1)  # Default reply value if no matching server is found
            if islan:
                reply += utils.encodeIP((globalvars.server_ip, self.config['clupd_server_port']))
            else:
                reply += utils.encodeIP((globalvars.public_ip, self.config['clupd_server_port']))
        return reply


    # Send error message to client
    def send_error(self, server_socket, client_address, error_message):
        error_packet = f"error:{error_message}".encode("latin-1")
        server_socket.sendto(error_packet, client_address)
        self.log.error(f"Sent error to {client_address}: {error_message}")

    # Send OK byte to the client
    def send_ok(self, server_socket, client_address):
        server_socket.sendto(b'\x00', client_address)

    # Handle storing client info
    def handle_client_info(self, server_socket, client_address, decrypted_data, key):
        chunk_count = int().from_bytes(decrypted_data[0:2], 'little')
        print(f"Recieved chunk count: {chunk_count}")
        constructed_packet = b''
        i = 0
        while i < chunk_count:
            print(f"Recieved chunk {i + 1} of {chunk_count}")
            packet = server_socket.recv(600)
            constructed_packet += packet
            i += 1

        key = manager.client_info[client_address]['key']
        decrypted_appdata = peer_decrypt_message(key, constructed_packet)
        print(constructed_packet)
        game_info = manager.unpack_contentserver_info(decrypted_appdata)

        if isinstance(game_info, tuple):
            server_id, wan_ip, lan_ip, port, region, cellid, applist = game_info
            is_clientupdate_server = False

            if len(applist) == 0:
                is_clientupdate_server = True
            print(repr(game_info))
            manager.add_contentserver_info(server_id, wan_ip, lan_ip, port, region, applist, cellid, False, is_clientupdate_server)
            #manager.client_info[client_address] = {'key':key}
            manager.client_last_heartbeat[client_address] = time.time()
            self.log.debug(f"Received and stored client info: {game_info}")
            self.send_ok(server_socket, client_address)
        else:
            self.send_error(server_socket, client_address, "Failed to parse game info")

    # Check if client should be forced to handshake again
    def check_client_heartbeat(self, client_address):
        if client_address in manager.client_last_heartbeat:
            elapsed_time = time.time() - manager.client_last_heartbeat[client_address]
            if elapsed_time > 300:  # Timeout 5 minutes
                return True  # Force handshake
        return False

    def handle_client_handshake(self, server_socket, client_address):
        # Generate new salt and key for the handshake
        salt = os.urandom(16)
        key = encryption.derive_key(self.config['peer_password'], salt)

        # Read the RSA key binaries
        with open('files/configs/main_key_1024.der', 'rb') as f:
            key_1024_data = f.read()
        with open('files/configs/network_key_512.der', 'rb') as f:
            key_512_data = f.read()

        # Prepare the handshake payload with length prefixes
        message = b"handshake successful"
        message_length = len(message).to_bytes(4, 'big')
        key1_length = len(key_1024_data).to_bytes(4, 'big')
        key2_length = len(key_512_data).to_bytes(4, 'big')

        handshake_payload = message_length + message + key1_length + key_1024_data + key2_length + key_512_data

        # Encrypt the handshake payload
        handshake_message = peer_encrypt_message(key, handshake_payload)

        # TODO send the current WAN cddb? that way the peer/slave cs can validate its custom blob and add them before sending the custom blobs to the csds.

        # Send the handshake response to the client
        server_socket.sendto(salt + handshake_message, client_address)
        self.log.debug(f"Handshake successful with {client_address}. Sent: {salt + handshake_message}")

        # Store the key in client_info to be used later for decryption
        manager.client_info[client_address] = {'key':key}
        return key

    def acceptcontentservers(self, client_address, server_socket, islan, data):  # Used for registering content servers with csds

        if len(data) < 5:
            self.send_error(server_socket, client_address, "Packet too small")
            return

        # Parse command byte (5th byte)
        command_byte = data[4:5]
        packet = data[5:]  # Remove the first 5 bytes
        #print(f"\ncommand byte: {command_byte}\n")
        if command_byte == b"\x04":
            if client_address in manager.client_info:
                del manager.client_info[client_address]
                del manager.client_last_heartbeat[client_address]
            self.log.info(f"Client {client_address} removed from the server.")
            result = manager.receive_removal(packet)
            if result:
                self.send_ok(server_socket, client_address)
            else:
                self.send_error(server_socket, client_address, "Unknown Error")
            server_socket.close()
            return

        # If the client is not already connected or needs to handshake again
        if command_byte == b'\x01' or client_address not in manager.client_info or self.check_client_heartbeat(client_address):
            if command_byte == b'\x01':  # Handshake command
                self.log.debug(f"Client {client_address} needs to handshake.")
                self.handle_client_handshake(server_socket, client_address)
            else:
                self.send_error(server_socket, client_address, "Client needs to handshake first.")
                return
        while True:  # Loop to keep listening for heartbeats
            try:
                msg = server_socket.recv(512)
                command_byte = msg[4:5]
                packet = msg[5:]
                key = manager.client_info[client_address]['key']
                decrypted_data = peer_decrypt_message(key, packet)
                self.log.debug(f"Decrypted packet from {client_address}: {decrypted_data}")

                if command_byte == b'\x02':  # Client sends info
                    self.log.debug(f"Processing client info from {client_address}...")
                    self.handle_client_info(server_socket, client_address, decrypted_data, key)
                    # manager.print_contentserver_list()
                elif command_byte == b'\x03':  # Heartbeat
                    manager.client_last_heartbeat[client_address] = time.time()
                    self.log.debug(f"Received heartbeat from {client_address}")
                    self.send_ok(server_socket, client_address)
                else:
                    break  # Break if the connection is closed or no further messages are received
            except:
                return