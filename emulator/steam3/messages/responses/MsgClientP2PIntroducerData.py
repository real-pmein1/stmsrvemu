import struct
from enum import IntEnum

from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse


class EIntroducerRouting(IntEnum):
    """Routing type for P2P introducer messages."""
    k_eRouteP2P = 0
    k_eRouteP2PVoiceChat = 1
    k_eRouteP2PNetworking = 2


class MsgClientP2PIntroducerData:
    """
    P2P introducer data message (server to client).
    EMsg: 813 (ClientP2PIntroducerMessage)

    Body layout:
        uint64  m_unSteamID (8 bytes)
        int32   m_ERoutingType (4 bytes) - EIntroducerRouting enum
        uint8   m_Data[1450] (1450 bytes)
        uint32  m_cubDataLen (4 bytes)
    """

    DATA_SIZE = 1450
    BODY_FORMAT = f"<Qi{DATA_SIZE}sI"
    BODY_SIZE = struct.calcsize(BODY_FORMAT)

    def __init__(self, client_obj=None, steam_id: int = 0, routing_type: EIntroducerRouting = EIntroducerRouting.k_eRouteP2P):
        self.client_obj = client_obj
        self.steam_id = steam_id
        self.routing_type = routing_type
        self.data = b""
        self.data_len = 0

    def deserialize(self, buffer: bytes, offset: int = 0) -> int:
        """
        Parse body from buffer starting at offset.
        Returns new offset after reading the body.
        """
        if len(buffer) < offset + self.BODY_SIZE:
            raise ValueError(
                f"Buffer too small for MsgClientP2PIntroducerData: need {self.BODY_SIZE} bytes"
            )

        self.steam_id, routing_type, raw_data, self.data_len = struct.unpack_from(
            self.BODY_FORMAT, buffer, offset
        )
        self.routing_type = EIntroducerRouting(routing_type)
        # Only keep the actual data based on data_len
        self.data = raw_data[:self.data_len] if self.data_len <= self.DATA_SIZE else raw_data

        return offset + self.BODY_SIZE

    def to_clientmsg(self) -> CMResponse:
        """
        Serialize body into a CMResponse packet.
        """
        packet = CMResponse(eMsgID=EMsg.ClientP2PIntroducerMessage, client_obj=self.client_obj)
        # Pad data to fixed size
        padded_data = self.data.ljust(self.DATA_SIZE, b'\x00')[:self.DATA_SIZE]
        packet.data = struct.pack(
            self.BODY_FORMAT,
            self.steam_id,
            int(self.routing_type),
            padded_data,
            len(self.data)
        )
        packet.length = len(packet.data)
        return packet

    def to_bytes(self) -> bytes:
        """
        Serialize body to raw bytes.
        """
        padded_data = self.data.ljust(self.DATA_SIZE, b'\x00')[:self.DATA_SIZE]
        return struct.pack(
            self.BODY_FORMAT,
            self.steam_id,
            int(self.routing_type),
            padded_data,
            len(self.data)
        )

    def __repr__(self):
        return (
            f"MsgClientP2PIntroducerData("
            f"steam_id={self.steam_id}, "
            f"routing_type={self.routing_type.name}, "
            f"data_len={self.data_len})"
        )

    def __str__(self):
        return str({
            "steam_id": self.steam_id,
            "routing_type": int(self.routing_type),
            "routing_type_name": self.routing_type.name,
            "data_len": self.data_len,
        })
