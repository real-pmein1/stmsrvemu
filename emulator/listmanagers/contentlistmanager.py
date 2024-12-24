
import datetime
import io
import logging
import pprint
import struct
import threading
import zipfile
from builtins import object

log = logging.getLogger("CSLSTHNDLR")


class ContentServerManager(object):
    contentserver_list = []
    contentserver_challenge_list = []
    lock = threading.Lock()

    client_info = {}
    client_last_heartbeat = {}

    def add_contentserver_info(self, server_id, wan_ip, lan_ip, port, region, received_applist, cellid, is_permanent = 0, is_pkgcs = False):
        log.debug(f"adding server {server_id} with wan ip {wan_ip} and lan ip {lan_ip} and port {port} and region {region} and cellid {cellid}, is clientupdate {is_pkgcs}")

        if not all([wan_ip, lan_ip, port, region, cellid, server_id]):
            log.error("Missing required server information.")
            return False

        current_time = datetime.datetime.now()

        if is_pkgcs:
            log.debug("adding client update server")
            entry = (wan_ip, lan_ip, port, region, current_time, [], is_permanent, is_pkgcs, cellid, server_id)
        else:
            log.debug("adding content server")
            entry = (wan_ip, lan_ip, port, region, current_time, received_applist, is_permanent, is_pkgcs, cellid, server_id)

        with self.lock:
            # Check if an entry with matching WAN IP, LAN IP, and port exists
            for idx, existing_entry in enumerate(self.contentserver_list):
                if existing_entry[0] == wan_ip and existing_entry[1] == lan_ip and existing_entry[2] == port:
                    # Replace the existing entry
                    log.debug(f"Replacing existing server with matching WAN IP {wan_ip}, LAN IP {lan_ip}, and port {port}")
                    self.contentserver_list[idx] = entry
                    log.debug(f"{wan_ip} updated in Content Directory Server List")
                    return True

            # If no matching entry is found, add the new one
            self.contentserver_list.append(entry)
            log.debug(f"{wan_ip} added to Content Directory Server List")
            return True

    def remove_old_entries(self):
        removed_entries = []
        current_time = datetime.datetime.now()
        with self.lock:
            for entry in self.contentserver_list[:]:  # Create a shallow copy to iterate over
                timestamp = entry[4]
                is_permanent = entry[6]
                time_diff = current_time - timestamp

                if time_diff.total_seconds() > 3600 and not is_permanent:  # Check if older than 60 minutes and not permanent
                    self.contentserver_list.remove(entry)
                    removed_entries.append(entry)
                    log.debug(f"Removing Server From list: publicip {entry[0]}, identifier: {entry[9]}, serverip: {entry[1]}, port: {entry[2]}")

        if len(removed_entries) == 0:
            return 0  # No entries were removed
        else:
            return 1  # Entries were successfully removed

    def get_empty_or_no_applist_entries(self, islan):
        empty_entries = []
        with self.lock:
            for entry in self.contentserver_list:
                if not entry[5] or len(entry[5]) == 0:  # No app list for this content server
                    if not islan:
                        empty_entries.append((entry[0], entry[2]))  # WAN IP and port
                    else:
                        empty_entries.append((entry[1], entry[2]))  # LAN IP and port
        count = len(empty_entries)
        if count > 0:
            return empty_entries, count
        else:
            return None, 0  # No entries found

    def find_ip_address(self, cellid = None, appid = None, version = None, islan = False, client_address = None):
        matches = []
        appid_version_matches = []

        with self.lock:
            # If appid and version are provided, attempt to find servers matching them
            if appid is not None and version is not None:
                # First, attempt to find servers matching the provided cellid, appid, and version
                for entry in self.contentserver_list:
                    if entry[5]:  # Ensure there is an applist
                        for app_entry in entry[5]:
                            try:
                                app_entry_appid = int(app_entry[0])
                                app_entry_version = int(app_entry[1])
                                if app_entry_appid == appid and app_entry_version == version:
                                    ip = entry[1] if islan else entry[0]
                                    appid_version_matches.append((ip, entry[2]))  # IP and port

                                    # Check if cellid matches or is None
                                    if cellid is None or entry[8] == cellid:
                                        matches.append((ip, entry[2]))  # IP and port
                                        break  # Found matching app in this server
                            except ValueError:
                                continue  # Skip if conversion fails
                # If no matches for appid and version are found, return None, 0
                if not appid_version_matches:
                    return None, 0
                # If no matches with cellid but found matches with appid and version, return all matching appid and version
                if not matches:
                    return appid_version_matches, len(appid_version_matches)

            else:
                # appid and version are None, so we need to return all servers matching the cellid
                for entry in self.contentserver_list:
                    # Check if cellid matches or is None
                    if cellid is None or entry[8] == cellid:
                        ip = entry[1] if islan else entry[0]
                        matches.append((ip, entry[2]))  # IP and port

                # If no entries match the cellid, return all servers
                if not matches:
                    for entry in self.contentserver_list:
                        ip = entry[1] if islan else entry[0]
                        matches.append((ip, entry[2]))  # IP and port

        # Check if any server matches the client's IP address
        client_ip = client_address if client_address else None
        if client_ip:
            for match in matches:
                if match[0] == client_ip:
                    return [match], 1  # Return only the matching server with the client's IP

        count = len(matches)
        if count > 0:
            return matches, count
        else:
            return None, 0  # No matching entries found

    def get_content_server_groups_list(self, cellid = None, appid = None, versionid = None, islan = False, client_address = None):
        # Get servers without an app list (client update servers)
        update_servers, update_count = self.get_empty_or_no_applist_entries(islan)

        # Get servers with an app list (content servers), filter by cellid, appid, and versionid
        content_servers, content_count = self.find_ip_address(cellid = cellid, appid = appid, version = versionid, islan = islan, client_address = client_address)

        if cellid:
            log.info(f"Getting content server groups for cellid {cellid}, appid {appid}, version {versionid}")
        else:
            log.info(f"Getting all content server groups (no specific cellid)")

        # If no matches for appid and version are found, return None, 0
        if appid is not None and versionid is not None and content_count == 0:
            log.warn(f"No content servers found for appid {appid} and version {versionid}")
            return None, 0

        # If no cellid is provided or no matches found for the cellid, return all entries
        if cellid is None or (update_count == 0 and content_count == 0):
            log.info("No specific cellid provided or no matches found, returning all content servers.")
            update_servers, update_count = self.get_empty_or_no_applist_entries(islan)
            content_servers, content_count = self.find_ip_address(appid = appid, version = versionid, islan = islan)

        # Combine the update servers with content servers
        combined_servers = []
        if content_servers:
            if update_servers:
                # Pair content servers with update servers
                for i, content_server in enumerate(content_servers):
                    update_server = update_servers[i % update_count]
                    combined_servers.append((cellid, update_server, content_server))
            else:
                # If no update servers, just return the content servers
                combined_servers.extend([(cellid, None, content_server) for content_server in content_servers])
        else:
            # If no content servers, just return the update servers
            combined_servers.extend([(cellid, update_server, None) for update_server in update_servers])

        # Return the combined list and the total count
        total_count = len(combined_servers)
        if total_count > 0:
            log.info(f"Returning {total_count} content server group(s).")
            return combined_servers, total_count
        else:
            log.warn("No content servers available.")
            return None, 0

    def remove_entry(self, wan_ip, lan_ip, port, region, ):
        with self.lock:
            for entry in self.contentserver_list:
                if entry[0] == wan_ip and entry[1] == lan_ip and entry[2] == port and entry[3] == region:
                    self.contentserver_list.remove(entry)
                    return True
        return False
    def remove_entry_by_id(self, server_id):
        with self.lock:
            for entry in self.contentserver_list:
                if entry[9] == server_id:
                    self.contentserver_list.remove(entry)
                    return True
        return False

    def receive_removal(self, packed_info):
        server_id = packed_info
        return self.remove_entry_by_id(server_id)

    def unpack_contentserver_info(self, decrypted_data):
        # Extract decryption_test (fixed size or until first null byte)
        parts = decrypted_data.split(b'\x00', 1)
        decryption_test = parts[0]
        # print(f"decryption test {decryption_test}")

        if decryption_test != b'gayben':  # Check decryption_test against expected value
            print(f"Decryption test failed: {decryption_test}")
            return False

        # Move past the decryption test and the null byte
        ip_index = len(decryption_test) + 1

        # Extract the server_id (uuid4().bytes is always 16 bytes long)
        server_id = decrypted_data[ip_index:ip_index + 16]  # Extract exactly 16 bytes for UUID
        ip_index += 17
        print(f"serverid: {server_id}")

        # Extract wan_ip until next null byte
        remaining_data = decrypted_data[ip_index:]
        parts = remaining_data.split(b'\x00', 2)  # Split at the next 2 null bytes for IP addresses
        wan_ip = parts[0]
        lan_ip = parts[1] if len(parts) > 1 else b''
        ip_index += len(wan_ip) + 1 + len(lan_ip) + 1  # Adjust index based on extracted data
        print(f"wan ip: {wan_ip}")
        print(f"lan ip: {lan_ip}")

        # The remaining data includes port, region, and cellid
        remaining_data = decrypted_data[ip_index:]

        if len(remaining_data) < 2:
            return False  # Not enough data to unpack port
        port = struct.unpack('H', remaining_data[:2])[0]
        ip_index += 2
        # print(f"port: {port}")

        region = remaining_data[2:4]  # Assuming region is 2 bytes long
        # print(f"region: {region}")
        ip_index += 2

        if len(remaining_data) < 5:
            return False  # Not enough data to unpack cellid
        cellid = struct.unpack('B', remaining_data[5:6])[0]
        # print(f"cellid: {cellid}")
        ip_index += 1

        # TODO enable the following code to allow peer/slave content servers to send us custom blobs to add to our secondblob.
        """# Extract the 1-byte flag indicating if there is zip data
        has_zip_data = struct.unpack('B', remaining_data[5:6])[0]
        ip_index += 1

        zip_data = b''
        if has_zip_data:
            # Extract the 4-byte integer indicating the size of the zip data
            zip_size = struct.unpack('I', remaining_data[6:10])[0]
            ip_index += 4

            # Extract the zip data itself
            zip_data = remaining_data[10:10 + zip_size]
            ip_index += zip_size
            print(f"Zip data size: {zip_size}")

            # Unzip the files and place them in "files/mod_blob/"
            with zipfile.ZipFile(io.BytesIO(zip_data), 'r') as zipf:
                zipf.extractall('files/mod_blob/')
        else:
            print("No zip data present.")"""

        # Rest would be applist data
        applist_data = remaining_data[6:]
        # print(f"applist data: {applist_data}")
        applist = []

        if len(applist_data) > 0:
            # Split the data by null bytes
            app_entries = applist_data.split(b'\x00')

            app_index = 0
            while app_index < len(app_entries) - 1:
                appid = app_entries[app_index]
                version = app_entries[app_index + 1]
                applist.append([appid.decode("latin-1"), version.decode("latin-1")])
                app_index += 3  # Move to the next appid/version pair

            print(f"Parsed app list: {repr(applist)}")
        else:
            return server_id, wan_ip, lan_ip, port, region, cellid, []

        return server_id, wan_ip, lan_ip, port, region, cellid, applist

    def print_contentserver_list(self, printapps = 0):
        with self.lock:
            for entry in self.contentserver_list:
                print("Server Identifier:", entry[9])
                print("WAN IP Address:", entry[0])
                print("LAN IP Address:", entry[1])
                print("Port:", entry[2])
                print("Region:", entry[3])
                print("CellID:", entry[8])
                if printapps == 1:
                    print("App List:")
                    for app_entry in entry[5]:
                        print("App ID:", app_entry[0])
                        print("Version:", app_entry[1])
                else:
                    appcount = 0
                    for app_entry in entry[5]:
                        appcount += 1
                    print("Number of Apps Available: " + str(appcount))
                print("--------------------")

manager = ContentServerManager()