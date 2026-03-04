import socket
import struct

class MsgClientCMList:
    def __init__(self):
        """Initialize the MsgClientCMList with an empty list of IP addresses."""
        self.ip_addresses = []

    def add_ip_address(self, ip):
        """
        Adds an IP address to the list. The IP address can be provided as a string or as bytes.
        :param ip: IP address (str or bytes)
        """
        if isinstance(ip, str):
            # Convert IP address string to bytes using inet_aton (convert dotted-decimal string to 4-byte format)
            ip_bytes = socket.inet_aton(ip)
            self.ip_addresses.append(ip_bytes)
        elif isinstance(ip, bytes):
            if len(ip) != 4:
                raise ValueError("IP address bytes must be exactly 4 bytes.")
            self.ip_addresses.append(ip)
        else:
            raise TypeError("IP address must be a string or 4-byte object.")

    def serialize(self):
        """
        Serializes the buffer with a 4-byte server count followed by the list of IP addresses in big-endian format.
        :return: A bytes object representing the serialized buffer.
        """
        # Create the buffer as a byte string
        buffer = b""

        # Write the 4-byte server count (number of IP addresses)
        server_count = len(self.ip_addresses)
        buffer += struct.pack('<I', server_count)  # Big-endian 4-byte integer

        # Append each IP address as 4 bytes in big-endian order
        for ip_bytes in self.ip_addresses:
            buffer += ip_bytes

        return buffer

    def deserialize(self, data: bytes):
        """
        Deserialize data from a byte string, reading a 4-byte server count followed by IP addresses.
        :param data: Byte string containing serialized data.
        """
        offset = 0

        # Read the 4-byte server count
        server_count, = struct.unpack('<I', data[offset:offset + 4])
        offset += 4

        # Clear existing addresses
        self.ip_addresses = []

        # Read each IP address (4 bytes per address)
        for _ in range(server_count):
            ip_bytes = data[offset:offset + 4]
            if len(ip_bytes) != 4:
                raise ValueError("Invalid IP address data in buffer.")
            self.ip_addresses.append(ip_bytes)
            offset += 4

"""# Example Usage:
msg = MsgClientCMList()

# Add IP addresses as strings
msg.add_ip_address("192.168.0.1")
msg.add_ip_address("10.0.0.1")

# Add IP address as bytes (must be exactly 4 bytes)
msg.add_ip_address(b'\xC0\xA8\x00\x02')  # This is 192.168.0.2

# Serialize the buffer
serialized_buffer = msg.serialize()

# For demonstration purposes: print the serialized buffer in a human-readable format
print(f"Serialized buffer: {serialized_buffer}")

# Parse the serialized buffer to show it works (reusing the previous parsing method)
def parse_server_ip_list(buffer: bytes):
    "\""Parses a buffer that contains a list of IP addresses."\""
    stream = BytesIO(buffer)

    # Read the first 4 bytes to get the server count
    server_count = struct.unpack('>I', stream.read(4))[0]  # >I is for big-endian unsigned 4-byte integer
    print(f"Number of servers: {server_count}")

    ip_list = []

    # Read each IP address (4 bytes each in big-endian order)
    for _ in range(server_count):
        ip_bytes = stream.read(4)  # Read 4 bytes for the IP address
        ip_address = socket.inet_ntoa(ip_bytes)  # Convert bytes to a human-readable IP address
        ip_list.append(ip_address)

    return ip_list

# Demonstrate that the serialized buffer can be parsed back
ip_addresses = parse_server_ip_list(serialized_buffer)
for ip in ip_addresses:
    print(f"IP Address: {ip}")"""