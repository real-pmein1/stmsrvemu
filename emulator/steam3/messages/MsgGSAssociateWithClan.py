"""
MsgGSAssociateWithClan - Request to associate a game server with a clan (EMsg 938)

Binary format (after SimpleClientMsgHdr):
    - uint64 m_ulSteamIDClan (8 bytes) - Steam ID of the clan to associate with

Sent by game servers to associate themselves with a specific clan.
Response uses EMsg 939 (GSAssociateWithClanResponse).
"""

import struct
from io import BytesIO


class MsgGSAssociateWithClan:
    def __init__(self, steam_id_clan=0):
        self.steam_id_clan = steam_id_clan  # 64-bit SteamID of the clan

    def deserialize(self, byte_buffer):
        """Deserializes the byte buffer into a MsgGSAssociateWithClan object."""
        stream = BytesIO(byte_buffer)

        # Read SteamID Clan (uint64)
        self.steam_id_clan = struct.unpack('<Q', stream.read(8))[0]

        return self

    def serialize(self):
        """Serializes the MsgGSAssociateWithClan object into a byte buffer."""
        stream = BytesIO()

        # Write SteamID Clan (uint64)
        stream.write(struct.pack('<Q', self.steam_id_clan))

        return stream.getvalue()

    def __bytes__(self):
        """Allow using bytes() on this object."""
        return self.serialize()

    def __len__(self):
        """Return the serialized length."""
        return 8  # 8 bytes for steam_id_clan

    def __repr__(self):
        return f"MsgGSAssociateWithClan(steam_id_clan={self.steam_id_clan:016x})"
