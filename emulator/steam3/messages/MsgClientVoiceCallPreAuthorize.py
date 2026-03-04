"""
MsgClientVoiceCallPreAuthorize and MsgClientVoiceCallPreAuthorizeResponse
Protobuf messages for P2P voice call pre-authorization handshake.

The server forwards these messages between caller and receiver to establish
voice call authorization before P2P candidates are exchanged.
"""
from __future__ import annotations
import struct
from steam3.Types.steamid import SteamID
from steam3.Types.emsg import EMsg
from steam3.protobufs.steammessages_clientserver_2_pb2 import (
    CMsgClientVoiceCallPreAuthorize,
    CMsgClientVoiceCallPreAuthorizeResponse,
)
from steam3.protobufs.steammessages_base_pb2 import CMsgProtoBufHeader


def set_proto_bit(emsg_id: int) -> int:
    """Set the protobuf bit on an EMsg ID."""
    return emsg_id | 0x80000000


class MsgClientVoiceCallPreAuthorizeRequest:
    """
    Represents EMsg.ClientVoiceCallPreAuthorize (9800) protobuf message.

    This is sent from caller to receiver to request voice call authorization.

    Protobuf body (CMsgClientVoiceCallPreAuthorize):
        - caller_steamid: fixed64 - SteamID of the calling user
        - receiver_steamid: fixed64 - SteamID of the receiving user
        - caller_id: int32 - Caller's identifier
        - hangup: bool - True if this is a hangup notification
    """

    def __init__(self, client_obj=None, data: bytes = None):
        self.client_obj = client_obj
        self.body = CMsgClientVoiceCallPreAuthorize()
        if data:
            self.deserialize(data)

    def deserialize(self, data: bytes) -> None:
        """Parse the protobuf body from raw data."""
        self.body.ParseFromString(data)

    @property
    def caller_steamid(self) -> int:
        return self.body.caller_steamid if self.body.HasField('caller_steamid') else 0

    @caller_steamid.setter
    def caller_steamid(self, value: int):
        self.body.caller_steamid = value

    @property
    def receiver_steamid(self) -> int:
        return self.body.receiver_steamid if self.body.HasField('receiver_steamid') else 0

    @receiver_steamid.setter
    def receiver_steamid(self, value: int):
        self.body.receiver_steamid = value

    @property
    def caller_id(self) -> int:
        return self.body.caller_id if self.body.HasField('caller_id') else 0

    @caller_id.setter
    def caller_id(self, value: int):
        self.body.caller_id = value

    @property
    def hangup(self) -> bool:
        return self.body.hangup if self.body.HasField('hangup') else False

    @hangup.setter
    def hangup(self, value: bool):
        self.body.hangup = value

    def to_clientmsg(self):
        """
        Serialize this message for sending to a client.

        Returns a raw bytes packet that can be sent directly.
        Format: [EMsg|proto_bit (4)] [header_size (4)] [proto_header] [body]
        """
        # Build protobuf header
        proto_header = CMsgProtoBufHeader()
        if self.client_obj:
            proto_header.steamid = self.client_obj.steamID
            proto_header.client_sessionid = self.client_obj.sessionID

        # Serialize header and body
        header_data = proto_header.SerializeToString()
        body_data = self.body.SerializeToString()

        # Build packet: EMsg with proto bit, header size, header, body
        packet_data = struct.pack('<II',
            set_proto_bit(EMsg.ClientVoiceCallPreAuthorize),
            len(header_data)
        ) + header_data + body_data

        return packet_data


class MsgClientVoiceCallPreAuthorizeResponseMsg:
    """
    Represents EMsg.ClientVoiceCallPreAuthorizeResponse (9801) protobuf message.

    This is sent from receiver back to caller in response to a voice call request.

    Protobuf body (CMsgClientVoiceCallPreAuthorizeResponse):
        - caller_steamid: fixed64 - SteamID of the calling user
        - receiver_steamid: fixed64 - SteamID of the receiving user
        - eresult: int32 - Result code (default 2)
        - caller_id: int32 - Caller's identifier
    """

    def __init__(self, client_obj=None, data: bytes = None):
        self.client_obj = client_obj
        self.body = CMsgClientVoiceCallPreAuthorizeResponse()
        if data:
            self.deserialize(data)

    def deserialize(self, data: bytes) -> None:
        """Parse the protobuf body from raw data."""
        self.body.ParseFromString(data)

    @property
    def caller_steamid(self) -> int:
        return self.body.caller_steamid if self.body.HasField('caller_steamid') else 0

    @caller_steamid.setter
    def caller_steamid(self, value: int):
        self.body.caller_steamid = value

    @property
    def receiver_steamid(self) -> int:
        return self.body.receiver_steamid if self.body.HasField('receiver_steamid') else 0

    @receiver_steamid.setter
    def receiver_steamid(self, value: int):
        self.body.receiver_steamid = value

    @property
    def eresult(self) -> int:
        return self.body.eresult if self.body.HasField('eresult') else 2

    @eresult.setter
    def eresult(self, value: int):
        self.body.eresult = value

    @property
    def caller_id(self) -> int:
        return self.body.caller_id if self.body.HasField('caller_id') else 0

    @caller_id.setter
    def caller_id(self, value: int):
        self.body.caller_id = value

    def to_clientmsg(self):
        """
        Serialize this message for sending to a client.

        Returns a raw bytes packet that can be sent directly.
        Format: [EMsg|proto_bit (4)] [header_size (4)] [proto_header] [body]
        """
        # Build protobuf header
        proto_header = CMsgProtoBufHeader()
        if self.client_obj:
            proto_header.steamid = self.client_obj.steamID
            proto_header.client_sessionid = self.client_obj.sessionID

        # Serialize header and body
        header_data = proto_header.SerializeToString()
        body_data = self.body.SerializeToString()

        # Build packet: EMsg with proto bit, header size, header, body
        packet_data = struct.pack('<II',
            set_proto_bit(EMsg.ClientVoiceCallPreAuthorizeResponse),
            len(header_data)
        ) + header_data + body_data

        return packet_data
