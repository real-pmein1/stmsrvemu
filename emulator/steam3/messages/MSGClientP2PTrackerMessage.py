from __future__ import annotations
import io
import struct
from steam3.Types.steamid import SteamID
from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse


class MSGClientP2PTrackerMessage:
    """Represents ``EMsg.ClientP2PTrackerMessage`` packets.

    Attributes:
        client_obj (Client): Owner of the packet.
        steam_id (SteamID): SteamID of the sending client.
        payload (bytes): Raw tracker payload.
        payload_len (int): Length of ``payload`` in bytes.
    """

    MAX_DATA_SIZE = 1450

    def __init__(self, client_obj, data: bytes | None = None, version: int | None = None):
        self.client_obj = client_obj
        self.steam_id = SteamID(0)
        self.payload = b""
        self.payload_len = 0
        if data:
            self.deserialize(data)

    def deserialize(self, data: bytes) -> None:
        if len(data) < 8 + 4:
            raise ValueError("Tracker message too short")
        idx = 0
        steam_raw, = struct.unpack_from("<Q", data, idx)
        idx += 8
        self.steam_id = SteamID.from_raw(steam_raw)
        self.payload_len, = struct.unpack_from("<I", data, len(data) - 4)
        if self.payload_len > self.MAX_DATA_SIZE:
            raise ValueError("payload length exceeds maximum")
        start = idx
        end = start + self.payload_len
        self.payload = data[start:end]

    def to_clientmsg(self) -> CMResponse:
        buf = io.BytesIO()
        buf.write(struct.pack("<Q", int(self.steam_id)))
        payload = self.payload[: self.payload_len]
        buf.write(payload)
        if self.payload_len < self.MAX_DATA_SIZE:
            buf.write(b"\x00" * (self.MAX_DATA_SIZE - self.payload_len))
        buf.write(struct.pack("<I", self.payload_len))
        packet = CMResponse(eMsgID=EMsg.ClientP2PTrackerMessage, client_obj=self.client_obj)
        packet.data = buf.getvalue()
        packet.length = len(packet.data)
        return packet

    def to_protobuf(self):  # pragma: no cover - legacy packet has no protobuf
        raise NotImplementedError
