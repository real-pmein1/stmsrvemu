import logging
from enum import IntEnum
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

import globalvars
from utilities.database import base_dbdriver, dbengine
from utilities.database.base_dbdriver import Beta1_Friendslist, Beta1_TrackerRegistry

log = logging.getLogger('TRKRDB')

class FriendRelationship(IntEnum):
    blocked = 0
    blockedfriend = 1
    requestRecipient = 2
    friend = 3
    requestInitiator = 4

class base_beta_dbdriver:
    def __init__(self, config):
        while globalvars.mariadb_initialized != True:
            continue
        self.db_driver = dbengine.create_database_driver()
        self.db_driver.connect()
        self.session = self.db_driver.get_session()

        self.UserRegistry = None
        self.Friend = None
        self.FriendsList = None
        self.FriendsRegistry = None
        self.CommunityRegistry = None

    def update_details(self, uid, username, firstname, lastname):
        # First, check if the nickname exists in FriendsRegistry and update there
        friends_record = self.session.query(self.FriendsRegistry).filter(self.FriendsRegistry.accountID == uid).first()
        community_record = self.session.query(self.CommunityRegistry).filter(self.CommunityRegistry.friendRegistryID == uid).first()

        if friends_record:
            friends_record.nickname = username  # Update nickname

        if community_record:
            community_record.real_name =  f"{firstname.decode('utf-8')} {lastname.decode('utf-8')}".strip()

        self.session.commit()

    def get_user_by_email(self, email):
        if isinstance(email, bytes):
            email = email.decode('latin-1')

        # First, query by email address, joining CommunityRegistry to get `real_name` fields
        user_data = (
                self.session.query(
                        self.UserRegistry.UniqueID,
                        self.UserRegistry.AccountEmailAddress,
                        self.FriendsRegistry.nickname,
                        self.CommunityRegistry.real_name
                )
                .join(self.FriendsRegistry, self.FriendsRegistry.accountID == self.UserRegistry.UniqueID)
                .join(self.CommunityRegistry, self.CommunityRegistry.friendRegistryID == self.FriendsRegistry.accountID)
                .filter(self.UserRegistry.AccountEmailAddress == email)
                .first()
        )

        if user_data:
            user_id, user_email, user_nickname, user_real_name = user_data
            firstname, lastname = (user_real_name.split(" ", 1) + [""])[:2]  # Split into first and last name
            return (user_id, user_email, user_nickname, firstname, lastname)

        # If no match by email, attempt to find by `UniqueUserName`
        user_data = (
                self.session.query(
                        self.UserRegistry.UniqueID,
                        self.UserRegistry.AccountEmailAddress,
                        self.FriendsRegistry.nickname,
                        self.CommunityRegistry.real_name
                )
                .join(self.FriendsRegistry, self.FriendsRegistry.accountID == self.UserRegistry.UniqueID)
                .join(self.CommunityRegistry, self.CommunityRegistry.friendRegistryID == self.FriendsRegistry.accountID)
                .filter(self.UserRegistry.UniqueUserName == email)
                .first()
        )

        if user_data:
            user_id, user_email, user_nickname, user_real_name = user_data
            firstname, lastname = (user_real_name.split(" ", 1) + [""])[:2]
            return (user_id, user_email, user_nickname, firstname, lastname)

        return None

    def get_user_by_uid(self, uid):
        # Query both tables with a join on the `accountID` from `friends_registry` and `UniqueID` from `userregistry`
        user_data = (
                self.session.query(
                        self.UserRegistry.UniqueID,
                        self.UserRegistry.AccountEmailAddress,
                        self.FriendsRegistry.nickname,
                        self.CommunityRegistry.real_name
                )
                .join(self.FriendsRegistry, self.FriendsRegistry.accountID == self.UserRegistry.UniqueID)
                .join(self.CommunityRegistry, self.CommunityRegistry.friendRegistryID == self.FriendsRegistry.accountID)
                .filter(self.UserRegistry.UniqueID == uid)
                .first()
        )

        if user_data:
            user_id, user_email, user_username, user_real_name = user_data
            firstname, lastname = (user_real_name.split(" ", 1) + [""])[:2]
            return (user_id, user_email, user_username, firstname, lastname)
        else:
            print("No user found for the given UID.")
            return (0, "", "", "", "")

    def search_users(self):
        # TODO do a real search, instead of just returning all users
        # Query joining UserRegistry and CommunityRegistry to get nickname as username
        user_data_rows = (
                self.session.query(
                        self.UserRegistry.UniqueID,
                        self.FriendsRegistry.nickname,
                        self.CommunityRegistry.real_name
                )
                .join(self.FriendsRegistry, self.FriendsRegistry.accountID == self.UserRegistry.UniqueID)
                .join(self.CommunityRegistry, self.CommunityRegistry.friendRegistryID == self.FriendsRegistry.accountID)
                .all()
        )
        result = [
                (user.UniqueID, user.nickname, *(user.real_name.split(" ", 1) + [""])[:2])  # Split `real_name` into first and last names
                for user in user_data_rows
        ]
        return result

    def pending_friends(self, uid):
        # Retrieve all entries where `friendsaccountID` matches `uid` and `relationship` is set to 2
        pending_friends_entries = self.session.query(self.FriendsList).filter_by(
                friendRegistryID = uid, relationship = int(FriendRelationship.requestRecipient)
        ).all()

        # Return a list of friendRegistryIDs from the pending friend requests
        return [entry.friendRegistryID for entry in pending_friends_entries]

    def real_friends(self, uid):
        # Retrieve all entries where `friendRegistryID` matches `uid` and `relationship` is set to 3
        real_friends_entries = self.session.query(self.FriendsList).filter_by(
                friendRegistryID = uid, relationship = int(FriendRelationship.friend)
        ).all()

        # Return a list of friendsaccountIDs from the confirmed friends
        return [entry.friendsaccountID for entry in real_friends_entries]

    def request_friend(self, source, target):
        # Check if a friendship entry already exists between source and target
        existing_friend_entry = self.session.query(self.FriendsList).filter_by(
                friendRegistryID = source, friendsaccountID = target
        ).first()

        if not existing_friend_entry:
            # No existing relationship found, so create new entries
            new_friend = self.FriendsList(
                    friendRegistryID = source,
                    friendsaccountID = target,
                    relationship = 4  # Request initiator
            )
            self.session.add(new_friend)

        # Commit the transaction to save changes
        self.session.commit()
        return True

    def remove_friend(self, user_id, friend_id):
        """
        Removes a friendship from the database, including the inverse entry.

        :param user_id: Account ID of the user.
        :param friend_id: Account ID of the friend to be removed.
        """
        # Error checking because we're not barbarians
        if user_id == friend_id:
            raise ValueError("Can't unfriend oneself, even though you might want to after this.")

        # Find and delete the primary friendship
        primary_friendship = self.session.query(self.FriendsList).filter_by(friendRegistryID = user_id, friendsaccountID = friend_id).one_or_none()
        if primary_friendship:
            self.session.delete(primary_friendship)
            log.debug(f"Deleted primary friendship: {user_id} -> {friend_id}")
        else:
            log.debug(f"Primary friendship not found: {user_id} -> {friend_id}")

        # Find and delete the inverse friendship
        inverse_friendship = self.session.query(self.FriendsList).filter_by(friendRegistryID = friend_id, friendsaccountID = user_id).one_or_none()
        if inverse_friendship:
            self.session.delete(inverse_friendship)
            log.debug(f"Deleted inverse friendship: {friend_id} -> {user_id}")
        else:
            log.debug(f"Inverse friendship not found: {friend_id} -> {user_id}")

        # Commit changes because we're not indecisive
        self.session.commit()

        return True  # "Friendship and its shadow have been eradicated. Hope it was worth it."

    def accept_friend_request(self, source, target):
        # Find the existing friend request from `source` to `target` (the initiator's entry)
        friend_request_entry = self.session.query(self.FriendsList).filter_by(
                friendRegistryID = source, friendsaccountID = target, relationship = 2
        ).first()
        inverse_friend_request_entry = self.session.query(self.FriendsList).filter_by(
                friendsaccountID = source, friendRegistryID = target, relationship = 4
        ).first()
        if friend_request_entry:
            # Update the relationship status to `3` (accepted friendship)
            friend_request_entry.relationship = 3
            inverse_friend_request_entry.relationship = 3
            # Commit to save the change and trigger the after_update event
            self.session.commit()
            return True
        else:
            # No pending request found
            return False

    """def deny_friend_request(self, sourceid, targetid):
        # Update status to 'none' for both source->target and target->source entries
        self.session.query(self.Friend).filter(self.Friend.source == sourceid, self.Friend.target == targetid).update({"relationship":0})"""

    def get_friends_by_source(self, uid):
        # Query FriendsList for entries where friendRegistryID is uid and relationship is 3
        result = self.session.query(self.FriendsList).filter(
                self.FriendsList.friendRegistryID == uid,
                self.FriendsList.relationship == 3
        ).all()
        return [friend.friendsaccountID for friend in result]  # Return friendsaccountID as target

    def get_friends_by_target(self, uid):
        # Query FriendsList for entries where friendsaccountID is uid and relationship is 3
        result = self.session.query(self.FriendsList).filter(
                self.FriendsList.friendsaccountID == uid,
                self.FriendsList.relationship == 3
        ).all()
        return [friend.friendRegistryID for friend in result]  # Return friendRegistryID as source


class beta2_dbdriver(base_beta_dbdriver):

    def __init__(self, config):
        super().__init__(config)
        self.UserRegistry = base_dbdriver.UserRegistry
        self.FriendsRegistry = base_dbdriver.FriendsRegistry
        self.FriendsList = base_dbdriver.FriendsList
        self.CommunityRegistry = base_dbdriver.CommunityRegistry

    def auth(self, email, username):
        # Fetch the user record by email
        userrecord_dbdata = self.session.query(self.UserRegistry).filter(self.UserRegistry.AccountEmailAddress == email).first()

        # If the email does not exist, try the uniqueusername or else log an error
        if userrecord_dbdata is None:
            userrecord_dbdata = self.session.query(self.UserRegistry).filter(self.UserRegistry.UniqueUserName == email).first()
            if userrecord_dbdata is None:
                log.error(f"{email} or {username} does not exist!")
                return False

        # Retrieve the FriendsRegistry record using the UniqueID from UserRegistry
        friends_record = self.session.query(self.FriendsRegistry).filter(self.FriendsRegistry.accountID == userrecord_dbdata.UniqueID).first()

        if friends_record:
            # Update the last_login time to the current time
            friends_record.last_login = datetime.now()

        # Commit the changes to the database
        try:
            self.session.commit()
            log.info(f"Updated TrackerUserName for user with email {email}")
        except Exception as e:
            # Handle exception, possibly rolling back the transaction and logging an error
            self.session.rollback()
            log.error(f"Failed to update TrackerUserName for user with email {email}: {e}")
            return False

        log.info(f"Found existing user with email {email}")
        return userrecord_dbdata.UniqueID # Assuming UniqueID is what you intend to return


class beta1_dbdriver(base_beta_dbdriver):
    def __init__(self, config):
        super().__init__(config)
        self.Beta1_TrackerUserRegistry = Beta1_TrackerRegistry
        self.Friend = Beta1_Friendslist

    def create_user(self, username, email, firstname, lastname, password):
        if self.session.query(self.Beta1_TrackerUserRegistry).filter_by(email = email).first() is not None:
            self.session.close()
            return False
        new_user = self.Beta1_TrackerUserRegistry(username = username, email = email, firstname = firstname, lastname = lastname, password = password)
        self.session.add(new_user)
        try:
            self.session.commit()
            return new_user.uniqueid  # Return the uniqueid of the new user
        except IntegrityError:
            self.session.rollback()
            return False

    def auth(self, auth_var, password, isbeta1 = False):
        if isinstance(auth_var, int):
            auth_var = self.session.query(self.Beta1_TrackerUserRegistry).filter_by(uniqueid = auth_var, password = password).first()
            if isbeta1:
                return auth_var.email
            else:
                return auth_var.username if auth_var.username is not None else None
        else:
            auth_var = self.session.query(self.Beta1_TrackerUserRegistry).filter_by(email = auth_var, password = password).first()
            return auth_var.uniqueid if auth_var.uniqueid is not None else None

    def get_user_by_uid(self, uid):
        #print(f"userid: {uid_adjusted}")
        userrecord_dbdata = self.session.query(self.Beta1_TrackerUserRegistry).filter_by(uniqueid = uid).first()

        if userrecord_dbdata:
            user_id = userrecord_dbdata.uniqueid
            user_email = userrecord_dbdata.email
            user_username = userrecord_dbdata.username
            user_firstname = userrecord_dbdata.firstname
            user_lastname = userrecord_dbdata.lastname
            return (user_id, user_email, user_username, user_firstname, user_lastname)
        else:
            return None