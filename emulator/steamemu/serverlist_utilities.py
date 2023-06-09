import time, logging
import struct
import utilities, socket
import steamemu.logger

from config import read_config
config = read_config()

log = logging.getLogger("serverlist_utils")

def create_add_server_packet(ip, port, server_type, key):
    packet = "\x1c" + utilities.encrypt(utilities.encodeIP((ip, port)) + struct.pack("16s", server_type.encode("utf-8")), key)
    return packet

def create_remove_server_packet(ip, port, server_type, key):
    packet = "\x1d" + utilities.encrypt(utilities.encodeIP((ip, port)) + struct.pack("16s", server_type.encode("utf-8")), key)
    return packet

def heartbeat(ip, port, server_type, key):
    masterdir_ipport = config["masterdir_ipport"]
    masterdir_ip, masterdir_port = masterdir_ipport.split(":")
    
    slavesock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    slavesock.connect((str(masterdir_ip), int(masterdir_port))) # Connect the socket to master dir server

    data = "\x00\x3e\x7b\x11"
    slavesock.send(data) # Send the 'im a dir server packet' packet
    
    response = slavesock.recv(1) # wait for a reply
    
    if response == '\x01':
        packet = create_add_server_packet(ip, port, server_type, key)
        slavesock.send(packet)
        confirmation = slavesock.recv(1) # wait for a reply
        
        if confirmation != "\x01" : # lets try again...
            heartbeat(ip, port, server_type, key)
    else :
        log.warning(server_type + "Failed to register server to Directory Server ")
        
    # Close the socket
    slavesock.close()

def remove_from_dir(ip, port, server_type, key):
    masterdir_ipport = config["masterdir_ipport"]
    masterdir_ip, masterdir_port = masterdir_ipport.split(":")
    
    slavesock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    slavesock.connect((masterdir_ip, masterdir_port)) # Connect the socket to master dir server

    data = "\x00\x3e\x7b\x11"
    slavesock.send(data) # Send the 'im a dir server packet' packet
    
    response = sock.recv(1) # wait for a reply
    
    if response == '\x01':
        packet = create_remove_server_packet(ip, port, server_type, key)
        sock.send(packet)
        confirmation = sock.recv(1) # wait for a reply
        
        if confirmation != "\x01" : # lets try again...
            remove_from_dir(ip, port, server_type, key)
    else:
        log.warning(server_type + "Failed to register server to Directory Server ")
        
    # Close the socket
    slavesock.close()
