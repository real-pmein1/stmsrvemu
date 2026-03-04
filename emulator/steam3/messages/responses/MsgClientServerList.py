import socket
import struct
from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse


class MsgClientServerList:
    """
    Note: There is no protobuf equivalent for ClientServerList.
    This message was deprecated before protobuf was introduced.
    Only to_clientmsg() is supported.
    """
    class ServerInfo:
        def __init__(self, server_type: int, ip: int, port: int):
            self.server_type = server_type
            self.server_address = (ip, port)

    def __init__(self, client_obj):
        self.client_obj = client_obj
        self.body = {
            "servers": []
        }

    @staticmethod
    def ip_to_int(ip_address: str) -> int:
        """
        Converts a dotted-quad IP address string to an integer.

        :param ip_address: String representation of the IP address (e.g., "127.0.0.1").
        :return: Integer representation of the IP address.
        """
        return struct.unpack("!I", socket.inet_aton(ip_address))[0]

    def add_server(self, server_type: int, ip: str, port: int):
        """
        Adds a server to the servers list.

        :param server_type: Integer representing the server type.
        :param ip: String representation of the server IP address.
        :param port: Integer representing the server port.
        """
        # Convert the IP address to an integer if it is a string
        if isinstance(ip, str):
            ip = self.ip_to_int(ip)
        self.body["servers"].append(self.ServerInfo(server_type, ip, port))

    def deserialize(self, data: bytes):
        """
        Deserialize data from a byte string.

        :param data: Byte string containing serialized data.
        """
        offset = 0
        server_count, = struct.unpack('<I', data[offset:offset + 4])
        offset += 4

        self.body["servers"] = []
        for _ in range(server_count):
            server_type, ip = struct.unpack('<II', data[offset:offset + 8])
            offset += 8
            port, = struct.unpack('<H', data[offset:offset + 2])
            offset += 2
            self.body["servers"].append(self.ServerInfo(server_type, ip, port))

    def serialize(self) -> bytes:
        """
        Serialize data into a byte string.

        :return: Byte string containing serialized data.
        """
        data = struct.pack('<I', len(self.body["servers"]))
        for server in self.body["servers"]:
            data += struct.pack('<IIH', server.server_type, server.server_address[0], server.server_address[1])
        return data

    def to_clientmsg(self):
        """
        Convert this PersonaStateMessage into a CMResponse packet.
        """
        packet = CMResponse(eMsgID=EMsg.ClientServerList, client_obj=self.client_obj)
        packet.data = self.serialize()
        packet.length = len(packet.data)
        return packet
