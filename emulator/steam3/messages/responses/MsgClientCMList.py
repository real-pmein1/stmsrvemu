import socket
import struct

import globalvars
from steam3.cm_packet_utils import CMProtoResponse, CMResponse
from steam3.Types.emsg import EMsg
from steam3.protobufs.steammessages_clientserver_pb2 import CMsgClientCMList


class CMListResponse:
    def __init__(self, client_obj):
        """
        Initialize the CMListResponse object with default values.
        """
        self.client_obj = client_obj
        self.ip_addresses = []  # List of IP addresses as bytes
        self.ports = []  # List of ports (for protobuf)
        self.websocket_addresses = []  # List of websocket addresses (for protobuf)
        self.percent_default_to_websocket = 0  # For protobuf

    def add_ip_address(self, ip, port=27017):
        """
        Adds an IP address to the list. The IP address can be provided as a string or as bytes.
        :param ip: IP address (str or bytes)
        :param port: Port number (default 27017)
        """
        if isinstance(ip, str):
            # Convert IP address string to bytes using inet_aton
            ip_bytes = socket.inet_aton(ip)
            self.ip_addresses.append(ip_bytes)
        elif isinstance(ip, bytes):
            if len(ip) != 4:
                raise ValueError("IP address bytes must be exactly 4 bytes.")
            self.ip_addresses.append(ip)
        else:
            raise TypeError("IP address must be a string or 4-byte object.")

        self.ports.append(port)

    def add_ip_addresses_for_client(self):
        """
        Automatically populate IP addresses based on client connection (LAN vs external).
        """
        client_address = str(self.client_obj.ip_port[0])

        # Determine if connection is local or external
        if str(client_address) in globalvars.server_network or globalvars.public_ip == "0.0.0.0":
            islan = True
        else:
            islan = False

        if islan:
            ip_list = [globalvars.server_ip, globalvars.server_ip]
        else:
            ip_list = [globalvars.public_ip, globalvars.public_ip]

        for ip in ip_list:
            # Reverse the byte order of the IP address for clientmsg format
            reversed_ip = ".".join(ip.split(".")[::-1])
            self.add_ip_address(reversed_ip)

    def to_protobuf(self):
        """
        Convert the CMListResponse data to a Protobuf object.
        :return: A CMProtoResponse packet with serialized protobuf data.
        """
        packet = CMProtoResponse(eMsgID=EMsg.ClientCMList, client_obj=self.client_obj)
        cm_list_msg = CMsgClientCMList()

        # Add IP addresses as uint32
        for ip_bytes in self.ip_addresses:
            # Convert IP bytes to uint32 (big endian to int)
            ip_int = struct.unpack('>I', ip_bytes)[0]
            cm_list_msg.cm_addresses.append(ip_int)

        # Add ports
        for port in self.ports:
            cm_list_msg.cm_ports.append(port)

        # Add websocket addresses if any
        for ws_addr in self.websocket_addresses:
            cm_list_msg.cm_websocket_addresses.append(ws_addr)

        if self.percent_default_to_websocket:
            cm_list_msg.percent_default_to_websocket = self.percent_default_to_websocket

        # Serialize the Protobuf message
        serialized_response = cm_list_msg.SerializeToString()

        # Attach serialized data to the packet
        packet.data = serialized_response
        packet.length = len(serialized_response)

        return packet

    def to_clientmsg(self):
        """
        Convert the CMListResponse data to a regular byte buffer.
        :return: A CMResponse packet with binary data.
        """
        packet = CMResponse(eMsgID=EMsg.ClientCMList, client_obj=self.client_obj)

        # Write the 4-byte server count (number of IP addresses)
        server_count = len(self.ip_addresses)
        packet.data = struct.pack('<I', server_count)

        # Append each IP address as 4 bytes
        for ip_bytes in self.ip_addresses:
            packet.data += ip_bytes

        packet.length = len(packet.data)

        return packet
