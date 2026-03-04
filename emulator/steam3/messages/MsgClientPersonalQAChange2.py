import struct


class MsgClientPersonalQAChange2:
    """
    Client request to change personal secret question/answer (version 2 with password and ticket).
    EMsg: 895 (ClientPersonalQAChange2)

    Body layout:
        char    m_rgchPassword[20] (fixed-size, null-padded)
        int32   m_iPersonalQuestion (question index)
        char    m_rgchNewQuestion[255] (fixed-size, null-padded)
        char    m_rgchNewAnswer[255] (fixed-size, null-padded)
        uint32  m_unTicketLength
        byte[]  ticket (variable length based on m_unTicketLength)
    """

    PASSWORD_SIZE = 20
    QUESTION_SIZE = 255
    ANSWER_SIZE = 255
    HEADER_FORMAT = f"<{PASSWORD_SIZE}si{QUESTION_SIZE}s{ANSWER_SIZE}sI"
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

    def __init__(self):
        self.password = ""
        self.personal_question_index = 0
        self.new_question = ""
        self.new_answer = ""
        self.ticket_length = 0
        self.ticket = b""

    def deserialize(self, buffer: bytes, offset: int = 0) -> int:
        """
        Parse body from buffer starting at offset.
        Returns new offset after reading the body.
        """
        if len(buffer) < offset + self.HEADER_SIZE:
            raise ValueError(
                f"Buffer too small for MsgClientPersonalQAChange2 header: need {self.HEADER_SIZE} bytes"
            )

        raw_password, self.personal_question_index, raw_question, raw_answer, self.ticket_length = struct.unpack_from(
            self.HEADER_FORMAT, buffer, offset
        )
        self.password = raw_password.rstrip(b'\x00').decode('utf-8', errors='replace')
        self.new_question = raw_question.rstrip(b'\x00').decode('utf-8', errors='replace')
        self.new_answer = raw_answer.rstrip(b'\x00').decode('utf-8', errors='replace')

        offset += self.HEADER_SIZE

        # Read the ticket data
        if self.ticket_length > 0:
            if len(buffer) < offset + self.ticket_length:
                raise ValueError(
                    f"Buffer too small for MsgClientPersonalQAChange2 ticket: need {self.ticket_length} bytes"
                )
            self.ticket = buffer[offset:offset + self.ticket_length]
            offset += self.ticket_length

        return offset

    def __repr__(self):
        return (
            f"MsgClientPersonalQAChange2("
            f"password='***', "
            f"personal_question_index={self.personal_question_index}, "
            f"new_question='{self.new_question}', "
            f"new_answer='***', "
            f"ticket_length={self.ticket_length})"
        )

    def __str__(self):
        return str({
            "password": "***",
            "personal_question_index": self.personal_question_index,
            "new_question": self.new_question,
            "new_answer": "***",
            "ticket_length": self.ticket_length,
        })
