import struct

from steam3.Types.emsg import EMsg
from steam3.Types.steam_types import EResult
from steam3.cm_packet_utils import CMResponse, CMProtoResponse
from steam3.protobufs.steammessages_clientserver_friends_pb2 import CMsgClientAddFriendResponse


class AddFriendResponse:
    """
    Response message for ClientAddFriendResponse.

    Fields:
        eresult (int): Result code (EResult)
        steam_id_added (int): SteamID of the added friend
        persona_name_added (str): Persona name of the added friend
        job_id (int): Job ID for clientmsg format
        is_old_style (bool): Whether to use deprecated message format
    """

    def __init__(self, client_obj):
        self.client_obj = client_obj
        self.eresult = EResult.OK
        self.steam_id_added = 0
        self.persona_name_added = ""
        self.job_id = 0
        self.is_old_style = False

    def to_clientmsg(self):
        """Serialize to legacy ClientMsg format."""
        if self.is_old_style:
            packet = CMResponse(eMsgID=EMsg.ClientAddFriendResponse_deprecated, client_obj=self.client_obj)
        else:
            packet = CMResponse(eMsgID=EMsg.ClientAddFriendResponse, client_obj=self.client_obj)

        # Build packet data
        packet_data = bytearray(struct.pack('<Q', self.job_id))
        packet_data += struct.pack('<Q', self.steam_id_added)
        packet_data += struct.pack('<I', int(self.eresult))
        packet_data += self.persona_name_added.encode('latin-1') + b'\x00'

        packet.data = bytes(packet_data)
        packet.length = len(packet.data)

        return packet

    def to_protobuf(self):
        """Serialize to protobuf format."""
        packet = CMProtoResponse(eMsgID=EMsg.ClientAddFriendResponse, client_obj=self.client_obj)

        add_friend_msg = CMsgClientAddFriendResponse()
        add_friend_msg.eresult = int(self.eresult)
        if self.steam_id_added:
            add_friend_msg.steam_id_added = self.steam_id_added
        if self.persona_name_added:
            add_friend_msg.persona_name_added = self.persona_name_added

        packet.data = add_friend_msg.SerializeToString()
        packet.length = len(packet.data)

        return packet

    def __repr__(self):
        return f"<AddFriendResponse eresult={self.eresult} steam_id={self.steam_id_added}>"
