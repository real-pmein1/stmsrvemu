import threading, logging, struct, binascii, socket, zlib, os, shutil

from Crypto.Hash import SHA

import steam
import config
import globalvars

class configserver(threading.Thread):
    def __init__(self, (socket, address), config) :
        threading.Thread.__init__(self)
        self.socket = socket
        self.address = address
        self.config = config

    def run(self):
        log = logging.getLogger("confsrv")

        clientid = str(self.address) + ": "

        log.info(clientid + "Connected to Config Server")

        command = self.socket.recv(4)

        if command == "\x00\x00\x00\x03" or command == "\x00\x00\x00\x02" :
            self.socket.send("\x01" + socket.inet_aton(self.address[0]))

            command = self.socket.recv_withlen()

            if len(command) == 1 :

                if command == "\x01" :
                    log.info(clientid + "sending first blob")

                    if os.path.isfile("files/1stcdr.py") :
                        f = open("files/1stcdr.py", "r")
                        firstblob = f.read()
                        f.close()
                        execdict = {}
                        execfile("files/1stcdr.py", execdict)
                        blob = steam.blob_serialize(execdict["blob"])
                    else :
                        f = open("files/firstblob.bin", "rb")
                        blob = f.read()
                        f.close()
                        firstblob_bin = blob
                        if firstblob_bin[0:2] == "\x01\x43":
                            firstblob_bin = zlib.decompress(firstblob_bin[20:])
                        firstblob_unser = steam.blob_unserialize(firstblob_bin)
                        firstblob = steam.blob_dump(firstblob_unser)
                        
                    firstblob_list = firstblob.split("\n")
                    steamui_hex = firstblob_list[3][25:41]
                    steamui_ver = int(steamui_hex[14:16] + steamui_hex[10:12] + steamui_hex[6:8] + steamui_hex[2:4], 16)
                    if steamui_ver < 61 : #guessing steamui version when steam client interface v2 changed to v3
                        globalvars.tgt_version = "1"
                        log.debug(clientid + "TGT version set to 1")
                    else :
                        globalvars.tgt_version = "2" #config file states 2 as default
                        log.debug(clientid + "TGT version set to 2")

                    self.socket.send_withlen(blob)

                elif command == "\x04" :
                    log.info(clientid + "sending network key")
                    
                    # TINserver's Net Key
                    #BERstring = binascii.a2b_hex("30819d300d06092a864886f70d010101050003818b0030818702818100") + binascii.a2b_hex("9525173d72e87cbbcbdc86146587aebaa883ad448a6f814dd259bff97507c5e000cdc41eed27d81f476d56bd6b83a4dc186fa18002ab29717aba2441ef483af3970345618d4060392f63ae15d6838b2931c7951fc7e1a48d261301a88b0260336b8b54ab28554fb91b699cc1299ffe414bc9c1e86240aa9e16cae18b950f900f") + "\x02\x01\x11"
                    
                    # This is cheating. I've just cut'n'pasted the hex from the network_key. FIXME
                    #BERstring = binascii.a2b_hex("30819d300d06092a864886f70d010101050003818b0030818702818100") + binascii.a2b_hex("bf973e24beb372c12bea4494450afaee290987fedae8580057e4f15b93b46185b8daf2d952e24d6f9a23805819578693a846e0b8fcc43c23e1f2bf49e843aff4b8e9af6c5e2e7b9df44e29e3c1c93f166e25e42b8f9109be8ad03438845a3c1925504ecc090aabd49a0fc6783746ff4e9e090aa96f1c8009baf9162b66716059") + "\x02\x01\x11"
                    BERstring = binascii.a2b_hex("30819d300d06092a864886f70d010101050003818b0030818702818100") + binascii.a2b_hex(self.config["net_key_n"][2:]) + "\x02\x01\x11"

                    signature = steam.rsa_sign_message_1024(steam.main_key_sign, BERstring)

                    reply = struct.pack(">H", len(BERstring)) + BERstring + struct.pack(">H", len(signature)) + signature

                    self.socket.send(reply)

                elif command == "\x05" :
                    log.info(clientid + "confserver command 5, unknown, sending zero reply")

                    self.socket.send("\x00")

                elif command == "\x06" :
                    log.info(clientid + "confserver command 6, unknown, sending zero reply")

                    self.socket.send("\x00")

                elif command == "\x07" :
                    log.info(clientid + "Sending out list of file servers")

                    #self.socket.send(binascii.a2b_hex("0001312d000000012c"))
        
                    if self.config["public_ip"] != "0.0.0.0" :
                        if clientid.startswith(globalvars.servernet) :
                            bin_ip = steam.encodeIP((self.config["server_ip"], self.config["file_server_port"]))
                        else :
                            bin_ip = steam.encodeIP((self.config["public_ip"], self.config["file_server_port"]))
                    else:
                        bin_ip = steam.encodeIP((self.config["server_ip"], self.config["file_server_port"]))
                    reply = struct.pack(">H", 1) + bin_ip
                    
                    self.socket.send_withlen(reply)

                elif command == "\x08" :
                    log.info(clientid + "confserver command 8, unknown, sending zero reply")

                    self.socket.send("\x00")

                else :
                    log.warning(clientid + "Invalid command: " + binascii.b2a_hex(command))

                    self.socket.send("\x00")

            elif command[0] == "\x02" or command[0] == "\x09":
            
                if command[0] == "\x09" :
                    self.socket.send(binascii.a2b_hex("00000001312d000000012c"))

                if os.path.isfile("files/cache/secondblob.bin") :
                    f = open("files/cache/secondblob.bin", "rb")
                    blob = f.read()
                    f.close()
                elif os.path.isfile("files/2ndcdr.py") :
                    if not os.path.isfile("files/2ndcdr.orig") :
                        shutil.copy2("files/2ndcdr.py","files/2ndcdr.orig")
                    g = open("files/2ndcdr.py", "r")
                    file = g.read()
                    g.close()
                    
                    for (search, replace, info) in globalvars.replacestringsCDR :
                        fulllength = len(search)
                        newlength = len(replace)
                        missinglength = fulllength - newlength
                        if missinglength < 0 :
                            print "WARNING: Replacement text " + replace + " is too long! Not replaced!"
                        else :
                            fileold = file
                            file = file.replace(search, replace)
                            if (search in fileold) and (replace in file) :
                                print("Replaced " + info + " " + search + " with " + replace)
                    h = open("files/2ndcdr.py", "w")
                    h.write(file)
                    h.close()
                    
                    execdict = {}
                    execfile("files/2ndcdr.py", execdict)
                    blob = steam.blob_serialize(execdict["blob"])
                    
                    if blob[0:2] == "\x01\x43" :
                        blob = zlib.decompress(blob[20:])
                        
                    start_search = 0
                    while True :
                        found = blob.find("\x30\x81\x9d\x30\x0d\x06\x09\x2a", start_search)
                        if found < 0 :
                            break
                    
                        # TINserver's Net Key
                        #BERstring = binascii.a2b_hex("30819d300d06092a864886f70d010101050003818b0030818702818100") + binascii.a2b_hex("9525173d72e87cbbcbdc86146587aebaa883ad448a6f814dd259bff97507c5e000cdc41eed27d81f476d56bd6b83a4dc186fa18002ab29717aba2441ef483af3970345618d4060392f63ae15d6838b2931c7951fc7e1a48d261301a88b0260336b8b54ab28554fb91b699cc1299ffe414bc9c1e86240aa9e16cae18b950f900f") + "\x02\x01\x11"

                        
                        #BERstring = binascii.a2b_hex("30819d300d06092a864886f70d010101050003818b0030818702818100") + binascii.a2b_hex("bf973e24beb372c12bea4494450afaee290987fedae8580057e4f15b93b46185b8daf2d952e24d6f9a23805819578693a846e0b8fcc43c23e1f2bf49e843aff4b8e9af6c5e2e7b9df44e29e3c1c93f166e25e42b8f9109be8ad03438845a3c1925504ecc090aabd49a0fc6783746ff4e9e090aa96f1c8009baf9162b66716059") + "\x02\x01\x11"
                        BERstring = binascii.a2b_hex("30819d300d06092a864886f70d010101050003818b0030818702818100") + binascii.a2b_hex(self.config["net_key_n"][2:]) + "\x02\x01\x11"
                        foundstring = blob[found:found + 160]
                        blob = blob.replace(foundstring, BERstring)
                        start_search = found + 160

                    compressed_blob = zlib.compress(blob, 9)
                    blob = "\x01\x43" + struct.pack("<QQH", len(compressed_blob) + 20, len(blob), 9) + compressed_blob
                    
                    cache_option = self.config["use_cached_blob"]
                    if cache_option == "true" :
                        f = open("files/cache/secondblob.bin", "wb")
                        f.write(blob)
                        f.close()
                    
                else :
                    if not os.path.isfile("files/secondblob.orig") :
                        shutil.copy2("files/secondblob.bin","files/secondblob.orig")
                    f = open("files/secondblob.bin", "rb")
                    blob = f.read()
                    f.close()
                    
                    if blob[0:2] == "\x01\x43":
                        blob = zlib.decompress(blob[20:])
                    blob2 = steam.blob_unserialize(blob)
                    blob3 = steam.blob_dump(blob2)
                    file = "blob = " + blob3
                    
                    for (search, replace, info) in globalvars.replacestringsCDR :
                        print "Fixing CDR"
                        fulllength = len(search)
                        newlength = len(replace)
                        missinglength = fulllength - newlength
                        if missinglength < 0 :
                            print "WARNING: Replacement text " + replace + " is too long! Not replaced!"
                        else :
                            file = file.replace(search, replace)
                            print("Replaced " + info + " " + search + " with " + replace)
                    
                    execdict = {}
                    exec(file, execdict)
                    blob = steam.blob_serialize(execdict["blob"])
                    
                    h = open("files/secondblob.bin", "wb")
                    h.write(blob)
                    h.close()
                    
                    g = open("files/secondblob.bin", "rb")
                    blob = g.read()
                    g.close()
                    
                    if blob[0:2] == "\x01\x43" :
                        blob = zlib.decompress(blob[20:])
                        
                    start_search = 0
                    while True :
                        found = blob.find("\x30\x81\x9d\x30\x0d\x06\x09\x2a", start_search)
                        if found < 0 :
                            break
                    
                        # TINserver's Net Key
                        #BERstring = binascii.a2b_hex("30819d300d06092a864886f70d010101050003818b0030818702818100") + binascii.a2b_hex("9525173d72e87cbbcbdc86146587aebaa883ad448a6f814dd259bff97507c5e000cdc41eed27d81f476d56bd6b83a4dc186fa18002ab29717aba2441ef483af3970345618d4060392f63ae15d6838b2931c7951fc7e1a48d261301a88b0260336b8b54ab28554fb91b699cc1299ffe414bc9c1e86240aa9e16cae18b950f900f") + "\x02\x01\x11"

                        
                        #BERstring = binascii.a2b_hex("30819d300d06092a864886f70d010101050003818b0030818702818100") + binascii.a2b_hex("bf973e24beb372c12bea4494450afaee290987fedae8580057e4f15b93b46185b8daf2d952e24d6f9a23805819578693a846e0b8fcc43c23e1f2bf49e843aff4b8e9af6c5e2e7b9df44e29e3c1c93f166e25e42b8f9109be8ad03438845a3c1925504ecc090aabd49a0fc6783746ff4e9e090aa96f1c8009baf9162b66716059") + "\x02\x01\x11"
                        BERstring = binascii.a2b_hex("30819d300d06092a864886f70d010101050003818b0030818702818100") + binascii.a2b_hex(self.config["net_key_n"][2:]) + "\x02\x01\x11"
                        foundstring = blob[found:found + 160]
                        blob = blob.replace(foundstring, BERstring)
                        start_search = found + 160

                    compressed_blob = zlib.compress(blob, 9)
                    blob = "\x01\x43" + struct.pack("<QQH", len(compressed_blob) + 20, len(blob), 9) + compressed_blob
                    
                    cache_option = self.config["use_cached_blob"]
                    if cache_option == "true" :
                        f = open("files/cache/secondblob.bin", "wb")
                        f.write(blob)
                        f.close()

                checksum = SHA.new(blob).digest()

                if checksum == command[1:] :
                    log.info(clientid + "Client has matching checksum for secondblob")
                    log.debug(clientid + "We validate it: " + binascii.b2a_hex(command))

                    self.socket.send("\x00\x00\x00\x00")

                else :
                    log.info(clientid + "Client didn't match our checksum for secondblob")
                    log.debug(clientid + "Sending new blob: " + binascii.b2a_hex(command))

                    self.socket.send_withlen(blob, False)

            else :
                log.info(clientid + "Invalid message: " + binascii.b2a_hex(command))

        else :
            log.info(clientid + "Invalid head message: " + binascii.b2a_hex(command))

        self.socket.close()

        log.info (clientid + "disconnected from Config Server")
