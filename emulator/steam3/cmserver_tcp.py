import logging
import struct
from config import read_config
from steam3.ClientManager.client import Client
from steam3.cm_crypto import symmetric_decrypt, symmetric_encrypt
from steam3.cmserver_base import CMServer_Base
from utilities.database.cmdb import cm_dbdriver
from utilities.networkhandler import TCPNetworkHandler, TCPNetworkHandlerCM

config = read_config()

database = cm_dbdriver(config)

class CMServerTCP_27017(TCPNetworkHandlerCM, CMServer_Base):
    """		// the tcp packet header is considerably less complex than the udp one
		// it only consists of the packet length, followed by the "VT01" magic"""
    def __init__(self, port, config, master_server):
        CMServer_Base.__init__(self, port, config)
        TCPNetworkHandlerCM.__init__(self, config, port)
        self.is_encrypted = True
        self.is_tcp = True
        self.server_type = "CMServerTCP_27017"
        self.log = logging.getLogger("CMTCP27017")
        self.master_server = master_server  # Store the reference to MasterServer

    def encrypt_packet(self, packet, client_obj: Client):
        # Override to implement specific encryption logic for 27017
        key = client_obj.symmetric_key
        encrypted_data = symmetric_encrypt(packet.data, key)
        return encrypted_data

    def decrypt_packet(self, packet, client_obj: Client):
        key = client_obj.symmetric_key
        try:
            packet.data = symmetric_decrypt(packet.data, key)
            # self.handle_decrypted(self, packet.data, client_obj)
        except:
            self.handle_unknown_command(self, packet.data, client_obj)
        return packet, True

    def handle_decryption_error(self, data, client_obj):
        with open("logs/decryption_error_cm_msgs.txt", 'a') as file:
            # Write the text to the file
            file.write(f'decryption key: {client_obj.symmetric_key}\n'
                       f'hmac key: {client_obj.hmac_key}'
                       f'data (raw): {data}\n')  # Adding a newline character to separate entries


class CMServerTCP_27014(TCPNetworkHandlerCM, CMServer_Base):
    def __init__(self, port, config, master_server):
        CMServer_Base.__init__(self, port, config)
        TCPNetworkHandlerCM.__init__(self, config, port)
        self.server_type = "CMServerTCP_27014"
        self.is_encrypted = False
        self.is_tcp = True
        self.log = logging.getLogger("CMTCP27014")
        self.master_server = master_server  # Store the reference to MasterServer