import struct
from io import BytesIO


class MsgClientDropItem:
    """
    EMsg 883 - Client request to drop/delete an item.
    Format: item_id(Q) + app_id(I)
    """

    def __init__(self, client_obj, data: bytes = None):
        self.item_id = 0
        self.app_id = 0
        self.client_obj = client_obj

        if data is not None:
            self.deserialize(data)

    def deserialize(self, data: bytes):
        stream = BytesIO(data)
        if len(data) >= 12:
            self.item_id, self.app_id = struct.unpack('<QI', stream.read(12))

    def __repr__(self):
        return f"MsgClientDropItem(item_id={self.item_id}, app_id={self.app_id})"
