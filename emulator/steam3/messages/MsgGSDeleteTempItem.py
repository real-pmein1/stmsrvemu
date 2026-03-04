import struct
from io import BytesIO


class MsgGSDeleteTempItem:
    """
    MsgGSDeleteTempItem - Request from game server to delete a temporary item.

    Structure from IDA analysis (MsgGSDeleteTempItem_t):
        - m_ulSteamID: uint64 - Steam ID of the user
        - m_ulItemID: uint64 - Temporary item ID to delete

    Temporary items are items that are not persisted in the database
    and only exist for the duration of a game session.
    Response is MsgGSDeleteTempItemResponse.
    """

    def __init__(self, steam_id=0, item_id=0):
        self.steam_id = steam_id  # 64-bit SteamID
        self.item_id = item_id  # 64-bit temporary item ID to delete

    def deserialize(self, byte_buffer):
        """Deserializes the byte buffer into a MsgGSDeleteTempItem object."""
        stream = BytesIO(byte_buffer)

        # Read SteamID (uint64)
        self.steam_id = struct.unpack('<Q', stream.read(8))[0]

        # Read Item ID (uint64)
        self.item_id = struct.unpack('<Q', stream.read(8))[0]

        return self

    def serialize(self):
        """Serializes the MsgGSDeleteTempItem object into a byte buffer."""
        stream = BytesIO()

        # Write SteamID (uint64)
        stream.write(struct.pack('<Q', self.steam_id))

        # Write Item ID (uint64)
        stream.write(struct.pack('<Q', self.item_id))

        return stream.getvalue()

    def __bytes__(self):
        """Allow using bytes() on this object."""
        return self.serialize()

    def __len__(self):
        """Return the serialized length."""
        return 16  # 8 + 8 bytes

    def __repr__(self):
        return f"MsgGSDeleteTempItem(steam_id={self.steam_id}, item_id={self.item_id})"
