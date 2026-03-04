import struct
from io import BytesIO


class MsgGSKick:
    """
    MsgGSKick - Message to kick a player from a game server.

    Structure from IDA analysis (MsgGSKick_t):
        - m_ulSteamID: uint64 - Steam ID of the player to kick
        - m_eDenyReason: uint32 - Reason for the kick (EDenyReason enum)

    Used by the CM server to notify a game server that a player should be kicked.
    """

    def __init__(self, steam_id=0, deny_reason=0):
        self.steam_id = steam_id  # 64-bit SteamID
        self.deny_reason = deny_reason  # 32-bit EDenyReason

    def deserialize(self, byte_buffer):
        """Deserializes the byte buffer into a MsgGSKick object."""
        stream = BytesIO(byte_buffer)

        # Read SteamID (uint64)
        self.steam_id = struct.unpack('<Q', stream.read(8))[0]

        # Read DenyReason (int32)
        self.deny_reason = struct.unpack('<I', stream.read(4))[0]

        return self

    def serialize(self):
        """Serializes the MsgGSKick object into a byte buffer."""
        stream = BytesIO()

        # Write SteamID (uint64)
        stream.write(struct.pack('<Q', self.steam_id))

        # Write DenyReason (int32)
        stream.write(struct.pack('<I', self.deny_reason))

        return stream.getvalue()

    def __bytes__(self):
        """Allow using bytes() on this object."""
        return self.serialize()

    def __len__(self):
        """Return the serialized length."""
        return 12  # 8 bytes for steam_id + 4 bytes for deny_reason

    def __repr__(self):
        return f"MsgGSKick(steam_id={self.steam_id}, deny_reason={self.deny_reason})"
