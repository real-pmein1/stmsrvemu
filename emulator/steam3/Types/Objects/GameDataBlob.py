import struct

from steam3.Types.keyvalue_class import KeyValueClass


class GameDataBlob(KeyValueClass):
    def __init__(self, copy=None, input_stream=None):
        super().__init__()
        if copy is not None:
            self.data = copy.data.copy()
        elif input_stream is not None:
            self.parse(input_stream)
        else:
            self.create_key("gamedata")

    def create_key(self, key):
        self.data[key] = {}

    def set_lobbyId(self, value):
        if value:
            self.add_key_value_uint64("gamedata:lobby", value)
        else:
            self.reset_lobbyId()

    def reset_lobbyId(self):
        self.delete_value("gamedata:lobby")

    def get_lobbyId(self):
        return self.get_value("gamedata:lobby", 0)

    def add_key_value_uint64(self, key, value):
        if isinstance(value, int):
            self.data[key] = struct.pack("<Q", value)
        else:
            raise TypeError("Value must be an integer")

    def get_value(self, key, default):
        try:
            return struct.unpack("<Q", self.data[key])[0]
        except KeyError:
            return default

    def delete_value(self, key):
        if key in self.data:
            del self.data[key]

    def parse(self, byte_data):
        # Implement parsing logic here if needed
        pass

    def __repr__(self):
        return f"<GameDataBlob {self.data}>"

# Example usage:
"""gamedata_blob = GameDataBlob()
gamedata_blob.set_lobbyId(123456789012345)
print(gamedata_blob.get_lobbyId())  # Should print the lobbyId
gamedata_blob.reset_lobbyId()
print(gamedata_blob.get_lobbyId())  # Should print 0
"""