import os
import struct


class MsgClientAppInfoResponse_2008:
    def __init__(self, app_ids, base_directory = 'files/appcache/vdf/2008/'):
        self.app_ids = app_ids
        self.base_directory = base_directory
        self.packet_buffer = bytearray()

    def collect_app_info(self):
        # First, pack the number of app IDs as a 4-byte little-endian integer
        self.packet_buffer += struct.pack('<I', len(self.app_ids))

        for app_id in self.app_ids:
            # Construct the file name for the current app ID
            file_path = os.path.join(self.base_directory, f'app_{app_id}.vdf')

            if os.path.isfile(file_path):
                print(f"Reading {file_path}...")
                # Open the file and read the bytes
                with open(file_path, 'rb') as f:
                    file_data = f.read()

                # Append the file data to the buffer
                self.packet_buffer += file_data
                # Append a null byte after each app info
                #self.packet_buffer += b'\x00'
            else:
                print(f"File {file_path} not found!")

    def get_packet(self):
        # Returns the final packet buffer
        return bytes(self.packet_buffer)


"""# Example Usage
app_ids = [11420, 12345, 54321]  # Replace with actual app IDs

collector = MsgClientAppInfoResponse_2008(app_ids)
collector.collect_app_info()

# Get the final packed buffer
packet = collector.get_packet()

# You can write the packet to a file or use it further
with open('output_packet.bin', 'wb') as output_file:
    output_file.write(packet)"""