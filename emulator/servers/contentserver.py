import binascii
import hashlib
import hmac
import io
import os
import os.path
import pickle
import threading
import time
import zlib
import struct

import ipcalc
from Crypto.Hash import SHA
import random

import globalvars
import utils
from listmanagers.contentlistmanager import manager
from listmanagers.contentserverlist_utilities import heartbeat_thread, send_removal
from servers.managers.latency_manager import latencychecker
from utilities import cdr_manipulator, encryption, steam2_sdk_utils, storages as stmstorages
from utilities.checksums import Checksum2, Checksum3, Checksum4, SDKChecksum
from utilities.manifests import *
from utilities.networkhandler import TCPNetworkHandler
from utilities.ticket_utils import Steam2Ticket
import threading
import time  # Required for time.sleep()

# Function to run the latencychecker


app_list = []
csConnectionCount = 0


class contentserver(TCPNetworkHandler):

    def __init__(self, port, config):
        global app_list
        self.server_type = "ContentServer"
        super(contentserver, self).__init__(config, port, self.server_type)  # Create an instance of NetworkHandler

        if globalvars.public_ip == "0.0.0.0":
            server_ip = globalvars.server_ip_b
        else:
            server_ip = globalvars.public_ip_b

        self.config = config
        self.secret_identifier = utils.generate_unique_server_id()
        self.key = None
        self.applist = self.parse_manifest_files()

        self.contentserver_info = {
                'server_id':self.secret_identifier,
                'wan_ip':   server_ip,
                'lan_ip':   globalvars.server_ip_b,
                'port':     int(port),
                'region':   globalvars.cs_region.encode('latin-1'),
                'cellid':   globalvars.cellid,
        }

        def run_latency_checker():
            checker = latencychecker(int(self.config["ping_server_port"]))
            checker.start()

        # Start latency checking thread for improved load balancing and better server selection for client
        latency_checker_thread = threading.Thread(target = run_latency_checker)
        latency_checker_thread.daemon = True
        latency_checker_thread.start()

        if not globalvars.aio_server:
            self.thread = threading.Thread(target = heartbeat_thread, args = (self,))
            self.thread.daemon = True
            self.thread.start()
        else:
            manager.add_contentserver_info(self.secret_identifier, server_ip, globalvars.server_ip, int(port), globalvars.cs_region, app_list, globalvars.cellid, True, False)

    def cleanup(self):
        """Content Server specific cleanup routine"""
        self.log.info(f"Cleaning up Content Server on port {self.port}")

        if not globalvars.aio_server:
            send_removal(self.secret_identifier)
        super().cleanup()

    def handle_client(self, client_socket, client_address):
        global csConnectionCount

        if str(client_address[0]) in ipcalc.Network(str(globalvars.server_net)):
            islan = True
            suffix = "_lan"
        else:
            islan = False
            suffix = "_wan"

        clientid = str(client_address) + ": "
        self.log.info(f"{clientid}Connected to Content Server")

        msg = client_socket.recv(4)
        csConnectionCount += 1

        self.log.debug(f"{clientid}Content server version: {msg}")

        if len(msg) == 0:
            self.log.info(f"{clientid}Got simple handshake. Closing connection.")
        # BETA 1 VERSION 0 & BETA1 VERSION 1
        elif msg in [b"\x00\x00\x00\x00", b"\x00\x00\x00\x01"]:
            self.log.info(f"{clientid}Storage mode entered")

            storagesopen = 0
            storages = {}

            client_socket.send(b"\x01")  # this should just be the handshake

            # FIXME THIS IS FOR BETA1 V1
            """currtime = time.time()

            client_ticket = b"\x69" * 0x10  # key used for MAC signature
            client_ticket += utils.unixtime_to_steamtime(currtime)  # TicketCreationTime
            client_ticket += utils.unixtime_to_steamtime(currtime + 86400)  # TicketValidUntilTime

            if islan == True:
                client_ticket += utils.encodeIP((self.config["server_ip"], int(self.config["content_server_port"])))
            else:
                client_ticket += utils.encodeIP((self.config["public_ip"], int(self.config["content_server_port"])))

            server_ticket = b"\x55" * 0x80  # ticket must be between 100 and 1000 bytes
            innerkey = bytes.fromhex("10231230211281239191238542314233")
            ticket = b"\x00\x00" + encryption.beta_encrypt_message(client_ticket, innerkey)
            ticket += struct.pack(">H", len(server_ticket)) + server_ticket

            ticket_signed = ticket + hmac.digest(client_ticket[0:16], ticket, hashlib.sha1)


            server_socket.send(b"\x00\x01" + struct.pack(">I", len(ticket_signed)) + ticket_signed)"""

            if msg == b"\x00\x00\x00\x01":
                command = client_socket.recv_withlen()
            else:
                command = client_socket.recv_withlen_short()

            if command[0:1] == b"\x00":
                (connid, messageid, app, version) = struct.unpack(">IIII", command[1:17])

                (app, version) = struct.unpack(">II", command[1:9])
                self.log.debug(f"{clientid}appid: {app}, verid: {version}")

                connid |= 0x80000000
                key = b"\x69" * 0x10
                if encryption.validate_mac(command[9:], key):
                    self.log.debug(clientid + repr(encryption.validate_mac(command[9:], key)))

                # TODO BEN, DO PROPER TICKET VALIDATION
                # bio = io.BytesIO(command[9:])

                # ticketsize, = struct.unpack(">H", bio.read(2))
                # ticket = bio.read(ticketsize)

                # ptext = encryption.decrypt_message(bio.read()[:-20], key)
                self.log.info(f"{clientid}Opening application {app} {version}")
                try:
                    s = stmstorages.Storage(app, self.config["betastoragedir"] + "beta1/", version)
                except Exception:
                    self.log.error("Application not installed! %d %d" % (app, version))

                    # reply = struct.pack(">LLc", connid, messageid, b"\x01")
                    reply = struct.pack(">B", 0)
                    client_socket.send(reply)
                    return

                storageid = storagesopen
                storagesopen += 1

                storages[storageid] = s
                storages[storageid].app = app
                storages[storageid].version = version

                if os.path.isfile(self.config["betamanifestdir"] + "beta1/" + str(app) + "_" + str(version) + ".manifest"):
                    f = open(self.config["betamanifestdir"] + "beta1/" + str(app) + "_" + str(version) + ".manifest", "rb")
                    self.log.info(f"{clientid}{app}_{version} is a beta depot")
                else:
                    self.log.error(f"Manifest not found for {app} {version} ")
                    # reply = struct.pack(">LLc", connid, messageid, b"\x01")
                    client_socket.send(b"\x00")
                    return
                manifest = f.read()
                f.close()

                manifest_appid = struct.unpack('<L', manifest[4:8])[0]
                manifest_verid = struct.unpack('<L', manifest[8:12])[0]
                self.log.debug(f"{clientid}Manifest ID: {manifest_appid} Version: {manifest_verid}")
                if (int(manifest_appid) != int(app)) or (int(manifest_verid) != int(version)):
                    self.log.error(f"Manifest doesn't match requested file: ({app}, {version}) ({manifest_appid}, {manifest_verid})")

                    # reply = struct.pack(">LLc", connid, messageid, b"\x01")
                    client_socket.send(b"\x00")
                    return

                globalvars.converting = "0"

                fingerprint = manifest[0x30:0x34]
                oldchecksum = manifest[0x34:0x38]
                manifest = manifest[:0x30] + b"\x00" * 8 + manifest[0x38:]
                checksum = struct.pack("<I", zlib.adler32(manifest, 0))
                manifest = manifest[:0x30] + fingerprint + checksum + manifest[0x38:]

                self.log.debug(f"Checksum fixed from  {binascii.b2a_hex(oldchecksum)}  to {binascii.b2a_hex(checksum)}")

                storages[storageid].manifest = manifest

                checksum = struct.unpack("<L", manifest[0x30:0x34])[0]  # FIXED, possible bug source

                # reply = struct.pack(">LLcLL", connid, messageid, b"\x00", storageid, checksum)
                reply = b"\x66" + fingerprint[::-1] + b"\x01"

                client_socket.send(reply, False)

                index_file = self.config["betastoragedir"] + "beta1/" + str(app) + "_" + str(version) + ".index"
                dat_file = self.config["betastoragedir"] + "beta1/" + str(app) + "_" + str(version) + ".dat"
                # Load the index
                with open(index_file, 'rb') as f:
                    index_data = pickle.load(f)
                try:
                    dat_file_handle.close()
                except:
                    pass
                dat_file_handle = open(dat_file, 'rb')
                while True:
                    command = client_socket.recv(1, False)
                    if len(command) == 0:
                        self.log.info(f"{clientid}Disconnected from Content Server")
                        client_socket.close()
                        return

                    if command[0:1] == b"\x01":  # HANDSHAKE
                        client_socket.send(b"")
                        break

                    elif command[0:1] in [b"\x02", b"\x04"]:  # SEND MANIFEST AGAIN
                        self.log.info(f"{clientid}Sending manifest")
                        client_socket.send(struct.pack(">I", len(manifest)) + manifest, False)

                    elif command[0:1] == b"\x03":  # CLOSE STORAGE
                        (storageid, messageid) = struct.unpack(">xLL", command)
                        del storages[storageid]
                        reply = struct.pack(">LLc", storageid, messageid, b"\x00")
                        self.log.info(f"{clientid}Closing down storage {storageid}")
                        client_socket.send(reply)
                    elif command[0:1] == b"\x05":  # SEND DATA
                        msg = client_socket.recv(12, False)
                        fileid, offset, length = struct.unpack(">III", msg)
                        index_file = self.config["betastoragedir"] + "beta1/" + str(app) + "_" + str(version) + ".index"
                        dat_file = self.config["betastoragedir"] + "beta1/" + str(app) + "_" + str(version) + ".dat"
                        if islan:
                            filedata = utils.readfile_beta(fileid, offset, length, index_data, dat_file_handle, "internal")
                        else:
                            filedata = utils.readfile_beta(fileid, offset, length, index_data, dat_file_handle, "external")
                        # 0000001a 00000000 00010000
                        # 00000001 00000000 00001e72
                        client_socket.send(b"\x01" + struct.pack(">II", len(filedata), 0), False)
                        for i in range(0, len(filedata), 0x2000):
                            chunk = filedata[i:i + 0x2000]
                            client_socket.send(struct.pack(">I", len(chunk)) + chunk, False)
                        # server_socket.send(struct.pack(">I", len(filedata)) + filedata, False)
        # \X02 FOR 2003 BETA V2 CONTENT
        elif msg == b"\x00\x00\x00\x02":
            self.log.info(f"{clientid}Storage mode entered")

            storagesopen = 0
            storages = {}

            client_socket.send(b"\x01")  # this should just be the handshake

            while True:

                command = client_socket.recv_withlen()

                if command[0:1] == b"\x00":  # SEND MANIFEST AND PROCESS RESPONSE

                    (connid, messageid, app, version) = struct.unpack(">IIII", command[1:17])
                    # print(connid, messageid, app, version)
                    # print(app)
                    # print(version)

                    (app, version) = struct.unpack(">II", command[1:9])
                    self.log.debug(clientid + "appid: " + str(int(app)) + ", verid: " + str(int(version)))

                    # bio = io.BytesIO(msg[9:])

                    # ticketsize, = struct.unpack(">H", bio.read(2))
                    # ticket = bio.read(ticketsize)

                    connid |= 0x80000000
                    key = b"\x69" * 0x10
                    if encryption.validate_mac(command[9:], key):
                        self.log.debug(clientid + repr(encryption.validate_mac(command[9:], key)))
                    # TODO BEN, DO PROPER TICKET VALIDATION
                    # print(binascii.b2a_hex(signeddata))

                    # if hmac.new(key, signeddata[:-20], hashlib.sha1).digest() == signeddata[-20:]:
                    #    self.log.debug(clientid + "HMAC verified OK")
                    # else:
                    #    self.log.error(clientid + "BAD HMAC")
                    #    raise Exception("BAD HMAC")

                    # bio = io.BytesIO(msg[9:]) #NOT WORKING, UNKNOWN KEY
                    # print(bio)
                    # ticketsize, = struct.unpack(">H", bio.read(2))
                    # print(ticketsize)
                    # ticket = bio.read(ticketsize)
                    # print(binascii.b2a_hex(ticket))
                    # postticketdata = io.BytesIO(bio.read()[:-20])
                    # IV = postticketdata.read(16)
                    # print(len(IV))
                    # print(binascii.b2a_hex(IV))
                    # enclen = postticketdata.read(2)
                    # print(binascii.b2a_hex(enclen))
                    # print(struct.unpack(">H", enclen)[0])
                    # enctext = postticketdata.read(struct.unpack(">H", enclen)[0])
                    # print(binascii.b2a_hex(enctext))
                    # ptext = utils.aes_decrypt(key, IV, enctext)
                    # print(binascii.b2a_hex(ptext))

                    self.log.info(f"{clientid}Opening application %d %d" % (app, version))
                    # connid = pow(2,31) + connid

                    try:
                        s = stmstorages.Storage(app, self.config["storagedir"], version)
                    except Exception:
                        self.log.error(f"Application not installed! {app:d} {version:d}")

                        # reply = struct.pack(">LLc", connid, messageid, b"\x01")
                        reply = struct.pack(">B", 0)
                        client_socket.send(reply)

                        break

                    storageid = storagesopen
                    storagesopen += 1

                    storages[storageid] = s
                    storages[storageid].app = app
                    storages[storageid].version = version

                    if os.path.isfile(self.config["betamanifestdir"] + str(app) + "_" + str(version) + ".manifest"):
                        f = open(self.config["betamanifestdir"] + str(app) + "_" + str(version) + ".manifest", "rb")
                        self.log.info(f"{clientid}{app}_{version} is a beta depot")
                    else:
                        self.log.error(f"Manifest not found for {app} {version} ")
                        # reply = struct.pack(">LLc", connid, messageid, b"\x01")
                        client_socket.send(b"\x00")
                        break
                    manifest = f.read()
                    f.close()

                    manifest_appid = struct.unpack('<L', manifest[4:8])[0]
                    manifest_verid = struct.unpack('<L', manifest[8:12])[0]
                    self.log.debug(f"{clientid}Manifest ID: {manifest_appid} Version: {manifest_verid}")
                    if (int(manifest_appid) != int(app)) or (int(manifest_verid) != int(version)):
                        self.log.error(f"Manifest doesn't match requested file: ({app}, {version}) ({manifest_appid}, {manifest_verid})")

                        # reply = struct.pack(">LLc", connid, messageid, b"\x01")
                        client_socket.send(b"\x00")

                        break

                    globalvars.converting = "0"

                    fingerprint = manifest[0x30:0x34]
                    oldchecksum = manifest[0x34:0x38]
                    manifest = manifest[:0x30] + b"\x00" * 8 + manifest[0x38:]
                    checksum = struct.pack("<I", zlib.adler32(manifest, 0))
                    manifest = manifest[:0x30] + fingerprint + checksum + manifest[0x38:]

                    self.log.debug(f"Checksum fixed from  {binascii.b2a_hex(oldchecksum)}  to {binascii.b2a_hex(checksum)}")

                    storages[storageid].manifest = manifest

                    checksum = struct.unpack("<L", manifest[0x30:0x34])[0]  # FIXED, possible bug source

                    # reply = struct.pack(">LLcLL", connid, messageid, b"\x00", storageid, checksum)
                    reply = b"\xff" + fingerprint[::-1]

                    client_socket.send(reply, False)

                    index_file = self.config["betastoragedir"] + str(app) + "_" + str(version) + ".index"
                    dat_file = self.config["betastoragedir"] + str(app) + "_" + str(version) + ".dat"

                    # Load the index
                    with open(index_file, 'rb') as f:
                        index_data = pickle.load(f)

                    try:
                        dat_file_handle.close()
                    except:
                        pass

                    dat_file_handle = open(dat_file, 'rb')

                    while True:
                        command = client_socket.recv(1, False)

                        if len(command) == 0:
                            self.log.info(f"{clientid}Disconnected from Content Server")
                            client_socket.close()
                            return

                        if command[0:1] == b"\x02":  # SEND MANIFEST AGAIN

                            self.log.info(f"{clientid}Sending manifest")

                            # (storageid, messageid) = struct.unpack(">xLL", command)

                            # manifest = storages[storageid].manifest
                            # reply = struct.pack(">LLcL", storageid, messageid, b"\x00", len(manifest))
                            # reply = struct.pack(">BL", 0, len(manifest))
                            # print(binascii.b2a_hex(reply))

                            # server_socket.send(reply)

                            # reply = struct.pack(">LLL", storageid, messageid, len(manifest))
                            reply = struct.pack(">L", len(manifest))
                            # print(binascii.b2a_hex(reply))

                            # print(binascii.b2a_hex(manifest))

                            client_socket.send(b"\x01" + reply + manifest, False)

                        elif command[0:1] == b"\x01":  # HANDSHAKE

                            client_socket.send(b"")
                            break

                        elif command[0:1] == b"\x03":  # CLOSE STORAGE

                            (storageid, messageid) = struct.unpack(">xLL", command)

                            del storages[storageid]

                            reply = struct.pack(">LLc", storageid, messageid, b"\x00")

                            self.log.info(f"{clientid}Closing down storage {storageid}")

                            client_socket.send(reply)

                        elif command[0:1] == b"\x04":  # SEND MANIFEST

                            self.log.info(f"{clientid}Sending manifest")

                            # (storageid, messageid) = struct.unpack(">xLL", command)

                            # manifest = storages[storageid].manifest

                            # reply = struct.pack(">LLcL", storageid, messageid, b"\x00", len(manifest))
                            # reply = struct.pack(">BL", 0, len(manifest))
                            # print(binascii.b2a_hex(reply))

                            # server_socket.send(reply)

                            # reply = struct.pack(">LLL", storageid, messageid, len(manifest))
                            reply = struct.pack(">L", len(manifest))
                            # print(binascii.b2a_hex(reply))

                            # print(binascii.b2a_hex(manifest))

                            client_socket.send(b"\x01" + reply + manifest, False)

                        elif command[0:1] == b"\x05":  # SEND DATA
                            msg = client_socket.recv(12, False)
                            fileid, offset, length = struct.unpack(">III", msg)
                            index_file = self.config["betastoragedir"] + str(app) + "_" + str(version) + ".index"
                            dat_file = self.config["betastoragedir"] + str(app) + "_" + str(version) + ".dat"
                            if islan:
                                filedata = utils.readfile_beta(fileid, offset, length, index_data, dat_file_handle, "internal")
                            else:
                                filedata = utils.readfile_beta(fileid, offset, length, index_data, dat_file_handle, "external")
                            # 0000001a 00000000 00010000
                            # 00000001 00000000 00001e72
                            client_socket.send(b"\x01" + struct.pack(">II", len(filedata), 0), False)
                            for i in range(0, len(filedata), 0x2000):
                                chunk = filedata[i:i + 0x2000]
                                client_socket.send(struct.pack(">I", len(chunk)) + chunk, False)
                            # server_socket.send(struct.pack(">I", len(filedata)) + filedata, False)

                        elif command[0:1] == b"\x06":  # BANNER

                            if len(command) == 10:
                                client_socket.send(b"\x01")
                                break
                            else:
                                self.log.info(f"Banner message: {binascii.b2a_hex(command)}")

                                if self.config['enable_custom_banner'].lower() == "true":
                                    url = self.config['custom_banner_url']
                                else:
                                    url = ("http://" + globalvars.get_octal_ip(islan,False) + "/platform/banner/random.php")

                                reply = struct.pack(">H", len(url)) + url.encode("latin-1")

                                client_socket.send(reply)

                        elif command[0:1] == b"\x07":  # SEND DATA

                            (storageid, messageid, fileid, filepart, numparts, priority) = struct.unpack(">xLLLLLB", command)

                            (chunks, filemode) = storages[storageid].readchunks(fileid, filepart, numparts)

                            reply = struct.pack(">LLcLL", storageid, messageid, b"\x00", len(chunks), filemode)

                            client_socket.send(reply, False)

                            for chunk in chunks:
                                reply = struct.pack(">LLL", storageid, messageid, len(chunk))

                                client_socket.send(reply, False)

                                reply = struct.pack(">LLL", storageid, messageid, len(chunk))

                                client_socket.send(reply, False)

                                client_socket.send(chunk, False)

                        elif command[0:1] == b"\x08":  # INVALID

                            self.log.warning("08 - Invalid Command!")
                            client_socket.send(b"\x01")
                        else:

                            self.log.warning(f"{binascii.b2a_hex(command[0:1])} - Invalid Command!")
                            client_socket.send(b"\x01")

                            break

                    try:
                        dat_file_handle.close()
                    except:
                        pass
                else:

                    self.log.warning(f"{binascii.b2a_hex(command[0:1])} - Invalid Command!")
                    client_socket.send(b"\x01")

                    break
        # \X06 FOR 2003 RELEASE
        elif msg in [ b"\x00\x00\x00\x05", b"\x00\x00\x00\x06"]:

            self.log.info(f"{clientid}Storage mode entered")

            storagesopen = 0
            storages = {}

            client_socket.send(b"\x01")  # this should just be the handshake

            while True:

                command = client_socket.recv_withlen()
                #log.debug(f"{clientid}Content server command: {command[0:1]}")

                if command[0:1] == b"\x00":  # BANNER

                    if len(command) == 10:
                        client_socket.send(b"\x01")
                        break

                    self.log.info(f"Banner message: {binascii.b2a_hex(command)}")

                    if self.config['enable_custom_banner'].lower() == "true":
                        url = self.config['custom_banner_url']
                    else:
                        url = ("http://" + globalvars.get_octal_ip(islan, False) + "/platform/banner/random.php")

                    reply = struct.pack(">cH", b"\x01", len(url)) + url.encode()

                    client_socket.send(reply)

                elif command[0:1] == b"\x12":  # SEND MANIFEST
                    (connid, messageid, app, version) = struct.unpack(">IIII", command[1:17])
                    # print(connid, messageid, app, version)
                    # print(app)
                    # print(version)
                    connid |= 0x80000000
                    key = b"\x69" * 0x10
                    signeddata = command[17:]
                    # print(binascii.b2a_hex(signeddata))

                    if hmac.new(key, signeddata[:-20], hashlib.sha1).digest() == signeddata[-20:]:
                        self.log.debug(clientid + "HMAC verified OK")
                    else:
                        self.log.error(clientid + "BAD HMAC")
                        raise Exception("BAD HMAC")

                    bio = io.BytesIO(signeddata)
                    # print(bio)
                    ticketsize, = struct.unpack(">H", bio.read(2))
                    # print(ticketsize)
                    ticket = bio.read(ticketsize)
                    # print(binascii.b2a_hex(ticket))
                    postticketdata = bio.read()[:-20]
                    IV = postticketdata[0:16]
                    # print(len(IV))
                    # print(len(postticketdata))
                    ptext = encryption.aes_decrypt(key, IV, postticketdata[4:])
                    self.log.info(f"{clientid}Opening application {app}, {version}")
                    # connid = pow(2,31) + connid

                    try:
                        s = stmstorages.Storage(app, self.config["storagedir"], version)
                    except Exception:
                        self.log.error(f"Application not installed! {app}, {version}")

                        reply = struct.pack(">LLc", connid, messageid, b"\x01")
                        client_socket.send(reply)

                        break
                    storageid = storagesopen
                    storagesopen += 1

                    storages[storageid] = s
                    storages[storageid].app = app
                    storages[storageid].version = version

                    if os.path.isfile("files/cache/" + str(app) + "_" + str(version) + "/" + str(app) + "_" + str(version) + ".manifest"):
                        f = open("files/cache/" + str(app) + "_" + str(version) + "/" + str(app) + "_" + str(version) + ".manifest", "rb")
                        self.log.info(clientid + str(app) + "_" + str(version) + " is a cached depot")
                    elif os.path.isfile(self.config["manifestdir"] + str(app) + "_" + str(version) + ".v4.manifest"):
                        f = open(self.config["manifestdir"] + str(app) + "_" + str(version) + ".v4.manifest", "rb")
                        self.log.info(clientid + str(app) + "_" + str(version) + " is a v0.4 depot")
                    elif os.path.isfile(self.config["v4manifestdir"] + str(app) + "_" + str(version) + ".manifest"):
                        f = open(self.config["v4manifestdir"] + str(app) + "_" + str(version) + ".manifest", "rb")
                        self.log.info(clientid + str(app) + "_" + str(version) + " is a v0.4 depot")
                    elif os.path.isfile(self.config["manifestdir"] + str(app) + "_" + str(version) + ".v2.manifest"):
                        f = open(self.config["manifestdir"] + str(app) + "_" + str(version) + ".v2.manifest", "rb")
                        self.log.info(clientid + str(app) + "_" + str(version) + " is a v0.2 depot")
                    elif os.path.isfile(self.config["v2manifestdir"] + str(app) + "_" + str(version) + ".manifest"):
                        f = open(self.config["v2manifestdir"] + str(app) + "_" + str(version) + ".manifest", "rb")
                        self.log.info(clientid + str(app) + "_" + str(version) + " is a v0.2 depot")
                    elif os.path.isfile(self.config["manifestdir"] + str(app) + "_" + str(version) + ".v3e.manifest"):
                        f = open(self.config["manifestdir"] + str(app) + "_" + str(version) + ".v3e.manifest", "rb")
                        self.log.info(clientid + str(app) + "_" + str(version) + " is a v0.3 extra depot")
                    elif os.path.isfile(self.config["manifestdir"] + str(app) + "_" + str(version) + ".v3.manifest"):
                        f = open(self.config["manifestdir"] + str(app) + "_" + str(version) + ".v3.manifest", "rb")
                        self.log.info(clientid + str(app) + "_" + str(version) + " is a v0.3 depot")
                    elif os.path.isfile(self.config["manifestdir"] + str(app) + "_" + str(version) + ".manifest"):
                        f = open(self.config["manifestdir"] + str(app) + "_" + str(version) + ".manifest", "rb")
                        self.log.info(clientid + str(app) + "_" + str(version) + " is a v0.3 depot")
                    elif os.path.isdir(self.config["v3manifestdir2"]):
                        if os.path.isfile(self.config["v3manifestdir2"] + str(app) + "_" + str(version) + ".manifest"):
                            f = open(self.config["v3manifestdir2"] + str(app) + "_" + str(version) + ".manifest", "rb")
                            self.log.info(f"{clientid}{app}_{version} is a v0.3 extra depot")
                        else:
                            self.log.error(f"Manifest not found for {app} {version} ")
                            reply = struct.pack(">LLc", connid, messageid, b"\x01")
                            client_socket.send(reply)
                            break
                    else:
                        self.log.error(f"Manifest not found for {app} {version} ")
                        reply = struct.pack(">LLc", connid, messageid, b"\x01")
                        client_socket.send(reply)
                        break

                    manifest = f.read()
                    f.close()

                    manifest_appid = struct.unpack('<L', manifest[4:8])[0]
                    manifest_verid = struct.unpack('<L', manifest[8:12])[0]
                    self.log.debug(f"{clientid}Manifest ID: {manifest_appid} Version: {manifest_verid}")
                    if (int(manifest_appid) != int(app)) or (int(manifest_verid) != int(version)):
                        self.log.error(f"Manifest doesn't match requested file: ({app}, {version}) ({manifest_appid}, {manifest_verid})")

                        reply = struct.pack(">LLc", connid, messageid, b"\x01")
                        client_socket.send(reply)

                        break

                    globalvars.converting = "0"

                    fingerprint = manifest[0x30:0x34]
                    oldchecksum = manifest[0x34:0x38]
                    manifest = manifest[:0x30] + b"\x00" * 8 + manifest[0x38:]
                    checksum = struct.pack("<I", zlib.adler32(manifest, 0))
                    manifest = manifest[:0x30] + fingerprint + checksum + manifest[0x38:]

                    self.log.debug(f"Checksum fixed from {binascii.b2a_hex(oldchecksum).decode('latin-1')}  to {binascii.b2a_hex(checksum).decode('latin-1')}")

                    storages[storageid].manifest = manifest

                    checksum = struct.unpack("<L", manifest[0x30:0x34])[0]  # FIXED, possible bug source

                    reply = struct.pack(">LLcLL", connid, messageid, b"\x00", storageid, checksum)

                    client_socket.send(reply, False)

                elif command[0:1] == b"\x09" or command[0:1] == b"\x0a" or command[0:1] == b"\x02":  # REQUEST MANIFEST #09 is used by early clients without a ticket# 02 used by 2003 steam
                    # TODO Proper ticket validation
                    if command[0:1] == b"\x0a":
                        self.log.info(f"{clientid}Login packet used")
                    # else :
                    # self.log.error(clientid + "Not logged in")

                    # reply = struct.pack(">LLc", connid, messageid, b"\x01")
                    # server_socket.send(reply)

                    # break

                    (connid, messageid, app, version) = struct.unpack(">xLLLL", command[0:17])

                    self.log.info(f"{clientid}Opening application {app}, {version}")
                    connid = pow(2, 31) + connid

                    try:
                        s = stmstorages.Storage(app, self.config["storagedir"], version, islan)
                    except Exception:
                        self.log.error(f"Application not installed! {app}, {version}")

                        reply = struct.pack(">LLc", connid, messageid, b"\x01")
                        client_socket.send(reply)

                        break

                    storageid = storagesopen
                    storagesopen += 1

                    storages[storageid] = s
                    storages[storageid].app = app
                    storages[storageid].version = version

                    manifest_dirs = [("files/cache/", f"{str(app)}_{str(version)}/{str(app)}_{str(version)}.manifest", "is a cached depot"), (self.config["manifestdir"], f"{str(app)}_{str(version)}.v4.manifest", "is a v0.4 depot"), (self.config["manifestdir"], f"{str(app)}_{str(version)}.v2.manifest", "is a v0.2 depot"), (self.config["manifestdir"], f"{str(app)}_{str(version)}.v3.manifest", "is a v0.3 depot"), (self.config["manifestdir"], f"{str(app)}_{str(version)}.v3e.manifest", "is a v0.3 extra depot"), (self.config["v4manifestdir"], f"{str(app)}_{str(version)}.manifest", "is a v0.4 depot"), (self.config["v2manifestdir"], f"{str(app)}_{str(version)}.manifest", "is a v0.2 depot"), (self.config["manifestdir"], f"{str(app)}_{str(version)}.manifest", "is a v0.3 depot"), (self.config["v3manifestdir2"], f"{str(app)}_{str(version)}.manifest", "is a v0.3 extra depot")]

                    f = None
                    manifest = None
                    for base_dir, manifestpath, message in manifest_dirs:
                        file_path = os.path.join(base_dir, manifestpath)
                        # print(file_path)
                        if os.path.isfile(file_path):

                            with open(file_path, "rb") as f:
                                self.log.info(f"{clientid}{app}_{version} {message}")
                                manifest = f.read()

                            manifest_appid = struct.unpack('<L', manifest[4:8])[0]
                            manifest_verid = struct.unpack('<L', manifest[8:12])[0]
                            self.log.debug(clientid + (f"Manifest ID: {manifest_appid} Version: {manifest_verid}"))
                            if (int(manifest_appid) != int(app)) or (int(manifest_verid) != int(version)):
                                self.log.error(f"Manifest doesn't match requested file: ({app}, {version}) ({manifest_appid}, {manifest_verid})")

                                reply = struct.pack(">LLc", connid, messageid, b"\x01")
                                client_socket.send(reply)

                                break

                            globalvars.converting = "0"

                            fingerprint = manifest[0x30:0x34]
                            oldchecksum = manifest[0x34:0x38]
                            manifest = manifest[:0x30] + b"\x00" * 8 + manifest[0x38:]
                            checksum = struct.pack("<I", zlib.adler32(manifest, 0))
                            manifest = manifest[:0x30] + fingerprint + checksum + manifest[0x38:]

                            self.log.debug(b"Checksum fixed from " + binascii.b2a_hex(oldchecksum) + b" to " + binascii.b2a_hex(checksum))

                            storages[storageid].manifest = manifest

                            checksum = struct.unpack("<L", manifest[0x30:0x34])[0]  # FIXED, possible bug source

                            reply = struct.pack(">LLcLL", connid, messageid, b"\x00", storageid, checksum)

                            client_socket.send(reply, False)
                            break
                    if manifest == None:
                        self.log.error(f"Manifest not found for {app} {version} ")
                        reply = struct.pack(">LLc", connid, messageid, b"\x01")
                        client_socket.send(reply)
                        break

                elif command[0:1] == b"\x01":  # HANDSHAKE

                    client_socket.send(b"")
                    break

                elif command[0:1] == b"\x03":  # CLOSE STORAGE

                    (storageid, messageid) = struct.unpack(">xLL", command)

                    del storages[storageid]

                    reply = struct.pack(">LLc", storageid, messageid, b"\x00")

                    self.log.info(f"{clientid}Closing down storage %d" % storageid)

                    client_socket.send(reply)

                elif command[0:1] == b"\x04":  # SEND MANIFEST

                    self.log.info(f"{clientid}Sending manifest")

                    (storageid, messageid) = struct.unpack(">xLL", command)

                    manifest = storages[storageid].manifest

                    reply = struct.pack(">LLcL", storageid, messageid, b"\x00", len(manifest))

                    client_socket.send(reply)

                    reply = struct.pack(">LLL", storageid, messageid, len(manifest))

                    client_socket.send(reply + manifest, False)

                elif command[0:1] == b"\x05":  # SEND UPDATE INFO
                    self.log.info(f"{clientid}Sending app update information")
                    (storageid, messageid, oldversion) = struct.unpack(">xLLL", command)
                    appid = storages[storageid].app
                    version = storages[storageid].version
                    self.log.info("Old GCF version: " + str(appid) + "_" + str(oldversion))
                    self.log.info("New GCF version: " + str(appid) + "_" + str(version))
                    manifestNew = Manifest2(appid, version)
                    manifestOld = Manifest2(appid, oldversion)

                    if os.path.isfile("files/cache/" + str(appid) + "_" + str(version) + "/" + str(appid) + "_" + str(version) + suffix + ".checksums"):
                        checksumNew = Checksum2(appid, version, islan)
                    elif os.path.isfile(self.config["manifestdir"] + str(appid) + "_" + str(version) + ".v4.manifest"):
                        checksumNew = Checksum4(appid)
                    elif os.path.isfile(self.config["v4manifestdir"] + str(appid) + "_" + str(version) + ".manifest"):
                        checksumNew = Checksum4(appid)
                    elif os.path.isfile(self.config["manifestdir"] + str(appid) + "_" + str(version) + ".v2.manifest"):
                        checksumNew = Checksum3(appid)
                    elif os.path.isfile(self.config["v2manifestdir"] + str(appid) + "_" + str(version) + ".manifest"):
                        checksumNew = Checksum3(appid)
                    else:
                        checksumNew = Checksum2(appid, version, islan)

                    if os.path.isfile("files/cache/" + str(appid) + "_" + str(version) + "/" + str(appid) + "_" + str(version) + suffix + ".checksums"):
                        checksumOld = Checksum2(appid, version, islan)
                    elif os.path.isfile(self.config["manifestdir"] + str(appid) + "_" + str(oldversion) + ".v4.manifest"):
                        checksumOld = Checksum4(appid)
                    elif os.path.isfile(self.config["v4manifestdir"] + str(appid) + "_" + str(oldversion) + ".manifest"):
                        checksumOld = Checksum4(appid)
                    elif os.path.isfile(self.config["manifestdir"] + str(appid) + "_" + str(oldversion) + ".v2.manifest"):
                        checksumOld = Checksum3(appid)
                    elif os.path.isfile(self.config["v2manifestdir"] + str(appid) + "_" + str(oldversion) + ".manifest"):
                        checksumOld = Checksum3(appid)
                    else:
                        checksumOld = Checksum2(appid, oldversion, islan)

                    filesOld = {}
                    filesNew = {}
                    for n in manifestOld.nodes.values():
                        if n.fileId != 0xffffffff:
                            n.checksum = checksumOld.getchecksums_raw(n.fileId)
                            filesOld[n.fullFilename] = n

                    for n in manifestNew.nodes.values():
                        if n.fileId != 0xffffffff:
                            n.checksum = checksumNew.getchecksums_raw(n.fileId)
                            filesNew[n.fullFilename] = n

                    del manifestNew
                    del manifestOld

                    changedFiles = []

                    for filename in filesOld:
                        if filename in filesNew and filesOld[filename].checksum != filesNew[filename].checksum:
                            changedFiles.append(filesOld[filename].fileId)
                            self.log.debug("Changed file: " + str(filename) + " : " + str(filesOld[filename].fileId))
                        if filename not in filesNew:
                            changedFiles.append(filesOld[filename].fileId)
                            # if not 0xffffffff in changedFiles:
                            # changedFiles.append(0xffffffff)
                            self.log.debug("Deleted file: " + str(filename) + " : " + str(filesOld[filename].fileId))

                    # for x in range(len(changedFiles)):
                        # self.log.debug(changedFiles[x], )

                    count = len(changedFiles)
                    self.log.info("Number of changed files: " + str(count))

                    if count == 0:
                        reply = struct.pack(">LLcL", storageid, messageid, b"\x01", 0)
                        client_socket.send(reply)
                    else:
                        reply = struct.pack(">LLcL", storageid, messageid, b"\x02", count)
                        client_socket.send(reply)

                        changedFilesTmp = []
                        for fileid in changedFiles:
                            changedFilesTmp.append(struct.pack("<L", fileid))
                        updatefiles = b"".join(changedFilesTmp)

                        reply = struct.pack(">LL", storageid, messageid)
                        client_socket.send(reply)
                        client_socket.send_withlen(updatefiles)

                elif command[0:1] == b"\x06":  # SEND CHECKSUMS

                    self.log.info(f"{clientid}Sending checksums")

                    (storageid, messageid) = struct.unpack(">xLL", command)

                    # if storages[storageid].app in globalvars.game_engine_file_appids + globalvars.dedicated_server_appids:
                    if islan:
                        suffix = "_lan"
                    else:
                        suffix = "_wan"
                    # else:
                        # suffix = ""

                    if os.path.isfile("files/cache/" + str(storages[storageid].app) + "_" + str(storages[storageid].version) + "/" + str(storages[storageid].app) + "_" + str(storages[storageid].version) + suffix + ".checksums"):
                        filename = "files/cache/" + str(storages[storageid].app) + "_" + str(storages[storageid].version) + "/" + str(storages[storageid].app) + "_" + str(storages[storageid].version) + suffix + ".checksums"
                    elif os.path.isfile("files/cache/" + str(storages[storageid].app) + "_" + str(storages[storageid].version) + "/" + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".manifest"):
                        filename = "files/cache/" + str(storages[storageid].app) + "_" + str(storages[storageid].version) + "/" + str(storages[storageid].app) + suffix + ".checksums"
                    elif os.path.isfile(self.config["manifestdir"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".v4.manifest"):
                        filename = self.config["storagedir"] + str(storages[storageid].app) + ".v4.checksums"
                    elif os.path.isfile(self.config["v4manifestdir"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".manifest"):
                        filename = self.config["v4storagedir"] + str(storages[storageid].app) + ".checksums"
                    elif os.path.isfile(self.config["manifestdir"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".v2.manifest"):
                        filename = self.config["storagedir"] + str(storages[storageid].app) + ".v2.checksums"
                    elif os.path.isfile(self.config["v2manifestdir"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".manifest"):
                        filename = self.config["v2storagedir"] + str(storages[storageid].app) + ".checksums"
                    elif os.path.isfile(self.config["manifestdir"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".v3e.manifest"):
                        filename = self.config["storagedir"] + str(storages[storageid].app) + ".v3e.checksums"
                    elif os.path.isfile(self.config["manifestdir"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".v3.manifest"):
                        filename = self.config["storagedir"] + str(storages[storageid].app) + ".v3.checksums"
                    elif os.path.isfile(self.config["manifestdir"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".manifest"):
                        filename = self.config["storagedir"] + str(storages[storageid].app) + ".checksums"
                    elif os.path.isdir(self.config["v3manifestdir2"]):
                        if os.path.isfile(self.config["v3manifestdir2"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".manifest"):
                            filename = self.config["v3storagedir2"] + str(storages[storageid].app) + ".checksums"
                        else:
                            self.log.error(f"Manifest not found for {app} {version} ")
                            reply = struct.pack(">LLc", connid, messageid, b"\x01")
                            client_socket.send(reply)
                            break
                    else:
                        self.log.error(f"Checksums not found for {app} {version} ")
                        reply = struct.pack(">LLc", connid, messageid, b"\x01")
                        client_socket.send(reply)
                        break

                    # print(filename)

                    f = open(filename, "rb")
                    file = f.read()
                    f.close()

                    # hack to rip out old sig, insert new
                    file = file[0:-128]
                    signature = encryption.rsa_sign_message(encryption.network_key, file)

                    file = file + signature

                    reply = struct.pack(">LLcL", storageid, messageid, b"\x00", len(file))

                    client_socket.send(reply)
                    #00000000 02000000 00 0000630c #v7
                    #00000000 00000002 00 0000630c #v5

                    reply = struct.pack(">LLL", storageid, messageid, len(file))

                    client_socket.send(reply + file, False)

                elif command[0:1] == b"\x07":  # SEND DATA

                    (storageid, messageid, fileid, filepart, numparts, priority) = struct.unpack(">xLLLLLB", command)

                    (chunks, filemode) = storages[storageid].readchunks(fileid, filepart, numparts)

                    reply = struct.pack(">LLcLL", storageid, messageid, b"\x00", len(chunks), filemode)

                    client_socket.send(reply, False)

                    for chunk in chunks:
                        reply = struct.pack(">LLL", storageid, messageid, len(chunk))

                        client_socket.send(reply, False)

                        reply = struct.pack(">LLL", storageid, messageid, len(chunk))

                        client_socket.send(reply, False)

                        client_socket.send(chunk, False)

                elif command[0:1] == b"\x08":  # INVALID

                    self.log.warning("08 - Invalid Command!")
                    client_socket.send(b"\x01")

                else:

                    self.log.warning(f"{binascii.b2a_hex(command[0:1])} - Invalid Command!")
                    client_socket.send(b"\x01")

                    break
        # \X07 FOR 2004+
        elif msg == b"\x00\x00\x00\x07":

            self.log.info(f"{clientid}Storage mode entered")

            storagesopen = 0
            storages = {}
            is_sdkdepot = False
            client_socket.send(b"\x01")  # this should just be the handshake

            while True:

                command = client_socket.recv_withlen()
                #log.debug(f"{clientid}Content server command: {command[0:1]}")

                # BANNER
                if command[0:1] == b"\x00":

                    if len(command) == 10:
                        client_socket.send(b"\x01")
                        break

                    if len(command) > 1:
                        self.log.info(f"Banner message: {binascii.b2a_hex(command)}")

                        if self.config['enable_custom_banner'].lower() == "true":
                            url = self.config['custom_banner_url']
                        else:
                            url = ("http://" + globalvars.get_octal_ip(islan, False) + "/platform/banner/random.php")

                        reply = struct.pack(">cH", b"\x01", len(url)) + url.encode()

                        client_socket.send(reply)
                    else:
                        client_socket.send(b"")
                # REQUEST MANIFEST #09 is used by clients without a ticket #0A is used by clients with a ticket
                elif command[0:1] == b"\x09" or command[0:1] == b"\x0a":
                    (connid, messageid, app, version) = struct.unpack(">xLLLL", command[0:17])
                    connid = pow(2, 31) + connid

                    if command[0:1] == b"\x0a":
                        self.log.info(f"{clientid}Login packet used\n ticket packet {command[1:]}")
                        real_ticket = command[19:]
                        # Ensure the ticket is real, otherwise it is probably cftoolkit trying to download apps
                        # FIXME: the 2010 client does not seem to re-authenticate to get a refreshed ticket when it is rejected...
                        if len(real_ticket) > 70:
                            ticket = Steam2Ticket(real_ticket)
                            # Validate the expiration time in the ticket
                            if ticket.is_expired:
                                self.log.error(clientid + "Not logged in")
                                # FIXME temporary hack for 2010 clients until i figure out why the client wont reauth when the cs rejects the ticket
                                reply = struct.pack(">LLc", connid, messageid, b"\x00")  # b"\x01")
                                client_socket.send(reply)
                                break

                    self.log.info(f"{clientid}Opening application {app:d} {version:d}")

                    # SDK_DEPOT - Check for app in the sdk depot directory first!

                    if steam2_sdk_utils.find_blob_file(app, version):
                        is_sdkdepot = True
                        manifest_class = SDKManifest(app, version)
                        self.log.info(f"{clientid}Application {app} v{version} is a SDK Depot")
                        manifest = manifest_class.manifestData
                        s = stmstorages.Steam2Storage(app, self.config["storagedir"], version, islan)
                    else:
                        #print("non-sdk manifest")
                        is_sdkdepot = False
                        try:
                            s = stmstorages.Storage(app, self.config["storagedir"], version, islan)
                        except Exception:

                            self.log.error(f"Application not installed! {app:d} {version:d}")

                            reply = struct.pack(">LLc", connid, messageid, b"\x01")

                            client_socket.send(reply)

                            break

                    storageid = storagesopen
                    storagesopen += 1

                    storages[storageid] = s
                    storages[storageid].app = app
                    storages[storageid].version = version

                    manifest_dirs = [
                            ("files/cache/", f"{str(app)}_{str(version)}/{str(app)}_{str(version)}.manifest", "is a cached depot"),
                            (self.config["manifestdir"], f"{str(app)}_{str(version)}.v4.manifest", "is a v0.4 depot"),
                            (self.config["manifestdir"], f"{str(app)}_{str(version)}.v2.manifest", "is a v0.2 depot"),
                            (self.config["manifestdir"], f"{str(app)}_{str(version)}.v3.manifest", "is a v0.3 depot"),
                            (self.config["manifestdir"], f"{str(app)}_{str(version)}.v3e.manifest", "is a v0.3 extra depot"),
                            (self.config["v4manifestdir"], f"{str(app)}_{str(version)}.manifest", "is a v0.4 depot"),
                            (self.config["v2manifestdir"], f"{str(app)}_{str(version)}.manifest", "is a v0.2 depot"),
                            (self.config["manifestdir"], f"{str(app)}_{str(version)}.manifest", "is a v0.3 depot"),
                            (self.config["v3manifestdir2"], f"{str(app)}_{str(version)}.manifest", "is a v0.3 extra depot")]

                    if not is_sdkdepot:
                        f = None
                        manifest = None
                        for base_dir, manifestpath, message in manifest_dirs:
                            file_path = os.path.join(base_dir, manifestpath)
                            #print(file_path)
                            if os.path.isfile(file_path):
                                with open(file_path, "rb") as f:
                                    self.log.info(f"{clientid}{app}_{version} {message}")
                                    manifest = f.read()

                        if manifest == None:
                            self.log.error(f"Manifest not found for {app} {version} ")
                            reply = struct.pack(">LLc", connid, messageid, b"\x01")
                            client_socket.send(reply)
                            break  # CLOSE CONNECT

                        manifest_appid = struct.unpack('<L', manifest[4:8])[0]
                        manifest_verid = struct.unpack('<L', manifest[8:12])[0]
                        self.log.debug(clientid + (f"Manifest ID: {manifest_appid} Version: {manifest_verid}"))
                        if (int(manifest_appid) != int(app)) or (int(manifest_verid) != int(version)):
                            self.log.error(f"Manifest doesn't match requested file: ({app}, {version}) ({manifest_appid}, {manifest_verid})")
                            reply = struct.pack(">LLc", connid, messageid, b"\x01")
                            client_socket.send(reply)
                            break

                        globalvars.converting = "0"

                        fingerprint = manifest[0x30:0x34]
                        oldchecksum = manifest[0x34:0x38]
                        manifest = manifest[:0x30] + b"\x00" * 8 + manifest[0x38:]
                        checksum = struct.pack("<I", zlib.adler32(manifest, 0))
                        manifest = manifest[:0x30] + fingerprint + checksum + manifest[0x38:]

                        self.log.debug(f"Checksum fixed from {binascii.b2a_hex(oldchecksum)} to {binascii.b2a_hex(checksum)}")

                    storages[storageid].manifest = manifest

                    checksum = struct.unpack("<L", manifest[0x30:0x34])[0]  # FIXED, possible bug source
                    # Send sdk depot manifest bytes 34:38 because we dont change it at all
                    reply = struct.pack(">LLcLL", connid, messageid, b"\x00", storageid, checksum)

                    client_socket.send(reply, False)
                # CLOSE CONNECTION
                elif command[0:1] == b"\x01":
                    client_socket.send(b"")
                    break
                # SEND CDR
                elif command[0:1] == b"\x02":
                    while globalvars.compiling_cdr:
                        time.sleep(1)

                    blob = cdr_manipulator.read_blob(islan)

                    self.log.debug(clientid + "Sending new blob: " + binascii.b2a_hex(command).decode())

                    client_socket.send_withlen(blob, False)  # false for not showing in log
                # CLOSE DOWNLOAD SESSION
                elif command[0:1] == b"\x03":

                    (storageid, messageid) = struct.unpack(">xLL", command)

                    del storages[storageid]

                    reply = struct.pack(">LLc", storageid, messageid, b"\x00")

                    self.log.info(f"{clientid}Closing down storage {storageid:d}")

                    client_socket.send(reply)
                # SEND MANIFEST
                elif command[0:1] == b"\x04":

                    self.log.info(f"{clientid}Sending manifest")

                    (storageid, messageid) = struct.unpack(">xLL", command)

                    manifest = storages[storageid].manifest

                    reply = struct.pack(">LLcL", storageid, messageid, b"\x00", len(manifest))

                    client_socket.send(reply)

                    reply = struct.pack(">LLL", storageid, messageid, len(manifest))

                    client_socket.send(reply + manifest, False)
                # SEND UPDATE INFO
                elif command[0:1] == b"\x05":
                    self.log.info(f"{clientid}Sending app update information")
                    (storageid, messageid, oldversion) = struct.unpack(">xLLL", command)
                    appid = storages[storageid].app
                    version = storages[storageid].version
                    self.log.info("Old GCF version: " + str(appid) + "_" + str(oldversion))
                    self.log.info("New GCF version: " + str(appid) + "_" + str(version))
                    # SDK_DEPOT - Check for app in the sdk depot directory first!
                    if steam2_sdk_utils.check_for_entry(appid, version):
                        self.log.info(f"{clientid}Sending app update from SDK Depot Files")
                        is_sdkdepot = True
                        manifest_class_new = SDKManifest(appid, version)
                        manifest_class_old = SDKManifest(appid, oldversion)
                        # self.log.info(f"{clientid}Application {app} v{version} is a SDK Depot")
                        manifestNew = manifest_class_new
                        manifestOld = manifest_class_old

                        checksumNew = SDKChecksum((int(appid), int(version)))
                        checksumOld = SDKChecksum((int(appid), int(oldversion)))
                    else:
                        manifestNew = Manifest2(appid, version)
                        manifestOld = Manifest2(appid, oldversion)

                        if os.path.isfile("files/cache/" + str(appid) + "_" + str(version) + "/" + str(appid) + "_" + str(version) + suffix + ".checksums"):
                            checksumNew = Checksum2(appid, version, islan)
                        elif os.path.isfile(self.config["manifestdir"] + str(appid) + "_" + str(version) + ".v4.manifest"):
                            checksumNew = Checksum4(appid)
                        elif os.path.isfile(self.config["v4manifestdir"] + str(appid) + "_" + str(version) + ".manifest"):
                            checksumNew = Checksum4(appid)
                        elif os.path.isfile(self.config["manifestdir"] + str(appid) + "_" + str(version) + ".v2.manifest"):
                            checksumNew = Checksum3(appid)
                        elif os.path.isfile(self.config["v2manifestdir"] + str(appid) + "_" + str(version) + ".manifest"):
                            checksumNew = Checksum3(appid)
                        else:
                            checksumNew = Checksum2(appid, version, islan)

                        if os.path.isfile("files/cache/" + str(appid) + "_" + str(version) + "/" + str(appid) + "_" + str(version) + suffix + ".checksums"):
                            checksumOld = Checksum2(appid, version, islan)
                        elif os.path.isfile(self.config["manifestdir"] + str(appid) + "_" + str(oldversion) + ".v4.manifest"):
                            checksumOld = Checksum4(appid)
                        elif os.path.isfile(self.config["v4manifestdir"] + str(appid) + "_" + str(oldversion) + ".manifest"):
                            checksumOld = Checksum4(appid)
                        elif os.path.isfile(self.config["manifestdir"] + str(appid) + "_" + str(oldversion) + ".v2.manifest"):
                            checksumOld = Checksum3(appid)
                        elif os.path.isfile(self.config["v2manifestdir"] + str(appid) + "_" + str(oldversion) + ".manifest"):
                            checksumOld = Checksum3(appid)
                        else:
                            checksumOld = Checksum2(appid, oldversion, islan)

                    filesOld = {}
                    filesNew = {}
                    for n in manifestOld.nodes.values():
                        if n.fileId != 0xffffffff:
                            n.checksum = checksumOld.getchecksums_raw(n.fileId)
                            filesOld[n.fullFilename] = n

                    for n in manifestNew.nodes.values():
                        if n.fileId != 0xffffffff:
                            n.checksum = checksumNew.getchecksums_raw(n.fileId)
                            filesNew[n.fullFilename] = n

                    del manifestNew
                    del manifestOld

                    changedFiles = []

                    for filename in filesOld:
                        if filename in filesNew and filesOld[filename].checksum != filesNew[filename].checksum:
                            changedFiles.append(filesOld[filename].fileId)
                            self.log.debug(f"Changed file: {str(filename)} : {str(filesOld[filename].fileId)}")
                        if not filename in filesNew:
                            changedFiles.append(filesOld[filename].fileId)
                            # if not 0xffffffff in changedFiles:
                            # changedFiles.append(0xffffffff)
                            self.log.debug(f"Deleted file: {str(filename)} : {str(filesOld[filename].fileId)}")

                    # for x in range(len(changedFiles)):
                    # self.log.debug(changedFiles[x], )

                    count = len(changedFiles)
                    self.log.info(f"Number of changed files: {str(count)}")

                    if count == 0:
                        reply = struct.pack(">LLcL", storageid, messageid, b"\x01", 0)
                        client_socket.send(reply)
                    else:
                        reply = struct.pack(">LLcL", storageid, messageid, b"\x02", count)
                        client_socket.send(reply)

                        changedFilesTmp = []
                        for fileid in changedFiles:
                            changedFilesTmp.append(struct.pack("<L", fileid))
                        updatefiles = b"".join(changedFilesTmp)

                        reply = struct.pack(">LL", storageid, messageid)
                        client_socket.send(reply)
                        client_socket.send_withlen(updatefiles)
                # SEND CHECKSUMS
                elif command[0:1] == b"\x06":
                    (storageid, messageid) = struct.unpack(">xLL", command)

                    #if storages[storageid].app in globalvars.game_engine_file_appids + globalvars.dedicated_server_appids:
                    if islan:
                        suffix = "_lan"
                    else:
                        suffix = "_wan"

                    if steam2_sdk_utils.find_blob_file(storages[storageid].app, storages[storageid].version):
                        self.log.info(f"{clientid}Sending checksums from SDK Depot")
                        is_sdkdepot = True
                        if self.config['cache_sdk_depot_checksums'].lower() == "true" and os.path.isfile("files/cache/%d.checksums" % str(storages[storageid].app)):
                            checksumfilename = os.path.join("files/cache/", "%d.checksums" % str(storages[storageid].app))
                            with open(checksumfilename, "rb") as f:
                                file = f.read()
                        else:
                            file = steam2_sdk_utils.extract_checksumbin(f"{str(storages[storageid].app)}_{str(storages[storageid].version)}.blob")
                    else:
                        self.log.info(f"{clientid}Sending checksums")
                        if os.path.isfile("files/cache/" + str(storages[storageid].app) + "_" + str(storages[storageid].version) + "/" + str(storages[storageid].app) + "_" + str(storages[storageid].version) + suffix + ".checksums"):
                            filename = "files/cache/" + str(storages[storageid].app) + "_" + str(storages[storageid].version) + "/" + str(storages[storageid].app) + "_" + str(storages[storageid].version) + suffix + ".checksums"
                        elif os.path.isfile("files/cache/" + str(storages[storageid].app) + "_" + str(storages[storageid].version) + "/" + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".manifest"):
                            filename = "files/cache/" + str(storages[storageid].app) + "_" + str(storages[storageid].version) + "/" + str(storages[storageid].app) + suffix + ".checksums"
                        elif os.path.isfile(self.config["manifestdir"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".v4.manifest"):
                            filename = self.config["storagedir"] + str(storages[storageid].app) + ".v4.checksums"
                        elif os.path.isfile(self.config["v4manifestdir"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".manifest"):
                            filename = self.config["v4storagedir"] + str(storages[storageid].app) + ".checksums"
                        elif os.path.isfile(self.config["manifestdir"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".v2.manifest"):
                            filename = self.config["storagedir"] + str(storages[storageid].app) + ".v2.checksums"
                        elif os.path.isfile(self.config["v2manifestdir"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".manifest"):
                            filename = self.config["v2storagedir"] + str(storages[storageid].app) + ".checksums"
                        elif os.path.isfile(self.config["manifestdir"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".v3e.manifest"):
                            filename = self.config["storagedir"] + str(storages[storageid].app) + ".v3e.checksums"
                        elif os.path.isfile(self.config["manifestdir"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".v3.manifest"):
                            filename = self.config["storagedir"] + str(storages[storageid].app) + ".v3.checksums"
                        elif os.path.isfile(self.config["manifestdir"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".manifest"):
                            filename = self.config["storagedir"] + str(storages[storageid].app) + ".checksums"
                        elif os.path.isdir(self.config["v3manifestdir2"]):
                            if os.path.isfile(self.config["v3manifestdir2"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".manifest"):
                                filename = self.config["v3storagedir2"] + str(storages[storageid].app) + ".checksums"
                            else:
                                self.log.error(f"Manifest not found for {app} {version} ")
                                reply = struct.pack(">LLc", connid, messageid, b"\x01")
                                client_socket.send(reply)
                                break
                        else:
                            self.log.error(f"Checksums not found for {app} {version} ")
                            reply = struct.pack(">LLc", connid, messageid, b"\x01")
                            client_socket.send(reply)
                            break

                        f = open(filename, "rb")
                        file = f.read()
                        f.close()

                    # hack to rip out old sig, insert new
                    file = file[0:-128]
                    signature = encryption.rsa_sign_message(encryption.network_key, file)

                    file = file + signature

                    reply = struct.pack(">LLcL", storageid, messageid, b"\x00", len(file))

                    client_socket.send(reply)

                    reply = struct.pack(">LLL", storageid, messageid, len(file))

                    client_socket.send(reply + file, False)
                # SEND DATA CHUNKS
                elif command[0:1] == b"\x07":

                    (storageid, messageid, fileid, filepart, numparts, priority) = struct.unpack(">xLLLLLB", command)

                    (chunks, filemode) = storages[storageid].readchunks(fileid, filepart, numparts)

                    reply = struct.pack(">LLcLL", storageid, messageid, b"\x00", len(chunks), filemode)

                    client_socket.send(reply, False)

                    for chunk in chunks:
                        
                        # LEAVE COMMENTED OUT IN CASE WE FIND A WAY TO ALTER CHECKSUMS ON THE FLY
                        
                        # uncomp_chunk = zlib.decompress(chunk)
                        
                        # processed_chunk = utils.readchunk_neuter(uncomp_chunk, True)
                        
                        # chunk = zlib.compress(processed_chunk, 9)

                        reply = struct.pack(">LLL", storageid, messageid, len(chunk))

                        client_socket.send(reply, False)

                        reply = struct.pack(">LLL", storageid, messageid, len(chunk))

                        client_socket.send(reply, False)

                        client_socket.send(chunk, False)
                # INVALID
                elif command[0:1] == b"\x08":
                    self.log.warning("0x08 - Invalid Command!")
                    client_socket.send(b"\x01")
                # SEND AVAILABLE CONTENT LIST
                elif command[0:1] == b"\xff":
                    buffer = bytearray()
                    count = 0
                    # Loop through the app_list and append each app_id and version to the buffer
                    for app_id, version in app_list:
                        count += 1
                        # Pack app_id and version as unsigned 32-bit integers and append to buffer
                        buffer.extend(struct.pack('<II', app_id, version))  # '<II' is for 2 little-endian 32-bit ints

                    byte_string = struct.pack("<I", count) + bytes(buffer)
                    client_socket.send(byte_string)
                # SEND STORAGE VERSION FOR NEUTERING (98)
                elif command[0:1] == b"\x62":
                    self.log.info(f"{clientid}Sending storage version")

                    (storageid, messageid) = struct.unpack(">xLL", command)

                    if os.path.isfile(self.config["manifestdir"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".v4.manifest"):
                            reply = struct.pack(">LLc", storageid, messageid, b"\x04")
                    elif os.path.isfile(self.config["v4manifestdir"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".manifest"):
                            reply = struct.pack(">LLc", storageid, messageid, b"\x04")
                    elif os.path.isfile(self.config["manifestdir"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".v2.manifest"):
                            reply = struct.pack(">LLc", storageid, messageid, b"\x02")
                    elif os.path.isfile(self.config["v2manifestdir"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".manifest"):
                            reply = struct.pack(">LLc", storageid, messageid, b"\x02")
                    elif os.path.isfile(self.config["manifestdir"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".v3e.manifest"):
                            reply = struct.pack(">LLc", storageid, messageid, b"\x03")
                    elif os.path.isfile(self.config["manifestdir"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".v3.manifest"):
                            reply = struct.pack(">LLc", storageid, messageid, b"\x03")
                    elif os.path.isfile(self.config["manifestdir"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".manifest"):
                            reply = struct.pack(">LLc", storageid, messageid, b"\x03")
                    elif os.path.isdir(self.config["v3manifestdir2"]):
                        if os.path.isfile(self.config["v3manifestdir2"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".manifest"):
                            reply = struct.pack(">LLc", storageid, messageid, b"\x03")
                        else:
                            self.log.error(f"Manifest not found for {app} ")
                            reply = struct.pack(">LLc", storageid, messageid, b"\x00")
                            client_socket.send(reply)
                            break
                    else:
                        self.log.error(f"Manifest not found for {app} ")
                        reply = struct.pack(">LLc", storageid, messageid, b"\x00")
                        client_socket.send(reply)
                        break

                    client_socket.send(reply)
                    #server_socket.send(reply)
                # SEND INDEX FOR NEUTERING (99) UNUSED
                elif command[0:1] == b"\x63":
                    self.log.info(f"{clientid}Sending index")

                    (storageid, messageid) = struct.unpack(">xLL", command)

                    if os.path.isfile(self.config["manifestdir"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".v4.manifest"):
                        filename = self.config["storagedir"] + str(storages[storageid].app) + ".v4.index"
                    elif os.path.isfile(self.config["manifestdir"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".v2.manifest"):
                        filename = self.config["storagedir"] + str(storages[storageid].app) + ".v2.index"
                    elif os.path.isfile(self.config["manifestdir"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".v3.manifest"):
                        filename = self.config["storagedir"] + str(storages[storageid].app) + ".v3.index"
                    elif os.path.isfile(self.config["manifestdir"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".v3e.manifest"):
                        filename = self.config["storagedir"] + str(storages[storageid].app) + ".v3e.index"
                    elif os.path.isfile(self.config["v4manifestdir"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".manifest"):
                        filename = self.config["v4storagedir"] + str(storages[storageid].app) + ".index"
                    elif os.path.isfile(self.config["v2manifestdir"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".manifest"):
                        filename = self.config["v2storagedir"] + str(storages[storageid].app) + ".index"
                    elif os.path.isfile(self.config["manifestdir"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".manifest"):
                        filename = self.config["storagedir"] + str(storages[storageid].app) + ".index"
                    elif os.path.isdir(self.config["v3manifestdir2"]):
                        if os.path.isfile(self.config["v3manifestdir2"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".manifest"):
                            filename = self.config["v3storagedir2"] + str(storages[storageid].app) + ".index"
                        else:
                            self.log.error(f"Index not found for {app} ")
                            reply = struct.pack(">LLc", connid, messageid, b"\x01")
                            client_socket.send(reply)
                            break
                    else:
                        self.log.error(f"Index not found for {app} ")
                        reply = struct.pack(">LLc", connid, messageid, b"\x01")
                        client_socket.send(reply)
                        break
                    
                    with open(filename, "rb") as f:
                        file = f.read()

                    reply = struct.pack(">LLcL", storageid, messageid, b"\x00", len(file))

                    client_socket.send(reply)

                    reply = struct.pack(">LLL", storageid, messageid, len(file))

                    client_socket.send(reply + file, False)
                # INVALID COMMAND
                else:

                    self.log.warning(f"{binascii.b2a_hex(command[0:1])} - Invalid Command!")
                    client_socket.send(b"\x01")

                    break
        # UNKNOWN
        elif msg == b"\x03\x00\x00\x00":
            self.log.info(f"{clientid}Unknown mode entered")
            client_socket.send(b"\x00")
        # LATENCY CHECK FROM CSDS
        # TODO Deprecate or complete, figure it out ben!
        elif msg == b"\x66\x61\x23\x45":
            self.log.info(f"{clientid}Recieved a Latency Test from CSDS")
            client_socket.send(b"\x00")
        else:
            self.log.warning(f"Invalid Command: {binascii.b2a_hex(msg)}")

        client_socket.close()
        self.log.info(f"{clientid}Disconnected from Content Server")

    def parse_manifest_files(self):
        # Define the locations to search for '.manifest' files
        locations = ['files/cache/', self.config["v4manifestdir"], self.config["v2manifestdir"], self.config["manifestdir"], self.config["v3manifestdir2"], self.config["betamanifestdir"]]
        app_buffer = b""
        for location in locations:
            for file_name in os.listdir(location):
                if file_name.endswith('.v2.manifest') or file_name.endswith('.v3.manifest') or file_name.endswith('.v4.manifest') or file_name.endswith('.v3e.manifest'):
                    # Extract app ID and version from the file name
                    app_id, version = file_name.split('_')
                    version = version.split(".")[0]
                    # for appid, version in self.applist:
                    # print("appid:", app_id)
                    # print("version:", version)
                    # Append app ID and version to app_list in this format
                    app_buffer += str(app_id).encode('latin-1') + b"\x00" + str(version).encode('latin-1') + b"\x00\x00"
                    app_list.append((app_id, version))
                elif file_name.endswith('.manifest'):
                    # Extract app ID and version from the file name
                    app_id, version = file_name.split('_')
                    version = version.rstrip('.manifest')
                    # for appid, version in self.applist:
                    # print("appid:", app_id)
                    # print("version:", version)
                    # Append app ID and version to app_list in this format
                    app_buffer += str(app_id).encode('latin-1') + b"\x00" + str(version).encode('latin-1') + b"\x00\x00"
                    app_list.append((app_id, version))
        # For SDK Support
        """for app_id, version  in steam2_sdk_utils.extract_blob_info("files/steam2_sdk_depots/"):
            app_buffer += str(app_id).encode('latin-1') + b"\x00" + str(version).encode('latin-1') + b"\x00\x00"
            app_list.append((app_id, version))"""
        # Parse .dat files in the SDK depot directory
        sdk_depot_dir = self.config['steam2sdkdir']
        if os.path.exists(sdk_depot_dir):
            steam2_sdk_utils.scan_directories(sdk_depot_dir,sdk_depot_dir)
            for file_name in os.listdir(sdk_depot_dir):
                if file_name.endswith('.dat'):
                    # Ensure the format matches <appid>_<version>.dat
                    try:
                        app_id, version = file_name.split('_')
                        version = version.rstrip('.dat')  # Remove the '.dat' extension
                        # Append app ID and version to app_list and app_buffer
                        app_buffer += str(app_id).encode('latin-1') + b"\x00" + str(version).encode('latin-1') + b"\x00\x00"
                        app_list.append((app_id, version))
                    except ValueError:
                        # Handle the case where the file name format doesn't match
                        print(f"Skipping file with unexpected format: {file_name}")

        return app_buffer