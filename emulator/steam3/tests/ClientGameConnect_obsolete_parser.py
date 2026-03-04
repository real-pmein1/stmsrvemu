import struct
from datetime import datetime
import ipaddress

class GameConnectToken:
    def __init__(self):
        self.token = None
        self.steam_global_id = None
        self.timestamp = None
        self.other = None

    def deserialize(self, buffer):
        """
        Deserializes the last 20 bytes of the buffer into the token, steamGlobalId, and timestamp.
        :param buffer: The byte buffer containing the game connect token data.
        :return: Tuple of token, steamGlobalId, and timestamp.
        """
        if len(buffer) != 20:
            raise ValueError("GameConnectToken buffer must be exactly 20 bytes.")
        self.token, self.steam_global_id, raw_timestamp = struct.unpack('<QQI', buffer[:20])
        self.timestamp = datetime.utcfromtimestamp(raw_timestamp).strftime('%m/%d/%Y %H:%M:%S')
        return self.token, self.steam_global_id, self.timestamp

    def __str__(self):
        return (
            f"GameConnectToken(\n"
            f"  Token: {self.token}\n"
            f"  SteamGlobalId: {self.steam_global_id}\n"
            f"  Timestamp: {self.timestamp}\n"
            f")"
        )


class MsgClientGameConnect:
    def __init__(self):
        self.unknown1 = None
        self.unknown2 = None  # Field 1
        self.variable_length_data = None
        self.game_connect_token = None

    def parse(self, byte_data):
        """
        Parses the MsgClientGameConnect message byte string into its individual parts.
        :param byte_data: The raw byte string of the message.
        """
        offset = 0
        try:
            # 4. Field 3 (uint32)
            self.unknown1 = byte_data[:6]
            offset += 6

            # Variable length data size
            variable_length_data_size = struct.unpack_from("<I", byte_data, offset)[0]
            offset += 4

            self.variable_length_data = byte_data[offset:offset + variable_length_data_size]
            offset += variable_length_data_size

            # New parsing logic for self.variable_length_data
            if self.variable_length_data:
                # First 2 bytes are unknown1
                self.unknown2 = self.variable_length_data[:2]

                # Next 4 bytes are the IP address
                ip_bytes = self.variable_length_data[2:6]
                self.ip_address = str(ipaddress.IPv4Address(ip_bytes))

                # Next 2 bytes are the port
                self.port = struct.unpack_from("<H", self.variable_length_data, 6)[0]

                self.token_size = struct.unpack_from("<I", self.variable_length_data, 10)[0]

                # If the last 20 bytes of the data are a GameConnectToken
                if len(self.variable_length_data) >= 20:
                    self.game_connect_token = GameConnectToken()
                    self.game_connect_token.deserialize(self.variable_length_data[14:])

        except struct.error as e:
            raise ValueError(f"Failed to parse MsgClientGameConnect: {e}")

    def __str__(self):
        """
        Returns a human-readable representation of the MsgClientGameConnect message.
        """
        return (
                f"MsgClientGameConnect(\n"
                f"  Unknown1: {self.unknown1}\n"
                f"  Unknown2: {self.unknown2}\n"
                f"  IP Address: {self.ip_address}\n"
                f"  Port: {self.port}\n"
                f"  Token Size: {self.token_size}\n"
                f"  Game Connect Token: {self.game_connect_token if self.game_connect_token else 'None'}\n"
                f")"
        )


# Example Usage
if __name__ == "__main__":
    # Example byte string for MsgClientGameConnect
    example_data = b'\xd1\x02\x00\x00 m\x88\x00\x01\x00\x10\x01-\xaa \x02\x01,\x92W\x1d\x00@\x01P\x00\x00\x00\\\x9e\xb6@\x87i\x01\x00\x14\x00\x00\x00e\x9eYD\x03"\x0f\xc5 m\x88\x00\x01\x00\x10\x01\x11\x1e@D'

    parser = MsgClientGameConnect()
    parser.parse(example_data[16:])
    print(parser)