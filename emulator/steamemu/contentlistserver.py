import threading, logging, struct, binascii, os, time
import utilities
import steam
import globalvars
import serverlist_utilities
import contentserverlist_utilities
import emu_socket
import steamemu.logger
import socket as pysocket
from contentserverlist_utilities import contentserver_list, ContentServerInfo, unpack_contentserver_info

class contentlistserver(threading.Thread):
    global contentserver_list
    log = logging.getLogger("clstsrv")
    
    def __init__(self, port, config):
        threading.Thread.__init__(self)
        self.port = int(port)
        self.config = config
        self.socket = emu_socket.ImpSocket()
        
        thread2 = threading.Thread(target=self.heartbeat_thread)
        thread2.daemon = True
        thread2.start()

    def heartbeat_thread(self):       
        while True:
            serverlist_utilities.heartbeat(globalvars.serverip, self.port, "csdserver", globalvars.peer_password )
            time.sleep(1800) # 30 minutes
            
    def run(self):        
        self.socket.bind((globalvars.serverip, self.port))
        self.socket.listen(5)

        while True:
            (clientsocket, address) = self.socket.accept()
            threading.Thread(target=self.handle_client, args=(clientsocket, address)).start()

    def handle_client(self, clientsocket, address):
        clientid = str(address) + ": "
        log.info(clientid + "Connected to Content Server Directory Server ")
        
        if self.config["public_ip"] != "0.0.0.0" :
            if clientid.startswith(globalvars.servernet) :
                bin_ip = utilities.encodeIP((self.config["server_ip"], self.config["content_server_port"]))
            else :
                bin_ip = utilities.encodeIP((self.config["public_ip"], self.config["content_server_port"]))
        else:
            bin_ip = utilities.encodeIP((self.config["server_ip"], self.config["content_server_port"]))
        
        msg = clientsocket.recv(4)
        if msg == "\x00\x4f\x8c\x11" :
            clientsocket.send("\x01") # handshake confirmed
    
            msg = clientsocket.recv(1024)
            command = msg[0]
            
            log.debug(binascii.b2a_hex(command))
            
            if command == "\x2b":
                if decrypted_msg is None:
                    log.warning(clientid + "Failed to decrypt packet: " + binascii.b2a_hex(msg))
                    clientsocket.send("\x00") #message decryption failed, the only response we give for failure
                    return
                # Add single server entry to the list
                packed_data = msg[1:]
                contentserver_list.append(unpack_contentserver_info(packed_data))
                clientsocket.send("\x01")
                log.info(server_type + " " +clientid + "Added to Content Server Directory Server")

            elif command == "\x2e":
                packed_data = msg[1:]
                # Remove server entry from the list
                decrypted_msg = utilities.decrypt(packed_data, globalvars.peer_password)
                if decrypted_msg is None:
                    log.warning(clientid + "Failed to decrypt packet: " + binascii.b2a_hex(msg))
                    clientsocket.send("\x00") #message decryption failed, the only response we give for failure
                    return

                ip, port, region = receive_removal(decrypted_msg)
                if remove_server_info(ip, port, region):
                    clientsocket.send("\x01")
                    log.info(server_type + " " +clientid + "Removed from Content Server Directory Server")
                    #if globalvars.is_masterdir != 1:
                        #send any requests to add or remove to the master server aswell
                        #clientsocket.sendto(msg, self.masterdir_ipport)
        elif msg == "\x00\x00\x00\x02" :
            clientsocket.send("\x01")

            msg = clientsocket.recv_withlen()
            command = msg[0]
            if command == "\x00" :
                if msg[2] == "\x00" and len(msg) == 21 :
                    log.info(clientid + "Sending out Content Servers  with packages")
                    reply = struct.pack(">H", 1) + "\x00\x00\x00\x00" + bin_ip + bin_ip
                elif msg[2] == "\x01" and len(msg) == 25 :
                    (appnum, version, numservers, region) = struct.unpack(">xxxLLHLxxxxxxxx", msg)
                    log.info("%ssend which server has content for app %s %s %s %s" % (clientid, appnum, version, numservers, region))
                    if self.config["sdk_ip"] == "0.0.0.0" :
                        log.warning("%sNo servers found for app %s %s %s %s" % (clientid, appnum, version, numservers, region))
                        reply = "\x00\x00" # no file servers for app
                    else :
                        log.info("%sHanding off to SDK server for app %s %s" % (clientid, appnum, version))
                        bin_ip = utilities.encodeIP((self.config["sdk_ip"], self.config["sdk_port"]))
                        reply = struct.pack(">H", 1) + "\x00\x00\x00\x00" + bin_ip + bin_ip
                else :
                    log.warning("Invalid message! " + binascii.b2a_hex(msg))
                    reply = "\x00\x00"
            elif command == "\x03" : # send out file servers (Which have the initial packages)
                log.info(clientid + "Sending out Content Servers with packages")
                reply = struct.pack(">H", 1) + bin_ip
            elif command == "\x19" : # find best cellid contentserver
                #packet structure:
                #U32 - command 0x19
                #1 byte - 0x00
                #1 byte - 0x00
                #1 byte - always 1
                #U32
                #U32
                #U16
                #U32
                #U32 - 0xffffffff
                #U32
                log.info(clientid + "Sending out Content Servers Based on CellId - Not Operational")
                reply = struct.pack(">H", 1) + bin_ip
                #Expected Response:
                #u16 - number of content servers
                #--next, loop according to number of servers--
                #u32 - 
                #gap - 6 bytes 0x00??
                #gap - 6 bytes 0x00??

            else :
                log.warning("Invalid message! " + binascii.b2a_hex(msg))
                reply = ""
            clientsocket.send_withlen(reply)
        else :
            log.warning("Invalid message! " + binascii.b2a_hex(msg))

        clientsocket.close()
        log.info(clientid + "Disconnected from Content Server Directory Server")

    #for adding content server to server list
    def add_contentserver_info(self, ip, port, applist, region, timestamp = ""):
        for server_info in server_list:
            if server_info.ip == ip and server_info.port == port and server_info.server_type == server_type:
                server_info.timestamp = timestamp
                return False
        server_list.append(ServerInfo(ip, port, applist, region, timestamp))
        return True
    
    #for server to server directory server list removal
    def remove_server_info(self, ip, port, region):
        initial_length = len(server_list)
        server_list = [server_info for server_info in contentserver_list if not (server_info.ip == ip and server_info.port == port and server_info.server_type == server_type)]
        return len(server_list) < initial_length

    #takes care of removing any servers that have not responded within an hour, the default heartbeat time is 30 minutes, so they had more than enough time to respond
    def remove_expired_servers(self):        
        current_time = time.time()
        server_list = [server_info for server_info in contentserver_list if server_info.timestamp == "0000-00-00 00:00:00" or (current_time - server_info.timestamp) <= 3600]

    def expired_servers_thread(self):
        while True:
            time.sleep(3600) # 1 hour
            self.remove_expired_servers()
    
    #used to retrieve all content servers or only specific content servers with certain apps or from certain regions
    def get_server_info_by_type(self, applist={}, region=""):
        if not applist and not region:
            return [server_info for server_info in contentserver_list]
        elif not region
            return [server_info for server_info in contentserver_list if server_info.applist == applist]
        else:
            return [server_info for server_info in contentserver_list if server_info.applist == applist and server_info.region == region]

    def recieve_contentserver_info(buffer, peer_password):
        decrypted_data = utilities.decrypt(buffer, peer_password)

        # Unpack the IP, port, and region
        ip_bytes, port, region = struct.unpack(">4sH16s", decrypted_data[:22])
        ip = utilities.decodeIP(ip_bytes)
        region = region.rstrip("\x00")

        # Unpack the applist
        applist = []
        offset = 22  # Start position after the IP, port, and region
        while offset < len(decrypted_data):
            appid, version = struct.unpack(">ii", decrypted_data[offset:offset + 8])
            applist.append({'appid': appid, 'version': version})
            offset += 8

        return ip, port, region, applist


