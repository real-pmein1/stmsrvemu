"""
MsgGSSetItemBlob - Request from game server to set item blob data.

This is used for custom item data (up to 1024 bytes of arbitrary binary data
that can be attached to items for game-specific purposes).

EMsg 937 - GSSetItemBlob (inferred from IDA callback analysis)
"""
import struct
from io import BytesIO


class MsgGSSetItemBlob:
    """
    MsgGSSetItemBlob - Request from game server to set item blob data.

    Structure from IDA analysis:
        - m_ulItemID: uint64 - Item ID to set blob for
        - m_unBlobSize: uint32 - Size of blob data
        - m_rgubData[]: bytes - Blob data (up to 1024 bytes)

    Response is MsgGSSetItemBlobResponse.
    Callback ID: 1509 (GSSetItemBlobResponse_t), size 12 bytes
    """

    MAX_BLOB_SIZE = 1024

    def __init__(self, item_id=0, blob_data=b''):
        self.item_id = item_id  # 64-bit item ID
        self.blob_data = blob_data[:self.MAX_BLOB_SIZE]  # Up to 1024 bytes

    def deserialize(self, byte_buffer):
        """Deserializes the byte buffer into a MsgGSSetItemBlob object."""
        stream = BytesIO(byte_buffer)

        # Read Item ID (uint64)
        self.item_id = struct.unpack('<Q', stream.read(8))[0]

        # Read Blob Size (uint32)
        blob_size = struct.unpack('<I', stream.read(4))[0]
        blob_size = min(blob_size, self.MAX_BLOB_SIZE)

        # Read Blob Data
        self.blob_data = stream.read(blob_size)

        return self

    def serialize(self):
        """Serializes the MsgGSSetItemBlob object into a byte buffer."""
        stream = BytesIO()

        # Write Item ID (uint64)
        stream.write(struct.pack('<Q', self.item_id))

        # Write Blob Size (uint32)
        stream.write(struct.pack('<I', len(self.blob_data)))

        # Write Blob Data
        stream.write(self.blob_data)

        return stream.getvalue()

    def __bytes__(self):
        return self.serialize()

    def __len__(self):
        return 12 + len(self.blob_data)  # 8 + 4 + data

    def __repr__(self):
        return f"MsgGSSetItemBlob(item_id={self.item_id}, blob_size={len(self.blob_data)})"
