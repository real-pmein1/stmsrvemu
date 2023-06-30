import time, logging
import struct
import utilities, socket, datetime, globalvars, threading
import steamemu.logger

from config import read_config
config = read_config()

log = logging.getLogger("dirserverlist_utils")

def send_heartbeat(server_info):
    packed_info = ""
    packed_info += server_info['ip_address'] + '\x00'
    packed_info += struct.pack('H', server_info['port'])
    packed_info += server_info['server_type'] + '\x00'
    packed_info += str(server_info['timestamp']) + '\x00'

    return heartbeat("\x1a" + utilities.encrypt(packed_info, globalvars.peer_password))

def heartbeat(encrypted_buffer):
    masterdir_ipport = config["masterdir_ipport"]
    mdir_ip, mdir_port = masterdir_ipport.split(":")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((str(mdir_ip), int(mdir_port))) # Connect the socket to master dir server

    data = "\x00\x3e\x7b\x11"
    sock.send(data) # Send the 'im a dir server packet' packet
    
    handshake = sock.recv(1) # wait for a reply
    
    if handshake == '\x01':
        sock.send(encrypted_buffer)
        confirmation = sock.recv(1) # wait for a reply
    else :
        log.warning("Failed to get handshake response from Master Directory Server.")
        
    if confirmation != '\x01' :
        log.warning("Failed to register server with Master Directory Server.")
    sock.close()
    
def unpack_server_info(encrypted_data):
    decrypted_data = utilities.decrypt(encrypted_data[1:], globalvars.peer_password)

    ip_address = ""
    ip_index = 0
    while decrypted_data[ip_index] != '\x00':
        ip_address += decrypted_data[ip_index]
        ip_index += 1
    ip_index += 1

    port = struct.unpack('H', decrypted_data[ip_index:ip_index + 2])[0]
    ip_index += 2

    server_type = ""
    while decrypted_data[ip_index] != '\x00':
        server_type += decrypted_data[ip_index]
        ip_index += 1
    ip_index += 1

    timestamp = ""
    while decrypted_data[ip_index] != '\x00':
        timestamp += decrypted_data[ip_index]
        ip_index += 1
    timestamp = float(timestamp)
    ip_index += 1
    return ip_address, port, server_type, timestamp

def send_removal(ip_address, port, server_type):
    ipaddr = ip_address.encode('utf-8')
    type = server_type.encode('utf-8')

    packed_info = struct.pack('!16s I 16s', ipaddr, port, type)

    return remove_from_dir("\x1d" + utilities.encrypt(packed_info, globalvars.peer_password))

def unpack_removal_info(encrypted_data):
    packed_info = utilities.decrypt(encrypted_data[1:], globalvars.peer_password)
    
    unpacked_info = struct.unpack('!16s I 16s', packed_info)
    ip_address = unpacked_info[0].decode('utf-8').rstrip('\x00')
    port = unpacked_info[1]
    server_type = unpacked_info[2].decode('utf-8').rstrip('\x00')
    return ip_address,port,server_type

def remove_from_dir(encrypted_buffer):
    masterdir_ipport = config["masterdir_ipport"]
    mdir_ip, mdir_port = masterdir_ipport.split(":")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((mdir_ip, mdir_port)) # Connect the socket to master dir server

    data = "\x00\x3e\x7b\x11"
    sock.send(data) # Send the 'im a dir server packet' packet 
    response = sock.recv(1) # wait for a reply
    
    if response == '\x01':
        sock.send(encrypted_buffer)
        confirmation = sock.recv(1) # wait for a reply
    else:
        log.warning("Failed to Remove self from Master Directory Server.")
    sock.close()

class DirServerManager(object):
    dirserver_list = []
    lock = threading.Lock()

    def add_server_info(self, ip_address, port, server_type, permanent = 0) :

        current_time = datetime.datetime.now()
        new_entry = (ip_address, port, server_type, current_time, permanent)
        with self.lock:
            for entry in self.dirserver_list : # check for the same server, if it exists then update the timestamp
                if entry[0] == ip_address and entry[1] == int(port) and entry[2] == server_type :
                    if entry[4] != 1 : # ignore permanent entries
                        self.dirserver_list.remove(entry)
                    else :
                        return
            self.dirserver_list.append(new_entry)

    def remove_old_entries(self):
        removed_entries = []
        current_time = datetime.datetime.now()
        with self.lock:
            for entry in self.dirserver_list:
                timestamp = entry[3]
                time_diff = current_time - timestamp
                if time_diff.total_seconds() > 3600:  # Check if older than 60 minutes (3600 seconds)
                    if entry[4] == 1:
                        continue  # Skip to the next entry
                    self.dirserver_list.remove(entry)
                    removed_entries.append(entry)
        if len(removed_entries) == 0:
            return 0  # No entries were removed
        else:
            return 1  # Entries were successfully removed

    def remove_entry(self, ip_address, port, server_type):
        with self.lock:
            for entry in self.dirserver_list:
                if entry[0] == ip_address and entry[1] == port and entry[2] == server_type:
                    self.dirserver_list.remove(entry)
                    return True
        return False
    
    def find_ip_address(self, server_type=None) :
        matches = []
        
        with self.lock :
            for entry in self.dirserver_list :
                if entry[2] == server_type :
                    matches.append((entry[0], entry[1]))  # Add IP address and port to matches
                    
        count = len(matches)
        
        if count > 0 :
            return matches, count
        else:
            return None, 0  # No matching entries found
      
    def get_and_prep_server_list(self, server_type, single = 0) :  # Grab all server ip/port's available for a specific client request      

        server_list, count = self.find_ip_address(str(server_type))
        
        if count > 0 :
            reply = struct.pack(">H", count)
            for ip, port in server_list :
                if single == 1 : # This means we only want 1 server, return the first one we find
                    return  (struct.pack(">H", 1) + utilities.encodeIP((ip, port)))
                reply += utilities.encodeIP((ip, port))
        else : 
            reply = "\x00\x00"
        return reply
    
    def print_dirserver_list(self):
        with self.lock:
            for entry in self.dirserver_list:
                print("IP Address: ", entry[0])
                print("Port: ", entry[1])
                print("server_type: ", entry[2])
                print("Permanent: ", "Yes" if entry[4] == 1 else "No")
                print("Timestamp:", str(entry[3]))
                #print("Timestamp: ", datetime.datetime.fromtimestamp(entry[3]).strftime('%Y-%m-%d %H:%M:%S'))
                print("--------------------")
