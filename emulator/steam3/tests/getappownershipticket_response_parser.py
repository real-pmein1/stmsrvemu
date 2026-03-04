import struct
from io import BytesIO
import datetime
class MsgClientGetAppOwnershipTicketResponse:
    def __init__(self):
        self.m_eResult = 0
        self.m_nAppID = 0
        self.m_cubTicketLength = 0
        self.m_cubSignatureLength = 0
        self.ticket_data = b''
        self.ticket_info = {}

    def parse(self, buffer):
        stream = BytesIO(buffer)

        # Parse the fixed size fields (first 16 bytes)
        self.m_eResult, self.m_nAppID, self.m_cubTicketLength, self.m_cubSignatureLength = struct.unpack('<I3I', stream.read(16))

        print(f"Result: {self.m_eResult}")
        print(f"App ID: {self.m_nAppID}")
        print(f"Ticket Length: {self.m_cubTicketLength}")
        print(f"Signature Length: {self.m_cubSignatureLength}")

        # Read the ticket data and signature (variable length)
        total_length = self.m_cubTicketLength + self.m_cubSignatureLength
        self.ticket_data = stream.read(total_length)

        # Parse ticket data using Steam3AppOwnershipTicket_2_t structure
        if self.m_cubTicketLength > 0:
            ticket = self.ticket_data[:self.m_cubTicketLength]
            self.parse_ticket(ticket)

        # Print the parsed ticket information
        if self.ticket_info:
            print("Parsed Ticket Information:")
            for key, value in self.ticket_info.items():
                print(f"  {key}: {value}")

        print(f"Signature Bytes: {(self.ticket_data[self.m_cubTicketLength:])}")
        # If buffer has more data, print remaining bytes
        remaining_bytes = stream.read()
        if remaining_bytes:
            print(f"Extra bytes in buffer: {remaining_bytes.hex()}")

    def parse_ticket(self, ticket):
        # Unpack the Steam3AppOwnershipTicket_2_t structure
        ticket_stream = BytesIO(ticket)
        fields = struct.unpack('<IIQIIIIII', ticket_stream.read(40))

        self.ticket_info = {
            "Ticket Length": fields[0],
            "Ticket Version": fields[1],
            "Steam ID": fields[2],
            "App ID": fields[3],
            "Public IP": self.convert_ip(self.reverse_ip_int(fields[4])),
            "Private IP": self.convert_ip(self.reverse_ip_int(fields[5])),
            "Ownership Flags": fields[6],
            "Issued Time": datetime.datetime.utcfromtimestamp(fields[7]).strftime('%m/%d/%Y %H:%M:%S'),
            "Expire Time": datetime.datetime.utcfromtimestamp(fields[8]).strftime('%m/%d/%Y %H:%M:%S'),
            # up to this point is considered version 1 and 2
        }
        version = fields[1]
        try:
            # Parse version 3 (same as version 2)
            if version > 2:
                sub_id_count = struct.unpack('<H', ticket_stream.read(2))[0]  # 2 byte count for version 3
                subscription_ids = []
                self.ticket_info['Subscription Count'] = sub_id_count
                for _ in range(sub_id_count):
                    sub_id = struct.unpack('<I', ticket_stream.read(4))[0]  # 4 byte sub id
                    ticket_stream.read(1)  # Skip null byte at the end of each sub id
                    subscription_ids.append(sub_id)
                self.ticket_info["Subscription IDs"] = subscription_ids

            # Parse version 4 (same as version 3 with extra DLC list and VAC banned flag)
            if version > 3:
                # Read DLC IDs
                dlc_id_count = struct.unpack('<H', ticket_stream.read(2))[0]  # 2 byte count of DLC ids
                dlc_ids = []
                self.ticket_info['DLC Count'] = dlc_id_count
                for _ in range(dlc_id_count):
                    dlc_id = struct.unpack('<I', ticket_stream.read(4))[0]  # 4 byte DLC id
                    ticket_stream.read(1)  # Skip null byte at the end of each DLC id
                    dlc_ids.append(dlc_id)

                self.ticket_info["DLC IDs"] = dlc_ids

                # Read VAC banned flag
                is_vac_banned = struct.unpack('<H', ticket_stream.read(2))[0]  # 2 byte boolean for VAC ban
                self.ticket_info["VAC Banned"] = bool(is_vac_banned)
        except:
            pass

        # Check if there are extra bytes in the ticket
        remaining_bytes = ticket_stream.read()
        if remaining_bytes:
            print(f"Extra bytes in ticket: {remaining_bytes.hex()}")

    @staticmethod
    def convert_ip(ip_int):
        # Convert an integer IP address to dotted format
        return f'{ip_int & 0xFF}.{(ip_int >> 8) & 0xFF}.{(ip_int >> 16) & 0xFF}.{(ip_int >> 24) & 0xFF}'

    @staticmethod
    def reverse_ip_int(ip_int):
        # Reverse the 4 bytes in the integer using bitwise shifts
        reversed_ip = (
            ((ip_int >> 24) & 0xFF) |       # Move the highest byte to the lowest
            ((ip_int >> 8) & 0xFF00) |      # Move the second highest byte to the second lowest
            ((ip_int << 8) & 0xFF0000) |    # Move the second lowest byte to the second highest
            ((ip_int << 24) & 0xFF000000)   # Move the lowest byte to the highest
        )
        return reversed_ip
# Example usage
"""_2008_packet = '5a030000240200ffffffffffffffffffffffffffffffffef1d9800010100100109e04100010000003c0a0000280000008000000028000000020000001d980001010010013c0a0000c4efca500200000a00000000d2eabb48529ad74862dc6102cdfc0215c87311f62047f9e963ae6bf51d6a6bcb152fc75de9e06e04920ce83fa30df79204df2377916583fe308ee87fea981bc6a9d47114f86d73f4ff19f191389e2e063413ad3af45304cca21abb9c323c6fc6751f31fd545b9e2211505f7b2e97e8cdbf71451882569efdfbeb1e7f6a03ba20d4954cb9095648c7'
_2008_packet = bytes.fromhex(_2008_packet)
_2009_packet = b"Z\x03\x00\x00$\x02\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xef\xc4\xa0\x9b\x01\x01\x00\x10\x01\xc9\x13\x14\x00\x01\x00\x00\x00\xea\x01\x00\x000\x00\x00\x00\x80\x00\x00\x000\x00\x00\x00\x04\x00\x00\x00\xc4\xa0\x9b\x01\x01\x00\x10\x01\xea\x01\x00\x00\x1fX0T\x018\xa8\xc0\x00\x00\x00\x00\xa1\xe9TJ!\x99pJ\x01\x00\x00\x00\x00\x00\x00\x00\xb37b\xa4O\n\x8b\xa5\x82\x8d\xf9\x99\x14qk?t\xa7d\xe3|\x9d\x13L__7\x02\xe6\x7f\xef\x05Va]E\xb2\xca\x8a\xc5x\x0b\n\x9dz\xcd\xa2 >\xa0}\xe8\xd32&\xa9\xb1\xc7\x07\x0b\xe0=\x0f\x0f\x93\x19d\xb2'dT\nZ\x08\xf4\xfd\xf2=\x8e\x89p0\xffu\x11\x19\x0e\xb5\xc2\x05\xfb\xac\x82\x05\xee\x1b\xf7\xfb\xf98\xd1C\x1e[X`\x00 \x02e\xabC\x8fW\xf0\x94\x1d\x08#&ZC\xda\x8f\x81L\xb7\x8b"

packet = _2009_packet[36:]
# buffer = struct.pack('<I3I', 1, 440, 128, 32) + b'\x01' * 128 + b'\x02' * 32
parser = MsgClientGetAppOwnershipTicketResponse()
parser.parse(packet)"""

parser = MsgClientGetAppOwnershipTicketResponse()
ownershipticket = b'0\x00\x00\x00\x02\x00\x00\x00\x02\x00\x00\x00\x01\x00\x10\x01\x07\x00\x00\x00@\xed\x87H@\xed\x87H\x00\x00\x00\x00\x01\xc2;g\x11\xd0;g\x8eI\xa4\xecS&S\xd9\x8f\x1d\xc9\xe3eKu\x16\x0f\x9b\xd4I\x9a\x13}\xa7\xb9tI(\x83\xddS\xb2l\xb1\xb3\x90%G\x8d\xfe\xf4\xbbh\xa7\xdd\xa1\x84\\e\x7fz\x90/\xa5hb4\x01\xecT\x8d)]\x9f\x0e0\xed\xbc\x1c\'\x07\xf3\xab\xff\xb6\x86\xaf\xc0\x05\xa1\x14\xaa\xee"\x1a\xd3XJ^\xff\xdc\xd0C:\xbb\xf5\xb4\xe9\t\xbd\xba\x08\xe5\x15\x86{M\xcc\x1ev|Rr\xf8\xder\xeb\xf7!AS\x14\xdf\x95S\x8e\xb2\xd2'
parser.parse_ticket(ownershipticket)
print(parser.ticket_info)