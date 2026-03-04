import struct

from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse


class MsgClientGameConnectDeny:
    """
    Game connect deny message (server to client).
    EMsg: 773 (ClientGameConnectDeny)

    This is sent when a client's connection to a game server is denied.

    Body layout:
        int32   m_nGameID (4 bytes) - App ID of the game
        uint32  m_unGameServerIP (4 bytes) - IP address of game server
        uint16  m_usPortServer (2 bytes) - Port of game server
        uint16  m_bSecure (2 bytes) - Whether server is VAC secured
        uint32  m_uReason (4 bytes) - Denial reason code
    """

    BODY_FORMAT = "<IIHHI"
    BODY_SIZE = struct.calcsize(BODY_FORMAT)

    def __init__(self, client_obj=None, game_id: int = 0, game_server_ip: int = 0,
                 port_server: int = 0, is_secure: bool = False, reason: int = 0):
        self.client_obj = client_obj
        self.game_id = game_id
        self.game_server_ip = game_server_ip
        self.port_server = port_server
        self.is_secure = is_secure
        self.reason = reason

    def deserialize(self, buffer: bytes, offset: int = 0) -> int:
        """
        Parse body from buffer starting at offset.
        Returns new offset after reading the body.
        """
        if len(buffer) < offset + self.BODY_SIZE:
            raise ValueError(
                f"Buffer too small for MsgClientGameConnectDeny: need {self.BODY_SIZE} bytes"
            )

        self.game_id, self.game_server_ip, self.port_server, secure_val, self.reason = struct.unpack_from(
            self.BODY_FORMAT, buffer, offset
        )
        self.is_secure = secure_val != 0
        return offset + self.BODY_SIZE

    def to_clientmsg(self) -> CMResponse:
        """
        Serialize body into a CMResponse packet.
        """
        packet = CMResponse(eMsgID=EMsg.ClientGameConnectDeny, client_obj=self.client_obj)
        packet.data = struct.pack(
            self.BODY_FORMAT,
            self.game_id,
            self.game_server_ip,
            self.port_server,
            1 if self.is_secure else 0,
            self.reason
        )
        packet.length = len(packet.data)
        return packet

    def to_bytes(self) -> bytes:
        """
        Serialize body to raw bytes.
        """
        return struct.pack(
            self.BODY_FORMAT,
            self.game_id,
            self.game_server_ip,
            self.port_server,
            1 if self.is_secure else 0,
            self.reason
        )

    def __repr__(self):
        return (
            f"MsgClientGameConnectDeny("
            f"game_id={self.game_id}, "
            f"game_server_ip={self.game_server_ip}, "
            f"port_server={self.port_server}, "
            f"is_secure={self.is_secure}, "
            f"reason={self.reason})"
        )

    def __str__(self):
        return str({
            "game_id": self.game_id,
            "game_server_ip": self.game_server_ip,
            "port_server": self.port_server,
            "is_secure": self.is_secure,
            "reason": self.reason,
        })
