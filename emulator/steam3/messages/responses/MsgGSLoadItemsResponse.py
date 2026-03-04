import struct
from io import BytesIO
from typing import List

from steam3.Types.Objects.PersistentItem import PersistentItem, PersistentItemAttribute


class MsgGSLoadItemsResponse:
    """
    MsgGSLoadItemsResponse - Response to GSLoadItems request.

    Structure from IDA analysis:
        - m_eResult: uint32 - Result code (EResult)
        - m_nItemCount: uint32 - Number of items in the response
        - items[]: Array of CPersistentItem serialized data

    Sent by CM server in response to GSLoadItems (EMsg 916).
    Response is EMsg 917 (GSLoadItemsResponse).
    """

    def __init__(self, result=1, steam_id=0):
        self.result = result  # EResult value (1 = OK)
        self.steam_id = steam_id  # Steam ID of the user whose items were loaded
        self.items: List[PersistentItem] = []

    def add_item(self, item):
        """Add an item to the response."""
        self.items.append(item)

    def deserialize(self, byte_buffer):
        """Deserializes the byte buffer into a MsgGSLoadItemsResponse object."""
        stream = BytesIO(byte_buffer)

        # Read Result (uint32)
        self.result = struct.unpack('<I', stream.read(4))[0]

        # Read Item Count (uint32)
        item_count = struct.unpack('<I', stream.read(4))[0]

        # Read items
        self.items = []
        for _ in range(item_count):
            # Read item data in same format as PersistentItem
            item_id = struct.unpack('<Q', stream.read(8))[0]
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

            item = PersistentItem(
                item_id=item_id,
                definition_index=definition_index,
                item_level=item_level,
                quality=quality,
                inventory_token=inventory_token,
                steam_id=self.steam_id,
                attributes=attributes
            )
            self.items.append(item)

        return self

    def serialize(self):
        """Serializes the MsgGSLoadItemsResponse object into a byte buffer."""
        stream = BytesIO()

        # Write Result (uint32)
        stream.write(struct.pack('<I', self.result))

        # Write Item Count (uint32)
        stream.write(struct.pack('<I', len(self.items)))

        # Write items
        for item in self.items:
            stream.write(item.serialize_for_load_response())

        return stream.getvalue()

    def __bytes__(self):
        """Allow using bytes() on this object."""
        return self.serialize()

    def __len__(self):
        """Return the serialized length."""
        base_len = 8  # result + count
        for item in self.items:
            # Base item size + attributes
            base_len += 28 + len(item.attributes) * 8
        return base_len

    def __repr__(self):
        return f"MsgGSLoadItemsResponse(result={self.result}, items={len(self.items)})"
