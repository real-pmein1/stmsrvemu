from steam3.Types.steam_types import EType, EUniverse, EInstanceFlag
import steam3.globals as cm_globals

class SteamID:
    anonUsersCount = cm_globals.anonUsersCount
    def __init__(self, steamid: int = 0) -> None:
        self.steamid: int = steamid
        self.universe: EUniverse = EUniverse.INVALID
        self.type: EType = EType.INVALID
        self.instance: EInstanceFlag = EInstanceFlag.ALL
        self.account_number: int = 0
        self._parse_steamid()

    def _parse_steamid(self) -> None:
        self.universe = EUniverse((self.steamid >> 56) & 0xFF)
        self.type = EType((self.steamid >> 52) & 0x0F)
        self.instance = EInstanceFlag((self.steamid >> 32) & 0xFFFFF)
        self.account_number = (self.steamid & 0xFFFFFFFF) // 2

    def set_universe(self, universe: EUniverse) -> None:
        self.universe = universe
        self._update_steamid()

    def set_type(self, type: EType) -> None:
        self.type = type
        self._update_steamid()

    def set_instance(self, instance: EInstanceFlag) -> None:
        self.instance = instance
        self._update_steamid()

    def set_accountID(self, account_number: int) -> None:
        self.account_number = account_number * 2
        self._update_steamid()

    def _update_steamid(self) -> None:
        self.steamid = (self.universe.value << 56) | (self.type.value << 52) | (self.instance.value << 32) | self.account_number

    def get_integer_format(self) -> int:
        return self.steamid

    def get_raw_bytes_format(self) -> bytes:
        return self.steamid.to_bytes(8, byteorder='little', signed=False)

    def get_accountID(self) -> int:
        return (self.account_number % 2) | (self.account_number // 2)

    def set_steam_local_id(self, steam_local_id: int, universe: EUniverse) -> None:
        self.account_number = steam_local_id * 2 + (steam_local_id >> 32)
        self.universe = universe
        self.type = EType.INDIVIDUAL
        self.instance = EInstanceFlag.ALL
        self._update_steamid()

    def set_from_identifier(self, identifier: int, universe: EUniverse, account_type: EType) -> None:
        self.account_number = identifier & 0xFFFFFFFF
        self.instance = EInstanceFlag((identifier >> 32) & 0xFFFFF)
        self.universe = universe
        self.type = account_type
        self._update_steamid()

    def get_static_steam_global_id(self) -> int:
        return (self.universe.value << 56) | (self.type.value << 52) | self.account_number

    def create_blank_anon_logon(self, universe: EUniverse) -> None:
        self.account_number = 0
        self.type = EType.ANONGAMESERVER
        self.universe = universe
        self.instance = EInstanceFlag.ALL
        self._update_steamid()

    def is_blank_anon_account(self) -> bool:
        return self.account_number == 0 and self.type == EType.ANONGAMESERVER and self.instance == EInstanceFlag.ALL

    def is_game_server_account(self) -> bool:
        return self.type in [EType.GAMESERVER, EType.ANONGAMESERVER]

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
    def is_account_type(steam_global_id: int, account_type: EType) -> bool:
        return (steam_global_id >> 52) & 0x0F == account_type.value

    @staticmethod
    def get_new_anon_global_id(steam_global_id: 'SteamID') -> int:
        SteamID.anonUsersCount += 1
        steam_global_id.set_accountID(SteamID.anonUsersCount)
        return steam_global_id.get_integer_format()

    @staticmethod
    def get_type_from_bytes(byte_array: bytes) -> EType:
        if len(byte_array) != 4:
            raise ValueError("Byte array must be exactly 4 bytes long")
        account_type_value = (int.from_bytes(byte_array, byteorder='little') >> 20) & 0x0F
        return EType(account_type_value)

    @staticmethod
    def combine_parts(first_part, second_part) -> bytes:
        if isinstance(first_part, bytes):
            if len(first_part) != 4:
                raise ValueError("First part byte array must be exactly 4 bytes long")
            first_part_int = int.from_bytes(first_part, byteorder='little')
        elif isinstance(first_part, int):
            first_part_int = first_part
        else:
            raise TypeError("First part must be either an integer or a byte array of 4 bytes")

        if isinstance(second_part, bytes):
            if len(second_part) != 4:
                raise ValueError("Second part byte array must be exactly 4 bytes long")
            second_part_int = int.from_bytes(second_part, byteorder='little')
        elif isinstance(second_part, int):
            second_part_int = second_part
        else:
            raise TypeError("Second part must be either an integer or a byte array of 4 bytes")

        combined_int = (second_part_int << 32) | first_part_int
        return combined_int.to_bytes(8, byteorder='little')

    def __repr__(self) -> str:
        return (f"SteamID(universe={self.universe}, type={self.type}, "
                f"instance={self.instance}, account_number={self.account_number})")


# Example usage:
#steamID = SteamID()
#steamID.set_universe(EUniverse.PUBLIC)
#steamID.set_type(EType.INDIVIDUAL)
#steamID.set_instance(EInstanceFlag.ALL)
#steamID.set_account_number(123456789)
#print(steamID)
#print("Integer format:", steamID.get_integer_format())
#print("Raw bytes format:", steamID.get_raw_bytes_format())