import binascii
import hashlib
import logging
import os
import re
import Levenshtein
from datetime import date, datetime, timedelta

from sqlalchemy import and_, exists, func, or_
from sqlalchemy.exc import NoResultFound, SQLAlchemyError

from steam3.Types.community_types import FriendRelationship, PlayerState
from steam3.Types.steam_types import EResult
from utilities.database import authdb, base_dbdriver, dbengine
from utilities.database.base_dbdriver import AccountPaymentCardInfoRecord, AccountPrepurchasedInfoRecord, AccountSubscriptionsBillingInfoRecord, AccountSubscriptionsRecord, AdministrationUsersRecord, AppOwnershipTicketRegistry, Beta1_Friendslist, Beta1_Subscriptions, Beta1_TrackerRegistry, Beta1_User, ClientInventoryItems, CommunityRegistry, ExternalPurchaseInfoRecord, FriendsChatHistory, FriendsGroupMembers, FriendsGroups, FriendsList, FriendsNameHistory, FriendsPlayHistory, FriendsRegistry, GuestPassRegistry, Steam3CCRecord, Steam3GiftTransactionRecord, Steam3TransactionAddressRecord, Steam3TransactionsRecord, SteamApplications, SteamSubApps, SteamSubscriptions, UserMachineIDRegistry, VACBans, UserRegistry

log = logging.getLogger('CMDB')

# TODO:
#  change admin account password
#

class admin_dbdriver:

    def __init__(self, config):
        self.config = config
        while globalvars.mariadb_initialized != True:
            continue
        self.db_driver = dbengine.create_database_driver()
        self.db_driver.connect()

        self.UserRegistry = base_dbdriver.UserRegistry

        # Create a session for ORM operations
        self.session = self.db_driver.get_session()


    def add_administrator(self, username, pw_hash, pw_seed, rights):
        """ Store a new user with hashed password and seed """
        try:
            new_user = AdministrationUsersRecord(
                Username=username,
                PWHash=pw_hash,
                PWSeed=pw_seed,
                Rights=rights
            )
            self.session.add(new_user)
            self.session.commit()
            return True
        except Exception as e:
            self.session.rollback()
            print(f"Error adding user: {e}")
            return False

    def validate_user(self, username_id, input_pw_hash):
        """ Validate a user's password hash """
        try:
            user_record = self.session.query(AdministrationUsersRecord).filter_by(Username=username_id).one()
            # Assuming the client-side logic recomputes the hash using the stored seed
            recomputed_hash = hashlib.sha256((user_record.PWSeed + input_pw_hash).encode('utf-8')).hexdigest()
            if recomputed_hash == user_record.PWHash:
                return True, user_record.Rights
            return False, None
        except Exception as e:
            print(f"Error validating user: {e}")
            return False, None

    def get_users_by_email(self, email_address):
        """Return a list of user unique IDs and usernames that match the given email address."""
        try:
            users = self.session.query(
                self.UserRegistry.UniqueID,
                self.UserRegistry.UniqueUserName
            ).filter(
                self.UserRegistry.AccountEmailAddress == email_address
            ).all()
            return [(user.UniqueID, user.UniqueUserName) for user in users]
        except SQLAlchemyError as e:
            log.error(f"Error fetching users by email {email_address}: {e}")
            return f"Error: {str(e)}\x00"

    def get_user_by_username(self, username):
        """Return a single entry with the user ID for the given username.
           If no exact match is found, return the closest matching usernames."""
        try:
            # Attempt to find the exact match
            user = self.session.query(
                    self.UserRegistry.UniqueID,
                    self.UserRegistry.UniqueUserName
            ).filter(
                    self.UserRegistry.UniqueUserName == username
            ).one()
            return [(user.UniqueID, user.AccountEmailAddress)]

        except NoResultFound:
            # If no exact match is found, find the closest matches using Levenshtein distance
            all_users = self.session.query(
                    self.UserRegistry.UniqueID,
                    self.UserRegistry.UniqueUserName
            ).all()

            if not all_users:
                return "Error: No Users In Database\x00"

            # Calculate the Levenshtein distance for each user
            closest_matches = sorted(
                    all_users,
                    key = lambda user:Levenshtein.distance(username, user.AccountEmailAddress)
            )[:5]  # Get top 5 closest matches

            return [(user.UniqueID, user.UniqueUserName) for user in closest_matches]

        except SQLAlchemyError as e:
            log.error(f"Error fetching user by username {username}: {e}")
            return f"Error: {str(e)}\x00"

    def get_user_by_userid(self, user_id):
        try:
            user_record = self.session.query(UserRegistry).filter(UserRegistry.UniqueID == user_id).first()
            if not user_record:
                return "User not found.\x00"
            return [user_record.UniqueUserName, user_record.AccountEmailAddress]
        except Exception as e:
            log.error(f"Error fetching user details for user ID {user_id}: {e}")
            return f"Error: {str(e)}\x00"

    def remove_user(self, unique_id):
        user = self.session.query(UserRegistry).filter_by(UniqueID = unique_id).first()
        if not user:
            return "User not found."

        # Remove related records
        self.session.query(AccountSubscriptionsRecord).filter_by(UserRegistry_UniqueID = user.UniqueID).delete()
        self.session.query(AccountPaymentCardInfoRecord).filter_by(UserRegistry_UniqueID = user.UniqueID).delete()
        self.session.query(AccountPrepurchasedInfoRecord).filter_by(UserRegistry_UniqueID = user.UniqueID).delete()
        self.session.query(AccountSubscriptionsBillingInfoRecord).filter_by(UserRegistry_UniqueID = user.UniqueID).delete()

        # Remove the user
        try:
            self.session.delete(user)
            self.session.commit()
            return b'\x00'
        except Exception as e:
            return f"Database Error deleting user {user.UniqueUserName}"


    def change_user_email(self, unique_id, new_email):
        user = self.session.query(UserRegistry).filter_by(UniqueID = unique_id).first()
        if not user:
            print("User not found.")
            return False
        try:
            user.AccountEmailAddress = new_email
            self.session.commit()
            print(f"Email address for user {user.UniqueUserName} has been updated.")
        except Exception as e:
            print(f"Database Error changing user: {user.UniqueUserName} Email Address to {new_email}")
            return -1
        return True

    def add_subscription(self, unique_id, subscription_ids):
        user = self.session.query(UserRegistry).filter_by(UniqueID = unique_id).first()
        if not user:
            print("User not found.")
            return False

        # Split the subscription_ids input into a list of IDs and strip spaces
        subscription_ids = [int(sid.strip()) for sid in subscription_ids.split(',')]
        try:
            # Loop through each subscription ID and add a new record for each
            for subscription_id in subscription_ids:
                new_subscription = AccountSubscriptionsRecord(
                        SubscriptionID = subscription_id,
                        UserRegistry_UniqueID = unique_id
                )
                self.session.add(new_subscription)

            # Commit all new subscriptions at once
            self.session.commit()
            print("Subscriptions added successfully.")
        except Exception as e:
            print(f"Database Error adding subscriptions to user account: {user.UniqueUserName}")
            return -1
        return True

    def set_user_ban(self, unique_id, banuser = True):
        user = self.session.query(UserRegistry).filter_by(UniqueID = unique_id).first()
        if not user:
            print("User not found.")
            return False

        user.Banned = banuser
        self.session.commit()
        print(f"User {user.UniqueUserName} has been banned.")
        
        return True

    def remove_subscription_from_user(self, unique_id, sub_id):
        subscription = self.session.query(AccountSubscriptionsRecord).filter_by(UserRegistry_UniqueID = unique_id, SubscriptionID = sub_id).first()
        if not subscription:
            print("Subscription not found.")
            return -1
        try:
            self.session.delete(subscription)
            self.session.commit()
            print("Subscription removed successfully.")
        except Exception as e:
            print(f"Error Deleting subscription: {subscription}, for user {username}")
            return -2
        
        return True

    def list_users(self):
        user_list = []
        for user in self.session.query(UserRegistry).all():
            user_info = [user.UniqueID, user.UniqueUserName, user.AccountEmailAddress]
            user_list.append(user_info)
        return user_list

    def list_subscriptions(self):
        console_height, _ = os.get_terminal_size()
        count = 0
        buffer = ""
        for subscription in self.session.query(SteamSubscriptions).all():
            buffer += f"SubscriptionID: {subscription.SubscriptionID}, Name: {subscription.Name}, ...\n"
            count += 1
            if count >= console_height - 1:
                count = 0
        
        return buffer

    def list_user_subscriptions(self, unique_id):

        # Retrieve all subscriptions for the user
        user_subscriptions = self.session.query(AccountSubscriptionsRecord).filter(AccountSubscriptionsRecord.UserRegistry_UniqueID == unique_id).all()

        subscription_list = []

        for subscription in user_subscriptions:
            # Find subscription name in SteamSubscriptions table
            steam_subscription = self.session.query(SteamSubscriptions).filter(SteamSubscriptions.SubscriptionID == subscription.SubscriptionID).first()
            subscription_name = steam_subscription.Name if steam_subscription else "Unknown"
            subscription_list.append([subscription.SubscriptionID, subscription_name])

        return subscription_list

    def list_applications_for_subscription(self, subscription_id):
        console_height, _ = os.get_terminal_size()
        count = 0
        sub_apps_record = self.session.query(SteamSubApps).filter_by(SteamSubscriptions_SubscriptionID = subscription_id).first()
        if not sub_apps_record:
            return "Subscription not found."

        app_list = sub_apps_record.AppList.split(',')
        buffer = f"Applications for Subscription ID {subscription_id}:"
        for app_id in app_list:
            steam_application = self.session.query(SteamApplications).filter_by(AppID = app_id).first()
            if steam_application:
                buffer += f"AppID: {app_id}, Name: {steam_application.Name}"
                count += 1
                if count >= console_height - 1:
                    count = 0

        return buffer

    def rename_user(self, unique_id, new_username):
        valid_username_pattern = r'^[A-Za-z0-9@.]+$'

        # Validate the new username
        if not re.match(valid_username_pattern, new_username):
            return "Invalid username."

        # Find the user by unique ID
        user_record = self.session.query(UserRegistry).filter_by(UniqueID = unique_id).first()
        if not user_record:
            return "User not found."

        # Check if the new username already exists
        existing_user = self.session.query(UserRegistry).filter_by(UniqueUserName = new_username).first()
        if existing_user:
            return "User Already Exists"

        try:
            # Proceed with renaming the user
            old_username = user_record.UniqueUserName
            user_record.UniqueUserName = new_username
            self.session.commit()
            print(f"Username updated from {old_username} to {new_username}")
            return b'\x00'  # Return b'\x00' on success
        except Exception as e:
            self.session.rollback()  # Roll back the session in case of an error
            return f"Failed to rename user: {old_username}. Error: {e}"

    def update_user_password(self, unique_id, salt, salted_digest):
        # Check if the user exists
        user = self.session.query(UserRegistry).filter_by(UniqueID = unique_id).first()
        if user:
            # Update the user's password and salt
            try:
                user.PassphraseSalt = salt
                user.SaltedPassphraseDigest = salted_digest
                self.session.commit()
                print(f"Password updated successfully for user: {user.UniqueUserName}")
            except Exception as e:
                return f"Error updating password for user: {user.UniqueUserName} {e}"
        else:
            return "User not found."

        return True

    def update_user_question(self, unique_id, question, salt, salted_digest):
        # Check if the user exists
        user = self.session.query(UserRegistry).filter_by(UniqueID = unique_id).first()
        if user:
            # Update the user's password and salt
            try:
                user.PersonalQuestion = question
                user.AnswerToQuestionSalt = salt
                user.SaltedAnswerToQuestionDigest = salted_digest
                self.session.commit()
                print(f"Password updated successfully for user: {user.UniqueUserName}")
            except Exception as e:
                return f"Error updating password for user: {user.UniqueUserName} {e}"
        else:
            return "User not found."

        return True

    def add_vac_ban_to_account(self, first_appid, last_appid, ban_duration_hours, unique_id):
        try:
            # Check if a VAC ban with the same first_appid, last_appid, and unique_id already exists
            existing_ban = self.session.query(VACBans).filter_by(
                    friendRegistryID = unique_id,
                    firstappid = first_appid,
                    lastappid = last_appid
            ).first()

            if existing_ban:
                return "error: Vac Ban already Exists for this appid range"

            # If no existing ban, proceed to add a new VAC ban
            current_time = datetime.now().strftime("%m/%d/%Y %H:%M:%S")
            vac_ban = VACBans(
                    friendRegistryID = unique_id,
                    starttime = current_time,
                    firstappid = first_appid,
                    lastappid = last_appid,
                    length_of_ban = ban_duration_hours
            )

            self.session.add(vac_ban)
            self.session.commit()
            log.info(f"VAC ban added successfully. To UserID: {unique_id}")
            return b"\x00"

        except Exception as e:
            self.session.rollback()  # Rollback the transaction in case of an error
            log.info(f"Error Adding Vac Ban to UserID: {unique_id}: {e}")
            return f"Error Adding Vac Ban to UserID: {unique_id}: {e}"

    def list_user_vac_bans(self, unique_id):
        ban_list = []
        bans = self.session.query(VACBans).filter_by(friendRegistryID = unique_id).all()
        if not bans:
            log.info("No VAC bans found for this user.")
            return "No VAC bans found for this user."

        for ban in bans:
            ban_list.append((ban.UniqueID, ban.firstappid, ban.lastappid))

        return ban_list

    def remove_vac_ban_from_account(self, ban_id_to_remove, unique_id):
        ban_to_remove = self.session.query(VACBans).filter_by(UniqueID = unique_id).first()
        if ban_to_remove:
            try:
                self.session.delete(ban_to_remove)
                self.session.commit()
                log.info("VAC ban removed successfully.")
            except Exception as e:
                log.info(f"Error Removing Vac Ban to UserID: {unique_id}: {e}")
                return f"Error Removing Vac Ban to UserID: {unique_id}: {e}"
        else:
            log.info("VAC ban not found.")
            return "VAC ban not found."
        return b'\x00'

    def update_community_profile(self, userid, real_name="", headline="", summary="", profile_url="",
                                 country="", state="", city="", avatarID="",
                                 website_title1="", website_url1="", website_title2="",
                                 website_url2="", website_title3="", website_url3="",
                                 profile_visibility=None, comment_permissions=None, welcome=None):
        """Update the community profile for a user based on provided parameters."""
        try:
            # Step 1: Find the friendsregistry.UniqueID where accountID matches the parameter userid
            unique_id = self.session.query(FriendsRegistry.UniqueID).filter_by(accountID=userid).one().UniqueID

            # Step 2: Use the found UniqueID to find the entry in CommunityRegistry
            community_profile = self.session.query(CommunityRegistry).filter_by(friendRegistryID=unique_id).one()

            # Step 3: Update any provided parameters
            if real_name:
                community_profile.real_name = real_name
            if headline:
                community_profile.headLine = headline
            if summary:
                community_profile.summary = summary
            if profile_url:
                community_profile.profile_url = profile_url
            if country:
                community_profile.country = country
            if state:
                community_profile.state = state
            if city:
                community_profile.city = city
            if avatarID:
                community_profile.avatarID = avatarID
            if website_title1:
                community_profile.website_title1 = website_title1
            if website_url1:
                community_profile.website_url1 = website_url1
            if website_title2:
                community_profile.website_title2 = website_title2
            if website_url2:
                community_profile.website_url2 = website_url2
            if website_title3:
                community_profile.website_title3 = website_title3
            if website_url3:
                community_profile.website_url3 = website_url3
            if profile_visibility is not None:
                community_profile.profile_visibility = profile_visibility
            if comment_permissions is not None:
                community_profile.comment_permissions = comment_permissions
            if welcome is not None:
                community_profile.welcome = welcome

            # Commit the changes
            self.session.commit()
            print("Community profile updated successfully.")
            return True
        except NoResultFound:
            print("User not found.")
            return False
        except SQLAlchemyError as e:
            self.session.rollback()
            print(f"Error updating community profile: {e}")
            return False

    def create_user(self, unique_username, passphrase_salt = "", salted_passphrase_digest = "",
            answer_to_question_salt = "", salted_answer_to_question_digest = "", personal_question = "",
            account_email_address = "", cell_id = 1, user_type = 1, banned = 0, email_verified = 0,
            first_name = "", last_name = "", tracker_username = ""):
        """Insert a new user into the UserRegistry table with the specified fields."""

        try:
            # Check if the username already exists
            existing_user = self.session.query(UserRegistry).filter_by(UniqueUserName = unique_username).first()
            if existing_user:
                return "Username Is Taken"

            # Proceed to create a new user if the username is not taken
            new_user = UserRegistry(
                    UniqueUserName = unique_username,
                    AccountCreationTime = datetime.now().strftime("%m/%d/%Y %H:%M:%S"),
                    UserType = user_type,
                    SaltedAnswerToQuestionDigest = salted_answer_to_question_digest,
                    PassphraseSalt = passphrase_salt,
                    AnswerToQuestionSalt = answer_to_question_salt,
                    PersonalQuestion = personal_question,
                    SaltedPassphraseDigest = salted_passphrase_digest,
                    LastRecalcDerivedSubscribedAppsTime = datetime.now().strftime("%m/%d/%Y %H:%M:%S"),
                    CellID = cell_id,
                    AccountEmailAddress = account_email_address,
                    Banned = banned,
                    email_verified = email_verified,
                    FirstName = first_name,
                    LastName = last_name,
                    TrackerUserName = tracker_username
            )

            # Add the new user to the session
            self.session.add(new_user)
            self.session.commit()

            print(f"User {unique_username} created successfully.")
            return int(new_user.UniqueID)

        except SQLAlchemyError as e:
            self.session.rollback()
            return f"Error creating user: {e}\0"

    #####################################
    #        Beta 1 SQL Functions       #
    #####################################
    def create_beta1_user(self, username, accountkey, salt, hash):
        """Insert a new user into the Beta1_User table, ensuring no duplicate username."""
        try:
            # Check for duplicate username
            existing_user = self.session.query(Beta1_User).filter_by(username = username).first()
            if existing_user:
                return "Username Is Taken"

            new_user = Beta1_User(
                    username = username,
                    createtime = int(datetime.now().timestamp()),
                    accountkey = accountkey,
                    salt = salt,
                    hash = hash
            )

            # Add the new user to the session
            self.session.add(new_user)
            self.session.commit()

            print(f"Beta1 user {username} created successfully.")
            return int(new_user.id)

        except SQLAlchemyError as e:
            self.session.rollback()
            print(f"Error creating Beta1 user: {e}")
            return None

    def create_beta1_subscription(self, username, subid):
        """Insert a new subscription into the Beta1_Subscriptions table, ensuring no duplicate entry."""
        try:
            # Check for duplicate subscription
            existing_subscription = self.session.query(Beta1_Subscriptions).filter_by(username = username, subid = subid).first()
            if existing_subscription:
                print(f"Beta1 subscription for {username} with subid {subid} already exists.")
                return False

            new_subscription = Beta1_Subscriptions(
                    username = username,
                    subid = subid,
                    subtime = int(datetime.now().timestamp())
            )

            # Add the new subscription to the session
            self.session.add(new_subscription)
            self.session.commit()

            print(f"Beta1 subscription for {username} with subid {subid} created successfully.")
            return True

        except SQLAlchemyError as e:
            self.session.rollback()
            print(f"Error creating Beta1 subscription: {e}")
            return False

    def create_beta1_tracker_registry(self, username, firstname, lastname, email, password):
        """Insert a new entry into the Beta1_TrackerRegistry table, ensuring no duplicate username."""
        try:
            # Check for duplicate username
            existing_entry = self.session.query(Beta1_TrackerRegistry).filter_by(username = username).first()
            if existing_entry:
                print(f"Beta1 tracker registry entry for {username} already exists.")
                return None

            new_entry = Beta1_TrackerRegistry(
                    username = username,
                    firstname = firstname,
                    lastname = lastname,
                    email = email,
                    password = password
            )

            # Add the new entry to the session
            self.session.add(new_entry)
            self.session.commit()

            print(f"Beta1 tracker registry entry for {username} created successfully.")
            return new_entry.uniqueid

        except SQLAlchemyError as e:
            self.session.rollback()
            print(f"Error creating Beta1 tracker registry entry: {e}")
            return None

    def create_beta1_friendslist(self, source, target):
        """Insert a new friend relation into the Beta1_Friendslist table, ensuring no duplicate entry."""
        try:
            # Check for duplicate friend relation
            existing_relation = self.session.query(Beta1_Friendslist).filter_by(source = source, target = target).first()
            if existing_relation:
                print(f"Beta1 friend relation between {source} and {target} already exists.")
                return None

            new_friend_relation = Beta1_Friendslist(
                    source = source,
                    target = target
            )

            # Add the new friend relation to the session
            self.session.add(new_friend_relation)
            self.session.commit()

            print(f"Beta1 friend relation between {source} and {target} created successfully.")
            return new_friend_relation.uniqueid

        except SQLAlchemyError as e:
            self.session.rollback()
            print(f"Error creating Beta1 friend relation: {e}")
            return None

    def beta1_list_all_users(self):
        """Returns a list of all Beta1 users with each entry containing the user ID and username."""
        try:
            users = self.session.query(Beta1_User.id, Beta1_User.username).all()
            return [(user.id, user.username) for user in users]
        except SQLAlchemyError as e:
            self.session.rollback()
            print(f"Error listing Beta1 users: {e}")
            return f"Error: {str(e)}\x00"
    def beta1_get_uniqueid_by_email(self, email):
        """Returns the user's uniqueid where the username matches the email or a null terminated error string."""
        try:
            user = self.session.query(Beta1_TrackerRegistry.uniqueid).filter_by(email=email).one()
            return user.uniqueid
        except NoResultFound:
            return "Error: User not found\x00"
        except SQLAlchemyError as e:
            self.session.rollback()
            print(f"Error fetching uniqueid by email: {e}")
            return f"Error: {str(e)}\x00"

    def beta1_get_email_by_uniqueid(self, uniqueid):
        """Returns the email of the user where the uniqueid matches or a null terminated error string."""
        try:
            user = self.session.query(Beta1_TrackerRegistry.email).filter_by(uniqueid = uniqueid).one()
            return user.email
        except NoResultFound:
            return "Error: User not found\x00"
        except SQLAlchemyError as e:
            self.session.rollback()
            print(f"Error fetching email by uniqueid: {e}")
            return f"Error: {str(e)}\x00"

    def beta1_list_user_subscriptions(self, uniqueid):
        """Finds the matching username from the Beta1 user table and returns a list of subscriptions."""
        try:
            user = self.session.query(Beta1_User.username).filter_by(id = uniqueid).one()
            subscriptions = self.session.query(Beta1_Subscriptions.subid, Beta1_Subscriptions.subtime).filter_by(username = user.username).all()
            return [(subscription.subid, subscription.subtime) for subscription in subscriptions]
        except NoResultFound:
            return "Error: User or subscriptions not found\x00"
        except SQLAlchemyError as e:
            self.session.rollback()
            print(f"Error listing user's subscriptions: {e}")
            return f"Error: {str(e)}\x00"

    def beta1_remove_subscription(self, uniqueid, subid):
        """Removes a subscription from the Beta1_Subscriptions table."""
        try:
            user = self.session.query(Beta1_User.username).filter_by(id = uniqueid).one()
            subscription = self.session.query(Beta1_Subscriptions).filter_by(username = user.username, subid = subid).one()
            self.session.delete(subscription)
            self.session.commit()
            return "\x00"
        except NoResultFound:
            return "Error: Subscription not found\x00"
        except SQLAlchemyError as e:
            self.session.rollback()
            print(f"Error removing subscription: {e}")
            return f"Error: {str(e)}\x00"