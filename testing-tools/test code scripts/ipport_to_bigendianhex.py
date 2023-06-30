import socket
import struct, binascii

def convert_to_network_format(ip_address, port):
    # Convert IP address to network format
    ip_bytes = socket.inet_aton(ip_address)

    # Convert port to network format
    port_hex = struct.pack('<H', port)

    # Combine IP and port hex values
    result = ip_bytes + port_hex

    # Convert to string representation
    result_str = ''.join(format(byte, '02x') for byte in result)

    return result_str
# Example usage
ip_address = '127.0.0.1'
port = 27034
result = convert_to_network_format(ip_address, port)
print(result*2)
print("\n")
print(str(binascii.b2a_hex("7F0000019A697F0000019A69")))
