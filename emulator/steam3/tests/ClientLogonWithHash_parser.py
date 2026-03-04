import struct

class ClientLogonWithHash:
    def __init__(self):
        self.protocol_version = None
        self.private_ip = None
        self.public_ip = None
        self.steam_global_id = None
        self.ticket_size = None
        self.account_name = None
        self.login_key = None
        self.ticket_bound_to_ip = None
        self.server_readable_ticket = None
        self.email = None
        self.interface_language = None
        self.account_creation_timestamp = None
        self.machine_id_info_available = None
        self.machine_id_info = None
        self.client_app_version_is_known = None
        self.client_app_version = None
        self.cell_id = None
        self.last_session_id = None
        self.remember_my_password = None

    def deserialize(self, data):
        """
        Deserializes a byte string into the fields of the ClientLogonWithHash class.
        """
        offset = 0
        try:
            # Read protocol version (int32)
            self.protocol_version = struct.unpack_from('<I', data, offset)[0]
            offset += 4

            # Read private IP (int32, XOR with 0xBAADF00D)
            self.private_ip = struct.unpack_from('<I', data, offset)[0] ^ 0xBAADF00D
            offset += 4

            # Read public IP (int32)
            self.public_ip = struct.unpack_from('<I', data, offset)[0]
            offset += 4

            # Read Steam Global ID (int64)
            self.steam_global_id = struct.unpack_from('<Q', data, offset)[0]
            offset += 8

            # Read ticket size (int32)
            self.ticket_size = struct.unpack_from('<I', data, offset)[0]
            offset += 4

            # Read account name until the first null byte
            account_name_end = data.find(b'\x00', offset)
            if account_name_end == -1:  # Handle case where null byte is not found
                raise ValueError("ClientLogonWithHash: Null-terminated account name not found in data.")
            self.account_name = data[offset:account_name_end]
            offset += 64  # Move past the null byte

            # Read authentication field (fixed-size buffer)
            login_key_end = data.find(b'\x00', offset)
            if login_key_end == -1:  # Handle case where null byte is not found
                raise ValueError("ClientLogonWithHash: Null-terminated Login Key not found in data.")
            self.login_key = data[offset:login_key_end]
            offset += len(self.login_key) + 1

            # Read ticket bound to IP (int32)
            self.ticket_bound_to_ip = struct.unpack_from('<I', data, offset)[0]
            offset += 4

            # Read server-readable ticket (size based on ticket size)
            self.server_readable_ticket = data[offset:offset + self.ticket_size]
            offset += self.ticket_size

            # Read email (null-terminated string)
            email_end = data.find(b'\x00', offset)
            self.email = data[offset:email_end]
            offset = email_end + 1

            # Read interface language (null-terminated string)
            language_end = data.find(b'\x00', offset)
            self.interface_language = data[offset:language_end]
            offset = language_end + 1

            # Read account creation timestamp (int32)
            self.account_creation_timestamp = struct.unpack_from('<I', data, offset)[0]
            offset += 4

            # Read machine ID info available (int32)
            self.machine_id_info_available = struct.unpack_from('<I', data, offset)[0]
            offset += 4

            # If machine ID info is available, read it (placeholder for actual parsing)
            if self.machine_id_info_available:
                self.machine_id_info = data[offset:offset + 64]  # Example size for machine ID info
                offset += 64

            # Read client app version known flag (int32)
            self.client_app_version_is_known = struct.unpack_from('<I', data, offset)[0]
            offset += 4

            # If client app version is known, read it (int32)
            if self.client_app_version_is_known:
                self.client_app_version = struct.unpack_from('<I', data, offset)[0]
                offset += 4

            # Read cell ID (int32)
            self.cell_id = struct.unpack_from('<I', data, offset)[0]
            offset += 4

            # Read last session ID (int32)
            self.last_session_id = struct.unpack_from('<I', data, offset)[0]
            offset += 4

            # Read remember my password (int8)
            self.remember_my_password = struct.unpack_from('<B', data, offset)[0] != 0
            offset += 1

            if len(data[offset:]) > 0:
                raise ValueError(f"ClientLogonWithHash: Extra data found after deserialization: {data[offset:]}")

        except struct.error as e:
            raise ValueError(f"Error deserializing ClientLogonWithHash: {e}")

    def __str__(self):
        """
        Returns a human-readable string representation of the object.
        """
        return (
            f"ClientLogonWithHash(\n"
            f"  Protocol Version: {self.protocol_version}\n"
            f"  Private IP: {self.private_ip}\n"
            f"  Public IP: {self.public_ip}\n"
            f"  Steam Global ID: {self.steam_global_id}\n"
            f"  Ticket Size: {self.ticket_size}\n"
            f"  Account Name: {self.account_name}\n"
            f"  Authentication Field: {self.authentication_field}\n"
            f"  QoS Level: {self.qos_level}\n"
            f"  Ticket Bound to IP: {self.ticket_bound_to_ip}\n"
            f"  Server Readable Ticket: {self.server_readable_ticket.hex()}\n"
            f"  Email: {self.email}\n"
            f"  Interface Language: {self.interface_language}\n"
            f"  Account Creation Timestamp: {self.account_creation_timestamp}\n"
            f"  Machine ID Info Available: {self.machine_id_info_available}\n"
            f"  Machine ID Info: {self.machine_id_info}\n"
            f"  Client App Version Known: {self.client_app_version_is_known}\n"
            f"  Client App Version: {self.client_app_version}\n"
            f"  Cell ID: {self.cell_id}\n"
            f"  Last Session ID: {self.last_session_id}\n"
            f"  Remember My Password: {self.remember_my_password}\n"
            f")"
        )


# Example data (placeholder binary string)
example_data = b'\x17\x00\x01\x00M\x1d*\xf2\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x8a\x01\x00\x00test\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00OYNg>Q[M"t*fLad7F#2\x00\x00\x00\x00\x00\xb4\x03\xa8\xc0\x00\x02\x00\x80testtest\x00\x01\xb4\x03\xa8\xc0\xc0\xa8\x03\xb4\xc0\xa8\x03\xb4\xa0i\xc0\xa8\x03\xb4\xa0i\xb4\xa3g:\'\xafS\x8a\xc1\x16\x0e\xf8\xebw\x07Q\x80=V\x18;\xe7\xe2\x00\x80\xf8D\xb9;\xe7\xe2\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x99:\xb9\xa4\xccDG\xe3\xee\xe5~o\xaf\x97\xbd\xd8\x00R\x00`\x00\x00\x00\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x10\x01\x00\x00\x00\x00\x00\x00\x00\xc0\xa8\x03\xb4\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00test@test.com\x00english\x00}\x051g\x00\x00\x00\x00\x01\x00\x00\x00\xd1\x03\x00\x00\x02\x00\x00\x00\x00\x00\x00\x00\x01'

client_logon = ClientLogonWithHash()
client_logon.deserialize(example_data)
print(client_logon)


print(len(b'test\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'))