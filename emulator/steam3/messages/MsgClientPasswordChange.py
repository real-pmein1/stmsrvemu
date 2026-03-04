import struct


class MsgClientPasswordChange:
    """
    Client request to change password (original version).
    EMsg: 804 (ClientPasswordChange)

    Body layout:
        char    m_rgchOldPassword[20] (fixed-size, null-padded)
        char    m_rgchNewPassword[20] (fixed-size, null-padded)
    """

    PASSWORD_SIZE = 20
    BODY_FORMAT = f"<{PASSWORD_SIZE}s{PASSWORD_SIZE}s"
    BODY_SIZE = struct.calcsize(BODY_FORMAT)

    def __init__(self):
        self.old_password = ""
        self.new_password = ""

    def deserialize(self, buffer: bytes, offset: int = 0) -> int:
        """
        Parse body from buffer starting at offset.
        Returns new offset after reading the body.
        """
        if len(buffer) < offset + self.BODY_SIZE:
            raise ValueError(
                f"Buffer too small for MsgClientPasswordChange: need {self.BODY_SIZE} bytes"
            )

        raw_old_password, raw_new_password = struct.unpack_from(
            self.BODY_FORMAT, buffer, offset
        )
        self.old_password = raw_old_password.rstrip(b'\x00').decode('utf-8', errors='replace')
        self.new_password = raw_new_password.rstrip(b'\x00').decode('utf-8', errors='replace')

        return offset + self.BODY_SIZE

    def __repr__(self):
        return f"MsgClientPasswordChange(old_password='***', new_password='***')"

    def __str__(self):
        return str({
            "old_password": "***",
            "new_password": "***",
        })
