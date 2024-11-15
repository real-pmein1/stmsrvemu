import glob
import importlib
import os
import datetime
import shutil
import logging
import sys
import importlib.util

from sqlalchemy import create_engine, Table, MetaData, func
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm

import utilities.time
from config import get_config as read_config

import utils

log = logging.getLogger('USERMIGRATE')

class UserRegistryProcessor:
    def __init__(self):
        self.config = read_config()
        self.engine = self.create_db_engine()
        self.metadata = MetaData()
        self.metadata.bind = self.engine  # Bind the engine to the metadata here
        self.Session = sessionmaker(bind=self.engine)

    def create_db_engine(self):
        db_host = self.config['database_host']
        db_port = self.config['database_port']
        db_user = self.config['database_username']
        db_password = self.config['database_password']
        db_name = self.config['database']
        return create_engine(f'mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}')


    def process_user_registry(self, user_registry):
        session = self.Session()
        # Correct the use of autoload argument
        UserRegistry = Table('userregistry', self.metadata, autoload_with = self.engine)

        # Calculate next UniqueID for UserRegistry
        next_unique_id = self.get_next_unique_id(UserRegistry, session)

        # Process UserRegistry data
        username = self.convert_string(self.get_value(user_registry, '\x01\x00\x00\x00'))
        new_user_data = {
                'UniqueID':                           next_unique_id,
                'UniqueUserName':                     username,
                'AccountCreationTime':                self.convert_time(self.get_value(user_registry, '\x02\x00\x00\x00')),
                'LastRecalcDerivedSubscribedAppsTime':self.convert_time(self.get_value(user_registry, '\x09\x00\x00\x00')),
                'AccountLastModifiedTime':            self.convert_time(self.get_value(user_registry, '\x0e\x00\x00\x00')),
                'Cellid':                             self.convert_to_decimal(self.get_value(user_registry, '\x0a\x00\x00\x00')),
                'AccountEmailAddress':                self.convert_string(self.get_value(user_registry, '\x0b\x00\x00\x00')),
                'UserType':                           self.convert_to_decimal(self.get_nested_value(user_registry, '\x06\x00\x00\x00', username, '\x02\x00\x00\x00')),
                'Banned':                             self.convert_to_decimal(self.get_value(user_registry, '\x0c\x00\x00\x00', 0)),
                'SaltedPassphraseDigest':             self.convert_to_hex(self.get_nested_value(user_registry, '\x05\x00\x00\x00', username, '\x01\x00\x00\x00')),
                'PassphraseSalt':                     self.convert_to_hex(self.get_nested_value(user_registry, '\x05\x00\x00\x00', username, '\x02\x00\x00\x00')),
                'PersonalQuestion':                   self.convert_string(self.get_nested_value(user_registry, '\x05\x00\x00\x00', username, '\x03\x00\x00\x00')),
                'SaltedAnswerToQuestionDigest':       self.convert_to_hex(self.get_nested_value(user_registry, '\x05\x00\x00\x00', username, '\x04\x00\x00\x00')),
                'AnswerToQuestionSalt':               self.convert_to_hex(self.get_nested_value(user_registry, '\x05\x00\x00\x00', username, '\x05\x00\x00\x00')),
                'email_verified': 0,

        }

        sub_dict = self.get_value(user_registry, '\x08\x00\x00\x00', {})
        if isinstance(sub_dict, dict):
            keys_as_strings = []
            for key in sub_dict.keys():
                if isinstance(key, bytes):
                    # Convert byte key to string using 'latin-1' encoding
                    key_str = key.decode('latin-1')
                else:
                    # If key is already a string, use it as is
                    key_str = key
                keys_as_strings.append(key_str)

            new_user_data['DerivedSubscribedAppsRecord'] = ', '.join(keys_as_strings)
            print(new_user_data['DerivedSubscribedAppsRecord'])
        else:
            pass

        # Insert new user data into UserRegistry
        session.execute(UserRegistry.insert(), new_user_data)

        account_subscriptions_record_data = self.get_value(user_registry, '\x07\x00\x00\x00', {})
        account_subscriptions_billing_info_data = self.get_value(user_registry, '\x0f\x00\x00\x00', {})

        self.process_account_subscriptions_record(account_subscriptions_record_data, next_unique_id, session)
        self.process_account_subscriptions_billing_info_record(account_subscriptions_billing_info_data, next_unique_id, session)

        session.commit()
        session.close()

    def process_account_subscriptions_record(self, subscriptions, user_id, session):
        AccountSubscriptionsRecord = Table('accountsubscriptionsrecord', self.metadata, autoload_with=self.engine)
        for sub_id, sub_data in subscriptions.items():
            new_subscription_data = {
                    'UniqueID':self.get_next_unique_id(AccountSubscriptionsRecord, session),
                    'UserRegistry_UniqueID':user_id, 'SubscriptionID':self.convert_to_decimal(sub_id),
                    'SubscribedDate':self.convert_time(self.get_value(sub_data, '\x01\x00\x00\x00')),
                    'UnsubscribedDate':self.get_future_date(100),
                    'SubscriptionStatus':self.convert_to_decimal(self.get_value(sub_data, '\x03\x00\x00\x00')),
                    'StatusChangeFlag':self.convert_to_decimal(self.get_value(sub_data, '\x05\x00\x00\x00')),
                    'PreviousSubscriptionState':self.convert_to_decimal(self.get_value(sub_data, '\x06\x00\x00\x00')),
                    'OptionalBillingStatus':self.convert_to_decimal(self.get_value(sub_data, '\x07\x00\x00\x00', '\x00')),
                    'UserIP':self.convert_string(self.get_value(sub_data, '\x08\x00\x00\x00', '')),
                    'UserCountryCode':self.convert_string(self.get_value(sub_data, '\x09\x00\x00\x00', ''))
            }
            session.execute(AccountSubscriptionsRecord.insert(), new_subscription_data)

    def process_account_subscriptions_billing_info_record(self, billing_info_data, user_id, session):
        if not billing_info_data:
            return
        AccountPrepurchasedInfoRecord = Table('accountprepurchasedinforecord', self.metadata, autoload_with=self.engine)
        AccountPaymentCardInfoRecord = Table('accountpaymentcardinforecord', self.metadata, autoload_with=self.engine)
        AccountSubscriptionBillingInfoRecord = Table('accountsubscriptionsbillinginforecord', self.metadata, autoload_with=self.engine)

        for billing_info_type_id, billing_info in billing_info_data.items():
            account_payment_card_info_record = int.from_bytes(self.get_value(billing_info, '\x01\x00\x00\x00', b'\x00'),'little')

            # Determine the record type and process accordingly
            if account_payment_card_info_record == 7:
                # Process type 7 billing info (no additional prepurchased info)
                payment_info_data = {
                        'UniqueID':self.get_next_unique_id(AccountSubscriptionBillingInfoRecord, session),
                        'UserRegistry_UniqueID':user_id,
                        'SubscriptionID':self.convert_to_decimal(billing_info_type_id),
                        'AccountPaymentType':account_payment_card_info_record
                }
                session.execute(AccountSubscriptionBillingInfoRecord.insert(), payment_info_data)

            elif account_payment_card_info_record == 6:
                # Process type 6 billing info
                payment_info_data = {
                        'UniqueID': self.get_next_unique_id(AccountSubscriptionBillingInfoRecord, session),
                        'UserRegistry_UniqueID': user_id,
                        'SubscriptionID':self.convert_to_decimal(billing_info_type_id),
                        'AccountPaymentType': account_payment_card_info_record
                }
                prepurchase_uniqueid = self.get_next_unique_id(AccountPrepurchasedInfoRecord, session)
                payment_info_data['AccountPrepurchasedInfoRecord_UniqueID'] = prepurchase_uniqueid

                session.execute(AccountSubscriptionBillingInfoRecord.insert(), payment_info_data)

                prepurchased_info = self.get_value(billing_info, '\x02\x00\x00\x00', {})
                type_of_proof_of_purchase = self.convert_string(self.get_value(prepurchased_info, '\x01\x00\x00\x00', ''))
                binary_proof_of_purchase_token = self.convert_string(self.get_value(prepurchased_info, '\x02\x00\x00\x00', ''))

                prepurchase_info_data = {
                        'UniqueID': prepurchase_uniqueid,
                        'UserRegistry_UniqueID':user_id,
                        'TypeOfProofOfPurchase': type_of_proof_of_purchase,
                        'BinaryProofOfPurchaseToken': binary_proof_of_purchase_token
                }
                session.execute(AccountPrepurchasedInfoRecord.insert(), prepurchase_info_data)

            elif account_payment_card_info_record == 5:
                # Process type 5 billing info
                payment_info_data = {
                        'UniqueID': self.get_next_unique_id(AccountSubscriptionBillingInfoRecord, session),
                        'UserRegistry_UniqueID': user_id,
                        'SubscriptionID': self.convert_to_decimal(billing_info_type_id),
                        'AccountPaymentType': account_payment_card_info_record
                }
                paymentcard_uniqueid = self.get_next_unique_id(AccountPaymentCardInfoRecord, session)
                payment_info_data['AccountPaymentCardReceiptRecord_UniqueID'] = paymentcard_uniqueid

                session.execute(AccountSubscriptionBillingInfoRecord.insert(), payment_info_data)

                card_info =  self.get_value(billing_info, '\x02\x00\x00\x00', {})
                payment_card_type = int.from_bytes(self.get_value(card_info, '\x01\x00\x00\x00', '2'), 'little')
                card_number = self.get_value(card_info, '\x02\x00\x00\x00', '1111').decode('latin-1').rstrip('\x00')
                card_holder_name = self.get_value(card_info, '\x03\x00\x00\x00', 'name').decode('latin-1').rstrip('\x00')
                card_exp_year = self.get_value(card_info, '\x04\x00\x00\x00', '').decode('latin-1').rstrip('\x00')
                card_exp_month = self.get_value(card_info, '\x05\x00\x00\x00', '').decode('latin-1').rstrip('\x00')
                card_cvv2 = self.get_value(card_info,'\x06\x00\x00\x00', '').decode('latin-1').rstrip('\x00')
                billing_address1 = self.get_value(card_info,'\x07\x00\x00\x00', 'address').decode('latin-1').rstrip('\x00')
                billing_address2 = self.get_value(card_info,'\x08\x00\x00\x00', '').decode('latin-1').rstrip('\x00')
                billing_city = self.get_value(card_info,'\x09\x00\x00\x00', 'Los Angeles').decode('latin-1').rstrip('\x00')
                billing_zip = self.get_value(card_info,'\x0a\x00\x00\x00', '12345').decode('latin-1').rstrip('\x00')
                billing_state = self.get_value(card_info,'\x0b\x00\x00\x00', 'CA').decode('latin-1').rstrip('\x00')
                billing_country = self.get_value(card_info,'\x0c\x00\x00\x00', 'United States').decode('latin-1').rstrip('\x00')
                CCApprovalCode = self.get_value(card_info,'\x0d\x00\x00\x00', '725863').decode('latin-1').rstrip('\x00')
                PriceBeforeTax = int.from_bytes(self.get_value(card_info,'\x0e\x00\x00\x00', b'\x00\x00\x00\x00'), 'little')
                tax_amount = int.from_bytes(self.get_value(card_info,'\x0f\x00\x00\x00', b'\x00\x00\x00\x00'), 'little')
                transDate = self.get_value(card_info,'\x10\x00\x00\x00', '22/01/2024').decode('latin-1').rstrip('\x00')
                transTime = self.get_value(card_info,'\x11\x00\x00\x00', '08:33:34').decode('latin-1').rstrip('\x00')
                AStoBBSTxnId = self.get_value(card_info,'\x12\x00\x00\x00', '32549943').decode('latin-1').rstrip('\x00')

                # Insert into AccountPaymentCardInfoRecord
                new_card_info_data = {
                        'UniqueID': paymentcard_uniqueid,
                        'UserRegistry_UniqueID': user_id,
                        'PaymentCardType': payment_card_type,
                        'CardNumber': card_number,
                        'CardHolderName': card_holder_name,
                        'CardExpYear': card_exp_year,
                        'CardExpMonth': card_exp_month,
                        'CardCVV2': card_cvv2,
                        'BillingAddress1': billing_address1,
                        'BillingAddress2': billing_address2,
                        'BillingCity': billing_city,
                        'BillingZip': billing_zip,
                        'BillingState': billing_state,
                        'BillingCountry': billing_country,
                        'CCApprovalCode': CCApprovalCode,
                        'PriceBeforeTax': PriceBeforeTax,
                        'TaxAmount': tax_amount,
                        'TransDate': transDate,
                        'TransTime': transTime,
                        'AStoBBSTxnId': AStoBBSTxnId,
                }
                session.execute(AccountPaymentCardInfoRecord.insert(),
                                new_card_info_data)

            # Commit changes to the database
            session.commit()

    def get_value(self, dictionary, key, default=None):
        # Try to get the value using the key as a string
        value = dictionary.get(key, default)

        # If the value is not found, try with the key as bytes
        if value is None and not isinstance(key, bytes):
            byte_key = key.encode('latin-1')
            value = dictionary.get(byte_key, default)

        # Return value as bytes if it's a string, or the value itself if it's not
        if value is not None:
            if isinstance(value, dict):
                # Process nested dictionary recursively
                return {self.get_key(k): self.get_value(value, k, default) for k in value}
            elif isinstance(value, str):
                return value.encode('latin-1')
            else:
                return value

        return None

    def get_key(self, key):
        # Convert key to string if it's bytes
        if isinstance(key, bytes):
            return key.decode('latin-1')
        return key

    def get_nested_value(self, dictionary, outer_key, inner_key, sub_key, default = None):
        outer_dict = self.get_value(dictionary, outer_key, default)
        if isinstance(outer_dict, dict):
            inner_dict = self.get_value(outer_dict, inner_key, default)
            if isinstance(inner_dict, dict):
                return self.get_value(inner_dict, sub_key, default)
        return None

    def convert_string(self, value):
        if value is not None:
            if isinstance(value, bytes):
                # Decode using 'latin-1' and strip null bytes
                return value.decode('latin-1').rstrip('\x00')
            elif isinstance(value, str):
                # Python 2.7, treat as raw bytes
                return value.rstrip('\x00')
        log.error(f"[SQLMigrator] Error While Converting Dictionary Value To String: {value}")
        return None

    def convert_to_bytes(self, value):
        # Convert value to bytes if it's not already in bytes
        if isinstance(value, bytes):
            return value
        elif isinstance(value, str):
            return value.encode('latin-1')
        elif isinstance(value, (int, float)):
            # Convert numbers to bytes (you can adjust the format as needed)
            return str(value).encode('latin-1')
        # Add more type conversions here if needed
        return bytes(value)

    def convert_time(self, time_bytes, years = 0):
        if time_bytes is not None:
            if isinstance(time_bytes, str):  # Python 2.7 string (interpreted as bytes)
                time_bytes = time_bytes.encode('latin-1')
            if time_bytes == b'\xe0' * 7 + b'\x00':
                return datetime.datetime.now() + datetime.timedelta(days = 365 * years)
            # Additional logic for converting byte sequence to datetime
            # Example: assuming time_bytes is a UNIX timestamp
            datetime_value = utilities.time.steamtime_to_datetime(time_bytes)
            return datetime_value
        return None

    def convert_to_decimal(self, value):
        if value is not None:
            if isinstance(value, str):  # Python 2.7 string (interpreted as bytes)
                value = value.encode('latin-1')
            return int.from_bytes(value, 'little')
        return None

    def convert_to_hex(self, value):
        if value is not None:
            if isinstance(value, str):  # Python 2.7 string (interpreted as bytes)
                value = value.encode('latin-1')
            return value.hex()
        return None

    def get_future_date(self, years = 100):
        # Get the current datetime and add the specified number of years
        future_date = datetime.datetime.now() + datetime.timedelta(days = 365 * years)
        # Format the future_date to the desired string format
        formatted_datetime = future_date.strftime('%m/%d/%Y %H:%M:%S')
        return formatted_datetime

    def get_next_unique_id(self, table, session):
        max_id = session.query(func.max(table.c.UniqueID)).scalar()
        return max_id + 1 if max_id is not None else 1

    def delete_unwanted_files_and_folders(self, folder_path):
        # Walk through the folder
        for root, dirs, files in os.walk(folder_path, topdown = False):
            # Remove __pycache__ directories
            for _dir in dirs:
                if _dir == '__pycache__':
                    shutil.rmtree(os.path.join(root, _dir))
                    log.info(f"Deleted directory: {os.path.join(root, _dir)}")

            # Remove .pyc and .pyo files
            for file in files:
                if file.endswith(('.pyc', '.pyo')):
                    os.remove(os.path.join(root, file))
                    log.info(f"Deleted file: {os.path.join(root, file)}")


    def archive_folder(self, folder_path):
        self.delete_unwanted_files_and_folders(folder_path)
        # Create an archive of the folder
        shutil.make_archive('original_users', 'zip', folder_path)
        log.info(f"The User Folder Has Been Successfully Converted To SQL And Archived To the Zip File: /files/users.zip")

    def process_files(self):
        users_folder = 'files/users/'
        py_files = glob.glob(os.path.join(users_folder, '*.py'))
        log.info('--- Starting User PY File to SQL DB Conversion ---')
        # Initialize the progress bar with the total number of files to process
        for py_file in tqdm(py_files, desc = 'Processing .py files', unit = 'file', file=sys.stdout):
            spec = importlib.util.spec_from_file_location("user_registry_module", py_file)
            user_registry_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(user_registry_module)

            # Assuming each file has a 'user_registry' dictionary
            if hasattr(user_registry_module, 'user_registry'):
                self.process_user_registry(user_registry_module.user_registry)

        # Archive the folder
        self.archive_folder(users_folder)

        # Remove the folder
        shutil.rmtree(users_folder)
        log.info('--- User PY File to SQL DB Conversion Complete ---')

def convert_userpy():
    processor = UserRegistryProcessor()
    processor.process_files()

#if __name__ == "__main__":
#    processor = UserRegistryProcessor()
#    processor.process_files()
def check_and_process_user_data():
    zip_path = "files/original_users.zip"
    user_dir_path = "files/users/"

    # Check if the zip file exists
    if os.path.exists(zip_path):
        print(f"{zip_path} already exists. No further action taken.")
        return
    # Check if the user directory exists
    elif os.path.exists(user_dir_path):
        # Check if the directory is empty
        if not os.listdir(user_dir_path):
            print(f"{user_dir_path} is empty. Deleting the folder.")
            shutil.rmtree(user_dir_path)  # Delete the empty folder
            return
        else:
            print(f"{user_dir_path} exists, is not empty, and {zip_path} does not exist. Calling userpyconverter().")
            convert_userpy()  # We convert ALL user py files to SQL database
    else:
        log.debug(f"No old users found")
        return