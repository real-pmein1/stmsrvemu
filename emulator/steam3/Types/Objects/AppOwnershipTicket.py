import ipaddress
import logging
import struct
from datetime import datetime
from io import BytesIO
from typing import List

from Crypto.Hash import SHA1
from Crypto.Signature import pkcs1_15

from steam3.utilities import ip_to_int, ip_to_reverse_int
from utilities import encryption

log = logging.getLogger("AppOwnershipTicket")

# TODO figure out if this class should call the database class to grab the correct subscription for v4 tickets
#  Or if it should be called outside of this class and added to the initialization as a parameter
class Steam3AppOwnershipTicket:
    def __init__(self, ticket_length=0, ticket_version=0, steam_id=0, app_id=0, public_ip=0, private_ip=0, app_ownership_ticket_flags=0, time_issued=0, time_expire=0):
        self._ticket_length = ticket_length
        self._ticket_version = ticket_version
        self._steam_id = steam_id
        self._app_id = app_id
        # Handle None IP addresses gracefully - default to 0.0.0.0 (0)
        self._public_ip = ip_to_int(str(ipaddress.IPv4Address(public_ip if public_ip is not None else 0)))
        self._private_ip = ip_to_int(str(ipaddress.IPv4Address(private_ip if private_ip is not None else 0)))
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
        total_ticket_len = len(ticket)

        log.debug(f"Parsing ticket of {total_ticket_len} bytes: {ticket[:64].hex()}...")

        # Read the ticket length field first
        self._ticket_length = struct.unpack('<I', ticket_stream.read(4))[0]
        log.debug(f"Inner ticket length field: {self._ticket_length}, total data: {total_ticket_len}")

        # Now read the ticket data based on the format from IDA analysis
        # Format: version, steamID, appID, publicIP, privateIP, flags, timeIssued, timeExpire
        fields = struct.unpack('<IQIIIIII', ticket_stream.read(36))

        self._ticket_version = fields[0]
        self._steam_id = fields[1]
        self._app_id = fields[2]
        self._public_ip = self.convert_ip(self.reverse_ip_int(fields[3]))
        self._private_ip = self.convert_ip(self.reverse_ip_int(fields[4]))
        self._app_ownership_ticket_flags = fields[5]
        self._time_issued = datetime.utcfromtimestamp(fields[6]).strftime('%m/%d/%Y %H:%M:%S')
        self._time_expire = datetime.utcfromtimestamp(fields[7]).strftime('%m/%d/%Y %H:%M:%S')

        log.debug(f"Ticket version: {self._ticket_version}, appID: {self._app_id}, steamID: {self._steam_id}")

        # Calculate remaining bytes in the ticket data (based on inner length field)
        # Inner length includes the 4-byte length field itself, so actual data is _ticket_length - 4
        # We've read 4 (length) + 36 (fields) = 40 bytes so far
        bytes_read = 40
        remaining_in_ticket = self._ticket_length - bytes_read if self._ticket_length > bytes_read else 0

        if self._ticket_version > 2:
            if remaining_in_ticket < 2:
                log.warning(f"Not enough data for subscription count (need 2 bytes, have {remaining_in_ticket})")
            else:
                sub_id_count = struct.unpack('<H', ticket_stream.read(2))[0]
                bytes_read += 2
                remaining_in_ticket -= 2
                log.debug(f"Subscription count: {sub_id_count}, remaining bytes: {remaining_in_ticket}")

                self.subscription_ids = []
                bytes_needed = sub_id_count * 4
                if bytes_needed > remaining_in_ticket:
                    log.warning(f"Subscription IDs need {bytes_needed} bytes but only {remaining_in_ticket} available. Reading what we can.")
                    # Read only what's available
                    available_subs = remaining_in_ticket // 4
                    for _ in range(available_subs):
                        sub_id = struct.unpack('<I', ticket_stream.read(4))[0]
                        self.subscription_ids.append(sub_id)
                    bytes_read += available_subs * 4
                    remaining_in_ticket -= available_subs * 4
                else:
                    for _ in range(sub_id_count):
                        sub_id = struct.unpack('<I', ticket_stream.read(4))[0]
                        self.subscription_ids.append(sub_id)
                    bytes_read += sub_id_count * 4
                    remaining_in_ticket -= sub_id_count * 4

        if self._ticket_version > 3:
            if remaining_in_ticket < 2:
                log.warning(f"Not enough data for DLC count (need 2 bytes, have {remaining_in_ticket})")
            else:
                dlc_id_count = struct.unpack('<H', ticket_stream.read(2))[0]
                bytes_read += 2
                remaining_in_ticket -= 2
                log.debug(f"DLC count: {dlc_id_count}, remaining bytes: {remaining_in_ticket}")

                self.dlc_ids = []
                bytes_needed = dlc_id_count * 6  # 4 bytes ID + 2 bytes size field per DLC
                if bytes_needed > remaining_in_ticket:
                    log.warning(f"DLC IDs need {bytes_needed} bytes but only {remaining_in_ticket} available. Reading what we can.")
                    available_dlcs = remaining_in_ticket // 6
                    for _ in range(available_dlcs):
                        dlc_id = struct.unpack('<I', ticket_stream.read(4))[0]
                        struct.unpack('<H', ticket_stream.read(2))  # Skip the empty size field
                        self.dlc_ids.append(dlc_id)
                    bytes_read += available_dlcs * 6
                    remaining_in_ticket -= available_dlcs * 6
                else:
                    for _ in range(dlc_id_count):
                        dlc_id = struct.unpack('<I', ticket_stream.read(4))[0]
                        struct.unpack('<H', ticket_stream.read(2))  # Skip the empty size field
                        self.dlc_ids.append(dlc_id)
                    bytes_read += dlc_id_count * 6
                    remaining_in_ticket -= dlc_id_count * 6

                if remaining_in_ticket >= 2:
                    self.vac_banned = bool(struct.unpack('<H', ticket_stream.read(2))[0])
                    bytes_read += 2

        remaining_bytes = ticket_stream.read()
        if remaining_bytes:
            log.debug(f"Extra bytes in ticket after parsing (likely signature): {len(remaining_bytes)} bytes")

    # Add subscription ID method for version 3 and above
    def add_subscription_ids(self, sub_ids: List[int]):
        self.subscription_ids.extend(sub_ids)
        self._ticket_length += 2 + len(sub_ids) * 4  # 2 bytes count + 4 bytes per subscription ID

    # Add DLC ID method for version 4 and above
    def add_dlc_ids(self, dlc_ids: List[int]):
        self.dlc_ids.extend(dlc_ids)
        self._ticket_length += 2 + len(dlc_ids) * 6  # 2 bytes count + 6 bytes per DLC (4 bytes ID + 2 bytes size)

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

    # Serialization method
    def serialize(self, addsignature = False):
        # Determine ticket version based on what data we have
        if self.dlc_ids or self.vac_banned:
            self._ticket_version = 4
        elif self.subscription_ids:
            self._ticket_version = 3
        else:
            self._ticket_version = 2
        
        # Build ticket data in the format expected by Steam3AppOwnershipTicket_2_t
        # Order matches C++ AppOwnershipTicket::serialize() method
        self.data = struct.pack("<I Q I I I I I I",
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
                self.data += struct.pack('<I', sub_id)

        if self._ticket_version > 3:
            self.data += struct.pack('<H', len(self.dlc_ids))
            for dlc_id in self.dlc_ids:
                self.data += struct.pack('<I', dlc_id)
                self.data += struct.pack('<H', 0)  # empty size field as per C++ code
            #self.data += struct.pack('<H', int(self.vac_banned))

        # Calculate length of ticket data (excluding signature)
        self._ticket_length = len(self.data) + 4  # +4 for the length field itself
        
        if addsignature:
            self.add_signature()
            
        # Return ticket in format expected by client: [length][data][signature]
        result = struct.pack('<I', self._ticket_length) + self.data
        if addsignature and self.signature:
            result += self.signature
            
        return result, len(self.signature) if self.signature else 0

    # Deserialization using struct.unpack
    @classmethod
    def deserialize(cls, data):
        # Create new instance and parse the ticket data
        instance = cls()
        instance.parse_ticket(data)
        return instance

# Example usage
"""ticket = Steam3AppOwnershipTicket(ticket_length=100, ticket_version=2, steam_id=12345678901234567, app_id=1234, public_ip=1234567890, private_ip=987654321, app_ownership_ticket_flags=1, time_issued=1617171717, time_expire=1717171717)
print(ticket)
serialized_data = ticket.serialize()
print(serialized_data)

# Deserialize example
new_ticket = Steam3AppOwnershipTicket.deserialize(serialized_data)
print(new_ticket)"""