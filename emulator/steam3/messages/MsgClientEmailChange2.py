import struct


class MsgClientEmailChange2:
    """
    Client request to change email address (version 2 with password and ticket).
    EMsg: 894 (ClientEmailChange2)

    Body layout:
        char    m_rgchPassword[20] (fixed-size, null-padded)
        char    m_rgchEmail[322] (fixed-size, null-padded)
        uint32  m_unTicketLength
        byte[]  ticket (variable length based on m_unTicketLength)
    """

    PASSWORD_SIZE = 20
    EMAIL_SIZE = 322
    HEADER_FORMAT = f"<{PASSWORD_SIZE}s{EMAIL_SIZE}sI"
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

    def __init__(self):
        self.password = ""
        self.email = ""
        self.ticket_length = 0
        self.ticket = b""

    def deserialize(self, buffer: bytes, offset: int = 0) -> int:
        """
        Parse body from buffer starting at offset.
        Returns new offset after reading the body.
        """
        if len(buffer) < offset + self.HEADER_SIZE:
            raise ValueError(
                f"Buffer too small for MsgClientEmailChange2 header: need {self.HEADER_SIZE} bytes"
            )

        raw_password, raw_email, self.ticket_length = struct.unpack_from(
            self.HEADER_FORMAT, buffer, offset
        )
        self.password = raw_password.rstrip(b'\x00').decode('utf-8', errors='replace')
        self.email = raw_email.rstrip(b'\x00').decode('utf-8', errors='replace')

        offset += self.HEADER_SIZE

        # Read the ticket data
        if self.ticket_length > 0:
            if len(buffer) < offset + self.ticket_length:
                raise ValueError(
                    f"Buffer too small for MsgClientEmailChange2 ticket: need {self.ticket_length} bytes"
                )
            self.ticket = buffer[offset:offset + self.ticket_length]
            offset += self.ticket_length

        return offset

    def __repr__(self):
        return (
            f"MsgClientEmailChange2("
            f"password='***', "
            f"email='{self.email}', "
            f"ticket_length={self.ticket_length})"
        )

    def __str__(self):
        return str({
            "password": "***",
            "email": self.email,
            "ticket_length": self.ticket_length,
        })
