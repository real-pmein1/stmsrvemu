"""
MsgGSGetItemBlob - Request from game server to get item blob data.

This is used for custom item data (up to 1024 bytes of arbitrary binary data
that can be attached to items for game-specific purposes).

EMsg 936 - GSGetItemBlob (inferred from IDA callback analysis)
"""
import struct
from io import BytesIO


class MsgGSGetItemBlob:
    """
    MsgGSGetItemBlob - Request from game server to get item blob data.

    Structure from IDA analysis (MsgItemBlob_t):
        - m_ulItemID: uint64 - Item ID to get blob for

    Response is MsgGSGetItemBlobResponse.
    Callback ID: 1508 (GSGetItemBlobResponse_t), size 1040 bytes
    """

    def __init__(self, item_id=0):
        self.item_id = item_id  # 64-bit item ID

    def deserialize(self, byte_buffer):
        """Deserializes the byte buffer into a MsgGSGetItemBlob object."""
        stream = BytesIO(byte_buffer)

        # Read Item ID (uint64)
        self.item_id = struct.unpack('<Q', stream.read(8))[0]

        return self

    def serialize(self):
        """Serializes the MsgGSGetItemBlob object into a byte buffer."""
        stream = BytesIO()

        # Write Item ID (uint64)
        stream.write(struct.pack('<Q', self.item_id))

        return stream.getvalue()

    def __bytes__(self):
        return self.serialize()

    def __len__(self):
        return 8

    def __repr__(self):
        return f"MsgGSGetItemBlob(item_id={self.item_id})"
