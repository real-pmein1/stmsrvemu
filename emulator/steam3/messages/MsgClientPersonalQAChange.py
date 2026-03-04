import struct


class MsgClientPersonalQAChange:
    """
    Client request to change personal secret question/answer (original version).
    EMsg: 844 (ClientPersonalQAChange)

    Body layout:
        int32   m_iPersonalQuestion (question index)
        char    m_rgchNewQuestion[255] (fixed-size, null-padded)
        char    m_rgchNewAnswer[255] (fixed-size, null-padded)
    """

    QUESTION_SIZE = 255
    ANSWER_SIZE = 255
    BODY_FORMAT = f"<i{QUESTION_SIZE}s{ANSWER_SIZE}s"
    BODY_SIZE = struct.calcsize(BODY_FORMAT)

    def __init__(self):
        self.personal_question_index = 0
        self.new_question = ""
        self.new_answer = ""

    def deserialize(self, buffer: bytes, offset: int = 0) -> int:
        """
        Parse body from buffer starting at offset.
        Returns new offset after reading the body.
        """
        if len(buffer) < offset + self.BODY_SIZE:
            raise ValueError(
                f"Buffer too small for MsgClientPersonalQAChange: need {self.BODY_SIZE} bytes"
            )

        self.personal_question_index, raw_question, raw_answer = struct.unpack_from(
            self.BODY_FORMAT, buffer, offset
        )
        self.new_question = raw_question.rstrip(b'\x00').decode('utf-8', errors='replace')
        self.new_answer = raw_answer.rstrip(b'\x00').decode('utf-8', errors='replace')

        return offset + self.BODY_SIZE

    def __repr__(self):
        return (
            f"MsgClientPersonalQAChange("
            f"personal_question_index={self.personal_question_index}, "
            f"new_question='{self.new_question}', "
            f"new_answer='***')"
        )

    def __str__(self):
        return str({
            "personal_question_index": self.personal_question_index,
            "new_question": self.new_question,
            "new_answer": "***",
        })
