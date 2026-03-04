#!/usr/bin/env python3
"""
Revised FTP Server Code

When a client uploads a XML, DAT, or BLOB file, the file is first moved to a temp directory.
For XML files (specifically, ContentDescriptionDB.xml), the AppID is parsed from the XML.
Then, if the configuration forces SDK upload review (i.e.
    configs['force_sdk_upload_review'].lower() == 'true'),
the server records the upload details (appid, uploader username, upload date/time,
total file size for the same appid, and uploader IP/port) into a new AwaitingReview database table.
If not forced, then the .blob and .dat files are moved to ../files/steam2_sdk_depots/ and
the <appid>.xml is moved to ../files/mod_blob/.

Also, file ownership is recorded so that only the uploader can later view/edit/delete the files.

The ftp_db module (created separately) is used to persist the pending-review and file-ownership information.
"""

import logging
import os
import shutil
import xml.etree.ElementTree as ET
from pyftpdlib.authorizers import DummyAuthorizer, AuthenticationFailed
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer
import config
import json

# Import our new FTP database functions
from utilities.database.ftp_db import ftp_dbdriver
from utilities.cdr_manipulator import merge_xml_into_cached_blobs


class DatabaseAuthorizer(DummyAuthorizer):
    """
    A custom FTP authorizer that queries the database for each authentication.
    This allows newly added users to log in without restarting the FTP server.
    """

    def __init__(self, ftp_db, default_directory, anonymous_directory=None):
        super().__init__()
        self.ftp_db = ftp_db
        self.default_directory = default_directory
        self.anonymous_directory = anonymous_directory
        # Create anonymous directory if provided (we handle anonymous in overridden methods)
        if anonymous_directory:
            os.makedirs(anonymous_directory, exist_ok=True)

    def _get_user_from_db(self, username):
        """Fetch user data from database."""
        users = self.ftp_db.get_ftp_users_for_authorizer()
        for user in users:
            if user['username'] == username:
                return user
        return None

    def _convert_permissions(self, perm_string):
        """Convert permission string to pyftpdlib permissions.

        Permission string chars:
            r = read (list, retrieve, enter directory)
            w = write (store, append, delete, make directory, write)
            d = delete
            u = upload (write + list/enter for navigation)

        pyftpdlib permissions:
            e = enter directory
            l = list directory
            r = retrieve/download file
            a = append to file
            d = delete file
            f = rename file
            m = make directory
            w = store/write file
        """
        perm = ''
        if 'r' in perm_string:
            perm += 'elr'  # list, retrieve, enter directory
        if 'w' in perm_string:
            perm += 'adfmw'  # store, append, delete, make directory, write
        if 'd' in perm_string and 'd' not in perm:
            perm += 'd'  # delete
        if 'u' in perm_string:
            perm += 'elmw'  # upload needs: enter, list, make dir, write
        # Remove duplicates while preserving order
        seen = set()
        perm = ''.join(c for c in perm if not (c in seen or seen.add(c)))
        return perm

    def validate_authentication(self, username, password, handler):
        """Validate user credentials against database."""
        # Check for anonymous
        if username == 'anonymous':
            if self.anonymous_directory:
                return
            raise AuthenticationFailed("Anonymous login not allowed.")

        # Query database for user
        user = self._get_user_from_db(username)
        if user is None:
            raise AuthenticationFailed("Authentication failed.")

        # Check password
        if user['password'] != password:
            raise AuthenticationFailed("Authentication failed.")

        # Ensure home directory exists
        if user.get('home_directory'):
            homedir = user['home_directory']
        else:
            homedir = os.path.join(self.default_directory, username)
        os.makedirs(homedir, exist_ok=True)

    def get_home_dir(self, username):
        """Return user's home directory."""
        if username == 'anonymous':
            return self.anonymous_directory

        user = self._get_user_from_db(username)
        if user:
            if user.get('home_directory'):
                return user['home_directory']
            return os.path.join(self.default_directory, username)
        return self.default_directory

    def has_user(self, username):
        """Check if user exists."""
        if username == 'anonymous':
            return self.anonymous_directory is not None
        return self._get_user_from_db(username) is not None

    def has_perm(self, username, perm, path=None):
        """Check if user has permission."""
        if username == 'anonymous':
            return perm in 'elr'

        user = self._get_user_from_db(username)
        if user:
            user_perms = self._convert_permissions(user['permissions'])
            return perm in user_perms
        return False

    def get_perms(self, username):
        """Return user's permissions."""
        if username == 'anonymous':
            return 'elr'

        user = self._get_user_from_db(username)
        if user:
            return self._convert_permissions(user['permissions'])
        return ''

    def get_msg_login(self, username):
        """Return login message."""
        return f"Welcome {username}!"

    def get_msg_quit(self, username):
        """Return quit message."""
        return "Goodbye."

configs = config.get_config()
database = ftp_dbdriver(configs)
# Directories
TEMP_DIRECTORY = os.path.join("files", "temp")
CUSTOMBLOB_DIRECTORY = os.path.join("files", "custom")
SDK_STORAGE_DIRECTORY = configs.get('steam2sdkdir', os.path.join("files", "steam2_sdk_depots"))
MOD_BLOB_DIRECTORY = os.path.join("files", "mod_blob")
FTP_QUOTA_FILE = "ftpquota.json"

def load_ftp_quota():
    try:
        with open(FTP_QUOTA_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

# Ensure directories exist
for d in (TEMP_DIRECTORY, CUSTOMBLOB_DIRECTORY, SDK_STORAGE_DIRECTORY, MOD_BLOB_DIRECTORY):
    os.makedirs(d, exist_ok=True)

class CustomFTPHandler(FTPHandler):
    def log(self, message):
        try:
            super().log(message)
        except UnicodeEncodeError:
            sanitized_message = message.encode('utf-8', errors='replace').decode('utf-8')
            super().log(sanitized_message)

    def on_connect(self):
        self.log(f"Connected from {self.remote_ip}:{self.remote_port}")

    def on_disconnect(self):
        self.log(f"Disconnected from {self.remote_ip}:{self.remote_port}")

    def on_login(self, username):
        self.log(f"User {username} logged in")
        # Store the username for later file ownership recording.
        self.username = username

    def on_login_failed(self, username, password):
        self.log(f"Failed login attempt for username: {username}")

    def ftp_CLNT(self, line):
        client_info = line.split(' ', 1)[1] if ' ' in line else 'Unknown client'
        self.log(f"Client information: {client_info}")

    def on_file_received(self, file_path):
        self.log(f"File received: {file_path}")
        filename = os.path.basename(file_path)
        extension = os.path.splitext(filename)[1].lower()

        # Get uploader info
        uploader = getattr(self, 'username', 'anonymous')
        uploader_ip = self.remote_ip
        uploader_port = str(self.remote_port)
        upload_datetime = datetime_now()

        # Create user-specific temp directory
        user_temp_directory = os.path.join(TEMP_DIRECTORY, uploader)
        os.makedirs(user_temp_directory, exist_ok=True)

        # Move the file to the user's temp directory first.
        temp_path = os.path.join(user_temp_directory, filename)
        try:
            shutil.move(file_path, temp_path)
            self.log(f"Moved file to user temp directory: {temp_path}")
        except Exception as e:
            self.log(f"Error moving file to temp directory: {e}")
            self.respond("550 File transfer failed due to server error.")
            return

        # Determine force review flag from configuration.
        force_review = configs['force_sdk_upload_review'].lower() == 'true'
        file_size = os.path.getsize(temp_path)

        quota_info = load_ftp_quota().get(uploader, {})
        quota_bytes = quota_info.get('quota', 0) * 1024 * 1024
        if quota_bytes and file_size > quota_bytes:
            self.log(f"Quota exceeded for {uploader}")
            os.remove(temp_path)
            self.respond("552 Quota exceeded.")
            return

        # Initialize variable to store appid (if determined)
        appid = None
        final_path = None  # Will be set if file is moved immediately.

        try:
            if extension == '.xml':
                if filename.lower() == 'contentdescriptiondb.xml':
                    try:
                        tree = ET.parse(temp_path)
                        root = tree.getroot()
                        app_record = root.find('.//AppRecord')
                        if app_record is None or 'AppId' not in app_record.attrib:
                            raise ValueError("No AppId found in ContentDescriptionDB.xml")
                        appid = app_record.attrib['AppId']
                        new_filename = f"{appid}.xml"
                        self.log(f"Renaming ContentDescriptionDB.xml to {new_filename}")

                        # Parse app names and subscriptions from the XML
                        app_names, subscriptions = parse_xml_metadata(temp_path)
                        self.log(f"Parsed metadata - Apps: {app_names}, Subs: {subscriptions}")

                        # Rename file in user's temp directory
                        new_temp_path = os.path.join(user_temp_directory, new_filename)
                        if temp_path != new_temp_path:
                            shutil.move(temp_path, new_temp_path)
                            temp_path = new_temp_path

                        if force_review:
                            # In review mode, record the XML file info in the pending review table.
                            # Use add_or_update to handle the case where DAT/BLOB files were
                            # uploaded before the XML - ensures XML path is added to file_paths.
                            database.add_or_update_pending_upload(
                                appid, uploader, upload_datetime, file_size,
                                uploader_ip, uploader_port,
                                new_file=new_filename, file_dir=user_temp_directory,
                                app_names=app_names, subscriptions=subscriptions
                            )
                            self.log(f"Pending review record added/updated for AppID {appid}")
                            # Do not move the file now; leave it in temp for review.
                        else:
                            # Immediately move the XML file.
                            new_path = os.path.join(MOD_BLOB_DIRECTORY, new_filename)
                            shutil.move(temp_path, new_path)
                            self.log(f"Moved XML file to {new_path}")
                            final_path = new_path
                            # Merge directly into cached blobs (no review required)
                            try:
                                merge_success, merge_msg = merge_xml_into_cached_blobs(new_path)
                                if merge_success:
                                    self.log(f"Merged AppID {appid} into cached blobs: {merge_msg}")
                                else:
                                    self.log(f"Warning: Failed to merge into cached blobs: {merge_msg}")
                            except Exception as merge_err:
                                self.log(f"Warning: Cache merge error: {merge_err}")
                    except Exception as e:
                        self.log(f"Error processing ContentDescriptionDB.xml: {e}")
                        self.respond("550 File transfer failed due to server error.")
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                        return
                else:
                    # For other XML files, simply move them to the custom directory.
                    new_path = os.path.join(CUSTOMBLOB_DIRECTORY, filename)
                    shutil.move(temp_path, new_path)
                    self.log(f"Moved XML file to {new_path}")
                    final_path = new_path
            elif extension in {'.dat', '.blob'}:
                # Determine appid from the filename (assuming filename format: <appid>_something.ext)
                parts = filename.split('_')
                if parts:
                    appid = parts[0]
                else:
                    self.log("Cannot determine AppID from filename")
                    self.respond("550 File transfer failed due to server error.")
                    os.remove(temp_path)
                    return
                if force_review:
                    # In review mode, track depot files (DAT/BLOB) in pending_uploads
                    # so they are properly moved when the app is approved.
                    database.add_or_update_pending_upload(
                        appid, uploader, upload_datetime, file_size,
                        uploader_ip, uploader_port,
                        new_file=filename, file_dir=user_temp_directory,
                        app_names="", subscriptions=""
                    )
                    self.log(f"Depot file {filename} tracked in pending for AppID {appid} (awaiting app approval)")
                else:
                    # Immediately move to SDK storage directory.
                    new_path = os.path.join(SDK_STORAGE_DIRECTORY, filename)
                    if os.path.exists(new_path):
                        self.log(f"File already exists: {new_path}")
                        self.respond("550 File transfer failed due to server error.")
                        os.remove(temp_path)
                        return
                    shutil.move(temp_path, new_path)
                    self.log(f"Moved {extension} file to {new_path}")
                    final_path = new_path
            else:
                self.log(f"User tried to upload a non-SDK related file: {filename}")
                self.respond("550 File type not allowed.")
                os.remove(temp_path)
                return
        except Exception as e:
            self.log(f"Error processing file {filename}: {e}")
            self.respond("550 File transfer failed due to server error.")
            os.remove(temp_path)
            return

        # Record file ownership regardless of review mode.
        if final_path is None:
            # If file not moved (i.e. pending review), use temp path.
            final_path = temp_path
        ownership_record = {
            "uploader": uploader,
            "appid": appid if appid is not None else "unknown",
            "file_path": final_path,
            "upload_datetime": upload_datetime,
            "file_size": file_size
        }
        database.add_file_ownership(ownership_record)
        rate_kbps = quota_info.get('bw', 0)
        if rate_kbps > 0:
            import time as _t
            _t.sleep(file_size / (rate_kbps * 1024))
        self.respond("250 File uploaded successfully.")

def datetime_now():
    """Return current date/time as string in 'mm/dd/YYYY HH:MM:SS' format."""
    from datetime import datetime
    return datetime.now().strftime("%m/%d/%Y %H:%M:%S")

def parse_xml_metadata(xml_path):
    """
    Parse ContentDescriptionDB.xml and extract app names and subscription info.
    Returns (app_names, subscriptions) where:
      - app_names: comma-separated string of app names
      - subscriptions: pipe-separated string of "id:name" pairs
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Extract all app names
        app_names = []
        for app_record in root.findall('.//AppRecord'):
            name_elem = app_record.find('Name')
            if name_elem is not None and name_elem.text:
                app_names.append(name_elem.text)

        # Extract subscription IDs and names
        subscriptions = []
        for sub_record in root.findall('.//SubscriptionRecord'):
            sub_id = sub_record.get('SubscriptionId', '')
            name_elem = sub_record.find('Name')
            sub_name = name_elem.text if name_elem is not None and name_elem.text else ''
            if sub_id:
                subscriptions.append(f"{sub_id}:{sub_name}")

        return ', '.join(app_names), '|'.join(subscriptions)
    except Exception as e:
        logging.error(f"Error parsing XML metadata: {e}")
        return "", ""

def create_ftp_server(directory, anonymous_directory, address="0.0.0.0", port=21):
    import sys
    import globalvars
    from config import save_config_value
    from utilities.thread_handler import server_registry

    # On Linux, binding to privileged ports (< 1024) requires root
    if sys.platform.startswith('linux') and port < 1024 and os.geteuid() != 0:
        logging.error(f"FTP server cannot bind to port {port}: privileged ports require root. "
                      "Run as root or use a port above 1024 to enable FTP.")
        # Mark FTP server as disabled so watchdog doesn't keep trying to restart it
        globalvars.disabled_servers.add('FTPUpdateServer')
        # Update the config so it reflects the disabled state
        save_config_value('enable_ftp', 'false')
        globalvars.config['enable_ftp'] = 'false'
        # Remove from server registries to prevent watchdog from tracking it
        if 'FTPUpdateServer' in globalvars.server_threads:
            del globalvars.server_threads['FTPUpdateServer']
        if 'FTPUpdateServer' in server_registry:
            del server_registry['FTPUpdateServer']
        logging.info("FTP server has been disabled due to insufficient privileges.")
        return

    # Setup logging for pyftpdlib
    logger = logging.getLogger('pyftpdlib')
    os.makedirs('logs', exist_ok=True)
    file_handler = logging.FileHandler('logs/pyftpdlib.log')
    logger.addHandler(file_handler)

    # Create database-backed authorizer (queries DB on each auth - no restart needed for new users)
    ftp_config = config.get_config()
    ftp_db = ftp_dbdriver(ftp_config)

    # Check for legacy file migration on first run
    db_users = ftp_db.get_ftp_users_for_authorizer()
    if not db_users and os.path.exists('ftpaccounts.txt'):
        logging.info("FTP: No users in database. Migrating from ftpaccounts.txt...")
        success, errors, messages = ftp_db.migrate_from_text_file('ftpaccounts.txt', 'ftpquota.json')
        for msg in messages:
            logging.info(f"FTP migration: {msg}")
        logging.info(f"FTP migration complete: {success} users migrated, {errors} errors")
    elif not db_users:
        logging.warning("FTP: No users found in database and no ftpaccounts.txt to migrate. "
                      "Add users via the admin console or remote admin tool.")

    # Use DatabaseAuthorizer - checks database on each login attempt
    # This means newly added users can log in immediately without server restart
    authorizer = DatabaseAuthorizer(ftp_db, directory, anonymous_directory)
    logging.info("FTP: Using database-backed authorizer (dynamic user loading enabled)")

    from pyftpdlib.handlers import FTPHandler
    handler = CustomFTPHandler
    handler.authorizer = authorizer
    handler.log_prefix = '[%(username)s] %(remote_ip)s:%(remote_port)s - '
    server = FTPServer((address, port), handler)
    print(f"Starting FTP server on {address}:{port}")
    server.serve_forever()

# Uncomment the following lines to run the FTP server standalone.
# if __name__ == "__main__":
#     create_ftp_server("files/ftproot", "files/beta1_ftp")
