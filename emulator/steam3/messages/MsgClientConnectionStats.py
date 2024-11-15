import struct
from io import BytesIO


class MsgClientConnectionStats:
    def __init__(self):
        # Initialize all potential fields with None to indicate missing data.
        self.m_nConnectAttempts = None
        self.m_nConnectSuccesses = None
        self.m_nConnectFailures = None
        self.m_nConnectionsDropped = None
        self.m_cConnectionsUDP = None
        self.m_cConnectionsTCP = None
        self.m_ulPktAbandoned = None
        self.m_cConnReqReceived = None
        self.m_ulPktResent = None
        self.m_ulMsgSent = None
        self.m_ulMsgSentFailed = None
        self.m_ulMsgRecv = None
        self.m_ulDatagramsSent = None
        self.m_ulDatagramsRecv = None
        self.m_ulBadPktRecv = None
        self.m_ulUnknownConnPktRecv = None
        self.m_ulMissedPktRecv = None
        self.m_ulDupPktRecv = None
        self.m_ulFailedConnectChallenges = None
        self.m_unMicroSecAvgLatency = None
        self.m_unMicroSecMinLatency = None
        self.m_unMicroSecMaxLatency = None
        self.m_unMemPoolMsgInUse = None

    def deserialize(self, buffer: bytes):
        """
        Parses the byte buffer to extract MsgClientStats fields.
        Handles missing parts gracefully.
        """
        stream = BytesIO(buffer)

        # Try to deserialize each field safely
        try:
            self.m_nConnectAttempts = struct.unpack('<i', stream.read(4))[0]
            self.m_nConnectSuccesses = struct.unpack('<i', stream.read(4))[0]
            self.m_nConnectFailures = struct.unpack('<i', stream.read(4))[0]
            self.m_nConnectionsDropped = struct.unpack('<i', stream.read(4))[0]
        except Exception as e:
            print(f"client connection stats: {e}")
            pass

        # Try to deserialize StatsVConn
        try:
            self.m_cConnectionsUDP = struct.unpack('<I', stream.read(4))[0]
            self.m_cConnectionsTCP = struct.unpack('<I', stream.read(4))[0]
            # Simulate skipping of the StatsUDP structure (48 bytes)
            stream.seek(48, 1)
            self.m_ulPktAbandoned = struct.unpack('<Q', stream.read(8))[0]
            self.m_cConnReqReceived = struct.unpack('<Q', stream.read(8))[0]
            self.m_ulPktResent = struct.unpack('<Q', stream.read(8))[0]
            self.m_ulMsgSent = struct.unpack('<Q', stream.read(8))[0]
            self.m_ulMsgSentFailed = struct.unpack('<Q', stream.read(8))[0]
            self.m_ulMsgRecv = struct.unpack('<Q', stream.read(8))[0]
            self.m_ulDatagramsSent = struct.unpack('<Q', stream.read(8))[0]
            self.m_ulDatagramsRecv = struct.unpack('<Q', stream.read(8))[0]
            self.m_ulBadPktRecv = struct.unpack('<Q', stream.read(8))[0]
            self.m_ulUnknownConnPktRecv = struct.unpack('<Q', stream.read(8))[0]
            self.m_ulMissedPktRecv = struct.unpack('<Q', stream.read(8))[0]
            self.m_ulDupPktRecv = struct.unpack('<Q', stream.read(8))[0]
            self.m_ulFailedConnectChallenges = struct.unpack('<Q', stream.read(8))[0]
            self.m_unMicroSecAvgLatency = struct.unpack('<I', stream.read(4))[0]
            self.m_unMicroSecMinLatency = struct.unpack('<I', stream.read(4))[0]
            self.m_unMicroSecMaxLatency = struct.unpack('<I', stream.read(4))[0]
            self.m_unMemPoolMsgInUse = struct.unpack('<I', stream.read(4))[0]
        except Exception as e:
            print(f"client connection stats: {e}")
            pass

        return self

    def __str__(self):
        """
        String representation showing only available fields.
        """
        available_fields = {key: value for key, value in self.__dict__.items() if value is not None}
        return f"MsgClientStats({available_fields})"

    def __repr__(self):
        """
        Detailed representation for debugging, showing only available fields.
        """
        return self.__str__()

# Example usage
"""if __name__ == "__main__":
    # Simulated buffer with data
    data = b'\x01\x00\x00\x00\x02\x00\x00\x00\x03\x00\x00\x00\x04\x00\x00\x00' + \
           b'\x05\x00\x00\x00\x06\x00\x00\x00' + b'\x00' * 48 + \
           b'\x07\x00\x00\x00\x00\x00\x00\x00\x08\x00\x00\x00\x00\x00\x00\x00'

    stats = MsgClientStats()
    stats.deserialize(data)
    print(stats)  # This will print only the fields that were successfully parsed."""