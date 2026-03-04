"""
MsgChannelEncryptResponse - Client -> Server encryption handshake response

From IDA analysis of steamclient.so CNetFilterEncryption::RecvMsgChannelEncryptRequest:

The client sends this in response to MsgChannelEncryptRequest.

MsgHdr_t (20 bytes):
    - m_EMsg: int32 (0x518 = ChannelEncryptResponse)
    - m_JobIDTarget: int64 (-1)
    - m_JobIDSource: int64 (-1)

MsgChannelEncryptResponse_t (8 bytes):
    - m_unProtocolVer: uint32 (protocol version, typically 1)
    - m_cubEncryptedKey: uint32 (size of the encrypted session key)

Variable data:
    - Encrypted session key (RSA encrypted, typically 128 bytes for 1024-bit key)
    - CRC32 of encrypted key (4 bytes)
    - Padding (4 bytes, zeros)

The client:
1. Generates a 32-byte random session key
2. RSA encrypts it with the public key for the specified universe
3. Computes CRC32 of the encrypted key
4. Sends the response with encrypted key + CRC32 + padding

Minimum packet size: 20 (header) + 8 (body) + 128 (encrypted key) + 8 (crc + padding) = 164 bytes
"""
import struct
from io import BytesIO
import binascii

from steam3.Types.emsg import EMsg


class MsgChannelEncryptResponse:
    """
    Client sends this to server with RSA-encrypted session key.

    Server must:
    1. Validate the CRC32 of the encrypted key
    2. Decrypt the session key using the private RSA key
    3. Store the session key for AES encryption of the channel
    4. Send MsgChannelEncryptResult with success/failure
    """
    EMSG = EMsg.ChannelEncryptResponse  # 0x518 = 1304
    HEADER_SIZE = 20
    BODY_SIZE = 8
    CRC_SIZE = 4
    PADDING_SIZE = 4

    def __init__(self, protocol_version: int = 1, encrypted_key: bytes = b'',
                 crc32: int = 0, block_size: int = 0):
        """
        Initialize the ChannelEncryptResponse message.

        Args:
            protocol_version: Protocol version (typically 1)
            encrypted_key: RSA-encrypted session key bytes
            crc32: CRC32 checksum of the encrypted key
            block_size: Size of the encrypted key (if 0, calculated from encrypted_key)
        """
        # Header fields
        self.emsg = self.EMSG
        self.target_job_id = -1
        self.source_job_id = -1

        # Body fields
        self.protocol_version = protocol_version
        self.encrypted_key = encrypted_key
        self.encrypted_key_size = block_size if block_size else len(encrypted_key)
        self.crc32 = crc32

    def serialize(self) -> bytes:
        """
        Serialize the message to bytes.

        Returns:
            Full packet bytes
        """
        stream = BytesIO()

        # MsgHdr_t header (20 bytes)
        stream.write(struct.pack('<Iqq',
            self.emsg,
            self.target_job_id,
            self.source_job_id
        ))

        # MsgChannelEncryptResponse_t body (8 bytes)
        stream.write(struct.pack('<II',
            self.protocol_version,
            self.encrypted_key_size
        ))

        # Variable data
        stream.write(self.encrypted_key)

        # CRC32 and padding (8 bytes)
        stream.write(struct.pack('<II', self.crc32, 0))

        return stream.getvalue()

    @classmethod
    def deserialize(cls, data: bytes) -> 'MsgChannelEncryptResponse':
        """
        Deserialize bytes to a MsgChannelEncryptResponse object.

        Args:
            data: Raw packet bytes

        Returns:
            MsgChannelEncryptResponse instance
        """
        min_size = cls.HEADER_SIZE + cls.BODY_SIZE
        if len(data) < min_size:
            raise ValueError(f"Data too short: expected at least {min_size} bytes, got {len(data)}")

        stream = BytesIO(data)

        # Parse header
        emsg, target_job_id, source_job_id = struct.unpack('<Iqq', stream.read(20))

        # Parse body
        protocol_version, encrypted_key_size = struct.unpack('<II', stream.read(8))

        # Parse variable data - encrypted key
        encrypted_key = stream.read(encrypted_key_size)

        # Parse CRC32 and padding
        crc32, padding = struct.unpack('<II', stream.read(8))

        instance = cls(
            protocol_version=protocol_version,
            encrypted_key=encrypted_key,
            crc32=crc32,
            block_size=encrypted_key_size
        )
        instance.target_job_id = target_job_id
        instance.source_job_id = source_job_id

        return instance

    def validate_crc(self) -> bool:
        """
        Validate that the CRC32 matches the encrypted key.

        Returns:
            True if CRC32 is valid, False otherwise
        """
        computed_crc = binascii.crc32(self.encrypted_key) & 0xFFFFFFFF
        return computed_crc == self.crc32

    def __repr__(self) -> str:
        return (f"MsgChannelEncryptResponse("
                f"protocol_version={self.protocol_version}, "
                f"encrypted_key_size={self.encrypted_key_size}, "
                f"crc32=0x{self.crc32:08X})")
