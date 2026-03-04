import struct

class MsgClientStat2Detail:
    """
    Represents a single stat detail from the client.

    Fields:
      - m_bNotNullFlags: 1 byte flag.
      - m_eClientStat: 2 bytes (uint16).
      - m_llValue: 8 bytes (int64).
      - m_nTimeOfDay: 4 bytes (uint32).
      - m_nCellID: (uint32) ? present only if flag bit 0x01 is set.
      - m_nDepotID: (uint32) ? present only if flag bit 0x01 is set.
      - m_nAppID: (uint32) ? present if flag bit 0x04 is set.
    """
    def __init__(self):
        self.m_bNotNullFlags = 0
        self.m_eClientStat = 0
        self.m_llValue = 0
        self.m_nTimeOfDay = 0
        self.m_nCellID = None   # Only present if (flags & 0x01) is true.
        self.m_nDepotID = None  # Only present if (flags & 0x01) is true.
        self.m_nAppID = None    # Only present if (flags & 0x04) is true.

    def __repr__(self):
        return (f"MsgClientStat2Detail\nflags=0x{self.m_bNotNullFlags:02X}\n"
                f"eClientStat={self.m_eClientStat}\nllValue={self.m_llValue}\n"
                f"nTimeOfDay={self.m_nTimeOfDay}\nnCellID={self.m_nCellID}\n"
                f"nDepotID={self.m_nDepotID}\nnAppID={self.m_nAppID}")

class MsgClientStat2:
    """
    Represents the entire clientstat2 message.

    Fields:
      - m_cStats: int32 ? the number of stat detail entries.
      - details: a list of MsgClientStat2Detail objects.
    """
    def __init__(self):
        self.m_cStats = 0
        self.details = []

    @classmethod
    def parse(cls, data: bytes):
        """
        Parse a bytes object containing a MsgClientStat2 packet.

        Raises:
          ValueError if the data is too short.
        """
        offset = 0
        if len(data) < 4:
            raise ValueError("Data too short for MsgClientStat2 header.")

        # Read m_cStats (int32, little-endian)
        m_cStats = int.from_bytes(data[offset:offset+4], byteorder='little', signed=True)
        offset += 4

        result = cls()
        result.m_cStats = m_cStats

        for i in range(m_cStats):
            detail = MsgClientStat2Detail()
            # Minimum size for the fixed part is 1+2+8+4 = 15 bytes.
            if len(data) < offset + 15:
                raise ValueError(f"Not enough data for stat detail #{i+1}.")

            # m_bNotNullFlags: 1 byte
            detail.m_bNotNullFlags = data[offset]
            offset += 1
            # m_eClientStat: 2 bytes, little-endian unsigned short.
            detail.m_eClientStat = int.from_bytes(data[offset:offset+2], byteorder='little')
            offset += 2
            # m_llValue: 8 bytes, little-endian signed 64-bit integer.
            detail.m_llValue = int.from_bytes(data[offset:offset+8], byteorder='little', signed=True)
            offset += 8
            # m_nTimeOfDay: 4 bytes, little-endian unsigned int.
            detail.m_nTimeOfDay = int.from_bytes(data[offset:offset+4], byteorder='little')
            offset += 4

            # Conditionally parse extra fields based on m_bNotNullFlags.
            if detail.m_bNotNullFlags & 0x01:
                # m_nCellID is present.
                if len(data) < offset + 4:
                    raise ValueError(f"Not enough data for m_nCellID in stat #{i+1}.")
                detail.m_nCellID = int.from_bytes(data[offset:offset+4], byteorder='little')
                offset += 4
                # m_nDepotID is present.
                if len(data) < offset + 4:
                    raise ValueError(f"Not enough data for m_nDepotID in stat #{i+1}.")
                detail.m_nDepotID = int.from_bytes(data[offset:offset+4], byteorder='little')
                offset += 4
                # If flag bit 0x04 is also set, m_nAppID is present.
                if detail.m_bNotNullFlags & 0x04:
                    if len(data) < offset + 4:
                        raise ValueError(f"Not enough data for m_nAppID in stat #{i+1}.")
                    detail.m_nAppID = int.from_bytes(data[offset:offset+4], byteorder='little')
                    offset += 4
            else:
                # If bit 0x01 is not set, but bit 0x04 is set then m_nAppID is present.
                if detail.m_bNotNullFlags & 0x04:
                    if len(data) < offset + 4:
                        raise ValueError(f"Not enough data for m_nAppID in stat #{i+1} (flag 0x04 only).")
                    detail.m_nAppID = int.from_bytes(data[offset:offset+4], byteorder='little')
                    offset += 4

            result.details.append(detail)
        return result

# Example usage:
"""if __name__ == "__main__":
    try:
        parsed = MsgClientStat2.parse(b'\x01\x00\x00\x00\x04\x04\x00}\x86\xc1\x15\x00\x00\x00\x00\xbd\x0e{gP\x00\x00\x00')
        print("Parsed packet:")
        print(f"m_cStats: {parsed.m_cStats}")
        for d in parsed.details:
            print(d)
    except Exception as e:
        print(f"Error parsing packet: {e}")"""
