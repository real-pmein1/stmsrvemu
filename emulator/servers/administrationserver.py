import binascii
import logging
import os
import socket as real_socket
import struct
import time
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import scrypt

import globalvars
import utils
from utilities.database.admin_db import admin_dbdriver
from utilities.networkhandler import TCPNetworkHandler

# Permission bits
CREATE_USER = 1
MODIFY_USER = 2
ADD_SUBSCRIPTION = 4
VAC_BANNING = 8
MODIFY_ADMINS = 16
CREATE_ADMIN_USERS = 32

# Encryption helper functions
def derive_key(shared_secret, salt):
    key = scrypt(shared_secret, salt, 32, N=2**14, r=8, p=1)
    return key

# Encrypt/Decrypt helper functions
def encrypt_message(key, plaintext):
    cipher = AES.new(key, AES.MODE_CFB)
    ciphertext = cipher.iv + cipher.encrypt(plaintext)
    print(f"Encrypting message. IV: {cipher.iv.hex()} Ciphertext: {ciphertext[16:].hex()}")
    return ciphertext

def decrypt_message(key, ciphertext):
    iv = ciphertext[:16]
    if len(iv) != 16:
        raise ValueError(f"Incorrect IV length: {len(iv)} (expected 16 bytes)")
    cipher = AES.new(key, AES.MODE_CFB, iv=iv)
    print(f"Decrypting message. IV: {iv.hex()} Ciphertext: {ciphertext[16:].hex()}")
    return cipher.decrypt(ciphertext[16:])

class administrationserver(TCPNetworkHandler):
    def __init__(self, port, config):
        self.server_type = "AdminServer"
        self.database = admin_dbdriver(config)
        self.authenticated_ips = globalvars.authenticated_ips  # Dictionary to track authenticated IP addresses
        # Store client info and heartbeats
        self.client_info = {}
        self.client_last_heartbeat = {}
        super(administrationserver, self).__init__(config, port, self.server_type)

    # This method checks if the user is authenticated before executing any commands
    def is_user_authenticated(self, client_address):
        # Check if the user exists in the client_info dictionary and if they are authenticated
        if client_address in self.client_info and self.client_info[client_address].get('authenticated', False):
            return True
        else:
            return False

    def handle_client(self, client_socket, client_address):
        utils.load_admin_ips()
        shared_secret = self.config['peer_password']
        ip_address = client_address[0]  # Extract the IP address, ignoring the port
        self.log.info(f"Connection from {ip_address}")

        #try:
        if ip_address in self.authenticated_ips and self.authenticated_ips[ip_address]:
            while True:
                data = client_socket.recv(1024)
                if not data:
                    break  # Client disconnected
                print(f"Received data from {client_address}: {data}")

                # Update heartbeat time for client on every received packet
                self.client_last_heartbeat[client_address] = time.time()

                if len(data) < 5:
                    self.send_error(client_socket, client_address, "Packet too small")
                    continue

                # Parse command byte (5th byte)
                command_byte = data[4:5]
                packet = data[5:]  # Remove the first 5 bytes

                # If the client is not already connected or needs to handshake again
                if client_address not in self.client_info or self.check_client_heartbeat(client_address):
                    if command_byte == b'\x01':  # Handshake command
                        print(f"Client {client_address} needs to handshake.")
                        self.handle_client_handshake(client_socket, client_address, shared_secret)
                    else:
                        self.send_error(client_socket, client_address, "Client needs to handshake first.")
                    continue

                # Use the existing key for the client
                key = self.client_info[client_address]['key']
                decrypted_data = decrypt_message(key, packet)
                self.log.debug(f"Decrypted packet from {client_address}: {decrypted_data}")

                # Update heartbeat time for client on every received packet
                self. client_last_heartbeat[client_address] = time.time()
                if command_byte == b'\x01':  # Handshake command
                    self.handle_client_handshake(client_socket, client_address, shared_secret)

                elif command_byte == b'\x02':  # Client login
                    self.log.info(f"Processing client login from {client_address}...")
                    self.handle_client_login(client_socket, client_address, decrypted_data)

                elif command_byte == b'\x03':  # Log Off
                    if client_address in self.client_info:
                        del self.client_info[client_address]
                        del self.client_last_heartbeat[client_address]
                        self.log.info(f"Client {client_address} Logged off successfully from the server.")
                        self.send_ok(client_socket, client_address)
                        client_socket.close()
                    else:
                        self.send_error(client_socket, client_address, "Client info not found")
                else:
                    self.log.info(f"command byte: {command_byte}")
                    self.client_last_heartbeat[client_address] = time.time()
                    packet_data = self.execute_command(client_socket, client_address, decrypted_data, command_byte)

                    if packet_data != -1: # -1 means error, which already got sent using send_error()
                        if len(packet_data) < 7:
                            packet_data.rjust(7, b'\x00')
                        encrypted_packet_data = encrypt_message(key, packet_data)
                        client_socket.send(encrypted_packet_data)

    # Check if client should be forced to handshake again
    def check_client_heartbeat(self, client_address):
        if client_address in self.client_last_heartbeat:
            elapsed_time = time.time() - self.client_last_heartbeat[client_address]

            if elapsed_time > int(self.config['admin_inactive_timout']):
                return True  # Force handshake
        return False

    # Handle the handshake process
    def handle_client_handshake(self, server_socket, client_address, shared_secret):

        # Generate new salt and key for the handshake
        salt = os.urandom(16)
        key = derive_key(shared_secret, salt)

        # Send handshake response to the client
        handshake_message = encrypt_message(key, b"handshake successful")
        server_socket.send(salt + handshake_message)
        print(f"Handshake successful with {client_address}. Sent: {salt + handshake_message}")

        # Store the key in client_info to be used later for decryption
        self.client_info[client_address] = {'key':key}
        return key

    # Send error message to client
    def send_error(self, server_socket, client_address, error_message):
        error_packet = f"error:{error_message}".encode("latin-1")
        server_socket.send(error_packet)
        print(f"Sent error to {client_address}: {error_message}")

    # Send OK byte to the client
    def send_ok(self, server_socket, client_address):
        server_socket.send(b'\x00')

    def handle_client_login(self, server_socket, client_address, decrypted_data):
        # Parsing the packed_info by splitting on null byte
        parsed_info = decrypted_data.split(b'\x00')

        username = parsed_info[0]
        password = parsed_info[1]
        print(f"Received client login: {username} {password}")
        stored_client = [b"ben", b"12345"]

        #if self.database.validate_user(username, password):
        if stored_client[0] == username and stored_client[1] == password:
            self.client_last_heartbeat[client_address] = time.time()
            self.send_ok(server_socket, client_address)
            self.client_info[client_address] = {'authenticated':True}
        else:
            self.send_error(server_socket, client_address, "User Login Failed")

    def execute_command(self, client_socket, client_address, decrypted_data, command_code):
        log = logging.getLogger(self.server_type)
        if command_code == b'\x0A' or command_code == b'\x10':  # Command ID for setting current user
            return self.get_user_details_response(decrypted_data)
        elif command_code == b'\x0B':
            return self.parse_username_query(decrypted_data)
        elif command_code == b'\x0C':
            return self.parse_email_query(decrypted_data)
        elif command_code == b'\x0D':
            return self.list_users_response()
        elif command_code == b'\x0E':
            result = self.create_user(decrypted_data)
            if not isinstance(result, int):
                self.send_error(client_socket, client_address, result)
                return -1
            return result
        elif command_code == b'\x1E':
            result = self.beta1_create_user(decrypted_data)
            if not isinstance(result, int):
                self.send_error(client_socket, client_address, result)
                return -1
            return result
        elif command_code == b'\x11':
            parsed_data = self.parse_packet(decrypted_data)
            result = self.database.remove_user(int(parsed_data[0]))
            if isinstance(result, str):
                self.send_error(client_socket, client_address, result)
                return -1
            return result
        elif command_code == b'\x12': #change username
            pass
        elif command_code == b'\x13':
            result = self.database.change_user_email(decrypted_data)
        elif command_code == b'\x16':
            result = self.parse_add_vac_ban(decrypted_data)
            if isinstance(result, str):
                self.send_error(client_socket, client_address, result)
                return -1
            return result
        elif command_code == b'\x17':
            parsed_data = self.parse_packet(decrypted_data)
            result = self.parse_remove_vac_ban(parsed_data)
            if isinstance(result, str):
                self.send_error(client_socket, client_address, result)
                return -1
            return result
        elif command_code == b'\x1f':
            parsed_data = self.parse_packet(decrypted_data)
            return self.parse_list_vac_bans(int(parsed_data[0]))
        elif command_code == b'\x20':  # Command ID for listing user subscriptions
            return self.list_user_subscriptions(decrypted_data)
        # Add additional elif blocks for each command as needed

        # Interpret the result to provide meaningful feedback
        if result is True:
            return b"Success"
        elif result is False:
            return b"Operation failed"
        else:
            return b"Error: " + str(result).encode('latin-1')

        return b"Unknown command"

    def parse_packet(self, packet):
        # Decode the packet from bytes to string using 'latin-1'
        decoded_string = packet.decode('latin-1')

        # Split the string by '|' to get the individual parameters
        parsed_values = decoded_string.split('|')

        return parsed_values

    def parse_email_query(self, parameters):
        email_address = parameters[0]
        matching_users = self.database.get_users_by_email(email_address)
        user_count = len(matching_users)
        response_list = f"{user_count}|"
        response_list += "|".join(f"{user[0]},{user[1]}" for user in matching_users)
        return response_list.encode('latin-1')

    def parse_username_query(self, parameters):
        username = parameters[0]
        matching_users = self.database.get_user_by_username(username)
        user_count = len(matching_users)
        response_list = f"{user_count}|"
        response_list += "|".join(f"{user[0]},{user[1]}" for user in matching_users)
        return response_list.encode('latin-1')

    def get_userid_query(self, user_id):
        user_details = self.database.get_user_details(user_id)
        if isinstance(user_details, str):  # Handling errors
            return user_details
        return "|".join(user_details).encode('latin-1')

    def list_user_subscriptions(self, user_id):
        subscriptions = self.database.list_user_subscriptions(user_id)
        subscription_count = len(subscriptions)

        # Convert subscription count to 4-byte integer
        count_bytes = struct.pack('>I', subscription_count)
        subscription_data = "|".join([f"{sub[0]},{sub[1]}" for sub in subscriptions])

        return count_bytes + subscription_data.encode('latin-1')

    def permission_denied(self):
        return b'Permission Denied'

    def parse_change_email(self, parameters):
        user_type, user_info, new_email = parameters[0], parameters[1], parameters[2]
        result = self.database.change_user_email(user_type, user_info, new_email)
        return self.format_response(result)

    def parse_add_subscription(self, parameters):
        userid, sub_count = parameters[0], int(parameters[1])
        sub_ids = parameters[2]
        result = self.database.add_subscription(userid, sub_ids)
        return self.format_response(result)

    def parse_remove_subscription(self, parameters):
        userid, sub_count = parameters[0], int(parameters[1])
        sub_ids = parameters[2]
        result = self.database.remove_subscription_from_user(userid, sub_ids)
        return self.format_response(result).encode('latin-1')

    def parse_add_vac_ban(self, parameters):
        userid, start_appid, end_appid, ban_time_in_sec = parameters[0], parameters[1], parameters[2], parameters[3], parameters[4]
        result = self.database.add_vac_ban_to_account(start_appid, end_appid, int(ban_time_in_sec), userid)
        return result

    def parse_remove_vac_ban(self, parameters):
        userid, banid = parameters[0], parameters[1]
        result = self.database.remove_vac_ban_from_account(banid, userid)
        return result

    def parse_list_vac_bans(self, userid):
        result = self.database.list_user_vac_bans(userid)
        if result:
            vac_ban_list = self.format_vac_ban_list(result)
            return vac_ban_list.encode('latin-1')
        else:
            return b'\x00'

    def list_users_response(self):
        user_list = self.database.list_users()
        user_count = len(user_list)

        # Convert user count to 4-byte integer
        count_bytes = struct.pack('>I', user_count)
        user_data = "|".join([f"{user[0]},{user[1]},{user[2]}" for user in user_list])

        return count_bytes + user_data.encode('latin-1')

    def list_beta1_users_response(self):
        user_list = self.database.beta1_list_all_users()
        user_count = len(user_list)

        # Convert user count to 4-byte integer
        count_bytes = struct.pack('>I', user_count)
        user_data = "|".join([f"{user[0]},{user[1]}" for user in user_list])

        return count_bytes + user_data.encode('latin-1')

    def parse_beta1_username_query(self, parameters):
        username = parameters[0]
        matching_user = self.database.beta1_get_uniqueid_by_email(username)
        return str(matching_user)

    def get_beta1_userid_query(self, parameters):
        userid = parameters[0]
        user_email = self.database.beta1_get_email_by_uniqueid(userid)
        return user_email.encode('latin-1')

    def format_vac_ban_list(self, vac_bans):
        formatted_list = ""
        for vac_ban in vac_bans:
            ban_id, start_appid, end_appid, length = vac_ban
            formatted_list += f"{ban_id},{start_appid},{end_appid},{length}|"
        return formatted_list

    def format_response(self, result):
        if result is True:
            return b'\x00'
        else:
            return b'\x01' + str(result).encode('latin-1') + b'\x00'

    def create_user(self, decrypted_data):
        # Split the packet data based on commas
        parsed_data = decrypted_data.split(", ")

        if len(parsed_data) != 7:
            # If the number of expected items is incorrect, handle the error
            print("Error: Unexpected data format")
            return None

        # Assigning each part to a variable
        username = parsed_data[0]
        email = parsed_data[1]
        password_salt_hex = parsed_data[2]
        salted_password_digest = parsed_data[3]
        selected_question = parsed_data[4]
        answer_salt_hex = parsed_data[5]
        salted_answertoguestion_digest = parsed_data[6]

        result = self.database.create_user(username, password_salt_hex, salted_password_digest,  answer_salt_hex, salted_answertoguestion_digest, selected_question, email)

        if isinstance(result, int):
            result = struct.pack("I", result) + (b"\x00" * 7)  # Pad the message for encryption/decryption sanity

        return result
    def beta1_create_user(self, decrypted_data):
        # Split the packet data based on commas
        parsed_data = decrypted_data.split(", ")

        if len(parsed_data) != 7:
            # If the number of expected items is incorrect, handle the error
            print("Error: Unexpected data format")
            return None

        # Assigning each part to a variable
        username = parsed_data[0]
        password_salt_hex = parsed_data[1]
        salted_password_digest = parsed_data[2]


        result = self.database.create_beta1_user(username, "", password_salt_hex, salted_password_digest)

        if isinstance(result, int):
            result = struct.pack("I", result) + (b"\x00" * 7)  # Pad the message for encryption/decryption sanity

        return result