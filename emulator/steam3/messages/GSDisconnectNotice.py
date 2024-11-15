import struct
from io import BytesIO

class MsgGSDisconnectNotice:
    def __init__(self):
        self.steam_id = 0

    def parse(self, byte_buffer):
        # Initialize a BytesIO stream from the byte buffer
        stream = BytesIO(byte_buffer)

        # Read the steam_id (64-bit unsigned integer)
        self.steam_id = struct.unpack('<Q', stream.read(8))[0]  # '<Q' is for little-endian 64-bit unsigned integer

        # Output the parsed Steam ID
        print(f"Steam ID: {self.steam_id}")

        # Check for any extra bytes
        remaining_bytes = stream.read()
        if remaining_bytes:
            print(f"Extra bytes: {remaining_bytes.hex()}")