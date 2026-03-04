import os
import struct
import zlib
from io import BytesIO
from typing import Optional
from steam3.Types.keyvaluesystem import KVS_TYPE_INT, KVS_TYPE_INT64, KVS_TYPE_STRING, KVS_TYPE_UINT64, KeyValuesSystem, RegistryKey, RegistryValue, VolatileRegistry
from steam3.Types.userstats import AchievementId, AchievementsIterator, Iterator, UserStatType, Word

class UserStatsSchema(KeyValuesSystem):
    """
    A schema that references user-defined stats and achievements from the KeyValues structure.
    """
    def __init__(self, registry: Optional[VolatileRegistry] = None):
        super().__init__(registry)
        self.schema_key: Optional[RegistryKey] = None
        self.stats_key: Optional[RegistryKey] = None
        self.init()

    def init(self):
        elements = self.get_registry_key().get_elements()
        if not elements:
            raise Exception("Invalid schema: no root key found in bin")

        self.schema_key = next((e for e in elements if e.is_key()), None)
        if not self.schema_key:
            raise Exception("Invalid schema: root key is missing")

        self.stats_key = self.schema_key.get_key("stats")
        if not self.stats_key:
            raise Exception("Invalid schema: no 'stats' subkey found")

    from typing import Dict, Callable

    def computeCrc(self, stats_dict: Dict[int, int], is_set_stat_callback: Callable[[int], bool], get_stat_int_callback: Callable[[int], int]) -> int:
        """
        :param stats_dict: A dict of {stat_id: stored_value} like in UserStats self.stats
        :param is_set_stat_callback: function(stat_id) -> bool
                                    checks if that stat is "set"
        :param get_stat_int_callback: function(stat_id) -> int
                                    returns the integer value of that stat
        :return: computed 32-bit CRC
        """
        # We'll do an actual CRC32 using zlib.
        # 1) Start with the schema version
        version = self.getVersion()
        # We'll convert the version to bytes in little-endian
        running = 0  # seed for zlib.crc32
        data_version = struct.pack('<I', version)
        running = zlib.crc32(data_version, running)

        # 2) For each stat that is "set", update the CRC with the stat ID and the stat INT
        # The C++ code sorts or just iterates in unspecified order. Typically, CRC doesn't require sorting,
        # but if the C++ code sorts keys, we should do the same to be identical.
        sorted_ids = sorted(stats_dict.keys())
        for sid in sorted_ids:
            if is_set_stat_callback(sid):
                # update with sid
                data_sid = struct.pack('<I', sid)
                running = zlib.crc32(data_sid, running)
                # update with the stored value
                val = get_stat_int_callback(sid)
                data_val = struct.pack('<I', val)
                running = zlib.crc32(data_val, running)

        # result is a 32-bit int
        crc_result = running & 0xFFFFFFFF
        return crc_result

    def getGameId(self) -> int:
        try:
            return Word.parse_string(self.schema_key.name)
        except Exception:
            return 0

    def getVersion(self) -> int:
        val = self.schema_key.get_value("version")
        if not val:
            return 0
        try:
            return int(val.value)
        except ValueError:
            return 0

    def getGameName(self) -> Optional[str]:
        # First try "GameName"
        val = self.schema_key.get_value("GameName")
        if val and isinstance(val.value, str):
            return val.value

        # fallback to "gamename"
        val2 = self.schema_key.get_value("gamename")
        if val2 and isinstance(val2.value, str):
            return val2.value

        return None

    def get_defined_stat_ids(self) -> 'Iterator':
        stat_keys = [k for k in self.stats_key.get_elements() if k.is_key()]
        stat_ids = []
        for sk in stat_keys:
            try:
                stat_ids.append(int(sk.name))
            except ValueError:
                pass
        return Iterator(stat_ids)

    def getStatKey(self, identifier) -> Optional[RegistryKey]:
        """
        Single function to get a stat key by either integer ID or stat name.
        """
        if isinstance(identifier, int):
            key_name = str(identifier)
            return self.stats_key.get_key(key_name)
        elif isinstance(identifier, str):
            candidates = [k for k in self.stats_key.get_elements() if k.is_key()]
            for ck in candidates:
                name_val = ck.get_value("name")
                if name_val and name_val.value == identifier:
                    return ck
            return None
        else:
            raise Exception("Invalid identifier type for getStatKey")

    def getStatId(self, name: str) -> int:
        stat_key = self.getStatKey(name)
        if not stat_key:
            raise Exception(f"Invalid stat name: {name}")
        return int(stat_key.name)

    def getStatName(self, stat_id: int) -> Optional[str]:
        skey = self.getStatKey(stat_id)
        if not skey:
            return None
        val = skey.get_value("name")
        return val.value if (val and isinstance(val.value, str)) else None

    def getStatType(self, stat_id: int) -> UserStatType:
        sk = self.getStatKey(stat_id)
        if not sk:
            return UserStatType.invalid

        # Check type_int first
        tval_int = sk.get_value("type_int")
        if tval_int and tval_int.value_type in (KVS_TYPE_INT, KVS_TYPE_INT64, KVS_TYPE_UINT64):
            try:
                return UserStatType(tval_int.value)
            except ValueError:
                pass

        # fallback: maybe 'type' is a string e.g. "4"
        tval_str = sk.get_value("type")
        if tval_str and tval_str.value_type == KVS_TYPE_STRING:
            try:
                numeric_type = int(tval_str.value)
                return UserStatType(numeric_type)
            except ValueError:
                pass

        return UserStatType.invalid

    def get_defined_achievement_ids(self, stat_id: Optional[int] = None) -> 'Iterator':
        if stat_id is not None:
            st_key = self.getStatKey(stat_id)
            if not st_key:
                return Iterator([])
            bits_key = st_key.get_key("bits")
            if not bits_key:
                return Iterator([])
            return AchievementsIterator(bits_key.get_elements())
        else:
            results = []
            for st in self.stats_key.get_elements():
                if st.is_key():
                    bits_k = st.get_key("bits")
                    if bits_k:
                        results.extend(bits_k.get_elements())
            return AchievementsIterator(results)

    def getAchievementKey(self, identifier) -> Optional[RegistryKey]:
        if isinstance(identifier, AchievementId):
            sk = self.getStatKey(identifier.stat_id)
            if not sk:
                return None
            bits_k = sk.get_key("bits")
            if not bits_k:
                return None
            return bits_k.get_key(str(identifier.bit))
        elif isinstance(identifier, str):
            for st in self.stats_key.get_elements():
                if st.is_key():
                    bits_k = st.get_key("bits")
                    if bits_k:
                        for sub in bits_k.get_elements():
                            if sub.is_key():
                                nm_val = sub.get_value("name")
                                if nm_val and nm_val.value == identifier:
                                    return sub
            return None
        else:
            raise Exception("Invalid identifier type for getAchievementKey")

    def getAchievementId(self, name: str) -> 'AchievementId':
        achievement_key = self.getAchievementKey(name)
        if not achievement_key:
            raise Exception(f"Invalid achievement name: {name}")
        bit_str = achievement_key.name
        bit_val = int(bit_str)
        parent_bits_key = achievement_key.parent
        if not parent_bits_key:
            raise Exception("Achievement key missing 'bits' parent.")
        parent_stat_key = parent_bits_key.parent
        if not parent_stat_key:
            raise Exception("'bits' key missing parent stat key.")
        stat_id_val = int(parent_stat_key.name)
        return AchievementId(stat_id_val, bit_val)

    def getAchievementName(self, achievement_id: 'AchievementId') -> Optional[str]:
        akey = self.getAchievementKey(achievement_id)
        if not akey:
            raise Exception("Invalid achievement id")
        val = akey.get_value("name")
        return val.value if (val and isinstance(val.value, str)) else None

    def isAchievementDisplayHidden(self, achievement_id: 'AchievementId') -> bool:
        return self.getAchievementAttribute_as_DWORD(achievement_id, "display", "hidden", 0) != 0

    def getAchievementDisplayIcon(self, achievement_id: 'AchievementId') -> Optional[str]:
        return self.getAchievementAttribute(achievement_id, "display", "icon", None)

    def getAchievementDisplayIconGray(self, achievement_id: 'AchievementId') -> Optional[str]:
        """
        Equivalent of the C++ getAchievementDisplayIconGray(AchievementId id)
        which returns getAchievementAttribute(id,"display","icon_gray",0)
        """
        return self.getAchievementAttribute(achievement_id, "display", "icon_gray", None)

    # -------------
    # Low-level getters for stats/achievements
    # -------------

    def getStatAttributeValue(self, stat_id: int, section: Optional[str], name: str) -> Optional[RegistryValue]:
        sk = self.getStatKey(stat_id)
        if not sk:
            raise Exception("Invalid stat id")
        if section:
            sk = sk.get_key(section)
            if not sk:
                return None
        return sk.get_value(name)

    def getAchievementAttributeValue(self, achievement_id: 'AchievementId', section: Optional[str], name: str) -> Optional[RegistryValue]:
        akey = self.getAchievementKey(achievement_id)
        if not akey:
            raise Exception("Invalid achievement id")
        if section:
            akey = akey.get_key(section)
            if not akey:
                return None
        return akey.get_value(name)

    def getStatAttribute_as_DWORD(self, stat_id: int, section: Optional[str], name: str, default_value: int) -> int:
        rv = self.getStatAttributeValue(stat_id, section, name)
        if rv and rv.value_type in (KVS_TYPE_INT, KVS_TYPE_INT64, KVS_TYPE_UINT64):
            return rv.value
        return default_value

    def getAchievementAttribute_as_DWORD(self, achievement_id: 'AchievementId', section: Optional[str], name: str, default_value: int) -> int:
        rv = self.getAchievementAttributeValue(achievement_id, section, name)
        if rv and rv.value_type in (KVS_TYPE_INT, KVS_TYPE_INT64, KVS_TYPE_UINT64):
            return rv.value
        return default_value

    def getAchievementAttribute(self, achievement_id: 'AchievementId', section: Optional[str], name: str, default_value: Optional[str]) -> Optional[str]:
        rv = self.getAchievementAttributeValue(achievement_id, section, name)
        if rv and rv.value_type == KVS_TYPE_STRING:
            return rv.value
        return default_value

    # -------------------------
    # ## Newly Added Methods from C++
    #    (Only if they do NOT already exist in Python code)
    # -------------------------

    def isStatSetByTrustedGS(self, stat_id: int) -> bool:
        return self.getStatAttribute_as_DWORD(stat_id, None, "bSetByTrustedGS", 0) != 0

    def getStatMin(self, stat_id: int) -> int:
        return self.getStatAttribute_as_DWORD(stat_id, None, "min", 0)

    def getStatMax(self, stat_id: int) -> int:
        return self.getStatAttribute_as_DWORD(stat_id, None, "max", -1)

    def getStatMaxChange(self, stat_id: int) -> int:
        return self.getStatAttribute_as_DWORD(stat_id, None, "maxchange", -1)

    def getStatDefault(self, stat_id: int) -> int:
        return self.getStatAttribute_as_DWORD(stat_id, None, "default", 0)

    def getStatWindowSize(self, stat_id: int) -> int:
        return self.getStatAttribute_as_DWORD(stat_id, None, "windowsize", 0)

    def getStatDirtyBits(self, stat_id: int) -> int:
        """
        In C++, uses getStatAttributeDWORD(...) with default=0
        """
        rv = self.getStatAttributeValue(stat_id, None, "dirtybits")
        if rv and isinstance(rv.value, int):
            return rv.value
        return 0

    def getStatUpdates(self, stat_id: int) -> int:
        rv = self.getStatAttributeValue(stat_id, None, "updates")
        if rv and isinstance(rv.value, int):
            return rv.value
        return 0

    def getStatIncrementOnly(self, stat_id: int) -> bool:
        return self.getStatAttribute_as_DWORD(stat_id, None, "incrementonly", 0) != 0

    def getStatDataInt(self, stat_id: int) -> int:
        rv = self.getStatAttributeValue(stat_id, None, "data")
        if rv and isinstance(rv.value, int):
            return rv.value
        return 0

    def getStatDataFloat(self, stat_id: int) -> float:
        """
        In C++: getStatAttributeFLOAT(id, 0, "data", 0.0f)
        """
        rv = self.getStatAttributeValue(stat_id, None, "data")
        if rv:
            # If it's float:
            if isinstance(rv.value, float):
                return rv.value
            # If it's string, attempt to parse:
            if isinstance(rv.value, str):
                try:
                    return float(rv.value)
                except ValueError:
                    return 0.0
        return 0.0

    def getStatState(self, stat_id: int) -> int:
        rv = self.getStatAttributeValue(stat_id, None, "state")
        if rv and isinstance(rv.value, int):
            return rv.value
        return 0

    def getStatDisplayName(self, stat_id: int) -> Optional[str]:
        """
        In C++: getStatAttribute(id, "display", "name", 0)
        """
        val = self.getStatAttributeValue(stat_id, "display", "name")
        if val and isinstance(val.value, str):
            return val.value
        return None

    # Achievement-specific
    def getAchievementAwardItem(self, ach_id: 'AchievementId') -> int:
        return self.getAchievementAttribute_as_DWORD(ach_id, None, "award_item", 0)

    def getAchievementProgressOperation(self, ach_id: 'AchievementId') -> Optional[str]:
        return self.getAchievementAttribute(ach_id, "progress/value", "operation", None)

    def getAchievementProgressOperand(self, ach_id: 'AchievementId', operand: int = 1) -> Optional[str]:
        operand_name = f"operand{operand}"
        return self.getAchievementAttribute(ach_id, "progress/value", operand_name, None)

    def getAchievementProgressMin(self, ach_id: 'AchievementId') -> int:
        return self.getAchievementAttribute_as_DWORD(ach_id, "progress", "min_val", 0)

    def getAchievementProgressMax(self, ach_id: 'AchievementId') -> int:
        return self.getAchievementAttribute_as_DWORD(ach_id, "progress", "max_val", -1)

    def getAchievementDisplayIconHandle(self, ach_id: 'AchievementId') -> int:
        return self.getAchievementAttributeDWORD(ach_id, "display", "icon_handle", -1)

    def getAchievementDisplayIconHandleGray(self, ach_id: 'AchievementId') -> int:
        return self.getAchievementAttributeDWORD(ach_id, "display", "icon_handle_gray", -1)

    def getAchievementDisplayName_lang(
        self, achievement_id: 'AchievementId',
        language: str, default_language: Optional[str] = None
    ) -> Optional[str]:
        """
        Navigates subkeys:
          achievementKey -> "display" -> "name"
        Then looks for a Value named language, or fallback to default_language, or 'token'.
        """
        # 1) Get the top-level achievement key
        ach_key = self.getAchievementKey(achievement_id)
        if not ach_key:
            return None

        # 2) Enter the 'display' subkey
        display_key = ach_key.get_key("display")
        if not display_key:
            return None

        # 3) Enter the 'name' subkey
        name_key = display_key.get_key("name")
        if not name_key:
            return None

        # 4) Attempt the 'language' value
        lang_val = name_key.get_value(language)
        if lang_val and lang_val.value_type == KVS_TYPE_STRING:
            return lang_val.value

        # 5) If language not found, try default_language
        if default_language:
            default_val = name_key.get_value(default_language)
            if default_val and default_val.value_type == KVS_TYPE_STRING:
                return default_val.value

        # 6) Fallback: try 'token'
        token_val = name_key.get_value("token")
        if token_val and token_val.value_type == KVS_TYPE_STRING:
            return token_val.value

        return None

    def getAchievementDisplayDesc_lang(
        self, achievement_id: 'AchievementId',
        language: str, default_language: Optional[str] = None
    ) -> Optional[str]:
        """
        Navigates:
          achievementKey -> "display" -> "desc"
        Then looks for a Value named language, fallback to default_language, or 'token'.
        """
        ach_key = self.getAchievementKey(achievement_id)
        if not ach_key:
            return None

        display_key = ach_key.get_key("display")
        if not display_key:
            return None

        desc_key = display_key.get_key("desc")
        if not desc_key:
            return None

        lang_val = desc_key.get_value(language)
        if lang_val and lang_val.value_type == KVS_TYPE_STRING:
            return lang_val.value

        if default_language:
            default_val = desc_key.get_value(default_language)
            if default_val and default_val.value_type == KVS_TYPE_STRING:
                return default_val.value

        token_val = desc_key.get_value("token")
        if token_val and token_val.value_type == KVS_TYPE_STRING:
            return token_val.value

        return None

    def getAchievementAttributeDWORD(self, ach_id: 'AchievementId', section: Optional[str], name: str, default_val: int) -> int:
        rv = self.getAchievementAttributeValue(ach_id, section, name)
        if rv and isinstance(rv.value, int):
            return rv.value
        return default_val

    @classmethod
    def from_stream(cls, in_stream: BytesIO) -> "UserStatsSchema":
        """
        Equivalent to the C++: UserStatsSchema(InputStream * in)
        1) Create a KeyValuesSystem
        2) Deserialize from the stream
        3) Build a UserStatsSchema from that registry
        """
        kvs = KeyValuesSystem()
        kvs.deserialize(in_stream)
        return cls(registry=kvs)

    @classmethod
    def from_file(cls, filepath: str) -> "UserStatsSchema":
        """
        Equivalent to the C++: UserStatsSchema(File * file).
        Reads the file into a stream, then calls from_stream.
        """
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"Schema file not found: {filepath}")

        with open(filepath, 'rb') as f:
            data = f.read()
        in_stream = BytesIO(data)
        return cls.from_stream(in_stream)
