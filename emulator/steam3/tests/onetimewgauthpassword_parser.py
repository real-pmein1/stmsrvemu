import struct
from io import BytesIO

class MsgClientOneTimeWGAuthPassword:
    def __init__(self):
        self.password = ""

    def deserialize(self, buffer: bytes):
        """
        Parses the byte buffer to extract the one-time WebGuard authentication password.
        """
        stream = BytesIO(buffer)

        # Read the password as a string, max length 17 characters (including null terminator)
        raw_password = stream.read(17)  # Read 17 bytes max for the password
        self.password = raw_password.decode('ascii').rstrip('\x00')  # Decode and strip null bytes

        return self

# Example buffer simulating the received data
"""example_buffer = (
    b'ThisIsYourPass\x00'  # Password (ASCII string with null termination)
)"""

packet = b'0\x03\x00\x00$\x02\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xef\xc4\xa0\x9b\x01\x01\x00\x10\x01\x00v/\x00\x00e925a1136a559a1c\x00'

packet = packet[36:]

# Deserialize the example buffer
auth_password_msg = MsgClientOneTimeWGAuthPassword()
auth_password_msg.deserialize(packet)

# Output the parsed data
print(f"One-time WebGuard Auth Password: {auth_password_msg.password}")