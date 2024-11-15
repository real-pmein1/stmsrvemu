import struct
import hashlib
from typing import Optional, List, Any
from io import BytesIO

from Crypto.Signature import pkcs1_15
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA1

# Constants for data types
KVS_TYPE_KEY = 0
KVS_TYPE_STRING = 1
KVS_TYPE_INT = 2
KVS_TYPE_FLOAT = 3
KVS_TYPE_PTR = 4
KVS_TYPE_WSTRING = 5
KVS_TYPE_COLOR = 6
KVS_TYPE_UINT64 = 7
KVS_TYPE_NO_MORE = 8
KVS_TYPE_DWORDPREFIXED_STRING = 9
KVS_TYPE_INT64 = 10
KVS_TYPE_NO_MORE_2 = 11  # Seen in CSGO

# Base class for registry elements
class RegistryElement:
    def __init__(self, name: str):
        self.name = name

    def is_value(self) -> bool:
        return isinstance(self, RegistryValue)

    def is_key(self) -> bool:
        return isinstance(self, RegistryKey)

    def update_digest(self, sha):
        pass  # To be implemented in subclasses

# Class representing a registry value
class RegistryValue(RegistryElement):
    def __init__(self, name: str, value_type: int, value: Any):
        super().__init__(name)
        self.value_type = value_type
        self.value = value

    def update_digest(self, sha):
        sha.update(self.name.encode('utf-8'))
        if self.value_type == KVS_TYPE_STRING:
            sha.update(self.value.encode('utf-8'))
        elif self.value_type == KVS_TYPE_INT:
            sha.update(struct.pack('<i', self.value))
        elif self.value_type == KVS_TYPE_FLOAT:
            sha.update(struct.pack('<f', self.value))
        # Add other types as needed

    def __repr__(self):
        return f"RegistryValue(name={self.name}, value_type={self.value_type}, value={self.value})"

# Class representing a registry key, which can contain other keys and values
class RegistryKey(RegistryElement):
    def __init__(self, name: str):
        super().__init__(name)
        self.elements: List[RegistryElement] = []
        self.parent: Optional['RegistryKey'] = None

    def add_element(self, element: RegistryElement):
        self.elements.append(element)
        if isinstance(element, RegistryKey):
            element.parent = self

    def get_element(self, name: str) -> Optional[RegistryElement]:
        for element in self.elements:
            if element.name == name:
                return element
        return None

    def get_elements(self) -> List[RegistryElement]:
        return self.elements

    def get_key(self, name: str) -> Optional['RegistryKey']:
        elem = self.get_element(name)
        if isinstance(elem, RegistryKey):
            return elem
        return None

    def create_key(self, name: str) -> 'RegistryKey':
        key = self.get_key(name)
        if not key:
            key = RegistryKey(name)
            self.add_element(key)
        return key

    def delete_key(self, name: str):
        self.elements = [e for e in self.elements if not (e.is_key() and e.name == name)]

    def get_value(self, name: str) -> Optional[RegistryValue]:
        elem = self.get_element(name)
        if isinstance(elem, RegistryValue):
            return elem
        return None

    def set_value(self, name: str, value_type: int, value: Any):
        val = self.get_value(name)
        if val is None:
            val = RegistryValue(name, value_type, value)
            self.add_element(val)
        else:
            val.value_type = value_type
            val.value = value

    def set_string_value(self, name: str, value: str):
        self.set_value(name, KVS_TYPE_STRING, value)

    def get_string_value(self, name: str) -> Optional[str]:
        val = self.get_value(name)
        if val and val.value_type == KVS_TYPE_STRING:
            return val.value
        return None

    def update_digest(self, sha):
        sha.update(self.name.encode('utf-8'))
        for element in self.elements:
            element.update_digest(sha)

    def __repr__(self):
        return f"RegistryKey(name={self.name}, elements={self.elements})"

# Base registry class
class VolatileRegistry:
    def __init__(self, case_sensitive_paths: bool = False, allow_duplicate_name: bool = False):
        self.case_sensitive_paths = case_sensitive_paths
        self.allow_duplicate_name = allow_duplicate_name
        self.root = RegistryKey("root")

    def get_registry_key(self) -> RegistryKey:
        return self.root

    def delete_key(self, name: str):
        self.root.delete_key(name)

    def __repr__(self):
        return f"VolatileRegistry(case_sensitive_paths={self.case_sensitive_paths}, allow_duplicate_name={self.allow_duplicate_name}, root={self.root})"

# SteamRegistry class with signing functionality
class SteamRegistry(VolatileRegistry):
    def __init__(self, case_sensitive_paths: bool = False, allow_duplicate_name: bool = False):
        super().__init__(case_sensitive_paths, allow_duplicate_name)

    def verify_signature(self, public_key: RSA.RsaKey):
        first_key = self.root.get_elements()[0] if self.root.get_elements() else None
        if not first_key:
            raise Exception("Missing key to verify signature")

        signatures = self.root.get_key("kvsignatures")
        if not signatures:
            raise Exception("Missing signature")

        sign = signatures.get_string_value(first_key.name)
        if not sign:
            raise Exception("Missing signature")

        signature_bytes = bytes.fromhex(sign)

        # Compute digest
        sha = SHA1.new()
        first_key.update_digest(sha)

        # Verify signature
        pkcs1_15.new(public_key).verify(sha, signature_bytes)

    def sign(self, private_key: RSA.RsaKey):
        first_key = self.root.get_elements()[0] if self.root.get_elements() else None
        if not first_key:
            raise Exception("Missing key to sign")

        # Compute digest
        sha = SHA1.new()
        first_key.update_digest(sha)

        # Compute signature
        signature_bytes = pkcs1_15.new(private_key).sign(sha)

        # Add signature
        signatures = self.root.create_key("kvsignatures")
        sign_hex = signature_bytes.hex()
        signatures.set_string_value(first_key.name, sign_hex)

    def remove_signature(self):
        self.root.delete_key("kvsignatures")

    def __repr__(self):
        return f"SteamRegistry(case_sensitive_paths={self.case_sensitive_paths}, allow_duplicate_name={self.allow_duplicate_name}, root={self.root})"

# KeyValuesSystem class handling serialization/deserialization
class KeyValuesSystem(SteamRegistry):
    def __init__(self, case_sensitive_paths: bool = False, allow_duplicate_name: bool = False):
        super().__init__(case_sensitive_paths, allow_duplicate_name)

    def serialize(self, out_stream: BytesIO):
        self.serialize_keys(out_stream, self.root)

    @staticmethod
    def serialize_keys(out_stream: BytesIO, key: RegistryKey):
        for element in key.get_elements():
            if element.is_value():
                KeyValuesSystem.serialize_value(out_stream, element)
            elif element.is_key():
                KeyValuesSystem.serialize_key(out_stream, element)
        out_stream.write(bytes([KVS_TYPE_NO_MORE]))

    @staticmethod
    def serialize_key(out_stream: BytesIO, key: RegistryKey):
        out_stream.write(bytes([KVS_TYPE_KEY]))
        out_stream.write(key.name.encode('utf-8') + b'\x00')
        KeyValuesSystem.serialize_keys(out_stream, key)

    @staticmethod
    def serialize_value(out_stream: BytesIO, value: RegistryValue):
        out_stream.write(bytes([value.value_type]))
        out_stream.write(value.name.encode('utf-8') + b'\x00')

        # Handle different value types
        if value.value_type == KVS_TYPE_STRING:
            if not isinstance(value.value, str):
                raise TypeError(f"Expected a string for value {value.name}, got {type(value.value).__name__}")
            out_stream.write(value.value.encode('utf-8') + b'\x00')
        elif value.value_type == KVS_TYPE_INT:
            if not isinstance(value.value, int):
                raise TypeError(f"Expected an integer for value {value.name}, got {type(value.value).__name__}")
            out_stream.write(struct.pack('<i', value.value))
        elif value.value_type == KVS_TYPE_FLOAT:
            if not isinstance(value.value, float):
                raise TypeError(f"Expected a float for value {value.name}, got {type(value.value).__name__}")
            out_stream.write(struct.pack('<f', value.value))
        elif value.value_type == KVS_TYPE_PTR:
            if not isinstance(value.value, int):
                raise TypeError(f"Expected an integer (pointer) for value {value.name}, got {type(value.value).__name__}")
            out_stream.write(struct.pack('<Q', value.value))
        elif value.value_type == KVS_TYPE_WSTRING:
            if not isinstance(value.value, str):
                raise TypeError(f"Expected a string for WSTRING value {value.name}, got {type(value.value).__name__}")
            wstr = value.value + '\x00'
            length = len(wstr)
            out_stream.write(struct.pack('<I', length))
            out_stream.write(wstr.encode('utf-16le'))
        elif value.value_type == KVS_TYPE_COLOR:
            if not isinstance(value.value, int):
                raise TypeError(f"Expected an integer for COLOR value {value.name}, got {type(value.value).__name__}")
            out_stream.write(struct.pack('<I', value.value))
        elif value.value_type == KVS_TYPE_UINT64:
            if not isinstance(value.value, int):
                raise TypeError(f"Expected an integer for UINT64 value {value.name}, got {type(value.value).__name__}")
            out_stream.write(struct.pack('<Q', value.value))
        elif value.value_type == KVS_TYPE_INT64:
            if not isinstance(value.value, int):
                raise TypeError(f"Expected an integer for INT64 value {value.name}, got {type(value.value).__name__}")
            out_stream.write(struct.pack('<q', value.value))
        else:
            raise Exception(f"Unsupported data type: {value.value_type}")

    def deserialize(self, input_stream: BytesIO):
        self.root = RegistryKey("root")
        self.deserialize_key(self.root, input_stream)

    @staticmethod
    def deserialize_key(current_key: RegistryKey, input_stream: BytesIO):
        while True:
            type_byte = input_stream.read(1)
            if not type_byte:
                break
            data_type = type_byte[0]
            if data_type in (KVS_TYPE_NO_MORE, KVS_TYPE_NO_MORE_2):
                return
            elif data_type == KVS_TYPE_KEY:
                name = KeyValuesSystem.read_string(input_stream)
                key = current_key.create_key(name)
                KeyValuesSystem.deserialize_key(key, input_stream)
            else:
                name = KeyValuesSystem.read_string(input_stream)
                value = KeyValuesSystem.read_value(data_type, input_stream)
                current_key.set_value(name, data_type, value)

    @staticmethod
    def read_string(input_stream: BytesIO) -> str:
        chars = []
        while True:
            c = input_stream.read(1)
            if c == b'\x00' or c == b'':
                break
            chars.append(c)
        return b''.join(chars).decode('utf-8')

    @staticmethod
    def read_value(data_type: int, input_stream: BytesIO) -> Any:
        if data_type == KVS_TYPE_STRING:
            return KeyValuesSystem.read_string(input_stream)
        elif data_type == KVS_TYPE_INT:
            data = input_stream.read(4)
            if len(data) < 4:
                raise EOFError("Unexpected end of data while reading INT value")
            return struct.unpack('<i', data)[0]
        elif data_type == KVS_TYPE_FLOAT:
            data = input_stream.read(4)
            if len(data) < 4:
                raise EOFError("Unexpected end of data while reading FLOAT value")
            return struct.unpack('<f', data)[0]
        elif data_type == KVS_TYPE_PTR:
            data = input_stream.read(8)
            if len(data) < 8:
                raise EOFError("Unexpected end of data while reading PTR value")
            return struct.unpack('<Q', data)[0]
        elif data_type == KVS_TYPE_WSTRING:
            # Read the length in terms of wchar_t units (2 bytes each)
            length_bytes = input_stream.read(4)
            if len(length_bytes) < 4:
                raise EOFError("Unexpected end of data while reading WSTRING length")
            length = struct.unpack('<I', length_bytes)[0]
            byte_length = length * 2  # Each wchar_t is 2 bytes
            wstr_bytes = input_stream.read(byte_length)
            if len(wstr_bytes) < byte_length:
                raise EOFError("Unexpected end of data while reading WSTRING value")
            return wstr_bytes.decode('utf-16le').rstrip('\x00')
        elif data_type == KVS_TYPE_COLOR:
            data = input_stream.read(4)
            if len(data) < 4:
                raise EOFError("Unexpected end of data while reading COLOR value")
            return struct.unpack('<I', data)[0]
        elif data_type == KVS_TYPE_UINT64:
            data = input_stream.read(8)
            if len(data) < 8:
                raise EOFError("Unexpected end of data while reading UINT64 value")
            return struct.unpack('<Q', data)[0]
        elif data_type == KVS_TYPE_INT64:
            data = input_stream.read(8)
            if len(data) < 8:
                raise EOFError("Unexpected end of data while reading INT64 value")
            return struct.unpack('<q', data)[0]
        else:
            raise Exception(f"Unsupported data type: {data_type}")

    def __repr__(self):
        return f"KeyValuesSystem(case_sensitive_paths={self.case_sensitive_paths}, allow_duplicate_name={self.allow_duplicate_name}, root={self.root})"

# Example usage
"""if __name__ == "__main__":
    # Create a KeyValuesSystem instance
    kvs = KeyValuesSystem()

    # Add some data
    kvs.root.create_key('TestKey')
    kvs.root.get_key('TestKey').set_string_value('TestValue', 'Hello World')

    # Serialize the data
    output_stream = BytesIO()
    kvs.serialize(output_stream)
    serialized_data = output_stream.getvalue()

    # Print serialized data
    print("Serialized Data:", serialized_data)
    data = b'\x00MessageObject\x00\x02NetSpeed\x00\x00\x00\x00\x00\x05NetSpeedLabel\x00\x0b\x00\x00\x00D\x00o\x00n\x00\'\x00t\x00 \x00K\x00n\x00o\x00w\x00\x00\x00\x02Microphone\x00\xff\xff\xff\xff\x05MicrophoneLabel\x00\x0b\x00\x00\x00D\x00o\x00n\x00\'\x00t\x00 \x00k\x00n\x00o\x00w\x00\x00\x00\x01CPUVendor\x00GenuineIntel\x00\x02CPUSpeed\x00\xb8\x0b\x00\x00\x02LogicalProcessors\x00\x08\x00\x00\x00\x02PhysicalProcessors\x00\x08\x00\x00\x00\x02HyperThreading\x00\x00\x00\x00\x00\x02FCMOV\x00\x01\x00\x00\x00\x02SSE2\x00\x01\x00\x00\x00\x02SSE3\x00\x01\x00\x00\x00\x02SSE4\x00\x01\x00\x00\x00\x02SSE4a\x00\x00\x00\x00\x00\x02SSE41\x00\x01\x00\x00\x00\x02SSE42\x00\x01\x00\x00\x00\x01OSVersion\x00Windows\x00\x02Is64BitOS\x00\x01\x00\x00\x00\x02OSType\x00\x00\x00\x00\x00\x02NTFS\x00\x01\x00\x00\x00\x01AdapterDescription\x00NVIDIA GeForce RTX 3050\x00\x01DriverVersion\x0030.0.15.1179\x00\x01DriverDate\x002022-2-10\x00\x02VRAMSize\x00\xff\x1f\x00\x00\x02BitDepth\x00 \x00\x00\x00\x02RefreshRate\x00\xa5\x00\x00\x00\x02NumMonitors\x00\x02\x00\x00\x00\x02NumDisplayDevices\x00\x02\x00\x00\x00\x02MonitorWidthInPixels\x00\x00\n\x00\x00\x02MonitorHeightInPixels\x00\xa0\x05\x00\x00\x02DesktopWidthInPixels\x008\x0e\x00\x00\x02DesktopHeightInPixels\x00\x80\x07\x00\x00\x02MonitorWidthInMillimeters\x00\xb9\x02\x00\x00\x02MonitorHeightInMillimeters\x00\x88\x01\x00\x00\x02MonitorDiagonalInMillimeters\x00\x1f\x03\x00\x00\x01VideoCard\x00NVIDIA GeForce RTX 3050\x00\x01DXVideoCardDriver\x00nvldumd.dll\x00\x01DXVideoCardVersion\x0030.0.15.1179\x00\x02DXVendorID\x00\xde\x10\x00\x00\x02DXDeviceID\x00\x07%\x00\x00\x01MSAAModes\x002x 4x 8x \x00\x02MultiGPU\x00\x00\x00\x00\x00\x02NumSLIGPUs\x00\x01\x00\x00\x00\x02DisplayType\x00\x00\x00\x00\x00\x02BusType\x00\x03\x00\x00\x00\x02BusRate\x00\x08\x00\x00\x00\x02dell_oem\x00\x00\x00\x00\x00\x01AudioDeviceDescription\x00Speakers (Realtek(R) Audio)\x00\x02RAM\x00\xb9\x7f\x00\x00\x02LanguageId\x00\x00\x00\x00\x00\x02DriveType\x00\x02\x00\x00\x00\x02TotalHD\x00\x82\xab*\x01\x02FreeHD\x00\x17i\x08\x00\x02SteamHDUsage\x00/\x00\x00\x00\x01OSInstallDate\x001969-12-31\x00\x01GameController\x00None\x00\x02NonSteamApp_firefox\x00\x00\x00\x00\x00\x02NonSteamApp_openoffice\x00\x00\x00\x00\x00\x02NonSteamApp_wfw\x00\x00\x00\x00\x00\x02NonSteamApp_za\x00\x00\x00\x00\x00\x02NonSteamApp_f4m\x00\x00\x00\x00\x00\x02NonSteamApp_cog\x00\x00\x00\x00\x00\x02NonSteamApp_pd\x00\x00\x00\x00\x00\x02NonSteamApp_vmf\x00\x00\x00\x00\x00\x02NonSteamApp_grl\x00\x00\x00\x00\x00\x02NonSteamApp_fv\x00\x00\x00\x00\x00\x07machineid\x00\xb0dU"B\xfe\xc2H\x02version\x00\x10\x00\x00\x00\x02country\x00US\x00\x00\x00ownership\x00\x08\x08\x08'

    # Deserialize the data
    input_stream = BytesIO(data)
    new_kvs = KeyValuesSystem()
    new_kvs.deserialize(input_stream)

    # Print the deserialized KeyValuesSystem
    print("Deserialized KeyValuesSystem:")
    print(new_kvs)

    # Print the internal structure
    print("Internal Structure:")
    print(new_kvs.root)"""