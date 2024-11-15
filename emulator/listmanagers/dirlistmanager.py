import datetime
import logging
import struct
import threading

import utils

log = logging.getLogger("DIRLSTMGR")


class DirServerManager(object):
    dirserver_list = []
    lock = threading.Lock()

    # TODO Finish Directory Server Peering
    def pack_serverlist(self):
        # Get the size of the list
        size = len(self.dirserver_list)

        # Pack the size into 4 bytes
        packed_size = struct.pack('I', size)
        return packed_size, self.dirserver_list

    def add_server_info(self, wan_ip, lan_ip, port, server_type, permanent = 0):
        current_time = datetime.datetime.now()
        new_entry = (wan_ip, lan_ip, port, server_type, permanent, current_time)
        with self.lock:
            for entry in self.dirserver_list:  # check for the same server, if it exists then update the timestamp
                if entry[0] == wan_ip and entry[1] == lan_ip and entry[2] == int(port) and entry[3] == server_type:
                    # if entry[4] != 1:  # ignore permanent entries
                    self.dirserver_list.remove(entry)
                    # else:
                    #    return -1
            log.debug(f"adding: {repr(new_entry)}")
            self.dirserver_list.append(new_entry)

    def remove_old_entries(self):
        removed_entries = []
        current_time = datetime.datetime.now()
        with self.lock:
            for entry in self.dirserver_list:
                timestamp = entry[5]
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

    def remove_entry(self, wan_ip, lan_ip, port, server_type):
        with self.lock:
            for entry in self.dirserver_list:
                if entry[0] == wan_ip and entry[1] == lan_ip and entry[2] == port and entry[3] == server_type:
                    self.dirserver_list.remove(entry)
                    return True
        return False

    def find_ip_address(self, server_type = None):
        matches = []
        with self.lock:
            for entry in self.dirserver_list:
                if entry[3] == server_type:  # Add IP address and port to matches
                    matches.append((entry[0],  # wan_ip
                                    entry[1],  # lan_ip
                                    entry[2]))  # port
        count = len(matches)
        if count > 0:
            return matches, count
        else:
            return None, 0  # No matching entries found

    def get_server_list(self, server_type, islan, single = 0):  # Grab all server ip/port's available for a specific client request
        server_list, count = self.find_ip_address(str(server_type))
        result = []

        if count > 0:
            for wan_ip, lan_ip, port in server_list:
                if islan:
                    result.append((lan_ip, port))
                else:
                    result.append((wan_ip, port))

                if single:
                    return result[:1]  # Return only the first entry if 'single' is True

        return result

    def get_and_prep_server_list(self, server_type, islan, single = 0):  # Grab all server ip/port's available for a specific client request
        server_list, count = self.find_ip_address(str(server_type))
        if count > 0:
            reply = struct.pack(">H", count)
            for wan_ip, lan_ip, port in server_list:
                if islan:
                    ip_port_tuple = (lan_ip, port)
                    log.debug(f"Sending: {server_type} {lan_ip} {port}")
                else:
                    ip_port_tuple = (wan_ip, port)
                    log.debug(f"Sending: {server_type} {wan_ip} {port}")
                if single == 1:  # This means we only want 1 server, return the first one we find
                    return struct.pack(">H", 1) + utils.encodeIP(ip_port_tuple)
                reply += utils.encodeIP(ip_port_tuple)
        else:
            reply = b"\x00\x00"
        return reply

    def print_dirserver_list(self):
        with self.lock:
            for entry in self.dirserver_list:
                print("Wan IP Address: ", entry[0])
                print("Lan IP Address: ", entry[1])
                print("Port: ", entry[2])
                print("server_type: ", entry[3])
                print("Permanent: ", "Yes" if entry[4] == 1 else "No")
                print("Timestamp:", str(entry[5]))
                print("--------------------")


manager = DirServerManager()