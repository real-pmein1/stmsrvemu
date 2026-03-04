import struct
from io import BytesIO


class MsgGSDeny:
    """
    MsgGSDeny - Message to deny a player connecting to a game server.

    Structure from IDA analysis (MsgGSDeny_t):
        - m_ulSteamID: uint64 (8 bytes) - Steam ID of the player being denied
        - m_eDenyReason: uint32 (4 bytes) - Reason code for the denial (EDenyReason enum)
        - Optional: reason_text string (if deny_reason == 7)

    Sent by CM server to game server to deny a player connection.
    Triggers callback 202 (GSClientDeny) on the game server.

    EDenyReason values:
        0 = Invalid
        1 = InvalidVersion
        2 = Generic
        3 = NotLoggedOn
        4 = NoLicense
        5 = Cheater
        6 = LoggedInElsewhere
        7 = UnknownText (reason text follows)
        8 = IncompatibleAnticheat
        9 = MemoryCorruption
        10 = IncompatibleSoftware
        11 = SteamConnectionLost
        12 = SteamConnectionError
        13 = SteamResponseTimedOut
        14 = SteamValidationStalled
        15 = SteamOwnerLeftGuestUser
    """

    def __init__(self, steam_id=0, deny_reason=0, reason_text=""):
        self.steam_id = steam_id  # 64-bit SteamID
        self.deny_reason = deny_reason  # 32-bit DenyReason
        self.reason_text = reason_text  # Optional string (only used if deny_reason == 7)

    def deserialize(self, byte_buffer):
        """Deserializes the byte buffer into a MsgGSDeny object."""
        stream = BytesIO(byte_buffer)

        # Read SteamID (uint64)
        self.steam_id = struct.unpack('<Q', stream.read(8))[0]

        # Read DenyReason (int32)
        self.deny_reason = struct.unpack('<I', stream.read(4))[0]

        # Read reason text only if deny_reason == 7 (UnknownText)
        if self.deny_reason == 7:
            remaining_bytes = stream.read()
            if remaining_bytes:
                # Remove null terminator if present
                if remaining_bytes[-1] == 0:
                    remaining_bytes = remaining_bytes[:-1]
                self.reason_text = remaining_bytes.decode('latin-1')

        return self

    def serialize(self):
        """Serializes the MsgGSDeny object into a byte buffer."""
        stream = BytesIO()

        # Write SteamID (uint64)
        stream.write(struct.pack('<Q', self.steam_id))

        # Write DenyReason (int32)
        stream.write(struct.pack('<I', self.deny_reason))

        # Write the reason text only if deny_reason == 7 (UnknownText)
        if self.deny_reason == 7 and self.reason_text:
            stream.write(self.reason_text.encode('latin-1') + b'\x00')

        return stream.getvalue()

    def __bytes__(self):
        """Allow using bytes() on this object."""
        return self.serialize()

    def __len__(self):
        """Return the serialized length."""
        base_len = 12  # 8 bytes for steam_id + 4 bytes for deny_reason
        if self.deny_reason == 7 and self.reason_text:
            base_len += len(self.reason_text.encode('latin-1')) + 1  # +1 for null terminator
        return base_len

    def __repr__(self):
        return f"MsgGSDeny(steam_id={self.steam_id}, deny_reason={self.deny_reason}, reason_text='{self.reason_text}')"