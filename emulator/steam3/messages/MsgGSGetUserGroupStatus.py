import struct
from io import BytesIO


class MsgGSGetUserGroupStatus:
    """
    MsgGSGetUserGroupStatus - Request to check if a user is a member of a Steam group.

    Structure from IDA analysis (MsgGSGetUserGroupStatus_t):
        - m_ulSteamIDUser: uint64 - Steam ID of the user to check
        - m_ulSteamIDGroup: uint64 - Steam ID of the group to check membership in

    Sent by game servers to query user's group membership status.
    Response is handled by CGSClientJobReceiveUserGroupStatus.
    """

    def __init__(self, steam_id_user=0, steam_id_group=0):
        self.steam_id_user = steam_id_user  # 64-bit SteamID of the user
        self.steam_id_group = steam_id_group  # 64-bit SteamID of the group

    def deserialize(self, byte_buffer):
        """Deserializes the byte buffer into a MsgGSGetUserGroupStatus object."""
        stream = BytesIO(byte_buffer)

        # Read SteamID User (uint64)
        self.steam_id_user = struct.unpack('<Q', stream.read(8))[0]

        # Read SteamID Group (uint64)
        self.steam_id_group = struct.unpack('<Q', stream.read(8))[0]

        return self

    def serialize(self):
        """Serializes the MsgGSGetUserGroupStatus object into a byte buffer."""
        stream = BytesIO()

        # Write SteamID User (uint64)
        stream.write(struct.pack('<Q', self.steam_id_user))

        # Write SteamID Group (uint64)
        stream.write(struct.pack('<Q', self.steam_id_group))

        return stream.getvalue()

    def __bytes__(self):
        """Allow using bytes() on this object."""
        return self.serialize()

    def __len__(self):
        """Return the serialized length."""
        return 16  # 8 bytes for each steam_id

    def __repr__(self):
        return f"MsgGSGetUserGroupStatus(steam_id_user={self.steam_id_user}, steam_id_group={self.steam_id_group})"
