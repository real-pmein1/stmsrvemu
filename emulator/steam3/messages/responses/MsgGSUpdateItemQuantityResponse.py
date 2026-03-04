"""
MsgGSUpdateItemQuantityResponse - Response to GSUpdateItemQuantity request.

EMsg 932 - GSUpdateItemQuantityResponse
"""
import struct
from io import BytesIO


class MsgGSUpdateItemQuantityResponse:
    """
    MsgGSUpdateItemQuantityResponse - Response to GSUpdateItemQuantity request.

    Structure from IDA analysis:
        - m_eResult: uint32 - Result code (EResult)
        - m_ulItemID: uint64 - Item ID that was updated
        - m_unNewQuantity: uint32 - New quantity (confirmed)

    Sent by CM server in response to GSUpdateItemQuantity (EMsg 931).
    Callback ID: 1510 (GSUpdateQuantity_t)
    """

    def __init__(self, result=1, item_id=0, new_quantity=0):
        self.result = result        # EResult value (1 = OK)
        self.item_id = item_id      # 64-bit item ID
        self.new_quantity = new_quantity  # 32-bit new quantity

    def deserialize(self, byte_buffer):
        """Deserializes the byte buffer into a MsgGSUpdateItemQuantityResponse object."""
        stream = BytesIO(byte_buffer)

        # Read Result (uint32)
        self.result = struct.unpack('<I', stream.read(4))[0]

        # Read Item ID (uint64)
        self.item_id = struct.unpack('<Q', stream.read(8))[0]

        # Read New Quantity (uint32)
        self.new_quantity = struct.unpack('<I', stream.read(4))[0]

        return self

    def serialize(self):
        """Serializes the MsgGSUpdateItemQuantityResponse object into a byte buffer."""
        stream = BytesIO()

        # Write Result (uint32)
        stream.write(struct.pack('<I', self.result))

        # Write Item ID (uint64)
        stream.write(struct.pack('<Q', self.item_id))

        # Write New Quantity (uint32)
        stream.write(struct.pack('<I', self.new_quantity))

        return stream.getvalue()

    def __bytes__(self):
        return self.serialize()

    def __len__(self):
        return 16  # 4 + 8 + 4

    def __repr__(self):
        return (f"MsgGSUpdateItemQuantityResponse(result={self.result}, "
                f"item_id={self.item_id}, qty={self.new_quantity})")
