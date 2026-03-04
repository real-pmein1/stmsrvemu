import struct
from io import BytesIO


class MsgClientRequestForgottenPasswordEmail:
    """
    Client request to send forgotten password email.
    EMsg: 5461 (ClientRequestForgottenPasswordEmail3)

    Body layout:
        uint8   unknown (bool flag)
        string  accountName (null-terminated)
        string  passwordTried (null-terminated)
        string  nv1 (null-terminated, unknown purpose)
    """

    def __init__(self):
        self.unknown = False
        self.account_name = ""
        self.password_tried = ""
        self.nv1 = ""

    def deserialize(self, buffer: bytes, offset: int = 0) -> int:
        """
        Parse body from buffer starting at offset.
        Returns new offset after reading the body.
        """
        stream = BytesIO(buffer[offset:])

        # Read unknown flag byte
        self.unknown = struct.unpack('<B', stream.read(1))[0] != 0

        # Read null-terminated strings
        self.account_name = self._read_string(stream)
        self.password_tried = self._read_string(stream)
        self.nv1 = self._read_string(stream)

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
            f"MsgClientRequestForgottenPasswordEmail("
            f"unknown={self.unknown}, "
            f"account_name='{self.account_name}', "
            f"password_tried='***', "
            f"nv1='{self.nv1}')"
        )

    def __str__(self):
        return str({
            "unknown": self.unknown,
            "account_name": self.account_name,
            "password_tried": "***",
            "nv1": self.nv1,
        })
