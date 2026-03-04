import struct
from steam3.Types.emsg import EMsg
from steam3.Types.steam_types import EResult
from steam3.cm_packet_utils import CMResponse, CMProtoResponse
from steam3.protobufs.steammessages_clientserver_login_pb2 import CMsgClientLoggedOff


class MsgClientLoggedOff:
    """This message is the one that boots a client from the CM, forces them to log off"""
    BODY_FORMAT = "<III"  # three little-endian unsigned 32-bit ints

    def __init__(self, client_obj):
        self.client_obj = client_obj
        self.result = EResult.OK
        self.secMinReconnectHint_obsolete = 1  # 1 minute
        self.secMaxReconnectHint_obsolete = 30  # 30 seconds

    def deSerialize(self, buffer: bytes, offset: int = 0):
        """
         unpacks:
          - result
          - secMinReconnectHint_obsolete
          - secMaxReconnectHint_obsolete

        Returns the new offset after reading the body.
        """

        # unpack our three fields
        (raw_result,
         self.secMinReconnectHint_obsolete,
         self.secMaxReconnectHint_obsolete) = struct.unpack_from(
            self.BODY_FORMAT, buffer, offset
        )

        # convert raw_result into enum
        self.result = EResult(raw_result)

        offset += struct.calcsize(self.BODY_FORMAT)


    def to_clientmsg(self):
        packet = CMResponse(eMsgID=EMsg.ClientLoggedOff, client_obj=self.client_obj)
        # pack the three fields
        packet.data = struct.pack(
            self.BODY_FORMAT,
            int(self.result),
            self.secMinReconnectHint_obsolete,
            self.secMaxReconnectHint_obsolete
        )
        packet.length = len(packet.data)
        return packet

    def to_protobuf(self):
        """Serialize to protobuf format."""
        packet = CMProtoResponse(eMsgID=EMsg.ClientLoggedOff, client_obj=self.client_obj)

        logged_off_msg = CMsgClientLoggedOff()
        logged_off_msg.eresult = int(self.result)

        packet.data = logged_off_msg.SerializeToString()
        packet.length = len(packet.data)

        return packet

    def __repr__(self):
        return f"<MsgClientLoggedOff result={self.result}>"
