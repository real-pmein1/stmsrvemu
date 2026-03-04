from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse


class MsgClientResetForgottenPassword:
    """
    MsgClientResetForgottenPassword_t
    EMsg: ClientResetForgottenPassword

    Fixed body layout (C char arrays):
        char account_name[64]
        char answer[255]
        char new_password[20]
        char old_password[20]
        char email_verification_key[255]
    """

    LEN_ACCOUNT = 64
    LEN_ANSWER = 255
    LEN_NEWPW = 20
    LEN_OLDPW = 20
    LEN_EMAILKEY = 255

    BODY_SIZE = LEN_ACCOUNT + LEN_ANSWER + LEN_NEWPW + LEN_OLDPW + LEN_EMAILKEY

    def __init__(
        self,
        client_obj,
        account_name: str = "",
        answer: str = "",
        new_password: str = "",
        old_password: str = "",
        email_verification_key: str = "",
    ):
        self.client_obj = client_obj
        self.account_name = account_name or ""
        self.answer = answer or ""
        self.new_password = new_password or ""
        self.old_password = old_password or ""
        self.email_verification_key = email_verification_key or ""

    @staticmethod
    def _pack_cbuf(s: str, length: int) -> bytes:
        raw = (s or "").encode("utf-8", errors="ignore")
        raw = raw[: max(0, length - 1)]  # leave room for NUL
        raw += b"\x00"
        return raw.ljust(length, b"\x00")

    @staticmethod
    def _unpack_cbuf(buf: bytes) -> str:
        return buf.split(b"\x00", 1)[0].decode("utf-8", errors="replace")

    def deSerialize(self, buffer: bytes, offset: int = 0) -> int:
        if len(buffer) < offset + self.BODY_SIZE:
            raise ValueError(f"Buffer too small: need {self.BODY_SIZE} bytes")

        p = offset

        self.account_name = self._unpack_cbuf(buffer[p:p + self.LEN_ACCOUNT])
        p += self.LEN_ACCOUNT

        self.answer = self._unpack_cbuf(buffer[p:p + self.LEN_ANSWER])
        p += self.LEN_ANSWER

        self.new_password = self._unpack_cbuf(buffer[p:p + self.LEN_NEWPW])
        p += self.LEN_NEWPW

        self.old_password = self._unpack_cbuf(buffer[p:p + self.LEN_OLDPW])
        p += self.LEN_OLDPW

        self.email_verification_key = self._unpack_cbuf(buffer[p:p + self.LEN_EMAILKEY])
        p += self.LEN_EMAILKEY

        return p

    def to_clientmsg(self) -> CMResponse:
        packet = CMResponse(eMsgID=EMsg.ClientResetForgottenPassword, client_obj=self.client_obj)

        body = (
            self._pack_cbuf(self.account_name, self.LEN_ACCOUNT)
            + self._pack_cbuf(self.answer, self.LEN_ANSWER)
            + self._pack_cbuf(self.new_password, self.LEN_NEWPW)
            + self._pack_cbuf(self.old_password, self.LEN_OLDPW)
            + self._pack_cbuf(self.email_verification_key, self.LEN_EMAILKEY)
        )

        packet.data = body
        packet.length = len(packet.data)
        return packet

    def __str__(self):
        return str({
            "emsg": int(EMsg.ClientResetForgottenPassword),
            "account_name": self.account_name,
            "answer_len": len(self.answer.encode("utf-8", errors="replace")),
            "new_password_len": len(self.new_password.encode("utf-8", errors="replace")),
            "old_password_len": len(self.old_password.encode("utf-8", errors="replace")),
            "email_verification_key_len": len(self.email_verification_key.encode("utf-8", errors="replace")),
        })