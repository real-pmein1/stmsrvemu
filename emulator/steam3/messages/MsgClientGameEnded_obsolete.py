import struct
from io import BytesIO

from steam3.Types.Objects.PreProtoBuf.gameConnectToken import GameConnectToken


class MsgClientGameEnded_obsolete:
    """
    Message sent by the client when ending/disconnecting from a game server.
    EMsg: 721 (ClientGameEnded_obsolete)

    Packet structure (after ClientMsgHdr_t header):
        - gameServerSteamID: uint64 (8 bytes) - Steam ID of the game server
        - gameServerIP: uint32 (4 bytes) - IP address of the game server
        - gameServerPort: uint32 (4 bytes) - Port of the game server
        - queryPort: uint16 (2 bytes) - Query port of the game server
        - secure: uint16 (2 bytes) - Whether the server is VAC secured
        - tokenLength: uint32 (4 bytes) - Length of the auth token
        - token: bytes[tokenLength] - The game connect token/auth ticket
    """

    def __init__(self):
        self.game_server_steam_id = 0
        self.game_server_ip = 0
        self.game_server_port = 0
        self.query_port = 0
        self.secure = 0
        self.token_length = 0
        self.token = None
        self.game_connect_token = None
        self.extra_bytes = None

    def deserialize(self, byte_buffer):
        """
        Parses the byte buffer and populates the class attributes.

        Args:
            byte_buffer: Raw bytes from the packet data (after header)
        """
        stream = BytesIO(byte_buffer)

        # Read gameServerSteamID (uint64, 8 bytes)
        self.game_server_steam_id = struct.unpack('<Q', stream.read(8))[0]

        # Read gameServerIP (uint32, 4 bytes)
        self.game_server_ip = struct.unpack('<I', stream.read(4))[0]

        # Read gameServerPort (uint32, 4 bytes)
        self.game_server_port = struct.unpack('<I', stream.read(4))[0]

        # Read queryPort (uint16, 2 bytes)
        self.query_port = struct.unpack('<H', stream.read(2))[0]

        # Read secure flag (uint16, 2 bytes)
        self.secure = struct.unpack('<H', stream.read(2))[0]

        # Read tokenLength (uint32, 4 bytes)
        self.token_length = struct.unpack('<I', stream.read(4))[0]

        # Read token data
        if self.token_length > 0:
            self.token = stream.read(self.token_length)

            # Try to parse as GameConnectToken if size matches
            if self.token_length == GameConnectToken.SIZE:
                try:
                    game_connect_token_obj = GameConnectToken()
                    self.game_connect_token = game_connect_token_obj.deserialize(self.token)
                except Exception:
                    self.game_connect_token = None

        # Store any remaining bytes
        self.extra_bytes = stream.read()

        return self

    def ip_to_string(self):
        """Converts the IP integer to dotted-quad format."""
        return f'{self.game_server_ip & 0xFF}.{(self.game_server_ip >> 8) & 0xFF}.{(self.game_server_ip >> 16) & 0xFF}.{(self.game_server_ip >> 24) & 0xFF}'

    def __str__(self):
        """Returns a string representation of the parsed data."""
        extra_bytes_str = self.extra_bytes.hex() if self.extra_bytes else "None"
        token_str = self.token.hex() if self.token else "None"
        return (
            f"MsgClientGameEnded_obsolete(\n"
            f"  Game Server Steam ID: {self.game_server_steam_id}\n"
            f"  Game Server IP: {self.ip_to_string()} ({self.game_server_ip})\n"
            f"  Game Server Port: {self.game_server_port}\n"
            f"  Query Port: {self.query_port}\n"
            f"  Secure: {self.secure}\n"
            f"  Token Length: {self.token_length}\n"
            f"  Token: {token_str[:64]}{'...' if self.token and len(token_str) > 64 else ''}\n"
            f"  Game Connect Token: {self.game_connect_token}\n"
            f"  Extra Bytes: {extra_bytes_str}\n"
            f")"
        )
