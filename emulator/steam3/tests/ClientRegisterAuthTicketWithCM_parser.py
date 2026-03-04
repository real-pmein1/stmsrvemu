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
        }
        version = fields[1]
        try:
            # Parse version 3
            if version > 2:
                sub_id_count = struct.unpack('<H', ticket_stream.read(2))[0]  # 2-byte count for version 3
                subscription_ids = []
                self.ticket_info['Subscription Count'] = sub_id_count
                for _ in range(sub_id_count):
                    sub_id = struct.unpack('<I', ticket_stream.read(4))[0]  # 4-byte sub ID
                    ticket_stream.read(1)  # Skip null byte at the end of each sub ID
                    subscription_ids.append(sub_id)
                self.ticket_info["Subscription IDs"] = subscription_ids

            # Parse version 4
            if version > 3:
                dlc_id_count = struct.unpack('<H', ticket_stream.read(2))[0]  # 2-byte count of DLC IDs
                dlc_ids = []
                self.ticket_info['DLC Count'] = dlc_id_count
                for _ in range(dlc_id_count):
                    dlc_id = struct.unpack('<I', ticket_stream.read(4))[0]  # 4-byte DLC ID
                    ticket_stream.read(1)  # Skip null byte at the end of each DLC ID
                    dlc_ids.append(dlc_id)

                self.ticket_info["DLC IDs"] = dlc_ids

                # VAC banned flag
                is_vac_banned = struct.unpack('<H', ticket_stream.read(2))[0]  # 2-byte VAC banned flag
                self.ticket_info["VAC Banned"] = bool(is_vac_banned)
        except:
            pass

        # Check if there are extra bytes in the ticket
        remaining_bytes = ticket_stream.read()
        if remaining_bytes:
            print(f"Extra bytes in ticket: {remaining_bytes, len(remaining_bytes)}")

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


def parse_auth_ticket(byte_data):
    """
    Parses the byte string constructed by the decompiled CCMInterface::SendAuthTicketToCM function.
    """
    parsed_data = {}

    try:
        # Start of the message
        offset = 0

        # 1. Header field: 5502 (4 bytes)
        parsed_data['header'] = struct.unpack_from("<I", byte_data, offset)[0]
        offset += 4

        # 2. Payload size (4 bytes)
        payload_size = struct.unpack_from("<I", byte_data, offset)[0]
        parsed_data['ticket_length'] = payload_size
        offset += 4

        # 3. Payload (variable size)
        if payload_size > 0:
            payload = byte_data[offset:offset + payload_size]
            offset += payload_size

            # Parse the payload using parse_ticket
            ticket_parser = MsgClientGetAppOwnershipTicketResponse()
            ticket_parser.parse_ticket(payload)
            parsed_data['ticket_info'] = ticket_parser.ticket_info
        else:
            parsed_data['ticket'] = b''
            parsed_data['ticket_info'] = {}

    except struct.error as e:
        raise ValueError(f"Failed to parse byte data: {e}")

    return parsed_data


# Example usage
if __name__ == "__main__":
    # Replace this with the byte string to parse
    packet = b'\x19\x00\x01\x00\xa8\x00\x00\x000\x00\x00\x00\x02\x00\x00\x00\x02\x00\x00\x00\x01\x00\x10\x01\x07\x00\x00\x00@\xed\x87H@\xed\x87H\x00\x00\x00\x00\x01\xc2;g\x11\xd0;g\x8eI\xa4\xecS&S\xd9\x8f\x1d\xc9\xe3eKu\x16\x0f\x9b\xd4I\x9a\x13}\xa7\xb9tI(\x83\xddS\xb2l\xb1\xb3\x90%G\x8d\xfe\xf4\xbbh\xa7\xdd\xa1\x84\\e\x7fz\x90/\xa5hb4\x01\xecT\x8d)]\x9f\x0e0\xed\xbc\x1c\'\x07\xf3\xab\xff\xb6\x86\xaf\xc0\x05\xa1\x14\xaa\xee"\x1a\xd3XJ^\xff\xdc\xd0C:\xbb\xf5\xb4\xe9\t\xbd\xba\x08\xe5\x15\x86{M\xcc\x1ev|Rr\xf8\xder\xeb\xf7!AS\x14\xdf\x95S\x8e\xb2\xd2'
    parsed_result = parse_auth_ticket(packet)

    for key, value in parsed_result.items():
        print(f"{key}: {value}")