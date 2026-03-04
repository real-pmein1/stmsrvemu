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
packet = b"I\x03\x00\x00$\x02\x00\x12\x00\x00\x00\x00\x00\x00\x00\xff\xff\xff\xff\xff\xff\xff\xff\xef\xc4\xa0\x9b\x01\x01\x00\x10\x01\xa0'\x0e\x00\x15\x00\x00\x00\x02\r\x00\x00\x13\x1c\x00\x00\x02\x003330\x00\x01icon\x000d252b5ad580d6a8ec07dab2c8a3afb30673ae35\x00\x01logo\x001168009462383309b3b8de28f0da96dd612459b9\x00\x01logo_small\x00842cbef810fed4c0a0bc384bc9973081213dfb5b\x00\x01name\x00Zuma Deluxe\x00\x01gameid\x003330\x00\x08\x08\x00\x0c\r\x00\x00\x13\x1c\x00\x00\x02\x003340\x00\x01icon\x002406382f6c24dafa633ac17e866a26654eeb30ec\x00\x01logo\x005317abfa1905a3bc73af08081232b1dba50ba41c\x00\x01logo_small\x00197ce556b758b94a88ac691da1b70ddeaa1d4661\x00\x01name\x00AstroPop Deluxe\x00\x01gameid\x003340\x00\x08\x08\x00\x16\r\x00\x00\x13\x1c\x00\x00\x02\x003350\x00\x01icon\x00314ee4635f2ab7662f7ef4b7775336817f5635e8\x00\x01logo\x00121f321ec3a92e877ca3c947683fed050427d3b6\x00\x01logo_small\x005b2f2fb9eb123c36a6feb4b0177467f4c18101c2\x00\x01name\x00Bejeweled Deluxe\x00\x01gameid\x003350\x00\x08\x08\x00 \r\x00\x00\x13\x1c\x00\x00\x02\x003360\x00\x01icon\x000ac7a0b5f69757ba52582668f057872bc8874842\x00\x01logo\x004f72f65ddab16fedba874e752deb52575913ac3a\x00\x01logo_small\x001e281501891debbdcff8deb78040edbbc115317f\x00\x01name\x00Big Money Deluxe\x00\x01gameid\x003360\x00\x08\x08\x00*\r\x00\x00\x13\x1c\x00\x00\x02\x003370\x00\x01icon\x002804cda520672511041a5949903f454ff70b2211\x00\x01logo\x001369f5d7426f2b5bed900e8693393d1e2b631b98\x00\x01logo_small\x004c092017e0ad1af17d240291fb4ad425d681c9a8\x00\x01name\x00BookWorm Deluxe\x00\x01gameid\x003370\x00\x08\x08\x004\r\x00\x00\x13\x1c\x00\x00\x02\x003380\x00\x01icon\x0047157cdfac7ef60d1d5effeacbc3052564b680c3\x00\x01logo\x008df2d4eae48695b733ce856650cefa8ad493f4ea\x00\x01logo_small\x00aab2fa517cbfcbc5ea996153e782b2289466e176\x00\x01name\x00Dynomite Deluxe\x00\x01gameid\x003380\x00\x08\x08\x00>\r\x00\x00\x13\x1c\x00\x00\x02\x003390\x00\x01icon\x00d34697dfa581120f4204fef71e2fbdf9a4800b6b\x00\x01logo\x00c516eb69b60d3987b0bb2ffb39a006a6be0953ba\x00\x01logo_small\x002a335184550c02ef8253db581358be9aebb18058\x00\x01name\x00Feeding Frenzy 2 Deluxe\x00\x01gameid\x003390\x00\x08\x08\x00H\r\x00\x00\x13\x1c\x00\x00\x02\x003400\x00\x01icon\x001671ed3cfa9bee9a1d29a7a002f143c0e7204958\x00\x01logo\x00a5017b229c6eda2e80e8bf002462c4cd5c48b65b\x00\x01logo_small\x001cbf1693859bf7d9f54d47abad7a3c599210317b\x00\x01name\x00Hammer Heads Deluxe\x00\x01gameid\x003400\x00\x08\x08\x00\xdc\x00\x00\x00\x13\x1c\x00\x00\x02\x00220\x00\x01icon\x00f118f400f3ccd9a8331ea975e8dd8d14584904f3\x00\x01logo\x00e4ad9cf1b7dc8475c1118625daf9abd4bdcbcad0\x00\x01logo_small\x00c2e409b1d9313648a4865b8aff9aba98fc6b4f04\x00\x01metacritic_url\x00pc/halflife2\x00\x01name\x00Half-Life 2\x00\x01metacritic_score\x0096\x00\x01gameid\x00220\x00\x08\x08\x00R\r\x00\x00\x13\x1c\x00\x00\x02\x003410\x00\x01icon\x0032180a539f834902f5d4ad1e8fb9a7ffa23d627f\x00\x01logo\x00f31011b715170baf123d0a6b8a530e3ce23565d0\x00\x01logo_small\x00c3118af99662ed4dbb54652650f8c053512add2b\x00\x01name\x00Heavy Weapon Deluxe\x00\x01gameid\x003410\x00\x08\x08\x00\\\r\x00\x00\x13\x1c\x00\x00\x02\x003420\x00\x01icon\x009c72c7c69e4a0b5308adb3bae85b55c511dd1d18\x00\x01logo\x002b9bd2c3e4252b453eca7add88348d3e7348ec91\x00\x01logo_small\x008a721dcdd0177fdbd460b188a85cfbcc910be664\x00\x01name\x00Iggle Pop Deluxe\x00\x01gameid\x003420\x00\x08\x08\x00f\r\x00\x00\x13\x1c\x00\x00\x02\x003430\x00\x01icon\x007361120ac7954053d232afc84e549ba3955928c6\x00\x01logo\x00d9c446b9dc5453f29b79373b61b9c1474fa06e5b\x00\x01logo_small\x002209776f3fd319a226172d05b7e4040e39a45ca6\x00\x01name\x00Pizza Frenzy\x00\x01gameid\x003430\x00\x08\x08\x00p\r\x00\x00\x13\x1c\x00\x00\x02\x003440\x00\x01icon\x0002074084ef06b81b974d6e81b3f057e19caebbea\x00\x01logo\x000f0ebb0a89b237e161f90492171444b0282beb5d\x00\x01logo_small\x00ac744b3e351625be6691185296bd31211517ba04\x00\x01name\x00Rocket Mania Deluxe\x00\x01gameid\x003440\x00\x08\x08\x00z\r\x00\x00\x13\x1c\x00\x00\x02\x003450\x00\x01icon\x0056228faf863bd22e191e41c959f3a6f20ea5b7b6\x00\x01logo\x0054fd641279e3385126ed14661c19baf67df4fa44\x00\x01logo_small\x00cc95383d046e087f0a04cde0453fbbd9e727d18b\x00\x01name\x00Typer Shark Deluxe\x00\x01gameid\x003450\x00\x08\x08\x00\x84\r\x00\x00\x13\x1c\x00\x00\x02\x003460\x00\x01icon\x00e64024d90c54fa9a771c502de0e0dbec0820204a\x00\x01logo\x00ede35957a2255dce6e80a136779106f573aff51a\x00\x01logo_small\x008cc746076b606583deb4533041bbce1f788f9bc7\x00\x01name\x00Talismania Deluxe\x00\x01gameid\x003460\x00\x08\x08\x00\x84g\x00\x00\x13\x1c\x00\x00\x02\x0026500\x00\x01name\x00Cogs\x00\x01logo\x00db01e5e8973e4a9590f1423b9c7c2199d7cb0186\x00\x01logo_small\x00db01e5e8973e4a9590f1423b9c7c2199d7cb0186_thumb\x00\x01icon\x0079586b14e3c64d447a3dbb6e18369636b9b5dfb0\x00\x01clienttga\x005858638b1a7d50d9f5456643bbe4c3383fb80045\x00\x01clienticon\x006975a115811754cfd0a1adcc0998918e13cce1de\x00\x01metacritic_url\x00pc/cogs\x00\x01metacritic_score\x0073\x00\x01gameid\x0026500\x00\x08\x08\x00\x8e\r\x00\x00\x13\x1c\x00\x00\x02\x003470\x00\x01icon\x00f4e54986a0ec32bb5e406f97f11304862bed5808\x00\x01logo\x0054061041975a2494439069316c2e7f26cc886d6e\x00\x01logo_small\x00abfd659eb2d8cd27acf71c06211c898708ee3148\x00\x01metacritic_url\x00pc/bookwormadventures\x00\x01name\x00Bookworm Adventures Deluxe\x00\x01metacritic_score\x0082\x00\x01gameid\x003470\x00\x08\x08\x00\xe4\x0c\x00\x00\x13\x1c\x00\x00\x02\x003300\x00\x01icon\x000dbd400f2e459d89a5579bc7aa28a271cc122e80\x00\x01logo\x00405eea6c0c3e0d9535c9951d3ba37043f9de89be\x00\x01logo_small\x003b4f993bc1c7a814fa6aea08f829707c2fb94b09\x00\x01name\x00Bejeweled 2 Deluxe\x00\x01gameid\x003300\x00\x08\x08\x00\xee\x0c\x00\x00\x13\x1c\x00\x00\x02\x003310\x00\x01icon\x00367ce081ed4fb0b1012f2bebac3c23ce8987922d\x00\x01logo\x00e5913393ea0e5adfd830f0d369263205363ae42a\x00\x01logo_small\x00292dc8894a18ffee023fa69300330df240c37e53\x00\x01name\x00Chuzzle Deluxe\x00\x01gameid\x003310\x00\x08\x08\x00\xf0\x05\x00\x00\x13\x1c\x00\x00\x02\x001520\x00\x01icon\x008ba747cadcc86d73db492c42d507ac4eb15ea850\x00\x01logo\x00585ccf3dfba5d1df40cda98960e199a84f340c20\x00\x01logo_small\x00be588d7337eaf9b30e69c9829d96ae70257b9a52\x00\x01metacritic_url\x00pc/defcon\x00\x01name\x00Defcon\x00\x01metacritic_score\x0084\x00\x01gameid\x001520\x00\x08\x08\x00\xf8\x0c\x00\x00\x13\x1c\x00\x00\x02\x003320\x00\x01icon\x00fb45c0144e6717e18c6c4e59605b4350ffa3cfde\x00\x01logo\x0083b92e483a66d7c2b2542659845979606d9cd290\x00\x01logo_small\x00dcfae07a72eafd9ad0929f8321991804b585ed02\x00\x01name\x00Insaniquarium Deluxe\x00\x01gameid\x003320\x00\x08\x08\x00"


packet = packet[36:]

parser = AppDataParser()
parser.parse_client_app_info_response(packet)