import threading, logging, struct, binascii, time, socket, ipaddress, os.path, ast, csv
import os
import steam
import config
import steamemu.logger
import globalvars
from Crypto.Cipher import AES
from steamemu.config import read_config

config = read_config()

class cserserver(threading.Thread):
    serversocket = None

    def __init__(self, host, port):
        #threading.Thread.__init__(self)
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        serversocket = self.socket

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
                log.info(clientid + "Received client stats")
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
        
        elif data.startswith("a"):  # 61
            log.info("Received app download stats - INOP")
        elif data.startswith("o"):  # 61
            log.info("Received app download stats - INOP")
        elif data.startswith("i"):  # 69
            log.info("Received unknown stats - INOP")
        elif data.startswith("k"):  # 6b
            log.info("Received app usage stats - INOP")
        elif data.startswith("g"):  # survey response
            CSER_ICE_KEY_g = bytearray([0x1B, 0xC8, 0x0D, 0x0E, 0x53, 0x2D, 0xB8, 0x36])
            CSER_ICE_KEY_g = CSER_ICE_KEY_g.ljust(16, b'\x00')  # Pad with zeros to make it 16 bytes
            aes_g = AES.new(str(CSER_ICE_KEY_g), AES.MODE_ECB)
            log.info("Received Survey Response (no actions taken)")
            self.socket.sendto("\xFF\xFF\xFF\xFF\x68\x01",address)
        else:
            log.info("Unknown CSER command: %s" % data)



