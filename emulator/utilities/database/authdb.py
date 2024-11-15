import datetime
import logging
import pprint
import random
import string
import time

from sqlalchemy.exc import NoResultFound, SQLAlchemyError

import globalvars
import utilities.time
from utilities.database import base_dbdriver, dbengine
from utilities.database.base_dbdriver import AccountSubscriptionsRecord
from utilities.database.userregistry import UserRegistry, UserRegistryBuilder
from utils import get_derived_appids

log = logging.getLogger('AUTHDB')


class auth_dbdriver:

    def __init__(self, config):

        # Assuming you have a db_driver instance created and connected
        while globalvars.mariadb_initialized != True:
            continue
        self.db_driver = dbengine.create_database_driver()
        self.db_driver.connect()

        self.user_registry_table = base_dbdriver.UserRegistry.__table__
        self.subscriptionsrecord_table = base_dbdriver.AccountSubscriptionsRecord.__table__
        self.subscriptionsbillinginforecord_table = base_dbdriver.AccountSubscriptionsBillingInfoRecord.__table__
        self.prepurchasedinforecord_table = base_dbdriver.AccountPrepurchasedInfoRecord.__table__
        self.paymentcardinforecord_table = base_dbdriver.AccountPaymentCardInfoRecord.__table__
        # Create a session for ORM operations
        self.session = self.db_driver.get_session()

    def check_username_exists(self, username):
        user_registry_data = self.db_driver.select_data(base_dbdriver.UserRegistry,
                                                        base_dbdriver.UserRegistry.UniqueUserName == username)
        if len(user_registry_data):
            return True
        else:
            return False

    def check_email_exists(self, email):
        user_registry_data = self.db_driver.select_data(base_dbdriver.UserRegistry,
                                                        base_dbdriver.UserRegistry.AccountEmailAddress == email)
        if len(user_registry_data):
            return True
        else:
            return False

    def check_userpw(self, username):
        user_registry_data = self.db_driver.select_data(base_dbdriver.UserRegistry,
                                                        self.user_registry_table.UniqueUserName == username)
        if len(user_registry_data):
            return user_registry_data[0].SaltedPassphraseDigest
        else:
            return 0

    def check_user_banned(self, username):
        user_record = self.db_driver.select_data(base_dbdriver.UserRegistry,
                                                 base_dbdriver.UserRegistry.UniqueUserName == username)
        return True if user_record[0].Banned == 1 else False
    def check_email_verified(self, username):
        user_record = self.db_driver.select_data(base_dbdriver.UserRegistry,
                                                 base_dbdriver.UserRegistry.UniqueUserName == username)
        return True if user_record[0].email_verified == 1 else False

    def get_uniqueuserid(self, username):
        user_registry_data = self.db_driver.select_data(base_dbdriver.UserRegistry,
                                                        base_dbdriver.UserRegistry.UniqueUserName == username)
        if len(user_registry_data) > 0:
            return user_registry_data[0].UniqueID
        else:
            return False

    def get_questionsalt(self, username):
        user_registry_data = self.db_driver.select_data(base_dbdriver.UserRegistry,
                                                        base_dbdriver.UserRegistry.UniqueUserName == username)
        if len(user_registry_data) > 0:
            return bytes.fromhex(user_registry_data[0].AnswerToQuestionSalt)
        else:
            return False

    def get_questionsalt_by_email(self, email):
        user_registry_data = self.db_driver.select_data(base_dbdriver.UserRegistry,
                                                        base_dbdriver.UserRegistry.AccountEmailAddress == email)
        if len(user_registry_data) > 0:
            return bytes.fromhex(user_registry_data[0].AnswerToQuestionSalt)
        else:
            return False

    def get_question_info(self, username):
        user_registry_data = self.db_driver.select_data(base_dbdriver.UserRegistry,
                                                        base_dbdriver.UserRegistry.UniqueUserName == username)
        if len(user_registry_data) > 0:
            return bytes.fromhex(user_registry_data[0].AnswerToQuestionSalt),user_registry_data[0].SaltedAnswerToQuestionDigest
        else:
            return False

    def get_userpass_stuff(self, username):
        user_registry_data = self.db_driver.select_data(base_dbdriver.UserRegistry,
                                                        base_dbdriver.UserRegistry.UniqueUserName == username)
        if len(user_registry_data) > 0:
            return bytes.fromhex(user_registry_data[0].SaltedPassphraseDigest), bytes.fromhex(user_registry_data[0].PassphraseSalt)
        else:
            return False

    def get_user_email(self, username):
        user_registry_data = self.db_driver.select_data(base_dbdriver.UserRegistry,
                                                        base_dbdriver.UserRegistry.UniqueUserName == username)
        if len(user_registry_data) > 0:
            return user_registry_data[0].AccountEmailAddress
        else:
            return False

    def check_validationcode(self, username, validationcode):
        user_registry_data = self.db_driver.select_data(base_dbdriver.UserRegistry,
                                                        base_dbdriver.UserRegistry.UniqueUserName == username)
        if len(user_registry_data) > 0:
            if not utilities.time.is_datetime_older_than_15_minutes(user_registry_data[0].info_change_validation_time) \
                    and user_registry_data[0].info_change_validation_code == validationcode:
                return True
        else:
            log.warning(f"[check_validationcode] User not found: {username}")
        return False

    def get_username_by_email(self, emailaddress):
        user_registry_data = self.db_driver.select_data(base_dbdriver.UserRegistry,
                                                        base_dbdriver.UserRegistry.AccountEmailAddress == emailaddress)
        if len(user_registry_data) > 0:
            return user_registry_data[0].UniqueUserName
        else:
            return False

    def check_resetcdkey(self, cdkey):
        checkkey_dbdata = self.db_driver.select_data(base_dbdriver.AccountPrepurchasedInfoRecord,
                                                     base_dbdriver.AccountPrepurchasedInfoRecord.BinaryProofOfPurchaseToken == cdkey)


        if len(checkkey_dbdata):
            userid = checkkey_dbdata[0].UserRegistry_UniqueID
            user_registry_data = self.db_driver.select_data(base_dbdriver.UserRegistry,
                                                            base_dbdriver.UserRegistry.UniqueID == userid)
            if len(user_registry_data):
                username = user_registry_data[0].UniqueUserName
                #emailaddress = user_registry_data[0].AccountEmailAddress
            else:
                return -2
        else:
            return -1

        return username #, emailaddress

    def get_numaccts_with_email(self, email):
        result = self.db_driver.select_data(base_dbdriver.UserRegistry,
                                            base_dbdriver.UserRegistry.AccountEmailAddress == email)
        return len(result)

    def check_resetemail(self, email):
        user_registry_data = self.db_driver.select_data(base_dbdriver.UserRegistry, base_dbdriver.UserRegistry.AccountEmailAddress == email)
        return bool(user_registry_data)

    def create_user(self, username, password_salt, password_digest, question, answer_salt, answer_digest, email_address, pkt_version):

        uniqueid = self.db_driver.get_next_available_id(self.user_registry_table)
        accountcreationtime = utilities.time.get_current_datetime()

        # Insert the user into user registry table
        new_user = {
                'UniqueID': uniqueid,
                'UniqueUserName': username,
                'AccountCreationTime': accountcreationtime,
                'UserType': 1,
                'SaltedAnswerToQuestionDigest':       answer_digest,
                'PassphraseSalt':                     password_salt,
                'AnswerToQuestionSalt':               answer_salt,
                'PersonalQuestion':                   question,
                'SaltedPassphraseDigest':             password_digest,
                'LastRecalcDerivedSubscribedAppsTime':accountcreationtime,
                'CellID':                             globalvars.cellid,
                'AccountEmailAddress':                email_address,
                'Banned':                             0,
                'AccountLastModifiedTime':            accountcreationtime,
                'DerivedSubscribedAppsRecord':        get_derived_appids(),
                'email_verified':                     0,
                'email_verificationcode': "",
        }
        try:
            self.db_driver.insert_data(base_dbdriver.UserRegistry, new_user)
        except Exception as e:
            # Handle the exception here (e.g., print an error message)
            log.error(f"[create_user] User {username}  Error occurred while inserting new user into userregistry: {e}")
            return -1
            # Insert entry into friends_registry table for the new user

        new_friend_entry = {
                'accountID':        uniqueid,
                'nickname':         username,  # Assuming nickname is the same as the username
                'status':           0,  # Default status, adjust if there's a specific default
                'primary_clanID':   None,
                'primary_groupID':  None,
                'currently_playing':None,
                'last_login':       None,
                'last_logoff':      None
        }

        try:
            self.db_driver.insert_data(base_dbdriver.FriendsRegistry, new_friend_entry)
        except Exception as e:
            log.error(f"[create_user] User {username} Error occurred while inserting into friends_registry: {e}")
            return -1

        # Insert entry into Community_Profile with specified defaults
        new_profile_entry = {
                'friendRegistryID':   uniqueid,
                'profile_visibility': 0,
                'comment_permissions':1,
                'welcome':            False
        }

        try:
            self.db_driver.insert_data(base_dbdriver.CommunityRegistry, new_profile_entry)
        except Exception as e:
            log.error(f"[create_user] User {username} Error occurred while inserting into community_profile: {e}")
            return -1

        if pkt_version not in ['b2003', 'r2003']:
            # Add default Subscription 0
            self.insert_sub_0(uniqueid)

        log.info(f"[create_user] New User Created & Added To Database: {username}")
        return 1

    def insert_sub_0(self, uniqueid):
        # Add default Subscription 0
        next_unique_sub_id = self.db_driver.get_next_available_id(self.subscriptionsrecord_table)
        current_datetime = utilities.time.get_current_datetime()
        data = {'UserRegistry_UniqueID':    uniqueid,
                'SubscriptionID':           0,
                'SubscribedDate':           current_datetime,
                'UnsubscribedDate':         utilities.time.add_100yrs(current_datetime),
                'SubscriptionStatus':       1,
                'StatusChangeFlag':         0,
                'PreviousSubscriptionState':31
        }
        try:
            self.db_driver.insert_data(base_dbdriver.AccountSubscriptionsRecord, data)
        except Exception as e:
            # Handle the exception here (e.g., print an error message)
            log.error(f"[create_user] Userid {uniqueid} Error occurred while inserting into accountsubscriptionsrecord: {e}", )
            return -1
        # Add the billing info record for default subscription 0
        next_unique_billing_id = self.db_driver.get_next_available_id(self.subscriptionsbillinginforecord_table)

        data = {
                'UserRegistry_UniqueID': uniqueid,
                'SubscriptionID': 0,  # subbillinginfo.SubscriptionID,
                'AccountPaymentType': 7,
        }
        try:
            self.db_driver.insert_data(base_dbdriver.AccountSubscriptionsBillingInfoRecord, data)
        except Exception as e:
            # Handle the exception here (e.g., print an error message)
            log.error(f"[create_user] Userid {uniqueid} Error occurred while inserting into accountsubscriptionsbillinginforecord: {e}")
            return -1

    def insert_subscription(self, username, subid, paymenttype, userip, tuple_paymentrecord = None):
        user_uniqueid = self.get_uniqueuserid(username)

        if user_uniqueid == 0:
            log.error(f"[insert_sub] User {username} Does Not Exist!")
            return False

        # Check if a subscription entry with the same UserRegistry_UniqueID and SubscriptionID already exists
        existing_subscriptions = self.db_driver.select_data(base_dbdriver.AccountSubscriptionsRecord,
                                                            (base_dbdriver.AccountSubscriptionsRecord.UserRegistry_UniqueID == user_uniqueid) &
                                                            (base_dbdriver.AccountSubscriptionsRecord.SubscriptionID == subid))

        if existing_subscriptions:
            log.warning(f"[insert_sub] Subid: {subid} Already Exists For User: {username}")
            return True

        current_time = utilities.time.get_current_datetime()
        next_unique_sub_id = self.db_driver.get_next_available_id(self.subscriptionsrecord_table)

        if subid == 0:
            subscription_status = 1
            status_change_flag = 1
            previous_subscription_state = 0
        else:
            subscription_status = 0
            status_change_flag = 0
            previous_subscription_state = 31

        data = {
                'UserRegistry_UniqueID':    user_uniqueid,
                'SubscriptionID':           subid,
                'SubscribedDate':           current_time,
                'UnsubscribedDate':         utilities.time.add_100yrs(current_time),
                'SubscriptionStatus':       subscription_status,
                'StatusChangeFlag':         status_change_flag,
                'PreviousSubscriptionState':previous_subscription_state,
                'UserIP':                   userip
        }

        max_retries = 3
        for attempt in range(max_retries):  # NOTE: This retry stuff is left-over code from when we used an SQLITE DB
            try:
                self.db_driver.insert_data(base_dbdriver.AccountSubscriptionsRecord, data)
                break
            except Exception as e:
                log.error(f"[insert_sub] Attempt {attempt + 1}: Error occurred while inserting subscription into accountsubscriptionsrecord: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)  # Wait a bit before retrying
                    continue
                else:
                    return False  # Failed after retries

        if paymenttype == 4:
            log.error(f"[insert_sub] User {username} Payment type 4 (external billing) Not supported")
            return False

        elif paymenttype == 5:
            next_unique_paymentcard_recordID = self.db_driver.get_next_available_id(self.paymentcardinforecord_table)
            (PaymentCardType, CardNumber, CardHolderName, CardExpYear, CardExpMonth, CardCVV2, BillingAddress1, BillingAddress2, BillingCity, BillinZip, BillingState, BillingCountry, BillingPhone, BillinEmailAddress, PriceBeforeTax, TaxAmount, CCApprovalCode, TransDate, TransTime, AStoBBSTxnId) = tuple_paymentrecord

            data = {
                    'UserRegistry_UniqueID':user_uniqueid,
                    'PaymentCardType':PaymentCardType,
                    'CardNumber':CardNumber,
                    'CardHolderName':CardHolderName,
                    'CardExpYear':int(CardExpYear),
                    'CardExpMonth':int(CardExpMonth),
                    'CardCVV2':int(CardCVV2),
                    'BillingAddress1':BillingAddress1,
                    'BillingAddress2':BillingAddress2,
                    'BillingCity':BillingCity,
                    'BillingZip':BillinZip,
                    'BillingState':BillingState,
                    'BillingCountry':BillingCountry,
                    'BillingPhone':BillingPhone,
                    'BillinEmailAddress':BillinEmailAddress,
                    'PriceBeforeTax':PriceBeforeTax,
                    'TaxAmount':TaxAmount,
                    'CCApprovalCode':CCApprovalCode,
                    'TransDate':TransDate,
                    'TransTime':TransTime,
                    'AStoBBSTxnId':AStoBBSTxnId,
                    'SubsId':subid,
                    'AcctName':username
            }
            for attempt in range(max_retries):  # NOTE: This retry stuff is left-over code from when we used an SQLITE DB
                try:
                    self.db_driver.insert_data(base_dbdriver.AccountPaymentCardInfoRecord, data)
                    break
                except Exception as e:
                    log.error(f"[Insert Sub] Error occurred while inserting into AccountPaymentType: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(1)  # Wait a bit before retrying
                        continue
                    else:
                        return False  # Failed after retries

        elif paymenttype == 6:
            next_unique_prepurchase_id = self.db_driver.get_next_available_id(self.prepurchasedinforecord_table)
            (TypeOfProofOfPurchase, BinaryProofOfPurchaseToken) = tuple_paymentrecord
            if BinaryProofOfPurchaseToken == '':
                BinaryProofOfPurchaseToken = '4610731021040'

            data = {
                    'UserRegistry_UniqueID':user_uniqueid,
                    'TypeOfProofOfPurchase':TypeOfProofOfPurchase,
                    'BinaryProofOfPurchaseToken':BinaryProofOfPurchaseToken,
                    'SubsId':subid
            }

            for attempt in range(max_retries):
                try:
                    self.db_driver.insert_data(base_dbdriver.AccountPrepurchasedInfoRecord, data)
                    break
                except Exception as e:
                    log.error("[insert_sub] Error occurred while inserting into accountprepurchasedinforecord:", e)
                    if attempt < max_retries - 1:
                        time.sleep(1)  # Wait a bit before retrying
                        continue
                    else:
                        return False  # Failed after retries
        else:
            if paymenttype != 7:
                log.error(f"[insert_sub] User {username} Has An Invalid Payment Type ID! PaymentTypeID: {str(paymenttype)}")
                return False

        data = {
                'UserRegistry_UniqueID': user_uniqueid,
                'SubscriptionID': int(subid),
                'AccountPaymentType': int(paymenttype)
        }

        if paymenttype == 5:
            data['AccountPaymentCardReceiptRecord_UniqueID'] = next_unique_paymentcard_recordID

        elif paymenttype == 6:
            data['AccountPrepurchasedInfoRecord_UniqueID'] = next_unique_prepurchase_id

        for attempt in range(max_retries):  # NOTE: This retry stuff is left-over code from when we used an SQLITE DB
            try:
                self.db_driver.insert_data(base_dbdriver.AccountSubscriptionsBillingInfoRecord, data)
                break
            except Exception as e:
                log.error(f"[insert_sub] Error occurred while inserting into accountsubscriptionsbillinginforecord: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)  # Wait a bit before retrying
                    continue
                else:
                    return False  # Failed after retries

        log.info(f"[insert_sub] Successfully inserted new Subscription To Database, Subscription ID: {str(subid)} Username: {username}")

    def get_userregistry_dict(self, username, clientver, ipaddress):
        user_registry = UserRegistry(self)
        user_registry_builder = UserRegistryBuilder()
        userrecord_dbdata_rows = self.db_driver.select_data(base_dbdriver.UserRegistry, base_dbdriver.UserRegistry.UniqueUserName == username)

        if not userrecord_dbdata_rows:
            log.error(f"[get_dict] User not found: {username}")
            return 0

        if len(userrecord_dbdata_rows) > 1:
            pprint.pprint(userrecord_dbdata_rows)
            log.error(f"[get_dict] More than 1 row returned when loading user from database! user: {username}")
            return 2

        userrecord_dbdata = userrecord_dbdata_rows[0]
        # Update IP address in the database
        # self.db_driver.update_data(base_dbdriver.UserRegistry,
        #                           base_dbdriver.UserRegistry.UniqueUserName == username,
        #                           {'ipaddress': ipaddress})

        # Building the user registry
        user_registry.build_user_registry(user_registry_builder, userrecord_dbdata)

        if clientver not in ["b2003", "r2003"]:
            user_registry.process_subscriptions_billing_info(user_registry_builder, userrecord_dbdata.UniqueID)

        user_registry.process_subscription_records(user_registry_builder, userrecord_dbdata.UniqueID, clientver)

        return user_registry_builder.build()

    def update_subscription_status_flags(self, username):
        try:
            # Get the 'UniqueID' for the given 'UniqueUserName'
            userrecord_dbdata = self.db_driver.select_data(
                    base_dbdriver.UserRegistry,
                    base_dbdriver.UserRegistry.UniqueUserName == username
            )

            if len(userrecord_dbdata) == 0:
                log.error(f"[update_sub] User {username} not found!")
                return False

            unique_id = userrecord_dbdata[0].UniqueID

            # Prepare the updates for SubscriptionStatus = 1
            where_clause_status_1 = (
                    (base_dbdriver.AccountSubscriptionsRecord.UserRegistry_UniqueID == unique_id) &
                    (base_dbdriver.AccountSubscriptionsRecord.SubscriptionStatus == 1)
            )
            new_values_status_1 = {
                    'StatusChangeFlag':0
            }

            # Update records where SubscriptionStatus = 1
            result_1 = self.db_driver.update_data(
                    base_dbdriver.AccountSubscriptionsRecord,
                    where_clause_status_1,
                    new_values_status_1
            )

            # Prepare the updates for SubscriptionStatus = 0
            where_clause_status_0 = (
                    (base_dbdriver.AccountSubscriptionsRecord.UserRegistry_UniqueID == unique_id) &
                    (base_dbdriver.AccountSubscriptionsRecord.SubscriptionStatus == 0)
            )
            new_values_status_0 = {
                    'SubscriptionStatus':       1,
                    'StatusChangeFlag':         1,
                    'PreviousSubscriptionState':0
            }

            # Update records where SubscriptionStatus = 0
            result_0 = self.db_driver.update_data(
                    base_dbdriver.AccountSubscriptionsRecord,
                    where_clause_status_0,
                    new_values_status_0
            )

            if result_0 or result_1:
                log.info(f"[update_sub] Successfully updated subscription records for user {username}")
                return True
            else:
                log.error(f"[update_sub] Update failed for user {username}")
                return False

        except Exception as e:
            log.error(f"[update_sub] Error updating subscription records: {e}")
            return False

    def unsubscribe(self, username, subid):
        try:
            # Get the 'UniqueID' for the given 'username'
            userrecord_dbdata = self.db_driver.select_data(base_dbdriver.UserRegistry, base_dbdriver.UserRegistry.UniqueUserName == username)

            if len(userrecord_dbdata) == 0:
                log.error(f"[unsubscribe] User {username} not found.")
                return False

            unique_id = userrecord_dbdata[0].UniqueID

            # Define where_clause to match the user's UniqueID and the SubscriptionID
            where_clause = ((base_dbdriver.AccountSubscriptionsRecord.UserRegistry_UniqueID == unique_id) &
                            (base_dbdriver.AccountSubscriptionsRecord.SubscriptionID == subid))

            # Use a method to delete the specified subscription record
            self.db_driver.remove_data(base_dbdriver.AccountSubscriptionsRecord, where_clause)

            # Define where_clause to match the user's UniqueID and the SubscriptionID
            where_clause = ((base_dbdriver.AccountSubscriptionsBillingInfoRecord.UserRegistry_UniqueID == unique_id) &
                            (base_dbdriver.AccountSubscriptionsBillingInfoRecord.SubscriptionID == subid))

            # Use a method to delete the specified subscription record
            self.db_driver.remove_data(base_dbdriver.AccountSubscriptionsBillingInfoRecord, where_clause)
            return True
        except Exception as e:
            log.error(f"[unsubscribe] {username} Error removing user subscription: {e}")
            return False

    def insert_email_verification(self, username):
        user_record = self.db_driver.select_data(base_dbdriver.UserRegistry,
                                                 base_dbdriver.UserRegistry.UniqueUserName == username)
        if len(user_record):
            # Generate a 6 alphanumeric random code
            verification_code = ''.join(random.choices(string.ascii_letters + string.digits,
                                                       k = 6))

            # Define the where clause for the update
            where_clause = base_dbdriver.UserRegistry.UniqueUserName == username

            # Update the user record with the verification code
            self.db_driver.update_data(base_dbdriver.UserRegistry,
                                       where_clause,
                                       {
                                               'email_verificationcode': verification_code
                                       })

            # Return the verification code and AccountEmailAddress
            return {
                    'verification_code': verification_code,
                    'email':user_record[0].AccountEmailAddress,
            }

        return None

    def insert_reset_password_validation(self, username):
        user_record = self.db_driver.select_data(base_dbdriver.UserRegistry,
                                                 base_dbdriver.UserRegistry.UniqueUserName == username)
        if len(user_record):
            current_time = utilities.time.get_current_datetime()
            # Generate a 6 alphanumeric random code
            verification_code = ''.join(random.choices(string.ascii_letters + string.digits,
                                                       k = 6))

            # Define the where clause for the update
            where_clause = base_dbdriver.UserRegistry.UniqueUserName == username

            # Update the user record with the verification code
            self.db_driver.update_data(base_dbdriver.UserRegistry,
                                       where_clause,
                                       {
                                               'info_change_validation_code': verification_code,
                                               'info_change_validation_time': current_time
                                       })

            # Return the validation code, AccountEmailAddress and question
            return {
                    'verification_code': verification_code,
                    'email': user_record[0].AccountEmailAddress,
                    'secretquestion': user_record[0].PersonalQuestion
            }

        return None
    def change_password(self, username, salted_digest, pass_salt):
        # Dictionary containing data to be updated
        current_time = utilities.time.get_current_datetime()

        data = {
                'SaltedPassphraseDigest': salted_digest,
                'PassphraseSalt': pass_salt,
                'AccountLastModifiedTime': current_time
        }
        # pprint.pprint(data)
        # Condition for the update (where clause)
        condition = base_dbdriver.UserRegistry.UniqueUserName == username

        # Use the update_data method to change the password
        success = self.db_driver.update_data(base_dbdriver.UserRegistry,
                                             condition,
                                             data)

        return success

    def change_email(self, username, new_email):
        current_time = utilities.time.get_current_datetime()

        # Dictionary containing data to be updated
        data = {
                'AccountEmailAddress':new_email,
                'AccountLastModifiedTime':current_time
        }

        # Condition for the update (where clause)
        condition = base_dbdriver.UserRegistry.UniqueUserName == username

        # Use the update_data method to change the email
        success = self.db_driver.update_data(base_dbdriver.UserRegistry,
                                             condition,
                                             data)

        return success

    def change_question(self, username, passworddigest, question, answersalt, saltedanswer):
        current_time = utilities.time.get_current_datetime()

        # Query the database to get the user record
        user_record = self.db_driver.select_data(base_dbdriver.UserRegistry,
                                                 base_dbdriver.UserRegistry.UniqueUserName == username)

        if not len(user_record):
            # User does not exist
            return -1

        # Check if the PassphraseSalt matches
        if user_record[0].SaltedPassphraseDigest != passworddigest[:32]:
            # Passphrase salt doesn't match
            return -2

        # Dictionary containing data to be updated
        data = {
                'PersonalQuestion': question,
                'SaltedAnswerToQuestionDigest': saltedanswer,
                'AnswerToQuestionSalt': answersalt,
                'AccountLastModifiedTime':current_time
        }

        # Condition for the update (where clause)
        condition = base_dbdriver.UserRegistry.UniqueUserName == username

        # Use the update_data method to change the security question
        success = self.db_driver.update_data(base_dbdriver.UserRegistry,
                                             condition,
                                             data)

        return success

    def check_or_set_auth_ticket(self, accountID, userIP, creationTime, expirationTime):
        session = self.session
        try:
            record = session.query(base_dbdriver.AuthenticationTicketsRecord).filter_by(UserRegistry_UniqueID=accountID).first()
            if record:
                if record.TicketExpirationTime < datetime.datetime.now():
                    session.delete(record)
                    session.commit()
                    return False
                return record.TicketCreationTime, record.TicketExpirationTime
            else:
                new_record = base_dbdriver.AuthenticationTicketsRecord(
                    UserRegistry_UniqueID=accountID,
                    UserIPAddress=userIP,
                    TicketCreationTime=creationTime,
                    TicketExpirationTime=expirationTime
                )
                session.add(new_record)
                session.commit()
                return None
        except SQLAlchemyError as e:
            session.rollback()
            print(f"Error checking or setting auth ticket: {e}")
            return None
        finally:
            session.close()


    def change_subscriptions_changeflag(self, username: str):
        """
        Finds a user by their username in UserRegistry, retrieves all their subscriptions
        in AccountSubscriptionsRecord, and sets SubscriptionStatus to 0 for any active subscriptions.
        """
        # FIXME this is a quick dirty hack to fix issue 49 (receipt triggers multiple times)
        try:
            # Find the user's unique ID by username
            user_id = self.session.query(base_dbdriver.UserRegistry.UniqueID).filter_by(UniqueUserName = username).one_or_none()

            if not user_id:
                raise NoResultFound(f"No user found with username: {username}")

            user_id = user_id[0]  # Extract the UniqueID

            # Find all subscriptions for the user that have SubscriptionStatus != 0
            subscriptions = (
                    self.session.query(AccountSubscriptionsRecord)
                    .filter(
                            AccountSubscriptionsRecord.UserRegistry_UniqueID == user_id,
                            AccountSubscriptionsRecord.StatusChangeFlag != 0
                    )
                    .all()
            )

            if subscriptions:
                # Update SubscriptionStatus to 0 for each subscription
                for subscription in subscriptions:
                    subscription.StatusChangeFlag = 0

                # Commit the changes
                self.session.commit()
        except NoResultFound as e:
            print(e)
            self.session.rollback()
        except Exception as e:
            print(f"An error occurred: {e}")
            self.session.rollback()