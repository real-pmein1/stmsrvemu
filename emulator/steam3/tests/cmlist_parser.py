import struct
from io import BytesIO
import socket

def parse_server_ip_list(buffer: bytes):
    """Parses a buffer that contains a list of IP addresses."""
    stream = BytesIO(buffer)

    # Read the first 4 bytes to get the server count
    server_count = struct.unpack('<I', stream.read(4))[0]  # >I is for big-endian unsigned 4-byte integer
    print(f"Number of servers: {server_count}")

    ip_list = []

    # Read each IP address (4 bytes each in big-endian order)
    for _ in range(server_count):
        ip_bytes = stream.read(4)  # Read 4 bytes for the IP address
        ip_address = socket.inet_ntoa(ip_bytes)  # Convert bytes to a human-readable IP address
        ip_list.append(ip_address)

    return ip_list

packet = b'\x0f\x03\x00\x00jhA\x01\x01\x00\x10\x01\xfa\x19\x16\x00\t\x00\x00\x00\xfa\x94\x1cE\xc6\x98\x1cE\xfa\x9c\x1cET\xbf\x1cE\xa2@\x8eD\xa3@\x8eD\xa4@\x8eD\xa5@\x8eD\xa6@\x8eD'

size = 36

ip_addresses = parse_server_ip_list(packet[16:])
for ip in ip_addresses:
    print(f"IP Address: {ip}")