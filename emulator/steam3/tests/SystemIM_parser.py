import struct
from io import BytesIO
from enum import Enum

class ESystemIMType(Enum):
    k_ESystemIMRawText = 0x0
    k_ESystemIMInvalidCard = 0x1
    k_ESystemIMRecurringPurchaseFailed = 0x2
    k_ESystemIMCardWillExpire = 0x3
    k_ESystemIMSubscriptionExpired = 0x4
    k_ESystemIMGuestPassReceived = 0x5
    k_ESystemIMGuestPassGranted = 0x6
    k_ESystemIMGiftRevoked = 0x7
    k_ESystemIMTypeMax = 0x8



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

        # Write the message body (null-terminated string)
        stream.write(self.message_body.encode('utf-8') + b'\x00')

        # Write the acknowledgment required flag (bool as 1 byte)
        stream.write(struct.pack('<?', self.ack_required))

        # Write the message ID (int64)
        stream.write(struct.pack('<Q', self.message_id))

        return stream.getvalue()

    @classmethod
    def deserialize(cls, byte_buffer):
        """ Deserializes a byte buffer into a MsgClientSystemIM object. """
        stream = BytesIO(byte_buffer)

        # Read system IM type (int32)
        system_im_type_value = struct.unpack('<I', stream.read(4))[0]

        # Try to get the string representation from the ESystemIMType enum
        try:
            system_im_type_enum = ESystemIMType(system_im_type_value)
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

    @staticmethod
    def _read_null_terminated_string(stream):
        """ Helper method to read a null-terminated string from a byte stream. """
        string_bytes = bytearray()
        while True:
            char = stream.read(1)
            if char == b'\x00':  # Null byte indicates end of string
                break
            string_bytes.extend(char)
        return string_bytes.decode('latin-1')


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


# Example usage of MsgClientSystemIM
"""msg = MsgClientSystemIM(system_im_type=1, message_body="Hello World", ack_required=True, message_id=123456)
serialized_data = msg.serialize()
print(f"Serialized data: {serialized_data}")
"""
packet = b'\xd6\x02\x00\x00t\x8b\x99\x00\x01\x00\x10\x01(\x8d\x0e\x00\x06\x00\x00\x00+\xbd\x00\xfahN@\x01\x01\x00\x00\x00292\x00'



# Deserialize back into a MsgClientSystemIM object
deserialized_msg = MsgClientSystemIM.deserialize(packet[16:])
print(f"Deserialized Message: Type={deserialized_msg.system_im_type}, Body={deserialized_msg.message_body}, AckRequired={deserialized_msg.ack_required}, MessageID={deserialized_msg.message_id}")

# Example usage of MsgClientSystemIMAck
ack_msg = MsgClientSystemIMAck()
ack_serialized_data = b'\xd7\x02\x00\x00$\x02\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xef\x1d\x87\x1e\x01\x01\x00\x10\x01\x80\xff\x07\x00\xfb\x04\x8c\xc1\n`\x80\x01'

deserialized_ack_msg = MsgClientSystemIMAck.deserialize(ack_serialized_data[36:])
print(f"Deserialized Ack Message: MessageID={deserialized_ack_msg.message_id}")