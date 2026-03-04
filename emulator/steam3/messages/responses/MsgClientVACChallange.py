import struct

from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse


class MsgClientVACChallenge:
    """
    MsgClientVACChallenge_t

    Body layout (assumed from decomp behavior):
        uint64 m_nGameID
        uint32 m_cubChallenge
        uint8  challenge[m_cubChallenge]   (var data, max 0x800)

    This matches the usage of:
        Body()->m_nGameID
        Body()->m_cubChallenge
        PubVarData() -> challenge bytes
    """

    BODY_FORMAT = "<QI"  # uint64 gameid, uint32 size
    BODY_SIZE = struct.calcsize(BODY_FORMAT)
    MAX_CHALLENGE = 0x800

    def __init__(self, client_obj, game_id: int = 0, challenge: bytes = b""):
        self.client_obj = client_obj
        self.m_nGameID = int(game_id)
        self.challenge = challenge or b""
        self.m_cubChallenge = len(self.challenge)

    def deSerialize(self, buffer: bytes, offset: int = 0) -> int:
        """
        Parse body from `buffer` starting at `offset`.
        Returns new offset after the message body (including var data).
        """
        if len(buffer) < offset + self.BODY_SIZE:
            raise ValueError(f"Buffer too small for MsgClientVACChallenge header: need {self.BODY_SIZE} bytes")

        self.m_nGameID, self.m_cubChallenge = struct.unpack_from(self.BODY_FORMAT, buffer, offset)
        offset += self.BODY_SIZE

        if self.m_cubChallenge > self.MAX_CHALLENGE:
            raise ValueError(
                f"VAC challenge too large: {self.m_cubChallenge} > {self.MAX_CHALLENGE}"
            )

        end = offset + self.m_cubChallenge
        if len(buffer) < end:
            raise ValueError(
                f"Buffer too small for VAC challenge data: need {self.m_cubChallenge} bytes, have {len(buffer) - offset}"
            )

        self.challenge = buffer[offset:end]
        offset = end
        return offset

    def to_clientmsg(self):
        """
        Serialize into a CMResponse packet with body + var data.
        """
        # keep m_cubChallenge consistent with actual payload
        self.m_cubChallenge = len(self.challenge)

        if self.m_cubChallenge > self.MAX_CHALLENGE:
            raise ValueError(
                f"VAC challenge too large to send: {self.m_cubChallenge} > {self.MAX_CHALLENGE}"
            )

        packet = CMResponse(eMsgID=EMsg.ClientVACChallenge, client_obj=self.client_obj)

        header = struct.pack(self.BODY_FORMAT, int(self.m_nGameID), int(self.m_cubChallenge))
        packet.data = header + (self.challenge or b"")
        packet.length = len(packet.data)
        return packet

    def __str__(self):
        return str({
            "m_nGameID": self.m_nGameID,
            "m_cubChallenge": self.m_cubChallenge,
            "challenge_len": len(self.challenge),
            "challenge_hex": self.challenge.hex(),
        })
