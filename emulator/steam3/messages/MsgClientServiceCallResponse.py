import struct


def parse_os_info(data):
    """
    Parses os_info based on the OSVERSIONINFOEX structure.
    """
    if len(data) < 156:
        raise ValueError("os_info data is too short to parse the structure.")

    # Unpack fixed-size fields
    structure_size, major_version, minor_version, build_number, platform_id = struct.unpack_from('<IIIII', data, 0)

    # Extract the CSD Version string (128 bytes)
    csd_version_raw = data[20:148]
    csd_version = csd_version_raw.split(b'\x00', 1)[0].decode('ascii', errors = 'ignore')

    # Unpack remaining fields (8 bytes)
    service_pack_major, service_pack_minor, suite_mask, product_type = struct.unpack_from('<HHHB', data, 148)
    reserved = data[151]

    # Calculate remaining bytes
    total_parsed = 152
    remaining_bytes = data[total_parsed:] if len(data) > total_parsed else None

    return {
            "structure_size":    structure_size,
            "major_version":     major_version,
            "minor_version":     minor_version,
            "build_number":      build_number,
            "platform_id":       platform_id,
            "csd_version":       csd_version,
            "service_pack_major":service_pack_major,
            "service_pack_minor":service_pack_minor,
            "suite_mask":        suite_mask,
            "product_type":      product_type,
            "reserved":          reserved,
            "remaining_bytes":   remaining_bytes.hex() if remaining_bytes else None,
    }


def parse_system_info(data):
    if len(data) < 36:
        raise ValueError("Data is too short to parse the full SYSTEM_INFO structure.")

    # Unpack fields according to SYSTEM_INFO structure
    processor_architecture, reserved = struct.unpack_from('<HH', data, 0)
    page_size = struct.unpack_from('<I', data, 4)[0]
    min_app_address = struct.unpack_from('<I', data, 8)[0]
    max_app_address = struct.unpack_from('<I', data, 12)[0]
    active_processor_mask = struct.unpack_from('<I', data, 16)[0]
    number_of_processors = struct.unpack_from('<I', data, 20)[0]
    processor_type = struct.unpack_from('<I', data, 24)[0]
    allocation_granularity = struct.unpack_from('<I', data, 28)[0]
    processor_level = struct.unpack_from('<H', data, 32)[0]
    processor_revision = struct.unpack_from('<H', data, 34)[0]

    # Map processor architecture to human-readable format
    arch_map = {0:"x86", 9:"x64", 6:"ARM"}
    processor_architecture_str = arch_map.get(processor_architecture, "Unknown")

    return {
            "processor_architecture":processor_architecture_str,
            "reserved":              reserved,
            "page_size":             page_size,
            "min_app_address":       f'0x{min_app_address:08X}',
            "max_app_address":       f'0x{max_app_address:08X}',
            "active_processor_mask": active_processor_mask,
            "number_of_processors":  number_of_processors,
            "processor_type":        processor_type,
            "allocation_granularity":allocation_granularity,
            "processor_level":       processor_level,
            "processor_revision":    processor_revision,
            "remaining_bytes":       None,  # No remaining bytes
    }


class MsgClientServiceCallResponse:
    """
    Python equivalent of MsgClientServiceCallResponse_t, parses and serializes a message.
    """

    def __init__(self):
        """
        Initializes the MsgClientServiceCallResponse with default values.
        """
        self.call_handle = 0
        self.e_call_result = 0
        self.os_version_info_size = 0
        self.system_info_size = 0
        self.os_info = b""
        self.system_info = b""
        self.remaining_bytes = b""

    @classmethod
    def from_bytes(cls, data):
        """
        Parses a byte string to populate the message fields.

        :param data: Byte string containing the serialized message.
        :return: An instance of MsgClientServiceCallResponse.
        """
        if len(data) < 16:  # Minimum size required for parsing
            raise ValueError("Data is too short to parse MsgClientServiceCallResponse_t")

        instance = cls()

        # Parse the fixed fields (16 bytes)
        (
            instance.call_handle,
            instance.e_call_result,
            instance.os_version_info_size,
            instance.system_info_size,
        ) = struct.unpack_from('<IIII', data, 0)

        # Extract the extra bytes
        extra_bytes = data[16:]

        # Parse os_info if size is available
        offset = 0
        if instance.os_version_info_size > 0:
            instance.os_info = extra_bytes[offset:offset + instance.os_version_info_size]
            offset += instance.os_version_info_size
            instance.os_info = parse_os_info(instance.os_info)

            # Parse system_info if size is available
        if instance.system_info_size > 0:
            instance.system_info = extra_bytes[offset:offset + instance.system_info_size]
            offset += instance.system_info_size
            instance.system_info = parse_system_info(instance.system_info)

        # Capture any remaining bytes
        if offset < len(extra_bytes):
            instance.remaining_bytes = extra_bytes[offset:]

        return instance

    def to_bytes(self):
        """
        Serializes the message fields into a byte string.

        :return: Byte string containing the serialized message.
        """
        # Pack the fixed fields
        main_fields = struct.pack(
            '<IIII',
            self.call_handle,
            self.e_call_result,
            self.os_version_info_size,
            self.system_info_size,
        )

        # Append os_info and system_info data
        return main_fields + self.os_info + self.system_info + self.remaining_bytes

    def __str__(self):
        """
        Returns a human-readable string representation of the message.

        :return: String representation of the MsgClientServiceCallResponse.
        """
        remaining_str = self.remaining_bytes.hex() if self.remaining_bytes else "None"
        return (
            f"MsgClientServiceCallResponse(\n"
            f"  call_handle={self.call_handle},\n"
            f"  e_call_result={self.e_call_result},\n"
            f"  os_version_info_size={self.os_version_info_size},\n"
            f"  system_info_size={self.system_info_size},\n"
            f"  os_info={self.os_info if self.os_info else 'None'},\n"
            f"  system_info={self.system_info if self.system_info else 'None'},\n"
            f"  remaining_bytes={remaining_str}\n"
            f")"
        )