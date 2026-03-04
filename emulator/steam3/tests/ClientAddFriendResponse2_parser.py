import struct
from io import BytesIO

class MsgClientAddFriendResponse2:
    def __init__(self):
        self.m_ulJobIDClient = 0
        self.m_ulFriendID = 0
        self.m_eResult = 0

    def parse(self, buffer):
        stream = BytesIO(buffer)

        # Read the first 16 bytes (JobID, FriendID, EResult)
        self.m_ulJobIDClient, self.m_ulFriendID, self.m_eResult = struct.unpack('<QQI', stream.read(20))

        print(f"Job ID: {self.m_ulJobIDClient}")
        print(f"Friend ID: {self.m_ulFriendID}")
        print(f"Result: {self.m_eResult}")

        # Check if the buffer has extra data (e.g., more fields or unprocessed bytes)
        remaining_bytes = stream.read()
        if remaining_bytes:
            print(f"Extra bytes in buffer: {remaining_bytes.hex()}")

# Example usage
#buffer = struct.pack('<QQI', 123456789, 987654321012345, 1)

packet = b'\x18\x03\x00\x00\x0fI\x94\x01\x01\x00\x10\x01x\x96V\x00\x10\x00\x00\x00\x00\x00\x00\x00\xc4\xa0\x9b\x01\x01\x00\x10\x01\x01\x00\x00\x00asdasdasdasdasd\x00'

packet = packet[16:]
parser = MsgClientAddFriendResponse2()
parser.parse(packet)