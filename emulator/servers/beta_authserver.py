import binascii
import copy
import hashlib
import hmac
import io
import os
import socket as real_socket
import zlib
import struct

import ipcalc
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Hash import SHA1
from Crypto.Signature import pkcs1_15

import globalvars
import utilities.time
from utilities import blobs, encryption
from utilities.database.beta1_authdb import *
from utilities.cdr_manipulator import read_secondblob
from utilities.networkhandler import TCPNetworkHandler


class Beta1_AuthServer(TCPNetworkHandler):
    def __init__(self, port, config):
        self.server_type = "Beta1_AuthServer"
        # Create an instance of NetworkHandler
        super(Beta1_AuthServer, self).__init__(config, port, self.server_type)
        self.config = config
        self.dict_blob = (
                read_secondblob("files/secondblob.py")
                if os.path.isfile("files/secondblob.py")
                else read_secondblob("files/secondblob.bin")
        )

        self.log = logging.getLogger("B1AUTHSRV")
        # self.blob, self.dict_blob = load_secondblob()

    def handle_client(self, client_socket, client_address):
        userdb = beta1_dbdriver(self.config)

        clientid = str(client_address) + ": "

        self.log.info(f"{clientid}Connected to Beta1 Authentication Server")

        if str(client_address[0]) in ipcalc.Network(str(globalvars.server_net)):
            islan = True
        else:
            islan = False

        msg = client_socket.recv(1)

        if msg[0] != 1:
            self.log.info(f"{clientid} Sent Unexpected First Byte")
            client_socket.send(b"\x00")
            return

        msg = client_socket.recv_all(4)
        version, = struct.unpack(">I", msg)
        if version == 0:
            recv_func = client_socket.recv_withlen_short
        elif version == 1:
            recv_func = client_socket.recv_withlen
        else:
            self.log.info(f"{clientid}Using Unrecognized version! {version}")
            client_socket.close()

        self.log.info(f"{clientid}Using Version: {version}")

        msg = client_socket.recv_all(4)
        client_internal_ip = msg[::-1]
        client_external_ip = real_socket.inet_aton(client_address[0])
        self.log.debug(f"{clientid}Internal IP: {client_internal_ip} Exernal IP: {client_external_ip}")
        client_socket.send(b"\x01" + client_external_ip[::-1])

        msg = recv_func()
        cmd = msg[0]
        self.log.debug(f"{clientid}Client Command: {cmd} packet: {binascii.b2a_hex(msg)}")

        if cmd == 0:
            self.log.info(f"{clientid}Recieved CCDB request, sending version {version}")

            if version == 0:
                client_socket.send(struct.pack("<IIIIIIII", 0, 6, 0, 0, 1, 0, 0, 0))
            elif version == 1:
                client_socket.send(struct.pack("<IIIIIIII", 0, 6, 1, 0, 1, 1, 0, 0))

            msg = client_socket.recv_all(1)
            client_socket.close()

        elif cmd == 1:  # Create User
            self.log.info(f"{clientid}Recieved Create User Request")
            data = bytes.fromhex("30819d300d06092a864886f70d010101050003818b0030818702818100") + encryption.network_key.n.to_bytes(128, byteorder = "big") + bytes.fromhex("020111")

            client_socket.send_withlen_short(data)

            sig = pkcs1_15.new(encryption.network_key).sign(SHA1.new(data))

            client_socket.send_withlen_short(sig)

            msg = recv_func()

            bio = io.BytesIO(msg)

            size, = struct.unpack(">H", bio.read(2))
            encr_key = bio.read(size)

            sessionkey = PKCS1_OAEP.new(encryption.network_key).decrypt(encr_key)
            # log.debug("session key", sessionkey.hex())

            if encryption.validate_mac(msg, sessionkey):
                self.log.info(f"{clientid}Message Validated OK")

            size, = struct.unpack(">I", bio.read(4))
            ctext = bio.read(size)
            ptext = encryption.beta_decrypt_message_v1(ctext[10:], sessionkey)
            # self.log.debug(f"{clientid} Decrypted Text: {ptext.hex()}")

            # pprint.pprint(blobs.blob_unserialize(ptext))

            res = userdb.create_user(ptext, version)
            if res:
                client_socket.send(b"\x01")
            else:
                client_socket.send(b"\x00")
        # login
        elif cmd == 2:
            self.log.info(f"{clientid}Recieved Login Request")
            bio = io.BytesIO(msg[1:])

            sz1, = struct.unpack(">H", bio.read(2))
            username1 = bio.read(sz1)

            sz2, = struct.unpack(">H", bio.read(2))
            username2 = bio.read(sz2)

            remainder = bio.read()
            if len(username1) != sz1 or len(username2) != sz2 or username1 != username2 or len(remainder) != 0:
                self.log.info(f"{clientid}Username1 and Username2 Do Not Match, Killing Connection!")
                client_socket.send(b"\x00")
                client_socket.close()
                return

            self.log.info(f"{clientid}Attempting Login With Username: {username1}")

            salt, _hash = userdb.get_salt_and_hash(username1)
            if salt is None:
                # TODO proper error to client
                self.log.info(f"{clientid}Incorrect Password!")
                client_socket.send(b"\x00")
                client_socket.close()
                return
            key = _hash[0:16]

            client_socket.send(salt)

            if version == 0:
                msg = client_socket.recv_withlen_short()
            elif version == 1:
                msg = client_socket.recv_withlen()

            ptext = encryption.decrypt_message(msg, key)
            # print(f"decrypted text: {ptext}")

            if len(ptext) != 12:
                self.log.info(f"{clientid}Incorrect Plaintext Size!")
                client_socket.send(b"\x00")
                client_socket.close()
                return

            if ptext[8:12] != client_internal_ip:
                self.log.info(f"{clientid}Internal IP Does not match, Bad Decryption!")
                client_socket.send(b"\x00")
                client_socket.close()
                return

            controlhash = hashlib.sha1(client_external_ip + client_internal_ip).digest()
            client_time = utilities.time.steamtime_to_unixtime(encryption.binaryxor(ptext[0:8], controlhash[0:8]))
            skew = int(time.time() - client_time)
            if abs(skew) >= 3600:
                self.log.info(f"{clientid}Client Clock Skew Too Large! Disconnecting")
                client_socket.send(b"\x00")
                client_socket.close()
                return

            userblob = userdb.get_user_blob(username1, self.dict_blob, version)
            binblob = blobs.blob_serialize(userblob)
            # just sending a plaintext blob for now

            blob_encrypted = struct.pack(">I", len(binblob)) + binblob
            currtime = int(time.time())

            innerkey = bytes.fromhex("10231230211281239191238542314233")
            times = utilities.time.unixtime_to_steamtime(currtime) + utilities.time.unixtime_to_steamtime(currtime + (60 * 60 * 24 * 28))
            if version == 1:
                steamid = bytes.fromhex("0000" + "00000000" + userblob[b"\x06\x00\x00\x00"][username1][b"\x01\x00\x00\x00"][0:4].hex())

                if islan:
                    bin_ip = utils.encodeIP((self.config["server_ip"], int(self.config["validation_port"])))
                else:
                    bin_ip = utils.encodeIP((self.config["public_ip"], int(self.config["validation_port"])))

                servers = bin_ip + bin_ip  # bytes.fromhex("111213149a69151617189a69")
                times = utilities.time.unixtime_to_steamtime(currtime) + utilities.time.unixtime_to_steamtime(currtime + (60 * 60 * 24 * 28))

                subheader = innerkey + steamid + servers + times
                subheader_encrypted = b"\x00\x00" + encryption.beta_encrypt_message(subheader, key)
            else:
                subheader = innerkey + times

                subheader_encrypted = b"\x00\x00" + encryption.beta_encrypt_message(subheader, key)

            data1_len_str = b"\x00\x80" + (b"\xff" * 0x80)

            ticket = subheader_encrypted + data1_len_str + blob_encrypted

            ticket_signed = ticket + hmac.digest(innerkey, ticket, hashlib.sha1)

            tgt_command = b"\x01"  # AuthenticateAndRequestTGT command
            steamtime = utilities.time.unixtime_to_steamtime(time.time())
            ticket_full = (
                    tgt_command
                    + steamtime
                    + b"\x00\xd2\x49\x6b\x00\x00\x00\x00"
                    + struct.pack(">I", len(ticket_signed))
                    + ticket_signed
            )
            self.log.info(f"{clientid}Sending Version {version} Ticket to client")
            client_socket.send(ticket_full)

        elif cmd in (3, 4, 5, 6, 9, 10):
            innerkey = bytes.fromhex("10231230211281239191238542314233")

            if not encryption.validate_mac(msg[1:], innerkey):
                self.log.info(f"{clientid}Mac Validation Failed")
                client_socket.send(b"\x00")
                client_socket.close()
                return

            bio = io.BytesIO(msg[1:])

            ticketsize, = struct.unpack(">H", bio.read(2))
            ticket = bio.read(ticketsize)

            ptext = encryption.decrypt_message(bio.read()[:-20], innerkey)

            # print("ptext", ptext.hex())
            # print("ptext", repr(ptext))

            bio = io.BytesIO(ptext)

            sz1, = struct.unpack("<H", bio.read(2))
            username1 = bio.read(sz1)

            sz2, = struct.unpack("<H", bio.read(2))
            username2 = bio.read(sz2)

            if len(username1) != sz1 or len(username2) != sz2 or username1 != username2:
                self.log.info(f"{clientid}Username1 and Username2 Do not Match!")
                client_socket.send(b"\x00")
                client_socket.close()
                return

            # print("usernames", repr(username1))

            controlhash = hashlib.sha1(client_external_ip + client_internal_ip).digest()
            client_time = utilities.time.steamtime_to_unixtime(encryption.binaryxor(bio.read(8), controlhash[0:8]))
            skew = int(time.time() - client_time)

            # print("time skew", skew)

            # delete account
            if cmd == 3:
                print(f"User requested to delete account: {username1}")
                result = userdb.delete_user(username1)
                if result:
                    userdb.remove_subscriptions_by_username(username1)
                client_socket.send(b"\x01")

            # logout
            elif cmd == 4:
                self.log.info(f"{clientid}{username1} Logged off")
                client_socket.send(b"\x01")
                # client_socket.close()
                return

            # subscribe to sub
            elif cmd == 5:
                self.log.info(f"{clientid}Subscription Request Recieved")
                binsubid = bio.read()
                if len(binsubid) != 4:
                    self.log.info(f"{clientid}SubID Incorrect length (> 4 bytes) {binsubid}")
                    client_socket.send(b"\x00")
                    client_socket.close()
                    return

                subid, = struct.unpack("<I", binsubid)

                if binsubid not in self.dict_blob[b"\x02\x00\x00\x00"]:
                    self.log.info(f"{clientid}Tried Adding Subscription Which Does Not Exist: {subid}")
                    client_socket.send(b"\x00")
                    client_socket.close()
                    return

                userdb.edit_subscription(username1, subid)

                userblob = userdb.get_user_blob(username1, self.dict_blob, version)
                binblob = blobs.blob_serialize(userblob)
                self.log.info(f"{clientid}Successfully Subscribed to SubID: {subid}")
                client_socket.send(struct.pack(">I", len(binblob)) + binblob)

            # unsubscribe to sub
            elif cmd == 6:
                self.log.info(f"{clientid}Unsubscribe Request Recieved")
                binsubid = bio.read()
                if len(binsubid) != 4:
                    self.log.info(f"{clientid}SubID Incorrect length (> 4 bytes) {binsubid}")
                    client_socket.send(b"\x00")
                    client_socket.close()
                    return

                subid, = struct.unpack("<I", binsubid)

                if binsubid not in self.dict_blob[b"\x02\x00\x00\x00"]:
                    self.log.info(f"{clientid}Tried UnSubscribing Using a SubID Which Does Not Exist: {subid}")
                    client_socket.send(b"\x00")
                    client_socket.close()
                    return

                userdb.edit_subscription(username1, subid, remove_sub = True)

                userblob = userdb.get_user_blob(username1, self.dict_blob, version)
                binblob = blobs.blob_serialize(userblob)
                self.log.info(f"{clientid}Successfully Unsubscribed from {subid}")
                client_socket.send(struct.pack(">I", len(binblob)) + binblob)

            # refresh info
            elif cmd == 9:
                self.log.info(f"{clientid}Recieved Refresh User Blob")
                try:
                    userblob = userdb.get_user_blob(username1, self.dict_blob, version)
                    binblob = blobs.blob_serialize(userblob)

                    client_socket.send(struct.pack(">I", len(binblob)) + binblob)
                except:
                    client_socket.send(b"\x00")
                    client_socket.close()
                    return

            # Content Ticket
            elif cmd == 10:
                self.log.info(f"{clientid}Recieved Content Ticket Request")

                currtime = time.time()

                client_ticket = b"\x69" * 0x10  # key used for MAC signature
                client_ticket += utilities.time.unixtime_to_steamtime(currtime)  # TicketCreationTime
                client_ticket += utilities.time.unixtime_to_steamtime(currtime + 86400)  # TicketValidUntilTime

                if islan:
                    client_ticket += utils.encodeIP((self.config["server_ip"], int(self.config["content_server_port"])))
                else:
                    client_ticket += utils.encodeIP((self.config["public_ip"], int(self.config["content_server_port"])))

                server_ticket = b"\x55" * 0x80  # ticket must be between 100 and 1000 bytes

                ticket = b"\x00\x00" + encryption.beta_encrypt_message(client_ticket, innerkey)
                ticket += struct.pack(">H", len(server_ticket)) + server_ticket

                ticket_signed = ticket + hmac.digest(client_ticket[0:16], ticket, hashlib.sha1)

                # for feb2002 the ticket size is encoded as u16
                if version == 1:
                    client_socket.send(b"\x00\x01" + struct.pack(">I", len(ticket_signed)) + ticket_signed)
                else:
                    client_socket.send(b"\x00\x01" + struct.pack(">H", len(ticket_signed)) + ticket_signed)

        # Client Registry Request
        elif msg[0] == 11:
            self.log.info(f"{clientid}Recieved Client Registry Request")
            binblob = blobs.blob_serialize(self.dict_blob)

            binblob = struct.pack(">I", len(binblob)) + binblob

            client_socket.send(binblob)
        # auto update
        elif msg[0] == 13:
            self.log.warning(f"{clientid}Requested FTP URL")

            client_socket.send_withlen(globalvars.server_ip_b + b"/0/Steam.exe")
        else:
            self.log.info(f"{clientid}Unknown Subcommand Received: {msg[0]}")
            self.log.debug(f"{clientid}{msg}")
            client_socket.send(b"\x00")