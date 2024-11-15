import binascii
import hashlib
import logging
from datetime import date, datetime, timedelta

from sqlalchemy import and_, exists, func, or_
from sqlalchemy.exc import NoResultFound, SQLAlchemyError

import globalvars
from steam3.Types.community_types import FriendRelationship, PlayerState
from steam3.Types.steam_types import EAccountFlags, EResult
from utilities.database import authdb, base_dbdriver, dbengine
from utilities.database.base_dbdriver import AppOwnershipTicketRegistry, ClientInventoryItems, CommunityClanMembers, CommunityRegistry, ExternalPurchaseInfoRecord, FriendsChatHistory, FriendsGroupMembers, FriendsGroups, FriendsList, FriendsNameHistory, FriendsPlayHistory, FriendsRegistry, GuestPassRegistry, Steam3CCRecord, Steam3GiftTransactionRecord, Steam3TransactionAddressRecord, Steam3TransactionsRecord, SteamApplications, UserMachineIDRegistry, VACBans
from utils import get_derived_appids

log = logging.getLogger('CMDB')


class cm_dbdriver:

    def __init__(self, config):

        self.config = config

        self.db_driver = dbengine.create_database_driver()
        while globalvars.mariadb_initialized != True:
            continue
        self.db_driver.connect()

        self.UserRegistry = base_dbdriver.UserRegistry

        # Create a session for ORM operations
        self.session = self.db_driver.get_session()

    ##################
    # User
    ##################

    def create_user(self, unique_username, user_type = 1, passphrase_salt = "", salted_passphrase_digest = "",
            answer_to_question_salt = "", personal_question = "", salted_answer_to_question_digest = "",
            cell_id = 1, account_email_address = "", banned = 0, email_verified = 0,
            first_name = None, last_name = None, tracker_username = None):
        """Insert a new user into the UserRegistry table with the specified fields."""
        try:
            # Check if the unique username already exists
            existing_user = self.session.query(self.UserRegistry).filter_by(UniqueUserName = unique_username).first()
            if existing_user:
                print(f"Username {unique_username} already exists.")
                return 0, EResult.DuplicateName

            new_user = self.UserRegistry(
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
                    DerivedSubscribedAppsRecord = get_derived_appids(),
                    Banned = banned,
                    AccountLastModifiedTime = datetime.now().strftime("%m/%d/%Y %H:%M:%S"),
                    email_verified = email_verified,
                    FirstName = first_name,
                    LastName = last_name,
                    TrackerUserName = tracker_username
            )

            # Add the new user to the session
            self.session.add(new_user)
            self.session.commit()

            print(f"User {unique_username} created successfully.")
            return new_user.UniqueID, EResult.OK

        except SQLAlchemyError as e:
            self.session.rollback()
            log.error(f"Error creating user: {e}")
            return 0, EResult.IOFailure

    def get_or_create_registry_entry(self, accountID: int) -> FriendsRegistry and bool:
        """
        Retrieves an existing FriendsRegistry entry by accountID or creates a new one if it does not exist,
        using the nickname from UserRegistry.

        :param accountID: The account ID of the user
        :return: tuple of (FriendsRegistry instance, created boolean)
        """
        # Check if the entry already exists in FriendsRegistry
        friend = self.session.query(FriendsRegistry).filter_by(accountID = accountID).first()
        if friend:
            community = self.session.query(CommunityRegistry).filter_by(friendRegistryID = accountID).first()
            if not community:
                print("creating Community Registry entry")
                new_community = CommunityRegistry(
                        friendRegistryID = accountID,
                )
                self.session.add(new_community)
                self.session.commit()
            return friend, False  # Return the found entry and False indicating it was not created now
        else:
            print("creating friendsregistry entry")
            new_friend = FriendsRegistry(
                    accountID = accountID,
                    nickname = '',  # Assuming the nickname to use is UniqueUserName
                    status = 0,  # Default status, modify as needed
                    last_login = datetime.now()  # Set last_login to now upon creation
            )
            self.session.add(new_friend)
            self.session.commit()
            # If not found in FriendsRegistry, retrieve nickname from UserRegistry
            #user = self.session.query(self.UserRegistry).filter_by(UniqueID = accountID).first()
            #if not user:
            #    raise ValueError("No user found with the given accountID in UserRegistry")

            # Create a new entry in FriendsRegistry with the nickname from UserRegistry
            community = self.session.query(CommunityRegistry).filter_by(friendRegistryID = accountID).first()
            if not community:
                print("creating Community Registry entry")
                new_community = CommunityRegistry(
                        friendRegistryID = accountID,
                )
                self.session.add(new_community)
                self.session.commit()
            return new_friend, True

    def check_user_information(self, email, password):
        user = self.session.query(self.UserRegistry).filter_by(AccountEmailAddress=email).first()
        if user:
            if user.Banned is not None or user.Banned != 0:
                salt = binascii.unhexlify(user.PassphraseSalt)
                digest_hex = user.SaltedPassphraseDigest[0:32]

                hashed_password = hashlib.sha1(salt[:4] + password.encode() + salt[4:]).digest()
                hashed_password_hex = binascii.hexlify(hashed_password[0:16])
                print(f"db_hash: {digest_hex.encode('latin-1')}, user_diget: {hashed_password_hex}")
                if digest_hex.encode('latin-1') == hashed_password_hex:
                    return 1
                else:
                    log.info(f"User {user.UniqueUserName} Tried logging in with an incorrect password!")
                    return 5
            else:
                log.info(f"User {user.UniqueUserName} is banned!")
                return 17
        else:
            log.info(f"Uknown User {email} tried to log in")
            return 18

    def compare_password_digests(self, email, digest):
        user = self.session.query(self.UserRegistry).filter_by(AccountEmailAddress=email).first()
        if user:
            if user.Banned is not None or user.Banned != 0:
                digest_hex = user.SaltedPassphraseDigest[0:32]
                print(f"db_hash: {digest_hex.encode('latin-1')}, user_diget: {digest.encode('latin-1')}")
                if digest_hex.encode('latin-1') == digest.encode('latin-1'):
                    return 1
                else:
                    log.info(f"User {user.UniqueUserName} Tried logging in with an incorrect password!")
                    return 5
            else:
                log.info(f"User {user.UniqueUserName} is banned!")
                return 17
        else:
            log.info(f"Uknown User {email} tried to log in")
            return 18

    def get_user_details(self, accountID) -> FriendsRegistry or None:
        """
        Retrieves all attributes of a user from the FriendsRegistry table as a dictionary.

        :param accountID: The account ID of the user to fetch.
        :return: A dictionary containing all user details or None if user does not exist.
        """
        # Fetch the user entry from FriendsRegistry based on accountID
        user = self.session.query(FriendsRegistry).filter_by(accountID=accountID).first()
        if user:
            return user
        else:
            return None  # Return None if no user is found with the given accountID

    def get_user_avatar(self, accountID):
        """
        Retrieves a users avatarID from CommunityRegistry.

        :param accountID: The account ID of the user to fetch.
        :return: A byte string avatarID
        """
        user = self.session.query(CommunityRegistry).filter_by(friendRegistryID=accountID).first()
        if user:
            return user.avatarID.encode('latin-1')
        else:
            return None  # Return None if no user is found with the given accountID

    def get_or_set_nickname(self, accountid, nickname = None):
        user = self.session.query(FriendsRegistry).filter_by(accountID = accountid).first()
        if user:
            if nickname and user.nickname != nickname:
                # Oh, a change? That's a shocker, given your aversion to anything resembling progress, douchebag.
                # Log the old nickname because someone has to remember your past mistakes.
                self.log_nickname_change(accountid, user.nickname)
                # Update to the new and supposedly better nickname
                user.nickname = nickname
                self.session.commit()
            # No change, just like your stagnant coding skills.
            return user.nickname if user.nickname is not None else 'unset'
        else:
            # Classic you, looking for something that doesn't exist?like your coding talent.
            raise ValueError("No user found with the given accountID, probably a loner like you.")

    def log_nickname_change(self, accountid, old_nickname):
        # Let?s record this monumental change, since we can't expect you to remember anything on your own.
        new_history_entry = FriendsNameHistory(
                friendRegistryID = accountid,
                nickname = old_nickname,
                datetime = datetime.now()  # Standard datetime format, try not to mess it up.
        )
        self.session.add(new_history_entry)
        self.session.commit()  # Commit the change, if you're capable of committing to anything, that is.

    def set_user_state(self, accountid, state: PlayerState):
        user = self.session.query(FriendsRegistry).filter_by(accountID = accountid).first()
        if user:
            user.status = int(state.value)
            self.session.commit()
            return True

        return False

    def set_last_login(self, user_id):
        """
        Update the last_login datetime for a user in the FriendsRegistry.

        :param user_id: The unique account ID of the user.
        """
        # Fetch the user from the FriendsRegistry table
        user = self.session.query(FriendsRegistry).filter_by(accountID=user_id).first()
        if user:
            user.last_login = datetime.now()  # Set current datetime
            self.session.commit()  # Commit the changes to the database
            return True

        return False

    def set_last_logoff(self, user_id):
        """
        Update the last_login datetime for a user in the FriendsRegistry.

        :param user_id: The unique account ID of the user.
        """
        # Fetch the user from the FriendsRegistry table
        user = self.session.query(FriendsRegistry).filter_by(accountID=user_id).first()
        if user:
            user.last_logoff = datetime.now()  # Set current datetime
            user.currently_playing = None
            self.session.commit()  # Commit the changes to the database
            return True

        return False

    def set_onetime_pass(self, accountID, otp):
        """
        Retrieves a users avatarID from CommunityRegistry.

        :param accountID: The account ID of the user to fetch.
        :return: A byte string avatarID
        """
        user = self.session.query(CommunityRegistry).filter_by(friendRegistryID=accountID).first()
        if user:
            user.onetime_pass = otp[0:17]  # Set current datetime
            self.session.commit()  # Commit the changes to the database
            return True
        else:
            return False  # Couldnt save one time pass, error!

    def check_and_update_machine_ids(self, account_id, bb3, ff2, _3b3, overwrite = False):
        """
        Checks and updates machine IDs for a given account.

        :param account_id: The account ID to search for.
        :param bb3: The BB3 machine ID to compare.
        :param ff2: The FF2 machine ID to compare.
        :param _3b3: The 3B3 machine ID to compare.
        :param overwrite: Whether to overwrite the existing machine IDs if they do not match.
        :return: True if the machine IDs match or were successfully updated, False otherwise.
        """
        try:
            # Extract the actual machine ID values from the tuples
            bb3_value = bb3[0] if isinstance(bb3, tuple) else bb3
            ff2_value = ff2[0] if isinstance(ff2, tuple) else ff2
            _3b3_value = _3b3[0] if isinstance(_3b3, tuple) else _3b3

            # Search for an existing entry by account ID
            entry = self.session.query(UserMachineIDRegistry).filter_by(accountID = account_id).first()

            if entry:
                # Compare the machine IDs
                if entry.BB3 == bb3_value and entry.FF2 == ff2_value and entry._3B3 == _3b3_value:
                    return True  # IDs match
                elif not overwrite:
                    return False  # IDs do not match and overwrite is false
                else:
                    # Overwrite the existing machine IDs
                    entry.BB3 = bb3_value
                    entry.FF2 = ff2_value
                    entry._3B3 = _3b3_value
                    self.session.commit()
                    return True  # IDs were updated
            else:
                # Create a new entry if none exists
                new_entry = UserMachineIDRegistry(accountID = account_id, BB3 = bb3_value, FF2 = ff2_value, _3B3 = _3b3_value)
                self.session.add(new_entry)
                self.session.commit()
                return True  # New entry created

        except SQLAlchemyError as e:
            self.session.rollback()
            log.error(f"Error in check_and_update_machine_ids: {e}")
            return False  # Return False if there is an error

    def get_user_email_and_verification_status(self, accountid: int):
        """
        Retrieves the email address and verification status for a given account ID.

        :param session: SQLAlchemy database session.
        :param accountid: The UniqueID of the user.
        :return: A tuple (email, email_verified) or None if the account does not exist.
        """
        user = self.session.query(self.UserRegistry.AccountEmailAddress, self.UserRegistry.email_verified).filter(
                self.UserRegistry.UniqueID == accountid
        ).first()

        if user:
            # email_verified is stored as an integer; convert it to a boolean
            return user.AccountEmailAddress, bool(user.email_verified)
        return None

    def compute_accountflags(self, userid: int) -> int:
        """
        Computes the combined EAccountFlags for a given user ID.

        :param session: SQLAlchemy session.
        :param userid: The UniqueID of the user in UserRegistry.
        :return: Combined EAccountFlags as an integer.
        """
        flags = EAccountFlags.NormalUser | EAccountFlags.PasswordSet  # Always set these flags

        # Check if the user exists in UserRegistry
        user = self.session.query(self.UserRegistry).filter(self.UserRegistry.UniqueID == userid).first()
        if not user:
            raise ValueError(f"No user found with ID {userid}")

        # Check if PersonaNameSet flag should be added
        nickname_exists = self.session.query(FriendsRegistry).filter(
                FriendsRegistry.accountID == userid, FriendsRegistry.nickname != None,
        ).count() > 0
        if nickname_exists:
            flags |= EAccountFlags.PersonaNameSet

        # Check if HWIDSet flag should be added
        hwid_exists = self.session.query(UserMachineIDRegistry).filter(
                UserMachineIDRegistry.accountID == userid,
                and_(
                        UserMachineIDRegistry.BB3 != None,
                        UserMachineIDRegistry.FF2 != None,
                        UserMachineIDRegistry._3B3 != None,
                )
        ).count() > 0
        if hwid_exists:
            flags |= EAccountFlags.HWIDSet

        # Check if PersonalQASet flag should be added
        if user.SaltedAnswerToQuestionDigest:
            flags |= EAccountFlags.PersonalQASet

        # Check if EmailValidated flag should be added
        if user.email_verified == 1:
            flags |= EAccountFlags.EmailValidated

        return flags

    ##################
    # User Clan Information
    ##################
    def get_users_clan_list(self, account_id: int, relationship: int):
        """
        Retrieve all entries from CommunityClanMembers where the friendRegistryID matches the account_id
        and the relationship matches the specified value.

        :param session: SQLAlchemy Session instance
        :param account_id: The account ID to filter by
        :param relationship: The relationship value to filter by
        :return: List of CommunityClanMembers entries
        """
        return self.session.query(CommunityClanMembers).filter(
                CommunityClanMembers.friendRegistryID == account_id,
                CommunityClanMembers.relationship == relationship
        ).all()

    ##################
    # Friend/Friendlist
    ##################
    def fix_invites(self, steamid):
        """
        Update the friend status to 3 for all friends of the given steamid where status is 2 or 4.

        This is only used if a client connects with a steam client that is steamui version 352 or greater,
        until the issue is resolved where the receiving user of a friend request does not get a pop-up
        dialog to accept a friend request.

        :param steamid: The steam ID to search for in the friendRegistryID field.
        """
        try:
            # Fetch all entries where friendRegistryID is equal to the provided steamid
            friends_list = self.session.query(FriendsList).filter(FriendsList.friendRegistryID == steamid).all()

            # Update status to 3 where status is 2 or 4
            for friend in friends_list:
                if friend.relationship in [2, 4]:
                    friend.relationship = 3
                    self.session.add(friend)

            self.session.commit()
        except Exception as e:
            self.session.rollback()
            log.error(f"Error updating friend status: {e}")

    def find_user_by_name(self, nickname):
        """
        Attempts to find a user by nickname. If the nickname contains an '@', it searches by email address.
        If not, it searches by username first in UserRegistry and then in FriendsRegistry if needed.
        """
        if not nickname:
            print("Empty nickname")
            return None

        try:
            if '@' in nickname:
                # If the nickname contains '@', treat it as an email address
                user = self.session.query(self.UserRegistry.UniqueID).filter(self.UserRegistry.AccountEmailAddress == nickname).first()
                if user:
                    return user.UniqueID
                else:
                    print("No user found with that email address")
                    return None
            else:
                # Try finding the user in UserRegistry by username
                user = self.session.query(self.UserRegistry.UniqueID).filter(self.UserRegistry.UniqueUserName == nickname).first()
                if user:
                    return user.UniqueID
                else:
                    # User not found in UserRegistry, try FriendsRegistry
                    friend = self.session.query(FriendsRegistry).filter(FriendsRegistry.nickname == nickname).first()
                    return friend.accountID if friend else None
        except Exception as e:
            print(f"An error occurred, {e}")
            return None

    def add_friend(self, user_id, friend_criteria, relationship = 4):
        # Determine the type of `friend_criteria` which can be username, accountID, email, or first/last name
        if isinstance(friend_criteria, int):  # Assuming accountID is an integer
            friend = self.session.query(self.UserRegistry).filter_by(UniqueID = friend_criteria).first()
        elif '@' in friend_criteria:  # Assuming an email has '@'
            friend = self.session.query(self.UserRegistry).filter_by(AccountEmailAddress = friend_criteria).first()
        elif ' ' in friend_criteria:  # Assuming first and last names are separated by space
            friend = self.session.query(CommunityRegistry).filter_by(real_name = friend_criteria).first()
            friend = self.session.query(self.UserRegistry).filter_by(UniqueID = friend.accountID).first() if friend else None
        else:
            friend = self.session.query(self.UserRegistry).filter_by(UniqueUserName = friend_criteria).first()

        if friend:
            existing_friend_entry = self.session.query(FriendsList).filter_by(
                    friendRegistryID = user_id, friendsaccountID = friend.UniqueID
            ).first()

            if existing_friend_entry:
                if existing_friend_entry.relationship == 3:
                    # this should prevent the error issue when trying to add a user twice
                    return False

                # FIXME use this if the users deleted each other, instead of removing it from the DB set relationship to 0
                existing_friend_entry.relationship = int(relationship)

                inverse_friend_entry = self.session.query(FriendsList).filter_by(
                        friendRegistryID = friend.UniqueID, friendsaccountID = user_id
                ).first()
                inverse_friend_entry.relationship = int(relationship)
            else:
                # Create a new friend entry in FriendsList
                new_friend = FriendsList(
                        friendRegistryID = user_id,
                        friendsaccountID = friend.UniqueID,
                        relationship = int(relationship)
                )
                self.session.add(new_friend)
            self.session.commit()
            return True

        return False

    def manage_friendship(self, user_id, friend_id, action):
        """
        Manages friendship actions such as accepting invite, removing, blocking, unblocking, ignoring, and unignoring.
        :param user_id: User's account ID initiating the action.
        :param friend_id: Friend's account ID on whom the action is performed.
        :param action: The type of action to perform ('remove', 'block', 'unblock', 'ignore', 'unignore', 'accept').
        """
        try:
            # Find the primary friendship entry
            primary_entry = self.session.query(FriendsList).filter_by(
                friendRegistryID=user_id, friendsaccountID=friend_id).first()
            if primary_entry:
                if action in ['block', 'ignore', 'unblock', 'unignore', 'accept']:
                    relationship_status = {
                        'block': FriendRelationship.blocked,
                        'ignore': FriendRelationship.ignored,
                        'unblock': FriendRelationship.friend,  # Active/friends status
                        'unignore': FriendRelationship.friend,  # Reset the status
                        'accept': FriendRelationship.friend
                    }.get(action, FriendRelationship.friend)

                    if primary_entry:
                        primary_entry.relationship = int(relationship_status)
                elif action == 'remove':
                    # Remove the primary entry if it exists
                    if primary_entry:
                        self.session.delete(primary_entry)

                self.session.commit()
                return True
            return False
        except SQLAlchemyError as e:
            log.error(f"Database error: {e}")
            self.session.rollback()
            return False

    def get_friendslist_relationships(self, user_id):
        friends = self.session.query(FriendsList).filter_by(friendRegistryID=user_id).all()
        return friends #[(friend.friendsaccountID, friend.relationship) for friend in friends]

    def get_user_friendslist_registry_entries(self, accountID):
        """
        Retrieves all FriendsRegistry entries for friends of the given user account ID,
        along with their relationship status.

        :param accountID: The account ID of the user whose friends are to be retrieved.
        :return: A list of tuples, each containing a FriendsRegistry object and the relationship status.
        """
        # First, get the user's registry entry to ensure it exists
        user_registry_entry = self.session.query(FriendsRegistry).filter_by(accountID = accountID).first()
        if not user_registry_entry:
            raise ValueError(f"No FriendsRegistry entry found for account ID {accountID}")

        # Now, retrieve all FriendsList entries for this user
        friends_entries = self.session.query(FriendsList).filter_by(friendRegistryID = accountID).all()

        # Collect all friends' account IDs and their relationships from these entries
        friends_info = [(entry.friendsaccountID, entry.relationship) for entry in friends_entries]

        # Retrieve the FriendsRegistry entries for these IDs and pair them with the relationship
        if friends_info:
            friends_registry_entries = []
            for account_id, relationship in friends_info:
                friend_registry_entry = self.session.query(FriendsRegistry).filter(FriendsRegistry.accountID == account_id).first()
                if friend_registry_entry:
                    # Append a tuple of the FriendsRegistry entry and the relationship
                    friends_registry_entries.append((friend_registry_entry, relationship))
            return friends_registry_entries
        else:
            # print("Database returned 0 entries for friendslist")
            # Return an empty list if the user has no friends
            return []

    def remove_friend(self, user_id, friend_id):
        """
        Removes a friendship from the database.

        :param user_id: Account ID of the user.
        :param friend_id: Account ID of the friend to be removed.
        """
        # Error checking because we're not barbarians
        if user_id == friend_id:
            raise ValueError("Can't unfriend oneself, even though you might want to after this.")

        # Find and delete the primary friendship
        primary_friendship = self.session.query(FriendsList).filter_by(friendRegistryID = user_id, friendsaccountID = friend_id).one_or_none()
        if primary_friendship:
            self.session.delete(primary_friendship)
            log.debug(f"Deleted primary friendship: {user_id} -> {friend_id}")
        else:
            log.debug(f"Primary friendship not found: {user_id} -> {friend_id}")
            return False

        # Commit changes because we're not indecisive
        self.session.commit()

        return True  # "Friendship and its shadow have been eradicated. Hope it was worth it."

    def get_user_nickname(self, accountid):
        """
        Retrieve the nickname of a friend from the Friends table.

        :param accountid: The ID of the friend.
        :return: Nickname of the friend or None if not found.
        """
        friend_record = self.session.query(FriendsRegistry).filter_by(accountID = accountid).first()
        if friend_record:
            return str(friend_record.nickname)
        else:
            #we grab the username from userregistry table
            userreg_record = self.session.query(self.UserRegistry).filter_by(UniqueID = accountid).first()
            return str(userreg_record.UniqueUserName)

    def add_chat_history_entry(self, from_userid, to_userid, message, acked = 0):
        """
        Adds a chat entry to the FriendsChatHistory table.

        :param from_userid: User ID of the message sender
        :param to_userid: User ID of the message receiver
        :param message: Content of the message
        :param acked: Acknowledgement status, defaults to 0
        """
        new_chat_entry = FriendsChatHistory(
                from_accountID = from_userid,
                to_accountID = to_userid,
                datetime = datetime.now().strftime('%m/%d/%Y %H:%M:%S'),  # Current date and time as a string
                message = message,
                acked = acked
        )
        self.session.add(new_chat_entry)
        self.session.commit()

    def retrieve_chat_history(self, from_accountid, to_accountid):
        """
        Retrieves all chat history entries between two user IDs.

        :param from_accountid: The account ID of the message sender
        :param to_accountid: The account ID of the message receiver
        :return: A list of FriendsChatHistory objects
        """
        chat_entries = self.session.query(FriendsChatHistory).filter_by(
            from_accountID=from_accountid,
            to_accountID=to_accountid
        ).all()
        return chat_entries

    ##################
    # Games Played History
    ##################
    def get_all_play_histories(self, accountID):
        """ Retrieves all play history records for a specific user """
        histories = self.session.query(FriendsPlayHistory).filter_by(friendRegistryID=accountID).all()
        return histories

    def add_play_history(self, accountID, processID = None, appID = None, name = '', serverID = None,
            server_ip = None, server_port = None, game_data = None, token_crc = None,
            vr_hmd_vendor = '', vr_hmd_model = '', launch_option_type = None,
            vr_hmd_runtime = None, controller_connection_type = None, end_datetime = None):
        """ Adds a play history record for a user and updates the currently_playing field """
        new_play_history = FriendsPlayHistory(
                friendRegistryID = accountID,
                processID = processID,
                appID = appID,
                name = name,
                serverID = serverID,
                server_ip = server_ip,
                server_port = server_port,
                game_data = game_data,
                token_crc = token_crc,
                vr_hmd_vendor = vr_hmd_vendor,
                vr_hmd_model = vr_hmd_model,
                launch_option_type = launch_option_type,
                vr_hmd_runtime = vr_hmd_runtime,
                controller_connection_type = controller_connection_type,
                start_datetime = datetime.now(),
                end_datetime = end_datetime
        )
        self.session.add(new_play_history)
        self.session.flush()  # Ensures new_play_history gets an ID

        # Update currently_playing in FriendsRegistry
        friend_registry = self.session.query(FriendsRegistry).filter_by(accountID = accountID).first()
        if friend_registry:
            friend_registry.currently_playing = new_play_history.UniqueID
        self.session.commit()

    def exiting_app(self, accountID):
        """
        Updates the currently playing status for a user by setting the end_datetime of the
        associated FriendsPlayHistory entry and resetting currently_playing to None.

        :param accountID: The account ID of the user.
        """
        # Fetch the user's current playing details from FriendsRegistry
        user = self.session.query(FriendsRegistry).filter_by(accountID=accountID).first()
        if user and user.currently_playing:
            # Fetch the FriendsPlayHistory entry that is currently active
            currently_playing_entry = self.session.query(FriendsPlayHistory).filter_by(
                UniqueID=user.currently_playing).first()

            if currently_playing_entry:
                # Update the end_datetime to the current datetime
                currently_playing_entry.end_datetime = datetime.now()

                # Reset the currently_playing field in FriendsRegistry
                user.currently_playing = None

                # Commit changes to the database
                self.session.commit()
                return True
            else:
                return False
        else:
            return False

    ##################
    # VAC Related
    ##################
    def get_vacban_by_userid(self, accountID):
        current_time = datetime.now()

        # Fetch all VAC bans for the given user ID
        vac_bans = self.session.query(VACBans).filter(VACBans.friendRegistryID == accountID).all()

        if not vac_bans:
            return None  # No VAC bans found for the user

        active_ban_details = []
        for ban in vac_bans:
            # Calculate the end time of the ban based on the start time and length of the ban
            end_time = ban.starttime + timedelta(hours = ban.length_of_ban)

            # Check if the current time is still within the ban duration
            if current_time < end_time:
                active_ban_details.append((ban.firstappid, ban.lastappid))
            else:
                # Optionally remove expired bans from the database
                self.session.delete(ban)

        # Commit any changes to the database if bans were removed
        if len(active_ban_details) != len(vac_bans):
            self.session.commit()

        return active_ban_details

    ##################
    # Inventory
    ##################
    def get_all_inventory_items(self, accountID):
        """ Returns all inventory items for a specific user using relationships """
        friend_registry = self.session.query(FriendsRegistry).filter_by(accountID=accountID).first()
        return friend_registry.inventory_items if friend_registry else []

    def get_all_inventory_items_by_appid(self, accountID, appID):
        """ Returns all inventory items for a specific user and specific appID using relationships """
        items = self.session.query(ClientInventoryItems).join(FriendsRegistry).filter(
            FriendsRegistry.accountID == accountID,
            ClientInventoryItems.appID == appID
        ).all()
        return items

    def add_inventory_item(self, accountID, itemID=None, appID=None, quantity=None,
                           acquired=None, price=None, state='', transactionID=None,
                           origin='', original_itemID=None, position=None, trade_after_datetime=''):
        """ Adds an inventory item with optional parameters using relationships """
        friend_registry = self.session.query(FriendsRegistry).filter_by(accountID=accountID).first()
        if friend_registry:
            new_item = ClientInventoryItems(
                itemID=itemID,
                appID=appID,
                quantity=quantity,
                acquired=acquired,
                price=price,
                state=state,
                transactionID=transactionID,
                origin=origin,
                original_itemID=original_itemID,
                position=position,
                trade_after_datetime=trade_after_datetime,
                owner=friend_registry  # Linking via relationship
            )
            self.session.add(new_item)
            self.session.commit()

    def delete_inventory_item(self, accountID, appID, uniqueID):
        """ Deletes a specific inventory item for a user based on UniqueID, accountID, and appID """
        item = self.session.query(ClientInventoryItems).filter(
            ClientInventoryItems.UniqueID == uniqueID,
            ClientInventoryItems.friendRegistryID == accountID,
            ClientInventoryItems.appID == appID
        ).first()
        if item:
            self.session.delete(item)
            self.session.commit()

    def delete_all_inventory_items_by_appid(self, accountID, appID):
        """ Deletes all inventory items for a specific user for a specific appID """
        items = self.session.query(ClientInventoryItems).filter(
            ClientInventoryItems.friendRegistryID == accountID,
            ClientInventoryItems.appID == appID
        ).all()
        for item in items:
            self.session.delete(item)
        self.session.commit()

    ##################
    # Groups
    ##################
    def get_all_users_groups(self, accountID):
        friend_entry = self.session.query(FriendsRegistry).filter_by(friendRegistryID = accountID).first()

        if friend_entry:
            owned_groups = friend_entry.groups_owned
            for group in owned_groups:
                print(group.name)  # Example attribute, adjust based on your FriendsGroups model
        else:
            log.debug(f"[get_all_users_groups] No groups found for user {accountID}.")

    def get_user_groups(self, accountID):
        """
        Fetches all groups that a specific user is a member of.

        :param accountID: The account ID of the user.
        :return: A list of dictionaries, each representing a group the user is a member of.
        """
        # Query FriendsGroupMembers to find all group memberships for the given accountID
        memberships = self.session.query(FriendsGroupMembers).filter(FriendsGroupMembers.friendRegistryID == accountID).all()

        # Collect all group IDs from memberships
        group_ids = [membership.GroupID for membership in memberships]

        # Ensure group_ids is not empty to avoid errors in the query
        if not group_ids:
            return []  # Return an empty list if no groups found

        # Query FriendsGroups to retrieve the groups details
        groups = self.session.query(FriendsGroups).filter(FriendsGroups.UniqueID.in_(group_ids)).all()

        return groups #[self.group_to_dict(group) for group in groups]

    def remove_user_from_group(self, accountID, groupID):
        """
        Removes a user from a group specified by accountID and groupID.

        :param accountID: The account ID of the user to be removed.
        :param groupID: The ID of the group from which the user is to be removed.
        """
        # Find the group membership entry for the user
        membership = self.session.query(FriendsGroupMembers).filter_by(
            friendRegistryID=accountID, GroupID=groupID).first()

        if membership:
            self.session.delete(membership)
            self.session.commit()
            return {"status": "success", "message": "User removed from group successfully."}
        else:
            return {"status": "error", "message": "Membership not found."}

    ##################
    # Chat History
    ##################
    def get_chat_history(self, accountID, friendsaccountID):
        """
        Retrieves all chat history entries for interactions between two specific users.

        :param accountID: The account ID of the user.
        :param friendsaccountID: The account ID of the friend.
        :return: A list of dictionaries, each representing a chat history entry.
        """
        # Fetch all relevant chat history entries
        chat_histories = self.session.query(FriendsChatHistory).filter(
            or_(
                and_(FriendsChatHistory.from_accountID == accountID, FriendsChatHistory.to_accountID == friendsaccountID),
                and_(FriendsChatHistory.from_accountID == friendsaccountID, FriendsChatHistory.to_accountID == accountID)
            )
        ).all()

        # Convert each entry to a dictionary
        return [self.chat_to_dict(chat) for chat in chat_histories]

    def chat_to_dict(self, chat):
        """
        Converts a FriendsChatHistory object into a dictionary.

        :param chat: A FriendsChatHistory object.
        :return: A dictionary representation of the chat history entry.
        """
        return {
            'UniqueID': chat.UniqueID,
            'from_accountID': chat.from_accountID,
            'to_accountID': chat.to_accountID,
            'datetime': chat.datetime,
            'message': chat.message,
            'acked': chat.acked
        }

    ##################
    # Chatrooms
    ##################

    ##################
    # Grab User Relationships
    ##################
    # example: data = db_driver.get_user_related_data(1, ['play_history', 'inventory_items'])
    def get_user_related_data(self, accountID, relationships):
        """
        Fetches specified relationship data for a given user.

        :param accountID: The account ID of the user in FriendsRegistry.
        :param relationships: List of relationship keys to fetch (e.g., 'play_history', 'inventory_items').
        :return: A dictionary containing the requested relationship data.
        """
        # Fetch the user's FriendsRegistry entry
        user = self.session.query(FriendsRegistry).filter_by(accountID = accountID).first()
        if not user:
            return {}  # Return an empty dict if user is not found

        related_data = {}
        for relation in relationships:
            # Access the relationship attribute if it exists in the user model
            if hasattr(user, relation):
                related_data[relation] = getattr(user, relation)

        # Convert relationship data to a dictionary format, assuming it's a list of SQLA objects
        for key, value in related_data.items():
            if isinstance(value, list):  # If the relationship data is a list of objects
                related_data[key] = [self.object_to_dict(obj) for obj in value]
            else:
                related_data[key] = self.object_to_dict(value)

        return related_data

    def object_to_dict(self, obj):
        """
        Utility method to convert a SQLAlchemy row object to a dictionary.
        """
        if obj is None:
            return None
        return {c.name:getattr(obj, c.name) for c in obj.__table__.columns}

    ##################
    # Purchases and Gift/Guest Passes
    ##################

    def check_user_owns_app(self, user_id, app_id):
        try:
            # Get all subscription IDs for the user (excluding SubscriptionID 0)
            subscriptions = self.session.query(base_dbdriver.AccountSubscriptionsRecord.SubscriptionID).filter(
                and_(
                    base_dbdriver.AccountSubscriptionsRecord.UserRegistry_UniqueID == user_id,
                    base_dbdriver.AccountSubscriptionsRecord.SubscriptionID != 0
                )
            ).all()

            subscription_ids = [sub.SubscriptionID for sub in subscriptions]

            # Check if any subscription's AppList contains the app_id
            for sub_id in subscription_ids:
                steam_sub_app = self.session.query(base_dbdriver.SteamSubApps).filter(
                    base_dbdriver.SteamSubApps.SteamSubscriptions_SubscriptionID == sub_id
                ).first()

                if steam_sub_app and steam_sub_app.AppList:
                    app_list = steam_sub_app.AppList.split(',')
                    if str(app_id) in app_list:
                        return EResult.OK

            return EResult.Fail
        except SQLAlchemyError as e:
            log.error(f"[check_user_owns_app] Database error: {e}")
            return EResult.Fail

    def check_and_update_ownership_ticket(self, user_id, app_id, app_ownership_ticket):
        try:
            # Search for a matching entry
            existing_ticket = self.session.query(AppOwnershipTicketRegistry).filter(
                and_(
                    AppOwnershipTicketRegistry.accountID == user_id,
                    AppOwnershipTicketRegistry.appID == app_id
                )
            ).first()

            current_time = datetime.now()

            if existing_ticket:
                # Check if the ticket has expired
                if existing_ticket.TimeExpiration < current_time:
                    # Delete the expired ticket
                    self.session.delete(existing_ticket)
                    self.session.commit()

                    # Insert the new ticket
                    new_ticket = AppOwnershipTicketRegistry(
                        accountID=user_id,
                        ticket_version=app_ownership_ticket.ticket_version,
                        flags=app_ownership_ticket.flags,
                        TimeCreated=current_time,
                        TimeExpiration=app_ownership_ticket.time_expire
                    )
                    self.session.add(new_ticket)
                    self.session.commit()
                    return False
                else:
                    # Ticket is valid, return the serialized data
                    app_ownership_ticket.ticket_version = existing_ticket.ticket_version
                    app_ownership_ticket.flags = existing_ticket.flags
                    app_ownership_ticket.time_created = existing_ticket.TimeCreated
                    app_ownership_ticket.time_expire = existing_ticket.TimeExpiration
                    return app_ownership_ticket
            else:
                # No entry exists, insert the new ticket
                new_ticket = AppOwnershipTicketRegistry(
                    accountID=user_id,
                    ticket_version=app_ownership_ticket.ticket_version,
                    flags=app_ownership_ticket.flags,
                    TimeCreated=current_time,
                    TimeExpiration=app_ownership_ticket.time_expire
                )
                self.session.add(new_ticket)
                self.session.commit()
                return False

        except SQLAlchemyError as e:
            log.error(f"[check_and_update_ownership_ticket] Database error: {e}")
            self.session.rollback()
            return False

    def get_non_subscribed_friends(self, steamids, subscriptionid):
        """
        Check which steamids from the friend list do not have the given subscription ID.

        :param steamids: List of steam IDs from the client object's friend list.
        :param subscriptionid: Subscription ID to check against.
        :return: List of steam IDs that do not have the given subscription ID.
        """
        result = []
        try:
            for steamid in steamids:
                # Check if the steamid and subscriptionid exist in the table
                user = self.session.query(base_dbdriver.AccountSubscriptionsRecord.UserRegistry_UniqueID).filter(
                        base_dbdriver.AccountSubscriptionsRecord.UserRegistry_UniqueID == steamid,
                        base_dbdriver.AccountSubscriptionsRecord.SubscriptionID == subscriptionid
                ).scalar()

                if user is None:
                    result.append(steamid)

        except Exception as e:
            log.error(f"[get_non_subscribed_friends] Error querying subscription records: {e}")

        return result

    def add_GuestPass(self, package_id, time_created, time_expiration, sent, acked, redeemed, recipient_address, sender_address, sender_name):

        try:
            new_entry = GuestPassRegistry(
                PackageID=package_id,
                TimeCreated=time_created,
                TimeExpiration=time_expiration,
                Sent=sent,
                Acked=acked,
                Redeemed=redeemed,
                RecipientAddress=recipient_address,
                SenderAddress=sender_address,
                SenderName=sender_name
            )
            self.session.add(new_entry)
            self.session.commit()
            print("[add_GuestPass] Entry added successfully.")
        except SQLAlchemyError as e:
            self.session.rollback()
            log.error(f"[add_GuestPass] Error adding entry: {e}")

    def get_GuestPass_by_accountid(self, account_id):

        try:
            entries = self.session.query(GuestPassRegistry).filter_by(PackageID=account_id).all()
            return entries
        except SQLAlchemyError as e:
            log.error(f"[get_GuestPass_by_accountid] Error retrieving entries: {e}")
            return []

    def update_GuestPass(self, gid, sent=None, acked=None, redeemed=None, recipient_address=None, sender_address=None, sender_name=None):

        try:
            entry = self.session.query(GuestPassRegistry).filter_by(GID=gid).first()
            if not entry:
                log.warning(f"[update_GuestPass] Entry not found for GID {gid}.")
                return

            if sent is not None:
                entry.Sent = sent
            if acked is not None:
                entry.Acked = acked
            if redeemed is not None:
                entry.Redeemed = redeemed
            if recipient_address is not None:
                entry.RecipientAddress = recipient_address
            if sender_address is not None:
                entry.SenderAddress = sender_address
            if sender_name is not None:
                entry.SenderName = sender_name

            self.session.commit()
            log.debug(f"[update_GuestPass] Entry updated successfully GID {gid}.")
        except SQLAlchemyError as e:
            self.session.rollback()
            log.error(f"[update_GuestPass] Error updating entry GID {gid}: {e}")

    def get_or_add_transaction_address(self, accountID, name, address1, address2, city, postcode, state, country_code, phone):
        try:
            # Check if an entry exists with all columns matching
            entry = self.session.query(Steam3TransactionAddressRecord).filter(
                and_(
                    Steam3TransactionAddressRecord.accountID == accountID,
                    Steam3TransactionAddressRecord.Name == name,
                    Steam3TransactionAddressRecord.Address1 == address1,
                    Steam3TransactionAddressRecord.Address2 == address2,
                    Steam3TransactionAddressRecord.City == city,
                    Steam3TransactionAddressRecord.PostCode == postcode,
                    Steam3TransactionAddressRecord.State == state,
                    Steam3TransactionAddressRecord.CountryCode == country_code,
                    Steam3TransactionAddressRecord.Phone == phone
                )
            ).first()

            if entry:
                # Return the UniqueID of the matched entry
                return entry.UniqueID
            else:
                # Add a new entry and return the UniqueID
                new_entry = Steam3TransactionAddressRecord(
                    accountID=accountID,
                    Name=name,
                    Address1=address1,
                    Address2=address2,
                    City=city,
                    PostCode=postcode,
                    State=state,
                    CountryCode=country_code,
                    Phone=phone
                )
                self.session.add(new_entry)
                self.session.commit()
                return new_entry.UniqueID
        except:
            return 0

    def get_or_add_cc_record(self, accountID, card_type, card_number, card_holder_name, card_exp_year, card_exp_month, card_cvv2, addressEntryID):
        try:
            # Check if an entry exists with all columns matching
            entry = self.session.query(Steam3CCRecord).filter(
                and_(
                    Steam3CCRecord.accountID == accountID,
                    Steam3CCRecord.CardType == card_type,
                    Steam3CCRecord.CardNumber == card_number,
                    Steam3CCRecord.CardHolderName == card_holder_name,
                    Steam3CCRecord.CardExpYear == card_exp_year,
                    Steam3CCRecord.CardExpMonth == card_exp_month,
                    Steam3CCRecord.CardCVV2 == card_cvv2,
                    Steam3CCRecord.BillingAddressEntryID == addressEntryID
                )
            ).first()

            if entry:
                # Return the UniqueID of the matched entry
                return entry.UniqueID
            else:
                # Add a new entry with the current date/time as a string for DateAdded
                current_time_str = datetime.now().strftime("%m/%d/%Y %H:%M:%S")
                new_entry = Steam3CCRecord(
                    accountID=accountID,
                    CardType=card_type,
                    CardNumber=card_number,
                    CardHolderName=card_holder_name,
                    CardExpYear=card_exp_year,
                    CardExpMonth=card_exp_month,
                    CardCVV2=card_cvv2,
                    DateAdded=current_time_str,
                    BillingAddressEntryID=addressEntryID
                )
                self.session.add(new_entry)
                self.session.commit()
                return new_entry.UniqueID
        except:
            return 0

    def get_cc_records_by_account(self, accountID):
        try:
            entries = self.session.query(Steam3CCRecord).filter_by(accountID = accountID).all()
            return entries
        except:
            return None

    def add_gift_transaction(self, sender_accountID, sub_id, giftee_email, giftee_account_id, gift_message, giftee_name, sentiment, signature):
        try:
            # Add a new entry with the current date/time as a string for DateAdded
            current_time_str = datetime.now().strftime("%m/%d/%Y %H:%M:%S")
            new_entry = Steam3GiftTransactionRecord(
                sender_accountID=sender_accountID,
                SubID=sub_id,
                GifteeEmail=giftee_email,
                GifteeAccountID=giftee_account_id,
                GiftMessage=gift_message,
                GifteeName=giftee_name,
                Sentiment=sentiment,
                Signature=signature,
                DateAdded=current_time_str
            )
            self.session.add(new_entry)
            self.session.commit()
            return new_entry.UniqueID
        except:
            return 0

    def add_external_purchase_info(self, accountID, packageID, transaction_type, transaction_data):
        try:
            # Add a new entry with the current date/time as a string for DateAdded
            current_time_str = datetime.now().strftime("%m/%d/%Y %H:%M:%S")
            new_entry = ExternalPurchaseInfoRecord(
                accountID=accountID,
                packageID=packageID,
                TransactionType=int(transaction_type),
                TransactionData=transaction_data,
                DateAdded=current_time_str
            )
            self.session.add(new_entry)
            self.session.commit()
            return new_entry.UniqueID
        except:
            return 0

    def add_steam3_transaction_record(self, accountID, transaction_type, transaction_entry_id, package_id, gift_unique_id, address_entry_id, base_cost, discounts, tax_cost, shipping_cost, shipping_entry_id, guest_passes_included):

        # Add a new entry with the current date/time as a string for TransactionDate
        current_time_str = datetime.now().strftime("%m/%d/%Y %H:%M:%S")
        if gift_unique_id:
            new_entry = Steam3TransactionsRecord(
                accountID=accountID,
                TransactionType=int(transaction_type),
                TransactionEntryID=transaction_entry_id,
                PackageID=package_id,
                GiftUniqueID=gift_unique_id,
                AddressEntryID=address_entry_id,
                TransactionDate=current_time_str,
                BaseCostInCents=base_cost,
                DiscountsInCents=discounts,
                TaxCostInCents=tax_cost,
                ShippingCostInCents=shipping_cost,
                ShippingEntryID=shipping_entry_id,
                GuestPasses_Included=guest_passes_included
            )
        else:
            new_entry = Steam3TransactionsRecord(
                accountID=accountID,
                TransactionType=int(transaction_type),
                TransactionEntryID=transaction_entry_id,
                PackageID=package_id,
                AddressEntryID=address_entry_id,
                TransactionDate=current_time_str,
                BaseCostInCents=base_cost,
                DiscountsInCents=discounts,
                TaxCostInCents=tax_cost,
                ShippingCostInCents=shipping_cost,
                ShippingEntryID=shipping_entry_id,
                GuestPasses_Included=guest_passes_included
            )
        self.session.add(new_entry)
        self.session.commit()
        return new_entry.UniqueID

    def update_steam3_transaction_completed(self, transactionID):
        #TODO:
        # Remove GiftTransactionRecord and add new entry to GuestPassRegistry If is Gift
        # Create GuestPassRegistry Entries for each guestpass_included subid/appid for registree
        # Add Entries for any Guest Passes that are included with a subscription to the giftee/requesting user
        try:
            entry = self.session.query(Steam3TransactionsRecord).filter_by(UniqueID=transactionID).first()
            if entry:
                entry.DateCompleted = datetime.now().strftime("%m/%d/%Y %H:%M:%S")
                self.session.commit()
                return entry.UniqueID
            else:
                return 0
        except:
            return 0

    def update_steam3_transaction_cancelled(self, accountID, transactionID):
        try:
            today = date.today()
            entry = self.session.query(Steam3TransactionsRecord).filter(
                    and_(
                            Steam3TransactionsRecord.accountID == accountID,
                            Steam3TransactionsRecord.UniqueID == transactionID,
                            Steam3TransactionsRecord.DateCompleted == None,
                            #func.date(Steam3TransactionsRecord.TransactionDate) == today
                    )
            ).first()
            if entry:
                # Update the DateCancelled
                entry.DateCancelled = datetime.now().strftime("%m/%d/%Y %H:%M:%S")

                # Remove the corresponding entry from Steam3GiftTransactionRecord if gift_unique_id is set
                # FIXME is this necessary? if we just put the cancellation date into the transaction, theses should just not be used at all
                #if entry.GiftUniqueID:
                #    gift_entry = self.session.query(Steam3GiftTransactionRecord).filter_by(UniqueID = entry.GiftUniqueID).first()
                #    if gift_entry:
                #        self.session.delete(gift_entry)

                self.session.commit()
                return True
            else:
                return False
        except:
            return False

    def get_transaction_entry_details(self, accountID, transactionID):
        """
        Retrieve a single entry from the Steam3TransactionsRecord table matching the accountID and transactionID,
        and fetch related entries from Steam3CCRecord, ExternalPurchaseInfoRecord, Steam3TransactionAddressRecord,
        and Steam3GiftTransactionRecord based on the transaction type and IDs.

        :param accountID: The account ID to match.
        :param transactionID: The transaction ID to match.
        :return: A tuple with the main transaction entry and related entries, or None if no match is found.
        """
        try:
            entry: Steam3TransactionsRecord = self.session.query(Steam3TransactionsRecord).filter(
                    Steam3TransactionsRecord.accountID == accountID,
                    Steam3TransactionsRecord.UniqueID == transactionID
            ).one()

            cc_entry: Steam3CCRecord = None
            external_purchase_entry: ExternalPurchaseInfoRecord = None
            address_entry: Steam3TransactionAddressRecord = None
            gift_entry: Steam3GiftTransactionRecord = None
            shipping_entry: Steam3TransactionAddressRecord = None

            if entry.TransactionType == 2:
                # Fetch the entry from Steam3CCRecord
                cc_entry = self.session.query(Steam3CCRecord).filter_by(UniqueID = entry.TransactionEntryID).first()

            elif entry.TransactionType == 4:
                # Fetch the entry from ExternalPurchaseInfoRecord
                external_purchase_entry = self.session.query(ExternalPurchaseInfoRecord).filter_by(UniqueID = entry.TransactionEntryID).first()

            if entry.AddressEntryID:
                # Fetch the entry from Steam3TransactionAddressRecord
                address_entry = self.session.query(Steam3TransactionAddressRecord).filter_by(UniqueID = entry.AddressEntryID).first()

            if entry.GiftUniqueID:
                # Fetch the entry from Steam3GiftTransactionRecord
                gift_entry = self.session.query(Steam3GiftTransactionRecord).filter_by(UniqueID = entry.GiftUniqueID).first()

            if entry.ShippingEntryID:
                # Fetch the entry from Steam3TransactionAddressRecord for shipping
                shipping_entry = self.session.query(Steam3TransactionAddressRecord).filter_by(UniqueID = entry.ShippingEntryID).first()

            return (entry, cc_entry, external_purchase_entry, address_entry, gift_entry, shipping_entry)

        except NoResultFound:
            return None
        except Exception as e:
            log.error(f"[get_transaction_entry_details] Error retrieving transaction entry {transactionID} details: {e}")
            return None

    def set_transaction_receipt_acknowledged(self, steamid, transactionID):
        try:
            transaction = self.session.query(Steam3TransactionsRecord).filter_by(UniqueID = transactionID, accountID = steamid).first()
            if transaction:
                transaction.DateAcknowledged = datetime.now()
                self.session.commit()
                log.debug(f"[set_transaction_receipt_acknowledged] Transaction {transactionID} acknowledged.")
            else:
                log.warning(f"set_transaction_receipt_acknowledged] Transaction {transactionID} not found.")
                return False
            return True
        except Exception as e:
            self.session.rollback()
            log.error(f"set_transaction_receipt_acknowledged] Error acknowledging transaction {transactionID}: {e}")
            return False

    def complete_transaction(self, steamid, transactionID):
        from steam3 import utilities
        # Get the current datetime
        current_time = datetime.now().strftime("%m/%d/%Y %H:%M:%S")

        # Retrieve the transaction record
        transaction = self.session.query(Steam3TransactionsRecord).filter_by(UniqueID=transactionID).first()
        if not transaction:
            return "Transaction not found"

        # Set DateCompleted for the transaction
        transaction.DateCompleted = current_time

        # Process GuestPasses_Included if any
        if transaction.GuestPasses_Included:
            package_ids = transaction.GuestPasses_Included.split(',')
            for package_id in package_ids:
                guest_pass = GuestPassRegistry(
                    GID=transaction.UniqueID,
                    PackageID=int(package_id),
                    TimeCreated=current_time,
                    TimeExpiration=utilities.add_time_to_current_uint32(days=68).strftime("%m/%d/%Y %H:%M:%S"),
                    SenderAccountID=transaction.accountID
                )
                self.session.add(guest_pass)

        # Check and process gift unique ID
        if transaction.GiftUniqueID and transaction.GiftUniqueID != 0:
            gift_record = self.session.query(Steam3GiftTransactionRecord).filter_by(UniqueID=transaction.GiftUniqueID).first()
            if gift_record:
                gift_record.DateCompleted = current_time
                # Duplicate the gift entry to GuestPassRegistry if needed
                new_guest_pass = GuestPassRegistry(
                    GID=gift_record.UniqueID,
                    PackageID=transaction.PackageID,
                    TimeCreated=current_time,
                    TimeExpiration=utilities.add_time_to_current_uint32(days=68).strftime("%m/%d/%Y %H:%M:%S"),
                    SenderAccountID=gift_record.sender_accountID
                )
                self.session.add(new_guest_pass)
                self.session.flush()  # This ensures the new entry gets a UniqueID assigned

                # Now set the GiftUniqueID to the new UniqueID from GuestPassRegistry
                transaction.GiftUniqueID = new_guest_pass.UniqueID

        # Commit changes to the database
        self.session.commit()
        return "Transaction completed successfully"

    def get_app_name(self, appid: int) -> bytes:
        """
        Retrieve the name of the application with the given AppID as a byte string.

        :param session: SQLAlchemy Session instance
        :param appid: The AppID to filter by.
        :return: The name of the application as a byte string, or an empty byte string if not found.
        """
        result = self.session.query(SteamApplications.Name).filter(SteamApplications.AppID == appid).scalar()
        return result.encode('latin-1') if result else b'\x00'