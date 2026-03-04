import struct

class MsgClientUFSUploadFileRequest:

    def __init__(self, data: bytes = None):
        self.appId = 0
        self.size = 0
        self.rawSize = 0
        self.sha = b'\x00' * 20
        self.time = 0
        self.filename = ''
        if data is not None:
            self.deserialize(data)

    def deserialize(self, data: bytes):
        """
        Parse the given byte buffer:
          1) appId      ? 4-byte little-endian uint32
          2) size       ? 4-byte little-endian uint32
          3) rawSize    ? 4-byte little-endian uint32
          4) sha        ? next 20 bytes
          5) time       ? 8-byte little-endian uint64
          6) filename   ? null-terminated UTF-8 string
        """
        offset = 0

        self.appId   = struct.unpack_from('<I', data, offset)[0]
        offset += 4

        self.size    = struct.unpack_from('<I', data, offset)[0]
        offset += 4

        self.rawSize = struct.unpack_from('<I', data, offset)[0]
        offset += 4

        self.sha     = struct.unpack_from('<20s', data, offset)[0]
        offset += 20

        self.time    = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        # read null-terminated filename
        end = data.find(b'\x00', offset)
        if end == -1:
            raise ValueError("Filename string not terminated")
        self.filename = data[offset:end].decode('utf-8', errors='replace')
        # offset = end + 1  # not needed unless you care about trailing bytes

    def serialize(self) -> bytes:
        """
        Build a byte buffer in the same order:
          appId, size, rawSize, sha, time, filename + '\\x00'
        """
        parts = []
        parts.append(struct.pack('<I', self.appId))
        parts.append(struct.pack('<I', self.size))
        parts.append(struct.pack('<I', self.rawSize))

        sha = self.sha
        if len(sha) != 20:
            sha = sha.ljust(20, b'\x00')
        parts.append(sha)

        parts.append(struct.pack('<Q', self.time))
        parts.append(self.filename.encode('utf-8') + b'\x00')

        return b''.join(parts)

    def __str__(self):
        return (
            f"{self.__class__.__name__}("
            f"appId={self.appId}, "
            f"size={self.size}, "
            f"rawSize={self.rawSize}, "
            f"sha={self.sha.hex()}, "
            f"time={self.time}, "
            f"filename='{self.filename}'"
            f")"
        )
