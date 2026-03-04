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
        # Store the session factory, not a single session instance
        # This allows us to create thread-safe sessions per operation
        self._session_factory = self.db_driver.get_session

        self.UserRegistry = None
        self.Friend = None
        self.FriendsList = None
        self.FriendsRegistry = None
        self.CommunityRegistry = None

    def _get_session(self):
        """Get a fresh session for thread-safe database operations."""
        return self._session_factory()

    def update_details(self, uid, username, firstname, lastname):
        session = self._get_session()
        try:
            # First, check if the nickname exists in FriendsRegistry and update there
            friends_record = session.query(self.FriendsRegistry).filter(self.FriendsRegistry.accountID == uid).first()
            community_record = session.query(self.CommunityRegistry).filter(self.CommunityRegistry.friendRegistryID == uid).first()

            if friends_record:
                friends_record.nickname = username  # Update nickname

            if community_record:
                community_record.real_name = f"{firstname.decode('utf-8')} {lastname.decode('utf-8')}".strip()

            session.commit()
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()

    def get_user_by_email(self, email):
        if isinstance(email, bytes):
            email = email.decode('latin-1')

        session = self._get_session()
        try:
            # First, query by email address, joining CommunityRegistry to get `real_name` fields
            user_data = (
                    session.query(
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
                    session.query(
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
        finally:
            session.close()

    def get_user_by_uid(self, uid):
        session = self._get_session()
        try:
            # Query both tables with a join on the `accountID` from `friends_registry` and `UniqueID` from `userregistry`
            user_data = (
                    session.query(
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
                log.warning(f"No user found for UID {uid}")
                return (0, "", "", "", "")
        finally:
            session.close()

    def search_users(self):
        session = self._get_session()
        try:
            # TODO do a real search, instead of just returning all users
            # Query joining UserRegistry and CommunityRegistry to get nickname as username
            user_data_rows = (
                    session.query(
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
        finally:
            session.close()

    def pending_friends(self, uid, isRetail):
        session = self._get_session()
        try:
            # Retrieve all entries where `friendRegistryID` matches `uid` and `relationship` is set to 2
            pending_friends_entries = session.query(self.FriendsList).filter_by(
                    friendRegistryID = uid, relationship = int(FriendRelationship.requestRecipient)
            ).all()
            # Return a list of friendsaccountIDs from the pending friend requests
            # Filter out any self-referential entries (should not exist, but defensive check)
            return [entry.friendsaccountID for entry in pending_friends_entries if entry.friendsaccountID != uid]
        finally:
            session.close()

    def real_friends(self, uid):
        session = self._get_session()
        try:
            # Retrieve all entries where `friendRegistryID` matches `uid` and `relationship` is set to 3
            real_friends_entries = session.query(self.FriendsList).filter_by(
                    friendRegistryID = uid, relationship = int(FriendRelationship.friend)
            ).all()

            # Return a list of friendsaccountIDs from the confirmed friends
            return [entry.friendsaccountID for entry in real_friends_entries]
        finally:
            session.close()

    def request_friend(self, source, target):
        # Prevent self-friend requests
        if source == target:
            log.warning(f"Rejected self-friend request from user {source}")
            return False

        session = self._get_session()
        try:
            # Check if a friendship entry already exists between source and target
            existing_friend_entry = session.query(self.FriendsList).filter_by(
                    friendRegistryID = source, friendsaccountID = target
            ).first()

            if not existing_friend_entry:
                # No existing relationship found, so create new entries
                new_friend = self.FriendsList(
                        friendRegistryID = source,
                        friendsaccountID = target,
                        relationship = 4  # Request initiator
                )
                session.add(new_friend)

            # NOTE: Do NOT manually create the inverse entry (target->source with relationship=2) here.
            # The inverse entry is created automatically by base_dbdriver.py via SQLAlchemy event triggers.

            # Commit the transaction to save changes
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            log.error(f"Error in request_friend: {e}")
            return False
        finally:
            session.close()

    def remove_friend(self, user_id, friend_id):
        """
        Removes a friendship from the database, including the inverse entry.

        :param user_id: Account ID of the user.
        :param friend_id: Account ID of the friend to be removed.
        """
        # Error checking because we're not barbarians
        if user_id == friend_id:
            raise ValueError("Can't unfriend oneself, even though you might want to after this.")

        session = self._get_session()
        try:
            # Find and delete the primary friendship
            primary_friendship = session.query(self.FriendsList).filter_by(friendRegistryID = user_id, friendsaccountID = friend_id).one_or_none()
            if primary_friendship:
                session.delete(primary_friendship)
                log.debug(f"Deleted primary friendship: {user_id} -> {friend_id}")
            else:
                log.debug(f"Primary friendship not found: {user_id} -> {friend_id}")

            # Find and delete the inverse friendship
            inverse_friendship = session.query(self.FriendsList).filter_by(friendRegistryID = friend_id, friendsaccountID = user_id).one_or_none()
            if inverse_friendship:
                session.delete(inverse_friendship)
                log.debug(f"Deleted inverse friendship: {friend_id} -> {user_id}")
            else:
                log.debug(f"Inverse friendship not found: {friend_id} -> {user_id}")

            # Commit changes because we're not indecisive
            session.commit()

            return True  # "Friendship and its shadow have been eradicated. Hope it was worth it."
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()

    def accept_friend_request(self, source, target):
        # Prevent accepting self-friend requests
        if source == target:
            log.warning(f"Rejected self-friend acceptance from user {source}")
            return False

        session = self._get_session()
        try:
            # Find the existing friend request from `source` to `target` (the initiator's entry)
            friend_request_entry = session.query(self.FriendsList).filter_by(
                    friendRegistryID = source, friendsaccountID = target, relationship = 2
            ).first()
            inverse_friend_request_entry = session.query(self.FriendsList).filter_by(
                    friendsaccountID = source, friendRegistryID = target, relationship = 4
            ).first()
            if friend_request_entry and inverse_friend_request_entry:
                # Update the relationship status to `3` (accepted friendship)
                friend_request_entry.relationship = 3
                inverse_friend_request_entry.relationship = 3
                # Commit to save the change and trigger the after_update event
                session.commit()
                return True
            else:
                # No pending request found
                return False
        except Exception as e:
            session.rollback()
            log.error(f"Error in accept_friend_request: {e}")
            return False
        finally:
            session.close()

    """def deny_friend_request(self, sourceid, targetid):
        # Update status to 'none' for both source->target and target->source entries
        session.query(self.Friend).filter(self.Friend.source == sourceid, self.Friend.target == targetid).update({"relationship":0})"""

    def get_friends_by_source(self, uid):
        session = self._get_session()
        try:
            # Query FriendsList for entries where friendRegistryID is uid and relationship is 3
            result = session.query(self.FriendsList).filter(
                    self.FriendsList.friendRegistryID == uid,
                    self.FriendsList.relationship == 3
            ).all()
            return [friend.friendsaccountID for friend in result]  # Return friendsaccountID as target
        finally:
            session.close()

    def get_friends_by_target(self, uid):
        session = self._get_session()
        try:
            # Query FriendsList for entries where friendsaccountID is uid and relationship is 3
            result = session.query(self.FriendsList).filter(
                    self.FriendsList.friendsaccountID == uid,
                    self.FriendsList.relationship == 3
            ).all()
            return [friend.friendRegistryID for friend in result]  # Return friendRegistryID as source
        finally:
            session.close()


class beta2_dbdriver(base_beta_dbdriver):

    def __init__(self, config):
        super().__init__(config)
        self.UserRegistry = base_dbdriver.UserRegistry
        self.FriendsRegistry = base_dbdriver.FriendsRegistry
        self.FriendsList = base_dbdriver.FriendsList
        self.CommunityRegistry = base_dbdriver.CommunityRegistry

    def auth(self, email, username):
        session = self._get_session()
        try:
            # Fetch the user record by email
            userrecord_dbdata = session.query(self.UserRegistry).filter(self.UserRegistry.AccountEmailAddress == email).first()

            # If the email does not exist, try the uniqueusername or else log an error
            if userrecord_dbdata is None:
                userrecord_dbdata = session.query(self.UserRegistry).filter(self.UserRegistry.UniqueUserName == email).first()
                if userrecord_dbdata is None:
                    log.error(f"{email} or {username} does not exist!")
                    return False

            # Retrieve the FriendsRegistry record using the UniqueID from UserRegistry
            friends_record = session.query(self.FriendsRegistry).filter(self.FriendsRegistry.accountID == userrecord_dbdata.UniqueID).first()

            if friends_record:
                # Update the last_login time to the current time
                friends_record.last_login = datetime.now()

            # Commit the changes to the database
            session.commit()
            log.info(f"Updated TrackerUserName for user with email {email}")

            log.info(f"Found existing user with email {email}")
            return userrecord_dbdata.UniqueID  # Assuming UniqueID is what you intend to return
        except Exception as e:
            # Handle exception, possibly rolling back the transaction and logging an error
            session.rollback()
            log.error(f"Failed to update TrackerUserName for user with email {email}: {e}")
            return False
        finally:
            session.close()


class beta1_dbdriver(base_beta_dbdriver):
    def __init__(self, config):
        super().__init__(config)
        self.Beta1_TrackerUserRegistry = Beta1_TrackerRegistry
        self.Friend = Beta1_Friendslist

    def create_user(self, username, email, firstname, lastname, password):
        session = self._get_session()
        try:
            if session.query(self.Beta1_TrackerUserRegistry).filter_by(email = email).first() is not None:
                return False
            new_user = self.Beta1_TrackerUserRegistry(username = username, email = email, firstname = firstname, lastname = lastname, password = password)
            session.add(new_user)
            session.commit()
            return new_user.uniqueid  # Return the uniqueid of the new user
        except IntegrityError:
            session.rollback()
            return False
        finally:
            session.close()

    def auth(self, auth_var, password, isbeta1 = False):
        session = self._get_session()
        try:
            if isinstance(auth_var, int):
                auth_record = session.query(self.Beta1_TrackerUserRegistry).filter_by(uniqueid = auth_var, password = password).first()
                if auth_record is None:
                    return None
                if isbeta1:
                    return auth_record.email
                else:
                    return auth_record.username if auth_record.username is not None else None
            else:
                auth_record = session.query(self.Beta1_TrackerUserRegistry).filter_by(email = auth_var, password = password).first()
                if auth_record is None:
                    return None
                return auth_record.uniqueid if auth_record.uniqueid is not None else None
        finally:
            session.close()

    def get_user_by_uid(self, uid):
        session = self._get_session()
        try:
            userrecord_dbdata = session.query(self.Beta1_TrackerUserRegistry).filter_by(uniqueid = uid).first()

            if userrecord_dbdata:
                user_id = userrecord_dbdata.uniqueid
                user_email = userrecord_dbdata.email
                user_username = userrecord_dbdata.username
                user_firstname = userrecord_dbdata.firstname
                user_lastname = userrecord_dbdata.lastname
                return (user_id, user_email, user_username, user_firstname, user_lastname)
            else:
                return None
        finally:
            session.close()

    def real_friends(self, uid):
        # Beta1: confirmed friends have bi-directional entries (source->target AND target->source)
        session = self._get_session()
        try:
            entries = session.query(self.Friend).filter_by(source=uid).all()
            friends = []
            for entry in entries:
                # Check if reverse entry exists (confirmed friend)
                reverse = session.query(self.Friend).filter_by(source=entry.target, target=uid).first()
                if reverse:
                    friends.append(entry.target)
            return friends
        finally:
            session.close()

    def search_users(self):
        # Query Beta1_TrackerUserRegistry for all users
        # Returns (uniqueid, email, username, firstname, lastname) to match beta1_user_search expectations
        session = self._get_session()
        try:
            user_data_rows = session.query(self.Beta1_TrackerUserRegistry).all()
            return [
                (user.uniqueid, user.email, user.username, user.firstname, user.lastname)
                for user in user_data_rows
            ]
        finally:
            session.close()

    def pending_friends(self, uid, isRetail):
        # Beta1: pending = source->target exists but target->source doesn't
        # Find entries where we are the target (someone requested us)
        # but we haven't added them back (no reverse entry)
        session = self._get_session()
        try:
            # Get all entries where someone has us as target
            incoming = session.query(self.Friend).filter_by(target=uid).all()
            pending = []
            for entry in incoming:
                # Check if reverse entry exists (we accepted)
                reverse = session.query(self.Friend).filter_by(source=uid, target=entry.source).first()
                if not reverse:
                    pending.append(entry.source)
            return pending
        finally:
            session.close()

    def get_friends_by_source(self, uid):
        # Beta1: return all targets where source=uid and bi-directional (confirmed friends)
        session = self._get_session()
        try:
            entries = session.query(self.Friend).filter_by(source=uid).all()
            friends = []
            for entry in entries:
                # Check if reverse entry exists (confirmed friend)
                reverse = session.query(self.Friend).filter_by(source=entry.target, target=uid).first()
                if reverse:
                    friends.append(entry.target)
            return friends
        finally:
            session.close()

    def get_friends_by_target(self, uid):
        # Beta1: return all sources where target=uid and bi-directional (confirmed friends)
        session = self._get_session()
        try:
            entries = session.query(self.Friend).filter_by(target=uid).all()
            friends = []
            for entry in entries:
                # Check if reverse entry exists (confirmed friend)
                reverse = session.query(self.Friend).filter_by(source=uid, target=entry.source).first()
                if reverse:
                    friends.append(entry.source)
            return friends
        finally:
            session.close()

    def update_details(self, uid, username, firstname, lastname):
        # Beta1: update Beta1_TrackerUserRegistry directly
        session = self._get_session()
        try:
            user_record = session.query(self.Beta1_TrackerUserRegistry).filter_by(uniqueid=uid).first()
            if user_record:
                if isinstance(username, bytes):
                    username = username.decode('utf-8')
                if isinstance(firstname, bytes):
                    firstname = firstname.decode('utf-8')
                if isinstance(lastname, bytes):
                    lastname = lastname.decode('utf-8')
                user_record.username = username
                user_record.firstname = firstname
                user_record.lastname = lastname
                session.commit()
        finally:
            session.close()

    def request_friend(self, source, target):
        # Beta1: add source->target entry (one-way = pending request)
        session = self._get_session()
        try:
            existing = session.query(self.Friend).filter_by(source=source, target=target).first()
            if not existing:
                new_friend = self.Friend(source=source, target=target)
                session.add(new_friend)
                session.commit()
            return True
        finally:
            session.close()

    def accept_friend_request(self, source, target):
        # Beta1: source is accepting request from target
        # Check that target->source exists (they requested us)
        # Then add source->target (we accept by adding reverse entry)
        session = self._get_session()
        try:
            # Check if target requested us
            request_entry = session.query(self.Friend).filter_by(source=target, target=source).first()
            if request_entry:
                # Add our acceptance (reverse entry)
                existing = session.query(self.Friend).filter_by(source=source, target=target).first()
                if not existing:
                    new_friend = self.Friend(source=source, target=target)
                    session.add(new_friend)
                    session.commit()
                return True
            return False
        finally:
            session.close()