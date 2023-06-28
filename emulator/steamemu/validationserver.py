import threading, logging, struct, binascii, time, socket, ipaddress, os.path, ast

from Crypto.Hash import SHA

import steam
import config
import globalvars

class validationserver(threading.Thread):
    def __init__(self, (socket, address), config) :
        threading.Thread.__init__(self)
        self.socket = socket
        self.address = address
        self.config = config

    def run(self):
        log = logging.getLogger("validatesrv")

        clientid = str(self.address) + ": "

        log.info(clientid + "Connected to Validation Server")

        command = self.socket.recv(13)
        
        log.debug(":" + binascii.b2a_hex(command[1:5]) + ":")
        log.debug(":" + binascii.b2a_hex(command) + ":")
        
        if command[1:5] == "\x00\x00\x00\x04" :

            self.socket.send("\x01" + socket.inet_aton(self.address[0])) #CRASHES IF NOT 01
            #log.debug((str(socket.inet_aton(self.address[0]))))
            #log.debug((str(socket.inet_ntoa(socket.inet_aton(self.address[0])))))
            #BERstring = binascii.a2b_hex("30819d300d06092a864886f70d010101050003818b0030818702818100") + binascii.a2b_hex(self.config["net_key_n"][2:]) + "\x02\x01\x11"
            #signature = steam.rsa_sign_message_1024(steam.main_key_sign, BERstring)
            #reply = struct.pack(">H", len(BERstring)) + BERstring + struct.pack(">H", len(signature)) + signature
            #self.socket.send(reply)
            ticket_full = self.socket.recv_withlen()
            ticket_full = binascii.b2a_hex(ticket_full)
            command = ticket_full[0:2]
            unknown1 = ticket_full[2:10]
            ip1 = ticket_full[10:18]
            ip2 = ticket_full[18:26]
            unknown2 = ticket_full[26:34]
            unknown3 = ticket_full[34:36]
            ticketLen = int(ticket_full[36:40], 16) * 2
            print(ticket_full)
            print(command)
            print(unknown1)
            print(ip1)
            print(ip2)
            print(unknown2)
            print(unknown3)
            print(ticketLen)
            ticket = ticket_full[40:40+ticketLen]
            print(ticket)
            subcommand1 = ticket[0:4]
            empty1_len = ticket[4:8]
            outerIV = ticket[8:40]
            empty1 = ticket[40:40+int(empty1_len, 16) * 2]
            username_len = int(ticket[296:300], 16)
            print(username_len)
            username_len_short = username_len - 50
            empty2_len = ticket[300:304]
            empty2 = ticket[304:304+int(empty2_len, 16) * 2]
            print(username_len_short)
            username = binascii.unhexlify(ticket[304:304+username_len_short])
            #accountId = ticket[304+int(empty2_len, 16)+4:304+int(empty2_len, 16)+4+16]
            accountId = "1020304000000000"
            print(accountId)
            iv = ticket_full[40+ticketLen:40+ticketLen+32]
            decr_len = ticket_full[40+ticketLen+32:40+ticketLen+32+4]
            encr_len = ticket_full[40+ticketLen+36:40+ticketLen+40]
            encr_data = ticket_full[40+ticketLen+40:40+ticketLen+104]
            sha_key = ticket_full[40+ticketLen+104:40+ticketLen+144]
            unknown1 = unknown1 + "\x01"
            currtime = time.time()
            tms = steam.unixtime_to_steamtime(currtime)
            steamid_header = binascii.a2b_hex("0000") #CRASHES IF NOT 00
            steamid = binascii.a2b_hex(accountId)
            unknown_data = bytearray(0x80)
            for ind in range(1, 9):
                start_index = (ind - 1) * 16
                value = (ind * 16) + ind
                unknown_data[start_index:start_index+16] = bytes([value] * 16)

            reply = unknown1 + tms + steamid_header + steamid + unknown_data
            replylen = struct.pack(">H", len(reply))
            self.socket.send(replylen + reply)
        
        #self.socket.send("\x01")

        #self.socket.close()
        #log.info(clientid + "Disconnected from Validation Server")