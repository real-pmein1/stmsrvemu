import struct

from steam3.cm_packet_utils import CMProtoResponse, CMResponse
from steam3.Types.emsg import EMsg
from steam3.protobufs.steammessages_clientserver_pb2 import CMsgClientSessionToken
from steam3.utilities import generate_64bit_token


class SessionTokenResponse:
    def __init__(self, client_obj):
        """
        Initialize the SessionTokenResponse object with default values.
        This token is used for authenticated content downloading in Steam2.
        """
        self.client_obj = client_obj
        self.token = 0  # 64-bit token

    def generate_token(self):
        """
        Generate a new session token and save it to the client object.
        """
        token_bytes = generate_64bit_token().encode('latin-1')
        self.client_obj.set_new_sessionkey(token_bytes)
        self.token = self.client_obj.session_token

    def to_protobuf(self):
        """
        Convert the SessionTokenResponse data to a Protobuf object.
        :return: A CMProtoResponse packet with serialized protobuf data.
        """
        packet = CMProtoResponse(eMsgID=EMsg.ClientSessionToken, client_obj=self.client_obj)
        session_token_msg = CMsgClientSessionToken()

        # Convert token bytes to uint64
        if isinstance(self.token, bytes):
            # If token is less than 8 bytes, pad it
            token_bytes = self.token[:8].ljust(8, b'\x00')
            session_token_msg.token = struct.unpack('<Q', token_bytes)[0]
        else:
            session_token_msg.token = self.token

        # Serialize the Protobuf message
        serialized_response = session_token_msg.SerializeToString()

        # Attach serialized data to the packet
        packet.data = serialized_response
        packet.length = len(serialized_response)

        return packet

    def to_clientmsg(self):
        """
        Convert the SessionTokenResponse data to a regular byte buffer.
        :return: A CMResponse packet with binary data.
        """
        packet = CMResponse(eMsgID=EMsg.ClientSessionToken, client_obj=self.client_obj)

        # The original format just sends the raw token bytes
        if isinstance(self.token, bytes):
            packet.data = self.token
        else:
            packet.data = struct.pack('<Q', self.token)

        packet.length = len(packet.data)

        return packet
