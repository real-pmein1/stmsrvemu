import time, logging
import struct
import utilities, socket, datetime, globalvars
import steamemu.logger

from config import read_config
config = read_config()

log = logging.getLogger("contentserverlist_utils")
contentserver_list = []

# Define the structure of contentserver_info
contentserver_info_structure = struct.Struct('!16s I 16s 21s I')

class ContentServerInfo:
    def __init__(self, ip_address, port, region, timestamp):
        self.ip_address = ip_address
        self.port = port
        self.region = region
        self.timestamp = timestamp
        self.applist = []

def update_contentserver_info(contentserver_info):
    global contentserver_list

    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for server_info in contentserver_list:
        if server_info.ip_address == contentserver_info.ip_address and server_info.port == contentserver_info.port and server_info.region == contentserver_info.region:
            server_info.timestamp = current_time
            return

    contentserver_info.timestamp = current_time
    contentserver_info.applist = []
    contentserver_list.append(contentserver_info)
    
def create_contentserver_info(ip_address, port, region, timestamp):
    contentserver_info = ContentServerInfo(ip_address, port, region, timestamp)
    contentserver_list.append(contentserver_info)
    return contentserver_info

def add_app(contentserver_info, app_id, version):
    contentserver_info.applist.append((app_id, version))

def receive_removal(packed_info):
    unpacked_info = struct.unpack('!16s I 16s', packed_info)
    ip_address = unpacked_info[0].decode('utf-8').rstrip('\x00')
    port = unpacked_info[1]
    region = unpacked_info[2].decode('utf-8').rstrip('\x00')
    return ip_address,port,region

def send_removal(ip_address, port, region):
    ipaddr = ip_address.encode('utf-8')
    reg = region.encode('utf-8')

    packed_info = struct.pack('!16s I 16s', ipaddr, port, reg)

    return remove_from_dir("\x2e" + utilities.encrypt(packed_info, globalvars.peer_password))

def remove_server_info(ip, port, region):
    global contentserver_list

    for server_info in contentserver_list:
        if server_info.ip_address == ip and server_info.port == port and server_info.region == region:
            contentserver_list.remove(server_info)
            #return 1
    #return 0

def send_heartbeat(contentserver_info):
    ip_address = contentserver_info.ip_address.encode('utf-8')
    port = contentserver_info.port
    region = contentserver_info.region.encode('utf-8')
    timestamp = str(contentserver_info.timestamp).encode('utf-8')

    applist_length = len(contentserver_info.applist)
    packed_applist = struct.pack('!I', applist_length)

    for app in contentserver_info.applist:
        app_id, version = app
        packed_applist += struct.pack('!II', int(app_id), int(version))

    packed_info = contentserver_info_structure.pack(ip_address, port, region, timestamp, len(packed_applist))

    return heartbeat("\x2b" + utilities.encrypt(packed_info + packed_applist, globalvars.peer_password))

def unpack_contentserver_info(enc_buffer):
    buffer = utilities.decrypt(enc_buffer, globalvars.peer_password)
    info_size = contentserver_info_structure.size
    info_data = buffer[:info_size]
    unpacked_info = contentserver_info_structure.unpack(info_data)
    ip_address = unpacked_info[0].decode('utf-8').rstrip('\x00')
    try:
        socket.inet_aton(ip_address)
    except socket.error:
        return False

    port = unpacked_info[1]
    region = unpacked_info[2].decode('utf-8').rstrip('\x00')
    timestamp = unpacked_info[3].decode('utf-8').rstrip('\x00')


    applist_data = buffer[info_size:]

    # Read the applist without unpacking
    unpacked_applist = list(applist_data)
    
    unpacked_info = ContentServerInfo(ip_address, port, region, timestamp)
    unpacked_info.applist = unpacked_applist

    return unpacked_info

def heartbeat(encrypted_buffer):
    csds_ipport = config["csds_ipport"]
    csds_ip, csds_port = csds_ipport.split(":")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((str(csds_ip), int(csds_port))) # Connect the socket to master dir server

    data = "\x00\x4f\x8c\x11"
    sock.send(data) # Send the 'im a dir server packet' packet
    
    response = sock.recv(1) # wait for a reply
    
    if response == '\x01':
        sock.send(encrypted_buffer)
        confirmation = sock.recv(1) # wait for a reply
        
        if confirmation != "\x01" : # lets try again...
            heartbeat(ip, port, server_type, key)
    else :
        log.warning("Content Server failed to register server to Content Server Directory Server ")
        
    # Close the socket
    sock.close()

def remove_from_dir(encrypted_buffer):
    csds_ipport = config["csds_ipport"]
    csds_ip, csds_port = csds_ipport.split(":")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((csds_ip, csds_port)) # Connect the socket to master dir server

    data = "\x00\x4f\x8c\x11"
    sock.send(data) # Send the 'im a dir server packet' packet
    
    response = sock.recv(1) # wait for a reply
    
    if response == '\x01':
        sock.send(encrypted_buffer)
        confirmation = sock.recv(1) # wait for a reply
        
        if confirmation != "\x01" : # lets try again...
            remove_from_dir(ip, port, server_type, key)
    else:
        log.warning("Content Server failed to register server to Content Server Directory Server ")
        
    # Close the socket
    sock.close()
