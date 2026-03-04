import struct


class MsgClientPasswordChange2:
    """
    Client request to change password (version 2 with ticket).
    EMsg: 893 (ClientPasswordChange2)

    Body layout:
        char    m_rgchOldPassword[20] (fixed-size, null-padded)
        char    m_rgchNewPassword[20] (fixed-size, null-padded)
        uint32  m_unTicketLength
        byte[]  ticket (variable length based on m_unTicketLength)
    """

    PASSWORD_SIZE = 20
    HEADER_FORMAT = f"<{PASSWORD_SIZE}s{PASSWORD_SIZE}sI"
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

    def __init__(self):
        self.old_password = ""
        self.new_password = ""
        self.ticket_length = 0
        self.ticket = b""

    def deserialize(self, buffer: bytes, offset: int = 0) -> int:
        """
        Parse body from buffer starting at offset.
        Returns new offset after reading the body.
        """
        if len(buffer) < offset + self.HEADER_SIZE:
            raise ValueError(
                f"Buffer too small for MsgClientPasswordChange2 header: need {self.HEADER_SIZE} bytes"
            )

        raw_old_password, raw_new_password, self.ticket_length = struct.unpack_from(
            self.HEADER_FORMAT, buffer, offset
        )
        self.old_password = raw_old_password.rstrip(b'\x00').decode('utf-8', errors='replace')
        self.new_password = raw_new_password.rstrip(b'\x00').decode('utf-8', errors='replace')

        offset += self.HEADER_SIZE

        # Read the ticket data
        if self.ticket_length > 0:
            if len(buffer) < offset + self.ticket_length:
                raise ValueError(
                    f"Buffer too small for MsgClientPasswordChange2 ticket: need {self.ticket_length} bytes"
                )
            self.ticket = buffer[offset:offset + self.ticket_length]
            offset += self.ticket_length

        return offset

    def __repr__(self):
        return (
            f"MsgClientPasswordChange2("
            f"old_password='***', "
            f"new_password='***', "
            f"ticket_length={self.ticket_length})"
        )

    def __str__(self):
        return str({
            "old_password": "***",
            "new_password": "***",
            "ticket_length": self.ticket_length,
        })
