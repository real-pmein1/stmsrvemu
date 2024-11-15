import logging
import socket
import socket as real_socket
import struct
import time

import ipcalc

import globalvars
from listmanagers.masterlistmanager import Server, challenge_manager, server_manager
from utilities.master_packethandler import PacketHandler
from utilities.networkhandler import UDPNetworkHandler


# from builtins import str


class MasterServer(UDPNetworkHandler):
    def __init__(self, port, config):
        self.server_type = "MasterSrv"
        super(MasterServer, self).__init__(config, port, self.server_type)  # Create an instance of NetworkHandler

        self.last_unique_id = 100

    def parse_address(self, ip_port_str):
        try:
            ip, port = ip_port_str.split(":")
            port = int(port)  # Convert port to an integer
            return ip, port
        except ValueError:
            # Handle error if input format is not correct
            raise ValueError("Invalid IP:Port format. Expected format 'ip:port'.")

    def reject_connection(self, address, reason):
        self.log.info(f"Reject connection from {address}: {reason}")
        reply = f"{chr(255)}{chr(255)}{chr(255)}{chr(255)}{'l'}\n{reason}"
        self.serversocket.sendto(reply, address)

    def packet_heartbeat(self, data, address):

        packet = PacketHandler(data)
        # Read challenge value
        nChallengeValue = packet.read_string()

        # Read packet sequence number
        seq = packet.read_string()

        # Read current users numbers
        num = packet.read_string()

        # Read protocol versiion
        nprotocol = packet.read_string()

        # Validate protocol
        # if nprotocol != current_protocol:
        #    reject_connection("Outdated protocol.")
        #    return

        # Validate the challenge
        if not challenge_manager.validate_challenge(address, int(nChallengeValue)):
            self.reject_connection(address, "Bad challenge.")
            return

        # Read game dir
        gamedir = packet.read_string()

        # Read server info
        info = packet.read_string()

        ds_ip = address
        if globalvars.public_ip != "0.0.0.0" and str(address[0]) in ipcalc.Network(str(globalvars.server_net)):
            ip_port_str = globalvars.public_ip + ":" + str(address[1])
            ds_ip = self.parse_address(ip_port_str)
        # Update or create a server instance
        server = server_manager.is_server_in_list(ds_ip)
        if not server:
            self.last_unique_id += 1
            server = Server(ds_ip, False, False, int(time.time()), self.last_unique_id + 1, False, False, "", int(num), 0, 0,
                            gamedir, "", "w", False, False, False, info, len(info))
            server_manager.add_server(server)
        else:
            server.time = int(time.time())
            server.players = int(num)
            server.gamedir = gamedir
            server.info = info
            server.info_length = len(info)

    def packet_heartbeat2(self, data, address):
        info = data.decode('iso-8859-1')  # Assuming data is a byte string

        # protocol = int(packet.info_value_for_key(info, "protocol"))
        challenge = int(PacketHandler.info_value_for_key(info, "challenge"))
        # Validate the challenge
        if not challenge_manager.validate_challenge(address, challenge):
            self.reject_connection(address, "Reject connection: Bad challenge.")
            return
        num = int(PacketHandler.info_value_for_key(info, "players"))
        maxplayers = int(PacketHandler.info_value_for_key(info, "max"))
        bots = int(PacketHandler.info_value_for_key(info, "bots"))
        gamedir = PacketHandler.info_value_for_key(info, "gamedir").lower()
        _map = PacketHandler.info_value_for_key(info, "map").lower()
        os = PacketHandler.info_value_for_key(info, "os").lower()
        dedicated = int(PacketHandler.info_value_for_key(info, "dedicated"))
        password = int(PacketHandler.info_value_for_key(info, "password"))
        secure = int(PacketHandler.info_value_for_key(info, "secure"))
        isproxy = int(PacketHandler.info_value_for_key(info, "proxy"))
        isproxytarget = int(PacketHandler.info_value_for_key(info, "proxytarget"))
        proxyaddress = PacketHandler.info_value_for_key(info, "proxyaddress")
        # version = PacketHandler.info_value_for_key(info, "version")
        ds_ip = address  # CLIENT ip address (WAN OR LAN)
        print(globalvars.server_net)
        print(ipcalc.Network(str(globalvars.server_net)))
        print(str(address[0]) in ipcalc.Network(str(globalvars.server_net)))
        print(globalvars.public_ip)
        if globalvars.public_ip != "0.0.0.0" and str(address[0]) in ipcalc.Network(str(globalvars.server_net)):  # DED SERVER ON EMU LAN for WAN servicing
            ip_port_str = globalvars.public_ip + ":" + str(address[1])
            ds_ip = self.parse_address(ip_port_str)
            ds_ip_local = address  # FOR SAME-LAN DED SERVER
            print(ds_ip)
            print(ds_ip_local)
            server_local = server_manager.is_server_in_list(ds_ip_local)
        # Update or create a server instance
        server = server_manager.is_server_in_list(ds_ip)

        if server is None:  # Check if the server was not found
            self.last_unique_id += 1

            server = Server(ds_ip, False, False, 0, self.last_unique_id + 1, isproxy, isproxytarget, proxyaddress,
                            num, maxplayers, bots, gamedir, _map, os, password, dedicated, secure, info, len(info))
            server_manager.add_server(server)
        else:
            server.time = int(time.time())  # Now this should be safe
            server.players = int(num)
            server.max = maxplayers
            server.bots = bots
            server.gamedir = gamedir
            server.map = _map
            server.os = os
            server.password = password
            server.dedicated = dedicated
            server.secure = secure
            server.isproxy = isproxy
            server.isProxyTarget = isproxytarget
            server.proxyTarget = proxyaddress
            server.info = info
            server.info_length = len(info)

        if server_local is None:  # Check if the LOCAL ded server was not found
            self.last_unique_id += 1

            server = Server(ds_ip_local, False, False, 0, self.last_unique_id + 1, isproxy, isproxytarget, proxyaddress,
                            num, maxplayers, bots, gamedir, _map, os, password, dedicated, secure, info, len(info))
            server_manager.add_server(server)
        else:
            server.time = int(time.time())  # Now this should be safe
            server.players = int(num)
            server.max = maxplayers
            server.bots = bots
            server.gamedir = gamedir
            server.map = _map
            server.os = os
            server.password = password
            server.dedicated = dedicated
            server.secure = secure
            server.isproxy = isproxy
            server.isProxyTarget = isproxytarget
            server.proxyTarget = proxyaddress
            server.info = info
            server.info_length = len(info)

        server_manager.print_all_servers()

    def packet_getchallenge(self, data, address):
        existing_challenge = challenge_manager.check_challenge(address)
        if existing_challenge is not None:
            challenge_value = existing_challenge
        else:
            challenge_value = challenge_manager.create_challenge(address)
        # Construct the reply
        reply = b'\xff\xff\xff\xff\x73\x0a'  # struct.pack('>BBBBB', 255, 255, 255, 255, ord('s'))

        reply += struct.pack('<I', challenge_value)
        self.serversocket.sendto(reply, address)

    def packet_shutdown(self, data, address):
        server_manager.remove_server_by_address(address)

    def packet_get_servers(self, data, address):
        # Initialize the reply string with a specific header
        reply = bytearray(struct.pack('>Ib', 0xFFFFFFFF, 0x66))  # 0x66 for M2A_SERVERS

        for server in server_manager.get_all_servers():
            # Uncomment the following lines if you want to filter LAN or proxy servers
            if server.islan:
                continue

            if len(reply) + 6 > 1024:
                break

            ip_packed = struct.pack('>I', int.from_bytes(server.address[0], 'big'))
            port_packed = struct.pack('>H', server.address[1])
            reply.extend(ip_packed + port_packed)

            self.serversocket.sendto(reply, address)

    def packet_get_servers_batch_responder(self, address, truenextid, criteria):
        send_info = truenextid & (1 << 31)
        nextid = truenextid & ~(1 << 31)

        # Convert nextid to an IP address
        nextid_ip = real_socket.inet_ntoa(struct.pack('!I', nextid))

        server_list = server_manager.get_all_servers()
        # print(repr(truenextid))
        # Construct the response packet
        reply = bytearray(b'\xff\xff\xff\xff\x66')
        reply += b"\x0a"
        i = 6

        savepos = i
        reply.extend(bytearray(6))  # Placeholder for the final truenextid
        i += 4

        for server in server_list:
            server_ip_int = struct.unpack('!I', real_socket.inet_aton(server.address[0]))[0]
            if nextid_ip != "0.0.0.0":
                if server_ip_int <= nextid:
                    continue  # Skip servers until reaching the one after nextid
            # if criteria is not None and not server_manager.server_passes_criteria(server, criteria) :
            #    continue

            if send_info:
                # Check if adding server info will exceed reply size
                if i + 6 + len(server.info) >= 1024:
                    self.log.warning(f"if send_info (exceeded 1024)")
                    break
                server_info = server.info.encode("iso-8859-1")
                server_address = struct.unpack('!I', server.address[0].encode("iso-8859-1"))[0]
                server_port = server.address[1]
                reply.extend(struct.pack('!I', server_address))
                reply.extend(struct.pack('!H', server_port))
                reply.extend(server_info + b'\0')
                i += 6 + len(server_info) + 1
            else:
                # print(f"else send_info {server.address[0]}")
                if i + 6 >= 1024:
                    self.log.warning("else send_info (exceeded 1024)")
                    break
                ip_bytes = real_socket.inet_aton(server.address[0])
                # Pack IP address and port in big endian format
                packed_data = struct.pack('!4sH', ip_bytes, server.address[1])
                reply.extend(packed_data)
                i += 6
        # server_manager.print_all_servers()

        # Update the truenextid in the reply, not needed until someone wants to host a network with thousands of servers
        """if i != 6 :  # If at least one server info is added
            # Ensure there are remaining servers in the list
            if server_list[nextid :] :
                # Check if the last server in the response is also the last server in the server list
                if server_list[nextid :][-1] == server_list[-1] :
                    # No more servers available beyond this response
                    new_truenextid = struct.unpack('!I', real_socket.inet_aton('0.0.0.0'))[0]  # '0.0.0.0:0' as int
                else :
                    # There are more servers available beyond this response
                    last_server_ip = server_list[nextid :][-1].address[0]
                    last_server_port = server_list[nextid :][-1].address[1]
                    last_server_ip_int = struct.unpack('!I', real_socket.inet_aton(last_server_ip))[0]
                    new_truenextid = (last_server_ip_int << 16) | last_server_port
            else :
                # No more servers available
                new_truenextid = struct.unpack('!I', real_socket.inet_aton('0.0.0.0'))[0]

            if send_info :
                new_truenextid |= (1 << 31)
            struct.pack_into('!I', reply, savepos, new_truenextid)
        else :  # No servers added, so no more servers available
            new_truenextid = struct.unpack('!I', real_socket.inet_aton('0.0.0.0'))[0]  # '0.0.0.0:0' as int
            if send_info :
                new_truenextid |= (1 << 31)
            struct.pack_into('!I', reply, savepos, new_truenextid)"""
        # print(repr(reply))
        reply += b'\0\0\0\0\0\0'
        # Send the packet
        self.serversocket.sendto(reply, address)

    def packet_get_batch(self, data, address):
        packet_handler = PacketHandler(data)
        truenextid = packet_handler.read_long()
        self.log.info("Get Batch server list requested")
        self.packet_get_servers_batch_responder(address, truenextid, criteria = None)

    def packet_get_batch2(self, data, address):
        packet_handler = PacketHandler(data)
        truenextid = packet_handler.read_long()
        self.log.info("Get Batch server list requested")
        info = packet_handler.read_string()
        criteria = {}
        # print(repr(info))
        if info:
            criteria = server_manager.parse_criteria_from_info(info)
        # print(repr(criteria))
        self.packet_get_servers_batch_responder(address, truenextid, criteria)

    # .encode("iso-8859-1")

    def packet_get_motd(self, data, address):
        f = open("motd.txt", "rb")
        motd = f.read()
        f.close()
        # Constructing the byte array
        header_bytes = bytes([255, 255, 255, 255, ord('h')])
        newline_bytes = b"\r\n"

        # Combining the bytes and the string
        reply = header_bytes + newline_bytes + motd

        # If you need the result as a bytes object, it's already in the correct format
        # If you need it as a string (for some reason), you can decode it, but be cautious about encoding compatibility
        reply_str = reply.decode('iso-8859-1')  # or another appropriate encoding
        self.serversocket.sendto(reply_str, address)

    def packet_ping(self, data, address):
        self.serversocket.sendto(bytes([255, 255, 255, 255, ord('j')]), address)

    def packet_nack(self, data, address):
        # Implement the logic for A2A_NACK packet
        pass

    def packet_Default(self, data, address):
        self.log.info(f"Recieved Unknown Packet: {repr(data)}")

    def packet_get_masterlist(self, input_bytes: bytes, address) -> bytes:
        # Write the initial response header
        response = struct.pack('!BBBBc', 255, 255, 255, 255, b'w')
        response += b"\r\n"
        if str(address[0]) in ipcalc.Network(str(globalvars.server_net)):  # or globalvars.public_ip == str(client_address[0]):
            server_ip = globalvars.server_ip
        else:
            server_ip = globalvars.public_ip

        response += struct.pack('!I', 0xffffffff)
        response += socket.inet_aton(server_ip)  # authservers, for steam that is userid validation
        response += struct.pack('!H', int(self.config['validation_port']))

        response += struct.pack('!I', 0xffffffff)
        response += socket.inet_aton(server_ip)  # titan servers, won only but set it anyway so it doesnt break hl
        response += struct.pack('!H', int(self.config['validation_port']))
        # Add the divider
        response += struct.pack('!I', 0xffffffff)
        response += socket.inet_aton(server_ip)
        response += struct.pack('!H', int(self.config['masterhl2_server_port']))
        self.serversocket.sendto(response, address)

    command_handlers = {
            b"0":packet_heartbeat2,
            b'q':packet_getchallenge,
            b'a':packet_heartbeat,
            b'b':packet_shutdown,
            b'c':packet_get_servers,
            b'e':packet_get_batch,
            b'1':packet_get_batch2,
            b'g':packet_get_motd,
            b'i':packet_ping,
            b'k':packet_nack,
            b'v':packet_get_masterlist,
    }

    def handle_client(self, data, address, fromCM = False):
        clientid = str(address) + ": "
        self.log.info(clientid + "Connected to Master Server")
        self.log.debug(clientid + ("Received message: %s, from %s" % (data, address)))
        dedsrv_port = 27015
        # header = data[:4]
        expected_header = b'\xff\xff\xff\xff'
        # command = data[4:5]
        # data = data[5:]
        # if header == expected_header:
        if data.startswith(expected_header):
            data = data[4:]
        handler = self.command_handlers.get(data[0:1], self.packet_Default)
        # print(repr(data))
        if fromCM:
            handler(data, address)
        else:
            try:
                handler(self, data, address)
            except:
                handler(data, address)  # FOR BETA1 CS14 - FIX IF THIS FAILS FOR OTHER VERSIONS
        # else:
        #    self.log.info("Header is incorrect!")
        #    return None  # Invalid header

        # self.serversocket.close()

        self.log.info(clientid + "Disconnected from Master Server")