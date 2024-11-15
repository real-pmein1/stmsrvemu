import struct
import socket

from steam3.utilities import reverse_bytes


class ClientAnonLogOn_Deprecated:
    def __init__(self, data):
        self.data = data
        self.parse()

    def parse(self):
        offset = 0

        # Protocol Version (4 bytes)
        self.protocol_version, = struct.unpack_from('<I', self.data, offset)
        offset += 4

        # Obfuscated IP (4 bytes)
        self.obfuscated_ip, = struct.unpack_from('<I', self.data, offset)
        self.obfuscated_ip = socket.inet_ntoa(int.to_bytes(reverse_bytes(self.obfuscated_ip ^ 0xBAADF00D), length = 4, byteorder = "little"))
        offset += 4

        # Public IP (4 bytes)
        self.public_ip, = struct.unpack_from('<I', self.data, offset)
        offset += 4

        # Steam GlobalID (8 bytes)
        self.steam_globalID, = struct.unpack_from('<Q', self.data, offset)
        offset += 8

        # Unknown1 (4 bytes)
        self.unknown1, = struct.unpack_from('<I', self.data, offset)
        offset += 4

        # Unknown2 (4 bytes)
        self.unknown2, = struct.unpack_from('<I', self.data, offset)
        offset += 4

        # Unknown3 (2 bytes)
        self.unknown3, = struct.unpack_from('<H', self.data, offset)
        offset += 2

        # Language (null-terminated string)
        language_end = self.data.find(b'\x00', offset)
        self.language = self.data[offset:language_end].decode('utf-8')
        offset = language_end + 1  # Skip the null terminator

        # SteamUI Version (4 bytes)
        self.steamui_version, = struct.unpack_from('<I', self.data, offset)
        offset += 4  # Prepare offset for any further fields if necessary

    def __str__(self):
        return str({
                "protocol_version":self.protocol_version,
                "obfuscated_ip":   socket.inet_ntoa(struct.pack('>I', self.obfuscated_ip)),
                "public_ip":       socket.inet_ntoa(struct.pack('>I', self.public_ip)),
                "steam_globalID":  self.steam_globalID,
                "unknown1":        self.unknown1,
                "unknown2":        self.unknown2,
                "unknown3":        self.unknown3,
                "language":        self.language,
                "steamui_version": self.steamui_version,
        })