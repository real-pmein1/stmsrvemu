import struct

from steam3.Types.emsg import EMsg
from steam3.Types.steam_types import EResult
from steam3.cm_packet_utils import CMResponse


class MsgClientSecretQAChangeResponse:
    """
    Response to secret question/answer change request.
    EMsg: 892 (ClientSecretQAChangeResponse)

    Body layout:
        uint32  result (EResult)
    """

    BODY_FORMAT = "<I"
    BODY_SIZE = struct.calcsize(BODY_FORMAT)

    def __init__(self, client_obj=None, result: EResult = EResult.Fail):
        self.client_obj = client_obj
        self.result = result

    def deserialize(self, buffer: bytes, offset: int = 0) -> int:
        """
        Parse body from buffer starting at offset.
        Returns new offset after reading the body.
        """
        if len(buffer) < offset + self.BODY_SIZE:
            raise ValueError(
                f"Buffer too small for MsgClientSecretQAChangeResponse: need {self.BODY_SIZE} bytes"
            )

        (raw_result,) = struct.unpack_from(self.BODY_FORMAT, buffer, offset)
        self.result = EResult(raw_result)

        return offset + self.BODY_SIZE

    def to_clientmsg(self) -> CMResponse:
        """
        Serialize body into a CMResponse packet.
        """
        packet = CMResponse(eMsgID=EMsg.ClientSecretQAChangeResponse, client_obj=self.client_obj)
        packet.data = struct.pack(self.BODY_FORMAT, int(self.result))
        packet.length = len(packet.data)
        return packet

    def to_protobuf(self) -> bytes:
        """
        Serialize body to raw bytes (non-protobuf format).
        """
        return struct.pack(self.BODY_FORMAT, int(self.result))

    def __repr__(self):
        return f"MsgClientSecretQAChangeResponse(result={self.result})"

    def __str__(self):
        return str({
            "result": int(self.result),
            "result_name": getattr(self.result, "name", str(self.result)),
        })
