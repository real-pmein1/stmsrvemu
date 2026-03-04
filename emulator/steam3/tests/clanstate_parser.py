import struct
from io import BytesIO
from enum import IntFlag
from steamid_parser import SteamID
# Define the flags
class ClanStateFlags(IntFlag):
    name = 0x01
    userCounts = 0x02
    announcements = 0x04
    events = 0x08

class ClanAccountFlags(IntFlag):
    public = 0x01
    large = 0x02
    locked = 0x04
    disabled = 0x08

class MsgClientClanState:
    def __init__(self):
        self.steam_id_clan = None
        self.clan_state_flags = 0
        self.m_bLarge = False
        self.m_bPublic = False
        self.m_bLocked = False
        self.m_bDisabled = False
        self.name_info = {}
        self.user_counts = {}
        self.announcements = []
        self.events = []

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

        # Read clan account flags (4 bytes)
        self.clan_state_flags = struct.unpack('<I', stream.read(4))[0]

        # Read the single byte for public and large clan flags
        account_flags = struct.unpack('<B', stream.read(1))[0]
        self.m_bPublic = bool(account_flags & 1)  # Bit 0: Public
        self.m_bLarge = bool(account_flags & 2)  # Bit 1: Large
        self.m_bLocked = bool(account_flags & 4)  # Bit 2: Locked
        self.m_bDisabled = bool(account_flags & 8)  # Bit 3: Disabled

        # Parse Name Info if NAME_INFO flag is set
        if self.clan_state_flags & ClanStateFlags.name:
            self.name_info = self._parse_name_info(stream)

        # Parse User Counts if USER_COUNTS flag is set
        if self.clan_state_flags & ClanStateFlags.userCounts:
            self.user_counts = self._parse_user_counts(stream)

        # Parse Announcements if ANNOUNCEMENTS flag is set
        if self.clan_state_flags & ClanStateFlags.announcements:
            self.announcements = self._parse_announcements(stream)

        # Parse Events if EVENTS flag is set
        if self.clan_state_flags & ClanStateFlags.events:
            self.events = self._parse_events(stream)

        # Check for leftover bytes
        remaining_bytes = stream.read()
        if remaining_bytes:
            print(f"Warning: Unparsed bytes left: {remaining_bytes.hex()}")

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
        return struct.pack('<B', byte_value)

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
        Parse Name Info including clan name and avatar.
        """
        # Parse clan name as a null-terminated string
        clan_name = b""
        while True:
            char = stream.read(1)
            if char == b"\x00" or not char:
                break
            clan_name += char
        clan_name = clan_name.decode("utf-8")

        # Parse avatar ID (up to 20 bytes, stopping at first null)
        avatar_raw = stream.read(20)
        avatar_end = avatar_raw.find(b"\x00")
        avatar_id = avatar_raw[:avatar_end].decode("latin-1", 'ignore') if avatar_end != -1 else avatar_raw.decode("latin-1", 'ignore')

        return {"clan_name":clan_name, "avatar_id":avatar_id}

    def _parse_user_counts(self, stream):
        """
        Parse user counts: members, online, in chat, in game.
        """
        members = struct.unpack('<I', stream.read(4))[0]
        online = struct.unpack('<I', stream.read(4))[0]
        in_chat = struct.unpack('<I', stream.read(4))[0]
        in_game = struct.unpack('<I', stream.read(4))[0]
        return {"members":members, "online":online, "in_chat":in_chat, "in_game":in_game}

    def _parse_announcements(self, stream):
        """
        Parse announcements. Assume each announcement is a null-terminated string.
        """
        num_announcements = struct.unpack('<I', stream.read(4))[0]
        announcements = []
        for _ in range(num_announcements):
            announcement = b""
            while True:
                char = stream.read(1)
                if char == b"\x00" or not char:
                    break
                announcement += char
            announcements.append(announcement.decode("utf-8"))
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
        Serialize Name Info including clan name and avatar.
        """
        clan_name = self.name_info.get("clan_name", "").encode("utf-8") + b"\x00"
        avatar_id = self.name_info.get("avatar_id", "").encode("latin-1", 'ignore').ljust(20, b"\x00")
        buffer.write(clan_name)
        buffer.write(avatar_id)

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
        Serialize announcements. Assume each announcement is a null-terminated string.
        """
        buffer.write(struct.pack('<I', len(self.announcements)))
        for announcement in self.announcements:
            buffer.write(announcement.encode("utf-8") + b"\x00")

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

# Example packet to simulate pNetPacket binary data
# packet = struct.pack('<QI', 12345678901234567890, 0x0F) + struct.pack('<B', 0x03)
packet = b'6\x03\x00\x00$\x02\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xef\xf5f\xb7\x00\x01\x00\x10\x01j;@\x00!\x08\x00\x00\x00\x00p\x01\x0b\x00\x00\x00\x03FacepunchStudios\x00\x80\xb4t\xcd\xf2\x92-q\x8cK\xc1\xc5\x94\x82\xc0\x92\xf8\xaf\x92\x1e\xb25\x00\x00\xd0\t\x00\x00\x00\x00\x00\x00\xf1\x01\x00\x00\x00\x00\x00\x00'

packet = packet[36:]
# Deserialize the example buffer
clan_state = MsgClientClanState()
clan_state.deserialize(packet)
print(clan_state)