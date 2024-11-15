import struct
from io import BytesIO


class MsgClientSystemIMAck:
    def __init__(self, message_id=0):
        self.message_id = message_id  # The message ID (m_gidMsg)

    @classmethod
    def deserialize(cls, byte_buffer):
        """ Deserializes a byte buffer into a MsgClientSystemIMAck object. """
        stream = BytesIO(byte_buffer)

        # Read the message ID (int64)
        message_id = struct.unpack('<Q', stream.read(8))[0]

        return cls(message_id)