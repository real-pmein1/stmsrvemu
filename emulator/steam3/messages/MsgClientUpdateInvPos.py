import struct
from io import BytesIO


class MsgClientUpdateInvPos:
    """
    EMsg 881 - Client request to update item position.
    Format: item_id(Q) + app_id(I) + new_pos(I)
    """

    def __init__(self, client_obj, data: bytes = None):
        self.item_id = 0
        self.app_id = 0
        self.new_position = 0
        self.client_obj = client_obj

        if data is not None:
            self.deserialize(data)

    def deserialize(self, data: bytes):
        stream = BytesIO(data)
        if len(data) >= 16:
            self.item_id, self.app_id, self.new_position = struct.unpack('<QII', stream.read(16))

    def __repr__(self):
        return f"MsgClientUpdateInvPos(item_id={self.item_id}, app_id={self.app_id}, pos={self.new_position})"
