import struct

class MsgClientAppInfoChanges:
    def __init__(self):
        self.current_change_number = 0
        self.force_full_update = False
        self.app_ids = []

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
