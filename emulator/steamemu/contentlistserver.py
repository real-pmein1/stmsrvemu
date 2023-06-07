import threading, logging, struct, binascii, os, time
import utilities
import steam
import globalvars
import serverlist_utilities

server_list = []

class contentlistserver(threading.Thread):
    global server_list
    
    def __init__(self, (socket, address), config) :
        threading.Thread.__init__(self)
        self.socket = socket
        self.address = address
        self.config = config
        
        # Start the thread for dir registration heartbeat, only
        thread2 = threading.Thread(target=self.heartbeat_thread)
        thread2.daemon = True
        thread2.start()
        
        # Read peer password from the config
        self.peer_password = self.config["peer_password"]
        
        # Start the thread for removing expired servers
        #thread = threading.Thread(target=self.expired_servers_thread)
        #thread.daemon = True
        #thread.start()
        
    def heartbeat_thread(self):       
        while True:
            serverlist_utilities.heartbeat(globalvars.serverip, self.config["csds_port"], "csdsserver", globalvars.peer_password )
            time.sleep(1800) # 30 minutes
            
    def run(self):
        log = logging.getLogger("clstsrv")
        clientid = str(self.address) + ": "
        log.info(clientid + "Connected to Content Server Directory Server ")
        
        if self.config["public_ip"] != "0.0.0.0" :
            if clientid.startswith(globalvars.servernet) :
                bin_ip = utilities.encodeIP((self.config["server_ip"], self.config["content_server_port"]))
            else :
                bin_ip = utilities.encodeIP((self.config["public_ip"], self.config["content_server_port"]))
        else:
            bin_ip = utilities.encodeIP((self.config["server_ip"], self.config["content_server_port"]))
        
        msg = self.socket.recv(4)
        if msg == "\x00\x00\x00\x02" :
            self.socket.send("\x01")

            msg = self.socket.recv_withlen()
            command = msg[0]
            if command == "\x00" :
                if msg[2] == "\x00" and len(msg) == 21 :
                    log.info(clientid + "Sending out Content Servers  with packages")
                    reply = struct.pack(">H", 1) + "\x00\x00\x00\x00" + bin_ip + bin_ip
                elif msg[2] == "\x01" and len(msg) == 25 :
                    (appnum, version, numservers, region) = struct.unpack(">xxxLLHLxxxxxxxx", msg)
                    log.info("%ssend which server has content for app %s %s %s %s" % (clientid, appnum, version, numservers, region))

                    if os.path.isfile("files/cache/" +str(appnum) + "_" + str(version) + "/" +str(appnum) + "_" + str(version) + ".manifest") :
                        reply = struct.pack(">H", 1) + "\x00\x00\x00\x00" + bin_ip + bin_ip
                    elif os.path.isfile(self.config["v2manifestdir"] + str(appnum) + "_" + str(version) + ".manifest") :
                        reply = struct.pack(">H", 1) + "\x00\x00\x00\x00" + bin_ip + bin_ip
                    elif os.path.isfile(self.config["manifestdir"] + str(appnum) + "_" + str(version) + ".manifest") :
                        reply = struct.pack(">H", 1) + "\x00\x00\x00\x00" + bin_ip + bin_ip
                    else :
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
                log.info(clientid + "Sending out Content Servers  with packages")
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
            self.socket.send_withlen(reply)
        else :
            log.warning("Invalid message! " + binascii.b2a_hex(msg))

        self.socket.close()
        log.info(clientid + "Disconnected from Content Servers  Server")
