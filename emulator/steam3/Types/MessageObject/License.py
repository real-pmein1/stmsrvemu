from steam3.Types.MessageObject import MessageObject
from steam3.Types.keyvalue_class import KVS_TYPE_INT, KVS_TYPE_STRING, KVS_TYPE_UINT64
from steam3.Types.steam_types import ELicenseType, ELicenseFlags, EPaymentMethod
import time


class License(MessageObject):
    """
    Modern License MessageObject based on the Steam client structure.
    
    This matches the protobuf License structure used by newer Steam clients:
    - package_id: The package (subscription) this license grants access to
    - time_created: Unix timestamp when license was created
    - time_next_process: Next processing time for recurring licenses
    - minute_limit: Minutes limit for time-based licenses (0 = unlimited)
    - minutes_used: Minutes already used
    - payment_method: How this license was obtained
    - flags: License flags (ELicenseFlags)
    - purchase_country_code: Country where license was purchased
    - license_type: Type of license (ELicenseType)
    - territory_code: Territory restriction
    - change_number: For license updates
    - owner_id: Original owner account ID
    - initial_period/initial_time_unit: Initial activation period
    - renewal_period/renewal_time_unit: Renewal period for recurring
    - access_token: For shared licenses
    - master_package_id: For sub-packages
    """
    
    def __init__(self, package_id=0, time_created=None, time_next_process=0, minute_limit=0, 
                 minutes_used=0, payment_method=EPaymentMethod.CreditCard, flags=ELicenseFlags.NONE, 
                 purchase_country_code="US", license_type=ELicenseType.SinglePurchase, 
                 territory_code=0, change_number=0, owner_id=0, initial_period=0, 
                 initial_time_unit=0, renewal_period=0, renewal_time_unit=0, access_token=0, 
                 master_package_id=0):
        
        # Initialize the base MessageObject
        super().__init__(data={})
        
        # Use current time if not provided
        if time_created is None:
            time_created = int(time.time())
        
        # Set all license fields

        self.setValue('PackageID', package_id, KVS_TYPE_INT)  # 4 byte int
        self.setValue('TimeCreated', time_created, KVS_TYPE_INT)  # 4 byte int
        self.setValue('TimeNextProcess', time_next_process, KVS_TYPE_INT)  # 4 byte int
        self.setValue('MinuteLimit', minute_limit, KVS_TYPE_INT)  # 4 byte int
        self.setValue('MinutesUsed', minutes_used, KVS_TYPE_INT)  # 4 byte int
        self.setValue('PaymentMethod', payment_method, KVS_TYPE_INT)  # 4 byte int # PaymentMethod
        self.setValue('PurchaseCountryCode', purchase_country_code, KVS_TYPE_STRING)  # 2 letter country code
        self.setValue('Flags', flags, KVS_TYPE_INT)  # 4 byte int  # LicenseFlags
        self.setValue('LicenseType', license_type, KVS_TYPE_INT)  # 4 byte int # LicenseType

        self.setValue('TerritoryCode', territory_code, KVS_TYPE_INT)
        self.setValue('ChangeNumber', change_number, KVS_TYPE_INT)
        self.setValue('OwnerID', owner_id, KVS_TYPE_INT)
        self.setValue('InitialPeriod', initial_period, KVS_TYPE_INT)
        self.setValue('InitialTimeUnit', initial_time_unit, KVS_TYPE_INT)
        self.setValue('RenewalPeriod', renewal_period, KVS_TYPE_INT)
        self.setValue('RenewalTimeUnit', renewal_time_unit, KVS_TYPE_INT)
        self.setValue('AccessToken', access_token, KVS_TYPE_UINT64)
        self.setValue('MasterPackageID', master_package_id, KVS_TYPE_INT)


    @classmethod
    def from_database_record(cls, db_record):
        """Create a License from a Steam3LicenseRecord database object"""
        return cls(
            package_id=db_record.PackageID,
            time_created=int(db_record.DateAdded.timestamp()) if db_record.DateAdded else int(time.time()),
            time_next_process=db_record.TimeNextProcess or 0,
            minute_limit=db_record.TimeLimit or 0,
            minutes_used=db_record.MinutesUsed or 0,
            payment_method=EPaymentMethod(db_record.PaymentType or EPaymentMethod.CreditCard),
            flags=ELicenseFlags(db_record.LicenseFlags or ELicenseFlags.NONE),
            purchase_country_code=db_record.PurchaseCountryCode or "US",
            license_type=ELicenseType(db_record.LicenseType or ELicenseType.SinglePurchase),
            territory_code=0,  # Not stored in current DB schema
            change_number=db_record.ChangeNumber or 0,
            owner_id=db_record.OwnerAccountID or db_record.AccountID,
            initial_period=db_record.InitialPeriod or 0,
            initial_time_unit=db_record.InitialTimeUnit or 0,
            renewal_period=db_record.RenewalPeriod or 0,
            renewal_time_unit=db_record.RenewalTimeUnit or 0,
            access_token=db_record.AccessToken or 0,
            master_package_id=db_record.MasterPackageID or 0
        )

    @classmethod
    def from_subscription_record(cls, sub_record):
        """
        Create a License from an AccountSubscriptionsRecord database object.

        This converts legacy Steam2 subscriptions to the Steam3 License format.
        AccountSubscriptionsRecord fields:
            - SubscriptionID -> PackageID
            - SubscribedDate (string "MM/DD/YYYY HH:MM:SS") -> TimeCreated
            - UserCountryCode -> PurchaseCountryCode
            - UserRegistry_UniqueID -> OwnerID

        Args:
            sub_record: An AccountSubscriptionsRecord database object

        Returns:
            A License MessageObject
        """
        from datetime import datetime

        # Parse SubscribedDate string to Unix timestamp
        time_created = int(time.time())  # Default to current time
        if sub_record.SubscribedDate:
            try:
                # Format: "MM/DD/YYYY HH:MM:SS" (e.g., "01/12/2024 17:25:34")
                dt = datetime.strptime(sub_record.SubscribedDate, "%m/%d/%Y %H:%M:%S")
                time_created = int(dt.timestamp())
            except (ValueError, TypeError):
                pass  # Use default if parsing fails

        return cls(
            package_id=sub_record.SubscriptionID,
            time_created=time_created,
            time_next_process=0,
            minute_limit=0,
            minutes_used=0,
            payment_method=EPaymentMethod.CreditCard,  # Default for legacy subscriptions
            flags=ELicenseFlags.NONE,
            purchase_country_code=sub_record.UserCountryCode[:2] if sub_record.UserCountryCode else "US",
            license_type=ELicenseType.SinglePurchase,  # Default for legacy subscriptions
            territory_code=0,
            change_number=0,
            owner_id=sub_record.UserRegistry_UniqueID or 0,
            initial_period=0,
            initial_time_unit=0,
            renewal_period=0,
            renewal_time_unit=0,
            access_token=0,
            master_package_id=0
        )
    
    def get_package_id(self):
        """Get the package ID for this license"""
        return self.getValue('PackageID', 0)
    
    def get_time_created(self):
        """Get the creation timestamp"""
        return self.getValue('TimeCreated', 0)
    
    def get_license_type(self):
        """Get the license type"""
        return ELicenseType(self.getValue('LicenseType', ELicenseType.SinglePurchase))
    
    def get_flags(self):
        """Get the license flags"""
        return ELicenseFlags(self.getValue('Flags', ELicenseFlags.NONE))
    
    def is_active(self):
        """Check if this license is currently active"""
        flags = self.get_flags()
        return not (flags & (ELicenseFlags.Expired | ELicenseFlags.CancelledByUser | 
                           ELicenseFlags.CancelledByAdmin | ELicenseFlags.NotActivated))
    
    def __repr__(self):
        return (f"<License package_id={self.get_package_id()} "
                f"type={self.get_license_type()} flags={self.get_flags()} "
                f"created={self.get_time_created()}>")


# Keep the old deprecated class for backwards compatibility
class Deprecated_License(MessageObject):
    """
    Deprecated License MessageObject for backwards compatibility with older Steam clients.

    This uses a simplified field set compared to the modern License class.
    """

    def __init__(self, package_id, time_created, time_next_process, minute_limit,
                 minutes_used, payment_method, purchase_country_code, flags, license_type):
        # Initialize the base MessageObject with an empty data dictionary
        super().__init__(data={})

        # Set initial values with specific keys for the License using provided parameters
        self.setValue('PackageID', package_id, KVS_TYPE_INT)  # 4 byte int
        self.setValue('TimeCreated', time_created, KVS_TYPE_INT)  # 4 byte int
        self.setValue('TimeNextProcess', time_next_process, KVS_TYPE_INT)  # 4 byte int
        self.setValue('MinuteLimit', minute_limit, KVS_TYPE_INT)  # 4 byte int
        self.setValue('MinutesUsed', minutes_used, KVS_TYPE_INT)  # 4 byte int
        self.setValue('PaymentMethod', payment_method, KVS_TYPE_INT)  # 4 byte int # PaymentMethod
        self.setValue('PurchaseCountryCode', purchase_country_code, KVS_TYPE_STRING)  # 2 letter country code
        self.setValue('flags', flags, KVS_TYPE_INT)  # 4 byte int  # LicenseFlags
        self.setValue('LicenseType', license_type, KVS_TYPE_INT)  # 4 byte int # LicenseType

    @classmethod
    def from_database_record(cls, db_record):
        """Create a Deprecated_License from a Steam3LicenseRecord database object"""
        return cls(
            package_id=db_record.PackageID,
            time_created=int(db_record.DateAdded.timestamp()) if db_record.DateAdded else int(time.time()),
            time_next_process=db_record.TimeNextProcess or 0,
            minute_limit=db_record.TimeLimit or 0,
            minutes_used=db_record.MinutesUsed or 0,
            payment_method=int(db_record.PaymentType or EPaymentMethod.CreditCard),
            purchase_country_code=db_record.PurchaseCountryCode or "US",
            flags=int(db_record.LicenseFlags or ELicenseFlags.NONE),
            license_type=int(db_record.LicenseType or ELicenseType.SinglePurchase)
        )

    @classmethod
    def from_subscription_record(cls, sub_record):
        """
        Create a Deprecated_License from an AccountSubscriptionsRecord database object.

        This converts legacy Steam2 subscriptions to the License format.
        """
        from datetime import datetime

        # Parse SubscribedDate string to Unix timestamp
        time_created = int(time.time())  # Default to current time
        if sub_record.SubscribedDate:
            try:
                # Format: "MM/DD/YYYY HH:MM:SS" (e.g., "01/12/2024 17:25:34")
                dt = datetime.strptime(sub_record.SubscribedDate, "%m/%d/%Y %H:%M:%S")
                time_created = int(dt.timestamp())
            except (ValueError, TypeError):
                pass  # Use default if parsing fails

        return cls(
            package_id=sub_record.SubscriptionID,
            time_created=time_created,
            time_next_process=0,
            minute_limit=0,
            minutes_used=0,
            payment_method=int(EPaymentMethod.CreditCard),
            purchase_country_code=sub_record.UserCountryCode[:2] if sub_record.UserCountryCode else "US",
            flags=int(ELicenseFlags.NONE),
            license_type=int(ELicenseType.SinglePurchase)
        )

    def get_package_id(self):
        """Get the package ID for this license"""
        return self.getValue('PackageID', 0)

    def get_time_created(self):
        """Get the creation timestamp"""
        return self.getValue('TimeCreated', 0)

    def __repr__(self):
        return f"<Deprecated_License package_id={self.get_package_id()} {self.data}>"