import struct
from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse

class MsgClientDFSEndSession:
    def __init__(self, client_obj=None, data: bytes = None):
        self.client_obj = client_obj
        self.eresult = 0
        self.unknown_1 = 1
        self.connection_attempts = 0
        self.connection_completions = 0
        self.transfer_attempts = 0
        self.transfer_completions = 0
        self.transfer_attempt_error = 0
        self.transfer_request_failed = False
        self.transfer_request_error = 0
        if data:
            self.deserialize(data)

    def deserialize(self, data: bytes):
        (self.eresult,
         self.unknown_1,
         self.connection_attempts,
         self.connection_completions,
         self.transfer_attempts,
         self.transfer_completions,
         self.transfer_attempt_error,
         tr_failed,
         self.transfer_request_error) = struct.unpack('<IIIIIIIII', data[:36])
        self.transfer_request_failed = bool(tr_failed)

    def to_clientmsg(self):
        packet = CMResponse(eMsgID=EMsg.ClientDFSEndSession, client_obj=self.client_obj)
        packet.data = struct.pack('<IIIIIIIII',
                                 self.eresult,
                                 self.unknown_1,
                                 self.connection_attempts,
                                 self.connection_completions,
                                 self.transfer_attempts,
                                 self.transfer_completions,
                                 self.transfer_attempt_error,
                                 1 if self.transfer_request_failed else 0,
                                 self.transfer_request_error)
        packet.length = len(packet.data)
        return packet

    def __str__(self):
        return f"MsgClientDFSEndSession(result={self.eresult})"

    __repr__ = __str__
