from steam3.Types.MessageObject import MessageObject
from steam3.Types.keyvalue_class import KVS_TYPE_INT, KVS_TYPE_UINT64


class ChatMemberInfo(MessageObject):
    def __init__(self, copy=None, input_stream=None):
        super().__init__()
        if copy is not None:
            self.data = copy.data.copy()
        elif input_stream is not None:
            self.parse(input_stream)
        else:
            self.set_SteamID(0)
            self.set_Permissions(0)
            self.set_Details(0)  # Assuming ClanPermission_nobody is 0

    def get_SteamID(self):
        return self.getValue("SteamID", 0)

    def get_Permissions(self):
        return self.getValue("Permissions", 0)

    def get_Details(self):
        return self.getValue("Details", 0)

    def set_SteamID(self, value):
        self.add_key_value_uint64("SteamID", value, KVS_TYPE_UINT64)

    def set_Permissions(self, value):
        self.add_key_value_int("Permissions", value, KVS_TYPE_INT)

    def set_Details(self, value):
        self.add_key_value_int("Details", value, KVS_TYPE_INT)

    def __repr__(self):
        return (f"<ChatMemberInfo SteamID={self.get_SteamID()} "
                f"Permissions={self.get_Permissions()} "
                f"Details={self.get_Details()}>")