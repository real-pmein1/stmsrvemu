import struct
from io import BytesIO

import struct
from io import BytesIO

class MsgGSDeny:
    def __init__(self, steam_id=0, deny_reason=0, reason_text=""):
        self.steam_id = steam_id  # 64-bit SteamID
        self.deny_reason = deny_reason  # 32-bit DenyReason
        self.reason_text = reason_text  # Optional string for additional reason

    def deserialize(self, byte_buffer):
        """ Deserializes the byte buffer into a MsgGSDeny object. """
        stream = BytesIO(byte_buffer)

        # Read SteamID (uint64)
        self.steam_id = struct.unpack('<Q', stream.read(8))[0]

        # Read DenyReason (int32)
        self.deny_reason = struct.unpack('<I', stream.read(4))[0]

        # Check if there are extra bytes for reason text
        remaining_bytes = stream.read()
        if remaining_bytes:
            self.reason_text = remaining_bytes.decode('utf-8')

        return self

    def serialize(self):
        """ Serializes the MsgGSDeny object into a byte buffer. """
        stream = BytesIO()

        # Write SteamID (uint64)
        stream.write(struct.pack('<Q', self.steam_id))

        # Write DenyReason (int32)
        stream.write(struct.pack('<I', self.deny_reason))

        # Write the reason text if present
        if self.reason_text:
            stream.write(self.reason_text.encode('latin-1') + b'\x00')

        return stream.getvalue()

    def __repr__(self):
        return f"MsgGSDeny(steam_id={self.steam_id}, deny_reason={self.deny_reason}, reason_text='{self.reason_text}')"