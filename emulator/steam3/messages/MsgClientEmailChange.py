import struct


class MsgClientEmailChange:
    """
    Client request to change email address (original version).
    EMsg: 843 (ClientEmailChange)

    Body layout:
        char    m_rgchEmail[322] (fixed-size, null-padded)
    """

    EMAIL_SIZE = 322
    BODY_FORMAT = f"<{EMAIL_SIZE}s"
    BODY_SIZE = struct.calcsize(BODY_FORMAT)

    def __init__(self):
        self.email = ""

    def deserialize(self, buffer: bytes, offset: int = 0) -> int:
        """
        Parse body from buffer starting at offset.
        Returns new offset after reading the body.
        """
        if len(buffer) < offset + self.BODY_SIZE:
            raise ValueError(
                f"Buffer too small for MsgClientEmailChange: need {self.BODY_SIZE} bytes"
            )

        raw_email, = struct.unpack_from(self.BODY_FORMAT, buffer, offset)
        self.email = raw_email.rstrip(b'\x00').decode('utf-8', errors='replace')

        return offset + self.BODY_SIZE

    def __repr__(self):
        return f"MsgClientEmailChange(email='{self.email}')"

    def __str__(self):
        return str({
            "email": self.email,
        })
