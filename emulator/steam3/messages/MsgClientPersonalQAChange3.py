import struct
from io import BytesIO


class MsgClientPersonalQAChange3:
    """
    Client request to change personal secret question/answer (deprecated version 3).
    EMsg: 5459 (ClientPersonalQAChange3)

    Body layout:
        uint8   dummy
        string  password (null-terminated)
        string  secretQuestion (null-terminated)
        string  secretQuestionAnswer (null-terminated)
        string  changeConfirmationCode (null-terminated)
    """

    def __init__(self):
        self.dummy = 0
        self.password = ""
        self.secret_question = ""
        self.secret_question_answer = ""
        self.change_confirmation_code = ""

    def deserialize(self, buffer: bytes, offset: int = 0) -> int:
        """
        Parse body from buffer starting at offset.
        Returns new offset after reading the body.
        """
        stream = BytesIO(buffer[offset:])

        # Read dummy byte
        self.dummy = struct.unpack('<B', stream.read(1))[0]

        # Read null-terminated strings
        self.password = self._read_string(stream)
        self.secret_question = self._read_string(stream)
        self.secret_question_answer = self._read_string(stream)
        self.change_confirmation_code = self._read_string(stream)

        return offset + stream.tell()

    @staticmethod
    def _read_string(stream: BytesIO) -> str:
        """Read a null-terminated string from the stream."""
        chars = []
        while True:
            char = stream.read(1)
            if not char or char == b'\x00':
                break
            chars.append(char)
        return b''.join(chars).decode('utf-8', errors='replace')

    def __repr__(self):
        return (
            f"MsgClientPersonalQAChange3("
            f"dummy={self.dummy}, "
            f"password='***', "
            f"secret_question='{self.secret_question}', "
            f"secret_question_answer='***', "
            f"change_confirmation_code='{self.change_confirmation_code}')"
        )

    def __str__(self):
        return str({
            "dummy": self.dummy,
            "password": "***",
            "secret_question": self.secret_question,
            "secret_question_answer": "***",
            "change_confirmation_code": self.change_confirmation_code,
        })
