import struct
from Crypto.Random import get_random_bytes

class TicketType:
    ClientAuthenticationTicket = 2

class Serializable(object):
    def serialize(self, out):
        raise NotImplementedError

    def deserialize(self, in_stream):
        raise NotImplementedError

class Vector(list):
    def add(self, value):
        self.append(value)

class ServerReadableTicket(Serializable):
    def __init__(self, steam_local_user_id, unique_account_name=None, client_public_ip=None):
        self.ticket_type = TicketType.ClientAuthenticationTicket
        self.key = bytearray(128)
        self.is_rsa_encrypted_key = False
        self.initial_value = bytearray(16)
        self.encrypted_information = None
        self.encrypted_information_size = 0
        self.steam_local_user_id = steam_local_user_id
        self.client_public_ip = client_public_ip
        self.subscription_ids = Vector()
        self.rsa_signature = bytearray(128)

        if unique_account_name is not None:
            self.generate_security_data(unique_account_name)

    def generate_security_data(self, unique_account_name=None):
        self.subscription_ids = Vector()

        self.ticket_type = TicketType.ClientAuthenticationTicket
        self.encrypted_information_size = 0
        self.encrypted_information = None

        self.set_steam_local_user_id(steam_local_user_id)
        self.set_client_public_ip(client_public_ip)

        self.subscription_ids.add(0)

        self.generate_security_data(unique_account_name)

    def set_steam_local_user_id(self, value):
        self.steam_local_user_id = value

    def set_client_public_ip(self, value):
        self.client_public_ip = value

    def serialize(self, out):
        out.write(struct.pack('<H', self.ticket_type))

        self.write_key(out)

        out.write(self.initial_value)
        self.write_encrypted_information(out)
        self.write_client_information(out)

        out.write(self.rsa_signature)

    def write_key(self, out):
        sized_out = SizePrefixedOutputStream(out, '<H')

        if self.is_rsa_encrypted_key:
            sized_out.write(self.key)
        else:
            sized_out.write(self.key[:16])

        sized_out.out = 0

    def write_encrypted_information(self, out):
        if self.encrypted_information is not None:
            out.write(self.encrypted_information)

    def write_client_information(self, out):
        sized_out = SizePrefixedOutputStream(out, '<H')

        sized_out.write(struct.pack('<Q', self.steam_local_user_id))
        sized_out.write(struct.pack('<I', self.client_public_ip))

        for subscription_id in self.subscription_ids:
            sized_out.write(struct.pack('<I', subscription_id))

        sized_out.out = 0

    def deserialize(self, in_stream):
        self.ticket_type = struct.unpack('<H', in_stream.read(2))[0]
        self.parse_key(in_stream)
        self.initial_value = bytearray(in_stream.read(16))
        self.parse_encrypted_information(in_stream)
        self.parse_client_information(in_stream)
        self.rsa_signature = bytearray(in_stream.read(128))

    def parse_key(self, in_stream):
        sized_in = SizePrefixedInputStream(in_stream, '<H')

        key_length = sized_in.available()
        if key_length == 128:
            self.is_rsa_encrypted_key = True
        elif key_length == 16:
            self.is_rsa_encrypted_key = False
        else:
            raise Exception("Invalid key length")

        self.key = bytearray(sized_in.read(key_length))
        sized_in.in_stream = 0

    def parse_encrypted_information(self, in_stream):
        decrypted_size = struct.unpack('>H', in_stream.read(2))[0]
        encrypted_in = SizePrefixedInputStream(in_stream, '>H')
        buffer = bytearray(encrypted_in.available())

        buffer[0:2] = struct.pack('>H', decrypted_size)
        buffer[2:4] = struct.pack('>H', encrypted_in.available())

        buf = bytearray(100)
        i = 0
        while encrypted_in.available():
            length = encrypted_in.readinto(buf)
            if not length:
                raise Exception("Broken stream")
            buffer[i+4:i+4+length] = buf[:length]
            i += length

        self.encrypted_information_size = len(buffer)
        self.encrypted_information = bytes(buffer)

    def parse_client_information(self, in_stream):
        sized_in = SizePrefixedInputStream(in_stream, '>H')

        self.steam_local_user_id = struct.unpack('>Q', sized_in.read(8))[0]
        self.client_public_ip = struct.unpack('>I', sized_in.read(4))[0]

        while sized_in.available():
            subscription_id = struct.unpack('>I', sized_in.read(4))[0]
            self.subscription_ids.add(subscription_id)

        sized_in.in_stream = 0

    def dump(self, out):
        buffer = bytearray(100)

        out.printfln("ticket type           : %u", self.ticket_type)
        if self.is_rsa_encrypted_key:
            out.println("RSA encrypted key     :")
            out.println(self.key[:128])
        else:
            out.println("key                   :")
            out.println(self.key[:16])
        out.print("initial value         : #")
        out.println(self.initial_value[:16])
        out.printfln("encrypted information : %u bytes", self.encrypted_information_size)
        out.println(self.encrypted_information)
        
        out.printfln("steamLocalUserID      : 0x%s", TextFormater.formatHexa(self.steam_local_user_id, buffer))
        
        address = InetAddress(self.client_public_ip, 0)
        out.printfln("client public ip      : %s", address.toString())
        del address
        
        out.print("subscription ids      : ")
        ids = self.subscription_ids.iterator()
        while ids.hasNext():
            out.printf("%u ", ids.next())
        del ids

        out.println()

        out.println("RSA signature         :")
        out.println(self.rsa_signature[:128])

    def get_steam_local_user_id(self):
        return self.steam_local_user_id

    def get_client_public_ip(self):
        return self.client_public_ip

    def get_subscription_ids(self):
        return self.subscription_ids

    def set_steam_local_user_id(self, value):
        self.steam_local_user_id = value

    def set_client_public_ip(self, value):
        self.client_public_ip = value

    def generate_security_data(self, unique_account_name=None):
        self.is_rsa_encrypted_key = True
        self.key = get_random_bytes(128)
        self.rsa_signature = get_random_bytes(128)
        self.initial_value = get_random_bytes(16)

        decrypted_information_size = 54 + 2 * len(unique_account_name)
        encrypted_information_size = (decrypted_information_size // 16 + (decrypted_information_size % 16 != 0)) * 16
        encrypted_information = get_random_bytes(encrypted_information_size)

        sized_encrypted_information = bytearray(encrypted_information_size + 4)
        sized_encrypted_information[0:2] = struct.pack('>H', decrypted_information_size)
        sized_encrypted_information[2:4] = struct.pack('>H', encrypted_information_size)
        sized_encrypted_information[4:] = encrypted_information

        self.encrypted_information_size = len(sized_encrypted_information)
        self.encrypted_information = bytes(sized_encrypted_information)

    def generate_security_data(self):
        self.is_rsa_encrypted_key = False
        self.key = bytearray(16)
        self.rsa_signature = bytearray(128)
        self.initial_value = bytearray(16)
        self.encrypted_information_size = 1
        self.encrypted_information = bytes(bytearray([0]))