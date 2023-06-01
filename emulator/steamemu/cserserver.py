import threading, logging, struct, binascii, time, socket, ipaddress, os.path, ast
import os
import steam
import config
import steamemu.logger
import globalvars

from steamemu.config import read_config

config = read_config()

class cserserver(threading.Thread):

    def __init__(self, host, port):
        #threading.Thread.__init__(self)
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

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
            log.info("Received encrypted ICE client stats - INOP")
        elif data.startswith("a"):  # 61
            log.info("Received app download stats - INOP")
        elif data.startswith("i"):  # 69
            log.info("Received unknown stats - INOP")
        elif data.startswith("k"):  # 6b
            log.info("Received app usage stats - INOP")
        elif data.startswith("g"):  # survey response
            log.info("Received Survey Response (no actions taken)")
        else:
            log.info("Unknown CSER command: %s" % data)



