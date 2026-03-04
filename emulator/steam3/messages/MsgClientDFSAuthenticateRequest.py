import struct
from io import BytesIO
from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse

class MsgClientDFSAuthenticateRequest:
    def __init__(self, client_obj=None, data: bytes = None):
        self.client_obj = client_obj
        self.download_file_url = ""
        self.unknown_1 = 1
        self.client_version = 0
        if data:
            self.deserialize(data)

    def deserialize(self, data: bytes):
        stream = BytesIO(data)
        raw = stream.read(128)
        self.download_file_url = raw.split(b"\x00", 1)[0].decode('utf-8', 'ignore')
        self.unknown_1, self.client_version = struct.unpack('<II', stream.read(8))

    def to_clientmsg(self):
        packet = CMResponse(eMsgID=EMsg.ClientDFSAuthenticateRequest,
                            client_obj=self.client_obj)
        url_bytes = self.download_file_url.encode('utf-8')[:127]
        url_bytes = url_bytes.ljust(128, b'\x00')
        packet.data = url_bytes + struct.pack('<II', self.unknown_1, self.client_version)
        packet.length = len(packet.data)
        return packet

    def __str__(self):
        return (f"MsgClientDFSAuthenticateRequest(url={self.download_file_url!r}, "
                f"unknown_1={self.unknown_1}, client_version={self.client_version})")

    __repr__ = __str__
