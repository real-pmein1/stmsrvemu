import struct

from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMProtoResponse, CMResponse
from steam3.protobufs.steammessages_clientserver_pb2 import CMsgClientGetAppOwnershipTicketResponse


class GetAppOwnershipTicketResponse:
    def __init__(self, client_obj):
        """
        Initialize the GetAppOwnershipTicketResponse object with default values.
        """
        self.eresult = 0
        self.app_id = 0
        self.ticket = b""
        self.signature_length = 0
        self.client_obj = client_obj

    def to_protobuf(self):
        """
        Convert the response data to a Protobuf message.
        :return: Serialized Protobuf response.
        """
        packet = CMProtoResponse(eMsgID = EMsg.ClientGetAppOwnershipTicketResponse, client_obj = self.client_obj)

        response = CMsgClientGetAppOwnershipTicketResponse()
        response.eresult = self.eresult
        response.app_id = self.app_id
        response.ticket = self.ticket

        packet.set_response_message(response)
        serialized_response = response.SerializeToString()

        # Attach serialized data to the packet.
        packet.data = serialized_response
        packet.length = len(serialized_response)

        return packet

    def to_clientmsg(self):
        """
        Convert the response data to a byte buffer.
        :return: A byte string.
        """
        packet = CMResponse(eMsgID = EMsg.ClientGetAppOwnershipTicketResponse, client_obj = self.client_obj)
        # Structure: eresult (4 bytes), app_id (4 bytes), ticket_length (4 bytes), ticket (variable length)
        packet.data = struct.pack('<I I I I', self.eresult, self.app_id, len(self.ticket) - self.signature_length, self.signature_length)
        packet.data += self.ticket
        packet.length = len(packet.data)
        return packet