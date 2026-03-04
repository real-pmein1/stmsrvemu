"""
MsgGSSetItemBlobResponse - Response to GSSetItemBlob request.
"""
import struct
from io import BytesIO


class MsgGSSetItemBlobResponse:
    """
    MsgGSSetItemBlobResponse - Response to GSSetItemBlob request.

    Structure from IDA callback analysis (GSSetItemBlobResponse_t):
        - m_eResult: uint32 - Result code (EResult)
        - m_ulItemID: uint64 - Item ID

    Callback ID: 1509
    Callback size: 12 bytes (4 + 8)
    """

    def __init__(self, result=1, item_id=0):
        self.result = result    # EResult value (1 = OK)
        self.item_id = item_id  # 64-bit item ID

    def deserialize(self, byte_buffer):
        """Deserializes the byte buffer into a MsgGSSetItemBlobResponse object."""
        stream = BytesIO(byte_buffer)

        # Read Result (uint32)
        self.result = struct.unpack('<I', stream.read(4))[0]

        # Read Item ID (uint64)
        self.item_id = struct.unpack('<Q', stream.read(8))[0]

        return self

    def serialize(self):
        """Serializes the MsgGSSetItemBlobResponse object into a byte buffer."""
        stream = BytesIO()

        # Write Result (uint32)
        stream.write(struct.pack('<I', self.result))

        # Write Item ID (uint64)
        stream.write(struct.pack('<Q', self.item_id))

        return stream.getvalue()

    def __bytes__(self):
        return self.serialize()

    def __len__(self):
        return 12  # 4 + 8

    def __repr__(self):
        return f"MsgGSSetItemBlobResponse(result={self.result}, item_id={self.item_id})"
