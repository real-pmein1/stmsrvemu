"""
Persistent inventory item classes for TF2-era item system (2008/2009).

Based on reverse engineering of steamclient CClientItem structure.
"""
import struct
from typing import List


class EItemQuality:
    """Item quality enum matching Steam's EItemQuality."""
    INVALID = -2  # 0xFFFFFFFE as signed
    ANY = -1      # 0xFFFFFFFF as signed
    NORMAL = 0
    COMMON = 1
    RARE = 2
    UNIQUE = 3
    COUNT = 4


class PersistentItemAttribute:
    """Represents an item attribute (definition_index, float value)."""
    def __init__(self, definition_index: int, value: float):
        self.definition_index = definition_index
        self.value = value

    def serialize(self) -> bytes:
        """Serialize attribute: uint32 def_index + float value."""
        return struct.pack('<If', self.definition_index, self.value)

    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> tuple:
        """Deserialize attribute from bytes. Returns (attribute, bytes_consumed)."""
        def_index, value = struct.unpack_from('<If', data, offset)
        return cls(def_index, value), 8

    def __repr__(self):
        return f"Attr({self.definition_index}={self.value})"


class PersistentItem:
    """
    Represents a persistent inventory item.

    For EMsg 886 (LoadItemsResponse), items are serialized as:
        - m_ulID (uint64): Unique item ID
        - m_unDefIndex (uint32): Item definition index
        - m_unLevel (uint32): Item level
        - m_eQuality (int32): Item quality (signed)
        - m_unInventoryPos (uint32): Inventory position/token
        - attribute_count (uint32): Number of attributes
        - attributes[]: Array of (uint32 def_index, float value)

    For EMsg 887 (ItemGranted), items include app_id at the start.
    """
    def __init__(
        self,
        item_id: int,
        definition_index: int,
        item_level: int,
        quality: int,
        inventory_token: int,
        app_id: int = 0,
        steam_id: int = 0,
        quantity: int = 1,
        attributes: list = None,
    ):
        self.item_id = item_id
        self.definition_index = definition_index
        self.item_level = item_level
        self.quality = quality
        self.inventory_token = inventory_token
        self.app_id = app_id
        self.steam_id = steam_id
        self.quantity = quantity
        self.attributes: List[PersistentItemAttribute] = []
        # Support legacy dict-style attributes
        if attributes:
            for attr in attributes:
                if isinstance(attr, dict):
                    self.add_attribute(attr.get("definition_index", 0), attr.get("value", 0.0))
                elif isinstance(attr, PersistentItemAttribute):
                    self.attributes.append(attr)

    def add_attribute(self, definition_index: int, value: float):
        self.attributes.append(PersistentItemAttribute(definition_index, value))

    def serialize_for_load_response(self) -> bytes:
        """
        Serialize for EMsg 886 (ClientLoadItemsResponse).
        Format: item_id(Q) + def_index(I) + level(I) + quality(i) + inv_pos(I) + attr_count(I) + attrs
        """
        buffer = struct.pack(
            '<QIIiII',
            self.item_id,
            self.definition_index,
            self.item_level,
            self.quality,
            self.inventory_token,
            len(self.attributes)
        )
        for attr in self.attributes:
            buffer += attr.serialize()
        return buffer

    def serialize_for_item_granted(self) -> bytes:
        """
        Serialize for EMsg 887 (ClientItemGranted).
        Format: app_id(I) + def_index(I) + level(I) + quality(i) + inv_pos(I) + attr_count(I) + attrs
        """
        buffer = struct.pack(
            '<IIIiII',
            self.app_id,
            self.definition_index,
            self.item_level,
            self.quality,
            self.inventory_token,
            len(self.attributes)
        )
        for attr in self.attributes:
            buffer += attr.serialize()
        return buffer

    @classmethod
    def from_db_model(cls, db_item) -> 'PersistentItem':
        """Create PersistentItem from database model."""
        item = cls(
            item_id=db_item.item_id,
            definition_index=db_item.definition_index,
            item_level=db_item.item_level,
            quality=db_item.quality,
            inventory_token=db_item.inventory_token,
            app_id=db_item.app_id,
            steam_id=db_item.steam_id,
            quantity=getattr(db_item, 'quantity', 1),
        )
        # Add attributes from relationship
        if hasattr(db_item, 'attributes') and db_item.attributes:
            for attr in db_item.attributes:
                item.add_attribute(attr.definition_index, attr.value)
        return item

    def __repr__(self):
        return (f"Item(id={self.item_id}, def={self.definition_index}, "
                f"lvl={self.item_level}, qual={self.quality}, pos={self.inventory_token}, "
                f"attrs={self.attributes})")


class ItemSerializer:
    """Helper class to serialize multiple items for a response."""
    def __init__(self, steam_id: int = 0, app_id: int = 0):
        self.steam_id = steam_id
        self.app_id = app_id
        self.items: List[PersistentItem] = []

    def add_item(self, item: PersistentItem):
        self.items.append(item)

    def remove_item(self, item_id: int):
        self.items = [item for item in self.items if item.item_id != item_id]

    def serialize(self) -> bytes:
        """Serialize all items for load response."""
        buffer = bytearray()
        for item in self.items:
            buffer.extend(item.serialize_for_load_response())
        return bytes(buffer)
