import binascii
import logging
import struct
import threading
import time
from datetime import datetime

import ipcalc

import globalvars
import utils
from listmanagers.dirlistmanager import manager
from listmanagers.serverlist_utilities import forward_heartbeat, send_listrequest, unpack_removal_info, unpack_server_info
from utilities.networkhandler import TCPNetworkHandler

dirConnectionTotalCount = 0


def expired_servers_thread():
    while True:
        time.sleep(3600)  # 1 hour
        manager.remove_old_entries()


class directoryserver(TCPNetworkHandler):

    def __init__(self, port, config):

        self.server_type = "masterdirserver" if globalvars.dir_ismaster == "true" else "dirserver"
        self.config = config

        super(directoryserver, self).__init__(config, int(port), self.server_type)

        if globalvars.public_ip == "0.0.0.0":
            server_ip = globalvars.server_ip_b
        else:
            server_ip = globalvars.public_ip_b

        if self.server_type == "masterdirserver":  # add ourselves to the serverlist as a directoryserver type,
            # with a 0'd timestamp to indicate that it cannot be removed
            manager.add_server_info(server_ip,globalvars.server_ip_b, self.config["dir_server_port"], self.server_type, 1)
            # log = logging.getLogger("master_dirserver")
        else:
            self.server_type = "dirserver"
            self.server_info = {
                'wan_ip': server_ip,
                'lan_ip': globalvars.server_ip_b,
                'port': int(self.port),
                'server_type': self.server_type,
                'timestamp': int(time.time())
            }
        self.log = logging.getLogger("DirectorySRV")

        thread = threading.Thread(target = expired_servers_thread)  # Thread for removing servers older
        # than 1 hour
        thread.daemon = True
        thread.start()

        # We are a slave, request serverlist
        if globalvars.dir_ismaster != "true":  # request list from 'master' directory server
            self.log.info("Connecting to Master Directory Server")
            recieved_list = send_listrequest()  # since we are a slave, get the full current list from
            # the master
            index = 0
            while index <= len(recieved_list):
                wan_ip = recieved_list[index]
                lan_ip = recieved_list[index + 1]
                port = recieved_list[index + 2]
                server_type = recieved_list[index + 3]
                timestamp = recieved_list[index + 4]
                manager.add_server_info(wan_ip, lan_ip, int(port), server_type)

        # datarate_thread = threading.Thread(target=self.netstats)
        # datarate_thread.daemon = True
        # datarate_thread.start()
        else:
            self.slavedir_list = []  # Initialize the 'Slave' Directory server list so we can keep track about whom to forward add-to-list requests on

    def netstats(self):
        while True:
            incoming_rate, outgoing_rate = self.calculate_data_rates()
            time.sleep(0.5)
            print(incoming_rate)

    def handle_client(self, client_socket, client_address):
        global dirConnectionTotalCount

        clientid = str(client_address) + ": "

        if globalvars.dir_ismaster == "true":
            self.log.info(f"{clientid} Connected to Directory Server")
        else:
            self.log.info(f"{clientid} Connected to Slave/Peer Directory Server")

        # Determine if connection is local or external
        if str(client_address[0]) in ipcalc.Network(str(globalvars.server_net)) or globalvars.public_ip == "0.0.0.0":
            islan = True
        else:
            islan = False

        msg = client_socket.recv(4)

        self.log.debug(binascii.b2a_hex(msg).decode())

        if msg == b"\x05\xaa\x6c\x15":  # Slave to master serverlist request
            self.handle_slavereq(clientid, client_socket)

        elif msg == b"\x00\x3e\x7b\x11":  # Add/Remove Server from List
            self.handle_processServer(clientid, client_socket)

        elif msg == b"\x00\x00\x00\x01" or msg == b"\x00\x00\x00\x02":

            dirConnectionTotalCount += 1  # only count user's, ignore heartbeat/other servers

            client_socket.send(b"\x01")
            msg = client_socket.recv_withlen()
            command = msg[0:1]
            self.log.debug(binascii.b2a_hex(command).decode())
            reply = b"\x00\x00"

            if command == b"\x00" or command == b"\x12" or command == b"\x1a":  # Send out list of authservers
                # According to TIN 0x12 is mailcheckserver so most likely authentication OR CM
                self.log.info(f"{clientid}Sending out list of Auth Servers")

                reply = manager.get_and_prep_server_list("AuthServer", islan)

            elif command == b"\x03":  # Send out list of Configuration Servers
                self.log.info(f"{clientid}Sending out list of Configuration Servers")

                reply = manager.get_and_prep_server_list("ConfigServer", islan)

            elif command == b"\x06" or command == b"\x05":  # send out content list servers
                self.log.info(f"{clientid}Sending out list of Content Server Directory Servers")

                reply = manager.get_and_prep_server_list("CSDServer", islan)

            elif command == b"\x0f" or command == b"\x18" or command == b"\x1e":  # goldsrc, src and rdkf master server
                self.log.info(f"{clientid}Sending out list of Master Servers")

                reply = manager.get_and_prep_server_list("MasterSrv", islan)

            elif command == b"\x14":  # send out CSER server
                self.log.info(f"{clientid}Sending out list of CSER Servers")

                reply = manager.get_and_prep_server_list("CSERServer", islan)

            elif command == b"\x0A":  # remote file harvest master server
                self.log.info(f"{clientid}Sending out list of Remote File Harvest Master Servers")

                reply = manager.get_and_prep_server_list("harvestserver", islan)

            elif command == b"\x1c":  # According to TIN this is for the slave authentication server
                if binascii.b2a_hex(msg).decode() == "1c600f2d40":
                    self.log.info(f"{clientid} Sending out CSDS and 2 Authentication Servers")

                    # Get server lists using the new method
                    csds_servers = manager.get_server_list("CSDServer", islan, 1)
                    auth_servers = manager.get_server_list("AuthServer", islan)

                    # Pack the number of servers into the reply
                    reply = struct.pack(">H", 3)  # Total number of servers in the reply

                    # Handle CSDS server
                    if csds_servers:
                        ip_port_tuple = csds_servers[0]  # csds_servers is now a list of (ip, port) tuples
                        reply += utils.encodeIP(ip_port_tuple)
                    else:
                        reply += b"\x00\x00"  # No CSDS server, append zeros

                    # Handle Auth servers
                    if len(auth_servers) > 0:
                        # First auth server
                        ip_port_tuple = auth_servers[0]  # First auth server tuple (ip, port)
                        reply += utils.encodeIP(ip_port_tuple)
                        if len(auth_servers) >= 2:
                            # Second auth server if available
                            ip_port_tuple = auth_servers[1]  # Second auth server tuple (ip, port)
                            reply += utils.encodeIP(ip_port_tuple)
                        else:
                            # Duplicate the first auth server tuple if only one available
                            reply += utils.encodeIP(ip_port_tuple)
                    else:
                        # No Auth servers, append zeros twice for 2 servers
                        reply += b"\x00\x00" * 2

                # FIXME figure out what the extra hex data actually stands for in the following statements:
                else:  # elif binascii.b2a_hex(msg).decode() == "1cb5aae840":  # Used for Subscription & CDKey Registration
                    self.log.info(f"{clientid}Sending out list of Auth Servers For Transactions {binascii.b2a_hex(msg).decode()}")

                    reply = manager.get_and_prep_server_list("AuthServer", islan)

            elif command == b"\x0B":  # master VCDS Validation (New valve cdkey Authentication) server
                self.log.info(clientid + "Sending out list of VCDS Validation (New valve CDKey Authentication) Master Servers")

                reply = manager.get_and_prep_server_list("ValidationSRV", islan)

            elif command == b"\x07":  # Ticket Validation master server
                self.log.info(f"{clientid}Sending out list of Ticket Validation Master Servers")

                reply = manager.get_and_prep_server_list("ValidationSRV", islan)

            elif command == b"\x10":  # Friends master server
                self.log.info(f"{clientid}Sending out list of Messaging Servers")

                reply = manager.get_and_prep_server_list("messagingserver", islan)

            elif command == b"\x0D" or command == b"\x0E":  # all MCS Master Public Content master server
                self.log.info(f"{clientid}Sending out list of MCS Master Public Content Master Servers")

                reply = manager.get_and_prep_server_list("CSDServer", islan)

            elif command == b"\x15":  # Log Processing Server's master server
                self.log.info(f"{clientid}Sending out list of Log Processing Master Servers")

                ip_port_tuple = (globalvars.public_ip, int("27021"))

                bin_ip = utils.encodeIP(ip_port_tuple)

                reply = struct.pack(">H", 1) + bin_ip

            elif command == b"\x09":  # system status master server
                self.log.info(f"{clientid}Sending out list of System Status Master Servers")

                ip_port_tuple = (globalvars.public_ip, int("27021"))

                bin_ip = utils.encodeIP(ip_port_tuple)

                reply = struct.pack(">H", 1) + bin_ip

            elif command == b"\x1D":  # BRS master server (Billing Bridge server?)
                self.log.info(f"{clientid}Sending out list of BRS Master Servers")

                ip_port_tuple = (globalvars.public_ip, int("27021"))

                bin_ip = utils.encodeIP(ip_port_tuple)

                reply = struct.pack(">H", 1) + bin_ip

            elif command == b"\x08":  # global transaction manager master server
                self.log.info(f"{clientid}Sending out list of Global Transaction Manager Master Servers")

                ip_port_tuple = (globalvars.public_ip, int("27021"))

                bin_ip = utils.encodeIP(ip_port_tuple)

                reply = struct.pack(">H", 1) + bin_ip

            elif command == b"\x04":  # server configuration  master server
                self.log.info(f"{clientid}Sending out list of Server Configuration Master Servers")

                ip_port_tuple = (globalvars.public_ip, int("27021"))

                bin_ip = utils.encodeIP(ip_port_tuple)

                reply = struct.pack(">H", 1) + bin_ip

            elif command == b"\x01":  # administration authentication master server
                self.log.info(f"{clientid}Sending out list of Administration Authentication Master Servers")

                ip_port_tuple = (globalvars.public_ip, int("27021"))

                bin_ip = utils.encodeIP(ip_port_tuple)

                reply = struct.pack(">H", 1) + bin_ip

            elif command == b"\x11":  # administration billing bridge master server
                self.log.info(f"{clientid}Sending out list of Administration Billing Bridge Master Servers")

                ip_port_tuple = (globalvars.public_ip, int("27021"))

                bin_ip = utils.encodeIP(ip_port_tuple)

                reply = struct.pack(">H", 1) + bin_ip

            elif command == b"\x02":  # administration configuration master server
                self.log.info(f"{clientid}Sending out list of Administration Configuration Master Servers")

                ip_port_tuple = (globalvars.public_ip, int("27021"))

                bin_ip = utils.encodeIP(ip_port_tuple)

                reply = struct.pack(">H", 1) + bin_ip

            elif command == b"\x16":  # administration log processing master server
                self.log.info(f"{clientid}Sending out list of Administration Log Processing Master Servers")

                ip_port_tuple = (globalvars.public_ip, int("27021"))

                bin_ip = utils.encodeIP(ip_port_tuple)

                reply = struct.pack(">H", 1) + bin_ip

            elif command == b"\x13":  # administration authentication master server
                self.log.info(f"{clientid}Sending out list of Administration Authentication Master Servers")

                ip_port_tuple = (globalvars.public_ip, int("27021"))

                bin_ip = utils.encodeIP(ip_port_tuple)

                reply = struct.pack(">H", 1) + bin_ip

            elif command == b"\x17":  # CSER Administration master server
                self.log.info(f"{clientid}Sending out list of CSER Administration Master Servers")

                ip_port_tuple = (globalvars.public_ip, int("27021"))

                bin_ip = utils.encodeIP(ip_port_tuple)

                reply = struct.pack(">H", 1) + bin_ip

            elif command == b"\x1B":  # VTS (validation ticket server) Administration master server
                self.log.info(f"{clientid}Sending out list of VTS Administration Master Servers")

                ip_port_tuple = (globalvars.public_ip, int("27021"))

                bin_ip = utils.encodeIP(ip_port_tuple)

                reply = struct.pack(">H", 1) + bin_ip

            else:
                self.log.info(f"{clientid}Sent unknown command: " + command.decode() + " Data: " + binascii.b2a_hex(msg).decode())
                reply == b"\x00\x00"

            client_socket.send_withlen(reply)
            client_socket.close()
        else:
            self.log.error(clientid + "Invalid Message: " + binascii.b2a_hex(msg).decode())

        client_socket.close()
        self.log.info(f"{clientid}disconnected from Directory Server")

    def handle_slavereq(self, clientid, client_socket):
        list_size, masterlist = manager.pack_serverlist()
        packed_length = struct.unpack('!I', list_size[:4])[0]
        self.log.info(f"{clientid} Slave DIR Server Requested Full Serverlist")
        client_socket.send(packed_length)  # handshake confirmed

        size_response = client_socket.recv(1)

        if size_response == b'\x01':
            client_socket.send(masterlist)
            slave_response = client_socket.recv(1)

            if slave_response == b'\x01':
                client_socket.close()
                self.log.info(f"{clientid} Slave DIR Server Disconnected")

    def handle_processServer(self, clientid, client_socket):
        client_socket.send(b"\x01")  # handshake confirmed
        msg = client_socket.recv(1024)
        command = msg[0:1]
        self.log.debug(binascii.b2a_hex(command).decode())

        if command == b"\x1a":  # Add server entry to the list
            wan_ip, lan_ip, port, server_type, timestamp = unpack_server_info(msg)
            try:
                client_socket.inet_aton(wan_ip)
            except client_socket.error:
                self.log.warning(f"{clientid} Sent bad heartbeat packet: {binascii.b2a_hex(msg).decode()}")
                client_socket.send(b"\x00")  # message decryption failed, the only response we give for failure
                client_socket.close()
                self.log.info(f"{clientid} Disconnected from Directory Server")
                return

            manager.add_server_info(wan_ip, lan_ip, int(port), server_type, 0)

            client_socket.send(b"\x01")
            self.log.debug(f"[{server_type}] {clientid} Added to Directory Server")

            self.log.debug("WAN IP Address: " + wan_ip)
            self.log.debug("LAN IP Address: " + lan_ip)
            self.log.debug("Port: " + str(port))
            self.log.debug("Server Type: " + server_type)
            self.log.debug("Timestamp: " + datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S'))

            if server_type == "dirserver" and globalvars.dir_ismaster == "true":  # only add to the slave list if you are master
                self.slavedir_list.append([wan_ip, lan_ip, int(port)])

            if globalvars.dir_ismaster != "true":  # relay any requests to the master server as well
                client_socket.sendto(msg, str(globalvars.config["masterdir_ipport"]))
            else:  # relay anything going to the master to all slaves.
                if len(self.slavedir_list) != 0:
                    for entry in self.slavedir_list:
                        if entry[0] != wan_ip and int(entry[2]) != int(port):  # make sure we aren't sending the slave server its own heartbeat...
                            forward_heartbeat(wan_ip, port, msg)

        elif command == b"\x1d":  # Remove server entry from the list
            wan_ip, port, server_type = unpack_removal_info(msg)
            try:
                client_socket.inet_aton(wan_ip)
            except client_socket.error:
                self.log.warning(f"{clientid} Sent bad removal request packet: {binascii.b2a_hex(msg).decode()}")
                client_socket.send(b"\x00")  # message decryption failed, the only response we give for failure
                client_socket.close()
                self.log.info(f"{clientid} Disconnected from Directory Server")
                return

            if manager.remove_entry(wan_ip, port, server_type) is True:
                client_socket.send(b"\x01")
                self.log.info(f"[{server_type}] {clientid} Removed server from Directory Server")
                if globalvars.dir_ismaster != "true":  # relay any requests to the master server aswell
                    client_socket.sendto(msg, str(self.config["masterdir_ipport"]))
            else:  # couldnt remove server because: doesnt exists, problem with list
                client_socket.send(b"\x01")
                self.log.info(f"[{server_type}] {clientid} There was an issue removing the server from Directory Server")