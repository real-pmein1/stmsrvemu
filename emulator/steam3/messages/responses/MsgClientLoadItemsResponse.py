import struct
from io import BytesIO
from typing import List

from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse
from steam3.Types.Objects.PersistentItem import PersistentItem


class MsgClientLoadItemsResponse:
    """
    EMsg 886 - Response to ClientLoadItems.
    Format: result(I) + item_count(I) + items[]
    """

    def __init__(self, client_obj, result: int = 0, app_id: int = 0):
        self.result = result
        self.app_id = app_id  # For reference, not serialized in response
        self.items: List[PersistentItem] = []
        self.client_obj = client_obj

    def add_item(self, item: PersistentItem):
        self.items.append(item)

    def serialize(self) -> bytes:
        """Serialize the response."""
        stream = BytesIO()
        stream.write(struct.pack('<II', self.result, len(self.items)))
        for item in self.items:
            stream.write(item.serialize_for_load_response())
        return stream.getvalue()

    def to_clientmsg(self):
        """Build a CMResponse packet."""
        packet = CMResponse(eMsgID=EMsg.ClientLoadItemsResponse, client_obj=self.client_obj)
        packet.data = self.serialize()
        packet.length = len(packet.data)
        return packet

    def __repr__(self):
        return f"MsgClientLoadItemsResponse(result={self.result}, items={len(self.items)})"
