from __future__ import annotations
from steam3.Types.wrappers import AccountID
from steam3.Types.steam_types import EType, EUniverse, EInstanceFlag
import steam3.globals as cm_globals
import logging

log = logging.getLogger('STEAMID')

class SteamID:
    anonUsersCount = cm_globals.anonUsersCount
    def __init__(self, steamid: int = 0) -> None:
        self.steamid: int = steamid
        # defaults if we never parse
        self.universe: EUniverse      = EUniverse.INVALID
        self.type:     EType          = EType.INVALID
        self.instance: EInstanceFlag  = EInstanceFlag.ALL
        self.account_number: int      = 0

        self._parse_steamid()

    ##############################
    # These two methods are for returning the
    # full steamid as an int when the object is referenced
    ##############################
    def __int__(self) -> int:
        return self.steamid

    def __index__(self) -> int:
        return self.steamid
    ##############################
    ##############################

    def _parse_steamid(self) -> SteamID:
        # ?? special?case the ?all?FF? steamid ??
        if self.steamid == 0xFFFFFFFFFFFFFFFF:
            # leave universe/type/instance/account_number at their defaults
            return self

        # ?? otherwise do your normal 64?bit slicing ??
        universe_val = (self.steamid >> 56) & 0xFF
        try:
            self.universe = EUniverse(universe_val)
        except ValueError:
            log.warning("Unknown universe %d in SteamID %s", universe_val, hex(self.steamid))
            self.universe = EUniverse.INVALID

        type_val = (self.steamid >> 52) & 0x0F
        try:
            self.type = EType(type_val)
        except ValueError:
            log.warning("Unknown type %d in SteamID %s", type_val, hex(self.steamid))
            self.type = EType.INVALID

        instance_val = (self.steamid >> 32) & 0xFFFFF
        try:
            self.instance = EInstanceFlag(instance_val)
        except ValueError:
            # Unknown instance flag - store raw value, default to ALL for compatibility
            log.debug("Unknown instance flag %d in SteamID %s, using ALL", instance_val, hex(self.steamid))
            self.instance = EInstanceFlag.ALL

        self.account_number = (self.steamid & 0xFFFFFFFF) // 2
        return self

    def set_universe(self, universe: EUniverse) -> SteamID:
        self.universe = universe
        self._update_steamid()
        return self

    def set_type(self, type: EType) -> SteamID:
        self.type = type
        self._update_steamid()
        return self

    def set_instance(self, instance: EInstanceFlag) -> SteamID:
        self.instance = instance
        self._update_steamid()
        return self

    def set_accountID(self, account_number: int) -> SteamID:
        self.account_number = account_number
        self._update_steamid()
        return self

    def _update_steamid(self) -> None:
        self.steamid = (self.universe.value << 56) | (self.type.value << 52) | (self.instance.value << 32) | self.account_number * 2

    def get_integer_format(self) -> int:
        return self.steamid

    def get_raw_bytes_format(self) -> bytes:
        return self.steamid.to_bytes(8, byteorder='little', signed=False)

    def get_accountID(self) -> AccountID:
        return AccountID(self.account_number)

    def set_steam_local_id(self, accountID: int, universe: EUniverse) -> SteamID:
        self.account_number = accountID
        self.universe = universe
        self.type = EType.INDIVIDUAL
        self.instance = EInstanceFlag.ALL
        self._update_steamid()
        return self

    def set_from_identifier(self, identifier: int, universe: EUniverse, accountType: EType, instance: EInstanceFlag | int = None) -> "SteamID":
        """
        identifier: full 64-bit SteamID
        universe:    the EUniverse
        accountType: the EType
        instance:    optional override for the instance flag;
                     if None, we pull it from the identifier bits.
        """

        # 1) low 32 bits = account number
        self.account_number = identifier & 0xFFFFFFFF

        # 2) bits 32..51 = instance field
        extracted = (identifier >> 32) & 0xFFFFF
        if instance is None:
            # map the raw integer to your enum, handle unknown values
            try:
                self.instance = EInstanceFlag(extracted)
            except ValueError:
                log.debug("Unknown instance flag %d in identifier, using ALL", extracted)
                self.instance = EInstanceFlag.ALL
        else:
            # allow passing either the enum itself or its int value
            if isinstance(instance, EInstanceFlag):
                self.instance = instance
            else:
                try:
                    self.instance = EInstanceFlag(instance)
                except ValueError:
                    log.debug("Unknown instance flag %d passed, using ALL", instance)
                    self.instance = EInstanceFlag.ALL

        # 3) store universe & type
        self.universe = universe
        self.type     = accountType

        # 4) re-serialize your 64-bit steamid string or whatever
        self._update_steamid()
        return self

    def get_static_steam_global_id(self) -> int:
        return (self.universe.value << 56) | (self.type.value << 52) | self.account_number

    def create_blank_anon_logon(self, universe: EUniverse) -> SteamID:
        self.account_number = 0
        self.type = EType.ANONGAMESERVER
        self.universe = universe
        self.instance = EInstanceFlag.ALL
        self._update_steamid()
        return self

    def create_normal_user_steamID(self, accountID, universe: EUniverse) -> SteamID:
        self.account_number = accountID
        self.type = EType.INDIVIDUAL
        self.universe = universe
        self.instance = EInstanceFlag.ALL
        self._update_steamid()
        return self


    def is_blank_anon_account(self) -> bool:
        return self.account_number == 0 and self.type == EType.ANONGAMESERVER and self.instance == EInstanceFlag.ALL

    def is_game_server_account(self) -> bool:
        return self.type in [EType.GAMESERVER, EType.ANONGAMESERVER]

    def is_anon_account(self) -> bool:
        return self.type in [EType.ANONUSER, EType.ANONGAMESERVER]

    def is_lan_mode_game_server(self) -> bool:
        return self.account_number == 0 and self.instance == EInstanceFlag.ALL and self.universe == EUniverse.PUBLIC and self.type == EType.INVALID

    def is_outof_date_game_server(self) -> bool:
        return self.account_number == 0 and self.instance == EInstanceFlag.ALL and self.universe == EUniverse.INVALID and self.type == EType.INVALID

    def is_not_init_yet_game_server(self) -> bool:
        return self.account_number == 1 and self.instance == EInstanceFlag.ALL and self.universe == EUniverse.INVALID and self.type == EType.INVALID

    def get_high_bytes(self) -> bytes:
        return (self.steamid >> 32).to_bytes(4, byteorder='little')

    def get_low_bytes(self) -> bytes:
        return (self.steamid & 0xFFFFFFFF).to_bytes(4, byteorder='little')

    @staticmethod
    def is_account_type(globalID: int, account_type: EType) -> bool:
        return (globalID >> 52) & 0x0F == account_type.value

    @staticmethod
    def get_new_anon_global_id(globalID: SteamID) -> int:
        SteamID.anonUsersCount += 1
        globalID.set_accountID(SteamID.anonUsersCount)
        return globalID.get_integer_format()

    @staticmethod
    def get_type_from_bytes(steamIDBytes: bytes) -> EType:
        if len(steamIDBytes) != 4:
            raise ValueError("Byte array must be exactly 4 bytes long")
        account_type_value = (int.from_bytes(steamIDBytes, byteorder='little') >> 20) & 0x0F
        return EType(account_type_value)

    @staticmethod
    def combine_parts(first_part, second_part) -> SteamID:
        """
        Combine a 32?bit low part and a 32?bit high part into an 8?byte SteamID,
        then return a new SteamID object parsed from that 64?bit value.
        """
        # decode first_part ? 32?bit little?endian int
        if isinstance(first_part, bytes):
            if len(first_part) != 4:
                raise ValueError("First part byte array must be exactly 4 bytes long")
            low = int.from_bytes(first_part, byteorder='little')
        elif isinstance(first_part, int):
            low = first_part & 0xFFFFFFFF
        else:
            raise TypeError("First part must be either an integer or 4?byte bytes")

        # decode second_part ? 32?bit little?endian int
        if isinstance(second_part, bytes):
            if len(second_part) != 4:
                raise ValueError("Second part byte array must be exactly 4 bytes long")
            high = int.from_bytes(second_part, byteorder='little')
        elif isinstance(second_part, int):
            high = second_part & 0xFFFFFFFF
        else:
            raise TypeError("Second part must be either an integer or 4?byte bytes")

        # stitch into a 64?bit value
        combined_int = (high << 32) | low

        # return a new SteamID initialized from that 64?bit integer
        return SteamID(combined_int)

    @classmethod
    def from_raw(cls, steamIDRaw: int | bytes | bytearray | SteamID) -> SteamID:
        if isinstance(steamIDRaw, cls):
            return steamIDRaw

        # integer case: allow -1 as a special ?all?FF? sentinel
        if isinstance(steamIDRaw, int):
            if steamIDRaw == -1:
                steamIDInt = 0xFFFFFFFFFFFFFFFF
            else:
                steamIDInt = steamIDRaw
        # bytes case stays the same
        elif isinstance(steamIDRaw, (bytes, bytearray)):
            if len(steamIDRaw) != 8:
                raise ValueError("Byte array must be exactly 8 bytes long")
            steamIDInt = int.from_bytes(steamIDRaw, byteorder='little', signed=False)
        else:
            raise TypeError("Raw SteamID must be a SteamID, integer, or 8?byte bytes/bytearray")

        return cls(steamIDInt)

    @classmethod
    def from_integer(cls, steamIDInt: int) -> SteamID:
        if not isinstance(steamIDInt, int):
            raise TypeError("steamid_int must be an integer")
        # allow -1
        if steamIDInt == -1:
            return cls(0xFFFFFFFFFFFFFFFF)
        if steamIDInt < 0 or steamIDInt > 0xFFFFFFFFFFFFFFFF:
            raise ValueError("steamid_int out of range for 64?bit value")
        return cls(steamIDInt)

    @classmethod
    def createSteamIDFromAccountID(cls, accountID: int) -> "SteamID":
        """
        Return a new SteamID instance for a ?normal? user
        (Universe=PUBLIC, Type=INDIVIDUAL, Instance=ALL).
        """
        obj = cls()  # calls __init__, which sets steamid=0 and parses it
        obj.account_number = accountID
        obj.universe      = EUniverse.PUBLIC
        obj.type          = EType.INDIVIDUAL
        obj.instance      = EInstanceFlag.ALL
        obj._update_steamid()
        return obj

    @staticmethod
    def static_create_normal_account_steamid(accountID: int) -> int:
        """
        Build a ?normal? user SteamID 64-bit integer from just an account number,
        using Universe=PUBLIC, Type=INDIVIDUAL, Instance=ALL.
        """
        # Constants for the bit positions:
        universe_bits = EUniverse.PUBLIC.value << 56
        type_bits     = EType.INDIVIDUAL.value << 52
        instance_bits = EInstanceFlag.ALL.value << 32
        # account number is stored as accountID * 2 in the low 32 bits
        account_bits  = (accountID & 0xFFFFFFFF) * 2

        return universe_bits | type_bits | instance_bits | account_bits

    def __repr__(self) -> str:
        return (f"SteamID(universe={self.universe}, type={self.type}, "
                f"instance={self.instance}, account_number={self.account_number})")

    # ==============================
    # Clan/Chat Conversion Utilities
    # ==============================

    def is_clan(self) -> bool:
        """Check if this is a clan (Steam Group) SteamID."""
        return self.type == EType.CLAN

    def is_chat(self) -> bool:
        """Check if this is a chat SteamID (lobby or clan chat)."""
        return self.type == EType.CHAT

    def is_clan_chat(self) -> bool:
        """Check if this is a clan chat room SteamID (type=CHAT with CLAN instance flag)."""
        return self.type == EType.CHAT and (self.instance.value & EInstanceFlag.CLAN.value) != 0

    def is_lobby(self) -> bool:
        """Check if this is a lobby SteamID (type=CHAT with LOBBY instance flag)."""
        return self.type == EType.CHAT and (self.instance.value & EInstanceFlag.LOBBY.value) != 0

    def to_clan_chat_id(self) -> "SteamID":
        """
        Convert a clan SteamID to its associated chat room SteamID.

        Clan chat rooms have:
        - Type = CHAT
        - Instance = CLAN (0x80000)
        - Same account number and universe as the clan

        Raises ValueError if this is not a clan SteamID.
        """
        if not self.is_clan():
            raise ValueError(f"Cannot convert non-clan SteamID to chat ID: type={self.type}")

        chat_id = SteamID()
        chat_id.account_number = self.account_number
        chat_id.universe = self.universe
        chat_id.type = EType.CHAT
        chat_id.instance = EInstanceFlag.CLAN
        chat_id._update_steamid()
        return chat_id

    def to_clan_id(self) -> "SteamID":
        """
        Convert a clan chat SteamID back to the original clan SteamID.

        Raises ValueError if this is not a clan chat SteamID.
        """
        if not self.is_clan_chat():
            raise ValueError(f"Cannot convert non-clan-chat SteamID to clan ID: type={self.type}, instance={self.instance}")

        clan_id = SteamID()
        clan_id.account_number = self.account_number
        clan_id.universe = self.universe
        clan_id.type = EType.CLAN
        clan_id.instance = EInstanceFlag.ALL
        clan_id._update_steamid()
        return clan_id

    @classmethod
    def create_clan_id(cls, account_id: int, universe: EUniverse = EUniverse.PUBLIC) -> "SteamID":
        """Create a clan (Steam Group) SteamID from an account ID."""
        obj = cls()
        obj.account_number = account_id
        obj.universe = universe
        obj.type = EType.CLAN
        obj.instance = EInstanceFlag.ALL
        obj._update_steamid()
        return obj

    @classmethod
    def create_clan_chat_id(cls, account_id: int, universe: EUniverse = EUniverse.PUBLIC) -> "SteamID":
        """Create a clan chat room SteamID from a clan account ID."""
        obj = cls()
        obj.account_number = account_id
        obj.universe = universe
        obj.type = EType.CHAT
        obj.instance = EInstanceFlag.CLAN
        obj._update_steamid()
        return obj

    @staticmethod
    def clan_id_to_chat_id(clan_steamid: int) -> int:
        """
        Static utility to convert a 64-bit clan SteamID to its chat room SteamID.

        Replaces:
        - Type bits (52-55): CLAN (7) -> CHAT (8)
        - Instance bits (32-51): ALL (1) -> CLAN (0x80000)
        """
        # Clear type and instance bits, then set new values
        account_bits = clan_steamid & 0xFFFFFFFF
        universe_bits = clan_steamid & 0xFF00000000000000

        new_type_bits = EType.CHAT.value << 52
        new_instance_bits = EInstanceFlag.CLAN.value << 32

        return universe_bits | new_type_bits | new_instance_bits | account_bits

    @staticmethod
    def chat_id_to_clan_id(chat_steamid: int) -> int:
        """
        Static utility to convert a 64-bit clan chat SteamID back to the clan SteamID.

        Replaces:
        - Type bits (52-55): CHAT (8) -> CLAN (7)
        - Instance bits (32-51): CLAN (0x80000) -> ALL (1)
        """
        account_bits = chat_steamid & 0xFFFFFFFF
        universe_bits = chat_steamid & 0xFF00000000000000

        new_type_bits = EType.CLAN.value << 52
        new_instance_bits = EInstanceFlag.ALL.value << 32

        return universe_bits | new_type_bits | new_instance_bits | account_bits


# Example usage:
#steamID = SteamID()
#steamID.set_universe(EUniverse.PUBLIC)
#steamID.set_type(EType.INDIVIDUAL)
#steamID.set_instance(EInstanceFlag.ALL)
#steamID.set_account_number(123456789)
#print(steamID)
#print("Integer format:", steamID.get_integer_format())
#print("Raw bytes format:", steamID.get_raw_bytes_format())