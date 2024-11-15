import struct
from datetime import datetime


class GameConnectToken:
    def __init__(self, token = b'', steamGlobalId= 0, timestamp = None):
        self.token = token
        self.steamGlobalId = steamGlobalId
        self.timestamp = timestamp

    def serialize(self):
        # Using struct to pack ULONGLONG, ULONGLONG, DWORD corresponding to C++ types
        return struct.pack('<QQI', self.token, self.steamGlobalId, self.timestamp)

    def serialize_single_deprecated(self):
        # Using struct to pack ULONGLONG, ULONGLONG, DWORD corresponding to C++ types
        return struct.pack('<QQ', self.token, self.steamGlobalId)

    def deserialize(self, buffer):
        # Using struct to pack ULONGLONG, ULONGLONG, DWORD corresponding to C++ types
        self.token, self.steamGlobalId, timestamp = struct.unpack('<QQI', buffer)
        self.timestamp = datetime.utcfromtimestamp(timestamp).strftime('%m/%d/%Y %H:%M:%S')
        return self.token, self.steamGlobalId, self.timestamp

    def deserialize_single_deprecated(self, buffer):
        # Using struct to pack ULONGLONG, ULONGLONG, DWORD corresponding to C++ types
        self.token, self.steamGlobalId = struct.unpack('<QQ', buffer)
        return self.token, self.steamGlobalId