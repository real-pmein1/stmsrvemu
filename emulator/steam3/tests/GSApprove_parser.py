import struct
from io import BytesIO

class MsgGSApprove:
    def __init__(self, steam_id=0):
        self.steam_id = steam_id  # 64-bit SteamID

    def deserialize(self, byte_buffer):
        """ Deserializes the byte buffer into a MsgGSApprove object. """
        stream = BytesIO(byte_buffer)

        # Read SteamID (uint64)
        self.steam_id = struct.unpack('<Q', stream.read(8))[0]

        return self

    def serialize(self):
        """ Serializes the MsgGSApprove object into a byte buffer. """
        stream = BytesIO()

        # Write SteamID (uint64)
        stream.write(struct.pack('<Q', self.steam_id))

        return stream.getvalue()

    def __repr__(self):
        return f"MsgGSApprove(steam_id={self.steam_id})"


# Example usage for MsgGSApprove:
byte_data_approve = b'\xf6\x02\x00\x00\x02\x84\x18\xf9\x1e\x00@\x01\x88\xe1&\x00\xca\x1f\x93\x00\x01\x00\x10\x01'

msg_approve = MsgGSApprove().deserialize(byte_data_approve[16:])
print(msg_approve)  # Output the deserialized data