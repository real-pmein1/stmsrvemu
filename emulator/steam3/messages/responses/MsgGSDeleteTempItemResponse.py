import struct
from io import BytesIO


class MsgGSDeleteTempItemResponse:
    """
    MsgGSDeleteTempItemResponse - Response to GSDeleteTempItem request.

    Structure from IDA analysis:
        - m_eResult: uint32 - Result code (EResult)
        - m_ulSteamID: uint64 - Steam ID of the user
        - m_ulItemID: uint64 - The deleted item ID

    Sent by CM server in response to GSDeleteTempItem (EMsg 926).
    Response is EMsg 927 (GSDeleteTempItemResponse).
    """

    def __init__(self, result=1, steam_id=0, item_id=0):
        self.result = result  # EResult value (1 = OK)
        self.steam_id = steam_id  # User's Steam ID
        self.item_id = item_id  # Deleted item ID

    def deserialize(self, byte_buffer):
        """Deserializes the byte buffer into a MsgGSDeleteTempItemResponse object."""
        stream = BytesIO(byte_buffer)

        # Read Result (uint32)
        self.result = struct.unpack('<I', stream.read(4))[0]

        # Read SteamID (uint64)
        self.steam_id = struct.unpack('<Q', stream.read(8))[0]

        # Read Item ID (uint64)
        self.item_id = struct.unpack('<Q', stream.read(8))[0]

        return self

    def serialize(self):
        """Serializes the MsgGSDeleteTempItemResponse object into a byte buffer."""
        stream = BytesIO()

        # Write Result (uint32)
        stream.write(struct.pack('<I', self.result))

        # Write SteamID (uint64)
        stream.write(struct.pack('<Q', self.steam_id))

        # Write Item ID (uint64)
        stream.write(struct.pack('<Q', self.item_id))

        return stream.getvalue()

    def __bytes__(self):
        """Allow using bytes() on this object."""
        return self.serialize()

    def __len__(self):
        """Return the serialized length."""
        return 20  # 4 + 8 + 8 bytes

    def __repr__(self):
        return (f"MsgGSDeleteTempItemResponse(result={self.result}, "
                f"steam_id={self.steam_id}, item_id={self.item_id})")
