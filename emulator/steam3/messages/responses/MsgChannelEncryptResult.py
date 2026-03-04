"""
MsgChannelEncryptResult - Server -> Client encryption handshake result

From IDA analysis of steamclient.so CNetFilterEncryption::RecvMsgChannelEncryptResult:

MsgHdr_t (20 bytes):
    - m_EMsg: int32 (0x519 = ChannelEncryptResult)
    - m_JobIDTarget: int64 (-1)
    - m_JobIDSource: int64 (-1)

MsgChannelEncryptResult_t (4 bytes):
    - m_EResult: int32 (1 = success, other = failure)

Total packet size: 24 bytes

The client checks if m_EResult == 1:
    - If success (1): Sets handshake state to Complete, cancels wakeup timer
    - If failure: Disconnects with error code 36
"""
import struct
from io import BytesIO

from steam3.Types.emsg import EMsg


class EResult:
    """Common EResult values for encryption handshake."""
    OK = 1
    Fail = 2
    NoConnection = 3
    InvalidPassword = 5
    InvalidProtocolVer = 34
    EncryptionFailure = 35


class MsgChannelEncryptResult:
    """
    Server sends this to client after validating the encrypted session key
    from the client's MsgChannelEncryptResponse.

    If result is 1 (OK), the encrypted channel is established and the client
    proceeds with login. Otherwise, the connection is closed.
    """
    EMSG = EMsg.ChannelEncryptResult  # 0x519 = 1305
    HEADER_SIZE = 20
    BODY_SIZE = 4
    TOTAL_SIZE = 24

    def __init__(self, result: int = EResult.OK):
        """
        Initialize the ChannelEncryptResult message.

        Args:
            result: EResult code (1 = OK/success, other values = failure)
        """
        # Header fields
        self.emsg = self.EMSG
        self.target_job_id = -1  # int64, -1 means no job
        self.source_job_id = -1  # int64, -1 means no job

        # Body fields
        self.result = result

    def serialize(self) -> bytes:
        """
        Serialize the message to bytes.

        Returns:
            24 bytes: 20-byte header + 4-byte body
        """
        stream = BytesIO()

        # MsgHdr_t header (20 bytes)
        # Format: <I = uint32 (emsg), q = int64 (target_job_id), q = int64 (source_job_id)
        stream.write(struct.pack('<Iqq',
            self.emsg,
            self.target_job_id,
            self.source_job_id
        ))

        # MsgChannelEncryptResult_t body (4 bytes)
        # Format: <i = int32 (result)
        stream.write(struct.pack('<i', self.result))

        return stream.getvalue()

    @classmethod
    def deserialize(cls, data: bytes) -> 'MsgChannelEncryptResult':
        """
        Deserialize bytes to a MsgChannelEncryptResult object.

        Args:
            data: Raw packet bytes (at least 24 bytes)

        Returns:
            MsgChannelEncryptResult instance
        """
        if len(data) < cls.TOTAL_SIZE:
            raise ValueError(f"Data too short: expected {cls.TOTAL_SIZE} bytes, got {len(data)}")

        stream = BytesIO(data)

        # Parse header
        emsg, target_job_id, source_job_id = struct.unpack('<Iqq', stream.read(20))

        # Parse body
        result, = struct.unpack('<i', stream.read(4))

        instance = cls(result=result)
        instance.target_job_id = target_job_id
        instance.source_job_id = source_job_id

        return instance

    @property
    def is_success(self) -> bool:
        """Check if the result indicates success."""
        return self.result == EResult.OK

    def __repr__(self) -> str:
        status = "OK" if self.is_success else f"FAIL({self.result})"
        return f"MsgChannelEncryptResult(result={status})"
