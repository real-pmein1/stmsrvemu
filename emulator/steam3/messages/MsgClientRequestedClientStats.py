import struct
from enum import IntEnum


# Define the ClientStat enum
class ClientStat(IntEnum):
    p2pConnectionsUDP = 0
    p2pConnectionsRelay = 1
    p2pGamesConnections = 2
    p2pVoiceConnections = 3
    p2pBytesDownloaded = 4


class MsgClientRequestedClientStats:
    def __init__(self):
        """
        Initialize the MsgClientRequestedClientStats with an empty stats list.
        """
        self.stats_list = []

    def add_requested_stats(self, stat):
        """
        Add a single stat to the stats list.
        :param stat: A ClientStat enum value.
        """
        if not isinstance(stat, ClientStat):
            raise TypeError("Stat must be an instance of ClientStat enum.")
        self.stats_list.append(stat)

    def serialize(self):
        """
        Serializes the MsgClientRequestedClientStats object into a byte buffer.
        :return: byte buffer containing the serialized data
        """
        # Create a byte buffer
        buffer = b""

        # Get the count of stats and write it to the buffer
        stats_count = len(self.stats_list)
        buffer += struct.pack('<I', stats_count)

        # Write each stat (4 bytes per stat, int32)
        for stat in self.stats_list:
            buffer += struct.pack('<I', stat)

        return buffer

    @classmethod
    def deserialize(cls, byte_buffer):
        """
        Deserializes a byte buffer into a MsgClientRequestedClientStats object.
        :param byte_buffer: byte buffer containing the serialized data
        :return: MsgClientRequestedClientStats object
        """
        # Read stats count (4 bytes, int32)
        stats_count = struct.unpack('<I', byte_buffer[:4])[0]

        # Read each stat (4 bytes per stat, int32) and convert to ClientStat enum
        stats_list = []
        offset = 4
        for _ in range(stats_count):
            stat = struct.unpack('<I', byte_buffer[offset:offset + 4])[0]
            stats_list.append(ClientStat(stat))
            offset += 4

        # Create a new instance and populate the stats list
        instance = cls()
        instance.stats_list = stats_list
        return instance

    def __repr__(self):
        stats_repr = [stat.name for stat in self.stats_list]
        return f"MsgClientRequestedClientStats(stats_list={stats_repr})"
