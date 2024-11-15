from io import BytesIO

from steam3.Types.keyvaluesystem import KeyValuesSystem, RegistryValue


class MessageObject:
    def __init__(self, data=None):
        self.data = data if data is not None else {}
        self.kv_class = KeyValuesSystem()
        self.message_objects = []

    def parse(self):
        start = 0
        while True:
            start = self.data.find(b'MessageObject\x00', start)
            if start == -1:
                break
            end = self.data.find(b'MessageObject\x00', start + 1)
            if end == -1:
                end = len(self.data)
            message_data = self.data[start:end]
            kv = KeyValuesSystem()
            kv.deserialize(BytesIO(message_data[len('MessageObject\x00'):]))

            # Convert the deserialized KeyValuesSystem to a dictionary and store it
            self.message_objects.append(self._kv_to_dict(kv.root))
            start = end

    def _kv_to_dict(self, registry_key):
        """
        Helper function to convert a RegistryKey object and its nested elements into a dictionary.
        """
        result = {}
        for element in registry_key.get_elements():
            if element.is_value():
                # Directly map RegistryValue elements to dictionary entries
                result[element.name] = element.value
            elif element.is_key():
                # Recursively convert nested RegistryKey elements
                result[element.name] = self._kv_to_dict(element)
        return result

    def get(self, key):
        return self.kv_class.data.get(key, None)

    def getValue(self, key, default=""):
        return self.data.get(key, default)

    def setValue(self, key, value, type):
        self.data[key] = (value, type)

    def setSubKey(self, key):
        self.data["SubKeyStart"] = key

    def setSubKeyEnd(self):
        self.data["SubKeyEnd"] = None

    def serialize(self):
        # Ensure self.data is serialized into binary format correctly
        if not isinstance(self.data, dict):
            raise ValueError("Data must be a dictionary before serialization.")

        # Create a BytesIO stream to store serialized data
        out_stream = BytesIO()

        # Use KeyValuesSystem to serialize each item in data
        for key, (value, value_type) in self.data.items():
            KeyValuesSystem.serialize_value(out_stream, RegistryValue(key, value_type, value))

        # Retrieve the binary content from the BytesIO stream
        serialized_data = out_stream.getvalue()

        # Return the full serialized output with the special prefix and suffix
        return b"\x00MessageObject\x00" + serialized_data + b"\x08\x08"

    def get_message_objects(self):
        return self.message_objects





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