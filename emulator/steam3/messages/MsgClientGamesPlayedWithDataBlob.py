import struct


class GameInfo:
    def __init__(self):
        self.serverGlobalId = None
        self.gameId = None
        self.serverIp = None
        self.serverPort = None
        self.vacSecured = None
        self.processId = None
        self.token = None
        self.gameName = None
        self.gameDataBlob = None

    def deserialize(self, buffer, offset):
        """Deserialize a single GameInfo entry from the buffer."""
        self.serverGlobalId, self.gameId = struct.unpack_from('<QQ', buffer, offset)
        offset += 16  # 8 bytes each for serverGlobalId and gameId

        self.serverIp, = struct.unpack_from('>I', buffer, offset)  # Big-endian 32-bit int
        offset += 4

        self.serverPort, self.vacSecured = struct.unpack_from('<HH', buffer, offset)
        offset += 4  # 2 bytes each for serverPort and vacSecured

        self.processId, = struct.unpack_from('<I', buffer, offset)  # Little-endian 32-bit int
        offset += 4

        # Parse token
        token_len, = struct.unpack_from('<I', buffer, offset)
        offset += 4
        if token_len:
            self.token = buffer[offset:offset + token_len]
            offset += token_len

        # Parse game name (null-terminated string)
        null_terminator_index = buffer.find(b'\x00', offset)
        if null_terminator_index == -1:
            raise ValueError("Game name not null-terminated")
        self.gameName = buffer[offset:null_terminator_index].decode('utf-8')
        offset = null_terminator_index + 1  # Move past the null byte

        # Parse game data blob size
        blob_size, = struct.unpack_from('<I', buffer, offset)
        offset += 4
        if blob_size:
            self.gameDataBlob = buffer[offset:offset + blob_size]
            offset += blob_size

        return offset  # Return the updated offset

    def __str__(self):
        return (f"GameInfo(serverGlobalId={self.serverGlobalId}, gameId={self.gameId}, serverIp={self.serverIp}, "
                f"serverPort={self.serverPort}, vacSecured={self.vacSecured}, processId={self.processId}, "
                f"token={self.token}, gameName={self.gameName}, gameDataBlob={self.gameDataBlob})")


class MsgClientGamesPlayed_WithDataBlob:
    def __init__(self, buffer):
        self.buffer = buffer
        self.games_info = []
        if buffer:
            self.deserialize()

    def deserialize(self):
        """Deserialize all GameInfo entries from the buffer."""
        offset = 0

        # Read the count of game info entries (4 bytes, little-endian)
        game_info_count, = struct.unpack_from('<I', self.buffer, offset)
        offset += 4

        # Deserialize each GameInfo entry
        for _ in range(game_info_count):
            game_info = GameInfo()
            offset = game_info.deserialize(self.buffer, offset)
            self.games_info.append(game_info)

    def __str__(self):
        return "\n".join(str(game_info) for game_info in self.games_info)

# Example binary data
"""buffer = b'\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x006\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00hQ\x00\x00\x00\x00\x00\x00Team Fortress 2 Dedicated Server\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00@\x01\xb8\x01\x00\x00\x00\x00\x00\x00\xb4\x03\xa8\xc0\x87i\x01\x00\xf0\x01\x00\x00\x04\x00\x00\x00\x00\x00\x00\x00Team Fortress 2\x00\x00\x00\x00\x00'

# Deserialize the data
deserializer = MsgClientGamesPlayed_WithDataBlob(buffer)
deserializer.deserialize()

# Print the results
print(deserializer)"""