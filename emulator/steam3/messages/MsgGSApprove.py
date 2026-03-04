import struct
from io import BytesIO


class MsgGSApprove:
    """
    MsgGSApprove - Message to approve a player connecting to a game server.

    Structure from IDA analysis (MsgGSApprove_t):
        - m_ulSteamID: uint64 (8 bytes) - Steam ID of the player to approve

    Sent by CM server to game server to approve a player connection.
    Triggers callback 201 (GSClientApprove) on the game server.
    """

    def __init__(self, steam_id=0):
        self.steam_id = steam_id  # 64-bit SteamID

    def deserialize(self, byte_buffer):
        """Deserializes the byte buffer into a MsgGSApprove object."""
        stream = BytesIO(byte_buffer)

        # Read SteamID (uint64)
        self.steam_id = struct.unpack('<Q', stream.read(8))[0]

        return self

    def serialize(self):
        """Serializes the MsgGSApprove object into a byte buffer."""
        stream = BytesIO()

        # Write SteamID (uint64)
        stream.write(struct.pack('<Q', self.steam_id))

        return stream.getvalue()

    def __bytes__(self):
        """Allow using bytes() on this object."""
        return self.serialize()

    def __len__(self):
        """Return the serialized length."""
        return 8  # 8 bytes for steam_id

    def __repr__(self):
        return f"MsgGSApprove(steam_id={self.steam_id})"