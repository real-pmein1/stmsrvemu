from __future__ import annotations
import struct
import logging

from steam3.Types.emsg import EMsg

log = logging.getLogger("MSGClientStoreUserStats")


class MSGClientStoreUserStats:
    """
    Client request to store/update user statistics for a specific game.

    Binary format (MsgClientStoreUserStats_t):
        - m_ulGameID: 8 bytes (uint64)
        - m_cStats: 4 bytes (int32)
    Header total: 12 bytes
    Followed by: [statID: 2 bytes (uint16)][statValue: 4 bytes (uint32)] x m_cStats

    Fields:
        gameID (int): 64-bit game/app identifier
        stats (dict): Dictionary of stat_id -> stat_value to store
    """

    def __init__(self, client_obj, data: bytes | None = None, version: int | None = None):
        self.client_obj = client_obj
        self.version = version or 1

        # Initialize fields with defaults
        self.gameID = 0
        self.stats = {}  # stat_id -> stat_value

        if data:
            self.deserialize(data)

    def deserialize(self, data: bytes):
        """
        Deserialize binary data into message fields.

        Binary format (little-endian):
        - gameID: 8 bytes (uint64)
        - statsCount: 4 bytes (int32)
        - For each stat:
          - statID: 2 bytes (uint16)
          - statValue: 4 bytes (uint32)
        """
        if len(data) < 12:  # Minimum: 8 + 4 = 12 bytes header
            raise ValueError("Insufficient data for ClientStoreUserStats")

        offset = 0

        # Parse game ID and stats count
        self.gameID, statsCount = struct.unpack_from('<QI', data, offset)
        offset += 12

        # Parse stats
        self.stats = {}
        for _ in range(statsCount):
            if offset + 6 > len(data):
                raise ValueError("Insufficient data for stat entries")

            statID, statValue = struct.unpack_from('<HI', data, offset)
            self.stats[statID] = statValue
            offset += 6

        log.debug(f"Parsed StoreUserStats: gameID={self.gameID}, statsCount={len(self.stats)}")
    
    def to_clientmsg(self):
        """Build CMResponse for sending to client"""
        from steam3.cm_packet_utils import CMResponse
        from io import BytesIO

        packet = CMResponse(EMsg.ClientStoreUserStats, self.client_obj)

        # Build data buffer
        buffer = BytesIO()

        # Write game ID and stats count (12 bytes header)
        buffer.write(struct.pack('<QI', self.gameID, len(self.stats)))

        # Write stats in sorted order for consistency
        for statID in sorted(self.stats.keys()):
            statValue = self.stats[statID]
            buffer.write(struct.pack('<HI', statID, statValue))

        packet.data = buffer.getvalue()
        packet.length = len(packet.data)

        return packet

    def to_protobuf(self):
        """Return protobuf message if available"""
        raise NotImplementedError("Protobuf version not implemented for StoreUserStats")

    def __repr__(self):
        return f"MSGClientStoreUserStats(gameID={self.gameID}, statsCount={len(self.stats)})"

    def __str__(self):
        return self.__repr__()