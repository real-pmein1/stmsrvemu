import struct
from io import BytesIO


class KeyValues:
    """Simplified KeyValues class for parsing binary data."""
    def __init__(self, name):
        self.name = name
        self.data = {}

    def read_as_binary(self, buffer):
        # Simulated binary read of KeyValues data (simplified for demonstration)
        # Example: Let's assume it reads a simple 4-byte integer as part of the key-value data.
        data_len = struct.unpack('<I', buffer.read(4))[0]  # Example key-value size
        self.data['example_key'] = buffer.read(data_len)  # Read that many bytes as data

    def get_crc32(self):
        # Simulate CRC32 calculation for KeyValues (just a placeholder)
        return 0xDEADBEEF


class CAppDataSection:
    def __init__(self, section_type):
        self.vptr = None  # Placeholder for virtual function pointer
        self.section_type = section_type
        self.CRC32 = 0
        self.key_values = KeyValues(f"section_{section_type}")

    def deserialize(self, buffer):
        # Deserialize KeyValues in this section
        self.key_values.read_as_binary(buffer)
        self.CRC32 = self.key_values.get_crc32()
        return self





class CAppData:
    def __init__(self):
        self.m_bHasGameDir = False
        self.m_mapSections = {}

    def read_sections_from_buffer(self, buffer):
        num_updated_sections = 0
        while True:
            section_type = buffer.get_uint8()  # Read the next section type (1 byte)
            print(f"Section Type: {section_type}")

            if section_type == 0:
                break  # No more sections

            # Assuming you have a function to handle reading the section
            self.handle_section(buffer, section_type)

            num_updated_sections += 1

        return num_updated_sections

    def handle_section(self, buffer, section_type):
        print(f"Handling section: {section_type}")
        # Logic to handle each section based on section type
        # Add your own logic to handle KeyValues or other formats.
        # Example: buffer.read_key_values() or buffer.get_unsigned_int(), etc.
        pass

class CUtlBuffer:
    def __init__(self, data):
        self.stream = BytesIO(data)

    def get_uint8(self):
        result = self.stream.read(1)
        if len(result) < 1:
            raise ValueError("No more bytes available to read a uint8.")
        return struct.unpack('<B', result)[0]

    def get_unsigned_int(self):
        result = self.stream.read(4)
        if len(result) < 4:
            raise ValueError("No more bytes available to read an unsigned int.")
        return struct.unpack('<I', result)[0]

class MsgClientAppInfoResponse:
    def __init__(self):
        self.num_apps = 0

    def deserialize(self, buffer):
        # Read number of apps
        self.num_apps = struct.unpack('<I', buffer.read(4))[0]
        return self


class AppDataParser:
    def __init__(self):
        self.app_data = CAppData()

    def parse_client_app_info_response(self, packet_data):
        buffer = CUtlBuffer(packet_data)

        # Parse application data sections from the buffer
        app_id, updated_sections = self.parse_app_data(buffer)
        print(f"App ID: {app_id}, Updated Sections: {updated_sections}")

    def parse_app_data(self, buffer):
        # Read App ID (4 bytes)
        count = buffer.get_unsigned_int()
        app_id = buffer.get_unsigned_int()
        print(f"Parsed App ID: {app_id}")

        # Read sections from the buffer
        num_sections_updated = self.app_data.read_sections_from_buffer(buffer)
        return app_id, num_sections_updated


# Example usage
packet = b'a\x03\x00\x00$\x02\x003\x00\x00\x00\x00\x00\x00\x00\xff\xff\xff\xff\xff\xff\xff\xff\xef\xc4\xa0\x9b\x01\x01\x00\x10\x01\x00v/\x00\x01\x00\x00\x00X>\x00\x00\x02\x0015960\x00\x01name\x00Little Farm\x00\x01logo\x00af9e038e8ff245406a798f0155a445442ff5fd08\x00\x01logo_small\x00945452d390e6f78810333c6a1bee517d50b2807f\x00\x01icon\x0036244468bcbe5d3382f205b3df07aa2ab4258108\x00\x01gameid\x0015960\x00\x08\x08\x00'

packet = packet[36:]

parser = AppDataParser()
parser.parse_client_app_info_response(packet)