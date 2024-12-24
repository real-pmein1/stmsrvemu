import struct
from typing import List, Any

class PersistentItemAttribute:
    def __init__(self, definition_index: int, value: float):
        self.definition_index = definition_index
        self.value = value

    def serialize(self) -> bytes:
        return struct.pack('<If', self.definition_index, self.value)

    def __repr__(self):
        return f"PersistentItemAttribute(definition_index={self.definition_index}, value={self.value})"

class PersistentItem:
    def __init__(
        self,
        item_id: int,
        steam_id: int,
        app_id: int,
        definition_index: int,
        item_level: int,
        quality: int,
        inventory_token: int,
    ):
        self.item_id = item_id
        self.steam_id = steam_id
        self.app_id = app_id
        self.definition_index = definition_index
        self.item_level = item_level
        self.quality = quality
        self.inventory_token = inventory_token
        self.attributes: List[PersistentItemAttribute] = []

    def add_attribute(self, definition_index: int, value: float):
        self.attributes.append(PersistentItemAttribute(definition_index, value))

    def serialize(self) -> bytes:
        buffer = struct.pack(
            '<QIQIIII',
            self.item_id,
            self.steam_id,
            self.app_id,
            self.definition_index,
            self.item_level,
            self.quality,
            self.inventory_token,
        )
        buffer += struct.pack('<I', len(self.attributes))  # Number of attributes
        for attr in self.attributes:
            buffer += attr.serialize()
        return buffer

    def __repr__(self):
        return (
            f"PersistentItem(item_id={self.item_id}, steam_id={self.steam_id}, app_id={self.app_id}, "
            f"definition_index={self.definition_index}, item_level={self.item_level}, quality={self.quality}, "
            f"inventory_token={self.inventory_token}, attributes={self.attributes})"
        )

class EItemQuality:
    INVALID = 0xFFFFFFFE
    ANY = 0xFFFFFFFF
    NORMAL = 0
    COMMON = 1
    RARE = 2
    UNIQUE = 3
    COUNT = 4

class ClientLoadItemsResponse:
    def __init__(self, app_id: int, result_code: int = 0):
        self.app_id = app_id
        self.result_code = result_code
        self.items: List[PersistentItem] = []

    def add_item(self, item: PersistentItem):
        self.items.append(item)

    def serialize(self) -> bytes:
        buffer = struct.pack('<II', self.result_code, self.app_id)
        buffer += struct.pack('<I', len(self.items))  # Number of items

        for item in self.items:
            buffer += item.serialize()

        return buffer

    def __repr__(self) -> str:
        return (
            f"ClientLoadItemsResponse(app_id={self.app_id}, result_code={self.result_code}, "
            f"items={self.items})"
        )

    def __str__(self) -> str:
        item_strings = [str(item) for item in self.items]
        return (
            f"ClientLoadItemsResponse:\n"
            f"  App ID: {self.app_id}\n"
            f"  Result Code: {self.result_code}\n"
            f"  Items:\n    " + "\n    ".join(item_strings)
        )

# Example usage
"""response = ClientLoadItemsResponse(app_id=12345, result_code=1)
item = PersistentItem(
    item_id=1001,
    steam_id=76561198000000000,
    app_id=123,
    definition_index=10,
    item_level=5,
    quality=EItemQuality.UNIQUE,
    inventory_token=123456
)
item.add_attribute(definition_index=1, value=0.5)
item.add_attribute(definition_index=2, value=1.5)
response.add_item(item)

print(response)
serialized_data = response.serialize()
print(f"Serialized Data: {serialized_data.hex()}")
"""