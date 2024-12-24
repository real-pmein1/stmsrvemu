import struct


class MsgClientServiceModule:
    """
    Python equivalent of MsgClientServiceModule_t, parses and serializes a message.
    """

    def __init__(self):
        """
        Initializes the MsgClientServiceModule with default values.
        """
        self.module_crc = 0
        self.replaces_crc = 0
        self.module = b""

    @classmethod
    def from_bytes(cls, data):
        """
        Parses a byte string to populate the message fields.

        :param data: Byte string containing the serialized message.
        :return: An instance of MsgClientServiceModule.
        """
        if len(data) < 8:  # Minimum size required for parsing
            raise ValueError("Data is too short to parse MsgClientServiceModule_t")

        instance = cls()

        # Parse the fixed fields (8 bytes)
        instance.module_crc, instance.replaces_crc = struct.unpack_from('<II', data, 0)

        # Any remaining bytes are treated as the `module` binary data
        if len(data) > 8:
            instance.module = data[8:]

        return instance

    def to_bytes(self):
        """
        Serializes the message fields into a byte string.

        :return: Byte string containing the serialized message.
        """
        # Pack the fixed fields
        header = struct.pack('<II', self.module_crc, self.replaces_crc)

        # Append the binary `module` data
        return header + self.module

    def write_module_to_file(self, file_name="survey.dll.05-07-2011"):
        """
        Writes the module binary data to a file.

        :param file_name: The name of the file to write to. Default is 'survey.dll.05-07-2011'.
        """
        if not self.module:
            raise ValueError("No module data to write.")

        with open(file_name, "wb") as file:
            file.write(self.module)

    def __str__(self):
        """
        Returns a human-readable string representation of the message.

        :return: String representation of the MsgClientServiceModule.
        """
        module_hex = self.module.hex() if self.module else "None"
        return (
            f"MsgClientServiceModule(\n"
            f"  module_crc={self.module_crc},\n"
            f"  replaces_crc={self.replaces_crc},\n"
            f"  module={module_hex}\n"
            f")"
        )