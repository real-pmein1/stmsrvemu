import struct
import datetime
import io
import logging
from typing import Optional, List

log = logging.getLogger("AppInfoParser")


class ApplicationData:
    """
    Class to store data for a single application.
    """
    def __init__(self, app_id):
        self.version = None
        self.app_id = app_id
        self.state = None
        self.last_change = None
        self.change_number = None
        self.is_allsections = False
        self.sections = {}      # Dictionary to store section data
        self.sections_raw = {}  # Dictionary to store raw bytes of each section
        # V2+ format fields (2014+)
        self.token = None       # uint64 access token
        self.sha_digest = None  # 20-byte SHA digest
        # For indexed random access
        self.file_offset = None  # Byte offset in VDF file
        self.data_size = None    # Total size of app entry in bytes

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
            # V1 (2010-2012): 0x02464456 (VDF\x02)
            # V2 (2012-2014): 0x06564424 ($DV\x06), 0x07564425
            # V2+ (2014+): 0x07564426, 0x07564427 (with token and SHA)
            magic_methods = {
                    0x02464456: self.parse_single_appinfo_file_v1,
                    0x06564424: self.parse_single_appinfo_file_v2,
                    0x07564425: self.parse_single_appinfo_file_v2,
                    0x07564426: self.parse_single_appinfo_file_v2_plus,
                    0x07564427: self.parse_single_appinfo_file_v2_plus,
                    0x06565524: self.parse_package_data_cache,
                    0x06565525: self.parse_package_data_cache,
                    0xFFFFFFFF: self.parse_individual_appinfo_file_v2,
            }

            if magic in magic_methods:
                magic_methods[magic](reader, magic)
            else:
                try:
                    reader.seek(0)  # Rewind the reader
                    self.parse_individual_appinfo_file_v1(reader)
                except:
                    raise Exception(f"Unknown magic number: 0x{magic:08X}")

    def parse_single_appinfo_file_v1(self, reader, magic=None):
        universe_bytes = reader.read(4)
        if len(universe_bytes) < 4:
            raise Exception("Unexpected end of file when reading universe")

        self.universe = struct.unpack('<i', universe_bytes)[0]

        while True:
            # Record position for indexed access
            app_start_pos = reader.tell() if hasattr(reader, 'tell') else None

            app_id_bytes = reader.read(4)
            if len(app_id_bytes) < 4:
                break  # Normal EOF
            app_id = struct.unpack('<I', app_id_bytes)[0]
            if app_id == 0:
                break

            state_bytes = reader.read(4)
            if len(state_bytes) < 4:
                raise Exception("Unexpected end of file when reading state")
            state = struct.unpack('<I', state_bytes)[0]

            last_change_bytes = reader.read(4)
            if len(last_change_bytes) < 4:
                raise Exception("Unexpected end of file when reading lastChange")
            last_change_unix = struct.unpack('<I', last_change_bytes)[0]
            last_change = self._convert_timestamp(last_change_unix)

            change_number_bytes = reader.read(4)
            if len(change_number_bytes) < 4:
                raise Exception("Unexpected end of file when reading changeNumber")
            change_number = struct.unpack('<I', change_number_bytes)[0]

            app_data = ApplicationData(app_id)
            app_data.state = state
            app_data.last_change = last_change
            app_data.change_number = change_number

            # Parse sections
            self.parse_app_data_cache_sections(reader, app_data)

            # Store position info for indexed access
            if app_start_pos is not None:
                app_end_pos = reader.tell() if hasattr(reader, 'tell') else None
                if app_end_pos is not None:
                    app_data.file_offset = app_start_pos
                    app_data.data_size = app_end_pos - app_start_pos

            # Add to applications list
            self.applications.append(app_data)

    def parse_single_appinfo_file_v2(self, reader, magic=None):
        universe_bytes = reader.read(4)
        if len(universe_bytes) < 4:
            raise Exception("Unexpected end of file when reading universe")

        self.universe = struct.unpack('<i', universe_bytes)[0]

        while True:
            # Record position for indexed access
            app_start_pos = reader.tell() if hasattr(reader, 'tell') else None

            app_id_bytes = reader.read(4)
            if len(app_id_bytes) < 4:
                break  # Normal EOF
            app_id = struct.unpack('<I', app_id_bytes)[0]
            if app_id == 0:
                break

            data_size_bytes = reader.read(4)
            if len(data_size_bytes) < 4:
                raise Exception("Unexpected end of file when reading dataSize")
            data_size = struct.unpack('<I', data_size_bytes)[0]

            data = reader.read(data_size)
            if len(data) != data_size:
                raise Exception("Unexpected end of file when reading data")

            data_reader = BytesRecordingReader(io.BytesIO(data))

            state_bytes = data_reader.read(4)
            if len(state_bytes) < 4:
                raise Exception("Unexpected end of data when reading state")
            state = struct.unpack('<I', state_bytes)[0]

            last_change_bytes = data_reader.read(4)
            if len(last_change_bytes) < 4:
                raise Exception("Unexpected end of data when reading lastChange")
            last_change_unix = struct.unpack('<I', last_change_bytes)[0]
            last_change = self._convert_timestamp(last_change_unix)

            change_number_bytes = data_reader.read(4)
            if len(change_number_bytes) < 4:
                raise Exception("Unexpected end of data when reading changeNumber")
            change_number = struct.unpack('<I', change_number_bytes)[0]

            app_data = ApplicationData(app_id)
            app_data.state = state
            app_data.last_change = last_change
            app_data.change_number = change_number

            # Store position info for indexed access
            if app_start_pos is not None:
                app_data.file_offset = app_start_pos
                app_data.data_size = 8 + data_size  # app_id(4) + data_size(4) + data

            # Parse sections
            self.parse_app_data_cache_sections(data_reader, app_data)

            # Add to applications list
            self.applications.append(app_data)

    def parse_single_appinfo_file_v2_plus(self, reader, magic=None):
        """
        Parse V2+ format (2014+) with token and SHA digest.

        Format per app:
        - uint32: app_id
        - uint32: data_size (size of following data blob)
        - Data blob containing:
          - uint32: state
          - uint32: last_change (unix timestamp)
          - uint64: token (access token)
          - 20 bytes: sha_digest
          - uint32: change_number
          - Sections (until 0x00 terminator)
        """
        universe_bytes = reader.read(4)
        if len(universe_bytes) < 4:
            raise Exception("Unexpected end of file when reading universe")

        self.universe = struct.unpack('<i', universe_bytes)[0]

        while True:
            # Record position for indexed access
            app_start_pos = reader.tell() if hasattr(reader, 'tell') else None

            app_id_bytes = reader.read(4)
            if len(app_id_bytes) < 4:
                break  # Normal EOF
            app_id = struct.unpack('<I', app_id_bytes)[0]
            if app_id == 0:
                break

            data_size_bytes = reader.read(4)
            if len(data_size_bytes) < 4:
                raise Exception("Unexpected end of file when reading dataSize")
            data_size = struct.unpack('<I', data_size_bytes)[0]

            data = reader.read(data_size)
            if len(data) != data_size:
                raise Exception(f"Unexpected end of file when reading data for app {app_id}")

            data_reader = BytesRecordingReader(io.BytesIO(data))

            # Read state (4 bytes)
            state_bytes = data_reader.read(4)
            if len(state_bytes) < 4:
                raise Exception("Unexpected end of data when reading state")
            state = struct.unpack('<I', state_bytes)[0]

            # Read last_change (4 bytes)
            last_change_bytes = data_reader.read(4)
            if len(last_change_bytes) < 4:
                raise Exception("Unexpected end of data when reading lastChange")
            last_change_unix = struct.unpack('<I', last_change_bytes)[0]
            last_change = self._convert_timestamp(last_change_unix)

            # Read token (8 bytes) - V2+ specific
            token_bytes = data_reader.read(8)
            if len(token_bytes) < 8:
                raise Exception("Unexpected end of data when reading token")
            token = struct.unpack('<Q', token_bytes)[0]

            # Read SHA digest (20 bytes) - V2+ specific
            sha_digest = data_reader.read(20)
            if len(sha_digest) < 20:
                raise Exception("Unexpected end of data when reading SHA digest")

            # Read change_number (4 bytes)
            change_number_bytes = data_reader.read(4)
            if len(change_number_bytes) < 4:
                raise Exception("Unexpected end of data when reading changeNumber")
            change_number = struct.unpack('<I', change_number_bytes)[0]

            app_data = ApplicationData(app_id)
            app_data.state = state
            app_data.last_change = last_change
            app_data.change_number = change_number
            app_data.token = token
            app_data.sha_digest = sha_digest

            # Store position info for indexed access
            if app_start_pos is not None:
                app_data.file_offset = app_start_pos
                app_data.data_size = 8 + data_size  # app_id(4) + data_size(4) + data

            # Parse sections
            self.parse_app_data_cache_sections(data_reader, app_data)

            # Add to applications list
            self.applications.append(app_data)

    def parse_individual_appinfo_file_v1(self, reader):
        appId_bytes = reader.read(4)
        if len(appId_bytes) < 4:
            raise EOFError("Unexpected end of file when reading appId")
        appId = struct.unpack('<i', appId_bytes)[0]

        app_data = ApplicationData(appId)

        # Parse sections
        self.parse_app_data_cache_sections(reader, app_data)

        # Add to applications list
        self.applications.append(app_data)

    def parse_individual_appinfo_file_v2(self, reader, magic = None):
        """struct __cppobj CAppData
           {
             uint32 m_unAppID;
             uint32 m_unChangeNumber;
             uint32 m_bAllSections;
           };
        """
        version_bytes = reader.read(4)
        if len(version_bytes) < 4:
            raise EOFError("Unexpected end of file when reading version_bytes")
        version = struct.unpack('<i', version_bytes)[0]

        if version != 1:
            print("Warning: version_bytes != 1 (version_bytes = {})".format(version_bytes))

        appId_bytes = reader.read(4)
        if len(appId_bytes) < 4:
            raise EOFError("Unexpected end of file when reading appId")
        appId = struct.unpack('<i', appId_bytes)[0]

        changenumber_bytes = reader.read(4)
        if len(changenumber_bytes) < 4:
            raise EOFError("Unexpected end of file when reading appinfo Change Number")
        changenumber = struct.unpack('<i', changenumber_bytes)[0]

        is_allsections_bytes = reader.read(4)
        if len(is_allsections_bytes) < 4:
            raise EOFError("Unexpected end of file when reading is_allsections")
        is_allsections = bool(struct.unpack('<i', is_allsections_bytes)[0])

        # Parse application data
        app_data = ApplicationData(appId)
        app_data.version = version
        app_data.change_number = changenumber
        app_data.is_allsections = is_allsections

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

    def _convert_timestamp(self, unix_time):
        """
        Converts a Unix timestamp (seconds since 1970-01-01 UTC) to a datetime,
        with a safe fallback if the value is out of range.
        """
        try:
            return datetime.datetime.utcfromtimestamp(unix_time)
        except (OverflowError, OSError, ValueError):
            # If it's garbage, just return the raw value so nothing crashes.
            return unix_time

    def get_app_ids(self):
        """
        Returns a sorted list of app IDs present in this appinfo file.
        """
        return sorted(app.app_id for app in self.applications)

    def get_appid_change_numbers(self):
        """
        Returns a list of (app_id, change_number) for all applications
        parsed from this appinfo file.
        """
        result = []
        for app in self.applications:
            # change_number can be None for some paths; optionally filter those out
            result.append((app.app_id, app.change_number))
        return result

    @classmethod
    def read_single_app_indexed(cls, vdf_path: str, app_id: int,
                                 file_offset: int, data_size: int,
                                 format_magic: int) -> Optional[ApplicationData]:
        """
        Read a single app from a VDF file using index information.

        This enables O(1) access to app data without parsing the entire file.

        :param vdf_path: Path to the VDF file
        :param app_id: The app ID to read
        :param file_offset: Byte offset where the app entry starts
        :param data_size: Total size of the app entry in bytes
        :param format_magic: The VDF format magic number
        :return: ApplicationData or None if read fails
        """
        try:
            with open(vdf_path, 'rb') as f:
                f.seek(file_offset)
                raw_data = f.read(data_size)

            if len(raw_data) < data_size:
                log.warning(f"Short read for app {app_id}: got {len(raw_data)}, expected {data_size}")
                return None

            data_reader = BytesRecordingReader(io.BytesIO(raw_data))

            # Create a temporary parser instance for the parsing methods
            parser = cls.__new__(cls)
            parser.applications = []

            # Determine format and parse accordingly
            if format_magic == 0x02464456:
                # V1 format: appId(4) + state(4) + lastChange(4) + changeNumber(4) + sections
                app_data = parser._parse_v1_app_entry(data_reader)
            elif format_magic in (0x06564424, 0x07564425):
                # V2 format: appId(4) + dataSize(4) + data blob
                app_data = parser._parse_v2_app_entry(data_reader)
            elif format_magic in (0x07564426, 0x07564427):
                # V2+ format: appId(4) + dataSize(4) + data blob with token/SHA
                app_data = parser._parse_v2_plus_app_entry(data_reader)
            else:
                log.error(f"Unknown format magic: 0x{format_magic:08X}")
                return None

            if app_data:
                app_data.file_offset = file_offset
                app_data.data_size = data_size

            return app_data

        except Exception as e:
            log.error(f"Failed to read app {app_id} from {vdf_path}: {e}")
            return None

    def _parse_v1_app_entry(self, reader) -> Optional[ApplicationData]:
        """Parse a single V1 format app entry."""
        try:
            app_id_bytes = reader.read(4)
            if len(app_id_bytes) < 4:
                return None
            app_id = struct.unpack('<I', app_id_bytes)[0]

            state_bytes = reader.read(4)
            state = struct.unpack('<I', state_bytes)[0] if len(state_bytes) >= 4 else 0

            last_change_bytes = reader.read(4)
            last_change_unix = struct.unpack('<I', last_change_bytes)[0] if len(last_change_bytes) >= 4 else 0
            last_change = self._convert_timestamp(last_change_unix)

            change_number_bytes = reader.read(4)
            change_number = struct.unpack('<I', change_number_bytes)[0] if len(change_number_bytes) >= 4 else 0

            app_data = ApplicationData(app_id)
            app_data.state = state
            app_data.last_change = last_change
            app_data.change_number = change_number

            self.parse_app_data_cache_sections(reader, app_data)
            return app_data

        except Exception as e:
            log.error(f"Error parsing V1 app entry: {e}")
            return None

    def _parse_v2_app_entry(self, reader) -> Optional[ApplicationData]:
        """Parse a single V2 format app entry."""
        try:
            app_id_bytes = reader.read(4)
            if len(app_id_bytes) < 4:
                return None
            app_id = struct.unpack('<I', app_id_bytes)[0]

            data_size_bytes = reader.read(4)
            if len(data_size_bytes) < 4:
                return None
            data_size = struct.unpack('<I', data_size_bytes)[0]

            # Read the data blob
            data = reader.read(data_size)
            if len(data) != data_size:
                return None

            data_reader = BytesRecordingReader(io.BytesIO(data))

            state_bytes = data_reader.read(4)
            state = struct.unpack('<I', state_bytes)[0] if len(state_bytes) >= 4 else 0

            last_change_bytes = data_reader.read(4)
            last_change_unix = struct.unpack('<I', last_change_bytes)[0] if len(last_change_bytes) >= 4 else 0
            last_change = self._convert_timestamp(last_change_unix)

            change_number_bytes = data_reader.read(4)
            change_number = struct.unpack('<I', change_number_bytes)[0] if len(change_number_bytes) >= 4 else 0

            app_data = ApplicationData(app_id)
            app_data.state = state
            app_data.last_change = last_change
            app_data.change_number = change_number

            self.parse_app_data_cache_sections(data_reader, app_data)
            return app_data

        except Exception as e:
            log.error(f"Error parsing V2 app entry: {e}")
            return None

    def _parse_v2_plus_app_entry(self, reader) -> Optional[ApplicationData]:
        """Parse a single V2+ format app entry (with token and SHA)."""
        try:
            app_id_bytes = reader.read(4)
            if len(app_id_bytes) < 4:
                return None
            app_id = struct.unpack('<I', app_id_bytes)[0]

            data_size_bytes = reader.read(4)
            if len(data_size_bytes) < 4:
                return None
            data_size = struct.unpack('<I', data_size_bytes)[0]

            # Read the data blob
            data = reader.read(data_size)
            if len(data) != data_size:
                return None

            data_reader = BytesRecordingReader(io.BytesIO(data))

            state_bytes = data_reader.read(4)
            state = struct.unpack('<I', state_bytes)[0] if len(state_bytes) >= 4 else 0

            last_change_bytes = data_reader.read(4)
            last_change_unix = struct.unpack('<I', last_change_bytes)[0] if len(last_change_bytes) >= 4 else 0
            last_change = self._convert_timestamp(last_change_unix)

            # Token (8 bytes)
            token_bytes = data_reader.read(8)
            token = struct.unpack('<Q', token_bytes)[0] if len(token_bytes) >= 8 else 0

            # SHA digest (20 bytes)
            sha_digest = data_reader.read(20)
            if len(sha_digest) < 20:
                sha_digest = b'\x00' * 20

            change_number_bytes = data_reader.read(4)
            change_number = struct.unpack('<I', change_number_bytes)[0] if len(change_number_bytes) >= 4 else 0

            app_data = ApplicationData(app_id)
            app_data.state = state
            app_data.last_change = last_change
            app_data.change_number = change_number
            app_data.token = token
            app_data.sha_digest = sha_digest

            self.parse_app_data_cache_sections(data_reader, app_data)
            return app_data

        except Exception as e:
            log.error(f"Error parsing V2+ app entry: {e}")
            return None

    @classmethod
    def read_multiple_apps_indexed(cls, vdf_path: str, app_entries: list,
                                    format_magic: int) -> List[ApplicationData]:
        """
        Read multiple apps from a VDF file using index information.

        :param vdf_path: Path to the VDF file
        :param app_entries: List of (app_id, file_offset, data_size) tuples
        :param format_magic: The VDF format magic number
        :return: List of ApplicationData objects
        """
        results = []
        try:
            with open(vdf_path, 'rb') as f:
                for app_id, file_offset, data_size in app_entries:
                    f.seek(file_offset)
                    raw_data = f.read(data_size)

                    if len(raw_data) < data_size:
                        log.warning(f"Short read for app {app_id}")
                        continue

                    data_reader = BytesRecordingReader(io.BytesIO(raw_data))

                    # Create parser instance for parsing methods
                    parser = cls.__new__(cls)
                    parser.applications = []

                    if format_magic == 0x02464456:
                        app_data = parser._parse_v1_app_entry(data_reader)
                    elif format_magic in (0x06564424, 0x07564425):
                        app_data = parser._parse_v2_app_entry(data_reader)
                    elif format_magic in (0x07564426, 0x07564427):
                        app_data = parser._parse_v2_plus_app_entry(data_reader)
                    else:
                        continue

                    if app_data:
                        app_data.file_offset = file_offset
                        app_data.data_size = data_size
                        results.append(app_data)

        except Exception as e:
            log.error(f"Failed to read apps from {vdf_path}: {e}")

        return results


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