import struct
from io import BytesIO


class MsgGSLoadItems:
    """
    MsgGSLoadItems - Request from game server to load items for a user.

    Structure from IDA analysis (MsgGSLoadItems_t):
        - m_ulSteamID: uint64 - Steam ID of the user to load items for

    Sent by game servers to request a player's inventory.
    Response is MsgGSLoadItemsResponse.
    """

    def __init__(self, steam_id=0):
        self.steam_id = steam_id  # 64-bit SteamID

    def deserialize(self, byte_buffer):
        """Deserializes the byte buffer into a MsgGSLoadItems object."""
        stream = BytesIO(byte_buffer)

        # Read SteamID (uint64)
        self.steam_id = struct.unpack('<Q', stream.read(8))[0]

        return self

    def serialize(self):
        """Serializes the MsgGSLoadItems object into a byte buffer."""
        stream = BytesIO()

        # Write SteamID (uint64)
        stream.write(struct.pack('<Q', self.steam_id))

        return stream.getvalue()

    def __bytes__(self):
        return self.serialize()

    def __len__(self):
        return 8

    def __repr__(self):
        return f"MsgGSLoadItems(steam_id={self.steam_id})"
