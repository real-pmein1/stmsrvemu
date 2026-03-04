#!/usr/bin/env python3
"""
FTP Management Menu

A curses-based interactive menu for managing FTP users and pending application uploads.
Works with both SimpleConsoleManager and TUIConsoleManager.
"""

import os
import sys
import json
import shutil
import logging
import xml.etree.ElementTree as ET

# Handle curses import for cross-platform support
try:
    import curses
    HAS_CURSES = True
except ImportError:
    try:
        # Windows may need windows-curses
        import curses
        HAS_CURSES = True
    except ImportError:
        HAS_CURSES = False

from config import get_config
from utilities.database.ftp_db import ftp_dbdriver

# File paths (kept for migration purposes)
FTP_ACCOUNTS_FILE = "ftpaccounts.txt"
FTP_QUOTA_FILE = "ftpquota.json"

log = logging.getLogger("FTPMenu")


class FTPMenuManager:
    """Manages FTP users and pending application uploads."""

    def __init__(self):
        self.config = get_config()
        self.database = ftp_dbdriver(self.config)

    # -------------------------------------------------------------------------
    # FTP Account Management (Database-backed)
    # -------------------------------------------------------------------------

    def get_ftp_users(self):
        """
        Get list of FTP users from database.
        Returns list of dicts: [{"username": str, "password": str, "permissions": str, "locked": bool}]
        """
        db_users = self.database.get_ftp_users()
        # Convert to legacy format for compatibility
        users = []
        for user in db_users:
            users.append({
                "username": user['username'],
                "password": user['password'],
                "permissions": user['permissions'],
                "locked": user['is_locked'],
                "quota_mb": user.get('quota_mb', 0),
                "bandwidth_kbps": user.get('bandwidth_kbps', 0)
            })
        return users

    def add_ftp_user(self, username, password, permissions="rw"):
        """Add a new FTP user to the database."""
        result = self.database.add_ftp_user(
            username=username,
            password=password,
            permissions=permissions,
            created_by="console_admin"
        )

        if result is True:
            # Create user home directory
            directory = self.config.get('ftp_homedir', 'files/ftproot')
            homedir = os.path.join(directory, username)
            os.makedirs(homedir, exist_ok=True)
            return True, f"User '{username}' created successfully"
        return False, str(result)

    def remove_ftp_user(self, username):
        """Remove an FTP user from the database."""
        result = self.database.remove_ftp_user(username)
        if result is True:
            return True, f"User '{username}' removed successfully"
        return False, str(result)

    def change_user_password(self, username, new_password):
        """Change a user's password in the database."""
        result = self.database.update_ftp_user_password(username, new_password)
        if result is True:
            return True, "Password changed successfully"
        return False, str(result)

    def toggle_user_lock(self, username):
        """Toggle the lock status of a user account in the database."""
        new_status, result = self.database.toggle_ftp_user_lock(username)
        if result is True:
            status = "locked" if new_status else "unlocked"
            return True, f"Account '{username}' {status}"
        return False, str(result)

    # -------------------------------------------------------------------------
    # Quota Management (Database-backed)
    # -------------------------------------------------------------------------

    def set_user_quota(self, username, quota_mb, bw_kbps=0):
        """Set quota for a user (quota in MB, bandwidth in KB/s)."""
        result = self.database.set_ftp_user_quota(username, quota_mb, bw_kbps)
        if result is True:
            return True, f"Quota set: {quota_mb}MB, {bw_kbps}KB/s bandwidth limit"
        return False, str(result)

    def get_user_quota(self, username):
        """Get quota for a specific user."""
        quota = self.database.get_ftp_user_quota(username)
        if quota:
            return {"quota": quota['quota_mb'], "bw": quota['bandwidth_kbps']}
        return {"quota": 0, "bw": 0}

    # -------------------------------------------------------------------------
    # Migration from Text File
    # -------------------------------------------------------------------------

    def migrate_from_text_file(self):
        """
        Migrate FTP users from ftpaccounts.txt to the database.
        Returns (success_count, error_count, messages).
        """
        return self.database.migrate_from_text_file(FTP_ACCOUNTS_FILE, FTP_QUOTA_FILE)

    # -------------------------------------------------------------------------
    # Pending Applications Management
    # -------------------------------------------------------------------------

    def get_pending_applications(self):
        """
        Get list of pending application uploads.
        Returns list of dicts with appid, uploader, app_names, subscriptions, file_paths, etc.
        """
        from utilities.database.base_dbdriver import AwaitingReview
        try:
            # Expire cached data to ensure fresh read from database
            self.database.session.expire_all()
            entries = self.database.session.query(AwaitingReview).all()
            pending = []
            for entry in entries:
                pending.append({
                    "appid": entry.appid,
                    "uploader": entry.uploader,
                    "upload_datetime": entry.upload_datetime,
                    "total_size": entry.total_size,
                    "uploader_ip": entry.uploader_ip,
                    "uploader_port": entry.uploader_port,
                    "file_paths": entry.file_paths.split('|') if entry.file_paths else [],
                    "app_names": entry.app_names or "",
                    "subscriptions": entry.subscriptions or ""
                })
            return pending
        except Exception as e:
            log.error(f"Error getting pending applications: {e}")
            return []

    def approve_application(self, appid):
        """
        Approve a pending application upload.
        All files (XML, DAT, BLOB) are tracked in file_paths.
        XML files go to mod_blob directory, DAT/BLOB files go to steam2_sdk_depots.
        Auto-discovery is still performed as a fallback for any untracked files.
        After moving, triggers blob merge via cache_cdr.
        """
        from utilities.cdr_manipulator import cache_cdr, load_blobs_to_memory

        pending = self.database.get_pending_upload_by_appid(appid)
        if not pending:
            return False, "Application not found"

        sdk_dir = self.database.get_sdk_depot_directory()
        mod_blob_dir = self.database.get_mod_blob_directory()

        # Ensure directories exist
        os.makedirs(sdk_dir, exist_ok=True)
        os.makedirs(mod_blob_dir, exist_ok=True)

        moved_files = []
        errors = []
        xml_dest_path = None
        temp_directory = None

        try:
            # Process all tracked files (XML, DAT, BLOB) and determine temp directory
            for file_path in pending['file_paths']:
                if not os.path.exists(file_path):
                    errors.append(f"File not found: {file_path}")
                    continue

                # Remember the temp directory for auto-discovery fallback
                if temp_directory is None:
                    temp_directory = os.path.dirname(file_path)

                filename = os.path.basename(file_path)
                ext = os.path.splitext(filename)[1].lower()

                try:
                    if ext == '.xml':
                        # XML files go to mod_blob directory
                        dest = os.path.join(mod_blob_dir, filename)
                        shutil.move(file_path, dest)
                        moved_files.append(dest)
                        xml_dest_path = dest
                        log.info(f"Approved: moved {filename} to {dest}")
                    elif ext in {'.dat', '.blob'}:
                        # DAT/BLOB files go to SDK depot directory
                        dest = os.path.join(sdk_dir, filename)
                        shutil.move(file_path, dest)
                        moved_files.append(dest)
                        log.info(f"Approved: moved {filename} to {dest}")
                    else:
                        errors.append(f"Unknown file type: {filename}")
                except Exception as e:
                    errors.append(f"Error moving {filename}: {e}")

            # Auto-discover any remaining depot files (fallback for untracked files)
            if temp_directory and os.path.isdir(temp_directory):
                try:
                    for filename in os.listdir(temp_directory):
                        # Check if filename starts with appid followed by underscore
                        if filename.startswith(f"{appid}_"):
                            ext = os.path.splitext(filename)[1].lower()
                            if ext in {'.dat', '.blob'}:
                                src_path = os.path.join(temp_directory, filename)
                                dest_path = os.path.join(sdk_dir, filename)
                                try:
                                    shutil.move(src_path, dest_path)
                                    moved_files.append(dest_path)
                                    log.info(f"Approved: auto-discovered and moved {filename} to {dest_path}")
                                except Exception as e:
                                    errors.append(f"Error moving depot {filename}: {e}")
                except Exception as e:
                    errors.append(f"Error scanning temp directory: {e}")

            # After moving XML, trigger blob merge via cache_cdr
            if xml_dest_path and os.path.exists(xml_dest_path):
                try:
                    log.info(f"Triggering cache_cdr for LAN after approval of appid {appid}")
                    cache_cdr(islan=True, isAppApproval_merge=True)
                    log.info(f"Triggering cache_cdr for WAN after approval of appid {appid}")
                    cache_cdr(islan=False, isAppApproval_merge=True)
                    log.info(f"Blob merge completed for appid {appid}")
                    # Reload blobs into memory from the updated cache files
                    load_blobs_to_memory()
                    log.info(f"Memory blobs reloaded after approval of appid {appid}")
                except Exception as e:
                    errors.append(f"Cache merge failed: {e}")
                    log.error(f"Failed to merge appid {appid} into cached blobs: {e}")

            # Log the admin action
            details = f"Approved {len(moved_files)} files"
            if errors:
                details += f"; Errors: {'; '.join(errors)}"
            admin_info = {"username": "console_admin", "ip": "127.0.0.1"}
            self.database.log_ftp_admin_action(admin_info, appid, "APPROVE", details)

            # Remove from pending
            self.database.remove_pending_upload(appid)

            if errors:
                return True, f"Application {appid} approved with errors: {'; '.join(errors)}. {len(moved_files)} files moved."
            return True, f"Application {appid} approved. {len(moved_files)} files moved."

        except Exception as e:
            log.error(f"Error approving application {appid}: {e}")
            return False, f"Error: {e}"

    def deny_application(self, appid):
        """
        Deny a pending application upload.
        Removes all tracked files (XML, DAT, BLOB).
        """
        pending = self.database.get_pending_upload_by_appid(appid)
        if not pending:
            return False, "Application not found"

        deleted_files = []
        try:
            for file_path in pending['file_paths']:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    deleted_files.append(file_path)
                    log.info(f"Denied: deleted {file_path}")

            # Log the admin action
            admin_info = {"username": "console_admin", "ip": "127.0.0.1"}
            self.database.log_ftp_admin_action(admin_info, appid, "DENY",
                                                f"Deleted {len(deleted_files)} files")

            # Remove from pending
            self.database.remove_pending_upload(appid)

            return True, f"Application {appid} denied. {len(deleted_files)} files deleted."

        except Exception as e:
            log.error(f"Error denying application {appid}: {e}")
            return False, f"Error: {e}"

    # -------------------------------------------------------------------------
    # Approved Applications Management
    # -------------------------------------------------------------------------

    def get_approved_applications(self):
        """Get list of all approved applications."""
        return self.database.get_approved_applications()

    def get_approved_application_by_appid(self, appid):
        """Get a specific approved application."""
        return self.database.get_approved_application_by_appid(appid)

    def update_approved_application(self, appid, app_names=None, subscriptions=None, modified_by="console_admin"):
        """Update an approved application's details."""
        result = self.database.update_approved_application(appid, app_names, subscriptions, modified_by)
        if result is True:
            # Also update the XML file if it exists
            app_data = self.database.get_approved_application_by_appid(appid)
            if app_data and app_data.get('xml_file_path'):
                xml_path = app_data['xml_file_path']
                if os.path.exists(xml_path):
                    try:
                        self._update_xml_subscriptions(xml_path, subscriptions)
                    except Exception as e:
                        log.error(f"Error updating XML file: {e}")
            return True, "Application updated successfully"
        return False, str(result)

    def delete_approved_application(self, appid):
        """
        Delete an approved application.
        Removes the XML file from mod_blob, DAT/BLOB files from steam2_sdk_depots,
        and the database entry.
        """
        app_data = self.database.get_approved_application_by_appid(appid)
        if not app_data:
            return False, "Application not found"

        sdk_dir = self.database.get_sdk_depot_directory()
        mod_blob_dir = self.database.get_mod_blob_directory()

        deleted_files = []
        errors = []

        try:
            # Delete the XML file from mod_blob
            xml_path = app_data.get('xml_file_path')
            if xml_path and os.path.exists(xml_path):
                try:
                    os.remove(xml_path)
                    deleted_files.append(xml_path)
                    log.info(f"Deleted XML file: {xml_path}")
                except Exception as e:
                    errors.append(f"Error deleting XML {xml_path}: {e}")

            # Find and delete DAT/BLOB files matching appid pattern in steam2_sdk_depots
            if os.path.isdir(sdk_dir):
                try:
                    for filename in os.listdir(sdk_dir):
                        # Check if filename starts with appid followed by underscore
                        if filename.startswith(f"{appid}_"):
                            ext = os.path.splitext(filename)[1].lower()
                            if ext in {'.dat', '.blob'}:
                                file_path = os.path.join(sdk_dir, filename)
                                try:
                                    os.remove(file_path)
                                    deleted_files.append(file_path)
                                    log.info(f"Deleted depot file: {file_path}")
                                except Exception as e:
                                    errors.append(f"Error deleting {file_path}: {e}")
                except Exception as e:
                    errors.append(f"Error scanning SDK depot directory: {e}")

            # Remove the database entry
            db_result = self.database.remove_approved_application(appid)
            if db_result is not True:
                errors.append(f"Database error: {db_result}")

            # Log the admin action
            admin_info = {"username": "console_admin", "ip": "127.0.0.1"}
            details = f"Deleted {len(deleted_files)} files"
            if errors:
                details += f"; Errors: {'; '.join(errors)}"
            self.database.log_ftp_admin_action(admin_info, appid, "DELETE", details)

            if errors:
                return True, f"Application {appid} deleted with errors: {'; '.join(errors)}. {len(deleted_files)} files removed."
            return True, f"Application {appid} deleted successfully. {len(deleted_files)} files removed."

        except Exception as e:
            log.error(f"Error deleting application {appid}: {e}")
            return False, f"Error: {e}"

    def parse_subscriptions_from_xml(self, xml_path):
        """
        Parse subscription records from an XML file.
        Returns list of dicts: [{"id": "123", "name": "Sub Name"}, ...]
        """
        subscriptions = []
        try:
            if not os.path.exists(xml_path):
                log.warning(f"XML file not found: {xml_path}")
                return subscriptions
            tree = ET.parse(xml_path)
            root = tree.getroot()
            # Find all subscription records
            for sub_record in root.findall(".//AllSubscriptionsRecord/SubscriptionRecord"):
                # Try to get SubscriptionId from attribute first
                sub_id = sub_record.get("SubscriptionId")
                if sub_id is None:
                    # Try to get from child element
                    sub_id_elem = sub_record.find("SubscriptionId")
                    sub_id = sub_id_elem.text if sub_id_elem is not None else None
                name_elem = sub_record.find("Name")
                name = name_elem.text if name_elem is not None else "Unknown"
                if sub_id is not None:
                    subscriptions.append({"id": str(sub_id), "name": name})
            log.info(f"Parsed {len(subscriptions)} subscriptions from {xml_path}")
        except Exception as e:
            log.error(f"Error parsing XML subscriptions: {e}")
        return subscriptions

    def parse_app_names_from_xml(self, xml_path):
        """
        Parse app names from an XML file.
        Returns comma-separated string of app names.
        """
        app_names = []
        try:
            if not os.path.exists(xml_path):
                return ""
            tree = ET.parse(xml_path)
            root = tree.getroot()
            for app_record in root.findall(".//AllAppsRecord/AppRecord"):
                name_elem = app_record.find("Name")
                if name_elem is not None and name_elem.text:
                    app_names.append(name_elem.text)
        except Exception as e:
            log.error(f"Error parsing XML app names: {e}")
        return ", ".join(app_names)

    def reparse_pending_from_xml(self, appid):
        """
        Re-parse metadata from the XML file for a pending application.
        Returns (success, message, new_app_names, new_subscriptions).
        """
        from utilities.database.base_dbdriver import AwaitingReview
        try:
            # Expire cached data to ensure fresh read from database
            self.database.session.expire_all()
            entry = self.database.session.query(AwaitingReview).filter_by(appid=appid).first()
            if not entry:
                return False, "Application not found", "", ""

            uploader = entry.uploader or ''

            # Find the XML file - check multiple possible locations
            xml_path = None

            # First, try to find XML in the file_paths list
            if entry.file_paths:
                for path in entry.file_paths.split('|'):
                    if path.endswith('.xml') and os.path.exists(path):
                        xml_path = path
                        break

            # If not found, search in common locations
            if not xml_path:
                possible_paths = [
                    # User-specific temp folder (new location)
                    os.path.join("files", "temp", uploader, f"{appid}.xml"),
                    # Root temp folder (old location)
                    os.path.join("files", "temp", f"{appid}.xml"),
                    # ContentDescriptionDB.xml in user folder
                    os.path.join("files", "temp", uploader, "ContentDescriptionDB.xml"),
                    # ContentDescriptionDB.xml in root temp
                    os.path.join("files", "temp", "ContentDescriptionDB.xml"),
                ]
                for path in possible_paths:
                    if os.path.exists(path):
                        xml_path = path
                        log.info(f"Found XML at fallback location: {path}")
                        break

            if not xml_path:
                return False, f"No XML file found for appid {appid}", "", ""

            # Parse the XML
            subs_list = self.parse_subscriptions_from_xml(xml_path)
            app_names = self.parse_app_names_from_xml(xml_path)

            # Format subscriptions as "id:name|id:name|..."
            subs_str = "|".join([f"{s['id']}:{s['name']}" for s in subs_list])

            # Update the database entry
            entry.app_names = app_names
            entry.subscriptions = subs_str

            # Also update file_paths if the XML wasn't there
            if not entry.file_paths or xml_path not in entry.file_paths:
                if entry.file_paths:
                    entry.file_paths = entry.file_paths + "|" + xml_path
                else:
                    entry.file_paths = xml_path

            self.database.session.commit()

            return True, f"Re-parsed: {len(subs_list)} subscriptions, {len(app_names.split(',')) if app_names else 0} apps", app_names, subs_str

        except Exception as e:
            log.error(f"Error re-parsing XML: {e}")
            return False, f"Error: {e}", "", ""

    def _update_xml_subscriptions(self, xml_path, subscriptions_str):
        """
        Update subscription IDs in an XML file.
        subscriptions_str format: "id:name|id:name|..."
        """
        if not subscriptions_str or not os.path.exists(xml_path):
            return

        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()

            # Parse the new subscriptions
            new_subs = {}
            for sub in subscriptions_str.split('|'):
                if ':' in sub:
                    sub_id, sub_name = sub.split(':', 1)
                    new_subs[sub_id.strip()] = sub_name.strip()

            # Update existing subscription records
            for sub_record in root.findall(".//AllSubscriptionsRecord/SubscriptionRecord"):
                sub_id_attr = sub_record.get("SubscriptionId")
                sub_id_elem = sub_record.find("SubscriptionId")

                old_id = None
                if sub_id_attr:
                    old_id = sub_id_attr
                elif sub_id_elem is not None:
                    old_id = sub_id_elem.text

                # Find corresponding new subscription
                # For now, we update by matching names since IDs might change
                name_elem = sub_record.find("Name")
                if name_elem is not None:
                    current_name = name_elem.text or ""
                    # Check if there's a new ID for this name
                    for new_id, new_name in new_subs.items():
                        if new_name == current_name or (old_id and old_id in new_subs):
                            if sub_id_attr is not None:
                                sub_record.set("SubscriptionId", new_id if old_id in new_subs else sub_id_attr)
                            if sub_id_elem is not None:
                                sub_id_elem.text = new_id if old_id in new_subs else sub_id_elem.text
                            break

            tree.write(xml_path, encoding='utf-8', xml_declaration=True)
        except Exception as e:
            log.error(f"Error updating XML subscriptions: {e}")
            raise

    def approve_application_with_subscriptions(self, appid, modified_subscriptions=None):
        """
        Approve a pending application with optionally modified subscriptions.
        All files (XML, DAT, BLOB) are tracked in file_paths.
        XML files go to mod_blob directory, DAT/BLOB files go to steam2_sdk_depots.
        Auto-discovery is still performed as a fallback for any untracked files.
        After moving, triggers blob merge via cache_cdr.
        """
        from utilities.cdr_manipulator import cache_cdr, load_blobs_to_memory

        pending = self.database.get_pending_upload_by_appid(appid)
        if not pending:
            return False, "Application not found"

        sdk_dir = self.database.get_sdk_depot_directory()
        mod_blob_dir = self.database.get_mod_blob_directory()

        os.makedirs(sdk_dir, exist_ok=True)
        os.makedirs(mod_blob_dir, exist_ok=True)

        moved_files = []
        errors = []
        xml_dest_path = None
        temp_directory = None

        try:
            # Process all tracked files (XML, DAT, BLOB) and determine temp directory
            for file_path in pending['file_paths']:
                if not os.path.exists(file_path):
                    errors.append(f"File not found: {file_path}")
                    continue

                # Remember the temp directory for auto-discovery fallback
                if temp_directory is None:
                    temp_directory = os.path.dirname(file_path)

                filename = os.path.basename(file_path)
                ext = os.path.splitext(filename)[1].lower()

                try:
                    if ext == '.xml':
                        dest = os.path.join(mod_blob_dir, filename)
                        # If subscriptions were modified, update the XML before moving
                        if modified_subscriptions:
                            self._update_xml_subscriptions(file_path, modified_subscriptions)
                        shutil.move(file_path, dest)
                        moved_files.append(dest)
                        xml_dest_path = dest
                        log.info(f"Approved: moved {filename} to {dest}")
                    elif ext in {'.dat', '.blob'}:
                        dest = os.path.join(sdk_dir, filename)
                        shutil.move(file_path, dest)
                        moved_files.append(dest)
                        log.info(f"Approved: moved {filename} to {dest}")
                    else:
                        errors.append(f"Unknown file type: {filename}")
                except Exception as e:
                    errors.append(f"Error moving {filename}: {e}")

            # Auto-discover any remaining depot files (fallback for untracked files)
            if temp_directory and os.path.isdir(temp_directory):
                try:
                    for filename in os.listdir(temp_directory):
                        # Check if filename starts with appid followed by underscore
                        if filename.startswith(f"{appid}_"):
                            ext = os.path.splitext(filename)[1].lower()
                            if ext in {'.dat', '.blob'}:
                                src_path = os.path.join(temp_directory, filename)
                                dest_path = os.path.join(sdk_dir, filename)
                                try:
                                    shutil.move(src_path, dest_path)
                                    moved_files.append(dest_path)
                                    log.info(f"Approved: auto-discovered and moved {filename} to {dest_path}")
                                except Exception as e:
                                    errors.append(f"Error moving depot {filename}: {e}")
                except Exception as e:
                    errors.append(f"Error scanning temp directory: {e}")

            # After moving XML, trigger blob merge via cache_cdr
            if xml_dest_path and os.path.exists(xml_dest_path):
                try:
                    log.info(f"Triggering cache_cdr for LAN after approval of appid {appid}")
                    cache_cdr(islan=True, isAppApproval_merge=True)
                    log.info(f"Triggering cache_cdr for WAN after approval of appid {appid}")
                    cache_cdr(islan=False, isAppApproval_merge=True)
                    log.info(f"Blob merge completed for appid {appid}")
                    # Reload blobs into memory from the updated cache files
                    load_blobs_to_memory()
                    log.info(f"Memory blobs reloaded after approval of appid {appid}")
                except Exception as e:
                    errors.append(f"Cache merge failed: {e}")
                    log.error(f"Failed to merge appid {appid} into cached blobs: {e}")

            # Log the admin action
            details = f"Approved {len(moved_files)} files with modified subscriptions"
            if errors:
                details += f"; Errors: {'; '.join(errors)}"
            admin_info = {"username": "console_admin", "ip": "127.0.0.1"}
            self.database.log_ftp_admin_action(admin_info, appid, "APPROVE", details)

            # Add to approved applications table
            subs_to_store = modified_subscriptions if modified_subscriptions else pending.get('subscriptions', '')
            self.database.add_approved_application(
                appid=appid,
                app_names=pending.get('app_names', ''),
                subscriptions=subs_to_store,
                xml_file_path=xml_dest_path,
                approved_by="console_admin"
            )

            # Remove from pending
            self.database.remove_pending_upload(appid)

            if errors:
                return True, f"Application {appid} approved with errors: {'; '.join(errors)}. {len(moved_files)} files moved."
            return True, f"Application {appid} approved. {len(moved_files)} files moved."

        except Exception as e:
            log.error(f"Error approving application {appid}: {e}")
            return False, f"Error: {e}"


# =============================================================================
# Curses-based Menu UI
# =============================================================================

class CursesMenu:
    """Curses-based interactive menu system."""

    def __init__(self, screen):
        self.screen = screen
        self.manager = FTPMenuManager()
        curses.curs_set(0)  # Hide cursor

        # Initialize colors if available
        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLUE)   # Selected
            curses.init_pair(2, curses.COLOR_GREEN, -1)                  # Success
            curses.init_pair(3, curses.COLOR_RED, -1)                    # Error/Locked
            curses.init_pair(4, curses.COLOR_YELLOW, -1)                 # Warning
            curses.init_pair(5, curses.COLOR_CYAN, -1)                   # Info

    def draw_title(self, title):
        """Draw a title bar at the top of the screen."""
        h, w = self.screen.getmaxyx()
        title_str = f" {title} "
        padding = (w - len(title_str)) // 2
        self.screen.attron(curses.A_BOLD)
        self.screen.addstr(0, 0, "=" * w)
        self.screen.addstr(1, padding, title_str)
        self.screen.addstr(2, 0, "=" * w)
        self.screen.attroff(curses.A_BOLD)

    def draw_footer(self, text="Use UP/DOWN arrows to navigate, ENTER to select, ESC to go back"):
        """Draw a footer at the bottom of the screen."""
        h, w = self.screen.getmaxyx()
        self.screen.addstr(h - 1, 0, text[:w-1], curses.A_DIM)

    def show_message(self, message, is_error=False, wait=True):
        """Display a message and optionally wait for keypress."""
        h, w = self.screen.getmaxyx()
        self.screen.clear()
        self.draw_title("Message")

        color = curses.color_pair(3) if is_error else curses.color_pair(2)

        # Word wrap the message
        lines = []
        for line in message.split('\n'):
            while len(line) > w - 4:
                lines.append(line[:w-4])
                line = line[w-4:]
            lines.append(line)

        y = 5
        for line in lines:
            if y < h - 3:
                self.screen.addstr(y, 2, line, color)
                y += 1

        if wait:
            self.screen.addstr(h - 2, 2, "Press any key to continue...")
            self.screen.refresh()
            self.screen.getch()

    def get_input(self, prompt, y_pos=5, hidden=False):
        """Get text input from the user."""
        h, w = self.screen.getmaxyx()
        curses.curs_set(1)  # Show cursor
        curses.echo()

        self.screen.addstr(y_pos, 2, prompt)
        self.screen.refresh()

        if hidden:
            curses.noecho()
            input_str = ""
            while True:
                ch = self.screen.getch()
                if ch in (curses.KEY_ENTER, 10, 13):
                    break
                elif ch in (curses.KEY_BACKSPACE, 127, 8):
                    if input_str:
                        input_str = input_str[:-1]
                        y, x = self.screen.getyx()
                        self.screen.addstr(y, x - 1, " ")
                        self.screen.move(y, x - 1)
                elif 32 <= ch < 127:
                    input_str += chr(ch)
                    self.screen.addch('*')
                self.screen.refresh()
        else:
            try:
                input_bytes = self.screen.getstr(y_pos, 2 + len(prompt), 100)
                input_str = input_bytes.decode('utf-8', errors='ignore')
            except:
                input_str = ""

        curses.noecho()
        curses.curs_set(0)  # Hide cursor
        return input_str.strip()

    def select_from_list(self, title, items, show_locked=False):
        """
        Display a selectable list and return the selected index.
        items: list of strings or list of tuples (display_text, data)
        Returns: (selected_index, selected_data) or (-1, None) if cancelled
        """
        if not items:
            self.show_message("No items to display.", is_error=True)
            return -1, None

        current = 0
        offset = 0

        while True:
            self.screen.clear()
            self.draw_title(title)
            self.draw_footer()

            h, w = self.screen.getmaxyx()
            max_display = h - 7  # Leave room for title and footer

            # Adjust offset for scrolling
            if current < offset:
                offset = current
            elif current >= offset + max_display:
                offset = current - max_display + 1

            # Draw items
            for i in range(min(len(items), max_display)):
                idx = offset + i
                if idx >= len(items):
                    break

                item = items[idx]
                if isinstance(item, tuple):
                    display_text = item[0]
                else:
                    display_text = str(item)

                y = 4 + i
                # Truncate if too long
                if len(display_text) > w - 6:
                    display_text = display_text[:w-9] + "..."

                if idx == current:
                    self.screen.attron(curses.color_pair(1) | curses.A_BOLD)
                    self.screen.addstr(y, 2, f"> {display_text}")
                    self.screen.attroff(curses.color_pair(1) | curses.A_BOLD)
                else:
                    # Check for locked indicator
                    if "(Locked)" in display_text:
                        self.screen.addstr(y, 2, f"  {display_text}", curses.color_pair(3))
                    else:
                        self.screen.addstr(y, 2, f"  {display_text}")

            # Show scroll indicators
            if offset > 0:
                self.screen.addstr(3, w - 3, "^", curses.A_BOLD)
            if offset + max_display < len(items):
                self.screen.addstr(4 + max_display, w - 3, "v", curses.A_BOLD)

            self.screen.refresh()

            key = self.screen.getch()

            if key == curses.KEY_UP:
                current = (current - 1) % len(items)
            elif key == curses.KEY_DOWN:
                current = (current + 1) % len(items)
            elif key == curses.KEY_PPAGE:  # Page Up
                current = max(0, current - max_display)
            elif key == curses.KEY_NPAGE:  # Page Down
                current = min(len(items) - 1, current + max_display)
            elif key == curses.KEY_HOME:
                current = 0
            elif key == curses.KEY_END:
                current = len(items) - 1
            elif key in (curses.KEY_ENTER, 10, 13):
                item = items[current]
                if isinstance(item, tuple):
                    return current, item[1]
                return current, item
            elif key == 27:  # ESC
                return -1, None

    # -------------------------------------------------------------------------
    # Menu Handlers
    # -------------------------------------------------------------------------

    def menu_create_user(self):
        """Create new FTP user menu."""
        self.screen.clear()
        self.draw_title("Create New FTP User")

        username = self.get_input("Enter username: ", y_pos=5)
        if not username:
            self.show_message("Username cannot be empty.", is_error=True)
            return

        self.screen.clear()
        self.draw_title("Create New FTP User")
        self.screen.addstr(5, 2, f"Username: {username}")

        password = self.get_input("Enter password: ", y_pos=7, hidden=True)
        if not password:
            self.show_message("Password cannot be empty.", is_error=True)
            return

        success, message = self.manager.add_ftp_user(username, password)
        self.show_message(message, is_error=not success)

    def menu_set_quota(self):
        """Set user quota menu."""
        users = self.manager.get_ftp_users()
        if not users:
            self.show_message("No FTP users found.", is_error=True)
            return

        # Build user list with current quota info
        quotas = self.manager.get_quotas()
        items = []
        for user in users:
            quota_info = quotas.get(user['username'], {})
            quota_mb = quota_info.get('quota', 0)
            display = f"{user['username']} (Current: {quota_mb}MB)"
            items.append((display, user['username']))

        idx, username = self.select_from_list("Select User to Set Quota", items)
        if idx == -1:
            return

        self.screen.clear()
        self.draw_title(f"Set Quota for {username}")

        quota_str = self.get_input("Enter quota limit in MB (0 for unlimited): ", y_pos=5)
        try:
            quota_mb = int(quota_str)
        except ValueError:
            self.show_message("Invalid quota value.", is_error=True)
            return

        self.screen.clear()
        self.draw_title(f"Set Quota for {username}")
        self.screen.addstr(5, 2, f"Quota: {quota_mb}MB")

        bw_str = self.get_input("Enter bandwidth limit in KB/s (0 for unlimited): ", y_pos=7)
        try:
            bw_kbps = int(bw_str)
        except ValueError:
            bw_kbps = 0

        success, message = self.manager.set_user_quota(username, quota_mb, bw_kbps)
        self.show_message(message, is_error=not success)

    def menu_change_password(self):
        """Change user password menu."""
        users = self.manager.get_ftp_users()
        if not users:
            self.show_message("No FTP users found.", is_error=True)
            return

        items = [(user['username'], user['username']) for user in users]

        idx, username = self.select_from_list("Select User to Change Password", items)
        if idx == -1:
            return

        self.screen.clear()
        self.draw_title(f"Change Password for {username}")

        new_password = self.get_input("Enter new password: ", y_pos=5, hidden=True)
        if not new_password:
            self.show_message("Password cannot be empty.", is_error=True)
            return

        success, message = self.manager.change_user_password(username, new_password)
        self.show_message(message, is_error=not success)

    def menu_lock_unlock_user(self):
        """Lock/unlock user account menu."""
        users = self.manager.get_ftp_users()
        if not users:
            self.show_message("No FTP users found.", is_error=True)
            return

        items = []
        for user in users:
            display = user['username']
            if user['locked']:
                display += " (Locked)"
            items.append((display, user['username']))

        idx, username = self.select_from_list("Select User to Lock/Unlock", items)
        if idx == -1:
            return

        success, message = self.manager.toggle_user_lock(username)
        self.show_message(message, is_error=not success)

    def menu_pending_applications(self):
        """Pending applications menu."""
        pending = self.manager.get_pending_applications()
        if not pending:
            self.show_message("No pending applications.", is_error=False)
            return

        # Build list with app names
        items = []
        for app in pending:
            app_name = app['app_names'] if app['app_names'] else f"AppID {app['appid']}"
            # Truncate long names
            if len(app_name) > 50:
                app_name = app_name[:47] + "..."
            items.append((app_name, app['appid']))

        idx, appid = self.select_from_list("Pending Applications", items)
        if idx == -1:
            return

        # Show application details menu
        self.menu_application_details(appid)

    def menu_application_details(self, appid):
        """Show details and options for a specific pending application."""
        pending = self.manager.database.get_pending_upload_by_appid(appid)
        if not pending:
            self.show_message("Application not found.", is_error=True)
            return

        # Store current subscriptions (can be modified before approval)
        current_subscriptions = pending.get('subscriptions', '')

        while True:
            self.screen.clear()
            self.draw_title(f"Application Details - AppID: {appid}")

            h, w = self.screen.getmaxyx()

            # Display application info
            y = 4
            self.screen.addstr(y, 2, "Application Information:", curses.A_BOLD | curses.color_pair(5))
            y += 2

            # App Names
            app_names = pending.get('app_names', 'N/A')
            self.screen.addstr(y, 2, f"App Name(s): {app_names[:w-15] if len(app_names) > w-15 else app_names}")
            y += 1

            # App ID
            self.screen.addstr(y, 2, f"AppID: {appid}")
            y += 1

            # Subscriptions
            if current_subscriptions:
                self.screen.addstr(y, 2, "Subscriptions:", curses.A_BOLD)
                y += 1
                for sub in current_subscriptions.split('|')[:5]:  # Show max 5 subscriptions
                    if ':' in sub:
                        sub_id, sub_name = sub.split(':', 1)
                        self.screen.addstr(y, 4, f"- ID {sub_id}: {sub_name[:w-20]}")
                    else:
                        self.screen.addstr(y, 4, f"- {sub}")
                    y += 1
                if len(current_subscriptions.split('|')) > 5:
                    self.screen.addstr(y, 4, f"... and {len(current_subscriptions.split('|')) - 5} more")
                    y += 1
            else:
                self.screen.addstr(y, 2, "Subscriptions: N/A")
                y += 1

            # Uploader info
            y += 1
            self.screen.addstr(y, 2, f"Uploader: {pending['uploader']} ({pending['uploader_ip']})")
            y += 1
            self.screen.addstr(y, 2, f"Upload Date: {pending['upload_datetime']}")
            y += 1
            self.screen.addstr(y, 2, f"Total Size: {pending['total_size']} bytes")
            y += 1
            self.screen.addstr(y, 2, f"Files: {len(pending['file_paths'])}")
            y += 2

            # Menu options
            options = [
                ("Re-parse from XML", "reparse"),
                ("Edit Subscriptions", "edit_subs"),
                ("Approve Application", "approve"),
                ("Deny Application", "deny"),
                ("Go Back", "back")
            ]

            self.screen.addstr(y, 2, "Options:", curses.A_BOLD)
            y += 1

            current = 0
            option_start_y = y

            while True:
                for i, (label, action) in enumerate(options):
                    if i == current:
                        self.screen.attron(curses.color_pair(1) | curses.A_BOLD)
                        self.screen.addstr(option_start_y + i, 2, f"> {label}")
                        self.screen.attroff(curses.color_pair(1) | curses.A_BOLD)
                    else:
                        if action == "approve":
                            self.screen.addstr(option_start_y + i, 2, f"  {label}", curses.color_pair(2))
                        elif action == "deny":
                            self.screen.addstr(option_start_y + i, 2, f"  {label}", curses.color_pair(3))
                        elif action == "edit_subs":
                            self.screen.addstr(option_start_y + i, 2, f"  {label}", curses.color_pair(4))
                        else:
                            self.screen.addstr(option_start_y + i, 2, f"  {label}")

                self.draw_footer()
                self.screen.refresh()

                key = self.screen.getch()

                if key == curses.KEY_UP:
                    current = (current - 1) % len(options)
                elif key == curses.KEY_DOWN:
                    current = (current + 1) % len(options)
                elif key in (curses.KEY_ENTER, 10, 13):
                    action = options[current][1]

                    if action == "reparse":
                        # Re-parse metadata from the XML file
                        success, message, new_app_names, new_subs = self.manager.reparse_pending_from_xml(appid)
                        if success:
                            current_subscriptions = new_subs
                            # Refresh pending data
                            pending = self.manager.database.get_pending_upload_by_appid(appid)
                        self.show_message(message, is_error=not success)
                        break  # Refresh the details screen
                    elif action == "edit_subs":
                        # Edit subscriptions before approval
                        new_subs = self.menu_edit_subscriptions(appid, current_subscriptions)
                        if new_subs is not None:
                            current_subscriptions = new_subs
                        break  # Refresh the details screen
                    elif action == "approve":
                        # Approve with potentially modified subscriptions
                        success, message = self.manager.approve_application_with_subscriptions(
                            appid, current_subscriptions
                        )
                        self.show_message(message, is_error=not success)
                        return  # Go back to pending list
                    elif action == "deny":
                        # Confirm denial
                        self.screen.clear()
                        self.draw_title("Confirm Denial")
                        self.screen.addstr(5, 2, f"Are you sure you want to deny AppID {appid}?")
                        self.screen.addstr(6, 2, "This will DELETE all uploaded files!")
                        self.screen.addstr(8, 2, "Press Y to confirm, any other key to cancel")
                        self.screen.refresh()

                        confirm = self.screen.getch()
                        if confirm in (ord('y'), ord('Y')):
                            success, message = self.manager.deny_application(appid)
                            self.show_message(message, is_error=not success)
                        return  # Go back to pending list
                    elif action == "back":
                        return
                elif key == 27:  # ESC
                    return

    def menu_edit_subscriptions(self, appid, current_subscriptions):
        """
        Menu for editing subscription IDs.
        Returns the modified subscriptions string or None if cancelled.
        """
        # Parse current subscriptions into a list
        subs_list = []
        if current_subscriptions:
            for sub in current_subscriptions.split('|'):
                if ':' in sub:
                    sub_id, sub_name = sub.split(':', 1)
                    subs_list.append({"id": sub_id.strip(), "name": sub_name.strip()})
                elif sub.strip():
                    subs_list.append({"id": sub.strip(), "name": "Unknown"})

        # If no subscriptions, offer to add one
        if not subs_list:
            self.screen.clear()
            self.draw_title("No Subscriptions Found")
            self.screen.addstr(5, 2, "No subscriptions found. Would you like to add one?")
            self.screen.addstr(7, 2, "Press Y to add a subscription, any other key to cancel")
            self.screen.refresh()

            key = self.screen.getch()
            if key not in (ord('y'), ord('Y')):
                return None

            # Add a new subscription
            self.screen.clear()
            self.draw_title("Add Subscription")
            sub_id = self.get_input("Enter Subscription ID: ", y_pos=5)
            if not sub_id or not sub_id.strip():
                return None
            sub_name = self.get_input("Enter Subscription Name: ", y_pos=7)
            if not sub_name:
                sub_name = "New Subscription"

            subs_list.append({"id": sub_id.strip(), "name": sub_name.strip()})
            self.show_message(f"Added subscription: ID {sub_id.strip()}", wait=False)
            curses.napms(1000)

        current = 0

        while True:
            self.screen.clear()
            self.draw_title(f"Edit Subscriptions - AppID: {appid}")

            h, w = self.screen.getmaxyx()
            y = 4

            self.screen.addstr(y, 2, "Select a subscription to edit its ID:", curses.A_BOLD)
            y += 2

            # Display subscriptions
            max_display = min(len(subs_list), h - 10)
            for i in range(max_display):
                sub = subs_list[i]
                display_text = f"ID: {sub['id']:>8} - {sub['name'][:w-25]}"
                if i == current:
                    self.screen.attron(curses.color_pair(1) | curses.A_BOLD)
                    self.screen.addstr(y + i, 2, f"> {display_text}")
                    self.screen.attroff(curses.color_pair(1) | curses.A_BOLD)
                else:
                    self.screen.addstr(y + i, 2, f"  {display_text}")

            # Show options at bottom
            footer_y = y + max_display + 2
            self.screen.addstr(footer_y, 2, "ENTER: Edit ID | A: Add new | D: Delete | S: Save | ESC: Cancel", curses.A_DIM)

            self.screen.refresh()
            key = self.screen.getch()

            if key == curses.KEY_UP:
                current = (current - 1) % len(subs_list)
            elif key == curses.KEY_DOWN:
                current = (current + 1) % len(subs_list)
            elif key in (curses.KEY_ENTER, 10, 13):
                # Edit the selected subscription's ID
                sub = subs_list[current]
                self.screen.clear()
                self.draw_title("Edit Subscription ID")
                self.screen.addstr(5, 2, f"Subscription: {sub['name']}")
                self.screen.addstr(6, 2, f"Current ID: {sub['id']}")

                new_id = self.get_input("Enter new ID: ", y_pos=8)
                if new_id and new_id.strip():
                    subs_list[current]['id'] = new_id.strip()
                    self.show_message(f"Subscription ID updated to: {new_id.strip()}", wait=False)
                    curses.napms(1000)
            elif key in (ord('a'), ord('A')):
                # Add new subscription
                self.screen.clear()
                self.draw_title("Add Subscription")
                sub_id = self.get_input("Enter Subscription ID: ", y_pos=5)
                if sub_id and sub_id.strip():
                    sub_name = self.get_input("Enter Subscription Name: ", y_pos=7)
                    if not sub_name:
                        sub_name = "New Subscription"
                    subs_list.append({"id": sub_id.strip(), "name": sub_name.strip()})
                    self.show_message(f"Added subscription: ID {sub_id.strip()}", wait=False)
                    curses.napms(1000)
            elif key in (ord('d'), ord('D')):
                # Delete selected subscription
                if len(subs_list) > 0:
                    sub = subs_list[current]
                    self.screen.clear()
                    self.draw_title("Delete Subscription")
                    self.screen.addstr(5, 2, f"Delete subscription ID {sub['id']}: {sub['name']}?")
                    self.screen.addstr(7, 2, "Press Y to confirm, any other key to cancel")
                    self.screen.refresh()
                    confirm = self.screen.getch()
                    if confirm in (ord('y'), ord('Y')):
                        del subs_list[current]
                        if current >= len(subs_list) and len(subs_list) > 0:
                            current = len(subs_list) - 1
                        self.show_message("Subscription deleted", wait=False)
                        curses.napms(1000)
            elif key in (ord('s'), ord('S')):
                # Save and return
                result = '|'.join([f"{s['id']}:{s['name']}" for s in subs_list])
                return result
            elif key == 27:  # ESC - cancel
                return None

    def menu_approved_applications(self):
        """Menu for managing approved applications."""
        apps = self.manager.get_approved_applications()
        if not apps:
            self.show_message("No approved applications found.", is_error=False)
            return

        # Build list with app names
        items = []
        for app in apps:
            app_name = app['app_names'] if app['app_names'] else f"AppID {app['appid']}"
            # Truncate long names
            if len(app_name) > 50:
                app_name = app_name[:47] + "..."
            items.append((f"{app_name} [{app['appid']}]", app['appid']))

        idx, appid = self.select_from_list("Approved Applications - Select to Edit", items)
        if idx == -1:
            return

        # Show application edit menu
        self.menu_edit_approved_application(appid)

    def menu_delete_approved_application(self):
        """Menu for deleting an approved application."""
        apps = self.manager.get_approved_applications()
        if not apps:
            self.show_message("No approved applications found.", is_error=False)
            return

        # Build list with app names
        items = []
        for app in apps:
            app_name = app['app_names'] if app['app_names'] else f"AppID {app['appid']}"
            # Truncate long names
            if len(app_name) > 50:
                app_name = app_name[:47] + "..."
            items.append((f"{app_name} [{app['appid']}]", app['appid']))

        idx, appid = self.select_from_list("Delete Approved Application - Select to Delete", items)
        if idx == -1:
            return

        # Get app details for confirmation
        app_data = self.manager.get_approved_application_by_appid(appid)
        if not app_data:
            self.show_message("Application not found.", is_error=True)
            return

        # Confirm deletion
        self.screen.clear()
        self.draw_title(f"Confirm Deletion - AppID: {appid}")

        h, w = self.screen.getmaxyx()
        y = 4

        app_name = app_data.get('app_names', 'N/A')
        self.screen.addstr(y, 2, f"Application: {app_name[:w-15] if len(app_name) > w-15 else app_name}", curses.A_BOLD)
        y += 1
        self.screen.addstr(y, 2, f"AppID: {appid}")
        y += 2

        self.screen.addstr(y, 2, "This will delete:", curses.color_pair(3))
        y += 1
        self.screen.addstr(y, 4, "- The XML file from mod_blob")
        y += 1
        self.screen.addstr(y, 4, "- All DAT/BLOB files from steam2_sdk_depots")
        y += 1
        self.screen.addstr(y, 4, "- The database entry")
        y += 2

        self.screen.addstr(y, 2, "Are you sure you want to delete this application?", curses.A_BOLD | curses.color_pair(4))
        y += 1
        self.screen.addstr(y, 2, "Press Y to confirm, any other key to cancel")

        self.screen.refresh()

        key = self.screen.getch()
        if key in (ord('y'), ord('Y')):
            success, message = self.manager.delete_approved_application(appid)
            self.show_message(message, is_error=not success)
        else:
            self.show_message("Deletion cancelled.", is_error=False)

    def menu_edit_approved_application(self, appid):
        """Menu for editing an approved application's details."""
        app_data = self.manager.get_approved_application_by_appid(appid)
        if not app_data:
            self.show_message("Application not found.", is_error=True)
            return

        while True:
            self.screen.clear()
            self.draw_title(f"Edit Application - AppID: {appid}")

            h, w = self.screen.getmaxyx()

            # Display current application info
            y = 4
            self.screen.addstr(y, 2, "Current Application Details:", curses.A_BOLD | curses.color_pair(5))
            y += 2

            # App Names
            app_names = app_data.get('app_names', 'N/A')
            self.screen.addstr(y, 2, f"App Name(s): {app_names[:w-15] if len(app_names) > w-15 else app_names}")
            y += 1

            # App ID
            self.screen.addstr(y, 2, f"AppID: {appid}")
            y += 1

            # Subscriptions
            subs = app_data.get('subscriptions', '')
            if subs:
                self.screen.addstr(y, 2, "Subscriptions:", curses.A_BOLD)
                y += 1
                for sub in subs.split('|')[:5]:  # Show max 5 subscriptions
                    if ':' in sub:
                        sub_id, sub_name = sub.split(':', 1)
                        self.screen.addstr(y, 4, f"- ID {sub_id}: {sub_name[:w-20]}")
                    else:
                        self.screen.addstr(y, 4, f"- {sub}")
                    y += 1
                if len(subs.split('|')) > 5:
                    self.screen.addstr(y, 4, f"... and {len(subs.split('|')) - 5} more")
                    y += 1
            else:
                self.screen.addstr(y, 2, "Subscriptions: N/A")
                y += 1

            # Approval info
            y += 1
            self.screen.addstr(y, 2, f"Approved: {app_data.get('approval_datetime', 'N/A')} by {app_data.get('approved_by', 'N/A')}")
            y += 1
            if app_data.get('last_modified'):
                self.screen.addstr(y, 2, f"Last Modified: {app_data['last_modified']} by {app_data.get('modified_by', 'N/A')}")
                y += 1
            y += 1

            # Menu options
            options = [
                ("Edit App Name", "edit_name"),
                ("Edit Subscriptions", "edit_subs"),
                ("Go Back", "back")
            ]

            self.screen.addstr(y, 2, "Options:", curses.A_BOLD)
            y += 1

            current = 0
            option_start_y = y

            while True:
                for i, (label, action) in enumerate(options):
                    if i == current:
                        self.screen.attron(curses.color_pair(1) | curses.A_BOLD)
                        self.screen.addstr(option_start_y + i, 2, f"> {label}")
                        self.screen.attroff(curses.color_pair(1) | curses.A_BOLD)
                    else:
                        if action == "edit_name":
                            self.screen.addstr(option_start_y + i, 2, f"  {label}", curses.color_pair(5))
                        elif action == "edit_subs":
                            self.screen.addstr(option_start_y + i, 2, f"  {label}", curses.color_pair(4))
                        else:
                            self.screen.addstr(option_start_y + i, 2, f"  {label}")

                self.draw_footer()
                self.screen.refresh()

                key = self.screen.getch()

                if key == curses.KEY_UP:
                    current = (current - 1) % len(options)
                elif key == curses.KEY_DOWN:
                    current = (current + 1) % len(options)
                elif key in (curses.KEY_ENTER, 10, 13):
                    action = options[current][1]

                    if action == "edit_name":
                        self.screen.clear()
                        self.draw_title("Edit Application Name")
                        self.screen.addstr(5, 2, f"Current Name: {app_data.get('app_names', 'N/A')}")
                        new_name = self.get_input("Enter new name: ", y_pos=7)
                        if new_name and new_name.strip():
                            success, msg = self.manager.update_approved_application(
                                appid, app_names=new_name.strip()
                            )
                            self.show_message(msg, is_error=not success)
                            # Refresh app_data
                            app_data = self.manager.get_approved_application_by_appid(appid)
                        break  # Refresh the edit screen

                    elif action == "edit_subs":
                        current_subs = app_data.get('subscriptions', '')
                        new_subs = self.menu_edit_subscriptions(appid, current_subs)
                        if new_subs is not None:
                            success, msg = self.manager.update_approved_application(
                                appid, subscriptions=new_subs
                            )
                            self.show_message(msg, is_error=not success)
                            # Refresh app_data
                            app_data = self.manager.get_approved_application_by_appid(appid)
                        break  # Refresh the edit screen

                    elif action == "back":
                        return

                elif key == 27:  # ESC
                    return

    def main_menu(self):
        """Main FTP management menu."""
        options = [
            ("Create New User", self.menu_create_user),
            ("Set User Quota", self.menu_set_quota),
            ("Change User Password", self.menu_change_password),
            ("Lock/Unlock User Account", self.menu_lock_unlock_user),
            ("Applications Pending Approval", self.menu_pending_applications),
            ("Manage Approved Applications", self.menu_approved_applications),
            ("Delete Approved Application", self.menu_delete_approved_application),
            ("Exit Menu", None)
        ]

        current = 0

        while True:
            self.screen.clear()
            self.draw_title("FTP Management Menu")
            self.draw_footer()

            for i, (label, handler) in enumerate(options):
                y = 5 + i
                if i == current:
                    self.screen.attron(curses.color_pair(1) | curses.A_BOLD)
                    self.screen.addstr(y, 2, f"> {label}")
                    self.screen.attroff(curses.color_pair(1) | curses.A_BOLD)
                else:
                    self.screen.addstr(y, 2, f"  {label}")

            self.screen.refresh()

            key = self.screen.getch()

            if key == curses.KEY_UP:
                current = (current - 1) % len(options)
            elif key == curses.KEY_DOWN:
                current = (current + 1) % len(options)
            elif key in (curses.KEY_ENTER, 10, 13):
                handler = options[current][1]
                if handler is None:  # Exit
                    break
                handler()
            elif key == 27:  # ESC
                break


def run_ftp_menu(screen=None):
    """
    Run the FTP management menu.
    Can be called with an existing curses screen or will initialize its own.
    """
    if not HAS_CURSES:
        print("Error: curses library not available.")
        print("On Windows, install with: pip install windows-curses")
        return False

    def _run(scr):
        menu = CursesMenu(scr)
        menu.main_menu()

    if screen is None:
        # Initialize curses ourselves
        try:
            curses.wrapper(_run)
        except Exception as e:
            print(f"Error running FTP menu: {e}")
            return False
    else:
        # Use provided screen
        _run(screen)

    return True


# For standalone testing
if __name__ == "__main__":
    run_ftp_menu()
