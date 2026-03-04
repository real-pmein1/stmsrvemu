"""
MsgClientClanState - Binary format for clan state updates (EMsg 822)

Binary format (after SimpleClientMsgHdr):
  - uint64 m_ulClanID (8 bytes) - Clan Steam ID
  - uint32 m_unStatusFlags (4 bytes) - ClanStateFlags bitmask
  - uint8 m_ubClanAccountFlags (1 bytes) - ClanAccountFlags bitmask

Variable data based on status flags:
  - If flag & 0x01 (name): null-terminated clan name + 20 bytes avatar SHA1
  - If flag & 0x02 (userCounts): 4 x uint32 (members, online, in_chat, in_game)
  - If flag & 0x0C (events/announcements): uint32 count + event data
    Each event: uint64 gid, uint32 time, null-terminated headline, uint64 game_id, uint8 just_posted
"""

import struct
from io import BytesIO
from enum import IntFlag

from steam3.Types.community_types import ClanStateFlags, ClanAccountFlags


class MsgClientClanState:
    def __init__(self):
        self.steam_id_clan = 0
        self.clan_state_flags = 0  # ClanStateFlags: name=0x01, userCounts=0x02, announcements=0x04, events=0x08
        self.clan_account_flags = 0  # ClanAccountFlags: public=0x01, large=0x02, locked=0x04, disabled=0x08
        # Convenience properties derived from clan_account_flags
        self.m_bPublic = False
        self.m_bLarge = False
        self.m_bLocked = False
        self.m_bDisabled = False
        # Data fields
        self.name_info = {}  # {"clan_name": str, "avatar_sha": bytes(20)}
        self.user_counts = {}  # {"members": int, "online": int, "in_chat": int, "in_game": int}
        self.announcements = []  # List of event dicts
        self.events = []  # List of event dicts

    def __str__(self):
        """
        Provide a human-readable string representation of the object's contents.
        """
        # Decode state flags
        state_flags = []
        if self.clan_state_flags & ClanStateFlags.name:
            state_flags.append("Name")
        if self.clan_state_flags & ClanStateFlags.userCounts:
            state_flags.append("User Counts")
        if self.clan_state_flags & ClanStateFlags.announcements:
            state_flags.append("Announcements")
        if self.clan_state_flags & ClanStateFlags.events:
            state_flags.append("Events")
        state_flags_str = ", ".join(state_flags) if state_flags else "None"

        account_flags = []
        if self.m_bPublic:
            account_flags.append("Public")
        if self.m_bLarge:
            account_flags.append("Large")
        if self.m_bLocked:
            account_flags.append("Locked")
        if self.m_bDisabled:
            account_flags.append("Disabled")

        account_flags_str = ", ".join(account_flags) if account_flags else "None"

        return (
            f"MsgClientClanState(\n"
            f"  Steam ID Clan: {self.steam_id_clan}\n"
            f"  Clan State Flags: {state_flags_str}\n"
            f"  Clan Account Flags: {account_flags_str}\n"
            f"  Name Info: {self.name_info}\n"
            f"  User Counts: {self.user_counts}\n"
            f"  Announcements: {self.announcements}\n"
            f"  Events: {self.events}\n"
            f")"
        )

    def deserialize(self, buffer):
        """
        Deserialize a byte buffer to populate the MsgClientClanState fields.
        """
        stream = BytesIO(buffer)

        # Read Steam ID (8 bytes)
        self.steam_id_clan = struct.unpack('<Q', stream.read(8))[0]

        # Read status flags (4 bytes) - determines what data follows
        self.clan_state_flags = struct.unpack('<I', stream.read(4))[0]

        # Read account flags (1 byte) - public/large/locked/disabled
        self.clan_account_flags = struct.unpack('<B', stream.read(1))[0]
        self.m_bPublic = bool(self.clan_account_flags & ClanAccountFlags.public)
        self.m_bLarge = bool(self.clan_account_flags & ClanAccountFlags.large)
        self.m_bLocked = bool(self.clan_account_flags & ClanAccountFlags.locked)
        self.m_bDisabled = bool(self.clan_account_flags & ClanAccountFlags.disabled)

        # Parse Name Info if name flag is set
        if self.clan_state_flags & ClanStateFlags.name:
            self.name_info = self._parse_name_info(stream)

        # Parse User Counts if userCounts flag is set
        if self.clan_state_flags & ClanStateFlags.userCounts:
            self.user_counts = self._parse_user_counts(stream)

        # Parse Events/Announcements if either flag is set (they share format)
        # Flag 0x04 = announcements, Flag 0x08 = events
        if self.clan_state_flags & (ClanStateFlags.announcements | ClanStateFlags.events):
            event_list = self._parse_events(stream)
            # Distribute to announcements or events based on flag
            if self.clan_state_flags & ClanStateFlags.announcements:
                self.announcements = event_list
            if self.clan_state_flags & ClanStateFlags.events:
                self.events = event_list

    def serialize(self):
        """
        Serialize the MsgClientClanState fields to a byte buffer.
        """
        buffer = BytesIO()

        # Write Steam ID (8 bytes)
        buffer.write(struct.pack('<Q', self.steam_id_clan))

        # Write clan account flags (4 bytes)
        buffer.write(struct.pack('<I', self.clan_state_flags))
        # Initialize byte value
        byte_value = 0

        # Set Bit 0 for m_bPublic
        if self.m_bPublic:
            byte_value |= 1  # Set the least significant bit (LSB)

        if self.m_bLarge:
            byte_value |= 2  # Set the second bit

        if self.m_bLocked:
            byte_value |= 4  # Set the second bit

        if self.m_bDisabled:
            byte_value |= 8  # Set the second bit

        # Pack the byte into a binary format
        buffer.write(struct.pack('<B', byte_value))

        # Serialize Name Info if NAME_INFO flag is set
        if self.clan_state_flags & ClanStateFlags.name:
            self._serialize_name_info(buffer)

        # Serialize User Counts if USER_COUNTS flag is set
        if self.clan_state_flags & ClanStateFlags.userCounts:
            self._serialize_user_counts(buffer)

        # Serialize Announcements if ANNOUNCEMENTS flag is set
        if self.clan_state_flags & ClanStateFlags.announcements:
            self._serialize_announcements(buffer)

        # Serialize Events if EVENTS flag is set
        if self.clan_state_flags & ClanStateFlags.events:
            self._serialize_events(buffer)

        return buffer.getvalue()

    def _parse_name_info(self, stream):
        """
        Parse Name Info including clan name and avatar SHA1 hash.
        """
        # Parse clan name as a null-terminated string
        clan_name = b""
        while True:
            char = stream.read(1)
            if char == b"\x00" or not char:
                break
            clan_name += char
        clan_name = clan_name.decode("utf-8", errors="replace")

        # Parse avatar SHA1 hash (always 20 bytes, raw binary)
        avatar_sha = stream.read(20)

        return {"clan_name": clan_name, "avatar_sha": avatar_sha}

    def _parse_user_counts(self, stream):
        """
        Parse user counts: members, online, in_chat, in_game.
        """
        members = struct.unpack('<I', stream.read(4))[0]
        online = struct.unpack('<I', stream.read(4))[0]
        in_chat = struct.unpack('<I', stream.read(4))[0]
        in_game = struct.unpack('<I', stream.read(4))[0]
        return {"members": members, "online": online, "in_chat": in_chat, "in_game": in_game}

    def _parse_announcements(self, stream):
        """
        Parse announcements. Same format as events (not currently used - deserialize uses _parse_events for both).
        Each announcement: uint64 gid, uint32 time, null-terminated headline, uint64 game_id, uint8 just_posted
        """
        num_announcements = struct.unpack('<I', stream.read(4))[0]
        announcements = []
        for _ in range(num_announcements):
            event_id = struct.unpack('<Q', stream.read(8))[0]
            event_time = struct.unpack('<I', stream.read(4))[0]
            headline = b""
            while True:
                char = stream.read(1)
                if char == b"\x00" or not char:
                    break
                headline += char
            headline = headline.decode("utf-8")
            game_id = struct.unpack('<Q', stream.read(8))[0]
            just_posted = struct.unpack('<?', stream.read(1))[0]
            announcements.append({"event_id": event_id, "event_time": event_time, "headline": headline, "game_id": game_id, "just_posted": just_posted})
        return announcements

    def _parse_events(self, stream):
        """
        Parse events, including event ID, time, headline, game ID, and justPosted.
        """
        num_events = struct.unpack('<I', stream.read(4))[0]
        events = []
        for _ in range(num_events):
            event_id = struct.unpack('<Q', stream.read(8))[0]
            event_time = struct.unpack('<I', stream.read(4))[0]
            headline = b""
            while True:
                char = stream.read(1)
                if char == b"\x00" or not char:
                    break
                headline += char
            headline = headline.decode("utf-8")
            game_id = struct.unpack('<Q', stream.read(8))[0]
            just_posted = struct.unpack('<?', stream.read(1))[0]
            events.append({"event_id": event_id, "event_time": event_time, "headline": headline, "game_id": game_id, "just_posted": just_posted})
        return events

    def _serialize_name_info(self, buffer):
        """
        Serialize Name Info including clan name and avatar SHA1 hash.
        """
        clan_name = self.name_info.get("clan_name", "").encode("utf-8") + b"\x00"
        # Avatar SHA is always exactly 20 raw bytes (SHA1 hash)
        avatar_sha = self.name_info.get("avatar_sha", b"\x00" * 20)
        if len(avatar_sha) < 20:
            avatar_sha = avatar_sha + b"\x00" * (20 - len(avatar_sha))
        elif len(avatar_sha) > 20:
            avatar_sha = avatar_sha[:20]
        buffer.write(clan_name)
        buffer.write(avatar_sha)

    def _serialize_user_counts(self, buffer):
        """
        Serialize user counts: members, online, in chat, in game.
        """
        buffer.write(struct.pack('<I', self.user_counts.get("members", 0)))
        buffer.write(struct.pack('<I', self.user_counts.get("online", 0)))
        buffer.write(struct.pack('<I', self.user_counts.get("in_chat", 0)))
        buffer.write(struct.pack('<I', self.user_counts.get("in_game", 0)))

    def _serialize_announcements(self, buffer):
        """
        Serialize announcements. Same format as events:
        uint32 count, then for each: uint64 gid, uint32 time, null-term headline, uint64 game_id, uint8 just_posted
        """
        buffer.write(struct.pack('<I', len(self.announcements)))
        for announcement in self.announcements:
            buffer.write(struct.pack('<Q', announcement.get("event_id", 0)))
            buffer.write(struct.pack('<I', announcement.get("event_time", 0)))
            buffer.write(announcement.get("headline", "").encode("utf-8") + b"\x00")
            buffer.write(struct.pack('<Q', announcement.get("game_id", 0)))
            buffer.write(struct.pack('<?', announcement.get("just_posted", False)))

    def _serialize_events(self, buffer):
        """
        Serialize events, including event ID, time, headline, game ID, and justPosted.
        """
        buffer.write(struct.pack('<I', len(self.events)))
        for event in self.events:
            buffer.write(struct.pack('<Q', event["event_id"]))
            buffer.write(struct.pack('<I', event["event_time"]))
            buffer.write(event["headline"].encode("utf-8") + b"\x00")
            buffer.write(struct.pack('<Q', event["game_id"]))
            buffer.write(struct.pack('<?', event["just_posted"]))