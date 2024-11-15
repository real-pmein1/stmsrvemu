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

# Example usage
# Simulate a message buffer containing a 64-bit Steam ID
byte_data = b'\x85\x03\x00\x00\x00\x04\xb3v&\x00@\x01\xdc5l\x00\xc2\x95\x00\x00\x01\x00\x10\x01'


# Create an instance of the parser and parse the byte data
parser = MsgGSDisconnectNotice()
parser.parse(byte_data[16:])