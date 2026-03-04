import struct
from io import BytesIO


class MsgGSGrantItem:
    """
    MsgGSGrantItem - Request from game server to grant an item to a user.

    Structure from IDA analysis (MsgGSGrantItem_t):
        - m_ulItemID: uint64 - Item ID to grant
        - m_ulSteamIDTarget: uint64 - Steam ID of the user to grant the item to

    Sent by game servers to grant an item from their inventory to a player.
    Response is MsgGSGrantItemResponse.
    """

    def __init__(self, item_id=0, steam_id_target=0):
        self.item_id = item_id  # 64-bit Item ID
        self.steam_id_target = steam_id_target  # 64-bit target SteamID

    def deserialize(self, byte_buffer):
        """Deserializes the byte buffer into a MsgGSGrantItem object."""
        stream = BytesIO(byte_buffer)

        # Read Item ID (uint64)
        self.item_id = struct.unpack('<Q', stream.read(8))[0]

        # Read Target SteamID (uint64)
        self.steam_id_target = struct.unpack('<Q', stream.read(8))[0]

        return self

    def serialize(self):
        """Serializes the MsgGSGrantItem object into a byte buffer."""
        stream = BytesIO()

        # Write Item ID (uint64)
        stream.write(struct.pack('<Q', self.item_id))

        # Write Target SteamID (uint64)
        stream.write(struct.pack('<Q', self.steam_id_target))

        return stream.getvalue()

    def __bytes__(self):
        return self.serialize()

    def __len__(self):
        return 16

    def __repr__(self):
        return f"MsgGSGrantItem(item_id={self.item_id}, steam_id_target={self.steam_id_target})"
