import struct

class PersistentItem:
    def __init__(self, item_id, definition_index, item_level, quality, inventory_token, quantity, attributes):
        self.item_id = item_id
        self.definition_index = definition_index
        self.item_level = item_level
        self.quality = quality
        self.inventory_token = inventory_token
        self.quantity = quantity
        self.attributes = attributes  # List of attribute dictionaries, each with "definition_index" and "value"

class ItemSerializer:
    def __init__(self, steam_id, app_id):
        self.steam_id = steam_id  # Steam ID of the owner (64-bit integer)
        self.app_id = app_id      # App ID associated with the items (32-bit integer)
        self.items = []           # List to hold PersistentItem instances

    def add_item(self, item):
        """
        Adds an item to the list.

        Args:
            item (PersistentItem): An instance of PersistentItem.
        """
        self.items.append(item)

    def remove_item(self, item_id):
        """
        Removes an item from the list by its item ID.

        Args:
            item_id (int): The ID of the item to remove.
        """
        self.items = [item for item in self.items if item.item_id != item_id]

    def edit_item(self, item_id, updated_item):
        """
        Edits an item in the list by its item ID.

        Args:
            item_id (int): The ID of the item to edit.
            updated_item (PersistentItem): The updated PersistentItem instance.
        """
        for idx, item in enumerate(self.items):
            if item.item_id == item_id:
                self.items[idx] = updated_item
                return

    def serialize(self):
        """
        Serializes all items into a byte string packet buffer.

        Returns:
            bytes: The serialized byte string buffer.
        """
        buffer = bytearray()

        # Write the item count
        buffer.extend(struct.pack("<I", len(self.items)))

        # Write the Steam ID (64-bit integer)
        buffer.extend(struct.pack("<Q", self.steam_id))

        # Write the App ID (32-bit integer)
        buffer.extend(struct.pack("<I", self.app_id))

        for item in self.items:
            # Write basic item properties
            buffer.extend(struct.pack("<Q", item.item_id))  # Item ID (64-bit)
            buffer.extend(struct.pack("<I", item.definition_index))  # Definition Index (32-bit)
            buffer.extend(struct.pack("<I", item.item_level))  # Item Level (32-bit)
            buffer.extend(struct.pack("<I", item.quality))  # Quality (32-bit)
            buffer.extend(struct.pack("<I", item.inventory_token))  # Inventory Token (32-bit)
            buffer.extend(struct.pack("<I", item.quantity))  # Quantity (32-bit)

            # Write attribute count
            buffer.extend(struct.pack("<I", len(item.attributes)))

            for attr in item.attributes:
                # Write each attribute
                buffer.extend(struct.pack("<I", attr["definition_index"]))  # Attribute Definition Index (32-bit)
                buffer.extend(struct.pack("<f", attr["value"]))  # Attribute Value (float)

        return bytes(buffer)

# Example usage
if __name__ == "__main__":
    serializer = ItemSerializer(steam_id=76561197960287930, app_id=730)

    # Add items
    serializer.add_item(PersistentItem(
        item_id=1,
        definition_index=1001,
        item_level=5,
        quality=2,
        inventory_token=12345,
        quantity=1,
        attributes=[
            {"definition_index": 2001, "value": 1.5},
            {"definition_index": 2002, "value": 2.0},
        ]
    ))

    serializer.add_item(PersistentItem(
        item_id=2,
        definition_index=1002,
        item_level=3,
        quality=1,
        inventory_token=67890,
        quantity=2,
        attributes=[
            {"definition_index": 2003, "value": 3.5},
        ]
    ))

    # Remove an item
    serializer.remove_item(1)

    # Edit an item
    serializer.edit_item(2, PersistentItem(
        item_id=2,
        definition_index=1003,
        item_level=4,
        quality=1,
        inventory_token=67890,
        quantity=3,
        attributes=[
            {"definition_index": 2004, "value": 4.5},
        ]
    ))

    # Serialize items into a buffer
    buffer = serializer.serialize()
    print(buffer)