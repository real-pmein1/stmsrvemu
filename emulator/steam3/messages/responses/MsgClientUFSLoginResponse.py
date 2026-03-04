import struct
from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse

class MsgClientUFSLoginResponse:
    """
    Python equivalent of the C++ MsgClientUFSLoginResponse.
    Fields:
      ? result           (int32)
      ? app_ids          (list of uint32)
    """
    def __init__(self, client_obj, data: bytes = None):
        self.result = 0
        self.app_ids = []
        self.client_obj = client_obj
        if data is not None:
            self.deserialize(data)

    def deserialize(self, data: bytes):
        """
        Parse a byte buffer into:
          1) 4-byte little-endian signed result
          2) 4-byte little-endian unsigned app count
          3) that many 4-byte little-endian app IDs
        """
        if len(data) < 8:
            raise ValueError("Message body too short for UFSLoginResponse content.")
        self.result = struct.unpack_from('<i', data)[0]
        app_count = struct.unpack_from('<I', data, 4)[0]
        offset = 8
        self.app_ids = [struct.unpack_from('<I', data, offset + i * 4)[0] for i in range(app_count)]

    def to_protobuf(self):
        packet = CMResponse(eMsgID=EMsg.ClientUFSLoginResponse, client_obj=self.client_obj)
        from steam3.protobufs import steammessages_clientserver_ufs_pb2 as ufs_pb2
        body = ufs_pb2.CMsgClientUFSLoginResponse()
        body.eresult = int(self.result)
        packet.data = body.SerializeToString()
        packet.length = len(packet.data)
        return packet

    def to_clientmsg(self):
        """
        Build a bytes payload:
          1) 4-byte little-endian signed result
          2) 4-byte little-endian unsigned app count
          3) each app ID as 4-byte little-endian unsigned
        """
        packet = CMResponse(eMsgID=EMsg.ClientUFSLoginResponse, client_obj=self.client_obj)

        packet.data = struct.pack('<i', self.result)
        packet.data += struct.pack('<I', len(self.app_ids))
        for app_id in self.app_ids:
            packet.data += struct.pack('<I', app_id)
        packet.length = len(packet.data)
        return packet

    def __str__(self):
        return (
            f"{self.__class__.__name__}("
            f"result={self.result}, "
            f"app_ids={self.app_ids}"
            f")"
        )
