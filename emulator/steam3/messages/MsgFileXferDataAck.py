import struct
from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse

class MsgFileXferDataAck:
    def __init__(self, client_obj=None, data: bytes = None):
        self.client_obj = client_obj
        self.file_transfer_id = 0
        self.bytes_downloaded = 0
        if data:
            self.deserialize(data)

    def deserialize(self, data: bytes):
        self.file_transfer_id, self.bytes_downloaded = struct.unpack('<IQ', data[:12])

    def to_clientmsg(self):
        packet = CMResponse(eMsgID=EMsg.FileXferDataAck, client_obj=self.client_obj)
        packet.data = struct.pack('<IQ', self.file_transfer_id, self.bytes_downloaded)
        packet.length = len(packet.data)
        return packet

    def __str__(self):
        return f"MsgFileXferDataAck(id={self.file_transfer_id}, bytes={self.bytes_downloaded})"

    __repr__ = __str__
