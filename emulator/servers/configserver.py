import binascii
import logging
import socket
import struct
import time

from Crypto.Hash import SHA

import ipcalc

import globalvars
import utils
from utilities import blobs, cdr_manipulator, encryption
from servers.managers.dirlistmanager import manager as dirmanager
from servers.managers import serverlist_utilities
from utilities.database import ccdb
from utilities.networkhandler import TCPNetworkHandler


class configserver(TCPNetworkHandler):
    def __init__(self, port, config):
        self.server_type = "ConfigServer"
        # Create an instance of NetworkHandler
        super(configserver, self).__init__(config, port, self.server_type)

    def handle_client(self, client_socket, client_address):
        # Load this everytime a client connects, this ensures that we can change the blob without restarting the server
        # firstblob = ccdb.load_filesys_blob() # FIXME Deprecate this as it's not needed
        
        firstblob = ccdb.load_ccdb('blob')

        clientid = str(client_address) + ": "

        if str(client_address[0]) in globalvars.server_network:
            islan = True
        else:
            islan = False
        self.log.info(clientid + "Connected to Config Server")
        valid_version = 0
        command = client_socket.recv(4)
        #is2003 = False
		# \x02 FOR RETAIL STEAM_0
        if  command in [b"\x00\x00\x00\x00", b"\x00\x00\x00\x01", b"\x00\x00\x00\x02"]:
            #is2003 = True
            client_socket.send(b"\x01")
            valid_version = 1
        elif command == b"\x00\x00\x00\x03":
            client_socket.send(b"\x01" + socket.inet_aton(client_address[0]))
            valid_version = 1
        else:
            self.log.info(clientid + "Invalid head message: " + binascii.b2a_hex(command).decode())
            valid_version = 0

        if valid_version == 1:
            command = client_socket.recv_withlen()

            if len(command) == 1:
                # SEND CCDB
                if command == b"\x01":
                    self.log.info(clientid + "Sending first blob")

                    if globalvars.record_ver == 1:
                        # This means a user is trying to go from a retail client to a beta client.  This can cause problems due to the difference in CCR Format
                        # To fix this, we just add the missing entries to the CCR and send it
                        if isinstance(firstblob, dict):
                            modified_firstblob = firstblob
                        else:
                            modified_firstblob = blobs.blob_unserialize(firstblob)
                        modified_firstblob[b'\x00\x00\x00\x00'] = b'\x03\x00\x00\x00'
                        new_entries = {
                                b'\x04\x00\x00\x00':b'\x00\x00\x00\x00',
                                b'\x05\x00\x00\x00':b'\x00\x00\x00\x00',
                                b'\x06\x00\x00\x00':b'\x00\x00\x00\x00',
                                b'\x07\x00\x00\x00':b'boo\x00',
                                b'\x08\x00\x00\x00':b'\x00\x00\x00\x00',
                                b'\x09\x00\x00\x00':b'foo\x00',
                                b'\x0a\x00\x00\x00':b'\x00\x00\x00\x00',
                                b'\x0b\x00\x00\x00':b'bar\x00',
                                b'\x0c\x00\x00\x00':b'\x00\x00\x00\x00',
                                b'\x0d\x00\x00\x00':b'foo\x00',
                                b'\x0e\x00\x00\x00':
                                                    {
                                                            b'cac':b'\x00\x00\x00\x00',
                                                            b'cas':b'\x00\x00\x00\x00'
                                                    },
                                b'\x0f\x00\x00\x00':b'\x00\x00\x00\x00'
                        }
                        modified_firstblob.update(new_entries)
                        new_frstblob = blobs.blob_serialize(modified_firstblob)
                        client_socket.send_withlen(new_frstblob, False)
                    else:
                        # steamui_ver is a string for record_ver 0 (beta v1 2002), integer otherwise
                        if isinstance(globalvars.steamui_ver, int) and globalvars.steamui_ver >= 61:
                            globalvars.tgt_version = "2"  # config file states 2 as default
                            self.log.debug(clientid + "TGT version set to 2")
                        else:
                            globalvars.tgt_version = "1"  # old beta clients or steamui_ver < 61
                            self.log.debug(clientid + "TGT version set to 1")

                        if isinstance(firstblob, dict):
                            firstblob = blobs.blob_serialize(firstblob)

                        client_socket.send_withlen(firstblob, False)
                # SEND NET KEY
                elif command == b"\x04":
                    self.log.info(clientid + "Sending network key")
                    # Use precomputed network key reply (computed once at startup)
                    client_socket.send(encryption.network_key_reply)
                # GETCURRENTAUTHFAILSAFEMODE
                elif command == b"\x05":
                    self.log.info(clientid + "confserver command 5, GetCurrentAuthFailSafeMode, sending zero reply")
                    client_socket.send(b"\x00")
                # GETCURRENTBILLINGFAILSAFEMODE
                elif command == b"\x06":
                    self.log.info(clientid + "confserver command 6, GetCurrentBillingFailSafeMode, sending zero reply")
                    client_socket.send(b"\x00")
                # GETCURRENTCONTENTFAILSAFEMODE
                elif command == b"\x07":
                    self.log.info(clientid + "Sending out list of Content Servers")
                    self.log.debug(clientid + "Sending GetCurrentContentFailSafeMode")

                    # client_socket.send(binascii.a2b_hex("0001312d000000012c"))
                    if globalvars.aio_server:
                        server_list = dirmanager.get_server_list("CSDServer", islan, single=1)
                    else:
                        server_list = serverlist_utilities.request_server_list("CSDServer", single=1)
                    if server_list:
                        bin_ip = utils.encodeIP(server_list[0])
                    else:
                        if str(client_address[0]) in ipcalc.Network(str(globalvars.server_net)):
                            bin_ip = utils.encodeIP((self.config["server_ip"], self.config["content_server_port"]))
                        else:
                            bin_ip = utils.encodeIP((self.config["public_ip"], self.config["content_server_port"]))

                    reply = struct.pack(">H", 1) + bin_ip

                    client_socket.send_withlen(reply)
                # GETCURRENTSTEAM3LOGONPERCENT
                elif command == b"\x08":
                    self.log.info(clientid + "confserver command 8, GetCurrentSteam3LogonPercent, sending zero reply")
                    client_socket.send(b"\x00\x00\x00\x00")
                # INVALID COMMAND
                else:
                    self.log.warning(clientid + "Invalid command: " + binascii.b2a_hex(command).decode())
                    client_socket.send(b"\x00")
            # SEND CDDB
            elif command[0:1] == b"\x02" or command[0:1] == b"\x09":

                if command[0:1] == b"\x09":
                    client_socket.send(binascii.a2b_hex("00000001312d000000012c"))

                while globalvars.compiling_cdr:
                    time.sleep(1)

                #if is2003:
                #    self.log.debug("Sending 2003 blob")
                #    blob = cdr_manipulator.read_blob(islan)
                #    #blob = cdr_manipulator.fixblobs_config(islan, True)
                #else:
                #    self.log.debug("Sending 2004+ blob")
                #    blob = cdr_manipulator.read_blob(islan)
                blob = cdr_manipulator.read_blob(islan)

                checksum = SHA.new(blob).digest()

                if checksum == command[1:]:
                    self.log.info(clientid + "Client has matching checksum for secondblob")
                    self.log.debug(clientid + "We validate it: " + binascii.b2a_hex(command).decode())
                    client_socket.send(b"\x00\x00\x00\x00")

                else:
                    self.log.info(clientid + "Client didn't match our checksum for secondblob")
                    self.log.debug(clientid + "Sending new blob: " + binascii.b2a_hex(command).decode())

                    client_socket.send_withlen(blob, False)  # false for not showing in log

            else:
                self.log.info(clientid + "Invalid message: " + binascii.b2a_hex(command).decode())

        client_socket.close()

        self.log.info(clientid + "disconnected from Config Server")