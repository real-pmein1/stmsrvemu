import struct

from steam3.cm_packet_utils import CMProtoResponse, CMResponse
from steam3.Types.emsg import EMsg
from steam3.protobufs.steammessages_clientserver_login_pb2 import CMsgClientAccountInfo


class AccountInfoResponse:
    def __init__(self, client_obj):
        """
        Initialize the AccountInfoResponse object with default values.
        """
        self.persona_name = ""
        self.ip_country = "US"
        self.count_authed_computers = 0
        self.account_flags = 0
        self.client_obj = client_obj

    def to_protobuf(self):
        """
        Convert the AccountInfoResponse data to a Protobuf object.
        :return: A CMProtoResponse packet with serialized protobuf data.
        """
        packet = CMProtoResponse(eMsgID=EMsg.ClientAccountInfo, client_obj=self.client_obj)
        account_info = CMsgClientAccountInfo()

        account_info.persona_name = self.persona_name
        account_info.ip_country = self.ip_country
        if self.count_authed_computers:
            account_info.count_authed_computers = self.count_authed_computers
        if self.account_flags:
            account_info.account_flags = self.account_flags

        # Serialize the Protobuf message
        serialized_response = account_info.SerializeToString()

        # Attach serialized data to the packet
        packet.data = serialized_response
        packet.length = len(serialized_response)

        return packet

    def to_clientmsg(self):
        """
        Convert the AccountInfoResponse data to a regular byte buffer.
        :return: A CMResponse packet with binary data.
        """
        packet = CMResponse(eMsgID=EMsg.ClientAccountInfo, client_obj=self.client_obj)

        # Original format: \x00 + nickname + \x00 + country_code + \x00
        nickname_bytes = self.persona_name.encode('latin-1')
        country_bytes = self.ip_country.upper().encode('latin-1')

        packet.data = b"\x00" + nickname_bytes + b'\x00' + country_bytes + b'\x00'
        packet.length = len(packet.data)

        return packet
