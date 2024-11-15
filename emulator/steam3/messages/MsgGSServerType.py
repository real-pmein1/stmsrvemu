import struct
from io import BytesIO

class MsgGSServerType:
    def __init__(self):
        self.m_unAppIdServed = 0
        self.m_unFlags = 0
        self.m_unGamePort = 0
        self.m_unGameIP = 0
        self.game_dir = ''
        self.version = ''
        self.usQueryPort = 0

    def parse(self, byte_buffer):
        """Parses the GameServer settings from the provided byte buffer."""
        stream = BytesIO(byte_buffer)

        try:
            # Read m_unAppIdServed (uint32)
            self.m_unAppIdServed = struct.unpack('<I', stream.read(4))[0]

            # Read m_unFlags (uint32)
            self.m_unFlags = struct.unpack('<I', stream.read(4))[0]

            # Read m_unGamePort (uint16)
            self.m_unGamePort = struct.unpack('<H', stream.read(2))[0]

            # Read m_unGameIP (uint32)
            self.m_unGameIP = struct.unpack('<I', stream.read(4))[0]

            # Read Game Directory (null-terminated string)
            self.game_dir = self.read_null_terminated_string(stream)

            # Read Version (null-terminated string)
            self.version = self.read_null_terminated_string(stream)

            # Read usQueryPort (uint16)  #seems to be in 2009 clients but not 2006
            self.usQueryPort = struct.unpack('<H', stream.read(2))[0]

        except Exception as e:
            print(f"gsServerType: {e}")
            pass

        # Check if there are extra bytes
        remaining_bytes = stream.read()
        if remaining_bytes:
            print(f"Extra bytes in buffer: {remaining_bytes.hex()}")

        return self

    @staticmethod
    def read_null_terminated_string(stream):
        """Reads a null-terminated string from the stream."""
        string_data = b""
        while True:
            char = stream.read(1)
            if char == b'\x00' or char == b'':  # Null byte or end of stream
                break
            string_data += char
        return string_data.decode('utf-8')

    def __repr__(self):
        return (f"MsgGSServerType(AppIdServed={self.m_unAppIdServed}, Flags={self.m_unFlags}, "
                f"GamePort={self.m_unGamePort}, GameIP={self.m_unGameIP}, "
                f"GameDir={self.game_dir}, Version={self.version}, QueryPort={self.usQueryPort})")


"""# Example usage:
packet_data = b'\x8c\x03\x00\x00\x02\x10\xe5t\x1d\x00@\x01\t\x012\x02\n\x00\x00\x00\x06\x00\x00\x00\n\x00\x00\t\x87icstrike\x001.1.2.5\x00'



parser = MsgGSServerType()
parser.parse(packet_data[16:])

# Output the parsed data
print(parser)"""