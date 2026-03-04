import os
import struct
import zlib
from io import BytesIO
from typing import Optional, Dict, List

from steam3.Types.keyvaluesystem import KeyValuesSystem,  RegistryKey, RegistryValue
from steam3.Types.userstats import AchievedAt, AchievementId,  Flags,  Result_OK, Result_invalidParam, Serializable, StatDict,  UserStatType,  currentTime
from steam3.Types.userstats.globalstats import GlobalStats
from steam3.Types.userstats.userstatsschema import UserStatsSchema


class UserStats(Serializable):
    """
    A Python class that mirrors the C++ UserStats code, leveraging your existing
    UserStatsSchema and Python data structures.
    """

    def __init__(self, schema: Optional['UserStatsSchema'] = None):
        super().__init__()
        self.ownSchema: bool = False   # indicates if we own the schema
        self.schema: Optional['UserStatsSchema'] = schema

        self.pendingChanges: int = 0
        self.crc: int = 0

        # We'll store stats in a Python dict: {stat_id: intValue}
        # C++ uses HashMap<StatId, DWORD>
        self.stats: StatDict = StatDict()

        # We'll store achievement times in a dict: {stat_id: AchievedAt}
        self.achievedAt: Dict[int, AchievedAt] = {}


    @classmethod
    def from_stream(cls, in_stream: BytesIO) -> "UserStats":
        """
        Reads/parses a usergamestats_<accountid>_<appid>.bin KeyValues-based
        buffer from the provided in_stream and populates a new UserStats object.

        The examples you gave show a structure like:
          <Key name="cache">
            <Value name="crc" type="int32">someValue</Value>
            <Value name="PendingChanges" type="int32">someValue</Value>
            <Key name="14">
              <Value name="DATA" or "data" type="int32">value</Value>
              <Key name="AchievementTimes">
                <Value name="2" type="int32">timestamp</Value>
                ...
              </Key>
            </Key>
            ...
        """
        # 1) Parse the KeyValues structure
        kvs = KeyValuesSystem()
        kvs.deserialize(in_stream)

        # 2) The root probably has <Key name="cache"> as the main node
        root_key = kvs.get_registry_key()
        if not root_key:
            raise Exception("Invalid user stats file: missing root Key")

        # Typically, the single top subkey might be named "cache"
        cache_key = None
        for elem in root_key.get_elements():
            if isinstance(elem, RegistryKey) and elem.name.lower() == "cache":
                cache_key = elem
                break
        if not cache_key:
            # Maybe the root key *is* the cache?
            if root_key.name.lower() == "cache":
                cache_key = root_key
            else:
                raise Exception("Invalid user stats file: missing 'cache' key")

        # 3) Build a new UserStats instance
        user_stats = cls()

        # 4) Extract the 'crc' and 'PendingChanges' if present
        crc_val = cache_key.get_value("crc")
        if crc_val and isinstance(crc_val.value, int):
            user_stats.crc = crc_val.value

        pend_val = cache_key.get_value("PendingChanges")
        if pend_val and isinstance(pend_val.value, int):
            user_stats.pendingChanges = pend_val.value

        # 5) For each subkey under 'cache' (other than 'crc' or 'PendingChanges'),
        #    parse the ID, the 'DATA' or 'data' int, plus any "AchievementTimes".
        for sub_elem in cache_key.get_elements():
            if isinstance(sub_elem, RegistryKey):
                # sub_elem.name is the stat ID as string
                try:
                    sid = int(sub_elem.name)
                except ValueError:
                    continue  # skip if not numeric

                # read the 'data' or 'DATA' value
                data_val = sub_elem.get_value("DATA")
                if not data_val:
                    data_val = sub_elem.get_value("data")
                stored_value = 0
                if data_val and isinstance(data_val.value, int):
                    stored_value = data_val.value

                # store that in user_stats.stats
                user_stats.stats[sid] = stored_value

                # see if there's an AchievementTimes subkey
                ach_times_key = sub_elem.get_key("AchievementTimes")
                if ach_times_key:
                    # parse each <Value name="bit" type="int32">timestamp</Value>
                    at = AchievedAt()
                    for kv in ach_times_key.get_elements():
                        if isinstance(kv, RegistryValue) and kv.value and isinstance(kv.value, int):
                            # kv.name = e.g. "2"
                            try:
                                bit_index = int(kv.name)
                            except ValueError:
                                bit_index = -1
                            if bit_index >= 0 and bit_index < 32:
                                at.bit[bit_index] = kv.value
                    # store in user_stats.achievedAt[sid] = at
                    user_stats.achievedAt[sid] = at

        return user_stats

    @classmethod
    def from_file(cls, filepath: str) -> "UserStats":
        """
        Reads the usergamestats_<accountid>_<appid>.bin from disk,
        calls from_stream to parse it, returns a UserStats instance.
        """
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        with open(filepath, "rb") as f:
            data = f.read()
        in_stream = BytesIO(data)
        return cls.from_stream(in_stream)

    def setSchema(self, schema: 'UserStatsSchema'):
        if self.ownSchema and self.schema:
            # If we "own" the old schema, we'd delete it in C++,
            # in Python we just drop the reference.
            self.schema = None
        self.ownSchema = False
        self.schema = schema

    def getSchema(self) -> Optional['UserStatsSchema']:
        return self.schema

    def getSchemaSafe(self) -> 'UserStatsSchema':
        if not self.schema:
            raise Exception("No attached schema")
        return self.schema

    def reset(self):
        """
        Clears all stats and achievement timestamps.
        """
        self.stats.clear()
        self.achievedAt.clear()

    def reset_stat(self, stat_id: int):
        """
        Resets a single stat ID and removes associated achievement times.
        """
        if stat_id in self.stats:
            del self.stats[stat_id]
        if stat_id in self.achievedAt:
            del self.achievedAt[stat_id]

    # We define a simple enum or int-based result:
    def updateStats(self, statsUpdate: Dict[int, int], explicitReset: bool,
                    failedValidationStats: Dict[int, int],
                    checkCurrentCrc: int) -> int:
        """
        Mirrors C++: ResultType UserStats::updateStats(...)
        """
        result = Result_OK

        if checkCurrentCrc != self.getCrc():
            # CRC mismatch
            # => fill failedValidationStats with current stats
            stat_ids = self.getSchemaSafe().get_defined_stat_ids()
            while stat_ids.hasNext():
                sid = stat_ids.next()
                failedValidationStats[sid] = self.getStatInt(sid)
            result = Result_invalidParam
        else:
            # Attempt to update each stat
            for sid, new_value in statsUpdate.items():
                if not self.updateStat(sid, new_value, explicitReset):
                    failedValidationStats[sid] = self.getStatInt(sid)
                    result = Result_invalidParam
        return result

    def updateStat(self, stat_id: int, value: int, explicitReset: bool) -> bool:
        """
        Based on the stat type, we call setStatInt, setStatFloat, setStatAvgRate,
        or updateAchievements.
        """
        stype = self.getSchemaSafe().getStatType(stat_id)
        if stype == UserStatType.invalid:
            return False
        elif stype == UserStatType.int_type:
            return self.setStatInt(stat_id, value, True, explicitReset)
        elif stype == UserStatType.float_type:
            # reinterpret the int bits as float
            float_val = struct.unpack('f', struct.pack('I', value))[0]
            return self.setStatFloat(stat_id, float_val, True, explicitReset)
        elif stype == UserStatType.avgRate:
            float_val = struct.unpack('f', struct.pack('I', value))[0]
            return self.setStatAvgRate(stat_id, float_val, True, explicitReset)
        elif stype == UserStatType.achievements or \
             stype == UserStatType.groupAchievements:
            self.updateAchievements(stat_id, value)
            return True
        else:
            return False

    def updateAchievements(self, stat_id: int, value: int):
        """
        In C++:
         - lastValue = getStatInt(statId)
         - earned = (lastValue ^ value) & value
         - we set achieved time for newly set bits
         - we clean up bits using a "cleanMask"
        """
        lastValue = self.getStatInt(stat_id)
        earned = (lastValue ^ value) & value
        cleanMask = 0

        # get all achievements for this stat
        achievements_iter = self.getSchemaSafe().get_defined_achievement_ids(stat_id)
        while achievements_iter.hasNext():
            ach_id = achievements_iter.next()
            # if newly earned bit => set time
            if Flags.is_flag_set(earned, (1 << ach_id.bit)):
                self.setAchievedAt(ach_id, currentTime())

            # building up the cleanMask
            cleanMask = Flags.set(cleanMask, (1 << ach_id.bit))

        # set the stat to (value & cleanMask)
        self.setStatInt(stat_id, (value & cleanMask), False, False)

    def getStatIds(self) -> List[int]:
        """
        Return the list of stat IDs we have in self.stats
        """
        return list(self.stats.keys())

    def isSetStat(self, stat_id: int) -> bool:
        return (stat_id in self.stats)

    def isSetStatByName(self, name: str) -> bool:
        sid = self.getSchemaSafe().getStatId(name)
        return self.isSetStat(sid)

    def setStatInt(self, stat_id: int, value: int, validate: bool, explicitReset: bool) -> bool:
        """
        If validate is True, check isValidStatValue before storing.
        """
        if validate and (not self.isValidStatValue_int(stat_id, value, explicitReset)):
            return False
        self.stats.put(stat_id, value)
        return True

    def setStatIntByName(self, name: str, value: int, validate: bool, explicitReset: bool) -> bool:
        stat_id = self.getSchemaSafe().getStatId(name)
        return self.setStatInt(stat_id, value, validate, explicitReset)

    def setStatFloat(self, stat_id: int, value: float, validate: bool, explicitReset: bool) -> bool:
        if validate and (not self.isValidStatValue_float(stat_id, value, explicitReset)):
            return False
        # store as int bits
        bits = struct.unpack('I', struct.pack('f', value))[0]
        self.stats.put(stat_id, bits)
        return True

    def setStatFloatByName(self, name: str, value: float, validate: bool, explicitReset: bool) -> bool:
        stat_id = self.getSchemaSafe().getStatId(name)
        return self.setStatFloat(stat_id, value, validate, explicitReset)

    def setStatAvgRate(self, stat_id: int, value: float, validate: bool, explicitReset: bool) -> bool:
        # In the C++ code, setStatAvgRate = setStatFloat
        return self.setStatFloat(stat_id, value, validate, explicitReset)

    def setStatAvgRateByName(self, name: str, value: float, validate: bool, explicitReset: bool) -> bool:
        stat_id = self.getSchemaSafe().getStatId(name)
        return self.setStatAvgRate(stat_id, value, validate, explicitReset)

    def getStatInt(self, stat_id: int) -> int:
        """
        Returns the stored int; if none, fallback to the schema default
        """
        if stat_id not in self.stats:
            if not self.schema:
                return 0
            return self.schema.getStatDefault(stat_id)
        return self.stats[stat_id]

    def getStatIntByName(self, name: str) -> int:
        sid = self.getSchemaSafe().getStatId(name)
        return self.getStatInt(sid)

    def getStatFloat(self, stat_id: int) -> float:
        """
        Retrieves the stored bits as float. If none, fallback to default.
        """
        if stat_id not in self.stats:
            if not self.schema:
                return 0.0
            return float(self.schema.getStatDefault(stat_id))
        bits = self.stats[stat_id]
        return struct.unpack('f', struct.pack('I', bits))[0]

    def getStatFloatByName(self, name: str) -> float:
        sid = self.getSchemaSafe().getStatId(name)
        return self.getStatFloat(sid)

    def getStatAvgRate(self, stat_id: int) -> float:
        # per C++ code, same as getStatFloat
        return self.getStatFloat(stat_id)

    def getStatAvgRateByName(self, name: str) -> float:
        sid = self.getSchemaSafe().getStatId(name)
        return self.getStatAvgRate(sid)

    # -------------------------------------------------------------------
    # Achievements
    # -------------------------------------------------------------------
    def isSetAchievement(self, ach_id: 'AchievementId') -> bool:
        return self.isSetStat(ach_id.stat_id)

    def isSetAchievementByName(self, name: str) -> bool:
        ach_id = self.getSchemaSafe().getAchievementId(name)
        return self.isSetAchievement(ach_id)

    def isAchieved(self, ach_id: 'AchievementId') -> bool:
        stat_value = self.getStatInt(ach_id.stat_id)
        return Flags.is_flag_set(stat_value, (1 << ach_id.bit))

    def isAchievedByName(self, name: str) -> bool:
        ach_id = self.getSchemaSafe().getAchievementId(name)
        return self.isAchieved(ach_id)

    def setAchieved(self, ach_id: 'AchievementId', achieved: bool = True):
        stat_value = self.getStatInt(ach_id.stat_id)
        if achieved:
            stat_value = Flags.set(stat_value, (1 << ach_id.bit))
            self.setAchievedAt(ach_id, currentTime())
            self.setStatInt(ach_id.stat_id, stat_value, False, False)
        else:
            stat_value = Flags.reset(stat_value, (1 << ach_id.bit))
            if stat_value != 0:
                self.setStatInt(ach_id.stat_id, stat_value, False, False)
                self.setAchievedAt(ach_id, 0)
            else:
                # resets entire stat if no bits remain
                self.reset_stat(ach_id.stat_id)

    def setAchievedByName(self, name: str, achieved: bool = True):
        ach_id = self.getSchemaSafe().getAchievementId(name)
        self.setAchieved(ach_id, achieved)

    def wasAchievedAt(self, ach_id: 'AchievementId') -> int:
        """
        Return the timestamp of when the achievement bit was set, or 0 if not found.
        """
        if ach_id.stat_id not in self.achievedAt:
            return 0
        times_struct = self.achievedAt[ach_id.stat_id]
        return times_struct.bit[ach_id.bit]

    def wasAchievedAtByName(self, name: str) -> int:
        ach_id = self.getSchemaSafe().getAchievementId(name)
        return self.wasAchievedAt(ach_id)

    def setAchievedAt(self, ach_id: 'AchievementId', timestamp: int):
        """
        Ensure we have an AchievedAt structure for the stat id,
        then set the 'bit[ach_id.bit]' to `timestamp`.
        """
        if ach_id.stat_id not in self.achievedAt:
            new_times = AchievedAt()
            self.achievedAt[ach_id.stat_id] = new_times
        times = self.achievedAt[ach_id.stat_id]
        times.bit[ach_id.bit] = timestamp

    def setAchievedAtByName(self, name: str, timestamp: int):
        ach_id = self.getSchemaSafe().getAchievementId(name)
        self.setAchievedAt(ach_id, timestamp)

    # -------------------------------------------------------------------
    # CRC / Validation
    # -------------------------------------------------------------------
    def getCrc(self) -> int:
        return self.crc

    def computeCrc(self) -> int:
        """
        C++ uses the schema version + each stat ID + each stat value
        to compute a 32-bit CRC. We'll do a simplified approach here.
        """
        if not self.schema:
            return self.crc

        self.crc = self.schema.computeCrc(
            stats_dict=self.stats,
            is_set_stat_callback=lambda sid: self.isSetStat(sid),
            get_stat_int_callback=lambda sid: self.getStatInt(sid)
        )
        return self.crc

    def isValidStatValue_int(self, stat_id: int, new_value: int, explicitReset: bool) -> bool:
        """
        Mirrors: isValidStatValue(StatId statId, DWORD value, bool explicitReset)
        """
        stype = self.getSchemaSafe().getStatType(stat_id)
        if stype == UserStatType.int_type:
            return self.isValidStatUpdate(stat_id, self.getStatInt(stat_id), new_value, explicitReset)
        elif stype == UserStatType.achievements or \
             stype == UserStatType.groupAchievements:
            return True
        else:
            return False

    def isValidStatValue_float(self, stat_id: int, new_float: float, explicitReset: bool) -> bool:
        """
        Mirrors: isValidStatValue(StatId statId, FLOAT value, bool explicitReset)
                 => isValidStatUpdate(statId, oldFloat, newFloat, ...)
        But C++ code treats them as DWORD for comparison.
        """
        stype = self.getSchemaSafe().getStatType(stat_id)
        if stype == UserStatType.float_type or \
           stype == UserStatType.avgRate:
            old_bits = struct.unpack('I', struct.pack('f', self.getStatFloat(stat_id)))[0]
            new_bits = struct.unpack('I', struct.pack('f', new_float))[0]
            return self.isValidStatUpdate(stat_id, old_bits, new_bits, explicitReset)
        else:
            return False

    def isValidStatUpdate(self, stat_id: int, old_value: int, new_value: int, explicitReset: bool) -> bool:
        """
        In C++: checks incrementOnly, min, max, maxchange, etc.
        """
        schema = self.getSchemaSafe()
        if explicitReset and new_value == schema.getStatDefault(stat_id):
            return True

        if schema.getStatIncrementOnly(stat_id) and (old_value > new_value):
            return False
        if new_value < schema.getStatMin(stat_id):
            return False
        if new_value > schema.getStatMax(stat_id):
            return False
        diff = abs(new_value - old_value)
        if diff > schema.getStatMaxChange(stat_id):
            return False
        return True

    # -------------------------------------------------------------------
    # (De)Serialization
    # -------------------------------------------------------------------
    def serialize(self, out_stream, attachSchema: bool = False):
        """
        In C++, it sorts keys, writes some metadata, writes schema if needed,
        writes stats, writes achievement times.
        We'll do a simpler approach or you can replicate the exact steps.
        """
        # We'll do a naive approach for demonstration:
        # 1) Write a marker for attachSchema
        out_stream.write(struct.pack('<B', 1 if attachSchema else 0))
        # 2) Write number of stats
        out_stream.write(struct.pack('<I', len(self.stats)))
        # 3) Write current CRC
        out_stream.write(struct.pack('<I', self.computeCrc()))

        # 4) If attachSchema => we would call something like:
        # if attachSchema: KeyValuesSystem.serialize(out_stream, self.schema.getRegistryKey())
        # but let's omit actual schema serialization for demonstration

        # 5) Write the stats
        for sid in sorted(self.stats.keys()):
            val = self.stats[sid]
            out_stream.write(struct.pack('<H', sid))     # 2 bytes
            out_stream.write(struct.pack('<I', val))     # 4 bytes

        # 6) Write the achievements
        # The code in C++ checks if we have any achievements
        if len(self.achievedAt) > 0:
            out_stream.write(struct.pack('<I', len(self.achievedAt)))  # how many stats have times
            for stat_id in sorted(self.achievedAt.keys()):
                times = self.achievedAt[stat_id]
                out_stream.write(struct.pack('<H', stat_id))
                for i in range(32):
                    out_stream.write(struct.pack('<i', times.bit[i]))
        else:
            out_stream.write(struct.pack('<I', 0))

    def deserialize(self, in_stream):
        """
        Similar to the C++ code. We'll read the data we wrote in serialize().
        """
        # 1) read attachSchema
        attachSchema_flag = struct.unpack('<B', in_stream.read(1))[0]
        # 2) read statsCount
        statsCount = struct.unpack('<I', in_stream.read(4))[0]
        self.crc = struct.unpack('<I', in_stream.read(4))[0]

        if attachSchema_flag != 0:
            # in C++, it constructs new UserStatsSchema(in)
            # for Python, you could do:
            self.schema = UserStatsSchema.from_stream(in_stream)
            self.ownSchema = True

        # read stats
        self.stats.clear()
        for _ in range(statsCount):
            sid_bytes = in_stream.read(2)
            if len(sid_bytes) < 2:
                break
            sid = struct.unpack('<H', sid_bytes)[0]
            val = struct.unpack('<I', in_stream.read(4))[0]
            self.stats.put(sid, val)

        # read achievedAt
        times_count = struct.unpack('<I', in_stream.read(4))[0]
        self.achievedAt.clear()
        for _ in range(times_count):
            st_id = struct.unpack('<H', in_stream.read(2))[0]
            newTimes = AchievedAt()
            for bit_index in range(32):
                t_val = struct.unpack('<i', in_stream.read(4))[0]
                newTimes.bit[bit_index] = t_val
            self.achievedAt[st_id] = newTimes

        return True


class UserStats_Obsolete:
    """
    This class parses an older KeyValues-based userstats bin that,
    when converted to XML, looks like:

    <Key name="420">
        <Value name="GameName" ...>Half-Life 2: Episode Two</Value>
        <Value name="Version" ...>10</Value>
        <Key name="stats">
            <Key name="0">
                <Value name="Type" type="string">4</Value>
                <Key name="bits">
                    <Key name="0">
                        <Value name="name" ...>EP2_KILL_POISONANTLION</Value>
                        <Key name="display">
                            <Value name="name" ...>#EP2_KILL_POISONANTLION_NAME</Value>
                            <Value name="desc" ...>#EP2_KILL_POISONANTLION_DESC</Value>
                            <Value name="icon" ...>ep2_kill_poisonantlion.jpg</Value>
                            ...
                        </Key>
                        <Value name="bit" type="int32">0</Value>
                    </Key>
                    ...
                </Key>
                <Value name="ID" type="string">0</Value>
                <Value name="data" type="int32">2621465</Value>
            </Key>
        </Key>
        <Value name="crc" type="int32">1359505827</Value>
    </Key>
    """

    def __init__(self):
        # The top-level key name => AppID
        self.appid: str = ""
        # "GameName", "Version", "crc" from top-level values
        self.gameName: Optional[str] = None
        self.version: Optional[str] = None
        self.crc: int = 0

        # We'll store each "stat" subkey in a dictionary: stat_id => {
        #   "Type": str/int,
        #   "ID": str/int,
        #   "data": int,
        #   "bits": list of achievements, each containing:
        #     { "bit_id": "0", "name": "EP2_KILL...", "bit": 0,
        #       "display": { "name": "#EP2_...", "desc": "...", "hidden": "0", "icon": "...", ... } }
        # }
        self.stats_definitions: Dict[str, Dict[str, any]] = {}

    @classmethod
    def from_stream(cls, in_stream: BytesIO) -> "UserStats_Obsolete":
        """
        Parse the KeyValues-based file from the stream, expecting the structure shown above.
        We'll assume there's a top-level Key named "420" or whatever the app id is.
        """
        kvs = KeyValuesSystem()
        kvs.deserialize(in_stream)
        root_key = kvs.get_registry_key()
        if not root_key:
            raise Exception("No top-level key found in userstats file")

        # The top-level key is presumably the <Key name="420"> or "root"
        # If you find "root", you'll see if there's a single child, or you do what you need.
        # We'll assume root_key is actually "420".
        # If it's "root", let's see if it has a single child:
        actual_top_key = root_key
        if root_key.name.lower() == "root":
            # gather child subkeys
            children = [x for x in root_key.get_elements() if isinstance(x, RegistryKey)]
            if len(children) == 1:
                actual_top_key = children[0]
            elif len(children) == 0:
                raise Exception("Root has no subkeys. Possibly empty file?")
            else:
                # pick the first or handle differently
                actual_top_key = children[0]

        self_obj = cls()
        self_obj.appid = actual_top_key.name  # e.g. "420"

        # parse top-level values: "GameName", "Version", "crc"
        val_gamename = actual_top_key.get_value("GameName")
        if val_gamename and isinstance(val_gamename.value, str):
            self_obj.gameName = val_gamename.value

        val_version = actual_top_key.get_value("Version")
        if val_version and isinstance(val_version.value, str):
            self_obj.version = val_version.value

        val_crc = actual_top_key.get_value("crc")
        if val_crc and isinstance(val_crc.value, int):
            self_obj.crc = val_crc.value

        # parse the <Key name="stats">
        stats_key = actual_top_key.get_key("stats")
        if stats_key:
            # For each <Key name="0"> or "1" or "2" ...
            for stat_subkey in stats_key.get_elements():
                if isinstance(stat_subkey, RegistryKey):
                    sid_str = stat_subkey.name
                    stat_info: Dict[str, any] = {}

                    # Now parse each <Value ...> or <Key ...>
                    for element in stat_subkey.get_elements():
                        if isinstance(element, RegistryValue):
                            # e.g. name="Type" => element.value => "4"
                            stat_info[element.name] = element.value
                        elif isinstance(element, RegistryKey):
                            # possibly <Key name="bits">
                            if element.name.lower() == "bits":
                                bits_list = []
                                # parse each <Key name="0"> or "1"
                                for bit_subkey in element.get_elements():
                                    if isinstance(bit_subkey, RegistryKey):
                                        bit_id_str = bit_subkey.name
                                        ach_info: Dict[str, any] = {}
                                        # parse each <Value ...> or <Key display>
                                        for bit_elem in bit_subkey.get_elements():
                                            if isinstance(bit_elem, RegistryValue):
                                                # e.g. name="name", value="EP2..."
                                                ach_info[bit_elem.name] = bit_elem.value
                                            elif isinstance(bit_elem, RegistryKey):
                                                # e.g. name="display"
                                                if bit_elem.name.lower() == "display":
                                                    disp_dict: Dict[str, any] = {}
                                                    for disp_val in bit_elem.get_elements():
                                                        if isinstance(disp_val, RegistryValue):
                                                            disp_dict[disp_val.name] = disp_val.value
                                                    ach_info["display"] = disp_dict
                                        # store the "bit_id" or "key_name"
                                        ach_info["bit_id"] = bit_id_str
                                        bits_list.append(ach_info)
                                stat_info["bits"] = bits_list
                    # store it in stats_definitions
                    self_obj.stats_definitions[sid_str] = stat_info

        return self_obj

    @classmethod
    def from_file(cls, filepath: str) -> "UserStats_Obsolete":
        """
        Reads the .bin from disk, returns a UserStats_Obsolete instance.
        """
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")
        with open(filepath, "rb") as f:
            data = f.read()
        in_stream = BytesIO(data)
        return cls.from_stream(in_stream)

    def computeCrc(self) -> int:
        """
        If you want to recalc a 32-bit CRC across the entire structure.
        We'll do a simple approach with zlib, incorporating (appid, gameName, version)
        plus the stats and achievements.
        """
        running = 0
        # incorporate the appid
        try:
            appid_int = int(self.appid)
            running = zlib.crc32(struct.pack('<I', appid_int), running)
        except ValueError:
            # if not numeric
            running = zlib.crc32(self.appid.encode('utf-8'), running)

        # incorporate gameName, version
        if self.gameName:
            running = zlib.crc32(self.gameName.encode('utf-8'), running)
        if self.version:
            running = zlib.crc32(self.version.encode('utf-8'), running)

        # incorporate stats
        sorted_sids = sorted(self.stats_definitions.keys(), key=lambda s: int(s))
        for sid in sorted_sids:
            # incorporate the stat ID
            sid_int = int(sid)
            running = zlib.crc32(struct.pack('<I', sid_int), running)
            st_info = self.stats_definitions[sid]
            # e.g. st_info might have { "Type": "4", "ID": "0", "data": 2621465, "bits": [...] }
            # incorporate those
            for key_name, val in sorted(st_info.items()):
                if key_name.lower() == "bits":
                    # each bit = { "bit_id":"0", "name":"EP2_...", "bit":0, "display": { ... } }
                    for ach in val:
                        # incorporate the bit_id
                        try:
                            bit_id_int = int(ach.get("bit_id", 0))
                            running = zlib.crc32(struct.pack('<I', bit_id_int), running)
                        except ValueError:
                            # if it's not numeric
                            running = zlib.crc32((ach.get("bit_id", "")).encode('utf-8'), running)

                        # incorporate name, bit
                        nm = ach.get("name", "")
                        running = zlib.crc32(nm.encode('utf-8'), running)

                        # 'bit' might be int
                        b_val = ach.get("bit", None)
                        if isinstance(b_val, int):
                            running = zlib.crc32(struct.pack('<I', b_val), running)
                        # incorporate display
                        disp = ach.get("display", {})
                        for dk, dv in sorted(disp.items()):
                            if isinstance(dv, str):
                                running = zlib.crc32(dv.encode('utf-8'), running)
                else:
                    # might be "Type", "ID", "data", etc.
                    if isinstance(val, str):
                        running = zlib.crc32(val.encode('utf-8'), running)
                    elif isinstance(val, int):
                        running = zlib.crc32(struct.pack('<I', val), running)

        new_crc = running & 0xFFFFFFFF
        return new_crc

    def printAllInfo(self):
        """
        A helper method to print everything that was parsed, following the structure.
        """
        print(f"AppID: {self.appid}")
        print(f"GameName: {self.gameName}")
        print(f"Version: {self.version}")
        print(f"CRC (from file): {self.crc}")

        print("\n-- Stats Definitions --")
        # e.g. "0" => { "Type":"4", "ID":"0", "data":..., "bits":[...] }
        for sid_str, st_info in sorted(self.stats_definitions.items(), key=lambda x: int(x[0])):
            print(f" Stat ID: {sid_str}")
            for k, v in st_info.items():
                if k.lower() == "bits" and isinstance(v, list):
                    print(f"   Achievements:")
                    for ach in v:
                        # ach might have { "bit_id":"0", "name":"EP2_...", "bit": 0, "display": {...} }
                        print(f"    - bit_id={ach.get('bit_id')}, name={ach.get('name')}, bit={ach.get('bit')}")
                        disp_info = ach.get("display", {})
                        print(f"      display => name={disp_info.get('name')}, desc={disp_info.get('desc')}, hidden={disp_info.get('hidden')}")
                        print(f"                 icon={disp_info.get('icon')}, icon_gray={disp_info.get('icon_gray')}")
                else:
                    print(f"   {k} = {v}")

        print("\nDone listing info from this obsolete userstats file.\n")



# ----------------------------
# Example Usage
# ----------------------------

def load_and_parse_user_game_stats_schema(appid: int, filepath: str):
    """
    Universal approach to parsing any .bin file into UserStatsSchema.
    Prints discovered stats and achievements, plus thorough usage of new schema methods.
    """
    import os
    from io import BytesIO

    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"The file {filepath} does not exist.")

    # 1) Read the entire binary into memory
    with open(filepath, 'rb') as f:
        data = f.read()
    input_stream = BytesIO(data)

    # 2) Deserialize into a KeyValuesSystem
    kvs = KeyValuesSystem()
    kvs.deserialize(input_stream)

    # 3) Initialize a UserStatsSchema from the KeyValuesSystem
    schema = UserStatsSchema(registry=kvs)

    # Basic file/game-level information
    print(f"Game ID: {schema.getGameId()}")
    print(f"Game Name: {schema.getGameName()}")
    print(f"Schema Version: {schema.getVersion()}")

    # ---------------------------------------------------------------------
    # Display All Stat Information
    # ---------------------------------------------------------------------
    stat_ids_iter = schema.get_defined_stat_ids()
    stat_list = []
    print("\n--- Discovered Stats ---")
    while stat_ids_iter.hasNext():
        sid = stat_ids_iter.next()
        stat_list.append(sid)

        s_name = schema.getStatName(sid)
        s_type = schema.getStatType(sid)
        s_trusted = schema.isStatSetByTrustedGS(sid)
        s_min = schema.getStatMin(sid)
        s_max = schema.getStatMax(sid)
        s_maxchange = schema.getStatMaxChange(sid)
        s_default = schema.getStatDefault(sid)
        s_windowsize = schema.getStatWindowSize(sid)
        s_dirtybits = schema.getStatDirtyBits(sid)
        s_updates = schema.getStatUpdates(sid)
        s_incr_only = schema.getStatIncrementOnly(sid)
        s_data_int = schema.getStatDataInt(sid)
        s_data_float = schema.getStatDataFloat(sid)
        s_state = schema.getStatState(sid)
        s_display_name = schema.getStatDisplayName(sid)

        print(f"\nStat ID = {sid}")
        print(f"  Name               = {s_name}")
        print(f"  DisplayName        = {s_display_name}")
        print(f"  Type               = {s_type.name}")
        print(f"  bSetByTrustedGS    = {s_trusted}")
        print(f"  min                = {s_min}")
        print(f"  max                = {s_max}")
        print(f"  maxChange          = {s_maxchange}")
        print(f"  default            = {s_default}")
        print(f"  windowSize         = {s_windowsize}")
        print(f"  dirtyBits          = {s_dirtybits}")
        print(f"  updates            = {s_updates}")
        print(f"  incrementOnly      = {s_incr_only}")
        print(f"  dataInt            = {s_data_int}")
        print(f"  dataFloat          = {s_data_float}")
        print(f"  state              = {s_state}")

    if not stat_list:
        print("\n(No stats found.)")

    # ---------------------------------------------------------------------
    # Display All Achievement Information
    # ---------------------------------------------------------------------
    achievements_iter = schema.get_defined_achievement_ids()
    print("\n--- Discovered Achievements ---")
    ach_list = []
    while achievements_iter.hasNext():
        ach_id = achievements_iter.next()
        ach_list.append(ach_id)

        a_name = schema.getAchievementName(ach_id)
        a_hidden = schema.isAchievementDisplayHidden(ach_id)
        a_icon = schema.getAchievementDisplayIcon(ach_id)
        a_icon_gray = schema.getAchievementDisplayIconGray(ach_id)  # REQUIRES getAchievementDisplayIconGray
        a_icon_handle = schema.getAchievementDisplayIconHandle(ach_id)
        a_icon_handle_gray = schema.getAchievementDisplayIconHandleGray(ach_id)
        a_award_item = schema.getAchievementAwardItem(ach_id)
        a_progress_min = schema.getAchievementProgressMin(ach_id)
        a_progress_max = schema.getAchievementProgressMax(ach_id)
        a_progress_op = schema.getAchievementProgressOperation(ach_id)
        a_progress_operand1 = schema.getAchievementProgressOperand(ach_id, 1)

        # Show multi-language or single-language display info:
        a_display_name_en = schema.getAchievementDisplayName_lang(ach_id, "english")
        a_display_desc_en = schema.getAchievementDisplayDesc_lang(ach_id, "english")

        print(f"\nAchievement ID   = {ach_id}")
        print(f"  Name           = {a_name}")
        print(f"  Hidden?        = {a_hidden}")
        print(f"  Icon           = {a_icon}")
        print(f"  Icon Gray      = {a_icon_gray}")
        print(f"  Icon Handle    = {a_icon_handle}")
        print(f"  Icon HandleGray= {a_icon_handle_gray}")
        print(f"  Award Item     = {a_award_item}")
        print(f"  Progress Min   = {a_progress_min}")
        print(f"  Progress Max   = {a_progress_max}")
        print(f"  Progress Oper  = {a_progress_op}")
        print(f"  Progress Opnd1 = {a_progress_operand1}")
        print(f"  DisplayName(english) = {a_display_name_en}")
        print(f"  DisplayDesc(english) = {a_display_desc_en}")

    if not ach_list:
        print("\n(No achievements found.)")

    # ---------------------------------------------------------------------
    # Optional: Demonstrate GlobalStats usage with the first discovered stat
    # ---------------------------------------------------------------------
    if stat_list:
        chosen_stat = stat_list[0]
        global_stats = GlobalStats(schema)
        print("\n--- Demonstrating GlobalStats usage ---")
        print(f"Setting Stat ID={chosen_stat} to 42 (int64)")
        global_stats.setStatInt64(chosen_stat, 42.9)
        read_back = global_stats.getStatInt64(chosen_stat)
        print(f"Reading it back: {read_back}")

        if schema.getStatType(chosen_stat) == UserStatType.float_type:
            print(f"Setting Stat ID={chosen_stat} to 99.99 (double)")
            global_stats.setStatDouble(chosen_stat, 99.99)
            dval = global_stats.getStatDouble(chosen_stat)
            print(f"Reading it back as double: {dval}")
        else:
            print("Chosen stat is not float type, skipping double example.")
    else:
        print("\nNo stats found to demonstrate setting values.")

    print("\n--- Done Displaying All Info ---")

    # Suppose you have usergamestats_12345_202990.bin
    user_stats = UserStats.from_file("UserGameStats_5962099_440.bin")
    print("CRC:", user_stats.crc)
    print("PendingChanges:", user_stats.pendingChanges)
    for sid, val in user_stats.stats.items():
        print(f"Stat {sid} => {val}")
        if sid in user_stats.achievedAt:
            times = user_stats.achievedAt[sid]
            for i, tstamp in enumerate(times.bit):
                if tstamp != 0:
                    print(f"  AchievementBit={i}, achievedAt={tstamp}")


if __name__ == "__main__":
    """This code is for the 'obsolete' / 2009 stats bin files"""
    file_path = "UserGameStats_5962099_590.bin"

    try:
        obsolete_stats = UserStats_Obsolete.from_file(file_path)
        # Print all info
        obsolete_stats.printAllInfo()

        # Optionally recalc CRC
        new_crc = obsolete_stats.computeCrc()
        print(f"Recomputed CRC: {new_crc}")

    except FileNotFoundError:
        print("File not found!")
    except Exception as e:
        print(f"Error parsing obsolete stats file: {e}")

    """This code is for loading 2010+ schema binaries"""
    appid = 202990
    filepath = f"UserGameStatsSchema_{appid}.bin"

    try:
        load_and_parse_user_game_stats_schema(appid, filepath)
    except Exception as ex:
        print(f"Error occurred: {ex}")