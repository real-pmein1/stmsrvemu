import threading, logging, struct, binascii, os.path, zlib, os, socket, shutil, ast, ConfigParser, filecmp, requests, pprint, hmac, hashlib, io, time, ipaddress, ipcalc, pickle

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

class fileserver(threading.Thread):
    def __init__(self, (socket, address), config) :
        threading.Thread.__init__(self)
        self.socket = socket
        self.address = address
        self.config = config

    def run(self):
        log = logging.getLogger("filesrv")
        clientid = str(self.address) + ": "
        log.info(clientid + "Connected to Content Server")

        msg = self.socket.recv(4)

        if len(msg) == 0 :
            log.info(clientid + "Got simple handshake. Closing connection.")
            
        elif msg == "\x00\x00\x00\x02" : #\x02 for 2003 beta v2 content
            log.info(clientid + "Storage mode entered")

            storagesopen = 0
            storages = {}

            self.socket.send("\x01") # this should just be the handshake

            while True :

                command = self.socket.recv_withlen()
                        
                if command[0] == "\x00" : #SEND MANIFEST AND PROCESS RESPONSE
                
                    (connid, messageid, app, version) = struct.unpack(">IIII", command[1:17])
                    #print(connid, messageid, app, version)
                    #print(app)
                    #print(version)
                
                    (app, version) = struct.unpack(">II", command[1:9])
                    log.debug(clientid + "appid: " + str(int(app)) + ", verid: " + str(int(version)))
                    
                    #bio = io.BytesIO(msg[9:])
                    
                    #ticketsize, = struct.unpack(">H", bio.read(2))
                    #ticket = bio.read(ticketsize)
                    
                    connid |= 0x80000000
                    key = "\x69" * 0x10
                    if steam.verify_message(key, command[9:]):
                        log.debug(clientid + repr(steam.verify_message(key, command[9:])))
                    #print(binascii.b2a_hex(signeddata))

                    #if hmac.new(key, signeddata[:-20], hashlib.sha1).digest() == signeddata[-20:]:
                    #    log.debug(clientid + "HMAC verified OK")
                    #else:
                    #    log.error(clientid + "BAD HMAC")
                    #    raise Exception("BAD HMAC")

                    #bio = io.BytesIO(msg[9:]) #NOT WORKING, UNKNOWN KEY
                    #print(bio)
                    #ticketsize, = struct.unpack(">H", bio.read(2))
                    #print(ticketsize)
                    #ticket = bio.read(ticketsize)
                    #print(binascii.b2a_hex(ticket))
                    #postticketdata = io.BytesIO(bio.read()[:-20])
                    #IV = postticketdata.read(16)
                    #print(len(IV))
                    #print(binascii.b2a_hex(IV))
                    #enclen = postticketdata.read(2)
                    #print(binascii.b2a_hex(enclen))
                    #print(struct.unpack(">H", enclen)[0])
                    #enctext = postticketdata.read(struct.unpack(">H", enclen)[0])
                    #print(binascii.b2a_hex(enctext))
                    #ptext = steam.aes_decrypt(key, IV, enctext)
                    #print(binascii.b2a_hex(ptext))
                    
                    log.info(clientid + "Opening application %d %d" % (app, version))
                    #connid = pow(2,31) + connid

                    try :
                        s = steam.Storage(app, self.config["storagedir"], version)
                    except Exception :
                        log.error("Application not installed! %d %d" % (app, version))

                        #reply = struct.pack(">LLc", connid, messageid, "\x01")
                        reply = struct.pack(">c", "\x00")
                        self.socket.send(reply)

                        break
                    storageid = storagesopen
                    storagesopen = storagesopen + 1

                    storages[storageid] = s
                    storages[storageid].app = app
                    storages[storageid].version = version
                    
                    if os.path.isfile(self.config["betamanifestdir"] + str(app) + "_" + str(version) + ".manifest") :
                        f = open(self.config["betamanifestdir"] + str(app) + "_" + str(version) + ".manifest", "rb")
                        log.info(clientid + str(app) + "_" + str(version) + " is a beta depot")
                    else :
                        log.error("Manifest not found for %s %s " % (app, version))
                        #reply = struct.pack(">LLc", connid, messageid, "\x01")
                        reply = struct.pack(">c", "\x00")
                        self.socket.send(reply)
                        break
                    manifest = f.read()
                    f.close()
                    
                    manifest_appid = struct.unpack('<L', manifest[4:8])[0]
                    manifest_verid = struct.unpack('<L', manifest[8:12])[0]
                    log.debug(clientid + ("Manifest ID: %s Version: %s" % (manifest_appid, manifest_verid)))
                    if (int(manifest_appid) != int(app)) or (int(manifest_verid) != int(version)) :
                        log.error("Manifest doesn't match requested file: (%s, %s) (%s, %s)" % (app, version, manifest_appid, manifest_verid))

                        #reply = struct.pack(">LLc", connid, messageid, "\x01")
                        reply = struct.pack(">c", "\x00")
                        self.socket.send(reply)

                        break
                    
                    globalvars.converting = "0"

                    fingerprint = manifest[0x30:0x34]
                    oldchecksum = manifest[0x34:0x38]
                    manifest = manifest[:0x30] + "\x00" * 8 + manifest[0x38:]
                    checksum = struct.pack("<i", zlib.adler32(manifest, 0))
                    manifest = manifest[:0x30] + fingerprint + checksum + manifest[0x38:]
                    
                    log.debug("Checksum fixed from " + binascii.b2a_hex(oldchecksum) + " to " + binascii.b2a_hex(checksum))
                    
                    storages[storageid].manifest = manifest

                    checksum = struct.unpack("<L", manifest[0x30:0x34])[0] # FIXED, possible bug source

                    #reply = struct.pack(">LLcLL", connid, messageid, "\x00", storageid, checksum)
                    reply = "\xff" + fingerprint[::-1]

                    self.socket.send(reply, False)
                    
                    index_file = self.config["betastoragedir"] + str(app) + "_" + str(version) + ".index"
                    dat_file = self.config["betastoragedir"] + str(app) + "_" + str(version) + ".dat"
                    # Load the index
                    with open(index_file, 'rb') as f:
                        index_data = pickle.load(f)
                    try:
                        dat_file_handle.close()
                    except:
                        a = 1 #dummy error
                    dat_file_handle = open(dat_file, 'rb')
                    
                    while True:
                        command = self.socket.recv(1)
                
                        if len(command) == 0:
                            log.info(clientid + "Disconnected from Content Server")
                            self.socket.close()
                            return

                        if command[0] == "\x02" : #SEND MANIFEST AGAIN

                            log.info(clientid + "Sending manifest")

                            #(storageid, messageid) = struct.unpack(">xLL", command)

                            #manifest = storages[storageid].manifest

                            #reply = struct.pack(">LLcL", storageid, messageid, "\x00", len(manifest))
                            #reply = struct.pack(">cL", "\x00", len(manifest))
                            #print(binascii.b2a_hex(reply))

                            #self.socket.send(reply)

                            #reply = struct.pack(">LLL", storageid, messageid, len(manifest))
                            reply = struct.pack(">L", len(manifest))
                            #print(binascii.b2a_hex(reply))
                            
                            #print(binascii.b2a_hex(manifest))

                            self.socket.send("\x01" + reply + manifest, False)

                        elif command[0] == "\x01" : #HANDSHAKE

                            self.socket.send("")
                            break

                        elif command[0] == "\x03" : #CLOSE STORAGE

                            (storageid, messageid) = struct.unpack(">xLL", command)

                            del storages[storageid]

                            reply = struct.pack(">LLc", storageid, messageid, "\x00")

                            log.info(clientid + "Closing down storage %d" % storageid)

                            self.socket.send(reply)

                        elif command[0] == "\x04" : #SEND MANIFEST

                            log.info(clientid + "Sending manifest")

                            #(storageid, messageid) = struct.unpack(">xLL", command)

                            #manifest = storages[storageid].manifest

                            #reply = struct.pack(">LLcL", storageid, messageid, "\x00", len(manifest))
                            #reply = struct.pack(">cL", "\x00", len(manifest))
                            #print(binascii.b2a_hex(reply))

                            #self.socket.send(reply)

                            #reply = struct.pack(">LLL", storageid, messageid, len(manifest))
                            reply = struct.pack(">L", len(manifest))
                            #print(binascii.b2a_hex(reply))
                            
                            #print(binascii.b2a_hex(manifest))

                            self.socket.send("\x01" + reply + manifest, False)

                        elif command[0] == "\x25" : #SEND UPDATE INFO - DISABLED WAS \x05
                            log.info(clientid + "Sending app update information")
                            (storageid, messageid, oldversion) = struct.unpack(">xLLL", command)
                            appid = storages[storageid].app
                            version = storages[storageid].version
                            log.info("Old GCF version: " + str(appid) + "_" + str(oldversion))
                            log.info("New GCF version: " + str(appid) + "_" + str(version))
                            manifestNew = Manifest2(appid, version)
                            manifestOld = Manifest2(appid, oldversion)
                            
                            if os.path.isfile(self.config["v2manifestdir"] + str(appid) + "_" + str(version) + ".manifest") :
                                checksumNew = Checksum3(appid)
                            else :
                                checksumNew = Checksum2(appid, version)
                                
                            if os.path.isfile(self.config["v2manifestdir"] + str(appid) + "_" + str(oldversion) + ".manifest") :
                                checksumOld = Checksum3(appid)
                            else :
                                checksumOld = Checksum2(appid, version)

                            filesOld = {}
                            filesNew = {}
                            for n in manifestOld.nodes.values():
                                if n.fileId != 0xffffffff:
                                    n.checksum = checksumOld.getchecksums_raw(n.fileId)
                                    filesOld[n.fullFilename] = n

                            for n in manifestNew.nodes.values():
                                if n.fileId != 0xffffffff:
                                    n.checksum = checksumNew.getchecksums_raw(n.fileId)
                                    filesNew[n.fullFilename] = n
                               
                            del manifestNew
                            del manifestOld

                            changedFiles = []

                            for filename in filesOld:
                                if filename in filesNew and filesOld[filename].checksum != filesNew[filename].checksum:
                                    changedFiles.append(filesOld[filename].fileId)
                                    log.debug("Changed file: " + str(filename) + " : " + str(filesOld[filename].fileId))
                                if not filename in filesNew:
                                    changedFiles.append(filesOld[filename].fileId)
                                    #if not 0xffffffff in changedFiles:
                                        #changedFiles.append(0xffffffff)                            
                                    log.debug("Deleted file: " + str(filename) + " : " + str(filesOld[filename].fileId))
                                    
                            for x in range(len(changedFiles)):
                                log.debug(changedFiles[x],)
                            
                            count = len(changedFiles)
                            log.info("Number of changed files: " + str(count))

                            if count == 0:
                                reply = struct.pack(">LLcL", storageid, messageid, "\x01", 0)
                                self.socket.send(reply)
                            else:
                                reply = struct.pack(">LLcL", storageid, messageid, "\x02", count)
                                self.socket.send(reply)
                                
                                changedFilesTmp = []
                                for fileid in changedFiles:
                                    changedFilesTmp.append(struct.pack("<L", fileid))
                                updatefiles = "".join(changedFilesTmp)
                                
                                reply = struct.pack(">LL", storageid, messageid)
                                self.socket.send(reply)
                                self.socket.send_withlen(updatefiles)
                            
                        elif command[0] == "\x05" : #SEND DATA
                            msg = self.socket.recv(12)
                            fileid, offset, length = struct.unpack(">III", msg)
                            if str(self.address[0]) in ipcalc.Network(str(globalvars.server_net)):
                                filedata = steam.readfile_beta(fileid, offset, length, index_data, dat_file_handle, "internal")
                            else:
                                filedata = steam.readfile_beta(fileid, offset, length, index_data, dat_file_handle, "external")
                            #0000001a 00000000 00010000
                            #00000001 00000000 00001e72
                            self.socket.send(b"\x01" + struct.pack(">II", len(filedata), 0), False)
                            for i in range(0, len(filedata), 0x2000):
                                chunk = filedata[i:i+0x2000]
                                self.socket.send(struct.pack(">I", len(chunk)) + chunk, False)
                            #self.socket.send(struct.pack(">I", len(filedata)) + filedata, False)
                        
                        elif command[0] == "\x06" : #BANNER

                            if len(command) == 10 :
                                self.socket.send("\x01")
                                break
                            else :
                                log.info("Banner message: " + binascii.b2a_hex(command))
                                
                                if self.config["http_port"] == "steam" or self.config["http_port"] == "0" or globalvars.steamui_ver < 87 :
                                    if str(self.address[0]) in ipcalc.Network(str(globalvars.server_net)):
                                        url = "http://" + self.config["http_ip"] + "/platform/banner/random.php"
                                        #print("INTERNAL BANNER")
                                    else:
                                        url = "http://" + self.config["public_ip"] + "/platform/banner/random.php"
                                        #print("EXTERNAL BANNER")
                                    #url = b"about:blank"
                                else :
                                    url = b"about:blank"

                                reply = struct.pack(">H", len(url)) + url

                                self.socket.send(reply)

                        elif command[0] == "\x07" : #SEND DATA

                            (storageid, messageid, fileid, filepart, numparts, dummy2) = struct.unpack(">xLLLLLB", command)

                            (chunks, filemode) = storages[storageid].readchunks(fileid, filepart, numparts)

                            reply = struct.pack(">LLcLL", storageid, messageid, "\x00", len(chunks), filemode)

                            self.socket.send(reply, False)

                            for chunk in chunks :

                                reply = struct.pack(">LLL", storageid, messageid, len(chunk))

                                self.socket.send(reply, False)

                                reply = struct.pack(">LLL", storageid, messageid, len(chunk))

                                self.socket.send(reply, False)

                                self.socket.send(chunk, False)

                        elif command[0] == "\x08" : #INVALID

                            log.warning("08 - Invalid Command!")
                            self.socket.send("\x01")
                        else :

                            log.warning(binascii.b2a_hex(command[0]) + " - Invalid Command!")
                            self.socket.send("\x01")

                            break
                            
                    try:
                        dat_file_handle.close()
                    except:
                        a = 1 #dummy error

                else :

                    log.warning(binascii.b2a_hex(command[0]) + " - Invalid Command!")
                    self.socket.send("\x01")

                    break
        
        elif msg == "\x00\x00\x00\x04" : #\x02 for 2003 beta v2 content
            log.info(clientid + "Content mode entered")
            self.socket.send("\x01")
                
            while True:
                msg = self.socket.recv_withlen()
                print("contentserver_worker |" + str(binascii.b2a_hex(msg)) + "|")
                print(len(msg))
                
                if msg[0] == "\x00": #COMMAND
                
                    (appid, verid) = struct.unpack(">II", msg[1:9])
                    print("appid", int(appid), "verid", int(verid))
                    
                    key = "\x69" * 0x10
                    if steam.verify_message(key, msg[9:]):
                        print(repr(steam.verify_message(key, msg[9:])))
                    
                    bio = io.BytesIO(msg[9:])
                    
                    ticketsize, = struct.unpack(">H", bio.read(2))
                    ticket = bio.read(ticketsize)
                    
                    #ptext = decrypt_message(bio.read()[:-20], key)
                    
                    #print("ptext", ptext.hex())
                    #print("ptext", repr(ptext))
                    
                    manif_version = 3
                    manif_num_items = 6
                    manif_dirnamesize = 64
                    manif_info1count = 1
                    manif_copycount = 1
                    manif_localcount = 0
                    
                    # offset_entries = offset_header + 0x38
                    # offset_dirnames = offset_entries + manif_num_items * 0x1c
                    # offset_yy = offset_dirnames + manif_dirnamesize
                    # offset_xx = offset_yy + (manif_info1count + num_items) * 4
                    # offset_ww = offset_xx + manif_copycount * 4
                    # offset_vv = offset_ww + manif_localcount * 4
                    
                    
                    manif_totalsize = 0x38 + manif_num_items * 0x1c + manif_dirnamesize + (manif_info1count + manif_num_items) * 4 + manif_copycount * 4 + manif_localcount * 4
                    
                    manif = struct.pack("<IIIIIIIIIIIIII", manif_version, 0x42, 0, manif_num_items, 5, 0x8000, manif_totalsize, manif_dirnamesize, manif_info1count, manif_copycount, manif_localcount, 2, 0, 0)
                    
                    manif += struct.pack("<IIIIIII",  1,       2, 0xffffffff,          0, 0xffffffff, 0, 1)
                    manif += struct.pack("<IIIIIII",  2,       3, 0xffffffff,          0,          0, 5, 2)
                    manif += struct.pack("<IIIIIII", 11, 0x80,             1, 0x00004000,          1, 3, 0)
                    manif += struct.pack("<IIIIIII", 18, 0x80,             2, 0x00004000,          1, 4, 0)
                    manif += struct.pack("<IIIIIII", 26, 0x80,             3, 0x00004000,          1, 0, 0)
                    manif += struct.pack("<IIIIIII", 35, 4062,             4, 0x00004000,          0, 0, 0)
                    
                    manif += "x\x00reslists\x00bg.txt\x00lol.txt\x00lol2.lst\x00testapp.exe".ljust(64, "\x00")
                    
                    manif += struct.pack("<IIIIIII", 1, 0, 1, 2, 3, 4, 0x80000005)
                    manif += struct.pack("<I", 5)
                    
                    #manif = bytes.fromhex("03000000e9000000010000000500000001000000008000000c0100002c000000020000000000000000000000001476e5fd2b3befb0281f6e0000000001000000ffffffff00000000ffffffff00000000010000000100000001000000ffffffff000000000000000000000000020000000500000001000000ffffffff000000000100000000000000030000000f00000001000000ffffffff0000000002000000000000000400000017000000502b0000110000000040000003000000000000000000000000686c32006d6174657269616c7300636f6e736f6c6500737461727475705f6c6f6164696e672e767466000002000000050000000100000002000000030000800000000004000080")
                    # manif = bytes.fromhex("03000000e9000000010000000500000001000000008000000c0100002c000000020000000000000000000000" + "02000000" + "fd2b3befb0281f6e")
                    # manif+= bytes.fromhex("0100000001000000ffffffff00000000ffffffff0000000001000000")
                    # manif+= bytes.fromhex("0100000001000000ffffffff00000000000000000000000002000000")
                    # manif+= bytes.fromhex("0500000001000000ffffffff000000000100000000000000030000000f00000001000000ffffffff0000000002000000000000000400000017000000502b0000110000000040000003000000000000000000000000686c32006d6174657269616c7300636f6e736f6c6500737461727475705f6c6f6164696e672e767466000002000000050000000100000002000000030000800000000004000080")
                    
                    manif = manif[:0x30] + "\x00" * 8 + manif[0x38:]
                    csums = struct.pack("<II", 0x11223344, zlib.adler32(manif, 0))
                    manif = manif[:0x30] + csums + manif[0x38:]
                        
                    # if len(manif) != manif_totalsize:
                        # raise Exception("bad manif size")
                        
                    print("manif size", hex(len(manif)))
                    
                    self.socket.send("\x66" + "\x11\x22\x33\x44" + "\x01")
                    
                    while True:
                        msg = self.socket.recv(1)
                        print("contentserver_worker |" + binascii.b2a_hex(msg) + "|")
                        
                        if len(msg) == 0:
                            print("contentserver connection close")
                            self.socket.close()
                            return
                            
                        if msg[0] == 2:
                            self.socket.send(struct.pack(">I", len(manif)) + manif)
                            
                        elif msg[0] == "5":
                            msg = self.socket.recv(12)
                            print("contentserver_worker |" + binascii.b2a_hex(msg) + "|")
                            
                            fileid, offset, length = struct.unpack(">III", msg)
                            if fileid == 1:
                                self.socket.send(b"\x01" + struct.pack(">II", 0x80, 0))
                                self.socket.send(struct.pack(">I", 0x80) + b"lol\n".ljust(0x80, b"\x00"))
                                
                            elif fileid == 2:
                                self.socket.send(b"\x01" + struct.pack(">II", 0x80, 0))
                                self.socket.send(struct.pack(">I", 0x80) + b"lol2\n".ljust(0x80, b"\x00"))
                            
                            elif fileid == 3:
                                self.socket.send(b"\x01" + struct.pack(">II", 0x80, 0))
                                self.socket.send(struct.pack(">I", 0x80) + b"testapp.exe\n".ljust(0x80, b"\x00"))

                            elif fileid == 4:
                                self.socket.send(b"\x01" + struct.pack(">II", 4062, 0))
                                self.socket.send(struct.pack(">I", 4062) + bytes.fromhex(testapp))
                            
                            print("sent block")
                            
                        elif binascii.b2a_hex(msg[0]) == "06":
                            
                            log.info(clientid + "Sending checksums")

                            (storageid, messageid) = struct.unpack(">xLL", command)

                            if os.path.isfile("files/cache/" + str(storages[storageid].app) + "_" + str(storages[storageid].version) + "/" + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".manifest") :
                                filename = "files/cache/" + str(storages[storageid].app) + "_" + str(storages[storageid].version) + "/"  + str(storages[storageid].app) + ".checksums"
                            elif os.path.isfile(self.config["v2manifestdir"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".manifest") :
                                filename = self.config["v2storagedir"] + str(storages[storageid].app) + ".checksums"
                            elif os.path.isfile(self.config["manifestdir"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".manifest") :
                                filename = self.config["storagedir"] + str(storages[storageid].app) + ".checksums"
                            elif os.path.isdir(self.config["v3manifestdir2"]) :
                                if os.path.isfile(self.config["v3manifestdir2"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".manifest") :
                                    filename = self.config["v3storagedir2"] + str(storages[storageid].app) + ".checksums"
                                else :
                                    log.error("Manifest not found for %s %s " % (app, version))
                                    reply = struct.pack(">LLc", connid, messageid, "\x01")
                                    self.socket.send(reply)
                                    break
                            else :
                                log.error("Checksums not found for %s %s " % (app, version))
                                reply = struct.pack(">LLc", connid, messageid, "\x01")
                                self.socket.send(reply)
                                break
                            f = open(filename, "rb")
                            file = f.read()
                            f.close()

                            # hack to rip out old sig, insert new
                            file = file[0:-128]
                            signature = steam.rsa_sign_message(steam.network_key_sign, file)

                            file = file + signature

                            reply = struct.pack(">LLcL", storageid, messageid, "\x00", len(file))

                            self.socket.send(reply)

                            reply = struct.pack(">LLL", storageid, messageid, len(file))

                            self.socket.send(reply + file, False)

                        else:
                            print("UNKNOWN MSG" + repr(msg))
                        
                            break
                        
                    else:
                        raise Exception("unknown subcommand")
                    
                    break
                    
                else:
                    raise Exception("unknown cmd")
                    
                # 00d3
                # 00 00000000 00000000 
                # 0080 5555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555
                # b8764da8a50940bdc8c25eb81c91a2e4001a002079d8f779074c2170965153f67b6f4d3f7e6cc9735887722f6000f7f2c0d70c4c8ebb70c0637ece9e51abc8c3164afb11596004e9
                
                

                
            while True:
                msg = self.socket.recv(16384)
                if len(msg) == 0:
                    print("disconnect")
                    break
                    
                print("server2 unknown msg |" + msg.hex() + "|")
        
        elif msg == "\x00\x00\x00\x05" or msg == "\x00\x00\x00\x06" : #\x06 for 2003 release

            log.info(clientid + "Storage mode entered")

            storagesopen = 0
            storages = {}

            self.socket.send("\x01") # this should just be the handshake

            while True :

                command = self.socket.recv_withlen()

                if command[0] == "\x00" : #BANNER

                    if len(command) == 10 :
                        self.socket.send("\x01")
                        break
                    else :
                        log.info("Banner message: " + binascii.b2a_hex(command))
                        
                        if self.config["http_port"] == "steam" or self.config["http_port"] == "0" or globalvars.steamui_ver < 87 :
                            if self.config["public_ip"] != "0.0.0.0" :
                                url = "http://" + self.config["public_ip"] + "/platform/banner/random.php"
                            else :
                                url = "http://" + self.config["http_ip"] + "/platform/banner/random.php"
                        else :
                            if self.config["public_ip"] != "0.0.0.0" :
                                url = "http://" + self.config["public_ip"] + ":" + self.config["http_port"] + "/platform/banner/random.php"
                            else :
                                url = "http://" + self.config["http_ip"] + ":" + self.config["http_port"] + "/platform/banner/random.php"

                        reply = struct.pack(">cH", "\x01", len(url)) + url

                        self.socket.send(reply)
                        
                elif command[0] == "\x02" : #SEND MANIFEST
                
                    if globalvars.steamui_ver < 24: 
                        (connid, messageid, app, version) = struct.unpack(">IIII", command[1:17])
                        #print(connid, messageid, app, version)
                        #print(app)
                        #print(version)
                        connid |= 0x80000000
                        key = b"\x69" * 0x10
                        signeddata = command[17:]
                        #print(binascii.b2a_hex(signeddata))

                        if hmac.new(key, signeddata[:-20], hashlib.sha1).digest() == signeddata[-20:]:
                            log.debug(clientid + "HMAC verified OK")
                        else:
                            log.error(clientid + "BAD HMAC")
                            raise Exception("BAD HMAC")

                        bio = io.BytesIO(signeddata)
                        #print(bio)
                        ticketsize, = struct.unpack(">H", bio.read(2))
                        #print(ticketsize)
                        ticket = bio.read(ticketsize)
                        #print(binascii.b2a_hex(ticket))
                        postticketdata = bio.read()[:-20]
                        IV = postticketdata[0:16]
                        #print(len(IV))
                        #print(len(postticketdata))
                        ptext = steam.aes_decrypt(key, IV, postticketdata[4:])
                        log.info(clientid + "Opening application %d %d" % (app, version))
                        #connid = pow(2,31) + connid

                        try :
                            s = steam.Storage(app, self.config["storagedir"], version)
                        except Exception :
                            log.error("Application not installed! %d %d" % (app, version))

                            reply = struct.pack(">LLc", connid, messageid, "\x01")
                            self.socket.send(reply)

                            break
                        storageid = storagesopen
                        storagesopen = storagesopen + 1

                        storages[storageid] = s
                        storages[storageid].app = app
                        storages[storageid].version = version
                        
                        if str(app) == "3" or str(app) == "7" :
                            if not os.path.isfile("files/cache/" + str(app) + "_" + str(version) + "/" + str(app) + "_" + str(version) + ".manifest") :
                                if os.path.isfile("files/convert/" + str(app) + "_" + str(version) + ".gcf") :
                                    log.info("Fixing files in app " + str(app) + " version " + str(version))
                                    g = open("files/convert/" + str(app) + "_" + str(version) + ".gcf", "rb")
                                    file = g.read()
                                    g.close()
                                    for (search, replace, info) in globalvars.replacestrings :
                                        fulllength = len(search)
                                        newlength = len(replace)
                                        missinglength = fulllength - newlength
                                        if missinglength < 0 :
                                            print "WARNING: Replacement text " + replace + " is too long! Not replaced!"
                                        elif missinglength == 0 :
                                            file = file.replace(search, replace)
                                            print "Replaced", info
                                        else :
                                            file = file.replace(search, replace + ('\x00' * missinglength))
                                            print "Replaced", info

                                    h = open("files/temp/" + str(app) + "_" + str(version) + ".neutered.gcf", "wb")
                                    h.write(file)
                                    h.close()
                                    gcf2storage("files/temp/" + str(app) + "_" + str(version) + ".neutered.gcf")
                                    sleep(1)
                                    os.remove("files/temp/" + str(app) + "_" + str(version) + ".neutered.gcf")
                        
                        if os.path.isfile("files/cache/" + str(app) + "_" + str(version) + "/" + str(app) + "_" + str(version) + ".manifest") :
                            f = open("files/cache/" + str(app) + "_" + str(version) + "/" + str(app) + "_" + str(version) + ".manifest", "rb")
                            log.info(clientid + str(app) + "_" + str(version) + " is a cached depot")
                        elif os.path.isfile(self.config["v2manifestdir"] + str(app) + "_" + str(version) + ".manifest") :
                            f = open(self.config["v2manifestdir"] + str(app) + "_" + str(version) + ".manifest", "rb")
                            log.info(clientid + str(app) + "_" + str(version) + " is a v0.2 depot")
                        elif os.path.isfile(self.config["manifestdir"] + str(app) + "_" + str(version) + ".manifest") :
                            f = open(self.config["manifestdir"] + str(app) + "_" + str(version) + ".manifest", "rb")
                            log.info(clientid + str(app) + "_" + str(version) + " is a v0.3 depot")
                        elif os.path.isdir(self.config["v3manifestdir2"]) :
                            if os.path.isfile(self.config["v3manifestdir2"] + str(app) + "_" + str(version) + ".manifest") :
                                f = open(self.config["v3manifestdir2"] + str(app) + "_" + str(version) + ".manifest", "rb")
                                log.info(clientid + str(app) + "_" + str(version) + " is a v0.3 extra depot")
                            else :
                                log.error("Manifest not found for %s %s " % (app, version))
                                reply = struct.pack(">LLc", connid, messageid, "\x01")
                                self.socket.send(reply)
                                break
                        else :
                            log.error("Manifest not found for %s %s " % (app, version))
                            reply = struct.pack(">LLc", connid, messageid, "\x01")
                            self.socket.send(reply)
                            break
                        manifest = f.read()
                        f.close()
                        
                        manifest_appid = struct.unpack('<L', manifest[4:8])[0]
                        manifest_verid = struct.unpack('<L', manifest[8:12])[0]
                        log.debug(clientid + ("Manifest ID: %s Version: %s" % (manifest_appid, manifest_verid)))
                        if (int(manifest_appid) != int(app)) or (int(manifest_verid) != int(version)) :
                            log.error("Manifest doesn't match requested file: (%s, %s) (%s, %s)" % (app, version, manifest_appid, manifest_verid))

                            reply = struct.pack(">LLc", connid, messageid, "\x01")
                            self.socket.send(reply)

                            break
                        
                        globalvars.converting = "0"

                        fingerprint = manifest[0x30:0x34]
                        oldchecksum = manifest[0x34:0x38]
                        manifest = manifest[:0x30] + "\x00" * 8 + manifest[0x38:]
                        checksum = struct.pack("<i", zlib.adler32(manifest, 0))
                        manifest = manifest[:0x30] + fingerprint + checksum + manifest[0x38:]
                        
                        log.debug("Checksum fixed from " + binascii.b2a_hex(oldchecksum) + " to " + binascii.b2a_hex(checksum))
                        
                        storages[storageid].manifest = manifest

                        checksum = struct.unpack("<L", manifest[0x30:0x34])[0] # FIXED, possible bug source

                        reply = struct.pack(">LLcLL", connid, messageid, "\x00", storageid, checksum)

                        self.socket.send(reply, False)
                    else:
                        a = 1 #DUMMY, TAKE OUT

                elif command[0] == "\x09" or command[0] == "\x0a" or command[0] == "\x02" : #REQUEST MANIFEST #09 is used by early clients without a ticket# 02 used by 2003 steam

                    if command[0] == "\x0a" :
                        log.info(clientid + "Login packet used")
                    #else :
                        #log.error(clientid + "Not logged in")

                        #reply = struct.pack(">LLc", connid, messageid, "\x01")
                        #self.socket.send(reply)

                        #break

                    (connid, messageid, app, version) = struct.unpack(">xLLLL", command[0:17])

                    log.info(clientid + "Opening application %d %d" % (app, version))
                    connid = pow(2,31) + connid

                    try :
                        s = steam.Storage(app, self.config["storagedir"], version)
                    except Exception :
                        log.error("Application not installed! %d %d" % (app, version))

                        reply = struct.pack(">LLc", connid, messageid, "\x01")
                        self.socket.send(reply)

                        break

                    storageid = storagesopen
                    storagesopen = storagesopen + 1

                    storages[storageid] = s
                    storages[storageid].app = app
                    storages[storageid].version = version
                    
                    if str(app) == "3" or str(app) == "7" :
                        if not os.path.isfile("files/cache/" + str(app) + "_" + str(version) + "/" + str(app) + "_" + str(version) + ".manifest") :
                            if os.path.isfile("files/convert/" + str(app) + "_" + str(version) + ".gcf") :
                                log.info("Fixing files in app " + str(app) + " version " + str(version))
                                g = open("files/convert/" + str(app) + "_" + str(version) + ".gcf", "rb")
                                file = g.read()
                                g.close()
                                for (search, replace, info) in globalvars.replacestrings :
                                    fulllength = len(search)
                                    newlength = len(replace)
                                    missinglength = fulllength - newlength
                                    if missinglength < 0 :
                                        print "WARNING: Replacement text " + replace + " is too long! Not replaced!"
                                    elif missinglength == 0 :
                                        file = file.replace(search, replace)
                                        print "Replaced", info
                                    else :
                                        file = file.replace(search, replace + ('\x00' * missinglength))
                                        print "Replaced", info

                                h = open("files/temp/" + str(app) + "_" + str(version) + ".neutered.gcf", "wb")
                                h.write(file)
                                h.close()
                                gcf2storage("files/temp/" + str(app) + "_" + str(version) + ".neutered.gcf")
                                sleep(1)
                                os.remove("files/temp/" + str(app) + "_" + str(version) + ".neutered.gcf")
                    
                    if os.path.isfile("files/cache/" + str(app) + "_" + str(version) + "/" + str(app) + "_" + str(version) + ".manifest") :
                        f = open("files/cache/" + str(app) + "_" + str(version) + "/" + str(app) + "_" + str(version) + ".manifest", "rb")
                        log.info(clientid + str(app) + "_" + str(version) + " is a cached depot")
                    elif os.path.isfile(self.config["v2manifestdir"] + str(app) + "_" + str(version) + ".manifest") :
                        f = open(self.config["v2manifestdir"] + str(app) + "_" + str(version) + ".manifest", "rb")
                        log.info(clientid + str(app) + "_" + str(version) + " is a v0.2 depot")
                    elif os.path.isfile(self.config["manifestdir"] + str(app) + "_" + str(version) + ".manifest") :
                        f = open(self.config["manifestdir"] + str(app) + "_" + str(version) + ".manifest", "rb")
                        log.info(clientid + str(app) + "_" + str(version) + " is a v0.3 depot")
                    elif os.path.isdir(self.config["v3manifestdir2"]) :
                        if os.path.isfile(self.config["v3manifestdir2"] + str(app) + "_" + str(version) + ".manifest") :
                            f = open(self.config["v3manifestdir2"] + str(app) + "_" + str(version) + ".manifest", "rb")
                            log.info(clientid + str(app) + "_" + str(version) + " is a v0.3 extra depot")
                        else :
                            log.error("Manifest not found for %s %s " % (app, version))
                            reply = struct.pack(">LLc", connid, messageid, "\x01")
                            self.socket.send(reply)
                            break
                    else :
                        log.error("Manifest not found for %s %s " % (app, version))
                        reply = struct.pack(">LLc", connid, messageid, "\x01")
                        self.socket.send(reply)
                        break
                    manifest = f.read()
                    f.close()
                    
                    manifest_appid = struct.unpack('<L', manifest[4:8])[0]
                    manifest_verid = struct.unpack('<L', manifest[8:12])[0]
                    log.debug(clientid + ("Manifest ID: %s Version: %s" % (manifest_appid, manifest_verid)))
                    if (int(manifest_appid) != int(app)) or (int(manifest_verid) != int(version)) :
                        log.error("Manifest doesn't match requested file: (%s, %s) (%s, %s)" % (app, version, manifest_appid, manifest_verid))

                        reply = struct.pack(">LLc", connid, messageid, "\x01")
                        self.socket.send(reply)

                        break
                    
                    globalvars.converting = "0"

                    fingerprint = manifest[0x30:0x34]
                    oldchecksum = manifest[0x34:0x38]
                    manifest = manifest[:0x30] + "\x00" * 8 + manifest[0x38:]
                    checksum = struct.pack("<i", zlib.adler32(manifest, 0))
                    manifest = manifest[:0x30] + fingerprint + checksum + manifest[0x38:]
                    
                    log.debug("Checksum fixed from " + binascii.b2a_hex(oldchecksum) + " to " + binascii.b2a_hex(checksum))
                    
                    storages[storageid].manifest = manifest

                    checksum = struct.unpack("<L", manifest[0x30:0x34])[0] # FIXED, possible bug source

                    reply = struct.pack(">LLcLL", connid, messageid, "\x00", storageid, checksum)

                    self.socket.send(reply, False)

                elif command[0] == "\x01" : #HANDSHAKE

                    self.socket.send("")
                    break

                elif command[0] == "\x03" : #CLOSE STORAGE

                    (storageid, messageid) = struct.unpack(">xLL", command)

                    del storages[storageid]

                    reply = struct.pack(">LLc", storageid, messageid, "\x00")

                    log.info(clientid + "Closing down storage %d" % storageid)

                    self.socket.send(reply)

                elif command[0] == "\x04" : #SEND MANIFEST

                    log.info(clientid + "Sending manifest")

                    (storageid, messageid) = struct.unpack(">xLL", command)

                    manifest = storages[storageid].manifest

                    reply = struct.pack(">LLcL", storageid, messageid, "\x00", len(manifest))

                    self.socket.send(reply)

                    reply = struct.pack(">LLL", storageid, messageid, len(manifest))

                    self.socket.send(reply + manifest, False)

                elif command[0] == "\x05" : #SEND UPDATE INFO
                    log.info(clientid + "Sending app update information")
                    (storageid, messageid, oldversion) = struct.unpack(">xLLL", command)
                    appid = storages[storageid].app
                    version = storages[storageid].version
                    log.info("Old GCF version: " + str(appid) + "_" + str(oldversion))
                    log.info("New GCF version: " + str(appid) + "_" + str(version))
                    manifestNew = Manifest2(appid, version)
                    manifestOld = Manifest2(appid, oldversion)
                    
                    if os.path.isfile(self.config["v2manifestdir"] + str(appid) + "_" + str(version) + ".manifest") :
                        checksumNew = Checksum3(appid)
                    else :
                        checksumNew = Checksum2(appid, version)
                        
                    if os.path.isfile(self.config["v2manifestdir"] + str(appid) + "_" + str(oldversion) + ".manifest") :
                        checksumOld = Checksum3(appid)
                    else :
                        checksumOld = Checksum2(appid, version)

                    filesOld = {}
                    filesNew = {}
                    for n in manifestOld.nodes.values():
                        if n.fileId != 0xffffffff:
                            n.checksum = checksumOld.getchecksums_raw(n.fileId)
                            filesOld[n.fullFilename] = n

                    for n in manifestNew.nodes.values():
                        if n.fileId != 0xffffffff:
                            n.checksum = checksumNew.getchecksums_raw(n.fileId)
                            filesNew[n.fullFilename] = n
                       
                    del manifestNew
                    del manifestOld

                    changedFiles = []

                    for filename in filesOld:
                        if filename in filesNew and filesOld[filename].checksum != filesNew[filename].checksum:
                            changedFiles.append(filesOld[filename].fileId)
                            log.debug("Changed file: " + str(filename) + " : " + str(filesOld[filename].fileId))
                        if not filename in filesNew:
                            changedFiles.append(filesOld[filename].fileId)
                            #if not 0xffffffff in changedFiles:
                                #changedFiles.append(0xffffffff)                            
                            log.debug("Deleted file: " + str(filename) + " : " + str(filesOld[filename].fileId))
                            
                    for x in range(len(changedFiles)):
                        log.debug(changedFiles[x],)
                    
                    count = len(changedFiles)
                    log.info("Number of changed files: " + str(count))

                    if count == 0:
                        reply = struct.pack(">LLcL", storageid, messageid, "\x01", 0)
                        self.socket.send(reply)
                    else:
                        reply = struct.pack(">LLcL", storageid, messageid, "\x02", count)
                        self.socket.send(reply)
                        
                        changedFilesTmp = []
                        for fileid in changedFiles:
                            changedFilesTmp.append(struct.pack("<L", fileid))
                        updatefiles = "".join(changedFilesTmp)
                        
                        reply = struct.pack(">LL", storageid, messageid)
                        self.socket.send(reply)
                        self.socket.send_withlen(updatefiles)
                    
                elif command[0] == "\x06" : #SEND CHECKSUMS

                    log.info(clientid + "Sending checksums")

                    (storageid, messageid) = struct.unpack(">xLL", command)

                    if os.path.isfile("files/cache/" + str(storages[storageid].app) + "_" + str(storages[storageid].version) + "/" + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".manifest") :
                        filename = "files/cache/" + str(storages[storageid].app) + "_" + str(storages[storageid].version) + "/"  + str(storages[storageid].app) + ".checksums"
                    elif os.path.isfile(self.config["v2manifestdir"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".manifest") :
                        filename = self.config["v2storagedir"] + str(storages[storageid].app) + ".checksums"
                    elif os.path.isfile(self.config["manifestdir"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".manifest") :
                        filename = self.config["storagedir"] + str(storages[storageid].app) + ".checksums"
                    elif os.path.isdir(self.config["v3manifestdir2"]) :
                        if os.path.isfile(self.config["v3manifestdir2"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".manifest") :
                            filename = self.config["v3storagedir2"] + str(storages[storageid].app) + ".checksums"
                        else :
                            log.error("Manifest not found for %s %s " % (app, version))
                            reply = struct.pack(">LLc", connid, messageid, "\x01")
                            self.socket.send(reply)
                            break
                    else :
                        log.error("Checksums not found for %s %s " % (app, version))
                        reply = struct.pack(">LLc", connid, messageid, "\x01")
                        self.socket.send(reply)
                        break
                    f = open(filename, "rb")
                    file = f.read()
                    f.close()

                    # hack to rip out old sig, insert new
                    file = file[0:-128]
                    signature = steam.rsa_sign_message(steam.network_key_sign, file)

                    file = file + signature

                    reply = struct.pack(">LLcL", storageid, messageid, "\x00", len(file))

                    self.socket.send(reply)

                    reply = struct.pack(">LLL", storageid, messageid, len(file))

                    self.socket.send(reply + file, False)

                elif command[0] == "\x07" : #SEND DATA

                    (storageid, messageid, fileid, filepart, numparts, dummy2) = struct.unpack(">xLLLLLB", command)

                    (chunks, filemode) = storages[storageid].readchunks(fileid, filepart, numparts)

                    reply = struct.pack(">LLcLL", storageid, messageid, "\x00", len(chunks), filemode)

                    self.socket.send(reply, False)

                    for chunk in chunks :

                        reply = struct.pack(">LLL", storageid, messageid, len(chunk))

                        self.socket.send(reply, False)

                        reply = struct.pack(">LLL", storageid, messageid, len(chunk))

                        self.socket.send(reply, False)

                        self.socket.send(chunk, False)

                elif command[0] == "\x08" : #INVALID

                    log.warning("08 - Invalid Command!")
                    self.socket.send("\x01")

                else :

                    log.warning(binascii.b2a_hex(command[0]) + " - Invalid Command!")
                    self.socket.send("\x01")

                    break

        elif msg == "\x00\x00\x00\x07" : #\x07 for 2004+

            log.info(clientid + "Storage mode entered")

            storagesopen = 0
            storages = {}

            self.socket.send("\x01") # this should just be the handshake

            while True :

                command = self.socket.recv_withlen()

                if command[0] == "\x00" : #BANNER

                    if len(command) == 10 :
                        self.socket.send("\x01")
                        break
                    elif len(command) > 1 :
                        log.info("Banner message: " + binascii.b2a_hex(command))
                        
                        if self.config["http_port"] == "steam" or self.config["http_port"] == "0" or globalvars.steamui_ver < 87 :
                            if self.config["public_ip"] != "0.0.0.0" :
                                url = "http://" + self.config["public_ip"] + "/platform/banner/random.php"
                            else :
                                url = "http://" + self.config["http_ip"] + "/platform/banner/random.php"
                        else :
                            if self.config["public_ip"] != "0.0.0.0" :
                                url = "http://" + self.config["public_ip"] + ":" + self.config["http_port"] + "/platform/banner/random.php"
                            else :
                                url = "http://" + self.config["http_ip"] + ":" + self.config["http_port"] + "/platform/banner/random.php"

                        reply = struct.pack(">cH", "\x01", len(url)) + url

                        self.socket.send(reply)
                    else :
                        self.socket.send("")
                        
                elif command[0] == "\xf2" : #SEND CDR - f2 TO DISABLE FOR 2003 TESTING
                
                    if os.path.isfile("files/cache/secondblob.bin") :
                        with open("files/cache/secondblob.bin", "rb") as f:
                            blob = f.read()
                    elif os.path.isfile("files/2ndcdr.py") or os.path.isfile("files/secondblob.py"):
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
                        if os.path.isfile("files/secondblob.orig") :
                            os.remove("files/secondblob.bin")
                            shutil.copy2("files/secondblob.orig","files/secondblob.bin")
                            os.remove("files/secondblob.orig")
                        with open("files/secondblob.bin", "rb") as g:
                            blob = g.read()
                        
                        if blob[0:2] == "\x01\x43":
                            blob = zlib.decompress(blob[20:])
                        blob2 = steam.blob_unserialize(blob)
                        blob3 = steam.blob_dump(blob2)
                        file = "blob = " + blob3
                        
                        for (search, replace, info) in globalvars.replacestringsCDR :
                            print "Fixing CDR 26"
                            fulllength = len(search)
                            newlength = len(replace)
                            missinglength = fulllength - newlength
                            if missinglength < 0 :
                                print "WARNING: Replacement text " + replace + " is too long! Not replaced!"
                            else :
                                file = file.replace(search, replace)
                                print("Replaced " + info + " " + search + " with " + replace)
                        
                        execdict = {}
                        execdict_temp_01 = {}
                        execdict_temp_02 = {}
                        exec(file, execdict)
                        
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
                        
                        #h = open("files/secondblob.bin", "wb")
                        #h.write(blob)
                        #h.close()
                        
                        #g = open("files/secondblob.bin", "rb")
                        #blob = g.read()
                        #g.close()
                        
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

                    checksum = SHA.new(blob).digest()

                    if checksum == command[1:] :
                        log.info(clientid + "Client has matching checksum for secondblob")
                        log.debug(clientid + "We validate it: " + binascii.b2a_hex(command))

                        self.socket.send("\x00\x00\x00\x00")

                    else :
                        log.info(clientid + "Client didn't match our checksum for secondblob")
                        log.debug(clientid + "Sending new blob: " + binascii.b2a_hex(command))

                        self.socket.send_withlen(blob, False)

                elif command[0] == "\x09" or command[0] == "\x0a" or command[0] == "\x02" : #REQUEST MANIFEST #09 is used by early clients without a ticket# 02 used by 2003 steam

                    if command[0] == "\x0a" :
                        log.info(clientid + "Login packet used")
                    #else :
                        #log.error(clientid + "Not logged in")

                        #reply = struct.pack(">LLc", connid, messageid, "\x01")
                        #self.socket.send(reply)

                        #break

                    (connid, messageid, app, version) = struct.unpack(">xLLLL", command[0:17])

                    log.info(clientid + "Opening application %d %d" % (app, version))
                    connid = pow(2,31) + connid

                    try :
                        s = steam.Storage(app, self.config["storagedir"], version)
                    except Exception :
                        log.error("Application not installed! %d %d" % (app, version))

                        reply = struct.pack(">LLc", connid, messageid, "\x01")
                        self.socket.send(reply)

                        break

                    storageid = storagesopen
                    storagesopen = storagesopen + 1

                    storages[storageid] = s
                    storages[storageid].app = app
                    storages[storageid].version = version
                    
                    if str(app) == "3" or str(app) == "7" :
                        if not os.path.isfile("files/cache/" + str(app) + "_" + str(version) + "/" + str(app) + "_" + str(version) + ".manifest") :
                            if os.path.isfile("files/convert/" + str(app) + "_" + str(version) + ".gcf") :
                                log.info("Fixing files in app " + str(app) + " version " + str(version))
                                g = open("files/convert/" + str(app) + "_" + str(version) + ".gcf", "rb")
                                file = g.read()
                                g.close()
                                for (search, replace, info) in globalvars.replacestrings :
                                    fulllength = len(search)
                                    newlength = len(replace)
                                    missinglength = fulllength - newlength
                                    if missinglength < 0 :
                                        print "WARNING: Replacement text " + replace + " is too long! Not replaced!"
                                    elif missinglength == 0 :
                                        file = file.replace(search, replace)
                                        print "Replaced", info
                                    else :
                                        file = file.replace(search, replace + ('\x00' * missinglength))
                                        print "Replaced", info

                                h = open("files/temp/" + str(app) + "_" + str(version) + ".neutered.gcf", "wb")
                                h.write(file)
                                h.close()
                                gcf2storage("files/temp/" + str(app) + "_" + str(version) + ".neutered.gcf")
                                sleep(1)
                                os.remove("files/temp/" + str(app) + "_" + str(version) + ".neutered.gcf")
                    
                    if os.path.isfile("files/cache/" + str(app) + "_" + str(version) + "/" + str(app) + "_" + str(version) + ".manifest") :
                        f = open("files/cache/" + str(app) + "_" + str(version) + "/" + str(app) + "_" + str(version) + ".manifest", "rb")
                        log.info(clientid + str(app) + "_" + str(version) + " is a cached depot")
                    elif os.path.isfile(self.config["v2manifestdir"] + str(app) + "_" + str(version) + ".manifest") :
                        f = open(self.config["v2manifestdir"] + str(app) + "_" + str(version) + ".manifest", "rb")
                        log.info(clientid + str(app) + "_" + str(version) + " is a v0.2 depot")
                    elif os.path.isfile(self.config["manifestdir"] + str(app) + "_" + str(version) + ".manifest") :
                        f = open(self.config["manifestdir"] + str(app) + "_" + str(version) + ".manifest", "rb")
                        log.info(clientid + str(app) + "_" + str(version) + " is a v0.3 depot")
                    elif os.path.isdir(self.config["v3manifestdir2"]) :
                        if os.path.isfile(self.config["v3manifestdir2"] + str(app) + "_" + str(version) + ".manifest") :
                            f = open(self.config["v3manifestdir2"] + str(app) + "_" + str(version) + ".manifest", "rb")
                            log.info(clientid + str(app) + "_" + str(version) + " is a v0.3 extra depot")
                        else :
                            log.error("Manifest not found for %s %s " % (app, version))
                            reply = struct.pack(">LLc", connid, messageid, "\x01")
                            self.socket.send(reply)
                            break
                    else :
                        log.error("Manifest not found for %s %s " % (app, version))
                        reply = struct.pack(">LLc", connid, messageid, "\x01")
                        self.socket.send(reply)
                        break
                    manifest = f.read()
                    f.close()
                    
                    manifest_appid = struct.unpack('<L', manifest[4:8])[0]
                    manifest_verid = struct.unpack('<L', manifest[8:12])[0]
                    log.debug(clientid + ("Manifest ID: %s Version: %s" % (manifest_appid, manifest_verid)))
                    if (int(manifest_appid) != int(app)) or (int(manifest_verid) != int(version)) :
                        log.error("Manifest doesn't match requested file: (%s, %s) (%s, %s)" % (app, version, manifest_appid, manifest_verid))

                        reply = struct.pack(">LLc", connid, messageid, "\x01")
                        self.socket.send(reply)

                        break
                    
                    globalvars.converting = "0"

                    fingerprint = manifest[0x30:0x34]
                    oldchecksum = manifest[0x34:0x38]
                    manifest = manifest[:0x30] + "\x00" * 8 + manifest[0x38:]
                    checksum = struct.pack("<i", zlib.adler32(manifest, 0))
                    manifest = manifest[:0x30] + fingerprint + checksum + manifest[0x38:]
                    
                    log.debug("Checksum fixed from " + binascii.b2a_hex(oldchecksum) + " to " + binascii.b2a_hex(checksum))
                    
                    storages[storageid].manifest = manifest

                    checksum = struct.unpack("<L", manifest[0x30:0x34])[0] # FIXED, possible bug source

                    reply = struct.pack(">LLcLL", connid, messageid, "\x00", storageid, checksum)

                    self.socket.send(reply, False)

                elif command[0] == "\x01" : #HANDSHAKE

                    self.socket.send("")
                    break

                elif command[0] == "\x03" : #CLOSE STORAGE

                    (storageid, messageid) = struct.unpack(">xLL", command)

                    del storages[storageid]

                    reply = struct.pack(">LLc", storageid, messageid, "\x00")

                    log.info(clientid + "Closing down storage %d" % storageid)

                    self.socket.send(reply)

                elif command[0] == "\x04" : #SEND MANIFEST

                    log.info(clientid + "Sending manifest")

                    (storageid, messageid) = struct.unpack(">xLL", command)

                    manifest = storages[storageid].manifest

                    reply = struct.pack(">LLcL", storageid, messageid, "\x00", len(manifest))

                    self.socket.send(reply)

                    reply = struct.pack(">LLL", storageid, messageid, len(manifest))

                    self.socket.send(reply + manifest, False)

                elif command[0] == "\x05" : #SEND UPDATE INFO
                    log.info(clientid + "Sending app update information")
                    (storageid, messageid, oldversion) = struct.unpack(">xLLL", command)
                    appid = storages[storageid].app
                    version = storages[storageid].version
                    log.info("Old GCF version: " + str(appid) + "_" + str(oldversion))
                    log.info("New GCF version: " + str(appid) + "_" + str(version))
                    manifestNew = Manifest2(appid, version)
                    manifestOld = Manifest2(appid, oldversion)
                    
                    if os.path.isfile(self.config["v2manifestdir"] + str(appid) + "_" + str(version) + ".manifest") :
                        checksumNew = Checksum3(appid)
                    else :
                        checksumNew = Checksum2(appid, version)
                        
                    if os.path.isfile(self.config["v2manifestdir"] + str(appid) + "_" + str(oldversion) + ".manifest") :
                        checksumOld = Checksum3(appid)
                    else :
                        checksumOld = Checksum2(appid, version)

                    filesOld = {}
                    filesNew = {}
                    for n in manifestOld.nodes.values():
                        if n.fileId != 0xffffffff:
                            n.checksum = checksumOld.getchecksums_raw(n.fileId)
                            filesOld[n.fullFilename] = n

                    for n in manifestNew.nodes.values():
                        if n.fileId != 0xffffffff:
                            n.checksum = checksumNew.getchecksums_raw(n.fileId)
                            filesNew[n.fullFilename] = n
                       
                    del manifestNew
                    del manifestOld

                    changedFiles = []

                    for filename in filesOld:
                        if filename in filesNew and filesOld[filename].checksum != filesNew[filename].checksum:
                            changedFiles.append(filesOld[filename].fileId)
                            log.debug("Changed file: " + str(filename) + " : " + str(filesOld[filename].fileId))
                        if not filename in filesNew:
                            changedFiles.append(filesOld[filename].fileId)
                            #if not 0xffffffff in changedFiles:
                                #changedFiles.append(0xffffffff)                            
                            log.debug("Deleted file: " + str(filename) + " : " + str(filesOld[filename].fileId))
                            
                    for x in range(len(changedFiles)):
                        log.debug(changedFiles[x],)
                    
                    count = len(changedFiles)
                    log.info("Number of changed files: " + str(count))

                    if count == 0:
                        reply = struct.pack(">LLcL", storageid, messageid, "\x01", 0)
                        self.socket.send(reply)
                    else:
                        reply = struct.pack(">LLcL", storageid, messageid, "\x02", count)
                        self.socket.send(reply)
                        
                        changedFilesTmp = []
                        for fileid in changedFiles:
                            changedFilesTmp.append(struct.pack("<L", fileid))
                        updatefiles = "".join(changedFilesTmp)
                        
                        reply = struct.pack(">LL", storageid, messageid)
                        self.socket.send(reply)
                        self.socket.send_withlen(updatefiles)
                    
                elif command[0] == "\x06" : #SEND CHECKSUMS

                    log.info(clientid + "Sending checksums")

                    (storageid, messageid) = struct.unpack(">xLL", command)

                    if os.path.isfile("files/cache/" + str(storages[storageid].app) + "_" + str(storages[storageid].version) + "/" + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".manifest") :
                        filename = "files/cache/" + str(storages[storageid].app) + "_" + str(storages[storageid].version) + "/"  + str(storages[storageid].app) + ".checksums"
                    elif os.path.isfile(self.config["v2manifestdir"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".manifest") :
                        filename = self.config["v2storagedir"] + str(storages[storageid].app) + ".checksums"
                    elif os.path.isfile(self.config["manifestdir"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".manifest") :
                        filename = self.config["storagedir"] + str(storages[storageid].app) + ".checksums"
                    elif os.path.isdir(self.config["v3manifestdir2"]) :
                        if os.path.isfile(self.config["v3manifestdir2"] + str(storages[storageid].app) + "_" + str(storages[storageid].version) + ".manifest") :
                            filename = self.config["v3storagedir2"] + str(storages[storageid].app) + ".checksums"
                        else :
                            log.error("Manifest not found for %s %s " % (app, version))
                            reply = struct.pack(">LLc", connid, messageid, "\x01")
                            self.socket.send(reply)
                            break
                    else :
                        log.error("Checksums not found for %s %s " % (app, version))
                        reply = struct.pack(">LLc", connid, messageid, "\x01")
                        self.socket.send(reply)
                        break
                    f = open(filename, "rb")
                    file = f.read()
                    f.close()

                    # hack to rip out old sig, insert new
                    file = file[0:-128]
                    signature = steam.rsa_sign_message(steam.network_key_sign, file)

                    file = file + signature

                    reply = struct.pack(">LLcL", storageid, messageid, "\x00", len(file))

                    self.socket.send(reply)

                    reply = struct.pack(">LLL", storageid, messageid, len(file))

                    self.socket.send(reply + file, False)

                elif command[0] == "\x07" : #SEND DATA

                    (storageid, messageid, fileid, filepart, numparts, dummy2) = struct.unpack(">xLLLLLB", command)

                    (chunks, filemode) = storages[storageid].readchunks(fileid, filepart, numparts)

                    reply = struct.pack(">LLcLL", storageid, messageid, "\x00", len(chunks), filemode)

                    self.socket.send(reply, False)

                    for chunk in chunks :

                        reply = struct.pack(">LLL", storageid, messageid, len(chunk))

                        self.socket.send(reply, False)

                        reply = struct.pack(">LLL", storageid, messageid, len(chunk))

                        self.socket.send(reply, False)

                        self.socket.send(chunk, False)

                elif command[0] == "\x08" : #INVALID

                    log.warning("08 - Invalid Command!")
                    self.socket.send("\x01")

                else :

                    log.warning(binascii.b2a_hex(command[0]) + " - Invalid Command!")
                    self.socket.send("\x01")

                    break
        
        elif msg == "\x03\x00\x00\x00" : #UNKNOWN
            log.info(clientid + "Unknown mode entered")
            self.socket.send("\x00")
        
        else :
            log.warning("Invalid Command: " + binascii.b2a_hex(msg))

        self.socket.close()
        log.info(clientid + "Disconnected from Content Server")
