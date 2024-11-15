from io import BytesIO
from typing import Any, Dict

# Import the new KeyValuesSystem and related classes
from steam3.Types.keyvaluesystem import (
    KeyValuesSystem,
    RegistryKey,
    RegistryValue,
    KVS_TYPE_KEY,
    KVS_TYPE_STRING,
    KVS_TYPE_INT,
    KVS_TYPE_FLOAT,
    KVS_TYPE_PTR,
    KVS_TYPE_WSTRING,
    KVS_TYPE_COLOR,
    KVS_TYPE_UINT64,
    KVS_TYPE_DWORDPREFIXED_STRING,
    KVS_TYPE_INT64,
    KVS_TYPE_NO_MORE,
    KVS_TYPE_NO_MORE_2,
)
class KeyValueClass:
    def __init__(self):
        self.data: Dict[str, Any] = {}
        self.kvs = KeyValuesSystem()

    def parse(self, byte_data: bytes):
        # Deserialize the byte data into the KeyValuesSystem
        input_stream = BytesIO(byte_data)
        self.kvs.deserialize(input_stream)
        # Convert the registry structure into a dictionary
        self.data = self._registry_key_to_dict(self.kvs.root)

    def _registry_key_to_dict(self, registry_key: RegistryKey) -> Dict[str, Any]:
        result = {}
        for element in registry_key.get_elements():
            if element.is_value():
                # Store the value as a tuple of (value, type) to match the old KeyValueClass behavior
                result[element.name] = (element.value, element.value_type)
            elif element.is_key():
                # Handle subkeys by using "SubKeyStart" and "SubKeyEnd"
                subkey_dict = self._registry_key_to_dict(element)
                result["SubKeyStart"] = element.name
                result.update(subkey_dict)
                result["SubKeyEnd"] = None
        return result

    def serialize(self, custom_data: Dict[str, Any] = None) -> bytes:
        if custom_data is None:
            data_to_serialize = self.data
        else:
            data_to_serialize = custom_data
        # Clear the root key
        self.kvs.root = RegistryKey("root")
        self._dict_to_registry_key(data_to_serialize, self.kvs.root)
        # Serialize the KeyValuesSystem into bytes
        out_stream = BytesIO()
        self.kvs.serialize(out_stream)
        return out_stream.getvalue()

    def _dict_to_registry_key(self, data_dict: Dict[str, Any], registry_key: RegistryKey):
        stack = []
        current_key = registry_key
        for key, value in data_dict.items():
            if key == "SubKeyStart":
                # Start a new subkey
                subkey_name = value
                subkey = RegistryKey(subkey_name)
                current_key.add_element(subkey)
                stack.append(current_key)
                current_key = subkey
            elif key == "SubKeyEnd":
                # End of the current subkey
                if stack:
                    current_key = stack.pop()
                else:
                    # Error, unmatched SubKeyEnd
                    raise Exception("Unmatched SubKeyEnd")
            elif isinstance(value, dict):
                # Nested dictionaries represent subkeys
                subkey = RegistryKey(key)
                current_key.add_element(subkey)
                self._dict_to_registry_key(value, subkey)
            else:
                # Handle values stored as (value, type) tuples
                if isinstance(value, tuple) and len(value) == 2:
                    val, val_type = value
                else:
                    # Default to KVS_TYPE_STRING if type is not specified
                    val = value
                    val_type = KVS_TYPE_STRING
                registry_value = RegistryValue(key, val_type, val)
                current_key.add_element(registry_value)

    @staticmethod
    def _read_null_terminated_wstring(data):
        parts = data.split(b'\x00\x00', 1)
        if len(parts) == 2:
            return parts[0].decode('utf-16-le'), parts[1] + b'\x00\x00'
        else:
            raise ValueError("WString not null-terminated")