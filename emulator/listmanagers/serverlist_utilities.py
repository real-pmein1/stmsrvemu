import logging
import socket
import struct
import time
from builtins import str

import globalvars
import utilities.encryption as encryption
from globalvars import config

log = logging.getLogger("DIRLSTMGR")


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

    data = "\x00\x3e\x7b\x11"
    sock.send(data)  # Send the 'im a dir server packet' packet

    handshake = sock.recv(1)  # wait for a reply

    if handshake == '\x01':
        sock.send(encrypted_buffer)
        confirmation = sock.recv(1)  # wait for a reply
        if confirmation != '\x01':
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

    data = "\x05\xaa\x6c\x15"
    sock.send(data)  # Send the 'im a dir server packet' packet

    serverlist_size = sock.recv(4)  # wait for a reply
    unpacked_length = struct.unpack('!I', serverlist_size[:4])[0]
    sock.send("\x01")
    recieved_list = []
    recieved_list = sock.recv(unpacked_length)
    sock.send("\x01")
    sock.close()
    log.info("Recieved Server List From Master Directory Server.")
    return recieved_list


# TODO Add Lan IP!
def send_removal(ip_address, port, in_server_type):
    ipaddr = ip_address.encode('latin-1')
    # lan_ip = ip_address.encode('latin-1')
    server_type = in_server_type.encode('latin-1')

    packed_info = struct.pack('!16s I 16s', ipaddr, port, server_type)

    return remove_from_dir("\x1d" + encryption.encrypt(packed_info, globalvars.peer_password))


# TODO Add Lan IP
def unpack_removal_info(encrypted_data):
    packed_info = encryption.decrypt(encrypted_data[1:], globalvars.peer_password)

    unpacked_info = struct.unpack('!16s I 16s', packed_info)
    ip_address = unpacked_info[0].decode('utf-8').rstrip('\x00')
    port = unpacked_info[1]
    server_type = unpacked_info[2].decode('utf-8').rstrip('\x00')
    return ip_address, port, server_type


def remove_from_dir(encrypted_buffer):
    masterdir_ipport = config["masterdir_ipport"]
    mdir_ip, mdir_port = masterdir_ipport.split(":")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((mdir_ip, mdir_port))  # Connect the socket to master dir server

    data = "\x00\x3e\x7b\x11"
    sock.send(data)  # Send the 'im a dir server packet' packet
    response = sock.recv(1)  # wait for a reply

    if response == '\x01':
        sock.send(encrypted_buffer)
        confirmation = sock.recv(1)  # wait for a reply
    else:
        log.warning("Failed to Remove self from Master Directory Server.")

    sock.close()