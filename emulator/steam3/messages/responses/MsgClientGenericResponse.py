import struct

from steam3.Types.emsg import EMsg
from steam3.Types.steam_types import EResult
from steam3.cm_packet_utils import CMResponse


class MsgClientGenericResponse:
    """
    Generic response message (server to client).
    EMsg: 5403 (ClientCreateAccountResponse / ClientGenericResponse)

    This is used for CreateAccountInformSteam3Response callback.
    The internal struct is MsgClientGenericResponse_t but maps to EMsg 5403.

    Body layout:
        uint32  m_EResult (EResult)
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
                f"Buffer too small for MsgClientGenericResponse: need {self.BODY_SIZE} bytes"
            )

        (raw_result,) = struct.unpack_from(self.BODY_FORMAT, buffer, offset)
        self.result = EResult(raw_result)
        return offset + self.BODY_SIZE

    def to_clientmsg(self) -> CMResponse:
        """
        Serialize body into a CMResponse packet.
        """
        # EMsg 5403 is ClientCreateAccountResponse but uses MsgClientGenericResponse_t struct
        packet = CMResponse(eMsgID=EMsg.ClientCreateAccountResponse, client_obj=self.client_obj)
        packet.data = struct.pack(self.BODY_FORMAT, int(self.result))
        packet.length = len(packet.data)
        return packet

    def to_bytes(self) -> bytes:
        """
        Serialize body to raw bytes.
        """
        return struct.pack(self.BODY_FORMAT, int(self.result))

    def __repr__(self):
        return f"MsgClientGenericResponse(result={self.result})"

    def __str__(self):
        return str({
            "result": int(self.result),
            "result_name": getattr(self.result, "name", str(self.result)),
        })
