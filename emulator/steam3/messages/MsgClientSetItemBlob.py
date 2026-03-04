"""
MsgClientSetItemBlob - Client request to set item blob data.

EMsg 5423 - ClientSetItemBlob
"""
import struct
from io import BytesIO


class MsgClientSetItemBlob:
    """
    MsgClientSetItemBlob - Client request to set item blob data.

    Structure:
        - m_ulItemID: uint64 - Item ID to set blob for
        - m_unAppID: uint32 - Application ID
        - m_unBlobSize: uint32 - Size of blob data
        - m_rgubData[]: bytes - Blob data (up to 1024 bytes)

    Response is MsgClientSetItemBlobResponse (EMsg 5424).
    """

    MAX_BLOB_SIZE = 1024

    def __init__(self, data=None, item_id=0, app_id=0, blob_data=b''):
        self.item_id = item_id  # 64-bit item ID
        self.app_id = app_id    # 32-bit app ID
        self.blob_data = blob_data[:self.MAX_BLOB_SIZE]

        if data is not None:
            self.deserialize(data)

    def deserialize(self, byte_buffer):
        """Deserializes the byte buffer."""
        stream = BytesIO(byte_buffer)

        if len(byte_buffer) >= 16:
            # Read Item ID (uint64)
            self.item_id = struct.unpack('<Q', stream.read(8))[0]

            # Read App ID (uint32)
            self.app_id = struct.unpack('<I', stream.read(4))[0]

            # Read Blob Size (uint32)
            blob_size = struct.unpack('<I', stream.read(4))[0]
            blob_size = min(blob_size, self.MAX_BLOB_SIZE)

            # Read Blob Data
            self.blob_data = stream.read(blob_size)

        return self

    def serialize(self):
        """Serializes the object into a byte buffer."""
        stream = BytesIO()

        # Write Item ID (uint64)
        stream.write(struct.pack('<Q', self.item_id))

        # Write App ID (uint32)
        stream.write(struct.pack('<I', self.app_id))

        # Write Blob Size (uint32)
        stream.write(struct.pack('<I', len(self.blob_data)))

        # Write Blob Data
        stream.write(self.blob_data)

        return stream.getvalue()

    def __bytes__(self):
        return self.serialize()

    def __len__(self):
        return 16 + len(self.blob_data)  # 8 + 4 + 4 + data

    def __repr__(self):
        return f"MsgClientSetItemBlob(item_id={self.item_id}, app_id={self.app_id}, blob_size={len(self.blob_data)})"
