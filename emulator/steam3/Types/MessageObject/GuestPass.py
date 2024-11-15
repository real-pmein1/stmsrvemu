from steam3.Types.MessageObject import MessageObject
from steam3.Types.keyvalue_class import KVS_TYPE_INT, KVS_TYPE_INT64, KVS_TYPE_STRING, KVS_TYPE_UINT64


class GuestPass_Deprecated(MessageObject):
    def __init__(self, GID, PackageID, TimeCreated, TimeExpiration, TimeSent, TimeAcked, TimeRedeemed, RecipientAddress, SenderAddress, SenderName):
        # Initialize the base MessageObject with an empty data dictionary
        super().__init__(data={})
        # Set initial values
        self.setValue('GID', GID, KVS_TYPE_UINT64)
        self.setValue('PackageID', PackageID, KVS_TYPE_INT)
        self.setValue('TimeCreated', TimeCreated, KVS_TYPE_INT)
        self.setValue('TimeExpiration', TimeExpiration, KVS_TYPE_INT)
        self.setValue('TimeSent', TimeSent, KVS_TYPE_INT)
        self.setValue('TimeAcked', TimeAcked, KVS_TYPE_INT)
        self.setValue('TimeRedeemed', TimeRedeemed, KVS_TYPE_INT)
        self.setValue('RecipientAddress', RecipientAddress, KVS_TYPE_STRING)
        self.setValue('SenderAddress', SenderAddress, KVS_TYPE_STRING)
        self.setValue('SenderName', SenderName, KVS_TYPE_STRING)

    def __repr__(self):
        # Display all data stored in this GuestPass
        return f"<GuestPass {self.data}>"

"""class GuestPass_Deprecated(MessageObject):
    def __init__(self, GID, PackageID, TimeCreated, TimeExpiration, TimeSent, TimeAcked, TimeRedeemed, RecipientAddress, SenderAddress, SenderName):
        super().__init__(data={})
        self.add_key_value_uint64('GID', GID)
        self.add_key_value_int('PackageID', PackageID)
        self.add_key_value_int('TimeCreated', TimeCreated)
        self.add_key_value_int('TimeExpiration', TimeExpiration)
        self.add_key_value_int('TimeSent', TimeSent)
        self.add_key_value_int('TimeAcked', TimeAcked)
        self.add_key_value_int('TimeRedeemed', TimeRedeemed)
        self.add_key_value_string('RecipientAddress', RecipientAddress)
        self.add_key_value_string('SenderAddress', SenderAddress)
        self.add_key_value_string('SenderName', SenderName)

    def __repr__(self):
        return f"<GuestPass {self.data}>"""