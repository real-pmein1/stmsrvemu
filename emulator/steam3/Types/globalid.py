from datetime import datetime, timedelta

from steam3.utilities import BitVector64


class GlobalID:
    def __init__(self, gid=0xFFFFFFFFFFFFFFFF):
        self.gidBits = BitVector64(gid)

    @property
    def SequentialCount(self):
        return self.gidBits[0, 0xFFFFF]

    @SequentialCount.setter
    def SequentialCount(self, value):
        self.gidBits[0, 0xFFFFF] = value

    @property
    def StartTime(self):
        start_time = self.gidBits[20, 0x3FFFFFFF]
        return datetime(2005, 1, 1) + timedelta(seconds=start_time)

    @StartTime.setter
    def StartTime(self, value):
        start_time = int((value - datetime(2005, 1, 1)).total_seconds())
        self.gidBits[20, 0x3FFFFFFF] = start_time

    @property
    def ProcessID(self):
        return self.gidBits[50, 0xF]

    @ProcessID.setter
    def ProcessID(self, value):
        self.gidBits[50, 0xF] = value

    @property
    def BoxID(self):
        return self.gidBits[54, 0x3FF]

    @BoxID.setter
    def BoxID(self, value):
        self.gidBits[54, 0x3FF] = value

    @property
    def Value(self):
        return self.gidBits.Data

    @Value.setter
    def Value(self, value):
        self.gidBits.Data = value

    def __eq__(self, other):
        if not isinstance(other, GlobalID):
            return False
        return self.gidBits.Data == other.gidBits.Data

    def __hash__(self):
        return hash(self.gidBits.Data)

    def __str__(self):
        return str(self.Value)

    @staticmethod
    def from_ulong(gid):
        return GlobalID(gid)

    def __int__(self):
        return self.gidBits.Data

# Implicit conversion methods
def ulong_to_globalid(gid):
    return GlobalID(gid)

def globalid_to_ulong(globalid):
    return int(globalid)

# Sealed UGCHandle class derived from GlobalID
class UGCHandle(GlobalID):
    def __init__(self, ugcId=0xFFFFFFFFFFFFFFFF):
        super().__init__(ugcId)

"""# Example usage
gid = GlobalID(123456789)
print(gid)
print(gid.Value)
gid.SequentialCount = 12345
print(gid.SequentialCount)
gid.StartTime = datetime(2022, 1, 1)
print(gid.StartTime)
gid.ProcessID = 10
print(gid.ProcessID)
gid.BoxID = 20
print(gid.BoxID)
print(gid == GlobalID(123456789))

ugc_handle = UGCHandle(987654321)
print(ugc_handle)
print(ugc_handle.Value)"""