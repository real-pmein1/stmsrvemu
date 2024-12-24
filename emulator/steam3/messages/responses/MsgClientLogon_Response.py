import struct
import socket

import globalvars
from steam3.cm_packet_utils import CMProtoResponse, CMResponse
from steam3.Types.emsg import EMsg
from steam3.protobufs.steammessages_clientserver_login_pb2 import CMsgClientLogonResponse


class LogonResponse:
    def __init__(self, client_obj):
        """
        Initialize the LogonResponse object with default values.
        """
        self.eresult = 0
        self.out_of_game_heartbeat_rate_sec = 9
        self.in_game_heartbeat_rate_sec = 9
        self.steam_id = 0
        self.client_id = 0
        self.public_ip = 0
        self.server_time = 0
        self.account_flags = 0
        self.is_anon = False
        self.client_obj = client_obj

    def to_protobuf(self):
        """
        Convert the LogonResponse data to a Protobuf object.
        :return: A Protobuf serialized response.
        """
        packet = CMProtoResponse(eMsgID = EMsg.ClientLogOnResponse, client_obj = self.client_obj)
        logon_response = CMsgClientLogonResponse()

        logon_response.eresult = self.eresult
        logon_response.legacy_out_of_game_heartbeat_seconds = (
                30 if self.is_anon else self.out_of_game_heartbeat_rate_sec
        )
        logon_response.heartbeat_seconds = self.in_game_heartbeat_rate_sec
        logon_response.client_supplied_steamid = self.steam_id * 2
        logon_response.deprecated_public_ip = self.public_ip
        logon_response.rtime32_server_time = self.server_time
        logon_response.account_flags = 0 if self.is_anon else self.account_flags

        packet.set_response_message(logon_response)
        # Serialize the Protobuf message.
        serialized_response = logon_response.SerializeToString()

        # Attach serialized data to the packet.
        packet.data = serialized_response
        packet.length = len(serialized_response)

        return packet

    def to_clientmsg(self):
        """
        Convert the LogonResponse data to a regular byte buffer.
        :return: A byte string.
        """
        packet = CMResponse(eMsgID = EMsg.ClientLogOnResponse, client_obj = self.client_obj)
        packet.data = struct.pack(
                'I I I I I I',
                self.eresult,
                self.out_of_game_heartbeat_rate_sec if not self.is_anon else 30,
                self.in_game_heartbeat_rate_sec,
                self.steam_id * 2,
                self.client_id,
                self.public_ip,
        )

        if globalvars.steamui_ver > 85:
            packet.data += struct.pack('<I', self.server_time)
        if globalvars.steamui_ver >= 288 and not self.is_anon:
            packet.data += struct.pack('<I', self.account_flags)

        packet.length = len(packet.data)
        return packet