"""
MsgChannelEncryptRequest - Server -> Client encryption handshake request

From IDA analysis of steamclient.so CNetFilterEncryption::RecvMsgChannelEncryptRequest:

MsgHdr_t (20 bytes):
    - m_EMsg: int32 (0x517 = ChannelEncryptRequest)
    - m_JobIDTarget: int64 (-1)
    - m_JobIDSource: int64 (-1)

MsgChannelEncryptRequest_t (8 bytes):
    - m_unProtocolVer: uint32 (protocol version, typically 1)
    - m_EUniverse: int32 (universe type: 1=Public, 2=Beta, etc.)

Total packet size: 28 bytes
"""
import struct
from io import BytesIO

from steam3.Types.emsg import EMsg


class MsgChannelEncryptRequest:
    """
    Server sends this to client to initiate encrypted channel handshake.

    The client will respond with MsgChannelEncryptResponse containing
    an RSA-encrypted session key.
    """
    EMSG = EMsg.ChannelEncryptRequest  # 0x517 = 1303
    HEADER_SIZE = 20
    BODY_SIZE = 8
    TOTAL_SIZE = 28

    def __init__(self, protocol_version: int = 1, universe: int = 1):
        """
        Initialize the ChannelEncryptRequest message.

        Args:
            protocol_version: Protocol version (default 1, max supported by client)
            universe: Steam universe (1=Public, 2=Beta, 3=Internal, 4=Dev)
        """
        # Header fields
        self.emsg = self.EMSG
        self.target_job_id = -1  # int64, -1 means no job
        self.source_job_id = -1  # int64, -1 means no job

        # Body fields
        self.protocol_version = protocol_version
        self.universe = universe

    def serialize(self) -> bytes:
        """
        Serialize the message to bytes.

        Returns:
            28 bytes: 20-byte header + 8-byte body
        """
        stream = BytesIO()

        # MsgHdr_t header (20 bytes)
        # Format: <I = uint32 (emsg), q = int64 (target_job_id), q = int64 (source_job_id)
        stream.write(struct.pack('<Iqq',
            self.emsg,
            self.target_job_id,
            self.source_job_id
        ))

        # MsgChannelEncryptRequest_t body (8 bytes)
        # Format: <I = uint32 (protocol_version), i = int32 (universe)
        stream.write(struct.pack('<Ii',
            self.protocol_version,
            self.universe
        ))

        return stream.getvalue()

    @classmethod
    def deserialize(cls, data: bytes) -> 'MsgChannelEncryptRequest':
        """
        Deserialize bytes to a MsgChannelEncryptRequest object.

        Args:
            data: Raw packet bytes (at least 28 bytes)

        Returns:
            MsgChannelEncryptRequest instance
        """
        if len(data) < cls.TOTAL_SIZE:
            raise ValueError(f"Data too short: expected {cls.TOTAL_SIZE} bytes, got {len(data)}")

        stream = BytesIO(data)

        # Parse header
        emsg, target_job_id, source_job_id = struct.unpack('<Iqq', stream.read(20))

        # Parse body
        protocol_version, universe = struct.unpack('<Ii', stream.read(8))

        instance = cls(protocol_version=protocol_version, universe=universe)
        instance.target_job_id = target_job_id
        instance.source_job_id = source_job_id

        return instance

    def __repr__(self) -> str:
        return (f"MsgChannelEncryptRequest("
                f"protocol_version={self.protocol_version}, "
                f"universe={self.universe})")
