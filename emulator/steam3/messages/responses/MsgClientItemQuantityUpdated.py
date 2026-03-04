"""
MsgClientItemQuantityUpdated - Notification that an item's quantity was updated.

EMsg 5425 - ClientItemQuantityUpdated
Callback ID: 1406 (ItemQuantityUpdated_t)
"""
import struct
from io import BytesIO


class MsgClientItemQuantityUpdated:
    """
    MsgClientItemQuantityUpdated - Notification that an item's quantity was updated.

    Structure from IDA callback analysis (ItemQuantityUpdated_t):
        - m_ulItemID: uint64 - Item ID that was updated
        - m_unNewQuantity: uint32 - New quantity value

    This is a server->client notification sent when an item's quantity changes.
    Callback ID: 1406
    """

    def __init__(self, item_id=0, new_quantity=0):
        self.item_id = item_id          # 64-bit item ID
        self.new_quantity = new_quantity  # 32-bit new quantity

    def deserialize(self, byte_buffer):
        """Deserializes the byte buffer."""
        stream = BytesIO(byte_buffer)

        # Read Item ID (uint64)
        self.item_id = struct.unpack('<Q', stream.read(8))[0]

        # Read New Quantity (uint32)
        self.new_quantity = struct.unpack('<I', stream.read(4))[0]

        return self

    def serialize(self):
        """Serializes the object into a byte buffer."""
        stream = BytesIO()

        # Write Item ID (uint64)
        stream.write(struct.pack('<Q', self.item_id))

        # Write New Quantity (uint32)
        stream.write(struct.pack('<I', self.new_quantity))

        return stream.getvalue()

    def __bytes__(self):
        return self.serialize()

    def __len__(self):
        return 12  # 8 + 4

    def __repr__(self):
        return f"MsgClientItemQuantityUpdated(item_id={self.item_id}, qty={self.new_quantity})"
