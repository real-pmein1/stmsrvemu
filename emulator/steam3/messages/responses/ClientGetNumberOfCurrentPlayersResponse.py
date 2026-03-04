import struct
from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMProtoResponse, CMResponse
from steam3.protobufs.steammessages_clientserver_2_pb2 import (
    CMsgDPGetNumberOfCurrentPlayersResponse,
)


class ClientGetNumberOfCurrentPlayersResponse:
    """Response containing the current player count for a game."""

    def __init__(self, client_obj, success: int = 0, player_count: int = 0):
        self.client_obj = client_obj
        self.success = success
        self.player_count = player_count

    def to_clientmsg(self) -> CMResponse:
        """Serialize this response into the legacy ClientMsg format."""
        packet = CMResponse(
            eMsgID=EMsg.ClientGetNumberOfCurrentPlayersResponse,
            client_obj=self.client_obj,
        )
        packet.data = struct.pack("<II", int(self.success), int(self.player_count))
        packet.length = len(packet.data)
        return packet

    def to_protobuf(self) -> CMProtoResponse:
        """Serialize this response into its protobuf representation."""
        packet = CMProtoResponse(
            eMsgID=EMsg.ClientGetNumberOfCurrentPlayersResponse,
            client_obj=self.client_obj,
        )
        body = CMsgDPGetNumberOfCurrentPlayersResponse()
        body.eresult = int(self.success)
        body.player_count = int(self.player_count)
        packet.set_response_message(body)
        data = body.SerializeToString()
        packet.data = data
        packet.length = len(data)
        return packet

    def __str__(self) -> str:  # pragma: no cover - trivial
        return (
            f"ClientGetNumberOfCurrentPlayersResponse("
            f"success={self.success}, player_count={self.player_count})"
        )
