from __future__ import annotations
import struct
import logging

from steam3.Types.emsg import EMsg

log = logging.getLogger("MSGClientGetUserStats")


class MSGClientGetUserStats:
    """
    Client request to get user statistics for a specific game.

    Binary format (MsgClientGetUserStats_t):
        - m_ulGameID: 8 bytes (uint64)
        - m_crcStats: 4 bytes (uint32)
        - m_nSchemaLocalVersion: 4 bytes (int32, signed - uses -1 for "no version")
    Total: 16 bytes

    Note: The target Steam ID comes from the message header, not the body.

    Fields:
        gameID (int): 64-bit game/app identifier
        statsCrc (int): CRC of current stats schema
        schemaLocalVersion (int): Local schema version (-1 if none)
    """

    def __init__(self, client_obj, data: bytes | None = None, version: int | None = None):
        self.client_obj = client_obj
        self.version = version or 1

        # Initialize fields with defaults
        self.gameID = 0
        self.statsCrc = 0
        self.schemaLocalVersion = -1

        if data:
            self.deserialize(data)

    def deserialize(self, data: bytes):
        """
        Deserialize binary data into message fields.

        Binary format (little-endian, 16 bytes total):
        - gameID: 8 bytes (uint64)
        - statsCrc: 4 bytes (uint32)
        - schemaLocalVersion: 4 bytes (int32, signed)
        """
        if len(data) < 16:
            raise ValueError("Insufficient data for ClientGetUserStats")

        # schemaLocalVersion is signed (uses -1 for "no local version")
        self.gameID, self.statsCrc, self.schemaLocalVersion = struct.unpack_from('<QIi', data, 0)

        log.debug(f"Parsed GetUserStats: gameID={self.gameID}, crc={self.statsCrc}, "
                 f"version={self.schemaLocalVersion}")
    
    def to_clientmsg(self):
        """Build CMResponse for sending to client"""
        from steam3.cm_packet_utils import CMResponse

        packet = CMResponse(EMsg.ClientGetUserStats, self.client_obj)

        # Pack the data (16 bytes)
        packet.data = struct.pack('<QIi',
                                 self.gameID,
                                 self.statsCrc,
                                 self.schemaLocalVersion)
        packet.length = len(packet.data)

        return packet

    def to_protobuf(self):
        """Return protobuf message if available"""
        raise NotImplementedError("Protobuf version not implemented for GetUserStats")

    def __repr__(self):
        return (f"MSGClientGetUserStats(gameID={self.gameID}, statsCrc={self.statsCrc}, "
               f"schemaLocalVersion={self.schemaLocalVersion})")

    def __str__(self):
        return self.__repr__()