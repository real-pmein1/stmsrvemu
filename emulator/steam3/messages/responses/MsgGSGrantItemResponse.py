import struct
from io import BytesIO

from steam3.Types.Objects.PersistentItem import PersistentItem, PersistentItemAttribute


class MsgGSGrantItemResponse:
    """
    MsgGSGrantItemResponse - Response to GSGrantItem request.

    Structure from IDA analysis:
        - m_eResult: uint32 - Result code (EResult)
        - m_ulSteamIDTarget: uint64 - Steam ID of the user who received the item
        - m_ulItemID: uint64 - The item ID that was granted (0 if failed)
        - CPersistentItem data (optional, only if successful)

    Sent by CM server in response to GSGrantItem (EMsg 924).
    Response is EMsg 925 (GSGrantItemResponse).
    """

    def __init__(self, result=1, steam_id_target=0, item_id=0, item=None):
        self.result = result  # EResult value (1 = OK)
        self.steam_id_target = steam_id_target  # Target user's Steam ID
        self.item_id = item_id  # Granted item ID (0 if failed)
        self.item = item  # Optional: Full item data for successful grants

    def deserialize(self, byte_buffer):
        """Deserializes the byte buffer into a MsgGSGrantItemResponse object."""
        stream = BytesIO(byte_buffer)

        # Read Result (uint32)
        self.result = struct.unpack('<I', stream.read(4))[0]

        # Read Target SteamID (uint64)
        self.steam_id_target = struct.unpack('<Q', stream.read(8))[0]

        # Read Item ID (uint64)
        self.item_id = struct.unpack('<Q', stream.read(8))[0]

        # If successful and more data available, read item
        remaining = byte_buffer[stream.tell():]
        if self.result == 1 and len(remaining) >= 24:
            definition_index = struct.unpack('<I', stream.read(4))[0]
            item_level = struct.unpack('<I', stream.read(4))[0]
            quality = struct.unpack('<i', stream.read(4))[0]
            inventory_token = struct.unpack('<I', stream.read(4))[0]
            attribute_count = struct.unpack('<I', stream.read(4))[0]

            attributes = []
            for _ in range(attribute_count):
                attr_def_index = struct.unpack('<I', stream.read(4))[0]
                attr_value = struct.unpack('<f', stream.read(4))[0]
                attributes.append(PersistentItemAttribute(attr_def_index, attr_value))

            self.item = PersistentItem(
                item_id=self.item_id,
                definition_index=definition_index,
                item_level=item_level,
                quality=quality,
                inventory_token=inventory_token,
                steam_id=self.steam_id_target,
                attributes=attributes
            )

        return self

    def serialize(self):
        """Serializes the MsgGSGrantItemResponse object into a byte buffer."""
        stream = BytesIO()

        # Write Result (uint32)
        stream.write(struct.pack('<I', self.result))

        # Write Target SteamID (uint64)
        stream.write(struct.pack('<Q', self.steam_id_target))

        # Write Item ID (uint64)
        stream.write(struct.pack('<Q', self.item_id))

        # Optionally write item data for successful grants
        if self.result == 1 and self.item:
            stream.write(struct.pack('<I', self.item.definition_index))
            stream.write(struct.pack('<I', self.item.item_level))
            stream.write(struct.pack('<i', self.item.quality))
            stream.write(struct.pack('<I', self.item.inventory_token))
            stream.write(struct.pack('<I', len(self.item.attributes)))
            for attr in self.item.attributes:
                stream.write(struct.pack('<If', attr.definition_index, attr.value))

        return stream.getvalue()

    def __bytes__(self):
        """Allow using bytes() on this object."""
        return self.serialize()

    def __len__(self):
        """Return the serialized length."""
        base_len = 20  # result + steam_id + item_id
        if self.result == 1 and self.item:
            base_len += 20 + len(self.item.attributes) * 8
        return base_len

    def __repr__(self):
        return (f"MsgGSGrantItemResponse(result={self.result}, "
                f"steam_id_target={self.steam_id_target}, item_id={self.item_id})")
