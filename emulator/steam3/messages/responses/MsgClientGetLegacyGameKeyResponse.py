import struct

from steam3.Types.emsg import EMsg
from steam3.Types.steam_types import EResult
from steam3.cm_packet_utils import CMResponse


class MsgClientGetLegacyGameKeyResponse:
    """
    Legacy game key response message (server to client).
    EMsg: 785 (ClientGetLegacyGameKeyResponse)

    Body layout:
        int32   m_nAppID (4 bytes)
        int32   m_EResult (4 bytes) - EResult enum
        int32   m_cubKey (4 bytes)
        char[]  key (variable, null-terminated string based on m_cubKey)
    """

    HEADER_FORMAT = "<iiI"
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
    MAX_KEY_SIZE = 64  # Based on assertion in client code

    def __init__(self, client_obj=None, app_id: int = 0, result: EResult = EResult.Fail, key: str = ""):
        self.client_obj = client_obj
        self.app_id = app_id
        self.result = result
        self.key = key

    def deserialize(self, buffer: bytes, offset: int = 0) -> int:
        """
        Parse body from buffer starting at offset.
        Returns new offset after reading the body.
        """
        if len(buffer) < offset + self.HEADER_SIZE:
            raise ValueError(
                f"Buffer too small for MsgClientGetLegacyGameKeyResponse header: need {self.HEADER_SIZE} bytes"
            )

        self.app_id, raw_result, key_size = struct.unpack_from(
            self.HEADER_FORMAT, buffer, offset
        )
        self.result = EResult(raw_result)
        offset += self.HEADER_SIZE

        # Read the key string if result is OK
        if self.result == EResult.OK and key_size > 0:
            actual_size = min(key_size, self.MAX_KEY_SIZE)
            if len(buffer) >= offset + actual_size:
                key_bytes = buffer[offset:offset + actual_size]
                self.key = key_bytes.rstrip(b'\x00').decode('utf-8', errors='replace')
                offset += actual_size

        return offset

    def to_clientmsg(self) -> CMResponse:
        """
        Serialize body into a CMResponse packet.
        """
        packet = CMResponse(eMsgID=EMsg.ClientGetLegacyGameKeyResponse, client_obj=self.client_obj)

        key_bytes = (self.key + '\x00').encode('utf-8')
        key_size = len(key_bytes)

        packet.data = struct.pack(
            self.HEADER_FORMAT,
            self.app_id,
            int(self.result),
            key_size
        )

        # Append the key if result is OK
        if self.result == EResult.OK:
            packet.data += key_bytes

        packet.length = len(packet.data)
        return packet

    def to_bytes(self) -> bytes:
        """
        Serialize body to raw bytes.
        """
        key_bytes = (self.key + '\x00').encode('utf-8')
        key_size = len(key_bytes)

        data = struct.pack(
            self.HEADER_FORMAT,
            self.app_id,
            int(self.result),
            key_size
        )

        if self.result == EResult.OK:
            data += key_bytes

        return data

    def __repr__(self):
        return (
            f"MsgClientGetLegacyGameKeyResponse("
            f"app_id={self.app_id}, "
            f"result={self.result}, "
            f"key='***')"
        )

    def __str__(self):
        return str({
            "app_id": self.app_id,
            "result": int(self.result),
            "result_name": getattr(self.result, "name", str(self.result)),
            "key_length": len(self.key),
        })
