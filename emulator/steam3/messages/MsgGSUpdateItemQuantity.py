"""
MsgGSUpdateItemQuantity - Request from game server to update item quantity.

EMsg 931 - GSUpdateItemQuantity
"""
import struct
from io import BytesIO


class MsgGSUpdateItemQuantity:
    """
    MsgGSUpdateItemQuantity - Request from game server to update item quantity.

    Structure from IDA analysis (MsgGSUpdateItemQuantity_t):
        - m_ulItemID: uint64 - Item ID to update
        - m_steamIDOwner: uint64 - Steam ID of the item owner
        - m_unAppID: uint32 - Application ID
        - m_unNewQuantity: uint32 - New quantity value

    Sent by game servers to update the quantity of an item (consumables, etc).
    Response is MsgGSUpdateItemQuantityResponse (EMsg 932).
    """

    def __init__(self, item_id=0, steam_id_owner=0, app_id=0, new_quantity=1):
        self.item_id = item_id          # 64-bit item ID
        self.steam_id_owner = steam_id_owner  # 64-bit SteamID
        self.app_id = app_id            # 32-bit app ID
        self.new_quantity = new_quantity  # 32-bit new quantity

    def deserialize(self, byte_buffer):
        """Deserializes the byte buffer into a MsgGSUpdateItemQuantity object."""
        stream = BytesIO(byte_buffer)

        # Read Item ID (uint64)
        self.item_id = struct.unpack('<Q', stream.read(8))[0]

        # Read Steam ID Owner (uint64)
        self.steam_id_owner = struct.unpack('<Q', stream.read(8))[0]

        # Read App ID (uint32)
        self.app_id = struct.unpack('<I', stream.read(4))[0]

        # Read New Quantity (uint32)
        self.new_quantity = struct.unpack('<I', stream.read(4))[0]

        return self

    def serialize(self):
        """Serializes the MsgGSUpdateItemQuantity object into a byte buffer."""
        stream = BytesIO()

        # Write Item ID (uint64)
        stream.write(struct.pack('<Q', self.item_id))

        # Write Steam ID Owner (uint64)
        stream.write(struct.pack('<Q', self.steam_id_owner))

        # Write App ID (uint32)
        stream.write(struct.pack('<I', self.app_id))

        # Write New Quantity (uint32)
        stream.write(struct.pack('<I', self.new_quantity))

        return stream.getvalue()

    def __bytes__(self):
        return self.serialize()

    def __len__(self):
        return 24  # 8 + 8 + 4 + 4

    def __repr__(self):
        return (f"MsgGSUpdateItemQuantity(item_id={self.item_id}, "
                f"owner={self.steam_id_owner}, app={self.app_id}, qty={self.new_quantity})")
