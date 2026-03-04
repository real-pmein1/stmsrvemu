import struct
from io import BytesIO

from steam3.Types.Objects.PersistentItem import PersistentItem, PersistentItemAttribute


class MsgGSItemGranted:
    """
    MsgGSItemGranted - Notification that an item was granted to a user.

    Structure from IDA analysis (MsgClientItemGranted_t with CPersistentItem):
        - CPersistentItem serialized data containing:
            - m_ulItemID: uint64 - Unique item ID
            - m_SteamID: uint64 - Steam ID of the owner
            - m_unAppID: uint32 - Application ID
            - m_unDefinitionIndex: uint32 - Item definition index
            - m_unItemLevel: uint32 - Item level
            - m_eQuality: int32 - Item quality (signed, EItemQuality)
            - m_unInventoryToken: uint32 - Inventory position
            - attribute_count: uint32 - Number of attributes
            - attributes[]: Array of (uint32 def_index, float value)

    Sent by CM to game servers to notify that a player was granted an item.
    Uses extended header format which includes the item data.
    """

    def __init__(self, item=None):
        self.item = item  # PersistentItem object

    def deserialize(self, byte_buffer):
        """Deserializes the byte buffer into a MsgGSItemGranted object."""
        stream = BytesIO(byte_buffer)

        # Read item data
        item_id = struct.unpack('<Q', stream.read(8))[0]
        steam_id = struct.unpack('<Q', stream.read(8))[0]
        app_id = struct.unpack('<I', stream.read(4))[0]
        definition_index = struct.unpack('<I', stream.read(4))[0]
        item_level = struct.unpack('<I', stream.read(4))[0]
        quality = struct.unpack('<i', stream.read(4))[0]  # Signed
        inventory_token = struct.unpack('<I', stream.read(4))[0]
        attribute_count = struct.unpack('<I', stream.read(4))[0]

        # Read attributes
        attributes = []
        for _ in range(attribute_count):
            attr_def_index = struct.unpack('<I', stream.read(4))[0]
            attr_value = struct.unpack('<f', stream.read(4))[0]
            attributes.append(PersistentItemAttribute(attr_def_index, attr_value))

        self.item = PersistentItem(
            item_id=item_id,
            definition_index=definition_index,
            item_level=item_level,
            quality=quality,
            inventory_token=inventory_token,
            app_id=app_id,
            steam_id=steam_id,
            attributes=attributes
        )

        return self

    def serialize(self):
        """Serializes the MsgGSItemGranted object into a byte buffer."""
        if not self.item:
            return b''

        stream = BytesIO()

        # Write item data
        stream.write(struct.pack('<Q', self.item.item_id))
        stream.write(struct.pack('<Q', self.item.steam_id))
        stream.write(struct.pack('<I', self.item.app_id))
        stream.write(struct.pack('<I', self.item.definition_index))
        stream.write(struct.pack('<I', self.item.item_level))
        stream.write(struct.pack('<i', self.item.quality))  # Signed
        stream.write(struct.pack('<I', self.item.inventory_token))
        stream.write(struct.pack('<I', len(self.item.attributes)))

        # Write attributes
        for attr in self.item.attributes:
            stream.write(struct.pack('<If', attr.definition_index, attr.value))

        return stream.getvalue()

    def __bytes__(self):
        """Allow using bytes() on this object."""
        return self.serialize()

    def __len__(self):
        """Return the serialized length."""
        base_len = 40  # 8 + 8 + 4 + 4 + 4 + 4 + 4 + 4
        if self.item:
            base_len += len(self.item.attributes) * 8
        return base_len

    def __repr__(self):
        return f"MsgGSItemGranted(item={self.item})"
