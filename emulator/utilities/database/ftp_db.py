#!/usr/bin/env python3
"""
ftp_db.py - FTP Server Database Management

This module provides database access for FTP upload review and file ownership.
It uses SQLAlchemy with MariaDB in the same style as admin_db.py and cmdb.py.

Table definitions are in base_dbdriver.py:
- AwaitingReview: Pending FTP uploads requiring administrative review
- FileOwnership: Records file ownership for uploaded files
- FTPAdminActionLog: Logs admin actions for FTP uploads
- ApprovedApplication: Stores approved applications after approval
- FTPUser: Stores FTP user accounts
"""

import os
import logging
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError

import globalvars
from utilities.database import dbengine
from utilities.database.base_dbdriver import (
    AwaitingReview,
    FileOwnership,
    FTPAdminActionLog,
    ApprovedApplication,
    FTPUser,
)


log = logging.getLogger('FTP_DB')


class ftp_dbdriver:
    def __init__(self, config):
        self.config = config
        self.log = logging.getLogger("ftp_dbdriver")

        # Wait for MariaDB to be initialized (same pattern as admin_db.py)
        while globalvars.mariadb_initialized != True:
            continue

        # Use the shared database engine
        self.db_driver = dbengine.create_database_driver()
        self.db_driver.connect()

        # Create a session for ORM operations
        self.session = self.db_driver.get_session()

    def _refresh_session(self):
        """
        Refresh the session to see latest committed data.
        MariaDB uses REPEATABLE READ isolation, so queries within a transaction
        only see data as of when the transaction started. This ends the current
        transaction and expires cached ORM objects.
        """
        self.session.rollback()
        self.session.expire_all()

    def add_pending_upload(self, record):
        """
        record: dict with keys:
          - appid, uploader, upload_datetime, total_size, uploader_ip, uploader_port, file_paths
          - app_names (optional): comma-separated app names
          - subscriptions (optional): subscription info "id:name|id:name|..."
        """
        try:
            new_entry = AwaitingReview(
                appid=record['appid'],
                uploader=record['uploader'],
                upload_datetime=record['upload_datetime'],
                total_size=record['total_size'],
                uploader_ip=record['uploader_ip'],
                uploader_port=str(record['uploader_port']),
                file_paths=record.get('file_paths', ""),
                app_names=record.get('app_names', ""),
                subscriptions=record.get('subscriptions', "")
            )
            self.session.add(new_entry)
            self.session.commit()
            return True
        except SQLAlchemyError as e:
            self.session.rollback()
            return f"Error adding pending upload: {e}"

    def add_or_update_pending_upload(self, appid, uploader, upload_datetime, file_size, uploader_ip, uploader_port, new_file, file_dir, app_names="", subscriptions=""):
        """
        If an entry for appid exists, update its total_size and append the new file path.
        Otherwise, create a new entry.
        """
        try:
            self.session.expire_all()
            entry = self.session.query(AwaitingReview).filter_by(appid=appid).first()
            new_full_path = os.path.join(file_dir, new_file)
            if entry:
                entry.total_size += file_size
                if entry.file_paths:
                    entry.file_paths += "|" + new_full_path
                else:
                    entry.file_paths = new_full_path
                # Always update app_names and subscriptions if provided - XML is the
                # authoritative source for this metadata and should take precedence
                if app_names:
                    entry.app_names = app_names
                if subscriptions:
                    entry.subscriptions = subscriptions
                self.session.commit()
                return True
            else:
                record = {
                    "appid": appid,
                    "uploader": uploader,
                    "upload_datetime": upload_datetime,
                    "total_size": file_size,
                    "uploader_ip": uploader_ip,
                    "uploader_port": uploader_port,
                    "file_paths": new_full_path,
                    "app_names": app_names,
                    "subscriptions": subscriptions
                }
                return self.add_pending_upload(record)
        except SQLAlchemyError as e:
            self.session.rollback()
            return f"Error updating pending upload: {e}"

    def get_pending_uploads(self):
        try:
            # Expire cached data to ensure fresh read from database
            self.session.expire_all()
            entries = self.session.query(AwaitingReview).all()
            summary = ""
            for entry in entries:
                summary += (f"AppID: {entry.appid}, Uploader: {entry.uploader}, "
                            f"Date: {entry.upload_datetime}, Total Size: {entry.total_size} bytes, "
                            f"IP: {entry.uploader_ip}, Port: {entry.uploader_port}, "
                            f"Apps: {entry.app_names or 'N/A'}, Subs: {entry.subscriptions or 'N/A'}\n")
            return summary if summary else "No pending uploads."
        except SQLAlchemyError as e:
            return f"Error retrieving pending uploads: {e}"

    def get_pending_upload_by_appid(self, appid):
        try:
            # Expire cached data to ensure fresh read from database
            self.session.expire_all()
            entry = self.session.query(AwaitingReview).filter_by(appid=appid).first()
            if entry:
                return {
                    "appid": entry.appid,
                    "uploader": entry.uploader,
                    "upload_datetime": entry.upload_datetime,
                    "total_size": entry.total_size,
                    "uploader_ip": entry.uploader_ip,
                    "uploader_port": entry.uploader_port,
                    "file_paths": entry.file_paths.split('|') if entry.file_paths else [],
                    "app_names": entry.app_names or "",
                    "subscriptions": entry.subscriptions or ""
                }
            return None
        except SQLAlchemyError as e:
            return None

    def remove_pending_upload(self, appid):
        try:
            self.session.expire_all()
            entry = self.session.query(AwaitingReview).filter_by(appid=appid).first()
            if entry:
                self.session.delete(entry)
                self.session.commit()
                return True
            return "No pending upload for appid"
        except SQLAlchemyError as e:
            self.session.rollback()
            return f"Error removing pending upload: {e}"

    def log_ftp_admin_action(self, admin_info, appid, action, details):
        try:
            log_entry = FTPAdminActionLog(
                admin_username=admin_info.get("username", "unknown"),
                admin_ip=admin_info.get("ip", "unknown"),
                appid=appid,
                action=action,
                details=details,
                timestamp=datetime.now().strftime("%m/%d/%Y %H:%M:%S")
            )
            self.session.add(log_entry)
            self.session.commit()
            return True
        except SQLAlchemyError as e:
            self.session.rollback()
            return f"Error logging admin action: {e}"

    def add_file_ownership(self, record):
        """
        record: dict with keys:
          - uploader, appid, file_path, upload_datetime, file_size
        """
        try:
            new_entry = FileOwnership(
                uploader=record['uploader'],
                appid=record['appid'],
                file_path=record['file_path'],
                upload_datetime=record['upload_datetime'],
                file_size=record['file_size']
            )
            self.session.add(new_entry)
            self.session.commit()
            return True
        except SQLAlchemyError as e:
            self.session.rollback()
            return f"Error adding file ownership: {e}"

    def get_sdk_depot_directory(self):
        # Return the SDK depot directory from config if available; otherwise, a default path.
        return self.config.get('steam2sdkdir', os.path.join("files", "steam2_sdk_depots"))

    def get_mod_blob_directory(self):
        # Return the mod blob directory path.
        return os.path.join("files", "mod_blob")

    def get_temp_directory(self):
        # Return the temp directory path.
        return os.path.join("files", "temp")

    # -------------------------------------------------------------------------
    # Approved Applications Management
    # -------------------------------------------------------------------------

    def add_approved_application(self, appid, app_names, subscriptions, xml_file_path, approved_by):
        """
        Add a newly approved application to the approved applications table.
        """
        try:
            new_entry = ApprovedApplication(
                appid=appid,
                app_names=app_names,
                subscriptions=subscriptions,
                xml_file_path=xml_file_path,
                approval_datetime=datetime.now().strftime("%m/%d/%Y %H:%M:%S"),
                approved_by=approved_by
            )
            self.session.add(new_entry)
            self.session.commit()
            return True
        except SQLAlchemyError as e:
            self.session.rollback()
            self.log.error(f"Error adding approved application: {e}")
            return f"Error: {e}"

    def get_approved_applications(self):
        """
        Get list of all approved applications.
        Returns list of dicts.
        """
        try:
            # Expire cached data to ensure fresh read from database
            self.session.expire_all()
            entries = self.session.query(ApprovedApplication).all()
            apps = []
            for entry in entries:
                apps.append({
                    "id": entry.id,
                    "appid": entry.appid,
                    "app_names": entry.app_names or "",
                    "subscriptions": entry.subscriptions or "",
                    "xml_file_path": entry.xml_file_path or "",
                    "approval_datetime": entry.approval_datetime,
                    "approved_by": entry.approved_by,
                    "last_modified": entry.last_modified,
                    "modified_by": entry.modified_by
                })
            return apps
        except SQLAlchemyError as e:
            self.log.error(f"Error getting approved applications: {e}")
            return []

    def get_approved_application_by_appid(self, appid):
        """
        Get a specific approved application by appid.
        """
        try:
            # Expire cached data to ensure fresh read from database
            self.session.expire_all()
            entry = self.session.query(ApprovedApplication).filter_by(appid=appid).first()
            if entry:
                return {
                    "id": entry.id,
                    "appid": entry.appid,
                    "app_names": entry.app_names or "",
                    "subscriptions": entry.subscriptions or "",
                    "xml_file_path": entry.xml_file_path or "",
                    "approval_datetime": entry.approval_datetime,
                    "approved_by": entry.approved_by,
                    "last_modified": entry.last_modified,
                    "modified_by": entry.modified_by
                }
            return None
        except SQLAlchemyError as e:
            self.log.error(f"Error getting approved application: {e}")
            return None

    def update_approved_application(self, appid, app_names=None, subscriptions=None, modified_by=None):
        """
        Update an approved application's app_names and/or subscriptions.
        """
        try:
            entry = self.session.query(ApprovedApplication).filter_by(appid=appid).first()
            if not entry:
                return "Application not found"

            if app_names is not None:
                entry.app_names = app_names
            if subscriptions is not None:
                entry.subscriptions = subscriptions

            entry.last_modified = datetime.now().strftime("%m/%d/%Y %H:%M:%S")
            entry.modified_by = modified_by or "unknown"

            self.session.commit()
            return True
        except SQLAlchemyError as e:
            self.session.rollback()
            self.log.error(f"Error updating approved application: {e}")
            return f"Error: {e}"

    def remove_approved_application(self, appid):
        """
        Remove an approved application from the table.
        """
        try:
            self.session.expire_all()
            entry = self.session.query(ApprovedApplication).filter_by(appid=appid).first()
            if entry:
                self.session.delete(entry)
                self.session.commit()
                return True
            return "Application not found"
        except SQLAlchemyError as e:
            self.session.rollback()
            self.log.error(f"Error removing approved application: {e}")
            return f"Error: {e}"

    def get_approved_applications_summary(self):
        """
        Get a summary string of all approved applications (for remote admin tool).
        """
        try:
            # Expire cached data to ensure fresh read from database
            self.session.expire_all()
            entries = self.session.query(ApprovedApplication).all()
            summary = ""
            for entry in entries:
                subs_preview = entry.subscriptions[:50] + "..." if entry.subscriptions and len(entry.subscriptions) > 50 else (entry.subscriptions or "N/A")
                summary += (f"AppID: {entry.appid}, Name: {entry.app_names or 'N/A'}, "
                           f"Subs: {subs_preview}, Approved: {entry.approval_datetime}\n")
            return summary if summary else "No approved applications."
        except SQLAlchemyError as e:
            return f"Error: {e}"

    # -------------------------------------------------------------------------
    # FTP User Management (Database-backed)
    # -------------------------------------------------------------------------

    def get_ftp_users(self):
        """
        Get all FTP users from the database.
        Returns list of dicts with user info.
        """
        try:
            self._refresh_session()
            users = self.session.query(FTPUser).all()
            result = []
            for user in users:
                result.append({
                    'id': user.id,
                    'username': user.username,
                    'password': user.password,
                    'permissions': user.permissions,
                    'home_directory': user.home_directory,
                    'is_locked': user.is_locked,
                    'quota_mb': user.quota_mb or 0,
                    'bandwidth_kbps': user.bandwidth_kbps or 0,
                    'created_datetime': user.created_datetime,
                    'created_by': user.created_by,
                    'last_login': user.last_login,
                    'login_count': user.login_count
                })
            return result
        except SQLAlchemyError as e:
            self.log.error(f"Error getting FTP users: {e}")
            return []

    def get_ftp_user(self, username):
        """
        Get a specific FTP user by username.
        Returns dict or None.
        """
        try:
            self._refresh_session()
            user = self.session.query(FTPUser).filter_by(username=username).first()
            if user:
                return {
                    'id': user.id,
                    'username': user.username,
                    'password': user.password,
                    'permissions': user.permissions,
                    'home_directory': user.home_directory,
                    'is_locked': user.is_locked,
                    'quota_mb': user.quota_mb or 0,
                    'bandwidth_kbps': user.bandwidth_kbps or 0,
                    'created_datetime': user.created_datetime,
                    'created_by': user.created_by,
                    'last_login': user.last_login,
                    'login_count': user.login_count
                }
            return None
        except SQLAlchemyError as e:
            self.log.error(f"Error getting FTP user: {e}")
            return None

    def add_ftp_user(self, username, password, permissions='rw', home_directory=None, created_by=None):
        """
        Add a new FTP user to the database.
        Returns True on success, error string on failure.
        """
        try:
            self.session.expire_all()
            # Check if user already exists
            existing = self.session.query(FTPUser).filter_by(username=username).first()
            if existing:
                return "User already exists"

            new_user = FTPUser(
                username=username,
                password=password,
                permissions=permissions,
                home_directory=home_directory,
                is_locked=False,
                quota_mb=0,
                bandwidth_kbps=0,
                created_datetime=datetime.now().strftime("%m/%d/%Y %H:%M:%S"),
                created_by=created_by,
                login_count=0
            )
            self.session.add(new_user)
            self.session.commit()
            return True
        except SQLAlchemyError as e:
            self.session.rollback()
            self.log.error(f"Error adding FTP user: {e}")
            return f"Error: {e}"

    def remove_ftp_user(self, username):
        """
        Remove an FTP user from the database.
        Returns True on success, error string on failure.
        """
        try:
            self.session.expire_all()
            user = self.session.query(FTPUser).filter_by(username=username).first()
            if not user:
                return "User not found"
            self.session.delete(user)
            self.session.commit()
            return True
        except SQLAlchemyError as e:
            self.session.rollback()
            self.log.error(f"Error removing FTP user: {e}")
            return f"Error: {e}"

    def update_ftp_user_password(self, username, new_password):
        """
        Update an FTP user's password.
        Returns True on success, error string on failure.
        """
        try:
            self.session.expire_all()
            user = self.session.query(FTPUser).filter_by(username=username).first()
            if not user:
                return "User not found"
            user.password = new_password
            self.session.commit()
            return True
        except SQLAlchemyError as e:
            self.session.rollback()
            self.log.error(f"Error updating FTP user password: {e}")
            return f"Error: {e}"

    def update_ftp_user_permissions(self, username, permissions):
        """
        Update an FTP user's permissions.
        Returns True on success, error string on failure.
        """
        try:
            self.session.expire_all()
            user = self.session.query(FTPUser).filter_by(username=username).first()
            if not user:
                return "User not found"
            user.permissions = permissions
            self.session.commit()
            return True
        except SQLAlchemyError as e:
            self.session.rollback()
            self.log.error(f"Error updating FTP user permissions: {e}")
            return f"Error: {e}"

    def toggle_ftp_user_lock(self, username):
        """
        Toggle the lock status of an FTP user.
        Returns (new_lock_status, True) on success, (None, error_string) on failure.
        """
        try:
            self.session.expire_all()
            user = self.session.query(FTPUser).filter_by(username=username).first()
            if not user:
                return None, "User not found"
            user.is_locked = not user.is_locked
            self.session.commit()
            return user.is_locked, True
        except SQLAlchemyError as e:
            self.session.rollback()
            self.log.error(f"Error toggling FTP user lock: {e}")
            return None, f"Error: {e}"

    def set_ftp_user_quota(self, username, quota_mb, bandwidth_kbps):
        """
        Set quota and bandwidth limit for an FTP user.
        Returns True on success, error string on failure.
        """
        try:
            self.session.expire_all()
            user = self.session.query(FTPUser).filter_by(username=username).first()
            if not user:
                return "User not found"
            user.quota_mb = quota_mb
            user.bandwidth_kbps = bandwidth_kbps
            self.session.commit()
            return True
        except SQLAlchemyError as e:
            self.session.rollback()
            self.log.error(f"Error setting FTP user quota: {e}")
            return f"Error: {e}"

    def get_ftp_user_quota(self, username):
        """
        Get quota info for an FTP user.
        Returns dict with quota_mb and bandwidth_kbps, or None.
        """
        try:
            self.session.expire_all()
            user = self.session.query(FTPUser).filter_by(username=username).first()
            if user:
                return {
                    'quota_mb': user.quota_mb or 0,
                    'bandwidth_kbps': user.bandwidth_kbps or 0
                }
            return None
        except SQLAlchemyError as e:
            self.log.error(f"Error getting FTP user quota: {e}")
            return None

    def record_ftp_login(self, username):
        """
        Record a successful login for an FTP user.
        Updates last_login and increments login_count.
        """
        try:
            user = self.session.query(FTPUser).filter_by(username=username).first()
            if user:
                user.last_login = datetime.now().strftime("%m/%d/%Y %H:%M:%S")
                user.login_count = (user.login_count or 0) + 1
                self.session.commit()
                return True
            return False
        except SQLAlchemyError as e:
            self.session.rollback()
            self.log.error(f"Error recording FTP login: {e}")
            return False

    def authenticate_ftp_user(self, username, password):
        """
        Authenticate an FTP user.
        Returns user dict if successful, None if failed, 'locked' if account is locked.
        """
        try:
            self._refresh_session()
            user = self.session.query(FTPUser).filter_by(username=username).first()
            if not user:
                return None
            if user.is_locked:
                return 'locked'
            if user.password == password:
                return {
                    'username': user.username,
                    'permissions': user.permissions,
                    'home_directory': user.home_directory,
                    'quota_mb': user.quota_mb or 0,
                    'bandwidth_kbps': user.bandwidth_kbps or 0
                }
            return None
        except SQLAlchemyError as e:
            self.log.error(f"Error authenticating FTP user: {e}")
            return None

    def get_ftp_users_for_authorizer(self):
        """
        Get FTP users in a format suitable for pyftpdlib authorizer.
        Returns list of dicts with username, password, permissions, home_dir.
        Only returns unlocked users.
        """
        try:
            self._refresh_session()
            users = self.session.query(FTPUser).filter_by(is_locked=False).all()
            result = []
            for user in users:
                result.append({
                    'username': user.username,
                    'password': user.password,
                    'permissions': user.permissions,
                    'home_directory': user.home_directory,
                    'quota_mb': user.quota_mb or 0,
                    'bandwidth_kbps': user.bandwidth_kbps or 0
                })
            return result
        except SQLAlchemyError as e:
            self.log.error(f"Error getting FTP users for authorizer: {e}")
            return []

    def get_ftp_users_summary(self):
        """
        Get a summary string of all FTP users (for remote admin tool).
        """
        try:
            self._refresh_session()
            users = self.session.query(FTPUser).all()
            if not users:
                return "No FTP users."
            lines = []
            for user in users:
                status = "LOCKED" if user.is_locked else "active"
                quota_info = f"quota:{user.quota_mb or 0}MB" if user.quota_mb else "no quota"
                lines.append(f"{user.username}|{user.permissions}|{status}|{quota_info}")
            return '\n'.join(lines)
        except SQLAlchemyError as e:
            return f"Error: {e}"

    def migrate_from_text_file(self, accounts_file_path, quota_file_path=None):
        """
        Migrate FTP users from the old text file format to the database.
        accounts_file_path: Path to ftpaccounts.txt
        quota_file_path: Optional path to ftpquota.json
        Returns (success_count, error_count, messages).
        """
        import json

        success_count = 0
        error_count = 0
        messages = []

        # Load quotas if available
        quotas = {}
        if quota_file_path and os.path.exists(quota_file_path):
            try:
                with open(quota_file_path, 'r') as f:
                    quotas = json.load(f)
            except Exception as e:
                messages.append(f"Warning: Could not load quota file: {e}")

        # Read and parse accounts file
        if not os.path.exists(accounts_file_path):
            return 0, 0, ["Accounts file not found"]

        try:
            with open(accounts_file_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue

                    parts = line.split(':')
                    if len(parts) < 3:
                        messages.append(f"Skipping invalid line: {line}")
                        error_count += 1
                        continue

                    username = parts[0]
                    password = parts[1]
                    permissions = parts[2].split(';')[0]  # Remove any comments

                    # Check if locked (permissions starting with '!')
                    is_locked = permissions.startswith('!')
                    if is_locked:
                        permissions = permissions[1:]

                    # Get quota if available
                    user_quota = quotas.get(username, {})
                    quota_mb = user_quota.get('quota', 0)
                    bandwidth_kbps = user_quota.get('bw', 0)

                    # Add to database
                    result = self.add_ftp_user(
                        username=username,
                        password=password,
                        permissions=permissions,
                        created_by='migration'
                    )

                    if result is True:
                        # Set lock status and quota
                        if is_locked:
                            self.toggle_ftp_user_lock(username)
                        if quota_mb or bandwidth_kbps:
                            self.set_ftp_user_quota(username, quota_mb, bandwidth_kbps)
                        success_count += 1
                        messages.append(f"Migrated user: {username}")
                    else:
                        error_count += 1
                        messages.append(f"Failed to migrate {username}: {result}")

        except Exception as e:
            messages.append(f"Error reading accounts file: {e}")
            error_count += 1

        return success_count, error_count, messages
