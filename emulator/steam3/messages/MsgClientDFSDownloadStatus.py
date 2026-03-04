import struct
from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse

class MsgClientDFSDownloadStatus:
    def __init__(self, client_obj=None, data: bytes = None):
        self.client_obj = client_obj
        self.unknown_1 = 1
        self.connection_attempts = 0
        self.connection_completions = 0
        self.transfer_attempts = 0
        self.transfer_completions = 0
        self.packets_count = 0
        self.downloaded_bytes = 0
        self.last_packet_bytes = 0
        self.total_cpu_usage = 0
        self.elapsed_time = 0
        if data:
            self.deserialize(data)

    def deserialize(self, data: bytes):
        (self.unknown_1,
         self.connection_attempts,
         self.connection_completions,
         self.transfer_attempts,
         self.transfer_completions,
         self.packets_count,
         self.downloaded_bytes,
         self.last_packet_bytes,
         self.total_cpu_usage,
         self.elapsed_time) = struct.unpack('<IIIIIIIIIQ', data[:44])

    def to_clientmsg(self):
        packet = CMResponse(eMsgID=EMsg.ClientDFSDownloadStatus, client_obj=self.client_obj)
        packet.data = struct.pack('<IIIIIIIIIQ',
                                 self.unknown_1,
                                 self.connection_attempts,
                                 self.connection_completions,
                                 self.transfer_attempts,
                                 self.transfer_completions,
                                 self.packets_count,
                                 self.downloaded_bytes,
                                 self.last_packet_bytes,
                                 self.total_cpu_usage,
                                 self.elapsed_time)
        packet.length = len(packet.data)
        return packet

    def __str__(self):
        return (f"MsgClientDFSDownloadStatus(downloaded={self.downloaded_bytes}, "
                f"packets={self.packets_count})")

    __repr__ = __str__
