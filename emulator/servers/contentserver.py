import binascii
import hashlib
import hmac
import io
import os
import os.path
import pickle
import threading
import time  # Required for time.sleep()
import zlib
import fnmatch
import glob
from functools import lru_cache
from datetime import datetime

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import globalvars
import utils
from servers.managers.contentlistmanager import manager
from servers.managers.contentserverlist_utilities import heartbeat_thread, send_removal
from servers.managers.latency_manager import latencychecker
from utilities.ticket_utils import Steam2Ticket
from utilities import cdr_manipulator, encryption,  storages as stmstorages
from utilities.checksums import Checksum2, Checksum3, Checksum4, SDKChecksum
from utilities.manifests import *
from utilities.networkhandler import TCPNetworkHandler


app_list = []
csConnectionCount = 0

class FolderEventHandler(FileSystemEventHandler):
    def __init__(self, callback, debounce_time=2.0):
        """
        Initialize with a callback to handle file events and a debounce time.
        """
        self.callback = callback
        self.debounce_time = debounce_time
        self.event_lock = threading.Lock()
        self.timer = None

    def _debounced_callback(self):
        """
        Calls the provided callback after debounce time has passed.
        """
        with self.event_lock:
            self.timer = None
        self.callback()

    def _trigger_debounce(self):
        """
        Handles resetting the debounce timer and eventually triggering the callback.
        """
        with self.event_lock:
            if self.timer:
                self.timer.cancel()
            self.timer = threading.Timer(self.debounce_time, self._debounced_callback)
            self.timer.start()

    def on_any_event(self, event):
        """
        Trigger callback for relevant file events with debounce.
        """
        if not event.is_directory:
            self._trigger_debounce()


class contentserver(TCPNetworkHandler):

    def __init__(self, port, config):
        global app_list
        self.server_type = "ContentServer"
        super(contentserver, self).__init__(config, port, self.server_type)  # Create an instance of NetworkHandler

        if globalvars.public_ip == "0.0.0.0":
            self.server_ip = globalvars.server_ip_b
        else:
            self.server_ip = globalvars.public_ip_b

        self.config = config
        self.secret_identifier = utils.generate_unique_server_id()
        self.key = None
        self.applist = self.parse_manifest_files()
        self.port = int(port)
        self.stop_event = threading.Event()
        self.folder_file_map = {}
        self.url_len = 0
        self.url_enc = None

        self.contentserver_info = {
                'server_id':self.secret_identifier,
                'wan_ip':   self.server_ip,
                'lan_ip':   globalvars.server_ip_b,
                'port':     self.port,
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

        if globalvars.aio_server:
            self.start_folder_watcher()
            manager.add_contentserver_info(self.secret_identifier, self.server_ip, globalvars.server_ip, self.port,
                                           globalvars.cs_region, app_list, globalvars.cellid, True, False)
        else:
            self.thread = threading.Thread(target=heartbeat_thread, args=(self,))
            self.thread.daemon = True
            self.thread.start()

    def cleanup(self):
        """Content Server specific cleanup routine"""
        self.log.info(f"Cleaning up Content Server on port {self.port}")

        if not globalvars.aio_server:
            send_removal(self.secret_identifier)
        super().cleanup()

    def start_folder_watcher(self):
        # Start a thread for folder watching
        self.folder_watcher_thread = threading.Thread(target=self.folder_watcher)
        self.folder_watcher_thread.daemon = True
        self.folder_watcher_thread.start()

    def folder_watcher(self):
        folders_to_watch = [
            self.config['manifestdir'],
            self.config['v2manifestdir'],
            self.config['v3manifestdir2'],
            self.config['v4manifestdir'],
            self.config['steam2sdkdir']
        ]

        folders_to_watch = [folder for folder in folders_to_watch if folder and os.path.exists(folder)]

        if not folders_to_watch:
            return

        # Initialize the file map with the current state of the folders
        self.folder_file_map = {folder: set(os.listdir(folder)) for folder in folders_to_watch}

        def handle_change():
            """
            Checks for actual changes in each folder and triggers the callback if there are changes.
            """
            has_changes = False
            for folder in folders_to_watch:
                current_files = set(os.listdir(folder))
                if current_files != self.folder_file_map[folder]:
                    self.folder_file_map[folder] = current_files
                    has_changes = True

            if has_changes:
                self.applist = self.parse_manifest_files()
                manager.add_contentserver_info(
                    self.secret_identifier,
                    self.server_ip,
                    globalvars.server_ip,
                    self.port,
                    globalvars.cs_region,
                    app_list,
                    globalvars.cellid,
                    True,
                    False
                )

        # Initialize the event handler and observer
        event_handler = FolderEventHandler(callback=handle_change, debounce_time=2.0)
        observer = Observer()

        for folder in folders_to_watch:
            observer.schedule(event_handler, path=folder, recursive=False)

        observer.start()
        self.stop_event.wait()
        observer.stop()
        observer.join()

    def stop_folder_watcher(self):
        """Stop the folder watcher thread by setting the stop event."""
        self.stop_event.set()

    def _get_checksums_filename(self, storage, islan):
        app = storage.app
        version = storage.version
        suffix = "_lan" if islan else "_wan"
        cache_dir = os.path.join("files", "cache", f"{app}_{version}")

        # 1) Try cached checksums
        path = os.path.join(cache_dir, f"{app}_{version}{suffix}.checksums")
        if os.path.isfile(path):
            return path

        # 2) If cached manifest exists, use its checksums (dropping version in filename)
        manifest_path = os.path.join(cache_dir, f"{app}_{version}.manifest")
        if os.path.isfile(manifest_path):
            return os.path.join(cache_dir, f"{app}{suffix}.checksums")

        # 3) Fallback mappings: (manifest_dir, checksum_dir, manifest_suffix, checksum_suffix)
        mappings = [
            (self.config["manifestdir"],    self.config["storagedir"],  ".v4.manifest",  ".v4.checksums"),
            (self.config["v4manifestdir"],  self.config["v4storagedir"], ".manifest",     ".checksums"),
            (self.config["manifestdir"],    self.config["storagedir"],  ".v2.manifest",  ".v2.checksums"),
            (self.config["v2manifestdir"],  self.config["v2storagedir"], ".manifest",     ".checksums"),
            (self.config["manifestdir"],    self.config["storagedir"],  ".v3e.manifest", ".v3e.checksums"),
            (self.config["manifestdir"],    self.config["storagedir"],  ".v3.manifest",  ".v3.checksums"),
            (self.config["manifestdir"],    self.config["storagedir"],  ".manifest",     ".checksums"),
        ]
        for mdir, cdir, msuf, csuf in mappings:
            mf = os.path.join(mdir, f"{app}_{version}{msuf}")
            if os.path.isfile(mf):
                return os.path.join(cdir, f"{app}{csuf}")

        # 4) Special v3manifestdir2 case
        v3_dir = self.config.get("v3manifestdir2", "")
        if os.path.isdir(v3_dir):
            v3m = os.path.join(v3_dir, f"{app}_{version}.manifest")
            if os.path.isfile(v3m):
                return os.path.join(self.config["v3storagedir2"], f"{app}.checksums")
            else:
                raise FileNotFoundError(f"Manifest not found for {app} {version}")

        # 5) Nothing found?time to quit this nonsense
        raise FileNotFoundError(f"Checksums not found for {app} {version}")

    def _get_checksums_filename_beta(self, storage, islan):
        app = storage.app
        version = storage.version
        suffix = "_lan" if islan else "_wan"
        cache_dir = os.path.join("files", "cache", "beta", f"{app}_{version}")

        # 1) Try cached checksums
        path = os.path.join(cache_dir, f"{app}_{version}{suffix}.checksums")
        if os.path.isfile(path):
            return path

        # 3) Fallback mappings: (manifest_dir, checksum_dir, manifest_suffix, checksum_suffix)
        mappings = [
            (self.config["betamanifestdir"],    self.config["betastoragedir"],  ".manifest",  ".checksums"),
        ]
        for mdir, cdir, msuf, csuf in mappings:
            mf = os.path.join(mdir, f"{app}_{version}{msuf}")
            if os.path.isfile(mf):
                return os.path.join(cdir, f"{app}_{version}{csuf}")

        # 5) Nothing found?time to quit this nonsense
        raise FileNotFoundError(f"Checksums not found for {app} {version}")

    def _select_checksum(self, appid, version, islan):
        """Pick and return the right checksum object for given app/version."""
        suffix = "_lan" if islan else "_wan"
        cache_dir = os.path.join("files", "cache", f"{appid}_{version}")
        # Cached checksums
        checksum_file = os.path.join(cache_dir, f"{appid}_{version}{suffix}.checksums")
        if os.path.isfile(checksum_file):
            return Checksum2(appid, version, suffix, False)
        # v4 manifests Checksum4
        if os.path.isfile(os.path.join(self.config["manifestdir"], f"{appid}_{version}.v4.manifest")) \
        or os.path.isfile(os.path.join(self.config["v4manifestdir"], f"{appid}_{version}.manifest")):
            return Checksum4(appid)
        # v2 manifests Checksum3
        if os.path.isfile(os.path.join(self.config["manifestdir"], f"{appid}_{version}.v2.manifest")) \
        or os.path.isfile(os.path.join(self.config["v2manifestdir"], f"{appid}_{version}.manifest")):
            return Checksum3(appid)
        # v3e manifests Checksum2 with neutered flag
        if os.path.isfile(os.path.join(self.config["manifestdir"], f"{appid}_{version}.v3e.manifest")) \
        or os.path.isfile(os.path.join(self.config.get("v3manifestdir2", ""), f"{appid}_{version}.manifest")):
            return Checksum2(appid, version, suffix, True)
        # sdk storage (unneutered)
        #if os.path.isfile(os.path.join(self.config["steam2sdkdir"], f"{appid}_{version}.dat")):
        base = f"{appid}_{version}"
        directory = self.config["steam2sdkdir"]
        #patterns = [
        #    os.path.join(directory, f"{base}.dat"),
        #    os.path.join(directory, f"{base}_*.dat"),
        #]
        #if any(glob.glob(p) for p in patterns):
        found = False
        exact = os.path.join(directory, f"{base}.dat")
        if os.path.isfile(exact):
            return SDKChecksum((int(appid), int(version)))
        else:
            # only scan if exact file missing
            with os.scandir(directory) as it:
                found = any(
                    entry.is_file() and
                    entry.name.startswith(f"{base}_") and
                    entry.name.endswith(".dat")
                    for entry in it
                )
                if found: return SDKChecksum((int(appid), int(version)))
        # Fallback plain Checksum2
        return Checksum2(appid, version, suffix, False)

    def _build_file_map(self, manifest, checksum):
        """Return {fullFilename: node} for all valid nodes with updated checksums."""
        files = {}
        for node in manifest.nodes.values():
            if node.fileId != 0xffffffff:
                node.checksum = checksum.getchecksums_raw(node.fileId)
                files[node.fullFilename] = node
        return files

    def _compute_changed_files(self, files_old, files_new):
        """Return list of fileIds that were deleted or whose checksum changed."""
        changed = []
        for fname, old_node in files_old.items():
            new_node = files_new.get(fname)
            if new_node is None:
                changed.append(old_node.fileId)
                self.log.debug(f"Deleted file: {fname} : {old_node.fileId}")
            elif old_node.checksum != new_node.checksum:
                changed.append(old_node.fileId)
                self.log.debug(f"Changed file: {fname} : {old_node.fileId}")
        return changed

    def fix_manifest_checksum(self, manifest: bytes):
        """
        Zeroes out the old checksum, recalculates Adler32 over the
        zeroed-out blob, then reinserts fingerprint + new checksum.
        """
        fingerprint = manifest[0x30:0x34]
        oldchecksum = manifest[0x34:0x38]
        manifest = manifest[:0x30] + b"\x00" * 8 + manifest[0x38:]
        checksum = struct.pack("<I", zlib.adler32(manifest, 0))
        manifest = manifest[:0x30] + fingerprint + checksum + manifest[0x38:]
        self.log.debug(f"Checksum fixed from {binascii.b2a_hex(oldchecksum)} to {binascii.b2a_hex(checksum)}")

        return manifest, fingerprint

    def handle_client(self, client_socket, client_address):
        global csConnectionCount

        if str(client_address[0]) in globalvars.server_network:
            islan = True
            suffix = "_lan"
        else:
            islan = False
            suffix = "_wan"

        # Moved this out of the loop to improve preformance
        custom = self.config['enable_custom_banner'][0].lower() == 't'
        static_url = self.config['custom_banner_url'] if custom \
                     else f"http://{globalvars.get_octal_ip(islan, False)}/platform/banner/random.php"
        self.url_len = len(static_url)
        self.url_enc = static_url.encode("latin-1")

        clientid = str(client_address) + ": "
        self.log.info(f"{clientid}Connected to Content Server")

        msg = client_socket.recv(4)
        csConnectionCount += 1

        self.log.debug(f"{clientid}Content server version: {msg}")

        if len(msg) == 0:
            self.log.info(f"{clientid}Got simple handshake. Closing connection.")

        # BETA 1 VERSION 0 & BETA1 VERSION 1
        elif msg in [b"\x00\x00\x00\x00", b"\x00\x00\x00\x01"]:
            self.log.info(f"{clientid}Beta 2002 Storage mode entered")

            storagesopen = 0
            storages = {}

            client_socket.send(b"\x01")  # this should just be the handshake

            if globalvars.steam_ver == 1:
                is_short = False
            else:
                is_short = True

            is_beta1 = is_short

            command = client_socket.recv_withlen(is_short = is_short)

            if command[0:1] == b"\x00":
                message = command[1:]
                connid, messageid, app, version = struct.unpack_from(">IIII", message, 0)

                app, version = struct.unpack_from(">II", message, 0)
                appName = globalvars.CDR_obj.get_app_name(app)

                self.log.debug(f"{clientid}appid: {app} {appName}, verid: {version}")

                connid |= 0x80000000
                key = b"\x69" * 0x10
                if encryption.validate_mac(command[9:], key):
                    self.log.debug(clientid + repr(encryption.validate_mac(command[9:], key)))

                # TODO BEN, DO PROPER TICKET VALIDATION
                # bio = io.BytesIO(command[9:])
                # ticketsize, = struct.unpack_from(">H", bio.read(2), 0)
                # ticket = bio.read(ticketsize)
                # ptext = encryption.decrypt_message(bio.read()[:-20], key)

                self.log.info(f"{clientid}Opening application {appName} ID: {app} VER: {version}")
                try:
                    beta_dir = os.path.join(self.config["betastoragedir"], "beta1")
                    s = stmstorages.Storage(app, beta_dir, version)
                except Exception:
                    self.log.error("Application not installed! %s %d %d" % (appName, app, version))
                    reply = struct.pack(">B", 0)
                    client_socket.send(reply)
                    return

                storageid = storagesopen
                storagesopen += 1

                storages[storageid] = s
                storages[storageid].app = app
                storages[storageid].version = version

                manifest_file = os.path.join(self.config["betamanifestdir"], "beta1", f"{app}_{version}.manifest")
                if os.path.isfile(manifest_file):
                    f = open(manifest_file, "rb")
                    self.log.info(f"{clientid}{app}_{version} is a beta depot")
                else:
                    self.log.error(f"Manifest not found for {app} {version} ")
                    # reply = struct.pack(">LLc", connid, messageid, b"\x01")
                    client_socket.send(b"\x00")
                    return
                manifest = f.read()
                f.close()

                manifest_appid, manifest_verid = struct.unpack_from('<LL', manifest, 4)
                self.log.debug(f"{clientid}Manifest ID: {manifest_appid} Version: {manifest_verid}")

                if (int(manifest_appid) != int(app)) or (int(manifest_verid) != int(version)):
                    self.log.error(f"Manifest doesn't match requested file: ({app}, {version}) ({manifest_appid}, {manifest_verid})")
                    # reply = struct.pack(">LLc", connid, messageid, b"\x01")
                    client_socket.send(b"\x00")
                    return

                manifest, fingerprint = self.fix_manifest_checksum(manifest)
                self.log.debug("Checksum fixed")

                storages[storageid].manifest = manifest
                reply = b"\x66" + fingerprint[::-1]

                client_socket.send(reply, False)

                index_file = os.path.join(beta_dir, f"{app}_{version}.index")
                dat_file = os.path.join(beta_dir, f"{app}_{version}.dat")
                checksum_file = os.path.join(beta_dir, f"{app}_{version}.checksums")
                # Load the index
                with open(index_file, 'rb') as f:
                    index_data = pickle.load(f)
                try:
                    dat_file_handle.close()
                except:
                    pass
                dat_file_handle = open(dat_file, 'rb')
                checksum_file_handle = open(checksum_file, 'rb')
                checksumdata = checksum_file_handle.read()
                while True:
                    command = client_socket.recv(1, False)
                    if len(command) == 0:
                        self.log.info(f"{clientid}Disconnected from Content Server")
                        client_socket.close()
                        return

                    if command[0:1] == b"\x01":  # HANDSHAKE
                        client_socket.send(b"")
                        break

                    elif command[0:1] == b"\x02":  # SEND MANIFEST AGAIN
                        self.log.info(f"{clientid}Sending manifest")
                        client_socket.send(b"\x01" + struct.pack(">I", len(manifest)) + manifest, False)

                    elif command[0:1] == b"\x03":  # SEND UPDATE INFO
                        self.log.info(f"{clientid}Sending app update information")
                        oldversion = struct.unpack(">I", client_socket.recv(4, True))[0]
                        manifest_file = os.path.join(self.config["betamanifestdir"], "beta1", f"{app}_{oldversion}.manifest")
                        if os.path.isfile(manifest_file):
                            with open(manifest_file, "rb") as f:
                                manifest = f.read()
                            self.log.info(f"{clientid}{app}_{oldversion} is a beta depot")
                            client_socket.send(b"\x01" + struct.pack(">I", len(manifest)) + manifest, False)
                        else:
                            self.log.error(f"Manifest not found for {app} {oldversion} ")
                            # reply = struct.pack(">LLc", connid, messageid, b"\x01")
                            client_socket.send(b"\x00")
                            return

                    elif command[0:1] == b"\x13":  # CLOSE STORAGE
                        storageid, messageid = struct.unpack_from(">xLL", command, 0)
                        del storages[storageid]
                        reply = struct.pack(">LLc", storageid, messageid, b"\x00")
                        self.log.info(f"{clientid}Closing down storage {storageid}")
                        client_socket.send(reply)

                    elif command[0:1] == b"\x04":  # SEND CHECKSUM
                        self.log.info(f"{clientid}Sending checksum for {appName} ID: {app}  Version: {version}")
                        client_socket.send(b"\x01" + struct.pack(">I", len(checksumdata)) + checksumdata)

                    elif command[0:1] == b"\x05":  # SEND DATA
                        msg = client_socket.recv(12, False)
                        fileid, offset, length = struct.unpack_from(">III", msg, 0)

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

        # \X02 FOR 2003 JAN BETA
        elif msg in [b"\x00\x00\x00\x02"]:
            self.log.info(f"{clientid}Beta Jan 2003 Storage mode entered")

            storagesopen = 0
            storages = {}

            client_socket.send(b"\x01")  # this should just be the handshake

            while True:

                command = client_socket.recv_withlen()

                if command[0:1] == b"\x00":  # SEND MANIFEST AND PROCESS RESPONSE
                    message  = command[1:]
                    connid, messageid, app, version = struct.unpack_from(">IIII", message, 0)

                    app, version = struct.unpack_from(">II", message, 0)
                    # print(connid, messageid, app, version)
                    # print(app)
                    # print(version)
                    appName = globalvars.CDR_obj.get_app_name(app)
                    self.log.debug(f"{clientid}appid: {app} {appName}, verid: {version}")

                    # bio = io.BytesIO(msg[9:])

                    # ticketsize, = struct.unpack_from(">H", bio.read(2), 0)
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
                    # ticketsize, = struct.unpack_from(">H", bio.read(2), 0)
                    # print(ticketsize)
                    # ticket = bio.read(ticketsize)
                    # print(binascii.b2a_hex(ticket))
                    # postticketdata = io.BytesIO(bio.read()[:-20])
                    # IV = postticketdata.read(16)
                    # print(len(IV))
                    # print(binascii.b2a_hex(IV))
                    # enclen = postticketdata.read(2)
                    # print(binascii.b2a_hex(enclen))
                    # print(struct.unpack_from(">H", enclen, 0)[0])
                    # enctext = postticketdata.read(struct.unpack_from(">H", enclen,0)[0])
                    # print(binascii.b2a_hex(enctext))
                    # ptext = utils.aes_decrypt(key, IV, enctext)
                    # print(binascii.b2a_hex(ptext))

                    self.log.info(f"{clientid}Opening application %s %d %d" % (appName, app, version))
                    # connid = pow(2,31) + connid

                    try:
                        s = stmstorages.Storage(app, self.config["storagedir"], version)
                    except Exception:
                        self.log.error(f"Application not installed! {appName} {app:d} {version:d}")

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

                    manifest_appid, manifest_verid = struct.unpack_from('<LL', manifest, 4)
                    self.log.debug(f"{clientid}Manifest ID: {manifest_appid} Version: {manifest_verid}")
                    if (int(manifest_appid) != int(app)) or (int(manifest_verid) != int(version)):
                        self.log.error(f"Manifest doesn't match requested file: ({app}, {version}) ({manifest_appid}, {manifest_verid})")

                        # reply = struct.pack(">LLc", connid, messageid, b"\x01")
                        client_socket.send(b"\x00")

                        break

                    manifest, fingerprint = self.fix_manifest_checksum(manifest)
                    self.log.debug("Checksum fixed")

                    storages[storageid].manifest = manifest

                    checksum = struct.unpack_from("<L", manifest, 0x30)[0]  # FIXED, possible bug source

                    # reply = struct.pack(">LLcLL", connid, messageid, b"\x00", storageid, checksum)
                    reply = b"\xff" + fingerprint[::-1]

                    client_socket.send(reply, False)

                    index_file = os.path.join(self.config["betastoragedir"], f"{app}_{version}.index")
                    dat_file = os.path.join(self.config["betastoragedir"], f"{app}_{version}.dat")

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

                        if command[0:1] in [b"\x02", b"\x04"]:  # SEND MANIFEST AGAIN

                            self.log.info(f"{clientid}Sending manifest")

                            # storageid, messageid = struct.unpack_from(">xLL", commanf, 0)

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

                            storageid, messageid = struct.unpack_from(">xLL", command, 0)

                            del storages[storageid]

                            reply = struct.pack(">LLc", storageid, messageid, b"\x00")

                            self.log.info(f"{clientid}Closing down storage {storageid}")

                            client_socket.send(reply)

                        elif command[0:1] == b"\x05":  # SEND DATA
                            msg = client_socket.recv(12, False)
                            fileid, offset, length = struct.unpack_from(">III", msg, 0)
                            index_file = os.path.join(self.config["betastoragedir"], f"{app}_{version}.index")
                            dat_file = os.path.join(self.config["betastoragedir"], f"{app}_{version}.dat")
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
                                    url = ("http://" + globalvars.get_octal_ip(islan, False) + "/platform/banner/random.php")

                                reply = struct.pack(">H", len(url)) + url.encode("latin-1")

                                client_socket.send(reply)

                        elif command[0:1] == b"\x07":  # SEND DATA

                            storageid, messageid, fileid, filepart, numparts, priority = struct.unpack_from(">xLLLLLB", command, 0)

                            chunks, filemode = storages[storageid].readchunks(fileid, filepart, numparts)

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

        # \X04 FOR 2003 JUNE BETA
        elif msg in [b"\x00\x00\x00\x04"]:

            self.log.info(f"{clientid}Beta June 2003 Storage mode entered")

            storagesopen = 0
            storages = {}

            client_socket.send(b"\x01")  # this should just be the handshake

            while True:

                command = client_socket.recv_withlen()
                # log.debug(f"{clientid}Content server command: {command[0:1]}")

                # BANNER
                if command[0:1] == b"\x00":
                    if len(command)==10:
                        resp = b"\x01"
                    else:
                        resp = struct.pack(">cH", b"\x01", self.url_len) + self.url_enc
                    client_socket.send(resp)
                    if len(command)==10: break
                    continue

                elif command[0:1] == b"\x01":  # REQUEST MANIFEST
                    connid, messageid, app, version = struct.unpack_from(">IIII", command, 1)
                    appName = globalvars.CDR_obj.get_app_name(app)
                    appNameIDStr = f"{appName} ({str(app)})"

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
                    ticketsize, = struct.unpack_from(">H", bio.read(2), 0)
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
                        s = stmstorages.StorageBeta(app, self.config["betastoragedir"], version)
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

                    cache_manifest = os.path.join(
                        "files",
                        "cache",
                        "beta",
                        f"{app}_{version}",
                        f"{app}_{version}.manifest",
                    )
                    if os.path.isfile(cache_manifest):
                        f = open(cache_manifest, "rb")
                        self.log.info(clientid + str(app) + "_" + str(version) + " is a cached depot")
                    elif os.path.isfile(self.config["betamanifestdir"] + str(app) + "_" + str(version) + ".manifest"):
                        f = open(self.config["betamanifestdir"] + str(app) + "_" + str(version) + ".manifest", "rb")
                        self.log.info(clientid + str(app) + "_" + str(version) + " is a beta depot")
                    else:
                        self.log.error(f"Manifest not found for {app} {version} ")
                        # reply = struct.pack(">LLc", connid, messageid, b"\x01")
                        reply = struct.pack(">LLc", connid & 0xFFFFFFFF, messageid & 0xFFFFFFFF, b'\x01')
                        client_socket.send(reply)
                        break


                    manifest = f.read()
                    f.close()

                    manifest_appid, manifest_verid = struct.unpack_from('<LL', manifest, 4)
                    self.log.debug(f"{clientid}Manifest ID: {manifest_appid} Version: {manifest_verid}")
                    if (int(manifest_appid) != int(app)) or (int(manifest_verid) != int(version)):
                        self.log.error(f"Manifest doesn't match requested file: ({app}, {version}) ({manifest_appid}, {manifest_verid})")

                        # reply = struct.pack(">LLc", connid, messageid, b"\x01")
                        reply = struct.pack(">LLc", connid & 0xFFFFFFFF, messageid & 0xFFFFFFFF, b'\x01')
                        client_socket.send(reply)

                        break

                    manifest, _ = self.fix_manifest_checksum(manifest)
                    self.log.debug("Checksum fixed")

                    storages[storageid].manifest = manifest

                    checksum = struct.unpack_from("<L", manifest, 0x30)[0]  # FIXED, possible bug source

                    reply = struct.pack(">LLcLL", connid, messageid, b"\x00", storageid, checksum)

                    client_socket.send(reply, False)

                elif command[0:1] == b"\x02":  # CLOSE STORAGE

                    storageid, messageid = struct.unpack_from(">xLL", command, 0)

                    del storages[storageid]

                    reply = struct.pack(">LLc", storageid, messageid, b"\x00")

                    self.log.info(f"{clientid}Closing down storage %d" % storageid)

                    client_socket.send(reply)

                elif command[0:1] == b"\x03":  # SEND MANIFEST

                    self.log.info(f"{clientid}Sending manifest")

                    storageid, messageid = struct.unpack_from(">xLL", command, 0)

                    manifest = storages[storageid].manifest

                    reply = struct.pack(">LLcL", storageid, messageid, b"\x00", len(manifest))

                    client_socket.send(reply)

                    reply = struct.pack(">LLL", storageid, messageid, len(manifest))

                    client_socket.send(reply + manifest, False)

                elif command[0:1] == b"\x04":  # SEND UPDATE INFO
                    self.log.info(f"{clientid}Sending app update information")
                    storageid, messageid, oldversion = struct.unpack_from(">xLLL", command, 0)
                    appid = storages[storageid].app
                    version = storages[storageid].version
                    self.log.info(f"Old depot id {str(appid)} version {str(oldversion)}")
                    self.log.info(f"New depot id {str(appid)} version {str(version)}")
                    # Load manifests
                    manifest_old = Manifest2(appid, oldversion)
                    manifest_new = Manifest2(appid, version)

                    # Select checksums
                    checksum_old = self._select_checksum(appid, oldversion, islan)
                    checksum_new = self._select_checksum(appid, version,   islan)

                    # Build filename?node maps
                    files_old = self._build_file_map(manifest_old, checksum_old)
                    files_new = self._build_file_map(manifest_new, checksum_new)

                    # Free memory early (because your code is already big enough)
                    del manifest_old, manifest_new

                    # Figure out what changed
                    changed_files = self._compute_changed_files(files_old, files_new)
                    count = len(changed_files)
                    self.log.info(f"Number of changed files: {count}")

                    # Reply
                    if count == 0:
                        reply = struct.pack(">LLcL", storageid, messageid, b"\x01", 0)
                        client_socket.send(reply)
                        return

                    # Tell client how many updates to expect
                    header = struct.pack(">LLcL", storageid, messageid, b"\x02", count)
                    client_socket.send(header)

                    # Send list of changed file IDs
                    updatefiles = b"".join(struct.pack("<L", fid) for fid in changed_files)
                    client_socket.send(struct.pack(">LL", storageid, messageid))
                    client_socket.send_withlen(updatefiles)

                elif command[0:1] == b"\x05":  # SEND CHECKSUMS
                    self.log.info(f"{clientid}Sending checksums")

                    # unpack once, instead of in every branch
                    storageid, messageid = struct.unpack_from(">xLL", command, 0)
                    storage = storages[storageid]

                    try:
                        filename = self._get_checksums_filename_beta(storage, islan)
                    except FileNotFoundError as e:
                        self.log.error(str(e))
                        reply = struct.pack(">LLc", connid, messageid, b"\x01")
                        client_socket.send(reply)
                        break  # exit early?no more of your broken chains

                    # read-and-sign in a context manager (fewer brain aneurysms)
                    with open(filename, "rb") as f:
                        data = f.read()

                    # rip out the ancient signature and slap on a fresh one
                    payload = data[:-128]
                    signature = encryption.rsa_sign_message(encryption.network_key, payload)
                    payload += signature

                    # send the OK + length
                    header = struct.pack(">LLcL", storageid, messageid, b"\x00", len(payload))
                    client_socket.send(header)

                    # send the actual data
                    footer = struct.pack(">LLL", storageid, messageid, len(payload))
                    client_socket.send(footer + payload, False)

                elif command[0:1] == b"\x06":  # SEND DATA

                    storageid, messageid, fileid, filepart, numparts, priority = struct.unpack_from(">xLLLLLB", command, 0)

                    chunks, filemode = storages[storageid].readchunks(fileid, filepart, numparts)

                    reply = struct.pack(">LLcLL", storageid, messageid, b"\x00", len(chunks), filemode)

                    client_socket.send(reply, False)

                    for chunk in chunks:
                        reply = struct.pack(">LLL", storageid, messageid, len(chunk))

                        client_socket.send(reply, False)

                        reply = struct.pack(">LLL", storageid, messageid, len(chunk))

                        client_socket.send(reply, False)

                        client_socket.send(chunk, False)

                else:

                    self.log.warning(f"{binascii.b2a_hex(command[0:1])} - Invalid Command!")
                    client_socket.send(b"\x01")

                    break

        # \X05-\X06 FOR RELEASE CLIENTS
        elif (msg in [b"\x00\x00\x00\x05", b"\x00\x00\x00\x06"]) or (msg in [b"\x00\x00\x00\x07"] and globalvars.steamui_ver <= 20):
            self.log.info(f"{clientid}2003 Storage mode entered")

            storagesopen = 0
            storages = {}
            is_sdkdepot = False
            client_socket.send(b"\x01")  # this should just be the handshake

            while True:

                command = client_socket.recv_withlen()
                # log.debug(f"{clientid}Content server command: {command[0:1]}")

                # BANNER
                if command[0:1] == b"\x00":
                    if len(command)==10:
                        resp = b"\x01"
                    else:
                        resp = struct.pack(">cH", b"\x01", self.url_len) + self.url_enc
                    client_socket.send(resp)
                    if len(command)==10: break
                    continue

                elif command[0:1] == b"\x12":  # SEND MANIFEST
                    connid, messageid, app, version = struct.unpack_from(">IIII", command, 1)
                    appName = globalvars.CDR_obj.get_app_name(app)
                    appNameIDStr = f"{appName} ({str(app)})"

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
                    ticketsize, = struct.unpack_from(">H", bio.read(2), 0)
                    # print(ticketsize)
                    ticket = bio.read(ticketsize)
                    # print(binascii.b2a_hex(ticket))
                    postticketdata = bio.read()[:-20]
                    IV = postticketdata[0:16]
                    # print(len(IV))
                    # print(len(postticketdata))
                    ptext = encryption.aes_decrypt(key, IV, postticketdata[4:])
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

                    cache_manifest = os.path.join(
                        "files",
                        "cache",
                        f"{app}_{version}",
                        f"{app}_{version}.manifest",
                    )
                    if os.path.isfile(cache_manifest):
                        f = open(cache_manifest, "rb")
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
                        v3_path = os.path.join(self.config["v3manifestdir2"], f"{app}_{version}.manifest")
                        if os.path.isfile(v3_path):
                            f = open(v3_path, "rb")
                            self.log.info(f"{clientid}{app}_{version} is a v0.3 extra depot")
                        else:
                            self.log.error(f"Manifest not found for {app} {version} ")
                            # reply = struct.pack(">LLc", connid, messageid, b"\x01")
                            reply = struct.pack(">LLc", connid & 0xFFFFFFFF, messageid & 0xFFFFFFFF, b'\x01')
                            client_socket.send(reply)
                            break
                    else:
                        self.log.error(f"Manifest not found for {app} {version} ")
                        # reply = struct.pack(">LLc", connid, messageid, b"\x01")
                        reply = struct.pack(">LLc", connid & 0xFFFFFFFF, messageid & 0xFFFFFFFF, b'\x01')
                        client_socket.send(reply)
                        break


                    manifest = f.read()
                    f.close()

                    manifest_appid, manifest_verid = struct.unpack_from('<L', manifest, 4)
                    self.log.debug(f"{clientid}Manifest ID: {manifest_appid} Version: {manifest_verid}")
                    if (int(manifest_appid) != int(app)) or (int(manifest_verid) != int(version)):
                        self.log.error(f"Manifest doesn't match requested file: ({app}, {version}) ({manifest_appid}, {manifest_verid})")

                        reply = struct.pack(">LLc", connid, messageid, b"\x01")
                        client_socket.send(reply)

                        break

                    manifest, _ = self.fix_manifest_checksum(manifest)
                    self.log.debug("Checksum fixed")

                    storages[storageid].manifest = manifest

                    checksum = struct.unpack_from("<L", manifest, 0x30)[0]  # FIXED, possible bug source

                    reply = struct.pack(">LLcLL", connid, messageid, b"\x00", storageid, checksum)

                    client_socket.send(reply, False)

                elif command[0:1] == b"\x09" or command[0:1] == b"\x0a" or command[0:1] == b"\x02":  # REQUEST MANIFEST #09 is used by early clients without a ticket# 02 used by 2003 steam


                    connid, messageid, app, version = struct.unpack_from(">xLLLL", command, 0)
                    appName = globalvars.CDR_obj.get_app_name(app)
                    appNameIDStr = f"{appName} ({str(app)})"

                    self.log.info(f"{clientid}Opening application {appName} ID: {app} Ver: {version}")
                    connid = pow(2, 31) + connid
                    if command[0:1] == b"\x0a":
                        self.log.info(f"{clientid}Login packet used\n ticket packet {command[1:]}")
                        real_ticket = command[19:]
                        # Ensure the ticket is real, otherwise it is probably cftoolkit trying to download apps
                        # FIXME: the 2010 client does not seem to re-authenticate to get a refreshed ticket when it is rejected...
                        if len(real_ticket) > 70:
                            ticket = Steam2Ticket(real_ticket)
                            print(ticket)

                            if ticket.is_expired:
                                self.log.error(clientid + "Not logged in")
                                # FIXME temporary hack for 2010 clients until i figure out why the client wont reauth when the cs rejects the ticket
                                reply = struct.pack(">LLc", connid, messageid, b"\x00")  # b"\x01")
                                client_socket.send(reply)
                                break

                            # Validate the expiration time in the ticket
                            if ticket.sessionToken:
                                from utilities.database.cmdb import cm_dbdriver
                                database = cm_dbdriver(config)
                                # TODO check steamid in appownership ticket against the userid associated with the username and pw digest
                                if not database.insertUFSSessionToken(ticket.username_str, ticket.password_digest_hex, ticket.sessionToken):
                                    self.log.warning(clientid + "User Tried using an invalid password/username combination in their ticket!")
                                    # FIXME temporary hack for 2010 clients until i figure out why the client wont reauth when the cs rejects the ticket
                                    reply = struct.pack(">LLc", connid, messageid, b"\x00")  # b"\x01")
                                    client_socket.send(reply)
                                    break

                    # SDK_DEPOT - Check to make sure there's no app in existing storage, if there is, use that instead as appids shouldn't be reused in custom depots
                    
                    is_sdkdepot = True

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

                    for base_dir, manifestpath, message in manifest_dirs:
                        file_path = os.path.join(base_dir, manifestpath)
                        if os.path.isfile(file_path): is_sdkdepot = False

                    if is_sdkdepot:
                        sdk_path = steam2_sdk_utils.find_blob_file(app, version)
                        if not sdk_path:
                            self.log.error(f"Application not installed! {appName} ID: {app} Ver: {version}")
                            break
                            
                        manifest_class = SDKManifest(app, version, sdk_path)

                        self.log.info(f"{clientid}Application {appNameIDStr} v{version} is a SDK Depot")
                        manifest = manifest_class.manifestData

                        s = stmstorages.Steam2Storage(app, self.config["storagedir"], version, islan)
                    else:
                        try:
                            s = stmstorages.Storage(app, self.config["storagedir"], version, islan)
                        except Exception:
                            self.log.error(f"Application not installed! {appName} ID: {app} Ver: {version}")

                            reply = struct.pack(">LLc", connid, messageid, b"\x01")
                            client_socket.send(reply)

                            break

                    storageid = storagesopen
                    storagesopen += 1

                    storages[storageid] = s
                    storages[storageid].app = app
                    storages[storageid].version = version

                    if not is_sdkdepot:
                        f = None
                        manifest = None
                        for base_dir, manifestpath, message in manifest_dirs:
                            file_path = os.path.join(base_dir, manifestpath)
                            # print(file_path)
                            if os.path.isfile(file_path):

                                with open(file_path, "rb") as f:
                                    self.log.info(f"{clientid}{app}_{version} {message}")
                                    manifest = f.read()

                        if manifest == None:
                            self.log.error(f"Manifest not found for {app} {version} ")
                            # reply = struct.pack(">LLc", connid, messageid, b"\x01")
                            reply = struct.pack(">LLc", connid & 0xFFFFFFFF, messageid & 0xFFFFFFFF, b'\x01')
                            client_socket.send(reply)
                            break

                        manifest_appid, manifest_verid = struct.unpack_from('<LL', manifest, 4)
                        self.log.debug(clientid + (f"Manifest ID: {manifest_appid} Version: {manifest_verid}"))
                        if (int(manifest_appid) != int(app)) or (int(manifest_verid) != int(version)):
                            self.log.error(f"Manifest doesn't match requested file: ({app}, {version}) ({manifest_appid}, {manifest_verid})")

                            # reply = struct.pack(">LLc", connid, messageid, b"\x01")
                            reply = struct.pack(">LLc", connid & 0xFFFFFFFF, messageid & 0xFFFFFFFF, b'\x01')
                            client_socket.send(reply)

                            break

                        manifest, _ = self.fix_manifest_checksum(manifest)
                        self.log.debug("Checksum fixed")

                    storages[storageid].manifest = manifest

                    checksum = struct.unpack_from("<L", manifest, 0x30)[0]  # FIXED, possible bug source

                    reply = struct.pack(">LLcLL", connid, messageid, b"\x00", storageid, checksum)

                    client_socket.send(reply, False)

                elif command[0:1] == b"\x01":  # HANDSHAKE

                    client_socket.send(b"")
                    break

                elif command[0:1] == b"\x02":  # SEND CDR
                    while globalvars.compiling_cdr:
                        time.sleep(1)

                    blob = cdr_manipulator.read_blob(islan)

                    self.log.debug(clientid + "Sending new blob: " + binascii.b2a_hex(command).decode())

                    client_socket.send_withlen(blob, False)

                elif command[0:1] == b"\x03":  # CLOSE STORAGE

                    storageid, messageid = struct.unpack_from(">xLL", command, 0)

                    del storages[storageid]

                    reply = struct.pack(">LLc", storageid, messageid, b"\x00")

                    self.log.info(f"{clientid}Closing down storage %d" % storageid)

                    client_socket.send(reply)

                elif command[0:1] == b"\x04":  # SEND MANIFEST

                    self.log.info(f"{clientid}Sending manifest")

                    storageid, messageid = struct.unpack_from(">xLL", command, 0)

                    manifest = storages[storageid].manifest

                    reply = struct.pack(">LLcL", storageid, messageid, b"\x00", len(manifest))

                    client_socket.send(reply)

                    reply = struct.pack(">LLL", storageid, messageid, len(manifest))

                    client_socket.send(reply + manifest, False)

                elif command[0:1] == b"\x05":  # SEND UPDATE INFO
                    self.log.info(f"{clientid}Sending app update information")
                    storageid, messageid, oldversion = struct.unpack_from(">xLLL", command, 0)
                    appid = storages[storageid].app
                    version = storages[storageid].version
                    self.log.info(f"Old depot id {str(appid)} version {str(oldversion)}")
                    self.log.info(f"New depot id {str(appid)} version {str(version)}")

                    #if steam2_sdk_utils.check_for_entry(appid, version):
                    if is_sdkdepot:
                        self.log.info(f"{clientid}Sending app update from SDK Depot Files")
                        is_sdkdepot = True
                        manifest_class_new = SDKManifest(appid, version)
                        manifest_class_old = SDKManifest(appid, oldversion)
                        # self.log.info(f"{clientid}Application {app} v{version} is a SDK Depot")
                        manifest_new = manifest_class_new
                        manifest_old = manifest_class_old

                        checksum_new = SDKChecksum((int(appid), int(version)))
                        checksum_old = SDKChecksum((int(appid), int(oldversion)))
                    else:
                        # Load manifests
                        manifest_old = Manifest2(appid, oldversion)
                        manifest_new = Manifest2(appid, version)

                        # Select checksums
                        checksum_old = self._select_checksum(appid, oldversion, islan)
                        checksum_new = self._select_checksum(appid, version,   islan)

                    # Build filename node maps
                    files_old = self._build_file_map(manifest_old, checksum_old)
                    files_new = self._build_file_map(manifest_new, checksum_new)

                    # Free memory early (because your code is already big enough)
                    del manifest_old, manifest_new

                    # Figure out what changed
                    changed_files = self._compute_changed_files(files_old, files_new)
                    count = len(changed_files)
                    self.log.info(f"Number of changed files: {count}")

                    # Reply
                    if count == 0:
                        reply = struct.pack(">LLcL", storageid, messageid, b"\x01", 0)
                        client_socket.send(reply)
                        return

                    # Tell client how many updates to expect
                    header = struct.pack(">LLcL", storageid, messageid, b"\x02", count)
                    client_socket.send(header)

                    # Send list of changed file IDs
                    updatefiles = b"".join(struct.pack("<L", fid) for fid in changed_files)
                    client_socket.send(struct.pack(">LL", storageid, messageid))
                    client_socket.send_withlen(updatefiles)

                elif command[0:1] == b"\x06":  # SEND CHECKSUMS
                    # unpack once, instead of in every branch
                    storageid, messageid = struct.unpack_from(">xLL", command, 0)
                    app, ver = storages[storageid].app, storages[storageid].version
                    neuteredCachePath = os.path.join("files", "cache", f"{app}_{ver}")
                    checksum_path = os.path.join(neuteredCachePath, f"{app}_{ver}{suffix}.checksums")
                    storage = storages[storageid]

                    if is_sdkdepot: # not os.path.isfile(checksum_path) and steam2_sdk_utils.find_blob_file(app, ver):
                        self.log.info(f"{clientid}Sending checksums from SDK Depot")

                        #checksumsPath = neuteredCachePath + f"{app}_{ver}{suffix}.checksums"

                        #if (self.config['cache_sdk_depot_checksums'].lower()=="true"
                        #and os.path.isfile(checksumsPath)):
                        # 1) build the base .checksums
                        data = steam2_sdk_utils.extract_checksumbin(app, ver,
                                                                  neuteredCachePath, suffix)
                        """# 2) patch only the replaced chunks? CRCs
                        chk = bytearray(raw)
                        chk = steam2_sdk_utils.patch_checksums_for_neutered(chk,
                                                                            neuteredCachePath)
                        file = bytes(chk)
                        # 3) cache for next time
                        with open(checksumsPath,"wb") as f:
                            f.write(file)"""
                        #else:
                        #    file = steam2_sdk_utils.extract_checksumbin(storages[storageid].app, str(storages[storageid].version), neuteredCachePath, suffix)
                    else:
                        try:
                            filename = self._get_checksums_filename(storage, islan)
                        except FileNotFoundError as e:
                            self.log.error(str(e))
                            reply = struct.pack(">LLc", connid, messageid, b"\x01")
                            client_socket.send(reply)
                            break  # exit early?no more of your broken chains

                        # read-and-sign in a context manager (fewer brain aneurysms)
                        with open(filename, "rb") as f:
                            data = f.read()

                    # rip out the ancient signature and slap on a fresh one
                    payload = data[:-128]
                    signature = encryption.rsa_sign_message(encryption.network_key, payload)
                    payload += signature

                    # send the OK + length
                    header = struct.pack(">LLcL", storageid, messageid, b"\x00", len(payload))
                    client_socket.send(header)

                    # send the actual data
                    footer = struct.pack(">LLL", storageid, messageid, len(payload))
                    client_socket.send(footer + payload, False)

                elif command[0:1] == b"\x07":  # SEND DATA

                    storageid, messageid, fileid, filepart, numparts, priority = struct.unpack_from(">xLLLLLB", command, 0)

                    chunks, filemode = storages[storageid].readchunks(fileid, filepart, numparts)

                    reply = struct.pack(">LLcLL", storageid, messageid, b"\x00", len(chunks), filemode)

                    client_socket.send(reply, False)

                    for chunk in chunks:
                        reply = struct.pack(">LLL", storageid, messageid, len(chunk))

                        client_socket.send(reply, False)

                        reply = struct.pack(">LLL", storageid, messageid, len(chunk))

                        client_socket.send(reply, False)

                        client_socket.send(chunk, False)

                elif command[0:1] == b"\xff":  # SEND AVAILABLE CONTENT LIST
                    buffer = bytearray()
                    count = 0
                    # Loop through the app_list and append each app_id and version to the buffer
                    for app_id, version in app_list:
                        count += 1
                        # Pack app_id and version as unsigned 32-bit integers and append to buffer
                        buffer.extend(struct.pack('<II', app_id, version))  # '<II' is for 2 little-endian 32-bit ints

                    byte_string = struct.pack("<I", count) + bytes(buffer)
                    client_socket.send(byte_string)

                elif command[0:1] == b"\x62":  # SEND STORAGE VERSION FOR NEUTERING
                    self.log.info(f"{clientid}Sending storage version")

                    (storageid, messageid) = struct.unpack(">xLL", command)
                    if os.path.isfile(self.config["steam2sdkdir"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".blob"):
                        reply = struct.pack(">LLc", storageid, messageid, b"\x03")
                    elif os.path.isfile(self.config["manifestdir"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".v4.manifest"):
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
                            # reply = struct.pack(">LLc", storageid, messageid, b"\x00")
                            reply = struct.pack(">LLc", connid & 0xFFFFFFFF, messageid & 0xFFFFFFFF, b'\x01')
                            client_socket.send(reply)
                            break
                    else:
                        self.log.error(f"Manifest not found for {app} ")
                        # reply = struct.pack(">LLc", storageid, messageid, b"\x00")
                        reply = struct.pack(">LLc", connid & 0xFFFFFFFF, messageid & 0xFFFFFFFF, b'\x01')
                        client_socket.send(reply)
                        break

                    client_socket.send(reply)

                elif command[0:1] == b"\x63":  # SEND INDEX FOR NEUTERING
                    self.log.info(f"{clientid}Sending index")

                    (storageid, messageid) = struct.unpack_from(">xLL", command, 0)
                    # FIXME add sdk depot index parsing method for this part
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

                else:

                    self.log.warning(f"{binascii.b2a_hex(command[0:1])} - Invalid Command!")
                    client_socket.send(b"\x01")

                    break

        # \X07 FOR 2004+ - REENABLED
        elif msg == b"\x00\x00\x00\x07":
            self.log.info(f"{clientid}2004 Storage mode entered")

            storagesopen = 0
            storages = {}
            is_sdkdepot = False
            client_socket.send(b"\x01")  # this should just be the handshake

            while True:

                command = client_socket.recv_withlen()
                # log.debug(f"{clientid}Content server command: {command[0:1]}")

                # BANNER
                if command[0:1] == b"\x00":
                    if len(command)==10:
                        resp = b"\x01"
                    elif len(command)>1:
                        resp = struct.pack(">cH", b"\x01", self.url_len) + self.url_enc
                    else:
                        resp = b""
                    client_socket.send(resp)
                    if len(command)==10: break


                # REQUEST MANIFEST #09 is used by clients without a ticket #0A is used by clients with a ticket
                elif command[0:1] == b"\x09" or command[0:1] == b"\x0a":
                    connid, messageid, app, version = struct.unpack_from(">xLLLL", command, 0)
                    connid = pow(2, 31) + connid

                    if command[0:1] == b"\x0a":
                        self.log.info(f"{clientid}Login packet used\n ticket packet {command[1:]}")
                        real_ticket = command[19:]
                        # Ensure the ticket is real, otherwise it is probably cftoolkit trying to download apps
                        # FIXME: the 2010 client does not seem to re-authenticate to get a refreshed ticket when it is rejected...
                        if len(real_ticket) > 70:
                            ticket = Steam2Ticket(real_ticket)
                            print(ticket)

                            if ticket.is_expired:
                                self.log.error(clientid + "Not logged in")
                                # FIXME temporary hack for 2010 clients until i figure out why the client wont reauth when the cs rejects the ticket
                                reply = struct.pack(">LLc", connid, messageid, b"\x00")  # b"\x01")
                                client_socket.send(reply)
                                break

                            # Validate the expiration time in the ticket
                            if ticket.sessionToken:
                                from utilities.database.cmdb import cm_dbdriver
                                database = cm_dbdriver(config)
                                # TODO check steamid in appownership ticket against the userid associated with the username and pw digest
                                if not database.insertUFSSessionToken(ticket.username_str, ticket.password_digest_hex, ticket.sessionToken):
                                    self.log.warning(clientid + "User Tried using an invalid password/username combination in their ticket!")
                                    # FIXME temporary hack for 2010 clients until i figure out why the client wont reauth when the cs rejects the ticket
                                    reply = struct.pack(">LLc", connid, messageid, b"\x00")  # b"\x01")
                                    client_socket.send(reply)
                                    break

                    appName = globalvars.CDR_obj.get_app_name(app)
                    appNameIDStr = f"{appName} ({str(app)})"

                    self.log.info(f"{clientid}Opening application {appName} ID: {app:d} VER: {version:d}")

                    # SDK_DEPOT - Check to make sure there's no app in existing storage, if there is, use that instead as appids shouldn't be reused in custom depots
                    year = ""
                    current = datetime.strptime(globalvars.CDDB_datetime, "%m/%d/%Y %H:%M:%S")

                    is_sdkdepot = True

                    manifest_dirs = [
                            ("files/cache/", f"{str(app)}_{str(version)}/{str(app)}_{str(version)}.manifest", "is a cached depot"),
                            (self.config["manifestdir"], f"{str(app)}_{str(version)}.v4.manifest", "is a v0.4 depot"),
                            (self.config["manifestdir"], f"{str(app)}_{str(version)}.v2.manifest", "is a v0.2 depot"),
                            (self.config["manifestdir"], f"{str(app)}_{str(version)}{str(year)}.v3.manifest", "is a v0.3 depot"),
                            #(self.config["manifestdir"], f"{str(app)}_{str(version)}.v3.manifest", "is a v0.3 depot"),
                            (self.config["manifestdir"], f"{str(app)}_{str(version)}.v3e.manifest", "is a v0.3 extra depot"),
                            (self.config["v4manifestdir"], f"{str(app)}_{str(version)}.manifest", "is a v0.4 depot"),
                            (self.config["v2manifestdir"], f"{str(app)}_{str(version)}.manifest", "is a v0.2 depot"),
                            (self.config["manifestdir"], f"{str(app)}_{str(version)}.manifest", "is a v0.3 depot"),
                            (self.config["v3manifestdir2"], f"{str(app)}_{str(version)}.manifest", "is a v0.3 extra depot")]

                    if app == 261 and (datetime(2006, 10, 12) <= current < datetime(2006, 11, 6)):
                        year = "_2006"
                        is_sdkdepot = False
                    else:
                        for base_dir, manifestpath, message in manifest_dirs:
                            file_path = os.path.join(base_dir, manifestpath)
                            if os.path.isfile(file_path): is_sdkdepot = False

                        if is_sdkdepot:
                            sdk_path = steam2_sdk_utils.find_blob_file(app, version)
                            if not sdk_path:
                                self.log.error(f"Application not installed! {appName} ID: {app} Ver: {version}")
                                break
                            manifest_class = SDKManifest(app, version, sdk_path)

                            self.log.info(f"{clientid}Application {appNameIDStr} v{version} is a SDK Depot")
                            manifest = manifest_class.manifestData

                            s = stmstorages.Steam2Storage(app, self.config["storagedir"], version, islan)
                        else:
                            try:
                                s = stmstorages.Storage(app, self.config["storagedir"], version, islan)
                            except Exception:
                                self.log.error(f"Application not installed! {appName} {app:d} {version:d}")
                                reply = struct.pack(">LLc", connid, messageid, b"\x01")
                                client_socket.send(reply)
                                break

                    storageid = storagesopen
                    storagesopen += 1

                    storages[storageid] = s
                    storages[storageid].app = app
                    storages[storageid].version = version

                    if not is_sdkdepot:
                        f = None
                        manifest = None
                        for base_dir, manifestpath, message in manifest_dirs:
                            file_path = os.path.join(base_dir, manifestpath)
                            # print(file_path)
                            if os.path.isfile(file_path):
                                with open(file_path, "rb") as f:
                                    self.log.info(f"{clientid}{app}_{version} {message}")
                                    manifest = f.read()

                        if manifest == None:
                            self.log.error(f"Manifest not found for {app} {version} ")
                            # reply = struct.pack(">LLc", connid, messageid, b"\x01")
                            reply = struct.pack(">LLc", connid & 0xFFFFFFFF, messageid & 0xFFFFFFFF, b'\x01')
                            client_socket.send(reply)
                            break  # CLOSE CONNECT

                        manifest_appid, manifest_verid = struct.unpack_from('<LL', manifest, 4)
                        self.log.debug(clientid + (f"Manifest ID: {manifest_appid} Version: {manifest_verid}"))
                        if (int(manifest_appid) != int(app)) or (int(manifest_verid) != int(version)):
                            self.log.error(f"Manifest doesn't match requested file: ({app}, {version}) ({manifest_appid}, {manifest_verid})")
                            # reply = struct.pack(">LLc", connid, messageid, b"\x01")
                            reply = struct.pack(">LLc", connid & 0xFFFFFFFF, messageid & 0xFFFFFFFF, b'\x01')
                            client_socket.send(reply)
                            break

                        manifest, _ = self.fix_manifest_checksum(manifest)
                        self.log.debug("Checksum fixed")


                    storages[storageid].manifest = manifest

                    checksum = struct.unpack_from("<L", manifest, 0x30)[0]  # FIXED, possible bug source
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

                    storageid, messageid = struct.unpack_from(">xLL", command, 0)

                    del storages[storageid]

                    reply = struct.pack(">LLc", storageid, messageid, b"\x00")

                    self.log.info(f"{clientid}Closing down storage {storageid:d}")

                    client_socket.send(reply)
                # SEND MANIFEST
                elif command[0:1] == b"\x04":

                    self.log.info(f"{clientid}Sending manifest")

                    (storageid, messageid) = struct.unpack_from(">xLL", command, 0)

                    manifest = storages[storageid].manifest

                    reply = struct.pack(">LLcL", storageid, messageid, b"\x00", len(manifest))

                    client_socket.send(reply)

                    reply = struct.pack(">LLL", storageid, messageid, len(manifest))

                    client_socket.send(reply + manifest, False)
                # SEND UPDATE INFO
                elif command[0:1] == b"\x05":
                    self.log.info(f"{clientid}Sending app update information")
                    storageid, messageid, oldversion = struct.unpack_from(">xLLL", command, 0)
                    appid = storages[storageid].app
                    version = storages[storageid].version
                    # self.log.info("Old GCF version: " + str(appid) + "_" + str(oldversion) + f"New {appNameIDStr}  GCF version: {str(version)}")
                    self.log.info(f"Old depot id {str(appid)} version {str(oldversion)}")
                    self.log.info(f"New depot id {str(appid)} version {str(version)}")

                    #if steam2_sdk_utils.check_for_entry(appid, version):
                    if is_sdkdepot:
                        self.log.info(f"{clientid}Sending app update from SDK Depot Files")
                        is_sdkdepot = True
                        suffix = "_lan" if islan else "_wan"

                        cache_dir = os.path.join("files", "cache", f"{appid}_{version}")
                        cachedManifest_file = os.path.join(cache_dir, f"{appid}_{version}{suffix}.manifest")
                        if os.path.isfile(cachedManifest_file):
                            # neutered sdk storage found
                            manifest_new = Manifest2(appid, version)
                        else:
                            # NONneutered sdk storage found
                            manifest_new = SDKManifest(appid, version)

                        cacheOldVersion_dir = os.path.join("files", "cache", f"{appid}_{oldversion}")
                        cachedOldManifest_file = os.path.join(cacheOldVersion_dir, f"{appid}_{oldversion}{suffix}.manifest")
                        if os.path.isfile(cachedOldManifest_file):
                            # neutered sdk storage found
                            manifest_old = Manifest2(appid, oldversion)
                        else:
                            # NONneutered sdk storage found
                            manifest_old = SDKManifest(appid, oldversion)

                        # self.log.info(f"{clientid}Application {app} v{version} is a SDK Depot")
                        # checksum_new = SDKChecksum((int(appid), int(version)))
                        # checksum_old = SDKChecksum((int(appid), int(oldversion)))
                    else:
                        self.log.info(f"{clientid}Sending app update from Storage Files")
                        # Load manifests
                        manifest_old = Manifest2(appid, oldversion)
                        manifest_new = Manifest2(appid, version)

                        # Select checksums
                    checksum_old = self._select_checksum(appid, oldversion, islan)
                    checksum_new = self._select_checksum(appid, version,   islan)

                    # Build filename node maps
                    files_old = self._build_file_map(manifest_old, checksum_old)
                    files_new = self._build_file_map(manifest_new, checksum_new)

                    # Free memory early (because your code is already big enough)
                    del manifest_old, manifest_new

                    # Figure out what changed
                    changed_files = self._compute_changed_files(files_old, files_new)
                    count = len(changed_files)
                    self.log.info(f"Number of changed files: {count}")

                    # Reply
                    if count == 0:
                        reply = struct.pack(">LLcL", storageid, messageid, b"\x01", 0)
                        client_socket.send(reply)
                        break

                    # Tell client how many updates to expect
                    header = struct.pack(">LLcL", storageid, messageid, b"\x02", count)
                    client_socket.send(header)

                    # Send list of changed file IDs
                    updatefiles = b"".join(struct.pack("<L", fid) for fid in changed_files)
                    client_socket.send(struct.pack(">LL", storageid, messageid))
                    client_socket.send_withlen(updatefiles)
                # SEND CHECKSUMS
                elif command[0:1] == b"\x06":
                    storageid, messageid = struct.unpack_from(">xLL", command, 0)
                    app, version = storages[storageid].app, storages[storageid].version
                    current = datetime.strptime(globalvars.CDDB_datetime, "%m/%d/%Y %H:%M:%S")
                    year = ""
                    neuteredCachePath = os.path.join("files", "cache", f"{app}_{version}")
                    checksum_path = os.path.join(neuteredCachePath, f"{app}_{version}{suffix}.checksums")
                    if app == 261 and (datetime(2006, 10, 12) <= current < datetime(2006, 11, 6)):
                        year = "_2006"
                    if is_sdkdepot and not os.path.isfile(checksum_path): # and steam2_sdk_utils.find_blob_file(app, version) and year == "":
                        self.log.info(f"{clientid}Sending checksums from SDK Depot")

                        #checksumsPath = neuteredCachePath + f"{app}_{version}{suffix}.checksums"

                        #if (self.config['cache_sdk_depot_checksums'].lower()=="true"
                        #and os.path.isfile(checksumsPath)):
                        # 1) build the base .checksums
                        file = steam2_sdk_utils.extract_checksumbin(app, version,
                                                                  neuteredCachePath, suffix)
                        """# 2) patch only the replaced chunks? CRCs
                        chk = bytearray(raw)
                        chk = steam2_sdk_utils.patch_checksums_for_neutered(chk,
                                                                            neuteredCachePath)
                        file = bytes(chk)
                        # 3) cache for next time
                        with open(checksumsPath,"wb") as f:
                            f.write(file)"""
                        #else:
                        #    file = steam2_sdk_utils.extract_checksumbin(storages[storageid].app, str(storages[storageid].version), neuteredCachePath, suffix)
                    else:
                        self.log.info(f"{clientid}Sending checksums")
                        cache_base = os.path.join("files", "cache", f"{storages[storageid].app}_{storages[storageid].version}")
                        manifest_name = f"{storages[storageid].app}_{storages[storageid].version}.manifest"
                        checksums_name = f"{storages[storageid].app}_{storages[storageid].version}{suffix}.checksums"
                        manifest_path = os.path.join(cache_base, manifest_name)
                        checksums_path = os.path.join(cache_base, checksums_name)
                        if os.path.isfile(checksums_path):
                            filename = checksums_path
                        elif os.path.isfile(manifest_path):
                            filename = os.path.join(cache_base, f"{storages[storageid].app}{suffix}.checksums")
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
                        elif os.path.isfile(self.config["manifestdir"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + f"{year}.v3.manifest"):
                            filename = self.config["storagedir"] + str(storages[storageid].app) + f"{year}.v3.checksums"
                        elif os.path.isfile(self.config["manifestdir"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".manifest"):
                            filename = self.config["storagedir"] + str(storages[storageid].app) + ".checksums"
                        elif os.path.isdir(self.config["v3manifestdir2"]):
                            if os.path.isfile(self.config["v3manifestdir2"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".manifest"):
                                filename = self.config["v3storagedir2"] + str(storages[storageid].app) + ".checksums"
                            else:
                                self.log.error(f"Manifest not found for {app} {version} ")
                                # reply = struct.pack(">LLc", connid, messageid, b"\x01")
                                reply = struct.pack(">LLc", connid & 0xFFFFFFFF, messageid & 0xFFFFFFFF, b'\x01')
                                client_socket.send(reply)
                                break
                        else:
                            self.log.error(f"Checksums not found for {app} {version} ")
                            # reply = struct.pack(">LLc", connid, messageid, b"\x01")
                            reply = struct.pack(">LLc", connid & 0xFFFFFFFF, messageid & 0xFFFFFFFF, b'\x01')
                            client_socket.send(reply)
                            break

                        #f = open(filename, "rb")
                        #file = f.read()
                        #f.close()
                        with open(filename, "rb") as f:
                            file = f.read()

                    # hack to rip out old sig, insert new
                    file = file[0:-128]
                    signature = encryption.rsa_sign_message(encryption.network_key, file)
                    file += signature

                    # Send initial response with file size
                    reply = struct.pack(">LLcL", storageid, messageid, b"\x00", len(file))
                    client_socket.send(reply)

                    # Send file data
                    reply = struct.pack(">LLL", storageid, messageid, len(file))
                    client_socket.send(reply + file, False)
                # SEND DATA CHUNKS
                elif command[0:1] == b"\x07":

                    storageid, messageid, fileid, filepart, numparts, priority = struct.unpack_from(">xLLLLLB", command, 0)

                    chunks, filemode = storages[storageid].readchunks(fileid, filepart, numparts)

                    reply = struct.pack(">LLcLL", storageid, messageid, b"\x00", len(chunks), filemode)

                    client_socket.send(reply, False)

                    for chunk in chunks:

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
                    if os.path.isfile(self.config["steam2sdkdir"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".blob"):
                        reply = struct.pack(">LLc", storageid, messageid, b"\x03")
                    elif os.path.isfile(self.config["manifestdir"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".v4.manifest"):
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
                            # reply = struct.pack(">LLc", storageid, messageid, b"\x00")
                            reply = struct.pack(">LLc", connid & 0xFFFFFFFF, messageid & 0xFFFFFFFF, b'\x01')
                            client_socket.send(reply)
                            break
                    else:
                        self.log.error(f"Manifest not found for {app} ")
                        # reply = struct.pack(">LLc", storageid, messageid, b"\x00")
                        reply = struct.pack(">LLc", connid & 0xFFFFFFFF, messageid & 0xFFFFFFFF, b'\x01')
                        client_socket.send(reply)
                        break

                    client_socket.send(reply)
                # SEND INDEX FOR NEUTERING (99) UNUSED
                elif command[0:1] == b"\x63":
                    self.log.info(f"{clientid}Sending index")

                    (storageid, messageid) = struct.unpack_from(">xLL", command, 0)
                    # FIXME add sdk depot index parsing method for this part
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
        elif msg == b"\x66\x61\x23\x45":
            self.log.info(f"{clientid}Received a Latency Test Request From CSDS")
            client_socket.send(b"\x00") # OK

        else:
            self.log.warning(f"Invalid Command: {binascii.b2a_hex(msg)}")

        client_socket.close()
        self.log.info(f"{clientid}Disconnected from Content Server")

    def parse_manifest_files(self):
        # Define the locations to search for '.manifest' files
        cache_dir = os.path.join('files', 'cache')
        locations = [cache_dir, self.config["v4manifestdir"], self.config["v2manifestdir"],
                     self.config["manifestdir"], self.config["v3manifestdir2"], self.config["betamanifestdir"]]
        app_buffer = b""
        for location in locations:
            for file_name in os.listdir(location):
                if fnmatch.fnmatch(file_name, "*_????.v3.manifest"):
                    # Extract app ID and version from the file name
                    app_id, version, year = file_name.split('_')
                    version = version.split(".")[0]
                    # for appid, version in self.applist:
                    # print("appid:", app_id)
                    # print("version:", version)
                    # Append app ID and version to app_list in this format
                    app_buffer += str(app_id).encode('latin-1') + b"\x00" + str(version).encode('latin-1') + b"\x00\x00"
                    app_list.append((app_id, version))
                elif file_name.endswith('.v2.manifest') or file_name.endswith('.v3.manifest') or file_name.endswith('.v4.manifest') or file_name.endswith('.v3e.manifest'):
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
            steam2_sdk_utils.scan_directories(sdk_depot_dir, sdk_depot_dir)
            for file_name in os.listdir(sdk_depot_dir):
                if file_name.endswith('.dat'):
                    # Ensure the format matches <appid>_<version>.dat
                    try:
                        parts = os.path.basename(file_name).split(".")[0].split("_")
                        app_id, version = parts[0:2]
                        # Append app ID and version to app_list and app_buffer
                        app_buffer += str(app_id).encode('latin-1') + b"\x00" + str(version).encode('latin-1') + b"\x00\x00"
                        app_list.append((app_id, version))
                    except ValueError:
                        # Handle the case where the file name format doesn't match
                        print(f"Skipping file with unexpected format: {file_name}")

        return app_buffer