import struct
from io import BytesIO


class MsgGSItemUpdated:
    """
    MsgGSItemUpdated - Notification that an item's inventory position was updated.

    Structure from IDA analysis (MsgGSItemUpdated_t):
        - m_ulSteamID: uint64 - Steam ID of the user
        - m_ulItemID: uint64 - The item ID that was updated
        - m_unNewPos: uint32 - New inventory position

    Sent by CM to game servers to notify that a player updated an item's position.
    """

    def __init__(self, steam_id=0, item_id=0, new_position=0):
        self.steam_id = steam_id  # 64-bit SteamID of the user
        self.item_id = item_id  # 64-bit Item ID that was updated
        self.new_position = new_position  # 32-bit new inventory position

    def deserialize(self, byte_buffer):
        """Deserializes the byte buffer into a MsgGSItemUpdated object."""
        stream = BytesIO(byte_buffer)

        # Read SteamID (uint64)
        self.steam_id = struct.unpack('<Q', stream.read(8))[0]

        # Read Item ID (uint64)
        self.item_id = struct.unpack('<Q', stream.read(8))[0]

        # Read New Position (uint32)
        self.new_position = struct.unpack('<I', stream.read(4))[0]

        return self

    def serialize(self):
        """Serializes the MsgGSItemUpdated object into a byte buffer."""
        stream = BytesIO()

        # Write SteamID (uint64)
        stream.write(struct.pack('<Q', self.steam_id))

        # Write Item ID (uint64)
        stream.write(struct.pack('<Q', self.item_id))

        # Write New Position (uint32)
        stream.write(struct.pack('<I', self.new_position))

        return stream.getvalue()

    def __bytes__(self):
        """Allow using bytes() on this object."""
        return self.serialize()

    def __len__(self):
        """Return the serialized length."""
        return 20  # 8 + 8 + 4 bytes

    def __repr__(self):
        return f"MsgGSItemUpdated(steam_id={self.steam_id}, item_id={self.item_id}, new_position={self.new_position})"
