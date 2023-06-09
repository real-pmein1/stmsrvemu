import time, logging
import struct
import utilities, globalvars, socket
import steamemu.logger

from config import read_config
config = read_config()

log = logging.getLogger("serverlist_utils")

def create_add_server_packet(ip, port, server_type, key):
    # Pack IP address (4 bytes), port (2 bytes), and server type (null-terminated string)
    ip_bytes = socket.inet_aton(ip)
    port_bytes = struct.pack(">H", port)
    server_type_bytes = server_type.encode('utf-8') + b'\x00'

    # Combine the packed data into a buffer
    buffer = ip_bytes + port_bytes + server_type_bytes
    packet = "\x1c" + utilities.encrypt(buffer, key)
    return packet


def create_remove_server_packet(ip, port, server_type, key):
    # Pack IP address (4 bytes), port (2 bytes), and server type (null-terminated string)
    ip_bytes = socket.inet_aton(ip)
    port_bytes = struct.pack(">H", port)
    server_type_bytes = server_type.encode('utf-8') + b'\x00'

    # Combine the packed data into a buffer
    buffer = ip_bytes + port_bytes + server_type_bytes
    packet = "\x1d" + utilities.encrypt(buffer, key)
    return packet

def heartbeat(ip, port, server_type):
    masterdir_ipport = config["masterdir_ipport"]
    masterdir_ip, masterdir_port = masterdir_ipport.split(":")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((str(masterdir_ip), int(masterdir_port))) # Connect the socket to master dir server

    data = "\x00\x3e\x7b\x11"
    sock.send(data) # Send the 'im a dir server packet' packet
    
    response = sock.recv(1) # wait for a reply
    
    if response == '\x01':
        packet = create_add_server_packet(ip, port, server_type, globalvars.peer_password)
        sock.send(packet)
        confirmation = sock.recv(1) # wait for a reply
        
        if confirmation != "\x01" : # lets try again...
            heartbeat(ip, port, server_type)
    else :
        log.warning(server_type + "Failed to register server to Directory Server ")
        
    # Close the socket
    sock.close()

def remove_from_dir(ip, port, server_type):
    masterdir_ipport = config["masterdir_ipport"]
    masterdir_ip, masterdir_port = masterdir_ipport.split(":")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((masterdir_ip, int(masterdir_port))) # Connect the socket to master dir server

    data = "\x00\x3e\x7b\x11"
    sock.send(data) # Send the 'im a dir server packet' packet
    
    response = sock.recv(1) # wait for a reply
    
    if response == '\x01':
        packet = create_remove_server_packet(ip, port, server_type, globalvars.peer_password)
        sock.send(packet)
        confirmation = sock.recv(1) # wait for a reply
        
        if confirmation != "\x01" : # lets try again...
            remove_from_dir(ip, port, server_type)
    else:
        log.warning(server_type + "Failed to register server to Directory Server ")
        
    # Close the socket
    sock.close()
