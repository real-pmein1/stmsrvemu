from steam3.Types.MessageObject import MessageObject
from steam3.Types.keyvalue_class import KVS_TYPE_INT, KVS_TYPE_STRING


class License_Deprecated(MessageObject):
    def __init__(self, package_id, time_created, time_next_process, minute_limit, minutes_used, payment_method, purchase_country_code, flags, license_type):
        # Initialize the base MessageObject with an empty data dictionary
        super().__init__(data={})
        # Set initial values with specific keys for the License using provided parameters
        self.setValue('PackageID', package_id, KVS_TYPE_INT)  # 4 byte int
        self.setValue('TimeCreated', time_created, KVS_TYPE_INT)  # 4 byte int
        self.setValue('TimeNextProcess', time_next_process, KVS_TYPE_INT)  # 4 byte int
        self.setValue('MinuteLimit', minute_limit, KVS_TYPE_INT)  # 4 byte int
        self.setValue('MinutesUsed', minutes_used, KVS_TYPE_INT)  # 4 byte int
        self.setValue('PaymentMethod', payment_method, KVS_TYPE_INT)  # 4 byte int # PaymentMethod
        self.setValue('PurchaseCountryCode', purchase_country_code, KVS_TYPE_STRING) # 2 letter country code or int?
        self.setValue('flags', flags, KVS_TYPE_INT)  # 4 byte int  # LicenseFlags
        self.setValue('LicenseType', license_type, KVS_TYPE_INT)  # 4 byte int # LicenseType

    def __repr__(self):
        # Display all data stored in this License for debugging
        return f"<License_Deprecated {self.data}>"


"""class License_Deprecated(MessageObject):
    def __init__(self, package_id, time_created, time_next_process, minute_limit, minutes_used, payment_method, purchase_country_code, flags, license_type):
        # Initialize the base MessageObject with an empty data dictionary
        super().__init__(data={})
        # Set initial values with specific keys for the License using provided parameters
        self.add_key_value_int('PackageID', package_id)  # 4 byte int
        self.add_key_value_int('TimeCreated', time_created)  # 4 byte int
        self.add_key_value_int('TimeNextProcess', time_next_process)  # 4 byte int
        self.add_key_value_int('MinuteLimit', minute_limit)  # 4 byte int
        self.add_key_value_int('MinutesUsed', minutes_used)  # 4 byte int
        self.add_key_value_int('PaymentMethod', payment_method)  # 4 byte int # PaymentMethod
        self.add_key_value_string('PurchaseCountryCode', purchase_country_code) # 2 letter country code or int?
        self.add_key_value_int('flags', flags)  # 4 byte int  # LicenseFlags
        self.add_key_value_int('LicenseType', license_type)  # 4 byte int # LicenseType

    def __repr__(self):
        # Display all data stored in this License for debugging
        return f"<License_Deprecated {self.data}>"""