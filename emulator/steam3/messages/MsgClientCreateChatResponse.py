import struct
from io import BytesIO
from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse


class MsgClientCreateChatResponse:

    def __init__(self, client_obj, data: bytes = None):
        self.result = 0
        self.chatGlobalId = 0
        self.type = 0
        self.friendChatGlobalId = 0
        self.client_obj = client_obj

        if data is not None:
            self.deserialize(data)

    def deserialize(self, data: bytes):
        """
        Parse a byte buffer into, in order:
          1) 4-byte little-endian signed result
          2) 8-byte little-endian unsigned chatGlobalId
          3) 4-byte little-endian signed type
          4) 8-byte little-endian unsigned friendChatGlobalId
        """
        stream = BytesIO(data)

        # result (int32)
        self.result, = struct.unpack('<i', stream.read(4))
        # chatGlobalId (uint64)
        self.chatGlobalId, = struct.unpack('<Q', stream.read(8))
        # type (int32)
        self.type, = struct.unpack('<i', stream.read(4))
        # friendChatGlobalId (uint64)
        self.friendChatGlobalId, = struct.unpack('<Q', stream.read(8))

    def to_protobuf(self):
        """
        Not implemented for this message type.
        """
        raise NotImplementedError("to_protobuf not implemented")

    def to_clientmsg(self):
        """
        Build a CMResponse packet with payload:
          1) 4-byte little-endian signed result
          2) 8-byte little-endian unsigned chatGlobalId
          3) 4-byte little-endian signed type
          4) 8-byte little-endian unsigned friendChatGlobalId
        """
        packet = CMResponse(eMsgID=EMsg.ClientCreateChatResponse, client_obj=self.client_obj)

        stream = BytesIO()
        stream.write(struct.pack('<i', self.result))
        stream.write(struct.pack('<Q', self.chatGlobalId))
        stream.write(struct.pack('<i', self.type))
        stream.write(struct.pack('<Q', self.friendChatGlobalId))

        packet.data = stream.getvalue()
        packet.length = len(packet.data)
        return packet

    def __str__(self):
        return (
            f"{self.__class__.__name__}("
            f"result={self.result}, "
            f"chatGlobalId={self.chatGlobalId}, "
            f"type={self.type}, "
            f"friendChatGlobalId={self.friendChatGlobalId}"
            f")"
        )
