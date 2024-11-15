import struct
from io import BytesIO

class MsgClientUFSGetFileListForApp:
    def __init__(self):
        self.m_nApps = 0
        self.apps_list = []

    def deserialize(self, buffer: bytes):
        """
        Parses the byte buffer to extract MsgClientUFSGetFileListForApp fields.
        Prints any extra bytes remaining in the buffer.
        """
        stream = BytesIO(buffer)

        # Read m_nApps (4 bytes, uint32)
        self.m_nApps = struct.unpack('<I', stream.read(4))[0]

        # Parse the list of AppIDs (each 4 bytes, uint32)
        self.apps_list = []
        for _ in range(self.m_nApps):
            app_id = struct.unpack('<I', stream.read(4))[0]
            self.apps_list.append(app_id)

        # Check for extra bytes
        remaining_bytes = stream.read()
        if remaining_bytes:
            print(f"Extra bytes found: {remaining_bytes}")

        return self

# Example buffer with 3 apps and extra bytes at the end
"""example_buffer = (
    struct.pack('<I', 3) +  # m_nApps (example: 3 applications)
    struct.pack('<I', 1001) +  # AppID 1 (example: 1001)
    struct.pack('<I', 1002) +  # AppID 2 (example: 1002)
    struct.pack('<I', 1003) +  # AppID 3 (example: 1003)
    b'\xAA\xBB\xCC\xDD'  # Extra bytes for testing
)"""
packet = b'V\x14\x00\x00$\x02\x00\xff\xff\xff\xff\xff\xff\xff\xff\x0e\x00\x00\x00\x00\x00\x00\x00\xefmw\xea\x02\x01\x00\x10\x01\xfc\xdf\x8b\x00\x01\x00\x00\x00\x07\x00\x00\x00'


packet = packet[36:]

# Deserialize the example buffer
file_list_response = MsgClientUFSGetFileListForApp()
file_list_response.deserialize(packet)

# Output the parsed data
print(f"Number of Apps: {file_list_response.m_nApps}")
print(f"Apps List: {file_list_response.apps_list}")