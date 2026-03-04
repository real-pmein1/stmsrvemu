import struct
from dataclasses import dataclass, field
from typing import List
@dataclass
class MsgClientUserStatsResponse:
    eResult: int = 0
    ulGameID: int = 0
    bSchemaAttached: bool = False
    m_cStats: int = 0
    m_crcStats: int = 0
    stats: List[Stat] = field(default_factory=list)
    schema: bytes = b''  # Raw schema data if attached

    def deserialize(self, buffer: bytes):
        """
        Deserialize the binary buffer into the class instance.
        """
        # Initial offset
        offset = 0

        # eResult (4 bytes)
        self.eResult, = struct.unpack_from('<I', buffer, offset)
        offset += 4

        # ulGameID (8 bytes)
        self.ulGameID, = struct.unpack_from('<Q', buffer, offset)
        offset += 8

        # bSchemaAttached (1 byte)
        self.bSchemaAttached, = struct.unpack_from('<?', buffer, offset)
        offset += 1

        # Padding (3 bytes)
        offset += 3

        # m_cStats (4 bytes)
        self.m_cStats, = struct.unpack_from('<I', buffer, offset)
        offset += 4

        # m_crcStats (4 bytes)
        self.m_crcStats, = struct.unpack_from('<I', buffer, offset)
        offset += 4

        # If schema is attached, handle schema data
        if self.bSchemaAttached:
            # For demonstration, let's assume the schema length is provided
            # This is an assumption; actual implementation depends on the schema format
            schema_length, = struct.unpack_from('<I', buffer, offset)
            offset += 4
            self.schema = buffer[offset:offset + schema_length]
            offset += schema_length
            print(f"Schema attached with length: {schema_length} bytes.")

        # Deserialize each stat
        for _ in range(self.m_cStats):
            if offset + 6 > len(buffer):
                raise ValueError("Buffer too small for stat data.")

            # statID (2 bytes)
            statID, = struct.unpack_from('<h', buffer, offset)
            offset += 2

            # data (4 bytes)
            data, = struct.unpack_from('<i', buffer, offset)
            offset += 4

            # Placeholder for type; in reality, type should be retrieved from schema
            # Here, we'll set type to a default value or handle externally
            stat_type = 2  # Assuming int32; replace with actual type from schema

            stat = Stat(statID=statID, type=stat_type, data=data)
            self.stats.append(stat)

    def serialize(self) -> bytes:
        """
        Serialize the class instance into a binary buffer.
        """
        buffer = b''

        # eResult (4 bytes)
        buffer += struct.pack('<I', self.eResult)

        # ulGameID (8 bytes)
        buffer += struct.pack('<Q', self.ulGameID)

        # bSchemaAttached (1 byte)
        buffer += struct.pack('<?', self.bSchemaAttached)

        # Padding (3 bytes)
        buffer += b'\x00\x00\x00'

        # m_cStats (4 bytes)
        buffer += struct.pack('<I', self.m_cStats)

        # m_crcStats (4 bytes)
        buffer += struct.pack('<I', self.m_crcStats)

        # If schema is attached, include schema data
        if self.bSchemaAttached:
            # For demonstration, include schema length followed by schema data
            schema_length = len(self.schema)
            buffer += struct.pack('<I', schema_length)
            buffer += self.schema

        # Serialize each stat
        for stat in self.stats:
            # statID (2 bytes)
            buffer += struct.pack('<h', stat.statID)

            # data (4 bytes)
            if stat.type == 2:  # int32
                buffer += struct.pack('<i', stat.data)
            elif stat.type == 3:  # float
                buffer += struct.pack('<f', stat.data)
            elif stat.type == 1:  # string
                encoded_str = stat.data.encode('utf-8') + b'\x00'
                buffer += encoded_str.ljust(4, b'\x00')  # Pad to 4 bytes
            elif stat.type == 5:  # wstring
                encoded_str = stat.data.encode('utf-16le') + b'\x00\x00'
                buffer += encoded_str.ljust(4, b'\x00')  # Pad to 4 bytes
            elif stat.type == 6:  # color (3 bytes)
                color_parts = stat.data.split()
                color_bytes = struct.pack('<BBB', int(color_parts[0]), int(color_parts[1]), int(color_parts[2]))
                buffer += color_bytes.ljust(4, b'\x00')  # Pad to 4 bytes
            elif stat.type == 7:  # uint64
                buffer += struct.pack('<Q', stat.data)
            else:
                raise ValueError(f"Unsupported stat type: {stat.type}")

        return buffer
