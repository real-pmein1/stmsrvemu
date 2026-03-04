import struct
from io import BytesIO

from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse


class MsgClientDropItemResponse:
    """
    EMsg 884 - Response to ClientDropItem.
    Format: result(I)
    """

    def __init__(self, client_obj, result: int = 0):
        self.result = result
        self.client_obj = client_obj

    def serialize(self) -> bytes:
        stream = BytesIO()
        stream.write(struct.pack('<I', self.result))
        return stream.getvalue()

    def to_clientmsg(self):
        """Build a CMResponse packet."""
        packet = CMResponse(eMsgID=EMsg.ClientDropItemResponse, client_obj=self.client_obj)
        packet.data = self.serialize()
        packet.length = len(packet.data)
        return packet

    def __repr__(self):
        return f"MsgClientDropItemResponse(result={self.result})"
