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
_2008_packet = '5a030000240200ffffffffffffffffffffffffffffffffef1d9800010100100109e04100010000003c0a0000280000008000000028000000020000001d980001010010013c0a0000c4efca500200000a00000000d2eabb48529ad74862dc6102cdfc0215c87311f62047f9e963ae6bf51d6a6bcb152fc75de9e06e04920ce83fa30df79204df2377916583fe308ee87fea981bc6a9d47114f86d73f4ff19f191389e2e063413ad3af45304cca21abb9c323c6fc6751f31fd545b9e2211505f7b2e97e8cdbf71451882569efdfbeb1e7f6a03ba20d4954cb9095648c7'
_2008_packet = bytes.fromhex(_2008_packet)
_2009_packet = b'Z\x03\x00\x00$\x02\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xef\xc4\xa0\x9b\x01\x01\x00\x10\x01\x00v/\x00\x01\x00\x00\x00\x00\x00\x00\x00(\x00\x00\x00\x80\x00\x00\x00(\x00\x00\x00\x02\x00\x00\x00\xc4\xa0\x9b\x01\x01\x00\x10\x01\x00\x00\x00\x00\xc4\xef\xcaP\x02\x00\x00\n\x00\x00\x00\x00\xa2\xad\xbaH"]\xd6H\x8dE\x9a{\xde\xa2\xdd\x82\x93(\xd5N\x9f\xeb\x86\x88\xcf\xe7\xbb\xd3\x84\xc6\xdf\xc9\x05V\xe0,Q\x83\xd1\x80\x82\x81@\x821~\xff\xdd\x9f&V@r\xdf=\xc3i\xb1<\x9c\xae\x9b>\xb1\xc3;4\x0f}\xa7\xdb\x14\x88\x89uS\x1b\xfc\x17]\xf4\xeb\x7fg\xf0L\xb5Y\x10\xa2\xa3t\x14p@\x87I\xd2Q\xb8\x12\xe0\x07C\'\x04\x16\xa2\xa1\nW}\x1bO\xdf\xdf\xc4\xf5\xb9!\xd5pT\xce6\xa3bu\x1a\xb53\xc0\xbfrsq'

packet = _2009_packet[36:]
# buffer = struct.pack('<I3I', 1, 440, 128, 32) + b'\x01' * 128 + b'\x02' * 32
parser = MsgClientGetAppOwnershipTicketResponse()
parser.parse(packet)


ownershipticket = b'\xa4\x00\x00\x00\x00\x00\x00\x00\x08\x00\x00\x00\x01\x00\x10\x01\x07\x00\x00\x00\xe8\xe0\x87H\xe8\xe0\x87H\x00\x00\x00\x00D\xb4\xdffT\xc2\xdff\x9e\xb8\xcfY\r\x82XM\xde\x0e\x84\xb15\xcb\x85L\xfcCS\x89\x0c\xf8>\x94e\xa4\xfbn\xa6\x0b\x04\x8c\xfd\xf3\x84\xb1D4\xce\x17\x97uwa(\xc8ur\xfb\xfa\xd6\xc4C\xfes\xe7*\x16\x01\x15\x82\xeeQ\x12\x9a\xef\xc9\xc4q\xb7\xef\xe6\xcc\x93\x8b\x9b&b\x03Sl\x19\xb9Nx\xf9\x7f\xf0qy\x03T3\x93^\x1e\xe8\xef\xed\x83\x9c`\n2\xd1\x948\xb6\x1f\xb1\xd9m\xd59g\xd5\x0e\x8aZla\xd3c\xe3\xa0\xbc\x04x'
parser.parse_ticket(ownershipticket)
print(parser.ticket_info)