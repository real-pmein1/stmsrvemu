import struct
from io import BytesIO

class MsgClientGameConnectTokens:
    def __init__(self):
        self.m_cubGameConnectToken = 0  # Size of each game connect token
        self.m_cGameConnectTokens = 0   # Number of game connect tokens
        self.tokens = []                # List to store parsed tokens

    def deserialize(self, buffer: bytes):
        """
        Parses the byte buffer to extract MsgClientGameConnectTokens fields.
        """
        stream = BytesIO(buffer)

        # Read m_cubGameConnectToken (4 bytes, int32)
        self.m_cubGameConnectToken = struct.unpack('<I', stream.read(4))[0]

        # Read m_cGameConnectTokens (4 bytes, int32)
        self.m_cGameConnectTokens = struct.unpack('<I', stream.read(4))[0]

        # Remove any tokens that are marked as used
        self.tokens = [token for token in self.tokens if not token['used']]

        # Parse each new token
        for i in range(self.m_cGameConnectTokens):
            # Read the token based on the size (m_cubGameConnectToken)
            token_data = stream.read(self.m_cubGameConnectToken)
            token = {'data': token_data, 'used': False}  # Store token data
            self.tokens.append(token)

        return self

    def print_tokens(self):
        """
        Helper function to print the tokens for debugging purposes.
        """
        for idx, token in enumerate(self.tokens):
            print(f"Token {idx + 1}: {token['data'].hex()} (Used: {token['used']})")


# Example buffer (replace this with actual data)
# Buffer format:
#   m_cubGameConnectToken (4 bytes), m_cGameConnectTokens (4 bytes), followed by token data
"""example_buffer = (
    struct.pack('<I', 16) +   # m_cubGameConnectToken (16 bytes per token)
    struct.pack('<I', 2) +    # m_cGameConnectTokens (2 tokens)
    b'\x00' * 16 +            # Token 1 data (16 bytes)
    b'\x01' * 16              # Token 2 data (16 bytes)
)"""
packet = b'\x0b\x03\x00\x00$\x02\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xef\xc4\xa0\x9b\x01\x01\x00\x10\x01\x00v/\x00\x14\x00\x00\x00\x01\x00\x00\x00\x91oAj7U\x8c&\xc4\xa0\x9b\x01\x01\x00\x10\x01\x94\xad\xbaH'


packet = packet[36:]
# Deserialize the example buffer
game_connect_tokens = MsgClientGameConnectTokens()
game_connect_tokens.deserialize(packet)

# Output the parsed data
print(f"Token Size: {game_connect_tokens.m_cubGameConnectToken}")
print(f"Number of Tokens: {game_connect_tokens.m_cGameConnectTokens}")
game_connect_tokens.print_tokens()