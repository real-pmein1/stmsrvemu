from __future__ import annotations
import struct
import logging
from io import BytesIO

from steam3.Types.steamid import SteamID
from steam3.Types.emsg import EMsg

log = logging.getLogger("MSGClientStatsUpdated")


class MSGClientStatsUpdated:
    """
    Notification sent to game servers when a player's stats are updated.
    
    Fields:
        steamID (int): Steam ID of the player whose stats were updated
        gameID (int): 64-bit game/app identifier
        statsCrc (int): New CRC of the updated stats
        updatedStats (dict): Stats that were updated (stat_id -> new_value)
    """
    
    def __init__(self, client_obj, data: bytes | None = None, version: int | None = None):
        self.client_obj = client_obj
        self.version = version or 1
        
        # Initialize fields with defaults
        self.steamID = 0
        self.gameID = 0
        self.statsCrc = 0
        self.updatedStats = {}  # stat_id -> new_value
        
        if data:
            self.deserialize(data)
    
    def deserialize(self, data: bytes):
        """
        Deserialize binary data into message fields.
        
        Binary format (little-endian):
        - steamID: 8 bytes (uint64)
        - gameID: 8 bytes (uint64)
        - statsCrc: 4 bytes (uint32)
        - updatedStatsCount: 4 bytes (uint32)
        - For each updated stat:
          - statID: 2 bytes (uint16)
          - statValue: 4 bytes (uint32)
        """
        if len(data) < 24:
            raise ValueError("Insufficient data for ClientStatsUpdated")
        
        offset = 0
        
        # Parse steam ID, game ID, stats CRC, and updated stats count
        self.steamID, self.gameID, self.statsCrc, updatedCount = struct.unpack_from('<QQII', data, offset)
        offset += 24
        
        # Parse updated stats
        self.updatedStats = {}
        for _ in range(updatedCount):
            if offset + 6 > len(data):
                raise ValueError("Insufficient data for updated stat entries")
            
            statID, statValue = struct.unpack_from('<HI', data, offset)
            self.updatedStats[statID] = statValue
            offset += 6
        
        log.debug(f"Parsed StatsUpdated: steamID={self.steamID}, gameID={self.gameID}, "
                 f"crc={self.statsCrc}, updatedCount={len(self.updatedStats)}")
    
    def to_clientmsg(self):
        """Build CMResponse for sending to client (game server)"""
        from steam3.cm_packet_utils import CMResponse
        
        packet = CMResponse(EMsg.ClientStatsUpdated, self.client_obj)
        
        # Build data buffer
        buffer = BytesIO()
        
        # Write steam ID, game ID, stats CRC, and updated stats count
        buffer.write(struct.pack('<QQII', 
                                self.steamID, 
                                self.gameID, 
                                self.statsCrc, 
                                len(self.updatedStats)))
        
        # Write updated stats in sorted order
        for statID in sorted(self.updatedStats.keys()):
            statValue = self.updatedStats[statID]
            buffer.write(struct.pack('<HI', statID, statValue))
        
        packet.data = buffer.getvalue()
        packet.length = len(packet.data)
        
        return packet
    
    def to_protobuf(self):
        """Return protobuf message if available"""
        raise NotImplementedError("Protobuf version not implemented for StatsUpdated")
    
    def __repr__(self):
        return (f"MSGClientStatsUpdated(steamID={self.steamID}, gameID={self.gameID}, "
               f"crc={self.statsCrc}, updatedCount={len(self.updatedStats)})")
    
    def __str__(self):
        return self.__repr__()