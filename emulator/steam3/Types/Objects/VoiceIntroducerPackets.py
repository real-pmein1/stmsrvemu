"""
VoiceIntroducer packet data types for P2P voice chat
Matches C++ VoiceIntroducer packet hierarchy

Classes:
- VoiceIntroducerPacketType: Enum for packet types
- SteamInetAddress: Network address structure
- VoiceCandidate: ICE/STUN candidate information
- PacketBase: Base class for all voice introducer packets
- InitiatorBase: Extends PacketBase with initiator info
- AddCandidate: Client to tracker local candidate packet
"""

from __future__ import annotations
import struct
import logging
from enum import IntEnum
from typing import Optional

log = logging.getLogger("VoiceIntroducerPackets")


class VoiceIntroducerPacketType(IntEnum):
    """Packet types for VoiceIntroducer messages"""
    ClientToTrackerAddLocalCandidates = 0x00
    TrackerToClientRequestConnectionNack = 0x01
    TrackerToClientRelayRemoteCandidates = 0x02


class InetAddressType(IntEnum):
    """Network address types"""
    Null = 0x00
    LoopBack = 0x01
    BroadCast = 0x02
    IP = 0x03


class SteamInetAddress:
    """
    Steam network address structure matching C++ SteamInetAddress

    Binary format (12 bytes):
        - port: 2 bytes (uint16)
        - padding: 2 bytes (alignment)
        - ip: 4 bytes (uint32, big-endian)
        - ip_type: 4 bytes (uint32)
    """

    SIZE = 12

    def __init__(self, ip: int = 0, port: int = 0, ip_type: InetAddressType = InetAddressType.IP):
        self.ip = ip
        self.port = port
        self.ip_type = ip_type

    @classmethod
    def from_string(cls, host: str, port: int) -> SteamInetAddress:
        """Create address from host string and port"""
        parts = host.split('.')
        if len(parts) == 4:
            ip = (int(parts[0]) << 24) | (int(parts[1]) << 16) | (int(parts[2]) << 8) | int(parts[3])
            return cls(ip, port, InetAddressType.IP)
        return cls(0, port, InetAddressType.Null)

    def serialize(self) -> bytes:
        """Serialize to binary format"""
        # Ensure numeric types are properly converted
        return struct.pack('<HHI', int(self.port), 0, int(self.ip)) + struct.pack('<I', int(self.ip_type))

    def deserialize(self, data: bytes, offset: int = 0) -> int:
        """Deserialize from binary data, returns new offset"""
        if len(data) < offset + self.SIZE:
            raise ValueError("Insufficient data for SteamInetAddress")

        self.port, _, self.ip = struct.unpack_from('<HHI', data, offset)
        offset += 8
        ip_type_raw, = struct.unpack_from('<I', data, offset)
        offset += 4
        self.ip_type = InetAddressType(ip_type_raw)

        return offset

    def get_ip_string(self) -> str:
        """Get IP as dotted string"""
        return f"{(self.ip >> 24) & 0xFF}.{(self.ip >> 16) & 0xFF}.{(self.ip >> 8) & 0xFF}.{self.ip & 0xFF}"

    def __repr__(self):
        return f"SteamInetAddress({self.get_ip_string()}:{self.port})"


class VoiceCandidate:
    """
    ICE/STUN candidate information matching C++ Candidate class

    Fields:
        name: Candidate identifier
        protocol: Protocol (UDP/TCP)
        address: IP address string
        port: Port number
        preference: Connection preference (0.0-1.0)
        username: ICE username
        password: ICE password
        type: Candidate type (local/stun/relay)
        network_name: Network interface name
        generation: Generation counter
        nat_type: NAT type classification
    """

    def __init__(self):
        self.name = ""
        self.protocol = "UDP"
        self.address = ""
        self.port = 0
        self.preference = 1.0
        self.username = ""
        self.password = ""
        self.type = "local"
        self.network_name = ""
        self.generation = 0
        self.nat_type = 0

    def serialize(self) -> bytes:
        """Serialize candidate to bytes using length-prefixed strings"""
        data = b""

        # Each string is prefixed with 2-byte length
        for s in [self.name, self.protocol, self.address]:
            encoded = str(s).encode('utf-8')
            data += struct.pack('<H', len(encoded)) + encoded

        # Ensure numeric types are properly converted (config might have strings)
        data += struct.pack('<H', int(self.port))
        data += struct.pack('<f', float(self.preference))

        for s in [self.username, self.password, self.type, self.network_name]:
            encoded = str(s).encode('utf-8')
            data += struct.pack('<H', len(encoded)) + encoded

        data += struct.pack('<I', int(self.generation))
        data += struct.pack('<B', int(self.nat_type))

        return data

    def deserialize(self, data: bytes, offset: int = 0) -> int:
        """Deserialize from bytes, returns new offset"""
        try:
            # Read name
            name_len, = struct.unpack_from('<H', data, offset)
            offset += 2
            self.name = data[offset:offset+name_len].decode('utf-8')
            offset += name_len

            # Read protocol
            protocol_len, = struct.unpack_from('<H', data, offset)
            offset += 2
            self.protocol = data[offset:offset+protocol_len].decode('utf-8')
            offset += protocol_len

            # Read address
            address_len, = struct.unpack_from('<H', data, offset)
            offset += 2
            self.address = data[offset:offset+address_len].decode('utf-8')
            offset += address_len

            # Read port and preference
            self.port, = struct.unpack_from('<H', data, offset)
            offset += 2
            self.preference, = struct.unpack_from('<f', data, offset)
            offset += 4

            # Read username
            username_len, = struct.unpack_from('<H', data, offset)
            offset += 2
            self.username = data[offset:offset+username_len].decode('utf-8')
            offset += username_len

            # Read password
            password_len, = struct.unpack_from('<H', data, offset)
            offset += 2
            self.password = data[offset:offset+password_len].decode('utf-8')
            offset += password_len

            # Read type
            type_len, = struct.unpack_from('<H', data, offset)
            offset += 2
            self.type = data[offset:offset+type_len].decode('utf-8')
            offset += type_len

            # Read network_name
            network_len, = struct.unpack_from('<H', data, offset)
            offset += 2
            self.network_name = data[offset:offset+network_len].decode('utf-8')
            offset += network_len

            # Read generation and nat_type
            self.generation, = struct.unpack_from('<I', data, offset)
            offset += 4
            self.nat_type, = struct.unpack_from('<B', data, offset)
            offset += 1

        except (struct.error, UnicodeDecodeError) as e:
            log.error(f"Failed to deserialize VoiceCandidate: {e}")

        return offset

    def __repr__(self):
        return f"VoiceCandidate({self.name}, {self.protocol}, {self.address}:{self.port}, type={self.type})"


class PacketBase:
    """
    Base class for VoiceIntroducer packets matching C++ PacketBase

    Binary format:
        - packet_type: 2 bytes (uint16)
        - local_steam_id: 8 bytes (uint64)
    """

    HEADER_SIZE = 10

    def __init__(self, packet_type: VoiceIntroducerPacketType = VoiceIntroducerPacketType.ClientToTrackerAddLocalCandidates,
                 local_steam_id: int = 0):
        self.packet_type = packet_type
        self.local_steam_id = local_steam_id

    def serialize(self) -> bytes:
        """Serialize base packet header"""
        return struct.pack('<HQ', int(self.packet_type), self.local_steam_id)

    def deserialize(self, data: bytes, offset: int = 0) -> int:
        """Deserialize base packet header, returns new offset"""
        if len(data) < offset + self.HEADER_SIZE:
            raise ValueError("Insufficient data for PacketBase")

        packet_type_raw, self.local_steam_id = struct.unpack_from('<HQ', data, offset)
        self.packet_type = VoiceIntroducerPacketType(packet_type_raw)

        return offset + self.HEADER_SIZE

    def __repr__(self):
        return f"PacketBase(type={self.packet_type.name}, local={self.local_steam_id})"


class InitiatorBase(PacketBase):
    """
    Initiator packet base matching C++ InitiatorBase

    Extends PacketBase with:
        - remote_steam_id: 8 bytes (uint64)
        - local_context_id: 8 bytes (uint64)
        - remote_context_id: 8 bytes (uint64)
    """

    INITIATOR_SIZE = PacketBase.HEADER_SIZE + 24

    def __init__(self, packet_type: VoiceIntroducerPacketType = VoiceIntroducerPacketType.ClientToTrackerAddLocalCandidates,
                 local_steam_id: int = 0, remote_steam_id: int = 0,
                 local_context_id: int = 0, remote_context_id: int = 0):
        super().__init__(packet_type, local_steam_id)
        self.remote_steam_id = remote_steam_id
        self.local_context_id = local_context_id
        self.remote_context_id = remote_context_id

    def serialize(self) -> bytes:
        """Serialize initiator packet"""
        data = super().serialize()
        data += struct.pack('<QQQ', self.remote_steam_id, self.local_context_id, self.remote_context_id)
        return data

    def deserialize(self, data: bytes, offset: int = 0) -> int:
        """Deserialize initiator packet, returns new offset"""
        offset = super().deserialize(data, offset)

        if len(data) < offset + 24:
            raise ValueError("Insufficient data for InitiatorBase")

        self.remote_steam_id, self.local_context_id, self.remote_context_id = struct.unpack_from('<QQQ', data, offset)

        return offset + 24

    def swap_payload(self):
        """
        Swap local and remote steam IDs for relay.
        This is called when forwarding a message from one client to another.
        NOTE: Only steam IDs are swapped, NOT context IDs (per tinserver implementation).
        """
        self.local_steam_id, self.remote_steam_id = self.remote_steam_id, self.local_steam_id

    def __repr__(self):
        return (f"InitiatorBase(type={self.packet_type.name}, "
               f"local={self.local_steam_id}, remote={self.remote_steam_id})")


class AddCandidate(InitiatorBase):
    """
    AddCandidate packet matching C++ AddCandidate class
    Used for ClientToTrackerAddLocalCandidates messages

    Extends InitiatorBase with:
        - is_initiator: 1 byte (bool)
        - relay_address: SteamInetAddress (12 bytes)
        - candidate_blob_size: 2 bytes (uint16/WORD)
        - candidate: VoiceCandidate (variable)
        - candidate_blob: Raw candidate bytes (optional)

    Total header size: 10 (PacketBase) + 24 (InitiatorBase) + 1 + 12 + 2 = 49 bytes
    """

    def __init__(self, local_steam_id: int = 0, remote_steam_id: int = 0,
                 relay_address: Optional[SteamInetAddress] = None,
                 candidate: Optional[VoiceCandidate] = None):
        super().__init__(VoiceIntroducerPacketType.ClientToTrackerAddLocalCandidates,
                        local_steam_id, remote_steam_id)
        self.is_initiator = True
        self.relay_address = relay_address or SteamInetAddress()
        self.candidate = candidate or VoiceCandidate()
        self.candidate_blob: Optional[bytes] = None

    def serialize(self) -> bytes:
        """Serialize AddCandidate packet"""
        data = super().serialize()
        data += struct.pack('<B', 1 if self.is_initiator else 0)
        data += self.relay_address.serialize()

        # Serialize candidate with WORD (2-byte) length prefix
        # Use stored blob if available (for forwarding), otherwise serialize candidate
        if self.candidate_blob is not None:
            candidate_data = self.candidate_blob
        else:
            candidate_data = self.candidate.serialize()
        data += struct.pack('<H', len(candidate_data))  # WORD size prefix
        data += candidate_data

        return data

    def deserialize(self, data: bytes, offset: int = 0) -> int:
        """Deserialize AddCandidate packet, returns new offset"""
        offset = super().deserialize(data, offset)

        if len(data) < offset + 1:
            raise ValueError("Insufficient data for AddCandidate")

        is_initiator_raw, = struct.unpack_from('<B', data, offset)
        offset += 1
        self.is_initiator = bool(is_initiator_raw)

        # Deserialize relay address
        offset = self.relay_address.deserialize(data, offset)

        # Deserialize candidate with WORD (2-byte) size prefix
        if offset + 2 <= len(data):
            candidate_len, = struct.unpack_from('<H', data, offset)  # WORD size prefix
            offset += 2

            # Store raw blob for forwarding - DO NOT deserialize!
            # The candidate blob is just forwarded unchanged (like tinserver does)
            if offset + candidate_len <= len(data):
                self.candidate_blob = data[offset:offset+candidate_len]
                # Note: We intentionally don't deserialize the candidate here.
                # The blob format uses big-endian for port/preference and is just
                # forwarded unchanged to the receiving client.
                offset += candidate_len

        return offset

    def swap_payload(self):
        """
        Swap local and remote for relay.

        Per tinserver AddCandidate::swapPayload():
        1. Change packet type from ClientToTrackerAddLocalCandidates (0x00)
           to TrackerToClientRelayRemoteCandidates (0x02)
        2. Set is_initiator to false (not toggle!)
        3. Swap local/remote steam IDs (via parent class)
        """
        # Change packet type for relay
        if self.packet_type == VoiceIntroducerPacketType.ClientToTrackerAddLocalCandidates:
            self.packet_type = VoiceIntroducerPacketType.TrackerToClientRelayRemoteCandidates
        else:
            log.warning(f"swap_payload called on unexpected packet type: {self.packet_type}")

        # Set initiator to false (client receiving relay is not the initiator)
        self.is_initiator = False

        # Swap steam IDs
        super().swap_payload()

    @staticmethod
    def from_bytes(data: bytes) -> Optional[AddCandidate]:
        """Create AddCandidate from raw bytes"""
        try:
            packet = AddCandidate()
            packet.deserialize(data)
            return packet
        except (ValueError, struct.error) as e:
            log.error(f"Failed to parse AddCandidate: {e}")
            return None

    def __repr__(self):
        return (f"AddCandidate(local={self.local_steam_id}, remote={self.remote_steam_id}, "
               f"initiator={self.is_initiator}, candidate={self.candidate})")


class ConnectionNack(InitiatorBase):
    """
    Connection NACK packet for TrackerToClientRequestConnectionNack messages
    Sent when connection request is rejected
    """

    def __init__(self, local_steam_id: int = 0, remote_steam_id: int = 0,
                 error_code: int = 0, error_message: str = ""):
        super().__init__(VoiceIntroducerPacketType.TrackerToClientRequestConnectionNack,
                        local_steam_id, remote_steam_id)
        self.error_code = error_code
        self.error_message = error_message

    def serialize(self) -> bytes:
        """Serialize ConnectionNack packet"""
        data = super().serialize()
        data += struct.pack('<I', self.error_code)
        error_bytes = self.error_message.encode('utf-8')
        data += struct.pack('<H', len(error_bytes))
        data += error_bytes
        return data

    def deserialize(self, data: bytes, offset: int = 0) -> int:
        """Deserialize ConnectionNack packet"""
        offset = super().deserialize(data, offset)

        if len(data) < offset + 4:
            raise ValueError("Insufficient data for ConnectionNack")

        self.error_code, = struct.unpack_from('<I', data, offset)
        offset += 4

        if offset + 2 <= len(data):
            msg_len, = struct.unpack_from('<H', data, offset)
            offset += 2
            if offset + msg_len <= len(data):
                self.error_message = data[offset:offset+msg_len].decode('utf-8', errors='replace')
                offset += msg_len

        return offset

    def __repr__(self):
        return f"ConnectionNack(error={self.error_code}, msg={self.error_message})"


class RelayRemoteCandidates(InitiatorBase):
    """
    Relay remote candidates packet for TrackerToClientRelayRemoteCandidates messages
    Sent to relay candidate information from one client to another
    """

    def __init__(self, local_steam_id: int = 0, remote_steam_id: int = 0,
                 candidates: Optional[list] = None):
        super().__init__(VoiceIntroducerPacketType.TrackerToClientRelayRemoteCandidates,
                        local_steam_id, remote_steam_id)
        self.candidates = candidates or []

    def serialize(self) -> bytes:
        """Serialize RelayRemoteCandidates packet"""
        data = super().serialize()
        data += struct.pack('<I', len(self.candidates))
        for candidate in self.candidates:
            candidate_data = candidate.serialize()
            data += struct.pack('<I', len(candidate_data))
            data += candidate_data
        return data

    def deserialize(self, data: bytes, offset: int = 0) -> int:
        """Deserialize RelayRemoteCandidates packet"""
        offset = super().deserialize(data, offset)

        if len(data) < offset + 4:
            raise ValueError("Insufficient data for RelayRemoteCandidates")

        count, = struct.unpack_from('<I', data, offset)
        offset += 4

        self.candidates = []
        for _ in range(count):
            if offset + 4 > len(data):
                break
            candidate_len, = struct.unpack_from('<I', data, offset)
            offset += 4

            candidate = VoiceCandidate()
            if offset + candidate_len <= len(data):
                candidate.deserialize(data, offset)
                self.candidates.append(candidate)
                offset += candidate_len

        return offset

    def __repr__(self):
        return f"RelayRemoteCandidates(candidates={len(self.candidates)})"


def parse_voice_introducer_packet(data: bytes) -> Optional[PacketBase]:
    """
    Parse raw VoiceIntroducer packet data and return appropriate packet type
    """
    if len(data) < PacketBase.HEADER_SIZE:
        log.error("Insufficient data for VoiceIntroducer packet")
        return None

    try:
        packet_type_raw, = struct.unpack_from('<H', data, 0)
        packet_type = VoiceIntroducerPacketType(packet_type_raw)

        if packet_type == VoiceIntroducerPacketType.ClientToTrackerAddLocalCandidates:
            packet = AddCandidate()
            packet.deserialize(data)
            return packet
        elif packet_type == VoiceIntroducerPacketType.TrackerToClientRequestConnectionNack:
            packet = ConnectionNack()
            packet.deserialize(data)
            return packet
        elif packet_type == VoiceIntroducerPacketType.TrackerToClientRelayRemoteCandidates:
            packet = RelayRemoteCandidates()
            packet.deserialize(data)
            return packet
        else:
            log.warning(f"Unknown VoiceIntroducer packet type: {packet_type_raw}")
            return None

    except (ValueError, struct.error) as e:
        log.error(f"Failed to parse VoiceIntroducer packet: {e}")
        return None
