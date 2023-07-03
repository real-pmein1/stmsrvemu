import threading, logging, struct, binascii, time, ipaddress, os.path, ast, zlib
import socket as pysocket
import config
import utilities
import blob_utilities
import encryption
import emu_socket
import steamemu.logger
import globalvars

from mysql_class import MySQLConnector
from Crypto.Hash import SHA
from networkhandler import TCPNetworkHandler

log = logging.getLogger("AuthenticationSRV")

class authserver(TCPNetworkHandler):
    mysqlconn = 0
    
    def __init__(self, port, config):
        server_type = "authserver"
        super(authserver, self).__init__(config, port, server_type)  # Create an instance of NetworkHandler
 
        mysqlconn = MySQLConnector() # Initialize mysql connection
        mysqlconn.connect() # Connect Persistently

    def handle_client(self, clientsocket, address):
        server_string = utilities.convert_ip_port(str(self.config['validation_ip']),int(self.config['validation_port']))
        final_srvstring = server_string + server_string
        servers = binascii.b2a_hex("7F0000019A697F0000019A69") 
        #region 
        #need to figure out a way to assign steamid's.  hopefully with mysql
        steamid = binascii.a2b_hex("0000" + "80808000" + "00000000")
        
        clientid = str(address) + ": "
        if os.path.isfile("files/firstblob.py") :
            f = open("files/firstblob.py", "r")
            firstblob = f.read()
            f.close()
            execdict = {}
            execfile("files/firstblob.py", execdict)
            blob = blob_utilities.blob_serialize(execdict["blob"])
            steamui_hex = blob['\x02\x00\x00\x00']
            steamui_ver = struct.unpack('<I', steamui_hex)[0]
        else :
            f = open("files/firstblob.bin", "rb")
            blob = f.read()
            f.close()
            firstblob_bin = blob
            if firstblob_bin[0:2] == "\x01\x43":
                firstblob_bin = zlib.decompress(firstblob_bin[20:])
            firstblob_unser = blob_utilities.blob_unserialize(firstblob_bin)
            firstblob = blob_utilities.blob_dump(firstblob_unser)
                
            firstblob_list = firstblob.split("\n")
            steamui_hex = firstblob_list[3][25:41]
            steamui_ver = int(steamui_hex[14:16] + steamui_hex[10:12] + steamui_hex[6:8] + steamui_hex[2:4], 16)

        if steamui_ver < 61 : #guessing steamui version when steam client interface v2 changed to v3
            globalvars.tgt_version = "1"
            log.debug(clientid + "TGT version set to 1")
        else :
            globalvars.tgt_version = "2" #config file states 2 as default
            log.debug(clientid + "TGT version set to 2")

        
        log.info(clientid + "Connected to Auth Server")

        command = clientsocket.recv(13)
        
        log.debug(":" + binascii.b2a_hex(command[1:5]) + ":")
        log.debug(":" + binascii.b2a_hex(command) + ":")
#region 
        if command[1:5] == "\x00\x00\x00\x04" or command[1:5] == "\x00\x00\x00\x01" or command[1:5] == "\x00\x00\x00\x02" :

            clientsocket.send("\x00" + pysocket.inet_aton(clientsocket.address[0]))
            log.debug((str(pysocket.inet_aton(clientsocket.address[0]))))
            log.debug((str(pysocket.inet_ntoa(pysocket.inet_aton(clientsocket.address[0])))))

            command = clientsocket.recv_withlen()

            if len(command) > 1 and len(command) < 256 :
            
                if os.path.isfile("files/users.txt") :
                    users = {} #OLD
                    f = open("files/users.txt")
                    for line in f.readlines() :
                        if line[-1:] == "\n" :
                            line = line[:-1]
                        if line.find(":") != -1 :
                            (user, password) = line.split(":")
                            users[user] = password
                    f.close()
                    #example: 020005746573743100057465737431 (test1)
                    #02 = padding

                usernamelen = struct.unpack(">H", command[1:3])[0]
                
                userblob = {}

                username = command[3:3 + usernamelen]
                #print "user:" + username + ":"
                if username == "" :
                    username = "2003"
                log.info(clientid + "Processing logon for user: " + username) # 7465737431
                log.debug(clientid + "Username length: " + str(usernamelen)) # 0005
                #username length and username is then received again
                legacyuser = 0
                legacyblocked = 0
                try :
                    users[username]
                    legacyuser = 1
                    if users[username] == "blocked" :
                        legacyblocked = 1
                    else :
                        legacyblocked = 0
                except :
                    legacyuser = 0
                
                if (os.path.isfile("files/users/" + username + ".py")) and legacyuser == 0 :
                    with open("files/users/" + username + ".py", 'r') as f:
                        userblobstr = f.read()
                        userblob = ast.literal_eval(userblobstr[16:len(userblobstr)])
                    #print(userblob)
                    blocked = binascii.b2a_hex(userblob['\x0c\x00\x00\x00'])
                    if blocked == "0001" :
                        log.info(clientid + "Blocked user: " + username)
                        clientsocket.send("\x00\x00\x00\x00\x00\x00\x00\x00")
                        command = clientsocket.recv_withlen()
                        steamtime = utilities.unixtime_to_steamtime(time.time())
                        tgt_command = "\x04" #BLOCKED
                        padding = "\x00" * 1222
                        ticket_full = tgt_command + steamtime + padding
                        clientsocket.send(ticket_full)
                    else :
                        personalsalt = userblob['\x05\x00\x00\x00'][username]['\x02\x00\x00\x00']
                        print(personalsalt)
                        clientsocket.send(personalsalt) #NEW SALT PER USER
                        command = clientsocket.recv_withlen()
                        key = userblob['\x05\x00\x00\x00'][username]['\x01\x00\x00\x00'][0:16]
                        #print(binascii.b2a_hex(key))
                        IV = command[0:16]
                        #print(binascii.b2a_hex(IV))
                        encrypted = command[20:36]
                        #print(binascii.b2a_hex(encrypted))
                        decodedmessage = binascii.b2a_hex(encryption.aes_decrypt(key, IV, encrypted))
                        log.debug(clientid + "Decoded message: " + decodedmessage)
                
                        if not decodedmessage.endswith("04040404") :
                            wrongpass = "1"
                            log.info(clientid + "Incorrect password entered for: " + username)
                        else :
                            wrongpass = "0"                
                
                        # create login ticket
                        execdict = {}
                        execdict_new = {}
                        with open("files/users/" + username + ".py", 'r') as f:
                            userblobstr = f.read()
                            execdict = ast.literal_eval(userblobstr[16:len(userblobstr)])
                        secretkey = {'\x05\x00\x00\x00'}
                        def without_keys(d, keys) :
                            return {x: d[x] for x in d if x not in keys}
                        execdict_new = without_keys(execdict, secretkey)
                        blob = blob_utilities.blob_serialize(execdict_new)
                        bloblen = len(blob)
                        log.debug("Blob length: " + str(bloblen) + " unserialized Blob data: " + str(execdict) + " serialized Blob data: " + str(blob))
                        innerkey = binascii.a2b_hex("10231230211281239191238542314233")
                        innerIV  = binascii.a2b_hex("12899c8312213a123321321321543344")
                        blob_encrypted = encryption.aes_encrypt(innerkey, innerIV, blob)
                        blob_encrypted = struct.pack("<L", bloblen) + innerIV + blob_encrypted
                        blob_signature = encryption.sign_message(innerkey, blob_encrypted)
                        blob_encrypted_len = 10 + len(blob_encrypted) + 20
                        blob_encrypted = struct.pack(">L", blob_encrypted_len) + "\x01\x45" + struct.pack("<LL", blob_encrypted_len, 0) + blob_encrypted + blob_signature
                        currtime = time.time()
                        outerIV = binascii.a2b_hex("92183129534234231231312123123353")
                        #steamid = binascii.a2b_hex("0000" + "80808000" + "00000000")
                        steamid = binascii.a2b_hex("0000" + binascii.b2a_hex(userblob['\x06\x00\x00\x00'][username]['\x01\x00\x00\x00'][0:16]))
                        #servers = binascii.a2b_hex("451ca0939a69451ca0949a69")
                        #authport = struct.pack("<L", int(port))
                        bin_ip = utilities.encodeIP((self.config["server_ip"], self.config["validation_port"]))
                        #bin_ip = steam.encodeIP(("172.21.0.20", "27039"))
                        servers = bin_ip + bin_ip
                        times = utilities.unixtime_to_steamtime(currtime) + utilities.unixtime_to_steamtime(currtime + (60*60*24*28))
                        subheader = innerkey + steamid + servers + times
                        subheader_encrypted = encryption.aes_encrypt(key, outerIV, subheader)
                        subhead_decr_len = "\x00\x36"
                        subhead_encr_len = "\x00\x40"
                        if globalvars.tgt_version == "1" : #nullData1
                            subheader_encrypted = "\x00\x01" + outerIV + subhead_decr_len + subhead_encr_len + subheader_encrypted #TTicket_SubHeader (EncrData)
                            log.debug(clientid + "TGT Version: 1") #v2 Steam
                        elif globalvars.tgt_version == "2" :
                            subheader_encrypted = "\x00\x02" + outerIV + "\x00\x36\x00\x40" + subheader_encrypted
                            log.debug(clientid + "TGT Version: 2") #v3 Steam
                        else :
                            subheader_encrypted = "\x00\x02" + outerIV + "\x00\x36\x00\x40" + subheader_encrypted
                            log.debug(clientid + "TGT Version: 2") #Assume v3 Steam
                        #unknown_part = "\x01\x68" + ("\xff" * 0x168) #THE ACTUAL TICKET!!!
                        #unknown_part = "\x01\x64" + ("\xfe" * 0x164)
                        #\x00\x02 + \x00\x80 + outerIV + (\x00 * int(80)) + \x00\x3a + \x00\x50 + (\x00 * int(50)) + DATA=\x00\x10 + (\x06\x01 in user.py) + clientIP + \x00\x00\x00\x00 + (\x00 * int(80))
                        #0 = eVersionNum
                        #1=eUniqueAccountName
                        #2=eAccountUserName
                        #3=eSteamInstanceID
                        #4=eSteamLocalUserID
                        #5=eClientExternalIPAddr
                        #6=eClientLocalIPAddr
                        #7=eUserIDTicketValidationServerIPAddr1
                        #8=eUserIDTicketValidationServerport1
                        #9=eUserIDTicketValidationServerIPAddr2
                        #10=eUserIDTicketValidationServerport2
                        #11=eClientToServerAESSessionKey
                        #12=eTicketCreationTime
                        #13=TicketValidUntilTime
                        #14=ServerReadablePart
                        subcommand3 = "\x00\x00\x00\x00"
                        empty1_len = "\x00\x80"
                        empty1 = ("\x00" * 0x80) #TTicketHeader unknown encrypted
                        empty3 = ("\x00" * 0x80) #unknown encrypted
                        #username_len = len(username) * 2
                        #username_len_packed = struct.pack(">H", 50 + username_len)
                        accountId = userblob['\x06\x00\x00\x00'][username]['\x01\x00\x00\x00'][0:16] #SteamID
                        clientIP = pysocket.inet_aton(clientsocket.address[0])
                        if globalvars.tgt_version == "1" :
                            subcommand1 = "\x00\x01" #for TGT v1
                            subcommand2 = "" #missing for TGT v1
                            empty2_dec_len = "\x00\x42"
                            empty2_enc_len = "\x00\x50"
                            empty2 = ("\x00" * 0x50) #160 chars long (80 int bytes) unknown encrypted
                        elif globalvars.tgt_version == "2" :
                            subcommand1 = "\x00\x02" #for TGT v2
                            subcommand2 = "\x00\x10" #steamID+clientIPaddress TGT v2 only
                            subcommand2 = subcommand2 + accountId + clientIP
                            empty2_dec_len = "\x00\x52"
                            empty2_enc_len = "\x00\x60"
                            empty2 = ("\x00" * 0x60) #192 chars long (96 int bytes) unknown encrypted
                        else :
                            subcommand1 = "\x00\x02" #assume TGT v2
                            subcommand2 = "\x00\x10" #steamID+clientIPaddress TGT v2 only
                            subcommand2 = subcommand2 + accountId + clientIP
                            empty2_dec_len = "\x00\x52"
                            empty2_enc_len = "\x00\x60"
                            empty2 = ("\x00" * 0x60) #192 chars long (96 int bytes) unknown encrypted
                        
                        #empty2 = username + empty2_empty[(len(username)):]
                        
                        real_ticket = subcommand1 + empty1_len + empty1 + IV + empty2_dec_len + empty2_enc_len + empty2 + subcommand2 + empty3
                        real_ticket_len = struct.pack(">H", len(real_ticket)) #TicketLen
                        #ticket = subheader_encrypted + unknown_part + blob_encrypted
                        ticket = subheader_encrypted + real_ticket_len + real_ticket + blob_encrypted
                        
                        ticket_signed = ticket + encryption.sign_message(innerkey, ticket)
                        if wrongpass == "1" :
                            tgt_command = "\x02"
                        else :
                            tgt_command = "\x00" # AuthenticateAndRequestTGT command
                        steamtime = utilities.unixtime_to_steamtime(time.time())
                        clock_skew_tolerance = "\x00\xd2\x49\x6b\x00\x00\x00\x00"
                        ticket_full = tgt_command + steamtime + clock_skew_tolerance + struct.pack(">L", len(ticket_signed)) + ticket_signed
                        clientsocket.send(ticket_full)    
                        
                elif legacyblocked == 1 :
                    log.warning(clientid + "Blocked legacy user: " + username)
                    clientsocket.send("\x00\x00\x00\x00\x00\x00\x00\x00")
                    steamtime = utilities.unixtime_to_steamtime(time.time())
                    tgt_command = "\x04" #BLOCKED
                    padding = "\x00" * 1222
                    ticket_full = tgt_command + steamtime + padding
                    clientsocket.send(ticket_full)
                elif legacyuser == 1 :
                    log.warning("Legacy user: " + username)
                
                    clientsocket.send("\x01\x23\x45\x67\x89\xab\xcd\xef") # salt - OLD
                    command = clientsocket.recv_withlen()

                    key = SHA.new("\x01\x23\x45\x67" + users[username] + "\x89\xab\xcd\xef").digest()[:16]
                    #print(binascii.b2a_hex(key))
                    IV = command[0:16]
                    #print(binascii.b2a_hex(IV))
                    encrypted = command[20:36]
                    #print(binascii.b2a_hex(encrypted))
                    decodedmessage = binascii.b2a_hex(encryption.aes_decrypt(key, IV, encrypted))
                    log.debug(clientid + "Decoded message: " + decodedmessage)
                
                    if not decodedmessage.endswith("04040404") :
                        wrongpass = "1"
                        log.info(clientid + "Incorrect password entered for: " + username)
                        #wrongpass = "0"  
                    else :
                        wrongpass = "0"                
                
                    # create login ticket
                    execdict = {}
                    execdict_new = {}
                    #execfile("files/users/%s.py" % username, execdict)
                    with open("files/users/" + username + ".py", 'r') as f:
                        userblobstr = f.read()
                        execdict = ast.literal_eval(userblobstr[16:len(userblobstr)])
                    #blob = blob_utilities.blob_serialize(execdict["user_registry"])
                    secretkey = {'\x05\x00\x00\x00'}
                    def without_keys(d, keys) :
                        return {x: d[x] for x in d if x not in keys}
                    execdict_new = without_keys(execdict, secretkey)
                    blob = blob_utilities.blob_serialize(execdict_new)
                    bloblen = len(blob)
                    log.debug("Blob length: " + str(bloblen))
                    innerkey = binascii.a2b_hex("10231230211281239191238542314233")
                    innerIV  = binascii.a2b_hex("12899c8312213a123321321321543344")
                    blob_encrypted = encryption.aes_encrypt(innerkey, innerIV, blob)
                    blob_encrypted = struct.pack("<L", bloblen) + innerIV + blob_encrypted
                    blob_signature = encryption.sign_message(innerkey, blob_encrypted)
                    blob_encrypted_len = 10 + len(blob_encrypted) + 20
                    blob_encrypted = struct.pack(">L", blob_encrypted_len) + "\x01\x45" + struct.pack("<LL", blob_encrypted_len, 0) + blob_encrypted + blob_signature
                    currtime = time.time()
                    outerIV = binascii.a2b_hex("92183129534234231231312123123353")
                    steamid = binascii.a2b_hex("0000" + "80808000" + "00000000")
                    bin_ip = utilities.encodeIP((globalvars.serverip, self.config["validation_server_port"]))
                    servers = bin_ip + bin_ip
                    times = utilities.unixtime_to_steamtime(currtime) + utilities.unixtime_to_steamtime(currtime + (60*60*24*28))
                    subheader = innerkey + steamid + servers + times
                    subheader_encrypted = encryption.aes_encrypt(key, outerIV, subheader)
                    if globalvars.tgt_version == "1" :
                        subheader_encrypted = "\x00\x01" + outerIV + "\x00\x36\x00\x40" + subheader_encrypted
                        log.debug(clientid + "TGT Version: 1") #v2 Steam
                    elif globalvars.tgt_version == "2" :
                        subheader_encrypted = "\x00\x02" + outerIV + "\x00\x36\x00\x40" + subheader_encrypted
                        log.debug(clientid + "TGT Version: 2") #v3 Steam
                    else :
                        subheader_encrypted = "\x00\x02" + outerIV + "\x00\x36\x00\x40" + subheader_encrypted
                        log.debug(clientid + "TGT Version: 2")
                    unknown_part = "\x01\x68" + ("\xff" * 0x168)
                    ticket = subheader_encrypted + unknown_part + blob_encrypted
                    ticket_signed = ticket + encryption.sign_message(innerkey, ticket)
                    if wrongpass == "1" :
                        tgt_command = "\x02"
                    else :
                        tgt_command = "\x00" # AuthenticateAndRequestTGT command
                    
                    steamtime = utilities.unixtime_to_steamtime(time.time())
                    ticket_full = tgt_command + steamtime + "\x00\xd2\x49\x6b\x00\x00\x00\x00" + struct.pack(">L", len(ticket_signed)) + ticket_signed
                    clientsocket.send(ticket_full)
                else :
                    log.info(clientid + "Unknown user: " + username)
                    clientsocket.send("\x00\x00\x00\x00\x00\x00\x00\x00")
                    steamtime = utilities.unixtime_to_steamtime(time.time())
                    tgt_command = "\x01"
                    padding = "\x00" * 1222
                    ticket_full = tgt_command + steamtime + padding
                    clientsocket.send(ticket_full)
    
            else :
                if binascii.b2a_hex(command[0]) == "04" : #User Logged off
                    log.info(clientid + "User Logged Off")
                    clientsocket.close()         
                elif binascii.b2a_hex(command[0]) == "0A" : # Get Encrypted Ticket for AppServer
                    log.info(clientid + "Get Encrypted UserID Ticket To Send To AppServer")
                    print(binascii.b2a_hex(command))
                    clientsocket.send("\x01")
                elif binascii.b2a_hex(command[0]) == "10" : # Change Password
                    log.info(clientid + "Change password")
                    print(binascii.b2a_hex(command))
                    clientsocket.send("\x01")
                elif binascii.b2a_hex(command[0]) == "12" : # Change Email
                    log.info(clientid + "Change Email")
                    BERstring = binascii.a2b_hex("30819d300d06092a864886f70d010101050003818b0030818702818100") + binascii.a2b_hex(self.config["net_key_n"][2:]) + "\x02\x01\x11"
                    signature = encryption.rsa_sign_message_1024(encryption.main_key_sign, BERstring)
                    reply = struct.pack(">H", len(BERstring)) + BERstring + struct.pack(">H", len(signature)) + signature
                    clientsocket.send(reply)
                    reply = clientsocket.recv_withlen()
                
                    RSAdata = reply[2:130]
                    datalength = struct.unpack(">L", reply[130:134])[0]
                    cryptedblob_signature = reply[134:136]
                    cryptedblob_length = reply[136:140]
                    cryptedblob_slack = reply[140:144]
                    cryptedblob = reply[144:]
                
                    key = encryption.get_aes_key(RSAdata, encryption.network_key)
                    log.debug("Message verification:" + repr(encryption.verify_message(key, cryptedblob)))
                    plaintext_length = struct.unpack("<L", cryptedblob[0:4])[0]
                    IV = cryptedblob[4:20]
                    ciphertext = cryptedblob[20:-20]
                    plaintext = encryption.aes_decrypt(key, IV, ciphertext)
                    plaintext = plaintext[0:plaintext_length]
                    #print(plaintext)
                    blobdict = blob_utilities.blob_unserialize(plaintext)
                    #print(blobdict)
                    usernamechk = blobdict['\x01\x00\x00\x00']
                    username_str = usernamechk.rstrip('\x00')
                    with open("files/users/" + username_str + ".py", 'r') as userblobfile:
                        userblobstr = userblobfile.read()
                        userblob = ast.literal_eval(userblobstr[16:len(userblobstr)])
                    #print(str(userblob))
                    personalsalt = userblob['\x05\x00\x00\x00'][username_str]['\x02\x00\x00\x00']
                    #print(personalsalt)
                    clientsocket.send(personalsalt) #NEW SALT PER USER
                    
                    #===================Reply with verification answer=======================#
                    
                    reply2 = clientsocket.recv_withlen()
                
                    RSAdata = reply2[2:130]
                    datalength = struct.unpack(">L", reply2[130:134])[0]
                    cryptedblob_signature = reply2[134:136]
                    cryptedblob_length = reply2[136:140]
                    cryptedblob_slack = reply2[140:144]
                    cryptedblob = reply2[144:]
                
                    key = encryption.get_aes_key(RSAdata, encryption.network_key)
                    log.debug("Message verification:" + repr(encryption.verify_message(key, cryptedblob)))
                    plaintext_length = struct.unpack("<L", cryptedblob[0:4])[0]
                    IV = cryptedblob[4:20]
                    ciphertext = cryptedblob[20:-20]
                    plaintext = encryption.aes_decrypt(key, IV, ciphertext)
                    plaintext = plaintext[0:plaintext_length]
                    print(blob_utilities.blob_unserialize(plaintext))
                    clientsocket.send("\x01")
                elif binascii.b2a_hex(command[0]) == "11" : # Change Personal Question
                    log.info(clientid + "Change Personal Question")
                    print(command)
                   # print blob_utilities.blob_unserialize(plaintext)
                    #clientsocket.send("\x01")
                elif binascii.b2a_hex(command[0]) == "1C" : # Change Account Name
                    log.info(clientid + "Change Account Name")
                    print(binascii.b2a_hex(command))
                    clientsocket.send("\x01")   
                elif binascii.b2a_hex(command[0]) == "09" : # Retrieve Account Info
                    print("Request Account Information")
                    clientsocket.send("\x01") 
                elif command == "\x1d" : #Create Account: Is Name in use
                    log.info(clientid + "command: query account name already in use")
                    #BERstring = binascii.a2b_hex("30819d300d06092a864886f70d010101050003818b0030818702818100") + binascii.a2b_hex("bf973e24beb372c12bea4494450afaee290987fedae8580057e4f15b93b46185b8daf2d952e24d6f9a23805819578693a846e0b8fcc43c23e1f2bf49e843aff4b8e9af6c5e2e7b9df44e29e3c1c93f166e25e42b8f9109be8ad03438845a3c1925504ecc090aabd49a0fc6783746ff4e9e090aa96f1c8009baf9162b66716059") + "\x02\x01\x11"
                    BERstring = binascii.a2b_hex("30819d300d06092a864886f70d010101050003818b0030818702818100") + binascii.a2b_hex(self.config["net_key_n"][2:]) + "\x02\x01\x11"
                    #BERstring = binascii.a2b_hex("30819d300d06092a864886f70d010101050003818b0030818702818100") + binascii.a2b_hex("9525173d72e87cbbcbdc86146587aebaa883ad448a6f814dd259bff97507c5e000cdc41eed27d81f476d56bd6b83a4dc186fa18002ab29717aba2441ef483af3970345618d4060392f63ae15d6838b2931c7951fc7e1a48d261301a88b0260336b8b54ab28554fb91b699cc1299ffe414bc9c1e86240aa9e16cae18b950f900f") + "\x02\x01\x11"
                    signature = encryption.rsa_sign_message_1024(encryption.main_key_sign, BERstring)
                    reply = struct.pack(">H", len(BERstring)) + BERstring + struct.pack(">H", len(signature)) + signature
                    clientsocket.send(reply)

                    reply = clientsocket.recv_withlen()
                
                    RSAdata = reply[2:130]
                    datalength = struct.unpack(">L", reply[130:134])[0]
                    cryptedblob_signature = reply[134:136]
                    cryptedblob_length = reply[136:140]
                    cryptedblob_slack = reply[140:144]
                    cryptedblob = reply[144:]
                
                    key = encryption.get_aes_key(RSAdata, encryption.network_key)
                    log.debug("Message verification:" + repr(encryption.verify_message(key, cryptedblob)))
                    plaintext_length = struct.unpack("<L", cryptedblob[0:4])[0]
                    IV = cryptedblob[4:20]
                    ciphertext = cryptedblob[20:-20]
                    plaintext = encryption.aes_decrypt(key, IV, ciphertext)
                    plaintext = plaintext[0:plaintext_length]
                    #print(plaintext)
                    plainblob = blob_utilities.blob_unserialize(plaintext)
                    #print(plainblob)
                    username = plainblob['\x01\x00\x00\x00']
                    username_str = username.rstrip('\x00')
                    #print(len(username_str))
                    if (os.path.isfile("files/users/" + username_str + ".py")) :
                        clientsocket.send("\x01") #Username in use!
                    else :
                        clientsocket.send("\x00") #Username is not in use      
                elif command == "\x22" : # Check Email is verified
                    log.info(clientid + "command: Check email [Not Implemented]")
                    clientsocket.send("\x00")
                elif command == "\x01" : # Create User
                    log.info(clientid + "command: Create user")
                    #BERstring = binascii.a2b_hex("30819d300d06092a864886f70d010101050003818b0030818702818100") + binascii.a2b_hex("bf973e24beb372c12bea4494450afaee290987fedae8580057e4f15b93b46185b8daf2d952e24d6f9a23805819578693a846e0b8fcc43c23e1f2bf49e843aff4b8e9af6c5e2e7b9df44e29e3c1c93f166e25e42b8f9109be8ad03438845a3c1925504ecc090aabd49a0fc6783746ff4e9e090aa96f1c8009baf9162b66716059") + "\x02\x01\x11"
                    BERstring = binascii.a2b_hex("30819d300d06092a864886f70d010101050003818b0030818702818100") + binascii.a2b_hex(self.config["net_key_n"][2:]) + "\x02\x01\x11"
                    #BERstring = binascii.a2b_hex("30819d300d06092a864886f70d010101050003818b0030818702818100") + binascii.a2b_hex("9525173d72e87cbbcbdc86146587aebaa883ad448a6f814dd259bff97507c5e000cdc41eed27d81f476d56bd6b83a4dc186fa18002ab29717aba2441ef483af3970345618d4060392f63ae15d6838b2931c7951fc7e1a48d261301a88b0260336b8b54ab28554fb91b699cc1299ffe414bc9c1e86240aa9e16cae18b950f900f") + "\x02\x01\x11"
                    signature = encryption.rsa_sign_message_1024(encryption.main_key_sign, BERstring)
                    reply = struct.pack(">H", len(BERstring)) + BERstring + struct.pack(">H", len(signature)) + signature
                    clientsocket.send(reply)

                    reply = clientsocket.recv_withlen()
                
                    RSAdata = reply[2:130]
                    datalength = struct.unpack(">L", reply[130:134])[0]
                    cryptedblob_signature = reply[134:136]
                    cryptedblob_length = reply[136:140]
                    cryptedblob_slack = reply[140:144]
                    cryptedblob = reply[144:]
                
                    key = encryption.get_aes_key(RSAdata, encryption.network_key)
                    log.debug("Message verification:" + repr(encryption.verify_message(key, cryptedblob)))
                    plaintext_length = struct.unpack("<L", cryptedblob[0:4])[0]
                    IV = cryptedblob[4:20]
                    ciphertext = cryptedblob[20:-20]
                    plaintext = encryption.aes_decrypt(key, IV, ciphertext)
                    plaintext = plaintext[0:plaintext_length]
                    print("plaintext: " + plaintext)
                    plainblob = blob_utilities.blob_unserialize(plaintext)
                    print("plainblob: " + str(plainblob))
                    
                    invalid = {'\x07\x00\x00\x00'}
                    def without_keys(d, keys) :
                        return {x: d[x] for x in d if x not in keys}
                    
                    plainblob_fixed = without_keys(plainblob, invalid)
                    
                    dict7 = {}
                    dict7 = {'\x07\x00\x00\x00': {'\x00\x00\x00\x00': {'\x01\x00\x00\x00': '\xe0\xe0\xe0\xe0\xe0\xe0\xe0\x00', '\x02\x00\x00\x00': '\x00\x00\x00\x00\x00\x00\x00\x00', '\x03\x00\x00\x00': '\x01\x00', '\x05\x00\x00\x00': '\x00', '\x06\x00\x00\x00': '\x1f\x00'}}}
                    
                    plainblob_fixed.update(dict7)
                    
                    #username = plainblob['\x06\x00\x00\x00']
                    #username_str = str(username)[2:str(plainblob['\x06\x00\x00\x00']).find('\'', 3)]
                    username = plainblob['\x01\x00\x00\x00']
                    username_str = username.rstrip('\x00')
                        
                    with open("files\\users\\" + username_str + ".py", 'w') as userblobfile :
                        userblobfile.write("user_registry = ")
                        userblobfile.write(str(plainblob_fixed))
                    
                    clientsocket.send("\x00")
                elif command == "\x13" : # Verify Email
                    print("verify Email")
                    clientsocket.send("\x01") 
                elif command == "\x14" : # Request verification Email
                    print("Requested Verification Email")
                    clientsocket.send("\x01") 
                elif command == "\x15" : # Update Account Billing Info
                    print("Update Account Billing Information") 
                    clientsocket.send("\x01") 
                elif command == "\x16" : # Update Subscription Billing Info
                    print("Update Subscription Billing Information")
                    BERstring = binascii.a2b_hex("30819d300d06092a864886f70d010101050003818b0030818702818100") + binascii.a2b_hex(self.config["net_key_n"][2:]) + "\x02\x01\x11"
                    signature = encryption.rsa_sign_message_1024(encryption.main_key_sign, BERstring)
                    reply = struct.pack(">H", len(BERstring)) + BERstring + struct.pack(">H", len(signature)) + signature
                    clientsocket.send(reply)
                    reply = clientsocket.recv_withlen()
                
                    RSAdata = reply[2:130]
                    datalength = struct.unpack(">L", reply[130:134])[0]
                    cryptedblob_signature = reply[134:136]
                    cryptedblob_length = reply[136:140]
                    cryptedblob_slack = reply[140:144]
                    cryptedblob = reply[144:]
                
                    key = encryption.get_aes_key(RSAdata, encryption.network_key)
                    log.debug("Message verification:" + repr(encryption.verify_message(key, cryptedblob)))
                    plaintext_length = struct.unpack("<L", cryptedblob[0:4])[0]
                    IV = cryptedblob[4:20]
                    ciphertext = cryptedblob[20:-20]
                    plaintext = encryption.aes_decrypt(key, IV, ciphertext)
                    plaintext = plaintext[0:plaintext_length]
                    #print(plaintext)
                    blobdict = blob_utilities.blob_unserialize(plaintext)
                    #print(blobdict)
                    usernamechk = blobdict['\x01\x00\x00\x00']
                    username_str = usernamechk.rstrip('\x00')
                    with open("files/users/" + username_str + ".py", 'r') as userblobfile:
                        userblobstr = userblobfile.read()
                        userblob = ast.literal_eval(userblobstr[16:len(userblobstr)])
                    #print(str(userblob))
                    personalsalt = userblob['\x05\x00\x00\x00'][username_str]['\x02\x00\x00\x00']
                    #print(personalsalt)
                    clientsocket.send(personalsalt) #NEW SALT PER USER
                    
                    reply2 = clientsocket.recv_withlen()
                
                    RSAdata = reply2[2:130]
                    datalength = struct.unpack(">L", reply2[130:134])[0]
                    cryptedblob_signature = reply2[134:136]
                    cryptedblob_length = reply2[136:140]
                    cryptedblob_slack = reply2[140:144]
                    cryptedblob = reply2[144:]
                
                    key = encryption.get_aes_key(RSAdata, encryption.network_key)
                    log.debug("Message verification:" + repr(encryption.verify_message(key, cryptedblob)))
                    plaintext_length = struct.unpack("<L", cryptedblob[0:4])[0]
                    IV = cryptedblob[4:20]
                    ciphertext = cryptedblob[20:-20]
                    plaintext = encryption.aes_decrypt(key, IV, ciphertext)
                    plaintext = plaintext[0:plaintext_length]
                    #print blob_utilities.blob_unserialize(plaintext)
                elif command == "\x0e" : # Lost Pass: request account info by username/request email verification
                    log.info(clientid + "Lost password - Find by Username [Not Implemented]")
                    #BERstring = binascii.a2b_hex("30819d300d06092a864886f70d010101050003818b0030818702818100") + binascii.a2b_hex("bf973e24beb372c12bea4494450afaee290987fedae8580057e4f15b93b46185b8daf2d952e24d6f9a23805819578693a846e0b8fcc43c23e1f2bf49e843aff4b8e9af6c5e2e7b9df44e29e3c1c93f166e25e42b8f9109be8ad03438845a3c1925504ecc090aabd49a0fc6783746ff4e9e090aa96f1c8009baf9162b66716059") + "\x02\x01\x11"
                    BERstring = binascii.a2b_hex("30819d300d06092a864886f70d010101050003818b0030818702818100") + binascii.a2b_hex(self.config["net_key_n"][2:]) + "\x02\x01\x11"
                    signature = encryption.rsa_sign_message_1024(encryption.main_key_sign, BERstring)
                    reply = struct.pack(">H", len(BERstring)) + BERstring + struct.pack(">H", len(signature)) + signature
                    clientsocket.send(reply)
                    reply = clientsocket.recv_withlen()
                
                    RSAdata = reply[2:130]
                    datalength = struct.unpack(">L", reply[130:134])[0]
                    cryptedblob_signature = reply[134:136]
                    cryptedblob_length = reply[136:140]
                    cryptedblob_slack = reply[140:144]
                    cryptedblob = reply[144:]
                
                    key = encryption.get_aes_key(RSAdata, encryption.network_key)
                    log.debug("Message verification:" + repr(encryption.verify_message(key, cryptedblob)))
                    plaintext_length = struct.unpack("<L", cryptedblob[0:4])[0]
                    IV = cryptedblob[4:20]
                    ciphertext = cryptedblob[20:-20]
                    plaintext = encryption.aes_decrypt(key, IV, ciphertext)
                    plaintext = plaintext[0:plaintext_length]
                    #print(plaintext)
                    blobdict = blob_utilities.blob_unserialize(plaintext)
                    usernamechk = blobdict['\x01\x00\x00\x00']
                    username_str = usernamechk.rstrip('\x00')
                    if os.path.isfile("files/users/" + username_str + ".py") :
                        clientsocket.send("\x00")
                    else :
                        clientsocket.send("\x01")
                elif command == "\x0f" : # Lost Pass: Reset Password
                    log.info(clientid + "command: Lost password - reset")
                    #BERstring = binascii.a2b_hex("30819d300d06092a864886f70d010101050003818b0030818702818100") + binascii.a2b_hex("bf973e24beb372c12bea4494450afaee290987fedae8580057e4f15b93b46185b8daf2d952e24d6f9a23805819578693a846e0b8fcc43c23e1f2bf49e843aff4b8e9af6c5e2e7b9df44e29e3c1c93f166e25e42b8f9109be8ad03438845a3c1925504ecc090aabd49a0fc6783746ff4e9e090aa96f1c8009baf9162b66716059") + "\x02\x01\x11"
                    BERstring = binascii.a2b_hex("30819d300d06092a864886f70d010101050003818b0030818702818100") + binascii.a2b_hex(self.config["net_key_n"][2:]) + "\x02\x01\x11"
                    signature = encryption.rsa_sign_message_1024(encryption.main_key_sign, BERstring)
                    reply = struct.pack(">H", len(BERstring)) + BERstring + struct.pack(">H", len(signature)) + signature
                    clientsocket.send(reply)
                    reply = clientsocket.recv_withlen()
                
                    RSAdata = reply[2:130]
                    datalength = struct.unpack(">L", reply[130:134])[0]
                    cryptedblob_signature = reply[134:136]
                    cryptedblob_length = reply[136:140]
                    cryptedblob_slack = reply[140:144]
                    cryptedblob = reply[144:]
                
                    key = encryption.get_aes_key(RSAdata, encryption.network_key)
                    log.debug("Message verification:" + repr(encryption.verify_message(key, cryptedblob)))
                    plaintext_length = struct.unpack("<L", cryptedblob[0:4])[0]
                    IV = cryptedblob[4:20]
                    ciphertext = cryptedblob[20:-20]
                    plaintext = encryption.aes_decrypt(key, IV, ciphertext)
                    plaintext = plaintext[0:plaintext_length]
                    #print(plaintext)
                    blobdict = blob_utilities.blob_unserialize(plaintext)
                    #print(blobdict)
                    usernamechk = blobdict['\x01\x00\x00\x00']
                    username_str = usernamechk.rstrip('\x00')
                    with open("files/users/" + username_str + ".py", 'r') as userblobfile:
                        userblobstr = userblobfile.read()
                        userblob = ast.literal_eval(userblobstr[16:len(userblobstr)])
                    #print(str(userblob))
                    personalsalt = userblob['\x05\x00\x00\x00'][username_str]['\x02\x00\x00\x00']
                    #print(personalsalt)
                    clientsocket.send(personalsalt) #NEW SALT PER USER
                    
                    #===================Reply with verification answer=======================#
                    
                    reply2 = clientsocket.recv_withlen()
                
                    RSAdata = reply2[2:130]
                    datalength = struct.unpack(">L", reply2[130:134])[0]
                    cryptedblob_signature = reply2[134:136]
                    cryptedblob_length = reply2[136:140]
                    cryptedblob_slack = reply2[140:144]
                    cryptedblob = reply2[144:]
                
                    key = encryption.get_aes_key(RSAdata, encryption.network_key)
                    log.debug("Message verification:" + repr(encryption.verify_message(key, cryptedblob)))
                    plaintext_length = struct.unpack("<L", cryptedblob[0:4])[0]
                    IV = cryptedblob[4:20]
                    ciphertext = cryptedblob[20:-20]
                    plaintext = encryption.aes_decrypt(key, IV, ciphertext)
                    plaintext = plaintext[0:plaintext_length]
                    print(blob_utilities.blob_unserialize(plaintext))
                elif command == "\x20" : # Lost Pass: request account info by email
                    log.info(clientid + "command: Lost password - email check [Not Implemented]")
                elif command == "\x21" : # Lost Pass: request account info by cdkey
                    log.info(clientid + "command: Lost password - request account name by cdkey [Not Implemented]")
                else :
                    # This is cheating. I've just cut'n'pasted the hex from the network_key. FIXME
                    #BERstring = binascii.a2b_hex("30819d300d06092a864886f70d010101050003818b0030818702818100") + binascii.a2b_hex("bf973e24beb372c12bea4494450afaee290987fedae8580057e4f15b93b46185b8daf2d952e24d6f9a23805819578693a846e0b8fcc43c23e1f2bf49e843aff4b8e9af6c5e2e7b9df44e29e3c1c93f166e25e42b8f9109be8ad03438845a3c1925504ecc090aabd49a0fc6783746ff4e9e090aa96f1c8009baf9162b66716059") + "\x02\x01\x11"
                    BERstring = binascii.a2b_hex("30819d300d06092a864886f70d010101050003818b0030818702818100") + binascii.a2b_hex(self.config["net_key_n"][2:]) + "\x02\x01\x11"
                    signature = encryption.rsa_sign_message_1024(encryption.main_key_sign, BERstring)
                    reply = struct.pack(">H", len(BERstring)) + BERstring + struct.pack(">H", len(signature)) + signature
                    clientsocket.send(reply)

                    reply = clientsocket.recv_withlen()
                
                    RSAdata = reply[2:130]
                    datalength = struct.unpack(">L", reply[130:134])[0]
                    cryptedblob_signature = reply[134:136]
                    cryptedblob_length = reply[136:140]
                    cryptedblob_slack = reply[140:144]
                    cryptedblob = reply[144:]
                
                    key = encryption.get_aes_key(RSAdata, encryption.network_key)
                    log.debug("Message verification:" + repr(encryption.verify_message(key, cryptedblob)))
                    plaintext_length = struct.unpack("<L", cryptedblob[0:4])[0]
                    IV = cryptedblob[4:20]
                    ciphertext = cryptedblob[20:-20]
                    plaintext = encryption.aes_decrypt(key, IV, ciphertext)
                    plaintext = plaintext[0:plaintext_length]
                    #print blob_utilities.blob_unserialize(plaintext)
                    print(clientsocket)
                    clientsocket.send("\x00")
                #log.warning(clientid + "Invalid command length: " + str(len(command)))

        else :
            data = clientsocket.recv(65535)
            log.warning(clientid + "Invalid command: " + binascii.b2a_hex(command[1:5]))
            log.warning(clientid + "Extra data:", binascii.b2a_hex(data))

        clientsocket.close()
        log.info(clientid + "Disconnected from Auth Server")
