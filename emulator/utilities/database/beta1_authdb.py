import logging
import struct
import time

import globalvars
import utilities.time
from utilities import blobs
from utilities.database import base_dbdriver, dbengine
from utilities.beta1_keyvalidation import validateBeta1Key
from config import get_config

log = logging.getLogger("BETA1DB")
config = get_config()


def k(n):
    return struct.pack("<I", n)


def k_v1(n):
    return struct.pack("<Q", n)


class beta1_dbdriver:

    def __init__(self, config):
        self.config = config
        while globalvars.mariadb_initialized != True:
            continue
        self.db_driver = dbengine.create_database_driver()
        self.db_driver.connect()

        self.Users_table = base_dbdriver.Beta1_User.__table__
        self.Beta1_Users = base_dbdriver.Beta1_User
        self.Subscription_table = base_dbdriver.Beta1_Subscriptions.__table__
        self.Beta1_Subscriptions = base_dbdriver.Beta1_Subscriptions
        # Create a session for ORM operations
        self.session = self.db_driver.get_session()

    def insert_user(self, username, createtime, accountkey, salt, _hash, user_id: int = None):
        # decode once
        username_str   = username.decode('latin-1')
        accountkey_str = accountkey.decode('latin-1')
        salt_str       = salt.decode('latin-1')
        hash_str       = _hash.decode('latin-1')

        # SPECIAL-KEY FLOW?
        if self.config.get('force_beta1_specialkey', '').lower() == 'true':
            # 1) Lookup existing user by username
            user = (
                self.session
                    .query(self.Users_table)
                    .filter_by(username=username_str)
                    .first()
            )
            # not found, or they've already filled in any of these ? cannot proceed
            if not user or user.createtime or user.salt or user.hash:
                return -3

            # 2) Validate the special key
            if validateBeta1Key(user.id, accountkey):
                # 3) update the record
                user.accountkey = accountkey_str
                user.salt       = salt_str
                user.hash       = hash_str
                user.createtime = createtime
                try:
                    self.session.commit()
                    return True
                except Exception:
                    self.session.rollback()
                    return False
            else:
                return -4

        # ??????????????????????????????
        # NORMAL INSERT-NEW-USER FLOW
        # ??????????????????????????????

        # 1) If an explicit ID was given, make sure it isn't already used
        if user_id is not None:
            existing_by_id = (
                self.session
                    .query(self.Users_table)
                    .filter_by(id=user_id)
                    .first()
            )
            if existing_by_id:
                print(f"ID `{user_id}` is already taken. User not inserted.")
                return -2

        # 2) Make sure the username isn't already taken
        existing_by_name = (
            self.session
                .query(self.Users_table)
                .filter_by(username=username_str)
                .first()
        )
        if existing_by_name:
            print(f"Username '{username_str}' already exists. User not inserted.")
            return -1

        # 3) Build and insert the new user
        user_kwargs = {
            'username':   username_str,
            'createtime': createtime,
            'accountkey': accountkey_str,
            'salt':       salt_str,
            'hash':       hash_str,
        }
        if user_id is not None:
            user_kwargs['id'] = user_id

        new_user = base_dbdriver.Beta1_User(**user_kwargs)
        self.session.add(new_user)
        try:
            self.session.commit()
            return True
        except Exception as e:
            self.session.rollback()
            print(f"Failed to insert user: {e}")
            return False

    def insert_subscription(self, username, subid, subtime):
        username = username.decode('latin-1') if isinstance(username, bytes) else username
        existing_subscription = self.session.query(base_dbdriver.Beta1_Subscriptions).filter_by(username = username, subid = subid).first()
        if existing_subscription is not None:
            print("Subscription already exists. Skipping insertion.")
            return False  # Indicate that insertion was skipped
        try:
            subscription = base_dbdriver.Beta1_Subscriptions(username = username, subid = subid, subtime = subtime)
            self.session.add(subscription)
            self.session.commit()
            return True  # Indicate successful insertion
        except Exception as e:
            print(f"Failed to insert subscription: {e}")
            self.session.rollback()
            return False

    def remove_subscription(self, username, subid):
        username = username.decode('latin-1') if isinstance(username, bytes) else username
        # Begin a transaction
        with self.session.begin():
            try:
                # Query for the mapped instance using the ORM interface
                subscription = self.session.query(self.Beta1_Subscriptions).filter_by(username = username, subid = subid).first()
                if subscription:
                    # Delete the ORM-mapped instance
                    self.session.delete(subscription)
                    # Commit the transaction

                    self.session.commit()
                    return True
                else:
                    # No such subscription exists
                    print("No subscription found to delete.")
                    return False
            except Exception as e:
                # Handle any exceptions, rollback the transaction if needed
                self.session.rollback()
                print(f"Failed to delete subscription: {e}")
                return False

    def remove_subscriptions_by_username(self, username):
        # Decode the username if it's not already in string format
        username = username.decode('latin-1') if isinstance(username, bytes) else username

        # Directly delete all matching subscriptions for the username
        deleted_count = self.session.query(self.Beta1_Subscriptions).filter_by(username = username).delete()
        self.session.commit()

        # Return the count of deleted rows, could be useful for verification or logging
        return deleted_count

    def get_user(self, username):
        if isinstance(username, bytes):
            username = username.decode('latin-1')
        return self.session.query(self.Users_table).filter_by(username=username).first()

    def delete_user(self, username):
        # Decode the username if it's not already in string format
        username = username.decode('latin-1') if isinstance(username, bytes) else username

        # Query and delete the user(s) directly without loading the instances
        deleted_count = self.session.query(self.Users_table).filter_by(username = username).delete()
        self.session.commit()

        # If deleted_count is greater than 0, then deletion was successful
        return deleted_count > 0

    def get_salt_and_hash(self, username):
        row = self.get_user(username)
        if row is None:
            return None, None
        print(repr(row))
        return bytes.fromhex(row.salt), bytes.fromhex(row.hash)

    def edit_subscription(self, username, subid, subtime = 0, remove_sub = False):
        subid = int(subid)
        subtime = int(subtime)
        if remove_sub:
            self.remove_subscription(username, subid)
        else:
            self.insert_subscription(username, subid, subtime)
            #self.db_driver.execute_query(f"INSERT INTO beta1_subscriptions VALUES ( CAST('{username}' AS BLOB), {subid}, {subtime})")

    def create_user(self, binblob, version):
        userblob = blobs.blob_unserialize(binblob)
        if b"__slack__" in userblob:
            numkeys = 11
        else:
            numkeys = 10
        if len(userblob) != numkeys:
            raise Exception()

        if userblob[b"\x00\x00\x00\x00"] != struct.pack("<H", 1):
            raise Exception()

        username = userblob[b"\x01\x00\x00\x00"]
        if username[-1] != 0:
            raise Exception()

        username = username[:-1]

        createtime = utilities.time.steamtime_to_unixtime(userblob[b"\x02\x00\x00\x00"])

        accountkey = userblob[b"\x03\x00\x00\x00"]
        if accountkey[-1] != 0:
            raise Exception()

        accountkey = accountkey[:-1]

        pwddetails = userblob[b"\x05\x00\x00\x00"][username]

        if len(pwddetails) != 2:
            raise Exception()

        hash = pwddetails[b"\x01\x00\x00\x00"]

        salt = pwddetails[b"\x02\x00\x00\x00"]

        # First we check if the name already exists
        if self.get_user(username) is not None :
            log.info(f"Username {username} already exists")
            return False
            # TODO send suggested usernames?
        print(username, int(createtime), accountkey, salt.hex(), hash.hex())
        #self.db_driver.execute_query(f"INSERT INTO beta1_subscriptions VALUES (CAST('{username}' AS BLOB), {int(createtime)}, CAST('{accountkey}' AS BLOB), CAST('{salt.hex( )}' AS BLOB), CAST('{hash.hex( )}' AS BLOB))")
        self.insert_user(username, int(createtime), accountkey, salt.hex().encode('latin-1'), hash.hex().encode('latin-1'))
        log.info(f"User {username} Successfully Registered")
        return True

    def get_user_blob(self, username, CDR, version):
        # Convert username to correct format if necessary (assuming it's in bytes)
        if isinstance(username, bytes):
            username_str = username.decode('latin-1')
        else:
            username_str = username

        # Retrieve subscriptions using ORM
        subrows = self.session.query(self.Subscription_table).filter_by(username = username_str).all()
        print(subrows)
        row = self.get_user(username_str)
        if row is None:
            return None

        blob = {}

        # Assuming struct.pack and utils methods are defined elsewhere
        blob[b"\x00\x00\x00\x00"] = struct.pack("<H", 1)
        blob[b"\x01\x00\x00\x00"] = username_str.encode() + b"\x00"
        blob[b"\x02\x00\x00\x00"] = utilities.time.unixtime_to_steamtime(row.createtime)
        blob[b"\x03\x00\x00\x00"] = row.accountkey.encode('latin-1') + b"\x00"

        entry = {}
        entry[b"\x01\x00\x00\x00"] = k_v1(row.id) if version == 1 else k(row.id)
        entry[b"\x02\x00\x00\x00"] = struct.pack("<H", 1)
        entry[b"\x03\x00\x00\x00"] = {}

        blob[b"\x06\x00\x00\x00"] = {username_str.encode('latin-1'):entry}

        subs = {}
        for subrow in subrows:
            entry = {}
            subid_bytes = struct.pack('<I', subrow.subid)

            entry[b"\x01\x00\x00\x00"] = utilities.time.unixtime_to_steamtime(subrow.subtime)
            entry[b"\x02\x00\x00\x00"] = b"\x00" * 8

            subs[subid_bytes] = entry

        blob[b"\x07\x00\x00\x00"] = subs

        apps = {}
        for subrow in subrows:
            subid_bytes = struct.pack('<I', subrow.subid)
            for key in CDR[b"\x02\x00\x00\x00"][subid_bytes][b"\x06\x00\x00\x00"]:
                logging.info(f"Added app {struct.unpack('<I', key)[0]} for sub {subrow.subid}")
                apps[key] = b""

        # DerivedSubscribedAppsRecord
        blob[b"\x08\x00\x00\x00"] = apps

        # LastRecalcDerivedSubscribedAppsTime
        blob[b"\x09\x00\x00\x00"] = utilities.time.unixtime_to_steamtime(time.time())

        # CellId
        blob[b"\x0a\x00\x00\x00"] = b"\x00\x00" + struct.pack('<h', int(globalvars.cellid))

        blob[b"__slack__"] = b"\x00" * 256
        return blob