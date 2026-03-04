# msg_client_get_lobby_list.py

import struct
from steam3.Types.Objects.LobbyTypes import LobbyFilter

from steam3.Types.community_types import LobbyFilterType, LobbyComparison

class MsgClientGetLobbyList:
    def __init__(self):
        # mirror your C++ defaults
        self.gameId = 0                          # ULONGLONG
        self.requestedLobbiesCount = -1          # DWORD (deprecated)
        self.filters = []                        # List[LobbyFilter]

    def _read_cstring(self, data: bytes, offset: int):
        """
        Reads a null-terminated ASCII string from data starting at offset.
        Returns (string, new_offset).
        """
        end = data.index(b'\x00', offset)
        s = data[offset:end].decode('ascii', errors='ignore')
        return s, end + 1

    def deserialize(self, byte_data: bytes):
        """
        Parses the MsgClientGetLobbyList message from its raw byte payload.
        """
        offset = 0
        try:
            # 1) gameId (uint64)
            self.gameId = struct.unpack_from("<Q", byte_data, offset)[0]
            offset += 8

            # 2) requestedLobbiesCount (uint32)
            self.requestedLobbiesCount = struct.unpack_from("<I", byte_data, offset)[0]
            offset += 4

            # 3) filtersCount (uint32)
            filters_count = struct.unpack_from("<I", byte_data, offset)[0]
            offset += 4

            # 4) loop over each LobbyFilter
            for _ in range(filters_count):
                # read key (cstring)
                key, offset = self._read_cstring(byte_data, offset)
                # read value (cstring)
                value, offset = self._read_cstring(byte_data, offset)
                # comparision (uint32 ? enum) - convert to signed int for negative enum values
                cmp_raw = struct.unpack_from("<I", byte_data, offset)[0]
                offset += 4
                # type (uint32 ? enum)
                type_raw = struct.unpack_from("<I", byte_data, offset)[0]
                offset += 4

                # Convert unsigned to signed for comparison enum (supports negative values like -2)
                if cmp_raw > 2147483647:  # If > max signed int32, convert to negative
                    cmp_signed = cmp_raw - 4294967296
                else:
                    cmp_signed = cmp_raw

                filt = LobbyFilter()
                filt.key = key
                filt.value = value
                filt.comparision = LobbyComparison(cmp_signed)
                filt.type = LobbyFilterType(type_raw)
                self.filters.append(filt)

        except (struct.error, ValueError) as e:
            raise ValueError(f"Failed to parse MsgClientGetLobbyList: {e}")

    def __str__(self):
        lines = [
            "MsgClientGetLobbyList(",
            f"  gameId: {self.gameId}",
            f"  requestedLobbiesCount: {self.requestedLobbiesCount}",
            "  filters:"
        ]
        if not self.filters:
            lines.append("    (none)")
        else:
            for f in self.filters:
                lines.append(
                    f"    - key={f.key!r}, value={f.value!r}, "
                    f"cmp={f.comparision.name}, type={f.type.name}"
                )
        lines.append(")")
        return "\n".join(lines)
