import ipaddress
import struct
from datetime import datetime
from io import BytesIO

from Crypto.Hash import SHA1
from Crypto.Signature import pkcs1_15

from steam3.utilities import ip_to_int, ip_to_reverse_int
from utilities import encryption


class Steam3AppOwnershipTicket:
    def __init__(self, ticket_length=0, ticket_version=0, steam_id=0, app_id=0, public_ip=0, private_ip=0, app_ownership_ticket_flags=0, time_issued=0, time_expire=0):
        self._ticket_length = ticket_length
        self._ticket_version = ticket_version
        self._steam_id = steam_id
        self._app_id = app_id
        self._public_ip = ip_to_int(str(ipaddress.IPv4Address(private_ip)))
        self._private_ip = ip_to_int(str(ipaddress.IPv4Address(private_ip)))
        self._app_ownership_ticket_flags = app_ownership_ticket_flags
        self._time_issued = time_issued
        self._time_expire = time_expire
        self.subscription_ids = []
        self.dlc_ids = []
        self.vac_banned = False

        self.data = None
        self.signature = None

    def __repr__(self):
        return (f"Steam3AppOwnershipTicket(ticket_length={self._ticket_length}, "
                f"ticket_version={self._ticket_version}, steam_id={self._steam_id}, "
                f"app_id={self._app_id}, public_ip={self._public_ip}, private_ip={self._private_ip}, "
                f"app_ownership_ticket_flags={self._app_ownership_ticket_flags}, "
                f"time_issued={self._time_issued}, time_expire={self._time_expire})")
        # Convert IP addresses

    @staticmethod
    def convert_ip(ip_int):
        return f'{ip_int & 0xFF}.{(ip_int >> 8) & 0xFF}.{(ip_int >> 16) & 0xFF}.{(ip_int >> 24) & 0xFF}'

    @staticmethod
    def reverse_ip_int(ip_int):
        return (
                ((ip_int >> 24) & 0xFF) |
                ((ip_int >> 8) & 0xFF00) |
                ((ip_int << 8) & 0xFF0000) |
                ((ip_int << 24) & 0xFF000000)
        )

    # Ticket parsing method
    def parse_ticket(self, ticket):
        ticket_stream = BytesIO(ticket)
        fields = struct.unpack('<IIQIIIIII', ticket_stream.read(40))

        self._ticket_length = fields[0]
        self._ticket_version = fields[1]
        self._steam_id = fields[2]
        self._app_id = fields[3]
        self._public_ip = self.convert_ip(self.reverse_ip_int(fields[4]))
        self._private_ip = self.convert_ip(self.reverse_ip_int(fields[5]))
        self._app_ownership_ticket_flags = fields[6]
        self._time_issued = datetime.utcfromtimestamp(fields[7]).strftime('%m/%d/%Y %H:%M:%S')
        self._time_expire = datetime.utcfromtimestamp(fields[8]).strftime('%m/%d/%Y %H:%M:%S')

        version = fields[1]

        if version > 2:
            sub_id_count = struct.unpack('<H', ticket_stream.read(2))[0]
            self.subscription_ids = []
            for _ in range(sub_id_count):
                sub_id = struct.unpack('<I', ticket_stream.read(4))[0]
                ticket_stream.read(1)  # Skip null byte
                self.subscription_ids.append(sub_id)

        if version > 3:
            dlc_id_count = struct.unpack('<H', ticket_stream.read(2))[0]
            self.dlc_ids = []
            for _ in range(dlc_id_count):
                dlc_id = struct.unpack('<I', ticket_stream.read(4))[0]
                ticket_stream.read(1)  # Skip null byte
                self.dlc_ids.append(dlc_id)

            self.vac_banned = bool(struct.unpack('<H', ticket_stream.read(2))[0])

        remaining_bytes = ticket_stream.read()
        if remaining_bytes:
            print(f"Extra bytes in ticket: {remaining_bytes.hex()}")

    # Add subscription ID method for version 3 and above
    def add_subscription_ids(self, sub_ids):
        self.subscription_ids.extend(sub_ids)
        self._ticket_length += 2 + len(sub_ids) * 5  # Update ticket length accordingly

    # Add DLC ID method for version 4 and above
    def add_dlc_ids(self, dlc_ids):
        self.dlc_ids.extend(dlc_ids)
        self._ticket_length += 2 + len(dlc_ids) * 5  # Update ticket length accordingly

    @property
    def ticket_length(self):
        return self._ticket_length

    @ticket_length.setter
    def ticket_length(self, value):
        self._ticket_length = value

    @property
    def ticket_version(self):
        return self._ticket_version

    @ticket_version.setter
    def ticket_version(self, value):
        self._ticket_version = value

    @property
    def steam_id(self):
        return self._steam_id

    @steam_id.setter
    def steam_id(self, value):
        self._steam_id = value

    @property
    def app_id(self):
        return self._app_id

    @app_id.setter
    def app_id(self, value):
        self._app_id = value

    @property
    def public_ip(self):
        return self._public_ip

    @public_ip.setter
    def public_ip(self, value):
        self._public_ip = value

    @property
    def private_ip(self):
        return self._private_ip

    @private_ip.setter
    def private_ip(self, value):
        self._private_ip = value

    @property
    def app_ownership_ticket_flags(self):
        return self._app_ownership_ticket_flags

    @app_ownership_ticket_flags.setter
    def app_ownership_ticket_flags(self, value):
        self._app_ownership_ticket_flags = value

    @property
    def time_issued(self):
        return self._time_issued

    @time_issued.setter
    def time_issued(self, value):
        self._time_issued = value

    @property
    def time_expire(self):
        return self._time_expire

    @time_expire.setter
    def time_expire(self, value):
        self._time_expire = value

    def add_signature(self):
        self.signature = encryption.rsa_sign_message(encryption.network_key, self.data)
        return self.signature

    """
    28000000                ticket length
    02000000                ticket version
    c4a09b0101001001        steam ID
    00000000                appid 0
    c4efca50                (80, 202, 239, 196)
    0200000a                (10, 0, 0, 2)
    00000000
    a2adba48                Sun Aug 31 2008 14:41:38 GMT+0000
    225dd648                Sun Sep 21 2008 14:41:38 GMT+0000
    """

    # Serialization method
    def serialize(self, addsignature = False):
        self.data = struct.pack("<I I Q I I I I I I",
                                self._ticket_length,
                                self._ticket_version,
                                self._steam_id,
                                self._app_id,
                                self._public_ip,
                                self._private_ip,
                                self._app_ownership_ticket_flags,
                                self._time_issued,
                                self._time_expire)

        if self._ticket_version > 2:
            self.data += struct.pack('<H', len(self.subscription_ids))
            for sub_id in self.subscription_ids:
                self.data += struct.pack('<I', sub_id) + b'\x00'  # Append null byte after each ID

        if self._ticket_version > 3:
            self.data += struct.pack('<H', len(self.dlc_ids))
            for dlc_id in self.dlc_ids:
                self.data += struct.pack('<I', dlc_id) + b'\x00'  # Append null byte after each DLC ID
            self.data += struct.pack('<H', int(self.vac_banned))  # 2-byte VAC banned flag

        if addsignature:
            self.add_signature()
            self.data += self.signature

        return self.data, len(self.signature)

    # Deserialization using struct.unpack
    @classmethod
    def deserialize(cls, data):
        unpacked_data = struct.unpack("<I I Q I I I I I I", data)
        return cls(*unpacked_data)

# Example usage
"""ticket = Steam3AppOwnershipTicket(ticket_length=100, ticket_version=2, steam_id=12345678901234567, app_id=1234, public_ip=1234567890, private_ip=987654321, app_ownership_ticket_flags=1, time_issued=1617171717, time_expire=1717171717)
print(ticket)
serialized_data = ticket.serialize()
print(serialized_data)

# Deserialize example
new_ticket = Steam3AppOwnershipTicket.deserialize(serialized_data)
print(new_ticket)"""