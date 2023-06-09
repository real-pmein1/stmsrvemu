import datetime
import threading, logging, struct, binascii, time, datetime
import time
import utilities
import emu_socket
import globalvars
import serverlist_utilities
import steamemu.logger
import socket as pysocket

from serverlist_utilities import heartbeat

server_list = []
log = logging.getLogger("masterdirsrv")

class directoryserver(threading.Thread):
    global server_list
    global log
    
    def __init__(self, port, config):
        threading.Thread.__init__(self)
        self.port = int(port)
        self.config = config
        self.socket = emu_socket.ImpSocket()
 
        if globalvars.is_masterdir == 1 :
            
            #add ourself to the serverlist as a directoryserver type, with a 0'd timestamp to indicate that it cannot be removed
            self.add_server_info(globalvars.serverip, self.config["dir_server_port"], "masterdirsrv", "0000-00-00 00:00:00")
        else:
            log = logging.getLogger("slavedirsrv")
            log.info("Connecting to Master Directory Server")
            #self.sendto("\x00\x3d\x7b\x11", self.masterdir_ip, str(self.masterdir_port))
            #msg = clientsocket.recv(1) #waiting for handshake response
            
            #if msg == "\x01" and len(msg) <= 1 :
                #clientsocket.send("\x55")
                #wait for list of server's
            # Start the thread for dir registration heartbeat, only
            thread2 = threading.Thread(target=self.heartbeat_thread)
            thread2.daemon = True
            thread2.start()
            
        # Start the thread for removing expired servers
        thread = threading.Thread(target=self.expired_servers_thread)
        thread.daemon = True
        thread.start()

        
    def run(self):        
        self.socket.bind((globalvars.serverip, self.port))
        self.socket.listen(5)

        while True:
            (clientsocket, address) = self.socket.accept()
            threading.Thread(target=self.handle_client, args=(clientsocket, address)).start()

    def handle_client(self, clientsocket, address):
        #threading.Thread.__init__(self)
        #check if we are a master or a slave. if we are a slave, make sure to send the master a request to initiate to add itself to the master
        if globalvars.is_masterdir == 1:           
            clientid = str(address) + ": "
            log.info(clientid + "Connected to Directory Server")
            
        else:           
            clientid = str(address) + ": "
            log.info(clientid + "Connected to Slave Directory Server")
               
        msg = clientsocket.recv(4)
        log.debug(binascii.b2a_hex(msg))
        
        if msg == "\x00\x3e\x7b\x11" :
            clientsocket.send("\x01") # handshake confirmed
    
            msg = clientsocket.recv(1024)
            command = msg[0]
            
            log.debug(binascii.b2a_hex(command))
            
            if command == "\x1c":
                decrypted_info = utilities.decrypt(msg[1:], globalvars.peer_password)
                # Add single server entry to the list
                # Extract the server info
                ip = decrypted_info[:4]
                port = struct.unpack("H", decrypted_info[4:6])[0]
                server_type = decrypted_info[6:].strip('\x00')
                self.add_server_info(str(pysocket.inet_ntoa(ip)), str(port), str(server_type))
                clientsocket.send("\x01")
                log.info(server_type + " " +clientid + "Added  to Directory Server")

            elif command == "\x1d":
                # Remove server entry from the list
                decrypted_msg = utilities.decrypt(msg, globalvars.peer_password)
                if decrypted_msg is None:
                    log.warning(clientid + "Failed to decrypt packet: " + binascii.b2a_hex(msg))
                    clientsocket.send("\x00") #message decryption failed, the only response we give for failure
                    return

                ip, port, server_type = self.extract_packet_data(decrypted_msg)
                if self.remove_server_info(ip, port, server_type):
                    clientsocket.send("\x01")
                    log.info(server_type + " " +clientid + "Removed from Directory Server")
                    if globalvars.is_masterdir != 1:
                        #send any requests to add or remove to the master server aswell
                        clientsocket.sendto(msg, self.masterdir_ipport)

            elif command == "\x55" :   #NOT FUNCTIONAL YET; the master serer does not send the serverlist yet
                clientsocket.send("\x01")
                msg = clientsocket.recv_withlen()
                # Recieve Current server List From Master
                decrypted_msg = utilities.decrypt(msg[1:], globalvars.peer_password)
                if decrypted_msg is None:
                    log.warning(clientid + "Failed to decrypt packet: " + binascii.b2a_hex(msg))
                    clientsocket.send("\x00") #message decryption failed, the only response we give for failure
                    return
                else:
                    receive_server_list() #add all servers in list to our list
                
        elif msg == "\x00\x00\x00\x01" or msg == "\x00\x00\x00\x02":
            clientsocket.send("\x01")

            msg = clientsocket.recv_withlen()
            command = msg[0]
            log.debug(binascii.b2a_hex(command))
            
            if command == "\x00" or command == "\x12" or command == "\x1a": # Send out list of authservers
                log.info(clientid + "Sending out list of Auth Servers: " + binascii.b2a_hex(command))    
                reply = self.get_server_list_by_type("authserver")
                
            elif command == "\x03": # Send out list of Configuration Servers
                log.info(clientid + "Sending out list of Configuration Servers")
                reply = self.get_server_list_by_type("configserver")
                
            elif command == "\x06" or command == "\x05" : # send out content list servers
                log.info(clientid + "Sending out list of content list servers")
                reply = self.get_server_list_by_type("csdserver")
                
            elif command == "\x0f" : # hl master server
                log.info(clientid + "Sending out list of HL Master Servers")
                reply = self.get_server_list_by_type("masterhlserver")
                
            elif command == "\x12" : #userid ticket validation server address, not supported yet
                log.info(clientid + "Sending out list of Client / Account Authentication servers")
                reply = self.get_server_list_by_type("validationtserver")
                
            elif command == "\x14" : # send out CSER server (not implemented)
                log.info(clientid + "Sending out list of CSER servers")
                reply = self.get_server_list_by_type("cserserver")
                
            elif command == "\x18" or command == "\x1e": # source master server
                log.info(clientid + "Requesting Source Master Server")
                reply = self.get_server_list_by_type("masterhl2server")
                 
            elif command == "\x0A" : # remote file harvest master server
                log.info(clientid + "Sending out list of Remote File Harvest Master Servers")
                reply = self.get_server_list_by_type("harvestserver")
                
            elif command == "\x0B" : #  master VCDS Validation (New valve cdkey Authentication) server
                log.info(clientid + "Sending out list of VCDS Validation (New valve CDKey Authentication) Master Servers")
                reply = self.get_server_list_by_type("validationserver")
                
            elif command == "\x10" : #  Friends master server
                log.info(clientid + "Sending out list of Messaging Servers")
                reply = self.get_server_list_by_type("messagingserver")
                
            elif command == "\x07" : # Ticket Validation master server
                log.info(clientid + "Sending out list of Ticket Validation Master Servers")
                reply = self.get_server_list_by_type("validationserver")
                
            #the only reason these are seperated from the regular csdserver if-statement is so we have a log of when these are requested    
            elif command == "\x0D" or command == "\x0E" : # all MCS Master Public Content master server
                log.info(clientid + "Sending out list of MCS Master Public Content Master Servers")
                reply = self.get_server_list_by_type("csdserver") 
                
            elif command == "\x1c" : # slave client authentication server's & proxy client authentication server's
                #Please note that this code is from vss, but dissassembly shows just recieving a authserver ip
                if binascii.b2a_hex(msg) == "1c600f2d40" :
                    csds_servers = self.get_server_info_by_type("csdserver")
                    auth_servers = self.get_server_info_by_type("authserver")
                    
                    #reply = "\x00\x00\x00\x14"
                    reply = struct.pack(">H", 3)  # Total number of servers in the reply
                    
                    if csds_servers:
                        reply += utilities.encodeIP((csds_servers[0].ip, csds_servers[0].port))
                    else:
                        reply = "\x00\x00"

                    if auth_servers:
                        if len(auth_servers) >= 2:
                            reply += utilities.encodeIP((auth_servers[0].ip, auth_servers[0].port))
                            reply += utilities.encodeIP((auth_servers[1].ip, auth_servers[1].port))
                        else:
                            reply += utilities.encodeIP((auth_servers[0].ip, auth_servers[0].port))
                            reply += utilities.encodeIP((auth_servers[0].ip, auth_servers[0].port))

                    clientsocket.send(reply)
            #The 5 servers below use 2 temporary udp and tcp ports for capturing the data, either 27021 or 27022    
            elif command == "\x15" : # Log Processing Server's master server
                log.info(clientid + "Sending out list of Log Processing Master Servers")
                bin_ip = utilities.encodeIP((globalvars.serverip, int("27021")))
                reply = struct.pack(">H", 1) + bin_ip
                
            elif command == "\x09" : # system status master server
                log.info(clientid + "Sending out list of System Status Master Servers")
                bin_ip = utilities.encodeIP((globalvars.serverip, int("27021")))
                reply = struct.pack(">H", 1) + bin_ip
                     
            elif command == "\x1D" : # BRS master server (Billing Bridge server?)
                log.info(clientid + "Sending out list of BRS Master Servers")
                bin_ip = utilities.encodeIP((globalvars.serverip, int("27022")))
                reply = struct.pack(">H", 1) + bin_ip
                
            elif command == "\x08" : # global transaction manager master server
                log.info(clientid + "Sending out list of Global Transaction Manager Master Servers")
                bin_ip = utilities.encodeIP((globalvars.serverip, int("27022")))
                reply = struct.pack(">H", 1) + bin_ip
                               
            elif command == "\x04" : # server configuration  master server
                log.info(clientid + "Sending out list of Server Configuration Master Servers")
                bin_ip = utilities.encodeIP((globalvars.serverip, int("27022")))
                reply = struct.pack(">H", 1) + bin_ip
                
            # Everything below this line is for 'administration' servers.
            # the purpose of each server is described in its name
            # but we believe that these are only queried from a internal valve steam network administration tool
            elif command == "\x01" : # administration authentication master server
                log.info(clientid + "Sending out list of Administration Authentication Master Servers")
                bin_ip = utilities.encodeIP((globalvars.serverip, int("27023")))
                reply = struct.pack(">H", 1) + bin_ip
                
            elif command == "\x11" : # administration billing bridge master server
                log.info(clientid + "Sending out list of Administration Billing Bridge Master Servers")
                bin_ip = utilities.encodeIP((globalvars.serverip, int("27023")))
                reply = struct.pack(">H", 1) + bin_ip
                
            elif command == "\x02" : # administration configuration master server
                log.info(clientid + "Sending out list of Administration Configuration Master Servers")
                bin_ip = utilities.encodeIP((globalvars.serverip, int("27023")))
                reply = struct.pack(">H", 1) + bin_ip
                              
            elif command == "\x16" : # administration log processing master server
                log.info(clientid + "Sending out list of Administration Log Processing Master Servers")
                bin_ip = utilities.encodeIP((globalvars.serverip, int("27023")))
                reply = struct.pack(">H", 1) + bin_ip
                
            elif command == "\x13" : # administration authentication master server
                log.info(clientid + "Sending out list of Administration Authentication Master Servers")
                bin_ip = utilities.encodeIP((globalvars.serverip, int("27023")))
                reply = struct.pack(">H", 1) + bin_ip
                                
            elif command == "\x0C" : # MCS Content Administration  master server
                log.info(clientid + "Sending out list of MCS Content Administration Master Servers")
                bin_ip = utilities.encodeIP((globalvars.serverip, int("27023")))
                reply = struct.pack(">H", 1) + bin_ip
                
            elif command == "\x17" : # CSER Administration master server
                log.info(clientid + "Sending out list of CSER Administration Master Servers")
                bin_ip = utilities.encodeIP((globalvars.serverip, int("27023")))
                reply = struct.pack(">H", 1) + bin_ip
                
            elif command == "\x1B" : # VTS (validation ticket server) Administration master server
                log.info(clientid + "Sending out list of VTS Administration Master Servers")
                bin_ip = utilities.encodeIP((globalvars.serverip, int("27023")))
                reply = struct.pack(">H", 1) + bin_ip
                
            else :
                log.info(clientid + "Invalid/not implemented command: " + binascii.b2a_hex(msg))
                reply = "\x00\x00"

            clientsocket.send_withlen(reply)
            
        else :
            log.error(clientid + "Invalid version message: " + binascii.b2a_hex(command))

        clientsocket.close()
        log.info (clientid + "disconnected from Directory Server")
        
    #for server to server directory server list addition
    def add_server_info(self, ip, port, server_type, timestamp = ""):
        for server_info in server_list:
            if server_info.ip == ip and server_info.port == port and server_info.server_type == server_type:
                server_info.timestamp = timestamp
                return False
        server_list.append(ServerInfo(ip, port, server_type, timestamp))
        return True
    
    #for server to server directory server list removal
    def remove_server_info(self, ip, port, server_type):
        initial_length = len(server_list)
        server_list = [server_info for server_info in server_list if not (server_info.ip == ip and server_info.port == port and server_info.server_type == server_type)]
        return len(server_list) < initial_length

    #takes care of removing any servers that have not responded within an hour, the default heartbeat time is 30 minutes, so they had more than enough time to respond
    def remove_expired_servers(self):        
        current_time = time.time()
        server_list = [server_info for server_info in server_list if server_info.timestamp == "0000-00-00 00:00:00" or (current_time - server_info.timestamp) <= 3600]

    def expired_servers_thread(self):
        while True:
            time.sleep(3600) # 1 hour
            self.remove_expired_servers()
            
    def heartbeat_thread(self):       
        while True:
            time.sleep(1800) # 30 minutes        
            serverlist_utilities.heartbeat(globalvars.serverip, str(config["dir_server_port"]), "directoryserver", globalvars.peer_password )
            
    #used to extract the decrypted payload buffer (after commad and message byte) for a server's request to add or remove itself.        
    def extract_packet_data(self, msg):
        ip, port, server_type = struct.unpack(">4sH16s", msg)
        ip = utilities.decodeIP(ip)
        server_type = server_type.rstrip("\x00")
        return ip, port, server_type
    
    def receive_server_list(self):
        buffer = clientsocket.recv_withlen()
        if not buffer:
            return
        #buffer = clientsocket.recvall(buffer_len)

        reply = utilities.decrypt(buffer, globalvars.peer_password)
        num_servers = struct.unpack(">H", reply[:2])[0]
        offset = 2

        for i in range(num_servers):
            server_type_bytes = reply[offset:offset + 3].decode('utf-8')
            ip_port = utilities.decodeIP(reply[offset + 3:offset + 7])
            ip, port = ip_port[0], ip_port[1]
            timestamp_bytes = reply[offset + 7:offset + 12].decode('utf-8')

            # Check if server is already in the global server_list
            for server_info in server_list:
                if server_info.ip == ip and server_info.port == port and server_info.server_type == server_type_bytes:
                    # If timestamp in new buffer is more recent than stored value, update
                    if timestamp_bytes > server_info.timestamp:
                        server_info.timestamp = timestamp_bytes
                    break
            else:  # If loop didn't break (i.e. no match found), add new server to global list
                server_info = ServerInfo(ip, port, server_type_bytes, timestamp_bytes) 
                server_list.append(server_info)
                
    #used to retrieve all the servers or only specific server types, for client requests and for sending the complete list of servers to new slave directory servers
    def get_server_info_by_type(self, server_type = ""):
        if not server_type:
            return [server_info for server_info in server_list]
        else:
            return [server_info for server_info in server_list if server_info.server_type == server_type]        

    #used for sending a slave directory server the complete server list
    def send_server_list(self):
        server_list = self.get_server_info_by_type()
        num_servers = len(server_list)

        if num_servers == 0:
            self.socket.send_withlen("\x00\x00")
        else:
            reply = struct.pack(">H", num_servers)
            for server_info in server_list:
                server_type_bytes = server_info.server_type.encode('utf-8')
                ip_port_bytes = utilities.encodeIP((server_info.ip, server_info.port))
                timestamp_bytes = server_info.timestamp.encode('utf-8')  # Assuming timestamp is already a string
                reply += server_type_bytes + ip_port_bytes + timestamp_bytes

            encbuffer = utilities.encrypt(reply, globalvars.peer_password)
            self.socket.send_withlen(encbuffer)
            
    def send_server_list_by_type(self, server_type):
        self.socket.send_withlen(self.get_server_list(server_type))
            
    #Grab all server ip/port's available for a specific client request        
    def get_server_list_by_type(self, server_type):
        server_list = self.get_server_info_by_type(server_type)
        num_servers = len(server_list)

        if num_servers == 0:
            return "\x00\x00"
        else:
            reply = struct.pack(">H", num_servers)
            for server_info in server_list:
                ip_port_bytes = utilities.encodeIP((server_info.ip, server_info.port))
                reply += ip_port_bytes
            return reply
    
class ServerInfo:
    def __init__(self, ip, port, server_type, timestamp):
        self.ip = ip
        self.port = port
        self.server_type = server_type
        self.timestamp = timestamp
