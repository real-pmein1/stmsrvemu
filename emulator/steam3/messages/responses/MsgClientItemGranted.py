from io import BytesIO

from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse
from steam3.Types.Objects.PersistentItem import PersistentItem


class MsgClientItemGranted:
    """
    EMsg 887 - Notification that an item was granted to the user.
    Used to notify client of new items (drops, trades, etc.)
    """

    def __init__(self, client_obj, item: PersistentItem = None):
        self.item = item
        self.client_obj = client_obj

    def serialize(self) -> bytes:
        if self.item:
            return self.item.serialize_for_item_granted()
        return b''

    def to_clientmsg(self):
        """Build a CMResponse packet."""
        packet = CMResponse(eMsgID=EMsg.ClientItemGranted, client_obj=self.client_obj)
        packet.data = self.serialize()
        packet.length = len(packet.data)
        return packet

    def __repr__(self):
        return f"MsgClientItemGranted(item={self.item})"
