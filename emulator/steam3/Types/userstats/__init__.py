import time
from enum import Enum
from typing import List
from steam3.Types.keyvaluesystem import RegistryElement
class Iterator:
    def __init__(self, items: List):
        self.items = items
        self.index = 0

    def hasNext(self) -> bool:
        return self.index < len(self.items)

    def next(self):
        if not self.hasNext():
            return None
        item = self.items[self.index]
        self.index += 1
        return item

    def remove(self):
        raise Exception("Remove operation not supported")
class UserStatType(Enum):
    invalid = 0
    int_type = 1
    float_type = 2
    avgRate = 3
    achievements = 4
    groupAchievements = 5
class AchievementId:
    def __init__(self, stat_id,  bit: int):
        self.stat_id = stat_id
        self.bit = bit

    def __repr__(self):
        return f"AchievementId(stat_id={self.stat_id}, bit={self.bit})"
class Word:
    @staticmethod
    def parse_string(s: str) -> int:
        # Convert a numeric string to int
        try:
            return int(s)
        except ValueError:
            raise Exception(f"Cannot parse word from string: {s}")
class Byte_:
    @staticmethod
    def parse_string(s: str) -> int:
        # Convert a numeric string to int
        try:
            return int(s)
        except ValueError:
            raise Exception(f"Cannot parse byte from string: {s}")
class TextFormatter:
    @staticmethod
    def format(value: int, buffer: List[str]) -> str:
        # Return string representation (the 'buffer' is unused in Python)
        return str(value)
Result_OK = 0
Result_invalidParam = 1
class Flags:
    @staticmethod
    def is_flag_set(value: int, mask: int) -> bool:
        return (value & mask) != 0

    @staticmethod
    def set(value: int, mask: int) -> int:
        return value | mask

    @staticmethod
    def reset(value: int, mask: int) -> int:
        return value & ~mask
class AchievedAt:
    """
    C++ code says AchievedAt has a 'bit[32]'.
    We'll store them in a list or dict for Python.
    """
    def __init__(self):
        # Each index is an int (timestamp)
        self.bit = [0]*32
class StatDict(dict):
    def put(self, key, value):
        self[key] = value

    def get(self, key, default=None):
        return super().get(key, default)
class Serializable:
    def serialize(self, out):
        pass

    def deserialize(self, inp):
        pass
def currentTime() -> int:
    # just return an int representing "now"
    # In real code, you might return time.time() or int(time.time())
    return int(time.time())
StatId = int  # Alias for clarity
class AchievementsIterator:
    def __init__(self, elements: List[RegistryElement]):
        # We only care about subkeys
        self.elements = [e for e in elements if e.is_key()]
        self.index = 0

    def hasNext(self) -> bool:
        return self.index < len(self.elements)

    def next(self) -> AchievementId:
        if not self.hasNext():
            raise Exception("No more achievements")
        achievement_key = self.elements[self.index]
        self.index += 1
        if not achievement_key.is_key():
            raise Exception("Expected a key for achievement")
        bit_str = achievement_key.name  # e.g. "0", "1", "2"
        bit = Byte_.parse_string(bit_str)
        parent_stat_key = achievement_key.parent.parent
        if not parent_stat_key:
            raise Exception("Achievement key has no parent stat key")
        stat_id = Word.parse_string(parent_stat_key.name)
        return AchievementId(stat_id=stat_id, bit=bit)

    def remove(self):
        raise Exception("Illegal operation")
