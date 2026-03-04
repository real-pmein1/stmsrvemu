import logging
import os
import shutil
import socket
import struct
import time
import zipfile
import io
import pickle

import globalvars
from globalvars import config
from utilities.encryption import derive_key, peer_decrypt_message, peer_encrypt_message
import utilities.encryption as encryption
from utils import launch_neuter_application_standalone
from utilities import contentdescriptionrecord

log = logging.getLogger("CSLSTMGR")

HEADER = b"\x00\x4f\x8c\x11"


def send_removal(server_id):
    return remove_from_dir(HEADER + b"\x04" + server_id)

def remove_from_dir(encrypted_buffer):
    csds_ipport = config["csds_ipport"]
    csds_ip, csds_port = csds_ipport.split(":")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((csds_ip, int(csds_port)))  # Connect the socket to master dir server

    sock.send(encrypted_buffer)
    confirmation = sock.recv(1)  # wait for a reply
    if confirmation != b'\x00':
        log.warning("Content Server failed to remove server to Content Server Directory Server ")

    sock.close()

def handle_server_error(error_message):
    """Handle any error message from the server."""
    log.error(f"Server Error: {error_message}")

# Send heartbeat
def send_heartbeat(client_socket, server_address, key):
    heartbeat_message = b"heartbeat" + b"_" * 10  # Extending the message length
    encrypted_message = peer_encrypt_message(key, heartbeat_message)
    packet = HEADER + b"\x03" + encrypted_message
    client_socket.send(packet)  # Command byte \x03 for heartbeat
    #print(f"Sent heartbeat packet: {packet}")

    # Wait for server response
    try:
        data = client_socket.recv(1024)
        log.debug(f"Received server response for heartbeat: {data}")
        if data == b'\x00':  # OK response from server
            log.debug("Server acknowledged heartbeat.")
            return True
        elif data.startswith(b"error:"):
            handle_server_error(data.decode("latin-1"))
            return False
    except socket.timeout:
        log.warning("Heartbeat response timed out.")
    return False


def _has_files(appid, version):
    paths_m = [
        os.path.join(config['v2manifestdir'], f"{appid}_{version}.manifest"),
        os.path.join(config['v3manifestdir2'], f"{appid}_{version}.manifest"),
        os.path.join(config.get('v4manifestdir', 'files/v4manifests/'), f"{appid}_{version}.manifest"),
        os.path.join('files/steam2_sdk_depots', f"{appid}_{version}.blob"),
    ]
    paths_s = [
        os.path.join(config['v2storagedir'], f"{appid}_{version}.dat"),
        os.path.join(config['v3storagedir2'], f"{appid}_{version}.dat"),
        os.path.join(config.get('v4storagedir', 'files/v4storages/'), f"{appid}_{version}.dat"),
        os.path.join('files/steam2_sdk_depots', f"{appid}_{version}.dat"),
    ]
    return any(os.path.isfile(p) for p in paths_m) and any(os.path.isfile(p) for p in paths_s)


def _gather_custom_blobs(used_apps, used_subs):
    custom_folder = 'files/mod_blob/'
    valid_files = []
    for root, _, files in os.walk(custom_folder):
        for file in files:
            if not file.endswith(('.bin', '.xml', '.py')):
                continue
            full = os.path.join(root, file)
            try:
                if file.endswith('.bin'):
                    record = contentdescriptionrecord.BinaryBlob(full).cdr
                elif file.endswith('.py'):
                    record = contentdescriptionrecord.DictBlob(full).cdr
                else:
                    record = contentdescriptionrecord.ContentDescriptionRecord.from_xml_file(full)
            except Exception as e:
                log.error(f"Failed to parse {file}: {e}")
                continue
            apps = [int.from_bytes(k, 'little') for k in record.ApplicationsRecord.keys()]
            subs = [int.from_bytes(k, 'little') for k in record.SubscriptionsRecord.keys()]
            skip = False
            for app in apps:
                if app in used_apps:
                    log.error(f"{file}: appid {app} in use; skipping")
                    skip = True
                    break
                app_rec = record.ApplicationsRecord.get(struct.pack('<I', app))
                if app_rec:
                    for vr in app_rec.VersionsRecord.values():
                        ver = vr.VersionId
                        if isinstance(ver, bytes):
                            ver = int.from_bytes(ver, 'little')
                        if not _has_files(app, ver):
                            log.error(f"{file}: missing files for {app}_{ver}; skipping")
                            skip = True
                            break
                if skip:
                    break
            if skip:
                continue
            for sub in subs:
                if sub in used_subs:
                    log.error(f"{file}: subid {sub} in use; skipping")
                    skip = True
                    break
            if not skip:
                valid_files.append(full)
    return valid_files


def build_serverinfo(contentserver_info, applist, ispkg=False, used_apps=None, used_subs=None):
    """This method is used to create the 'add server' and heartbeat packet for both the contentserver
    and the client update server.
    The way the content directory server determines if a server is an update server or not is by checking
    if there is any data after the cellid byte string, if not then it is an update server
    because the update server does not contain an app list"""
    packed_info = b'gayben\x00'
    packed_info += contentserver_info['server_id'] + b'\x00'
    packed_info += contentserver_info['wan_ip'] + b'\x00'
    # print(f"public IP: {contentserver_info['wan_ip']}")
    packed_info += contentserver_info['lan_ip'] + b'\x00'
    # print(f"LAN IP: {contentserver_info['lan_ip']}")
    packed_info += struct.pack('H', contentserver_info['port'])
    packed_info += contentserver_info['region'] + b'\x00'
    packed_info += struct.pack('B', contentserver_info['cellid'])

    if ispkg is False:
        used_apps = used_apps or set()
        used_subs = used_subs or set()
        valid_files = _gather_custom_blobs(used_apps, used_subs)
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in valid_files:
                zipf.write(file_path, os.path.relpath(file_path, 'files/mod_blob'))

        # Get the zip data from the buffer
        zip_data = zip_buffer.getvalue()

        if zip_data:
            # Append a 1-byte flag indicating that there is zip data
            packed_info += struct.pack('B', 1)
            # Append a 4-byte integer of the size of the zip data
            packed_info += struct.pack('I', len(zip_data))
            packed_info += zip_data
        else:
            # Append a 1-byte flag indicating that there is no zip data
            packed_info += struct.pack('B', 0)

        packed_info += applist

    return packed_info

def split_into_chunks(byte_string, chunk_size=512):
    # Split the byte string into chunks of 512 bytes
    chunks = [byte_string[i:i + chunk_size] for i in range(0, len(byte_string), chunk_size)]
    return chunks


def request_used_ids(sock, key):
    packet = HEADER + b"\x06" + peer_encrypt_message(key, b"")
    sock.send(packet)
    size_data = sock.recv(4)
    if not size_data:
        return {'apps': [], 'subs': []}
    length = struct.unpack('!I', size_data)[0]
    data = b""
    while len(data) < length:
        chunk = sock.recv(length - len(data))
        if not chunk:
            break
        data += chunk
    try:
        dec = peer_decrypt_message(key, data)
        return pickle.loads(dec)
    except Exception as e:
        log.error(f"Failed to decode used id list: {e}")
        return {'apps': [], 'subs': []}


def send_client_info(client_socket, server_address, key, server_instance):
    is_pkgsrv = True if server_instance.applist == [] else False
    client_info = build_serverinfo(
        server_instance.contentserver_info,
        server_instance.applist,
        is_pkgsrv,
        getattr(server_instance, 'used_app_ids', set()),
        getattr(server_instance, 'used_sub_ids', set()),
    )

    chunks = split_into_chunks(peer_encrypt_message(key,client_info))
    num_chunks = len(chunks)

    encrypted_message = peer_encrypt_message(key, struct.pack('<H', num_chunks))
    packet = HEADER + b"\x02" + encrypted_message
    client_socket.send(packet)  # Command byte \x02 for sending info

    # Send each chunk
    i = 0
    while i < num_chunks:
        encrypted_message = chunks[i]
        #print(encrypted_message)
        #print(client_socket.send(encrypted_message))
        client_socket.send(encrypted_message)
        i += 1
        time.sleep(.1)

    log.debug(f"Sent client info packet: {packet}")

    # Wait for server response
    data = client_socket.recv(1024)

    if data == b'\x00':  # OK response from server
        log.debug("Server acknowledged client info.")
        return True
    elif data.startswith(b"error:"):
        handle_server_error(data.decode("latin-1"))
        return False
    else:
        log.warning(f"Unexpected response: {data}")
        return False

def handshake(client_socket, server_address, shared_secret, CLIENT_IDENTIFIER):
    salt = os.urandom(16)
    key = derive_key(shared_secret, salt)

    # Include the client identifier in the handshake
    message = peer_encrypt_message(key, CLIENT_IDENTIFIER + b"handshake")
    client_socket.send(HEADER + b"\x01" + salt + message)  # Command byte \x01 for handshake
    command_byte = b'\x01'
    log.debug(f"Handshake packet sent: {HEADER + command_byte + salt + message}")

    # Wait for server response
    assembled_data = b""
    while True:
        packet = client_socket.recv(4096)
        log.debug(f"Received packet: {packet}")
        assembled_data += packet
        if b"END_OF_BLOB" in packet:
            assembled_data = assembled_data.replace(b"END_OF_BLOB", b"")
            break

    log.debug(f"Full assembled data: {assembled_data}")

    if assembled_data.startswith(b"error:"):
        handle_server_error(assembled_data.decode("latin-1"))
        return None

    server_salt = assembled_data[:16]
    key = derive_key(shared_secret, server_salt)
    decrypted_data = peer_decrypt_message(key, assembled_data[16:])
    log.debug(f"Decrypted handshake response: {decrypted_data}")

    # Parse the decrypted data
    offset = 0

    # Read message_length
    if len(decrypted_data) < offset + 4:
        log.warning("Handshake failed. Incomplete data.")
        return None
    message_length = int.from_bytes(decrypted_data[offset:offset+4], 'big')
    offset += 4

    # Read message
    if len(decrypted_data) < offset + message_length:
        log.warning("Handshake failed. Incomplete data.")
        return None
    message = decrypted_data[offset:offset+message_length]
    offset += message_length

    # Read key1_length
    if len(decrypted_data) < offset + 4:
        log.warning("Handshake failed. Incomplete data.")
        return None
    key1_length = int.from_bytes(decrypted_data[offset:offset+4], 'big')
    offset += 4

    # Read key1_data
    if len(decrypted_data) < offset + key1_length:
        log.warning("Handshake failed. Incomplete data.")
        return None
    key1_data = decrypted_data[offset:offset+key1_length]
    offset += key1_length

    # Read key2_length
    if len(decrypted_data) < offset + 4:
        log.warning("Handshake failed. Incomplete data.")
        return None
    key2_length = int.from_bytes(decrypted_data[offset:offset+4], 'big')
    offset += 4

    # Read key2_data
    if len(decrypted_data) < offset + key2_length:
        log.warning("Handshake failed. Incomplete data.")
        return None
    key2_data = decrypted_data[offset:offset+key2_length]
    offset += key2_length

    # Read secondblob_length
    if len(decrypted_data) < offset + 4:
        log.warning("Failed to retrieve second blob: incomplete data.")
        return None
    secondblob_length = int.from_bytes(decrypted_data[offset:offset + 4], 'big')
    offset += 4

    # Read second blob data
    if len(decrypted_data) < offset + secondblob_length:
        log.warning("Failed to retrieve second blob: incomplete data.")
        return None

    second_blob = decrypted_data[offset:offset + secondblob_length]
    offset += secondblob_length

    # Save to file - use path relative to project root (not '../..' which is fragile)
    cache_dir = os.path.join('files', 'cache')
    wan_blob = os.path.join(cache_dir, 'secondblob_wan.bin')
    with open(wan_blob, 'wb') as f:
        f.write(second_blob)
        try:
            shutil.rmtree(os.path.join(cache_dir, 'secondblob_lan.bin'))
        except Exception:
            pass
    log.debug("Saved second blob data to files/cache/secondblob_wan.bin")


    if message == b"handshake successful":
        log.debug("Handshake successful with server.")
        # Save the keys to files - use path relative to project root
        config_dir = os.path.join('files', 'configs')
        with open(os.path.join(config_dir, 'main_key_1024.der'), 'wb') as f:
            f.write(key1_data)
        with open(os.path.join(config_dir, 'network_key_512.der'), 'wb') as f:
            f.write(key2_data)
        encryption.main_key, encryption.network_key = encryption.import_rsa_keys()
        encryption.BERstring = encryption.network_key.public_key().export_key("DER")
        encryption.signed_mainkey_reply = encryption.get_mainkey_reply()
        log.debug("Received RSA keys saved to files.")

        return key
    else:
        log.warning(f"Handshake failed. Received message: {message}")
        return None


def heartbeat_thread(server_instance):
    shared_secret = server_instance.config['peer_password']  # Predefined shared secret for simplicity
    CLIENT_IDENTIFIER = os.urandom(16)
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.bind(('', 44991))
    csds_ipport = config["csds_ipport"]
    csds_ip, csds_port = csds_ipport.split(":")
    server_address = (csds_ip, int(csds_port))
    client_socket.connect(server_address)
    # Initial handshake
    key = handshake(client_socket, server_address, shared_secret, CLIENT_IDENTIFIER)
    server_instance.key = key
    if not key:
        log.error("Handshake failed. Exiting.")
        return

    if not globalvars.aio_server:
        used = request_used_ids(client_socket, key)
        server_instance.used_app_ids = set(used.get('apps', []))
        server_instance.used_sub_ids = set(used.get('subs', []))
    else:
        server_instance.used_app_ids = set()
        server_instance.used_sub_ids = set()

    # Send client info
    if not send_client_info(client_socket, server_address, key, server_instance):
        log.error("Failed to send client info. Exiting.")
        return
    # Start heartbeat loop
    heartbeat_attempts = 0
    client_socket.settimeout(5)  # Set a 5-second timeout for heartbeat responses
    launch_neuter_application_standalone()
    while heartbeat_attempts < 3:
        success = send_heartbeat(client_socket, server_address, key)
        if success:
            heartbeat_attempts = 0  # Reset attempts on success
        else:
            heartbeat_attempts += 1
            log.warning(f"Heartbeat attempt {heartbeat_attempts} failed.")

        if heartbeat_attempts >= 3:
            log.error("Failed to receive server response after 3 heartbeats. Closing client.")
            break

        time.sleep(300)
    #client_socket.close()