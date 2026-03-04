import struct
from steam3.Types.emsg import EMsg
from steam3.Types.steam_types import EResult
from steam3.cm_packet_utils import CMResponse

class MsgClientUFSUploadFileResponse:
    """
    Python equivalent of C++ MsgClientUFSUploadFileResponse.
    Fields:
      ? result  (int32 ? EResult)
      ? sha     (20 bytes)
    """
    def __init__(self, client_obj, sourceJobID, targetJobID, data: bytes = None):
        self.client_obj = client_obj
        self.result     = EResult.OK
        self.sha        = b'\x00' * 20
        self.targetJobID      = targetJobID
        self.sourceJobID      = sourceJobID
        if data is not None:
            self.deserialize(data)

    def deserialize(self, data: bytes):
        """
        Parse:
          1) 4-byte little-endian signed result
          2) next 20 bytes as SHA
        """
        if len(data) < 24:
            raise ValueError("Message body too short for UploadFileResponse content.")
        res_int = struct.unpack_from('<i', data)[0]
        self.result = EResult(res_int)
        self.sha = struct.unpack_from('<20s', data, 4)[0]

    def to_protobuf(self):
        packet = CMResponse(eMsgID=EMsg.ClientUFSUploadFileResponse,
                            client_obj=self.client_obj)
        packet.targetJobID = self.sourceJobID
        packet.sourceJobID = self.targetJobID
        from steam3.protobufs import steammessages_clientserver_ufs_pb2 as ufs_pb2
        body = ufs_pb2.CMsgClientUFSUploadFileResponse()
        body.eresult = int(self.result)
        body.sha_file = self.sha
        packet.data = body.SerializeToString()
        packet.length = len(packet.data)
        return packet

    def to_clientmsg(self):
        """
        Build a CMResponse packet:
          1) result (int32 LE)
          2) sha    (20 bytes)
        """
        packet = CMResponse(eMsgID=EMsg.ClientUFSUploadFileResponse,
                            client_obj=self.client_obj)
        packet.targetJobID = self.sourceJobID  # these get flipped because of how the CM packets work
        packet.sourceJobID = self.targetJobID
        packet.data = struct.pack('<i20s', self.result.value, self.sha)
        packet.length = len(packet.data)
        return packet

    def __str__(self):
        sha_hex = self.sha.hex()
        return (
            f"{self.__class__.__name__}("
            f"result={self.result.name}, "
            f"sha={sha_hex}"
            f")"
        )
