import struct
from datetime import datetime
from io import BytesIO

class GameConnectToken:
    def __init__(self, token, steamGlobalId, timestamp=None):
        self.token = token
        self.steamGlobalId = steamGlobalId
        self.timestamp = timestamp

    def serialize(self):
        # Using struct to pack ULONGLONG, ULONGLONG, DWORD corresponding to C++ types
        return struct.pack('<QQI', self.token, self.steamGlobalId, self.timestamp)

    def serialize_single_deprecated(self):
        # Using struct to pack ULONGLONG, ULONGLONG, DWORD corresponding to C++ types
        return struct.pack('<QQ', self.token, self.steamGlobalId)


class MsgClientGameConnectTokens:
    def __init__(self):
        self.m_cubGameConnectToken = 0
        self.m_cGameConnectTokens = 0
        self.tokens = []

    def parse(self, buffer):
        stream = BytesIO(buffer)

        # Read m_cubGameConnectToken (4 bytes, int32)
        self.m_cubGameConnectToken = struct.unpack('<I', stream.read(4))[0]

        # Read m_cGameConnectTokens (4 bytes, int32)
        self.m_cGameConnectTokens = struct.unpack('<I', stream.read(4))[0]

        print(f"Token size: {self.m_cubGameConnectToken}")
        print(f"Number of Tokens: {self.m_cGameConnectTokens}")

        # Read and parse each token
        for i in range(self.m_cGameConnectTokens):
            # Reading 16 bytes for token and steamGlobalId
            token_data = stream.read(16)
            if len(token_data) != 16:
                raise ValueError(f"Expected 16 bytes for token and steamGlobalId but got {len(token_data)}")

            # Unpack token and steamGlobalId
            token, steamGlobalId = struct.unpack('<QQ', token_data)

            # Optionally read timestamp if present (4 bytes)
            if self.m_cubGameConnectToken > 16:
                timestamp_data = stream.read(4)
                if len(timestamp_data) != 4:
                    raise ValueError(f"Expected 4 bytes for timestamp but got {len(timestamp_data)}")
                timestamp = struct.unpack('<I', timestamp_data)[0]
                timestamp = datetime.utcfromtimestamp(timestamp).strftime('%m/%d/%Y %H:%M:%S')
            else:
                timestamp = None

            # Create GameConnectToken object
            game_connect_token = GameConnectToken(token, steamGlobalId, timestamp)
            self.tokens.append(game_connect_token)

            print(f"Parsed Token: {game_connect_token.token}, SteamGlobalId: {game_connect_token.steamGlobalId}, Timestamp: {game_connect_token.timestamp}")

        try:
            maximum_tokens = struct.unpack('<I', stream.read(4))[0]
            print(f"Maximum Tokens: {maximum_tokens}")
        except:
            pass
        # Check for extra bytes (if any)
        remaining_bytes = stream.read()
        if remaining_bytes:
            print(f"Extra bytes found: {remaining_bytes.hex()}")


# Example usage
"""packet = (
        b'\x08\x00\x00\x00'  # m_cubGameConnectToken (8 bytes)
        b'\x02\x00\x00\x00'  # m_cGameConnectTokens (2 tokens)
        b'\x01\x02\x03\x04'  # Token 1 (data part)
        b'\x04\x00\x00\x00'  # Token 1 (m_nSize)
        b'\x01\x00\x00\x00'  # Token 1 (m_nUsed)
        b'\x05\x06\x07\x08'  # Token 2 (data part)
        b'\x04\x00\x00\x00'  # Token 2 (m_nSize)
        b'\x02\x00\x00\x00'  # Token 2 (m_nUsed)
)"""


packet = b'\x0b\x03\x00\x00c\xe5\x00\x00\x01\x00\x10\x01\xb6\x06\x1c\x00\x14\x00\x00\x00\x01\x00\x00\x00\xb7E\x9d"\xc1\x11\xe6"c\xe5\x00\x00\x01\x00\x10\x01\xdd\xcd\xecC'

parser = MsgClientGameConnectTokens()
parser.parse(packet[16:])