"""
SNet Message Base Classes and Enums

From IDA analysis of steamclient.so CSNetSocketMsgHandler::Process:

SNetMsgHeader_t (18 bytes):
    - m_nVersion: byte (offset 0x0) - Protocol version, typically 1
    - m_eSNetMsg: byte (offset 0x1) - Message type (ESNetMsg enum)
    - m_unDestID: uint32 (offset 0x2) - Destination connection ID
    - m_unSrcID: uint32 (offset 0x6) - Source connection ID
    - m_unDestPacketIDToAck: uint32 (offset 0xA) - Last received packet ID to acknowledge
    - m_unSrcPacketID: uint32 (offset 0xE) - Source packet sequence number

Note: The CMPacket class handles the transport-layer header (36 bytes for UDP).
The 'packetid' field in CMPacket corresponds to m_eSNetMsg.
Message payloads go in CMPacket.data field.

Connection Handshake Flow (from tinserver analysis):
    1. Client -> Server: ChallengeReq (0x01) - seq=1, ack=0, length=0
    2. Server -> Client: Challenge (0x02) - seq=1, ack=1, data=challenge^MASK + load
    3. Client -> Server: Connect (0x03) - seq=1 or 2, ack=1, length=4, data=unmasked challenge
    4. Server -> Client: Accept (0x04) - seq=2, ack=client_seq, connection established
    5. After Accept, encrypted Data (0x06) packets can be exchanged
"""
import time
from enum import IntEnum


class ESNetMsg(IntEnum):
    """
    SNet message types from steamclient.so CSNetSocketMsgHandler::Process switch statement.

    These map to CMPacket.packetid values.
    """
    ChallengeReq = 1     # Client -> Server: Initial challenge request (renamed from Connect for clarity)
    Challenge = 2        # Server -> Client: Challenge with XORed value + server load
    Connect = 3          # Client -> Server: Challenge response with unmasked challenge
    Accept = 4           # Server -> Client: Connection established (renamed from ConnectSuccess)
    Disconnect = 5       # Bidirectional: Disconnect notification
    Data = 6             # Bidirectional: Normal data packet
    Datagram = 7         # Heartbeat/keepalive


# Constants used in handshake
SNET_PROTOCOL_VERSION = 1
CHALLENGE_XOR_KEY = 0xA426DF2B   # XOR key (NET_SOCKET_CHALLENGE_MASK from tinserver)
DEFAULT_SERVER_LOAD = 2          # Default server load indicator
CHALLENGE_ROTATION_INTERVAL = 10  # Rotate challenge every 10 seconds (like tinserver)


class ChallengeManager:
    """
    Manages dynamic challenge generation similar to tinserver.

    Tinserver rotates the challenge every 10 seconds and keeps the previous
    challenge valid for a brief overlap period to handle race conditions.
    """

    _instance = None
    _current_challenge = None
    _previous_challenge = None
    _last_rotation_time = 0

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize with a fresh challenge."""
        self._rotate_challenge()

    def _generate_challenge(self) -> int:
        """
        Generate a new challenge value based on current time.

        Uses time-based generation similar to tinserver's approach.
        """
        # Use time-based seed for challenge generation
        current_time = int(time.time())
        # Mix with a constant to create variety
        challenge = ((current_time * 0x41C64E6D) + 0x3039) & 0xFFFFFFFF
        return challenge if challenge != 0 else 0x12345678

    def _rotate_challenge(self):
        """Rotate to a new challenge, keeping the old one as previous."""
        self._previous_challenge = self._current_challenge
        self._current_challenge = self._generate_challenge()
        self._last_rotation_time = time.time()

    def get_challenge(self) -> int:
        """
        Get the current challenge value, rotating if necessary.

        Returns:
            Current challenge value (unmasked)
        """
        current_time = time.time()
        if current_time - self._last_rotation_time >= CHALLENGE_ROTATION_INTERVAL:
            self._rotate_challenge()
        return self._current_challenge

    def validate_challenge(self, challenge: int) -> bool:
        """
        Validate a challenge value from a client.

        Accepts both current and previous challenge to handle race conditions
        during rotation (like tinserver does).

        Args:
            challenge: The unmasked challenge value from client

        Returns:
            True if challenge is valid (matches current or previous)
        """
        current_time = time.time()
        if current_time - self._last_rotation_time >= CHALLENGE_ROTATION_INTERVAL:
            self._rotate_challenge()

        if challenge == self._current_challenge:
            return True
        if self._previous_challenge is not None and challenge == self._previous_challenge:
            return True
        return False

    def get_masked_challenge(self) -> int:
        """
        Get the current challenge XORed with the mask (for sending to client).

        Returns:
            Challenge value XORed with CHALLENGE_XOR_KEY
        """
        return self.get_challenge() ^ CHALLENGE_XOR_KEY


# Global challenge manager instance
challenge_manager = ChallengeManager()


def get_current_challenge() -> int:
    """Get the current unmasked challenge value."""
    return challenge_manager.get_challenge()


def get_masked_challenge() -> int:
    """Get the current challenge XORed with mask (for Challenge packet)."""
    return challenge_manager.get_masked_challenge()


def validate_challenge(challenge: int) -> bool:
    """Validate an unmasked challenge value from client."""
    return challenge_manager.validate_challenge(challenge)
