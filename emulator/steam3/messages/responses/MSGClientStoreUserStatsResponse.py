from __future__ import annotations
import struct
import logging

from steam3.Types.emsg import EMsg
from steam3.Types.steam_types import EResult

log = logging.getLogger("MSGClientStoreUserStatsResponse")


class MSGClientStoreUserStatsResponse:
    """
    Server response to client StoreUserStats request indicating success/failure.

    Binary format (MsgClientStoreUserStatsResponse_t) - 16 bytes:
        - m_ulGameID: 8 bytes (uint64)
        - m_eResult: 4 bytes (EResult/int32)
        - m_crcStats: 4 bytes (uint32)
    Total: 16 bytes

    Note: Clients from 2009+ (e.g., Steam client ~2010) may support an extended 20-byte
    format with m_cFailedValidation count and failed stat entries. However, the 16-byte
    format is compatible with all client versions - newer clients simply ignore the
    missing failed validation data and clear their local pending stats unconditionally.

    Fields:
        gameID (int): 64-bit game/app identifier
        result (EResult): Result of the operation
        statsCrc (int): New CRC of the stats
    """

    def __init__(self, client_obj, data: bytes | None = None, version: int | None = None):
        self.client_obj = client_obj
        self.version = version or 1

        # Initialize fields with defaults
        self.gameID = 0
        self.result = EResult.OK
        self.statsCrc = 0

        if data:
            self.deserialize(data)

    def deserialize(self, data: bytes):
        """
        Deserialize binary data into message fields.

        Binary format (little-endian, 16 bytes):
        - gameID: 8 bytes (uint64)
        - result: 4 bytes (int32)
        - statsCrc: 4 bytes (uint32)
        """
        if len(data) < 16:
            raise ValueError("Insufficient data for ClientStoreUserStatsResponse")

        # Parse game ID, result, and stats CRC
        self.gameID, result_value, self.statsCrc = struct.unpack_from('<QII', data, 0)
        self.result = EResult(result_value)

        log.debug(f"Parsed StoreUserStatsResponse: gameID={self.gameID}, result={self.result}, "
                 f"crc={self.statsCrc}")
    
    def to_clientmsg(self):
        """Build CMResponse for sending to client"""
        from steam3.cm_packet_utils import CMResponse

        packet = CMResponse(EMsg.ClientStoreUserStatsResponse, self.client_obj)

        # 16-byte response format compatible with all client versions
        # Note: 2009+ clients may support extended format with failed validation stats,
        # but they handle the 16-byte format fine by clearing all pending stats locally.
        packet.data = struct.pack('<QII',
                                self.gameID,
                                int(self.result),
                                self.statsCrc)
        packet.length = len(packet.data)

        return packet

    def to_protobuf(self):
        """Return protobuf message if available"""
        raise NotImplementedError("Protobuf version not implemented for StoreUserStatsResponse")

    def __repr__(self):
        return (f"MSGClientStoreUserStatsResponse(gameID={self.gameID}, result={self.result}, "
               f"crc={self.statsCrc})")

    def __str__(self):
        return self.__repr__()