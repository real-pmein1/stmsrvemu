import struct

from steam3.Types.emsg import EMsg
from steam3.Types.steam_types import EResult
from steam3.cm_packet_utils import CMResponse


class MsgClientRequestForgottenPasswordEmailResponse:
    """
    Response to forgotten password email request.
    EMsg: 5402 (ClientRequestForgottenPasswordEmailResponse)

    Body layout:
        uint32  result (EResult)
        uint32  secretQuestionAnswerRequired (bool as int32)
    """

    BODY_FORMAT = "<II"
    BODY_SIZE = struct.calcsize(BODY_FORMAT)

    def __init__(self, client_obj=None, result: EResult = EResult.Fail, secret_question_answer_required: bool = False):
        self.client_obj = client_obj
        self.result = result
        self.secret_question_answer_required = secret_question_answer_required

    def deserialize(self, buffer: bytes, offset: int = 0) -> int:
        """
        Parse body from buffer starting at offset.
        Returns new offset after reading the body.
        """
        if len(buffer) < offset + self.BODY_SIZE:
            raise ValueError(
                f"Buffer too small for MsgClientRequestForgottenPasswordEmailResponse: need {self.BODY_SIZE} bytes"
            )

        raw_result, raw_secret_required = struct.unpack_from(self.BODY_FORMAT, buffer, offset)
        self.result = EResult(raw_result)
        self.secret_question_answer_required = raw_secret_required != 0

        return offset + self.BODY_SIZE

    def to_clientmsg(self) -> CMResponse:
        """
        Serialize body into a CMResponse packet.
        """
        packet = CMResponse(eMsgID=EMsg.ClientRequestForgottenPasswordEmailResponse, client_obj=self.client_obj)
        packet.data = struct.pack(
            self.BODY_FORMAT,
            int(self.result),
            1 if self.secret_question_answer_required else 0
        )
        packet.length = len(packet.data)
        return packet

    def to_protobuf(self) -> bytes:
        """
        Serialize body to raw bytes (non-protobuf format).
        """
        return struct.pack(
            self.BODY_FORMAT,
            int(self.result),
            1 if self.secret_question_answer_required else 0
        )

    def __repr__(self):
        return (
            f"MsgClientRequestForgottenPasswordEmailResponse("
            f"result={self.result}, "
            f"secret_question_answer_required={self.secret_question_answer_required})"
        )

    def __str__(self):
        return str({
            "result": int(self.result),
            "result_name": getattr(self.result, "name", str(self.result)),
            "secret_question_answer_required": self.secret_question_answer_required,
        })
