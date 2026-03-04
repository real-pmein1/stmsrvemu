"""
MsgClientAcknowledgeClanInvite - Client accepts or rejects a clan invitation

Message ID: 745 (EMsg.ClientAcknowledgeClanInvite)
Direction: Client → Server

Structure:
    uint64  clan_steam_id  - Steam ID of the clan
    bool    accept         - True to accept, false to reject
"""

import struct
from io import BytesIO


class MsgClientAcknowledgeClanInvite:
    """
    Client response to accept or reject a clan invitation.

    Based on Steam protocol reverse engineering analysis.
    """

    def __init__(self, client_obj=None, data=None):
        self.clan_steam_id = 0
        self.accept = False

        if data:
            self.deserialize(data)

    def __str__(self):
        action = "ACCEPT" if self.accept else "REJECT"
        return (
            f"MsgClientAcknowledgeClanInvite(\n"
            f"  Clan Steam ID: {self.clan_steam_id:016x}\n"
            f"  Action: {action}\n"
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

        # Read accept flag (1 byte boolean)
        self.accept = struct.unpack('<?', stream.read(1))[0]

        # Check for leftover bytes
        remaining = stream.read()
        if remaining:
            print(f"Warning: MsgClientAcknowledgeClanInvite has unparsed bytes: {remaining.hex()}")

    def serialize(self):
        """
        Serialize message fields to byte buffer.

        Returns:
            bytes - Serialized binary data
        """
        buffer = BytesIO()

        # Write clan Steam ID (8 bytes)
        buffer.write(struct.pack('<Q', self.clan_steam_id))

        # Write accept flag (1 byte boolean)
        buffer.write(struct.pack('<?', self.accept))

        return buffer.getvalue()
