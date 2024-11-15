import struct
from io import BytesIO
from typing import List, Optional, Dict, Any

# Define constants for data types
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

# Class representing a registry value
class RegistryValue(RegistryElement):
    def __init__(self, name: str, value_type: int, value: Any):
        super().__init__(name)
        self.value_type = value_type
        self.value = value

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

    def get_value(self, name: str) -> Optional[RegistryValue]:
        elem = self.get_element(name)
        if isinstance(elem, RegistryValue):
            return elem
        return None

    def create_key(self, name: str) -> 'RegistryKey':
        key = self.get_key(name)
        if not key:
            key = RegistryKey(name)
            self.add_element(key)
        return key

    def set_value(self, name: str, value_type: int, value: Any):
        val = self.get_value(name)
        if val is None:
            val = RegistryValue(name, value_type, value)
            self.add_element(val)
        else:
            val.value_type = value_type
            val.value = value

    def delete_key(self, name: str):
        self.elements = [e for e in self.elements if not (e.is_key() and e.name == name)]

    def get_parent_key(self) -> Optional['RegistryKey']:
        return self.parent

# Class handling serialization and deserialization of the registry
class KeyValuesSystem:
    def __init__(self, case_sensitive_paths: bool = False, allow_duplicate_name: bool = False):
        self.root = RegistryKey("root")
        self.case_sensitive_paths = case_sensitive_paths
        self.allow_duplicate_name = allow_duplicate_name

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

        if value.value_type == KVS_TYPE_STRING:
            out_stream.write(value.value.encode('utf-8') + b'\x00')
        elif value.value_type == KVS_TYPE_INT:
            out_stream.write(struct.pack('<i', value.value))
        elif value.value_type == KVS_TYPE_FLOAT:
            out_stream.write(struct.pack('<f', value.value))
        elif value.value_type == KVS_TYPE_PTR:
            out_stream.write(struct.pack('<Q', value.value))
        elif value.value_type == KVS_TYPE_WSTRING:
            wstr = value.value.encode('utf-16le') + b'\x00\x00'
            out_stream.write(struct.pack('<I', len(wstr)))
            out_stream.write(wstr)
        elif value.value_type == KVS_TYPE_COLOR:
            out_stream.write(struct.pack('<I', value.value))
        elif value.value_type == KVS_TYPE_UINT64:
            out_stream.write(struct.pack('<Q', value.value))
        elif value.value_type == KVS_TYPE_INT64:
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
            if data_type == KVS_TYPE_NO_MORE or data_type == KVS_TYPE_NO_MORE_2:
                if len(input_stream.getvalue()) > 2:
                    continue
                else:
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
            return struct.unpack('<i', input_stream.read(4))[0]
        elif data_type == KVS_TYPE_FLOAT:
            return struct.unpack('<f', input_stream.read(4))[0]
        elif data_type == KVS_TYPE_PTR:
            return struct.unpack('<Q', input_stream.read(8))[0]
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
            return struct.unpack('<I', input_stream.read(4))[0]
        elif data_type == KVS_TYPE_UINT64:
            return struct.unpack('<Q', input_stream.read(8))[0]
        elif data_type == KVS_TYPE_INT64:
            return struct.unpack('<q', input_stream.read(8))[0]
        else:
            raise Exception(f"Unsupported data type: {data_type}")

    # Methods for setting and getting values
    def set_int32_value(self, key_name: str, value_name: str, value: int):
        key = self.root.get_key(key_name)
        if not key:
            key = self.root.create_key(key_name)
        key.set_value(value_name, KVS_TYPE_INT, value)

    def get_int32_value(self, key_name: str, value_name: str) -> int:
        key = self.root.get_key(key_name)
        if key:
            value = key.get_value(value_name)
            if value and value.value_type == KVS_TYPE_INT:
                return value.value
        raise KeyError(f"Value '{value_name}' not found in key '{key_name}'")

    def set_string_value(self, key_name: str, value_name: str, value: str):
        key = self.root.get_key(key_name)
        if not key:
            key = self.root.create_key(key_name)
        key.set_value(value_name, KVS_TYPE_STRING, value)

    def get_string_value(self, key_name: str, value_name: str) -> str:
        key = self.root.get_key(key_name)
        if key:
            value = key.get_value(value_name)
            if value and value.value_type == KVS_TYPE_STRING:
                return value.value
        raise KeyError(f"Value '{value_name}' not found in key '{key_name}'")

    def set_float_value(self, key_name: str, value_name: str, value: float):
        key = self.root.get_key(key_name)
        if not key:
            key = self.root.create_key(key_name)
        key.set_value(value_name, KVS_TYPE_FLOAT, value)

    def get_float_value(self, key_name: str, value_name: str) -> float:
        key = self.root.get_key(key_name)
        if key:
            value = key.get_value(value_name)
            if value and value.value_type == KVS_TYPE_FLOAT:
                return value.value
        raise KeyError(f"Value '{value_name}' not found in key '{key_name}'")

    def set_pointer_value(self, key_name: str, value_name: str, value: int):
        key = self.root.get_key(key_name)
        if not key:
            key = self.root.create_key(key_name)
        key.set_value(value_name, KVS_TYPE_PTR, value)

    def get_pointer_value(self, key_name: str, value_name: str) -> int:
        key = self.root.get_key(key_name)
        if key:
            value = key.get_value(value_name)
            if value and value.value_type == KVS_TYPE_PTR:
                return value.value
        raise KeyError(f"Value '{value_name}' not found in key '{key_name}'")

    def set_wstring_value(self, key_name: str, value_name: str, value: str):
        key = self.root.get_key(key_name)
        if not key:
            key = self.root.create_key(key_name)
        key.set_value(value_name, KVS_TYPE_WSTRING, value)

    def get_wstring_value(self, key_name: str, value_name: str) -> str:
        key = self.root.get_key(key_name)
        if key:
            value = key.get_value(value_name)
            if value and value.value_type == KVS_TYPE_WSTRING:
                return value.value
        raise KeyError(f"Value '{value_name}' not found in key '{key_name}'")

    def set_color_value(self, key_name: str, value_name: str, value: int):
        key = self.root.get_key(key_name)
        if not key:
            key = self.root.create_key(key_name)
        key.set_value(value_name, KVS_TYPE_COLOR, value)

    def get_color_value(self, key_name: str, value_name: str) -> int:
        key = self.root.get_key(key_name)
        if key:
            value = key.get_value(value_name)
            if value and value.value_type == KVS_TYPE_COLOR:
                return value.value
        raise KeyError(f"Value '{value_name}' not found in key '{key_name}'")

    def set_int64_value(self, key_name: str, value_name: str, value: int):
        key = self.root.get_key(key_name)
        if not key:
            key = self.root.create_key(key_name)
        key.set_value(value_name, KVS_TYPE_INT64, value)

    def get_int64_value(self, key_name: str, value_name: str) -> int:
        key = self.root.get_key(key_name)
        if key:
            value = key.get_value(value_name)
            if value and (value.value_type == KVS_TYPE_INT64 or value.value_type == KVS_TYPE_UINT64):
                return value.value
        raise KeyError(f"Value '{value_name}' not found in key '{key_name}'")

    def set_value(self, key_name: str, value_name: str, value: bytes):
        key = self.root.get_key(key_name)
        if not key:
            key = self.root.create_key(key_name)
        key.set_value(value_name, KVS_TYPE_STRING, value.decode('utf-8'))

    def get_value(self, key_name: str, value_name: str) -> bytes:
        key = self.root.get_key(key_name)
        if key:
            value = key.get_value(value_name)
            if value:
                return value.value.encode('utf-8')
        raise KeyError(f"Value '{value_name}' not found in key '{key_name}'")

    def set_strings_value(self, key_name: str, value_name: str, values: List[str]):
        concatenated_values = '\n'.join(values)
        self.set_string_value(key_name, value_name, concatenated_values)

    def get_strings_value(self, key_name: str, value_name: str) -> List[str]:
        concatenated_values = self.get_string_value(key_name, value_name)
        return concatenated_values.split('\n')

    def create_key(self, key_name: str) -> RegistryKey:
        return self.root.create_key(key_name)

    def get_key(self, key_name: str) -> Optional[RegistryKey]:
        return self.root.get_key(key_name)

    def delete_key(self, key_name: str):
        self.root.delete_key(key_name)

# Class representing a message object, extending KeyValuesSystem
class MessageObject(KeyValuesSystem):
    MESSAGE_OBJECT = "MessageObject"

    def __init__(self):
        super().__init__()
        self.root.create_key(self.MESSAGE_OBJECT)

    def set_int32_value(self, value_name: str, value: int):
        super().set_int32_value(self.MESSAGE_OBJECT, value_name, value)

    def get_int32_value(self, value_name: str, default_value: int = 0) -> int:
        try:
            return super().get_int32_value(self.MESSAGE_OBJECT, value_name)
        except KeyError:
            return default_value

    def set_string_value(self, value_name: str, value: str):
        super().set_string_value(self.MESSAGE_OBJECT, value_name, value)

    def get_string_value(self, value_name: str) -> Optional[str]:
        try:
            return super().get_string_value(self.MESSAGE_OBJECT, value_name)
        except KeyError:
            return None

    def set_strings_value(self, value_name: str, values: List[str]):
        super().set_strings_value(self.MESSAGE_OBJECT, value_name, values)

    def get_strings_value(self, value_name: str) -> Optional[List[str]]:
        try:
            return super().get_strings_value(self.MESSAGE_OBJECT, value_name)
        except KeyError:
            return None

    def set_value(self, value_name: str, value: bytes):
        super().set_value(self.MESSAGE_OBJECT, value_name, value)

    def get_value(self, value_name: str) -> Optional[bytes]:
        try:
            return super().get_value(self.MESSAGE_OBJECT, value_name)
        except KeyError:
            return None

    def set_float_value(self, value_name: str, value: float):
        super().set_float_value(self.MESSAGE_OBJECT, value_name, value)

    def get_float_value(self, value_name: str, default_value: float = 0.0) -> float:
        try:
            return super().get_float_value(self.MESSAGE_OBJECT, value_name)
        except KeyError:
            return default_value

    def set_pointer_value(self, value_name: str, value: int):
        super().set_pointer_value(self.MESSAGE_OBJECT, value_name, value)

    def get_pointer_value(self, value_name: str) -> Optional[int]:
        try:
            return super().get_pointer_value(self.MESSAGE_OBJECT, value_name)
        except KeyError:
            return None

    def set_wstring_value(self, value_name: str, value: str):
        super().set_wstring_value(self.MESSAGE_OBJECT, value_name, value)

    def get_wstring_value(self, value_name: str) -> Optional[str]:
        try:
            return super().get_wstring_value(self.MESSAGE_OBJECT, value_name)
        except KeyError:
            return None

    def set_color_value(self, value_name: str, value: int):
        super().set_color_value(self.MESSAGE_OBJECT, value_name, value)

    def get_color_value(self, value_name: str, default_value: int = 0) -> int:
        try:
            return super().get_color_value(self.MESSAGE_OBJECT, value_name)
        except KeyError:
            return default_value

    def set_int64_value(self, value_name: str, value: int):
        super().set_int64_value(self.MESSAGE_OBJECT, value_name, value)

    def get_int64_value(self, value_name: str, default_value: int = 0) -> int:
        try:
            return super().get_int64_value(self.MESSAGE_OBJECT, value_name)
        except KeyError:
            return default_value

    def get_record(self, key_name: str) -> Optional[RegistryKey]:
        key = self.root.get_key(self.MESSAGE_OBJECT)
        if key:
            return key.get_key(key_name)
        return None

    def new_record(self, key_name: str) -> RegistryKey:
        key = self.root.get_key(self.MESSAGE_OBJECT)
        if key:
            return key.create_key(key_name)
        else:
            return self.root.create_key(key_name)

def print_registry_key(key: RegistryKey, indent: str = ""):
    """Recursively print all keys and values in the registry."""
    for element in key.get_elements():
        if element.is_value():
            value_type = element.value_type
            value = element.value
            print(f"{indent}{element.name}: {value} (Type: {value_type})")
        elif element.is_key():
            print(f"{indent}Key: {element.name}")
            print_registry_key(element, indent + "  ")

# Create a MessageObject instance
msg_obj = MessageObject()

# Set some values
msg_obj.set_int32_value('Score', 100)
msg_obj.set_string_value('PlayerName', 'Alice')
msg_obj.set_float_value('Health', 75.5)
msg_obj.set_int64_value('BigNumber', 1234567890123456789)

# Get values
score = msg_obj.get_int32_value('Score')
player_name = msg_obj.get_string_value('PlayerName')
health = msg_obj.get_float_value('Health')
big_number = msg_obj.get_int64_value('BigNumber')

print(f"Player: {player_name}, Score: {score}, Health: {health}, BigNumber: {big_number}")

# Serialize the object to a bytes stream
output_stream = BytesIO()
msg_obj.serialize(output_stream)

# Reset stream position to the beginning for reading
output_stream.seek(0)

# Deserialize into a new MessageObject
new_msg_obj = MessageObject()
new_msg_obj.deserialize(BytesIO(b'\x00MessageObject\x00\x00addressinfo\x00\x01name\x00ben test\x00\x01Address1\x00asdasdasds\x00\x01Address2\x00\x00\x01City\x00sdafd\x00\x01PostCode\x0012345\x00\x01state\x00AS\x00\x01CountryCode\x00US\x00\x01Phone\x001231231234\x00\x08\x02CreditCardType\x00\x01\x00\x00\x00\x01CardNumber\x004111111111111111\x00\x01CardHolderName\x00ben test\x00\x01CardExpYear\x002024\x00\x01CardExpMonth\x0005\x00\x01CardCVV2\x00111\x00\x08\x08\x00MessageObject\x00\x01name\x00ben test\x00\x01Address1\x00asdasdasds\x00\x01Address2\x00\x00\x01City\x00sdafd\x00\x01PostCode\x0012345\x00\x01state\x00AS\x00\x01CountryCode\x00US\x00\x01Phone\x001231231234\x00\x08\x08\x00MessageObject\x00\x02IsGift\x00\x01\x00\x00\x00\x01GifteeEmail\x00test@ben.com\x00\x07GifteeAccountID\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01GiftMessage\x00I hope you enjoy these games!\x00\x01GifteeName\x00test\x00\x01Sentiment\x00Best Wishes\x00\x01Signature\x00test\x00\x08\x08'))

# Get the root key from the deserialized MessageObject
root_key = new_msg_obj.get_key(new_msg_obj.MESSAGE_OBJECT)

# Print all key-value pairs recursively
print("Deserialized Key/Value pairs:")
if root_key:
    print_registry_key(root_key)