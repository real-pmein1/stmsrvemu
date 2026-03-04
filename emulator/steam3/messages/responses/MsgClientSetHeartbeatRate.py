import struct

from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse


class MsgClientSetHeartbeatRate:
    """
    Set heartbeat rate message (server to client).
    EMsg: 755 (ClientSetHeartbeatRate)

    This is sent by the server to tell the client how often to send heartbeats.

    Body layout:
        int32   m_nOutOfGameHeartbeatRateSec (4 bytes) - Heartbeat rate when not in game
        int32   m_nInGameHeartbeatRateSec (4 bytes) - Heartbeat rate when in game
    """

    BODY_FORMAT = "<ii"
    BODY_SIZE = struct.calcsize(BODY_FORMAT)

    def __init__(self, client_obj=None, out_of_game_rate: int = 60, in_game_rate: int = 300):
        self.client_obj = client_obj
        self.out_of_game_rate = out_of_game_rate
        self.in_game_rate = in_game_rate

    def deserialize(self, buffer: bytes, offset: int = 0) -> int:
        """
        Parse body from buffer starting at offset.
        Returns new offset after reading the body.
        """
        if len(buffer) < offset + self.BODY_SIZE:
            raise ValueError(
                f"Buffer too small for MsgClientSetHeartbeatRate: need {self.BODY_SIZE} bytes"
            )

        self.out_of_game_rate, self.in_game_rate = struct.unpack_from(
            self.BODY_FORMAT, buffer, offset
        )
        return offset + self.BODY_SIZE

    def to_clientmsg(self) -> CMResponse:
        """
        Serialize body into a CMResponse packet.
        """
        packet = CMResponse(eMsgID=EMsg.ClientSetHeartbeatRate, client_obj=self.client_obj)
        packet.data = struct.pack(
            self.BODY_FORMAT,
            self.out_of_game_rate,
            self.in_game_rate
        )
        packet.length = len(packet.data)
        return packet

    def to_bytes(self) -> bytes:
        """
        Serialize body to raw bytes.
        """
        return struct.pack(
            self.BODY_FORMAT,
            self.out_of_game_rate,
            self.in_game_rate
        )

    def __repr__(self):
        return (
            f"MsgClientSetHeartbeatRate("
            f"out_of_game_rate={self.out_of_game_rate}, "
            f"in_game_rate={self.in_game_rate})"
        )

    def __str__(self):
        return str({
            "out_of_game_rate": self.out_of_game_rate,
            "in_game_rate": self.in_game_rate,
        })
