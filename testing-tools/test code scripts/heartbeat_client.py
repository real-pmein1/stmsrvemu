import struct
import utilities
import socket

def create_encrypt_server_packet(ip, port, server_type, key):
    packet = "\x1c" + utilities.encrypt(utilities.encodeIP((ip, port)) + struct.pack("16s", server_type.encode("utf-8")), key)
    return packet

# Generate random strings for the arguments
ip = "192.168.0.1"
port = "8080"
server_type = "web-server"
key = "password"

# Create a TCP socket
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Connect to the server
client_socket.connect(("localhost", 1234))

# Send the request to the server
client_socket.send("\x00\x3e\x7b\x11")

# Receive the response from the server
response = client_socket.recv(1)

if response == '\x01':
    # Create the encrypted server packet
    encrypted_packet = create_encrypt_server_packet(ip, port, server_type, key)

    # Send the encrypted server packet to the server
    client_socket.send(encrypted_packet)

# Close the socket
client_socket.close()
