import binascii
import hashlib
import json
import logging
import random
import string
from typing import Dict, List, Optional, Tuple, Any
import time
from datetime import date, datetime, timedelta

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session
from sqlalchemy.types import Integer
from sqlalchemy import Engine, and_, exists, func, or_, text
from sqlalchemy.exc import IntegrityError, MultipleResultsFound, NoResultFound, OperationalError, SQLAlchemyError

import globalvars
from steam3.Types.wrappers import AccountID, WrapperBase
from steam3.Types.chat_types import ChatMemberStatus
from steam3.Types.community_types import FriendRelationship, PlayerState
from steam3.Types.steam_types import ELeaderboardDataRequest as LeaderboardDataRequest, ELeaderboardSortMethod as LeaderboardSortMethod, ELeaderboardUploadScoreMethod as LeaderboardUploadScoreMethod
from steam3.Types.steam_types import EAccountFlags, EResult, EPurchaseResultDetail, EPaymentMethod, EType, EInstanceFlag, EUniverse
from steam3.Types.steamid import SteamID
from steam3.Types.chat_types import (
    ChatPermission, ChatRoomFlags, ChatAction, ChatActionResult,
    ChatRoomEnterResponse, ChatEntryType, ChatRelationship, ChatRoomType
)
from steam3.utilities import get_state_iso_code
from utilities.database import authdb, base_dbdriver, dbengine
from utilities.database.base_dbdriver import (
    AccountSubscriptionsRecord,
    AppOwnershipTicketRegistry,
    ChatRoomHistory,
    ChatRoomMembers,
    ChatRoomRegistry,
    ChatRoomSpeakers,
    ChatRoomGroup,
    ChatRoomGroupChat,
    ChatRoomGroupRole,
    ClientInventoryItems,
    PersistentItem,
    PersistentItemAttribute,
    CommunityClanMembers,
    CommunityClanRegistry,
    CommunityClanEvents,
    ClanPermissionTemplate,
    ClanEventAttendance,
    CommunityRegistry,
    CountryTax,
    ExternalPurchaseInfoRecord,
    FriendsChatHistory,
    FriendsGroupMembers,
    FriendsGroups,
    FriendsList,
    FriendsNameHistory,
    FriendsPlayHistory,
    FriendsRegistry,
    GuestPassRegistry,
    LeaderboardEntry,
    LeaderboardRegistry,
    LobbyRegistry,
    LobbyMembers,
    LobbyMetadata,
    LobbySearchView,
    StateSalesTax,
    Steam3CCRecord,
    Steam3LicenseRecord,
    Steam3TransactionAddressRecord,
    Steam3TransactionsRecord,
    SteamApplications,
    TransactionGuestPasses,
    UserAchievements,
    UserMachineIDRegistry,
    UserRegistry,
    UserStatsCache,
    UserStatsData,
    VACBans,
    LegacyGameKeys,
)
from utils import get_derived_appids
from utilities.database.purchase_db import PurchaseDatabase


log = logging.getLogger('CMDB')


# 1a) For all ORM queries (filter_by, session.query, etc.)
@event.listens_for(Session, "do_orm_execute")
def _unwrap_wrapperbase_do_orm_execute(execute_state):
    params = execute_state.parameters
    if not params:
        return
    if isinstance(params, dict):
        for k, v in params.items():
            if isinstance(v, WrapperBase):
                params[k] = int(v)
    else:
        # multiple sets (executemany)
        new = []
        for row in params:
            if isinstance(row, dict):
                for k, v in row.items():
                    if isinstance(v, WrapperBase):
                        row[k] = int(v)
                new.append(row)
            else:
                new_row = []
                for v in row:
                    new_row.append(int(v) if isinstance(v, WrapperBase) else v)
                new.append(tuple(new_row))
        execute_state.parameters = type(params)(new)

# 1b) For raw core SQL (Engine.execute, connection.execute, etc.)
@event.listens_for(Engine, "before_execute")
def _unwrap_wrapperbase_before_execute(conn, clauseelement, multiparams, params, execution_options):
    def unwrap(obj):
        if isinstance(obj, WrapperBase):
            return int(obj)
        return obj

    def process_paramset(paramset):
        if isinstance(paramset, dict):
            return {k: unwrap(v) for k, v in paramset.items()}
        elif isinstance(paramset, (list, tuple)):
            return type(paramset)(unwrap(v) for v in paramset)
        else:
            return paramset

    multiparams = [process_paramset(mp) for mp in multiparams] if multiparams else multiparams
    params      = process_paramset(params)   if params      else params
    return multiparams, params
def _unwrap_params(params):
    """
    Recursively replace any WrapperBase values in a dict or list/tuple
    with their int(v) equivalent.
    """
    if isinstance(params, dict):
        for k, v in params.items():
            if isinstance(v, WrapperBase):
                params[k] = int(v)
    elif isinstance(params, (list, tuple)):
        for idx, v in enumerate(params):
            if isinstance(v, WrapperBase):
                # if list, set in place; if tuple, convert to list first
                if isinstance(params, list):
                    params[idx] = int(v)
                else:
                    tmp = list(params)
                    tmp[idx] = int(v)
                    return type(params)(tmp)
    return params

@event.listens_for(Engine, "before_cursor_execute")
def _before_cursor_execute(conn, cursor, statement, parameters,
                           context, executemany):
    # parameters here might be a dict or a sequence of sequences
    if executemany and isinstance(parameters, (list, tuple)):
        for row in parameters:
            _unwrap_params(row)
    else:
        _unwrap_params(parameters)


class cm_dbdriver:

    def __init__(self, config):

        self.config = config

        self.db_driver = dbengine.create_database_driver()
        while globalvars.mariadb_initialized != True:
            continue
        self.db_driver.connect()

        # Import all required model classes from base_dbdriver
        self.UserRegistry = base_dbdriver.UserRegistry
        self.FriendsRegistry = base_dbdriver.FriendsRegistry
        self.ChatRoomRegistry = base_dbdriver.ChatRoomRegistry
        self.LobbyRegistry = base_dbdriver.LobbyRegistry
        self.LobbyMetadata = base_dbdriver.LobbyMetadata
        self.LobbyMembers = base_dbdriver.LobbyMembers
        self.CommunityRegistry = base_dbdriver.CommunityRegistry
        
        # Create a session for ORM operations
        self.session = self.db_driver.get_session()

        # Lazy-initialized purchase database instance
        self._purchase_db = None

    @property
    def purchase_db(self) -> PurchaseDatabase:
        """Get the PurchaseDatabase instance for purchase operations."""
        if self._purchase_db is None:
            self._purchase_db = PurchaseDatabase(self.session)
        return self._purchase_db

    ##################
    # User
    ##################

    from datetime import datetime
    from sqlalchemy.exc import SQLAlchemyError, IntegrityError

    def create_user(
        self,
        unique_username,
        user_type=1,
        passphrase_salt="",
        salted_passphrase_digest="",
        answer_to_question_salt="",
        personal_question="",
        salted_answer_to_question_digest="",
        cell_id=1,
        account_email_address="",
        banned=0,
        email_verified=0,
        first_name=None,
        last_name=None,
        tracker_username=None
    ):
        """Insert a new user into UserRegistry. Also ensure FriendsRegistry + Community_Profile exist.
           Return signature unchanged: (UniqueID, EResult)
        """
        try:
            existing_user = (
                self.session.query(self.UserRegistry)
                .filter_by(UniqueUserName=unique_username)
                .first()
            )
            if existing_user:
                print(f"Username {unique_username} already exists.")
                return 0, EResult.DuplicateName

            new_user = self.UserRegistry(
                UniqueUserName=unique_username,
                AccountCreationTime=datetime.now().strftime("%m/%d/%Y %H:%M:%S"),
                UserType=user_type,
                SaltedAnswerToQuestionDigest=salted_answer_to_question_digest,
                PassphraseSalt=passphrase_salt,
                AnswerToQuestionSalt=answer_to_question_salt,
                PersonalQuestion=personal_question,
                SaltedPassphraseDigest=salted_passphrase_digest,
                LastRecalcDerivedSubscribedAppsTime=datetime.now().strftime("%m/%d/%Y %H:%M:%S"),
                CellID=cell_id,
                AccountEmailAddress=account_email_address,
                DerivedSubscribedAppsRecord=get_derived_appids(),
                Banned=banned,
                AccountLastModifiedTime=datetime.now().strftime("%m/%d/%Y %H:%M:%S"),
                email_verified=email_verified,
            )

            # Add and flush so UniqueID is assigned without committing yet
            self.session.add(new_user)
            self.session.flush()

            account_id = new_user.UniqueID

            # ---- 1) FriendsRegistry MUST exist before Community_Profile ----
            friends_row = (
                self.session.query(self.FriendsRegistry)
                .filter_by(accountID=account_id)
                .first()
            )
            if not friends_row:
                friends_row = self.FriendsRegistry(
                    accountID=account_id,
                    nickname="",
                    status=0,
                    primary_clanID=None,
                    primary_groupID=None,
                    currently_playing=None,
                    last_login=datetime.now(),
                    last_logoff=None
                )
                self.session.add(friends_row)
                self.session.flush()

            # ---- 2) Community_Profile (CommunityRegistry) ----
            community_row = (
                self.session.query(CommunityRegistry)
                .filter_by(friendRegistryID=account_id)
                .first()
            )
            if not community_row:
                community_row = (
                    self.session.query(CommunityRegistry)
                    .filter_by(friendRegistryID=account_id)
                    .first()
                )
                if not community_row:
                    community_row = CommunityRegistry(
                        friendRegistryID=account_id,
                        profile_url=unique_username,   # <-- USE THE USERNAME
                    )
                    self.session.add(community_row)
                    self.session.flush()

            # Commit everything as one transaction
            self.session.commit()

            print(f"User {unique_username} created successfully.")
            return account_id, EResult.OK

        except IntegrityError as e:
            self.session.rollback()
            log.error(f"Integrity error creating user/friends/community rows: {e}")
            return 0, EResult.IOFailure

        except SQLAlchemyError as e:
            self.session.rollback()
            log.error(f"Error creating user: {e}")
            return 0, EResult.IOFailure


    def get_or_create_registry_entry(self, accountID: int):
        """
        Ensure there is a UserRegistry row for `accountID`,
        then get-or-create FriendsRegistry row,
        and also ensure CommunityRegistry exists (by friendRegistryID).
        Returns (friends_row, is_new_friends).
        """
        is_new_friends = False

        try:
            # 1) UserRegistry
            try:
                user_row = (
                    self.session.query(self.UserRegistry)
                    .filter_by(UniqueID=accountID)
                    .one()
                )
            except NoResultFound:
                user_row = self.UserRegistry(
                    UniqueID=accountID,
                    AccountCreationTime=datetime.now().strftime("%m/%d/%Y %H:%M:%S"),
                    UserType=1,
                    CellID=1,
                )
                self.session.add(user_row)
                self.session.flush()

            unique_username = user_row.UniqueUserName

            # 2) FriendsRegistry
            try:
                friends_row = (
                    self.session.query(self.FriendsRegistry)
                    .filter_by(accountID=accountID)
                    .one()
                )
            except NoResultFound:
                friends_row = self.FriendsRegistry(
                    accountID=accountID,
                    nickname="",
                    status=0,
                    primary_clanID=None,
                    primary_groupID=None,
                    currently_playing=None,
                    last_login=datetime.now(),
                    last_logoff=None,
                )
                self.session.add(friends_row)
                self.session.flush()
                is_new_friends = True

            # 3) CommunityRegistry (use username so DB shuts up)
            try:
                (
                    self.session.query(CommunityRegistry)
                    .filter_by(friendRegistryID=accountID)
                    .one()
                )
            except NoResultFound:
                self.session.add(
                    CommunityRegistry(
                        friendRegistryID=accountID,
                        profile_url=unique_username,   # <-- IMPORTANT
                        real_name=unique_username      # optional but sane
                    )
                )
                self.session.flush()

            self.session.commit()
            return friends_row, is_new_friends

        except IntegrityError:
            self.session.rollback()
            friends_row = (
                self.session.query(self.FriendsRegistry)
                .filter_by(accountID=accountID)
                .one()
            )
            return friends_row, False



    def check_user_loginkey_information(self, username, loginkey):
        user = self.session.query(self.UserRegistry).filter_by(UniqueUserName=username.rstrip('\x00')).first()
        if user:
            if user.Banned is not None and user.Banned != 0:
                log.info(f"User {user.UniqueUserName} is banned!")
                return 17, None
            else:
                print(f"loginkey: {loginkey}\n db loginkey: {user.loginkey}\n keys match: {user.loginkey == loginkey}")
                if user.loginkey == loginkey.rstrip('\x00'):
                    return 1, user.UniqueID
                else:
                    log.info(f"User {user.UniqueUserName} Tried logging in with an invalid login key!")
                    return 5, None
        else:
            log.info(f"Uknown User {username} tried to log in")
            return 18, None

    def check_user_information_by_username_or_email(self, account_name, password):
        """
        Check user login credentials by username or email and return (error_code, accountID).
        First tries to find user by email, then by username if not found.
        Used by protobuf login handlers where account_name can be either.
        """
        try:
            # First try by email
            user = self.session.query(self.UserRegistry).filter_by(AccountEmailAddress=account_name).first()
            # If not found by email, try by username
            if not user:
                user = self.session.query(self.UserRegistry).filter_by(UniqueUserName=account_name).first()

            if user:
                # Check if user is banned
                if user.Banned is not None and user.Banned != 0:
                    log.info(f"User {user.UniqueUserName} is banned!")
                    return 17, None

                # User is not banned, check password
                salt = binascii.unhexlify(user.PassphraseSalt)
                digest_hex = user.SaltedPassphraseDigest[0:32]

                hashed_password = hashlib.sha1(salt[:4] + password.encode() + salt[4:]).digest()
                hashed_password_hex = binascii.hexlify(hashed_password[0:16])

                if digest_hex.encode('latin-1') == hashed_password_hex:
                    return 1, user.UniqueID  # Success
                else:
                    log.info(f"User {user.UniqueUserName} tried logging in with an incorrect password!")
                    return 5, None  # Invalid credentials
            else:
                log.info(f"Unknown user {account_name} tried to log in")
                return 18, None  # Invalid user
        except SQLAlchemyError as e:
            log.error(f"Database error in check_user_information_by_username_or_email: {e}")
            return 2, None  # Database error

    def check_user_information(self, email, password):
        """Check user login credentials and return (error_code, accountID)"""
        try:
            user = self.session.query(self.UserRegistry).filter_by(AccountEmailAddress=email).first()
            if user:
                # Check if user is banned (Banned field should be None or 0 for non-banned users)
                if user.Banned is not None and user.Banned != 0:
                    log.info(f"User {user.UniqueUserName} is banned!")
                    return 17, None
                
                # User is not banned, check password
                salt = binascii.unhexlify(user.PassphraseSalt)
                digest_hex = user.SaltedPassphraseDigest[0:32]

                hashed_password = hashlib.sha1(salt[:4] + password.encode() + salt[4:]).digest()
                hashed_password_hex = binascii.hexlify(hashed_password[0:16])
                
                if digest_hex.encode('latin-1') == hashed_password_hex:
                    return 1, user.UniqueID  # Success
                else:
                    log.info(f"User {user.UniqueUserName} tried logging in with an incorrect password!")
                    return 5, None  # Invalid credentials
            else:
                log.info(f"Unknown user {email} tried to log in")
                return 18, None  # Invalid user
        except SQLAlchemyError as e:
            log.error(f"Database error in check_user_information: {e}")
            return 2, None  # Database error

    def compare_password_digests(self, email, digest):
        """Compare password digests and return (error_code, accountID)"""
        try:
            user = self.session.query(self.UserRegistry).filter_by(AccountEmailAddress=email).first()
            if user:
                # Check if user is banned (Banned field should be None or 0 for non-banned users)
                if user.Banned is not None and user.Banned != 0:
                    log.info(f"User {user.UniqueUserName} is banned!")
                    return 17, None
                
                # User is not banned, check digest
                digest_hex = user.SaltedPassphraseDigest[0:32]
                log.debug(f"db_digest: {digest_hex.encode('latin-1')}, user_digest: {digest.encode('latin-1')}")
                if digest_hex.encode('latin-1') == digest.encode('latin-1'):
                    return 1, user.UniqueID  # Success
                else:
                    log.info(f"User {user.UniqueUserName} tried logging in with an incorrect password digest!")
                    return 5, None  # Invalid credentials
            else:
                log.info(f"Unknown user {email} tried to log in")
                return 18, None  # Invalid user
        except SQLAlchemyError as e:
            log.error(f"Database error in compare_password_digests: {e}")
            return 2, None  # Database error

    def insertUFSSessionToken(self, userName, digest, sessionToken):
        """Insert UFS session token for user after validating credentials"""
        try:
            user = self.session.query(self.UserRegistry).filter_by(UniqueUserName=userName).first()
            if user:
                # Check if user is banned (Banned field should be None or 0 for non-banned users)
                if user.Banned is not None and user.Banned != 0:
                    log.info(f"User {user.UniqueUserName} is banned!")
                    return 17, None
                
                # User is not banned, check digest
                digest_hex = user.SaltedPassphraseDigest[0:32]
                log.debug(f"db_digest: {digest_hex}, user_digest: {digest}")
                if digest_hex == digest:
                    user.ufsSessionToken = sessionToken
                    self.session.commit()
                    return 1
                else:
                    log.info(f"User {user.UniqueUserName} tried logging in with an incorrect password!")
                    return 5, None
            else:
                log.info(f"Unknown user {userName} tried to log in")
                return 18, None
        except SQLAlchemyError as e:
            log.error(f"Database error in insertUFSSessionToken: {e}")
            self.session.rollback()
            return 2, None

    def compareUFSSessionToken(self, accountID, sessionToken):
        user = self.session.query(self.UserRegistry).filter_by(UniqueID=accountID).first()
        if user:
            if user.Banned is not None or user.Banned != 0:
                storedToken = user.ufsSessionToken
                log.debug(f"sessionToken: {sessionToken}, user_diget: {storedToken}")
                if sessionToken.decode('latin-1') == storedToken:
                    return 1
                else:
                    log.info(f"User {user.UniqueUserName} Tried logging in with an incorrect sessionToken!")
                    return 5, None
            else:
                log.info(f"User {user.UniqueUserName} is banned!")
                return 17, None
        else:
            log.info(f"Uknown User {accountID} tried to log in")
            return 18, None

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

    def check_and_update_machine_ids(self, account_id, bb3=None, ff2=None, _3b3=None, bbb=None, _333=None, overwrite=False):
        """
        Checks and updates machine IDs for a given account.
        Supports all 5 machineID types: BB3 (machine guid), FF2 (MAC), 3B3 (diskID), BBB (bios serial), 333 (custom data).
        Any machineID type can be None/missing.

        :param account_id: The account ID to search for.
        :param bb3: The BB3 machine ID (machine guid) to compare.
        :param ff2: The FF2 machine ID (MAC address) to compare.
        :param _3b3: The 3B3 machine ID (disk ID) to compare.
        :param bbb: The BBB machine ID (BIOS serial) to compare.
        :param _333: The 333 machine ID (custom data) to compare.
        :param overwrite: Whether to overwrite the existing machine IDs if they do not match.
        :return: True if the machine IDs match or were successfully updated, False otherwise.
        """
        try:
            # Helper function to extract value from tuple if needed, handling None gracefully
            def extract_value(val):
                if val is None or val == 'N/A':
                    return None
                return val[0] if isinstance(val, tuple) else val

            # Extract the actual machine ID values
            bb3_value = extract_value(bb3)
            ff2_value = extract_value(ff2)
            _3b3_value = extract_value(_3b3)
            bbb_value = extract_value(bbb)
            _333_value = extract_value(_333)

            # Search for an existing entry by account ID
            entry = self.session.query(UserMachineIDRegistry).filter_by(accountID=account_id).first()

            if entry:
                # Compare the machine IDs (only compare non-None values)
                def values_match(existing, new_val):
                    if new_val is None:
                        return True  # If new value is None, don't consider it a mismatch
                    return existing == new_val

                all_match = (
                    values_match(entry.BB3, bb3_value) and
                    values_match(entry.FF2, ff2_value) and
                    values_match(entry._3B3, _3b3_value) and
                    values_match(entry.BBB, bbb_value) and
                    values_match(entry._333, _333_value)
                )

                if all_match:
                    return True  # IDs match
                elif not overwrite:
                    return False  # IDs do not match and overwrite is false
                else:
                    # Overwrite the existing machine IDs (only update non-None values)
                    if bb3_value is not None:
                        entry.BB3 = bb3_value
                    if ff2_value is not None:
                        entry.FF2 = ff2_value
                    if _3b3_value is not None:
                        entry._3B3 = _3b3_value
                    if bbb_value is not None:
                        entry.BBB = bbb_value
                    if _333_value is not None:
                        entry._333 = _333_value
                    self.session.commit()
                    return True  # IDs were updated
            else:
                # Create a new entry if none exists
                new_entry = UserMachineIDRegistry(
                    accountID=account_id,
                    BB3=bb3_value,
                    FF2=ff2_value,
                    _3B3=_3b3_value,
                    BBB=bbb_value,
                    _333=_333_value
                )
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
        # Ensure accountid is a plain int for the query
        accountid_int = int(accountid)

        user = self.session.query(self.UserRegistry.AccountEmailAddress, self.UserRegistry.email_verified).filter(
                self.UserRegistry.UniqueID == accountid_int
        ).first()

        if user:
            # email_verified is stored as an integer; convert it to a boolean
            return user.AccountEmailAddress, bool(user.email_verified)

        # Debug: Check if user exists at all
        user_exists = self.session.query(self.UserRegistry).filter(
                self.UserRegistry.UniqueID == accountid_int
        ).first()
        if user_exists:
            log.error(f"User {accountid_int} exists but has no email: {user_exists.AccountEmailAddress}")
        else:
            log.error(f"User {accountid_int} does not exist in UserRegistry at all!")

        return None

    def generate_verification_code(self, accountid: int):
        """
        Generates a verification code for the user if their email is not verified,
        updates the email_verificationcode field, and returns their email address
        and verification code as a dictionary.

        :param accountid: The UniqueID of the user.
        :return: A dictionary {'email': email_address, 'verification_code': code}
                 or None if the account does not exist.
        """
        # Fetch the user from the database
        user = self.session.query(self.UserRegistry).filter(self.UserRegistry.UniqueID == accountid).first()

        if user is None:
            # Account does not exist
            return None

        if not user.email_verified:
            # Generate a 6-character verification code
            verification_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k = 6))

            # Update the user record with the new verification code
            user.email_verificationcode = verification_code

            # Commit the changes to the database
            self.session.commit()
        else:
            # If email is already verified, use the existing verification code
            verification_code = user.email_verificationcode

        # Return the email address and verification code
        return {
                'email':            user.AccountEmailAddress,
                'verification_code':verification_code
        }

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

        # Check if HWIDSet flag should be added (any of the 5 machineID types being set counts)
        hwid_exists = self.session.query(UserMachineIDRegistry).filter(
                UserMachineIDRegistry.accountID == userid,
                or_(
                        UserMachineIDRegistry.BB3 != None,
                        UserMachineIDRegistry.FF2 != None,
                        UserMachineIDRegistry._3B3 != None,
                        UserMachineIDRegistry.BBB != None,
                        UserMachineIDRegistry._333 != None,
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

    def set_email_verified(self, userid: int) -> None:
        """
        Marks a user's email as verified.

        :param userid: The UniqueID of the user in UserRegistry.
        """
        user = self.session.query(self.UserRegistry).filter(
            self.UserRegistry.UniqueID == userid
        ).first()

        if not user:
            raise ValueError(f"No user found with ID {userid}")

        if user.email_verified != 1:
            user.email_verified = 1
            self.session.commit()

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

    def get_clan_by_id(self, clan_id: int):
        """
        Get a clan registry entry by its unique ID.

        :param clan_id: The unique ID of the clan
        :return: CommunityClanRegistry entry or None
        """
        return self.session.query(CommunityClanRegistry).filter(
            CommunityClanRegistry.UniqueID == clan_id
        ).first()

    def get_clan_member_count(self, clan_id: int) -> int:
        """
        Get the total number of members in a clan.

        :param clan_id: The unique ID of the clan
        :return: Number of members
        """
        try:
            return self.session.query(CommunityClanMembers).filter(
                CommunityClanMembers.CommunityClanID == clan_id,
                CommunityClanMembers.relationship == 3  # ChatRelationship.member
            ).count()
        except Exception:
            return 0

    def get_clan_members(self, clan_id: int):
        """
        Get all member entries for a clan.

        :param clan_id: The unique ID of the clan
        :return: List of CommunityClanMembers entries
        """
        return self.session.query(CommunityClanMembers).filter(
            CommunityClanMembers.CommunityClanID == clan_id
        ).all()

    ##################
    # Friend/Friendlist
    ##################
    def fix_invites(self, steamid):
        """
        Update the friend status to 3 (friend) for all friends of the given steamid where status is 2 or 4.
        Also updates the inverse relationship (the other user's side).

        This is only used if a client connects with a steam client that is steamui version 352 or greater,
        until the issue is resolved where the receiving user of a friend request does not get a pop-up
        dialog to accept a friend request.

        :param steamid: The steam ID to search for in the friendRegistryID field.
        :return: List of accountIDs of friends whose relationships were auto-accepted.
        """
        auto_accepted_friends = []
        try:
            # Fetch all entries where friendRegistryID is equal to the provided steamid
            friends_list = self.session.query(FriendsList).filter(FriendsList.friendRegistryID == steamid).all()

            # Update status to 3 where status is 2 or 4
            for friend in friends_list:
                if friend.relationship in [2, 4]:
                    friend.relationship = 3
                    self.session.add(friend)
                    auto_accepted_friends.append(friend.accountID)

                    # Also update the inverse relationship (the other user's side)
                    inverse_entry = self.session.query(FriendsList).filter(
                        FriendsList.friendRegistryID == friend.accountID,
                        FriendsList.accountID == steamid
                    ).first()
                    if inverse_entry:
                        inverse_entry.relationship = 3
                        self.session.add(inverse_entry)

            self.session.commit()
            return auto_accepted_friends
        except Exception as e:
            self.session.rollback()
            log.error(f"Error updating friend status: {e}")
            return []

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
                    return AccountID(user.UniqueID)
                else:
                    print("No user found with that email address")
                    return None
            else:
                # Try finding the user in UserRegistry by username
                user = self.session.query(self.UserRegistry.UniqueID).filter(self.UserRegistry.UniqueUserName == nickname).first()
                if user:
                    return AccountID(user.UniqueID)
                else:
                    # User not found in UserRegistry, try FriendsRegistry
                    friend = self.session.query(FriendsRegistry).filter(FriendsRegistry.nickname == nickname).first()
                    return AccountID(friend.accountID) if friend else None
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
        # Expire all cached objects to ensure we get fresh data from the database
        # This is important for friend invites where entries are created via SQLAlchemy triggers
        self.session.expire_all()

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

        if userreg_record is None:
            log.debug(f"No record found for account ID {accountid} in FriendsRegistry")
            username = '[unset]'
        else:
            username = userreg_record.UniqueUserName

        return str(username)

    def update_user_login_key(self, unique_id, login_key):
        """
        Updates the login key for a user in the user registry.

        :param unique_id: The unique ID of the user.
        :param login_key: The 20-character login key to store.
        :param db_url: The database connection URL (default is SQLite for demonstration).
        """
        try:
            # Check if the user exists
            user = self.session.query(self.UserRegistry).filter_by(UniqueID = unique_id).first()
            if user:
                # Update the login key
                user.loginkey = login_key
                log.debug(f"Updated login key for user with unique_id {unique_id}.")
            else:
                log.error(f"No user found with unique_id {unique_id}.")
                return False

            # Commit the changes
            self.session.commit()
            return True
        except Exception as e:
            log.error(f"An error occurred: {e}")
            self.session.rollback()
            return False

    def update_user_session_key(self, unique_id, session_key):
        """
        Updates the session key for a user in the user registry.

        :param unique_id: The unique ID of the user.
        :param session_key: The session key to store.
        """
        try:
            # Check if the user exists
            user = self.session.query(self.UserRegistry).filter_by(UniqueID=unique_id).first()
            if user:
                # Update the session key
                user.sessionkey = session_key
                log.debug(f"Updated session key for user with unique_id {unique_id}.")
            else:
                log.error(f"No user found with unique_id {unique_id}.")
                return False

            # Commit the changes
            self.session.commit()
            return True
        except Exception as e:
            log.error(f"An error occurred: {e}")
            self.session.rollback()
            return False

    def update_user_symmetric_key(self, unique_id, symmetric_key):
        """
        Updates the symmetric key for a user in the user registry.

        :param unique_id: The unique ID of the user.
        :param symmetric_key: The symmetric key to store.
        """
        try:
            # Check if the user exists
            user = self.session.query(self.UserRegistry).filter_by(UniqueID=unique_id).first()
            if user:
                # Update the symmetric key
                user.symmetric_key = symmetric_key
                log.debug(f"Updated symmetric key for user with unique_id {unique_id}.")
            else:
                log.error(f"No user found with unique_id {unique_id}.")
                return False

            # Commit the changes
            self.session.commit()
            return True
        except Exception as e:
            log.error(f"An error occurred: {e}")
            self.session.rollback()
            return False

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
    # Chatrooms
    ##################

    def createChatroom(self, chatroom):
        """
        Create a new ChatRoomRegistry entry with a consecutive UniqueID.
        Returns the new accountID.
        """
        try:
            # 1) Find the current maximum UniqueID (or 0 if none exist)
            max_id = self.session.query(func.max(ChatRoomRegistry.UniqueID)).scalar() or 0
            next_id = max_id + 1

            # 2) Build the new registry entry using next_id
            registry_entry = ChatRoomRegistry(
                UniqueID             = next_id,
                chatroom_type        = chatroom.chat_type,
                owner_accountID      = chatroom.owner_accountID,
                groupID              = chatroom.associated_groupID,
                appID                = chatroom.applicationID,
                chatroom_name        = chatroom.name,
                datetime             = chatroom.creation_time,
                message              = chatroom.motd,
                servermessage        = chatroom.servermessage,
                chatroom_flags       = chatroom.flags,
                owner_permissions    = chatroom.permissions.get("owner", {}).get("permissions", 0),
                moderator_permissions= chatroom.permissions.get("moderator", {}).get("permissions", 0),
                member_permissions   = chatroom.permissions.get("member", {}).get("permissions", 0),
                default_permissions  = chatroom.permissions.get("default", {}).get("permissions", 0),
                maxmembers           = chatroom.member_limit,
                current_usercount    = len(chatroom.clientlist),
            )

            # 3) Insert and commit
            self.session.add(registry_entry)
            self.session.commit()

            # 4) Return the newly assigned chatroom ID
            return next_id

        except Exception as e:
            self.session.rollback()
            raise

    def get_permanent_chatrooms(self):
        try:
            return (
                self.session.query(ChatRoomRegistry)
                .filter(ChatRoomRegistry.chatroom_type != ChatRoomType.lobby)
                .all()
            )
        except SQLAlchemyError as exc:
            self.session.rollback()
            log.error("get_permanent_chatrooms failed: %s", exc)
            return []

    def updateUserCount(self, chatroom_id, clientlist):
        """
        Update the current_usercount for the given chatroom based on len(clientlist).
        Returns the new count, or the exception object on error.
        """
        try:
            # Grab the registry entry (or blow up if not found)
            registry = (
                self.session
                    .query(ChatRoomRegistry)
                    .filter(ChatRoomRegistry.UniqueID == chatroom_id)
                    .one()
            )
            # Do the math that apparently you can't
            new_count = len(clientlist)
            registry.current_usercount = new_count
            self.session.commit()
            return new_count
        except NoResultFound as e:
            self.session.rollback()
            return e  # You deleted it on your own? Nice going.
        except Exception as e:
            self.session.rollback()
            return e  # Return the error so you can read it this time

    def update_chatroom_flags(self, chatroom_id: int, flags: int) -> None:
        try:
            (
                self.session.query(ChatRoomRegistry)
                .filter(ChatRoomRegistry.UniqueID == chatroom_id)
                .update({"chatroom_flags": flags})
            )
            self.session.commit()
        except SQLAlchemyError as exc:
            self.session.rollback()
            log.error("update_chatroom_flags failed: %s", exc)

    def update_chatroom_member_limit(self, chatroom_id: int, member_limit: int) -> None:
        try:
            (
                self.session.query(ChatRoomRegistry)
                .filter(ChatRoomRegistry.UniqueID == chatroom_id)
                .update({"maxmembers": member_limit})
            )
            self.session.commit()
        except SQLAlchemyError as exc:
            self.session.rollback()
            log.error("update_chatroom_member_limit failed: %s", exc)

    def set_chatroom_metadata(self, chatroom_id: int, metadata: bytes) -> None:
        try:
            (
                self.session.query(ChatRoomRegistry)
                .filter(ChatRoomRegistry.UniqueID == chatroom_id)
                .update({"metadata_info": metadata.decode('latin-1')})
            )
            self.session.commit()
        except SQLAlchemyError as exc:
            self.session.rollback()
            log.error("set_chatroom_metadata failed: %s", exc)

    def removeChatroom(self, chatroom_id):
        """
        Delete the chatroom registry entry for the given ID.
        Returns True if successful, or the exception object on error.
        """
        try:
            deleted = (
                self.session
                    .query(ChatRoomRegistry)
                    .filter(ChatRoomRegistry.UniqueID == chatroom_id)
                    .delete()
            )
            if deleted == 0:
                # Nothing to delete?congratulations, you asked to delete something that doesn't exist.
                self.session.rollback()
                return Exception(f"No chatroom with ID {chatroom_id}")
            self.session.commit()
            return True
        except Exception as e:
            self.session.rollback()
            return e  # Here?s your failure back in digestible form

    def add_chatroom_msg_history(self, chatroomObj, message, sender):
        # Save the message to the database for permanent chatrooms
        try:
            chat_history_entry = ChatRoomHistory(
                chatroomID=chatroomObj.accountID,
                from_accountID=int(sender.steamID.get_accountID()),  # Convert AccountID wrapper to int
                message=message,
                datetime=datetime.now()
            )
            self.session.add(chat_history_entry)
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            raise e

    def getChatRoomHistory(self, chatroomID):
        """
        Retrieves all chat history entries for interactions between two specific users.

        :param chatroomID: The account ID of the chatroom
        :return: A list of dictionaries, each representing a chat history entry.
        """
        # Fetch all relevant chat history entries
        chat_histories = self.session.query(ChatRoomHistory).filter(ChatRoomHistory.chatroomID == chatroomID).all()

        # Convert each entry to a dictionary
        return [self.chat_to_dict(chat) for chat in chat_histories]

    def get_chatroom_member(self, chatRoomID: int, friendRegistryID: int):
        """
        Fetch a single ChatRoomMembers entry by chatRoomID and friendRegistryID.
        Raises an exception if more than one result is found, because that would mean
        you royally screwed up your UNIQUE constraint.

        :param session: SQLAlchemy session
        :param chatRoomID: Integer ID of the chat room (foreign key to chatrooms_registry)
        :param friendRegistryID: Integer ID of the friend (foreign key to friends_registry)
        :return: ChatRoomMembers instance
        :raises MultipleResultsFound: if more than one record is returned
        :raises NoResultFound: if no record is found
        """
        try:
            member = (
                self.session
                .query(ChatRoomMembers)
                .filter_by(chatRoomID=chatRoomID, friendRegistryID=friendRegistryID)
                .one()
            )
        except MultipleResultsFound:
            # If this happens, you violated the UNIQUE constraint?something is terribly wrong.
            raise MultipleResultsFound(
                f"Error: more than one ChatRoomMembers entry for chatRoomID={chatRoomID} "
                f"and friendRegistryID={friendRegistryID}. Fix your database, you dummy."
            )

        except NoResultFound:
            raise  # Re-raise so callers can handle it properly

        return member

    def set_chatroom_member(self, chatRoomID: int, accountID: int, relationship: int, memberRankDetails: int = 0, inviterAccountID = None):
        """
        Insert or update a ChatRoomMembers record. If exactly one record is found,
        update its fields only where they differ. If none is found, create a new record.
        If more than one entry is found, return None.

        :param chatRoomID: Integer ID of the chat room
        :param accountID: Integer ID of the friend
        :param relationship: Integer relationship value to set
        :param memberRankDetails: Optional rank/details field
        :param inviterAccountID: Integer ID of the user who sent the invite (used
                                 when relationship is -1 or TO_BE_INVITED)
        :return: The ChatRoomMembers instance that was created or updated, or None if
                 multiple entries exist
        """
        try:
            member = self.get_chatroom_member(chatRoomID, accountID)
        except NoResultFound:
            # No existing entry: create one
            member = ChatRoomMembers(
                chatRoomID=chatRoomID,
                friendRegistryID=accountID,
                relationship=relationship,
                inviterAccountID=(
                    inviterAccountID
                    if relationship in (-1, ChatMemberStatus.TO_BE_INVITED)
                    else None
                ),
                memberRankDetails=memberRankDetails or None
            )
            self.session.add(member)
            self.session.flush()
            return member

        except MultipleResultsFound:
            raise Exception()

        # Exactly one record found: patch only fields that differ
        updated = False

        # 1) Relationship
        if member.relationship != relationship:
            member.relationship = relationship
            updated = True

        # 2) Inviter (only for ?to be invited? statuses, otherwise clear)
        if relationship in (-1, ChatMemberStatus.TO_BE_INVITED):
            if member.inviterAccountID != inviterAccountID:
                member.inviterAccountID = inviterAccountID
                updated = True


        # 3) Member rank/details
        #    (treat zero or falsy incoming as ?no detail?)
        new_rank = memberRankDetails or None
        if member.memberRankDetails != new_rank:
            member.memberRankDetails = new_rank
            updated = True

        if updated:
            self.session.flush()

        return member

    def remove_chatroom_member(self, chatRoomID: int, friendRegistryID: int):
        """
        Delete the ChatRoomMembers entry identified by chatRoomID and friendRegistryID.
        If no such entry exists, raise NoResultFound?because even you should know
        when you?re trying to delete something that doesn?t exist.

        :param session: SQLAlchemy session (do try not to drop it like you drop your brain cells).
        :param chatRoomID: Integer ID of the chat room (foreign key to chatrooms_registry).
        :param friendRegistryID: Integer ID of the friend (foreign key to friends_registry).
        :raises NoResultFound: if no record is found (because somehow, you forgot to add it first).
        """
        try:
            # Reuse the getter you still can?t code yourself
            member = self.get_chatroom_member(chatRoomID, friendRegistryID)
            self.session.delete(member)
            self.session.flush()
            return True
        except NoResultFound:
            # Of course there?s no entry, because you probably never created one.
            raise NoResultFound(
                f"No ChatRoomMembers entry to remove for chatRoomID={chatRoomID} "
                f"and friendRegistryID={friendRegistryID}. "
                f"Congrats on trying to delete thin air, Einstein."
            )

    def get_pending_invites(self, chatRoomID: int) -> list[tuple[int, int]]:
        """
        Fetch all ChatRoomMembers entries for a given chatRoomID where
        relationship is -1 or TO_BE_INVITED, and return a list of
        (friendRegistryID, inviterAccountID) tuples.

        :param chatRoomID: Integer ID of the chat room
        :return: List of tuples (friendRegistryID, inviterAccountID)
                 for every pending invite
        """
        rows = (
            self.session
                .query(ChatRoomMembers)
                .filter_by(chatRoomID=chatRoomID)
                .filter(ChatRoomMembers.relationship.in_((-1, ChatMemberStatus.TO_BE_INVITED)))
                .all()
        )

        # Return (invitee, inviter) pairs. If none, you get an empty list?just like your social calendar.
        return [(row.friendRegistryID, row.inviterAccountID) for row in rows]

    def get_all_chatrooms_for_player(self, accountID: int) -> list[tuple[int, int]]:
        """
        Fetch all ChatRoomMembers entries for a given player (by accountID) and return
        a list of (chatRoomID, relationship) tuples. If the player isn?t in any chatrooms,
        this returns an empty list?just like your social life, I guess.

        :param accountID: Integer ID of the player (friendRegistryID)
        :return: List of tuples (chatRoomID, relationship) for every row found
        """
        # Query for every ChatRoomMembers row matching this accountID.
        rows = (
            self.session
                .query(ChatRoomMembers)
                .filter_by(friendRegistryID=accountID)
                .all()
        )

        # If you get no rows, return an empty list. Not that you?ll be surprised.
        if not rows:
            return []

        # Build a list of (chatRoomID, relationship) pairs. Try not to trip over the basics.
        result_list = [(row.chatRoomID, row.relationship) for row in rows]
        return result_list

    def get_all_users_for_chatroom(self, chatRoomID: int) -> list[tuple[int, int]]:
        """
        Fetch all ChatRoomMembers entries for a given chatRoomID and return
        a list of (accountID, relationship) tuples. If the chatroom has no members,
        returns an empty list.

        :param chatRoomID: Integer ID of the chat room (foreign key to chatrooms_registry)
        :return: List of tuples (friendRegistryID, relationship) for every row found
        """
        # Query for every ChatRoomMembers row matching this chatRoomID
        rows = (
            self.session
                .query(ChatRoomMembers)
                .filter_by(chatRoomID=chatRoomID)
                .all()
        )

        # Build and return a list of (accountID, relationship) pairs.
        # If there are no rows, this will simply be an empty list.
        return [(row.friendRegistryID, row.relationship) for row in rows]

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
            vr_hmd_runtime = None, controller_connection_type = None, end_datetime = None, max_retries = 3):
        """ Adds a play history record for a user and updates the currently_playing field """
        retry_count = 0

        while retry_count < max_retries:
            try:
                # Add play history entry
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
                friend_registry = self.session.query(FriendsRegistry).filter_by(accountID = accountID).with_for_update().first()
                if friend_registry:
                    friend_registry.currently_playing = new_play_history.UniqueID
                else:
                    # Log if the accountID was not found
                    log.warning(f"FriendsRegistry entry not found for accountID: {accountID}")

                # Commit transaction
                self.session.commit()
                return new_play_history

            except OperationalError as e:
                if "Deadlock found when trying to get lock" in str(e):
                    retry_count += 1
                    log.warning(f"Deadlock detected. Retrying transaction {retry_count}/{max_retries}...")
                    time.sleep(0.5 * retry_count)  # Exponential backoff
                else:
                    log.error(f"Database error: {e}")
                    raise
            except Exception as e:
                log.error(f"Unexpected error: {e}")
                self.session.rollback()
                raise
        else:
            log.error(f"Failed to add play history after {max_retries} retries due to deadlock.")
            raise RuntimeError("Failed to add play history due to repeated deadlocks.")

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
            return [(0,0)]  # No VAC bans found for the user

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
    # Persistent Items (TF2-era inventory system)
    ##################
    def get_persistent_items_by_steamid_appid(self, steam_id: int, app_id: int) -> List[PersistentItem]:
        """Get all persistent items for a user in a specific app."""
        try:
            items = self.session.query(PersistentItem).filter(
                PersistentItem.steam_id == steam_id,
                PersistentItem.app_id == app_id
            ).all()
            return items
        except SQLAlchemyError as e:
            log.error(f"[get_persistent_items_by_steamid_appid] Database error: {e}")
            return []

    def get_persistent_item_by_id(self, item_id: int) -> Optional[PersistentItem]:
        """Get a specific persistent item by its unique item ID."""
        try:
            return self.session.query(PersistentItem).filter(
                PersistentItem.item_id == item_id
            ).first()
        except SQLAlchemyError as e:
            log.error(f"[get_persistent_item_by_id] Database error: {e}")
            return None

    def add_persistent_item(self, steam_id: int, app_id: int, item_id: int,
                           definition_index: int, item_level: int, quality: int,
                           inventory_token: int, quantity: int = 1,
                           attributes: List[Tuple[int, float]] = None) -> Optional[PersistentItem]:
        """Add a new persistent item to the database."""
        try:
            new_item = PersistentItem(
                steam_id=steam_id,
                app_id=app_id,
                item_id=item_id,
                definition_index=definition_index,
                item_level=item_level,
                quality=quality,
                inventory_token=inventory_token,
                quantity=quantity
            )
            self.session.add(new_item)
            self.session.flush()  # Get the ID before adding attributes

            # Add attributes if provided
            if attributes:
                for attr_def_index, attr_value in attributes:
                    attr = PersistentItemAttribute(
                        item_id=new_item.id,
                        definition_index=attr_def_index,
                        value=attr_value
                    )
                    self.session.add(attr)

            self.session.commit()
            return new_item
        except IntegrityError as e:
            log.error(f"[add_persistent_item] Integrity error (duplicate item_id?): {e}")
            self.session.rollback()
            return None
        except SQLAlchemyError as e:
            log.error(f"[add_persistent_item] Database error: {e}")
            self.session.rollback()
            return None

    def update_persistent_item_position(self, item_id: int, steam_id: int, app_id: int,
                                         new_position: int) -> EResult:
        """Update the inventory position of a persistent item."""
        try:
            item = self.session.query(PersistentItem).filter(
                PersistentItem.item_id == item_id,
                PersistentItem.steam_id == steam_id,
                PersistentItem.app_id == app_id
            ).first()

            if not item:
                return EResult.NoMatch

            item.inventory_token = new_position
            self.session.commit()
            return EResult.OK
        except SQLAlchemyError as e:
            log.error(f"[update_persistent_item_position] Database error: {e}")
            self.session.rollback()
            return EResult.Fail

    def delete_persistent_item(self, item_id: int, steam_id: int, app_id: int) -> EResult:
        """Delete (drop) a persistent item. Returns EResult."""
        try:
            item = self.session.query(PersistentItem).filter(
                PersistentItem.item_id == item_id,
                PersistentItem.steam_id == steam_id,
                PersistentItem.app_id == app_id
            ).first()

            if not item:
                return EResult.NoMatch

            # Attributes will be deleted via cascade
            self.session.delete(item)
            self.session.commit()
            return EResult.OK
        except SQLAlchemyError as e:
            log.error(f"[delete_persistent_item] Database error: {e}")
            self.session.rollback()
            return EResult.Fail

    def get_next_item_id(self, app_id: int) -> int:
        """Generate the next unique item ID for an app."""
        try:
            max_id = self.session.query(func.max(PersistentItem.item_id)).filter(
                PersistentItem.app_id == app_id
            ).scalar()
            return (max_id or 0) + 1
        except SQLAlchemyError as e:
            log.error(f"[get_next_item_id] Database error: {e}")
            # Return a random high number as fallback
            return random.randint(100000, 999999)

    def add_persistent_item_attribute(self, item_id: int, definition_index: int,
                                       value: float) -> bool:
        """Add an attribute to an existing persistent item."""
        try:
            item = self.session.query(PersistentItem).filter(
                PersistentItem.item_id == item_id
            ).first()
            if not item:
                return False

            attr = PersistentItemAttribute(
                item_id=item.id,
                definition_index=definition_index,
                value=value
            )
            self.session.add(attr)
            self.session.commit()
            return True
        except SQLAlchemyError as e:
            log.error(f"[add_persistent_item_attribute] Database error: {e}")
            self.session.rollback()
            return False

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
    #  MISC
    ##################

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

    ##################
    # Purchases and Gift/Guest Passes
    ##################

    def get_tax_rate_for_address(self, addressinfo: dict) -> float:
        """
        Returns the applicable tax rate as a decimal fraction.
        For non-US addresses, query the CountryTax table based on the 2-letter country code.
        For US addresses, query the StateSalesTax table based on the 2-letter state code.
        If no record is found, returns 0.0.
        """
        country = addressinfo.get('CountryCode', '').upper()
        if country != "US":
            result = self.session.query(CountryTax.tax_rate).filter(CountryTax.country == country).first()
            if result and result.tax_rate is not None:
                return float(result.tax_rate) / 100.0
            else:
                return 0.0
        else:
            raw_state = addressinfo.get('state', '')
            state_code = get_state_iso_code(raw_state)
            result = self.session.query(StateSalesTax.tax_rate).filter(StateSalesTax.state == state_code).first()
            if result and result.tax_rate is not None:
                return float(result.tax_rate) / 100.0
            else:
                return 0.0

    def get_user_owned_subscription_ids(self, user_unique_id: int) -> list:
        """
        Queries the database for all subscriptions owned by the user.

        1. Queries AccountSubscriptionsRecord where UserRegistry_UniqueID == user_unique_id
           and extracts the SubscriptionID.
        2. Queries Steam3LicenseRecord where accountID == user_unique_id
           and extracts the PackageID.

        Returns:
            A combined list of dictionaries. Each dictionary contains:
                - 'subscription_id': the subscription (or package) id (as an integer)
                - 'steam3': True if this subscription is from Steam3LicenseRecord, False otherwise.
        """
        results = []

        # Example pseudo-code for AccountSubscriptionsRecord:
        account_subs = self.session.query(AccountSubscriptionsRecord.SubscriptionID)\
                              .filter(AccountSubscriptionsRecord.UserRegistry_UniqueID == user_unique_id).all()
        for row in account_subs:
            results.append({
                'subscription_id': row.SubscriptionID,
                'steam3': False
            })

        # Example pseudo-code for Steam3LicenseRecord:
        license_subs = self.session.query(Steam3LicenseRecord.PackageID)\
                              .filter(Steam3LicenseRecord.AccountID == user_unique_id).all()
        for row in license_subs:
            results.append({
                'subscription_id': row.PackageID,
                'steam3': True
            })

        return results

    def grant_license(self, account_id: int, package_id: int, license_type: int = 1,
                     payment_type: int = 0, country_code: str = "US") -> bool:
        """
        Grant a license to a user account (used for key activation).
        Delegates to PurchaseDatabase for actual implementation.

        Args:
            account_id (int): User's account ID
            package_id (int): Package/App ID to grant
            license_type (int): Type of license (1 = retail key, 2 = complimentary, etc.)
            payment_type (int): Payment method used (0 = none for key activation)
            country_code (str): Purchase country code

        Returns:
            bool: True if license was granted successfully
        """
        return self.purchase_db.grant_license(
            account_id=account_id,
            package_id=package_id,
            license_type=license_type,
            payment_type=payment_type,
            country_code=country_code
        )

    def get_user_licenses(self, user_id: int):
        """
        Retrieve all active licenses for a given user.
        
        Args:
            user_id (int): The user's account ID
            
        Returns:
            List of Steam3LicenseRecord objects for the user, or None if query fails
        """
        try:
            licenses = self.session.query(Steam3LicenseRecord).filter(
                Steam3LicenseRecord.AccountID == user_id
            ).all()

            return licenses
            
        except Exception as e:
            self.logger.error(f"Error retrieving licenses for user {user_id}: {e}")
            return None

    def get_user_subscriptions(self, user_id: int):
        """
        Retrieve all active subscriptions for a given user from the legacy AccountSubscriptionsRecord table.

        These are subscriptions from the older Steam2 subscription system that should also be
        sent as licenses in the ClientLicenseList response.

        Args:
            user_id (int): The user's account ID (UserRegistry_UniqueID)

        Returns:
            List of AccountSubscriptionsRecord objects for the user, or empty list if query fails
        """
        try:
            subscriptions = self.session.query(AccountSubscriptionsRecord).filter(
                AccountSubscriptionsRecord.UserRegistry_UniqueID == user_id,
                AccountSubscriptionsRecord.SubscriptionStatus == 1,  # Only active subscriptions
                AccountSubscriptionsRecord.SubscriptionID != 0  # Exclude the default subscription 0
            ).all()

            return subscriptions if subscriptions else []

        except Exception as e:
            self.logger.error(f"Error retrieving subscriptions for user {user_id}: {e}")
            return []

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

    def get_guest_pass_by_id(self, guest_pass_id: int):
        """
        Retrieve a guest pass record by its unique ID.

        Args:
            guest_pass_id (int): The unique ID of the guest pass

        Returns:
            GuestPassRegistry object if found, None otherwise
        """
        try:
            entry = self.session.query(GuestPassRegistry).filter_by(UniqueID=guest_pass_id).first()
            return entry
        except SQLAlchemyError as e:
            log.error(f"[get_guest_pass_by_id] Error retrieving guest pass {guest_pass_id}: {e}")
            return None

    def update_GuestPass(self, gid, sent=None, acked=None, redeemed=None, recipient_address=None, sender_address=None, sender_name=None):

        try:
            entry = self.session.query(GuestPassRegistry).filter_by(UniqueID=gid).first()
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
        except Exception as e:
            self.session.rollback()
            log.error(f"[update_GuestPass] Error updating entry GID {gid}: {e}")

    # NOTE: Extended guest pass/gift pass operations have been moved to
    # utilities/database/purchase_db.py PurchaseDatabase class for better organization.
    # Use PurchaseDatabase for:
    # - create_guest_pass(), get_passes_to_give(), get_passes_to_redeem()
    # - send_guest_pass(), acknowledge_guest_pass(), redeem_guest_pass()
    # - expire_guest_pass(), revoke_guest_pass(), get_expired_passes()
    # - link_pass_to_transaction(), get_passes_for_transaction()
    # - queue_pending_system_im(), get_pending_system_ims(), mark_system_im_delivered()

    def get_or_add_cc_record(self, accountID, card_type, card_number, card_holder_name, card_exp_year, card_exp_month, card_cvv2):
        try:
            # Check if an entry exists with all columns matching
            entry = self.session.query(Steam3CCRecord).filter(
                and_(
                    Steam3CCRecord.AccountID == accountID,
                    Steam3CCRecord.CardType == card_type,
                    Steam3CCRecord.CardNumber == card_number,
                    Steam3CCRecord.CardHolderName == card_holder_name,
                    Steam3CCRecord.CardExpYear == card_exp_year,
                    Steam3CCRecord.CardExpMonth == card_exp_month,
                    Steam3CCRecord.CardCVV2 == card_cvv2,
                    #Steam3CCRecord.BillingAddressEntryID == addressEntryID
                )
            ).first()

            if entry:
                # Return the UniqueID of the matched entry
                return entry.UniqueID
            else:
                # Add a new entry with the current date/time as a string for DateAdded
                current_time_str = datetime.now().strftime("%m/%d/%Y %H:%M:%S")
                new_entry = Steam3CCRecord(
                    AccountID=accountID,
                    CardType=card_type,
                    CardNumber=card_number,
                    CardHolderName=card_holder_name,
                    CardExpYear=card_exp_year,
                    CardExpMonth=card_exp_month,
                    CardCVV2=card_cvv2,
                    DateAdded=current_time_str,
                    #BillingAddressEntryID=addressEntryID
                )
                self.session.add(new_entry)
                self.session.commit()
                return new_entry.UniqueID
        except Exception as e:
            log.error(f"[get_or_add_cc_record] Error retrieving entries: {e}")
            return 0

    def get_cc_records_by_account(self, accountID):
        try:
            entries = self.session.query(Steam3CCRecord).filter_by(AccountID = accountID).all()
            return entries
        except Exception as e:
            log.error(f"[get_cc_records_by_account] Error retrieving entries: {e}")
            return 0
    
    def get_user_payment_methods(self, accountID, payment_method=None):
        """Get user's payment methods, optionally filtered by type.
        
        Args:
            accountID: User's account ID
            payment_method: Optional EPaymentMethod to filter by
            
        Returns:
            List of payment method records
        """
        try:
            from utilities.database.base_dbdriver import ExternalPurchaseInfoRecord
            
            query = self.session.query(ExternalPurchaseInfoRecord).filter_by(AccountID=accountID)
            
            if payment_method:
                query = query.filter_by(TransactionType=payment_method)
                
            entries = query.all()
            return entries
            
        except Exception as e:
            log.error(f"[get_user_payment_methods] Error retrieving payment methods: {e}")
            return []

    def check_activation_key_exists(self, key: str) -> int:
        try:
            return 1 if self.session.query(
                exists().where(LegacyGameKeys.GameKey == key)
            ).scalar() else 0
        except SQLAlchemyError as exc:
            self.session.rollback()
            log.error("[check_activation_key_exists] %s", exc)
            return 0

    def redeem_activation_key(self, account_id: int, key: str):
        """Validate and redeem an activation code for a user.

        Args:
            account_id (int): Account performing the redemption.
            key (str): Activation key string.

        Returns:
            tuple[EResult, EPurchaseResultDetail, int | None]:
                Result code, detailed result, and the associated package/app ID on success.
        """
        try:
            entry = (
                self.session.query(LegacyGameKeys)
                .filter_by(GameKey=key)
                .one_or_none()
            )
            if entry is None:
                return EResult.Fail, EPurchaseResultDetail.BadActivationCode, None
            if entry.SteamID:
                return EResult.Fail, EPurchaseResultDetail.DuplicateActivationCode, None

            entry.SteamID = int(account_id)
            current_time = datetime.now().strftime("%m/%d/%Y %H:%M:%S")
            license_row = Steam3LicenseRecord(
                AccountID=account_id,
                PackageID=entry.AppID,
                LicenseKey=key,
                DateAdded=current_time,
                LicenseFlags=0,
                LicenseType=1,
                PaymentType=EPaymentMethod.ActivationCode.value,
                PurchaseCountryCode=None,
                TimeLimit=0,
                MinutesUsed=0,
                TimeNextProcess=None,
                ChangeNumber=0,
                OwnerAccountID=account_id,
                InitialPeriod=None,
                InitialTimeUnit=None,
                RenewalPeriod=None,
                RenewalTimeUnit=None,
                AccessToken=None,
                MasterPackageID=entry.AppID,
            )
            self.session.add(license_row)
            self.session.commit()
            return EResult.OK, EPurchaseResultDetail.NoDetail, entry.AppID
        except SQLAlchemyError as exc:
            self.session.rollback()
            log.error("[redeem_activation_key] %s", exc)
            return EResult.Fail, EPurchaseResultDetail.ContactSupport, None

    def activate_legacy_key(self, key: str, steam_id: int):
        """Legacy alias for redeem_activation_key method.

        Args:
            key (str): Activation key string.
            steam_id (int): Steam ID (full 64-bit ID, will be converted to account ID).

        Returns:
            tuple[EResult, EPurchaseResultDetail, int | None]:
                Result code, detailed result, and the associated package/app ID on success.
        """
        # Convert full steam ID to account ID (lower 32 bits)
        account_id = steam_id & 0xFFFFFFFF
        return self.redeem_activation_key(account_id, key)

    def user_has_subscription(self, account_id: int, package_id: int) -> bool:
        """Check if a user already owns a specific subscription/package.

        Args:
            account_id (int): User's account ID
            package_id (int): Package/subscription ID to check

        Returns:
            bool: True if user already owns this package, False otherwise
        """
        try:
            # Check Steam3LicenseRecord table
            exists_license = self.session.query(
                exists().where(
                    (Steam3LicenseRecord.AccountID == account_id) &
                    (Steam3LicenseRecord.PackageID == package_id)
                )
            ).scalar()

            if exists_license:
                return True

            # Also check AccountSubscriptionsRecord (legacy subscriptions)
            exists_subscription = self.session.query(
                exists().where(
                    (AccountSubscriptionsRecord.UserRegistry_UniqueID == account_id) &
                    (AccountSubscriptionsRecord.SubscriptionID == package_id) &
                    (AccountSubscriptionsRecord.SubscriptionStatus == 1)
                )
            ).scalar()

            return exists_subscription

        except SQLAlchemyError as exc:
            self.session.rollback()
            log.error("[user_has_subscription] %s", exc)
            return False

    def create_cdkey_license(
        self,
        account_id: int,
        package_id: int,
        cd_key: str,
        game_code: int,
        territory_code: int,
        serial_number: int
    ) -> EResult:
        """Create a license record for a CD key activation using CDR lookup.

        This method creates a license without relying on LegacyGameKeys table.
        The package_id should be determined from CDR based on the decoded game_code.

        Args:
            account_id (int): User's account ID
            package_id (int): Package/subscription ID from CDR
            cd_key (str): The full CD key string
            game_code (int): Decoded game code from CD key (7 bits)
            territory_code (int): Decoded territory code from CD key (8 bits)
            serial_number (int): Decoded serial number from CD key (25 bits)

        Returns:
            EResult: OK on success, error code on failure
        """
        try:
            current_time = datetime.now().strftime("%m/%d/%Y %H:%M:%S")

            # Create the license record
            license_row = Steam3LicenseRecord(
                AccountID=account_id,
                PackageID=package_id,
                LicenseKey=cd_key,
                DateAdded=current_time,
                LicenseFlags=0,
                LicenseType=1,  # Retail key activation
                PaymentType=EPaymentMethod.ActivationCode.value,
                PurchaseCountryCode=None,
                TimeLimit=0,
                MinutesUsed=0,
                TimeNextProcess=None,
                ChangeNumber=0,
                OwnerAccountID=account_id,
                InitialPeriod=None,
                InitialTimeUnit=None,
                RenewalPeriod=None,
                RenewalTimeUnit=None,
                AccessToken=None,
                MasterPackageID=package_id,
            )

            self.session.add(license_row)
            self.session.commit()

            log.info(
                f"[create_cdkey_license] Created license for account={account_id}, "
                f"package={package_id}, game_code={game_code}, serial={serial_number}"
            )

            return EResult.OK

        except SQLAlchemyError as exc:
            self.session.rollback()
            log.error("[create_cdkey_license] %s", exc)
            return EResult.Fail

    def get_app_name(self, appid: int) -> bytes:
        """
        Retrieve the name of the application with the given AppID as a byte string.

        :param session: SQLAlchemy Session instance
        :param appid: The AppID to filter by.
        :return: The name of the application as a byte string, or an empty byte string if not found.
        """
        result = self.session.query(SteamApplications.Name).filter(SteamApplications.AppID == appid).scalar()
        return result.encode('latin-1') if result else b'\x00'

    def get_or_create_leaderboard(self,
                                  app_id: int,
                                  name: str,
                                  sort_method: int,
                                  display_type: int,
                                  create_if_not_found: bool):
        """
        Return the LeaderboardRegistry row for (app_id,name).
        If not found and create_if_not_found is True, insert it.
        Returns None if missing and not created.
        """
        try:
            # lookup
            lb = self.session.query(LeaderboardRegistry).filter_by(appID=app_id, name=name).first()

            # optionally create
            if lb is None and create_if_not_found:
                lb = LeaderboardRegistry(
                    appID        = app_id,
                    name         = name,
                    sort_method  = sort_method,
                    display_type = display_type
                )
                self.session.add(lb)
                self.session.commit()   # flush & assign UniqueID

            return lb

        except SQLAlchemyError as e:
            # you may want to log e here
            self.session.rollback()
            return None

    def get_leaderboard(self, app_id: int, name: str):
        """_getLeaderboard ? existing row or None."""
        return (
            self.session
                .query(LeaderboardRegistry)
                .filter_by(appID=app_id, name=name)
                .first()
        )

    def get_leaderboard_by_id(self, lb_id: int):
        """Get leaderboard by its UniqueID."""
        return (
            self.session
                .query(LeaderboardRegistry)
                .filter_by(UniqueID=lb_id)
                .first()
        )

    def count_entries(self, lb_unique_id: int) -> int:
        """
        Return how many LeaderboardEntry rows are linked to lb_unique_id.
        """
        try:
            return self.session.query(LeaderboardEntry).filter_by(LeaderboardID=lb_unique_id).count()

        except SQLAlchemyError as e:
            # log e if you have a logger
            self.session.rollback()
            return 0

    def get_entries_range(self,
                          lb_id: int,
                          start: int,
                          end:   int
                          ) -> List[LeaderboardEntry]:
        """_getEntries by rank range."""
        return (
            self.session
                .query(LeaderboardEntry)
                .filter(
                    LeaderboardEntry.LeaderboardID == lb_id,
                    LeaderboardEntry.rank >= start,
                    LeaderboardEntry.rank <= end
                )
                .order_by(LeaderboardEntry.rank)
                .all()
        )

    def get_player_global_rank(self, lb_id: int, player_id: int) -> int:
        """_getPlayerGlobalRank."""
        entry = (
            self.session
                .query(LeaderboardEntry.rank)
                .filter_by(LeaderboardID=lb_id, friendRegistryID=player_id)
                .first()
        )
        return entry[0] if entry else 0

    def get_around_user_entries(self,
                                lb_id: int,
                                player_id: int,
                                start: int,
                                end:   int
                                ) -> List[LeaderboardEntry]:
        """_getAroundUserEntries."""
        rank = self.get_player_global_rank(lb_id, player_id)
        if not rank:
            return []
        return self.get_entries_range(lb_id, rank + start, rank + end)

    def get_friends_entries(self,
                            lb_id: int,
                            player_account_id: int,
                            start: int,
                            end:   int
                            ) -> List[LeaderboardEntry]:
        """
        Return leaderboard entries for the given player and that player's friends,
        ordered by rank, limited to [start..end].
        """
        # 1) sanitize range
        if start < 1:
            start = 1
        count = end - start + 1

        # 2) load the FriendsRegistry row for this player
        reg = (
            self.session
                .query(FriendsRegistry)
                .filter_by(accountID=player_account_id)
                .first()
        )
        if not reg:
            return []

        # 3) build list of accountIDs: self + all friends
        friend_ids = [fl.friendRegistryID for fl in reg.friends]
        ids = [reg.accountID] + friend_ids

        # 4) query the entries
        return (
            self.session
                .query(LeaderboardEntry)
                .filter(
                    LeaderboardEntry.LeaderboardID    == lb_id,
                    LeaderboardEntry.friendRegistryID.in_(ids)
                )
                .order_by(LeaderboardEntry.rank)
                .limit(count)
                .offset(start - 1)
                .all()
        )

    def set_player_score(self,
                         lb_id: int,
                         player_id: int,
                         score: int,
                         details: List[int],
                         ugc_id: int
                         ) -> None:
        """_setPlayerScore."""
        blob = b''.join(d.to_bytes(4, 'little', signed=False) for d in details)
        now = int(time.time())

        entry = (
            self.session
                .query(LeaderboardEntry)
                .filter_by(LeaderboardID=lb_id, friendRegistryID=player_id)
                .first()
        )
        if not entry:
            entry = LeaderboardEntry(
                LeaderboardID    = lb_id,
                friendRegistryID = player_id,
                rank             = 0,
                score            = score,
                time             = now,
                details          = blob,
                ugcID            = ugc_id
            )
            self.session.add(entry)
        else:
            entry.score   = score
            entry.time    = now
            entry.details = blob
            entry.ugcID   = ugc_id

        self.session.commit()

    def get_player_score_and_ugc(self,
                                 lb_id: int,
                                 player_id: int,
                                 default_score: int = 0,
                                 default_ugc: int   = 0
                                 ) -> Tuple[int,int]:
        """_getPlayerScoreAndUgcId."""
        entry = (
            self.session
                .query(LeaderboardEntry.score, LeaderboardEntry.ugcID)
                .filter_by(LeaderboardID=lb_id, friendRegistryID=player_id)
                .first()
        )
        if entry:
            return entry.score, entry.ugcID
        return default_score, default_ugc

    def set_score(self,
                  lb_id: int,
                  player_id: int,
                  score: int,
                  details: List[int],
                  mode: LeaderboardUploadScoreMethod
                  ) -> bool:
        """setScore ? calls Asc or Desc variant depending on mode & sort order."""
        # get current sort method on the registry
        reg = self.session.query(LeaderboardRegistry).get(lb_id)
        sm  = reg.sort_method if reg else None

        keep_best = (mode == LeaderboardUploadScoreMethod.KeepBest)
        force     = (mode == LeaderboardUploadScoreMethod.ForceUpdate)

        old_score, old_ugc = self.get_player_score_and_ugc(lb_id, player_id, 0, 0)

        if sm == LeaderboardSortMethod.Ascending:
            should = (score < old_score) or force
            if should:
                self.set_player_score(lb_id, player_id, score, details, old_ugc)
                self.update_ranks_asc(lb_id, score)
            return should

        if sm == LeaderboardSortMethod.Descending:
            should = (score > old_score) or force
            if should:
                self.set_player_score(lb_id, player_id, score, details, old_ugc)
                self.update_ranks_desc(lb_id, score)
            return should

        return False

    def get_entry_count(self, lb_id: int) -> int:
        """_getLeaderboardEntryCount."""
        return (
            self.session
                .query(func.count(LeaderboardEntry.UniqueID))
                .filter_by(LeaderboardID=lb_id)
                .scalar() or 0
        )

    def update_ranks_asc(self, lb_id: int, since_score: int) -> None:
        """_updateRanksAsc."""
        self.session.execute(
            """
            UPDATE Leaderboard_Entry AS e
               SET rank = (
                   SELECT COUNT(1)+1
                     FROM Leaderboard_Entry e2
                    WHERE e2.LeaderboardID = e.LeaderboardID
                      AND (e.score > e2.score
                            OR (e.score = e2.score AND e.time < e2.time))
               )
             WHERE e.LeaderboardID = :lb
               AND e.score >= :ss
            """,
            {'lb': lb_id, 'ss': since_score}
        )
        self.session.commit()

    def update_ranks_desc(self, lb_id: int, since_score: int) -> None:
        """_updateRanksDesc."""
        self.session.execute(
            """
            UPDATE Leaderboard_Entry AS e
               SET rank = (
                   SELECT COUNT(1)+1
                     FROM Leaderboard_Entry e2
                    WHERE e2.LeaderboardID = e.LeaderboardID
                      AND (e.score < e2.score
                            OR (e.score = e2.score AND e.time < e2.time))
               )
             WHERE e.LeaderboardID = :lb
               AND e.score <= :ss
            """,
            {'lb': lb_id, 'ss': since_score}
        )
        self.session.commit()


    ##################
    # Lobby Management
    ##################

    def create_lobby(self, app_id: int, lobby_type: int, lobby_flags: int, 
                    owner_account_id: int, cell_id: int, public_ip: int, max_members: int):
        """Create a new lobby in the database."""
        from utilities.database.base_dbdriver import LobbyRegistry
        
        lobby = LobbyRegistry(
            appID=app_id,
            type=lobby_type,
            flags=lobby_flags,
            owner_accountID=owner_account_id,
            cellID=cell_id,
            public_ip=public_ip,
            members_max=max_members
        )
        
        self.session.add(lobby)
        self.session.commit()
        return lobby.UniqueID

    def delete_lobby(self, lobby_id: int):
        """Delete a lobby and all associated data."""
        from utilities.database.base_dbdriver import LobbyRegistry, LobbyMembers, LobbyMetadata
        
        # Delete metadata first
        self.session.query(LobbyMetadata).filter_by(LobbyID=lobby_id).delete()
        # Delete members
        self.session.query(LobbyMembers).filter_by(LobbyID=lobby_id).delete()
        # Delete lobby itself
        self.session.query(LobbyRegistry).filter_by(UniqueID=lobby_id).delete()
        self.session.commit()

    def get_lobby(self, lobby_id: int):
        """Get lobby information by ID."""
        from utilities.database.base_dbdriver import LobbyRegistry
        return self.session.query(LobbyRegistry).filter_by(UniqueID=lobby_id).first()

    def add_lobby_member(self, lobby_id: int, account_id: int, relation: int = 1):
        """Add a member to a lobby."""
        from utilities.database.base_dbdriver import LobbyMembers
        
        # Check if already a member
        existing = self.session.query(LobbyMembers).filter_by(
            LobbyID=lobby_id, friendRegistryID=account_id
        ).first()
        
        if not existing:
            member = LobbyMembers(
                LobbyID=lobby_id,
                friendRegistryID=account_id,
                relation=relation
            )
            self.session.add(member)
            self.session.commit()

    def remove_lobby_member(self, lobby_id: int, account_id: int):
        """Remove a member from a lobby."""
        from utilities.database.base_dbdriver import LobbyMembers
        
        self.session.query(LobbyMembers).filter_by(
            LobbyID=lobby_id, friendRegistryID=account_id
        ).delete()
        self.session.commit()

    def get_lobby_members(self, lobby_id: int):
        """Get all members of a lobby."""
        from utilities.database.base_dbdriver import LobbyMembers
        return self.session.query(LobbyMembers).filter_by(LobbyID=lobby_id).all()

    def set_lobby_metadata(self, lobby_id: int, account_id: int, key: str, value: str):
        """Set or update lobby metadata key-value pair."""
        from utilities.database.base_dbdriver import LobbyMetadata
        
        # Try to find existing metadata
        metadata = self.session.query(LobbyMetadata).filter_by(
            LobbyID=lobby_id, friendRegistryID=account_id, key=key
        ).first()
        
        if metadata:
            metadata.value = value
        else:
            metadata = LobbyMetadata(
                LobbyID=lobby_id,
                friendRegistryID=account_id,
                key=key,
                value=value
            )
            self.session.add(metadata)
        
        self.session.commit()

    def get_lobby_metadata(self, lobby_id: int):
        """Get all metadata for a lobby."""
        from utilities.database.base_dbdriver import LobbyMetadata
        return self.session.query(LobbyMetadata).filter_by(LobbyID=lobby_id).all()

    def get_lobbies_by_app(self, app_id: int, limit: int = 50):
        """Get lobbies for a specific app."""
        from utilities.database.base_dbdriver import LobbyRegistry
        return self.session.query(LobbyRegistry).filter_by(appID=app_id).limit(limit).all()

    def update_lobby_owner(self, lobby_id: int, new_owner_account_id: int):
        """Update lobby owner."""
        from utilities.database.base_dbdriver import LobbyRegistry
        
        lobby = self.session.query(LobbyRegistry).filter_by(UniqueID=lobby_id).first()
        if lobby:
            lobby.owner_accountID = new_owner_account_id
            self.session.commit()
            return True
        return False

    ##################
    # Achievements
    ##################

    def get_user_achievement(self, user_id: int, app_id: int, achievement_name: str):
        """Get a specific user achievement."""
        from utilities.database.base_dbdriver import UserAchievements
        try:
            return self.session.query(UserAchievements).filter_by(
                accountID=user_id,
                appID=app_id,
                achievementName=achievement_name
            ).first()
        except Exception as e:
            log.error(f"Error getting user achievement: {e}")
            return None

    def store_user_achievement(self, user_id: int, app_id: int, achievement_name: str, unlock_time: int):
        """Store a new user achievement unlock."""
        from utilities.database.base_dbdriver import UserAchievements
        try:
            # Check if achievement already exists
            existing = self.get_user_achievement(user_id, app_id, achievement_name)
            if existing:
                log.debug(f"Achievement {achievement_name} already unlocked for user {user_id}, app {app_id}")
                return False

            # Create new achievement record
            new_achievement = UserAchievements(
                accountID=user_id,
                appID=app_id,
                achievementName=achievement_name,
                unlockTime=unlock_time,
                achieved=1
            )
            
            self.session.add(new_achievement)
            self.session.commit()
            log.info(f"Stored achievement '{achievement_name}' for user {user_id}, app {app_id}")
            return True
            
        except Exception as e:
            self.session.rollback()
            log.error(f"Error storing user achievement: {e}")
            return False

    def get_user_achievements_for_app(self, user_id: int, app_id: int):
        """Get all achievements for a user in a specific app."""
        from utilities.database.base_dbdriver import UserAchievements
        try:
            return self.session.query(UserAchievements).filter_by(
                accountID=user_id,
                appID=app_id
            ).all()
        except Exception as e:
            log.error(f"Error getting user achievements: {e}")
            return []

    def get_achievement_master_data(self, app_id: int):
        """Get achievement master data for an app."""
        from utilities.database.base_dbdriver import AchievementMaster
        try:
            return self.session.query(AchievementMaster).filter_by(appID=app_id).all()
        except Exception as e:
            log.error(f"Error getting achievement master data: {e}")
            return []

    def get_achievement_percentages(self, app_id: int):
        """Get achievement unlock percentages for an app."""
        from utilities.database.base_dbdriver import AchievementPercent
        try:
            return self.session.query(AchievementPercent).filter_by(appID=app_id).all()
        except Exception as e:
            log.error(f"Error getting achievement percentages: {e}")
            return []

    ##################
    # User Stats
    ##################

    def get_user_stats_for_app(self, user_id: int, app_id: int):
        """Get all stats for a user in a specific app."""
        from utilities.database.base_dbdriver import UserStats
        try:
            return self.session.query(UserStats).filter_by(
                user_id=user_id,
                app_id=app_id
            ).all()
        except Exception as e:
            log.error(f"Error getting user stats: {e}")
            return []

    def store_user_stat(self, user_id: int, app_id: int, stat_name: str, stat_value: str):
        """Store or update a user stat."""
        from utilities.database.base_dbdriver import UserStats
        try:
            # Check if stat already exists
            existing = self.session.query(UserStats).filter_by(
                user_id=user_id,
                app_id=app_id,
                stat=stat_name
            ).first()
            
            if existing:
                # Update existing stat
                existing.value = stat_value
            else:
                # Create new stat record
                new_stat = UserStats(
                    user_id=user_id,
                    app_id=app_id,
                    stat=stat_name,
                    value=stat_value
                )
                self.session.add(new_stat)
            
            self.session.commit()
            log.debug(f"Stored stat '{stat_name}' = '{stat_value}' for user {user_id}, app {app_id}")
            return True
            
        except Exception as e:
            self.session.rollback()
            log.error(f"Error storing user stat: {e}")
            return False

    ##################
    # Chatroom Management
    ##################

    def get_max_chatroom_id(self) -> Optional[int]:
        """
        Get the maximum chatroom UniqueID from the database.
        Returns None if no chatrooms exist or on error.
        """
        try:
            from sqlalchemy import func
            max_id = self.session.query(func.max(ChatRoomRegistry.UniqueID)).scalar()
            return max_id
        except SQLAlchemyError as e:
            log.error(f"Failed to get max chatroom ID: {e}")
            return None

    def persist_chatroom(self, chat_id: int, room_type: int, owner_id: int, clan_id: int,
                        game_id: int, name: str, created_at: datetime, flags: int,
                        officer_permission: int, member_permission: int, all_permission: int,
                        max_members: int) -> bool:
        """Persist chatroom to database using existing ChatRoomRegistry table"""
        try:
            # Generate a unique name for unnamed chatrooms (e.g., lobbies)
            # This avoids UNIQUE constraint violations on empty names
            chatroom_name = name if name else f"chatroom_{chat_id}"

            db_chatroom = ChatRoomRegistry(
                UniqueID=chat_id,
                chatroom_type=room_type,
                owner_accountID=owner_id,
                groupID=clan_id if clan_id > 0 else None,
                appID=game_id,
                chatroom_name=chatroom_name,
                datetime=created_at,
                message='',  # MOTD - empty for now
                servermessage=0,
                chatroom_flags=flags,
                owner_permissions=officer_permission,
                moderator_permissions=officer_permission,
                member_permissions=member_permission,
                default_permissions=all_permission,
                maxmembers=max_members,
                locked=0,
                metadata_info='',
                current_usercount=0
            )
            
            self.session.add(db_chatroom)
            self.session.commit()
            log.debug(f"Persisted chatroom {chat_id} to database")
            return True
        except SQLAlchemyError as e:
            self.session.rollback()
            log.error(f"Failed to persist chatroom: {e}")
            return False

    def remove_chatroom_from_db(self, chat_id: int) -> bool:
        """Remove chatroom from database using existing table structure"""
        try:
            # Remove chatroom and all related data using existing tables
            self.session.query(ChatRoomHistory).filter_by(chatroomID=chat_id).delete()
            self.session.query(ChatRoomMembers).filter_by(chatRoomID=chat_id).delete()
            self.session.query(ChatRoomRegistry).filter_by(UniqueID=chat_id).delete()
            
            self.session.commit()
            log.debug(f"Removed chatroom {chat_id} from database")
            return True
        except SQLAlchemyError as e:
            self.session.rollback()
            log.error(f"Failed to remove chatroom from database: {e}")
            return False

    def persist_chatroom_member_join(self, chat_id: int, steam_id: int, permissions: int) -> bool:
        """Persist member join to database using existing ChatRoomMembers table"""
        try:
            # Extract account ID from Steam ID for database storage
            # Convert to int explicitly since get_accountID() returns an AccountID wrapper
            account_id = int(SteamID.from_raw(steam_id).get_accountID())

            db_member = ChatRoomMembers(
                chatRoomID=chat_id,
                friendRegistryID=account_id,
                relationship=1,  # 1 = member
                inviterAccountID=None,
                memberRankDetails=int(permissions)  # Convert enum to int for database storage
            )

            self.session.add(db_member)
            self.session.commit()
            log.debug(f"Persisted member {steam_id} (account {account_id}) join to chatroom {chat_id}")
            return True
        except SQLAlchemyError as e:
            self.session.rollback()
            log.error(f"Failed to persist member join: {e}")
            return False

    def persist_chatroom_member_leave(self, chat_id: int, steam_id: int) -> bool:
        """Remove member from database using existing table structure"""
        try:
            # Extract account ID from Steam ID for database query
            # Convert to int explicitly since get_accountID() returns an AccountID wrapper
            account_id = int(SteamID.from_raw(steam_id).get_accountID())

            self.session.query(ChatRoomMembers).filter_by(
                chatRoomID=chat_id, friendRegistryID=account_id
            ).delete()
            
            self.session.commit()
            log.debug(f"Removed member {steam_id} from chatroom {chat_id}")
            return True
        except SQLAlchemyError as e:
            self.session.rollback()
            log.error(f"Failed to remove member from database: {e}")
            return False

    def persist_chatroom_message(self, chat_id: int, sender_steam_id: int, message_data: bytes) -> bool:
        """Persist chat message to database using existing ChatRoomHistory table"""
        try:
            # Extract accountID from 64-bit SteamID - the from_accountID column is INT (32-bit)
            sender_account_id = int(SteamID.from_raw(sender_steam_id).get_accountID())

            db_message = ChatRoomHistory(
                chatroomID=chat_id,
                from_accountID=sender_account_id,
                message=message_data.decode('utf-8', errors='ignore')[:255],  # Truncate to fit
                datetime=datetime.now()
            )

            self.session.add(db_message)
            self.session.commit()
            log.debug(f"Persisted message from accountID {sender_account_id} to chatroom {chat_id}")
            return True
        except SQLAlchemyError as e:
            self.session.rollback()
            log.error(f"Failed to persist message: {e}")
            return False

    ##################
    # User Statistics Management
    ##################

    def get_user_stats_cache(self, steamid: int, appid: int) -> dict:
        """Get user stats cache entry from database"""
        try:
            cache_entry = self.session.query(UserStatsCache).filter_by(
                steam_id=steamid,
                app_id=appid
            ).first()
            
            if cache_entry:
                return {
                    'crc': cache_entry.crc,
                    'pending_changes': cache_entry.pending_changes,
                    'schema_version': cache_entry.schema_version,
                    'last_updated': cache_entry.last_updated
                }
            return None
        except SQLAlchemyError as e:
            log.error(f"Database error loading stats cache: {e}")
            return None

    def get_user_stats_data(self, steamid: int, appid: int) -> dict:
        """Get user stats data from database"""
        try:
            stats_data = self.session.query(UserStatsData).filter_by(
                steam_id=steamid,
                app_id=appid
            ).all()
            
            return {stat_entry.stat_id: stat_entry.stat_value for stat_entry in stats_data}
        except SQLAlchemyError as e:
            log.error(f"Database error loading stats data: {e}")
            return {}

    def get_user_achievements_data(self, steamid: int, appid: int) -> dict:
        """Get user achievements data from database"""
        try:
            achievements_data = self.session.query(UserAchievements).filter_by(
                steam_id=steamid,
                app_id=appid
            ).all()
            
            # Group by stat_id
            achievements = {}
            for ach_entry in achievements_data:
                if ach_entry.stat_id not in achievements:
                    achievements[ach_entry.stat_id] = {}
                achievements[ach_entry.stat_id][ach_entry.bit_position] = ach_entry.achieved_at
            
            return achievements
        except SQLAlchemyError as e:
            log.error(f"Database error loading achievements data: {e}")
            return {}

    def persist_user_stats_cache(self, steamid: int, appid: int, crc: int, pending_changes: int, 
                                schema_version: int) -> bool:
        """Persist user stats cache to database"""
        try:
            current_time = datetime.now()
            
            cache_entry = self.session.query(UserStatsCache).filter_by(
                steam_id=steamid, 
                app_id=appid
            ).first()
            
            if cache_entry:
                cache_entry.crc = crc
                cache_entry.pending_changes = pending_changes
                cache_entry.last_updated = current_time
                if schema_version is not None:
                    cache_entry.schema_version = schema_version
            else:
                cache_entry = UserStatsCache(
                    steam_id=steamid,
                    app_id=appid,
                    crc=crc,
                    pending_changes=pending_changes,
                    schema_version=schema_version,
                    last_updated=current_time
                )
                self.session.add(cache_entry)
            
            self.session.commit()
            return True
        except SQLAlchemyError as e:
            self.session.rollback()
            log.error(f"Database error persisting stats cache: {e}")
            return False

    def persist_user_stats_data(self, steamid: int, appid: int, stats_data: dict) -> bool:
        """Persist user stats data to database"""
        try:
            current_time = datetime.now()
            
            for stat_id, stat_value in stats_data.items():
                stat_entry = self.session.query(UserStatsData).filter_by(
                    steam_id=steamid,
                    app_id=appid,
                    stat_id=stat_id
                ).first()
                
                if stat_entry:
                    stat_entry.stat_value = stat_value
                    stat_entry.last_updated = current_time
                else:
                    stat_entry = UserStatsData(
                        steam_id=steamid,
                        app_id=appid,
                        stat_id=stat_id,
                        stat_value=stat_value,
                        last_updated=current_time
                    )
                    self.session.add(stat_entry)
            
            self.session.commit()
            return True
        except SQLAlchemyError as e:
            self.session.rollback()
            log.error(f"Database error persisting stats data: {e}")
            return False

    def persist_user_achievements_data(self, steamid: int, appid: int, achievements_data: dict) -> bool:
        """Persist user achievements data to database"""
        try:
            current_time = datetime.now()
            
            for stat_id, achievements in achievements_data.items():
                for bit_pos, achieved_at in achievements.items():
                    if achieved_at != 0:
                        ach_entry = self.session.query(UserAchievements).filter_by(
                            steam_id=steamid,
                            app_id=appid,
                            stat_id=stat_id,
                            bit_position=bit_pos
                        ).first()
                        
                        if ach_entry:
                            ach_entry.achieved_at = achieved_at
                            ach_entry.last_updated = current_time
                        else:
                            ach_entry = UserAchievements(
                                steam_id=steamid,
                                app_id=appid,
                                stat_id=stat_id,
                                bit_position=bit_pos,
                                achieved_at=achieved_at,
                                last_updated=current_time
                            )
                            self.session.add(ach_entry)
            
            self.session.commit()
            return True
        except SQLAlchemyError as e:
            self.session.rollback()
            log.error(f"Database error persisting achievements data: {e}")
            return False

    # ==========================
    # COMMUNITY FUNCTIONALITY (integrated from community_db.py)
    # ==========================

    def _create_default_permission_templates(self):
        """Create default clan permission templates"""
        templates = [
            {
                'template_name': 'public_clan',
                'permission_edit_profile': ChatPermission.allMembers,
                'permission_make_officer': ChatPermission.owner,
                'permission_add_event': ChatPermission.ownerAndOfficer,
                'permission_choose_potw': ChatPermission.ownerAndOfficer,
                'permission_invite_member': ChatPermission.allMembers,
                'permission_kick_member': ChatPermission.ownerAndOfficer
            },
            {
                'template_name': 'private_clan',
                'permission_edit_profile': ChatPermission.ownerAndOfficer,
                'permission_make_officer': ChatPermission.owner,
                'permission_add_event': ChatPermission.ownerAndOfficer,
                'permission_choose_potw': ChatPermission.owner,
                'permission_invite_member': ChatPermission.ownerAndOfficer,
                'permission_kick_member': ChatPermission.ownerAndOfficer
            }
        ]
        
        try:
            for template_data in templates:
                existing = self.session.query(ClanPermissionTemplate).filter_by(
                    template_name=template_data['template_name']
                ).first()
                
                if not existing:
                    template = ClanPermissionTemplate(**template_data)
                    self.session.add(template)
            
            self.session.commit()
        except SQLAlchemyError as e:
            self.session.rollback()
            log.error(f"Failed to create permission templates: {e}")

    # ==========================
    # CHATROOM OPERATIONS
    # ==========================
    
    def register_chatroom(self, owner_id: int, room_type: ChatRoomType, name: str,
                         clan_id: int = 0, game_id: int = 0, 
                         officer_permission: int = ChatPermission.officerDefault,
                         member_permission: int = ChatPermission.memberDefault,
                         all_permission: int = ChatPermission.everyoneDefault,
                         max_members: int = 50, flags: int = ChatRoomFlags.none,
                         friend_chat_id: int = 0, invited_id: int = 0) -> int:
        """
        Register a new chatroom - matches C++ registerChatRoom functionality
        Returns chatroom Steam ID or 0 on failure
        """
        try:
            # Generate unique chatroom ID
            chat_id = self._get_unique_chatroom_id(room_type)
            steam_id = self._generate_chatroom_steam_id(chat_id, room_type)
            
            # Extract account ID from Steam ID for database storage
            # Convert to int since get_accountID() returns an AccountID wrapper
            from steam3.Types.steamid import SteamID
            owner_account_id = int(SteamID.from_raw(owner_id).get_accountID())
            
            chatroom = ChatRoomRegistry(
                UniqueID=chat_id,
                chatroom_type=int(room_type),
                owner_accountID=owner_account_id,
                groupID=clan_id if clan_id > 0 else None,
                appID=game_id,
                chatroom_name=name,
                datetime=datetime.now(),
                message='',  # MOTD
                servermessage=0,
                chatroom_flags=flags,
                owner_permissions=officer_permission,
                moderator_permissions=officer_permission,
                member_permissions=member_permission,
                default_permissions=all_permission,
                maxmembers=max_members,
                locked=0,
                metadata_info='',
                current_usercount=0
            )
            
            self.session.add(chatroom)
            
            # Add invited members if specified
            if invited_id != 0:
                self.set_chatroom_membership(chat_id, invited_id, ChatRelationship.invited)
            
            if friend_chat_id != 0:
                self.set_chatroom_membership(chat_id, friend_chat_id, ChatRelationship.toBeInvited)
            
            self.session.commit()
            log.info(f"Created chatroom {chat_id}: '{name}' (type={room_type}, owner={owner_id})")
            return steam_id
            
        except SQLAlchemyError as e:
            self.session.rollback()
            log.error(f"Failed to create chatroom: {e}")
            return 0
    
    def _get_unique_chatroom_id(self, room_type: ChatRoomType) -> int:
        """Generate unique chatroom ID matching C++ logic"""
        try:
            max_id = self.session.query(func.max(ChatRoomRegistry.UniqueID)).scalar() or 0
            return max_id + 1
        except SQLAlchemyError:
            return 1000000  # Fallback ID
    
    def _generate_chatroom_steam_id(self, chat_id: int, room_type: ChatRoomType) -> int:
        """Generate Steam ID for chatroom matching C++ logic"""
        instance = EInstanceFlag.ALL if room_type != ChatRoomType.lobby else EInstanceFlag.LOBBY
        steam_id = SteamID()
        steam_id.set_from_identifier(chat_id, EUniverse.PUBLIC, EType.CHAT, instance)
        return int(steam_id)
    
    def get_chatroom(self, chat_steam_id: int) -> Optional[ChatRoomRegistry]:
        """Get chatroom by Steam ID"""
        try:
            # Extract chat ID from Steam ID
            # Convert to int since get_accountID() returns an AccountID wrapper
            steam_id_obj = SteamID.from_raw(chat_steam_id)
            chat_id = int(steam_id_obj.get_accountID())

            return self.session.query(ChatRoomRegistry).filter_by(UniqueID=chat_id).first()
        except SQLAlchemyError as e:
            log.error(f"Failed to get chatroom: {e}")
            return None
    
    def set_chatroom_membership(self, chat_id: int, player_id: int, 
                               relationship: ChatRelationship) -> bool:
        """Set chatroom membership relationship"""
        try:
            existing = self.session.query(ChatRoomMembers).filter_by(
                chatRoomID=chat_id, friendRegistryID=player_id
            ).first()
            
            if existing:
                existing.relationship = int(relationship)
            else:
                member = ChatRoomMembers(
                    chatRoomID=chat_id,
                    friendRegistryID=player_id,
                    relationship=int(relationship),
                    inviterAccountID=None,
                    memberRankDetails=0
                )
                self.session.add(member)
            
            self.session.commit()
            return True
            
        except SQLAlchemyError as e:
            self.session.rollback()
            log.error(f"Failed to set chatroom membership: {e}")
            return False
    
    def get_chatroom_members(self, chat_id: int) -> List[ChatRoomMembers]:
        """Get all chatroom members"""
        try:
            return self.session.query(ChatRoomMembers).filter_by(chatRoomID=chat_id).all()
        except SQLAlchemyError as e:
            log.error(f"Failed to get chatroom members: {e}")
            return []
    
    def delete_chatroom(self, chat_id: int) -> bool:
        """Delete chatroom and all associated data"""
        try:
            # Delete in proper order due to foreign key constraints
            self.session.query(ChatRoomHistory).filter_by(chatroomID=chat_id).delete()
            self.session.query(ChatRoomSpeakers).filter_by(chatRoomID=chat_id).delete()
            self.session.query(ChatRoomMembers).filter_by(chatRoomID=chat_id).delete()
            self.session.query(ChatRoomRegistry).filter_by(UniqueID=chat_id).delete()
            
            self.session.commit()
            log.info(f"Deleted chatroom {chat_id}")
            return True
            
        except SQLAlchemyError as e:
            self.session.rollback()
            log.error(f"Failed to delete chatroom: {e}")
            return False

    # ==========================
    # LOBBY OPERATIONS
    # ==========================
    
    def register_lobby(self, app_id: int, owner_id: int, lobby_type: int,
                      flags: int = 0, cell_id: int = 0, public_ip: int = 0,
                      max_members: int = 4) -> int:
        """Register new lobby - matches C++ registerLobby functionality"""
        try:
            # Generate unique lobby ID
            lobby_id = self._get_unique_lobby_id()
            steam_id = self._generate_lobby_steam_id(lobby_id)
            
            lobby = LobbyRegistry(
                UniqueID=lobby_id,
                appID=app_id,
                type=lobby_type,
                flags=flags,
                owner_accountID=owner_id,
                cellID=cell_id,
                public_ip=public_ip,
                members_max=max_members
            )
            
            self.session.add(lobby)
            
            # Add owner as first member
            self.set_lobby_membership(lobby_id, owner_id, ChatRelationship.member)
            
            self.session.commit()
            log.info(f"Created lobby {lobby_id} (app={app_id}, owner={owner_id})")
            return steam_id
            
        except SQLAlchemyError as e:
            self.session.rollback()
            log.error(f"Failed to create lobby: {e}")
            return 0
    
    def _get_unique_lobby_id(self) -> int:
        """Generate unique lobby ID"""
        try:
            max_id = self.session.query(func.max(LobbyRegistry.UniqueID)).scalar() or 0
            return max_id + 1
        except SQLAlchemyError:
            return 2000000  # Fallback ID
    
    def _generate_lobby_steam_id(self, lobby_id: int) -> int:
        """Generate Steam ID for lobby - use LOBBY flag only, NOT MMSLobby"""
        steam_id = SteamID()
        steam_id.set_from_identifier(lobby_id, EUniverse.PUBLIC, EType.CHAT, 
                                   EInstanceFlag.LOBBY)
        return int(steam_id)
    
    def search_lobbies(self, app_id: int, filters: List[Dict], max_results: int = 50) -> List[Dict]:
        """
        Advanced lobby search with multiple filter types
        Matches C++ _searchLobbies functionality
        """
        try:
            # Base query - exclude locked/unjoinable lobbies  
            query = self.session.query(LobbyRegistry).filter(
                LobbyRegistry.appID == app_id,
                LobbyRegistry.flags.op('&')(ChatRoomFlags.locked | ChatRoomFlags.unjoinable) == 0
            )
            
            # Apply filters dynamically
            for filter_data in filters:
                filter_type = filter_data.get('type')
                
                if filter_type == 'string_compare':
                    # Join with metadata for string comparison
                    metadata_alias = self.session.query(LobbyMetadata).filter(
                        LobbyMetadata.LobbyID == LobbyRegistry.UniqueID,
                        LobbyMetadata.friendRegistryID == 0,  # Global metadata
                        LobbyMetadata.key == filter_data['key']
                    ).subquery()
                    
                    query = query.join(metadata_alias, LobbyRegistry.UniqueID == metadata_alias.c.LobbyID)
                    
                    # Apply string comparison operator
                    operator = filter_data['operator']
                    value = filter_data['value']
                    
                    if operator == '=':
                        query = query.filter(metadata_alias.c.value == value)
                    elif operator == '!=':
                        query = query.filter(metadata_alias.c.value != value)
                    elif operator == '<':
                        query = query.filter(metadata_alias.c.value < value)
                    elif operator == '>':
                        query = query.filter(metadata_alias.c.value > value)
                    elif operator == '<=':
                        query = query.filter(metadata_alias.c.value <= value)
                    elif operator == '>=':
                        query = query.filter(metadata_alias.c.value >= value)
                
                elif filter_type == 'numerical_compare':
                    # Join with metadata for numerical comparison
                    metadata_alias = self.session.query(LobbyMetadata).filter(
                        LobbyMetadata.LobbyID == LobbyRegistry.UniqueID,
                        LobbyMetadata.friendRegistryID == 0,
                        LobbyMetadata.key == filter_data['key']
                    ).subquery()
                    
                    query = query.join(metadata_alias, LobbyRegistry.UniqueID == metadata_alias.c.LobbyID)
                    
                    # Apply numerical comparison
                    operator = filter_data['operator']
                    value = filter_data['value']
                    
                    if operator == '=':
                        query = query.filter(func.cast(metadata_alias.c.value, text('REAL')) == value)
                    elif operator == '!=':
                        query = query.filter(func.cast(metadata_alias.c.value, text('REAL')) != value)
                    elif operator == '<':
                        query = query.filter(func.cast(metadata_alias.c.value, text('REAL')) < value)
                    elif operator == '>':
                        query = query.filter(func.cast(metadata_alias.c.value, text('REAL')) > value)
                    elif operator == '<=':
                        query = query.filter(func.cast(metadata_alias.c.value, text('REAL')) <= value)
                    elif operator == '>=':
                        query = query.filter(func.cast(metadata_alias.c.value, text('REAL')) >= value)
                
                elif filter_type == 'slots_available':
                    # Calculate available slots using member count
                    member_count_subquery = self.session.query(
                        LobbyMembers.LobbyID,
                        func.count(LobbyMembers.friendRegistryID).label('member_count')
                    ).filter(
                        LobbyMembers.relation == ChatRelationship.member
                    ).group_by(LobbyMembers.LobbyID).subquery()
                    
                    # Join and filter by available slots
                    query = query.outerjoin(
                        member_count_subquery, 
                        LobbyRegistry.UniqueID == member_count_subquery.c.LobbyID
                    ).filter(
                        (LobbyRegistry.members_max - func.coalesce(member_count_subquery.c.member_count, 0)) >= filter_data['value']
                    )
            
            # Apply result limit
            query = query.limit(min(max_results, 50))
            
            lobbies = query.all()
            
            # Convert to dictionary format
            result = []
            for lobby in lobbies:
                lobby_data = {
                    'lobby_id': lobby.UniqueID,
                    'app_id': lobby.appID,
                    'type': lobby.type,
                    'flags': lobby.flags,
                    'owner_id': lobby.owner_accountID,
                    'cell_id': lobby.cellID,
                    'public_ip': lobby.public_ip,
                    'members_max': lobby.members_max,
                    'distance': 0.0,  # Not implemented in emulated server
                    'weight': 0       # Not implemented in emulated server
                }
                result.append(lobby_data)
            
            return result
            
        except SQLAlchemyError as e:
            log.error(f"Failed to search lobbies: {e}")
            return []
    
    def set_lobby_membership(self, lobby_id: int, player_id: int, 
                           relationship: ChatRelationship) -> bool:
        """Set lobby membership"""
        try:
            existing = self.session.query(LobbyMembers).filter_by(
                LobbyID=lobby_id, friendRegistryID=player_id
            ).first()
            
            if existing:
                existing.relation = int(relationship)
            else:
                member = LobbyMembers(
                    LobbyID=lobby_id,
                    friendRegistryID=player_id,
                    relation=int(relationship)
                )
                self.session.add(member)
            
            self.session.commit()
            return True
            
        except SQLAlchemyError as e:
            self.session.rollback()
            log.error(f"Failed to set lobby membership: {e}")
            return False
    
    def set_lobby_metadata(self, lobby_id: int, player_id: int, key: str, value: str) -> bool:
        """Set lobby metadata (global if player_id=0, per-player otherwise)"""
        try:
            existing = self.session.query(LobbyMetadata).filter_by(
                LobbyID=lobby_id, friendRegistryID=player_id, key=key
            ).first()
            
            if existing:
                existing.value = value
            else:
                metadata = LobbyMetadata(
                    LobbyID=lobby_id,
                    friendRegistryID=player_id,
                    key=key,
                    value=value
                )
                self.session.add(metadata)
            
            self.session.commit()
            return True
            
        except SQLAlchemyError as e:
            self.session.rollback()
            log.error(f"Failed to set lobby metadata: {e}")
            return False
    
    def get_lobby_metadata(self, lobby_id: int, player_id: int = 0) -> Dict[str, str]:
        """Get lobby metadata"""
        try:
            metadata_entries = self.session.query(LobbyMetadata).filter_by(
                LobbyID=lobby_id, friendRegistryID=player_id
            ).all()
            
            return {entry.key: entry.value for entry in metadata_entries}
            
        except SQLAlchemyError as e:
            log.error(f"Failed to get lobby metadata: {e}")
            return {}

    def delete_lobby(self, lobby_id: int) -> bool:
        """Delete lobby and all associated data"""
        try:
            # Delete in proper order due to foreign key constraints
            self.session.query(LobbyMetadata).filter_by(LobbyID=lobby_id).delete()
            self.session.query(LobbyMembers).filter_by(LobbyID=lobby_id).delete()
            self.session.query(LobbyRegistry).filter_by(UniqueID=lobby_id).delete()
            
            self.session.commit()
            log.info(f"Deleted lobby {lobby_id}")
            return True
            
        except SQLAlchemyError as e:
            self.session.rollback()
            log.error(f"Failed to delete lobby: {e}")
            return False
    
    def get_lobbies_by_app(self, app_id: int, limit: int = 100) -> List[Dict]:
        """Get all lobbies for an application"""
        try:
            lobbies = self.session.query(LobbyRegistry).filter_by(appID=app_id).limit(limit).all()
            
            result = []
            for lobby in lobbies:
                lobby_data = {
                    'lobby_id': lobby.UniqueID,
                    'app_id': lobby.appID,
                    'type': lobby.type,
                    'flags': lobby.flags,
                    'owner_id': lobby.owner_accountID,
                    'cell_id': lobby.cellID,
                    'public_ip': lobby.public_ip,
                    'members_max': lobby.members_max
                }
                result.append(lobby_data)
            
            return result
            
        except SQLAlchemyError as e:
            log.error(f"Failed to get lobbies by app: {e}")
            return []

    # ==========================
    # CLAN OPERATIONS
    # ==========================
    
    def register_clan(self, owner_id: int, name: str, tag: str, is_public: bool = True,
                     template_name: str = 'public_clan') -> int:
        """Register new clan - matches C++ registerClan functionality"""
        try:
            # Check name/tag availability
            if not self._is_clan_name_available(name):
                log.warning(f"Clan name '{name}' not available")
                return 0
            
            if not self._is_clan_tag_available(tag):
                log.warning(f"Clan tag '{tag}' not available")
                return 0
            
            # Get permission template
            template = self.session.query(ClanPermissionTemplate).filter_by(
                template_name=template_name
            ).first()
            
            if not template:
                template = self.session.query(ClanPermissionTemplate).filter_by(
                    template_name='public_clan'
                ).first()
            
            # Generate unique clan ID
            clan_id = self._get_unique_clan_id()
            
            clan = CommunityClanRegistry(
                UniqueID=clan_id,
                clan_name=name,
                clan_tag=tag,
                owner_accountID=owner_id,
                clan_status=1 if is_public else 0,
                profile_permisions=template.permission_edit_profile if template else ChatPermission.allMembers,
                moderator_permissions=template.permission_make_officer if template else ChatPermission.owner,
                event_permissions=template.permission_add_event if template else ChatPermission.ownerAndOfficer,
                potw_permissions=template.permission_choose_potw if template else ChatPermission.ownerAndOfficer,
                invite_permissions=template.permission_invite_member if template else ChatPermission.allMembers,
                kick_permissions=template.permission_kick_member if template else ChatPermission.ownerAndOfficer
            )
            
            self.session.add(clan)
            
            # Add owner as first member
            self.set_clan_membership(clan_id, owner_id, ChatRelationship.member, rank=1)  # ClanRank_owner
            
            self.session.commit()
            log.info(f"Created clan {clan_id}: '{name}' ['{tag}'] (owner={owner_id})")
            return clan_id
            
        except SQLAlchemyError as e:
            self.session.rollback()
            log.error(f"Failed to create clan: {e}")
            return 0
    
    def _get_unique_clan_id(self) -> int:
        """Generate unique clan ID"""
        try:
            max_id = self.session.query(func.max(CommunityClanRegistry.UniqueID)).scalar() or 0
            return max_id + 1
        except SQLAlchemyError:
            return 3000000  # Fallback ID
    
    def _is_clan_name_available(self, name: str) -> bool:
        """Check if clan name is available"""
        try:
            existing = self.session.query(CommunityClanRegistry).filter_by(clan_name=name).first()
            return existing is None
        except SQLAlchemyError:
            return False
    
    def _is_clan_tag_available(self, tag: str) -> bool:
        """Check if clan tag is available"""
        try:
            existing = self.session.query(CommunityClanRegistry).filter_by(clan_tag=tag).first()
            return existing is None
        except SQLAlchemyError:
            return False
    
    def set_clan_membership(self, clan_id: int, player_id: int, 
                          relationship: ChatRelationship, rank: int = 3) -> bool:
        """Set clan membership and rank"""
        try:
            existing = self.session.query(CommunityClanMembers).filter_by(
                CommunityClanID=clan_id, friendRegistryID=player_id
            ).first()
            
            if existing:
                existing.relationship = int(relationship)
                existing.user_rank = rank
            else:
                member = CommunityClanMembers(
                    CommunityClanID=clan_id,
                    friendRegistryID=player_id,
                    user_rank=rank,
                    relationship=int(relationship),
                    is_maingroup=True
                )
                self.session.add(member)
            
            self.session.commit()
            return True
            
        except SQLAlchemyError as e:
            self.session.rollback()
            log.error(f"Failed to set clan membership: {e}")
            return False
    
    def get_clan_member_permission_level(self, clan_id: int, player_id: int) -> int:
        """Get player's permission level in clan - matches C++ logic"""
        try:
            member = self.session.query(CommunityClanMembers).filter_by(
                CommunityClanID=clan_id, friendRegistryID=player_id
            ).first()
            
            if not member or member.relationship != ChatRelationship.member:
                return 0  # ClanPermission_nobody
            
            # Map rank to permission level
            rank = member.user_rank
            if rank == 1:  # ClanRank_owner
                return 7  # ClanPermission_allMembers (includes all permissions)
            elif rank == 2:  # ClanRank_officer
                return 3  # ClanPermission_ownerAndOfficer
            elif rank == 3:  # ClanRank_member
                return 4  # ClanPermission_member
            else:
                return 0  # ClanPermission_nobody
                
        except SQLAlchemyError as e:
            log.error(f"Failed to get clan member permission: {e}")
            return 0
    
    def is_allowed_clan_action(self, clan_id: int, player_id: int, permission_field: str) -> bool:
        """Check if player is allowed to perform clan action"""
        try:
            clan = self.session.query(CommunityClanRegistry).filter_by(UniqueID=clan_id).first()
            if not clan:
                return False
            
            player_permission_level = self.get_clan_member_permission_level(clan_id, player_id)
            required_permission = getattr(clan, permission_field, 0)
            
            return (required_permission & player_permission_level) != 0
            
        except SQLAlchemyError as e:
            log.error(f"Failed to check clan permission: {e}")
            return False

    # ==========================
    # DATABASE VIEWS AND OPTIMIZATION
    # ==========================
    
    def create_database_views(self):
        """Create database views for performance optimization"""
        try:
            # Create lobby search view for efficient member counting
            lobby_view_sql = """
            CREATE OR REPLACE VIEW lobby_search_view AS
            SELECT 
                l.UniqueID as lobby_id,
                l.appID as app_id,
                l.type,
                l.flags,
                l.owner_accountID as owner_id,
                l.cellID as cell_id,
                l.public_ip,
                l.members_max,
                COALESCE(member_count.count, 0) as members_count,
                (l.members_max - COALESCE(member_count.count, 0)) as available_slots
            FROM Lobby_Registry l
            LEFT JOIN (
                SELECT LobbyID, COUNT(*) as count 
                FROM Lobby_Members 
                WHERE relation = 3 
                GROUP BY LobbyID
            ) member_count ON l.UniqueID = member_count.LobbyID
            """
            
            # Create chatroom member count view
            chatroom_view_sql = """
            CREATE OR REPLACE VIEW chatroom_member_count AS
            SELECT 
                cr.UniqueID as chat_id,
                COUNT(cm.friendRegistryID) as members_count,
                (cr.maxmembers - COUNT(cm.friendRegistryID)) as available_slots
            FROM chatrooms_registry cr
            LEFT JOIN chatroom_members cm ON cr.UniqueID = cm.chatRoomID
            WHERE cm.relationship IS NULL OR (cm.relationship != 1 AND cm.relationship != 4)
            GROUP BY cr.UniqueID
            """
            
            self.session.execute(text(lobby_view_sql))
            self.session.execute(text(chatroom_view_sql))
            self.session.commit()
            
            log.info("Database views created successfully")
            
        except SQLAlchemyError as e:
            self.session.rollback()
            log.error(f"Failed to create database views: {e}")
    
    def initialize_default_data(self):
        """Initialize default data for community features"""
        try:
            # Create default permission templates
            self._create_default_permission_templates()
            
            # Create database views
            self.create_database_views()
            
            log.info("Default community data structures prepared")
            
        except Exception as e:
            log.error(f"Failed to initialize default data: {e}")

    # =============================================================================
    # HELPER METHODS
    # =============================================================================
    
    def _get_unique_chatroom_id(self, room_type: ChatRoomType) -> int:
        """Generate unique chatroom ID"""
        try:
            max_id = self.session.query(func.max(self.ChatRoomRegistry.UniqueID)).scalar() or 0
            return max_id + 1
        except SQLAlchemyError:
            return 1000000  # Fallback ID
    
    def _generate_chatroom_steam_id(self, chat_id: int, room_type: ChatRoomType) -> int:
        """Generate Steam ID for chatroom"""
        if room_type == ChatRoomType.lobby:
            instance = EInstanceFlag.LOBBY
        elif room_type == ChatRoomType.clan:
            instance = EInstanceFlag.CLAN
        else:
            instance = EInstanceFlag.ALL
            
        steam_id = SteamID()
        steam_id.set_from_identifier(chat_id, EUniverse.PUBLIC, EType.CHAT, instance)
        return int(steam_id)
    
    def _get_unique_lobby_id(self) -> int:
        """Generate unique lobby ID"""
        try:
            max_id = self.session.query(func.max(self.LobbyRegistry.UniqueID)).scalar() or 0
            return max_id + 1
        except SQLAlchemyError:
            return 2000000  # Fallback ID
    
    def _generate_lobby_steam_id(self, lobby_id: int) -> int:
        """Generate Steam ID for lobby"""
        steam_id = SteamID()
        steam_id.set_from_identifier(lobby_id, EUniverse.PUBLIC, EType.CHAT, 
                                   EInstanceFlag.LOBBY)
        return int(steam_id)


    # =============================================================================
    # COMMUNITY DATABASE INITIALIZATION
    # =============================================================================
    
    def initialize_community_database(self):
        """
        Initialize community database features
        Creates views, default data, and optimizations matching C++ functionality
        """
        log.info("Initializing community database features...")
        
        try:
            # Create database views for performance
            self.create_community_views()
            
            # Create database indexes for performance
            self.create_database_indexes()
            
            # Initialize default permission templates
            self.create_default_permission_templates()
            
            # Create default data
            self.initialize_default_data()
            
            log.info("Community database initialization completed successfully")
            return True
            
        except Exception as e:
            log.error(f"Failed to initialize community database: {e}")
            return False

    def create_community_views(self):
        """Create database views for efficient community operations"""
        if not self.session:
            log.error("Database session not available")
            return
        
        try:
            # Lobby search view with member counting (updated table/column names)
            lobby_view_sql = """
            CREATE OR REPLACE VIEW lobby_search_view AS
            SELECT 
                l.UniqueID as lobby_id,
                l.AppID as app_id,
                l.LobbyType as lobby_type,
                l.LobbyFlags as lobby_flags,
                l.OwnerID as owner_id,
                l.MaxMembers as max_members,
                l.CurrentMembers as current_members,
                l.TimeCreated as created_time,
                COALESCE(member_count.count, 0) as actual_member_count,
                (l.MaxMembers - COALESCE(member_count.count, 0)) as available_slots
            FROM Lobby_Registry l
            LEFT JOIN (
                SELECT LobbyID, COUNT(*) as count 
                FROM Lobby_Members 
                WHERE Relationship = 1
                GROUP BY LobbyID
            ) member_count ON l.UniqueID = member_count.LobbyID;
            """
            
            # Chatroom member count view (updated table/column names)
            chatroom_view_sql = """
            CREATE OR REPLACE VIEW chatroom_member_count AS
            SELECT 
                cr.UniqueID as chat_id,
                cr.Name as name,
                cr.ChatRoomType as room_type,
                cr.OwnerID as owner_id,
                cr.MaxMembers as max_members,
                cr.TimeCreated as created_time,
                COUNT(CASE WHEN cm.Relationship = 3 THEN 1 END) as members_count,
                (COALESCE(cr.MaxMembers, 50) - COUNT(CASE WHEN cm.Relationship = 3 THEN 1 END)) as available_slots
            FROM chatrooms_registry cr
            LEFT JOIN chatroom_members cm ON cr.UniqueID = cm.ChatRoomID
            GROUP BY cr.UniqueID;
            """
            
            # Clan member count view (updated table/column names)
            clan_view_sql = """
            CREATE OR REPLACE VIEW clan_member_count AS
            SELECT 
                ccr.UniqueID as clan_id,
                ccr.ClanName as name,
                ccr.ClanTag as tag,
                ccr.OwnerID as owner_id,
                ccr.ClanStatus as is_public,
                COUNT(CASE WHEN ccm.Relationship = 3 THEN 1 END) as members_count,
                COUNT(CASE WHEN ccm.Relationship = 3 AND ccm.UserRank = 2 THEN 1 END) as officer_count
            FROM Community_ClanRegistry ccr
            LEFT JOIN Community_Clan_Members ccm ON ccr.UniqueID = ccm.CommunityClanID
            GROUP BY ccr.UniqueID;
            """
            
            # Advanced lobby search view for metadata filtering (updated table name)
            lobby_metadata_view_sql = """
            CREATE OR REPLACE VIEW lobby_metadata_search AS
            SELECT 
                lsv.*,
                GROUP_CONCAT(CONCAT(lm.Key, '=', lm.Value) SEPARATOR ';') as metadata_string
            FROM lobby_search_view lsv
            LEFT JOIN lobby_metadata lm ON lsv.lobby_id = lm.LobbyID AND lm.PlayerID = 0
            GROUP BY lsv.lobby_id;
            """
            
            # Execute all view creation statements
            views = [
                ("lobby_search_view", lobby_view_sql),
                ("chatroom_member_count", chatroom_view_sql), 
                ("clan_member_count", clan_view_sql),
                ("lobby_metadata_search", lobby_metadata_view_sql)
            ]
            
            for view_name, view_sql in views:
                try:
                    self.session.execute(text(view_sql))
                    log.info(f"Created view: {view_name}")
                except Exception as e:
                    log.warning(f"Failed to create view {view_name}: {e}")
            
            self.session.commit()
            log.info("Database views created successfully")
            
        except Exception as e:
            self.session.rollback()
            log.error(f"Failed to create community views: {e}")

    def create_database_indexes(self):
        """Create database indexes for performance optimization"""
        if not self.session:
            return
        
        try:
            # Performance indexes for community features (updated table/column names)
            indexes = [
                # Chatroom indexes
                "CREATE INDEX IF NOT EXISTS idx_chatroom_type ON chatrooms_registry (ChatRoomType)",
                "CREATE INDEX IF NOT EXISTS idx_chatroom_owner ON chatrooms_registry (OwnerID)",
                "CREATE INDEX IF NOT EXISTS idx_chatroom_app ON chatrooms_registry (GameID)",
                "CREATE INDEX IF NOT EXISTS idx_chatroom_members_chat ON chatroom_members (ChatRoomID)",
                "CREATE INDEX IF NOT EXISTS idx_chatroom_members_player ON chatroom_members (PlayerID)",
                "CREATE INDEX IF NOT EXISTS idx_chatroom_members_relationship ON chatroom_members (Relationship)",
                
                # Lobby indexes  
                "CREATE INDEX IF NOT EXISTS idx_lobby_app ON Lobby_Registry (AppID)",
                "CREATE INDEX IF NOT EXISTS idx_lobby_owner ON Lobby_Registry (OwnerID)",
                "CREATE INDEX IF NOT EXISTS idx_lobby_type ON Lobby_Registry (LobbyType)",
                "CREATE INDEX IF NOT EXISTS idx_lobby_flags ON Lobby_Registry (LobbyFlags)",
                "CREATE INDEX IF NOT EXISTS idx_lobby_members_lobby ON Lobby_Members (LobbyID)",
                "CREATE INDEX IF NOT EXISTS idx_lobby_members_player ON Lobby_Members (PlayerID)",
                "CREATE INDEX IF NOT EXISTS idx_lobby_metadata_lobby ON lobby_metadata (LobbyID)",
                "CREATE INDEX IF NOT EXISTS idx_lobby_metadata_key ON lobby_metadata (Key)",
                
                # Clan indexes
                "CREATE INDEX IF NOT EXISTS idx_clan_name ON Community_ClanRegistry (ClanName)",
                "CREATE INDEX IF NOT EXISTS idx_clan_tag ON Community_ClanRegistry (ClanTag)",
                "CREATE INDEX IF NOT EXISTS idx_clan_owner ON Community_ClanRegistry (OwnerID)",
                "CREATE INDEX IF NOT EXISTS idx_clan_status ON Community_ClanRegistry (ClanStatus)",
                "CREATE INDEX IF NOT EXISTS idx_clan_members_clan ON Community_Clan_Members (CommunityClanID)",
                "CREATE INDEX IF NOT EXISTS idx_clan_members_player ON Community_Clan_Members (PlayerID)",
                "CREATE INDEX IF NOT EXISTS idx_clan_members_relationship ON Community_Clan_Members (Relationship)",
                "CREATE INDEX IF NOT EXISTS idx_clan_members_rank ON Community_Clan_Members (UserRank)",
                
                # Event indexes
                "CREATE INDEX IF NOT EXISTS idx_clan_events_clan ON community_clan_events (CommunityClanID)",
                "CREATE INDEX IF NOT EXISTS idx_clan_events_time ON community_clan_events (StartTime)",
                "CREATE INDEX IF NOT EXISTS idx_clan_events_type ON community_clan_events (EventType)",
                
                # Friends indexes
                "CREATE INDEX IF NOT EXISTS idx_friends_account ON friends_registry (UniqueID)",
                "CREATE INDEX IF NOT EXISTS idx_friends_persona ON friends_registry (PersonaName)",
                "CREATE INDEX IF NOT EXISTS idx_friends_list_player ON friends_friendslist (PlayerID)",
                "CREATE INDEX IF NOT EXISTS idx_friends_list_friend ON friends_friendslist (FriendID)",
            ]
            
            for index_sql in indexes:
                try:
                    self.session.execute(text(index_sql))
                except Exception as e:
                    log.warning(f"Failed to create index: {e}")
            
            self.session.commit()
            log.info("Database indexes created successfully")
            
        except Exception as e:
            self.session.rollback()
            log.error(f"Failed to create database indexes: {e}")

    def create_default_permission_templates(self):
        """Create default clan permission templates matching C++ defaults"""
        if not self.session:
            return
        
        try:
            # Templates with integer permission values matching ChatPermission enum values
            templates = [
                {
                    'template_name': 'public_clan',
                    'permission_edit_profile': 8,      # talk permission for all members
                    'permission_make_officer': 896,    # owner permission
                    'permission_add_event': 154,       # owner and officer
                    'permission_choose_potw': 154,     # owner and officer  
                    'permission_invite_member': 8,     # all members
                    'permission_kick_member': 154      # owner and officer
                },
                {
                    'template_name': 'private_clan',
                    'permission_edit_profile': 154,    # owner and officer only
                    'permission_make_officer': 896,    # owner only
                    'permission_add_event': 154,       # owner and officer
                    'permission_choose_potw': 896,     # owner only
                    'permission_invite_member': 154,   # owner and officer
                    'permission_kick_member': 154      # owner and officer
                },
                {
                    'template_name': 'gaming_clan',
                    'permission_edit_profile': 154,    # owner and officer
                    'permission_make_officer': 896,    # owner only
                    'permission_add_event': 8,         # all members can add events
                    'permission_choose_potw': 154,     # owner and officer
                    'permission_invite_member': 8,     # all members
                    'permission_kick_member': 154      # owner and officer
                }
            ]
            
            for template_data in templates:
                existing = self.session.query(self.ClanPermissionTemplate).filter_by(
                    template_name=template_data['template_name']
                ).first()
                
                if not existing:
                    template = self.ClanPermissionTemplate(**template_data)
                    self.session.add(template)
                    log.info(f"Created permission template: {template_data['template_name']}")
            
            self.session.commit()
            log.info("Permission templates initialized")
            
        except Exception as e:
            self.session.rollback()
            log.error(f"Failed to create permission templates: {e}")

    def verify_community_tables(self):
        """Verify that all community tables exist and are properly structured"""
        if not self.session:
            log.error("Database session not available")
            return False
        
        try:
            # Check required tables exist (updated table names)
            required_tables = [
                'chatrooms_registry',
                'chatroom_members', 
                'chatroom_speakers',
                'Community_ClanRegistry',
                'Community_Clan_Members',
                'community_clan_events',
                'Lobby_Registry',
                'Lobby_Members',
                'lobby_metadata',
                'chat_room_group',
                'chat_room_group_chat',
                'chat_room_group_role',
                'clan_permission_template',
                'clan_event_attendance',
                'friends_registry',
                'friends_friendslist'
            ]
            
            for table_name in required_tables:
                result = self.session.execute(
                    text("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = :table_name"),
                    {'table_name': table_name}
                ).scalar()
                
                if result == 0:
                    log.warning(f"Table {table_name} does not exist")
                    return False
            
            log.info("All community tables verified successfully")
            return True
            
        except Exception as e:
            log.error(f"Failed to verify community tables: {e}")
            return False

    def cleanup_expired_lobbies(self, hours_old: int = 24):
        """Clean up expired empty lobbies"""
        if not self.session:
            return
        
        try:
            # Clean up empty lobbies older than specified hours
            cutoff_time = datetime.now() - timedelta(hours=hours_old)
            
            # Find empty lobbies older than cutoff time
            empty_lobbies = self.session.query(self.LobbyRegistry).filter(
                self.LobbyRegistry.CurrentMembers == 0,
                self.LobbyRegistry.TimeCreated < cutoff_time
            ).all()
            
            lobby_count = len(empty_lobbies)
            if lobby_count > 0:
                # Delete metadata and members first
                for lobby in empty_lobbies:
                    self.session.query(self.LobbyMetadata).filter_by(LobbyID=lobby.UniqueID).delete()
                    self.session.query(self.LobbyMembers).filter_by(LobbyID=lobby.UniqueID).delete()
                
                # Delete the lobbies
                self.session.query(self.LobbyRegistry).filter(
                    self.LobbyRegistry.CurrentMembers == 0,
                    self.LobbyRegistry.TimeCreated < cutoff_time
                ).delete()
                
                self.session.commit()
                log.info(f"Cleaned up {lobby_count} expired empty lobbies")
            
        except Exception as e:
            self.session.rollback()
            log.error(f"Failed to cleanup expired lobbies: {e}")


    def get_marketing_messages_by_date(self, cdr_datetime_str: str, count: int = 5) -> List[int]:
        """
        Retrieve marketing message GIDs from the MarketingMessages table.

        Selects up to `count` messages that are closest to and not past the CDR date.
        Messages are sorted by DATETIME descending (most recent first) where DATETIME <= cdr_date.

        Args:
            cdr_datetime_str: CDR datetime string in format "MM/DD/YYYY HH:MM:SS"
            count: Number of messages to retrieve (default 5, range 3-5)

        Returns:
            List of GID integers for the marketing messages
        """
        try:
            # Parse the CDR datetime string
            cdr_datetime = datetime.strptime(cdr_datetime_str, "%m/%d/%Y %H:%M:%S")

            # Ensure count is in valid range
            count = max(3, min(5, count))

            # Query using raw SQL for simplicity
            query = text("""
                SELECT GID
                FROM MarketingMessages
                WHERE `DATETIME` <= :cdr_date
                ORDER BY `DATETIME` DESC
                LIMIT :limit
            """)

            result = self.session.execute(query, {
                'cdr_date': cdr_datetime,
                'limit': count
            })

            gids = [row[0] for row in result.fetchall()]

            if gids:
                log.debug(f"Retrieved {len(gids)} marketing messages for date {cdr_datetime_str}")
            else:
                log.warning(f"No marketing messages found for date {cdr_datetime_str}")

            return gids

        except Exception as e:
            log.error(f"Failed to get marketing messages: {e}")
            return []


def get_cmdb():
    """Get the global database instance"""
    global cmdb_instance
    if 'cmdb_instance' not in globals():
        from config import get_config as read_config
        cmdb_instance = cm_dbdriver(read_config())
    return cmdb_instance

