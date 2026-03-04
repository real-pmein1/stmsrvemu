from __future__ import annotations
import io
import struct
from steam3.Types.steamid import SteamID
from steam3.Types.steam_types import EIntroducerRouting
from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse


class MSGClientP2PIntroducerMessage:
    """Represents ``EMsg.ClientP2PIntroducerMessage`` packets.

    This packet wraps introducer data that allows the server to forward
    peer-to-peer connection information between two clients.

    Attributes:
        client_obj (Client): Owner of the packet.
        steam_id (SteamID): SteamID of the sending client.
        routing_type (EIntroducerRouting): Type of P2P routing.
        payload (bytes): Raw introducer payload supplied by the client.
        payload_len (int): Number of valid bytes in ``payload``.
    """

    MAX_DATA_SIZE = 1450

    def __init__(self, client_obj, data: bytes | None = None, version: int | None = None):
        self.client_obj = client_obj
        self.steam_id = SteamID(0)
        self.routing_type = EIntroducerRouting.k_eRouteP2PFileShare
        self.payload = b""
        self.payload_len = 0
        if data:
            self.deserialize(data)

    def deserialize(self, data: bytes) -> None:
        """Populate the instance from binary data.

        Args:
            data (bytes): Serialized ``MsgClientP2PIntroducerData_t`` structure.
        """
        if len(data) < 8 + 4 + 4:
            raise ValueError("Introducer message too short")
        idx = 0
        steam_raw, = struct.unpack_from("<Q", data, idx)
        idx += 8
        self.steam_id = SteamID.from_raw(steam_raw)
        routing_raw, = struct.unpack_from("<I", data, idx)
        idx += 4
        self.routing_type = EIntroducerRouting(routing_raw)
        self.payload_len, = struct.unpack_from("<I", data, len(data) - 4)
        if self.payload_len > self.MAX_DATA_SIZE:
            raise ValueError("payload length exceeds maximum")
        start = idx
        end = start + self.payload_len
        self.payload = data[start:end]

    def to_clientmsg(self) -> CMResponse:
        """Serialize the object into a ``CMResponse``."""
        buf = io.BytesIO()
        buf.write(struct.pack("<Q", int(self.steam_id)))
        buf.write(struct.pack("<I", int(self.routing_type)))
        payload = self.payload[: self.payload_len]
        buf.write(payload)
        if self.payload_len < self.MAX_DATA_SIZE:
            buf.write(b"\x00" * (self.MAX_DATA_SIZE - self.payload_len))
        buf.write(struct.pack("<I", self.payload_len))
        packet = CMResponse(eMsgID=EMsg.ClientP2PIntroducerMessage, client_obj=self.client_obj)
        packet.data = buf.getvalue()
        packet.length = len(packet.data)
        return packet

    def to_protobuf(self):  # pragma: no cover - legacy packet has no protobuf
        raise NotImplementedError
