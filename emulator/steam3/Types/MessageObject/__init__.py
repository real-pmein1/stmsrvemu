from io import BytesIO
from typing import Optional
from steam3.Types.keyvaluesystem import KeyValuesSystem, RegistryKey, RegistryValue, KVS_TYPE_STRING

class MessageObject:
    def __init__(self, data=None):
        """
        Initialize a MessageObject.

        :param data: bytes (raw KV blob containing one or more MessageObject blocks),
                     dict (to build a KV tree), or None (start empty).
        """
        self.kv = KeyValuesSystem()
        self.message_objects = []
        self.current_key: Optional[RegistryKey] = None
        self.data = {}

        if data is None:
            # Start fresh; create a working "MessageObject" key.
            self.current_key = self.kv.root.create_key("MessageObject")

        elif isinstance(data, (bytes, bytearray, memoryview)):
            # Parse raw binary containing one or more "MessageObject\0" segments.
            self.raw_data = bytes(data)
            self.parse()
            # After parsing, default to the last parsed MessageObject key if available.
            mos = [e for e in self.kv.root.get_elements()
                   if isinstance(e, RegistryKey) and e.name == "MessageObject"]
            self.current_key = mos[-1] if mos else self.kv.root

        elif isinstance(data, dict):
            # Build a KV tree from a Python dict.
            self.current_key = self.kv.root.create_key("MessageObject")
            for key, item in data.items():
                if isinstance(item, dict):
                    self.setSubKey(key)
                    for sub_key, sub_item in item.items():
                        if isinstance(sub_item, tuple) and len(sub_item) == 2:
                            self.current_key.set_value(sub_key, sub_item[1], sub_item[0])
                        else:
                            self.current_key.set_value(sub_key, KVS_TYPE_STRING, str(sub_item))
                    self.setSubKeyEnd()
                else:
                    if isinstance(item, tuple) and len(item) == 2:
                        self.current_key.set_value(key, item[1], item[0])
                    else:
                        self.current_key.set_value(key, KVS_TYPE_STRING, str(item))
        else:
            raise ValueError("Data must be bytes, dict, or None.")

    def parse(self):
        """
        Scan self.raw_data for all occurrences of b'MessageObject\\x00' and, for each,
        deserialize the following KV payload into a new 'MessageObject' subkey under root.
        Also cache a plain dict for convenience in self.message_objects.
        """
        if not hasattr(self, 'raw_data') or self.raw_data is None:
            raise ValueError("No raw binary data provided for parsing.")

        data = self.raw_data
        prefix = b"MessageObject\x00"
        start = 0

        while True:
            start = data.find(prefix, start)
            if start == -1:
                break

            next_start = data.find(prefix, start + len(prefix))
            if next_start == -1:
                next_start = len(data)

            # Payload (values/keys) inside this MessageObject block
            message_data = data[start + len(prefix): next_start]

            # Create a real subkey under root and deserialize into it.
            subkey = self.kv.root.create_key("MessageObject")
            KeyValuesSystem.deserialize_key(subkey, BytesIO(message_data))

            # Cache a dict view of this subkey for convenience
            self.message_objects.append(self._kv_to_dict(subkey))

            start = next_start

        # If nothing was found, leave structure as-is (no exception).

    def _kv_to_dict(self, registry_key) -> dict:
        """Recursively convert a RegistryKey to a plain dict."""
        result = {}
        for element in registry_key.get_elements():
            if element.is_value():
                result[element.name] = element.value
            elif element.is_key():
                result[element.name] = self._kv_to_dict(element)
        return result

    def setValue(self, key, value, value_type):
        self.current_key.set_value(key, value_type, value)

    def setSubKey(self, key):
        new_subkey = self.current_key.create_key(key)
        self.current_key = new_subkey

    def setSubKeyEnd(self):
        if self.current_key.parent is not None:
            self.current_key = self.current_key.parent

    def serialize(self, include_wrapper: bool = True):
        """
        Serialize the MessageObject to binary format.

        Args:
            include_wrapper: If True, include the "MessageObject" key wrapper.
                           If False, serialize only the contents (legacy behavior).

        Format with wrapper (include_wrapper=True):
            0x00 "MessageObject\0" <values...> 0x08 0x08

        Format without wrapper (include_wrapper=False):
            <type> <name\0> <value> ... 0x08
        """
        out_stream = BytesIO()
        mo_key = self.kv.root.get_key("MessageObject")

        if mo_key:
            if include_wrapper:
                # Include the full MessageObject key wrapper
                # Format: 0x00 "MessageObject\0" <contents> 0x08
                KeyValuesSystem.serialize_key(out_stream, mo_key)
                # Add final end marker for root level
                out_stream.write(bytes([0x08]))
            else:
                # Legacy: serialize only the contents without wrapper
                KeyValuesSystem.serialize_keys(out_stream, mo_key)
        else:
            # Fallback: serialize from root
            self.kv.serialize(out_stream)

        return out_stream.getvalue()

    def get(self, key):
        """
        Retrieve the value associated with 'key' from the current key.
        If current_key is missing (e.g., earlier code set it to None), recover it.
        """
        if self.current_key is None:
            mos = [e for e in self.kv.root.get_elements()
                   if isinstance(e, RegistryKey) and e.name == "MessageObject"]
            self.current_key = mos[0] if mos else self.kv.root

        val_obj = self.current_key.get_value(key)
        return val_obj.value if val_obj else None

    def getValue(self, key, default=""):
        val = self.get(key)
        return val if val is not None else default

    def get_message_objects(self):
        return self.message_objects

    def parse_to_dict(self) -> dict:
        return self._kv_to_dict(self.kv.root)

    def __repr__(self):
        return f"<MessageObject {self.kv}>"




# Parsing Example usage:
# data = b'\x00MessageObject\x00\x00addressinfo\x00\x01name\x00ben test\x00\x01Address1\x00asdasdasds\x00\x01Address2\x00\x00\x01City\x00sdafd\x00\x01PostCode\x0012345\x00\x01state\x00AS\x00\x01CountryCode\x00US\x00\x01Phone\x001231231234\x00\x08\x02CreditCardType\x00\x01\x00\x00\x00\x01CardNumber\x004111111111111111\x00\x01CardHolderName\x00ben test\x00\x01CardExpYear\x002024\x00\x01CardExpMonth\x0005\x00\x01CardCVV2\x00111\x00\x08\x08\x00MessageObject\x00\x01name\x00ben test\x00\x01Address1\x00asdasdasds\x00\x01Address2\x00\x00\x01City\x00sdafd\x00\x01PostCode\x0012345\x00\x01state\x00AS\x00\x01CountryCode\x00US\x00\x01Phone\x001231231234\x00\x08\x08\x00MessageObject\x00\x02IsGift\x00\x01\x00\x00\x00\x01GifteeEmail\x00test@ben.com\x00\x07GifteeAccountID\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01GiftMessage\x00I hope you enjoy these games!\x00\x01GifteeName\x00test\x00\x01Sentiment\x00Best Wishes\x00\x01Signature\x00test\x00\x08\x08'
# message_objects = MessageObject(data)
# message_objects.parse()
# for obj in message_objects.get_message_objects():
#    print(obj)

# Serializing/Create MessageObject Example:
# kv = KeyValueClass()
# Assume kv.data is filled with key-value pairs.
# kv.data['name'] = 'ChatGPT'
# kv.data['age'] = 30

# message_obj = MessageObject(kv)
# serialized_data = message_obj.serialize()
# print(serialized_data)