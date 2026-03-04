from __future__ import annotations
import struct
import logging
from io import BytesIO

from steam3.Types.emsg import EMsg
from steam3.Types.steam_types import EResult

log = logging.getLogger("MSGClientGetUserStatsResponse")


class MSGClientGetUserStatsResponse:
    """
    Server response to client GetUserStats request containing user stats and achievements.
    
    Binary format (matches MsgClientGetUserStatsResponse_t):
        - m_ulGameID: 8 bytes (uint64)
        - m_eResult: 4 bytes (EResult)
        - m_bSchemaAttached: 1 byte (bool)
        - m_cStats: 4 bytes (int32)
        - m_crcStats: 4 bytes (uint32)
        - Schema data (if attached)
        - Stat entries: 16-bit statID + 32-bit data pairs
    
    Fields:
        gameID (int): 64-bit game/app identifier
        result (EResult): Result of the operation
        schema_attached (bool): Whether schema data is included
        stats_count (int): Number of stat entries
        crc_stats (int): CRC32 checksum of stats
        schema_data (bytes): Raw binary schema data
        stats_data (dict): Dictionary of stat_id -> value pairs
    """
    
    def __init__(self, client_obj, data: bytes | None = None, version: int | None = None):
        self.client_obj = client_obj
        self.version = version or 1
        
        # Initialize fields with defaults matching MsgClientGetUserStatsResponse_t structure
        self.gameID = 0
        self.result = EResult.OK
        self.schema_attached = False
        self.stats_count = 0
        self.crc_stats = 0
        self.schema_data = b""
        self.stats_data = {}  # stat_id -> value mapping
        
        if data:
            self.deserialize(data)
    
    def deserialize(self, data: bytes):
        """
        Deserialize binary data into message fields matching MsgClientGetUserStatsResponse_t.
        
        Binary format (little-endian):
        - m_ulGameID: 8 bytes (uint64)
        - m_eResult: 4 bytes (EResult)
        - m_bSchemaAttached: 1 byte (bool)
        - m_cStats: 4 bytes (int32)
        - m_crcStats: 4 bytes (uint32)
        - Schema data (if attached)
        - Stat entries: 16-bit statID + 32-bit data pairs
        """
        if len(data) < 21:  # 8 + 4 + 1 + 4 + 4 = 21 bytes minimum
            raise ValueError("Insufficient data for ClientGetUserStatsResponse")
        
        # Unpack fixed header
        self.gameID, result_value, schema_attached_byte, self.stats_count, self.crc_stats = struct.unpack_from('<QIBII', data, 0)
        self.result = EResult(result_value)
        self.schema_attached = bool(schema_attached_byte)
        
        offset = 21
        
        # Read schema data if attached
        if self.schema_attached and offset < len(data):
            # Schema data continues until stats begin
            # We need to calculate where stats start based on stats_count
            stats_data_size = self.stats_count * 6  # 2 bytes statID + 4 bytes data per stat
            schema_end = len(data) - stats_data_size
            self.schema_data = data[offset:schema_end]
            offset = schema_end
        
        # Read stat entries (16-bit statID + 32-bit data pairs)
        self.stats_data = {}
        for i in range(self.stats_count):
            if offset + 6 <= len(data):  # 2 + 4 bytes
                stat_id, stat_value = struct.unpack_from('<HI', data, offset)
                self.stats_data[stat_id] = stat_value
                offset += 6
        
        log.debug(f"Parsed GetUserStatsResponse: gameID={self.gameID}, result={self.result}, "
                 f"schema_attached={self.schema_attached}, stats_count={self.stats_count}")
    
    def to_clientmsg(self):
        """Build CMResponse for sending to client matching MsgClientGetUserStatsResponse_t structure"""
        from steam3.cm_packet_utils import CMResponse
        
        packet = CMResponse(EMsg.ClientGetUserStatsResponse, self.client_obj)
        
        # Build data buffer
        buffer = BytesIO()
        
        # Write fixed header matching MsgClientGetUserStatsResponse_t structure
        # m_ulGameID (8 bytes), m_eResult (4 bytes), m_bSchemaAttached (1 byte), 
        # m_cStats (4 bytes), m_crcStats (4 bytes)
        buffer.write(struct.pack('<QIBII', 
                                self.gameID,
                                int(self.result),
                                1 if self.schema_attached else 0,
                                self.stats_count,
                                self.crc_stats))
        
        # Attach raw schema data if present (don't parse it - just append as binary)
        if self.schema_attached and self.schema_data:
            buffer.write(self.schema_data)
        
        # Write stat entries as 16-bit statID + 32-bit data pairs
        # Following the format from gamestats_parser.py key/value approach
        for stat_id, stat_value in self.stats_data.items():
            # Ensure stat_id fits in 16-bit unsigned integer range (0-65535)
            safe_stat_id = int(stat_id) & 0xFFFF
            safe_stat_value = int(stat_value) & 0xFFFFFFFF  # Ensure 32-bit value
            buffer.write(struct.pack('<HI', safe_stat_id, safe_stat_value))
        
        packet.data = buffer.getvalue()
        packet.length = len(packet.data)
        
        log.debug(f"Built GetUserStatsResponse packet: {len(packet.data)} bytes, "
                 f"gameID={self.gameID}, result={self.result}, schema_attached={self.schema_attached}, "
                 f"stats_count={self.stats_count}")
        
        return packet
    
    def to_protobuf(self):
        """Return protobuf message if available"""
        raise NotImplementedError("Protobuf version not implemented for GetUserStatsResponse")
    
    def __repr__(self):
        return (f"MSGClientGetUserStatsResponse(gameID={self.gameID}, result={self.result}, "
               f"schema_attached={self.schema_attached}, stats_count={self.stats_count}, "
               f"crc_stats={self.crc_stats})")
    
    def __str__(self):
        return self.__repr__()