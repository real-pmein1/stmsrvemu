"""
SNetChallengeMsg - Server -> Client challenge message

From IDA analysis of steamclient.so CClientNetworkingAPI::OnReceiveConnectMsg:

When the server receives a ChallengeReq message (type 0x01), it responds with a Challenge
message (type 0x02) containing the challenge XORed with the mask.

Message structure:
    CMPacket header (36 bytes for UDP): packetid = 0x02 (Challenge)
    Payload (8 bytes):
        - challenge: uint32 (challenge XOR CHALLENGE_XOR_KEY)
        - server_load: uint32 (server load indicator)

The client must XOR the received value with CHALLENGE_XOR_KEY to unmask it,
then send the UNMASKED challenge back in Connect (type 0x03).

Server flow (from tinserver analysis):
1. Client sends ChallengeReq (type 0x01) - seq=1, ack=0, length=0
2. Server sends Challenge (type 0x02) - seq=1, ack=1, data=challenge^MASK + load
3. Client sends Connect (type 0x03) - seq=1 or 2, ack=1, length=4, data=unmasked challenge
4. Server validates challenge and sends Accept (type 0x04) - seq=2, ack=client_seq
"""
import struct
from io import BytesIO

from steam3.messages.SNetMsgBase import (
    ESNetMsg, DEFAULT_SERVER_LOAD, get_masked_challenge
)


class SNetChallengeMsg:
    """
    Challenge message sent by server after receiving ChallengeReq.

    The server generates a dynamic challenge value (rotated every 10 seconds)
    and XORs it with CHALLENGE_XOR_KEY before sending. The client must unmask
    and echo back the original challenge value.
    """
    ESNET_MSG = ESNetMsg.Challenge  # 0x02
    PAYLOAD_SIZE = 8  # 4 bytes challenge + 4 bytes server_load

    def __init__(self, challenge: int = None, server_load: int = DEFAULT_SERVER_LOAD):
        """
        Initialize the Challenge message.

        Args:
            challenge: Pre-masked challenge value (if None, uses current dynamic challenge masked)
            server_load: Server load indicator (default: 2)
        """
        # If no challenge provided, get the current masked challenge
        if challenge is None:
            self.challenge = get_masked_challenge()
        else:
            self.challenge = challenge
        self.server_load = server_load

    def serialize(self) -> bytes:
        """
        Serialize the message payload to bytes.

        Returns:
            8 bytes: 4-byte challenge + 4-byte server_load
        """
        return struct.pack('<II', self.challenge, self.server_load)

    @classmethod
    def deserialize(cls, data: bytes) -> 'SNetChallengeMsg':
        """
        Deserialize bytes to a SNetChallengeMsg object.

        Args:
            data: Raw payload bytes (at least 8 bytes)

        Returns:
            SNetChallengeMsg instance
        """
        if len(data) < cls.PAYLOAD_SIZE:
            raise ValueError(f"Data too short: expected {cls.PAYLOAD_SIZE} bytes, got {len(data)}")

        challenge, server_load = struct.unpack('<II', data[:8])
        return cls(challenge=challenge, server_load=server_load)

    def __repr__(self) -> str:
        return (f"SNetChallengeMsg("
                f"challenge=0x{self.challenge:08X}, "
                f"server_load={self.server_load})")
