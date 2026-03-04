import logging
import os
import re
import struct
from datetime import datetime
import globalvars
from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse
from utilities.appinfo_utils import find_appid_files_2009

log = logging.getLogger("MsgClientAppInfoResponse_Obsolete")

# Maximum number of apps to send in a single response to prevent client crashes
MAX_APPINFO_RESPONSE = 200

class MsgClientAppInfoResponse_Obsolete:
    def __init__(self, client_obj, app_ids, is2009, start_date="01/01/2020 00:00:00", islan=False):
        self.app_ids = app_ids
        self.packet_buffer = bytearray()
        self.is_2009 = is2009
        self.islan = islan
        self.start_date = start_date  # Default start date if none provided.
        self.client_obj = client_obj

    def to_clientmsg(self):
        packet = None
        successful_files = 0
        temp_buffer = bytearray()
        network_type = "lan" if self.islan else "wan"

        # Convert app_ids to a set for faster lookups
        app_ids_set = set(self.app_ids) if self.app_ids else set()

        log.debug(f"[AppInfo Obsolete] Requested {len(app_ids_set)} app IDs: {list(app_ids_set)[:20]}{'...' if len(app_ids_set) > 20 else ''}")

        # Limit the number of app IDs to prevent client crashes
        app_ids_to_process = list(app_ids_set)
        if len(app_ids_to_process) > MAX_APPINFO_RESPONSE:
            log.warning(f"Limiting appinfo request from {len(app_ids_set)} to {MAX_APPINFO_RESPONSE} to prevent client crash")
            app_ids_to_process = app_ids_to_process[:MAX_APPINFO_RESPONSE]

        # Convert to set for O(1) lookups during filtering
        app_ids_to_process_set = set(app_ids_to_process)

        if self.is_2009:
            packet = CMResponse(eMsgID=EMsg.ClientAppInfoResponse_obsolete, client_obj=self.client_obj)

            # Parse the CDDB datetime; if parsing fails, use current time.
            try:
                current_cdr_date = datetime.strptime(globalvars.CDDB_datetime, "%m/%d/%Y %H:%M:%S")
            except Exception as e:
                log.error(f"Error parsing CDDB datetime: {e}")
                current_cdr_date = datetime.now()

            # Construct the expected folder name with timestamp.
            current_folder_name = current_cdr_date.strftime("%Y-%m-%d_%H-%M")
            base_path = os.path.join("files", "cache", "appinfo", "2009_2010", network_type)
            exact_folder_path = os.path.join(base_path, current_folder_name)
            log.debug(f"[AppInfo 2009] Base path: {base_path}, Exact folder path: {exact_folder_path}")

            # If the exact folder exists, use it; otherwise search for a "close" match.
            if os.path.exists(exact_folder_path):
                log.debug(f"[AppInfo 2009] Exact directory found: {exact_folder_path}")
                folders_to_search = [exact_folder_path]
            else:
                log.debug(f"[AppInfo 2009] No exact directory found for date {current_folder_name}, searching for closest match...")
                if not os.path.exists(base_path):
                    log.debug(f"[AppInfo 2009] Base path does not exist: {base_path}. Creating it...")
                    os.makedirs(base_path, exist_ok=True)
                # Get just the date portion (YYYY-MM-DD)
                date_only = current_cdr_date.strftime("%Y-%m-%d")
                possible_folders = [
                    d for d in os.listdir(base_path)
                    if os.path.isdir(os.path.join(base_path, d)) and d.startswith(date_only)
                ]

                if possible_folders:
                    # Pick the latest (or the one that sorts highest)
                    closest_folder = sorted(possible_folders)[-1]
                    log.debug(f"[AppInfo 2009] Found closest folder: {closest_folder}")
                    exact_folder_path = os.path.join(base_path, closest_folder)
                    folders_to_search = [exact_folder_path]
                else:
                    log.debug(f"[AppInfo 2009] No folder found matching date {date_only}. Using fallback logic...")
                    folders_to_search = []

            if folders_to_search:
                for folder in folders_to_search:
                    for file_name in os.listdir(folder):
                        # Attempt to extract app_id from the file name assuming it follows "app_<appid>..." format.
                        match = re.match(r'app_(\d+)', file_name)
                        if not match:
                            # If the file doesn't match the expected pattern, skip it.
                            continue
                        app_id = int(match.group(1))
                        if app_id not in app_ids_to_process_set:
                            # Skip files that aren't in the approved list.
                            continue

                        file_path = os.path.join(folder, file_name)
                        if os.path.isfile(file_path):
                            try:
                                with open(file_path, 'rb') as f:
                                    file_data = f.read()
                                # Transform disk cache format to network format:
                                # Skip: magic (4) + version (4) = 8 bytes
                                # Keep: appId (4) + changeNumber (4) = 8 bytes
                                # Skip: is_allsections (4) = 4 bytes
                                # Keep: sections (rest of file)
                                file_data = file_data[8:]  # Skip magic + version
                                file_data = file_data[:8] + file_data[12:]  # Keep appId+changeNumber, skip is_allsections

                                # Validate section termination (should end with 0x00)
                                if file_data and file_data[-1:] != b'\x00':
                                    log.warning(f"[AppInfo 2009] File {file_path} may be missing section terminator (0x00), last byte: {file_data[-1:].hex()}")

                                temp_buffer += file_data
                                successful_files += 1
                                log.debug(f"[AppInfo 2009] Added app {app_id} ({len(file_data)} bytes) from {file_path}")
                            except Exception as e:
                                log.error(f"Error reading {file_path}: {e}")
            else:
                # Fallback: use the file list returned by find_appid_files_2009
                file_list = find_appid_files_2009(self.start_date, self.islan)
                for app_id, file_path in file_list:
                    if app_id not in app_ids_to_process_set:
                        continue
                    if os.path.isfile(file_path):
                        try:
                            with open(file_path, 'rb') as f:
                                file_data = f.read()
                            # Transform disk cache format to network format
                            file_data = file_data[8:]  # Skip magic + version
                            file_data = file_data[:8] + file_data[12:]  # Keep appId+changeNumber, skip is_allsections

                            # Validate section termination
                            if file_data and file_data[-1:] != b'\x00':
                                log.warning(f"[AppInfo 2009 fallback] File {file_path} may be missing section terminator (0x00)")

                            temp_buffer += file_data
                            successful_files += 1
                            log.debug(f"[AppInfo 2009 fallback] Added app {app_id} ({len(file_data)} bytes) from {file_path}")
                        except Exception as e:
                            log.error(f"Error reading {file_path}: {e}")
        else: # 2008
            packet = CMResponse(eMsgID=EMsg.ClientAppInfoResponse, client_obj=self.client_obj)

            cache_directory = os.path.join("files", "cache", "appinfo", "2008", network_type)

            if os.path.isdir(cache_directory):
                base_directory = cache_directory
            else:
                base_directory = os.path.join("files", "appcache", "2008")

            log.debug(f"[AppInfo 2008] Looking for {len(app_ids_to_process)} apps in {base_directory}")

            # Proceed with file reading - only read files for requested app IDs
            for app_id in app_ids_to_process:
                # Construct the file name for the current app ID
                file_path = os.path.join(base_directory, f'app_{app_id}.vdf')

                if os.path.isfile(file_path):
                    try:
                        # Open the file and read the bytes
                        with open(file_path, 'rb') as f:
                            file_data = f.read()

                        # Append the file data to the temp buffer
                        temp_buffer += file_data
                        # Increment the successful file count
                        successful_files += 1

                    except Exception as e:
                        log.error(f"Error reading {file_path}: {e}")
                else:
                    log.debug(f"[AppInfo 2008] File {file_path} not found, skipping")

        # If no files were found for 2009, just send m_cNumApps=0 (no extra bytes needed)
        # For 2008, the original behavior is preserved
        if successful_files == 0 and len(temp_buffer) == 0:
            if not self.is_2009:
                # 2008 path - preserve original behavior
                temp_buffer = b'\x00\x00\x00\x00'
            log.warning(f"[AppInfo {'2009' if self.is_2009 else '2008'}] No appinfo files found for requested apps; sending empty response (m_cNumApps=0)")

        log.info(f"[AppInfo {'2009' if self.is_2009 else '2008'}] Sending {successful_files} app infos (requested: {len(app_ids_to_process)})")

        self.packet_buffer += struct.pack('<I', successful_files)
        self.packet_buffer += temp_buffer
        packet.data = self.packet_buffer

        # Debug: log hex preview of response for format verification
        if log.isEnabledFor(logging.DEBUG) and self.is_2009:
            # Show first 64 bytes: m_cNumApps (4) + first app's appId (4) + changeNumber (4) + section start
            hex_preview = self.packet_buffer[:64].hex() if len(self.packet_buffer) >= 64 else self.packet_buffer.hex()
            log.debug(f"[AppInfo 2009] Response payload ({len(self.packet_buffer)} bytes), hex preview: {hex_preview}")

        return packet

    def get_packet_buffer(self):
        return bytes(self.packet_buffer)


"""# Example Usage
app_ids = [11420, 12345, 54321]  # Replace with actual app IDs

collector = MsgClientAppInfoResponse_Obsolete(app_ids)
collector.serialize()

# Get the final packed buffer
packet = collector.get_packet()

# You can write the packet to a file or use it further
with open('output_packet.bin', 'wb') as output_file:
    output_file.write(packet)"""