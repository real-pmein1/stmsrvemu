"""
SNetConnectSuccessMsg - Server -> Client connection Accept message

From IDA analysis of steamclient.so CUDPConnection::OnConnectAccept:

When the server receives a valid Connect (type 0x03) with the correct
unmasked challenge, it responds with Accept (type 0x04) to confirm the
connection is established.

Message structure:
    CMPacket header (36 bytes for UDP): packetid = 0x04 (Accept)
    Payload (0 or 8 bytes):
        - steam_id: uint64 (optional, server's steam ID)

The client transitions to connected state upon receiving this message.

Server flow (from tinserver analysis):
1. Client sends ChallengeReq (type 0x01) - seq=1, ack=0
2. Server sends Challenge (type 0x02) - seq=1, ack=1, data=challenge^MASK + load
3. Client sends Connect (type 0x03) - seq=1 or 2, ack=1, data=unmasked challenge
4. Server validates challenge and sends Accept (type 0x04) - seq=2, ack=client_seq
"""
import struct
from io import BytesIO

from steam3.messages.SNetMsgBase import ESNetMsg


class SNetConnectSuccessMsg:
    """
    Accept message sent by server after validating challenge.

    This confirms the connection is established. The payload can optionally
    include the server's steam ID, though the current implementation sends
    an empty payload which is also valid.
    """
    ESNET_MSG = ESNetMsg.Accept  # 0x04

    def __init__(self, steam_id: int = None):
        """
        Initialize the ConnectSuccess message.

        Args:
            steam_id: Optional server steam ID (uint64). If None, empty payload.
        """
        self.steam_id = steam_id

    def serialize(self) -> bytes:
        """
        Serialize the message payload to bytes.

        Returns:
            Empty bytes if no steam_id, otherwise 8-byte steam_id
        """
        if self.steam_id is not None:
            return struct.pack('<Q', self.steam_id)
        return b''

    @classmethod
    def deserialize(cls, data: bytes) -> 'SNetConnectSuccessMsg':
        """
        Deserialize bytes to a SNetConnectSuccessMsg object.

        Args:
            data: Raw payload bytes (0 or 8+ bytes)

        Returns:
            SNetConnectSuccessMsg instance
        """
        steam_id = None
        if len(data) >= 8:
            steam_id, = struct.unpack('<Q', data[:8])
        return cls(steam_id=steam_id)

    def __repr__(self) -> str:
        if self.steam_id is not None:
            return f"SNetConnectSuccessMsg(steam_id=0x{self.steam_id:016X})"
        return "SNetConnectSuccessMsg()"
