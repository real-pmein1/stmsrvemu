import struct
from datetime import datetime
from io import BytesIO

class GameConnectToken:
    def __init__(self, token = b'', steamGlobalId= 0, timestamp = None):
        self.token = token
        self.steamGlobalId = steamGlobalId
        self.timestamp = timestamp

    def serialize(self):
        # Using struct to pack ULONGLONG, ULONGLONG, DWORD corresponding to C++ types
        return struct.pack('<QQI', self.token, self.steamGlobalId, self.timestamp)

    def serialize_single_deprecated(self):
        # Using struct to pack ULONGLONG, ULONGLONG, DWORD corresponding to C++ types
        return struct.pack('<QQ', self.token, self.steamGlobalId)

    def deserialize(self, buffer):
        # Using struct to pack ULONGLONG, ULONGLONG, DWORD corresponding to C++ types
        self.token, self.steamGlobalId, timestamp = struct.unpack('<QQI', buffer)
        self.timestamp = datetime.utcfromtimestamp(timestamp).strftime('%m/%d/%Y %H:%M:%S')
        return self.token, self.steamGlobalId, self.timestamp

    def deserialize_single_deprecated(self, buffer):
        # Using struct to pack ULONGLONG, ULONGLONG, DWORD corresponding to C++ types
        self.token, self.steamGlobalId = struct.unpack('<QQ', buffer)
        return self.token, self.steamGlobalId

class MsgGSUserPlaying3:
    def __init__(self):
        self.steam_id = 0
        self.public_ip = 0
        self.game_connect_token_size = 0
        self.game_connect_token = None

    def parse(self, byte_buffer):
        stream = BytesIO(byte_buffer)

        # Read and unpack the Steam ID (uint64)
        self.steam_id = struct.unpack('<Q', stream.read(8))[0]

        # Read and unpack the Public IP (uint32), bytes are reversed, so we reverse it to correct order
        self.public_ip = struct.unpack('<I', stream.read(4))[0]

        # Read and unpack the Game Connect Token size (uint32)
        self.game_connect_token_size = struct.unpack('<I', stream.read(4))[0]

        # Read the Game Connect Token based on the size
        game_connect_token = stream.read(self.game_connect_token_size)

        game_connect_token_class = GameConnectToken()
        self.game_connect_token = game_connect_token_class.deserialize(game_connect_token)

        # Output parsed values
        print(f"Steam ID: {self.steam_id}")
        print(f"Public IP: {self.int_to_ip(self.reverse_ip_bytes(self.public_ip))}")
        print(f"Game Connect Token Size: {self.game_connect_token_size}")
        print(f"Game Connect Token: {self.game_connect_token}")

        # Check for any extra bytes in the stream
        remaining_bytes = stream.read()
        if remaining_bytes:
            print(f"Extra bytes: {remaining_bytes.hex()}")


    @staticmethod
    def int_to_ip(ip_int):
        return f'{ip_int & 0xFF}.{(ip_int >> 8) & 0xFF}.{(ip_int >> 16) & 0xFF}.{(ip_int >> 24) & 0xFF}'

    @staticmethod
    def reverse_ip_bytes(ip_int):
        # Reverse the byte order of the IP integer (little-endian to big-endian)
        return struct.unpack('>I', struct.pack('<I', ip_int))[0]

# Example usage
byte_data = b'\x89\x03\x00\x00\x00\x04\xb3v&\x00@\x01\xdc5l\x00\xd8z\x00\x00\x01\x00\x10\x01d\x00\x00\n\x14\x00\x00\x00N\x189\x12\xa2\xb5t?\x81TZ\x01\x01\x00\x10\x01\tQ\x91D'

parser = MsgGSUserPlaying3()
parser.parse(byte_data[16:])