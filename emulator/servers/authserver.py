import binascii
import datetime
import hashlib
import hmac
import logging
import os
import pprint
import random
import secrets
import socket as real_socket
import struct
import time
import ipcalc

from Crypto.Hash import SHA, SHA1
from Crypto.Signature import pkcs1_15
from Crypto.Cipher import AES

import globalvars
import utilities.encryption as encryption
import utilities.name_suggestor
import utilities.time
import utils

from listmanagers.contentlistmanager import manager as csdsmanager
from listmanagers.dirlistmanager import manager as dirmanager
from utilities import auth_cc_blocker, blobs, cdr_manipulator, name_suggestor, sendmail, validationcode_manager
from utilities.blobs import blob_serialize, blob_unserialize
from utilities.database import ccdb
from utilities.database.authdb import auth_dbdriver
from utilities.networkhandler import TCPNetworkHandler
from utilities.ticket_utils import Steam2Ticket


# noinspection ProblematicWhitespace
class authserver(TCPNetworkHandler):
    def __init__(self, port, config):
        self.server_type = "AuthServer"
        self.innerkey = binascii.a2b_hex("10231230211281239191238542314233")

        self.validationcode_manager = validationcode_manager.VerificationCodeManager()
        self.suggestednames_amnt = int(config['amount_of_suggested_names'])
        self.islan = False
        self.dirmanager = dirmanager
        self.contentlist_manager = csdsmanager
        self.database = auth_dbdriver(config)
        self.innerIV = secrets.token_bytes(16)
        self.block_rules = auth_cc_blocker.load_block_rules(config['configsdir'] + '/' + 'creditcard_blacklist.txt')

        # Create an instance of NetworkHandler
        super(authserver, self).__init__(config, port, self.server_type)

    def send_mainkey(self, client_socket):
        mainkey = encryption.signed_mainkey_reply
        client_socket.send(mainkey)

    def send_netkey(self, client_socket):
        BERstring = bytes.fromhex("30819d300d06092a864886f70d010101050003818b0030818702818100") + encryption.network_key.n.to_bytes(128, byteorder = "big") + bytes.fromhex("020111")
        signature = pkcs1_15.new(encryption.network_key).sign(SHA1.new(BERstring))
        reply = struct.pack(">H", len(BERstring)) + BERstring + struct.pack(">H", len(signature)) + signature
        client_socket.send(reply)

    def handle_client(self, client_socket, client_address):

        # Load this everytime a client connects, this ensures that we can change the blob without restarting the server
        # ccdb.load_filesys_blob() # FIXME Deprecate this as it's not needed

        clientid = str(client_address) + ": "

        # Set a new random innerIV for security every time a connection is made, instead of doing it everytime a different packet is called. This should improve preformance a tiny amount.
        self.innerIV = secrets.token_bytes(16)

        self.log.info(f"{clientid}Connected to Auth Server")
        if str(client_address[0]) in ipcalc.Network(str(globalvars.server_net)):
            self.islan = True
        else:
            self.islan = False

        command = client_socket.recv(13)

        self.log.debug(f":{binascii.b2a_hex(command[1:5])}:")
        self.log.debug(f":{binascii.b2a_hex(command)}:")

        version_map = {
                b"\x00\x00\x00\x01": "b2003",  # 2003 beta 2
                b"\x00\x00\x00\x03": "r2003",  # 2003 release
                b"\x00\x00\x00\x04": "r2004",  # 2004-2007
                b"\x00\x00\x00\x05": "r2007",  # 2007+
        }

        cmd_slice = command[1:5]
        pkt_version = version_map.get(cmd_slice)

        if pkt_version == "r2004" and globalvars.record_ver == 2: #TODO - NOV 2003, CLIENT INCORRECT
            pkt_version == "r2003"
        # if globalvars.steamui_ver == 7:
        # pkt_version = "r2003"

        if pkt_version:
            self.log.debug(f"{clientid}Using {pkt_version} auth protocol")
        else:
            self.log.debug(f"{clientid}Unknown auth protocol")

        client_external_ip = real_socket.inet_aton(client_address[0])
        client_socket.send(b"\x00" + client_external_ip)
        self.log.debug(str(client_external_ip))
        self.log.debug(real_socket.inet_ntoa(client_external_ip))

        command = client_socket.recv_withlen()

        # TODO Look into missing packets: \x07, \x08, \x0d, \x17, \x18, \x19, \x1a
        # \x03 is Delete Account, Only used in 2002 Beta 1
        command_map = {
                b"\x01": self.create_user,
                b"\x02": self.login,
                # september 2003 has code in it for packet \x03 which is delete account, but it doesnt seem to be functional
                b"\x04": self.logout,
                b"\x05": self.subscribe,
                b"\x06": self.unsubscribe,
                b"\x09": self.ticket_login,
                b"\x0a": self.request_content_ticket,
                b"\x0b": self.send_CDR,
                b"\x0c": self.request_encrypted_userid_ticket,
                b"\x0e": self.reset_password_by_username,
                b"\x0f": self.reset_password,
                b"\x10": self.change_password,
                b"\x11": self.change_question,
                b"\x12": self.change_email,
                b"\x13": self.verify_email,
                b"\x14": self.request_verification_email,
                b"\x15": self.update_account_billinginfo,
                b"\x16": self.update_subscription_billinginfo,
                b"\x1b": self.unknown_1b,
                b"\x1c": self.change_account_name,
                b"\x1d": self.check_username_availability,
                b"\x1e": self.request_suggested_names,
                b"\x1f": self.generate_account_name,
                b"\x20": self.reset_password_by_email,
                b"\x21": self.reset_password_by_cdkey,
                b"\x22": self.get_num_accounts_with_email,
                b"\x23": self.subscription_receipt_acknowledgement,
                None: self.handle_unknown_command  # Default handler for unknown commands
        }

        command_byte = command[0:1]
        packet_method = command_map.get(command_byte, command_map[None])

        # Call the packet_method with the appropriate arguments
        packet_method(client_address, client_socket, clientid, command, pkt_version)

        client_socket.close()
        self.log.info(f"{clientid}Disconnected from Auth Server")

    def handle_unknown_command(self, client_address, client_socket, clientid, command, pkt_version):
        data = client_socket.recv(65535)
        self.log.warning(f"{clientid}Invalid command: {binascii.b2a_hex(command[0:1])}"
                    f"Extra data: {binascii.b2a_hex(data)}")

    def extract_payment_data(self, payment_type, additional_data):
        # pprint.pprint(additional_data)

        if payment_type == 1:  # Payment type 1
            payment_tuple = [additional_data[key].decode('latin-1').rstrip('\x00') for key in sorted(additional_data.keys()) if key not in [b'\x01\x00\x00\x00', b'\x14\x00\x00\x00', b'\x15\x00\x00\x00', b'\x2d\x00\x00\x00']]

            # Convert b'\x01\x00\x00\x00' from bytes to integer and insert at position 1
            payment_tuple.insert(0, int.from_bytes(additional_data[b'\x01\x00\x00\x00'], 'little'))

            price_before_tax = int.from_bytes(additional_data[b'\x14\x00\x00\x00'], 'little')
            tax_amount = int.from_bytes(additional_data[b'\x15\x00\x00\x00'], 'little')
            payment_tuple.extend([str(price_before_tax), str(tax_amount)])
            # Append additional variables
            payment_tuple.extend([
                    str(random.randint(111111, 999999)),  # CCApprovalCode
                    datetime.datetime.now().strftime("%d/%m/%Y"),  # TransDate
                    datetime.datetime.now().strftime("%H:%M:%S"),  # TransTime
                    str(random.randint(11111111, 99999999)),  # AStoBBSTxnId
            ])
            return tuple(payment_tuple)

        elif payment_type == 2:  # Payment type 2
            proof_of_purchase = additional_data[b'\x01\x00\x00\x00'].rstrip(b'\x00')
            purchase_token = additional_data[b'\x02\x00\x00\x00'].rstrip(b'\x00')
            # We decrypt the key using the rsa network key ONLY if it is a ValveCDKey
            # Also, remove the first 10 bytes
            if proof_of_purchase == b'ValveCDKey':
                decrypted_key = encryption.aes_decrypt_no_IV(encryption.network_key, purchase_token[10:]).decode('latin-1')
            else:
                decrypted_key = purchase_token.decode('latin-1')

            proof_of_purchase = proof_of_purchase.decode('latin-1')
            payment_record_tuple = (proof_of_purchase, decrypted_key)
            return payment_record_tuple

        elif payment_type == 3:  # Payment type 3
            return None

        elif payment_type == 4:
            self.log.error('[Subscribe] Payment type 4 (external billing) not supported!')
            self.log.error(additional_data)
            pprint.pprint(additional_data)
            return None

        else:
            return None  # Unknown or unsupported payment type

    def subscribe(self, client_address, client_socket, clientid, command, pkt_version):
        ticket_full = binascii.b2a_hex(command)
        command = ticket_full[0:2]
        ticket_len = ticket_full[2:6]
        tgt_ver = ticket_full[6:10]
        data1_len = ticket_full[10:14]
        data1_len = int(data1_len, 16) * 2
        userIV = binascii.a2b_hex(ticket_full[14 + data1_len:14 + data1_len + 32])
        username_len = ticket_full[314:318]
        username = binascii.a2b_hex(ticket_full[14:14 + (int(username_len, 16) * 2)]).decode('latin-1')
        ticket_len = int(ticket_len, 16) * 2
        ticket = ticket_full[2:ticket_len + 2]
        postticketdata = ticket_full[2 + ticket_len + 4:]
        key = self.innerkey
        iv = binascii.a2b_hex(postticketdata[0:32])
        encdata_len = int(postticketdata[36:40], 16) * 2
        encdata = postticketdata[40:40 + encdata_len]
        decodedmessage = binascii.b2a_hex(encryption.aes_decrypt(key, iv, binascii.a2b_hex(encdata)))
        decodedmessage = binascii.a2b_hex(decodedmessage)
        username_len_new = struct.unpack("<H", decodedmessage[0:2])
        username_len_new = (2 + username_len_new[0]) * 2
        header = username_len_new + 8
        blob_len = struct.unpack("<H", decodedmessage[header + 2:header + 4])
        blob_len = (blob_len[0])
        blob = decodedmessage[header:header + blob_len]

        blobnew = blobs.blob_unserialize(decodedmessage[header:header + blob_len])

        subscription_id = int.from_bytes(blobnew.get(b'\x01\x00\x00\x00', None), 'little')

        if self.database.check_username_exists(username):
            # TODO RETURN \X01 IF USER IS ABUSING RATELIMIT OR DEMAND IS TOO HIGH
            # We check if the user's email is verified IF SMTP is enabled and force_email_verification is true
            if not self.database.check_email_verified(username):
                if globalvars.smtp_enable.lower() == "true" and globalvars.force_email_verification.lower() == "true":
                    client_socket.send(b"\x02")
                    return

            # Extracting payment type
            payment_type = None
            additional_data = None
            sub_dict = blobnew.get(b'\x02\x00\x00\x00', None)
            #pprint.pprint(sub_dict)
            if sub_dict:
                payment_type = int.from_bytes(sub_dict.get(b'\x01\x00\x00\x00', None), 'little')
                additional_data = sub_dict.get(b'\x02\x00\x00\x00', None)
                #pprint.pprint(additional_data)
                # Setting receipt_id based on payment type using a dictionary
                receipt_id_map = {1:5, 2:6, 3:7, 4:8}
                receipt_id = receipt_id_map.get(payment_type, 7)

                # Get the payment tuple
                payment_data = self.extract_payment_data(payment_type, additional_data)

            else:
                # subscription 0
                receipt_id = 7
                payment_data = None
            if payment_data is not None:
                cc_card_number = payment_data[1]

            cc_blocked = False
            if receipt_id == 5 and auth_cc_blocker.is_card_blocked(cc_card_number, self.block_rules):
                cc_blocked = True
                self.log.info(f"{clientid} {username} Tried to use a blocked Card {cc_card_number}.")
                cc_card_type = payment_data[0]
                cc_name = payment_data[2]
                cc_zip = payment_data[9]
            else:
                # insert!
                self.database.insert_subscription(username, subscription_id, receipt_id, client_socket.ip_to_bytes(client_address[0]), payment_data)

            execdict = self.database.get_userregistry_dict(username, pkt_version, client_address[0])

            if cc_blocked:
                blocked_sub_dict = {
                        subscription_id.to_bytes(4, 'little'): {
                        b'\x01\x00\x00\x00': b'\x05',
                        b'\x02\x00\x00\x00': additional_data
                        }
                }

                blocked_sub_dict[b'\x02\x00\x00\x00'] = cc_card_number[12:].encode('latin-1') + b'\x00'

                # we add the information from the original packets x02 dictionary, but edit the cc to be the last 4 of the cc
                execdict[b'\x0f\x00\x00\x00'].update(blocked_sub_dict)

            if globalvars.steamui_ver == 5:  # FOR NOV 2003
                execdict.pop(b'\x0f\x00\x00\x00')

            # Print Final Subscriber Account Record Blob before sending it
            #pprint.pprint(execdict, width = 100)

            blob = blobs.blob_serialize(execdict)

            bloblen = len(blob)
            self.log.debug(f"Blob length: {str(bloblen)}")
            blob_encrypted = encryption.aes_encrypt(self.innerkey, self.innerIV, blob)
            blob_encrypted = struct.pack("<L", bloblen) + self.innerIV + blob_encrypted
            blob_signature = encryption.sign_message(self.innerkey, blob_encrypted)
            blob_encrypted_len = 10 + len(blob_encrypted) + 20
            blob_encrypted = struct.pack(">L", blob_encrypted_len) + b"\x01\x45" + struct.pack("<LL", blob_encrypted_len, 0) + blob_encrypted + blob_signature

            if pkt_version in ["b2003", "r2003"]:  # retail 2003, beta 2003
                client_socket.send(blob_encrypted)
            else:
                if not cc_blocked:
                    client_socket.send(b"\x00" + blob_encrypted)
                else:
                    client_socket.send(b"\x03" + blob_encrypted)

    def ticket_login(self, client_address, client_socket, clientid, command, pkt_version):
        ticket_full = binascii.b2a_hex(command)
        command = ticket_full[0:2]
        ticket_len = ticket_full[2:6]
        tgt_ver = ticket_full[6:10]
        self.log.debug(f"tgt_ver value: {tgt_ver}")
        data1_len = ticket_full[10:14]
        data1_len = int(data1_len, 16) * 2
        userIV = binascii.a2b_hex(ticket_full[14 + data1_len:14 + data1_len + 32])
        username_len = ticket_full[314:318]
        username = binascii.a2b_hex(ticket_full[14:14 + (int(username_len, 16) * 2)]).decode('latin-1')
        self.log.info(f"{clientid}Ticket login for: {username}")
        ticket_len = int(ticket_len, 16) * 2
        postticketdata = ticket_full[2 + ticket_len + 4:]
        key = self.innerkey
        iv = binascii.a2b_hex(postticketdata[0:32])
        encdata_len = int(postticketdata[36:40], 16) * 2
        encdata = postticketdata[40:40 + encdata_len]
        decodedmessage = binascii.b2a_hex(encryption.aes_decrypt(key, iv, binascii.a2b_hex(encdata)))
        # ------------------------------------------------------------------
        # client_socket.send(b"\x00")
        # create login ticket
        # TODO add/use authdb method check_or_set_auth_ticket for checking if ticket exists
        self.database.update_subscription_status_flags(username)

        #  Check if the user is real, like if you redo the database and have a client with an old clientregistry.blob
        #  and that client tries to login automatically, this will catch it and reject it if the username is not real
        if not self.database.check_username_exists(username):
            client_socket.send(b"\x03") # FIXME figure out the correct error code for this packet when a user does not exist!
            return

        execdict = self.database.get_userregistry_dict(username, pkt_version, client_address[0])

        if not isinstance(execdict, dict): # error
            client_socket.send(execdict)
            return

        if globalvars.steamui_ver == 5: #FOR NOV 2003
            execdict.pop(b'\x0f\x00\x00\x00')

        blob = blobs.blob_serialize(execdict)

        bloblen = len(blob)
        self.log.debug(f"Blob length: {str(bloblen)}")

        blob_encrypted = encryption.aes_encrypt(self.innerkey, self.innerIV, blob)
        blob_encrypted = struct.pack("<L", bloblen) + self.innerIV + blob_encrypted
        blob_signature = encryption.sign_message(self.innerkey, blob_encrypted)
        blob_encrypted_len = 10 + len(blob_encrypted) + 20
        blob_encrypted = struct.pack(">L", blob_encrypted_len) + b"\x01\x45" + struct.pack("<LL", blob_encrypted_len, 0) + blob_encrypted + blob_signature

        if pkt_version in ["b2003", "r2003"]:  # retail 2003, beta 2003
            client_socket.send(blob_encrypted)
        else:
            client_socket.send(b"\x00" + blob_encrypted)

        # set x05 to 0 if x03 is 1

        self.database.update_subscription_status_flags(username)

    def change_account_name(self, client_address, client_socket, clientid, command, pkt_version):
        self.log.info(f"{clientid}Change Account Name - Not Operational")
        self.log.debug(command)
        # TODO CHECK IF ACCOUNT NAME IN USE, IF TRUE SEND x02 ELSE SEND X00. x01 is unknown error!
        client_socket.send(b"\x01")

    def unknown_1b(self, client_address, client_socket, clientid, command, pkt_version):
        self.log.info(f"{clientid} Recieved Unknown Packet 0x1B - Not Operational")
        # TODO Figure out if any clients actually send this packet, then handle it correctly if they do
        self.log.debug(command)
        client_socket.send(b"\x01")

    def update_subscription_billinginfo(self, client_address, client_socket, clientid, command, pkt_version):
        self.log.info(f"{clientid}Update Subscription Billing Information - Not Operational")
        # TODO Figure out if any clients actually send this packet, then handle it correctly if they do
        self.log.debug(command)
        # DO NOT SEND ANYTHING TO CLIENT! JUST RETURN

    def update_account_billinginfo(self, client_address, client_socket, clientid, command, pkt_version):
        self.log.info(f"{clientid}Update Account Billing Information - Not Operational")
        # TODO Figure out if any clients actually send this packet, then handle it correctly if they do
        self.log.debug(command)
        # DO NOT SEND ANYTHING TO CLIENT! JUST RETURN

    def request_verification_email(self, client_address, client_socket, clientid, command, pkt_version):
        self.log.info(f"{clientid}Requested Verification Email - Not Operational")
        self.log.debug(command)
        # TODO SEND EMAIL CONTAINING EMAIL VERIFICATION CODE
        # DO NOT SEND ANYTHING TO CLIENT! JUST RETURN

    def verify_email(self, client_address, client_socket, clientid, command, pkt_version):
        self.log.info(f"{clientid}Verify Email - Not Operational")
        self.log.debug(command)
        # TODO CHECK VERIFICATION CODE FOR TIME (less than 15 minutes old) AND AGAINST WHAT THE USER SENT AS THE CODE
        client_socket.send(b"\x01")

    def send_CDR(self, client_address, client_socket, clientid, command, pkt_version):
        blob = cdr_manipulator.read_blob(self.islan)
        checksum = SHA.new(blob).digest()
        if checksum == command[1:]:
            self.log.info(f"{clientid}Client has matching checksum for secondblob")
            self.log.debug(f"{clientid}We validate it: {binascii.b2a_hex(command)}")

            client_socket.send(b"\x00\x00\x00\x00")

        else:
            self.log.info(f"{clientid}Client didn't match our checksum for secondblob")
            self.log.debug(f"{clientid}Sending new blob: {binascii.b2a_hex(command)}")

            client_socket.send_withlen(blob, True)  # false for not showing in log

    def reset_password_by_cdkey(self, client_address, client_socket, clientid, command, pkt_version):
        self.log.info(f"{clientid}Password reset by CD key")

        if pkt_version == "b2003":  # beta 2003
            self.send_netkey(client_socket)
        else:
            self.send_mainkey(client_socket)

        reply = client_socket.recv_withlen()
        RSAdata = reply[2:130]
        datalength = struct.unpack(">L", reply[130:134])[0]
        cryptedblob_signature = reply[134:136]
        cryptedblob_length = reply[136:140]
        cryptedblob_slack = reply[140:144]

        if pkt_version == "r2003":  # retail 2003
            cryptedblob = reply[144:144 + datalength - 10]
        else:
            cryptedblob = reply[144:]

        key = encryption.get_aes_key(RSAdata, encryption.network_key)
        self.log.debug(f"Message verification:{repr(encryption.verify_message(key, cryptedblob))}")

        if repr(encryption.verify_message(key, cryptedblob)):
            plaintext_length = struct.unpack("<L", cryptedblob[0:4])[0]
            IV = cryptedblob[4:20]
            ciphertext = cryptedblob[20:-20]
            plaintext = encryption.aes_decrypt(key, IV, ciphertext)
            plaintext = plaintext[0:plaintext_length]

            # print(plaintext)
            blobdict = blobs.blob_unserialize(plaintext)
            # print(blobdict)

            keychk = blobdict[b'\x01\x00\x00\x00']
            key_str = keychk.rstrip(b'\x00').decode('latin-1')
            username = self.database.check_resetcdkey(key_str)

            if username not in [-1, -2]:
                if pkt_version == "r2003":  # retail 2003
                    client_socket.send(b"\x01")
                else:
                    client_socket.send(b"\x00")

                if self.config["smtp_enabled"].lower() == "true":
                    self.send_change_info_validation_email(username, client_address)

            else:
                if username == -1:
                    self.log.error(f"{clientid}CDKey does not exist! cdkey: {key_str}")
                elif username == -2:
                    self.log.critical(f"{clientid}User Does Not Exist! THIS SHOULD NOT HAPPEN!!!")
                else:
                    self.log.error(f"{clientid}Failed to retrieve Username, Unknown Error")
        else:
            self.log.error(f"{clientid}Error - Could not Decrypt Password Reset By CDKey message")

            if pkt_version == "r2003":  # retail 2003
                client_socket.send(b"\x00")
            else:
                client_socket.send(b"\x01")

    def reset_password_by_email(self, client_address, client_socket, clientid, command, pkt_version):
        self.log.info(f"{clientid}Password reset by email")

        if pkt_version == "b2003":  # beta 2003
            self.send_netkey(client_socket)
        else:
            self.send_mainkey(client_socket)

        reply = client_socket.recv_withlen()

        RSAdata = reply[2:130]
        datalength = struct.unpack(">L", reply[130:134])[0]
        cryptedblob_signature = reply[134:136]
        cryptedblob_length = reply[136:140]
        cryptedblob_slack = reply[140:144]

        if pkt_version == "r2003":  # retail 2003
            cryptedblob = reply[144:144 + datalength - 10]
        else:
            cryptedblob = reply[144:]

        key = encryption.get_aes_key(RSAdata, encryption.network_key)
        self.log.debug(f"Message verification:{repr(encryption.verify_message(key, cryptedblob))}")

        if repr(encryption.verify_message(key, cryptedblob)):
            plaintext_length = struct.unpack("<L", cryptedblob[0:4])[0]
            IV = cryptedblob[4:20]
            ciphertext = cryptedblob[20:-20]
            plaintext = encryption.aes_decrypt(key, IV, ciphertext)
            plaintext = plaintext[0:plaintext_length]

            # print(plaintext)
            blobdict = blobs.blob_unserialize(plaintext)
            # print(blobdict)

            emailchk = blobdict[b'\x01\x00\x00\x00']
            email_str = emailchk.rstrip(b'\x00').decode()

            username = self.database.get_username_by_email(email_str)

            if username != 0:
                if pkt_version == "r2003":  # retail 2003
                    client_socket.send(b"\x01")
                else:
                    client_socket.send(b"\x00")

                if self.config["smtp_enabled"].lower() == "true":
                    self.send_change_info_validation_email(username, client_address)
            else:
                if pkt_version == "r2003":  # retail 2003
                    client_socket.send(b"\x00")
                else:
                    client_socket.send(b"\x01")

    def reset_password(self, client_address, client_socket, clientid, command, pkt_version):
        self.log.info(f"{clientid}Password reset by client")
        if pkt_version == "b2003":  # beta 2003
            self.send_netkey(client_socket)
        else:
            self.send_mainkey(client_socket)
        reply = client_socket.recv_withlen()
        RSAdata = reply[2:130]
        datalength = struct.unpack(">L", reply[130:134])[0]
        cryptedblob_signature = reply[134:136]
        cryptedblob_length = reply[136:140]
        cryptedblob_slack = reply[140:144]
        if pkt_version == "r2003":  # retail 2003
            cryptedblob = reply[144:144 + datalength - 10]
        else:
            cryptedblob = reply[144:]
        key = encryption.get_aes_key(RSAdata, encryption.network_key)
        self.log.debug(f"Message verification:{repr(encryption.verify_message(key, cryptedblob))}")

        if repr(encryption.verify_message(key, cryptedblob)):
            plaintext_length = struct.unpack("<L", cryptedblob[0:4])[0]
            IV = cryptedblob[4:20]
            ciphertext = cryptedblob[20:-20]
            plaintext = encryption.aes_decrypt(key, IV, ciphertext)
            plaintext = plaintext[0:plaintext_length]
            # print(plaintext)
            blobdict = blobs.blob_unserialize(plaintext)
            # print(blobdict)
            usernamechk = blobdict[b'\x01\x00\x00\x00']
            username_str = usernamechk.rstrip(b'\x00').decode('latin-1')

            # print(userblob)
            questionsalt = self.database.get_questionsalt(username_str)
            # print(questionsalt)
            if questionsalt != 0:
                client_socket.send(questionsalt)  # USER'S QUESTION SALT
                reply2 = client_socket.recv_withlen()
            else:
                self.log.error(f"{clientid}User Does not exist!")
                if pkt_version == "r2003":  # retail 2003
                    client_socket.send(b"\x00")
                else:
                    client_socket.send(b"\x01")
                client_socket.close()
                return

            header = reply2[0:2]
            enc_len = reply2[2:6]
            zeros = reply2[6:10]
            blob_len = reply2[10:14]
            innerIV = reply2[14:30]
            enc_blob = reply2[30:-20]
            sig = reply2[-20:]
            dec_blob = encryption.aes_decrypt(key, innerIV, enc_blob)
            unser_blob = blobs.blob_unserialize(dec_blob[:-dec_blob[-1]])

            validationcode = unser_blob[b"\x04\x00\x00\x00"].rstrip(b'\x00').decode('latin-1')
            answer_digest = unser_blob[b'\x01\x00\x00\x00'].hex()
            new_password_salt = unser_blob[b'\x02\x00\x00\x00'].hex()
            new_password_digest = unser_blob[b'\x03\x00\x00\x00'].hex()

            # pprint.pprint(unser_blob)

            emailaddress = self.database.get_user_email(username_str)
            _, db_answer_digest = self.database.get_question_info(username_str)

            if self.config["smtp_enabled"].lower() == "true":
                if not self.database.check_validationcode(username_str, validationcode):
                    self.log.warning(f"{clientid}Validation Code Incorrect for: {username_str}")
                    if pkt_version == "r2003":  # retail 2003
                        client_socket.send(b"\x00")
                    else:
                        client_socket.send(b"\x02")

                    # We send a failed attempt email to warn user
                    sendmail.send_attempted_pw_change_email(emailaddress, client_address, username_str)
                    client_socket.close()
                    return

            else: # we skip the code/question check
                pass
            result = False

            if answer_digest[0:16] == db_answer_digest[0:16]:
                result = self.database.change_password(username_str, new_password_digest, new_password_salt)
            else:
                self.log.warning(f"{clientid}Answer to personal question incorrect for user: {username_str}")
                if pkt_version == "r2003":  # retail 2003
                    client_socket.send(b"\x00")
                else:
                    client_socket.send(b"\x03")
                sendmail.send_attempted_pw_change_email(emailaddress, client_address, username_str)
                client_socket.close()
                return

            if result:
                self.log.info(f"{clientid}Password changed for: {username_str}")
                if pkt_version == "r2003":  # retail 2003
                    client_socket.send(b"\x01")
                else:
                    client_socket.send(b"\x00")

                if self.config["smtp_enabled"].lower() == "true":
                    sendmail.send_password_changed_email(emailaddress, client_address, username_str)

            else:
                self.log.warning(f"{clientid}Database error for: {username_str}")
                if pkt_version == "r2003":  # retail 2003
                    client_socket.send(b"\x00")
                else:
                    client_socket.send(b"\x03")

        else:
            self.log.warning(f"{clientid}Password change message could not be decrypted")
            if pkt_version == "r2003":  # retail 2003
                client_socket.send(b"\x00")
            else:
                client_socket.send(b"\x03")

    def reset_password_by_username(self, client_address, client_socket, clientid, command, pkt_version):
        self.log.info(f"{clientid}Password reset: check username exists")
        if pkt_version == "b2003":  # beta 2003
            self.send_netkey(client_socket)
        else:
            self.send_mainkey(client_socket)

        reply = client_socket.recv_withlen()
        RSAdata = reply[2:130]
        datalength = struct.unpack(">L", reply[130:134])[0]
        cryptedblob_signature = reply[134:136]
        cryptedblob_length = reply[136:140]
        cryptedblob_slack = reply[140:144]
        if pkt_version == "r2003":  # retail 2003
            cryptedblob = reply[144:144 + datalength - 10]
        else:
            cryptedblob = reply[144:]
        key = encryption.get_aes_key(RSAdata, encryption.network_key)
        self.log.debug(f"Message verification:{repr(encryption.verify_message(key, cryptedblob))}")
        plaintext_length = struct.unpack("<L", cryptedblob[0:4])[0]
        IV = cryptedblob[4:20]
        ciphertext = cryptedblob[20:-20]

        if pkt_version == "b2003":  # Beta 2003
            if len(ciphertext[encryption.BS:]) % encryption.BS != 0: # BEN NOTE: Beta 2 2003 client packet needs to be padded! or it wont decrypt
                ciphertext = encryption.pad(ciphertext)

        plaintext = encryption.aes_decrypt(key, IV, ciphertext)
        plaintext = plaintext[0:plaintext_length]

        # Beta2 2003 packet example:
        # b'\x01P:\x00\x00\x00\x00\x00\x00\x00\x04\x00\x0e\x00\x00\x00\x01\x00\x00\x00test@test.com\x00\x04\x00\x0e\x00\x00\x00\x02\x00\x00\x00test@test.com\x00'

        # print(plaintext)
        blobdict = blobs.blob_unserialize(plaintext)
        # print(blobdict)

        usernamechk = blobdict[b'\x01\x00\x00\x00']
        username_str = usernamechk.rstrip(b'\x00').decode('latin-1')

        # pprint.pprint(blobdict)
        # 0 = no personal question set or 1 = success, 2 = account or user does not exist, 3 user blocked, > 3 unknown error

        if self.database.check_username_exists(username_str):
            if pkt_version == "r2003":  # retail 2003
                client_socket.send(b"\x01")
            else:
                client_socket.send(b"\x00")

            if self.config["smtp_enabled"].lower() == "true":
                self.send_change_info_validation_email(username_str, client_address)
        else:
            if pkt_version == "r2003":  # retail 2003
                client_socket.send(b"\x00")
            elif pkt_version == "b2003":  # beta 2003
                if self.database.check_email_exists(username_str):
                    print('Email found')
                    # Steam expects a blob with the question expects the packet ti be encrypted
                    # TODO: finnish beta 2 forgotten password
                    """question ={
                            b'\x01\x00\x00\x00': b'this is a question\x00'
                    }
                    blob = blob_serialize(question)
                    client_socket.send_withlen(b'\x00' + struct.pack('<H', len(blob)) + blob)  # USER'S QUESTION SALT
                    reply2 = client_socket.recv_withlen()
                    print(reply2)
                    #else:
                    #    self.log.error(f"{clientid}User Does not exist!")"""
                    self.log.error(f"Beta 2003 Forgot Password functionality not implemented yet!")
                    client_socket.send(b"\x01")
                else:
                    print('Email not found')
                    client_socket.send(b"\x00")
            else:
                client_socket.send(b"\x01")

    def create_user(self, client_address, client_socket, clientid, command, pkt_version):
        self.log.info(f"{clientid}New user: Create user")
        if pkt_version == "b2003":  # beta 2003
            self.send_netkey(client_socket)
        else:
            self.send_mainkey(client_socket)

        reply = client_socket.recv_withlen()
        encr_key_len, = struct.unpack(">H", reply[0:2])
        RSAdata = reply[2:130]
        datalength = struct.unpack(">L", reply[130:134])[0]
        cryptedblob_signature = reply[134:136]
        cryptedblob_length = reply[136:140]
        cryptedblob_slack = reply[140:144]
        cryptedblob = reply[144:144 + datalength - 10]  # modified for Steam '03 support

        key = encryption.get_aes_key(RSAdata, encryption.network_key)
        self.log.debug(f"Message verification:{repr(encryption.verify_message(key, cryptedblob))}")
        plaintext_length = struct.unpack("<L", cryptedblob[0:4])[0]
        IV = cryptedblob[4:20]
        ciphertext = cryptedblob[20:-20]
        plaintext = encryption.aes_decrypt(key, IV, ciphertext)
        plaintext = plaintext[0:plaintext_length]
        # print(plaintext)
        plainblob = blobs.blob_unserialize(plaintext)
        # print(plainblob)
        username_bytes = plainblob[b'\x01\x00\x00\x00'].rstrip(b'\x00')
        username_str = username_bytes.decode('latin-1')

        if not pkt_version in ["b2003", "r2003", "r2004"]:
            if utils.check_username(username_str) == 2:
                self.log.error(f"{clientid}Client Username Had Illegal Characters")
                client_socket.send(b'\x02')
                client_socket.close()
                return
        if self.database.check_username_exists(username_str):
            self.log.error(f"{clientid}Username Already Exists!")
            client_socket.send(b'\x02')
            client_socket.close()
            return

        if not pkt_version == "b2003":  # beta 2003
            email_str = plainblob[b'\x0b\x00\x00\x00'].rstrip(b'\x00').decode('latin-1')
        else:
            email_str = username_str

        if utils.check_email(email_str) == 3:
            self.log.error(f"{clientid}Client Email Had Illegal Characters")
            client_socket.send(b'\x03')
            client_socket.close()
            return
        # pprint.pprint(plainblob)
        password_digest = plainblob[b'\x05\x00\x00\x00'][username_bytes][b'\x01\x00\x00\x00'][0:16].hex()
        password_salt = plainblob[b'\x05\x00\x00\x00'][username_bytes][b'\x02\x00\x00\x00'].hex()
        question = plainblob[b'\x05\x00\x00\x00'][username_bytes][b'\x03\x00\x00\x00'].rstrip(b'\x00').decode('latin-1')
        answer_digest = plainblob[b'\x05\x00\x00\x00'][username_bytes][b'\x04\x00\x00\x00'].hex()
        answer_salt = plainblob[b'\x05\x00\x00\x00'][username_bytes][b'\x05\x00\x00\x00'].hex()

        result = self.database.create_user(username_str, password_salt, password_digest, question, answer_salt, answer_digest, email_str, pkt_version)

        if globalvars.steamui_ver == 5: #FOR NOV 2003
            pkt_version = "r2003"

        if result == 1:
            if pkt_version in ["b2003", "r2003"]:  # beta 2003
                client_socket.send(b"\x01")
            else:
                client_socket.send(b"\x00")

            if globalvars.smtp_enable == "true":
                self.send_email(username_str, client_address, 'newuser')

        else:
            if pkt_version in ["b2003", "r2003"]:  # beta 2003
                client_socket.send(b"\x00")
            else:
                client_socket.send(b"\x01")

    def subscription_receipt_acknowledgement(self, client_address, client_socket, clientid, command, pkt_version):
        """d: b'#\x01h\x00\x01\x00\x80testtest\x00\x01\xb4\x03\xa8\xc0\xc0\xa8\x03\xb4\xc0\xa8\x03\xb4\xa0i\xc0\xa8\x03\xb4\xa0i\xb4\xa3g:\'\xafS\x8a\xc1\x16\x0e\xf8\xebw\x07Q\x80\xcf\xba\x80\xaf\xe6\xe2\x00\x80\x8a\xa9!\xb0\xe6\xe2\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xa6\xbc\xd3\xd1\xa1\x0f\x05\x14\x83\x03\xce\xc2D1^\xc4\x00B\x00P\x00\x00\x00\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00^\x8a>Y\x9f"c\x80`\xc0,\xd36\xb4\xdfQ\x00,\x000\\\x0bn\x98\xa0F\x0f\xac\x1e_N"l\x9b\xaa=\x0fY=\xd2Y3E<R3\xbe\xcf\x039\xe8\xa0\xec\xea;\xf2\x7f\x7f\x8f_\xb42\xe3}\xa7\xe5C^\x92q\xd4\x1b\x7f#\xb6\x81\x99\xfc\x1e&\xd5\xa3\x8d\xb5\xf4+x\x80'"""
        self.log.info(f"{clientid}Client Acknowledged Subscription Receipt command: {command}")
        ticket = Steam2Ticket(command[3:])
        self.database.change_subscriptions_changeflag(ticket.username_str)
        client_socket.close()

    def get_num_accounts_with_email(self, client_address, client_socket, clientid, command, pkt_version):
        self.log.info(f"{clientid}Client Requested Email Address Check")
        if pkt_version == "b2003":  # beta 2003
            self.send_netkey(client_socket)
        else:
            self.send_mainkey(client_socket)

        reply = client_socket.recv_withlen()
        RSAdata = reply[2:130]
        datalength = struct.unpack(">L", reply[130:134])[0]
        cryptedblob_signature = reply[134:136]
        cryptedblob_length = reply[136:140]
        cryptedblob_slack = reply[140:144]
        cryptedblob = reply[144:]
        key = encryption.get_aes_key(RSAdata, encryption.network_key)
        self.log.debug(f"Message verification:{repr(encryption.verify_message(key, cryptedblob))}")
        plaintext_length = struct.unpack("<L", cryptedblob[0:4])[0]
        IV = cryptedblob[4:20]
        ciphertext = cryptedblob[20:-20]
        plaintext = encryption.aes_decrypt(key, IV, ciphertext)
        plaintext = plaintext[0:plaintext_length]
        # print(plaintext)
        plainblob = blobs.blob_unserialize(plaintext)
        # print(plainblob)
        email = plainblob[b'\x01\x00\x00\x00']
        email_str = email.rstrip(b'\x00').decode('latin-1')
        # print(len(username_str))
        self.log.info(f"{clientid}New user: check email exists: {email_str}")

        num_of_accts = self.database.get_numaccts_with_email(email_str)
        if num_of_accts != 0:
            self.log.warning(f"{clientid}New user: email already in use")
            client_socket.send(b"\x00" + num_of_accts.to_bytes(4, "little")) # \x01 = error
        else:
            self.log.info(f"{clientid}New user: email ok to use")
            client_socket.send(b"\x00" + b"\x00\x00\x00\x00") # 0 accounts / none

    def request_suggested_names(self, client_address, client_socket, clientid, command, pkt_version):
        self.log.info(f"{clientid}Get Suggested names packet")
        if pkt_version == "b2003":
            self.send_netkey(client_socket)
        else:
            self.send_mainkey(client_socket)

        reply = client_socket.recv_withlen()
        RSAdata = reply[2:130]
        datalength = struct.unpack(">L", reply[130:134])[0]
        cryptedblob_signature = reply[134:136]
        cryptedblob_length = reply[136:140]
        cryptedblob_slack = reply[140:144]
        cryptedblob = reply[144:]
        key = encryption.get_aes_key(RSAdata, encryption.network_key)
        self.log.debug(f"Message verification:{repr(encryption.verify_message(key, cryptedblob))}")
        plaintext_length = struct.unpack("<L", cryptedblob[0:4])[0]
        IV = cryptedblob[4:20]
        ciphertext = cryptedblob[20:-20]
        plaintext = encryption.aes_decrypt(key, IV, ciphertext)
        plaintext = plaintext[0:plaintext_length]
        # print(plaintext)
        plainblob = blobs.blob_unserialize(plaintext)
        # print(plainblob)
        username = plainblob[b'\x01\x00\x00\x00']
        username_str = username.rstrip(b'\x00')
        suggestedname = name_suggestor.similar_username_generator(username_str.decode('latin-1'), self.suggestednames_amnt, self.database)
        ser_suggestednames = blobs.blob_serialize(suggestedname)
        client_socket.send_withlen(ser_suggestednames)

    def check_username_availability(self, client_address, client_socket, clientid, command, pkt_version):
        if pkt_version == "b2003":
            self.send_netkey(client_socket)
        else:
            self.send_mainkey(client_socket)

        reply = client_socket.recv_withlen()
        RSAdata = reply[2:130]
        datalength = struct.unpack(">L", reply[130:134])[0]
        cryptedblob_signature = reply[134:136]
        cryptedblob_length = reply[136:140]
        cryptedblob_slack = reply[140:144]
        cryptedblob = reply[144:]
        key = encryption.get_aes_key(RSAdata, encryption.network_key)
        self.log.debug(f"Message verification:{repr(encryption.verify_message(key, cryptedblob))}")
        plaintext_length = struct.unpack("<L", cryptedblob[0:4])[0]
        IV = cryptedblob[4:20]
        ciphertext = cryptedblob[20:-20]
        plaintext = encryption.aes_decrypt(key, IV, ciphertext)
        plaintext = plaintext[0:plaintext_length]
        # print(plaintext)
        plainblob = blobs.blob_unserialize(plaintext)
        # print(plainblob)
        username = plainblob[b'\x01\x00\x00\x00']
        username_str = username.rstrip(b'\x00').decode('latin-1')
        # print(len(username_str))
        self.log.info(f"{clientid}New user: check username exists: {username_str}")

        if self.database.check_username_exists(username_str):
            self.log.warning(f"{clientid}New user: username already exists")
            client_socket.send(b"\x01")
        else:
            self.log.info(f"{clientid}New user: username not found")
            client_socket.send(b"\x00")

    def request_encrypted_userid_ticket(self, client_address, client_socket, clientid, command, pkt_version):
        # TODO FIGURE OUT THIS PACKET
        self.log.info(f"{clientid}Get Encrypted UserID Ticket To Send To AppServer  - Not Operational")
        self.log.debug(command)
        client_socket.send(b"\x01")

    def request_content_ticket(self, client_address, client_socket, clientid, command, pkt_version):
        ticket_full = binascii.b2a_hex(command)
        command = ticket_full[0:2]
        ticket_len = ticket_full[2:6]
        tgt_ver = ticket_full[6:10]
        data1_len = ticket_full[10:14]
        data1_len = int(data1_len, 16) * 2
        userIV = binascii.a2b_hex(ticket_full[14 + data1_len:14 + data1_len + 32])
        username_len = ticket_full[314:318]
        username = binascii.a2b_hex(ticket_full[14:14 + (int(username_len, 16) * 2)])
        self.log.info(f"{clientid}Content login for: {username}")
        ticket_len = int(ticket_len, 16) * 2
        postticketdata = ticket_full[2 + ticket_len + 4:]
        key = self.innerkey
        iv = binascii.a2b_hex(postticketdata[0:32])
        encdata_len = int(postticketdata[36:40], 16) * 2
        encdata = postticketdata[40:40 + encdata_len]
        decodedmessage = binascii.b2a_hex(encryption.aes_decrypt(key, iv, binascii.a2b_hex(encdata)))
        # ------------------------------------------------------------------
        # Incompatible ContentTicket VersionNum
        # u16SizeOfPlaintextClientReadableContentTicket
        # Bad u16SizeOfAESEncryptedClientReadableContentTicket
        # u16SizeOfServerReadableContentTicket
        currtime = time.time()
        client_ticket = b"\x69" * 0x10  # key used for MAC signature
        client_ticket += utilities.time.unixtime_to_steamtime(currtime)  # TicketCreationTime
        client_ticket += utilities.time.unixtime_to_steamtime(currtime + 86400)  # TicketValidUntilTime
        client_ticket += os.urandom(4)  # struct.pack("<I", 1)
        client_ticket += os.urandom(8)  # struct.pack("<II", 1, 2)

        if self.islan:
            matches, count = self.contentlist_manager.find_ip_address(islan = True)
            if count > 0:
                cs_lan_ip, port = matches[0]
                client_ticket += utils.encodeIP((cs_lan_ip, port)) + b"\x00\x00"  # why are there extra bytes? maybe padding to 4 byte boundary
            else:
                client_ticket += utils.encodeIP((self.config["server_ip"], self.config["content_server_port"])) + b"\x00\x00"  # why are there extra bytes? maybe padding to 4 byte boundary
        else:
            matches, count = self.contentlist_manager.find_ip_address()
            if count > 0:
                cs_wan_ip, port = matches[0]
                client_ticket += utils.encodeIP((cs_wan_ip, port)) + b"\x00\x00"  # why are there extra bytes? maybe padding to 4 byte boundary
            else:
                client_ticket += utils.encodeIP((self.config["public_ip"], self.config["content_server_port"])) + b"\x00\x00"  # why are there extra bytes? maybe padding to 4 byte boundary

        server_ticket = b"\x55" * 0x80 # <---- TODO No info in ida about this blob, it was only serverside related shit
        innerIV = secrets.token_bytes(16)
        client_ticket_encrypted = encryption.aes_encrypt(key, innerIV, client_ticket)  # utils.encrypt_with_pad(client_ticket, key, innerIV)
        if pkt_version == "b2003":  # beta 2003
            ticket = b"\x00\x01"
        else:  # retail 2003, 2004, 2007
            ticket = b"\x00\x02"
        ticket += innerIV + struct.pack(">HH", len(client_ticket), len(client_ticket_encrypted)) + client_ticket_encrypted
        ticket += struct.pack(">H", len(server_ticket)) + server_ticket
        # ticket_signed = ticket + hmac.digest(client_ticket[0:16], ticket, hashlib.sha1)
        ticket_signed = ticket + hmac.new(client_ticket[0:16], ticket, hashlib.sha1).digest()
        client_socket.send(b"\x00\x01" + struct.pack(">I", len(ticket_signed)) + ticket_signed)

    def logout(self, client_address, client_socket, clientid, command, pkt_version):
        ticket_full = binascii.b2a_hex(command)
        command = ticket_full[0:2]
        ticket_len = ticket_full[2:6]
        tgt_ver = ticket_full[6:10]
        self.log.debug(f"tgt_ver value: {tgt_ver}")
        data1_len = ticket_full[10:14]
        data1_len = int(data1_len, 16) * 2
        userIV = binascii.a2b_hex(ticket_full[14 + data1_len:14 + data1_len + 32])
        username_len = ticket_full[314:318]
        username = binascii.a2b_hex(ticket_full[14:14 + (int(username_len, 16) * 2)])
        self.log.info(f"{clientid}User {username} logged out")

    def generate_account_name(self, client_address, client_socket, clientid, command, pkt_version):
        # TODO FIGURE OUT THIS PACKET!
        self.log.info(f"{clientid}Generate Suggested Name packet 2 - Not Operational")
        self.log.debug(command)
        self.send_mainkey(client_socket)
        reply = client_socket.recv_withlen()
        RSAdata = reply[2:130]
        datalength = struct.unpack(">L", reply[130:134])[0]
        cryptedblob_signature = reply[134:136]
        cryptedblob_length = reply[136:140]
        cryptedblob_slack = reply[140:144]
        cryptedblob = reply[144:]
        key = encryption.get_aes_key(RSAdata, encryption.network_key)
        self.log.debug("Message verification:" + repr(encryption.verify_message(key, cryptedblob)))
        plaintext_length = struct.unpack("<L", cryptedblob[0:4])[0]
        IV = cryptedblob[4:20]
        ciphertext = cryptedblob[20:-20]
        plaintext = encryption.aes_decrypt(key, IV, ciphertext)
        plaintext = plaintext[0:plaintext_length]
        # print(plaintext)
        plainblob = blobs.blob_unserialize(plaintext)
        pprint.pprint(plainblob)
        client_socket.send(b"\x01")

    def change_email(self, client_address, client_socket, clientid, command, pkt_version):
        self.log.info(f"{clientid}Change email")
        ticket_full = binascii.b2a_hex(command)
        command = ticket_full[0:2]
        ticket_len = ticket_full[2:6]
        tgt_ver = ticket_full[6:10]
        data1_len = ticket_full[10:14]
        data1_len = int(data1_len, 16) * 2
        userIV = binascii.a2b_hex(ticket_full[14 + data1_len:14 + data1_len + 32])
        username_len = ticket_full[314:318]
        username = binascii.a2b_hex(ticket_full[14:14 + (int(username_len, 16) * 2)]).decode('latin-1')
        ticket_len = int(ticket_len, 16) * 2
        ticket = ticket_full[2:ticket_len + 2]
        postticketdata = ticket_full[2 + ticket_len + 4:]
        key = self.innerkey
        iv = binascii.a2b_hex(postticketdata[0:32])
        encdata_len = int(postticketdata[36:40], 16) * 2
        encdata = postticketdata[40:40 + encdata_len]
        decodedmessage = binascii.b2a_hex(encryption.aes_decrypt(key, iv, binascii.a2b_hex(encdata)))
        decodedmessage = binascii.a2b_hex(decodedmessage)
        username_len_new = struct.unpack("<H", decodedmessage[0:2])
        username_len_new = (2 + username_len_new[0]) * 2
        header = username_len_new + 8
        blob_len = struct.unpack("<H", decodedmessage[header + 2:header + 4])
        blob_len = (blob_len[0])
        blob = (decodedmessage[header:header + blob_len])
        new_emailaddress = blob[:-struct.unpack(">B", blob[-1:])[0]].decode('latin-1')
        original_emailaddress = self.database.get_user_email(username)

        if not self.database.change_email(username, new_emailaddress):
            self.log.error(f"{clientid}Database Error While Changing Email Address!")
            client_socket.send(b"\x01")
            client_socket.close()
            return

        userblob = self.database.get_userregistry_dict(username, pkt_version, client_address[0])

        blob = blobs.blob_serialize(userblob)

        # print(blob)
        bloblen = len(blob)
        self.log.debug(f"Blob length: {str(bloblen)}")

        # innerIV  = secrets.token_bytes(16) #ONLY FOR BLOB ENCRYPTION USING AES-CBC
        innerIV = userIV
        blob_encrypted = encryption.aes_encrypt(self.innerkey, innerIV, blob)
        blob_encrypted = struct.pack("<L", bloblen) + innerIV + blob_encrypted
        blob_signature = encryption.sign_message(self.innerkey, blob_encrypted)
        blob_encrypted_len = 10 + len(blob_encrypted) + 20
        blob_encrypted = struct.pack(">L", blob_encrypted_len) + b"\x01\x45" + struct.pack("<LL", blob_encrypted_len, 0) + blob_encrypted
        ticket = ticket + blob_encrypted
        ticket_signed = ticket + encryption.sign_message(self.innerkey, ticket)
        client_socket.send(b"\x00" + blob_encrypted + blob_signature)


        if self.config["smtp_enabled"].lower() == "true":
            sendmail.send_email_changed_email(original_emailaddress, client_address, username)
            sendmail.send_email_changed_email(new_emailaddress, client_address, username)

    def change_question(self, client_address, client_socket, clientid, command, pkt_version):
        ticket_full = binascii.b2a_hex(command)
        command = ticket_full[0:2]
        ticket_len = ticket_full[2:6]
        tgt_ver = ticket_full[6:10]
        data1_len = ticket_full[10:14]
        username_len = ticket_full[314:318]
        username = binascii.a2b_hex(ticket_full[14:14 + (int(username_len, 16) * 2)]).decode('latin-1')
        self.log.info(f"{clientid}Secret question change requested for: {username}")
        userblob = {}
        _, personalsalt = self.database.get_userpass_stuff(username)
        # print(personalsalt)
        client_socket.send(personalsalt)  # NEW SALT PER USER
        blobtext = client_socket.recv_withlen()
        key = self.innerkey
        IV = secrets.token_bytes(16)
        if pkt_version == "r2003":  # retail 2003
            crypted_blob = blobtext[14:]
        else:  # beta 2003???, 2004 2007
            crypted_blob = blobtext[10:]
        if repr(encryption.verify_message(key, crypted_blob)):
            emailaddress = self.database.get_user_email(username)
            plaintext = encryption.aes_decrypt(key, IV, crypted_blob[4:-4])
            blob_len = int(binascii.b2a_hex(plaintext[18:19]), 16)
            blob_len = len(plaintext) - 16 - blob_len
            blob = blobs.blob_unserialize(plaintext[16:-blob_len])
            # print(blob)
            # print(binascii.b2a_hex(blob[b'\x01\x00\x00\x00']))
            # print(binascii.b2a_hex(userblob[b'\x05\x00\x00\x00'][username][b'\x01\x00\x00\x00']))
            result = self.database.change_question(
                    username,
                    blob[b'\x01\x00\x00\x00'].hex(),
                    blob[b'\x02\x00\x00\x00'],
                    blob[b'\x03\x00\x00\x00'].hex(),
                    blob[b'\x04\x00\x00\x00'].hex())
            if result > 0:
                self.log.info(f"{clientid}Secret question changed for: {username}")
                if pkt_version == "r2003":  # retail 2003
                    client_socket.send(b"\x01")
                else:
                    client_socket.send(b"\x00")

                if self.config["smtp_enabled"].lower() == "true":
                    sendmail.send_question_changed_confirmation(emailaddress, client_address, username)
            elif result == -2:
                self.log.warning(f"{clientid}Secret question change failed (Incorrect Password) for: {username}")
                if pkt_version == "r2003":  # retail 2003
                    client_socket.send(b"\x00")
                else:
                    client_socket.send(b"\x01")

                # TODO SHOULD WE SEND AN FAILED ATTEMPT EMAIL?
                #if self.config["smtp_enabled"].lower() == "true":
                #    sendmail.send_question_changed_attempt(emailaddress, client_address, username)
            else:
                self.log.warning(f"{clientid}Database error for: {username}")
                if pkt_version == "r2003":  # retail 2003
                    client_socket.send(b"\x00")
                else:
                    client_socket.send(b"\x01")

        else:
            self.log.warning(f"{clientid}Secret question change failed for: {username}")
            if pkt_version == "r2003":  # retail 2003
                client_socket.send(b"\x00")
            else:
                client_socket.send(b"\x01")

    def change_password(self, client_address, client_socket, clientid, command, pkt_version):
        ticket_full = binascii.b2a_hex(command)
        command = ticket_full[0:2]
        ticket_len = ticket_full[2:6]
        tgt_ver = ticket_full[6:10]
        data1_len = ticket_full[10:14]
        username_len = ticket_full[314:318]
        username = binascii.a2b_hex(ticket_full[14:14 + (int(username_len, 16) * 2)]).decode('latin-1')
        self.log.info(f"{clientid}Password change requested for: {username}")
        userblob = {}

        original_passworddigest, personalsalt = self.database.get_userpass_stuff(username)
        # print(personalsalt)
        client_socket.send(personalsalt)

        blobtext = client_socket.recv_withlen()

        key = self.innerkey
        IV = secrets.token_bytes(16)

        if pkt_version == "r2003":  # retail 2003
            crypted_blob = blobtext[14:]
        else:
            crypted_blob = blobtext[10:]

        if repr(encryption.verify_message(key, crypted_blob)):
            plaintext = encryption.aes_decrypt(key, IV, crypted_blob[4:-4])
            blob_len = int(binascii.b2a_hex(plaintext[18:19]), 16)
            blob_len = len(plaintext) - 16 - blob_len
            blob = blobs.blob_unserialize(plaintext[16:-blob_len])
            # print(blob)
            # print(binascii.b2a_hex(blob[b'\x01\x00\x00\x00']))
            # print(binascii.b2a_hex(userblob[b'\x05\x00\x00\x00'][username][b'\x01\x00\x00\x00']))
            # pprint.pprint(blob)
            # print(original_passworddigest)
            # print(personalsalt)

            sent_digest = blob[b'\x01\x00\x00\x00']
            new_password_salt = blob[b'\x02\x00\x00\x00'].hex()
            new_password_digest = blob[b'\x03\x00\x00\x00'][0:16].hex()
            emailaddress = self.database.get_user_email(username)
            pprint.pprint(blob)

            if sent_digest[0:16] == original_passworddigest[0:16]:
                if self.database.change_password(username, new_password_digest, new_password_salt):
                    self.log.info(f"{clientid}Password changed for: {username}")

                    if pkt_version == "r2003":  # retail 2003
                        client_socket.send(b"\x01")
                    else:
                        client_socket.send(b"\x00")

                    if self.config["smtp_enabled"].lower() == "true":
                        sendmail.send_password_changed_email(emailaddress, client_address, username)
                else:
                    self.log.warning(f"{clientid}Database error for: {username}")
                    if pkt_version == "r2003":  # retail 2003
                        client_socket.send(b"\x00")
                    else:  # beta 2003????, 2004, 2007+
                        client_socket.send(b"\x01")
            else:
                self.log.warning(f"{clientid}Password change failed (Incorrect Original Password) for: {username}")
                if pkt_version == "r2003":  # retail 2003
                    client_socket.send(b"\x00")
                else:
                    client_socket.send(b"\x01")

                if self.config["smtp_enabled"].lower() == "true":
                    sendmail.send_attempted_pw_change_email(emailaddress, client_address, username)
        else:
            self.log.warning(f"{clientid}Password change failed (User Does Not Exist) for: {username}")
            if pkt_version == "r2003":  # retail 2003
                client_socket.send(b"\x00")
            else:
                client_socket.send(b"\x01")

    def login(self, client_address, client_socket, clientid, command, pkt_version):
        usernamelen = struct.unpack(">H", command[1:3])[0]
        self.log.debug(f"{clientid}Main login command: {binascii.b2a_hex(command[0:1])}")

        if globalvars.steamui_ver > 4 and globalvars.steamui_ver < 8: #FOR NOV 2003 - FEB 2004
            pkt_version = "r2003"
        
        username_bytes = command[3:3 + usernamelen]
        username = username_bytes.decode('latin-1').lower()
        if not self.database.check_username_exists(username):
            self.log.info(f"{clientid}Unknown user: {username}")
            client_socket.send(b"\x00\x00\x00\x00\x00\x00\x00\x00")
            steamtime = utilities.time.unixtime_to_steamtime(time.time())
            tgt_command = b"\x01"  # UNKNOWN USER
            padding = b"\x00" * 1222
            ticket_full = tgt_command + steamtime + padding
            if pkt_version in ["b2003", "r2003"]:
                client_socket.send(b"\x02")
                client_socket.close()
            else:
                client_socket.send(ticket_full)
                client_socket.close()
            return

        if self.database.check_user_banned(username):
            self.log.info(f"{clientid}Blocked user: {username}")
            client_socket.send(b"\x00\x00\x00\x00\x00\x00\x00\x00")
            command = client_socket.recv_withlen()
            steamtime = utilities.time.unixtime_to_steamtime(time.time())
            tgt_command = b"\x04"  # BLOCKED
            padding = b"\x00" * 1222
            ticket_full = tgt_command + steamtime + padding
            if pkt_version == "b2003":
                client_socket.send(b"\x02")
                client_socket.close()
            else:
                client_socket.send(ticket_full)
                client_socket.close()
            return
        else:
            password_digest, password_salt = self.database.get_userpass_stuff(username)
            # print(password_digest, password_salt)
            client_socket.send(password_salt)

            command = client_socket.recv_withlen()

            IV = command[0:16]
            # print(binascii.b2a_hex(IV))
            encrypted = command[20:36]
            # print(binascii.b2a_hex(encrypted))
            decodedmessage = binascii.b2a_hex(encryption.aes_decrypt(password_digest[0:16], IV, encrypted))
            self.log.debug(f"{clientid}Authentication package: {decodedmessage}")

            if not decodedmessage.endswith(b"04040404"):
                self.log.info(f"{clientid}Incorrect password entered for: {username}")

                if globalvars.steamui_ver < 24:
                    tgt_command = b"\x00"
                else:
                    tgt_command = b"\x02"  # Incorrect password

                steamtime = utilities.time.unixtime_to_steamtime(time.time())
                clock_skew_tolerance = b"\x00\xd2\x49\x6b\x00\x00\x00\x00"
                authenticate = tgt_command + steamtime + clock_skew_tolerance
                client_socket.send(authenticate)
                client_socket.close()
                return

            userregistry_blob = self.database.get_userregistry_dict(username, pkt_version, client_address[0])

            if not isinstance(userregistry_blob, dict):
                if userregistry_blob == 2:
                    self.log.error(f"{clientid}[Login] Error, Multiple rows with the same username!")
                    client_socket.send(b"\x06")
                    return

            blob = blobs.blob_serialize(userregistry_blob)

            # pprint.pprint(blob)
            # pprint.pprint(userregistry_blob, width=250)
            bloblen = len(blob)
            self.log.debug(f"Blob length: {str(bloblen)}")
            blob_encrypted = encryption.aes_encrypt(self.innerkey, self.innerIV, blob)
            blob_encrypted = struct.pack("<L", bloblen) + self.innerIV + blob_encrypted
            blob_signature = encryption.sign_message(self.innerkey, blob_encrypted)
            blob_encrypted_len = 10 + len(blob_encrypted) + 20
            blob_encrypted = struct.pack(">L", blob_encrypted_len) + b"\x01\x45" + struct.pack("<LL", blob_encrypted_len, 0) + blob_encrypted + blob_signature
            currtime = time.time()

            outerIV = binascii.a2b_hex("92183129534234231231312123123353")

            steamUniverse = struct.pack(">H", int(self.config["universe"]))

            steamid = steamUniverse + userregistry_blob[b'\x06\x00\x00\x00'][username_bytes][b'\x01\x00\x00\x00']

            matches, count = self.dirmanager.find_ip_address("ValidationSRV")
            if count > 0:
                wan_ip, lan_ip, port = matches[0]
                if self.islan:
                    bin_ip = utils.encodeIP((lan_ip.decode('latin-1'), port))
                else:
                    bin_ip = utils.encodeIP((wan_ip.decode('latin-1'), port))
            else:
                if self.islan:
                    bin_ip = utils.encodeIP((self.config["server_ip"], self.config["validation_port"]))
                else:
                    bin_ip = utils.encodeIP((self.config["public_ip"], self.config["validation_port"]))
            print(f"validation server: {client_socket.inet_ntoa(bin_ip[:-2])}:{struct.unpack('<H', bin_ip[4:])}")
            servers = bin_ip + bin_ip

            currtime = int(currtime)
            creation_time = utilities.time.unixtime_to_steamtime(currtime)
            ticket_expiration_time = utilities.time.unixtime_to_steamtime(currtime + (utilities.time.get_expiration_seconds()))
            subheader = self.innerkey \
                        + steamid \
                        + servers \
                        + creation_time \
                        + ticket_expiration_time
            subheader_encrypted = encryption.aes_encrypt(password_digest[0:16], outerIV, subheader)
            subhead_decr_len = b"\x00\x36"
            subhead_encr_len = b"\x00\x40"
            print(f"Subheader un-encrypted: {subheader}\n encrypted: {subheader_encrypted}")
            if globalvars.tgt_version == "1":  # nullData1 Beta 2003, retail 2003, 2004
                subheader_encrypted = b"\x00\x01" + outerIV + subhead_decr_len + subhead_encr_len + subheader_encrypted  # TTicket_SubHeader (EncrData)
                self.log.debug(f"{clientid}TGT Version: 1")  # v1/v2 Steam

            elif globalvars.tgt_version == "2": # 2007+?
                subheader_encrypted = b"\x00\x02" + outerIV + subhead_decr_len + subhead_encr_len + subheader_encrypted
                self.log.debug(f"{clientid}TGT Version: 2")  # v3 Steam

            else:
                subheader_encrypted = b"\x00\x02" + outerIV + subhead_decr_len + subhead_encr_len + subheader_encrypted
                self.log.debug(f"{clientid}TGT Version: 2")  # Assume v3 Steam

            clientIP = real_socket.inet_aton(client_address[0])
            publicIP = clientIP[::-1]

            # subcommand3 = b"\x00\x00\x00\x00"
            data1_len_str = b"\x00\x80"
            # empty1 = (b"\x00" * 0x80) #TTicketHeader unknown encrypted
            data1 = username_bytes \
                    + username_bytes \
                    + b"\x00\x01" \
                    + publicIP \
                    + clientIP \
                    + servers \
                    + password_digest[0:16] \
                    + creation_time \
                    + ticket_expiration_time
            # Calculate data1_len_empty as an integer
            data1_len_empty = int(0x80 * 2) - len(binascii.b2a_hex(data1))
            # Rest of the code remains the same
            data1_full = data1 + (b"\x00" * (data1_len_empty // 2))
            empty3 = (b"\x00" * 0x80)  # unknown encrypted - RSA sig?
            username_len = len(username)
            # username_len_packed = struct.pack(">H", 50 + username_len)
            accountId = userregistry_blob[b'\x06\x00\x00\x00'][username_bytes][b'\x01\x00\x00\x00'][0:16]  # SteamID
            data2 = struct.pack(">L", len(username))

            if globalvars.tgt_version == "1": # beta 2003, retail 2003, 2004+
                tgtversion = b"\x00\x01"  # for TGT v1
                subcommand2 = b""  # missing for TGT v1
                empty2_dec_len = b"\x00\x42"
                empty2_enc_len = b"\x00\x50"
                # empty2 = (b"\x00" * 0x50) #160 chars long (80 int bytes) unknown encrypted
                data2_len_empty = int(0x50 * 2) - len(binascii.b2a_hex(data2))
                data2_full = data2 + (b"\x00" * (data2_len_empty // 2))

            else:
                tgtversion = b"\x00\x02"  # assume TGT v2
                subcommand2 = b"\x00\x10"  # steamID+clientIPaddress TGT v2 only
                subcommand2 = subcommand2 + accountId + clientIP
                empty2_dec_len = b"\x00\x52"
                empty2_enc_len = b"\x00\x60"
                # empty2 = (b"\x00" * 0x60) #192 chars long (96 int bytes) unknown encrypted
                data2_len_empty = int(0x60 * 2) - len(binascii.b2a_hex(data2))
                data2_full = data2 + (b"\x00" * (data2_len_empty // 2))

            # empty2 = username + empty2_empty[(len(username)):]
            real_ticket = tgtversion \
                          + data1_len_str \
                          + data1_full \
                          + IV \
                          + empty2_dec_len \
                          + empty2_enc_len \
                          + data2_full \
                          + subcommand2 \
                          + empty3
            real_ticket_len = struct.pack(">H", len(real_ticket))  # TicketLen
            # ticket = subheader_encrypted + unknown_part + blob_encrypted
            ticket = subheader_encrypted \
                     + real_ticket_len \
                     + real_ticket \
                     + blob_encrypted

            ticket_signed = ticket + encryption.sign_message(self.innerkey, ticket)
            # TODO add ticket information to authenticationticketrecord table Use authdb method check_or_set_auth_ticket()

            if globalvars.steamui_ver < 24:
                tgt_command = b"\x01"  # Authenticated # AuthenticateAndRequestTGT command
            else:
                # tgt_command = b"\x03" #Clock-skew too far out
                tgt_command = b"\x00"

            steamtime = utilities.time.unixtime_to_steamtime(time.time())
            clock_skew_tolerance = b"\x00\xd2\x49\x6b\x00\x00\x00\x00"
            authenticate = tgt_command + steamtime + clock_skew_tolerance
            writeAccountInformation = struct.pack(">L", len(ticket_signed)) + ticket_signed  # FULL TICKET (steamticket.bin)
            client_socket.send(authenticate + writeAccountInformation)  # print(bloblen)

    def send_email(self, username_str, client_address, email_type="newuser"):
        if isinstance(username_str, bytes):
            username_str = username_str.decode('latin-1')
        if self.database.check_username_exists(username_str):
            validation_dict = self.database.insert_email_verification(username_str)
        else:
            return
        if email_type == "newuser":
            # Send Email Verification Code and Password Recoveru Qiuestion
            sendmail.send_new_user_email(validation_dict['email'], client_address, username_str, validation_dict['verification_code'])
        elif email_type == "verify":
            sendmail.send_verification_email(validation_dict['email'], validation_dict['verification_code'], client_address, username_str)
        else:
            self.log.error(f"Unknown email type selected {email_type} for username {username_str}")

    def send_change_info_validation_email(self, username_str, client_address):
        if isinstance(username_str, bytes):
            username_str = username_str.decode('latin-1')

        # Send Email Verification Code and Password Recovery Question
        if self.database.check_username_exists(username_str):
            validation_dict = self.database.insert_reset_password_validation(username_str)
            print(f"[Password Reset] {username_str} Validation Code: {validation_dict['verification_code']}")
            sendmail.send_reset_password_email(validation_dict['email'],
                                           validation_dict['verification_code'],
                                           validation_dict['secretquestion'],
                                           client_address,
                                           username_str)

    def unsubscribe(self, client_address, client_socket, clientid, command, pkt_version):
        ticket_full = binascii.b2a_hex(command)
        command = ticket_full[0:2]
        ticket_len = ticket_full[2:6]
        tgt_ver = ticket_full[6:10]
        data1_len = ticket_full[10:14]
        data1_len = int(data1_len, 16) * 2
        userIV = binascii.a2b_hex(ticket_full[14 + data1_len:14 + data1_len + 32])
        username_len = ticket_full[314:318]
        username = binascii.a2b_hex(ticket_full[14:14 + (int(username_len, 16) * 2)]).decode('latin-1')
        ticket_len = int(ticket_len, 16) * 2
        ticket = ticket_full[2:ticket_len + 2]
        postticketdata = ticket_full[2 + ticket_len + 4:]
        key = self.innerkey
        iv = binascii.a2b_hex(postticketdata[0:32])
        encdata_len = int(postticketdata[36:40], 16) * 2
        encdata = postticketdata[40:40 + encdata_len]
        decodedmessage = binascii.b2a_hex(encryption.aes_decrypt(key, iv, binascii.a2b_hex(encdata)))
        decodedmessage = binascii.a2b_hex(decodedmessage)
        username_len_new = struct.unpack("<H", decodedmessage[0:2])
        username_len_new = (2 + username_len_new[0]) * 2
        header = username_len_new + 8
        padding_byte = decodedmessage[-1:]
        padding_int, = struct.unpack(">B", padding_byte)
        sub_id, = struct.unpack("<L", decodedmessage[header:-padding_int])
        self.log.info(f"{clientid}Unsubscribe from package " + str(sub_id))
        # ------------------------------------------------------------------
        if self.database.unsubscribe(username, sub_id):
            execdict = self.database.get_userregistry_dict(username, pkt_version, client_address[0])

            def without_keys(d, keys):
                return {x:d[x] for x in d if x not in keys}

            secretkey2 = {b'\x0f\x00\x00\x00'}
            execdict_new2 = without_keys(execdict, secretkey2)
            # pprint.pprint(execdict_new2)
            blob = blobs.blob_serialize(execdict_new2)
            bloblen = len(blob)
            self.log.debug(f"Blob length: {str(bloblen)}")
            blob_encrypted = encryption.aes_encrypt(self.innerkey, self.innerIV, blob)
            blob_encrypted = struct.pack("<L", bloblen) + self.innerIV + blob_encrypted
            blob_signature = encryption.sign_message(self.innerkey, blob_encrypted)
            blob_encrypted_len = 10 + len(blob_encrypted) + 20
            blob_encrypted = struct.pack(">L", blob_encrypted_len) + b"\x01\x45" + struct.pack("<LL", blob_encrypted_len, 0) + blob_encrypted + blob_signature
            client_socket.send(blob_encrypted)
        else:
            self.log.error(f"{clientid}Database Error During Unsubscribe!")
            client_socket.send(b'\x00')
            client_socket.close()