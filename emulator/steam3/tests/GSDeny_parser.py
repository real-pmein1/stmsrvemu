import struct
from io import BytesIO

class MsgGSDeny:
    def __init__(self, steam_id=0, deny_reason=0, reason=""):
        self.steam_id = steam_id  # 64-bit SteamID
        self.deny_reason = deny_reason  # 32-bit Deny Reason
        self.reason = reason  # Optional reason string

    def deserialize(self, byte_buffer):
        """ Deserializes the byte buffer into a MsgGSDeny object. """
        stream = BytesIO(byte_buffer)

        # Read SteamID (uint64)
        self.steam_id = struct.unpack('<Q', stream.read(8))[0]

        # Read Deny Reason (int32)
        self.deny_reason = struct.unpack('<i', stream.read(4))[0]

        # Check if there are extra bytes for the reason string
        remaining_bytes = stream.read()
        if remaining_bytes:
            # Read the reason string (assumed to be null-terminated)
            self.reason = self._read_null_terminated_string(remaining_bytes)

        return self

    def _read_null_terminated_string(self, byte_data):
        """ Helper method to read a null-terminated string from byte data. """
        string_bytes = bytearray()
        for byte in byte_data:
            if byte == 0:
                break
            string_bytes.append(byte)
        return string_bytes.decode('utf-8')

    def __repr__(self):
        return (f"MsgGSDeny(steam_id={self.steam_id}, deny_reason={self.deny_reason}, "
                f"reason='{self.reason}')")

# Example usage
# Simulated byte buffer representing MsgGSDeny_t data
# SteamID: 76561198000000000 (0x110000100000000) and DenyReason: 2
byte_data = b'\xf7\x02\x00\x00\x00\x04\xb3v&\x00@\x01\xdc5l\x00\xc2\x95\x00\x00\x01\x00\x10\x01\x03\x00\x00\x00'

# Deserialize the buffer
msg = MsgGSDeny().deserialize(byte_data[16:])

# Output the parsed data
print(msg)