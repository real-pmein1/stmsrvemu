import pprint
import struct

def parse_game_info(buffer: bytes):
    offset = 0  # Track position in the buffer

    # Read the count of game info entries (4 bytes, little-endian)
    game_info_count, = struct.unpack_from('<I', buffer, offset)
    offset += 4

    games_info = []  # List to hold parsed game info
    for _ in range(game_info_count):

        game_info = {
            "serverGlobalId": None,
            "gameId": None,
            "serverIp": None,
            "serverPort": None,
            "vacSecured": None,
            "processId": None,
            "token": None,
            "gameName": None,
            "gameDataBlob": None,
        }

        # Parse fixed-size fields
        game_info["serverGlobalId"], game_info["gameId"] = struct.unpack_from('<QQ', buffer, offset)
        offset += 16  # 8 bytes each for serverGlobalId and gameId

        game_info["serverIp"], = struct.unpack_from('>I', buffer, offset)  # Big-endian 32-bit int
        offset += 4

        game_info["serverPort"], game_info["vacSecured"] = struct.unpack_from('<HH', buffer, offset)
        offset += 4  # 2 bytes each for serverPort and vacSecured

        game_info["processId"], = struct.unpack_from('<I', buffer, offset)  # Little-endian 32-bit int
        offset += 4

        # Parse token
        token_len, = struct.unpack_from('<I', buffer, offset)
        offset += 4
        if token_len:
            game_info["token"] = buffer[offset:offset + token_len]
            offset += token_len

        # Parse game name (null-terminated string)
        null_terminator_index = buffer.find(b'\x00', offset)

        game_info["gameName"] = buffer[offset:null_terminator_index].decode('utf-8')
        offset = null_terminator_index + 1  # Move past the null byte

        # Parse game data blob size
        blob_size, = struct.unpack_from('<I', buffer, offset)
        offset += 4
        if blob_size:
            game_info["gameDataBlob"] = buffer[offset:offset + blob_size]
            offset += blob_size

        games_info.append(game_info)

    return games_info


buffer = b'\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\xb8\x01\x00\x00\x00\x00\x00\x00@\xed\x87H\x87i\x00\x00\x9cg\x00\x00\x14\x00\x00\x00\xd0B\x93\x84\xd3Da\xa2\x02\x00\x00\x00\x01\x00\x10\x01n\x95:g\x00\x00\x00\x00\x00'
pprint.pprint(parse_game_info(buffer))