import struct
import datetime
import io


class ApplicationData:
    """
    Class to store data for a single application.
    """
    def __init__(self, app_id):
        self.app_id = app_id
        self.state = None
        self.last_change = None
        self.change_number = None
        self.sections = {}      # Dictionary to store section data
        self.sections_raw = {}  # Dictionary to store raw bytes of each section

    def __repr__(self):
        return f"<ApplicationData app_id={self.app_id}>"


class BytesRecordingReader:
    """
    A wrapper around a reader that records bytes read when recording is enabled.
    """
    def __init__(self, reader):
        self.reader = reader
        self.recording = False
        self.recorded_bytes = bytearray()

    def read(self, n=-1):
        data = self.reader.read(n)
        if self.recording and data:
            self.recorded_bytes.extend(data)
        return data

    def start_recording(self):
        self.recorded_bytes = bytearray()
        self.recording = True

    def stop_recording(self):
        self.recording = False

    def get_recorded_bytes(self):
        return bytes(self.recorded_bytes)

    def __getattr__(self, name):
        return getattr(self.reader, name)


class AppInfoParser:
    """
    Class to parse appinfo files of various versions and make the data accessible.
    """
    def __init__(self, input_file):
        self.input_file = input_file
        self.applications = []  # List to store ApplicationData instances
        self.universe = None
        self.parse()

    def parse(self):
        with open(self.input_file, 'rb') as reader:
            reader = BytesRecordingReader(reader)  # Wrap the reader
            # Read the magic number
            magic_bytes = reader.read(4)
            if len(magic_bytes) < 4:
                raise Exception("File too short to read magic number")
            magic = struct.unpack('<I', magic_bytes)[0]

            # Map magic numbers to parsing methods
            magic_methods = {
                    0x02464456: self.parse_app_data_cache_v1,
                    0x06564424: self.parse_app_data_cache_v2,
                    0x07564425: self.parse_app_data_cache_v2,
                    0x06565524: self.parse_package_data_cache,
                    0x06565525: self.parse_package_data_cache,
                    0xFFFFFFFF: self.parse_single_app_data_cache_v2,
                    None: self.parse_single_app_data_cache_v1,
            }

            if magic in magic_methods:
                magic_methods[magic](reader, magic)
            else:
                raise Exception(f"Unknown magic number: 0x{magic:08X}")

    def parse_app_data_cache_v1(self, reader, magic = None):
        universe_bytes = reader.read(4)
        if len(universe_bytes) < 4:
            raise Exception("Unexpected end of file when reading universe")
        self.universe = struct.unpack('<i', universe_bytes)[0]

        while True:
            app_id_bytes = reader.read(4)
            if len(app_id_bytes) < 4:
                raise Exception("Unexpected end of file when reading appId")
            app_id = struct.unpack('<i', app_id_bytes)[0]
            if app_id == 0:
                break

            state_bytes = reader.read(4)
            if len(state_bytes) < 4:
                raise Exception("Unexpected end of file when reading state")
            state = struct.unpack('<i', state_bytes)[0]

            last_change_bytes = reader.read(4)
            if len(last_change_bytes) < 4:
                raise Exception("Unexpected end of file when reading lastChange")
            last_change_unix = struct.unpack('<I', last_change_bytes)[0]
            last_change = self._convert_timestamp(last_change_unix)

            change_number_bytes = reader.read(4)
            if len(change_number_bytes) < 4:
                raise Exception("Unexpected end of file when reading changeNumber")
            change_number = struct.unpack('<i', change_number_bytes)[0]

            app_data = ApplicationData(app_id)
            app_data.state = state
            app_data.last_change = last_change
            app_data.change_number = change_number

            # Parse sections
            self.parse_app_data_cache_sections(reader, app_data)

            # Add to applications list
            self.applications.append(app_data)

    def parse_app_data_cache_v2(self, reader, magic = None):
        universe_bytes = reader.read(4)
        if len(universe_bytes) < 4:
            raise Exception("Unexpected end of file when reading universe")
        self.universe = struct.unpack('<i', universe_bytes)[0]

        while True:
            app_id_bytes = reader.read(4)
            if len(app_id_bytes) < 4:
                raise Exception("Unexpected end of file when reading appId")
            app_id = struct.unpack('<i', app_id_bytes)[0]
            if app_id == 0:
                break

            data_size_bytes = reader.read(4)
            if len(data_size_bytes) < 4:
                raise Exception("Unexpected end of file when reading dataSize")
            data_size = struct.unpack('<i', data_size_bytes)[0]

            data = reader.read(data_size)
            if len(data) != data_size:
                raise Exception("Unexpected end of file when reading data")

            data_reader = BytesRecordingReader(io.BytesIO(data))

            state_bytes = data_reader.read(4)
            if len(state_bytes) < 4:
                raise Exception("Unexpected end of data when reading state")
            state = struct.unpack('<i', state_bytes)[0]

            last_change_bytes = data_reader.read(4)
            if len(last_change_bytes) < 4:
                raise Exception("Unexpected end of data when reading lastChange")
            last_change_unix = struct.unpack('<I', last_change_bytes)[0]
            last_change = self._convert_timestamp(last_change_unix)

            change_number_bytes = data_reader.read(4)
            if len(change_number_bytes) < 4:
                raise Exception("Unexpected end of data when reading changeNumber")
            change_number = struct.unpack('<i', change_number_bytes)[0]

            app_data = ApplicationData(app_id)
            app_data.state = state
            app_data.last_change = last_change
            app_data.change_number = change_number

            # Parse sections
            self.parse_app_data_cache_sections(data_reader, app_data)

            # Add to applications list
            self.applications.append(app_data)

    def parse_single_app_data_cache_v1(self, reader, app_id):
        app_data = ApplicationData(app_id)

        # Parse sections
        self.parse_app_data_cache_sections(reader, app_data)

        # Add to applications list
        self.applications.append(app_data)
    def parse_single_app_data_cache_v2(self, reader, magic = None):
        unknown1_bytes = reader.read(4)
        if len(unknown1_bytes) < 4:
            raise Exception("Unexpected end of file when reading unknown1")
        unknown1 = struct.unpack('<i', unknown1_bytes)[0]

        app_id_bytes = reader.read(4)
        if len(app_id_bytes) < 4:
            raise Exception("Unexpected end of file when reading appId")
        app_id = struct.unpack('<i', app_id_bytes)[0]

        unknown2_bytes = reader.read(4)
        if len(unknown2_bytes) < 4:
            raise Exception("Unexpected end of file when reading unknown2")
        unknown2 = struct.unpack('<i', unknown2_bytes)[0]

        unknown3_bytes = reader.read(4)
        if len(unknown3_bytes) < 4:
            raise Exception("Unexpected end of file when reading unknown3")
        unknown3 = struct.unpack('<i', unknown3_bytes)[0]

        # Parse application data
        app_data = ApplicationData(app_id)
        # unknown1, unknown2, and unknown3 can be stored if needed

        # Parse sections
        self.parse_app_data_cache_sections(reader, app_data)

        # Add to applications list
        self.applications.append(app_data)

    def parse_package_data_cache(self, reader, magic = None):
        unknown1_bytes = reader.read(4)
        if len(unknown1_bytes) < 4:
            raise Exception("Unexpected end of file when reading unknown1")
        unknown1 = struct.unpack('<i', unknown1_bytes)[0]

        # Packages can be stored similarly to applications if needed
        self.packages = []

        while True:
            sub_id_bytes = reader.read(4)
            if len(sub_id_bytes) < 4:
                raise Exception("Unexpected end of file when reading subId")
            sub_id = struct.unpack('<i', sub_id_bytes)[0]
            if sub_id == -1:
                break

            unknown3 = reader.read(20)
            if len(unknown3) != 20:
                raise Exception("Unexpected end of file when reading unknown3")

            package_data = {
                'sub_id': sub_id,
                'unknown3': unknown3.hex(),
                'key_values': self.parse_key_values(reader)
            }

            self.packages.append(package_data)

    def parse_app_data_cache_sections(self, reader, app_data):
        while True:
            section_type_bytes = reader.read(1)
            if len(section_type_bytes) < 1:
                raise Exception("Unexpected end of file when reading sectionType")
            section_type = section_type_bytes[0]
            if section_type == 0:
                break

            # Map section types to names
            section_type_string = {
                1: "All",
                2: "Common",
                3: "Extended",
                4: "Config",
                5: "Stats",
                6: "Install",
                7: "Depots",
                8: "VAC",
                9: "DRM",
                10: "UFS",
                11: "OGG",
                12: "Items",
                13: "Policies",
                14: "SystemRequirements",
                15: "Community",
            }.get(section_type, str(section_type))

            # Start recording bytes
            reader.start_recording()

            # Parse key-values for this section
            section_data = self.parse_key_values(reader)

            # Stop recording bytes
            reader.stop_recording()
            raw_bytes = reader.get_recorded_bytes()

            # Adjust raw bytes according to your specifications
            raw_bytes = self.adjust_raw_bytes(section_type, raw_bytes)

            # Store the section data and raw bytes in the app_data
            app_data.sections[section_type_string] = section_data
            app_data.sections_raw[section_type_string] = raw_bytes

    def adjust_raw_bytes(self, section_type, raw_bytes):
        """
        Adjusts the raw bytes of a section according to the specified rules.
        """
        # Remove the appid from the Common section
        if section_type == 2:
            # Find the position after the second null byte
            if raw_bytes.startswith(b'\x00'):
                second_null_index = raw_bytes.find(b'\x00', 1)
                if second_null_index != -1:
                    raw_bytes = raw_bytes[second_null_index + 1:]
            else:
                # Find the first null byte
                first_null_index = raw_bytes.find(b'\x00')
                if first_null_index != -1:
                    raw_bytes = raw_bytes[first_null_index + 1:]
        else:
            # Remove the section name and its null byte
            if raw_bytes.startswith(b'\x00'):
                second_null_index = raw_bytes.find(b'\x00', 1)
                if second_null_index != -1:
                    raw_bytes = raw_bytes[second_null_index + 1:]
            else:
                first_null_index = raw_bytes.find(b'\x00')
                if first_null_index != -1:
                    raw_bytes = raw_bytes[first_null_index + 1:]

        # Insert the section ID as a uint8 byte at the beginning
        raw_bytes = struct.pack('B', section_type) + raw_bytes
        return raw_bytes

    def parse_key_values(self, reader):
        data = {}
        while True:
            value_type_bytes = reader.read(1)
            if len(value_type_bytes) < 1:
                raise Exception("Unexpected end of file when reading valueType")
            value_type = value_type_bytes[0]
            if value_type == 8:  # End marker
                break

            name = self.read_string(reader)
            if value_type == 0:  # Nested key
                # Recursively parse nested key-values
                nested_data = self.parse_key_values(reader)
                data[name] = nested_data
            else:
                value = self.read_value(reader, value_type)
                data[name] = value
        return data

    def read_string(self, reader):
        chars = []
        while True:
            b = reader.read(1)
            if len(b) == 0:
                raise Exception("Unexpected end of file when reading string")
            if b == b'\x00':
                break
            chars.append(b)
        s = b''.join(chars).decode('utf-8', errors='replace')
        s = s.replace('\v', '\\v')
        return s

    def read_wide_string(self, reader):
        chars = []
        while True:
            w = reader.read(2)
            if len(w) < 2:
                raise Exception("Unexpected end of file when reading wide string")
            char = struct.unpack('<H', w)[0]
            if char == 0:
                break
            if char == 0x0B:
                chars.append('\\v')
            else:
                chars.append(chr(char))
        return ''.join(chars)

    def read_value(self, reader, value_type):
        if value_type == 1:
            value_string = self.read_string(reader)
            return value_string
        elif value_type == 2:
            value_int32_bytes = reader.read(4)
            if len(value_int32_bytes) < 4:
                raise Exception("Unexpected end of file when reading int32 value")
            value_int32 = struct.unpack('<i', value_int32_bytes)[0]
            return value_int32
        elif value_type == 3:
            value_float_bytes = reader.read(4)
            if len(value_float_bytes) < 4:
                raise Exception("Unexpected end of file when reading float value")
            value_float = struct.unpack('<f', value_float_bytes)[0]
            return value_float
        elif value_type == 5:
            value_wstring = self.read_wide_string(reader)
            return value_wstring
        elif value_type == 6:
            color_bytes = reader.read(3)
            if len(color_bytes) < 3:
                raise Exception("Unexpected end of file when reading color value")
            value_color_r, value_color_g, value_color_b = struct.unpack('<BBB', color_bytes)
            return (value_color_r, value_color_g, value_color_b)
        elif value_type == 7:
            value_uint64_bytes = reader.read(8)
            if len(value_uint64_bytes) < 8:
                raise Exception("Unexpected end of file when reading uint64 value")
            value_uint64 = struct.unpack('<Q', value_uint64_bytes)[0]
            return value_uint64
        else:
            raise Exception(f"Unknown or unimplemented value type: {value_type}")

    def _convert_timestamp(self, unix_time):
        """
        Converts the given Steam time (Unix timestamp + offset) to a datetime object.
        """
        # Steam uses timestamps with a base offset of 62135596800
        # which is the difference between 1970-01-01 and 1601-01-01 in seconds
        base_offset = 62135596800
        return datetime.datetime.utcfromtimestamp(unix_time + base_offset)

    def get_applications(self):
        """
        Returns the list of applications parsed.
        """
        return self.applications

    def get_application_by_id(self, app_id):
        """
        Returns the application data for the given app_id.

        :param app_id: The application ID to look for.
        :return: An ApplicationData instance or None if not found.
        """
        for app in self.applications:
            if app.app_id == app_id:
                return app
        return None

# Example usage
if __name__ == "__main__":
    input_file = "app_520.vdf"
    parser = AppInfoParser(input_file)

    # Access the list of applications
    applications = parser.get_applications()
    print(f"Total applications parsed: {len(applications)}")

    # Iterate over applications and access their data
    for app in applications:
        print(f"App ID: {app.app_id}")
        print(f"State: {app.state}")
        print(f"Last Change: {app.last_change}")
        print(f"Change Number: {app.change_number}")

        # Access sections
        for section_name, section_data in app.sections.items():
            print(f"Section: {section_name}")
            print(f"Data: {section_data}")

            # Access raw bytes of the section
            raw_bytes = app.sections_raw.get(section_name)
            if raw_bytes:
                print(f"Raw Bytes (hex): {raw_bytes}")
        print("-" * 40)