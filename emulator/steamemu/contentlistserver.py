import threading, logging, struct, binascii, os, time, atexit
import socket as pysocket
import utilities
import steam
import globalvars
import emu_socket
import steamemu.logger

from contentserverlist_utilities import unpack_contentserver_info, ContentServerManager
from tcp_socket import TCPNetworkHandler

log = logging.getLogger("CSDSRV")

manager = ContentServerManager() 
csdsConnectionCount = 0
   
class contentlistserver(TCPNetworkHandler):
    global manager, csdsConnectionCount
    
    def __init__(self, port, config):
        server_type = "csdserver"
        super(contentlistserver, self).__init__(config, port, server_type)  # Create an instance of NetworkHandler
        
        thread = threading.Thread(target=self.expired_servers_thread) # Thread for removing servers older than 1 hour
        thread.daemon = True
        thread.start()
        #Ben note: Figure out how to get the appid's and versions from the sdk contentserver.
        #ideas include: if a packet exists for getting the app list, have csds send the packet and parse the response
        #or put sdk contentserver in a folder within stmserver that we can parse through the files ourselves
       # if self.config["use_sdk"] == 1 :
       #      sdk_server_info = {
       #     'ip_address': str(self.config["sdk_ip"]),
       #     'port': int(self.config["sdk_port"]),
       #     'region': globalvars.cs_region,
       #     'timestamp': 1623276000
       # }


    def handle_client(self, clientsocket, address):
        clientid = str(address) + ": "
        log.info(clientid + "Connected to Content Server Directory Server ")
        msg = clientsocket.recv(4)
        
        if msg == "\x00\x4f\x8c\x11" :
            
            clientsocket.send("\x01") # handshake confirmed
            length_packet = clientsocket.recv(4)
            unpacked_length = struct.unpack('!I',  length_packet[:4])[0]
        
            clientsocket.send("\x01") 
            msg = clientsocket.recv(unpacked_length)
            command = msg[0]
            
            log.debug(binascii.b2a_hex(command))
            
            if command == "\x2b" : # Add single server entry to the list
                
                ip_address, port, region, timestamp, received_applist = unpack_contentserver_info(msg)
                try:
                    pysocket.inet_aton(ip_address)
                except pysocket.error:
                    log.warning(clientid + "Failed to decrypt CS Heartbeat packet: " + binascii.b2a_hex(msg))
                    clientsocket.send("\x00") #message decryption failed, the only response we give for failure
                    clientsocket.close()
                    log.info(clientid + "Disconnected from Content Server Directory Server")
                    return
                        
                manager.add_contentserver_info(ip_address, int(port), region, received_applist)
                clientsocket.send("\x01")
                log.info("[" + region + "] " +clientid + "Added to Content Server Directory Server")

            elif command == "\x2e" : #Remove server entry from the list
                
                packed_data = msg[1:]          
                decrypted_msg = utilities.decrypt(packed_data, globalvars.peer_password)
                ip_address, port, region = receive_removal(decrypted_msg)
                try:
                    pysocket.inet_aton(ip_address)
                except pysocket.error:
                    log.warning(clientid + "Failed to decrypt CS Removal packet: " + binascii.b2a_hex(msg))
                    clientsocket.send("\x00") #message decryption failed, the only response we give for failure
                    clientsocket.close()
                    log.info(clientid + "Disconnected from Content Server Directory Server")
                    return
                                
                if manager.remove_entry(ip, port, region) is True:
                    clientsocket.send("\x01")
                    log.info("[" + region + "] " + clientid + "Removed server from Content Server Directory Server")
                else: #couldnt remove server because: doesnt exists or problem with list
                    clientsocket.send("\x01")
                    log.info("[" + region + "] " + clientid + "There was an issue removing the server from Content Server Directory Server")

        elif msg == "\x00\x00\x00\x02" :
            csdsConnectionCount += 1 #ignore cs heartbeats and removal connections
            clientsocket.send("\x01")
            msg = clientsocket.recv_withlen()
            command = msg[0]
            
            if command == "\x00" :
                
                if msg[2] == "\x00" and len(msg) == 21 :
                    
                    log.info(clientid + "Sending out Content Servers with packages")
                    all_results, all_count = manager.find_ip_address()
                    if all_count > 0:
                        reply = struct.pack(">H", all_count) + "\x00\x00\x00\x00"
                        for ip, port in all_results:
                            bin_ip = utilities.encodeIP((ip, int(port)))
                            reply += (bin_ip + bin_ip)
                    else:
                        reply = "\x00\x00"
                        
                elif msg[2] == "\x01" and len(msg) == 25 :
                    
                    (appnum, version, numservers, region) = struct.unpack(">xxxLLHLxxxxxxxx", msg)
                    log.info("%ssend which server has content for app %s %s %s %s" % (clientid, appnum, version, numservers, region))
                    results, count = manager.find_ip_address(str(region), str(appnum), str(version))

                    if count > 0:
                        reply = struct.pack(">H", count) + "\x00\x00\x00\x00"
                        for ip, port in results:
                            bin_ip = utilities.encodeIP((ip, port))
                            reply += bin_ip + bin_ip
                    else:
                         reply = struct.pack(">H", 0)  # Default reply value if no matching server is found
                   
                    if self.config["sdk_ip"] != "0.0.0.0" :
                        log.info("%sHanding off to SDK server for app %s %s" % (clientid, appnum, version))
                        bin_ip = utilities.encodeIP((self.config["sdk_ip"], self.config["sdk_port"]))
                        reply = struct.pack(">H", 1) + "\x00\x00\x00\x00" + bin_ip + bin_ip
                else :
                    log.warning("Invalid message! " + binascii.b2a_hex(msg))
                    reply = "\x00\x00"
            elif command == "\x03" : # send out file servers (Which have the initial packages)
                log.info(clientid + "Sending out Content Servers with packages")
                all_results, all_count = manager.find_ip_address()
                if all_count > 0:
                    reply = struct.pack(">H", all_count) + "\x00\x00\x00\x00"
                    for ip, port in all_results:
                        reply = struct.pack(">H", 1) + utilities.encodeIP((ip, int(port)))
                        break #only 1 content server, eventually we will have the cs send package info
                              #so we can differentiate which servers have which packages
                
            elif command == "\x19" : # Get TicketGrantingServer
                # Parsing the buffer
                _, _, _, value1, value2, value3, value4, unknown_value, value5 = struct.unpack('!B B B I I H s I I I', command[1:])
                log.info("%sValue1: %d Value2: %d Value3: %d Value4: %d Unknown Value: %s Value5: %d" % (clientid, value1, value2, value3, value4, unknown_value, value5))

                all_results, all_count = manager.find_ip_address()
                if all_count > 0:
                    reply = struct.pack(">H", 1) + "\x00\x00\x00\x00"
                    for ip, port in all_results:
                        reply += utilities.encodeIP((ip, int(port)))
                        break
            else :
                log.warning("Invalid message! " + binascii.b2a_hex(msg))
                reply = ""
            clientsocket.send_withlen(reply)
        else :
            log.warning("Invalid message! " + binascii.b2a_hex(msg))

        clientsocket.close()
        log.info(clientid + "Disconnected from Content Server Directory Server")

    #takes care of removing any servers that have not responded within an hour,
    #the default heartbeat time is 30 minutes, so they had more than enough time to respond
    def expired_servers_thread(self):
        while True:
            time.sleep(3600) # 1 hour
            manager.remove_old_entries()
    
