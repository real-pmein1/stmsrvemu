import struct
from io import BytesIO


class MsgGSItemDropped:
    """
    MsgGSItemDropped - Notification that an item was dropped/deleted.

    Structure from IDA analysis (MsgGSItemDropped_t):
        - m_ulSteamID: uint64 - Steam ID of the user who dropped the item
        - m_ulItemID: uint64 - The item ID that was dropped

    Sent by CM to game servers to notify that a player dropped an item.
    """

    def __init__(self, steam_id=0, item_id=0):
        self.steam_id = steam_id  # 64-bit SteamID of the user
        self.item_id = item_id  # 64-bit Item ID that was dropped

    def deserialize(self, byte_buffer):
        """Deserializes the byte buffer into a MsgGSItemDropped object."""
        stream = BytesIO(byte_buffer)

        # Read SteamID (uint64)
        self.steam_id = struct.unpack('<Q', stream.read(8))[0]

        # Read Item ID (uint64)
        self.item_id = struct.unpack('<Q', stream.read(8))[0]

        return self

    def serialize(self):
        """Serializes the MsgGSItemDropped object into a byte buffer."""
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
        return 16  # 8 bytes for steam_id + 8 bytes for item_id

    def __repr__(self):
        return f"MsgGSItemDropped(steam_id={self.steam_id}, item_id={self.item_id})"
