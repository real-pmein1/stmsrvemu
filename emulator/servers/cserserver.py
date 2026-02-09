import binascii
import csv
import hashlib
import io
import logging
import os
import socket
import struct
import time
from builtins import range, str
from datetime import datetime

import ipcalc
from libs.CryptICE import IceKey

import globalvars
import utils
from utilities.networkbuffer import NetworkBuffer
from utilities.networkhandler import UDPNetworkHandler


def int_wrapper(value):
    try:
        val1 = int(value, base = 16)
        return val1
    except (ValueError, TypeError):
        return 0


# Define a function to read strings from buffer until null byte
def read_string_until_null(buffer):
    result = []
    while True:
        char = buffer.read(1)
        if char == b'\x00' or not char:
            break
        result.append(char)
    return b''.join(result)


class CSERServer(UDPNetworkHandler):

    def __init__(self, port, config):
        self.server_type = "CSERServer"
        super(CSERServer, self).__init__(config, int(port), self.server_type)  # Create an instance of NetworkHandler
        self.log = logging.getLogger(self.server_type)
        self.handlers = {
                b'e': self.parse_steamstats,
                b'c': self.parse_crashreport,
                b'q': self.parse_encryptedbugreport,
                b'p': self.parse_unknownp,
                b'a': self.parse_app_install_stats,
                b'o': self.parse_bugreport,
                b'i': self.handle_unknown_stats,
                b'k': self.parse_gamestats,
                b'm': self.parse_phonehome,
                b'g': self.parse_surveyresults,
                b'u': self.parse_upload_gamestats
        }

    def handle_client(self, data, address):

        clientid = str(address) + ": "
        self.log.info(clientid + "Connected to CSER Server")
        self.log.debug(clientid + ("Received message: %s, from %s" % (repr(data), address)))

        command = data[:1]
        if command in self.handlers:
            self.handlers[command](address, data[2:], clientid)
        else:
            self.log.info("Unknown CSER command: %s" % data)

    def parse_unknownp(self, address, data, clientid):
        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        filename = "clientstats//{}.{}.unknownstats.txt".format(address, timestamp)
        with open(filename, 'w') as file:
            file.write({data})

    def parse_upload_gamestats(self, address, data, clientid):
        ice = IceKey(1, [54, 175, 165, 5, 76, 251, 29, 113])
        # Decrypt the remainder of the data
        decrypted = ice.Decrypt(bytes.fromhex(data[3:].hex()))

        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        filename = "clientstats//{}.{}.enrypted_gamestats.txt".format(address, timestamp)
        with open(filename, 'w') as file:
            file.write({decrypted})

    def parse_app_install_stats(self, address, data, clientid):
        self.log.info(f"{clientid}Received Application Installation Stats")
        reply = b"\xFF\xFF\xFF\xFFb"
        unknown1 = data[0:1]
        appId = struct.unpack('<I', data[1:5])[0]
        duration = struct.unpack('<I', data[5:9])[0]
        isDownload = data[9:10]
        nbGcf = data[10:11]

        keys = ['GameID', '']
        vals = [str(appId), str(duration) + "s"]

        #debug = ""
        if isDownload == b"\x01":
            keys[1] = 'DownloadDuration'
            #debug += f"\r\n appId: {appId}\r\n download duration: {duration}s\r\n"
        elif isDownload == b"\x00":
            keys[1] = 'ExtractionDuration'
            #debug += f"\r\n appId: {appId}\r\n extraction duration: {duration}s\r\n"
        else:
            keys[1] = f'UnknownDuration_{isDownload}'
            #debug += f"\r\n appId: {appId}\r\n unknown duration({isDownload}): {duration}s\r\n"
        #print(debug)
        downloaded_from_content_server = False

        nbGcf = struct.unpack('B', nbGcf)[0]
        # debug +=f"Number of GCFs Downloaded {int(nbGcf)}\n"
        keys.append('Number of GCFs Downloaded')
        vals.append(str(nbGcf))
        for ind in range(nbGcf):
            ip = struct.unpack('>I', data[11 + ind * 4:15 + ind * 4])[0]
            if ip != -1:
                # debug += f" downloaded from content server :"
                downloaded_from_content_server = True
                break

        if downloaded_from_content_server:
            for ind in range(nbGcf):
                ip = struct.unpack('>I', data[11 + ind * 4:15 + ind * 4])[0]
                if ip != -1:
                    ip_str = socket.inet_ntoa(struct.pack('>I', ip))
                    # debug += f" {ip_str}"

                    key = f"GCF[{len(keys) - 1}] Downloaded From ContentServer"
                    keys.append(key)
                    vals.append(ip_str)

        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        filename = "clientstats/downloadstats/{}.{}.downloadstats.txt".format(address, timestamp)
        with open(filename, 'w') as file:
            for key, val in zip(keys, vals):
                file.write(f'{key}: {val}\n')  # file.write(debug)

        self.serversocket.sendto(reply + b"\x01", address)

    def handle_unknown_stats(self, address, data, clientid):
        """
        CSERServer  Received message: b'i\n\x01\n\x00\x00\x00\x01\x00\x00\xdaA\xaa\x00q}\xc8B', from ('72.135.236.199', 65386)
        CSERServer    INFO     ('72.135.236.199', 65386): Received unknown stats - INOP
        CSERServer    DEBUG    unknown stats: b'\x01\n\x00\x00\x00\x01\x00\x00 \xdaA\xaa\x00 q}\xc8B'
        """
        self.log.info(f"{clientid}Received unknown stats - INOP")
        self.log.debug(f"unknown stats: {data}")
        self.serversocket.sendto(b"\xFF\xFF\xFF\xFFj\x01", address)

    def check_allowupload(self, reply, address):
        allowupload = b"\x02" if self.config["allow_harvest_upload"].lower() == "true" else b"\x01"  # \x00 = unknown
        reply += b"\x01" + allowupload
        if allowupload == b"\x02":
            # TODO BEN, GRAB FROM DIR SERVER & SEND HARVEST SERVER NEWLY GENERATED CONTEXT ID'S FOR ITS LIST IF NOT AIO SERVER
            if str(address[0]) in ipcalc.Network(str(globalvars.server_net)):
                bin_ip = utils.encodeIP((self.config['server_ip'], int(self.config['harvest_server_port'])))
            else:
                bin_ip = utils.encodeIP((self.config['harvest_ip'], int(self.config['harvest_server_port'])))
            contextid = globalvars.session_id_manager.add_new_context_id()
            reply += bin_ip + contextid
        return reply

    def parse_gamestats(self, address, data, clientid):
        self.log.info(f"{clientid} Received game statistics")
        reply = b"\xFF\xFF\xFF\xFFl"  # Base reply with identifier

        data_bin = bytes.fromhex(data.hex())  # Convert data to binary
        buffer = NetworkBuffer(data_bin)

        # Read protocol version
        protover = buffer.extract_u8()
        if protover != 2:  # Only version 2 is valid based on the updated logic
            self.log.error(f"Invalid Game Statistics protocol version: {protover}")
            self.serversocket.sendto(reply + b"\x00", address)  # Protocol error
            return

        # Read application ID and upload size
        appid = buffer.extract_u32()
        uploadsize = buffer.extract_u32()

        # Log statistics
        txt_gamestats = f"Protocol 2\nApplication ID: {appid}\nReport Size: {uploadsize}\n"
        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"clientstats/gamestats/{address}_{timestamp}.gamestats.txt"
        with open(filename, "w") as file:
            file.write(txt_gamestats)

        # Handle game stats upload logic
        statsUniqueId = int(hashlib.md5(filename.encode()).hexdigest(), 16)

        # Build response
        reply += b"\x01"  # Protocol OK
        if not statsUniqueId:
            reply += b"\x00"  # No file upload
        else:
            # Use IP from config['harvest_ip']
            try:
                harvest_ip = self.config['harvest_ip']
                ip_bytes = struct.pack(">I", int.from_bytes(socket.inet_aton(harvest_ip), "big"))
            except KeyError:
                self.log.error("Missing 'harvest_ip' in configuration")
                self.serversocket.sendto(reply + b"\x00", address)  # Protocol error
                return
            except Exception as e:
                self.log.error(f"Invalid 'harvest_ip': {e}")
                self.serversocket.sendto(reply + b"\x00", address)  # Protocol error
                return
            harvest_port = int(self.config['harvest_server_port'])
            port_bytes = struct.pack(">H", harvest_port)  # Use port from fileUploadServer

            reply += b"\x01"  # File upload requested
            reply += ip_bytes
            reply += port_bytes
            reply += struct.pack(">I", statsUniqueId)  # Add statsUniqueId

        # Send the response
        self.serversocket.sendto(reply, address)

    def parse_bugreport(self, address, data, clientid):
        self.log.info("Received bug report")
        """b'\x01\xe5\x0f\x00\x00hl2.exe\x00tf\x00tc_hydro\x00\xff\x07\x00\x00\xb7\x0b\x00\x00GenuineIntel\x00\t\x00\x00\x00\x05\x00\x00\x00\xde\x10\x00\x00\x07%\x00\x00 (Build 9200) version 6.2\x00\xdc\xa1\x00\x00In-game Crash\x00sdf@dsdsf.com\x00[1:2]\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00tc_hydro: dfdddf\x00;\x02\x00\x00dsfsd dsfds dsffdf\n\nlevel:  tc_hydro\nbuild:  4069 (Steam)\nposition:  setpos -1904.000000 -2832.000000 288.031250; setang 7.589999 106.764076 0.000000\nDriver Name:  NVIDIA GeForce RTX 3050\nVendorId / DeviceId:  0x10de / 0x2507\nSubSystem / Rev:  0x8e991462 / 0xa1\nDXLevel:  gamemode\nVid:  1024 x 768\nFramerate:  100.970\nConvars:\n\tskill:  1\n\tnet:  rate 30000 update 20 cmd 30 latency 0 msec\n\thost_thread_mode:  0\n\tsv_alternateticks:  0\n\tai_strong_optimizations:  0\nMap version:  4384\ngamedir:  f:\\development\\steam\\emulator_v2\\client\\lan\\steamapps\\test\\team fortress 2\\tf\n\n\x00\x00\x00'"""
        """		// C2M_BUGREPORT details
        //		u8(C2M_BUGREPORT_PROTOCOL_VERSION) = 1 2 or 3
        //		u16(encryptedlength)
        //		remainder=encrypteddata"""
        data_bin = bytes.fromhex(data.hex())
        data_length = len(data_bin)
        buffer = NetworkBuffer(data_bin)
        reportver = buffer.extract_u8()
        encryptedlen = buffer.extract_u16()
        reply = b"\xFF\xFF\xFF\xFF\x71"
        if not reportver in [1, 2, 3]:
            self.log.warning(f"{clientid}Sent Bug Report with invalid protocal version! Version: {reportver}")
            self.serversocket.sendto(reply + b"\x00\x00", address)  # \x00 = bad version, 2nd \x00 = no file upload
        else:
            ice = IceKey(1, [200, 145, 10, 149, 195, 190, 108, 243])
            reply += b"\x01"  # Good protocol version
            # Decrypt the remainder of the data
            decrypted = ice.Decrypt(buffer.get_buffer_from_cursor())
            timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"clientstats/bugreports/{address}.{timestamp}.bugreport.txt"

            # Create a new NetworkBuffer instance for the decrypted data
            buffer = NetworkBuffer(decrypted)
            """// encrypted payload:
            //		byte corruptionid = 1
            //		u32(buildnumber)
            //		string(exename 64)
            //		string(gamedir 64)
            //		string(mapname 64)
            //		u32 RAM
            //		u32 CPU
            //		string(processor)
            //		u32 DXVerHigh
            //		u32 DXVerLow
            //		u32	DXVendorID
            //		u32 DXDeviceID
            //		string(OSVer)"""
            corruptionid = buffer.extract_u8()
            buildnumber = buffer.extract_u32()
            exename = buffer.extract_string()
            gamedir = buffer.extract_string()
            mapname = buffer.extract_string()
            ramsize = buffer.extract_u32()
            cpuspeed = buffer.extract_u32()
            proccessor_type = buffer.extract_string()
            dxverhigh = buffer.extract_u32()
            dxverlow = buffer.extract_u32()
            dxvendorid = buffer.extract_u32()
            dxdeviceid = buffer.extract_u32()
            os_name = buffer.extract_string()
            txt_bugreport = (f'Protocol 1\nCorruption ID: {corruptionid}\nBuild Number: {buildnumber}\nExecuteable: '
                             f'{exename}\nGame Directory: {gamedir}\nMap: {mapname}\nRam: {ramsize}\nProcessor (MHZ):{cpuspeed}\n'
                             f'Processor: {proccessor_type}\nDirectX Version: {dxverhigh}.{dxverlow}\nDirectX VendorID: '
                             f'{dxvendorid}\nDirectX DeviceID: {dxdeviceid}\nOperating System: {os_name}\n')
            """"// Version 2+:
            //	{
            //			reporttype(char 32)
            //			email(char 80)
            //			accountname(char 80)
            //	}"""
            if reportver in [2, 3]:
                report_type = buffer.extract_string()
                email = buffer.extract_string()
                # FIXME The username seems to not be included in steamui 1060 tf2 in-game crash reports, infact from here its a bunch of plain text information, no file info or anything
                # accoutname = buffer.extract_string()
                txt_bugreport += (f'Report Type: {report_type}\nEmail Address: {email}\n') # \nAccount Name: {accoutname}

                # Attempt to see what's after the email
                possible_account = buffer.extract_string()

                # Check if it matches the pattern [X:Y]
                # Being so brain-dead, I'll even hold your hand with a simple check
                if possible_account.startswith('[') and possible_account.endswith(']') and ':' in possible_account:
                    # It's an account ID
                    # Everything after this is raw data
                    remainder = buffer.extract_buffer(buffer.remaining_length())
                    raw_filename = f"clientstats/bugreports/{address}.{timestamp}.plain.txt"
                    os.makedirs(os.path.dirname(raw_filename), exist_ok=True)
                    with open(raw_filename, 'wb') as f:
                        f.write(remainder)
                else:
                    # Not an account ID, so assume it's an account name
                    accountname = possible_account
                    txt_bugreport += f'Account Name: {accountname}\n'

                    if reportver == 3:
                        userid = buffer.extract_u64()
                        txt_bugreport += f'SteamID: {userid}\n'

                    filename = buffer.extract_string()
                    zipsize = buffer.extract_u32()
                    textlen = buffer.extract_u32()
                    description = buffer.extract_buffer(int(textlen))

                    if isinstance(filename, bytearray):
                        filename = filename.decode('utf-8')

                    os.makedirs(os.path.dirname(filename), exist_ok=True)

                    with open(filename, "w", encoding='ascii', errors='replace') as file:
                        file.write(
                            f'{txt_bugreport}Memory Dump Filename: {filename}\n'
                            f'Zip Size: {zipsize}kb\nDescription: {description}\n'
                        )
            else:
                # If reportver not in [2,3], just do whatever your lame original code did
                # You're welcome, short and tubby.
                filename = buffer.extract_string()
                zipsize = buffer.extract_u32()
                textlen = buffer.extract_u32()
                description = buffer.extract_buffer(int(textlen))

                if isinstance(filename, bytearray):
                    filename = filename.decode('utf-8')

                os.makedirs(os.path.dirname(filename), exist_ok=True)

                with open(filename, "w", encoding='ascii', errors='replace') as file:
                    file.write(
                        f'{txt_bugreport}Memory Dump Filename: {filename}\n'
                        f'Zip Size: {zipsize}kb\nDescription: {description}\n'
                    )

            # Finish with your pathetic upload check
            reply += self.check_allowupload(reply, address)
            self.serversocket.sendto(reply, address)

    def parse_crashreport(self, address, data, clientid):
        self.log.info(f"{clientid}Received client crash report")

        reply = b"\xFF\xFF\xFF\xFFd"

        ipstr = str(address)
        ipstr1 = ipstr.split('\'')
        ipactual = ipstr1[1]

        message = data[3:].hex()
        keylist = list(range(13))
        vallist = list(range(13))
        keylist[0] = "Unknown1"
        keylist[1] = "Unknown2"
        keylist[2] = "ModuleName"
        keylist[3] = "FileName"
        keylist[4] = "CodeFile"
        keylist[5] = "ThrownAt"
        keylist[6] = "Unknown3"
        keylist[7] = "Unknown4"
        keylist[8] = "AssertPreCondition"
        keylist[9] = "FileSize"
        keylist[10] = "OsCode"
        keylist[11] = "Unknown5"
        keylist[12] = "Message"

        templist = binascii.a2b_hex(message)
        templist2 = templist.split(b'\x00')

        vallist[0] = str(int_wrapper(binascii.b2a_hex(templist2[0][2:4])))
        vallist[1] = str(int_wrapper(binascii.b2a_hex(templist2[1])))
        vallist[2] = str(templist2[2])
        vallist[3] = str(templist2[3])
        vallist[4] = str(templist2[4])
        vallist[5] = str(int_wrapper(binascii.b2a_hex(templist2[5])))
        vallist[6] = str(int_wrapper(binascii.b2a_hex(templist2[7])))
        vallist[7] = str(int_wrapper(binascii.b2a_hex(templist2[10])))
        vallist[8] = str(templist2[13])
        vallist[9] = str(int_wrapper(binascii.b2a_hex(templist2[14])))
        vallist[10] = str(int_wrapper(binascii.b2a_hex(templist2[15])))
        vallist[11] = str(int_wrapper(binascii.b2a_hex(templist2[18])))
        try:
            vallist[12] = str(templist2[23])
        except:
            vallist[12] = ''
        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"clientstats/exceptionlogs/{address}.{timestamp}.csv"

        f = open(filename, "w")
        f.write("SteamExceptionsData")
        f.write("\n")
        f.write(keylist[0] + "," + keylist[1] + "," + keylist[2] + "," + keylist[3] + "," + keylist[4] + "," + keylist[5] + "," + keylist[6] + "," + keylist[7] + "," + keylist[8] + "," + keylist[9] + "," + keylist[10] + "," + keylist[11] + "," + keylist[12])
        f.write("\n")
        f.write(vallist[0] + "," + vallist[1] + "," + vallist[2] + "," + vallist[3] + "," + vallist[4] + "," + vallist[5] + "," + vallist[6] + "," + vallist[7] + "," + vallist[8] + "," + vallist[9] + "," + vallist[10] + "," + vallist[11] + "," + vallist[12])
        f.close()

        # d =  message type
        # then 0 = invalid message protocol, 1 = upload request denied, 2 = Ok to upload to harvest server
        # 2 = server accepts minidump, so client will send it now
        reply += self.check_allowupload(reply, address)
        self.serversocket.sendto(reply, address)

    def parse_encryptedbugreport(self, address, data, clientid):
        self.log.info(f"{clientid}Received encrypted bug report stats")
        # C2M_BUGREPORT details
        #     u8(C2M_UPLOADDATA_PROTOCOL_VERSION) == 1
        #     u16(encryptedlength)
        #     remainder=encrypteddata
        # encrypted payload:
        #b'\x01\x01SteamExecutionData\x00\x18StatTimestamp\x001715563736\x00HashedSteamID\x0054bb1caa3f4d546b0ca9bab9575d712\x00LanguageID\x009\x00OSVersion\x002003  (Build 9200)\x00LogicalProcessors\x008\x00PhysicalProcessors\x008\x00CPUSpeed\x002999987552\x00TotalPhysRAM\x0034285973504\x00AvailPhysRAM\x0015219982336\x00TotalVirtual\x002147352576\x00AvailVirtual\x001769357312\x00SteamVersion\x00234\x00SteamUniverse\x001\x00SteamDuration\x0086\x00SteamUpdateDuration\x000\x00SteamUpdateStatus\x000\x00GameLaunches\x000\x00GameUpdateDuration\x000\x00GameLaunchDelay\x000\x00GameDuration\x000\x00GameCrashes\x000\x00SteamCrashes\x000\x00SteamRestartReason\x000\x00SteamDowntime\x00219\x00\x00\x00\x00\x00\x00'
        #     byte(corruptionid)
        #     byte(protocolid) // C2M_UPLOADDATA_DATA_VERSION == 1
        #     string(tablename 40)
        #     u8(numvalues)
        #     for each value:
        #         string(fieldname 32)
        #         string(value 128)

        data_bin = bytes.fromhex(data.hex())
        data_length = len(data_bin)
        buffer = io.BytesIO(data_bin)
        protocol_version, = struct.unpack("B", buffer.read(1))
        self.log.debug(f"protocol version: {protocol_version}")
        encrypted_length, = struct.unpack("<H", buffer.read(2))
        # Decrypt the remainder of the data
        self.log.debug(f"encrypted length: {encrypted_length}")
        # Initialize the IceKey with the specific key
        ice = IceKey(1, [54, 175, 165, 5, 76, 251, 29, 113])

        # Decrypt the data
        decrypted = ice.Decrypt(data_bin[3:])
        self.log.debug(f"encrypted: {data_bin}\n decrypted: {decrypted}")
        # Process the decrypted data
        buffer = io.BytesIO(decrypted)
        info = {"encrypted_length":data_length, }

        # Extract information from the buffer
        corruption_id, = struct.unpack("B", buffer.read(1))
        protocol_id, = struct.unpack("B", buffer.read(1))
        tablename = read_string_until_null(buffer)
        num_values, = struct.unpack("B", buffer.read(1))
        values = []
        print(tablename)
        for _ in range(num_values):
            fieldname = read_string_until_null(buffer)
            value = read_string_until_null(buffer)
            if fieldname == b'StatTimestamp':
                value = self.int_to_datetime_bytes(value)
            values.append((fieldname, value))

        # Add extracted values to the dictionary
        info["corruption_id"] = corruption_id
        info["protocol_id"] = protocol_id
        info["tablename"] = tablename
        info["num_values"] = num_values
        info["values"] = values

        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"clientstats/bugreports/{address[0]}.{timestamp}.csv"

        # Save the information to a CSV file
        with open(filename, 'w', newline = '') as csv_file:
            csv_writer = csv.writer(csv_file)
            for field, val in values:
                csv_writer.writerow([field, val])

        """//M2C_ACKUPLOADDATA details
        u8(protocol okay (bool))"""
        self.serversocket.sendto(b"\xFF\xFF\xFF\xFF\x72\x01", address)  # 72 = r command and the next byte is a bool, ok = 1, bad = 0

    def int_to_datetime_bytes(self, value):
        # Convert the byte string representing an integer to an actual integer
        utctime = int(value.decode('ascii'))
        # Pack it as an 8-byte buffer
        # Convert the Unix timestamp to a datetime object
        dt_object = datetime.utcfromtimestamp(utctime)
        # Format the datetime object as a string
        value = dt_object.strftime('%m/%d/%Y %H:%M:%S').encode('latin-1')
        return value

    def parse_steamstats(self, address, data, clientid):
        self.log.info(f"{clientid}Received steam stats")

        ipstr = str(address)
        ipstr1 = ipstr.split('\'')
        ipactual = ipstr1[1]

        message = binascii.b2a_hex(data[1:])
        keylist = list(range(7))
        vallist = list(range(7))
        # keylist[0] = "LastUpload" # this was missing, shows up in ida in 2005.  havnt looked at older steam versions to see if it is also there
        keylist[0] = "SuccessCount"
        keylist[1] = "ShutdownFailureCount"  # this was flipped with unknownfailurecount
        keylist[2] = "UnknownFailureCount"
        keylist[3] = "UptimeCleanCounter"
        keylist[4] = "UptimeCleanTotal"
        keylist[5] = "UptimeFailureCounter"
        keylist[6] = "UptimeFailureTotal"
        # keylist[7] =

        filename = binascii.a2b_hex(message[0:10]) # Steam.exe or Steam.dll

        if filename in [b'Steam.exe\x00', b'Steam.dll\x00']:
            vallist[0] = str(int(message[24:26], base = 16))
            vallist[1] = str(int(message[26:28], base = 16))
            vallist[2] = str(int(message[28:30], base = 16))
            vallist[3] = str(int(message[30:32], base = 16))
            vallist[4] = str(int(message[32:34], base = 16))
            vallist[5] = str(int(message[34:36], base = 16))
            vallist[6] = str(int(message[36:38], base = 16))
            # vallist[7] = str(int(message[38:40], base=16))

            timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"clientstats/steamstats/{ipactual}.{timestamp}.{filename}.csv"

            f = open(filename, "w")
            f.write(binascii.hexlify(message[2:21]).decode('latin-1'))
            f.write("\n")
            f.write(keylist[0] + "," + keylist[1] + "," + keylist[2] + "," + keylist[3] + "," + keylist[4] + "," + keylist[5] + "," + keylist[6])  # + "," + keylist[7])
            f.write("\n")
            f.write(vallist[0] + "," + vallist[1] + "," + vallist[2] + "," + vallist[3] + "," + vallist[4] + "," + vallist[5] + "," + vallist[6])  # + "," + vallist[7])

            try:
                f.write(f"\r\nrest of packet: {str(message[38:])}")
            except:
                pass

            f.close()
        else:
            timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"clientstats/steamstats/{ipactual}.{timestamp}.unknown.csv"

            f = open(filename, "w")
            f.write(str(binascii.a2b_hex(message)))

        self.serversocket.sendto(b"\xFF\xFF\xFF\xFFf", address)

    def parse_phonehome(self, address, data, clientid):
        self.log.info(f"{clientid}Received Phone Home")
        """
        // C2M_PHONEHOME
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

        ice = IceKey(1, [27, 200, 13, 14, 83, 45, 184, 54])  # unknown key, this is probably incorrect

        # Assuming you have received the encrypted data in the 'data' variable
        data_bin = bytes.fromhex(data[3:].hex())
        data_length = len(data_bin)
        reply = b"\xFF\xFF\xFF\xFF\x6E"
        # Create a NetworkBuffer instance with the decrypted data
        buffer = NetworkBuffer(data_bin)

        # Extract information
        protocol_version = buffer.extract_u8()
        session_id = buffer.extract_u32()

        # Check if the byte string matches any of the stored context IDs
        is_match = globalvars.session_id_manager.match_byte_string(session_id)

        if session_id != 0 and not is_match:
            self.log.warning(f"{clientid}Session ID Does not match any known previous IDs! {session_id}")
            self.serversocket.sendto(reply + b"\x00", address)
            return
        else:
            encrypted_length = buffer.extract_u16()
            encrypted_data = buffer.extract_buffer(encrypted_length)

            # Decrypt the remainder of the data
            decrypted = ice.Decrypt(encrypted_data)

            # Create a new NetworkBuffer instance for the decrypted data
            buffer = NetworkBuffer(decrypted)

            # Extract the remaining information
            corruption_id = buffer.extract_u8()
            unique_id = buffer.extract_string()
            computer_name = buffer.extract_string()
            username = buffer.extract_string()
            game_dir = buffer.extract_string()
            engine_timestamp = struct.unpack('f', buffer.extract_buffer(4))[0]
            message_type = buffer.extract_u8()

            # Log the received data
            self.log.info(f"{clientid}Received Phone Home")

            # Prepare the extracted data
            extracted_data = {
                "protocol_version" : protocol_version,
                "session_id"       : session_id,
                "encrypted_length" : encrypted_length,
                "corruption_id"    : corruption_id,
                "unique_id"        : unique_id,
                "computer_name"    : computer_name,
                "username"         : username,
                "game_dir"         : game_dir,
                "engine_timestamp" : engine_timestamp,
                "message_type"     : message_type
            }

            # Generate a filename based on the IP address and timestamp
            timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"clientstats/phonehome/{address}.{timestamp}.phonehome.txt"

            # Write the extracted data to a file
            with open(filename, "w") as file:
                for key, value in list(extracted_data.items()):
                    file.write("\n{} : {}".format(key, value))

            """// M2C_ACKPHONEHOME details
            //	u8(connection allowed (bool))
            //  u32(sessionid)"""
            if session_id == 0:
                session_id = globalvars.session_id_manager.add_new_context_id()  # random session id

            self.serversocket.sendto(reply + b"\x01" + session_id, address)

    def parse_surveyresults(self, address, data, clientid):
        self.log.info(f'{clientid}Recieved Survey Results')

        # Helper function to read a null-terminated string
        def read_null_terminated_string(bytes_, start_index):
            end_index = bytes_.find(b'\x00', start_index)
            return bytes_[start_index:end_index], end_index + 1

        ice = IceKey(1, [27, 200, 13, 14, 83, 45, 184, 54])
        data_bin = bytes.fromhex(data[3:].hex())
        byte_string = ice.Decrypt(data_bin)

        result = {}
        index = 0
        # Decryption OK
        result['DecryptionOK'], index = byte_string[index], index + 1

        if result['DecryptionOK'] != 1:
            self.log.info(f'{clientid}Failed To Decrypt Survey Results')
            self.serversocket.sendto(b"\xFF\xFF\xFF\xFF\x68\x00", address)
        else:
            # TODO put this into the database as steam2_survey_data
            if data[0:1] == b"\x02":

                # Client ID
                result['clientid'], index = read_null_terminated_string(byte_string, index)

                # RAM Size
                result['ramsize'], index = struct.unpack('>I', byte_string[index:index + 4])[0], index + 4

                # Processor Speed
                result['processorspeed'], index = struct.unpack('>I', byte_string[index:index + 4])[0], index + 4

                # Net Speed
                result['netspeed'], index = struct.unpack('>I', byte_string[index:index + 4])[0], index + 4

                # Screen Size
                result['screensize'], index = struct.unpack('>I', byte_string[index:index + 4])[0], index + 4

                # Render Mode
                result['rendermode'], index = byte_string[index], index + 1

                # Bit Depth
                result['bitdepth'], index = struct.unpack('B', byte_string[index:index + 1])[0], index + 1

                # Skip 1 byte
                index += 1

                # Video Driver DLL
                result['videodriverdll'], index = read_null_terminated_string(byte_string, index)

                # Skip 1 byte
                index += 1

                # Video Card
                result['videocard'], index = read_null_terminated_string(byte_string, index)

                # High Video Card Version
                result['highvidcardver'], index = struct.unpack('>I', byte_string[index:index + 4])[0], index + 4

                # Low Video Card Version
                result['lowvidcardver'], index = struct.unpack('>I', byte_string[index:index + 4])[0], index + 4

                # Card Vendor ID
                result['cardvendorid'], index = struct.unpack('>I', byte_string[index:index + 4])[0], index + 4

                # Device ID
                result['deviceid'], index = struct.unpack('>I', byte_string[index:index + 4])[0], index + 4

                # RDTSC, CMOV, FCMOV, SSE, SSE2, 3DNOW, NTFS
                fields = ['rdtsc', 'cmov', 'fcmov', 'sse', 'sse2', '3dnow', 'ntfs']
                for field in fields:
                    result[field], index = byte_string[index], index + 1

                # Processor Type
                result['proctype'], index = read_null_terminated_string(byte_string, index)

                # Logical Processor Count, Physical Processor Count, Hyper-Threading
                result['logicalprocessorcount'], index = byte_string[index], index + 1

                result['physicalproccesorcount'], index = byte_string[index], index + 1

                result['hyperthreading'], index = byte_string[index], index + 1

                # AGP String
                result['agpstr'], index = read_null_terminated_string(byte_string, index)

                # Bus Speed
                result['bus_speed'], index = struct.unpack('>I', byte_string[index:index + 4])[0], index + 4

                # Windows Version
                result['winver'], index = read_null_terminated_string(byte_string, index)

                # IP Address
                # Unpack the three bytes into three integers
                ip_parts = struct.unpack('BBB', byte_string[index:index + 3])
                result['ipaddress'], index = "{}.{}.{}.xxx".format(*ip_parts), index + 3

                # Language ID
                result['languageid'], index = byte_string[index], index + 1

                # Media Type
                result['mediatype'], index = byte_string[index], index + 1

                # Free HDD Block
                result['freehdblock'], index = struct.unpack('>I', byte_string[index:index + 4])[0], index + 4

                # Total HDD Space
                result['totalhdspace'], index = struct.unpack('>I', byte_string[index:index + 4])[0], index + 4

                # Unknown Buffer
                result['unknownbuffer'] = byte_string[index:]

            elif data[0:1] == b"\x05":

                result['clientid'], index = read_null_terminated_string(byte_string, index)

                # RAM Size
                result['ramsize'], index = struct.unpack('>I', byte_string[index:index + 4])[0], index + 4

                # Processor Speed
                result['processorspeed'], index = struct.unpack('>I', byte_string[index:index + 4])[0], index + 4

                # Net Speed
                result['netspeed'], index = struct.unpack('>I', byte_string[index:index + 4])[0], index + 4

                # Render Mode
                result['renderer'], index = byte_string[index], index + 1

                scr_games = ["goldsrc_screen", "hl1src_screen", "hl2_screen", "hl2mp_screen", "css_screen", "dod_screen", "lostcoast_screen"]
                i = 0
                while i < len(scr_games):
                    game = scr_games[i]
                    # screen width
                    result[f'{game}_width'], index = struct.unpack('>I', byte_string[index:index + 4])[0], index + 4

                    # screen height
                    result[f'{game}_height'], index = struct.unpack('>I', byte_string[index:index + 4])[0], index + 4

                    # game windowed
                    result[f'{game}_windowed'], index = byte_string[index], index + 1

                    # game screen deoth
                    result[f'{game}_depth'], index = byte_string[index], index + 1
                    i += 1

                result['adapter'], index = read_null_terminated_string(byte_string, index)

                result['driver_version'], index = read_null_terminated_string(byte_string, index)

                result['video_card'], index = read_null_terminated_string(byte_string, index)

                result['directx_videocard_driver'], index = read_null_terminated_string(byte_string, index)

                result['directx_videocard_version'], index = read_null_terminated_string(byte_string, index)

                result['msaa_modes'], index = read_null_terminated_string(byte_string, index)

                result['monitor_vendor'], index = read_null_terminated_string(byte_string, index)

                result['monitor_model'], index = read_null_terminated_string(byte_string, index)

                result['driver_year'], index = struct.unpack('>I', byte_string[index:index + 4])[0], index + 4

                result['driver_month'], index = byte_string[index], index + 1

                result['driver_day'], index = byte_string[index], index + 1

                result['vram_size'], index = struct.unpack('>I', byte_string[index:index + 4])[0], index + 4

                result['bit_depth'], index = byte_string[index], index + 1

                result['monitor_refresh_rate'], index = struct.unpack('>I', byte_string[index:index + 4])[0], index + 4

                result['number_of_monitors'], index = byte_string[index], index + 1

                result['number_of_display_devices'], index = byte_string[index], index + 1

                result['monitor_width_px'], index = struct.unpack('>I', byte_string[index:index + 4])[0], index + 4

                result['monitor_height_px'], index = struct.unpack('>I', byte_string[index:index + 4])[0], index + 4

                result['desktop_width_px'], index = struct.unpack('>I', byte_string[index:index + 4])[0], index + 4

                result['desktop_height_px'], index = struct.unpack('>I', byte_string[index:index + 4])[0], index + 4

                result['monitor_width_mm'], index = struct.unpack('>I', byte_string[index:index + 4])[0], index + 4

                result['monitor_height_mm'], index = struct.unpack('>I', byte_string[index:index + 4])[0], index + 4

                result['desktop_wdith_mm'], index = struct.unpack('>I', byte_string[index:index + 4])[0], index + 4

                result['desktop_height_mm'], index = struct.unpack('>I', byte_string[index:index + 4])[0], index + 4

                result['monitor_diagonal_nn'], index = struct.unpack('>I', byte_string[index:index + 4])[0], index + 4

                result['d3d_vendor_id'], index = struct.unpack('>I', byte_string[index:index + 4])[0], index + 4

                result['d3d_device_id'], index = struct.unpack('>I', byte_string[index:index + 4])[0], index + 4

                result['multi_gpu'], index = byte_string[index], index + 1

                result['number_sli_gpus'], index = byte_string[index], index + 1

                result['display_type'], index = byte_string[index], index + 1

                result['bus_type'], index = byte_string[index], index + 1

                result['bus_rate'], index = byte_string[index], index + 1

                result['agpgart'], index = byte_string[index], index + 1

                result['rdtsc'], index = byte_string[index], index + 1

                result['cmov'], index = byte_string[index], index + 1

                result['fcmov'], index = byte_string[index], index + 1

                result['sse'], index = byte_string[index], index + 1

                result['sse2'], index = byte_string[index], index + 1

                result['3dnow'], index = byte_string[index], index + 1

                result['ntfs'], index = byte_string[index], index + 1

                result['cpu_vendor'], index = read_null_terminated_string(byte_string, index)

                result['physical_processors'], index = byte_string[index], index + 1

                result['logical_processors'], index = byte_string[index], index + 1

                result['hyperthreading'], index = byte_string[index], index + 1

                result['agp'], index = read_null_terminated_string(byte_string, index)

                result['bus_speed'], index = struct.unpack('>I', byte_string[index:index + 4])[0], index + 4

                result['os_version'], index = read_null_terminated_string(byte_string, index)

                result['audio_device'], index = struct.unpack('>I', byte_string[index:index + 4])[0], index + 4

                result['ip2'], index = byte_string[index], index + 1

                result['ip1'], index = byte_string[index], index + 1

                result['ip0'], index = byte_string[index], index + 1

                result['language_id'], index = byte_string[index], index + 1

                result['drive_type'], index = byte_string[index], index + 1

                result['free_hd_space'], index = struct.unpack('>I', byte_string[index:index + 4])[0], index + 4

                result['total_hd_space'], index = struct.unpack('>I', byte_string[index:index + 4])[0], index + 4
                # TODO loop here


            timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
            filename = "clientstats/surveys/{}.{}.hwsurvey.txt".format(address[0], timestamp)
            with open(filename, 'w') as file:
                for key, value in result.items():
                    if key != 'DecryptionOK':
                        file.write(f'{key}: {value}\n')

            self.serversocket.sendto(b"\xFF\xFF\xFF\xFF\x68\x01\x00\x00\x00" + b"thank you\x00", address)