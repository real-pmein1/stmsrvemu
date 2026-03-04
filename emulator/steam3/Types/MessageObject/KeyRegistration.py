from steam3.Types.keyvaluesystem import KVS_TYPE_STRING
from steam3.Types.MessageObject import MessageObject  # adjust import path as needed

class KeyRegistration(MessageObject):
    """
    A specialized MessageObject for Steam Key Registration messages.

    You can construct it either from raw bytes (it will parse the first
    MessageObject entry and extract its 'Key' field) or by passing a key
    string to create a fresh registration message.
    """
    def __init__(self, raw_data: bytes = None, key: str = None):
        # From raw bytes: parse out the Key
        if raw_data is not None:
            super().__init__(raw_data)
            self.parse()  # populate self.message_objects
            objs = self.get_message_objects()
            if not objs:
                raise ValueError("No MessageObject entries found in data")
            # we only care about the first one
            self.payload = objs[0]
            self.key = self.payload.get("Key")
        # From a Python string: build a new MessageObject with that Key
        elif key is not None:
            super().__init__({ "Key": (key, KVS_TYPE_STRING) })
            # The dict-init path in MessageObject sets up kv.root->MessageObject->Key
            self.payload = { "Key": key }
            self.key = key
        else:
            raise ValueError("Either raw_data or key must be provided")

    def __str__(self):
        return f"KeyRegistration(Key={self.key})"

    def __repr__(self):
        return f"<KeyRegistration payload={self.payload!r}>"

    def serialize(self) -> bytes:
        """
        Returns the binary form of this registration message,
        including the leading 'MessageObject\x00' prefix.
        """
        # MessageObject.serialize already includes the prefix & trailing markers
        return super().serialize()
