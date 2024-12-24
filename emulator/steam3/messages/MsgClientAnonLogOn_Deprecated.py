import struct

class MsgClientAnonLogOn_Deprecated:
    def __init__(self, data: bytes):
        self.protocol_version = None
        self.private_ip = None
        self.public_ip = None
        self.steam_id = None
        self.ticket_length = None
        self.ticket = None
        self.email = None
        self.language = None
        self.client_version = None
        self.remaining_bytes = None

        self._deserialize(data)

    def _deserialize(self, data: bytes):
        """
        Deserialize the MsgClientAnonLogOn structure from a byte stream.
        """
        buffer = memoryview(data)
        cursor = 0

        try:
            # Protocol version (4 bytes)
            self.protocol_version = buffer[cursor:cursor + 4].tobytes()
            cursor += 4

            # Private IP (4 bytes, deobfuscated)
            private_ip_obfuscated = buffer[cursor:cursor + 4].tobytes()
            self.private_ip = struct.unpack('<I', private_ip_obfuscated)[0] ^ 0xBAADF00D
            cursor += 4

            # Public IP (4 bytes)
            self.public_ip = struct.unpack('<I', buffer[cursor:cursor + 4])[0]
            cursor += 4

            # SteamID (8 bytes)
            self.steam_id = struct.unpack('<Q', buffer[cursor:cursor + 8])[0]
            cursor += 8

            # Ticket length (4 bytes)
            self.ticket_length = struct.unpack('<I', buffer[cursor:cursor + 4])[0]
            cursor += 4

            # Ticket (if ticket length > 0, read until null byte)
            if self.ticket_length > 0:
                ticket_end = buffer[cursor:].tobytes().find(b'\x00')
                if ticket_end == -1:
                    raise ValueError("Null terminator not found for ticket.")
                self.ticket = buffer[cursor:cursor + ticket_end].tobytes()
                cursor += ticket_end + 1  # Skip the null byte
            else:
                self.ticket = None

            # Email (read until null byte)
            email_end = buffer[cursor:].tobytes().find(b'\x00')
            if email_end == -1:
                raise ValueError("Null terminator not found for email.")
            self.email = buffer[cursor:cursor + email_end].tobytes().decode('utf-8')
            cursor += email_end + 1  # Skip the null byte

            # Language (read until null byte)
            lang_end = buffer[cursor:].tobytes().find(b'\x00')
            if lang_end == -1:
                raise ValueError("Null terminator not found for language.")
            self.language = buffer[cursor:cursor + lang_end].tobytes().decode('utf-8')
            cursor += lang_end + 1  # Skip the null byte

            # 4-byte null padding
            null_padding = buffer[cursor:cursor + 4].tobytes()
            if null_padding != b'\x00\x00\x00\x00':
                raise ValueError("Expected 4-byte null padding.")
            cursor += 4

            # 1-byte null padding
            if buffer[cursor] != 0:
                raise ValueError("Expected 1-byte null padding.")
            cursor += 1

            # Client version (4 bytes)
            self.client_version = struct.unpack('<I', buffer[cursor:cursor + 4])[0]
            cursor += 4

            # Remaining bytes
            self.remaining_bytes = buffer[cursor:].tobytes()

        except Exception as e:
            print(f"Error during deserialization: {e}")
            raise

    def __str__(self):
        return (f"MsgClientAnonLogOn(Protocol Version={self.protocol_version}, Private IP={self.private_ip}, "
                f"Public IP={self.public_ip}, Steam ID={self.steam_id}, Ticket Length={self.ticket_length}, "
                f"Email='{self.email}', Language='{self.language}', Client Version={self.client_version})")

    def __repr__(self):
        return (f"MsgClientAnonLogOn(protocol_version={self.protocol_version}, private_ip={self.private_ip}, "
                f"public_ip={self.public_ip}, steam_id={self.steam_id}, ticket_length={self.ticket_length}, "
                f"ticket={self.ticket}, email='{self.email}', language='{self.language}', "
                f"client_version={self.client_version}, remaining_bytes={self.remaining_bytes})")
