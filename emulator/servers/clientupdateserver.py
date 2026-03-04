import sys
import traceback
import binascii
import os
import os.path
from Crypto.Hash import SHA
import threading
import globalvars
import utilities.blobs
import utilities.encryption
import utils
from servers.managers.contentlistmanager import manager
from servers.managers.contentserverlist_utilities import send_removal, heartbeat_thread
from utilities import cdr_manipulator
from utilities.manifests import *
from utilities.networkhandler import TCPNetworkHandler
from utilities.neuter import neuter
from utilities.custom_neuter_tracker import validate_and_update_cached_pkg, extract_pkg_info, check_configs_if_needed

cusConnectionCount = 0


def _validate_pkg_cache(cache_path, filename):
    """
    Validate and update cached pkg file if needed.

    Checks for custom neuter config changes and mod_pkg changes,
    invalidating/updating the cache as necessary.

    Args:
        cache_path: Full path to the cached pkg file
        filename: The pkg filename (str or bytes)
    """
    # Check for custom neuter config changes (rate-limited, mtime-based)
    # This will invalidate affected caches if configs have changed
    check_configs_if_needed()

    pkg_type, version = extract_pkg_info(filename)
    if pkg_type and version:
        validate_and_update_cached_pkg(cache_path, pkg_type, version)



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
            'server_id': self.secret_identifier,
            'wan_ip': server_ip,
            'lan_ip': globalvars.server_ip_b,
            'port': int(port),
            'region': globalvars.cs_region.encode('latin-1'),
            'cellid': globalvars.cellid,
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
                exc_info=(args.exc_type, args.exc_value, args.exc_traceback)
            )

        threading.excepthook = global_thread_exception_handler

        clientid = str(client_address) + ": "
        try:
            self.log.info(clientid + "Connected to Client Update Server")

            # Determine if client is on LAN
            islan = str(client_address[0]) in globalvars.server_network

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
                                    os.mkdir(os.path.join("files", "cache", "external"))
                                except OSError as error:
                                    self.log.debug(f"{clientid}External pkg dir already exists")

                                try:
                                    os.mkdir(os.path.join("files", "cache", "internal"))
                                except OSError as error:
                                    self.log.debug(f"{clientid}Internal pkg dir already exists")

                                if isbeta:
                                    try:
                                        os.mkdir(os.path.join("files", "cache", "external", "betav2"))
                                    except OSError as error:
                                        self.log.debug(clientid + "External beta pkg dir already exists")
                                    try:
                                        os.mkdir(os.path.join("files", "cache", "internal", "betav2"))
                                    except OSError as error:
                                        self.log.debug(clientid + "Internal beta pkg dir already exists")

                                    if islan:
                                        internal_beta = os.path.join("files", "cache", "internal", "betav2", newfilename)
                                        _validate_pkg_cache(internal_beta, newfilename)
                                        if not os.path.isfile(internal_beta):
                                            neuter(self.config["packagedir"] + "betav2/" + newfilename, internal_beta, self.config["server_ip"], self.config["dir_server_port"], True)
                                        f = open(internal_beta, 'rb')
                                    else:
                                        external_beta = os.path.join("files", "cache", "external", "betav2", newfilename)
                                        _validate_pkg_cache(external_beta, newfilename)
                                        if not os.path.isfile(external_beta):
                                            neuter(self.config["packagedir"] + "betav2/" + newfilename, external_beta, self.config["public_ip"], self.config["dir_server_port"], False)
                                        f = open(external_beta, 'rb')
                                else:
                                    if islan:
                                        internal_file = os.path.join("files", "cache", "internal", newfilename.decode())
                                        _validate_pkg_cache(internal_file, newfilename)
                                        if not os.path.isfile(internal_file):
                                            neuter(self.config["packagedir"] + newfilename.decode(), internal_file, self.config["server_ip"], self.config["dir_server_port"], True)
                                        f = open(internal_file, 'rb')
                                    else:
                                        external_file = os.path.join("files", "cache", "external", newfilename.decode())
                                        _validate_pkg_cache(external_file, newfilename)
                                        if not os.path.isfile(external_file):
                                            neuter(self.config["packagedir"] + newfilename.decode(), external_file, self.config["public_ip"], self.config["dir_server_port"], False)
                                        f = open(external_file, 'rb')
                            else:
                                if isbeta:
                                    try:
                                        os.mkdir(os.path.join("files", "cache", "betav2"))
                                    except OSError as error:
                                        self.log.debug(clientid + "Beta pkg dir already exists")
                                    beta_path = os.path.join("files", "cache", "betav2", newfilename)
                                    _validate_pkg_cache(beta_path, newfilename)
                                    if not os.path.isfile(beta_path):
                                        neuter(self.config["packagedir"] + "betav2/" + newfilename, beta_path, self.config["server_ip"], self.config["dir_server_port"], True)
                                    f = open(beta_path, 'rb')
                                else:
                                    cache_path = os.path.join("files", "cache", newfilename.decode())
                                    _validate_pkg_cache(cache_path, newfilename)
                                    if not os.path.isfile(cache_path):
                                        neuter(self.config["packagedir"] + newfilename.decode(), cache_path, self.config["server_ip"], self.config["dir_server_port"], True)
                                    f = open(cache_path, 'rb')

                            file = f.read()
                            f.close()

                            signature = utilities.encryption.rsa_sign_message(utilities.encryption.network_key, file)

                            reply = struct.pack('>LL', len(signature), len(signature)) + signature

                            client_socket.send(reply)
                        else:
                            filename = filename.decode('latin-1')

                            if self.config["public_ip"] != "0.0.0.0":
                                try:
                                    os.mkdir(os.path.join("files", "cache", "external"))
                                except OSError as error:
                                    self.log.debug(clientid + "External pkg dir already exists")

                                try:
                                    os.mkdir(os.path.join("files", "cache", "internal"))
                                except OSError as error:
                                    self.log.debug(clientid + "Internal pkg dir already exists")

                                if isbeta:
                                    try:
                                        os.mkdir(os.path.join("files", "cache", "external", "betav2"))
                                    except OSError as error:
                                        self.log.debug(clientid + "External beta pkg dir already exists")
                                    try:
                                        os.mkdir(os.path.join("files", "cache", "internal", "betav2"))
                                    except OSError as error:
                                        self.log.debug(clientid + "Internal beta pkg dir already exists")

                                    if islan:  # or globalvars.public_ip == str(client_address[0]):
                                        try:
                                            internal_beta = os.path.join("files", "cache", "internal", "betav2", filename)
                                            _validate_pkg_cache(internal_beta, filename)
                                            if not os.path.isfile(internal_beta):
                                                neuter(self.config["packagedir"] + "betav2/" + filename, internal_beta, self.config["server_ip"], self.config["dir_server_port"], True)
                                            f = open(internal_beta, 'rb')
                                        except:
                                            cache_internal = os.path.join("files", "cache", "internal", filename)
                                            _validate_pkg_cache(cache_internal, filename)
                                            if not os.path.isfile(cache_internal):
                                                neuter(self.config["packagedir"] + filename, cache_internal, self.config["server_ip"], self.config["dir_server_port"], False)
                                            f = open(cache_internal, 'rb')
                                    else:
                                        external_check_path = os.path.join("files", "cache", "external", filename)
                                        _validate_pkg_cache(external_check_path, filename)
                                        if not os.path.isfile(external_check_path):
                                            try:
                                                beta_ext = os.path.join("files", "cache", "external", "betav2", filename)
                                                _validate_pkg_cache(beta_ext, filename)
                                                if not os.path.isfile(beta_ext):
                                                    neuter(self.config["packagedir"] + "betav2/" + filename, beta_ext, self.config["public_ip"], self.config["dir_server_port"], False)
                                                f = open(beta_ext, 'rb')
                                            except:
                                                cache_external = os.path.join("files", "cache", "external", filename)
                                                _validate_pkg_cache(cache_external, filename)
                                                if not os.path.isfile(cache_external):
                                                    neuter(self.config["packagedir"] + filename, cache_external, self.config["public_ip"], self.config["dir_server_port"], False)
                                                f = open(cache_external, 'rb')
                                        else:
                                            f = open(external_check_path, 'rb')
                                else:
                                    if islan:
                                        internal_path = os.path.join("files", "cache", "internal", filename)
                                        _validate_pkg_cache(internal_path, filename)
                                        if not os.path.isfile(internal_path):
                                            neuter(self.config["packagedir"] + filename, internal_path, self.config["server_ip"], self.config["dir_server_port"], True)
                                        f = open(internal_path, 'rb')
                                    else:
                                        external_path = os.path.join("files", "cache", "external", filename)
                                        _validate_pkg_cache(external_path, filename)
                                        if not os.path.isfile(external_path):
                                            neuter(self.config["packagedir"] + filename, external_path, self.config["public_ip"], self.config["dir_server_port"], False)
                                        f = open(external_path, 'rb')
                            else:
                                if isbeta:
                                    try:
                                        os.mkdir(os.path.join("files", "cache", "betav2"))
                                    except OSError as error:
                                        self.log.debug(clientid + "Beta pkg dir already exists")
                                    beta_file = os.path.join("files", "cache", "betav2", filename)
                                    _validate_pkg_cache(beta_file, filename)
                                    if not os.path.isfile(beta_file):
                                        neuter(self.config["packagedir"] + "betav2/" + filename, beta_file, self.config["server_ip"], self.config["dir_server_port"], True)
                                    f = open(beta_file, 'rb')
                                else:
                                    cache_file = os.path.join("files", "cache", filename)
                                    _validate_pkg_cache(cache_file, filename)
                                    if not os.path.isfile(cache_file):
                                        neuter(self.config["packagedir"] + filename, cache_file, self.config["server_ip"], self.config["dir_server_port"], True)
                                    f = open(cache_file, 'rb')

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
