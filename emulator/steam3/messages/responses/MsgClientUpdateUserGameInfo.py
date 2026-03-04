import struct

from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse


class MsgClientUpdateUserGameInfo:
    """
    MsgClientUpdateUserGameInfo_t

    Inferred body layout:
        uint64 m_ulGameID
        uint64 m_steamIDGS
        uint32 m_unGameIP
        uint16 m_usGamePort
        uint16 _pad0              (alignment)
        uint32 m_cubToken         (bytes of var-data token)

    Followed by var-data:
        uint8 token[m_cubToken]

    Notes:
    - Token is stored in the var-data area (PubVarData/CubVarData).
    - The receiver validates CubVarData() >= m_cubToken before reading token.
    """

    BODY_FORMAT = "<QQIHHI"
    BODY_SIZE = struct.calcsize(BODY_FORMAT)

    # Not shown in your snippet, but it's smart to cap this.
    # Steam tokens are typically not enormous.
    MAX_TOKEN = 4096

    def __init__(
        self,
        client_obj,
        game_id: int = 0,
        steamid_gs: int = 0,
        game_ip: int = 0,
        game_port: int = 0,
        token: bytes = b"",
    ):
        self.client_obj = client_obj

        self.m_ulGameID = int(game_id)
        self.m_steamIDGS = int(steamid_gs)
        self.m_unGameIP = int(game_ip) & 0xFFFFFFFF
        self.m_usGamePort = int(game_port) & 0xFFFF

        self.token = token or b""
        self.m_cubToken = len(self.token)

    def deSerialize(self, buffer: bytes, offset: int = 0) -> int:
        """
        Parse body + token var-data from `buffer`.
        Returns new offset after consuming message.
        """
        if len(buffer) < offset + self.BODY_SIZE:
            raise ValueError(
                f"Buffer too small for MsgClientUpdateUserGameInfo body: need {self.BODY_SIZE} bytes"
            )

        (self.m_ulGameID,
         self.m_steamIDGS,
         self.m_unGameIP,
         self.m_usGamePort,
         _pad0,
         self.m_cubToken) = struct.unpack_from(self.BODY_FORMAT, buffer, offset)

        offset += self.BODY_SIZE

        if self.m_cubToken > self.MAX_TOKEN:
            raise ValueError(f"Token too large: {self.m_cubToken} > {self.MAX_TOKEN}")

        end = offset + self.m_cubToken
        if len(buffer) < end:
            raise ValueError(
                f"Buffer too small for token var-data: need {self.m_cubToken} bytes, have {len(buffer) - offset}"
            )

        self.token = buffer[offset:end]
        offset = end
        return offset

    def to_clientmsg(self) -> CMResponse:
        """
        Serialize body + token var-data into a CMResponse packet.
        """
        self.m_cubToken = len(self.token)

        if self.m_cubToken > self.MAX_TOKEN:
            raise ValueError(f"Token too large to send: {self.m_cubToken} > {self.MAX_TOKEN}")

        packet = CMResponse(eMsgID=EMsg.ClientUpdateUserGameInfo, client_obj=self.client_obj)

        body = struct.pack(
            self.BODY_FORMAT,
            int(self.m_ulGameID),
            int(self.m_steamIDGS),
            int(self.m_unGameIP),
            int(self.m_usGamePort),
            0,  # _pad0
            int(self.m_cubToken),
        )

        packet.data = body + (self.token or b"")
        packet.length = len(packet.data)
        return packet

    def __str__(self):
        return str({
            "m_ulGameID": self.m_ulGameID,
            "m_steamIDGS": self.m_steamIDGS,
            "m_unGameIP": self.m_unGameIP,
            "m_usGamePort": self.m_usGamePort,
            "m_cubToken": self.m_cubToken,
            "token_hex": self.token.hex(),
        })
