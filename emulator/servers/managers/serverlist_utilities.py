import logging
import socket
import struct
import time
import pickle
from builtins import str

import globalvars
import utilities.encryption as encryption
from globalvars import config

log = logging.getLogger("DIRLSTMGR")

# Maps server type names to request command bytes used by the directory server.
# Defined at module scope so it can be reused without reconstruction.
SERVER_TYPE_REQUEST_MAP: dict[str, bytes] = {
    'AuthServer': b'\x00',
    'ConfigServer': b'\x03',
    'CSDServer': b'\x05',
    'Harvest': b'\x0a',
    'ValidationSRV': b'\x07',
}


def send_heartbeat(server_info):
    packed_info = b""
    packed_info += server_info['wan_ip'] + b'\x00'
    packed_info += server_info['lan_ip'] + b'\x00'
    packed_info += struct.pack('H', server_info['port'])
    packed_info += server_info['server_type'].encode('latin-1') + b'\x00'
    timestamp_bytes = server_info['timestamp'].to_bytes(4, byteorder = 'big')  # Adjust the byte size (4 in this example) as needed
    packed_info += timestamp_bytes + b'\x00'
    print(server_info['timestamp'])
    return heartbeat(b"\x1a" + encryption.encrypt_bytes(packed_info, globalvars.peer_password))


def heartbeat(encrypted_buffer):
    masterdir_ipport = config["masterdir_ipport"]
    mdir_ip, mdir_port = masterdir_ipport.split(":")

    while True:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((str(mdir_ip), int(mdir_port)))  # Connect the socket to master dir server
            break
        except socket.error as e:
            print("Connection error:", str(e))
            print("Retrying in 5 minutes...")
            time.sleep(5 * 60)  # Wait for 5 minutes before retrying

    data = b"\x00\x3e\x7b\x11"
    sock.send(data)  # Send the 'im a dir server packet' packet

    handshake = sock.recv(1)  # wait for a reply

    if handshake == b'\x01':
        sock.send(encrypted_buffer)
        confirmation = sock.recv(1)  # wait for a reply
        if confirmation != b'\x01':
            log.warning("Failed to register server with Master Directory Server.")
    else:
        log.warning("Failed to get handshake response from Master Directory Server.")
    sock.close()


def unpack_server_info(encrypted_data):
    decrypted_data = encryption.decrypt_bytes(encrypted_data[1:], globalvars.peer_password)

    wan_ip = bytearray()
    ip_index = 0
    while decrypted_data[ip_index] != 0:  # Comparing with byte 0, not string '\x00'
        wan_ip.append(decrypted_data[ip_index])
        ip_index += 1
    ip_index += 1
    wan_ip_str = wan_ip.decode('latin-1')  # Convert bytes to string
    print(wan_ip_str)
    lan_ip = bytearray()
    while decrypted_data[ip_index] != 0:
        lan_ip.append(decrypted_data[ip_index])
        ip_index += 1
    ip_index += 1
    lan_ip_str = lan_ip.decode('latin-1')
    print(lan_ip_str)
    port = struct.unpack('H', decrypted_data[ip_index:ip_index + 2])[0]
    ip_index += 2
    print(port)
    server_type = bytearray()
    while decrypted_data[ip_index] != 0:
        server_type.append(decrypted_data[ip_index])
        ip_index += 1
    ip_index += 1
    server_type_str = server_type.decode('latin-1')
    print(server_type_str)
    timestamp_index = ip_index  # Where timestamp data starts
    timestamp, = struct.unpack('!I', decrypted_data[timestamp_index:timestamp_index + 4])  # Unpack 4 bytes to integer

    print(timestamp)
    return wan_ip_str, lan_ip_str, port, server_type_str, timestamp


# TODO Add lan_ip!
def forward_heartbeat(ip_address, port, encrypted_buffer):
    while True:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((str(ip_address), int(port)))  # Connect the socket to master dir server
            break
        except socket.error as e:
            print("Connection error:", str(e))
            print("Retrying in 5 minutes...")
            time.sleep(5 * 60)  # Wait for 5 minutes before retrying

    data = b"\x00\x3e\x7b\x11"
    sock.send(data)  # Send the 'im a dir server packet' packet

    handshake = sock.recv(1)  # wait for a reply

    if handshake == b'\x01':
        sock.send(encrypted_buffer)
        confirmation = sock.recv(1)  # wait for a reply
        if confirmation != b'\x01':
            log.warning("Failed to forward heartbeat to slave Directory Server.")
    else:
        log.warning("Failed to get handshake response to forward to slave Directory Server.")

    sock.close()


def send_listrequest():
    masterdir_ipport = config["masterdir_ipport"]
    mdir_ip, mdir_port = masterdir_ipport.split(":")

    while True:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((str(mdir_ip), int(mdir_port)))  # Connect the socket to master dir server
            break
        except socket.error as e:
            print("Connection error:", str(e))
            print("Retrying in 5 minutes...")
            time.sleep(5 * 60)  # Wait for 5 minutes before retrying

    data = b"\x05\xaa\x6c\x15"
    sock.send(data)  # Send the 'im a dir server packet' packet

    serverlist_size = sock.recv(4)  # wait for a reply
    unpacked_length = struct.unpack('!I', serverlist_size[:4])[0]
    sock.send(b"\x01")
    data = b""
    while len(data) < unpacked_length:
        chunk = sock.recv(unpacked_length - len(data))
        if not chunk:
            break
        data += chunk
    sock.send(b"\x01")
    sock.close()
    decrypted = encryption.decrypt_bytes(data, globalvars.peer_password)
    try:
        return pickle.loads(decrypted)
    except Exception:
        return []


def send_listrequest_peer(ip, port):
    """Request a server list from another directory server peer."""
    while True:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((str(ip), int(port)))
            break
        except socket.error as e:
            print("Connection error:", str(e))
            print("Retrying in 5 minutes...")
            time.sleep(5 * 60)

    data = b"\x05\xaa\x6c\x15"
    sock.send(data)

    serverlist_size = sock.recv(4)
    unpacked_length = struct.unpack('!I', serverlist_size[:4])[0]
    sock.send(b"\x01")
    data = b""
    while len(data) < unpacked_length:
        chunk = sock.recv(unpacked_length - len(data))
        if not chunk:
            break
        data += chunk
    sock.send(b"\x01")
    sock.close()
    decrypted = encryption.decrypt_bytes(data, globalvars.peer_password)
    try:
        return pickle.loads(decrypted)
    except Exception:
        return []


# TODO Add Lan IP!
def send_removal(ip_address, port, in_server_type):
    ipaddr = ip_address.encode('latin-1')
    # lan_ip = ip_address.encode('latin-1')
    server_type = in_server_type.encode('latin-1')

    packed_info = struct.pack('!16s I 16s', ipaddr, port, server_type)

    return remove_from_dir(b"\x1d" + encryption.encrypt(packed_info, globalvars.peer_password))


# TODO Add Lan IP
def unpack_removal_info(encrypted_data):
    packed_info = encryption.decrypt(encrypted_data[1:], globalvars.peer_password)

    unpacked_info = struct.unpack('!16s I 16s', packed_info)
    ip_address = unpacked_info[0].decode('latin-1').rstrip('\x00')
    port = unpacked_info[1]
    server_type = unpacked_info[2].decode('latin-1').rstrip('\x00')
    return ip_address, port, server_type


def remove_from_dir(encrypted_buffer):
    masterdir_ipport = config["masterdir_ipport"]
    mdir_ip, mdir_port = masterdir_ipport.split(":")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((mdir_ip, int(mdir_port)))  # Connect the socket to master dir server

    data = b"\x00\x3e\x7b\x11"
    sock.send(data)  # Send the 'im a dir server packet' packet
    response = sock.recv(1)  # wait for a reply

    if response == b'\x01':
        sock.send(encrypted_buffer)
        confirmation = sock.recv(1)  # wait for a reply
    else:
        log.warning("Failed to Remove self from Master Directory Server.")

    sock.close()

def request_server_list(server_type, single=0):
    """Request a list of servers of a given type from the directory server."""
    cmd = SERVER_TYPE_REQUEST_MAP.get(server_type)
    if cmd is None:
        return []
    ds_ip, ds_port = config['masterdir_ipport'].split(':')
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((ds_ip, int(ds_port)))
        sock.send(b'\x00\x00\x00\x01')
        if sock.recv(1) != b'\x01':
            return []
        sock.send(struct.pack('>L', 1) + cmd)
        size_data = sock.recv(4)
        if not size_data:
            return []
        length = struct.unpack('>L', size_data)[0]
        data = b''
        while len(data) < length:
            chunk = sock.recv(length - len(data))
            if not chunk:
                break
            data += chunk
    finally:
        sock.close()
    if len(data) < 2:
        return []
    count = struct.unpack('>H', data[:2])[0]
    servers = []
    offset = 2
    for _ in range(count):
        if len(data) < offset + 6:
            break
        ip = socket.inet_ntoa(data[offset:offset+4])
        port = struct.unpack('>H', data[offset+4:offset+6])[0]
        servers.append((ip, port))
        offset += 6
        if single and servers:
            break
    return servers


def forward_packet(ip_address, port, packet):
    """Forward a directory server packet to another peer."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((str(ip_address), int(port)))
        sock.send(b"\x00\x3e\x7b\x11")
        if sock.recv(1) == b"\x01":
            sock.send(packet)
            sock.recv(1)
    except Exception as e:
        log.warning(f"Failed to forward packet to {ip_address}:{port} - {e}")
    finally:
        try:
            sock.close()
        except Exception:
            pass

