"""
MsgClientSetItemBlobResponse - Response to ClientSetItemBlob request.

EMsg 5424 - ClientSetItemBlobResponse
"""
import struct
from io import BytesIO


class MsgClientSetItemBlobResponse:
    """
    MsgClientSetItemBlobResponse - Response to ClientSetItemBlob request.

    Structure:
        - m_eResult: uint32 - Result code (EResult)
        - m_ulItemID: uint64 - Item ID
    """

    def __init__(self, result=1, item_id=0):
        self.result = result    # EResult value (1 = OK)
        self.item_id = item_id  # 64-bit item ID

    def deserialize(self, byte_buffer):
        """Deserializes the byte buffer."""
        stream = BytesIO(byte_buffer)

        # Read Result (uint32)
        self.result = struct.unpack('<I', stream.read(4))[0]

        # Read Item ID (uint64)
        self.item_id = struct.unpack('<Q', stream.read(8))[0]

        return self

    def serialize(self):
        """Serializes the object into a byte buffer."""
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
        return f"MsgClientSetItemBlobResponse(result={self.result}, item_id={self.item_id})"
