import struct
from io import BytesIO
from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse

class MsgFileXferRequest:
    def __init__(self, client_obj=None, data: bytes = None):
        self.client_obj = client_obj
        self.download_file_url = ""
        self.file_transfer_id = 0
        self.file_transfer_protocol = 0
        if data:
            self.deserialize(data)

    def deserialize(self, data: bytes):
        stream = BytesIO(data)
        raw = stream.read(261)
        self.download_file_url = raw.split(b"\x00", 1)[0].decode('utf-8', 'ignore')
        self.file_transfer_id, self.file_transfer_protocol = struct.unpack('<II', stream.read(8))

    def to_clientmsg(self):
        packet = CMResponse(eMsgID=EMsg.FileXferRequest, client_obj=self.client_obj)
        url_bytes = self.download_file_url.encode('utf-8')[:260]
        url_bytes = url_bytes.ljust(261, b'\x00')
        packet.data = url_bytes + struct.pack('<II', self.file_transfer_id, self.file_transfer_protocol)
        packet.length = len(packet.data)
        return packet

    def __str__(self):
        return (f"MsgFileXferRequest(url={self.download_file_url!r}, id={self.file_transfer_id}, "
                f"protocol={self.file_transfer_protocol})")

    __repr__ = __str__
