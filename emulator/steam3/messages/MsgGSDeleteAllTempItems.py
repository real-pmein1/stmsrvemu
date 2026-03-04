import struct
from io import BytesIO


class MsgGSDeleteAllTempItems:
    """
    MsgGSDeleteAllTempItems - Request from game server to delete all temporary items.

    Structure from IDA analysis (MsgGSDeleteAllTempItems_t):
        - m_ulSteamID: uint64 - Steam ID of the user

    Deletes all temporary items for a player. Temporary items are items
    that only exist for the duration of a game session.
    Response is MsgGSDeleteAllTempItemsResponse.
    """

    def __init__(self, steam_id=0):
        self.steam_id = steam_id  # 64-bit SteamID

    def deserialize(self, byte_buffer):
        """Deserializes the byte buffer into a MsgGSDeleteAllTempItems object."""
        stream = BytesIO(byte_buffer)

        # Read SteamID (uint64)
        self.steam_id = struct.unpack('<Q', stream.read(8))[0]

        return self

    def serialize(self):
        """Serializes the MsgGSDeleteAllTempItems object into a byte buffer."""
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
        return f"MsgGSDeleteAllTempItems(steam_id={self.steam_id})"
