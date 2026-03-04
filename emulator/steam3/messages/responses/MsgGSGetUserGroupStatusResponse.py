import struct
from io import BytesIO


class MsgGSGetUserGroupStatusResponse:
    """
    MsgGSGetUserGroupStatusResponse - Response with user's group membership status.

    Structure from IDA analysis (MsgGSGetUserGroupStatusResponse_t):
        - m_ulSteamIDUser: uint64 - Steam ID of the user
        - m_ulSteamIDGroup: uint64 - Steam ID of the group
        - m_eClanRelationship: uint32 - EClanRelationship enum value
        - m_eClanRank: uint32 - EClanRank enum value

    Sent by CM server in response to GSGetUserGroupStatus.
    """

    def __init__(self, steam_id_user=0, steam_id_group=0, clan_relationship=0, clan_rank=0):
        self.steam_id_user = steam_id_user  # 64-bit SteamID of the user
        self.steam_id_group = steam_id_group  # 64-bit SteamID of the group
        self.clan_relationship = clan_relationship  # EClanRelationship enum value
        self.clan_rank = clan_rank  # EClanRank enum value

    def deserialize(self, byte_buffer):
        """Deserializes the byte buffer into a MsgGSGetUserGroupStatusResponse object."""
        stream = BytesIO(byte_buffer)

        # Read SteamID User (uint64)
        self.steam_id_user = struct.unpack('<Q', stream.read(8))[0]

        # Read SteamID Group (uint64)
        self.steam_id_group = struct.unpack('<Q', stream.read(8))[0]

        # Read ClanRelationship (uint32)
        self.clan_relationship = struct.unpack('<I', stream.read(4))[0]

        # Read ClanRank (uint32)
        self.clan_rank = struct.unpack('<I', stream.read(4))[0]

        return self

    def serialize(self):
        """Serializes the MsgGSGetUserGroupStatusResponse object into a byte buffer."""
        stream = BytesIO()

        # Write SteamID User (uint64)
        stream.write(struct.pack('<Q', self.steam_id_user))

        # Write SteamID Group (uint64)
        stream.write(struct.pack('<Q', self.steam_id_group))

        # Write ClanRelationship (uint32)
        stream.write(struct.pack('<I', self.clan_relationship))

        # Write ClanRank (uint32)
        stream.write(struct.pack('<I', self.clan_rank))

        return stream.getvalue()

    def __bytes__(self):
        """Allow using bytes() on this object."""
        return self.serialize()

    def __len__(self):
        """Return the serialized length."""
        return 24  # 8 + 8 + 4 + 4

    def __repr__(self):
        return (f"MsgGSGetUserGroupStatusResponse("
                f"steam_id_user={self.steam_id_user}, "
                f"steam_id_group={self.steam_id_group}, "
                f"clan_relationship={self.clan_relationship}, "
                f"clan_rank={self.clan_rank})")
