import threading, logging, struct, binascii, os, time
import utilities
import steam
import globalvars
import serverlist_utilities
import contentserverlist_utilities
import emu_socket
import steamemu.logger
import socket as pysocket
from contentserverlist_utilities import contentserver_list, ContentServerInfo, unpack_contentserver_info, remove_server_info
log = logging.getLogger("clstsrv")
    
class contentlistserver(threading.Thread):
    global contentserver_list
    global log
    
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
        
        msg = clientsocket.recv(4)
        if msg == "\x00\x4f\x8c\x11" :
            clientsocket.send("\x01") # handshake confirmed
    
            msg = clientsocket.recv(1024)
            command = msg[0]
            
            log.debug(binascii.b2a_hex(command))
            
            if command == "\x2b":
                # Add single server entry to the list
                packed_data = msg[1:]
                unpacked_serverinfo = unpack_contentserver_info(packed_data)
                if unpacked_serverinfo is False:
                    log.warning(clientid + "Failed to decrypt packet: " + binascii.b2a_hex(msg))
                    clientsocket.send("\x00") #message decryption failed, the only response we give for failure
                    clientsocket.close()
                    log.info(clientid + "Disconnected from Content Server Directory Server")
                    return
                contentserver_list.append(unpacked_serverinfo)
                print contentserver_list
                clientsocket.send("\x01")
                log.info(unpacked_serverinfo.region + " " +clientid + "Added to Content Server Directory Server")

            elif command == "\x2e":
                packed_data = msg[1:]
                # Remove server entry from the list
                decrypted_msg = utilities.decrypt(packed_data, globalvars.peer_password)
                ip_address, port, region = struct.unpack('!16s I 16s', decrypted_msg)
                ip_address = ip_address.rstrip('\x00').decode('utf-8')
                try:
                    socket.inet_aton(ip_address)
                except socket.error:
                    log.warning(clientid + "Failed to decrypt packet: " + binascii.b2a_hex(msg))
                    clientsocket.send("\x00") #message decryption failed, the only response we give for failure
                    clientsocket.close()
                    log.info(clientid + "Disconnected from Content Server Directory Server")
                    return
                
                region = region.rstrip('\x00').decode('utf-8')
                
                if remove_server_info(ip, port, region): #will eventually check if it removed the server, couldnt find it or couldnt remove it
                    clientsocket.send("\x01")
                    log.info(server_type + " " +clientid + "Removed from Content Server Directory Server")

        elif msg == "\x00\x00\x00\x02" :
            clientsocket.send("\x01")

            msg = clientsocket.recv_withlen()
            command = msg[0]
            if command == "\x00" :
                if msg[2] == "\x00" and len(msg) == 21 :
                    log.info(clientid + "Sending out Content Servers  with packages")
                    num_servers = len(contentserver_list)
                    reply = struct.pack(">H", num_servers) + "\x00\x00\x00\x00"

                    for contentserver_info in contentserver_list:
                        bin_ip = utilities.encodeIP((contentserver_info.ip_address, contentserver_info.port)
                        reply += bin_ip + bin_ip
                elif msg[2] == "\x01" and len(msg) == 25 :
                    (appnum, version, numservers, region) = struct.unpack(">xxxLLHLxxxxxxxx", msg)
                    log.info("%ssend which server has content for app %s %s %s %s" % (clientid, appnum, version, numservers, region))
                    reply = struct.pack(">H", 0)  # Default reply value if no matching server is found
                    i = 0
                    for contentserver_info in contentserver_list:
                        if contentserver_info.region == region:
                            for app_info in contentserver_info.applist:
                                app_id, app_version = app_info
                                if app_id == appnum and app_version == version:
                                    i++
                                    bin_ip = utilities.encodeIP((contentserver_info.ip_address, contentserver_info.port))
                                    reply = struct.pack(">H", i) + "\x00\x00\x00\x00" + bin_ip + bin_ip
                                    break
                    if self.config["sdk_ip"] != "0.0.0.0" :
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
        #elif region is ""
            #return [server_info for server_info in contentserver_list if server_info.applist == applist]
        else:
            return [server_info for server_info in contentserver_list if server_info.applist == applist and server_info.region == region]

