import ipaddress
import struct

from steam3.Types.Objects.PreProtoBuf.gameConnectToken import GameConnectToken


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