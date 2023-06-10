import time, logging
import struct
import utilities, socket, datetime, globalvars, threading
import steamemu.logger

from config import read_config
config = read_config()

log = logging.getLogger("contentserverlist_utils")

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

def send_heartbeat(contentserver_info, applist):
    packed_info = ""
    packed_info += contentserver_info['ip_address'] + '\x00'
    packed_info += struct.pack('H', contentserver_info['port'])
    packed_info += contentserver_info['region'] + '\x00'
    packed_info += str(contentserver_info['timestamp']) + '\x00'
    packed_info += applist

    return heartbeat("\x2b" + utilities.encrypt(packed_info, globalvars.peer_password))

def unpack_contentserver_info(encrypted_data):
    decrypted_data = utilities.decrypt(encrypted_data[1:], globalvars.peer_password)

    ip_address = ""
    ip_index = 0
    while decrypted_data[ip_index] != '\x00':
        ip_address += decrypted_data[ip_index]
        ip_index += 1
    ip_index += 1

    port = struct.unpack('H', decrypted_data[ip_index:ip_index + 2])[0]
    ip_index += 2

    region = ""
    while decrypted_data[ip_index] != '\x00':
        region += decrypted_data[ip_index]
        ip_index += 1
    ip_index += 1

    timestamp = ""
    while decrypted_data[ip_index] != '\x00':
        timestamp += decrypted_data[ip_index]
        ip_index += 1
    timestamp = float(timestamp)
    ip_index += 1

    applist_data = decrypted_data[ip_index:]
    applist = []

    app_index = 0
    while app_index < len(applist_data):
        appid = ""
        version = ""
        while app_index < len(applist_data) and applist_data[app_index] != '\x00':
            appid += applist_data[app_index]
            app_index += 1
        app_index += 1

        while app_index < len(applist_data) and applist_data[app_index:app_index + 2] != '\x00\x00':
            version += applist_data[app_index]
            app_index += 1
        app_index += 2

        applist.append([appid, version])

    return ip_address, port, region, timestamp, applist

def heartbeat(encrypted_buffer):
    csds_ipport = config["csds_ipport"]
    csds_ip, csds_port = csds_ipport.split(":")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((str(csds_ip), int(csds_port))) # Connect the socket to master dir server

    data = "\x00\x4f\x8c\x11"
    sock.send(data) # Send the 'im a dir server packet' packet
    
    response = sock.recv(1) # wait for a reply
    
    if response == '\x01':
        sock.send(str(len(encrypted_buffer)))
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

class ContentServerManager(object):
    contentserver_list = []
    lock = threading.Lock()

    def add_contentserver_info(self, ip_address, port, region, received_applist):
        current_time = datetime.datetime.now()
        entry = (ip_address, port, region, current_time, received_applist)
        with self.lock:
            self.contentserver_list.append(entry)

    def remove_old_entries(self):
        removed_entries = []
        current_time = datetime.datetime.now()
        with self.lock:
            for entry in self.contentserver_list:
                timestamp = entry[3]
                time_diff = current_time - timestamp
                if time_diff.total_seconds() > 3600:  # Check if older than 60 minutes (3600 seconds)
                    self.contentserver_list.remove(entry)
                    removed_entries.append(entry)
        if len(removed_entries) == 0:
            return 0  # No entries were removed
        else:
            return 1  # Entries were successfully removed

    def find_ip_address(self, region=None, appid=None, version=None):
        if not region and not appid and not version:  # Check if all arguments are empty or None
            all_entries = [(entry[0], entry[1]) for entry in self.contentserver_list]
            count = len(all_entries)
            if count > 0:
                return all_entries, count
            else:
                return None, 0  # No entries found
        else:
            matches = []
            with self.lock:
                for entry in self.contentserver_list:
                    if region and entry[2] == region:
                        for app_entry in entry[4]:
                            if app_entry[0] == appid and app_entry[1] == version:
                                matches.append((entry[0], entry[1]))  # Add IP address and port to matches
                    elif appid and version:
                        for app_entry in entry[4]:
                            if app_entry[0] == appid and app_entry[1] == version:
                                matches.append((entry[0], entry[1]))  # Add IP address and port to matches
            count = len(matches)
            if count > 0:
                return matches, count
            else:
                return None, 0  # No matching entries found
    
    def remove_entry(self, ip_address, port, region):
        with self.lock:
            for entry in self.contentserver_list:
                if entry[0] == ip_address and entry[1] == port and entry[2] == region:
                    self.contentserver_list.remove(entry)
                    return True
        return False
