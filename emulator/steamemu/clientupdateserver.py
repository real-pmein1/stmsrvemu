import threading, logging, struct, binascii, os.path, zlib, os, socket, shutil, ast, ConfigParser, filecmp, requests, pprint, hmac, hashlib, io, time, ipcalc

from Crypto.Hash import SHA

import steam
import config
import globalvars
from Steam2.manifest import *
from Steam2.neuter import neuter
from Steam2.manifest2 import Manifest2
from Steam2.checksum2 import Checksum2
from Steam2.checksum3 import Checksum3
from gcf_to_storage import gcf2storage
from time import sleep

class clientupdateserver(threading.Thread):
    def __init__(self, (socket, address), config) :
        threading.Thread.__init__(self)
        self.socket = socket
        self.address = address
        self.config = config

    def run(self):
        log = logging.getLogger("clupdsrv")
        clientid = str(self.address) + ": "
        log.info(clientid + "Connected to Client Update Server")

        msg = self.socket.recv(4)

        if len(msg) == 0 :
            log.info(clientid + "Got simple handshake. Closing connection.")
            
        elif msg == "\x00\x00\x00\x00" : #2003 beta v2 client update
            log.info(clientid + "Package mode entered")
            self.socket.send("\x01")
            while True :
                msg = self.socket.recv_withlen()

                if not msg :
                    log.info(clientid + "no message received")
                    break

                command = struct.unpack(">L", msg[:4])[0]

                if command == 2 : #CELLID
                    self.socket.send("\x00\x00\x00\x01")
                    break

                elif command == 3 :
                    log.info(clientid + "Exiting package mode")
                    break

                elif command == 0 :
                    filename_len_byte = 0
                    for bytein in msg:
                        if bytein == "\x00":
                            filename_len_byte += 1
                        else:
                            break
                    command = struct.unpack(">L", msg[:4])[0]
                    filenamelength = struct.unpack(">B", msg[filename_len_byte:filename_len_byte + 1])
                    filename = msg[filename_len_byte + 1:filename_len_byte + 1 + filenamelength[0]]
                    #(dummy1, filenamelength) = struct.unpack(">LL", msg[4:12])
                    #filename = msg[12:12+filenamelength]
                    #dummy2 = struct.unpack(">L", msg[12+filenamelength:])[0]

                    if len(msg) != (filenamelength[0] + 16) :
                        log.warning(clientid + "There is extra data in the request")

                    log.info(clientid + filename)

                    if filename[-14:] == "_rsa_signature" :
                        newfilename = filename[:-14]
                        if self.config["public_ip"] != "0.0.0.0" :
                            try :
                                os.mkdir("files/cache/external")
                            except OSError as error :
                                log.debug(clientid + "External beta pkg dir already exists")
                            try :
                                os.mkdir("files/cache/external/betav2")
                            except OSError as error :
                                log.debug(clientid + "External beta pkg dir already exists")
                            
                            try :
                                os.mkdir("files/cache/internal")
                            except OSError as error :
                                log.debug(clientid + "Internal beta pkg dir already exists")
                            try :
                                os.mkdir("files/cache/internal/betav2")
                            except OSError as error :
                                log.debug(clientid + "Internal beta pkg dir already exists")
                            
                            if str(self.address[0]) in ipcalc.Network(str(globalvars.server_net)):
                                if not os.path.isfile("files/cache/internal/betav2/" + newfilename) :
                                    neuter(self.config["packagedir"] + "betav2/" + newfilename, "files/cache/internal/betav2/" + newfilename, self.config["server_ip"], self.config["dir_server_port"], "lan")
                                f = open('files/cache/internal/betav2/' + newfilename, 'rb')
                            else :
                                if not os.path.isfile("files/cache/external/betav2/" + newfilename) :
                                    neuter(self.config["packagedir"] + "betav2/" + newfilename, "files/cache/external/betav2/" + newfilename, self.config["public_ip"], self.config["dir_server_port"], "wan")
                                f = open('files/cache/external/betav2/' + newfilename, 'rb')
                        else :
                            try :
                                os.mkdir("files/cache/betav2")
                            except OSError as error :
                                log.debug(clientid + "Beta pkg dir already exists")
                            if not os.path.isfile("files/cache/betav2/" + newfilename) :
                                neuter(self.config["packagedir"] + "betav2/" + newfilename, "files/cache/betav2/" + newfilename, self.config["server_ip"], self.config["dir_server_port"], "lan")
                            f = open('files/cache/betav2/' + newfilename, 'rb')

                        file = f.read()
                        f.close()

                        signature = steam.rsa_sign_message(steam.network_key_sign, file)

                        reply = struct.pack('>LL', len(signature), len(signature)) + signature

                        self.socket.send(reply)

                    else :
                        if self.config["public_ip"] != "0.0.0.0" :
                            try :
                                os.mkdir("files/cache/external")
                            except OSError as error :
                                log.debug(clientid + "External pkg dir already exists")
                            try :
                                os.mkdir("files/cache/external/betav2")
                            except OSError as error :
                                log.debug(clientid + "External beta pkg dir already exists")
                            
                            try :
                                os.mkdir("files/cache/internal")
                            except OSError as error :
                                log.debug(clientid + "Internal pkg dir already exists")
                            try :
                                os.mkdir("files/cache/internal/betav2")
                            except OSError as error :
                                log.debug(clientid + "Internal beta pkg dir already exists")
                            
                            if str(self.address[0]) in ipcalc.Network(str(globalvars.server_net)):
                                if not os.path.isfile("files/cache/internal/betav2/" + filename) :
                                    neuter(self.config["packagedir"] + "betav2/" + filename, "files/cache/internal/betav2/" + filename, self.config["server_ip"], self.config["dir_server_port"], "lan")
                                f = open('files/cache/internal/betav2/' + filename, 'rb')
                            else :
                                if not os.path.isfile("files/cache/external/betav2/" + filename) :
                                    neuter(self.config["packagedir"] + "betav2/" + filename, "files/cache/external/betav2/" + filename, self.config["public_ip"], self.config["dir_server_port"], "wan")
                                f = open('files/cache/external/betav2/' + filename, 'rb')
                        else :
                            try :
                                os.mkdir("files/cache/betav2")
                            except OSError as error :
                                log.debug(clientid + "Beta pkg dir already exists")
                            if not os.path.isfile("files/cache/betav2/" + filename) :
                                neuter(self.config["packagedir"] + "betav2/" + filename, "files/cache/betav2/" + filename, self.config["server_ip"], self.config["dir_server_port"], "lan")
                            f = open('files/cache/betav2/' + filename, 'rb')
                            
                        file = f.read()
                        f.close()

                        reply = struct.pack('>LL', len(file), len(file))

                        self.socket.send( reply )
                        self.socket.send(file, False)
                        #self.socket.close()
                        #log.info(clientid + "Disconnected from File Server")
                        break

                else :
                    log.warning(clientid +"invalid Command")

        elif msg == "\x00\x00\x00\x02" or msg == "\x00\x00\x00\x03" : #release client update
            log.info(clientid + "Package mode entered")
            self.socket.send("\x01")
            while True :
                msg = self.socket.recv_withlen()

                if not msg :
                    log.info(clientid + "no message received")
                    break

                command = struct.unpack(">L", msg[:4])[0]

                if command == 2 : #CELLID
                    self.socket.send("\x00\x00\x00\x01")
                    break

                elif command == 3 :
                    log.info(clientid + "Exiting package mode")
                    break

                elif command == 0 :
                    filename_len_byte = 0
                    for bytein in msg:
                        if bytein == "\x00":
                            filename_len_byte += 1
                        else:
                            break
                    command = struct.unpack(">L", msg[:4])[0]
                    filenamelength = struct.unpack(">B", msg[filename_len_byte:filename_len_byte + 1])
                    filename = msg[filename_len_byte + 1:filename_len_byte + 1 + filenamelength[0]]
                    #(dummy1, filenamelength) = struct.unpack(">LL", msg[4:12])
                    #filename = msg[12:12+filenamelength]
                    #dummy2 = struct.unpack(">L", msg[12+filenamelength:])[0]

                    if len(msg) != (filenamelength[0] + 16) :
                        log.warning(clientid + "There is extra data in the request")

                    log.info(clientid + filename)

                    if filename[-14:] == "_rsa_signature" :
                        newfilename = filename[:-14]
                        if self.config["public_ip"] != "0.0.0.0" :
                            try :
                                os.mkdir("files/cache/external")
                            except OSError as error :
                                log.debug(clientid + "External pkg dir already exists")
                            
                            try :
                                os.mkdir("files/cache/internal")
                            except OSError as error :
                                log.debug(clientid + "Internal pkg dir already exists")
                            
                            if str(self.address[0]) in ipcalc.Network(str(globalvars.server_net)):
                                if not os.path.isfile("files/cache/internal/" + newfilename) :
                                    neuter(self.config["packagedir"] + newfilename, "files/cache/internal/" + newfilename, self.config["server_ip"], self.config["dir_server_port"], "lan")
                                f = open('files/cache/internal/' + newfilename, 'rb')
                            else :
                                if not os.path.isfile("files/cache/external/" + newfilename) :
                                    neuter(self.config["packagedir"] + newfilename, "files/cache/external/" + newfilename, self.config["public_ip"], self.config["dir_server_port"], "wan")
                                f = open('files/cache/external/' + newfilename, 'rb')
                        else :
                            if not os.path.isfile("files/cache/" + newfilename) :
                                neuter(self.config["packagedir"] + newfilename, "files/cache/" + newfilename, self.config["server_ip"], self.config["dir_server_port"], "lan")
                            f = open('files/cache/' + newfilename, 'rb')

                        file = f.read()
                        f.close()

                        signature = steam.rsa_sign_message(steam.network_key_sign, file)

                        reply = struct.pack('>LL', len(signature), len(signature)) + signature

                        self.socket.send(reply)

                    else :
                        if self.config["public_ip"] != "0.0.0.0" :
                            try :
                                os.mkdir("files/cache/external")
                            except OSError as error :
                                log.debug(clientid + "External pkg dir already exists")
                            
                            try :
                                os.mkdir("files/cache/internal")
                            except OSError as error :
                                log.debug(clientid + "Internal pkg dir already exists")
                            
                            if str(self.address[0]) in ipcalc.Network(str(globalvars.server_net)):
                                if not os.path.isfile("files/cache/internal/" + filename) :
                                    neuter(self.config["packagedir"] + filename, "files/cache/internal/" + filename, self.config["server_ip"], self.config["dir_server_port"], "lan")
                                f = open('files/cache/internal/' + filename, 'rb')
                            else :
                                if not os.path.isfile("files/cache/external/" + filename) :
                                    neuter(self.config["packagedir"] + filename, "files/cache/external/" + filename, self.config["public_ip"], self.config["dir_server_port"], "wan")
                                f = open('files/cache/external/' + filename, 'rb')
                        else :
                            if not os.path.isfile("files/cache/" + filename) :
                                neuter(self.config["packagedir"] + filename, "files/cache/" + filename, self.config["server_ip"], self.config["dir_server_port"], "lan")
                            f = open('files/cache/' + filename, 'rb')
                            
                        file = f.read()
                        f.close()

                        reply = struct.pack('>LL', len(file), len(file))

                        self.socket.send( reply )
                        #self.socket.send(file, False)
                    
                        for i in range(0, len(file), 0x500):
                            chunk = file[i:i+0x500]
                            self.socket.send(chunk, False)

                else :
                    log.warning(clientid + "Invalid Command: " + str(command))
        
        elif msg == "\x00\x00\x00\x07": #cdr download
            log.info(clientid + "CDDB mode entered")
            self.socket.send("\x01")
            while True :
                msg = self.socket.recv_withlen()

                if not msg :
                    log.info(clientid + "no message received")
                    break
                   
                if len(msg) == 10:
                    self.socket.send("\x01")
                    break

                command = struct.unpack(">B", msg[:1])[0]
                
                if command == 2 : #SEND CDR
                    log.debug(clientid + "Requesting CDR")
                    if os.path.isfile("files/cache/secondblob.bin") :
                        with open("files/cache/secondblob.bin", "rb") as f:
                            blob = f.read()
                    elif os.path.isfile("files/2ndcdr.py") or os.path.isfile("files/secondblob.py"):
                        log.info("Converting python CDR to cache...")
                        if os.path.isfile("files/2ndcdr.orig") :
                            #shutil.copy2("files/2ndcdr.py","files/2ndcdr.orig")
                            os.remove("files/2ndcdr.py")
                            shutil.copy2("files/2ndcdr.orig","files/secondblob.py")
                            os.remove("files/2ndcdr.orig")
                        if os.path.isfile("files/2ndcdr.py"):
                            shutil.copy2("files/2ndcdr.py","files/secondblob.py")
                            os.remove("files/2ndcdr.py")
                        with open("files/secondblob.py", "r") as g:
                            file = g.read()
                        
                        for (search, replace, info) in globalvars.replacestringsCDR :
                            print(search)
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
                        #h = open("files/2ndcdr.py", "w")
                        #h.write(file)
                        #h.close()
                        
                        execdict = {}
                        execdict_temp_01 = {}
                        execdict_temp_02 = {}
                        #execfile("files/2ndcdr.py", execdict)
                        exec(file, execdict)
                    
                        for sub_id_main in execdict["blob"]["\x02\x00\x00\x00"]:
                            #if "\x16\x00\x00\x00" in execdict["blob"]["\x02\x00\x00\x00"][sub_id_main]:
                            #    execdict["blob"]["\x02\x00\x00\x00"][sub_id_main]["\x16\x00\x00\x00"] = "\x00"
                                
                            if "\x17\x00\x00\x00" in execdict["blob"]["\x02\x00\x00\x00"][sub_id_main]:
                                sub_key = execdict["blob"]["\x02\x00\x00\x00"][sub_id_main]["\x17\x00\x00\x00"]
                                #print(sub_key)
                                if "AllowPurchaseFromRestrictedCountries" in sub_key:
                                    sub_key.pop("AllowPurchaseFromRestrictedCountries")
                                    #print(sub_key)
                                if "PurchaseRestrictedCountries" in sub_key:
                                    sub_key.pop("PurchaseRestrictedCountries")
                                    #print(sub_key)
                                if "RestrictedCountries" in sub_key:
                                    sub_key.pop("RestrictedCountries")
                                    #print(sub_key)
                                if "OnlyAllowRestrictedCountries" in sub_key:
                                    sub_key.pop("OnlyAllowRestrictedCountries")
                                    #print(sub_key)
                                if "onlyallowrunincountries" in sub_key:
                                    sub_key.pop("onlyallowrunincountries")
                                    print(sub_key)
                                if len(sub_key) == 0:
                                    execdict["blob"]["\x02\x00\x00\x00"][sub_id_main].pop("\x17\x00\x00\x00")
                        
                        for file in os.walk("files/custom"):
                            for pyblobfile in file[2]:
                                if (pyblobfile.endswith(".py") or pyblobfile.endswith(".bin")) and not pyblobfile == "2ndcdr.py" and not pyblobfile == "1stcdr.py" and not pyblobfile.startswith("firstblob") and not pyblobfile.startswith("secondblob"):
                                    #if os.path.isfile("files/extrablob.py") :
                                    log.info(clientid + "Found extra blob: " + pyblobfile)
                                    execdict_update = {}
                                    
                                    if pyblobfile.endswith(".bin"):
                                        f = open("files/custom/" + pyblobfile, "rb")
                                        blob = f.read()
                                        f.close()
                                        
                                        if blob[0:2] == "\x01\x43":
                                            blob = zlib.decompress(blob[20:])
                                        blob2 = steam.blob_unserialize(blob)
                                        blob3 = steam.blob_dump(blob2)
                                        execdict_update = "blob = " + blob3
                        
                                    elif pyblobfile.endswith(".py"):
                                        with open("files/custom/" + pyblobfile, 'r') as m :
                                            userblobstr_upd = m.read()
                                        execdict_update = ast.literal_eval(userblobstr_upd[7:len(userblobstr_upd)])
                                        
                                    for k in execdict_update :
                                        for j in execdict["blob"] :
                                            if j == k :
                                                execdict["blob"][j].update(execdict_update[k])
                                            else :
                                                if k == "\x01\x00\x00\x00" :
                                                    execdict_temp_01.update(execdict_update[k])
                                                elif k == "\x02\x00\x00\x00" :
                                                    execdict_temp_02.update(execdict_update[k])

                                    for k,v in execdict_temp_01.items() :
                                        execdict["blob"].pop(k,v)

                                    for k,v in execdict_temp_02.items() :
                                        execdict["blob"].pop(k,v)
                                
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
                        
                        #cache_option = self.config["use_cached_blob"]
                        #if cache_option == "true" :
                        f = open("files/cache/secondblob.bin", "wb")
                        f.write(blob)
                        f.close()
                        
                    else :
                        log.info("Converting binary CDR to cache...")
                        globalvars.compiling_cdr = True
                        if os.path.isfile("files/secondblob.orig") :
                            os.remove("files/secondblob.bin")
                            shutil.copy2("files/secondblob.orig","files/secondblob.bin")
                            os.remove("files/secondblob.orig")
                        with open("files/secondblob.bin", "rb") as g:
                            blob = g.read()
                        
                        if blob[0:2] == "\x01\x43":
                            blob = zlib.decompress(blob[20:])
                            log.warn("The first client waiting for this CDR might appear to have crashed")
                        blob2 = steam.blob_unserialize(blob)
                        #blob3 = steam.blob_dump(blob2)
                        blob3 = pprint.saferepr(blob2) #1/5th of the time compared with using blob_dump
                        file = "blob = " + blob3
                        
                        for (search, replace, info) in globalvars.replacestringsCDR :
                            #print "Fixing CDR"
                            fulllength = len(search)
                            newlength = len(replace)
                            missinglength = fulllength - newlength
                            if missinglength < 0 :
                                #print "WARNING: Replacement text " + replace + " is too long! Not replaced!"
                                dummy = 1
                            else :
                                file = file.replace(search, replace)
                                #print("Replaced " + info + " " + search + " with " + replace)
                        
                        execdict = {}
                        execdict_temp_01 = {}
                        execdict_temp_02 = {}
                        exec(file, execdict)
                    
                        for sub_id_main in execdict["blob"]["\x02\x00\x00\x00"]:
                            #if "\x16\x00\x00\x00" in execdict["blob"]["\x02\x00\x00\x00"][sub_id_main]:
                            #    execdict["blob"]["\x02\x00\x00\x00"][sub_id_main]["\x16\x00\x00\x00"] = "\x00"
                                
                            if "\x17\x00\x00\x00" in execdict["blob"]["\x02\x00\x00\x00"][sub_id_main]:
                                sub_key = execdict["blob"]["\x02\x00\x00\x00"][sub_id_main]["\x17\x00\x00\x00"]
                                #print(sub_key)
                                if "AllowPurchaseFromRestrictedCountries" in sub_key:
                                    sub_key.pop("AllowPurchaseFromRestrictedCountries")
                                    #print(sub_key)
                                if "PurchaseRestrictedCountries" in sub_key:
                                    sub_key.pop("PurchaseRestrictedCountries")
                                    #print(sub_key)
                                if "RestrictedCountries" in sub_key:
                                    sub_key.pop("RestrictedCountries")
                                    #print(sub_key)
                                if "OnlyAllowRestrictedCountries" in sub_key:
                                    sub_key.pop("OnlyAllowRestrictedCountries")
                                    #print(sub_key)
                                if "onlyallowrunincountries" in sub_key:
                                    sub_key.pop("onlyallowrunincountries")
                                    print(sub_key)
                                if len(sub_key) == 0:
                                    execdict["blob"]["\x02\x00\x00\x00"][sub_id_main].pop("\x17\x00\x00\x00")
                                    
                        BERstring = binascii.a2b_hex("30819d300d06092a864886f70d010101050003818b0030818702818100") + binascii.a2b_hex(self.config["net_key_n"][2:]) + "\x02\x01\x11"
                        for sig in execdict["blob"]["\x05\x00\x00\x00"]: #replaces the old signature search, completes in less than 1 second now
                            value = execdict["blob"]["\x05\x00\x00\x00"][sig]
                            #print(value)
                            if len(value) == 160 and value.startswith(binascii.a2b_hex("30819d300d06092a")):
                                execdict["blob"]["\x05\x00\x00\x00"][sig] = BERstring
                                
                        for file in os.walk("files/custom"):
                            for pyblobfile in file[2]:
                                if (pyblobfile.endswith(".py") or pyblobfile.endswith(".bin")) and not pyblobfile == "2ndcdr.py" and not pyblobfile == "1stcdr.py" and not pyblobfile.startswith("firstblob") and not pyblobfile.startswith("secondblob"):
                                    #if os.path.isfile("files/extrablob.py") :
                                    log.info(clientid + "Found extra blob: " + pyblobfile)
                                    execdict_update = {}
                                    
                                    if pyblobfile.endswith(".bin"):
                                        f = open("files/custom/" + pyblobfile, "rb")
                                        blob = f.read()
                                        f.close()
                                        
                                        if blob[0:2] == "\x01\x43":
                                            blob = zlib.decompress(blob[20:])
                                        blob2 = steam.blob_unserialize(blob)
                                        blob3 = steam.blob_dump(blob2)
                                        execdict_update = "blob = " + blob3
                    
                                        for (search, replace, info) in globalvars.replacestringsCDR :
                                            print "Fixing CDR 27"
                                            fulllength = len(search)
                                            newlength = len(replace)
                                            missinglength = fulllength - newlength
                                            if missinglength < 0 :
                                                print "WARNING: Replacement text " + replace + " is too long! Not replaced!"
                                            else :
                                                execdict_update = execdict_update.replace(search, replace)
                                                print("Replaced " + info + " " + search + " with " + replace)
                    
                                    elif pyblobfile.endswith(".py"):
                                        with open("files/custom/" + pyblobfile, 'r') as m :
                                            userblobstr_upd = m.read()
                        
                                        for (search, replace, info) in globalvars.replacestringsCDR :
                                            print "Fixing CDR 28"
                                            fulllength = len(search)
                                            newlength = len(replace)
                                            missinglength = fulllength - newlength
                                            if missinglength < 0 :
                                                print "WARNING: Replacement text " + replace + " is too long! Not replaced!"
                                            else :
                                                userblobstr_upd = userblobstr_upd.replace(search, replace)
                                                print("Replaced " + info + " " + search + " with " + replace)
                                            
                                        execdict_update = ast.literal_eval(userblobstr_upd[7:len(userblobstr_upd)])
                                        
                                    for k in execdict_update :
                                        for j in execdict["blob"] :
                                            if j == k :
                                                execdict["blob"][j].update(execdict_update[k])
                                            else :
                                                if k == "\x01\x00\x00\x00" :
                                                    execdict_temp_01.update(execdict_update[k])
                                                elif k == "\x02\x00\x00\x00" :
                                                    execdict_temp_02.update(execdict_update[k])

                                    for k,v in execdict_temp_01.items() :
                                        execdict["blob"].pop(k,v)

                                    for k,v in execdict_temp_02.items() :
                                        execdict["blob"].pop(k,v)
                                
                        blob = steam.blob_serialize(execdict["blob"])
                        
                        #h = open("files/secondblob.bin", "wb")
                        #h.write(blob)
                        #h.close()
                        
                        #g = open("files/secondblob.bin", "rb")
                        #blob = g.read()
                        #g.close()
                        
                        if blob[0:2] == "\x01\x43" :
                            blob = zlib.decompress(blob[20:])
                            
                        #start_search = 0
                        #while True :
                        #    found = blob.find("\x30\x81\x9d\x30\x0d\x06\x09\x2a", start_search)
                        #    if found < 0 :
                        #        break
                        
                        #    # TINserver's Net Key
                        #    #BERstring = binascii.a2b_hex("30819d300d06092a864886f70d010101050003818b0030818702818100") + binascii.a2b_hex("9525173d72e87cbbcbdc86146587aebaa883ad448a6f814dd259bff97507c5e000cdc41eed27d81f476d56bd6b83a4dc186fa18002ab29717aba2441ef483af3970345618d4060392f63ae15d6838b2931c7951fc7e1a48d261301a88b0260336b8b54ab28554fb91b699cc1299ffe414bc9c1e86240aa9e16cae18b950f900f") + "\x02\x01\x11"

                            
                        #    #BERstring = binascii.a2b_hex("30819d300d06092a864886f70d010101050003818b0030818702818100") + binascii.a2b_hex("bf973e24beb372c12bea4494450afaee290987fedae8580057e4f15b93b46185b8daf2d952e24d6f9a23805819578693a846e0b8fcc43c23e1f2bf49e843aff4b8e9af6c5e2e7b9df44e29e3c1c93f166e25e42b8f9109be8ad03438845a3c1925504ecc090aabd49a0fc6783746ff4e9e090aa96f1c8009baf9162b66716059") + "\x02\x01\x11"
                        #    BERstring = binascii.a2b_hex("30819d300d06092a864886f70d010101050003818b0030818702818100") + binascii.a2b_hex(self.config["net_key_n"][2:]) + "\x02\x01\x11"
                        #    foundstring = blob[found:found + 160]
                        #    blob = blob.replace(foundstring, BERstring)
                        #    start_search = found + 160

                        compressed_blob = zlib.compress(blob, 9)
                        blob = "\x01\x43" + struct.pack("<QQH", len(compressed_blob) + 20, len(blob), 9) + compressed_blob
                        
                        #cache_option = self.config["use_cached_blob"]
                        #if cache_option == "true" :
                        f = open("files/cache/secondblob.bin", "wb")
                        f.write(blob)
                        f.close()

                    checksum = SHA.new(blob).digest()

                    if checksum == msg[1:] :
                        log.info(clientid + "Client has matching checksum for secondblob")
                        log.debug(clientid + "We validate it: " + binascii.b2a_hex(msg[1:]))

                        self.socket.send("\x00\x00\x00\x00")

                    else :
                        log.info(clientid + "Client didn't match our checksum for secondblob")
                        log.debug(clientid + "Sending new blob: " + binascii.b2a_hex(msg[1:]))

                        self.socket.send_withlen(blob, False)
                    globalvars.compiling_cdr = False
                
                else :
                    log.warn(clientid + "Unknown command: " + str(msg[:1]))
        else :
            log.warning("Invalid Command: " + binascii.b2a_hex(msg))

        self.socket.close()
        log.info(clientid + "Disconnected from Client Update Server")
                    