import threading, logging, struct, binascii, time, socket, ipaddress, os.path, ast

from Crypto.Hash import SHA

import steam
import config
import globalvars

class authserver(threading.Thread):
    def __init__(self, (socket, address), config) :
        threading.Thread.__init__(self)
        self.socket = socket
        self.address = address
        self.config = config

    def run(self):
        log = logging.getLogger("authsrv")

        clientid = str(self.address) + ": "

        log.info(clientid + "Connected to Auth Server")

        command = self.socket.recv(13)
        
        log.debug(":" + binascii.b2a_hex(command[1:5]) + ":")
        log.debug(":" + binascii.b2a_hex(command) + ":")

        if command[1:5] == "\x00\x00\x00\x04" or command[1:5] == "\x00\x00\x00\x01" or command[1:5] == "\x00\x00\x00\x02" :

            self.socket.send("\x00" + socket.inet_aton(self.address[0]))
            log.debug((str(socket.inet_aton(self.address[0]))))
            log.debug((str(socket.inet_ntoa(socket.inet_aton(self.address[0])))))

            command = self.socket.recv_withlen()

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
                        self.socket.send("\x00\x00\x00\x00\x00\x00\x00\x00")
                        command = self.socket.recv_withlen()
                        steamtime = steam.unixtime_to_steamtime(time.time())
                        tgt_command = "\x04" #BLOCKED
                        padding = "\x00" * 1222
                        ticket_full = tgt_command + steamtime + padding
                        self.socket.send(ticket_full)
                    else :
                        personalsalt = userblob['\x05\x00\x00\x00'][username]['\x02\x00\x00\x00']
                        print(personalsalt)
                        self.socket.send(personalsalt) #NEW SALT PER USER
                        command = self.socket.recv_withlen()
                        key = userblob['\x05\x00\x00\x00'][username]['\x01\x00\x00\x00'][0:16]
                        #print(binascii.b2a_hex(key))
                        IV = command[0:16]
                        #print(binascii.b2a_hex(IV))
                        encrypted = command[20:36]
                        #print(binascii.b2a_hex(encrypted))
                        decodedmessage = binascii.b2a_hex(steam.aes_decrypt(key, IV, encrypted))
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
                        blob = steam.blob_serialize(execdict_new)
                        bloblen = len(blob)
                        log.debug("Blob length: " + str(bloblen))
                        innerkey = binascii.a2b_hex("10231230211281239191238542314233")
                        innerIV  = binascii.a2b_hex("12899c8312213a123321321321543344")
                        blob_encrypted = steam.aes_encrypt(innerkey, innerIV, blob)
                        blob_encrypted = struct.pack("<L", bloblen) + innerIV + blob_encrypted
                        blob_signature = steam.sign_message(innerkey, blob_encrypted)
                        blob_encrypted_len = 10 + len(blob_encrypted) + 20
                        blob_encrypted = struct.pack(">L", blob_encrypted_len) + "\x01\x45" + struct.pack("<LL", blob_encrypted_len, 0) + blob_encrypted + blob_signature
                        currtime = time.time()
                        outerIV = binascii.a2b_hex("92183129534234231231312123123353")
                        steamid = binascii.a2b_hex("0000" + "80808000" + "00000000")
                        servers = binascii.a2b_hex("451ca0939a69451ca0949a69")
                        times = steam.unixtime_to_steamtime(currtime) + steam.unixtime_to_steamtime(currtime + (60*60*24*28))
                        subheader = innerkey + steamid + servers + times
                        subheader_encrypted = steam.aes_encrypt(key, outerIV, subheader)
                        #if self.config["tgt_version"] == "1" :
                        if globalvars.tgt_version == "1" :
                            subheader_encrypted = "\x00\x01" + outerIV + "\x00\x36\x00\x40" + subheader_encrypted
                            log.debug(clientid + "TGT Version: 1") #v2 Steam
                        #elif self.config["tgt_version"] == "2" :
                        elif globalvars.tgt_version == "2" :
                            subheader_encrypted = "\x00\x02" + outerIV + "\x00\x36\x00\x40" + subheader_encrypted
                            log.debug(clientid + "TGT Version: 2") #v3 Steam
                        else :
                            subheader_encrypted = "\x00\x02" + outerIV + "\x00\x36\x00\x40" + subheader_encrypted
                            log.debug(clientid + "TGT Version: 2")
                        unknown_part = "\x01\x68" + ("\xff" * 0x168)
                        ticket = subheader_encrypted + unknown_part + blob_encrypted
                        ticket_signed = ticket + steam.sign_message(innerkey, ticket)
                        if wrongpass == "1" :
                            tgt_command = "\x02" # Incorrect password
                        else :
                            tgt_command = "\x00" # AuthenticateAndRequestTGT command
                    
                        steamtime = steam.unixtime_to_steamtime(time.time())
                        ticket_full = tgt_command + steamtime + "\x00\xd2\x49\x6b\x00\x00\x00\x00" + struct.pack(">L", len(ticket_signed)) + ticket_signed
                        self.socket.send(ticket_full)
                elif legacyblocked == 1 :
                    log.warning(clientid + "Blocked legacy user: " + username)
                    self.socket.send("\x00\x00\x00\x00\x00\x00\x00\x00")
                    steamtime = steam.unixtime_to_steamtime(time.time())
                    tgt_command = "\x04" #BLOCKED
                    padding = "\x00" * 1222
                    ticket_full = tgt_command + steamtime + padding
                    self.socket.send(ticket_full)
                elif legacyuser == 1 :
                    log.warning("Legacy user: " + username)
                
                    self.socket.send("\x01\x23\x45\x67\x89\xab\xcd\xef") # salt - OLD
                    command = self.socket.recv_withlen()

                    key = SHA.new("\x01\x23\x45\x67" + users[username] + "\x89\xab\xcd\xef").digest()[:16]
                    #print(binascii.b2a_hex(key))
                    IV = command[0:16]
                    #print(binascii.b2a_hex(IV))
                    encrypted = command[20:36]
                    #print(binascii.b2a_hex(encrypted))
                    decodedmessage = binascii.b2a_hex(steam.aes_decrypt(key, IV, encrypted))
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
                    #blob = steam.blob_serialize(execdict["user_registry"])
                    secretkey = {'\x05\x00\x00\x00'}
                    def without_keys(d, keys) :
                        return {x: d[x] for x in d if x not in keys}
                    execdict_new = without_keys(execdict, secretkey)
                    blob = steam.blob_serialize(execdict_new)
                    bloblen = len(blob)
                    log.debug("Blob length: " + str(bloblen))
                    innerkey = binascii.a2b_hex("10231230211281239191238542314233")
                    innerIV  = binascii.a2b_hex("12899c8312213a123321321321543344")
                    blob_encrypted = steam.aes_encrypt(innerkey, innerIV, blob)
                    blob_encrypted = struct.pack("<L", bloblen) + innerIV + blob_encrypted
                    blob_signature = steam.sign_message(innerkey, blob_encrypted)
                    blob_encrypted_len = 10 + len(blob_encrypted) + 20
                    blob_encrypted = struct.pack(">L", blob_encrypted_len) + "\x01\x45" + struct.pack("<LL", blob_encrypted_len, 0) + blob_encrypted + blob_signature
                    currtime = time.time()
                    outerIV = binascii.a2b_hex("92183129534234231231312123123353")
                    steamid = binascii.a2b_hex("0000" + "80808000" + "00000000")
                    servers = binascii.a2b_hex("451ca0939a69451ca0949a69")
                    times = steam.unixtime_to_steamtime(currtime) + steam.unixtime_to_steamtime(currtime + (60*60*24*28))
                    subheader = innerkey + steamid + servers + times
                    subheader_encrypted = steam.aes_encrypt(key, outerIV, subheader)
                    #if self.config["tgt_version"] == "1" :
                    if globalvars.tgt_version == "1" :
                        subheader_encrypted = "\x00\x01" + outerIV + "\x00\x36\x00\x40" + subheader_encrypted
                        log.debug(clientid + "TGT Version: 1") #v2 Steam
                    #elif self.config["tgt_version"] == "2" :
                    elif globalvars.tgt_version == "2" :
                        subheader_encrypted = "\x00\x02" + outerIV + "\x00\x36\x00\x40" + subheader_encrypted
                        log.debug(clientid + "TGT Version: 2") #v3 Steam
                    else :
                        subheader_encrypted = "\x00\x02" + outerIV + "\x00\x36\x00\x40" + subheader_encrypted
                        log.debug(clientid + "TGT Version: 2")
                    unknown_part = "\x01\x68" + ("\xff" * 0x168)
                    ticket = subheader_encrypted + unknown_part + blob_encrypted
                    ticket_signed = ticket + steam.sign_message(innerkey, ticket)
                    if wrongpass == "1" :
                        tgt_command = "\x02"
                    else :
                        tgt_command = "\x00" # AuthenticateAndRequestTGT command
                    
                    steamtime = steam.unixtime_to_steamtime(time.time())
                    ticket_full = tgt_command + steamtime + "\x00\xd2\x49\x6b\x00\x00\x00\x00" + struct.pack(">L", len(ticket_signed)) + ticket_signed
                    self.socket.send(ticket_full)
                else :
                    log.info(clientid + "Unknown user: " + username)
                    self.socket.send("\x00\x00\x00\x00\x00\x00\x00\x00")
                    steamtime = steam.unixtime_to_steamtime(time.time())
                    tgt_command = "\x01"
                    padding = "\x00" * 1222
                    ticket_full = tgt_command + steamtime + padding
                    self.socket.send(ticket_full)

            elif len(command) >= 256 :
                #print(binascii.b2a_hex(command[0:3]))
                if binascii.b2a_hex(command[0:3]) == "100168" :
                    log.info(clientid + "Change password")
                    self.socket.send("\x00")
                else :
                    log.info(clientid + "Ticket login")
                    self.socket.send("\x01")
            elif len(command) == 1 :
                if command == "\x1d" :
                    log.info(clientid + "command: Check username")
                    #BERstring = binascii.a2b_hex("30819d300d06092a864886f70d010101050003818b0030818702818100") + binascii.a2b_hex("bf973e24beb372c12bea4494450afaee290987fedae8580057e4f15b93b46185b8daf2d952e24d6f9a23805819578693a846e0b8fcc43c23e1f2bf49e843aff4b8e9af6c5e2e7b9df44e29e3c1c93f166e25e42b8f9109be8ad03438845a3c1925504ecc090aabd49a0fc6783746ff4e9e090aa96f1c8009baf9162b66716059") + "\x02\x01\x11"
                    BERstring = binascii.a2b_hex("30819d300d06092a864886f70d010101050003818b0030818702818100") + binascii.a2b_hex(self.config["net_key_n"][2:]) + "\x02\x01\x11"
                    #BERstring = binascii.a2b_hex("30819d300d06092a864886f70d010101050003818b0030818702818100") + binascii.a2b_hex("9525173d72e87cbbcbdc86146587aebaa883ad448a6f814dd259bff97507c5e000cdc41eed27d81f476d56bd6b83a4dc186fa18002ab29717aba2441ef483af3970345618d4060392f63ae15d6838b2931c7951fc7e1a48d261301a88b0260336b8b54ab28554fb91b699cc1299ffe414bc9c1e86240aa9e16cae18b950f900f") + "\x02\x01\x11"
                    signature = steam.rsa_sign_message_1024(steam.main_key_sign, BERstring)
                    reply = struct.pack(">H", len(BERstring)) + BERstring + struct.pack(">H", len(signature)) + signature
                    self.socket.send(reply)

                    reply = self.socket.recv_withlen()
                
                    RSAdata = reply[2:130]
                    datalength = struct.unpack(">L", reply[130:134])[0]
                    cryptedblob_signature = reply[134:136]
                    cryptedblob_length = reply[136:140]
                    cryptedblob_slack = reply[140:144]
                    cryptedblob = reply[144:]
                
                    key = steam.get_aes_key(RSAdata, steam.network_key)
                    log.debug("Message verification:" + repr(steam.verify_message(key, cryptedblob)))
                    plaintext_length = struct.unpack("<L", cryptedblob[0:4])[0]
                    IV = cryptedblob[4:20]
                    ciphertext = cryptedblob[20:-20]
                    plaintext = steam.aes_decrypt(key, IV, ciphertext)
                    plaintext = plaintext[0:plaintext_length]
                    #print(plaintext)
                    plainblob = steam.blob_unserialize(plaintext)
                    #print(plainblob)
                    username = plainblob['\x01\x00\x00\x00']
                    username_str = username.rstrip('\x00')
                    #print(len(username_str))
                    if (os.path.isfile("files/users/" + username_str + ".py")) :
                        self.socket.send("\x01")#not working
                    else :
                        self.socket.send("\x00")
                elif command == "\x22" :
                    log.info(clientid + "command: Check email")
                    self.socket.send("\x00")
                elif command == "\x01" :
                    log.info(clientid + "command: Create user")
                    #BERstring = binascii.a2b_hex("30819d300d06092a864886f70d010101050003818b0030818702818100") + binascii.a2b_hex("bf973e24beb372c12bea4494450afaee290987fedae8580057e4f15b93b46185b8daf2d952e24d6f9a23805819578693a846e0b8fcc43c23e1f2bf49e843aff4b8e9af6c5e2e7b9df44e29e3c1c93f166e25e42b8f9109be8ad03438845a3c1925504ecc090aabd49a0fc6783746ff4e9e090aa96f1c8009baf9162b66716059") + "\x02\x01\x11"
                    BERstring = binascii.a2b_hex("30819d300d06092a864886f70d010101050003818b0030818702818100") + binascii.a2b_hex(self.config["net_key_n"][2:]) + "\x02\x01\x11"
                    #BERstring = binascii.a2b_hex("30819d300d06092a864886f70d010101050003818b0030818702818100") + binascii.a2b_hex("9525173d72e87cbbcbdc86146587aebaa883ad448a6f814dd259bff97507c5e000cdc41eed27d81f476d56bd6b83a4dc186fa18002ab29717aba2441ef483af3970345618d4060392f63ae15d6838b2931c7951fc7e1a48d261301a88b0260336b8b54ab28554fb91b699cc1299ffe414bc9c1e86240aa9e16cae18b950f900f") + "\x02\x01\x11"
                    signature = steam.rsa_sign_message_1024(steam.main_key_sign, BERstring)
                    reply = struct.pack(">H", len(BERstring)) + BERstring + struct.pack(">H", len(signature)) + signature
                    self.socket.send(reply)

                    reply = self.socket.recv_withlen()
                
                    RSAdata = reply[2:130]
                    datalength = struct.unpack(">L", reply[130:134])[0]
                    cryptedblob_signature = reply[134:136]
                    cryptedblob_length = reply[136:140]
                    cryptedblob_slack = reply[140:144]
                    cryptedblob = reply[144:]
                
                    key = steam.get_aes_key(RSAdata, steam.network_key)
                    log.debug("Message verification:" + repr(steam.verify_message(key, cryptedblob)))
                    plaintext_length = struct.unpack("<L", cryptedblob[0:4])[0]
                    IV = cryptedblob[4:20]
                    ciphertext = cryptedblob[20:-20]
                    plaintext = steam.aes_decrypt(key, IV, ciphertext)
                    plaintext = plaintext[0:plaintext_length]
                    #print(plaintext)
                    plainblob = steam.blob_unserialize(plaintext)
                    #print(plainblob)
                    
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
                    
                    self.socket.send("\x00")
                elif command == "\x0e" :
                    log.info(clientid + "command: Lost password - username check")
                    #BERstring = binascii.a2b_hex("30819d300d06092a864886f70d010101050003818b0030818702818100") + binascii.a2b_hex("bf973e24beb372c12bea4494450afaee290987fedae8580057e4f15b93b46185b8daf2d952e24d6f9a23805819578693a846e0b8fcc43c23e1f2bf49e843aff4b8e9af6c5e2e7b9df44e29e3c1c93f166e25e42b8f9109be8ad03438845a3c1925504ecc090aabd49a0fc6783746ff4e9e090aa96f1c8009baf9162b66716059") + "\x02\x01\x11"
                    BERstring = binascii.a2b_hex("30819d300d06092a864886f70d010101050003818b0030818702818100") + binascii.a2b_hex(self.config["net_key_n"][2:]) + "\x02\x01\x11"
                    signature = steam.rsa_sign_message_1024(steam.main_key_sign, BERstring)
                    reply = struct.pack(">H", len(BERstring)) + BERstring + struct.pack(">H", len(signature)) + signature
                    self.socket.send(reply)
                    reply = self.socket.recv_withlen()
                
                    RSAdata = reply[2:130]
                    datalength = struct.unpack(">L", reply[130:134])[0]
                    cryptedblob_signature = reply[134:136]
                    cryptedblob_length = reply[136:140]
                    cryptedblob_slack = reply[140:144]
                    cryptedblob = reply[144:]
                
                    key = steam.get_aes_key(RSAdata, steam.network_key)
                    log.debug("Message verification:" + repr(steam.verify_message(key, cryptedblob)))
                    plaintext_length = struct.unpack("<L", cryptedblob[0:4])[0]
                    IV = cryptedblob[4:20]
                    ciphertext = cryptedblob[20:-20]
                    plaintext = steam.aes_decrypt(key, IV, ciphertext)
                    plaintext = plaintext[0:plaintext_length]
                    #print(plaintext)
                    blobdict = steam.blob_unserialize(plaintext)
                    usernamechk = blobdict['\x01\x00\x00\x00']
                    username_str = usernamechk.rstrip('\x00')
                    if os.path.isfile("files/users/" + username_str + ".py") :
                        self.socket.send("\x00")
                    else :
                        self.socket.send("\x01")
                elif command == "\x0f" :
                    log.info(clientid + "command: Lost password - reset")
                    #BERstring = binascii.a2b_hex("30819d300d06092a864886f70d010101050003818b0030818702818100") + binascii.a2b_hex("bf973e24beb372c12bea4494450afaee290987fedae8580057e4f15b93b46185b8daf2d952e24d6f9a23805819578693a846e0b8fcc43c23e1f2bf49e843aff4b8e9af6c5e2e7b9df44e29e3c1c93f166e25e42b8f9109be8ad03438845a3c1925504ecc090aabd49a0fc6783746ff4e9e090aa96f1c8009baf9162b66716059") + "\x02\x01\x11"
                    BERstring = binascii.a2b_hex("30819d300d06092a864886f70d010101050003818b0030818702818100") + binascii.a2b_hex(self.config["net_key_n"][2:]) + "\x02\x01\x11"
                    signature = steam.rsa_sign_message_1024(steam.main_key_sign, BERstring)
                    reply = struct.pack(">H", len(BERstring)) + BERstring + struct.pack(">H", len(signature)) + signature
                    self.socket.send(reply)
                    reply = self.socket.recv_withlen()
                
                    RSAdata = reply[2:130]
                    datalength = struct.unpack(">L", reply[130:134])[0]
                    cryptedblob_signature = reply[134:136]
                    cryptedblob_length = reply[136:140]
                    cryptedblob_slack = reply[140:144]
                    cryptedblob = reply[144:]
                
                    key = steam.get_aes_key(RSAdata, steam.network_key)
                    log.debug("Message verification:" + repr(steam.verify_message(key, cryptedblob)))
                    plaintext_length = struct.unpack("<L", cryptedblob[0:4])[0]
                    IV = cryptedblob[4:20]
                    ciphertext = cryptedblob[20:-20]
                    plaintext = steam.aes_decrypt(key, IV, ciphertext)
                    plaintext = plaintext[0:plaintext_length]
                    #print(plaintext)
                    blobdict = steam.blob_unserialize(plaintext)
                    #print(blobdict)
                    usernamechk = blobdict['\x01\x00\x00\x00']
                    username_str = usernamechk.rstrip('\x00')
                    with open("files/users/" + username_str + ".py", 'r') as userblobfile:
                        userblobstr = userblobfile.read()
                        userblob = ast.literal_eval(userblobstr[16:len(userblobstr)])
                    #print(userblob)
                    personalsalt = userblob['\x05\x00\x00\x00'][username_str]['\x02\x00\x00\x00']
                    #print(personalsalt)
                    self.socket.send(personalsalt) #NEW SALT PER USER
                    reply2 = self.socket.recv_withlen()
                
                    RSAdata = reply2[2:130]
                    datalength = struct.unpack(">L", reply2[130:134])[0]
                    cryptedblob_signature = reply2[134:136]
                    cryptedblob_length = reply2[136:140]
                    cryptedblob_slack = reply2[140:144]
                    cryptedblob = reply2[144:]
                
                    key = steam.get_aes_key(RSAdata, steam.network_key)
                    log.debug("Message verification:" + repr(steam.verify_message(key, cryptedblob)))
                    plaintext_length = struct.unpack("<L", cryptedblob[0:4])[0]
                    IV = cryptedblob[4:20]
                    ciphertext = cryptedblob[20:-20]
                    plaintext = steam.aes_decrypt(key, IV, ciphertext)
                    plaintext = plaintext[0:plaintext_length]
                    #print steam.blob_unserialize(plaintext)
                    
                    
                elif command == "\x20" :
                    log.info(clientid + "command: Lost password - email check")
                elif command == "\x21" :
                    log.info(clientid + "command: Lost password - product check")
                else :
                    # This is cheating. I've just cut'n'pasted the hex from the network_key. FIXME
                    #BERstring = binascii.a2b_hex("30819d300d06092a864886f70d010101050003818b0030818702818100") + binascii.a2b_hex("bf973e24beb372c12bea4494450afaee290987fedae8580057e4f15b93b46185b8daf2d952e24d6f9a23805819578693a846e0b8fcc43c23e1f2bf49e843aff4b8e9af6c5e2e7b9df44e29e3c1c93f166e25e42b8f9109be8ad03438845a3c1925504ecc090aabd49a0fc6783746ff4e9e090aa96f1c8009baf9162b66716059") + "\x02\x01\x11"
                    BERstring = binascii.a2b_hex("30819d300d06092a864886f70d010101050003818b0030818702818100") + binascii.a2b_hex(self.config["net_key_n"][2:]) + "\x02\x01\x11"
                    signature = steam.rsa_sign_message_1024(steam.main_key_sign, BERstring)
                    reply = struct.pack(">H", len(BERstring)) + BERstring + struct.pack(">H", len(signature)) + signature
                    self.socket.send(reply)

                    reply = self.socket.recv_withlen()
                
                    RSAdata = reply[2:130]
                    datalength = struct.unpack(">L", reply[130:134])[0]
                    cryptedblob_signature = reply[134:136]
                    cryptedblob_length = reply[136:140]
                    cryptedblob_slack = reply[140:144]
                    cryptedblob = reply[144:]
                
                    key = steam.get_aes_key(RSAdata, steam.network_key)
                    log.debug("Message verification:" + repr(steam.verify_message(key, cryptedblob)))
                    plaintext_length = struct.unpack("<L", cryptedblob[0:4])[0]
                    IV = cryptedblob[4:20]
                    ciphertext = cryptedblob[20:-20]
                    plaintext = steam.aes_decrypt(key, IV, ciphertext)
                    plaintext = plaintext[0:plaintext_length]
                    #print steam.blob_unserialize(plaintext)
                
                    self.socket.send("\x00")
            else :
                log.warning(clientid + "Invalid command length: " + str(len(command)))

        else :
            data = self.socket.recv(65535)
            log.warning(clientid + "Invalid command: " + binascii.b2a_hex(command[1:5]))
            log.warning(clientid + "Extra data:", binascii.b2a_hex(data))

        self.socket.close()
        log.info(clientid + "Disconnected from Auth Server")
