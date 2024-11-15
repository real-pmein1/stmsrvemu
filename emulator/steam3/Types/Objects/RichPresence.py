from steam3.Types.keyvalue_class import KVS_TYPE_STRING, KeyValueClass


class RichPresence(KeyValueClass):
    def __init__(self, copy=None, input_stream=None):
        super().__init__()
        self.kv_class = KeyValueClass()
        if copy is not None:
            self.data = copy.data.copy()
        elif input_stream is not None:
            self.parse(input_stream)
        else:
            self.create_key("RP")

    def create_key(self, key):
        #self.data[key] = {}
        self.data["SubKeyStart"] = key
    def set_endkey(self):
        self.data["SubKeyEnd"] = None
    def get_richPresenceKeys(self):
        return list(self.data["RP"].keys())

    def set_richPresence(self, key, value):
        #self.setvalue(key, value, KVS_TYPE_STRING)
        self.data[key] = (value, KVS_TYPE_STRING)

    def reset_richPresence(self, key):
        if key in self.data["RP"]:
            del self.data["RP"][key]

    def get_richPresence(self, key):
        return self.data["RP"].get(key, None)

    def serialize(self):
        return self.kv_class.serialize(self.data)

    def __repr__(self):
        return f"<RichPresence {self.data}>"