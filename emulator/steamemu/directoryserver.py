import threading, logging, struct, binascii

import steam
import globalvars

class directoryserver(threading.Thread):
    def __init__(self, (socket, address), config) :
        threading.Thread.__init__(self)
        self.socket = socket
        self.address = address
        self.config = config

    def run(self):
        log = logging.getLogger("dirsrv")
        clientid = str(self.address) + ": "
        log.info(clientid + "Connected to Directory Server")
        
        #print("Client ID is: " + clientid)
        msg = self.socket.recv(4)
        log.debug(binascii.b2a_hex(msg))
        if msg == "\x00\x00\x00\x01" or msg == "\x00\x00\x00\x02":
            self.socket.send("\x01")

            msg = self.socket.recv_withlen()
            command = msg[0]
            log.debug(binascii.b2a_hex(command))
            if command == "\x00" or command == "\x12": # send out Client Authentication Server
                log.info(clientid + "Sending out specific Client Authentication server: " + binascii.b2a_hex(command))
                if self.config["public_ip"] != "0.0.0.0" :
                    if clientid.startswith(globalvars.servernet) :
                        bin_ip = steam.encodeIP((self.config["server_ip"], self.config["auth_server_port"]))
                    else :
                        bin_ip = steam.encodeIP((self.config["public_ip"], self.config["auth_server_port"]))
                else :
                    bin_ip = steam.encodeIP((self.config["server_ip"], self.config["auth_server_port"]))
                reply = struct.pack(">H", 1) + bin_ip
            elif command == "\x03" : # send out Configuration Servers
                log.info(clientid + "Sending out list of Configuration Servers")
                if self.config["public_ip"] != "0.0.0.0" :
                    if clientid.startswith(globalvars.servernet) :
                        bin_ip = steam.encodeIP((self.config["server_ip"], self.config["conf_server_port"]))
                    else :
                        bin_ip = steam.encodeIP((self.config["public_ip"], self.config["conf_server_port"]))
                else :
                    bin_ip = steam.encodeIP((self.config["server_ip"], self.config["conf_server_port"]))
                reply = struct.pack(">H", 1) + bin_ip
            elif command == "\x06" or command == "\x05" : # send out content list servers
                log.info(clientid + "Sending out list of content list servers")
                if self.config["public_ip"] != "0.0.0.0" :
                    if clientid.startswith(globalvars.servernet) :
                        bin_ip = steam.encodeIP((self.config["server_ip"], self.config["contlist_server_port"]))
                    else :
                        bin_ip = steam.encodeIP((self.config["public_ip"], self.config["contlist_server_port"]))
                else :
                    bin_ip = steam.encodeIP((self.config["server_ip"], self.config["contlist_server_port"]))
                reply = struct.pack(">H", 1) + bin_ip
            elif command == "\x0f" : # hl master server
                log.info(clientid + "Sending out list of HL Master Servers")
                if self.config["public_ip"] != "0.0.0.0" :
                    if clientid.startswith(globalvars.servernet) :
                        bin_ip = steam.encodeIP((self.config["server_ip"], self.config["hlmaster_server_port"]))
                    else :
                        bin_ip = steam.encodeIP((self.config["public_ip"], self.config["hlmaster_server_port"]))
                else :
                    bin_ip = steam.encodeIP((self.config["server_ip"], self.config["hlmaster_server_port"]))
                reply = struct.pack(">H", 1) + bin_ip
            elif command == "\x12" : # Client / Account Authentication server address, not supported
                log.info(clientid + "Sending out list of Client / Account Authentication servers")
                if self.config["public_ip"] != "0.0.0.0" :
                    if clientid.startswith(globalvars.servernet) :
                        bin_ip = steam.encodeIP((self.config["server_ip"], self.config["auth_server_port"]))
                    else :
                        bin_ip = steam.encodeIP((self.config["public_ip"], self.config["auth_server_port"]))
                else :
                    bin_ip = steam.encodeIP((self.config["server_ip"], self.config["auth_server_port"]))
                reply = struct.pack(">H", 1) + bin_ip
            elif command == "\x14" : # send out CSER server (not implemented)
                log.info(clientid + "Sending out list of CSER servers")
                if self.config["public_ip"] != "0.0.0.0" :
                    if clientid.startswith(globalvars.servernet) :
                        bin_ip = steam.encodeIP((self.config["server_ip"], 27013))
                    else :
                        bin_ip = steam.encodeIP((self.config["public_ip"], 27013))
                else :
                    bin_ip = steam.encodeIP((self.config["server_ip"], 27013))
                reply = struct.pack(">H", 1) + bin_ip
            elif command == "\x18" : # source master server
                log.info(clientid + "Requesting Source Master Server")
                if self.config["public_ip"] != "0.0.0.0" :
                    if clientid.startswith(globalvars.servernet) :
                        bin_ip = steam.encodeIP((self.config["server_ip"], 27011))
                    else :
                        bin_ip = steam.encodeIP((self.config["public_ip"], 27011))
                else :
                    bin_ip = steam.encodeIP((self.config["server_ip"], 27011))
                #reply = struct.pack(">I", 8) + struct.pack(">H", 1) + bin_ip
                reply = struct.pack(">H", 1) + bin_ip
            elif command == "\x1e" : # rdkf master server
                log.info(clientid + "Requesting RDKF Master Server")
                bin_ip = steam.encodeIP(("172.20.0.23", "27012"))
                reply = struct.pack(">H", 1) + bin_ip
            elif command == "\x1c" : # slave client authentication server's & proxy client authentication server's
                if binascii.b2a_hex(msg) == "1c600f2d40" :
                    if self.config["public_ip"] != "0.0.0.0" :
                        if clientid.startswith(globalvars.servernet) : #seems 2 master auth server too with content server first
                            bin_ip = steam.encodeIP((self.config["server_ip"], self.config["file_server_port"]))
                            bin_ip += steam.encodeIP((self.config["server_ip"], self.config["auth_server_port"]))
                            bin_ip += steam.encodeIP((self.config["server_ip"], self.config["auth_server_port"]))
                        else :
                            bin_ip = steam.encodeIP((self.config["public_ip"], self.config["file_server_port"]))
                            bin_ip += steam.encodeIP((self.config["public_ip"], self.config["auth_server_port"]))
                            bin_ip += steam.encodeIP((self.config["public_ip"], self.config["auth_server_port"]))
                    else :
                        bin_ip = steam.encodeIP((self.config["server_ip"], self.config["file_server_port"]))
                        bin_ip += steam.encodeIP((self.config["server_ip"], self.config["auth_server_port"]))
                        bin_ip += steam.encodeIP((self.config["server_ip"], self.config["auth_server_port"]))
                    reply = struct.pack(">H", 1) + bin_ip

            elif command == "\x01" : # administration authentication master server
                log.info(clientid + "Sending out list of Administration Authentication Master Servers")
                bin_ip = steam.encodeIP(("0.0.0.0", "27020"))
                reply = struct.pack(">H", 1) + bin_ip
            elif command == "\x11" : # administration billing bridge   master server
                log.info(clientid + "Sending out list of Administration Billing Bridge Master Servers")
                bin_ip = steam.encodeIP(("0.0.0.0", "27021"))
                reply = struct.pack(">H", 1) + bin_ip
            elif command == "\x02" : # administration configuration master server
                log.info(clientid + "Sending out list of Administration Configuration Master Servers")
                bin_ip = steam.encodeIP(("0.0.0.0", "27022"))
                reply = struct.pack(">H", 1) + bin_ip
            elif command == "\x08" : # global transaction manager master server
                log.info(clientid + "Sending out list of Global Transaction Manager Master Servers")
                bin_ip = steam.encodeIP(("0.0.0.0", "27023"))
                reply = struct.pack(">H", 1) + bin_ip
            elif command == "\x16" : # administration log processing master server
                log.info(clientid + "Sending out list of Administration Log Processing Master Servers")
                bin_ip = steam.encodeIP(("0.0.0.0", "27024"))
                reply = struct.pack(">H", 1) + bin_ip
            elif command == "\x13" : # administration authentication master server
                log.info(clientid + "Sending out list of Administration Authentication Master Servers")
                bin_ip = steam.encodeIP(("0.0.0.0", "27025"))
                reply = struct.pack(">H", 1) + bin_ip
            elif command == "\x04" : # server configuration  master server
                log.info(clientid + "Sending out list of Server Configuration Master Servers")
                bin_ip = steam.encodeIP(("0.0.0.0", "27026"))
                reply = struct.pack(">H", 1) + bin_ip
            elif command == "\x09" : # system status master server
                log.info(clientid + "Sending out list of System Status Master Servers")
                bin_ip = steam.encodeIP(("0.0.0.0", "27027"))
                reply = struct.pack(">H", 1) + bin_ip
            elif command == "\xA0" : # remote file harvest master server
                log.info(clientid + "Sending out list of Remote File Harvest Master Servers")
                bin_ip = steam.encodeIP(("0.0.0.0", "27028"))
                reply = struct.pack(">H", 1) + bin_ip
            elif command == "\xB0" : #  master VCDS Validation (New valve cdkey Authentication) server
                log.info(clientid + "Sending out list of VCDS Validation (New valve CDKey Authentication) Master Servers")
                bin_ip = steam.encodeIP(("0.0.0.0", "27029"))
                reply = struct.pack(">H", 1) + bin_ip
            elif command == "\x10" : #  Friends master server
                log.info(clientid + "Sending out list of Friends Servers")
                bin_ip = steam.encodeIP(("0.0.0.0", "27040"))
                reply = struct.pack(">H", 1) + bin_ip
            elif command == "\xC0" : # MCS Content Administration  master server
                log.info(clientid + "Sending out list of MCS Content Administration Master Servers")
                bin_ip = steam.encodeIP(("0.0.0.0", "27041"))
                reply = struct.pack(">H", 1) + bin_ip
            elif command == "\xD0" or command == "\xE0" : # all MCS Master Public Content master server
                log.info(clientid + "Sending out list of MCS Master Public Content Master Servers")
                bin_ip = steam.encodeIP(("0.0.0.0", "27042"))
                reply = struct.pack(">H", 1) + bin_ip
            elif command == "\x15" : # Log Processing Server's master server
                log.info(clientid + "Sending out list of Log Processing Master Servers")
                bin_ip = steam.encodeIP(("0.0.0.0", "27043"))
                reply = struct.pack(">H", 1) + bin_ip
            elif command == "\x1D" : # BRS master server
                log.info(clientid + "Sending out list of BRS Master Servers")
                bin_ip = steam.encodeIP(("0.0.0.0", "27044"))
                reply = struct.pack(">H", 1) + bin_ip
            elif command == "\x17" : # CSER Administration master server
                log.info(clientid + "Sending out list of CSER Administration Master Servers")
                bin_ip = steam.encodeIP(("0.0.0.0", "27045"))
                reply = struct.pack(">H", 1) + bin_ip
            elif command == "\x1B" : # VTS Administration master server
                log.info(clientid + "Sending out list of VTS Administration Master Servers")
                bin_ip = steam.encodeIP(("0.0.0.0", "27049"))
                reply = struct.pack(">H", 1) + bin_ip
            elif command == "\x07" : # Ticket Validation master server
                log.info(clientid + "Sending out list of Ticket Validation Master Servers")
                bin_ip = steam.encodeIP(("0.0.0.0", "27051"))
                reply = struct.pack(">H", 1) + bin_ip
            else :
                log.info(clientid + "Invalid/not implemented command: " + binascii.b2a_hex(msg))
                reply = "\x00\x00"

            self.socket.send_withlen(reply)
            
        else :
            log.error(clientid + "Invalid version message: " + binascii.b2a_hex(command))

        self.socket.close()
        log.info (clientid + "disconnected from Directory Server")
