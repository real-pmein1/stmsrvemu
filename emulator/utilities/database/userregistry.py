import logging

import globalvars
import utilities.time
import utils
from utilities import encryption

from utilities.blobs import BlobBuilder
from utilities.database import base_dbdriver

log = logging.getLogger('UserRegBuilder')


class UserRegistry(): # NOTE: this is a subclass of the Auth Database Driver, makes life simpler when dealing with the database

    def __init__(self, authdb_instance):
        self.authdb_instance = authdb_instance
        self.db_driver = self.authdb_instance.db_driver
        self.username = None

    def build_user_registry(self, builder, user_data):
        userregistry_version = 4

        builder.add_entry(b"\x00\x00\x00\x00", userregistry_version.to_bytes(2, "little"))
        builder.add_entry(b"\x01\x00\x00\x00", user_data.UniqueUserName.encode('latin-1') + b"\x00")
        builder.add_entry(b"\x02\x00\x00\x00", utilities.time.datetime_to_steamtime(user_data.AccountCreationTime))
        builder.add_entry(b"\x03\x00\x00\x00", b'Egq-pe-y\x00')

        numbers = user_data.DerivedSubscribedAppsRecord
        if numbers and numbers.strip() != '':
            integers = [int(x.strip()) for x in numbers.split(',')]
            result_dict = {value.to_bytes(4, byteorder = 'little'):b'' for value in integers}
        else:
            result_dict = b''
        builder.add_entry(b"\x08\x00\x00\x00", result_dict)
        builder.add_entry(b"\x09\x00\x00\x00", utilities.time.datetime_to_steamtime(user_data.LastRecalcDerivedSubscribedAppsTime))
        builder.add_entry(b"\x0a\x00\x00\x00", globalvars.cellid.to_bytes(4, "little"))
        builder.add_entry(b"\x0b\x00\x00\x00", user_data.AccountEmailAddress.encode('latin-1') + b"\x00")
        builder.add_entry(b"\x0e\x00\x00\x00", utilities.time.datetime_to_steamtime(user_data.AccountLastModifiedTime))

        builder.AccountUsersRecord(
                user_data.UniqueUserName.encode("latin-1"),
                {
                        b"\x01\x00\x00\x00":int(user_data.UniqueID).to_bytes(4, "little") + b"\x00\x00\x00\x00",
                        b"\x02\x00\x00\x00":user_data.UserType.to_bytes(2, "little"),
                        b"\x03\x00\x00\x00":{},
                }
        )

    def process_subscriptions_billing_info(self, builder, user_id):
        subscriptions_billing_record_data = self.db_driver.select_data(
                base_dbdriver.AccountSubscriptionsBillingInfoRecord,
                base_dbdriver.AccountSubscriptionsBillingInfoRecord.UserRegistry_UniqueID == user_id
        )

        for record in subscriptions_billing_record_data:
            self.process_individual_billing_info(builder, record)

    def process_individual_billing_info(self, builder, record):
        subscription_billing_info_typeid = record.SubscriptionID.to_bytes(4, "little")

        if subscription_billing_info_typeid not in globalvars.CDR_DICTIONARY[b'\x02\x00\x00\x00']:
            return  # Skip processing if the subscription ID is not found

        payment_receipt_type = record.AccountPaymentType

        if payment_receipt_type == 7:
            builder.add_account_subscriptions_billing_info(subscription_billing_info_typeid, payment_receipt_type.to_bytes(1, "little"))

        elif payment_receipt_type == 6:
            sub_prepurchase_record_data = self.db_driver.select_data(
                    base_dbdriver.AccountPrepurchasedInfoRecord,
                    base_dbdriver.AccountPrepurchasedInfoRecord.UniqueID == record.AccountPrepurchasedInfoRecord_UniqueID
            )

            # We encrypt the key using the rsa network key, ONLY if it is a ValveCDKey
            if sub_prepurchase_record_data[0].TypeOfProofOfPurchase.encode('latin-1') == b'ValveCDKey':
                encrypted_key = b'\x00\x00\x00\x00\x00\x00\x00\x1d\x00\x80' + encryption.aes_encrypt_no_IV(encryption.network_key, sub_prepurchase_record_data[0].BinaryProofOfPurchaseToken.encode('latin-1'))
            else:
                encrypted_key = sub_prepurchase_record_data[0].BinaryProofOfPurchaseToken.encode('latin-1')

            builder.add_account_subscriptions_billing_info(subscription_billing_info_typeid,
                                                           payment_receipt_type.to_bytes(1, "little"),
                                                           card_number = sub_prepurchase_record_data[0].TypeOfProofOfPurchase.encode('latin-1') + b"\x00",
                                                           card_holder_name = encrypted_key + b"\x00")

        elif payment_receipt_type == 5:
            sub_payment_card_record_data = self.db_driver.select_data(
                    base_dbdriver.AccountPaymentCardInfoRecord,
                    base_dbdriver.AccountPaymentCardInfoRecord.UniqueID == record.AccountPaymentCardReceiptRecord_UniqueID
            )

            payment_card_dbdata_variables = sub_payment_card_record_data[0]
            price_before_tax_bytes = int(payment_card_dbdata_variables.PriceBeforeTax).to_bytes(4, "little")
            tax_amount_bytes = int(payment_card_dbdata_variables.TaxAmount).to_bytes(4, "little")

            builder.add_account_subscriptions_billing_info(subscription_billing_info_typeid,
                                                           payment_receipt_type.to_bytes(1, "little"),
                                                           payment_card_dbdata_variables.PaymentCardType.to_bytes(1, "little"),
                                                           payment_card_dbdata_variables.CardNumber[12:].encode('latin-1') + b'\x00',
                                                           payment_card_dbdata_variables.CardHolderName.encode('latin-1') + b'\x00',
                                                           payment_card_dbdata_variables.BillingAddress1.encode('latin-1') + b'\x00',
                                                           payment_card_dbdata_variables.BillingAddress2.encode('latin-1') + b'\x00',
                                                           payment_card_dbdata_variables.BillingCity.encode('latin-1') + b'\x00',
                                                           payment_card_dbdata_variables.BillingZip.encode('latin-1') + b'\x00',
                                                           payment_card_dbdata_variables.BillingState.encode('latin-1') + b'\x00',
                                                           payment_card_dbdata_variables.BillingCountry.encode('latin-1') + b'\x00',
                                                           str(payment_card_dbdata_variables.CCApprovalCode).encode('ascii') + b"\x00",
                                                           price_before_tax_bytes,
                                                           tax_amount_bytes,
                                                           payment_card_dbdata_variables.TransDate.encode('latin-1') + b'\x00',
                                                           payment_card_dbdata_variables.TransTime.encode('latin-1') + b'\x00',
                                                           str(payment_card_dbdata_variables.AStoBBSTxnId).encode('ascii') + b"\x00",
                                                           b"\x00\x00\x00\x00")

        else:
            log.error(f"[PaymentInfo] {self.username} Has No Subscriptions! Should have at least subscription 0!")

    def process_subscription_records(self, builder, user_id, clientver):
        subscription_record_variables = self.db_driver.select_data(
                base_dbdriver.AccountSubscriptionsRecord,
                base_dbdriver.AccountSubscriptionsRecord.UserRegistry_UniqueID == user_id
        )

        if not subscription_record_variables:  # This will be True for an empty list
            if clientver in ["b2003"]:
                # This block will only execute if clientver is "B2003" and subscription_record_variables is empty
                builder.add_entry(b"\x07\x00\x00\x00", {})
                return
            else:
                #log.error(f"[Subscription Info] {self.username} Has No Subscriptions! Should have at least subscription 0!")
                self.authdb_instance.insert_sub_0(user_id)
                subscription_record_variables = self.db_driver.select_data(
                        base_dbdriver.AccountSubscriptionsRecord,
                        base_dbdriver.AccountSubscriptionsRecord.UserRegistry_UniqueID == user_id
                )

        for record in subscription_record_variables:
            subscription_id_bytes = record.SubscriptionID.to_bytes(4, "little")

            # Check if the subscription ID exists under b'\x02\x00\x00\x00'
            if subscription_id_bytes in globalvars.CDR_DICTIONARY[b'\x02\x00\x00\x00']:
                builder.add_account_subscription(
                        subscription_id_bytes,
                        utilities.time.datetime_to_steamtime(record.SubscribedDate),
                        b"\x00\x00\x00\x00\x00\x00\x00\x00",
                        record.SubscriptionStatus.to_bytes(1, "little") + b"\x00",
                        record.StatusChangeFlag.to_bytes(1, "little"),
                        record.PreviousSubscriptionState.to_bytes(1, "little") + b"\x00",
                        clientver
                )


class UserRegistryBuilder(BlobBuilder):

    def __init__(self):
        super(UserRegistryBuilder, self).__init__()

    def AccountUsersRecord(self, username, value_dict):
        self.add_subdict(b"\x06\x00\x00\x00", username, value_dict)

    def DerivedSubscribedAppsRecord(self, value_dict):
        self.add_subdict(b"\x08\x00\x00\x00", "", value_dict)

    def InsertBaseRegistryInformation(self, **kwargs):
        for key, value in kwargs.items():
            self.add_entry(key, value)

    def InsertBaseUserRegistryInformation(self,
                                        Version,
                                        UniqueUsername,
                                        AccountCreationTime,
                                        OptionalAccountCreationKey,
                                        LastRecalcDerivedSubscribedAppsTime,
                                        Cellid,
                                        AccountEmailAddress,
                                        AccountLastModifiedTime):
        
        self.add_entry(b"\x00\x00\x00\x00", Version)
        self.add_entry(b"\x01\x00\x00\x00", UniqueUsername)
        self.add_entry(b"\x02\x00\x00\x00", AccountCreationTime)
        self.add_entry(b"\x03\x00\x00\x00", OptionalAccountCreationKey)
        self.add_entry(b"\x09\x00\x00\x00", LastRecalcDerivedSubscribedAppsTime)
        self.add_entry(b"\x0a\x00\x00\x00", Cellid)
        self.add_entry(b"\x0b\x00\x00\x00", AccountEmailAddress)
        self.add_entry(b"\x0e\x00\x00\x00", AccountLastModifiedTime)

    # The following functions are used for creating the Beta 1 Steam User Registry

    def InsertAccountUserRecord(self, unique_user_name, steam_local_user_id, user_type, user_app_access_rights_record= '') :
        
        self.AccountUsersRecord(unique_user_name, {
                b"\x01\x00\x00\x00": steam_local_user_id,
                b"\x02\x00\x00\x00": user_type,
                b"\x03\x00\x00\x00": user_app_access_rights_record if user_app_access_rights_record != '' else {},
        })

    def add_account_subscription(self, subscription_id,subscribed_date, unsubscribed_date, subscription_status, status_change_flag, previous_subscription_state, optional_billing_status=0, user_ip= b'', user_country_code=b'', clientver= 'r2004'):
        
        subscription_entry = {
            b"\x01\x00\x00\x00": subscribed_date,
            b"\x02\x00\x00\x00": unsubscribed_date,
            b"\x03\x00\x00\x00": subscription_status,
            b"\x05\x00\x00\x00": status_change_flag,
            b"\x06\x00\x00\x00": previous_subscription_state
        }
        if clientver == 'r2007':
            additional_entries = {
                    b"\x07\x00\x00\x00": optional_billing_status,
                    b"\x08\x00\x00\x00": user_ip,
                    b"\x09\x00\x00\x00": user_country_code
            }
            subscription_entry.update(additional_entries)

        self.add_subdict(b"\x07\x00\x00\x00", subscription_id, subscription_entry)

    def add_account_subscriptions_billing_info(self,
                                            subscription_id,
                                            payment_receipt_type,
                                            card_type = b"",
                                            card_number = b"",
                                            card_holder_name = b"",
                                            billing_address1 = b"",
                                            billing_address2 = b"",
                                            billing_city = b"",
                                            billing_zip = b"",
                                            billing_state = b"",
                                            billing_country = b"",
                                            cc_approvalcode = b"",
                                            price_before_tax = b"",
                                            tax_amount = b"",
                                            trans_date = b"",
                                            trans_time = b"",
                                            astobbstxnid = b"",
                                            shipping_cost = b"\x00\x00\x00\x00"):

        # print(repr(payment_card_type))
        if payment_receipt_type == b'\x07' :
            payment_card_info_record = {
                    b"\x01\x00\x00\x00":payment_receipt_type,
                    b"\x02\x00\x00\x00":{},
            }
        elif payment_receipt_type == b'\x06' :
            payment_card_info_record = {
                    b"\x01\x00\x00\x00":payment_receipt_type,
                    b"\x02\x00\x00\x00":{
                            b"\x01\x00\x00\x00": card_number, # Re-using these variables so I do not need to create 2 extra parameters
                            b"\x02\x00\x00\x00": card_holder_name,
                },
            }
        elif payment_receipt_type == b'\x05' :
            payment_card_info_record = {
                    b"\x01\x00\x00\x00":payment_receipt_type,
                    b"\x02\x00\x00\x00":{
                            b"\x01\x00\x00\x00": card_type,
                            b"\x02\x00\x00\x00": card_number,  # Everything else is null terminated string
                            b"\x03\x00\x00\x00": card_holder_name,
                            b"\x07\x00\x00\x00": billing_address1,
                            b"\x08\x00\x00\x00": billing_address2,
                            b"\x09\x00\x00\x00": billing_city,
                            b"\x0a\x00\x00\x00": billing_zip,
                            b"\x0b\x00\x00\x00": billing_state,
                            b"\x0c\x00\x00\x00": billing_country,
                            b"\x0d\x00\x00\x00": cc_approvalcode,
                            b"\x0e\x00\x00\x00": price_before_tax,
                            b"\x0f\x00\x00\x00": tax_amount,
                            b"\x10\x00\x00\x00": trans_date,
                            b"\x11\x00\x00\x00": trans_time,
                            b"\x12\x00\x00\x00": astobbstxnid,
                            b"\x13\x00\x00\x00": shipping_cost
                },
            }

        else :
            log.error(f"Error!!! add_account_subscriptions_billing_info() Incorrect Payment Card TypeID: {payment_receipt_type}")
        self.add_subdict(b"\x0f\x00\x00\x00", subscription_id, payment_card_info_record)

    def build(self) :
        self.add_entry(b'\x0c\x00\x00\x00', b'\x00\x00')
        return self.registry