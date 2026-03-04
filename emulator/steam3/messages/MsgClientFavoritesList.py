import struct


class MsgClientFavoritesList:
    """
    Client favorites list message.
    EMsg: 786 (ClientFavoritesList)

    Decompiled parse order (per entry):
        uint32  unAppID
        uint32  unIP
        uint16  unPort
        uint32  unFlags
        uint32  RTime32LastPlayedOnServer

    Body:
        uint32 m_cFavorites
        followed by m_cFavorites entries.
    """

    COUNT_FORMAT = "<I"
    COUNT_SIZE = struct.calcsize(COUNT_FORMAT)

    # Match decompiled reads: u32, u32, u16, u32, u32
    ENTRY_FORMAT = "<IIHII"
    ENTRY_SIZE = struct.calcsize(ENTRY_FORMAT)

    def __init__(self):
        self.favorites = []

    def addFavorite(self, app_id: int, ip: int, port: int, flags: int = 0, last_played: int = 0):
        """
        Add a favorite entry.

        :param app_id: uint32 AppId_t
        :param ip: uint32 IPv4 as integer (whatever endian your protocol expects upstream)
        :param port: uint16 port
        :param flags: uint32
        :param last_played: uint32 (RTime32)
        """
        self.favorites.append({
            "app_id": int(app_id) & 0xFFFFFFFF,
            "ip": int(ip) & 0xFFFFFFFF,
            "port": int(port) & 0xFFFF,
            "flags": int(flags) & 0xFFFFFFFF,
            "last_played": int(last_played) & 0xFFFFFFFF,
        })

    def to_clientmsg(self) -> bytes:
        """
        Serialize this message body to raw bytes (clientmsg-style),
        matching the decompiled read order.

        Layout:
            uint32 count
            repeated entries: <IIHII
        """
        count = len(self.favorites)
        out = bytearray()
        out += struct.pack(self.COUNT_FORMAT, count)

        for fav in self.favorites:
            out += struct.pack(
                self.ENTRY_FORMAT,
                fav["app_id"] & 0xFFFFFFFF,
                fav["ip"] & 0xFFFFFFFF,
                fav["port"] & 0xFFFF,
                fav["flags"] & 0xFFFFFFFF,
                fav["last_played"] & 0xFFFFFFFF,
            )

        return bytes(out)

    def deserialize(self, buffer: bytes, offset: int = 0) -> int:
        """
        Parse body from buffer starting at offset.
        Returns new offset after reading the body.
        """
        if len(buffer) < offset + self.COUNT_SIZE:
            raise ValueError(
                f"Buffer too small for MsgClientFavoritesList header: need {self.COUNT_SIZE} bytes"
            )

        (count,) = struct.unpack_from(self.COUNT_FORMAT, buffer, offset)
        offset += self.COUNT_SIZE

        self.favorites = []
        for _ in range(count):
            if len(buffer) < offset + self.ENTRY_SIZE:
                raise ValueError(
                    f"Buffer too small for MsgClientFavoritesList entry: need {self.ENTRY_SIZE} bytes"
                )

            app_id, ip, port_u16, flags, last_played = struct.unpack_from(
                self.ENTRY_FORMAT, buffer, offset
            )
            self.favorites.append({
                "app_id": app_id,
                "ip": ip,
                "port": port_u16 & 0xFFFF,
                "flags": flags,
                "last_played": last_played,
            })
            offset += self.ENTRY_SIZE

        return offset

    def __repr__(self):
        return f"MsgClientFavoritesList(count={len(self.favorites)}, favorites={self.favorites})"

    def __str__(self):
        return str({
            "count": len(self.favorites),
            "favorites": self.favorites,
        })
