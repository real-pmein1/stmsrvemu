import threading, logging, struct, binascii, ipcalc

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

        msg = self.socket.recv(4)
        log.debug(binascii.b2a_hex(msg))
        if msg == "\x00\x00\x00\x01" :
            self.socket.send("\x01")

            msg = self.socket.recv_withlen()
            command = msg[0]
            log.debug(binascii.b2a_hex(command))
            if command == "\x00" : # send out auth server for a specific username
                log.info(clientid + "Sending out specific auth server: " + binascii.b2a_hex(command))
                if self.config["public_ip"] != "0.0.0.0" :
                    if str(self.address[0]) in ipcalc.Network(str(globalvars.server_net)):
                        bin_ip = steam.encodeIP((self.config["server_ip"], self.config["auth_server_port"]))
                    else :
                        bin_ip = steam.encodeIP((self.config["public_ip"], self.config["auth_server_port"]))
                else :
                    bin_ip = steam.encodeIP((self.config["server_ip"], self.config["auth_server_port"]))
                reply = struct.pack(">H", 1) + bin_ip
            elif command == "\x03" : # send out config servers
                log.info(clientid + "Sending out list of config servers")
                if self.config["public_ip"] != "0.0.0.0" :
                    if str(self.address[0]) in ipcalc.Network(str(globalvars.server_net)):
                        bin_ip = steam.encodeIP((self.config["server_ip"], self.config["conf_server_port"]))
                    else :
                        bin_ip = steam.encodeIP((self.config["public_ip"], self.config["conf_server_port"]))
                else :
                    bin_ip = steam.encodeIP((self.config["server_ip"], self.config["conf_server_port"]))
                reply = struct.pack(">H", 1) + bin_ip
            elif command == "\x06" : # send out content list servers
                log.info(clientid + "Sending out list of content list servers")
                if self.config["public_ip"] != "0.0.0.0" :
                    if str(self.address[0]) in ipcalc.Network(str(globalvars.server_net)):
                        bin_ip = steam.encodeIP((self.config["server_ip"], self.config["contlist_server_port"]))
                    else :
                        bin_ip = steam.encodeIP((self.config["public_ip"], self.config["contlist_server_port"]))
                else :
                    bin_ip = steam.encodeIP((self.config["server_ip"], self.config["contlist_server_port"]))
                reply = struct.pack(">H", 1) + bin_ip
            elif command == "\x0f" : # hl master server
                log.info(clientid + "Requesting HL Master Server")
                if self.config["public_ip"] != "0.0.0.0" :
                    if str(self.address[0]) in ipcalc.Network(str(globalvars.server_net)):
                        bin_ip = steam.encodeIP((self.config["server_ip"], 27010))
                    else :
                        bin_ip = steam.encodeIP((self.config["public_ip"], 27010))
                else :
                    bin_ip = steam.encodeIP((self.config["server_ip"], 27010))
                reply = struct.pack(">H", 1) + bin_ip
            elif command == "\x12" : # account retrieve server address, not supported
                log.info(clientid + "Sending out list of account retrieval servers")
                if self.config["public_ip"] != "0.0.0.0" :
                    if str(self.address[0]) in ipcalc.Network(str(globalvars.server_net)):
                        bin_ip = steam.encodeIP((self.config["server_ip"], self.config["auth_server_port"]))
                    else :
                        bin_ip = steam.encodeIP((self.config["public_ip"], self.config["auth_server_port"]))
                else :
                    bin_ip = steam.encodeIP((self.config["server_ip"], self.config["auth_server_port"]))
                reply = struct.pack(">H", 1) + bin_ip
            elif command == "\x14" : # send out CSER server (not implemented)
                log.info(clientid + "Sending out list of CSER(?) servers")
                if self.config["public_ip"] != "0.0.0.0" :
                    if str(self.address[0]) in ipcalc.Network(str(globalvars.server_net)):
                        bin_ip = steam.encodeIP((self.config["server_ip"], 27013))
                    else :
                        bin_ip = steam.encodeIP((self.config["public_ip"], 27013))
                else :
                    bin_ip = steam.encodeIP((self.config["server_ip"], 27013))
                reply = struct.pack(">H", 1) + bin_ip
            elif command == "\x18" : # source master server
                log.info(clientid + "Requesting Source Master Server")
                if self.config["public_ip"] != "0.0.0.0" :
                    if str(self.address[0]) in ipcalc.Network(str(globalvars.server_net)):
                        bin_ip = steam.encodeIP((self.config["server_ip"], 27011))
                    else :
                        bin_ip = steam.encodeIP((self.config["public_ip"], 27011))
                else :
                    bin_ip = steam.encodeIP((self.config["server_ip"], 27011))
                reply = struct.pack(">H", 1) + bin_ip
            elif command == "\x1e" : # rdkf master server
                log.info(clientid + "Requesting RDKF Master Server")
                if self.config["public_ip"] != "0.0.0.0" :
                    if str(self.address[0]) in ipcalc.Network(str(globalvars.server_net)):
                        bin_ip = steam.encodeIP((self.config["server_ip"], 27012))
                    else :
                        bin_ip = steam.encodeIP((self.config["public_ip"], 27012))
                else :
                    bin_ip = steam.encodeIP((self.config["server_ip"], 27012))
                reply = struct.pack(">H", 1) + bin_ip
            else :
                log.info(clientid + "Invalid/not implemented command: " + binascii.b2a_hex(msg))
                reply = "\x00\x00"

            self.socket.send_withlen(reply)

        elif msg == "\x00\x00\x00\x02" :
            self.socket.send("\x01")

            msg = self.socket.recv_withlen()
            command = msg[0]
            log.debug(binascii.b2a_hex(command))
            if command == "\x00" and len(msg) == 5 : # send out auth server for a specific username
                log.info(clientid + "Sending out specific auth server: " + binascii.b2a_hex(command))
                if str(self.address[0]) in ipcalc.Network(str(globalvars.server_net)):
                    bin_ip = steam.encodeIP((self.config["server_ip"], self.config["auth_server_port"]))
                else :
                    bin_ip = steam.encodeIP((self.config["public_ip"], self.config["auth_server_port"]))
                reply = struct.pack(">H", 1) + bin_ip
            elif command == "\x03" : # send out config servers
                log.info(clientid + "Sending out list of config servers")
                if str(self.address[0]) in ipcalc.Network(str(globalvars.server_net)):
                    bin_ip = steam.encodeIP((self.config["server_ip"], self.config["conf_server_port"]))
                else :
                    bin_ip = steam.encodeIP((self.config["public_ip"], self.config["conf_server_port"]))
                reply = struct.pack(">H", 1) + bin_ip
            elif command == "\x06" : # send out content list servers
                log.info(clientid + "Sending out list of content list servers")
                if str(self.address[0]) in ipcalc.Network(str(globalvars.server_net)):
                    bin_ip = steam.encodeIP((self.config["server_ip"], self.config["contlist_server_port"]))
                else :
                    bin_ip = steam.encodeIP((self.config["public_ip"], self.config["contlist_server_port"]))
                reply = struct.pack(">H", 1) + bin_ip
            elif command == "\x0b" or command == "\x1c" : # send out auth server for a specific username
                log.info(clientid + "Sending out auth server for a specific username: " + binascii.b2a_hex(command))
                if str(self.address[0]) in ipcalc.Network(str(globalvars.server_net)):
                    bin_ip = steam.encodeIP((self.config["server_ip"], self.config["auth_server_port"]))
                else :
                    bin_ip = steam.encodeIP((self.config["public_ip"], self.config["auth_server_port"]))
                reply = struct.pack(">H", 1) + bin_ip
            elif command == "\x0f" : # hl master server
                log.info(clientid + "Requesting HL Master Server")
                if str(self.address[0]) in ipcalc.Network(str(globalvars.server_net)):
                    bin_ip = steam.encodeIP((self.config["server_ip"], 27010))
                else :
                    bin_ip = steam.encodeIP((self.config["public_ip"], 27010))
                reply = struct.pack(">H", 1) + bin_ip
            elif command == "\x12" : # account retrieve server address, not supported
                log.info(clientid + "Sending out list of account retrieval servers")
                if str(self.address[0]) in ipcalc.Network(str(globalvars.server_net)):
                    bin_ip = steam.encodeIP((self.config["server_ip"], self.config["auth_server_port"]))
                else :
                    bin_ip = steam.encodeIP((self.config["public_ip"], self.config["auth_server_port"]))
                reply = struct.pack(">H", 1) + bin_ip
            elif command == "\x14" : # send out CSER server (not implemented)
                log.info(clientid + "Sending out list of CSER servers")
                if str(self.address[0]) in ipcalc.Network(str(globalvars.server_net)):
                    bin_ip = steam.encodeIP((self.config["server_ip"], 27013))
                else :
                    bin_ip = steam.encodeIP((self.config["public_ip"], 27013))
                reply = struct.pack(">H", 1) + bin_ip
            elif command == "\x18" : # source master server
                log.info(clientid + "Requesting Source Master Server")
                if str(self.address[0]) in ipcalc.Network(str(globalvars.server_net)):
                    bin_ip = steam.encodeIP((self.config["server_ip"], 27011))
                else :
                    bin_ip = steam.encodeIP((self.config["public_ip"], 27011))
                reply = struct.pack(">H", 1) + bin_ip
            elif command == "\x1e" : # rdkf master server
                log.info(clientid + "Requesting RDKF Master Server")
                if str(self.address[0]) in ipcalc.Network(str(globalvars.server_net)):
                    bin_ip = steam.encodeIP((self.config["server_ip"], 27012))
                else :
                    bin_ip = steam.encodeIP((self.config["public_ip"], 27012))
                reply = struct.pack(">H", 1) + bin_ip
            else :
                log.info(clientid + "Invalid/not implemented command: " + binascii.b2a_hex(msg))
                reply = "\x00\x00"

            self.socket.send_withlen(reply)
        
        else :
            log.error(clientid + "Invalid version message: " + binascii.b2a_hex(command))

        self.socket.close()
        log.info (clientid + "disconnected from Directory Server")
