
import datetime
import io
import logging
import struct
import threading
import zipfile
import os

import utils
import globalvars
from builtins import object
from utilities.cdr_manipulator import (
    save_ephemeral_blob,
    remove_ephemeral_blob,
    merge_ephemeral_into_memory,
    remove_ephemeral_from_memory
)

log = logging.getLogger("CSLSTHNDLR")


class ContentServerManager(object):
    contentserver_list = []
    contentserver_challenge_list = []
    lock = threading.Lock()
    # Index for O(1) server lookups by (wan_ip, lan_ip, port)
    _server_index = {}

    client_info = {}
    client_last_heartbeat = {}
    custom_blobs = {}

    def _rebuild_index(self):
        """Rebuild the server index after list modifications. Must be called while holding lock."""
        self._server_index.clear()
        for idx, entry in enumerate(self.contentserver_list):
            server_key = (entry[0], entry[1], entry[2])
            self._server_index[server_key] = idx

    def add_contentserver_info(self, server_id, wan_ip, lan_ip, port, region,
                               received_applist, cellid, is_permanent=0,
                               is_pkgcs=False):
        """Add or update a content server entry.

        Older parts of the ecosystem still pass a number of fields as
        ``bytes`` which breaks JSON serialisation on the admin side.  To
        keep behaviour consistent across the codebase we normalise the
        inputs to strings and integers here.
        """

        log.debug(
            f"adding server {server_id} with wan ip {wan_ip} and lan ip {lan_ip} and port {port} "
            f"and region {region} and cellid {cellid}, is clientupdate {is_pkgcs}"
        )

        if not all([wan_ip, lan_ip, port, region, cellid, server_id]):
            log.error("Missing required server information.")
            return False

        if isinstance(wan_ip, bytes):
            wan_ip = wan_ip.decode("latin-1")
        if isinstance(lan_ip, bytes):
            lan_ip = lan_ip.decode("latin-1")
        if isinstance(region, bytes):
            region = region.decode("latin-1")

        normalised_applist = []
        for app in received_applist:
            if isinstance(app, (list, tuple)) and len(app) == 2:
                appid, version = app
                if isinstance(appid, bytes):
                    appid = appid.decode("latin-1")
                if isinstance(version, bytes):
                    version = version.decode("latin-1")
                normalised_applist.append([appid, version])
            else:
                normalised_applist.append(app)

        current_time = datetime.datetime.now()

        if is_pkgcs:
            log.debug("adding client update server")
            entry = (
                wan_ip,
                lan_ip,
                int(port),
                region,
                current_time,
                [],
                int(is_permanent),
                bool(is_pkgcs),
                int(cellid),
                server_id,
            )
        else:
            log.debug("adding content server")
            entry = (
                wan_ip,
                lan_ip,
                int(port),
                region,
                current_time,
                normalised_applist,
                int(is_permanent),
                bool(is_pkgcs),
                int(cellid),
                server_id,
            )

        with self.lock:
            # Use index for O(1) lookup instead of linear search
            server_key = (wan_ip, lan_ip, int(port))
            if server_key in self._server_index:
                idx = self._server_index[server_key]
                log.debug(f"Replacing existing server with matching WAN IP {wan_ip}, LAN IP {lan_ip}, and port {port}")
                self.contentserver_list[idx] = entry
                log.debug(f"{wan_ip} updated in Content Directory Server List")
                return True

            # If no matching entry is found, add the new one
            idx = len(self.contentserver_list)
            self.contentserver_list.append(entry)
            self._server_index[server_key] = idx
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
                    # Remove from index before removing from list
                    server_key = (entry[0], entry[1], entry[2])
                    self._server_index.pop(server_key, None)
                    self.contentserver_list.remove(entry)
                    removed_entries.append(entry)
                    log.debug(f"Removing Server From list: publicip {entry[0]}, identifier: {entry[9]}, serverip: {entry[1]}, port: {entry[2]}")
            # Rebuild index after removals to fix indices
            self._rebuild_index()

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

    def remove_entry(self, wan_ip, lan_ip, port, region):
        if isinstance(wan_ip, bytes):
            wan_ip = wan_ip.decode("latin-1")
        if isinstance(lan_ip, bytes):
            lan_ip = lan_ip.decode("latin-1")
        if isinstance(region, bytes):
            region = region.decode("latin-1")

        with self.lock:
            server_key = (wan_ip, lan_ip, int(port))
            if server_key in self._server_index:
                idx = self._server_index[server_key]
                entry = self.contentserver_list[idx]
                if entry[3] == region:  # Verify region matches
                    self.contentserver_list.remove(entry)
                    self._rebuild_index()
                    return True
        return False

    def remove_entry_by_id(self, server_id):
        if isinstance(server_id, str):
            try:
                server_id = bytes.fromhex(server_id)
            except ValueError:
                return False

        with self.lock:
            for entry in self.contentserver_list:
                if entry[9] == server_id:
                    self.contentserver_list.remove(entry)
                    self._rebuild_index()
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
        offset = len(decryption_test) + 1

        # Extract the server_id (uuid4().bytes is always 16 bytes long)
        server_id = decrypted_data[offset:offset + 16]  # Extract exactly 16 bytes for UUID
        offset += 17  # 16 bytes + null terminator
        print(f"serverid: {server_id}")

        # Extract wan_ip until next null byte
        remaining_data = decrypted_data[offset:]
        parts = remaining_data.split(b'\x00', 2)  # Split at the next 2 null bytes for IP addresses
        wan_ip = parts[0]
        lan_ip = parts[1] if len(parts) > 1 else b''
        offset += len(wan_ip) + 1 + len(lan_ip) + 1  # Adjust index based on extracted data
        print(f"wan ip: {wan_ip}")
        print(f"lan ip: {lan_ip}")

        # The remaining data includes port, region, cellid, zip flag, and applist
        remaining_data = decrypted_data[offset:]
        local_offset = 0

        # Extract port (2 bytes, unsigned short)
        if len(remaining_data) < 2:
            return False  # Not enough data to unpack port
        port = struct.unpack('H', remaining_data[local_offset:local_offset + 2])[0]
        local_offset += 2
        # print(f"port: {port}")

        # Extract region (null-terminated string, variable length)
        region_end = remaining_data.find(b'\x00', local_offset)
        if region_end == -1:
            return False  # No null terminator found for region
        region = remaining_data[local_offset:region_end]
        local_offset = region_end + 1  # Move past region and null terminator
        # print(f"region: {region}")

        # Extract cellid (1 byte, unsigned char)
        if len(remaining_data) < local_offset + 1:
            return False  # Not enough data to unpack cellid
        cellid = struct.unpack('B', remaining_data[local_offset:local_offset + 1])[0]
        local_offset += 1
        # print(f"cellid: {cellid}")

        # Extract the 1-byte flag indicating if there is zip data
        if len(remaining_data) < local_offset + 1:
            # No more data - this is a package/update server with no applist
            return server_id, wan_ip, lan_ip, port, region, cellid, []

        has_zip_data = struct.unpack('B', remaining_data[local_offset:local_offset + 1])[0]
        local_offset += 1

        zip_data = b''
        if has_zip_data:
            # Extract the 4-byte integer indicating the size of the zip data
            if len(remaining_data) < local_offset + 4:
                return False  # Not enough data for zip size
            zip_size = struct.unpack('I', remaining_data[local_offset:local_offset + 4])[0]
            local_offset += 4

            # Extract the zip data itself
            if len(remaining_data) < local_offset + zip_size:
                return False  # Not enough data for zip content
            zip_data = remaining_data[local_offset:local_offset + zip_size]
            local_offset += zip_size
            print(f"Zip data size: {zip_size}")

            # Unzip the files and place them in "files/mod_blob/"
            with zipfile.ZipFile(io.BytesIO(zip_data), 'r') as zipf:
                zipf.extractall(os.path.join('files', 'mod_blob'))
            utils.check_secondblob_changed()
        else:
            print("No zip data present.")

        # Rest would be applist data (starts after zip data or zip flag if no zip)
        applist_data = remaining_data[local_offset:]
        # print(f"applist data: {applist_data}")
        applist = []

        if len(applist_data) > 0:
            # Split the data by null bytes
            app_entries = applist_data.split(b'\x00')

            # Filter out empty entries that may result from trailing null bytes
            app_entries = [e for e in app_entries if e]

            app_index = 0
            while app_index + 1 < len(app_entries):
                appid = app_entries[app_index]
                version = app_entries[app_index + 1]
                applist.append([appid.decode("latin-1"), version.decode("latin-1")])
                app_index += 2  # Move to the next appid/version pair

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

    def add_custom_blob(self, sub_id, app_id, sub_blob, app_blob, server_id=None):
        """
        Add a custom blob from an external content server.

        This creates an ephemeral blob that:
        - Gets saved to temp folder for persistence across blob reloads
        - Gets merged into memory blobs (not cache files)
        - Gets automatically re-merged when base blob changes
        - Gets cleaned up on server shutdown

        Args:
            sub_id: Subscription ID
            app_id: Application ID
            sub_blob: Subscription blob data
            app_blob: Application blob data
            server_id: Optional server identifier for tracking

        Returns:
            True if added successfully, False if already exists
        """
        # Check if already exists in CDR_DICTIONARY
        if globalvars.CDR_DICTIONARY:
            subs = globalvars.CDR_DICTIONARY.get(b"\x02\x00\x00\x00", {})
            apps = globalvars.CDR_DICTIONARY.get(b"\x01\x00\x00\x00", {})
            sub_key = struct.pack('<I', sub_id)
            app_key = struct.pack('<I', app_id)
            if sub_key in subs or app_key in apps:
                log.debug(f"Custom blob already exists for sub:{sub_id} app:{app_id}")
                return False

        # Convert server_id to string for filename if it's bytes
        server_id_str = None
        if server_id:
            if isinstance(server_id, bytes):
                server_id_str = server_id.hex()
            else:
                server_id_str = str(server_id)

        # Save ephemeral blob to temp folder (persists across blob reloads)
        save_ephemeral_blob(sub_id, app_id, sub_blob, app_blob, server_id=server_id_str)

        # Merge into memory blobs (updates CDR_DICTIONARY and re-serializes CDR_BLOB_*)
        merge_ephemeral_into_memory(sub_id, app_id, sub_blob, app_blob)

        # Track locally for removal when content server disconnects
        self.custom_blobs[(sub_id, app_id)] = (sub_blob, app_blob, server_id_str)

        log.info(f"Added ephemeral blob for sub:{sub_id} app:{app_id}")
        return True

    def remove_custom_blob(self, sub_id, app_id, server_id=None):
        """
        Remove a custom blob from memory and disk.

        Args:
            sub_id: Subscription ID
            app_id: Application ID
            server_id: Optional server identifier

        Returns:
            True if removed, False if not found
        """
        key = (sub_id, app_id)
        if key not in self.custom_blobs:
            return False

        # Get server_id from stored data if not provided
        stored_data = self.custom_blobs[key]
        if server_id is None and len(stored_data) > 2:
            server_id = stored_data[2]

        # Remove from disk
        remove_ephemeral_blob(sub_id, app_id, server_id=server_id)

        # Remove from memory
        remove_ephemeral_from_memory(sub_id, app_id)

        # Remove from local tracking
        del self.custom_blobs[key]

        log.info(f"Removed ephemeral blob for sub:{sub_id} app:{app_id}")
        return True

    def get_all_appids_and_versions(self):
        """Get all AppIDs and their available versions from all content servers.

        Returns:
            dict: {appid: {version: [server_info, ...], ...}, ...}
            where server_info contains server details for that app/version
        """
        appid_data = {}

        with self.lock:
            for entry in self.contentserver_list:
                if entry[5]:  # Ensure there is an applist
                    server_info = {
                        'wan_ip': entry[0],
                        'lan_ip': entry[1],
                        'port': entry[2],
                        'region': entry[3],
                        'timestamp': entry[4],
                        'cellid': entry[8] if len(entry) > 8 else None,
                        'server_id': entry[6] if len(entry) > 6 else None
                    }

                    for app_entry in entry[5]:
                        try:
                            appid = int(app_entry[0])
                            version = int(app_entry[1])

                            if appid not in appid_data:
                                appid_data[appid] = {}

                            if version not in appid_data[appid]:
                                appid_data[appid][version] = []

                            appid_data[appid][version].append(server_info)

                        except (ValueError, IndexError):
                            continue  # Skip invalid entries

        return appid_data

manager = ContentServerManager()