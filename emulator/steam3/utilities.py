import re
import socket
import struct
import time
import secrets
import string
import creditcard
import csv
import ipaddress
from datetime import datetime

from steam3.Types.community_types import PersonaStateFlags


def getAccountId(request):
    res = request.accountID
    res //= 2
    return res & 0xFFFF


def create_GlobalID(accountId, clientId2):
    # Ensure accountId and clientId2 are treated as 32-bit unsigned integers
    # Pack accountId (the least significant part) and clientId2 (the most significant part) into bytes
    # Note: '<I' - unsigned int (32-bit) in little-endian format
    steam_globalID = struct.pack('<I', accountId) + struct.pack('<I', clientId2)

    # Unpack the 64-bit integer from the combined byte object
    # '<Q' - unsigned long long (64-bit) in little-endian format
    globalID_Int = struct.unpack('<Q', steam_globalID)[0]

    return globalID_Int


def reverse_bytes(uint):
    return struct.unpack("<I", struct.pack(">I", uint))[0]


def decipher_persona_flags(value):
    """
    Decodes an integer to find the active flags set, ideally helping someone who struggles
    with the concept that light switches need to be turned on to work.
    """
    # Pull out the flags like pulling teeth, painful but necessary
    flags = [flag.name for flag in PersonaStateFlags if flag & PersonaStateFlags(value)]
    return flags if flags else ['none']  # Giving you an out when inevitably nothing makes sense

def read_null_terminated_string(stream, max_length):
    """
    Reads a null-terminated string from the stream, up to max_length bytes.
    Stops at the first null byte or after max_length bytes are read.
    """
    string_bytes = bytearray()

    for _ in range(max_length):
        byte = stream.read(1)
        if byte == b'\x00' or not byte:  # Stop at null byte or if there's nothing to read
            break
        string_bytes.extend(byte)

    return string_bytes.decode('utf-8')

def read_string(data, start):
    # Let's pretend we know where strings end
    end = data.index(0, start)
    return data[start:end].decode('utf-8'), end + 1


def get_current_time_uint32():
    # Get the current time in seconds since the Unix epoch
    current_time = int(time.time())
    # Convert to uint32 by taking the modulo 2**32
    current_time_uint32 = current_time % (2**32)
    return current_time_uint32


def add_time_to_current_uint32(days = 0, hours = 0, minutes = 0, seconds = 0):
    # Get the current time in seconds since the Unix epoch
    current_time = int(time.time())

    # Calculate the total number of seconds to add
    total_seconds_to_add = (
            (days * 24 * 3600) +
            (hours * 3600) +
            (minutes * 60) +
            seconds
    )

    # Add the specified amount of time to the current time
    future_time = current_time + total_seconds_to_add

    # Convert to uint32 by taking the modulo 2**32
    future_time_uint32 = future_time % (2 ** 32)
    return future_time_uint32


def uint32_to_time(raw_bytes):
    # Ensure the input is exactly 4 bytes
    if len(raw_bytes) != 4:
        raise ValueError("Input must be exactly 4 bytes long.")

    # Unpack the 4-byte raw bytes as a uint32 (unsigned 32-bit integer)
    # '<I' indicates little-endian format for an unsigned int
    seconds_since_epoch = struct.unpack('<I', raw_bytes)[0]

    # Convert the seconds since the epoch to a datetime object
    timestamp = datetime.utcfromtimestamp(seconds_since_epoch)

    # Optionally format the datetime object to a string for readability
    readable_time = timestamp.strftime('%Y-%m-%d %H:%M:%S')

    return readable_time


def get_packed_datetime(value):
    if isinstance(value, datetime):
        dt_struct_time = value.timetuple()
    elif isinstance(value, str):
        try:
            dt = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
            dt_struct_time = dt.timetuple()
        except ValueError as e:
            raise ValueError(f"String is not in the expected datetime format 'YYYY-MM-DD HH:MM:SS': {value}") from e
    else:
        raise TypeError(f"Unsupported type for datetime value: {type(value)}")

    dt_timestamp = int(time.mktime(dt_struct_time))
    return struct.pack('I', dt_timestamp)


def convert_str_ip2hostordert(ipaddr):
    ip_int = struct.unpack("!I", socket.inet_aton(ipaddr))[0]  # Convert IP string to 32-bit integer
    ip_packed = struct.pack('>I', ip_int)  # Network byte order (big-endian)

    return ip_packed

def ip_to_reverse_int(ip):
    # Convert the IP to a packed binary format
    packed_ip = socket.inet_aton(ip)
    # Reverse the byte order
    reversed_packed_ip = packed_ip[::-1]
    # Convert to an integer
    reversed_int_ip = struct.unpack("<I", reversed_packed_ip)[0]
    return reversed_int_ip

def ip_to_int(ip):
    # Convert the IP to a packed binary format
    packed_ip = socket.inet_aton(ip)
    # Convert to an integer
    int_ip = struct.unpack("!I", packed_ip)[0]
    return int_ip


def ip_port_to_packet_format(ip_address, port):
    # Convert IP address to 4-byte binary format
    binary_ip = socket.inet_aton(ip_address)

    # Convert port to 2-byte binary format in network byte order (big-endian)
    binary_port = struct.pack('!H', port)

    # Combine the binary IP address and binary port
    packet_data = binary_ip + binary_port

    return packet_data


def generate_token(length=16):
    characters = string.ascii_letters + string.digits + string.punctuation
    otp = ''.join(secrets.choice(characters) for _ in range(length))
    return otp


def convert_to_binary(data):
    return data.encode('latin-1')


def generate_64bit_token():
    # Generate a random 64-bit integer
    token = secrets.randbits(64)

    # Convert the integer to a hexadecimal string (without the '0x' prefix)
    hex_token = hex(token)[2:]

    # Ensure the hex string is always 16 characters long (64 bits / 4 bits per hex digit)
    hex_token = hex_token.zfill(16)

    return hex_token


def get_credit_card_brand(card_number):
    brand = creditcard.get_brand(card_number)
    return brand

def read_until_null_byte(buffer):
    null_byte_index = buffer.find(b'\x00')
    if null_byte_index != -1:
        return buffer[:null_byte_index]
    return buffer  # Return the entire buffer if no null byte is found

class InputStream:
    def __init__(self, data):
        self.data = data
        self.offset = 0

    def read_int32(self):
        value, = struct.unpack_from(">I", self.data, self.offset)
        self.offset += 4
        return value


def bytes_to_dollars_cents(byte_data):
    # Ensure byte_data is exactly 4 bytes
    if len(byte_data) != 4:
        raise ValueError("byte_data must be exactly 4 bytes")

    # Unpack the 4 bytes into an integer (assuming little-endian format)
    int_value = struct.unpack('<I', byte_data)[0]

    # Convert cents to dollars
    dollars = int_value // 100
    cents = int_value % 100

    return f"${dollars}.{cents:02d}"


def dollars_cents_to_bytes(money_str):
    try:
        # Split the input string into dollars and cents
        dollars, cents = money_str.split('.')

        # Convert dollars and cents to integers
        dollars = int(dollars)
        cents = int(cents)

        # Ensure cents is between 0 and 99
        if not (0 <= cents < 100):
            raise ValueError("cents must be between 0 and 99")

        # Convert dollars and cents to total cents
        total_cents = (dollars * 100) + cents

        # Pack the total cents into 4 bytes (unsigned int, little-endian)
        byte_data = struct.pack('<I', total_cents)

        return byte_data
    except ValueError:
        raise ValueError("Invalid input format. Expected a string like '4.23'")


def compare_dictionaries(dict1, dict2):
    # Determine the smaller dictionary to iterate over its keys
    smaller_dict = dict1 if len(dict1) <= len(dict2) else dict2
    larger_dict = dict2 if smaller_dict == dict1 else dict1

    for key in smaller_dict:
        if key in larger_dict:
            if smaller_dict[key] != larger_dict[key]:
                return False
        else:
            return False
    return True


def extract_guest_pass_packages(data):
    guest_pass_values = []

    def search_dict(d, current_depth, start_depth):
        for key, value in d.items():
            key_str = key.decode('latin-1') if isinstance(key, bytes) else key
            if re.match(r'OnPurchaseGrantGuestPassPackage\d*', key_str):
                value_str = value.decode('latin-1').strip('\x00') if isinstance(value, bytes) else value.strip('\x00')
                guest_pass_values.append(value_str)
            elif isinstance(value, dict):
                search_dict(value, current_depth + 1, start_depth)

    if isinstance(data, dict):
        search_dict(data, 0, 0)  # Start the search at depth 0

    return ','.join(guest_pass_values)


class BitVector64:
    def __init__(self, data=0):
        self.data = data

    @property
    def Data(self):
        return self.data

    @Data.setter
    def Data(self, value):
        self.data = value

    def __getitem__(self, key):
        start_bit, mask = key
        return (self.data >> start_bit) & mask

    def __setitem__(self, key, value):
        start_bit, mask = key
        self.data = (self.data & ~(mask << start_bit)) | ((value & mask) << start_bit)

def is_valid_email(email):
    email = email.strip()

    # Split and check for the presence of exactly one @ symbol
    try:
        local_part, domain_part = email.split('@')
    except ValueError:
        return False

    # Basic length checks
    if not (1 <= len(local_part) <= 64 and 1 <= len(domain_part) <= 255):
        return False

    # Local part allowed characters check
    if any(not (char.isalnum() or char in "._%+-") for char in local_part):
        return False

    # Domain part basic checks
    if '.' not in domain_part or domain_part[0] == '.' or domain_part[-1] == '.':
        return False

    # Split domain part into labels
    domain_labels = domain_part.split('.')

    # Domain labels allowed characters and length check
    for label in domain_labels:
        if not (1 <= len(label) <= 63 and all(char.isalnum() or char == '-' for char in label)):
            return False
        if label[0] == '-' or label[-1] == '-':
            return False

    # Top-level domain length check
    if not (2 <= len(domain_labels[-1]) <= 63):
        return False

    return True

# Test the function
"""email = "example.email+alias@sub.domain.com"
result = "ValidEmail" if is_valid_email(email) else "InvalidEmail"
print(result)"""


def get_country_code(ip_address: str) -> str:
    # Path to the CSV file
    csv_file_path = 'files/geolitedb/GeoLite2-Country-Blocks-IPv4.csv'
    country_file_path = 'files/geolitedb/GeoLite2-Country-Locations-en.csv'

    # Dictionary to map geoname_id to country ISO code
    geoname_to_country = {}

    # Load the country codes from the locations CSV file
    with open(country_file_path, mode = 'r', encoding = 'utf-8') as country_file:
        country_reader = csv.DictReader(country_file)
        for row in country_reader:
            geoname_id = row['geoname_id']
            iso_code = row['country_iso_code']
            geoname_to_country[geoname_id] = iso_code

    # Convert the input IP address to an integer
    ip_int = int(ipaddress.IPv4Address(ip_address))

    # Open the GeoLite2 CSV file and look for the IP range
    with open(csv_file_path, mode = 'r', encoding = 'utf-8') as csvfile:
        reader = csv.DictReader(csvfile)

        for row in reader:
            # Parse the IP range
            network = ipaddress.IPv4Network(row['network'], strict = False)

            # Check if the IP address is within the range
            if ip_int >= int(network.network_address) and ip_int <= int(network.broadcast_address):
                # Get the geoname_id from the CSV
                geoname_id = row['geoname_id']

                # Return the corresponding country code
                if geoname_id in geoname_to_country:
                    return geoname_to_country[geoname_id]
                else:
                    return "US"  # Default if no country code is found

    return "US"  # Default if no match is found