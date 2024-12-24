import struct
class StatsUDP:
    def __init__(self, data):
        self.deserialize(data)

    def deserialize(self, data):
        fields = struct.unpack('<QQQQQ', data)
        (
            self.m_ulPktSent,
            self.m_ulBytesSent,
            self.m_ulPktRecv,
            self.m_ulPktProcessed,
            self.m_ulBytesRecv,
        ) = fields

    def __str__(self):
        return (
            f"StatsUDP(m_ulPktSent={self.m_ulPktSent}, m_ulBytesSent={self.m_ulBytesSent}, "
            f"m_ulPktRecv={self.m_ulPktRecv}, m_ulPktProcessed={self.m_ulPktProcessed}, "
            f"m_ulBytesRecv={self.m_ulBytesRecv})"
        )

    def __repr__(self):
        return self.__str__()
class StatsVConn:
    def __init__(self, data):
        self.deserialize(data)

    def deserialize(self, data):
        udp_size = struct.calcsize('<QQQQQ')
        stats_udp_data = data[8:8 + udp_size]
        self.m_cConnectionsUDP, self.m_cConnectionsTCP = struct.unpack('<II', data[:8])
        self.m_StatsUDP = StatsUDP(stats_udp_data)

        remaining_data = data[8 + udp_size:]
        fields = struct.unpack('<QQQQQQQQQQQQQIIII', remaining_data)
        (
            self.m_ulPktAbandoned,
            self.m_cConnReqReceived,
            self.m_ulPktResent,
            self.m_ulMsgSent,
            self.m_ulMsgSentFailed,
            self.m_ulMsgRecv,
            self.m_ulDatagramsSent,
            self.m_ulDatagramsRecv,
            self.m_ulBadPktRecv,
            self.m_ulUnknownConnPktRecv,
            self.m_ulMissedPktRecv,
            self.m_ulDupPktRecv,
            self.m_ulFailedConnectChallenges,
            self.m_unMicroSecAvgLatency,
            self.m_unMicroSecMinLatency,
            self.m_unMicroSecMaxLatency,
            self.m_unMemPoolMsgInUse,
        ) = fields

    def __str__(self):
        return (
            f"StatsVConn(m_cConnectionsUDP={self.m_cConnectionsUDP}, m_cConnectionsTCP={self.m_cConnectionsTCP}, "
            f"m_StatsUDP={self.m_StatsUDP}, m_ulPktAbandoned={self.m_ulPktAbandoned}, "
            f"m_cConnReqReceived={self.m_cConnReqReceived}, m_ulPktResent={self.m_ulPktResent}, "
            f"m_ulMsgSent={self.m_ulMsgSent}, m_ulMsgSentFailed={self.m_ulMsgSentFailed}, "
            f"m_ulMsgRecv={self.m_ulMsgRecv}, m_ulDatagramsSent={self.m_ulDatagramsSent}, "
            f"m_ulDatagramsRecv={self.m_ulDatagramsRecv}, m_ulBadPktRecv={self.m_ulBadPktRecv}, "
            f"m_ulUnknownConnPktRecv={self.m_ulUnknownConnPktRecv}, m_ulMissedPktRecv={self.m_ulMissedPktRecv}, "
            f"m_ulDupPktRecv={self.m_ulDupPktRecv}, m_ulFailedConnectChallenges={self.m_ulFailedConnectChallenges}, "
            f"m_unMicroSecAvgLatency={self.m_unMicroSecAvgLatency}, "
            f"m_unMicroSecMinLatency={self.m_unMicroSecMinLatency}, m_unMicroSecMaxLatency={self.m_unMicroSecMaxLatency}, "
            f"m_unMemPoolMsgInUse={self.m_unMemPoolMsgInUse})"
        )

    def __repr__(self):
        return self.__str__()
class StatsLogon:
    def __init__(self, data):
        self.deserialize(data)

    def deserialize(self, data):
        fields = struct.unpack('<iiii', data)
        (
            self.m_nConnectAttempts,
            self.m_nConnectSuccesses,
            self.m_nConnectFailures,
            self.m_nConnectionsDropped,
        ) = fields

    def __str__(self):
        return (
            f"StatsLogon(m_nConnectAttempts={self.m_nConnectAttempts}, m_nConnectSuccesses={self.m_nConnectSuccesses}, "
            f"m_nConnectFailures={self.m_nConnectFailures}, m_nConnectionsDropped={self.m_nConnectionsDropped})"
        )

    def __repr__(self):
        return self.__str__()
