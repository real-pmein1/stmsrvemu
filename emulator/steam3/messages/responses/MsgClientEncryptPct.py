import struct

from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse


class MsgClientEncryptPct:
    """
    Client encrypt percentage message (server to client).
    EMsg: 784 (ClientEncryptPct)

    Body layout:
        int32   m_nPct (encryption percentage)
    """

    BODY_FORMAT = "<i"
    BODY_SIZE = struct.calcsize(BODY_FORMAT)

    def __init__(self, client_obj=None, pct: int = 0):
        self.client_obj = client_obj
        self.pct = pct

    def deserialize(self, buffer: bytes, offset: int = 0) -> int:
        """
        Parse body from buffer starting at offset.
        Returns new offset after reading the body.
        """
        if len(buffer) < offset + self.BODY_SIZE:
            raise ValueError(
                f"Buffer too small for MsgClientEncryptPct: need {self.BODY_SIZE} bytes"
            )

        (self.pct,) = struct.unpack_from(self.BODY_FORMAT, buffer, offset)
        return offset + self.BODY_SIZE

    def to_clientmsg(self) -> CMResponse:
        """
        Serialize body into a CMResponse packet.
        """
        packet = CMResponse(eMsgID=EMsg.ClientEncryptPct, client_obj=self.client_obj)
        packet.data = struct.pack(self.BODY_FORMAT, self.pct)
        packet.length = len(packet.data)
        return packet

    def to_bytes(self) -> bytes:
        """
        Serialize body to raw bytes.
        """
        return struct.pack(self.BODY_FORMAT, self.pct)

    def __repr__(self):
        return f"MsgClientEncryptPct(pct={self.pct})"

    def __str__(self):
        return str({
            "pct": self.pct,
        })
