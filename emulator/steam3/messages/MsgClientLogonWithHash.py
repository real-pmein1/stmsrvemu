"""packetid: ClientLogOnWithHash_Deprecated (5465)
data: b'\x17\x00\x01\x00M\x1d*\xf2\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x8a\x01\x00\x00test\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00
\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00
\x00OYNg>Q[M"t*fLad7F#2\x00\x00\x00\x00\x00\xb4\x03\xa8\xc0\x00\x02\x00\x80testtest\x00\x01\xb4\x03\xa8\xc0\xc0\xa8\x03\xb4\xc0\xa8\x03\xb4\xa0i\xc0\xa8\x03\xb4\xa0i\xb4
\xa3g:\'\xafS\x8a\xc1\x16\x0e\xf8\xebw\x07Q\x80=V\x18;\xe7\xe2\x00\x80\xf8D\xb9;\xe7\xe2\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00
\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00
\x00\x00\x00\x99:\xb9\xa4\xccDG\xe3\xee\xe5~o\xaf\x97\xbd\xd8\x00R\x00`\x00\x00\x00\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00
\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00
\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x10\x01\x00\x00\x00\x00\x00\x00\x00\xc0\xa8\x03\xb4\x00
\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00
\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00
\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00test@test.com\x00
english\x00}\x051g\x00\x00\x00\x00\x01\x00\x00\x00\xd1\x03\x00\x00\x02\x00\x00\x00\x00\x00\x00\x00\x01'"""
import struct
import socket

import globalvars
from steam3.Types.MessageObject import MessageObject
from steam3.Types.MessageObject.MachineID import MachineID
from steam3.utilities import reverse_bytes, uint32_to_time
from utilities import ticket_utils

class ClientLogonWithHash:
    def __init__(self, data = None):
        self.protocol = None
        self.obfuscated_ip = None
        self.public_ip = None
        self.steam_global_id = None
        self.ticket_length = None
        self.username = None
        self.login_key = None
        self.qos_level = None
        self.ticket = None
        self.email = None
        self.language = None
        self.account_creation_time = None
        self.machine_id_available = None
        self.machine_id = None
        self.version_set_flag = None
        self.steamui_version = None
        self.cellid = None
        self.last_sessionID = None
        self.remember_password = None

        if data:
            self.deserialize(data)
    def deserialize(self, data):
        """
        Deserializes a byte string into the fields of the ClientLogonWithHash class.
        """
        offset = 0
        try:
            # Read protocol version (int32)
            self.protocol = struct.unpack_from('<I', data, offset)[0]
            offset += 4

            # Read private IP (int32, XOR with 0xBAADF00D)
            self.obfuscated_ip = struct.unpack_from('<I', data, offset)[0]
            self.obfuscated_ip = socket.inet_ntoa(int.to_bytes(reverse_bytes(self.obfuscated_ip ^ 0xBAADF00D), length = 4, byteorder = "little"))

            offset += 4

            # Read public IP (int32)
            self.public_ip = struct.unpack_from('<I', data, offset)[0]
            offset += 4

            # Read Steam Global ID (int64)
            self.steam_global_id = struct.unpack_from('<Q', data, offset)[0]
            offset += 8

            # Read ticket size (int32)
            self.ticket_length = struct.unpack_from('<I', data, offset)[0]
            offset += 4

            # Read account name until the first null byte
            username_end = data.find(b'\x00', offset)
            if username_end == -1:  # Handle case where null byte is not found
                raise ValueError("ClientLogonWithHash: Null-terminated account name not found in data.")
            self.username = data[offset:username_end].decode('ascii')
            offset += 64  # Move past the null byte

            # Read authentication field (fixed-size buffer)
            login_key_end = data.find(b'\x00', offset)
            if login_key_end == -1:  # Handle case where null byte is not found
                raise ValueError("ClientLogonWithHash: Null-terminated Login Key not found in data.")
            self.login_key = data[offset:login_key_end].decode('ascii')
            offset += len(self.login_key) + 1

            # Read ticket bound to IP (int32)
            self.qos_level = struct.unpack_from('<I', data, offset)[0]
            offset += 4

            # Read server-readable ticket (size based on ticket size)
            ticket = data[offset:offset + self.ticket_length]
            offset += self.ticket_length
            self.ticket = ticket_utils.Steam2Ticket(ticket[4:])

            # Read email (null-terminated string)
            email_end = data.find(b'\x00', offset)
            self.email = data[offset:email_end].decode('ascii')
            offset = email_end + 1

            # Read interface language (null-terminated string)
            language_end = data.find(b'\x00', offset)
            self.language = data[offset:language_end].decode('ascii')
            offset = language_end + 1

            # Read account creation timestamp (int32)
            self.account_creation_time = struct.unpack_from('<I', data, offset)[0]
            offset += 4

            # Read machine ID info available (int32)
            self.machine_id_available = struct.unpack_from('<I', data, offset)[0]
            offset += 4

            # If machine ID info is available, read it (placeholder for actual parsing)
            if self.machine_id_available:
                self.machine_id = MessageObject(data[offset:])
                self.machine_id.parse()
                index = data.find(b"\x08\x08", offset)
                if index == -1:
                    raise ValueError("MachineID sequence not found")
                offset = index + 2
                """self.machine_id = data[offset:offset + 64]  # Example size for machine ID info
                offset += 64"""

            # Read client app version known flag (int32)
            self.version_set_flag = struct.unpack_from('<I', data, offset)[0]
            offset += 4

            # If client app version is known, read it (int32)
            if self.version_set_flag:
                self.steamui_version = struct.unpack_from('<I', data, offset)[0]
                offset += 4

            # Read cell ID (int32)
            self.cellid = struct.unpack_from('<I', data, offset)[0]
            offset += 4

            # Read last session ID (int32)
            self.last_sessionID = struct.unpack_from('<I', data, offset)[0]
            offset += 4

            # Read remember my password (int8)
            self.remember_password = struct.unpack_from('<B', data, offset)[0] != 0
            offset += 1

            if len(data[offset:]) > 0:
                raise ValueError(f"ClientLogonWithHash: Extra data found after deserialization: {data[offset:]}")

        except struct.error as e:
            raise ValueError(f"Error deserializing ClientLogonWithHash: {e}")

    def __str__(self):
        """
        Returns a human-readable string representation of the object using commas.
        """
        return (
                f"ClientLogonWithHash("
                f"Protocol Version: {self.protocol}, "
                f"Private IP: {self.obfuscated_ip}, "
                f"Public IP: {self.public_ip}, "
                f"Steam Global ID: {self.steam_global_id}, "
                f"Ticket Size: {self.ticket_length}, "
                f"Account Name: {self.username}, "
                f"Login Key: {self.login_key}, "
                f"QOS Level: {self.qos_level}, "
                f"Server Readable Ticket: {self.ticket if self.ticket else 'None'}, "
                f"Email: {self.email}, "
                f"Interface Language: {self.language}, "
                f"Account Creation Timestamp: {self.account_creation_time}, "
                f"Machine ID Info Available: {self.machine_id_available}, "
                f"Machine ID Info: {self.machine_id}, "
                f"Client App Version Known: {self.version_set_flag}, "
                f"Client App Version: {self.steamui_version}, "
                f"Cell ID: {self.cellid}, "
                f"Last Session ID: {self.last_sessionID}, "
                f"Remember My Password: {self.remember_password}"
                f")"
        )