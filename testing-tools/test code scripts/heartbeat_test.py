import time
import struct
import utilities
import socket

def create_encrypt_server_packet(ip, port, server_type, key):
    packet = "\x1c" + utilities.encrypt(utilities.encodeIP((ip, port)) + struct.pack("16s", server_type.encode("utf-8")), key)
    return packet

def decrypt_server_packet(packet, key):
    packet = "\x1c" + utilities.decrypt(packet, key)
    return packet

class ServerInfo:
    def __init__(self, ip, port, server_type, timestamp):
        self.ip = ip
        self.port = port
        self.server_type = server_type
        self.timestamp = timestamp

# Create a TCP/IP socket
serversock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Bind the socket to a specific address and port
server_address = ('localhost', 1234)
serversock.bind(server_address)

# Listen for incoming connections
serversock.listen(1)

while True:
    print('Waiting for a client to connect...')
    clientsock, client_address = serversock.accept()
    print('Client connected:', client_address)

    # Receive data from the client
    data = clientsock.recv(4)

    if data == '\x00\x3e\x7b\x11':
        print('Received valid request from the client')
        response = '\x01'
        clientsock.sendall(response)

        # Generate random strings for the arguments
        ip = "192.168.0.1"
        port = "8080"
        server_type = "web-server"
        key = "password"

        packet = create_encrypt_server_packet(ip, port, server_type, key)
        clientsock.sendall(packet)

        encrypted_packet = clientsock.recv(1024)
        if encrypted_packet and encrypted_packet[0] == '\x1c':
            decrypted_packet = decrypt_server_packet(encrypted_packet[1:], key)
            server_info = struct.unpack('!4sH16sI', decrypted_packet)
            ip_address = socket.inet_ntoa(server_info[0])
            port = server_info[1]
            server_type = server_info[2].strip('\x00')
            timestamp = server_info[3]
            server = ServerInfo(ip_address, port, server_type, timestamp)
            print('Received server info:')
            print('IP:', server.ip)
            print('Port:', server.port)
            print('Server Type:', server.server_type)
            print('Timestamp:', server.timestamp)

    # Close the client socket
    clientsock.close()
