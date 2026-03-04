import struct

from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse


class MsgClientCheckPassword:
    """
    MsgClientCheckPassword_t

    Inferred body layout:
        uint8  m_bSendRecoveryEmail
        (possible padding)

    Followed by "str data" appended via AddStrData:
        char account_name[]  (NUL-terminated)
        char password[]      (NUL-terminated)

    Notes:
    - ExtendedClientMsgHdr_t steamid/sessionid are handled by CMResponse / outer layer.
    - If your actual string storage is length-prefixed, replace _read_cstr/_write_cstr.
    """

    # bool stored as 1 byte is the usual in these bodies.
    BODY_FORMAT = "<B"
    BODY_SIZE = struct.calcsize(BODY_FORMAT)

    def __init__(self, client_obj, account_name: str = "", password: str = "", attempt_recovery: bool = False):
        self.client_obj = client_obj
        self.m_bSendRecoveryEmail = bool(attempt_recovery)
        self.account_name = account_name or ""
        self.password = password or ""

    @staticmethod
    def _read_cstr(buf: bytes, offset: int) -> tuple[str, int]:
        """
        Read NUL-terminated UTF-8 string from buf starting at offset.
        Returns (string, new_offset_after_nul).
        """
        end = buf.find(b"\x00", offset)
        if end == -1:
            raise ValueError("Missing NUL terminator while reading string data")
        s = buf[offset:end].decode("utf-8", errors="replace")
        return s, end + 1

    @staticmethod
    def _write_cstr(s: str) -> bytes:
        """
        Write NUL-terminated UTF-8 string.
        """
        return (s or "").encode("utf-8") + b"\x00"

    def deSerialize(self, buffer: bytes, offset: int = 0) -> int:
        """
        Parse body + appended string data from `buffer`.
        Returns new offset after consuming what we parsed.
        """
        if len(buffer) < offset + self.BODY_SIZE:
            raise ValueError(f"Buffer too small for MsgClientCheckPassword body: need {self.BODY_SIZE} bytes")

        (flag,) = struct.unpack_from(self.BODY_FORMAT, buffer, offset)
        self.m_bSendRecoveryEmail = bool(flag)
        offset += self.BODY_SIZE

        # Now parse the two AddStrData strings: account name, password
        self.account_name, offset = self._read_cstr(buffer, offset)
        self.password, offset = self._read_cstr(buffer, offset)

        return offset

    def to_clientmsg(self) -> CMResponse:
        """
        Serialize into a CMResponse packet (body + str data).
        """
        packet = CMResponse(eMsgID=EMsg.ClientCheckPassword, client_obj=self.client_obj)

        body = struct.pack(self.BODY_FORMAT, 1 if self.m_bSendRecoveryEmail else 0)
        strdata = self._write_cstr(self.account_name) + self._write_cstr(self.password)

        packet.data = body + strdata
        packet.length = len(packet.data)
        return packet

    def __str__(self):
        # Not printing password in plaintext because even robots get second-hand embarrassment.
        return str({
            "m_bSendRecoveryEmail": self.m_bSendRecoveryEmail,
            "account_name": self.account_name,
            "password_len": len(self.password.encode("utf-8", errors="replace")),
        })
