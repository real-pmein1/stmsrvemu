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

packet = b'\x18\x00\x00\x00\xb9=\xa5H\xba=\xa5H\xbb=\xa5H\xbc=\xa5H\xfa\x9c\x1cE\xa2@\x8eD\xa3@\x8eD\xa4@\x8eD\xa5@\x8eD\xa6@\x8eD\xaa\x91\x1cE\xab\x91\x1cE\xac\x91\x1cE4\x9eo\xd05\x9eo\xd0R\xabo\xd0S\xabo\xd0"[\x8eD#[\x8eD$[\x8eDT\x85o\xd0U\x85o\xd0\xb2t\x8eD\xb3t\x8eD'

size = 36

ip_addresses = parse_server_ip_list(packet)
for ip in ip_addresses:
    print(f"IP Address: {ip}")