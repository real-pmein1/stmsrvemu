import struct
from io import BytesIO


class ClientAnonLogOn_Deprecated:
    def __init__(self):
        self.protocolVersion = 0
        self.privateIp = 0
        self.publicIp = 0
        self.steamGlobalId = 0
        self.unknown1 = 0
        self.unknown2 = 0
        self.unknown3 = 0
        self.unknown4 = 0
        self.clientAppVersion = None

    def deSerialize(self, byte_buffer):
        # Create a BytesIO stream from the byte buffer
        stream = BytesIO(byte_buffer)

        # Read protocolVersion (int32)
        self.protocolVersion = struct.unpack('<I', stream.read(4))[0]

        # Read privateIp (int32) and XOR with 0xBAADF00D
        privateIp = struct.unpack('<i', stream.read(4))[0] ^ 0xBAADF00D
        self.privateIp = self.convert_ip(self.reverse_ip_int(privateIp))

        # Read publicIp (int32)
        self.publicIp = struct.unpack('<i', stream.read(4))[0]

        # Read steamGlobalId (int64)
        self.steamGlobalId = struct.unpack('<q', stream.read(8))[0]

        try:
            # Read unknown1 (int32), unknown2 (int32), unknown3 (int16), and unknown4 (int8)
            self.unknown1 = struct.unpack('<i', stream.read(4))[0]
            self.unknown2 = struct.unpack('<i', stream.read(4))[0]
            self.unknown3 = struct.unpack('<h', stream.read(2))[0]
            self.unknown4 = struct.unpack('<b', stream.read(1))[0]


        except Exception as e:
            print(f"anon client login: {e}")
            pass

        # If there are remaining bytes in the stream, read clientAppVersion (int32)
        if stream.tell() < len(byte_buffer):
            self.clientAppVersion = struct.unpack('<i', stream.read(4))[0]

        return self

    @staticmethod
    def convert_ip(ip_int):
        # Convert an integer IP address to dotted format
        return f'{ip_int & 0xFF}.{(ip_int >> 8) & 0xFF}.{(ip_int >> 16) & 0xFF}.{(ip_int >> 24) & 0xFF}'

    @staticmethod
    def reverse_ip_int(ip_int):
        # Reverse the 4 bytes in the integer using bitwise shifts
        reversed_ip = (
                ((ip_int >> 24) & 0xFF) |  # Move the highest byte to the lowest
                ((ip_int >> 8) & 0xFF00) |  # Move the second highest byte to the second lowest
                ((ip_int << 8) & 0xFF0000) |  # Move the second lowest byte to the second highest
                ((ip_int << 24) & 0xFF000000)  # Move the lowest byte to the highest
        )
        return reversed_ip