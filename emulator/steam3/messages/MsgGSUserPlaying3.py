import struct
from io import BytesIO

from steam3.Types.Objects.PreProtoBuf.gameConnectToken import GameConnectToken


class MsgGSUserPlaying3:
    def __init__(self):
        self.steam_id = 0
        self.public_ip = 0
        self.game_connect_token_size = 0
        self.game_connect_token = None
        self.extra_bytes = None  # Store any extra bytes for representation

    def parse(self, byte_buffer):
        """
        Parses the byte buffer and populates the class attributes.
        """
        stream = BytesIO(byte_buffer)

        # Read and unpack the Steam ID (uint64)
        self.steam_id = struct.unpack('<Q', stream.read(8))[0]

        # Read and unpack the Public IP (uint32), bytes are reversed
        self.public_ip = struct.unpack('<I', stream.read(4))[0]

        # Read and unpack the Game Connect Token size (uint32)
        self.game_connect_token_size = struct.unpack('<I', stream.read(4))[0]

        # Read the Game Connect Token based on the size
        game_connect_token = stream.read(self.game_connect_token_size)

        # Assuming GameConnectToken class has a deserialize method
        game_connect_token_class = GameConnectToken()
        self.game_connect_token = game_connect_token_class.deserialize(game_connect_token)

        # Check for any extra bytes in the stream
        self.extra_bytes = stream.read()

    def __str__(self):
        """
        Returns a string representation of the parsed data.
        """
        extra_bytes_str = self.extra_bytes.hex() if self.extra_bytes else "None"
        return (
            f"MsgGSUserPlaying3(\n"
            f"  Steam ID: {self.steam_id}\n"
            f"  Public IP: {self.int_to_ip(self.reverse_ip_bytes(self.public_ip))}\n"
            f"  Game Connect Token Size: {self.game_connect_token_size}\n"
            f"  Game Connect Token: {self.game_connect_token}\n"
            f"  Extra Bytes: {extra_bytes_str}\n"
            f")"
        )

    @staticmethod
    def int_to_ip(ip_int):
        """
        Converts an integer IP address to dotted format.
        """
        return f'{ip_int & 0xFF}.{(ip_int >> 8) & 0xFF}.{(ip_int >> 16) & 0xFF}.{(ip_int >> 24) & 0xFF}'

    @staticmethod
    def reverse_ip_bytes(ip_int):
        """
        Reverses the byte order of the IP integer (little-endian to big-endian).
        """
        return struct.unpack('>I', struct.pack('<I', ip_int))[0]