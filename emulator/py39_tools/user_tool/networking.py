import os

from Crypto.Cipher import AES
from Crypto.Protocol.KDF import scrypt

import globals

# Constant header for packets
HEADER = b"\xbe\xee\xee\xff"
# Unique pre-shared client identifier (must be shared securely with the server)
CLIENT_IDENTIFIER = os.urandom(16)  # Randomly generated identifier for this client


def derive_key(shared_secret, salt):
    key = scrypt(shared_secret, salt, 32, N=2**14, r=8, p=1)
    return key


# Encrypt/Decrypt helper functions
def encrypt_message(key, plaintext):
    cipher = AES.new(key, AES.MODE_CFB)
    ciphertext = cipher.iv + cipher.encrypt(plaintext)
    print(f"Encrypting message. IV: {cipher.iv.hex()} Ciphertext: {ciphertext[16:].hex()}")
    return ciphertext


def decrypt_message(key, ciphertext):
    iv = ciphertext[:16]
    cipher = AES.new(key, AES.MODE_CFB, iv=iv)
    print(f"Decrypting message. IV: {iv.hex()} Ciphertext: {ciphertext[16:].hex()}")
    return cipher.decrypt(ciphertext[16:])


def handle_server_error(error_message):
    """Handle any error message from the server."""
    print(f"Server Error: {error_message}")


def perform_handshake_and_authenticate(config):
    globals.client_socket.bind(('', 0))  # Bind to any available port

    server_address = (config['adminserverip'], int(config['adminserverport']))
    globals.server_ip = config['adminserverip']
    globals.server_port = int(config['adminserverport'])
    username = config['adminusername']
    password = config['adminpassword']
    shared_secret = config['peer_password']

    globals.client_socket.connect(server_address)

    salt = os.urandom(16)
    globals.symmetric_key = derive_key(shared_secret, salt)

    # Include the client identifier in the handshake
    message = encrypt_message(globals.symmetric_key, CLIENT_IDENTIFIER + b"handshake")
    globals.client_socket.send(HEADER + b"\x01" + salt + message)  # Command byte \x01 for handshake
    command_byte = b'\x01'
    print(f"Handshake packet sent: {HEADER + command_byte + salt + message}")

    # Wait for server response
    data = globals.client_socket.recv(1024)
    print(f"Received handshake response: {data}")
    if data.startswith(b"error:"):
        handle_server_error(data.decode("latin-1"))
        return None

    server_salt = data[:16]
    globals.symmetric_key = derive_key(shared_secret, server_salt)
    decrypted_data = decrypt_message(globals.symmetric_key, data[16:])
    print(f"Decrypted handshake response: {decrypted_data}")

    if decrypted_data == b"handshake successful":
        print("Handshake successful with server.")
        result = send_client_login(globals.client_socket, server_address, username, password)
        if result:
            return True
        else:
            return False
    else:
        print(f"Handshake failed. Received: {decrypted_data}")
        return False


def send_client_login(client_socket, server_address, username, password):

    packed_info = username.encode('latin-1') + b'\x00'
    packed_info += password.encode('latin-1') + b'\x00'

    encrypted_message = encrypt_message(globals.symmetric_key, packed_info)
    packet = HEADER + b"\x02" + encrypted_message
    client_socket.send(packet)  # Command byte \x02 for sending info
    print(f"Sent client info packet: {packet}")

    # Wait for server response
    data = client_socket.recv(1024)
    print(f"Received server response for client info: {data}")
    if data == b'\x00':  # OK response from server
        print("Server acknowledged client info.")
        return True
    elif data.startswith(b"error:"):
        handle_server_error(data.decode("latin-1"))
        return False
    else:
        print(f"Unexpected response: {data}")
        return False


def send_request_to_server(command_code, parameters):
    """
    Send a request to the server and receive a response.

    :param command_code: Command code as a string.
    :param parameters: List of parameters to send with the command.
    :return: Decrypted response from the server.
    """
    symmetric_key = globals.symmetric_key

    try:
        # Construct the packet with the command code and parameters
        packet = f"{'|'.join(map(str, parameters))}".encode('latin-1')  # Encode parameters to bytes
        if len(packet) < 7:
            packet.rjust(7, b"\x00")
        encrypted_packet = encrypt_message(symmetric_key, packet)

        # Send the encrypted packet (using send() for a connected socket)
        globals.client_socket.send(HEADER + command_code.encode('latin-1') + encrypted_packet)

        # Wait for and decrypt the response
        encrypted_response = globals.client_socket.recv(1024)

        # Check if the response starts with 'error:', bypass decryption if true
        if encrypted_response.startswith(b'error:'):
            return encrypted_response.decode('latin-1')  # Decode to return it as a string

        # Otherwise, decrypt the response
        response = decrypt_message(symmetric_key, encrypted_response)
        return response

    except Exception as e:
        print(f"Error: {e}")
        return None