import struct

from steam3.Types.Objects.AppOwnershipTicket import Steam3AppOwnershipTicket


class MsgClientRegisterAuthTicketWithCM:
    def __init__(self):
        self.header = None
        self.ticket_length = None
        self.ticket = None
        self.signature = None
        self.parsed_ticket = None  # Instance of Steam3AppOwnershipTicket

    def deserialize(self, byte_data):
        """
        Deserialize the byte string and parse the header, payload size, ticket info, and signature.
        """
        try:
            offset = 0

            # 1. Header field: 5502 (4 bytes)
            self.header = struct.unpack_from("<I", byte_data, offset)[0]
            offset += 4

            # 2. Payload size (4 bytes)
            self.ticket_length = struct.unpack_from("<I", byte_data, offset)[0]
            offset += 4

            # 3. Ticket data (variable size)
            if self.ticket_length > 0:
                ticket_data = byte_data[offset:offset + self.ticket_length]
                offset += self.ticket_length

                # Parse ticket using Steam3AppOwnershipTicket
                self.parsed_ticket = Steam3AppOwnershipTicket()
                self.parsed_ticket.parse_ticket(ticket_data)

            # 4. Cryptographic signature (remaining bytes)
            if offset < len(byte_data):
                self.signature = byte_data[offset:]

        except struct.error as e:
            raise ValueError(f"Failed to parse byte data: {e}")

    def __str__(self):
        """
        Return a string representation of the parsed data.
        """
        return (
            f"AuthTicketParser(\n"
            f"  Header: {self.header}\n"
            f"  Ticket Length: {self.ticket_length}\n"
            f"  Parsed Ticket: {self.parsed_ticket}\n"
            f"  Signature: {self.signature.hex() if self.signature else None}\n"
            f")"
        )


# Example Usage
"""if __name__ == "__main__":
    # Example packet data
    packet = b'\x19\x00\x01\x00\xa8\x00\x00\x000\x00\x00\x00\x02\x00\x00\x00\x02\x00\x00\x00\x01\x00\x10\x01\x07\x00\x00\x00@\xed\x87H@\xed\x87H\x00\x00\x00\x00\x01\xc2;g\x11\xd0;g\x8eI\xa4\xecS&S\xd9\x8f\x1d\xc9\xe3eKu\x16\x0f\x9b\xd4I\x9a\x13}\xa7\xb9tI(\x83\xddS\xb2l\xb1\xb3\x90%G\x8d\xfe\xf4\xbbh\xa7\xdd\xa1\x84\\e\x7fz\x90/\xa5hb4\x01\xecT\x8d)]\x9f\x0e0\xed\xbc\x1c\'\x07\xf3\xab\xff\xb6\x86\xaf\xc0\x05\xa1\x14\xaa\xee"\x1a\xd3XJ^\xff\xdc\xd0C:\xbb\xf5\xb4\xe9\t\xbd\xba\x08\xe5\x15\x86{M\xcc\x1ev|Rr\xf8\xder\xeb\xf7!AS\x14\xdf\x95S\x8e\xb2\xd2' \
             + b'\x12\x34\x56\x78\x9a\xbc\xde\xf0'  # Example signature

    # Parse the ticket
    parser = AuthTicketParser()
    parser.deserialize(packet)
    print(parser)"""