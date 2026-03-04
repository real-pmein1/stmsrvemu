"""
MsgGSGetItemBlobResponse - Response to GSGetItemBlob request.

Contains up to 1024 bytes of item-specific blob data.
"""
import struct
from io import BytesIO


class MsgGSGetItemBlobResponse:
    """
    MsgGSGetItemBlobResponse - Response to GSGetItemBlob request.

    Structure from IDA callback analysis (GSGetItemBlobResponse_t):
        - m_eResult: uint32 - Result code (EResult)
        - m_ulItemID: uint64 - Item ID
        - m_unBlobSize: uint32 - Size of blob data (max 1024)
        - m_rgubData[1024]: bytes - Blob data (fixed 1024 byte buffer)

    Callback ID: 1508
    Callback size: 1040 bytes (4 + 8 + 4 + 1024)
    """

    MAX_BLOB_SIZE = 1024

    def __init__(self, result=1, item_id=0, blob_data=b''):
        self.result = result        # EResult value (1 = OK)
        self.item_id = item_id      # 64-bit item ID
        self.blob_data = blob_data[:self.MAX_BLOB_SIZE]  # Up to 1024 bytes

    def deserialize(self, byte_buffer):
        """Deserializes the byte buffer into a MsgGSGetItemBlobResponse object."""
        stream = BytesIO(byte_buffer)

        # Read Result (uint32)
        self.result = struct.unpack('<I', stream.read(4))[0]

        # Read Item ID (uint64)
        self.item_id = struct.unpack('<Q', stream.read(8))[0]

        # Read Blob Size (uint32)
        blob_size = struct.unpack('<I', stream.read(4))[0]
        blob_size = min(blob_size, self.MAX_BLOB_SIZE)

        # Read Blob Data (up to 1024 bytes)
        self.blob_data = stream.read(blob_size)

        return self

    def serialize(self):
        """Serializes the MsgGSGetItemBlobResponse object into a byte buffer."""
        stream = BytesIO()

        # Write Result (uint32)
        stream.write(struct.pack('<I', self.result))

        # Write Item ID (uint64)
        stream.write(struct.pack('<Q', self.item_id))

        # Write Blob Size (uint32)
        blob_size = len(self.blob_data)
        stream.write(struct.pack('<I', blob_size))

        # Write Blob Data (padded to 1024 bytes for fixed-size callback struct)
        padded_data = self.blob_data.ljust(self.MAX_BLOB_SIZE, b'\x00')
        stream.write(padded_data)

        return stream.getvalue()

    def __bytes__(self):
        return self.serialize()

    def __len__(self):
        return 1040  # 4 + 8 + 4 + 1024 (fixed size for callback)

    def __repr__(self):
        return (f"MsgGSGetItemBlobResponse(result={self.result}, "
                f"item_id={self.item_id}, blob_size={len(self.blob_data)})")
