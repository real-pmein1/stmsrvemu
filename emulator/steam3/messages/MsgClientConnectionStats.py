import struct
from steam3.Types.stat_types import StatsLogon, StatsVConn


class MsgClientConnectionStats:
    def __init__(self, data):
        self.deserialize(data)

    def deserialize(self, data):
        logon_size = struct.calcsize('<iiii')
        logon_data = data[:logon_size]
        self.m_StatsLogon = StatsLogon(logon_data)

        vconn_data = data[logon_size:]
        self.m_StatsVConn = StatsVConn(vconn_data)

    def __str__(self):
        return (
            f"MsgClientConnectionStats(m_StatsLogon={self.m_StatsLogon}, "
            f"m_StatsVConn={self.m_StatsVConn})"
        )

    def __repr__(self):
        return self.__str__()

# Example usage
"""if __name__ == "__main__":
    # Simulated buffer with data
    data = b'\x01\x00\x00\x00\x02\x00\x00\x00\x03\x00\x00\x00\x04\x00\x00\x00' + \
           b'\x05\x00\x00\x00\x06\x00\x00\x00' + b'\x00' * 48 + \
           b'\x07\x00\x00\x00\x00\x00\x00\x00\x08\x00\x00\x00\x00\x00\x00\x00'

    stats = MsgClientStats(data)
    print(stats)  # This will print only the fields that were successfully parsed."""