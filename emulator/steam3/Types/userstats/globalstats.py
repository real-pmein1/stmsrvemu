import struct
from typing import Dict, Optional
from steam3.Types.userstats import Iterator, StatId
from steam3.Types.userstats.userstatsschema import UserStatsSchema

class GlobalStats:
    GLOBAL_STATS_LIFESPAN = 0

    def __init__(self, schema: Optional[UserStatsSchema] = None):
        self.own_schema: bool = False
        self.schema: Optional[UserStatsSchema] = schema
        self.timestamp: int = 0
        self.stats: Dict[StatId, int] = {}

    def __del__(self):
        pass  # Python handles memory management

    def setDay(self, day: Optional[int] = None):
        if day is None:
            day = self.GLOBAL_STATS_LIFESPAN
        self.setDayId(day // (60 * 60 * 24))

    def setDayId(self, day_id: int = GLOBAL_STATS_LIFESPAN):
        self.timestamp = day_id * (60 * 60 * 24)

    def getDay(self) -> int:
        return self.timestamp

    def getDayId(self) -> int:
        return self.timestamp // (60 * 60 * 24)

    def setSchema(self, schema: UserStatsSchema):
        if self.own_schema and self.schema:
            del self.schema
        self.own_schema = False
        self.schema = schema

    def getSchema(self) -> Optional[UserStatsSchema]:
        return self.schema

    def getSchemaSafe(self) -> UserStatsSchema:
        if not self.schema:
            raise Exception("No attached schema")
        return self.schema

    def reset(self, stat_id: Optional[StatId] = None):
        """
        If stat_id is None, reset all stats.
        Otherwise, remove a single stat.
        """
        if stat_id is None:
            self.stats.clear()
        else:
            self.stats.pop(stat_id, None)

    def getStatIds(self) -> Iterator:
        return Iterator(list(self.stats.keys()))

    def isSetStat(self, stat_id: StatId) -> bool:
        return stat_id in self.stats

    def isSetStatByName(self, name: str) -> bool:
        s = self.getSchemaSafe()
        sid = s.getStatId(name)
        return (sid in self.stats)

    def getStatData(self, stat_id: StatId) -> int:
        s = self.getSchemaSafe()
        return self.stats.get(stat_id, s.getStatAttribute_as_DWORD(stat_id, None, "default", 0))

    def setStatInt64(self, stat_id: StatId, value: int) -> bool:
        """
        Sets a stat to int64. Does not do validation in this universal approach.
        """
        self.stats[stat_id] = value
        return True

    def getStatInt64(self, stat_id: StatId) -> int:
        """
        Return the int64 stat value, or default if not set.
        """
        s = self.getSchemaSafe()
        return self.stats.get(stat_id, s.getStatAttribute_as_DWORD(stat_id, None, "default", 0))

    def setStatDouble(self, stat_id: StatId, value: float) -> bool:
        """
        Sets a stat to double by packing into a 64-bit integer.
        """
        packed = struct.pack('<d', value)
        as_uint64 = struct.unpack('<Q', packed)[0]
        self.stats[stat_id] = as_uint64
        return True

    def getStatDouble(self, stat_id: StatId) -> float:
        """
        Returns a double by unpacking the stored 64-bit integer.
        """
        s = self.getSchemaSafe()
        val = self.stats.get(stat_id, s.getStatAttribute_as_DWORD(stat_id, None, "default", 0))
        packed = struct.pack('<Q', val)
        return struct.unpack('<d', packed)[0]
