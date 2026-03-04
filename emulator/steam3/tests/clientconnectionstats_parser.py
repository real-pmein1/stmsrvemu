import struct
from io import BytesIO


class StatsLogon:
    def __init__(self):
        self.m_nConnectAttempts = 0
        self.m_nConnectSuccesses = 0
        self.m_nConnectFailures = 0
        self.m_nConnectionsDropped = 0

    def deserialize(self, buffer: BytesIO):
        self.m_nConnectAttempts = struct.unpack('<i', buffer.read(4))[0]
        self.m_nConnectSuccesses = struct.unpack('<i', buffer.read(4))[0]
        self.m_nConnectFailures = struct.unpack('<i', buffer.read(4))[0]
        self.m_nConnectionsDropped = struct.unpack('<i', buffer.read(4))[0]


class StatsVConn:
    def __init__(self):
        self.m_cConnectionsUDP = 0
        self.m_cConnectionsTCP = 0
        self.m_ulPktAbandoned = 0
        self.m_cConnReqReceived = 0
        self.m_ulPktResent = 0
        self.m_ulMsgSent = 0
        self.m_ulMsgSentFailed = 0
        self.m_ulMsgRecv = 0
        self.m_ulDatagramsSent = 0
        self.m_ulDatagramsRecv = 0
        self.m_ulBadPktRecv = 0
        self.m_ulUnknownConnPktRecv = 0
        self.m_ulMissedPktRecv = 0
        self.m_ulDupPktRecv = 0
        self.m_ulFailedConnectChallenges = 0
        self.m_unMicroSecAvgLatency = 0
        self.m_unMicroSecMinLatency = 0
        self.m_unMicroSecMaxLatency = 0
        self.m_unMemPoolMsgInUse = 0

    def deserialize(self, buffer: BytesIO):
        self.m_cConnectionsUDP = struct.unpack('<I', buffer.read(4))[0]
        self.m_cConnectionsTCP = struct.unpack('<I', buffer.read(4))[0]
        # Simulating skipping of the StatsUDP structure (48 bytes)
        buffer.seek(48, 1)
        try:
            self.m_ulPktAbandoned = struct.unpack('<Q', buffer.read(8))[0]
            self.m_cConnReqReceived = struct.unpack('<Q', buffer.read(8))[0]
            self.m_ulPktResent = struct.unpack('<Q', buffer.read(8))[0]
            self.m_ulMsgSent = struct.unpack('<Q', buffer.read(8))[0]
            self.m_ulMsgSentFailed = struct.unpack('<Q', buffer.read(8))[0]
            self.m_ulMsgRecv = struct.unpack('<Q', buffer.read(8))[0]
            self.m_ulDatagramsSent = struct.unpack('<Q', buffer.read(8))[0]
            self.m_ulDatagramsRecv = struct.unpack('<Q', buffer.read(8))[0]
            self.m_ulBadPktRecv = struct.unpack('<Q', buffer.read(8))[0]
            self.m_ulUnknownConnPktRecv = struct.unpack('<Q', buffer.read(8))[0]
            self.m_ulMissedPktRecv = struct.unpack('<Q', buffer.read(8))[0]
            self.m_ulDupPktRecv = struct.unpack('<Q', buffer.read(8))[0]
            self.m_ulFailedConnectChallenges = struct.unpack('<Q', buffer.read(8))[0]
            self.m_unMicroSecAvgLatency = struct.unpack('<I', buffer.read(4))[0]
            self.m_unMicroSecMinLatency = struct.unpack('<I', buffer.read(4))[0]
            self.m_unMicroSecMaxLatency = struct.unpack('<I', buffer.read(4))[0]
            self.m_unMemPoolMsgInUse = struct.unpack('<I', buffer.read(4))[0]
        except Exception as e:
            print(f"gs status update: {e}")
            pass


class MsgClientStats:
    def __init__(self):
        self.m_StatsLogon = StatsLogon()
        self.m_StatsVConn = StatsVConn()

    def deserialize(self, buffer: bytes):
        """
        Parses the byte buffer to extract MsgClientStats fields.
        """
        stream = BytesIO(buffer)

        # Deserialize StatsLogon
        self.m_StatsLogon.deserialize(stream)

        # Deserialize StatsVConn
        self.m_StatsVConn.deserialize(stream)

        return self

    def print_stats(self):
        """
        Prints the deserialized stats for debugging purposes.
        """
        print("StatsLogon:")
        print(f"  Connect Attempts: {self.m_StatsLogon.m_nConnectAttempts}")
        print(f"  Connect Successes: {self.m_StatsLogon.m_nConnectSuccesses}")
        print(f"  Connect Failures: {self.m_StatsLogon.m_nConnectFailures}")
        print(f"  Connections Dropped: {self.m_StatsLogon.m_nConnectionsDropped}")

        print("\nStatsVConn:")
        print(f"  UDP Connections: {self.m_StatsVConn.m_cConnectionsUDP}")
        print(f"  TCP Connections: {self.m_StatsVConn.m_cConnectionsTCP}")
        print(f"  Packets Abandoned: {self.m_StatsVConn.m_ulPktAbandoned}")
        print(f"  Connection Requests Received: {self.m_StatsVConn.m_cConnReqReceived}")
        print(f"  Packets Resent: {self.m_StatsVConn.m_ulPktResent}")
        print(f"  Messages Sent: {self.m_StatsVConn.m_ulMsgSent}")
        print(f"  Messages Sent Failed: {self.m_StatsVConn.m_ulMsgSentFailed}")
        print(f"  Messages Received: {self.m_StatsVConn.m_ulMsgRecv}")
        print(f"  Datagrams Sent: {self.m_StatsVConn.m_ulDatagramsSent}")
        print(f"  Datagrams Received: {self.m_StatsVConn.m_ulDatagramsRecv}")
        print(f"  Bad Packets Received: {self.m_StatsVConn.m_ulBadPktRecv}")
        print(f"  Unknown Connection Packets Received: {self.m_StatsVConn.m_ulUnknownConnPktRecv}")
        print(f"  Missed Packets Received: {self.m_StatsVConn.m_ulMissedPktRecv}")
        print(f"  Duplicate Packets Received: {self.m_StatsVConn.m_ulDupPktRecv}")
        print(f"  Failed Connection Challenges: {self.m_StatsVConn.m_ulFailedConnectChallenges}")
        print(f"  Average Latency (microseconds): {self.m_StatsVConn.m_unMicroSecAvgLatency}")
        print(f"  Min Latency (microseconds): {self.m_StatsVConn.m_unMicroSecMinLatency}")
        print(f"  Max Latency (microseconds): {self.m_StatsVConn.m_unMicroSecMaxLatency}")
        print(f"  Memory Pool Messages in Use: {self.m_StatsVConn.m_unMemPoolMsgInUse}")


# Example usage
# Sample buffer: You need to replace this with actual data from the packet
"""buffer = (
        struct.pack('<i', 5) +  # Connect Attempts
        struct.pack('<i', 4) +  # Connect Successes
        struct.pack('<i', 1) +  # Connect Failures
        struct.pack('<i', 0) +  # Connections Dropped
        struct.pack('<I', 20) +  # UDP Connections
        struct.pack('<I', 30) +  # TCP Connections
        struct.pack('<48x') +  # Simulate 48 bytes for StatsUDP
        struct.pack('<Q', 100) +  # Packets Abandoned
        struct.pack('<Q', 50) +  # Connection Requests Received
        struct.pack('<Q', 10) +  # Packets Resent
        struct.pack('<Q', 500) +  # Messages Sent
        struct.pack('<Q', 2) +  # Messages Sent Failed
        struct.pack('<Q', 300) +  # Messages Received
        struct.pack('<Q', 250) +  # Datagrams Sent
        struct.pack('<Q', 275) +  # Datagrams Received
        struct.pack('<Q', 0) +  # Bad Packets Received
        struct.pack('<Q', 1) +  # Unknown Connection Packets Received
        struct.pack('<Q', 0) +  # Missed Packets Received
        struct.pack('<Q', 2) +  # Duplicate Packets Received
        struct.pack('<Q', 1) +  # Failed Connection Challenges
        struct.pack('<I', 500) +  # Avg Latency (microseconds)
        struct.pack('<I', 100) +  # Min Latency (microseconds)
        struct.pack('<I', 2000) +  # Max Latency (microseconds)
        struct.pack('<I', 5)  # Memory Pool Messages in Use
)"""
packet = b'\xc6\x02\x00\x00$\x02\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xef\xc4\xa0\x9b\x01\x01\x00\x10\x01\x00v/\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x11\x00\x00\x00\x00\x00\x00\x00\x0c\x06\x00\x00\x00\x00\x00\x00\x13\x00\x00\x00\x00\x00\x00\x00\x13\x00\x00\x00\x00\x00\x00\x00\xe0\n\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xb1\xcc\x03\x00%\n\x03\x00>\x8f\x04\x00\x01\x00\x00\x00'
packet = packet[36:]
# Deserialize the buffer
client_stats = MsgClientStats()
client_stats.deserialize(packet)

# Print the parsed data
client_stats.print_stats()