import binascii
import logging
import struct

import utilities.encryption
from utilities.networkhandler import TCPNetworkHandler


class vttserver(TCPNetworkHandler):
    def __init__(self, port, config):
        self.server_type = "VTTServer"
        super(vttserver, self).__init__(config, int(port), self.server_type)

        
    def handle_client(self, client_socket, client_address):
        
        clientid = str(client_address) + ": "

        self.log.info(f"{clientid} Connected to VTT Server")

        error_count = 0

        while True:
            try:
                # config_update = read_config()

                command = client_socket.recv(26)

                self.log.debug("COMMAND :" + binascii.b2a_hex(command).decode() + ":")

                if command[0:8] == b"\x53\x45\x4e\x44\x4d\x41\x43\x20":  # SENDMAC (v2) + MAC in caps and hyphens
                    # print("SENDMAC")
                    self.log.info(f"{clientid} SENDMAC received")
                    macaddress = binascii.unhexlify(binascii.b2a_hex(command))[9:26]
                    self.log.info(f"{clientid} MAC address received: {str(macaddress)}")
                    # TO DO: create MAC filter here

                    if self.config["cafe_use_mac_auth"].lower() == "true":
                        mac_count = 0
                        cafemacs = (self.config["cafemacs"].split(";"))
                        # print(len(cafemacs))
                        while mac_count < len(cafemacs):
                            # print(cafemacs[mac_count])
                            if macaddress == cafemacs[mac_count]:
                                client_socket.send(b"\x01\x00\x00\x00")  # VALID
                                break
                            mac_count += 1
                            if mac_count == len(cafemacs):
                                client_socket.send(b"\xfd\xff\xff\xff")  # NO VALID MAC
                                break
                    else:
                        client_socket.send(b"\x01\x00\x00\x00")  # ALWAYS VALID

                elif command[0:6] == b"\x53\x45\x54\x4d\x41\x43":  # SETMAC (v1)
                    self.log.info(f"{clientid} SETMAC received")
                    client_socket.send(b"\x01\x00\x00\x00")

                elif command[0:4] == b"\x00\x00\xff\xff":  # Response (v1)
                    self.log.info(f"{clientid} RESPONSE sent")
                    #client_socket.send(b"\x01\x00\x00\x00")  # works for 1.3, need to test OK
                    client_socket.send(b"\x4f\x4b\x00\x00")  # OK

                elif command[0:9] == b"\x43\x48\x41\x4c\x4c\x45\x4e\x47\x45":  # CHALLENGE (v1)
                    self.log.info(f"{clientid} CHALLENGE received")
                    client_socket.send(b"\xff\xff\x00\x00")  # CHALLENGE reply (can be anything, is the inverse of the client reply)

                elif command == b"\x47\x45\x54\x53\x56\x52\x53\x55\x4d":  # GETSRVSUM (update CAS)
                    client_socket.send(struct.pack(">I", 14))  # CHALLENGE reply (can be anything, is the inverse of the client reply)

                elif command[5:12] == b"\x47\x45\x54\x49\x4e\x46\x4f":  # GETINFO
                    # print(binascii.b2a_hex(command))
                    self.log.info(f"{clientid} GETINFO received")
                    cafeuser = self.config["cafeuser"]
                    cafepass = self.config["cafepass"]
                    username_dec = cafeuser + "%" + cafepass
                    username_enc = utilities.encryption.textxor(username_dec)
                    # print(username_dec)
                    # print(username_enc)
                    reply = struct.pack("<L", len(username_enc)) + username_enc
                    # print(binascii.b2a_hex(reply))
                    client_socket.send(reply)

                elif command[0:8] == b"\x53\x45\x4e\x44\x4d\x49\x4e\x53" or command[5:13] == b"\x53\x45\x4e\x44\x4d\x49\x4e\x53":  # SENDMINS
                    self.log.info(f"{clientid} SENDMINS received")
                    # client_socket.send(b"\x01\x00\x00\x00") #FAKE MINS
                    reply = struct.pack("<L", int(self.config["cafetime"]))
                    client_socket.send(reply)

                elif command[0:8] == b"\x47\x45\x54\x49\x4e\x46\x4f\x20":  # GETINFO AGAIN
                    # print(binascii.b2a_hex(command))
                    self.log.info(f"{clientid} GETINFO received")
                    cafeuser = self.config["cafeuser"]
                    cafepass = self.config["cafepass"]
                    username_dec = cafeuser + "%" + cafepass
                    username_enc = utilities.encryption.textxor(username_dec)
                    # print(username_dec)
                    # print(username_enc)
                    reply = struct.pack("<L", len(username_enc)) + username_enc
                    # print(binascii.b2a_hex(reply))
                    client_socket.send(reply)

                elif command[0:8] == b"\x50\x49\x4e\x47\x20\x20\x20\x20":  # PING
                    self.log.info(f"{clientid} PING received")

                elif len(command) == 5:
                    self.log.warning(f"{clientid} Client failed to log in")

                elif len(command) == 0:
                    self.log.info(f"{clientid} Client ended session")
                    break

                else:
                    if error_count == 1:
                        self.log.info(f"{clientid} UNKNOWN VTT COMMAND {binascii.b2a_hex(command[0:26]).decode()}")
                    error_count += 1
                    if error_count > 5:
                        # self.log.info(f"{clientid} CAS client logged off or errored, disconnecting socket")
                        break

            except:
                self.log.error(f"{clientid} An error occured between the client and the VTT")
                break

        client_socket.close()
        self.log.info(f"{clientid} Disconnected from VTT Server")

class cafeserver:
    def __init__(self, port, config):
        self.__class__ = vttserver
        self.server_type = "CafeServer"
        vttserver.__init__(self, port, config)