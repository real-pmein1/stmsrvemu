import struct
from datetime import datetime
from random import getrandbits

import globalvars
from steam3.cm_packet_utils import CMProtoResponse, CMResponse
from steam3.Types.emsg import EMsg
from steam3.Types.Objects.PreProtoBuf.gameConnectToken import GameConnectToken
from steam3.protobufs.steammessages_clientserver_pb2 import CMsgClientGameConnectTokens


class GameConnectTokensResponse:
    def __init__(self, client_obj):
        """
        Initialize the GameConnectTokensResponse object with default values.
        """
        self.client_obj = client_obj
        self.tokens = []  # List of GameConnectToken objects
        self.max_tokens_to_keep = 10

    def add_token(self, token):
        """
        Add a GameConnectToken to the response.
        :param token: A GameConnectToken object
        """
        self.tokens.append(token)

    def generate_default_tokens(self, count=2):
        """
        Generate default tokens for the client.
        :param count: Number of tokens to generate
        """
        steam_globalID = self.client_obj.steamID.get_static_steam_global_id()
        for _ in range(count):
            token = GameConnectToken(
                getrandbits(64),
                steam_globalID,
                int(datetime.utcnow().timestamp())
            )
            self.tokens.append(token)

    def to_protobuf(self):
        """
        Convert the GameConnectTokensResponse data to a Protobuf object.
        :return: A CMProtoResponse packet with serialized protobuf data.
        """
        packet = CMProtoResponse(eMsgID=EMsg.ClientGameConnectTokens, client_obj=self.client_obj)
        tokens_msg = CMsgClientGameConnectTokens()

        tokens_msg.max_tokens_to_keep = self.max_tokens_to_keep

        # Add each token as serialized bytes
        for token in self.tokens:
            tokens_msg.tokens.append(token.serialize())

        # Serialize the Protobuf message
        serialized_response = tokens_msg.SerializeToString()

        # Attach serialized data to the packet
        packet.data = serialized_response
        packet.length = len(serialized_response)

        return packet

    def to_clientmsg(self):
        """
        Convert the GameConnectTokensResponse data to a regular byte buffer.
        :return: A CMResponse packet with binary data.
        """
        packet = CMResponse(eMsgID=EMsg.ClientGameConnectTokens, client_obj=self.client_obj)

        # Size of GameConnectToken structure (QQI = 8+8+4 = 20 bytes)
        game_connect_token_length = struct.calcsize('<QQI')
        packet.data = struct.pack('I', game_connect_token_length)

        # Number of tokens
        packet.data += struct.pack('I', len(self.tokens))

        # Serialize each token
        for token in self.tokens:
            packet.data += token.serialize()

        # Add maximum tokens for newer versions
        if globalvars.steamui_ver > 624:
            packet.data += struct.pack('I', self.max_tokens_to_keep)

        packet.length = len(packet.data)

        return packet
