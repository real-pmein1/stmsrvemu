import struct
from io import BytesIO

class MsgClientUpdateGuestPassesList:
    def __init__(self):
        self.m_eResult = 0
        self.m_cGuestPassesToGive = 0
        self.m_cGuestPassesToRedeem = 0

    def deserialize(self, buffer: bytes):
        """
        Parses the byte buffer to extract m_eResult, m_cGuestPassesToGive, and m_cGuestPassesToRedeem
        """
        stream = BytesIO(buffer)

        # Read m_eResult (4 bytes, int32)
        self.m_eResult = struct.unpack('<I', stream.read(4))[0]

        # Read m_cGuestPassesToGive (4 bytes, int32)
        self.m_cGuestPassesToGive = struct.unpack('<I', stream.read(4))[0]

        # Read m_cGuestPassesToRedeem (4 bytes, int32)
        self.m_cGuestPassesToRedeem = struct.unpack('<I', stream.read(4))[0]

        # Return the object itself for easier access
        return self


# Example buffer (should replace this with actual data)
"""example_buffer = (
    struct.pack('<I', 1) +  # m_eResult (example: success)
    struct.pack('<I', 5) +  # m_cGuestPassesToGive (example: 5 passes to give)
    struct.pack('<I', 2)    # m_cGuestPassesToRedeem (example: 2 passes to redeem)
)"""

packet = b'\x1e\x03\x00\x00$\x02\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xef\xc4\xa0\x9b\x01\x01\x00\x10\x01\x00v/\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'


packet = packet[36:]
# Deserialize the example buffer
msg = MsgClientUpdateGuestPassesList()
msg.deserialize(packet)

# Output the parsed data
print(f"Result: {msg.m_eResult}")
print(f"Guest Passes to Give: {msg.m_cGuestPassesToGive}")
print(f"Guest Passes to Redeem: {msg.m_cGuestPassesToRedeem}")