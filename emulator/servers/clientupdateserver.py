import sys
import traceback
import binascii
import os
import os.path
import threading
import time

import ipcalc
from Crypto.Hash import SHA

import globalvars
import utilities.blobs
import utilities.encryption
import utils
from listmanagers.contentlistmanager import manager
from listmanagers.contentserverlist_utilities import send_removal, heartbeat_thread
from utilities import cdr_manipulator
from utilities.manifests import *
from utilities.networkhandler import TCPNetworkHandler
from utilities.neuter import neuter

cusConnectionCount = 0



class clientupdateserver(TCPNetworkHandler):
    def __init__(self, port, config):
        self.server_type = "ClientUpdateServer"
        super(clientupdateserver, self).__init__(config, port, self.server_type)  # Create an instance of NetworkHandler

        if globalvars.public_ip == "0.0.0.0":
            server_ip = globalvars.server_ip_b
        else:
            server_ip = globalvars.public_ip_b

        self.secret_identifier = utils.generate_unique_server_id()

        self.applist = []
        self.key = None
        self.contentserver_info = {
                'server_id':self.secret_identifier,
                'wan_ip':   server_ip,
                'lan_ip':   globalvars.server_ip_b,
                'port':     int(port),
                'region':   globalvars.cs_region.encode('latin-1'),
                'cellid':   globalvars.cellid,
        }
        self.log = logging.getLogger("ClUpdSRV")
        if not globalvars.aio_server:
            self.log.info("If you are seeing this message, The heartbeat thread in ClientUpdate Server is running and you should be using standalone servers\n If you are not using standalone servers, please report this message!")
            self.thread = threading.Thread(target = heartbeat_thread, args = (self,))
            self.thread.daemon = True
            self.thread.start()
        else:
            manager.add_contentserver_info(self.secret_identifier, server_ip, globalvars.server_ip, int(port), globalvars.cs_region, "", globalvars.cellid, True, True)

    def run(self):
        try:
            self.log.info("Client Update Server thread started.")
            super().run()  # Call the parent run method which contains the main loop
        except Exception as e:
            self.log.error("Client Update Server encountered an exception:", exc_info=True)
            # Optionally, you can set a flag or use another mechanism to notify the watchdog
        finally:
            self.log.info("Client Update Server thread terminating.")

    def cleanup(self):
        """Content Server specific cleanup routine"""
        self.log.info(f"Cleaning up Client Update Server on port {self.port}")

        if not globalvars.aio_server:
            send_removal(self.secret_identifier)
        super().cleanup()

    def handle_client(self, client_socket, client_address):
        global cusConnectionCount

        def global_thread_exception_handler(args):
            logging.getLogger('threadhndl').error(
                    f"Exception in thread '{args.thread.name}': {args.exc_type.__name__}: {args.exc_value}",
                    exc_info = (args.exc_type, args.exc_value, args.exc_traceback)
            )

        threading.excepthook = global_thread_exception_handler

        clientid = str(client_address) + ": "
        try:
            self.log.info(clientid + "Connected to Client Update Server")
            if str(client_address[0]) in ipcalc.Network(str(globalvars.server_net)): # or globalvars.public_ip == str(client_address[0]): # we ignore this because it breaks things
                islan = True
            else:
                islan = False

            msg = client_socket.recv(4)

            if len(msg) == 0:
                self.log.info(f"{clientid}Got simple handshake. Closing connection.")
            # 2003+ RELEASE CLIENT UPDATE
            if msg == b"\x00\x00\x00\x00" or msg == b"\x00\x00\x00\x02" or msg == b"\x00\x00\x00\x03":
                self.log.info(f"{clientid}Package mode entered")

                # If this is a beta client, set to true.  Else false.
                isbeta = True if globalvars.record_ver == 1 else False
                #print(f"Command code: {msg}")
                client_socket.send(b"\x01")

                while True:
                    msg = client_socket.recv_withlen()

                    if not msg:
                        self.log.info(f"{clientid}no message received")
                        break

                    command = struct.unpack(">L", msg[:4])[0]
                    # CELLID
                    if command == 2:
                        client_socket.send(struct.pack('>I', int(self.config["cellid"])))
                        break
                    # CLOSE CONNECTION
                    elif command == 3:
                        self.log.info(f"{clientid}Exiting package mode")
                        break
                    # GET PACKAGE
                    elif command == 0:
                        command = struct.unpack(">L", msg[:4])[0]

                        # Find the position of the first non-zero byte after the command
                        filename_start = 4

                        #this disables a error when going from beta client to retail
                        if len(msg) < 11:
                            print("Message size less than 11 bytes")
                            break

                        while msg[filename_start] == 0:
                            filename_start += 1
                            if filename_start >= len(msg):
                                self.log.error(f"{clientid}Filename not found in the message")

                        # Extract the filename length (assuming it's one byte)
                        filenamelength = struct.unpack(">B", msg[filename_start:filename_start + 1])[0]
                        filename_start += 1  # Move past the length byte
                        filename = msg[filename_start:filename_start + filenamelength]

                        filename = utils.sanitize_filename(filename)

                        if filename[-14:] == b"_rsa_signature":
                            newfilename = filename[:-14]
                            if self.config["public_ip"] != "0.0.0.0":
                                try:
                                    os.mkdir("files/cache/external")
                                except OSError as error:
                                    self.log.debug(f"{clientid}External pkg dir already exists")

                                try:
                                    os.mkdir("files/cache/internal")
                                except OSError as error:
                                    self.log.debug(f"{clientid}Internal pkg dir already exists")

                                if isbeta:
                                    try:
                                        os.mkdir("files/cache/external/betav2")
                                    except OSError as error:
                                        self.log.debug(clientid + "External beta pkg dir already exists")
                                    try:
                                        os.mkdir("files/cache/internal/betav2")
                                    except OSError as error:
                                        self.log.debug(clientid + "Internal beta pkg dir already exists")

                                    if islan:
                                        if not os.path.isfile("files/cache/internal/betav2/" + newfilename):
                                            neuter(self.config["packagedir"] + "betav2/" + newfilename, "files/cache/internal/betav2/" + newfilename, self.config["server_ip"], self.config["dir_server_port"], True)
                                        f = open('files/cache/internal/betav2/' + newfilename, 'rb')
                                    else:
                                        if not os.path.isfile("files/cache/external/betav2/" + newfilename):
                                            neuter(self.config["packagedir"] + "betav2/" + newfilename, "files/cache/external/betav2/" + newfilename, self.config["public_ip"], self.config["dir_server_port"], False)
                                        f = open('files/cache/external/betav2/' + newfilename, 'rb')
                                else:
                                    if islan:
                                        if not os.path.isfile("files/cache/internal/" + newfilename.decode()):
                                            neuter(self.config["packagedir"] + newfilename.decode(), "files/cache/internal/" + newfilename.decode(), self.config["server_ip"], self.config["dir_server_port"], True)
                                        f = open('files/cache/internal/' + newfilename.decode(), 'rb')
                                    else:
                                        if not os.path.isfile("files/cache/external/" + newfilename.decode()):
                                            neuter(self.config["packagedir"] + newfilename.decode(), "files/cache/external/" + newfilename.decode(), self.config["public_ip"], self.config["dir_server_port"], False)
                                        f = open('files/cache/external/' + newfilename.decode(), 'rb')
                            else:
                                if isbeta:
                                    try:
                                        os.mkdir("files/cache/betav2")
                                    except OSError as error:
                                        self.log.debug(clientid + "Beta pkg dir already exists")
                                    if not os.path.isfile("files/cache/betav2/" + newfilename):
                                        neuter(self.config["packagedir"] + "betav2/" + newfilename, "files/cache/betav2/" + newfilename, self.config["server_ip"], self.config["dir_server_port"], True)
                                    f = open('files/cache/betav2/' + newfilename, 'rb')
                                else:
                                    if not os.path.isfile("files/cache/" + newfilename.decode()):
                                        neuter(self.config["packagedir"] + newfilename.decode(), "files/cache/" + newfilename.decode(), self.config["server_ip"], self.config["dir_server_port"], True)
                                    f = open('files/cache/' + newfilename.decode(), 'rb')

                            file = f.read()
                            f.close()

                            signature = utilities.encryption.rsa_sign_message(utilities.encryption.network_key, file)

                            reply = struct.pack('>LL', len(signature), len(signature)) + signature

                            client_socket.send(reply)
                        else:
                            filename = filename.decode('latin-1')

                            if self.config["public_ip"] != "0.0.0.0":
                                try:
                                    os.mkdir("files/cache/external")
                                except OSError as error:
                                    self.log.debug(clientid + "External pkg dir already exists")

                                try:
                                    os.mkdir("files/cache/internal")
                                except OSError as error:
                                    self.log.debug(clientid + "Internal pkg dir already exists")

                                if isbeta:
                                    try:
                                        os.mkdir("files/cache/external/betav2")
                                    except OSError as error:
                                        self.log.debug(clientid + "External beta pkg dir already exists")
                                    try:
                                        os.mkdir("files/cache/internal/betav2")
                                    except OSError as error:
                                        self.log.debug(clientid + "Internal beta pkg dir already exists")

                                    if islan:  # or globalvars.public_ip == str(client_address[0]):
                                        try:
                                            if not os.path.isfile("files/cache/internal/betav2/" + filename):
                                                neuter(self.config["packagedir"] + "betav2/" + filename, "files/cache/internal/betav2/" + filename, self.config["server_ip"], self.config["dir_server_port"], True)
                                            f = open('files/cache/internal/betav2/' + filename, 'rb')
                                        except:
                                            neuter(self.config["packagedir"] + filename, "files/cache/internal/" + filename, self.config["server_ip"], self.config["dir_server_port"], False)
                                            f = open('files/cache/internal/' + filename, 'rb')
                                    else:
                                        if not os.path.isfile("files/cache/external/" + filename):
                                            try:
                                                if not os.path.isfile("files/cache/external/betav2/" + filename):
                                                    neuter(self.config["packagedir"] + "betav2/" + filename, "files/cache/external/betav2/" + filename, self.config["public_ip"], self.config["dir_server_port"], False)
                                                f = open('files/cache/external/betav2/' + filename, 'rb')
                                            except:
                                                neuter(self.config["packagedir"] + filename, "files/cache/external/" + filename, self.config["public_ip"], self.config["dir_server_port"], False)
                                                f = open('files/cache/external/' + filename, 'rb')
                                else:
                                    if islan:
                                        if not os.path.isfile("files/cache/internal/" + filename):
                                            neuter(self.config["packagedir"] + filename, "files/cache/internal/" + filename, self.config["server_ip"], self.config["dir_server_port"], True)
                                        f = open('files/cache/internal/' + filename, 'rb')
                                    else:
                                        if not os.path.isfile("files/cache/external/" + filename):
                                            neuter(self.config["packagedir"] + filename, "files/cache/external/" + filename, self.config["public_ip"], self.config["dir_server_port"], False)
                                        f = open('files/cache/external/' + filename, 'rb')
                            else:
                                if isbeta:
                                    try:
                                        os.mkdir("files/cache/betav2")
                                    except OSError as error:
                                        self.log.debug(clientid + "Beta pkg dir already exists")
                                    if not os.path.isfile("files/cache/betav2/" + filename):
                                        neuter(self.config["packagedir"] + "betav2/" + filename, "files/cache/betav2/" + filename, self.config["server_ip"], self.config["dir_server_port"], True)
                                    f = open('files/cache/betav2/' + filename, 'rb')
                                else:
                                    if not os.path.isfile("files/cache/" + filename):
                                        neuter(self.config["packagedir"] + filename, "files/cache/" + filename, self.config["server_ip"], self.config["dir_server_port"], True)
                                    f = open('files/cache/' + filename, 'rb')

                            file = f.read()
                            f.close()

                            reply = struct.pack('>LL', len(file), len(file))

                            if isbeta:
                                client_socket.send(reply)
                                client_socket.send(file, False)
                                break
                            else:
                                client_socket.send(reply)
                                # server_socket.send(file, False)

                                for i in range(0, len(file), 0x500):
                                    chunk = file[i:i + 0x500]
                                    client_socket.send(chunk, False)
                                # FIXME is this required for non-beta?
                                # break
                    else:
                        self.log.warning(clientid + "1 Invalid Command: " + str(command))
            # 2003 beta client?
            elif msg == b"\x00\x00\x00\x07":
                self.log.info(clientid + "CDDB mode entered")
                client_socket.send(b"\x01")
                while True:
                    msg = client_socket.recv_withlen()

                    if not msg:
                        self.log.info(clientid + "no message received")
                        break

                    if len(msg) == 10:
                        client_socket.send(b"\x01")
                        break

                    command = struct.unpack(">B", msg[:1])[0]
                    # SEND CDR
                    if command == 2:

                        blob = cdr_manipulator.read_blob(islan)

                        checksum = SHA.new(blob).digest()

                        if checksum == msg[1:]:
                            self.log.info(clientid + "Client has matching checksum for secondblob")
                            self.log.debug(clientid + "We validate it: " + binascii.b2a_hex(msg[1:]).decode())

                            client_socket.send(b"\x00\x00\x00\x00")

                        else:
                            self.log.info(clientid + "Client didn't match our checksum for secondblob")
                            self.log.debug(clientid + "Sending new blob: " + binascii.b2a_hex(msg[1:]).decode())

                            client_socket.send_withlen(blob, False)

                    else:
                        self.log.warning(clientid + "Unknown command: " + str(msg[0:1]))
            else:
                self.log.warning("2 Invalid Command: " + binascii.b2a_hex(msg).decode())
        except Exception as e:
            traceback.print_exc()
            self.log.error(f"{clientid}An error occurred: {e}")
            tb = sys.exc_info()[2]  # Get the original traceback
            self.log.error(''.join(traceback.format_tb(tb)))  # Logs traceback up to this point
            raise e.with_traceback(tb)  # Re-raise with the original traceback
        finally:
            client_socket.close()
            self.log.info(clientid + "Disconnected from Client Update Server")