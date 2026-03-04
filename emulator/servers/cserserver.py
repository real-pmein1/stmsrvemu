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
from utilities.database import statistics_db
from servers.managers.dirlistmanager import manager as dirmanager
from servers.managers import serverlist_utilities


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
                b'a': self.parse_app_install_stats,
                b'c': self.parse_crashreport,
                b'e': self.parse_steamstats,
                b'g': self.parse_surveyresults,
                b'i': self.handle_bandwidth_stats,
                b'k': self.parse_gamestats,
                b'm': self.parse_phonehome,
                b'o': self.parse_bugreport,
                b'q': self.parse_uploaddata,
                b'u': self.parse_upload_gamestats
        }

    def int_to_datetime_bytes(self, value):
        # Convert the byte string representing an integer to an actual integer
        utctime = int(value.decode('ascii'))
        # Pack it as an 8-byte buffer
        # Convert the Unix timestamp to a datetime object
        dt_object = datetime.utcfromtimestamp(utctime)
        # Format the datetime object as a string
        value = dt_object.strftime('%m/%d/%Y %H:%M:%S').encode('latin-1')
        return value

    def read_string(self, data: bytes, offset: int) -> (str, int):
        """
        Reads a null-terminated string from data starting at offset.
        Returns a tuple of (string, new_offset) where new_offset is positioned after the null terminator.
        """
        end = data.find(b'\x00', offset)
        if end == -1:
            raise ValueError("Null terminator not found in string")
        s = data[offset:end].decode("latin-1")
        return s, end + 1

    def handle_client(self, data, address):
        clientid = str(address) + ": "
        self.log.info(clientid + "Connected to CSER Server")
        self.log.debug(clientid + ("Received message: %s, from %s" % (repr(data), address)))

        command = data[:1]
        if command in self.handlers:
            self.handlers[command](address, data[2:], clientid)
        else:
            self.log.info("Unknown CSER command: %s" % data)

    def parse_upload_gamestats(self, address, data, clientid):
        self.log.info(f"{clientid}Received Unknown Upload Game Stats")
        ice = IceKey(1, [54, 175, 165, 5, 76, 251, 29, 113])
        # Decrypt the remainder of the data
        decrypted = ice.Decrypt(bytes.fromhex(data[3:].hex()))

        statistics_db.log_event('upload_gamestats',
                                {'ip': address[0], 'data': decrypted.hex()})

    def parse_app_install_stats(self, address, data, clientid):
        self.log.info(f"{clientid}Received Application Installation Stats")
        reply = b"\xFF\xFF\xFF\xFFb"
        protocol_version = data[0:1]
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

        statistics_db.log_event('app_install_stats',
                                dict(zip(keys, vals)))

        # The official server does not send a reply for this packet. Our
        # previous implementation returned a quake style header which does
        # not exist in the C++ code.  We therefore simply swallow the
        # message with no response so the behaviour matches the original
        # implementation.

    def handle_bandwidth_stats(self, address, data, clientid):
        """
        Processes the incoming bandwidth stats buffer, saves the parsed
        data to a log file in files/clientstats/bandwidthstats, and sends a reply.
        """
        self.log.info(f"{clientid}Received Client Bandwidth Stats")
        offset = 0

        version = int.from_bytes(data[0:1], "little")
        offset += 1

        # Parse cellId (4 bytes, int32)
        cellId = int.from_bytes(data[offset:offset+4], "little")
        offset += 4

        # Parse number of records (1 byte, int8)
        nbRecord = data[offset]
        offset += 1

        records = []
        for i in range(nbRecord):
            contentServerId = int.from_bytes(data[offset:offset+2], "little")
            offset += 2
            bytesCount = int.from_bytes(data[offset:offset+4], "little")
            offset += 4
            durationInSec = struct.unpack(">f", data[offset:offset+4])[0]
            offset += 4
            records.append({'server': contentServerId, 'bytes': bytesCount,
                            'duration': durationInSec})

        statistics_db.log_event('bandwidth_stats',
                                {'ip': address[0], 'version': version,
                                 'cellId': cellId, 'records': records})

        # The C++ implementation simply logs these statistics and does not
        # acknowledge the datagram.  Remove the custom ack so the behaviour is
        # compatible with the original server.

    def build_upload_reply(self, message_type, require_upload: bool = False, unique_id: int = 0) -> bytes:
        """
        Reply format the client expects (little-endian reads):
          byte 0: 'd'
          byte 1: 0x01  (protocol ok; client requires == 1)
          byte 2: 0x01  (no upload) OR 0x02 (upload)
          if byte2 == 0x02:
              u32 ip        (little-endian)
              u16 port      (little-endian)
              u32 unique_id (little-endian)
        """
        reply = bytearray()
        reply.extend(message_type)     # message type
        reply.append(0x01)         # protocol OK (must be 1)

        if not require_upload:
            reply.append(0x01)     # REPORTING_SERVER_PROTOCOL_NO_FILE_UPLOAD
            return bytes(reply)

        # pick harvest server
        if globalvars.aio_server:
            server = dirmanager.get_server_list("Harvest", False, single=1)
        else:
            server = serverlist_utilities.request_server_list("Harvest", single=1)

        if not server:
            reply.append(0x01)     # fallback: no upload server available
            return bytes(reply)

        harvest_ip, harvest_port = server[0]

        reply.append(0x02)  # REPORTING_SERVER_PROTOCOL_FILE_UPLOAD

        # Client reads IP with sub_42DF90: u32 little-endian.
        # Convert dotted IP -> 4 bytes network order -> interpret as little-endian u32 for packing.
        ip_u32_le = int.from_bytes(socket.inet_aton(harvest_ip), "little")
        reply.extend(struct.pack("<I", ip_u32_le))

        # Client reads port with parseIP: u16 little-endian.
        reply.extend(struct.pack("<H", int(harvest_port) & 0xFFFF))

        # Client reads unique id with sub_42DF90: u32 little-endian.
        reply.extend(struct.pack("<I", unique_id & 0xFFFFFFFF))

        return bytes(reply)

    def parse_gamestats(self, address, data, clientid):
        """
        // On the wire from the client (Win32UploadGameStatsBlocking):
        //   [0] = C2M_REPORT_GAMESTATISTICS
        //   [1] = '\n'
        //   [2] = protocol_version (byte)
        //
        //   if (old protocol, version=1):
        //        [3..6]   = buildNumber (int32)
        //        exeName (null-terminated string)
        //        gameDirectory (string)
        //        mapName (string)
        //        [..next4] = statsBlobVersion (int32)
        //        [..next4] = statsBlobSize (int32)
        //        [..nextN] = stats data (N bytes)
        //
        //   if (new protocol, version=2):
        //        [3..6]   = appId (int32)
        //        [7..10]  = statsBlobSize (int32)
        //        [..nextN] = stats data (N bytes)
        //
        // Then the client expects a quake-style response:
        //   [0..3]  = 0xFF,0xFF,0xFF,0xFF
        //   [4]     = 'l' (0x6C) => M2C_ACKREPORT_GAMESTATISTICS
        //   [5]     = validProtocol (0 or 1)
        //   [6]     = disposition  (0 => skip, 1 => request upload)
        //   [7..10] = harvester IP   (uint32 little-endian)
        //   [11..12]= harvester port (uint16 little-endian)
        //   [13..16]= context ID     (uint32 little-endian)
        """

        self.log.info(f"{clientid}: Received game statistics")

        # 0x6c = 'l' = M2C_ACKREPORT_GAMESTATISTICS

        # 1) Convert the raw data and skip the first 2 bytes
        data_bin = bytes(data)
        data_bin = data_bin[2:]
        if len(data_bin) < 8:
            return
        appId, upload_len = struct.unpack_from('<II', data_bin, 0)
        data_bin = data_bin[8:]
        self.log.debug(f"appId {appId} upload_len {upload_len}")
        reply = self.build_upload_reply(b'l')
        # 2) Parse the protocol version
        buffer = NetworkBuffer(data_bin)
        if buffer.remaining_length() < 1:
            # Not enough data to read protocol version
            self.log.error("GameStats packet too short to read protocol version.")
            self.serversocket.sendto(b"l\x00", address)
            return

        protover = buffer.extract_u8()
        valid_protocol = True   # assume valid for now
        old_protocol = (protover == 1)
        new_protocol = (protover == 2)

        if not (old_protocol or new_protocol):
            self.log.error(f"Unknown GameStats protocol version: {protover}")
            self.serversocket.sendto(b"l\x00", address)
            return

        # 3) Parse the rest depending on old vs new layout
        build_number = None
        exe_name = None
        game_directory = None
        map_name = None
        stats_blob_version = None
        app_id = None
        stats_blob_size = 0

        if old_protocol:
            # buildNumber (int32)
            build_number = buffer.extract_u32()

            # read zero-terminated strings
            exe_name = buffer.extract_string()
            game_directory = buffer.extract_string()
            map_name = buffer.extract_string()

            # statsBlobVersion (int32)
            stats_blob_version = buffer.extract_u32()

            # statsBlobSize (int32)
            stats_blob_size = buffer.extract_u32()

        else:  # new_protocol => version == 2
            # appId (int32)
            app_id = buffer.extract_u32()
            # statsBlobSize (int32)
            stats_blob_size = buffer.extract_u32()

        # 4) Extract the stats data
        if stats_blob_size < 0 or stats_blob_size > buffer.remaining_length():
            self.log.error(f"Stats blob size invalid: {stats_blob_size} (remaining={buffer.remaining_length()})")
            self.serversocket.sendto(b"l\x00", address)
            return

        stats_blob = buffer.extract_buffer(stats_blob_size)

        # 5) Store data in the database instead of writing to files
        details = {
            'protover': protover,
            'build_number': build_number,
            'exe_name': exe_name,
            'game_directory': game_directory,
            'map_name': map_name,
            'stats_blob_version': stats_blob_version,
            'app_id': app_id,
            'stats_blob_size': stats_blob_size,
            'stats_blob_hex': stats_blob.hex()
        }

        statistics_db.log_event('gamestats', details)

        self.serversocket.sendto(reply, address)

    def parse_bugreport(self, address, data, clientid):
        self.log.info("Received bug report")

        # Convert incoming data to binary.
        data_bin = bytes.fromhex(data.hex())
        buffer = NetworkBuffer(data_bin)

        # Extract header: u8 (protocol version) and u16 (encrypted length).
        protocol_version = buffer.extract_u8()
        encryptedlen = buffer.extract_u16()

        if protocol_version not in [1, 2, 3]:
            self.log.warning(f"{clientid} sent a bug report with an invalid protocol version! Version: {protocol_version}")
            self.serversocket.sendto(b"\xff\xff\xff\xffp" + b"\x00\x00", address)
            return

        # Decrypt the remainder.
        ice = IceKey(1, [200, 145, 10, 149, 195, 190, 108, 243])
        decrypted = ice.Decrypt(buffer.get_buffer_from_cursor())
        self.log.info(f"Decrypted Bug Report Packet: {decrypted}")

        try:
            # Reinitialize buffer with the decrypted payload.
            parser_obj = NetworkBuffer(decrypted)
            report = {}

            # Always-present fields:
            report['corruption_identifier'] = parser_obj.extract_u8()
            report['build_number'] = parser_obj.extract_u32()
            report['executable_name'] = parser_obj.extract_string()
            report['game_directory'] = parser_obj.extract_string()
            report['map_name'] = parser_obj.extract_string()
            report['ram'] = parser_obj.extract_u32()
            report['cpu'] = parser_obj.extract_u32()
            report['processor'] = parser_obj.extract_string()
            report['dx_version_high'] = parser_obj.extract_u32()
            report['dx_version_low'] = parser_obj.extract_u32()
            report['dx_vendor_id'] = parser_obj.extract_u32()
            report['dx_device_id'] = parser_obj.extract_u32()
            report['os_version'] = parser_obj.extract_string()
            report['attachment_file_size'] = parser_obj.extract_u32()

            # Protocol v2+ fields:
            if protocol_version >= 2:
                report['report_type'] = parser_obj.extract_string()
                report['email'] = parser_obj.extract_string()
                report['account_name'] = parser_obj.extract_string()

                # Protocol v3+ field:
                if protocol_version >= 3:
                    user_id_bytes = parser_obj.extract_buffer(8)
                    report['user_id'] = int.from_bytes(user_id_bytes, byteorder='little')
            else:
                report['report_type'] = ""
                report['email'] = ""
                report['account_name'] = ""
                report['user_id'] = None

            # Always-present fields after protocol extras:
            report['title'] = parser_obj.extract_string()
            report['body_length'] = parser_obj.extract_u32()
            body_bytes = parser_obj.extract_buffer(report['body_length'])
            report['body'] = body_bytes.decode('utf-8', errors='replace')

            # Compose the bug report text.
            bugreport_text = f"Protocol {protocol_version}\n"
            bugreport_text += f"Corruption ID: {report['corruption_identifier']}\n"
            bugreport_text += f"Build Number: {report['build_number']}\n"
            bugreport_text += f"Executable: {report['executable_name']}\n"
            bugreport_text += f"Game Directory: {report['game_directory']}\n"
            bugreport_text += f"Map: {report['map_name']}\n"
            bugreport_text += f"RAM: {report['ram']}\n"
            bugreport_text += f"Processor (MHz): {report['cpu']}\n"
            bugreport_text += f"Processor: {report['processor']}\n"
            bugreport_text += f"DirectX Version: {report['dx_version_high']}.{report['dx_version_low']}\n"
            bugreport_text += f"DirectX VendorID: {report['dx_vendor_id']}\n"
            bugreport_text += f"DirectX DeviceID: {report['dx_device_id']}\n"
            bugreport_text += f"Operating System: {report['os_version']}\n"
            bugreport_text += f"Attachment File Size: {report['attachment_file_size']}\n"
            if protocol_version >= 2:
                bugreport_text += f"Report Type: {report['report_type']}\n"
                bugreport_text += f"Email Address: {report['email']}\n"
                bugreport_text += f"Account Name: {report['account_name']}\n"
                if protocol_version >= 3:
                    bugreport_text += f"SteamID: {report['user_id']}\n"
            bugreport_text += f"Title: {report['title']}\n"
            bugreport_text += f"Body Length: {report['body_length']}\n"
            bugreport_text += f"Body: {report['body']}\n"

        except Exception as e:
            self.log.error(f"Error parsing bug report: {e}")
            return

        statistics_db.log_event('bugreport', report)
        reply = self.build_upload_reply(b"p")

        self.serversocket.sendto(reply, address)

    def parse_crashreport(self, address, data, clientid):
        self.log.info(f"{clientid}Received client crash report")

        ipstr = str(address)
        ipstr1 = ipstr.split('\'')
        ipactual = ipstr1[1]

        packet = data
        # Convert hex message to binary data and split by null terminator
        offset = 0
        result = {}

        # Read fields using byte slicing.
        # packet[0] is the crashreport request protocol (client sends 2)
        result["ReqProto"] = packet[offset]
        offset += 1
        if result["ReqProto"] != 2:
            self.log.warning(f"{clientid}Crashreport: unexpected req proto {result['ReqProto']}")

        # readInt8: Version
        result["Version"] = packet[offset]
        offset += 1

        # readInt32: Build
        result["Build"] = int.from_bytes(packet[offset:offset + 4], "little")
        offset += 4

        # readString: ExeName
        result["ModuleName"], offset = self.read_string(packet, offset)

        # readString: ModuleName
        result["FileName"], offset = self.read_string(packet, offset)

        # readString: SourceFileName
        result["SourceFileName"], offset = self.read_string(packet, offset)

        # readInt32: CrashAddress
        result["CrashAddress"] = int.from_bytes(packet[offset:offset + 4], "little")
        offset += 4

        # readInt32: ErrorCode
        result["ErrorCode"] = int.from_bytes(packet[offset:offset + 4], "little")
        offset += 4

        # readInt32: Unknown2
        result["Unknown2"] = int.from_bytes(packet[offset:offset + 4], "little")
        offset += 4

        # readString: Type
        result["Type"], offset = self.read_string(packet, offset)

        # readInt32: MinidumpSize
        result["MinidumpSize"] = int.from_bytes(packet[offset:offset + 4], "little")
        offset += 4

        # readString: Os
        result["Os"], offset = self.read_string(packet, offset)

        # readInt16: Unknown3
        result["Unknown3"] = int.from_bytes(packet[offset:offset + 2], "little")
        offset += 2

        # readInt16: Unknown4
        result["Unknown4"] = int.from_bytes(packet[offset:offset + 2], "little")
        offset += 2

        # readInt8: Unknown5
        result["Unknown5"] = packet[offset]
        offset += 1

        # If version == 3, read an extra Unknown6 (int32)
        if result["Version"] == 3:
            result["Unknown6"] = int.from_bytes(packet[offset:offset + 4], "little")
            offset += 4

        # Read reason length (DWORD) - we ignore its value
        result["ReasonLength"] = int.from_bytes(packet[offset:offset + 4], "little")
        offset += 4

        # readString: Reason
        result["Reason"], offset = self.read_string(packet, offset)

        if result["ReasonLength"] != len(result["Reason"]):
            self.log.debug("Crashreport: reason length mismatch (expected %d, got %d)",
                           result["ReasonLength"], len(result["Reason"]))

        statistics_db.log_event('crashreport', result)
        require_upload = (result["MinidumpSize"] > 0)
        reply = self.build_upload_reply(b"d")

        self.serversocket.sendto(reply, address)

    def parse_uploaddata(self, address, data, clientid):
        """
        // Packet layout from client (BuildUploadDataMessage):
        //  [0] = C2M_UPLOADDATA
        //  [1] = '\n'
        //  [2] = C2M_UPLOADDATA_PROTOCOL_VERSION == 1
        //  [3..4] = encrypted_length (little-endian)
        //  [5..end] = encrypted data
        //
        // Encrypted payload format:
        //  [0] = corruption_id (0x01)
        //  [1] = data_version (1)
        //  [2..N] = tablename (null-terminated)
        //           num_values (u8)
        //           for each value => field_name, field_value (both null-terminated)
        //           (padded to multiple of 8 bytes)
        """

        self.log.info(f"{clientid} Received encrypted bug report stats")

        # 1) Convert the raw UDP data into bytes
        data_bin = bytes(data)  # or bytes.fromhex(data.hex()), both effectively the same
        # 2) Skip the first 2 bytes: [C2M_UPLOADDATA, '\n']
        data_bin = data_bin[2:]

        # 3) Parse protocol_version + encrypted_length
        buffer = io.BytesIO(data_bin)

        protocol_version = struct.unpack("B", buffer.read(1))[0]
        self.log.debug(f"protocol version: {protocol_version}")

        encrypted_length = struct.unpack("<H", buffer.read(2))[0]
        self.log.debug(f"encrypted length: {encrypted_length}")

        # 4) Read the next `encrypted_length` bytes (the encrypted payload)
        encrypted_data = buffer.read(encrypted_length)

        # 5) Decrypt using the exact same key as the client
        ice_key = IceKey(1, [54, 175, 165, 5, 76, 251, 29, 113])
        decrypted = ice_key.Decrypt(encrypted_data)

        self.log.debug(f"Encrypted raw: {encrypted_data}\nDecrypted: {decrypted}")

        # 6) Parse fields from the decrypted buffer
        buffer = io.BytesIO(decrypted)

        corruption_id = struct.unpack("B", buffer.read(1))[0]
        data_version = struct.unpack("B", buffer.read(1))[0]

        try:
            tablename = read_string_until_null(buffer)
            num_values = struct.unpack("B", buffer.read(1))[0]

            values = []
            for _ in range(num_values):
                fieldname = read_string_until_null(buffer)
                value = read_string_until_null(buffer)

                # Example: if a field name is "StatTimestamp", convert int->datetime
                if fieldname == b'StatTimestamp':
                    value = self.int_to_datetime_bytes(value)

                values.append((fieldname, value))

            decoded_values = [(f.decode('latin1'), v) for f, v in values]
            statistics_db.log_event('uploaddata', {
                'tablename': tablename.decode('latin1'),
                'corruption_id': corruption_id,
                'data_version': data_version,
                'values': decoded_values})
        except:
            pass
        finally:
            # The reference implementation does not acknowledge this packet.
            # Remove the custom quake-style response for compatibility.
            pass

    def parse_steamstats(self, address, data, clientid):
        self.log.info(f"{clientid}Received steam stats")
        offset = 0

        # Read version (1 byte, int8)
        version = data[offset]
        offset += 1

        if version != 1:
            self.log.error(f"Invalid version: {version}")
            return

        # Read the client string
        client, offset = self.read_string(data, offset)

        # Read the 7 int32 values (little-endian)
        successCount          = int.from_bytes(data[offset:offset+4], "little")
        offset += 4
        unknownFailureCount   = int.from_bytes(data[offset:offset+4], "little")
        offset += 4
        shutdownFailureCount  = int.from_bytes(data[offset:offset+4], "little")
        offset += 4
        uptimeCleanCounter    = int.from_bytes(data[offset:offset+4], "little")
        offset += 4
        uptimeCleanTotal      = int.from_bytes(data[offset:offset+4], "little")
        offset += 4
        uptimeFailureCounter  = int.from_bytes(data[offset:offset+4], "little")
        offset += 4
        uptimeFailureTotal    = int.from_bytes(data[offset:offset+4], "little")
        offset += 4

        # Prepare parsed stats in a dictionary.
        parsed = {
            "Client": client,
            "SuccessCount": successCount,
            "UnknownFailureCount": unknownFailureCount,
            "ShutdownFailureCount": shutdownFailureCount,
            "UptimeCleanCounter": uptimeCleanCounter,
            "UptimeCleanTotal": uptimeCleanTotal,
            "UptimeFailureCounter": uptimeFailureCounter,
            "UptimeFailureTotal": uptimeFailureTotal
        }

        statistics_db.log_event('steamstats', parsed)
        # The native server does not emit an acknowledgement for this packet.
        # Send response back to client.
        # self.serversocket.sendto(b"\xFF\xFF\xFF\xFFf", address)

    def parse_phonehome(self, address, data, clientid):
        """
        // Layout of raw, unencrypted data from client:
        //  [0] = C2M_PHONEHOME (0x01)
        //  [1] = '\n' (0x0A)
        //  [2] = C2M_PHONEHOME_PROTOCOL_VERSION (byte)
        //  [3..6]  = session_id (uint32)
        //  [7..8]  = encrypted_length (uint16)
        //  [9..end] = encrypted data

        // Inside the encrypted portion, the C++ code writes:
        //  [0] = corruption_id (u8) => 0x01
        //  [1] = data_version (u8)
        //  [2..N] = build_identifier (string)
        //           computer_name (string)
        //           username (string)
        //           game_dir (string)
        //           build_number (int32)
        //           engine_timestamp (float)
        //           message_type (u8)
        //           if message_type in (3,4) => map_name (string)
        //           isDebugUser (u8)
        //           (padding to 8-byte multiple)
        """
        self.log.info(f"{clientid} Received Phone Home")

        #
        # 1) Skip the first 2 bytes: [C2M_PHONEHOME, '\n']
        #    so the next byte we read is the protocol version.
        #
        data_bin = data[2:]  # was data[3:] previously

        # Prepare a small quake-style header for our reply
        # The C++ code expects to see something that ultimately yields
        # responseType == 0x6E (M2C_ACKPHONEHOME) after discarding quake?s 4x 0xFF.
        reply_header = b"\xFF\xFF\xFF\xFF\x6E"

        buffer = NetworkBuffer(data_bin)

        # 2) Parse protocol_version, session_id, encrypted_length.
        protocol_version = buffer.extract_u8()   # This is now the correct byte
        session_id = buffer.extract_u32()
        encrypted_length = buffer.extract_u16()
        encrypted_data = buffer.extract_buffer(encrypted_length)

        #
        # 3) Decrypt the remainder using the correct ICE key
        #    The C++ code uses:
        #    unsigned char ucEncryptionKey[8] = {191, 1, 0, 222, 85, 39, 154, 1};
        #
        ice = IceKey(1, [191, 1, 0, 222, 85, 39, 154, 1])
        decrypted = ice.Decrypt(encrypted_data)

        buffer = NetworkBuffer(decrypted)

        # 4) Read the encrypted fields in the order they're written by the client
        corruption_id = buffer.extract_u8()      # 0x01
        data_version = buffer.extract_u8()       # e.g. 1

        build_id = buffer.extract_string()       # "build_identifier"
        computer_name = buffer.extract_string()
        username = buffer.extract_string()
        game_dir = buffer.extract_string()

        build_number = buffer.extract_u32()      # int32 build number
        engine_timestamp = buffer.extract_float()# float( realtime )
        message_type = buffer.extract_u8()

        # If message_type is 3 or 4, the client wrote a map_name string
        map_name = ""
        if message_type in (3, 4):
            map_name = buffer.extract_string()

        # The client always writes isDebugUser (byte) after the optional map name
        is_debug_user = buffer.extract_u8()

        # 5) Validate the session ID if not zero
        is_match = globalvars.session_id_manager.match_byte_string(session_id)
        if session_id != 0 and not is_match:
            self.log.warning(
                f"{clientid} Session ID does not match any known previous IDs! {session_id}"
            )
            # The server tells the client to discard / fail
            self.serversocket.sendto(reply_header + b"\x00", address)
            return

        # 6) If session_id == 0, create a new one
        if session_id == 0:
            session_id = globalvars.session_id_manager.add_new_context_id(address[0])

        # 7) Log the extracted data
        self.log.info(f"{clientid} Decrypted phonehome packet => "
                      f"prot_ver={protocol_version}, corruption_id={corruption_id}, "
                      f"data_ver={data_version}, build_id={build_id}, comp={computer_name}, "
                      f"user={username}, game_dir={game_dir}, build_number={build_number}, "
                      f"engine_ts={engine_timestamp}, msg_type={message_type}, map={map_name}, "
                      f"isDebug={is_debug_user}, session_id={session_id}")

        # 8) Write extracted data to a file
        extracted_data = {
            "protocol_version": protocol_version,
            "session_id": session_id,
            "encrypted_length": encrypted_length,
            "corruption_id": corruption_id,
            "data_version": data_version,
            "build_id": build_id,
            "computer_name": computer_name,
            "username": username,
            "game_dir": game_dir,
            "build_number": build_number,
            "engine_timestamp": engine_timestamp,
            "message_type": message_type,
            "map_name": map_name,
            "is_debug_user": is_debug_user
        }
        statistics_db.log_event('phonehome', extracted_data)

        #
        # 9) Send back:  quake-style header + (allowPlay=1) + session_id (4 bytes)
        #
        # The C++ code (host_phonehome.cpp) does:
        #   responseType = replybuf.ReadByte();  // expecting 0x6E
        #   bool allowPlay = replybuf.ReadByte() == 1; // next byte
        #   session_id = replybuf.ReadLong(); // next 4 bytes
        #
        # So we need:  [FF,FF,FF,FF, 6E, 01, <4 bytes sessionID> ]
        #
        ack_payload = reply_header + b"\x01" + struct.pack("<I", session_id)

        self.serversocket.sendto(ack_payload, address)

    def parse_surveyresults(self, address, data, clientid):
        self.log.info(f'{clientid}Recieved Survey Results')

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
            if data[0:1] == b"\x02":

                # Client ID
                result['clientid'], index = self.read_string(byte_string, index)

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
                result['videodriverdll'], index = self.read_string(byte_string, index)

                # Skip 1 byte
                index += 1

                # Video Card
                result['videocard'], index = self.read_string(byte_string, index)

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
                result['proctype'], index = self.read_string(byte_string, index)

                # Logical Processor Count, Physical Processor Count, Hyper-Threading
                result['logicalprocessorcount'], index = byte_string[index], index + 1

                result['physicalproccesorcount'], index = byte_string[index], index + 1

                result['hyperthreading'], index = byte_string[index], index + 1

                # AGP String
                result['agpstr'], index = self.read_string(byte_string, index)

                # Bus Speed
                result['bus_speed'], index = struct.unpack('>I', byte_string[index:index + 4])[0], index + 4

                # Windows Version
                result['winver'], index = self.read_string(byte_string, index)

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

                result['clientid'], index = self.read_string(byte_string, index)

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

                result['adapter'], index = self.read_string(byte_string, index)

                result['driver_version'], index = self.read_string(byte_string, index)

                result['video_card'], index = self.read_string(byte_string, index)

                result['directx_videocard_driver'], index = self.read_string(byte_string, index)

                result['directx_videocard_version'], index = self.read_string(byte_string, index)

                result['msaa_modes'], index = self.read_string(byte_string, index)

                result['monitor_vendor'], index = self.read_string(byte_string, index)

                result['monitor_model'], index = self.read_string(byte_string, index)

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

                result['cpu_vendor'], index = self.read_string(byte_string, index)

                result['physical_processors'], index = byte_string[index], index + 1

                result['logical_processors'], index = byte_string[index], index + 1

                result['hyperthreading'], index = byte_string[index], index + 1

                result['agp'], index = self.read_string(byte_string, index)

                result['bus_speed'], index = struct.unpack('>I', byte_string[index:index + 4])[0], index + 4

                result['os_version'], index = self.read_string(byte_string, index)

                result['audio_device'], index = struct.unpack('>I', byte_string[index:index + 4])[0], index + 4

                result['ip2'], index = byte_string[index], index + 1

                result['ip1'], index = byte_string[index], index + 1

                result['ip0'], index = byte_string[index], index + 1

                result['language_id'], index = byte_string[index], index + 1

                result['drive_type'], index = byte_string[index], index + 1

                result['free_hd_space'], index = struct.unpack('>I', byte_string[index:index + 4])[0], index + 4

                result['total_hd_space'], index = struct.unpack('>I', byte_string[index:index + 4])[0], index + 4
                drives = []
                while index + 4 <= len(byte_string):
                    drive, = struct.unpack('>I', byte_string[index:index + 4])
                    drives.append(drive)
                    index += 4
                result['drives'] = drives

            statistics_db.record_s3surveydata(result)

            self.serversocket.sendto(b"\xFF\xFF\xFF\xFF\x68\x01\x00\x00\x00" + b"thank you\x00", address)
