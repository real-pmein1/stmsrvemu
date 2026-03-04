"""
MsgClientGetItemBlobResponse - Response to ClientGetItemBlob request.

EMsg 5422 - ClientGetItemBlobResponse
"""
import struct
from io import BytesIO


class MsgClientGetItemBlobResponse:
    """
    MsgClientGetItemBlobResponse - Response to ClientGetItemBlob request.

    Structure:
        - m_eResult: uint32 - Result code (EResult)
        - m_ulItemID: uint64 - Item ID
        - m_unBlobSize: uint32 - Size of blob data (max 1024)
        - m_rgubData[]: bytes - Blob data
    """

    MAX_BLOB_SIZE = 1024

    def __init__(self, result=1, item_id=0, blob_data=b''):
        self.result = result        # EResult value (1 = OK)
        self.item_id = item_id      # 64-bit item ID
        self.blob_data = blob_data[:self.MAX_BLOB_SIZE]

    def deserialize(self, byte_buffer):
        """Deserializes the byte buffer."""
        stream = BytesIO(byte_buffer)

        # Read Result (uint32)
        self.result = struct.unpack('<I', stream.read(4))[0]

        # Read Item ID (uint64)
        self.item_id = struct.unpack('<Q', stream.read(8))[0]

        # Read Blob Size (uint32)
        blob_size = struct.unpack('<I', stream.read(4))[0]
        blob_size = min(blob_size, self.MAX_BLOB_SIZE)

        # Read Blob Data
        self.blob_data = stream.read(blob_size)

        return self

    def serialize(self):
        """Serializes the object into a byte buffer."""
        stream = BytesIO()

        # Write Result (uint32)
        stream.write(struct.pack('<I', self.result))

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
        return 16 + len(self.blob_data)  # 4 + 8 + 4 + data

    def __repr__(self):
        return (f"MsgClientGetItemBlobResponse(result={self.result}, "
                f"item_id={self.item_id}, blob_size={len(self.blob_data)})")
