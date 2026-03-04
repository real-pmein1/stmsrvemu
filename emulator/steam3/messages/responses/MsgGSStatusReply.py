import struct

from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse


class MsgGSStatusReply:
    """
    Game server status reply message (server to client).
    EMsg: 774 (GSStatusReply)

    This is sent to game servers to indicate their VAC secure status.

    Body layout:
        uint32  m_bSecure (4 bytes) - 1 if server is VAC secured, 0 otherwise
    """

    BODY_FORMAT = "<I"
    BODY_SIZE = struct.calcsize(BODY_FORMAT)

    def __init__(self, client_obj=None, is_secure: bool = False):
        self.client_obj = client_obj
        self.is_secure = is_secure

    def deserialize(self, buffer: bytes, offset: int = 0) -> int:
        """
        Parse body from buffer starting at offset.
        Returns new offset after reading the body.
        """
        if len(buffer) < offset + self.BODY_SIZE:
            raise ValueError(
                f"Buffer too small for MsgGSStatusReply: need {self.BODY_SIZE} bytes"
            )

        (secure_val,) = struct.unpack_from(self.BODY_FORMAT, buffer, offset)
        self.is_secure = secure_val != 0
        return offset + self.BODY_SIZE

    def to_clientmsg(self) -> CMResponse:
        """
        Serialize body into a CMResponse packet.
        """
        packet = CMResponse(eMsgID=EMsg.GSStatusReply, client_obj=self.client_obj)
        packet.data = struct.pack(self.BODY_FORMAT, 1 if self.is_secure else 0)
        packet.length = len(packet.data)
        return packet

    def to_bytes(self) -> bytes:
        """
        Serialize body to raw bytes.
        """
        return struct.pack(self.BODY_FORMAT, 1 if self.is_secure else 0)

    def __repr__(self):
        return f"MsgGSStatusReply(is_secure={self.is_secure})"

    def __str__(self):
        return str({
            "is_secure": self.is_secure,
        })
