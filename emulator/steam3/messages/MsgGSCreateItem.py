import struct
from io import BytesIO


class MsgGSCreateItem:
    """
    MsgGSCreateItem - Request from game server to create an item.

    Structure from IDA analysis (MsgGSCreateItem_t):
        - m_ulSteamID: uint64 - Steam ID of the user to create item for
        - m_nAppID: uint32 - Application ID
        - m_unDefinitionIndex: uint32 - Item definition index
        - m_eQuality: int32 - Item quality (EItemQuality, signed)

    Sent by game servers to create a new item for a player.
    Response is MsgGSCreateItemResponse.
    """

    def __init__(self, steam_id=0, app_id=0, definition_index=0, quality=0):
        self.steam_id = steam_id  # 64-bit SteamID
        self.app_id = app_id  # 32-bit Application ID
        self.definition_index = definition_index  # 32-bit item definition index
        self.quality = quality  # 32-bit signed quality (EItemQuality)

    def deserialize(self, byte_buffer):
        """Deserializes the byte buffer into a MsgGSCreateItem object."""
        stream = BytesIO(byte_buffer)

        # Read SteamID (uint64)
        self.steam_id = struct.unpack('<Q', stream.read(8))[0]

        # Read App ID (uint32)
        self.app_id = struct.unpack('<I', stream.read(4))[0]

        # Read Definition Index (uint32)
        self.definition_index = struct.unpack('<I', stream.read(4))[0]

        # Read Quality (int32, signed)
        self.quality = struct.unpack('<i', stream.read(4))[0]

        return self

    def serialize(self):
        """Serializes the MsgGSCreateItem object into a byte buffer."""
        stream = BytesIO()

        # Write SteamID (uint64)
        stream.write(struct.pack('<Q', self.steam_id))

        # Write App ID (uint32)
        stream.write(struct.pack('<I', self.app_id))

        # Write Definition Index (uint32)
        stream.write(struct.pack('<I', self.definition_index))

        # Write Quality (int32, signed)
        stream.write(struct.pack('<i', self.quality))

        return stream.getvalue()

    def __bytes__(self):
        """Allow using bytes() on this object."""
        return self.serialize()

    def __len__(self):
        """Return the serialized length."""
        return 20  # 8 + 4 + 4 + 4 bytes

    def __repr__(self):
        return (f"MsgGSCreateItem(steam_id={self.steam_id}, app_id={self.app_id}, "
                f"definition_index={self.definition_index}, quality={self.quality})")
