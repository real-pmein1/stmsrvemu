import struct
from io import BytesIO


class MsgClientResetForgottenPassword4:
    """
    Client request to reset forgotten password (version 4).
    EMsg: 5551 (ClientResetForgottenPassword4)

    Body layout:
        uint8   (must be 0)
        string  accountName (null-terminated)
        string  secretQuestionAnswer (null-terminated)
        string  newPassword (null-terminated)
        uint8   (must be 0)
        string  forgottenPasswordEmailCode (null-terminated)
    """

    def __init__(self):
        self.account_name = ""
        self.secret_question_answer = ""
        self.new_password = ""
        self.forgotten_password_email_code = ""

    def deserialize(self, buffer: bytes, offset: int = 0) -> int:
        """
        Parse body from buffer starting at offset.
        Returns new offset after reading the body.
        """
        stream = BytesIO(buffer[offset:])

        # Read first marker byte (should be 0)
        marker1 = struct.unpack('<B', stream.read(1))[0]
        if marker1 != 0:
            raise ValueError(f"Unknown message format: expected 0, got {marker1}")

        # Read null-terminated strings
        self.account_name = self._read_string(stream)
        self.secret_question_answer = self._read_string(stream)
        self.new_password = self._read_string(stream)

        # Read second marker byte (should be 0)
        marker2 = struct.unpack('<B', stream.read(1))[0]
        if marker2 != 0:
            raise ValueError(f"Unknown message format: expected 0, got {marker2}")

        self.forgotten_password_email_code = self._read_string(stream)

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
            f"MsgClientResetForgottenPassword4("
            f"account_name='{self.account_name}', "
            f"secret_question_answer='***', "
            f"new_password='***', "
            f"forgotten_password_email_code='{self.forgotten_password_email_code}')"
        )

    def __str__(self):
        return str({
            "account_name": self.account_name,
            "secret_question_answer": "***",
            "new_password": "***",
            "forgotten_password_email_code": self.forgotten_password_email_code,
        })
