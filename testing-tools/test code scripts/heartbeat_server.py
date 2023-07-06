import time
import struct
import utilities
import socket

def create_encrypt_server_packet(ip, port, server_type, key):
    packet = "\x1c" + utilities.encrypt(utilities.encodeIP((ip, port)) + struct.pack("16s", server_type.encode("utf-8")), key)
    return packet

def decrypt_server_packet(packet, key):
    decrypted_packet = utilities.decrypt(packet[1:], key)
    return decrypted_packet

class ServerInfo:
    def __init__(self, ip, port, server_type, timestamp):
        self.ip = ip
        self.port = port
        self.server_type = server_type
        self.timestamp = timestamp

def start_server():
    # Create a TCP socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Bind the socket to a specific address and port
    server_socket.bind(("localhost", 1234))

    # Listen for incoming connections
    server_socket.listen(1)
    print("Server listening on port 1234")

    while True:
        # Accept a new client connection
        client_socket, address = server_socket.accept()
        print("Accepted connection from:", address)

        # Receive data from the client
        data = client_socket.recv(4)

        if data == "\x00\x3e\x7b\x11":
            # Send response to the client
            client_socket.send('\x01')

            # Receive the encrypted server packet from the client
            encrypted_packet = client_socket.recv(1024)

            # Check for '\x1c' in the first byte of the packet
            if encrypted_packet[0] == "\x1c":
                # Decrypt the packet
                decrypted_info = decrypt_server_packet(encrypted_packet, "password")

                # Extract the server info
                ip = decrypted_info[:4]
                port = struct.unpack("H", decrypted_info[4:6])[0]
                server_type = decrypted_info[6:].strip('\x00')

                # Create the server info object
                server_info = ServerInfo(ip, port, server_type, int(time.time()))

                # Print the server info
                print(server_info.__dict__)

        # Close the client socket
        client_socket.close()

# Start the server
start_server()