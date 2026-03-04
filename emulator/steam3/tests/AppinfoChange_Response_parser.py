import struct

class MsgClientAppInfoChanges:
    def __init__(self):
        self.current_change_number = 0
        self.force_full_update = False
        self.app_ids = []

    def deserialize(self, buffer):
        """
        Deserialize data from the given byte buffer.

        :param buffer: The byte buffer to deserialize.
        """
        offset = 0

        # Read current change number (4 bytes, DWORD)
        self.current_change_number = struct.unpack_from('<I', buffer, offset)[0]
        offset += struct.calcsize('<I')

        # Read app count (4 bytes, DWORD)
        app_count = struct.unpack_from('<I', buffer, offset)[0]
        offset += struct.calcsize('<I')

        # Read force full update flag (1 byte, bool)
        self.force_full_update = struct.unpack_from('<B', buffer, offset)[0] != 0
        offset += struct.calcsize('<B')

        # Read app IDs
        self.app_ids = []
        for _ in range(app_count):
            app_id = struct.unpack_from('<I', buffer, offset)[0]
            self.app_ids.append(app_id)
            offset += struct.calcsize('<I')

        # Check for unprocessed bytes
        if offset < len(buffer):
            print(f"Warning: {len(buffer) - offset} unprocessed bytes remaining in the buffer.")

    def serialize(self):
        """
        Serialize the object into a byte buffer.

        :return: A byte buffer containing serialized data.
        """
        buffer = bytearray()

        # Write current change number (4 bytes, DWORD)
        buffer.extend(struct.pack('<I', self.current_change_number))

        # Write app count (4 bytes, DWORD)
        buffer.extend(struct.pack('<I', len(self.app_ids)))

        # Write force full update flag (1 byte, bool)
        buffer.extend(struct.pack('<B', int(self.force_full_update)))

        # Write app IDs
        for app_id in self.app_ids:
            buffer.extend(struct.pack('<I', app_id))

        return bytes(buffer)


# Example serialized buffer
example_buffer = b'c\x03\x00\x00$\x02\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xefmw\xea\x02\x01\x00\x10\x01\xfc\xdf\x8b\x00#H\x00\x00Y\x00\x00\x00\x002\x00\x00\x00<\x00\x00\x00B\t\x00\x00\x92\t\x00\x00\x93\t\x00\x00\x94\t\x00\x00\x95\t\x00\x00\x9c\t\x00\x00.\x0e\x00\x00\x92\x0e\x00\x00\xfc\x14\x00\x00\xfe\x1f\x00\x00\n#\x00\x00\x0b#\x00\x00\x9a3\x00\x00\x1a;\x00\x00\x90B\x00\x00\x91B\x00\x00*D\x00\x00+D\x00\x00,D\x00\x00-D\x00\x00.D\x00\x00/D\x00\x000D\x00\x001D\x00\x002D\x00\x003D\x00\x00TQ\x00\x00UQ\x00\x00VQ\x00\x00WQ\x00\x00XQ\x00\x00YQ\x00\x00ZQ\x00\x00\xd2U\x00\x00ZZ\x00\x00xZ\x00\x00\x8cZ\x00\x00\xca]\x00\x00nd\x00\x00\x82d\x00\x00r~\x00\x00\xae~\x00\x00\xaf~\x00\x00p\x8f\x00\x00\xa6\x90\x00\x00\xa4\x9c\x00\x00\xcc\x9c\x00\x00\xe2\x9f\x00\x00\xe3\x9f\x00\x00(\xa0\x00\x00\xf8\xa7\x00\x00\xf9\xa7\x00\x00\xc8\xaf\x00\x00\xc9\xaf\x00\x00X\xb1\x00\x00\xa2\xb2\x00\x00\xb0\xb3\x00\x00\xba\xb3\x00\x00r\xba\x00\x00\x04\xbf\x00\x00$\xc2\x00\x00%\xc2\x00\x00\xc8\xc3\x00\x00\xc9\xc3\x00\x00\x1f\x89\x00\x00\xfa\x15\x00\x00v\xa7\x00\x00w\xa7\x00\x00x\xa7\x00\x00y\xa7\x00\x00z\xa7\x00\x00\xe8\xc6\x00\x00\xe9\xc6\x00\x00\xd2\xc3\x00\x00\x88\xa4\x00\x00\xf2\xc6\x00\x00\xf3\xc6\x00\x00\xfb\x15\x00\x00\xfc\x15\x00\x00\xfd\x15\x00\x00\xfc\xc6\x00\x00\xfd\xc6\x00\x00\x06\xc7\x00\x00\x07\xc7\x00\x00\xf5]\x00\x00\xf6]\x00\x00\xf7]\x00\x00'

# Deserialize
msg = MsgClientAppInfoChanges()
msg.deserialize(example_buffer[36:])

print("Deserialized Data:")
print(f"  Current Change Number: {msg.current_change_number}")
print(f"  Force Full Update: {msg.force_full_update}")
print(f"  App IDs: {msg.app_ids}")
