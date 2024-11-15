import struct
from io import BytesIO

class MsgClientNewsUpdate:
    def __init__(self):
        self.m_usNumNewsUpdates = 0
        self.news_updates = []

    def deserialize(self, buffer: bytes):
        """
        Parses the byte buffer to extract MsgClientNewsUpdate fields.
        """
        stream = BytesIO(buffer)

        # Read m_usNumNewsUpdates (2 bytes, uint16)
        self.m_usNumNewsUpdates = struct.unpack('<H', stream.read(2))[0]

        # Parse each news update entry
        for _ in range(self.m_usNumNewsUpdates):
            # Read eNewsUpdateType (1 byte, uint8)
            eNewsUpdateType = struct.unpack('<B', stream.read(1))[0]

            if eNewsUpdateType == 4:
                # SteamNewsClientUpdate_t: Handle 13 bytes for this update type
                update = {
                    "type": "SteamNewsClientUpdate",
                    "news_id": struct.unpack('<I', stream.read(4))[0],
                    "current_bootstrapper_version": struct.unpack('<I', stream.read(4))[0],
                    "current_client_version": struct.unpack('<I', stream.read(4))[0],
                    "reload_cddb": struct.unpack('<B', stream.read(1))[0]
                }
            elif eNewsUpdateType > 0:
                # SteamNewsItemUpdate_t: Handle 28 bytes for this update type
                update = {
                    "type": "SteamNewsItemUpdate",
                    "news_id": struct.unpack('<I', stream.read(4))[0],
                    "have_sub_id": struct.unpack('<I', stream.read(4))[0],
                    "not_have_sub_id": struct.unpack('<I', stream.read(4))[0],
                    "have_app_id": struct.unpack('<I', stream.read(4))[0],
                    "not_have_app_id": struct.unpack('<I', stream.read(4))[0],
                    "have_app_id_installed": struct.unpack('<I', stream.read(4))[0],
                    "have_played_app_id": struct.unpack('<I', stream.read(4))[0]
                }
            else:
                # ClientAppNewsItemUpdate_t: Handle 12 bytes for this update type
                update = {
                    "type": "ClientAppNewsItemUpdate",
                    "news_id": struct.unpack('<I', stream.read(4))[0],
                    "app_id": struct.unpack('<I', stream.read(4))[0]
                }

            # Append the update to the list
            self.news_updates.append(update)

        # Check for extra bytes
        remaining_bytes = stream.read()
        if remaining_bytes:
            print(f"Extra bytes found: {remaining_bytes.hex()}")

        return self

    def print_updates(self):
        """
        Helper function to print the list of news updates.
        """
        print(f"Number of News Updates: {self.m_usNumNewsUpdates}")
        for idx, update in enumerate(self.news_updates):
            print(f"News Update {idx + 1}:")
            for key, value in update.items():
                print(f"  {key}: {value}")


# Example usage
# Construct an example buffer for testing
# Let's assume we have 2 news updates:
# News Update Type 4 (SteamNewsClientUpdate_t) followed by 13 bytes
# News Update Type 1 (SteamNewsItemUpdate_t) followed by 28 bytes

"""buffer = (
    struct.pack('<H', 2) +  # m_usNumNewsUpdates
    struct.pack('<B', 4) +  # eNewsUpdateType = 4
    struct.pack('<I', 1001) +  # News ID
    struct.pack('<I', 3001) +  # Bootstrapper Version
    struct.pack('<I', 4001) +  # Client Version
    struct.pack('<B', 1) +     # Reload CDDB (1 byte)
    struct.pack('<B', 1) +  # eNewsUpdateType = 1
    struct.pack('<I', 2002) +  # News ID
    struct.pack('<I', 3002) +  # Have Sub ID
    struct.pack('<I', 4002) +  # Not Have Sub ID
    struct.pack('<I', 5002) +  # Have App ID
    struct.pack('<I', 6002) +  # Not Have App ID
    struct.pack('<I', 7002) +  # Have App ID Installed
    struct.pack('<I', 8002)    # Have Played App ID
)
"""
packet = b'\x03\x03\x00\x00\x14x\x96\x01\x01\x00\x10\x016S/\x00\x03\x00\x00r\x03\x00\x004\x08\x00\x00\x00q\x03\x00\x00t\t\x00\x00\x00q\x03\x00\x00`\t\x00\x00'


packet = packet[16:]
# Deserialize the example buffer
news_update = MsgClientNewsUpdate()
news_update.deserialize(packet)

# Output the parsed data
news_update.print_updates()