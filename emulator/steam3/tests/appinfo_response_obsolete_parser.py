#!/usr/bin/env python3
"""
AppInfo Response Parser for MsgClientAppInfoResponse packets.

Packet Structure:
    struct MsgClientAppInfoResponse_t {
        uint32 m_cNumApps;  // Number of apps in the packet
    };

    For each app:
        - appid (uint32)
        - change_number (uint32)
        - Sections (loop until section_type == 0):
            - section_type (uint8): 0=end, 1-15=section type
            - KeyValues binary data (if section_type != 0)

KeyValues Binary Format:
    - type (uint8): 0=NONE/nested, 1=STRING, 2=INT, 3=FLOAT, 4=PTR, 5=WSTRING, 6=COLOR, 7=UINT64, 8=END
    - name (null-terminated string)
    - value (based on type)
"""

import struct
import io


# KeyValues type constants
TYPE_NONE = 0       # Nested KeyValues (sub-dictionary)
TYPE_STRING = 1     # Null-terminated string
TYPE_INT = 2        # 32-bit signed integer
TYPE_FLOAT = 3      # 32-bit float
TYPE_PTR = 4        # 32-bit unsigned (pointer)
TYPE_WSTRING = 5    # Wide string (length-prefixed)
TYPE_COLOR = 6      # 4 bytes RGBA
TYPE_UINT64 = 7     # 64-bit unsigned integer
TYPE_NUMTYPES = 8   # End marker

# Section type names
SECTION_TYPE_NAMES = {
    0: "End",
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
}


class CUtlBuffer:
    """Buffer class for reading binary data with various data types."""

    def __init__(self, data):
        if isinstance(data, bytes):
            self.stream = io.BytesIO(data)
        else:
            self.stream = data
        self.data = data if isinstance(data, bytes) else None

    @property
    def offset(self):
        return self.stream.tell()

    def get_bytes_remaining(self):
        current = self.stream.tell()
        self.stream.seek(0, 2)  # Seek to end
        end = self.stream.tell()
        self.stream.seek(current)
        return end - current

    def get_uint8(self):
        data = self.stream.read(1)
        if len(data) < 1:
            raise ValueError("Buffer overflow while reading uint8")
        return struct.unpack('<B', data)[0]

    def get_unsigned_short(self):
        data = self.stream.read(2)
        if len(data) < 2:
            raise ValueError("Buffer overflow while reading unsigned short")
        return struct.unpack('<H', data)[0]

    def get_int(self):
        data = self.stream.read(4)
        if len(data) < 4:
            raise ValueError("Buffer overflow while reading int32")
        return struct.unpack('<i', data)[0]

    def get_unsigned_int(self):
        data = self.stream.read(4)
        if len(data) < 4:
            raise ValueError("Buffer overflow while reading unsigned int")
        return struct.unpack('<I', data)[0]

    def get_float(self):
        data = self.stream.read(4)
        if len(data) < 4:
            raise ValueError("Buffer overflow while reading float")
        return struct.unpack('<f', data)[0]

    def get_double(self):
        data = self.stream.read(8)
        if len(data) < 8:
            raise ValueError("Buffer overflow while reading double/uint64")
        return struct.unpack('<Q', data)[0]

    def get_string(self):
        """Read null-terminated string."""
        chars = []
        while True:
            b = self.stream.read(1)
            if len(b) == 0:
                raise ValueError("Unexpected end of buffer when reading string")
            if b == b'\x00':
                break
            chars.append(b)
        try:
            return b''.join(chars).decode('utf-8', errors='replace')
        except:
            return b''.join(chars).decode('latin-1', errors='replace')

    def get_wide_string(self, length):
        """Read wide string with given length in characters."""
        if length <= 0:
            return ""
        # Each wide char is 4 bytes (wchar_t on Linux/Steam)
        data = self.stream.read(length * 4)
        if len(data) < length * 4:
            raise ValueError("Buffer overflow while reading wide string")
        # Decode as UTF-32LE
        try:
            result = data.decode('utf-32-le', errors='replace')
            # Remove null terminator if present
            if result and result[-1] == '\x00':
                result = result[:-1]
            return result
        except:
            return data.hex()

    def peek_string_length(self):
        """Peek the length of next null-terminated string without consuming."""
        current = self.stream.tell()
        length = 0
        while True:
            b = self.stream.read(1)
            if len(b) == 0 or b == b'\x00':
                length += 1  # Include null terminator
                break
            length += 1
        self.stream.seek(current)
        return length


class KeyValues:
    """Parser for Steam KeyValues binary format."""

    def __init__(self):
        self.data = {}

    def read_as_binary(self, buffer, depth=0):
        """
        Read KeyValues from binary buffer.

        Returns the parsed dictionary or None on error.
        """
        if depth > 100:
            raise ValueError("KeyValues stack depth exceeded 100")

        if buffer.get_bytes_remaining() <= 0:
            return None

        # Read first type
        value_type = buffer.get_uint8()
        if value_type == TYPE_NUMTYPES:
            return self.data

        while True:
            # Read key name
            key_name = buffer.get_string()

            # Read value based on type
            if value_type == TYPE_NONE:
                # Nested KeyValues
                nested_kv = KeyValues()
                nested_kv.read_as_binary(buffer, depth + 1)
                self.data[key_name] = nested_kv.data

            elif value_type == TYPE_STRING:
                value = buffer.get_string()
                self.data[key_name] = value

            elif value_type == TYPE_INT:
                value = buffer.get_int()
                self.data[key_name] = value

            elif value_type == TYPE_FLOAT:
                value = buffer.get_float()
                self.data[key_name] = value

            elif value_type == TYPE_PTR:
                value = buffer.get_unsigned_int()
                self.data[key_name] = value

            elif value_type == TYPE_WSTRING:
                length = buffer.get_int()
                if length > 0xFFFF:
                    raise ValueError(f"Wide string length too large: {length}")
                if length > 0:
                    value = buffer.get_wide_string(length)
                else:
                    value = ""
                self.data[key_name] = value

            elif value_type == TYPE_COLOR:
                r = buffer.get_uint8()
                g = buffer.get_uint8()
                b = buffer.get_uint8()
                a = buffer.get_uint8()
                self.data[key_name] = (r, g, b, a)

            elif value_type == TYPE_UINT64:
                value = buffer.get_double()
                self.data[key_name] = value

            else:
                # Unknown type, skip
                pass

            # Check if more data available
            if buffer.get_bytes_remaining() <= 0:
                break

            # Read next type
            value_type = buffer.get_uint8()
            if value_type == TYPE_NUMTYPES:
                break

            if buffer.get_bytes_remaining() <= 0:
                break

        return self.data


class ApplicationData:
    """Class to store parsed data for a single application."""

    def __init__(self, app_id):
        self.app_id = app_id
        self.change_number = None
        self.sections = {}  # section_name -> KeyValues data dict

    def __repr__(self):
        return f"<ApplicationData app_id={self.app_id} change_number={self.change_number}>"


class AppInfoResponseParser:
    """
    Parser for MsgClientAppInfoResponse packets.

    Parses the complete response including:
    - App count header
    - Multiple apps with their sections
    - KeyValues data for each section
    """

    def __init__(self):
        self.num_apps = 0
        self.applications = []

    def parse(self, data, include_header=True):
        """
        Parse the AppInfo response data.

        Args:
            data: Raw bytes of the packet data
            include_header: If True, expects m_cNumApps at start.
                          If False, parses apps until end of data.
        """
        buffer = CUtlBuffer(data)

        if include_header:
            # Read number of apps
            self.num_apps = buffer.get_unsigned_int()
            print(f"=== MsgClientAppInfoResponse ===")
            print(f"Number of apps: {self.num_apps}")
            print()

        app_index = 0
        while buffer.get_bytes_remaining() >= 8:  # Need at least appid + change_number
            if include_header and app_index >= self.num_apps:
                break

            try:
                app_data = self._parse_single_app(buffer, app_index)
                if app_data:
                    self.applications.append(app_data)
                    app_index += 1
            except ValueError as e:
                print(f"Error parsing app {app_index}: {e}")
                break

        return self.applications

    def _parse_single_app(self, buffer, app_index):
        """Parse a single app's data from the buffer."""
        # Read app ID
        app_id = buffer.get_unsigned_int()

        # Read change number
        change_number = buffer.get_unsigned_int()

        print(f"--- App #{app_index + 1} ---")
        print(f"  AppID: {app_id}")
        print(f"  Change Number: {change_number}")

        app_data = ApplicationData(app_id)
        app_data.change_number = change_number

        # Parse sections
        self._parse_sections(buffer, app_data)

        print()
        return app_data

    def _parse_sections(self, buffer, app_data):
        """Parse all sections for an app."""
        while buffer.get_bytes_remaining() > 0:
            # Read section type
            section_type = buffer.get_uint8()

            if section_type == 0:
                # End of sections for this app
                break

            section_name = SECTION_TYPE_NAMES.get(section_type, f"Unknown_{section_type}")
            print(f"  Section: {section_name} (type={section_type})")

            # Parse KeyValues for this section
            try:
                kv = KeyValues()
                kv.read_as_binary(buffer)
                app_data.sections[section_name] = kv.data

                # Print section contents
                self._print_keyvalues(kv.data, indent=4)
            except ValueError as e:
                print(f"    Error parsing section: {e}")
                break

    def _print_keyvalues(self, data, indent=0):
        """Recursively print KeyValues data with indentation."""
        prefix = " " * indent

        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, dict):
                    print(f"{prefix}{key}:")
                    self._print_keyvalues(value, indent + 2)
                elif isinstance(value, tuple) and len(value) == 4:
                    # Color value
                    print(f"{prefix}{key}: RGBA({value[0]}, {value[1]}, {value[2]}, {value[3]})")
                else:
                    # Truncate long values for display
                    value_str = str(value)
                    if len(value_str) > 100:
                        value_str = value_str[:100] + "..."
                    print(f"{prefix}{key}: {value_str}")
        else:
            print(f"{prefix}{data}")


def parse_appinfo_response(data, include_header=True):
    """
    Convenience function to parse AppInfo response data.

    Args:
        data: Raw bytes of the packet data
        include_header: If True, expects m_cNumApps at start

    Returns:
        List of ApplicationData objects
    """
    parser = AppInfoResponseParser()
    return parser.parse(data, include_header)


# Test script
if __name__ == "__main__":
    # Test data - note: this data has the header REMOVED according to original comments
    # The original comment said: "REMOVED THE HEADER AND THE 4 BYTE APP COUNT"
    # So we need to set include_header=False

    byte_data =  b'I\x03\x00\x00$\x02\x00\x0f\x00\xe0LB\xa3\x00\x00\xff\xff\xff\xff\xff\xff\xff\xff\xef\xc4\xa0\x9b\x01\x01\x00\x10\x01\x87\x93{\x00\x01\x00\x00\x00\xca]\x00\x00\xceX\x00\x00\x02\x0024010\x00\x01name\x00RailWorks\x00\x01clienticon\x00d4f24b9e49aabaae532dc860114bce5b9aa44b3a\x00\x01clienttga\x009257b4e7507d8b65b7be19bbf6b75874a63c791c\x00\x01icon\x00d7a13f94698905a0bb1fd7ca5f3f002758307e47\x00\x01logo\x00860f8bb1fda5fb27625070692ead15444d9b18bf\x00\x01logo_small\x00860f8bb1fda5fb27625070692ead15444d9b18bf_thumb\x00\x01gameid\x0024010\x00\x08\x08\x03\x00extended\x00\x01AllowElevation\x001\x00\x01developer\x00RailSimulator.com\x00\x01gamedir\x00RailWorks\x00\x01homepage\x00http://www.railsimulator.com/\x00\x01icon\x00\x00\x01installscript\x00installscript.vdf\x00\x01NoServers\x001\x00\x01order\x001\x00\x01primarycache\x0024009\x00\x01serverbrowsername\x00\x00\x01state\x00eStateAvailable\x00\x01cddbfingerprint\x00435544087\x00\x01depotscrc\x001810171065\x00\x01ListOfDLC\x0024012,24021,24022,24023,24024,24025,24026,24027,24028,24029,24030,24031,24032,24033,24034,24035,24036,24037,24038,24039,24040,24041,24042,24043,24044,24045,24046,24047,24048,24049,24050,24051,24052,24053,24054,24055,24056,24057,24058,24059,24060,24061,24062,24065,24066,24067,24068,24069,24070\x00\x08\x08\x06\x00installscript\x00\x00registry\x00\x00HKEY_LOCAL_MACHINE\\SOFTWARE\\RailSimulator.com\\RailWorks\x00\x00string\x00\x01Install_Path\x00%INSTALLDIR%\x00\x01Exe_Path\x00%INSTALLDIR%\\RailWorks.exe\x00\x08\x08\x08\x00Run Process\x00\x00Initialise\x00\x01HasRunKey\x00HKEY_LOCAL_MACHINE\\Software\\Valve\\Steam\\Apps\\24010\\DOTNETandDX\x00\x01process 1\x00%INSTALLDIR%\\Install\\NetFx20SP1_x86.exe\x00\x01command 1\x00/q /nopatch /norestart\x00\x08\x00Initialise\x00\x01HasRunKey\x00HKEY_LOCAL_MACHINE\\Software\\Valve\\Steam\\Apps\\24010\\DOTNETandDX\x00\x01process 1\x00%INSTALLDIR%\\Install\\DirectX9\\DXSETUP.exe\x00\x01command 1\x00/silent\x00\x08\x00PhysX\x00\x01HasRunKey\x00HKEY_LOCAL_MACHINE\\Software\\Valve\\Steam\\Apps\\24010\\PhysX\x00\x01process 1\x00%INSTALLDIR%\\Install\\PhysX_6.10.25_SystemSoftware.exe\x00\x01command 1\x00/quiet\x00\x01NoCleanUp\x001\x00\x08\x08\x08\x08\x00'

    print("=" * 60)
    print("APPINFO RESPONSE PARSER TEST")
    print("=" * 60)
    print()

    # Parse without header (test data has header removed)
    applications = parse_appinfo_response(byte_data[36:], include_header=True)

    print()
    print("=" * 60)
    print("PARSING SUMMARY")
    print("=" * 60)
    print(f"Total applications parsed: {len(applications)}")
    print()

    for app in applications:
        print(f"AppID: {app.app_id}, Change Number: {app.change_number}")
        print(f"  Sections: {list(app.sections.keys())}")
        for section_name, section_data in app.sections.items():
            if isinstance(section_data, dict):
                # Get the root key (usually the appid as string)
                for root_key, root_value in section_data.items():
                    if isinstance(root_value, dict):
                        print(f"    {section_name}/{root_key}: {len(root_value)} keys")
                    else:
                        print(f"    {section_name}/{root_key}: {root_value}")
        print()

    print("=" * 60)
    print("TEST WITH HEADER (simulated)")
    print("=" * 60)
    print()

    # Create test data with header (prepend app count)
    num_apps = len(applications)
    test_data_with_header = struct.pack('<I', num_apps) + byte_data

    # Parse with header
    applications2 = parse_appinfo_response(test_data_with_header, include_header=True)
    print(f"Parsed {len(applications2)} applications with header")
