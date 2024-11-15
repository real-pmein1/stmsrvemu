import struct
from io import BytesIO
from enum import IntEnum


# Define the ClientStat enum
class ClientStat(IntEnum):
    ClientStat_p2pConnectionsUDP = 0
    ClientStat_p2pConnectionsRelay = 1
    ClientStat_p2pGamesConnections = 2
    ClientStat_p2pVoiceConnections = 3
    ClientStat_p2pBytesDownloaded = 4


class MsgClientRequestedClientStats:
    def __init__(self, stats_count=0, stats_list=None):
        """
        Initialize the MsgClientRequestedClientStats with the stats count and list of stats.
        :param stats_count: The number of stats (int)
        :param stats_list: List of stats, each stat is a ClientStat (enum)
        """
        self.stats_count = stats_count
        self.stats_list = stats_list if stats_list is not None else []

    def serialize(self):
        """
        Serializes the MsgClientRequestedClientStats object into a byte buffer.
        :return: byte buffer containing the serialized data
        """
        stream = BytesIO()

        # Write the stats count (4 bytes, int32)
        stream.write(struct.pack('<I', self.stats_count))

        # Write each stat (4 bytes per stat, int32)
        for stat in self.stats_list:
            stream.write(struct.pack('<I', stat))

        return stream.getvalue()

    @classmethod
    def deserialize(cls, byte_buffer):
        """
        Deserializes a byte buffer into a MsgClientRequestedClientStats object.
        :param byte_buffer: byte buffer containing the serialized data
        :return: MsgClientRequestedClientStats object
        """
        stream = BytesIO(byte_buffer)

        # Read stats count (4 bytes, int32)
        stats_count = struct.unpack('<I', stream.read(4))[0]

        # Read each stat (4 bytes per stat, int32) and convert to ClientStat enum
        stats_list = []
        for _ in range(stats_count):
            stat = struct.unpack('<I', stream.read(4))[0]
            stats_list.append(ClientStat(stat))

        return cls(stats_count, stats_list)

    def __repr__(self):
        stats_repr = [stat.name for stat in self.stats_list]
        return f"MsgClientRequestedClientStats(stats_count={self.stats_count}, stats_list={stats_repr})"

# Example usage:

# Create a MsgClientRequestedClientStats object
msg = MsgClientRequestedClientStats(stats_count=3, stats_list=[100, 200, 300])

"""# Serialize it to a byte buffer
serialized_data = msg.serialize()
print(f"Serialized Data: {serialized_data}")"""
packet = b'h\x15\x00\x00$\x02\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xefmw\xea\x02\x01\x00\x10\x01\xfc\xdf\x8b\x00\x05\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x02\x00\x00\x00\x03\x00\x00\x00\x04\x00\x00\x00'

# Deserialize the byte buffer back to an object
deserialized_msg = MsgClientRequestedClientStats.deserialize(packet[36:])
print(f"Deserialized Object: {deserialized_msg}")