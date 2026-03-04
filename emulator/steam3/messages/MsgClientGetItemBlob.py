"""
MsgClientGetItemBlob - Client request to get item blob data.

EMsg 5421 - ClientGetItemBlob
"""
import struct
from io import BytesIO


class MsgClientGetItemBlob:
    """
    MsgClientGetItemBlob - Client request to get item blob data.

    Structure from IDA analysis:
        - m_ulItemID: uint64 - Item ID to get blob for
        - m_unAppID: uint32 - Application ID

    Response is MsgClientGetItemBlobResponse (EMsg 5422).
    """

    def __init__(self, data=None, item_id=0, app_id=0):
        self.item_id = item_id  # 64-bit item ID
        self.app_id = app_id    # 32-bit app ID

        if data is not None:
            self.deserialize(data)

    def deserialize(self, byte_buffer):
        """Deserializes the byte buffer."""
        stream = BytesIO(byte_buffer)

        if len(byte_buffer) >= 12:
            # Read Item ID (uint64)
            self.item_id = struct.unpack('<Q', stream.read(8))[0]

            # Read App ID (uint32)
            self.app_id = struct.unpack('<I', stream.read(4))[0]

        return self

    def serialize(self):
        """Serializes the object into a byte buffer."""
        stream = BytesIO()

        # Write Item ID (uint64)
        stream.write(struct.pack('<Q', self.item_id))

        # Write App ID (uint32)
        stream.write(struct.pack('<I', self.app_id))

        return stream.getvalue()

    def __bytes__(self):
        return self.serialize()

    def __len__(self):
        return 12  # 8 + 4

    def __repr__(self):
        return f"MsgClientGetItemBlob(item_id={self.item_id}, app_id={self.app_id})"
