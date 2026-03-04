import struct

from steam3.Types.emsg import EMsg
from steam3.Types.steam_types import EResult
from steam3.cm_packet_utils import CMResponse


class MsgClientResetForgottenPasswordResponse:
    """
    Usually the same as MsgClientGenericResponse_t in older Steam3 clients:
        uint32 m_EResult
    """
    BODY_FORMAT = "<I"
    BODY_SIZE = struct.calcsize(BODY_FORMAT)

    def __init__(self, client_obj, result: EResult = EResult.OK):
        self.client_obj = client_obj
        self.m_EResult = result

    def deSerialize(self, buffer: bytes, offset: int = 0) -> int:
        if len(buffer) < offset + self.BODY_SIZE:
            raise ValueError(f"Buffer too small: need {self.BODY_SIZE} bytes")

        (raw_result,) = struct.unpack_from(self.BODY_FORMAT, buffer, offset)
        self.m_EResult = EResult(raw_result)
        return offset + self.BODY_SIZE

    def to_clientmsg(self) -> CMResponse:
        packet = CMResponse(eMsgID=EMsg.ClientResetForgottenPasswordResponse, client_obj=self.client_obj)
        packet.data = struct.pack(self.BODY_FORMAT, int(self.m_EResult))
        packet.length = len(packet.data)
        return packet
