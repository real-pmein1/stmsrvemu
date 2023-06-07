import myimports
import threading, logging, struct, binascii, time, socket, ipaddress, os.path, ast, csv
import os
import utilities
import config
import steamemu.logger
import globalvars
import serverlist_utilities


class IceKey(object):
    def __init__(self, key):
        self.key = key

    def decrypt(self, block):
        key = self.key

        x = struct.unpack('>LL', block.ljust(8, '\x00'))
        delta = 0x9e3779b9
        sum = (delta * 16) & 0xffffffff

        for i in range(16):
            x = list(x)
            x[1] -= ((x[0] << 4) + key[2]) ^ (x[0] + sum) ^ ((x[0] >> 5) + key[3])
            x[1] &= 0xffffffff
            x[0] -= ((x[1] << 4) + key[0]) ^ (x[1] + sum) ^ ((x[1] >> 5) + key[1])
            x[0] &= 0xffffffff
            sum -= delta

        return struct.pack('>LL', x[0], x[1])

class cserserver(threading.Thread):
    def __init__(self, host, port):
        #threading.Thread.__init__(self)
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
       # Start the thread for dir registration heartbeat, only
        thread2 = threading.Thread(target=self.heartbeat_thread)
        thread2.daemon = True
        thread2.start()
        
    def heartbeat_thread(self):       
        while True:
            serverlist_utilities.heartbeat(globalvars.serverip, self.port, "cserserver", globalvars.peer_password )
            time.sleep(1800) # 30 minutes
            
    def start(self):
        
        self.socket.bind((self.host, self.port))

        while True:
            #recieve a packet
            data, address = self.socket.recvfrom(1280)
            # Start a new thread to process each packet
            threading.Thread(target=self.process_packet, args=(data, address)).start()

    def process_packet(self, data, address):
        log = logging.getLogger("csersrv")
        # Process the received packet
        clientid = str(address) + ": "
        log.info(clientid + "Connected to CSER Server")
        log.debug(clientid + ("Received message: %s, from %s" % (data, address)))
        ipstr = str(address)
        ipstr1 = ipstr.split('\'')
        ipactual = ipstr1[1]
        if data.startswith("e"):  # 65
            message = binascii.b2a_hex(data)
            keylist = ["SuccessCount", "UnknownFailureCount", "ShutdownFailureCount",
                       "UptimeCleanCounter", "UptimeCleanTotal", "UptimeFailureCounter",
                       "UptimeFailureTotal"]
            vallist = [str(int(message[24:26], base=16)),
                       str(int(message[26:28], base=16)),
                       str(int(message[28:30], base=16)),
                       str(int(message[30:32], base=16)),
                       str(int(message[32:34], base=16)),
                       str(int(message[34:36], base=16)),
                       str(int(message[36:38], base=16))]

            try:
                os.mkdir("clientstats")
            except OSError as error:
                log.debug("Client stats dir already exists")

            if message.startswith("650a01537465616d2e657865"):  # Steam.exe
                f = open("clientstats\\" + str(ipactual) + ".steamexe.csv", "w")
                f.write(str(binascii.a2b_hex(message[6:24])))
                f.write("\n")
                f.write(",".join(keylist))
                f.write("\n")
                f.write(",".join(vallist))
                f.close()
                log.info(clientid + "Received steam client stats")
        elif data.startswith("c"):  # 63
            message = binascii.b2a_hex(data)
            keylist = ["Unknown1", "Unknown2", "ModuleName", "FileName", "CodeFile", "ThrownAt",
                       "Unknown3", "Unknown4", "AssertPreCondition", "Unknown5", "OsCode",
                       "Unknown6", "Message"]
            templist = binascii.a2b_hex(message)
            templist2 = templist.split(b'\x00')
            try:
                vallist = [str(int(binascii.b2a_hex(templist2[0][2:4]), base=16)),
                           str(int(binascii.b2a_hex(templist2[1]), base=16)),
                           str(templist2[2]),
                           str(templist2[3]),
                           str(templist2[4]),
                           str(int(binascii.b2a_hex(templist2[5]), base=16)),
                           str(int(binascii.b2a_hex(templist2[7]), base=16)),
                           str(int(binascii.b2a_hex(templist2[10]), base=16)),
                           str(templist2[13]),
                           str(int(binascii.b2a_hex(templist2[14]), base=16)),
                           str(int(binascii.b2a_hex(templist2[15]), base=16)),
                           str(int(binascii.b2a_hex(templist2[18]), base=16)),
                           str(templist2[23])]

                try:
                    os.mkdir("crashlogs")
                except OSError as error:
                    log.debug("Client crash reports dir already exists")

                f = open("crashlogs\\" + str(ipactual) + ".csv", "w")
                f.write("SteamExceptionsData")
                f.write("\n")
                f.write(",".join(keylist))
                f.write("\n")
                f.write(",".join(vallist))
                f.close()
                log.info(clientid + "Received client crash report")
            except Exception as e:
                log.debug(clientid + "Failed to receive client crash report: " + str(e))
                #d =  message type
                #then 1 = request denied, invalid message protocol
                #2 = server accepts minidump, so client will send it now
                
        elif data.startswith("q"):  # 71
            CSER_ICE_KEY_q = bytearray([0x36, 0xAF, 0xA5, 0x05, 0x4C, 0xFB, 0x1D, 0x71])
            CSER_ICE_KEY_q = CSER_ICE_KEY_q.ljust(16, b'\x00')  # Pad with zeros to make it 16 bytes
            aes_q = AES.new(str(CSER_ICE_KEY_q), AES.MODE_ECB)
            log.info("Received encrypted ICE client stats")
                # C2M_BUGREPORT details
                #     u8(C2M_UPLOADDATA_PROTOCOL_VERSION)
                #     u16(encryptedlength)
                #     remainder=encrypteddata

                # encrypted payload:
                #     byte(corruptionid)
                #     byte(protocolid) // C2M_UPLOADDATA_DATA_VERSION
                #     string(tablename 40)
                #     u8(numvalues)
                #     for each value:
                #         string(fieldname 32)
                #         string(value 128)
            """len = struct.unpack('H', data[1:3])[0]
                sentData = data[3:]

                log.debug("Received crypted Steam client stats packet, from %s: %s" % (from_address, sentData))

                decrypted = ''

                # Create the AES decryption object
                aes = AES.new(CSER_ICE_KEY_q, AES.MODE_ECB)

                for ind in range(len / 8):
                    encrypted_block = sentData[ind * 8:(ind + 1) * 8]
                    decrypted_block = aes.decrypt(encrypted_block)
                    decrypted += decrypted_block

                log.debug("Received Steam client stats packet, from %s: %s" % (from_address, decrypted))

                debug = ''

                header = struct.unpack('H', decrypted[:2])[0]
                if header != 0x0101:
                    log.debug("Invalid stats header, from %s: %s" % (from_address, decrypted))
                    return 0

                subject = decrypted[2:]

                keys = []
                values = []

                debug += "\r\n%s : \r\n" % subject
                next_index = 2 + len(subject) + 1
                nbFields = ord(decrypted[next_index])
                next_index += 1

                for ind in range(nbFields):
                    tmp = ""
                    key = decrypted[next_index:].split('\x00', 1)[0]
                    next_index += len(key) + 1

                    value = decrypted[next_index:].split('\x00', 1)[0]
                    next_index += len(value) + 1

                    keys.append(key)
                    values.append(value)
                    tmp = "  %s: %s\r\n" % (key, value)
                    debug += tmp

                log.debug("Received Steam client stats, from %s: %s" % (from_address, debug))

                # Save key-value pairs to a CSV file
                filename = os.path.join('./logs', from_address[0] + '.bugreport#' + decrypted[0] + '.csv')
                with open(filename, 'w') as csvfile:
                    writer = csv.writer(csvfile)
                    for key, value in zip(keys, values):
                        writer.writerow([key, value])

                # Clean up
                del aes
                del decrypted
                del debug"""
            self.socket.sendto("\xFF\xFF\xFF\xFF\x72\x01", address) # 72 = r command and the next byte is a bool, ok = 1, bad = 0
        
        elif data.startswith("a"):  # 61
            log.info("Received app download stats - INOP")
        elif data.startswith("o"):
            log.info("Received bug report - INOP")
            """ // M2C_ACKBUGREPORT details
		//	u8(protocol okay (bool))
		//	u8(BR_NO_FILES or BR_REQEST_FILES )
		//  iff BR_REQEST_FILES then add:
		//    u32(harvester ip address)
		//	  u16(harvester port #)
		//	  u32(upload context id)
            """
            self.socket.sendto("\xFF\xFF\xFF\xFF\x71\x01", address)
        elif data.startswith("i"):  # 69
            log.info("Received unknown stats - INOP")
        elif data.startswith("k"):  # 6b
            log.info("Received game statistics stats - INOP")
        elif data.startswith("m"):
            """	// C2M_PHONEHOME
                //	u8( C2M_PHONEHOME_PROTOCOL_VERSION )
                //	u32( sessionid ) or 0 to request a new sessionid
                //  u16(encryptedlength)
                //  remainder = encrypteddata:
		// u8 corruption id == 1
		//  string build unique id
		//  string computername
		//	string username
		//  string gamedir
		//  float( enginetimestamp )
		//  u8 messagetype:
		//    1:  engine startup 
		//    2:  engine shutdown
		//    3:  map started + mapname
		//    4:  map finished + mapname
		//	string( mapname )
            """
            log.info("Received Phone Home- INOP")
            """ // M2C_ACKPHONEHOME details
                //	u8(connection allowed (bool))
                //  u32(sessionid)
            """
            self.socket.sendto("\xFF\xFF\xFF\xFF\x6E\x01", address) #random session id, 321 
        elif data.startswith("g"):  # survey response
            len = struct.unpack("<H", data[1:3])[0]
            sentData = data[3:]

            """decrypted = bytearray(len)

            ice = IceKey([0x1B, 0xC8, 0x0D, 0x0E, 0x53, 0x2D, 0xB8, 0x36])

            num_blocks = len // 8
            remaining_bytes = len % 8

            for ind in range(num_blocks):
                block_in = sentData[8 * ind:8 * ind + 8]
                block_out = ice.decrypt(block_in)
                decrypted[8 * ind:8 * ind + 8] = block_out

            if remaining_bytes > 0:
                block_in = sentData[num_blocks * 8:].ljust(8, '\x00')
                block_out = ice.decrypt(block_in)[:remaining_bytes]
                decrypted[num_blocks * 8:] = block_out

            print decrypted
            # Save decrypted data to a file
            ip_address = address[0]
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            filename = "clientstats/{}.{}.hwsurvey.txt".format(ip_address, timestamp)

            with open(filename, "w") as f:
                f.write(decrypted)"""
           #remove the following 2 lines when decryption is figured out
            with open(filename, "w") as f:
                f.write(sentData)
            self.socket.sendto("\xFF\xFF\xFF\xFF\x68\x01\x00\x00\x00"+"thank you\n\0", address)
        else:
            log.info("Unknown CSER command: %s" % data)



