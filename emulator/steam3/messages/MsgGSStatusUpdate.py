import struct
from io import BytesIO


class MsgGSStatusUpdate:
    def __init__(self):
        self.players = 0
        self.max_players = 0
        self.bot_players = 0
        self.server_name = ''
        self.map_name = ''

    def parse(self, byte_buffer):
        stream = BytesIO(byte_buffer)

        # Read number of players (int8)
        self.players = struct.unpack('<I', stream.read(4))[0]

        # Read maximum number of players (int8)
        self.max_players = struct.unpack('<I', stream.read(4))[0]

        # Read number of bot players (int8)
        self.bot_players = struct.unpack('<I', stream.read(4))[0]
        self.unknown = struct.unpack('<I', stream.read(4))[0]
        # Read the server name (null-terminated string)
        self.server_name = self.read_null_terminated_string(stream)

        # Read the map name (null-terminated string)
        self.map_name = self.read_null_terminated_string(stream)

        # Output parsed values
        print(f"Players: {self.players}")
        print(f"Max Players: {self.max_players}")
        print(f"Bot Players: {self.bot_players}")
        print(f"Server Name: {self.server_name}")
        print(f"Map Name: {self.map_name}")
        print(f"Unknown Variable: {self.unknown}")

        # Check for any extra bytes in the stream
        remaining_bytes = stream.read()
        if remaining_bytes:
            print(f"Extra bytes: {remaining_bytes.hex()}")

    @staticmethod
    def read_null_terminated_string(stream):
        string_bytes = bytearray()
        while True:
            char = stream.read(1)
            if char == b'\x00':
                break
            string_bytes.extend(char)
        return string_bytes.decode('utf-8')