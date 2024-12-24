import struct


class MsgClientServiceCall:
    """
    Python equivalent of MsgClientServiceCall_t, parses and serializes a message.
    """

    def __init__(self):
        """
        Initializes the MsgClientServiceCall with default values.
        """
        self.call_handle = 0
        self.module_crc = 0
        self.function_id = 0
        self.max_out = 0
        self.flags = 0
        self.extra_bytes = b""

    @classmethod
    def from_bytes(cls, data):
        """
        Parses a byte string to populate the message fields.

        :param data: Byte string containing the serialized message.
        :return: An instance of MsgClientServiceCall.
        """
        # Check minimum size required for parsing
        if len(data) < 17:
            raise ValueError("Data is too short to parse MsgClientServiceCall_t")

        instance = cls()

        # Parse main fields (17 bytes)
        (
            instance.call_handle,
            instance.module_crc,
            instance.function_id,
            instance.max_out,
            instance.flags,
        ) = struct.unpack_from('<IIIIB', data, 0)

        # Check for extra bytes
        if len(data) > 17:
            instance.extra_bytes = data[17:]

        return instance

    def to_bytes(self):
        """
        Serializes the message fields into a byte string.

        :return: Byte string containing the serialized message.
        """
        # Pack main fields
        main_fields = struct.pack(
            '<IIIIB',
            self.call_handle,
            self.module_crc,
            self.function_id,
            self.max_out,
            self.flags,
        )

        # Append any extra bytes
        return main_fields + self.extra_bytes

    def __str__(self):
        """
        Returns a human-readable string representation of the message.

        :return: String representation of the MsgClientServiceCall.
        """
        extra_bytes_str = self.extra_bytes.hex() if self.extra_bytes else "None"
        return (
            f"MsgClientServiceCall(\n"
            f"  call_handle={self.call_handle},\n"
            f"  module_crc={self.module_crc},\n"
            f"  function_id={self.function_id},\n"
            f"  max_out={self.max_out},\n"
            f"  flags={self.flags},\n"
            f"  extra_bytes={extra_bytes_str}\n"
            f")"
        )