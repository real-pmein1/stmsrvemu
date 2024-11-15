import struct
from io import BytesIO
from enum import Enum

from steam3.Types import steam_types


class MsgClientSystemIM:
    def __init__(self, system_im_type=0, message_body="", ack_required=False, message_id=0):
        self.system_im_type = system_im_type  # Equivalent to m_ESystemIMType in C++
        self.message_body = message_body  # The message body (m_rgchMsgBody in C++)
        self.ack_required = ack_required  # Whether acknowledgment is required (m_bAckRequired)
        self.message_id = message_id  # Unique message ID (m_gidMsg)

    def serialize(self):
        """ Serializes the object to a byte stream. """
        stream = BytesIO()

        # Write the system IM type (int32)
        stream.write(struct.pack('<I', self.system_im_type))

        # Write the message ID (int64)
        stream.write(struct.pack('<Q', self.message_id))

        # Write the acknowledgment required flag (bool as 1 byte)
        stream.write(struct.pack('<I', self.ack_required))

        # Write the message body (null-terminated string)
        stream.write(self.message_body.encode('utf-8') + b'\x00')

        return stream.getvalue()

    @classmethod
    def deserialize(cls, byte_buffer):
        """ Deserializes a byte buffer into a MsgClientSystemIM object. """
        stream = BytesIO(byte_buffer)

        # Read system IM type (int32)
        system_im_type_value = struct.unpack('<I', stream.read(4))[0]

        # Try to get the string representation from the ESystemIMType enum
        try:
            system_im_type_enum = steam_types.SystemIMType(system_im_type_value)
            system_im_type = f"{system_im_type_enum.name} ({system_im_type_value})"
        except ValueError:
            # If the value is not valid in the enum, fall back to just using the number
            system_im_type = f"Unknown ({system_im_type_value})"

        # Read the message ID (int64)
        message_id = struct.unpack('<Q', stream.read(8))[0]

        # Read the acknowledgment required flag (boolean as 1 byte)
        ack_required = struct.unpack('<?', stream.read(1))[0]

        # Read message body (read until null byte)
        message_body = cls._read_null_terminated_string(stream)

        return cls(system_im_type, message_body, ack_required, message_id)