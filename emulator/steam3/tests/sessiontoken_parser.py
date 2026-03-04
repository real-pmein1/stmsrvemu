import struct
from io import BytesIO

class MsgClientSessionToken:
    def __init__(self):
        self.m_unNewToken = 0

    def deserialize(self, buffer: bytes):
        """
        Parses the byte buffer to extract the session token.
        """
        stream = BytesIO(buffer)

        # Read the session token (8 bytes, uint64)
        self.m_unNewToken = struct.unpack('<Q', stream.read(8))[0]

        return self

# Example buffer simulating the received session token (64-bit unsigned integer)
#example_buffer = struct.pack('<Q', 1234567890123456789)  # Example session token as uint64

packet = b'R\x03\x00\x00$\x02\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xef\xc4\xa0\x9b\x01\x01\x00\x10\x01\x00v/\x00B\x05\xd7HzrcZ'

packet = packet[36:]
# Deserialize the example buffer
session_token_msg = MsgClientSessionToken()
session_token_msg.deserialize(packet)

# Output the parsed data
print(f"Session Token: {session_token_msg.m_unNewToken}")