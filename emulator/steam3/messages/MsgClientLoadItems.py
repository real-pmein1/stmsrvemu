import struct
from io import BytesIO


class MsgClientLoadItems:
    """
    EMsg 885 - Client request to load items.
    Format: app_id (uint32)
    """

    def __init__(self, client_obj, data: bytes = None):
        self.app_id = 0
        self.client_obj = client_obj

        if data is not None:
            self.deserialize(data)

    def deserialize(self, data: bytes):
        stream = BytesIO(data)
        if len(data) >= 4:
            self.app_id, = struct.unpack('<I', stream.read(4))

    def __repr__(self):
        return f"MsgClientLoadItems(app_id={self.app_id})"
