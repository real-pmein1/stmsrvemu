import socket

import user_config

STEAM_VERSION = None
STEAMUI_VERSION = None
RECORD_VERSION = None
server_ip = None
server_port = None
username = None
symmetric_key = None

configuration = user_config
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)