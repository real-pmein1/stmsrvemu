import os
import struct
from datetime import datetime
import globalvars
from steam3.utilities import create_4byte_id_from_date, find_appid_files, find_appid_files_2009


class MsgClientAppInfoResponse_2008:
    def __init__(self, app_ids, base_directory = 'files/appcache/2008/', start_date="01/01/2020 00:00:00"):
        self.app_ids = app_ids
        self.base_directory = base_directory
        self.packet_buffer = bytearray()
        self.is_2009 = False if base_directory == 'files/appcache/2008/' else True

        self.start_date = start_date  # Example default date

    def serialize(self):
        # Initialize a count for successfully opened files
        successful_files = 0

        # Temporary buffer to store file data
        temp_buffer = bytearray()

        if self.is_2009:
            current_cdr_date = datetime.strptime(globalvars.CDDB_datetime, "%m/%d/%Y %H:%M:%S")
            current_changeid = create_4byte_id_from_date(current_cdr_date)
            # Use the find_appid_files function
            file_list = find_appid_files_2009(self.start_date)
            temp_buffer = b""  # Ensure temp_buffer is initialized
            successful_files = 0  # Counter for successful file reads

            for app_id, file_path in file_list:
                if os.path.isfile(file_path):
                    try:
                        print(f"Reading {file_path}...")
                        with open(file_path, 'rb') as f:
                            file_data = f.read()

                        # The following is to remove the excess stuff that the client adds to the appinfo files, which does NOT get sent
                        # Remove the first 8 bytes
                        file_data = file_data[8:]

                        # Remove 4 bytes starting at index 8
                        file_data = file_data[:8] + file_data[12:]

                        temp_buffer += file_data
                        successful_files += 1
                    except Exception as e:
                        print(f"Error reading {file_path}: {e}")
        else:
            # Original way of finding files
            for app_id in self.app_ids:
                file_path = os.path.join(self.base_directory, f'app_{app_id}.vdf')
                if os.path.isfile(file_path):
                    try:
                        print(f"Reading {file_path}...")
                        with open(file_path, 'rb') as f:
                            file_data = f.read()
                        temp_buffer += file_data
                        successful_files += 1
                    except Exception as e:
                        print(f"Error reading {file_path}: {e}")

        # Pack the number of successful files into the packet buffer
        self.packet_buffer += struct.pack('<I', successful_files)
        # Add the successful file data to the packet buffer
        self.packet_buffer += temp_buffer

    def get_packet(self):
        # Returns the final packet buffer
        return bytes(self.packet_buffer)


"""# Example Usage
app_ids = [11420, 12345, 54321]  # Replace with actual app IDs

collector = MsgClientAppInfoResponse_2008(app_ids)
collector.serialize()

# Get the final packed buffer
packet = collector.get_packet()

# You can write the packet to a file or use it further
with open('output_packet.bin', 'wb') as output_file:
    output_file.write(packet)"""