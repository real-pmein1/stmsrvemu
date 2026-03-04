import struct
from io import BytesIO


class MsgGSDeleteAllTempItemsResponse:
    """
    MsgGSDeleteAllTempItemsResponse - Response to GSDeleteAllTempItems request.

    Structure from IDA analysis:
        - m_eResult: uint32 - Result code (EResult)
        - m_ulSteamID: uint64 - Steam ID of the user
        - m_nDeletedCount: uint32 - Number of items that were deleted

    Sent by CM server in response to GSDeleteAllTempItems (EMsg 928).
    Response is EMsg 929 (GSDeleteAllTempItemsResponse).
    """

    def __init__(self, result=1, steam_id=0, deleted_count=0):
        self.result = result  # EResult value (1 = OK)
        self.steam_id = steam_id  # User's Steam ID
        self.deleted_count = deleted_count  # Number of items deleted

    def deserialize(self, byte_buffer):
        """Deserializes the byte buffer into a MsgGSDeleteAllTempItemsResponse object."""
        stream = BytesIO(byte_buffer)

        # Read Result (uint32)
        self.result = struct.unpack('<I', stream.read(4))[0]

        # Read SteamID (uint64)
        self.steam_id = struct.unpack('<Q', stream.read(8))[0]

        # Read Deleted Count (uint32)
        self.deleted_count = struct.unpack('<I', stream.read(4))[0]

        return self

    def serialize(self):
        """Serializes the MsgGSDeleteAllTempItemsResponse object into a byte buffer."""
        stream = BytesIO()

        # Write Result (uint32)
        stream.write(struct.pack('<I', self.result))

        # Write SteamID (uint64)
        stream.write(struct.pack('<Q', self.steam_id))

        # Write Deleted Count (uint32)
        stream.write(struct.pack('<I', self.deleted_count))

        return stream.getvalue()

    def __bytes__(self):
        """Allow using bytes() on this object."""
        return self.serialize()

    def __len__(self):
        """Return the serialized length."""
        return 16  # 4 + 8 + 4 bytes

    def __repr__(self):
        return (f"MsgGSDeleteAllTempItemsResponse(result={self.result}, "
                f"steam_id={self.steam_id}, deleted_count={self.deleted_count})")
