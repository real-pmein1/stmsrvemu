import struct
import binascii
import socket
import time
from datetime import datetime, timedelta

class Steam2Ticket:
    def __init__(self, real_ticket):
        self.real_ticket = real_ticket
        self._parse_ticket()

    def steamtime_to_unixtime(self, raw_bytes):
        steam_time = struct.unpack("<Q", raw_bytes)[0]
        unix_time = steam_time / 1000000 - 62135596800
        return unix_time

    def steamtime_to_datetime(self, raw_bytes):
        try:
            unix_time = self.steamtime_to_unixtime(raw_bytes)
            dt_object = datetime.utcfromtimestamp(unix_time)
            formatted_datetime = dt_object.strftime('%m/%d/%Y %H:%M:%S')
            return formatted_datetime
        except Exception as e:
            print(f"Error converting steam time: {e}")
            return "Invalid steam time"

    def parse_ip_port(self, data):
        ip = socket.inet_ntoa(data[:4])
        port_bytes = data[4:6]
        port = struct.unpack('>H', port_bytes[::-1])[0]
        return f"{ip}:{port}"

    def _parse_ticket(self):
        pos = 0

        # TGT version
        self.tgt_version = self.real_ticket[pos:pos + 2]
        pos += 2

        # Data1 length string
        data1_len_str = self.real_ticket[pos:pos + 2]
        data1_len = struct.unpack(">H", data1_len_str)[0]
        pos += 2

        # Data1
        data1 = self.real_ticket[pos:pos + data1_len]
        pos += data1_len

        # IV
        self.iv = self.real_ticket[pos:pos + 16]
        pos += 16

        """# Empty2 lengths
        self.empty2_dec_len = struct.unpack(">H", self.real_ticket[pos:pos + 2])[0]
        pos += 2
        self.empty2_enc_len = struct.unpack(">H", self.real_ticket[pos:pos + 2])[0]
        pos += 2

        # Data2
        data2_len = self.empty2_dec_len * 2  # Each byte represents two characters in hex
        self.data2 = self.real_ticket[pos:pos + data2_len]
        pos += data2_len

        # Subcommand2
        subcommand2_len = 18  # assuming 18 bytes based on structure
        self.subcommand2 = self.real_ticket[pos:pos + subcommand2_len]
        pos += subcommand2_len

        # Empty3
        self.empty3 = self.real_ticket[pos:pos + 128]"""

        # Parse Data1 fields
        username_bytes = data1.split(b'\x00', 1)[0]
        self.username = username_bytes[:len(username_bytes) // 2].decode('ascii')
        pos_data1 = len(username_bytes)
        self.indicator = data1[pos_data1:pos_data1 + 2]
        pos_data1 += 2
        self.public_ip = data1[pos_data1:pos_data1 + 4][::-1]  # Reverse byte order
        pos_data1 += 4
        self.client_ip = data1[pos_data1:pos_data1 + 4]
        pos_data1 += 4
        servers = data1[pos_data1:pos_data1 + 12]
        pos_data1 += 12
        self.password_digest = data1[pos_data1:pos_data1 + 16]
        pos_data1 += 16
        self.creation_time = data1[pos_data1:pos_data1 + 8]
        pos_data1 += 8
        self.ticket_expiration_time = data1[pos_data1:pos_data1 + 8]
        pos_data1 += 8

        # Parse servers into two IP:port pairs
        self.server1 = self.parse_ip_port(servers[:6])
        self.server2 = self.parse_ip_port(servers[6:])

    @property
    def tgt_version_hex(self):
        return binascii.hexlify(self.tgt_version).decode()

    @property
    def username_str(self):
        return self.username

    @property
    def public_ip_str(self):
        return socket.inet_ntoa(self.public_ip)

    @property
    def client_ip_str(self):
        return socket.inet_ntoa(self.client_ip)

    @property
    def server1_str(self):
        return self.server1

    @property
    def server2_str(self):
        return self.server2

    @property
    def password_digest_hex(self):
        return binascii.hexlify(self.password_digest).decode()

    @property
    def creation_time_formatted(self):
        return self.steamtime_to_datetime(self.creation_time)

    @property
    def ticket_expiration_time_formatted(self):
        return self.steamtime_to_datetime(self.ticket_expiration_time)

    @property
    def time_until_expiration(self):
        expiration_unix_time = self.steamtime_to_unixtime(self.ticket_expiration_time)
        current_unix_time = time.time()
        time_diff = expiration_unix_time - current_unix_time
        return timedelta(seconds=time_diff)

    @property
    def is_expired(self):
        expiration_unix_time = self.steamtime_to_unixtime(self.ticket_expiration_time)
        current_unix_time = time.time()
        return current_unix_time > expiration_unix_time

    def __repr__(self):
        return (f"Steam2Ticket(tgt_version={self.tgt_version_hex}, username={self.username_str}, "
                f"public_ip={self.public_ip_str}, client_ip={self.client_ip_str}, server1={self.server1_str}, "
                f"server2={self.server2_str}, password_digest={self.password_digest_hex}, "
                f"creation_time={self.creation_time_formatted}, ticket_expiration_time={self.ticket_expiration_time_formatted}, "
                f"time_until_expiration={self.time_until_expiration})")

    def __str__(self):
        return (f"TGT Version: {self.tgt_version_hex}\n"
                f"Username: {self.username_str}\n"
                f"Public IP (reversed): {self.public_ip_str}\n"
                f"Client IP: {self.client_ip_str}\n"
                f"Server 1: {self.server1_str}\n"
                f"Server 2: {self.server2_str}\n"
                f"Password Digest: {self.password_digest_hex}\n"
                f"Creation Time: {self.creation_time_formatted}\n"
                f"Ticket Expiration Time: {self.ticket_expiration_time_formatted}\n"
                f"Time Until Expiration: {self.time_until_expiration}")