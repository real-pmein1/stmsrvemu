"""
MsgClientInviteUserToClan - Client request to invite a user to a clan

Message ID: 744 (EMsg.ClientInviteUserToClan)
Direction: Client → Server

Structure:
    uint64  clan_steam_id     - Steam ID of the clan
    uint64  invitee_steam_id  - Steam ID of user to invite
"""

import struct
from io import BytesIO


class MsgClientInviteUserToClan:
    """
    Client request to invite a user to a clan.

    Based on Steam protocol reverse engineering analysis.
    """

    def __init__(self, client_obj=None, data=None):
        self.clan_steam_id = 0
        self.invitee_steam_id = 0

        if data:
            self.deserialize(data)

    def __str__(self):
        return (
            f"MsgClientInviteUserToClan(\n"
            f"  Clan Steam ID: {self.clan_steam_id:016x}\n"
            f"  Invitee Steam ID: {self.invitee_steam_id:016x}\n"
            f")"
        )

    def deserialize(self, data):
        """
        Deserialize byte buffer to populate message fields.

        Args:
            data: bytes - Binary data to deserialize
        """
        stream = BytesIO(data)

        # Read clan Steam ID (8 bytes)
        self.clan_steam_id = struct.unpack('<Q', stream.read(8))[0]

        # Read invitee Steam ID (8 bytes)
        self.invitee_steam_id = struct.unpack('<Q', stream.read(8))[0]

        # Check for leftover bytes
        remaining = stream.read()
        if remaining:
            print(f"Warning: MsgClientInviteUserToClan has unparsed bytes: {remaining.hex()}")

    def serialize(self):
        """
        Serialize message fields to byte buffer.

        Returns:
            bytes - Serialized binary data
        """
        buffer = BytesIO()

        # Write clan Steam ID (8 bytes)
        buffer.write(struct.pack('<Q', self.clan_steam_id))

        # Write invitee Steam ID (8 bytes)
        buffer.write(struct.pack('<Q', self.invitee_steam_id))

        return buffer.getvalue()
