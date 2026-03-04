import ast
import binascii
import copy
import logging
import os
import pprint
import shutil
import struct
import zlib
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import mariadb
import xml.etree.ElementTree as ET

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from tzlocal import get_localzone

import globalvars
import utilities.blobs
from config import get_config as read_config
from utilities import blobs, encryption
from utilities.contentdescriptionrecord import ContentDescriptionRecord
from utilities.time import steamtime_to_datetime

config = read_config()
log = logging.getLogger('CDDB')
CACHE_DIR = os.path.join('files', 'cache')
EPHEMERAL_BLOB_DIR = os.path.join("files", "temp", "ephemeral_blobs")

# Track if subscription changelog has been written this session (overwrite on first write, append after)
_subscription_changelog_initialized = False


# ============================================================================
# DATABASE QUERY RESULT CACHING (Phase 6 Optimization)
# ============================================================================
# Cache database query results to avoid repeated expensive temporal queries
# when the timestamp hasn't changed (common case: multiple restarts with same date)

_blob_dict_cache = {}
_blob_dict_cache_lock = None

def _get_cache_lock():
    """Lazy initialization of cache lock."""
    global _blob_dict_cache_lock
    if _blob_dict_cache_lock is None:
        import threading
        _blob_dict_cache_lock = threading.Lock()
    return _blob_dict_cache_lock


def get_cached_blob_dict(cddb: str, timestamp: str):
    """
    Get cached blob dict if available for this database and timestamp.

    Args:
        cddb: Database name (e.g., 'ContentDescriptionDB' or 'BetaContentDescriptionDB')
        timestamp: Timestamp string for the temporal query

    Returns:
        Deep copy of cached blob dict if found, None otherwise
    """
    cache_key = (cddb, timestamp)
    with _get_cache_lock():
        if cache_key in _blob_dict_cache:
            log.debug(f"Using cached blob dict for {cddb} at {timestamp}")
            # Return deep copy to avoid modifications affecting cache
            return copy.deepcopy(_blob_dict_cache[cache_key])
    return None


def set_cached_blob_dict(cddb: str, timestamp: str, blob_dict: dict):
    """
    Cache a blob dict for future use.

    Args:
        cddb: Database name
        timestamp: Timestamp string
        blob_dict: The blob dict to cache (will be deep copied)
    """
    cache_key = (cddb, timestamp)
    with _get_cache_lock():
        # Only keep last 2 entries to avoid memory bloat
        if len(_blob_dict_cache) >= 2:
            # Remove oldest entry
            oldest_key = next(iter(_blob_dict_cache))
            del _blob_dict_cache[oldest_key]
        # Deep copy to isolate cache from modifications
        _blob_dict_cache[cache_key] = copy.deepcopy(blob_dict)
        log.debug(f"Cached blob dict for {cddb} at {timestamp}")


def clear_blob_dict_cache():
    """Clear the blob dict cache (call when config changes)."""
    with _get_cache_lock():
        _blob_dict_cache.clear()
        log.debug("Cleared blob dict cache")


# ============================================================================
# In-Memory CDR Blob Caching Functions
# ============================================================================

def load_blobs_to_memory():
    """
    Load all cached blob files into memory and update CDR_DICTIONARY.
    Thread-safe. Call this after cache files are finalized.

    This function:
    1. Reads LAN/WAN blobs (including 2003 versions) from cache files
    2. Stores serialized bytes in globalvars.CDR_BLOB_* variables
    3. Deserializes LAN blob to update globalvars.CDR_DICTIONARY
    4. Re-merges any ephemeral blobs from external content servers
    """
    if globalvars.CDR_BLOB_LOCK is None:
        import threading
        globalvars.CDR_BLOB_LOCK = threading.RLock()

    with globalvars.CDR_BLOB_LOCK:
        # Read LAN blobs
        globalvars.CDR_BLOB_LAN = _read_blob_file("secondblob_lan.bin")
        globalvars.CDR_BLOB_LAN_2003 = _read_blob_file("secondblob_lan_2003.bin")

        # Read WAN blobs
        globalvars.CDR_BLOB_WAN = _read_blob_file("secondblob_wan.bin")
        globalvars.CDR_BLOB_WAN_2003 = _read_blob_file("secondblob_wan_2003.bin")

        # Deserialize LAN blob for CDR_DICTIONARY and related globals
        if globalvars.CDR_BLOB_LAN is not None:
            _update_cdr_dictionary_from_blob(globalvars.CDR_BLOB_LAN)

        # Re-merge any ephemeral blobs from external content servers
        _remerge_ephemeral_blobs()

        log.info("Loaded CDR blobs into memory")


def _read_blob_file(filename):
    """
    Read a blob file from cache directory.

    Args:
        filename: Name of the file in CACHE_DIR

    Returns:
        bytes: File contents, or None if file not found
    """
    filepath = os.path.join(CACHE_DIR, filename)
    if os.path.isfile(filepath):
        try:
            with open(filepath, "rb") as f:
                return f.read()
        except Exception as e:
            log.warning(f"Failed to read blob file {filename}: {e}")
    return None


def _update_cdr_dictionary_from_blob(blob_bytes):
    """
    Decompress and deserialize blob bytes into CDR_DICTIONARY and related globals.

    Args:
        blob_bytes: Compressed/serialized blob bytes
    """
    if blob_bytes is None:
        return

    try:
        blob = blob_bytes
        if blob.startswith(b"\x01\x43"):
            blob = zlib.decompress(blob[20:])

        blob_dict = blobs.blob_unserialize(blob)

        # Update global dictionary
        globalvars.CDR_DICTIONARY = blob_dict

        # Update CDR object and related globals
        globalvars.CDR_obj = ContentDescriptionRecord(blob_dict)
        globalvars.subscription_pass_list = globalvars.CDR_obj.get_onpurchase_guest_passes_info()

        # Update datetime globals
        if b"\x03\x00\x00\x00" in blob_dict:
            globalvars.current_blob_datetime = steamtime_to_datetime(blob_dict[b"\x03\x00\x00\x00"])
            globalvars.CDDB_datetime = steamtime_to_datetime(blob_dict[b"\x03\x00\x00\x00"])

    except Exception as e:
        log.error(f"Failed to update CDR_DICTIONARY from blob: {e}")


def _reserialize_memory_blobs():
    """
    Re-serialize CDR_DICTIONARY back into CDR_BLOB_LAN and CDR_BLOB_WAN.
    Called after ephemeral merges to keep serialized blobs in sync with dictionary.

    Must be called while holding CDR_BLOB_LOCK.
    """
    if globalvars.CDR_DICTIONARY is None:
        return

    try:
        # Serialize the dictionary
        serialized = optimized_blob_serialize(globalvars.CDR_DICTIONARY)

        # If already compressed, decompress first
        if serialized.startswith(b"\x01\x43"):
            serialized = zlib.decompress(serialized[20:])

        # Compress with standard header
        compressed = zlib.compress(serialized, 9)
        final_blob = b"\x01\x43" + struct.pack("<QQH", len(compressed) + 20, len(serialized), 9) + compressed

        # Update both LAN and WAN (they're the same for ephemeral content)
        globalvars.CDR_BLOB_LAN = final_blob
        globalvars.CDR_BLOB_WAN = final_blob

    except Exception as e:
        log.error(f"Failed to re-serialize memory blobs: {e}")


# ============================================================================
# Ephemeral Blob Management (for external content servers)
# ============================================================================

def save_ephemeral_blob(sub_id, app_id, sub_blob, app_blob, server_id=None):
    """
    Save an ephemeral blob from an external content server.
    These are stored in temp and re-merged after blob changes.

    Args:
        sub_id: Subscription ID
        app_id: Application ID
        sub_blob: Serialized subscription blob data
        app_blob: Serialized application blob data
        server_id: Optional server identifier for tracking
    """
    try:
        os.makedirs(EPHEMERAL_BLOB_DIR, exist_ok=True)

        if server_id:
            filename = f"ephemeral_{server_id}_{sub_id}_{app_id}.bin"
        else:
            filename = f"ephemeral_{sub_id}_{app_id}.bin"

        filepath = os.path.join(EPHEMERAL_BLOB_DIR, filename)

        # Pack: sub_id (4) + app_id (4) + sub_len (4) + app_len (4) + sub_blob + app_blob
        data = struct.pack('<IIII', sub_id, app_id, len(sub_blob), len(app_blob))
        data += sub_blob + app_blob

        with open(filepath, 'wb') as f:
            f.write(data)

        log.debug(f"Saved ephemeral blob for sub:{sub_id} app:{app_id}")

    except Exception as e:
        log.error(f"Failed to save ephemeral blob sub:{sub_id} app:{app_id}: {e}")


def remove_ephemeral_blob(sub_id, app_id, server_id=None):
    """
    Remove an ephemeral blob file.

    Args:
        sub_id: Subscription ID
        app_id: Application ID
        server_id: Optional server identifier
    """
    try:
        if server_id:
            filename = f"ephemeral_{server_id}_{sub_id}_{app_id}.bin"
        else:
            filename = f"ephemeral_{sub_id}_{app_id}.bin"

        filepath = os.path.join(EPHEMERAL_BLOB_DIR, filename)
        if os.path.isfile(filepath):
            os.remove(filepath)
            log.debug(f"Removed ephemeral blob for sub:{sub_id} app:{app_id}")

    except Exception as e:
        log.warning(f"Failed to remove ephemeral blob sub:{sub_id} app:{app_id}: {e}")


def cleanup_all_ephemeral_blobs():
    """
    Remove all ephemeral blob files.
    Call this on server shutdown or cold-start to clean up stale blobs.
    """
    if not os.path.isdir(EPHEMERAL_BLOB_DIR):
        return

    removed_count = 0
    for filename in os.listdir(EPHEMERAL_BLOB_DIR):
        if filename.startswith("ephemeral_") and filename.endswith(".bin"):
            filepath = os.path.join(EPHEMERAL_BLOB_DIR, filename)
            try:
                os.remove(filepath)
                removed_count += 1
            except Exception as e:
                log.warning(f"Failed to remove ephemeral blob {filename}: {e}")

    if removed_count > 0:
        log.info(f"Cleaned up {removed_count} ephemeral blob(s)")


def _remerge_ephemeral_blobs():
    """
    Re-merge all saved ephemeral blobs into memory.
    Called after load_blobs_to_memory() when blob changes occur.
    Does NOT modify cache files - only updates memory.

    Must be called while holding CDR_BLOB_LOCK.
    """
    if not os.path.isdir(EPHEMERAL_BLOB_DIR):
        return

    merged_count = 0
    for filename in os.listdir(EPHEMERAL_BLOB_DIR):
        if filename.startswith("ephemeral_") and filename.endswith(".bin"):
            filepath = os.path.join(EPHEMERAL_BLOB_DIR, filename)
            try:
                with open(filepath, 'rb') as f:
                    data = f.read()

                if len(data) < 16:
                    log.warning(f"Ephemeral blob {filename} too small, skipping")
                    continue

                sub_id, app_id, sub_len, app_len = struct.unpack('<IIII', data[:16])
                sub_blob = data[16:16+sub_len]
                app_blob = data[16+sub_len:16+sub_len+app_len]

                # Merge into memory only (not cache files)
                _merge_ephemeral_into_dictionary(sub_id, app_id, sub_blob, app_blob)
                merged_count += 1

            except Exception as e:
                log.warning(f"Failed to re-merge ephemeral blob {filename}: {e}")

    if merged_count > 0:
        # Re-serialize blobs after all ephemeral merges
        _reserialize_memory_blobs()
        log.info(f"Re-merged {merged_count} ephemeral blob(s) into memory")


def _merge_ephemeral_into_dictionary(sub_id, app_id, sub_blob, app_blob):
    """
    Merge ephemeral blob data into CDR_DICTIONARY only.

    Args:
        sub_id: Subscription ID (integer)
        app_id: Application ID (integer)
        sub_blob: Serialized subscription data
        app_blob: Serialized application data

    Note: Must be called while holding CDR_BLOB_LOCK.
    """
    if globalvars.CDR_DICTIONARY is None:
        return

    sub_key = struct.pack('<I', sub_id)
    app_key = struct.pack('<I', app_id)

    APPS_KEY = b"\x01\x00\x00\x00"
    SUBS_KEY = b"\x02\x00\x00\x00"

    # Initialize keys if they don't exist
    if APPS_KEY not in globalvars.CDR_DICTIONARY:
        globalvars.CDR_DICTIONARY[APPS_KEY] = {}
    if SUBS_KEY not in globalvars.CDR_DICTIONARY:
        globalvars.CDR_DICTIONARY[SUBS_KEY] = {}

    # Add/update application and subscription
    globalvars.CDR_DICTIONARY[APPS_KEY][app_key] = app_blob
    globalvars.CDR_DICTIONARY[SUBS_KEY][sub_key] = sub_blob


def merge_ephemeral_into_memory(sub_id, app_id, sub_blob, app_blob):
    """
    Merge ephemeral blob data into memory blobs.
    Updates CDR_DICTIONARY and re-serializes CDR_BLOB_LAN/WAN.
    Does NOT write to cache files.

    Thread-safe.

    Args:
        sub_id: Subscription ID (integer)
        app_id: Application ID (integer)
        sub_blob: Serialized subscription data
        app_blob: Serialized application data
    """
    if globalvars.CDR_BLOB_LOCK is None:
        import threading
        globalvars.CDR_BLOB_LOCK = threading.RLock()

    with globalvars.CDR_BLOB_LOCK:
        _merge_ephemeral_into_dictionary(sub_id, app_id, sub_blob, app_blob)
        _reserialize_memory_blobs()


def remove_ephemeral_from_memory(sub_id, app_id):
    """
    Remove ephemeral blob data from memory blobs.
    Updates CDR_DICTIONARY and re-serializes CDR_BLOB_LAN/WAN.

    Thread-safe.

    Args:
        sub_id: Subscription ID (integer)
        app_id: Application ID (integer)
    """
    if globalvars.CDR_BLOB_LOCK is None:
        import threading
        globalvars.CDR_BLOB_LOCK = threading.RLock()

    with globalvars.CDR_BLOB_LOCK:
        if globalvars.CDR_DICTIONARY is None:
            return

        sub_key = struct.pack('<I', sub_id)
        app_key = struct.pack('<I', app_id)

        APPS_KEY = b"\x01\x00\x00\x00"
        SUBS_KEY = b"\x02\x00\x00\x00"

        # Remove application and subscription
        if APPS_KEY in globalvars.CDR_DICTIONARY:
            globalvars.CDR_DICTIONARY[APPS_KEY].pop(app_key, None)
        if SUBS_KEY in globalvars.CDR_DICTIONARY:
            globalvars.CDR_DICTIONARY[SUBS_KEY].pop(sub_key, None)

        # Re-serialize memory blobs
        _reserialize_memory_blobs()


# ============================================================================
# Original CDR Functions (modified for memory caching)
# ============================================================================

def read_blob(islan, is2003=False):
    """
    Read blob from memory if available, otherwise fall back to disk.
    Thread-safe.

    Args:
        islan: True for LAN blob, False for WAN blob
        is2003: True for 2003-era blob format

    Returns:
        bytes: The serialized/compressed blob data
    """
    # Initialize lock if needed
    if globalvars.CDR_BLOB_LOCK is None:
        import threading
        globalvars.CDR_BLOB_LOCK = threading.RLock()

    # Try to get from memory first (thread-safe read)
    with globalvars.CDR_BLOB_LOCK:
        if is2003:
            if islan and globalvars.CDR_BLOB_LAN_2003 is not None:
                return globalvars.CDR_BLOB_LAN_2003
            elif not islan and globalvars.CDR_BLOB_WAN_2003 is not None:
                return globalvars.CDR_BLOB_WAN_2003
        else:
            if islan and globalvars.CDR_BLOB_LAN is not None:
                return globalvars.CDR_BLOB_LAN
            elif not islan and globalvars.CDR_BLOB_WAN is not None:
                return globalvars.CDR_BLOB_WAN

    # Fallback to disk read (shouldn't happen in normal operation after initialization)
    log.debug("Reading blob from disk - memory cache miss")

    if islan and is2003:
        with open(os.path.join(CACHE_DIR, "secondblob_lan_2003.bin"), "rb") as f:
            blob = f.read()
    elif is2003:
        with open(os.path.join(CACHE_DIR, "secondblob_wan_2003.bin"), "rb") as f:
            blob = f.read()
    elif islan:
        with open(os.path.join(CACHE_DIR, "secondblob_lan.bin"), "rb") as f:
            blob = f.read()
    else:
        with open(os.path.join(CACHE_DIR, "secondblob_wan.bin"), "rb") as f:
            blob = f.read()
    return blob

def cache_cdr(islan, isAppApproval_merge = False):
    neuter_type = "LAN" if islan else "WAN"
    time.sleep(1)
    date_separator = ["-", "/", "_", "."]
    time_separator = [":", "_"]
    new_date = False
    new_time = False
    with open("emulator.ini", 'r') as f:
        mainini = f.readlines()
    for line in mainini:
        if line.startswith("steam_date="):
            new_date = line[11:21]
        if line.startswith("steam_time="):
            new_time = line[11:19]
    try:
        log.info(f"Creating {neuter_type} cached blob from ContentDescriptionDB...")
        for separator in date_separator:
            if separator in new_date:
                datetime.strptime(new_date, f"%Y{separator}%m{separator}%d")
                steam_date = new_date.replace(separator, "-")
        for separator in time_separator:
            if separator in new_time:
                datetime.strptime(new_time, f"%H{separator}%M{separator}%S")
                steam_time = new_time.replace(separator, "_")
        timestamp = steam_date + " " + steam_time
        local_tz = get_localzone()

        # ======== TIMEZONE CONVERSION ========
        # Parse the timestamp as UTC
        db_dt = datetime.strptime(timestamp, "%Y-%m-%d %H_%M_%S").replace(tzinfo = timezone.utc)

        # No conversion to local time is needed
        # Remove the timezone info if your database expects naive datetime in UTC
        # db_dt = db_dt.replace(tzinfo=None)

        # Format the timestamp for SQL query
        timestamp = db_dt.strftime('%Y-%m-%d %H_%M_%S')
        # =====================================

        if timestamp < "2002-02-25 07_42_30":
            timestamp = "2002-02-25 07_42_30"

        if timestamp < "2003-09-09 18_50_46":
            cddb = "BetaContentDescriptionDB"
        else:
            cddb = "ContentDescriptionDB"

        conn2 = mariadb.connect(
            user=config["database_username"],
            password=config["database_password"],
            host=config["database_host"],
            port=int(config["database_port"]),
            database=cddb
        )

        # OPTIMIZATION: construct_blob_from_cddb now returns dict directly
        blob_dict = construct_blob_from_cddb(config["database_host"], config["database_port"], config["database_username"], config["database_password"], cddb, timestamp, CACHE_DIR)
    except Exception as e:
        log.warn("Cached blob creation from ContentDescriptionDB failed")
        log.debug(f"DB error: {str(e)}")
        log.info(f"Converting binary {neuter_type} CDDB blob file to cache...")

        blob_dict = None

        if os.path.isfile("files/2ndcdr.py") or os.path.isfile("files/secondblob.py"):
            if os.path.isfile("files/2ndcdr.orig"):
                os.remove("files/2ndcdr.py")
                shutil.copy2("files/2ndcdr.orig", "files/secondblob.py")
                os.remove("files/2ndcdr.orig")
            if os.path.isfile("files/2ndcdr.py"):
                shutil.copy2("files/2ndcdr.py", "files/secondblob.py")
                os.remove("files/2ndcdr.py")
            # OPTIMIZATION: Load .py file directly with ast.literal_eval instead of exec
            with open("files/secondblob.py", "r") as g:
                file_content = g.read()
            # Parse "blob = {...}" format
            if file_content.strip().startswith("blob"):
                # Find the dict part after "blob = "
                eq_pos = file_content.find("=")
                if eq_pos != -1:
                    dict_str = file_content[eq_pos + 1:].strip()
                    blob_dict = ast.literal_eval(dict_str)
        else:
            if os.path.isfile("files/secondblob.orig"):
                os.remove("files/secondblob.bin")
                shutil.copy2("files/secondblob.orig", "files/secondblob.bin")
                os.remove("files/secondblob.orig")
            if not os.path.isfile("files/secondblob.bin"):
                # Try to use cached blob as fallback before waiting
                cached_blob_path = os.path.join(CACHE_DIR, "secondblob_lan.bin")
                if os.path.isfile(cached_blob_path):
                    log.info("files/secondblob.bin not found, using cached blob as fallback")
                    with open(cached_blob_path, "rb") as g:
                        blob = g.read()
                    try:
                        if blob[0:2] == b"\x01\x43":
                            blob = zlib.decompress(blob[20:])
                        blob_dict = blobs.blob_unserialize(blob)
                    except Exception as e:
                        log.error(f"Failed to unserialize cached blob: {e}")
                        blob_dict = None
                else:
                    log.warn("secondblob not found and no cached blob available, waiting for file...")
                    while True:
                        time.sleep(1)
                        if os.path.isfile("files/secondblob.bin"):
                            break
                    with open("files/secondblob.bin", "rb") as g:
                        blob = g.read()
                    try:
                        if blob[0:2] == b"\x01\x43":
                            blob = zlib.decompress(blob[20:])
                        blob_dict = blobs.blob_unserialize(blob)
                    except Exception as e:
                        log.error(f"Failed to unserialize blob: {e}")
            else:
                with open("files/secondblob.bin", "rb") as g:
                    blob = g.read()
                try:
                    # OPTIMIZATION: Use blob_unserialize directly, no string conversion
                    if blob[0:2] == b"\x01\x43":
                        blob = zlib.decompress(blob[20:])
                    blob_dict = blobs.blob_unserialize(blob)
                except Exception as e:
                    log.error(f"Failed to unserialize blob: {e}")

    # OPTIMIZATION: Use blob_replace_dict_optimized for maximum performance
    # This uses iterative traversal and pattern pre-filtering for 2-3x speedup
    blobs.blob_replace_dict_optimized(blob_dict, globalvars.replace_string_cdr(islan))

    # Apply all blob modifications using centralized function
    # Order: integrate_customs_files -> remove_de_restrictions -> neuter_unlock_times -> disable_steam3_purchasing
    blob_dict = apply_blob_modifications(blob_dict, islan)

    # Serialize, replace RSA signatures, and compress using centralized function
    blob = serialize_and_compress_blob(blob_dict)

    if isAppApproval_merge:
        if islan:
            with open(os.path.join(CACHE_DIR, "secondblob_lan.bin"), "wb") as f:
                f.write(blob)
        else:
            with open(os.path.join(CACHE_DIR, "secondblob_wan.bin"), "wb") as f:
                f.write(blob)
    else:
        if islan:
            with open(os.path.join(CACHE_DIR, "secondblob_lan.bin.temp"), "wb") as f:
                f.write(blob)
            #with open(os.path.join(CACHE_DIR, "secondblob_lan_2003.bin"), "wb") as f:
            #    f.write(blob_2003)
        else:
            with open(os.path.join(CACHE_DIR, "secondblob_wan.bin.temp"), "wb") as f:
                f.write(blob)
            #with open(os.path.join(CACHE_DIR, "secondblob_wan_2003.bin"), "wb") as f:
            #    f.write(blob_2003)
    log.info(f"CDDB neutering for {neuter_type} complete")

    return blob_dict


def cache_cdr_unified(isAppApproval_merge=False):
    """
    OPTIMIZED: Build CDR blob ONCE and create both LAN and WAN variants.

    This function provides significant performance improvement over calling
    cache_cdr(True) and cache_cdr(False) separately because:
    1. Database queries are executed ONCE instead of twice
    2. Base blob processing (restrictions removal, unlock times) is done ONCE
    3. Only the final neutering replacements differ between LAN/WAN
    4. Serialization and compression can be parallelized

    Args:
        isAppApproval_merge: If True, writes to .bin files directly (for app approval merges)
                            If False, writes to .temp files (normal neutering)

    Returns:
        tuple: (lan_blob_dict, wan_blob_dict)
    """
    import sys
    from concurrent.futures import ThreadPoolExecutor

    # Check for shutdown before doing expensive work - prevents "cannot schedule
    # new futures after interpreter shutdown" error when watchdog thread is still
    # running during program restart/shutdown
    shutdown_req = getattr(globalvars, 'shutdown_requested', False)
    is_finalizing = sys.is_finalizing()
    log.debug(f"cache_cdr_unified called: shutdown_requested={shutdown_req}, is_finalizing={is_finalizing}")
    if shutdown_req or is_finalizing:
        log.warning("Shutdown in progress, skipping CDR caching")
        return None, None

    # Clear replacement string caches to ensure fresh LAN/WAN IPs are used
    globalvars.clear_replacement_cache()

    # Debug: Show config IP values
    log.debug(f"Config IPs - server_ip: {globalvars.config['server_ip']}, public_ip: {globalvars.config['public_ip']}, http_ip: {globalvars.config['http_ip']}, http_domainname: {globalvars.config['http_domainname']}")

    log.info("Creating unified cached blob from ContentDescriptionDB (LAN + WAN)...")
    start_time = time.time()

    # === STEP 1: Parse timestamp (done ONCE) ===
    date_separator = ["-", "/", "_", "."]
    time_separator = [":", "_"]
    new_date = False
    new_time = False

    with open("emulator.ini", 'r') as f:
        mainini = f.readlines()
    for line in mainini:
        if line.startswith("steam_date="):
            new_date = line[11:21]
        if line.startswith("steam_time="):
            new_time = line[11:19]

    log.debug(f"Parsed date/time from ini: new_date={new_date}, new_time={new_time}")

    blob_dict = None
    try:
        for separator in date_separator:
            if separator in new_date:
                datetime.strptime(new_date, f"%Y{separator}%m{separator}%d")
                steam_date = new_date.replace(separator, "-")
        for separator in time_separator:
            if separator in new_time:
                datetime.strptime(new_time, f"%H{separator}%M{separator}%S")
                steam_time = new_time.replace(separator, "_")
        timestamp = steam_date + " " + steam_time

        # Timezone conversion
        from tzlocal import get_localzone
        db_dt = datetime.strptime(timestamp, "%Y-%m-%d %H_%M_%S").replace(tzinfo=timezone.utc)
        timestamp = db_dt.strftime('%Y-%m-%d %H_%M_%S')

        if timestamp < "2002-02-25 07_42_30":
            timestamp = "2002-02-25 07_42_30"

        if timestamp < "2003-09-09 18_50_46":
            cddb = "BetaContentDescriptionDB"
        else:
            cddb = "ContentDescriptionDB"

        # === STEP 2: Build base blob from database (done ONCE) ===
        log.info(f"Building base blob from database {cddb} at timestamp {timestamp}...")
        db_start = time.time()
        blob_dict = construct_blob_from_cddb(
            config["database_host"],
            config["database_port"],
            config["database_username"],
            config["database_password"],
            cddb,
            timestamp,
            CACHE_DIR
        )
        log.debug(f"Database blob construction took {time.time() - db_start:.2f}s")

    except Exception as e:
        log.warn("Cached blob creation from ContentDescriptionDB failed")
        log.debug(f"DB error: {str(e)}")
        log.info("Converting binary CDDB blob file to cache...")

        # Fallback to file-based blob loading
        if os.path.isfile("files/2ndcdr.py") or os.path.isfile("files/secondblob.py"):
            if os.path.isfile("files/2ndcdr.orig"):
                os.remove("files/2ndcdr.py")
                shutil.copy2("files/2ndcdr.orig", "files/secondblob.py")
                os.remove("files/2ndcdr.orig")
            if os.path.isfile("files/2ndcdr.py"):
                shutil.copy2("files/2ndcdr.py", "files/secondblob.py")
                os.remove("files/2ndcdr.py")

            with open("files/secondblob.py", "r") as g:
                file_content = g.read()
            if file_content.strip().startswith("blob"):
                eq_pos = file_content.find("=")
                if eq_pos != -1:
                    dict_str = file_content[eq_pos + 1:].strip()
                    blob_dict = ast.literal_eval(dict_str)
        else:
            if os.path.isfile("files/secondblob.orig"):
                os.remove("files/secondblob.bin")
                shutil.copy2("files/secondblob.orig", "files/secondblob.bin")
                os.remove("files/secondblob.orig")
            if not os.path.isfile("files/secondblob.bin"):
                # Try to use cached blob as fallback before waiting
                cached_blob_path = os.path.join(CACHE_DIR, "secondblob_lan.bin")
                if os.path.isfile(cached_blob_path):
                    log.info("files/secondblob.bin not found, using cached blob as fallback")
                    with open(cached_blob_path, "rb") as g:
                        blob = g.read()
                    try:
                        if blob[0:2] == b"\x01\x43":
                            blob = zlib.decompress(blob[20:])
                        blob_dict = blobs.blob_unserialize(blob)
                    except Exception as e:
                        log.error(f"Failed to unserialize cached blob: {e}")
                        return None, None
                else:
                    log.warn("secondblob not found and no cached blob available, waiting for file...")
                    while True:
                        time.sleep(1)
                        if os.path.isfile("files/secondblob.bin"):
                            break
                    with open("files/secondblob.bin", "rb") as g:
                        blob = g.read()
                    try:
                        if blob[0:2] == b"\x01\x43":
                            blob = zlib.decompress(blob[20:])
                        blob_dict = blobs.blob_unserialize(blob)
                    except Exception as e:
                        log.error(f"Failed to unserialize blob: {e}")
                        return None, None
            else:
                with open("files/secondblob.bin", "rb") as g:
                    blob = g.read()
                try:
                    if blob[0:2] == b"\x01\x43":
                        blob = zlib.decompress(blob[20:])
                    blob_dict = blobs.blob_unserialize(blob)
                except Exception as e:
                    log.error(f"Failed to unserialize blob: {e}")
                    return None, None

    if blob_dict is None:
        log.error("Failed to build base blob")
        return None, None

    log.debug(f"Base blob built successfully, proceeding with LAN/WAN creation")

    # === STEP 3: Create LAN and WAN variants via deep copy ===
    # NOTE: Deep copy happens BEFORE modifications so custom files can be processed correctly
    log.debug("Creating LAN/WAN variants...")
    copy_start = time.time()

    lan_blob_dict = copy.deepcopy(blob_dict)
    wan_blob_dict = copy.deepcopy(blob_dict)

    log.debug(f"Deep copy took {time.time() - copy_start:.2f}s")

    # === STEP 4: Apply LAN/WAN specific URL replacements ===
    neuter_start = time.time()

    # Apply CDR replacements (different URLs for LAN vs WAN)
    # OPTIMIZATION: Single traversal for both LAN and WAN replacements
    lan_ip = globalvars.get_octal_ip(islan=True)
    wan_ip = globalvars.get_octal_ip(islan=False)
    log.info(f"Neutering with LAN IP: {lan_ip}, WAN IP: {wan_ip}")

    if lan_ip == wan_ip:
        log.error(f"LAN and WAN IPs are identical ({lan_ip})! Check server_ip vs public_ip in config.")

    lan_replacements = globalvars.replace_string_cdr(islan=True)
    wan_replacements = globalvars.replace_string_cdr(islan=False)

    # Verify replacement tuples are different
    if lan_replacements and wan_replacements:
        lan_first_replace = lan_replacements[0][1]  # First replacement value
        wan_first_replace = wan_replacements[0][1]
        log.info(f"LAN replacement target: {lan_first_replace[:60]}")
        log.info(f"WAN replacement target: {wan_first_replace[:60]}")
        if lan_first_replace == wan_first_replace:
            log.error("LAN and WAN replacement values are IDENTICAL - IPs must be different in config!")

    # Use dual replacement - traverses blob structure ONCE instead of twice
    blobs.blob_replace_dual_optimized(lan_blob_dict, wan_blob_dict, lan_replacements, wan_replacements)

    log.debug(f"CDR replacements took {time.time() - neuter_start:.2f}s")

    # === STEP 5: Apply all modifications using centralized function ===
    # Order: integrate_customs_files -> remove_de_restrictions -> neuter_unlock_times -> disable_steam3_purchasing
    # This ensures custom files also get their restrictions removed
    log.debug("Applying blob modifications (including custom files)...")
    mod_start = time.time()

    lan_blob_dict = apply_blob_modifications(lan_blob_dict, islan=True)
    wan_blob_dict = apply_blob_modifications(wan_blob_dict, islan=False)

    log.debug(f"Blob modifications took {time.time() - mod_start:.2f}s")

    # === STEP 6: Serialize and compress both variants (parallelized) ===
    serialize_start = time.time()

    # Re-check for shutdown before creating ThreadPoolExecutor - this is the critical
    # point where "cannot schedule new futures after interpreter shutdown" occurs
    if getattr(globalvars, 'shutdown_requested', False) or sys.is_finalizing():
        log.warning("Shutdown detected before serialization, aborting CDR caching")
        return None, None

    # Process both variants in parallel using ThreadPoolExecutor
    # Wrap in try/except to handle race condition where interpreter starts
    # finalizing between the check above and the executor.submit call
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            lan_future = executor.submit(serialize_and_compress_blob, lan_blob_dict)
            wan_future = executor.submit(serialize_and_compress_blob, wan_blob_dict)

            lan_blob_final = lan_future.result()
            wan_blob_final = wan_future.result()
    except RuntimeError as e:
        if "cannot schedule new futures after interpreter shutdown" in str(e):
            log.warning("Shutdown RuntimeError caught, aborting CDR caching")
            return None, None
        log.error(f"RuntimeError in ThreadPoolExecutor: {e}")
        raise

    log.debug(f"Serialization and compression completed in {time.time() - serialize_start:.2f}s")

    # === STEP 7: Write both blobs to files ===
    write_start = time.time()

    if isAppApproval_merge:
        lan_path = os.path.join(CACHE_DIR, "secondblob_lan.bin")
        wan_path = os.path.join(CACHE_DIR, "secondblob_wan.bin")
    else:
        lan_path = os.path.join(CACHE_DIR, "secondblob_lan.bin.temp")
        wan_path = os.path.join(CACHE_DIR, "secondblob_wan.bin.temp")

    with open(lan_path, "wb") as f:
        f.write(lan_blob_final)
    with open(wan_path, "wb") as f:
        f.write(wan_blob_final)

    log.debug(f"File writing took {time.time() - write_start:.2f}s")

    total_time = time.time() - start_time
    log.info(f"Unified CDDB neutering complete (LAN + WAN) in {total_time:.2f}s")
    log.debug(f"cache_cdr_unified returning successfully with blobs")

    return lan_blob_dict, wan_blob_dict


def update_blob_date():
    blob = read_secondblob(os.path.join(CACHE_DIR, "secondblob_lan.bin"))
    globalvars.CDDB_datetime = steamtime_to_datetime(blob[b"\x03\x00\x00\x00"])


def optimized_blob_serialize(blobdict):
    """
    Optimized blob serialization using cached struct.pack values and efficient
    bytearray operations.

    PHASE 3 OPTIMIZATION: Uses pre-cached struct.pack values for common sizes
    and efficient list joining.
    """
    # Pre-cache common header packs for this serialization
    # Most names are 4 bytes (like b'\x01\x00\x00\x00')
    header_cache = {}

    def get_header(namesize, datasize):
        key = (namesize, datasize)
        if key not in header_cache:
            header_cache[key] = struct.pack("<HL", namesize, datasize)
        return header_cache[key]

    def serialize_dict(d):
        """Serialize a dict into a complete blob with header (b'\x01\x50' + size + data + slack)."""
        subtext_list = []

        for name, data in d.items():
            if name == b"__slack__":
                continue

            # Ensure name is a bytes object
            name_bytes = name if isinstance(name, bytes) else name.encode('ascii')

            if isinstance(data, dict):
                # Recursively serialize nested dict - this returns a COMPLETE blob with header
                data = serialize_dict(data)
            elif isinstance(data, str):
                data = data.encode('ascii')

            namesize = len(name_bytes)
            datasize = len(data)

            # Use cached header pack
            header = get_header(namesize, datasize)
            subtext_list.append(header)
            subtext_list.append(name_bytes)
            subtext_list.append(data)

        blobtext = b''.join(subtext_list)

        # Get slack for this dict level
        slack = d.get(b"__slack__", b"")

        # Wrap with blob header: b'\x01\x50' + totalsize + slacksize + content + slack
        totalsize = len(blobtext) + 10
        sizetext = struct.pack("<LL", totalsize, len(slack))
        return b'\x01\x50' + sizetext + blobtext + slack

    return serialize_dict(blobdict)


def remove_de_restrictions(execdict):
    for sub_id_main in execdict["blob"][b"\x02\x00\x00\x00"]:

        if b"\x17\x00\x00\x00" in execdict["blob"][b"\x02\x00\x00\x00"][sub_id_main]:
            sub_key = execdict["blob"][b"\x02\x00\x00\x00"][sub_id_main][b"\x17\x00\x00\x00"]
            # print(sub_key)
            if b"AllowPurchaseFromRestrictedCountries" in sub_key:
                sub_key.pop(b"AllowPurchaseFromRestrictedCountries")  # print(sub_key)
            if b"PurchaseRestrictedCountries" in sub_key:
                sub_key.pop(b"PurchaseRestrictedCountries")  # print(sub_key)
            if b"RestrictedCountries" in sub_key:
                sub_key.pop(b"RestrictedCountries")  # print(sub_key)
            if b"OnlyAllowRestrictedCountries" in sub_key:
                sub_key.pop(b"OnlyAllowRestrictedCountries")  # print(sub_key)
            if b"onlyallowrunincountries" in sub_key:
                sub_key.pop(b"onlyallowrunincountries")
                # print(sub_key)
            if len(sub_key) == 0:
                execdict["blob"][b"\x02\x00\x00\x00"][sub_id_main].pop(b"\x17\x00\x00\x00")
    try:
        for sig in execdict["blob"][b"\x05\x00\x00\x00"]:  # replaces the old signature search, completes in less than 1 second now
            value = execdict["blob"][b"\x05\x00\x00\x00"][sig]
            # print(value)
            if len(value) == 160 and value.startswith(binascii.a2b_hex("30819d300d06092a")):
                execdict["blob"][b"\x05\x00\x00\x00"][sig] = encryption.BERstring
    except:
        pass


def neuter_unlock_times(execdict):
    if config["alter_preload_unlocks"].lower() == "true":
        log.info("Altering preload unlock dates")
        for app in execdict["blob"][b'\x01\x00\x00\x00']:
            if b'\x0e\x00\x00\x00' in execdict["blob"][b'\x01\x00\x00\x00'][app]:
                for info in execdict["blob"][b'\x01\x00\x00\x00'][app][b'\x0e\x00\x00\x00']:
                    if info == 'PreloadCountdownTextTime':
                        if b'days' in execdict["blob"][b'\x01\x00\x00\x00'][app][b'\x0e\x00\x00\x00'][info]:
                            preload_count = int(execdict["blob"][b'\x01\x00\x00\x00'][app][b'\x0e\x00\x00\x00'][info].decode()[:-6])
                    else:
                        preload_count = 5
                    if info == 'PreloadUnlockTime':
                        unlock_time = execdict["blob"][b'\x01\x00\x00\x00'][app][b'\x0e\x00\x00\x00'][info].decode()[:-1]
                        if ":" in unlock_time:
                            current_datetime = datetime.now()
                            new_datetime = current_datetime + timedelta(days=preload_count)
                            new_datetime = new_datetime.strftime("%Y:%m:%d:%H:%M").replace(":0", ":")
                        else:
                            current_datetime = int(datetime.now().timestamp())
                            new_datetime = current_datetime + (((preload_count * 24) * 60) * 60)
                        execdict["blob"][b'\x01\x00\x00\x00'][app][b'\x0e\x00\x00\x00'][info] = str(new_datetime).encode() + b'\x00'


def remove_keys_recursively(data_dict, target_keys):
    """Recursively remove specified keys from all levels of nested dictionaries."""
    keys_list = list(data_dict.keys())  # Get list of keys to avoid runtime modification issues
    for key in keys_list:
        if key in target_keys:
            # If key needs to be removed, it is removed here
            log.debug(f"Removing key: {key}")  # Debug print statement
            data_dict.pop(key, None)
        elif isinstance(data_dict[key], dict):
            # If the value is another dictionary, recurse into it
            #print(f"Descending into dictionary at key: {key}")  # Debug print statement
            remove_keys_recursively(data_dict[key], target_keys)
            # After recursion, check if the subdictionary is empty and remove if so


def disable_steam3_purchasing(execdict):
    """Disables Steam3 purchasing until the CM supports it. Some users may just want to use Steam2 anyway."""
    log.info("Disabling Steam3 Purchasing")

    for sub in execdict["blob"][b'\x02\x00\x00\x00']:
        if b'\x16\x00\x00\x00' in execdict["blob"][b'\x02\x00\x00\x00'][sub]:
            execdict["blob"][b'\x02\x00\x00\x00'][sub][b'\x16\x00\x00\x00'] = b'\x00'

    target_keys = [
            # b"convar_bClientAllowHardwarePromos",
            # b"convar_bClientAllowPurchaseWizard",
            b"convar_bClientAllowSteam3ActivationCodes",
            b"convar_bClientAllowSteam3CCPurchase",
            b"convar_bClientCCPurchaseFallbackToSteam2",
            b"convar_bClientMakeAllCCPurchasesSteam3"
    ]

    # Call the recursive function to remove keys
    remove_keys_recursively(execdict, target_keys)


# ============================================================================
# Centralized Blob Processing Functions
# ============================================================================
# These functions provide a single point of entry for common blob operations,
# ensuring consistent processing for both database and file-based blobs.

def replace_rsa_signatures(blob_bytes):
    """
    Replace Valve RSA signatures with emulator's BERstring in serialized blob bytes.

    This searches for the RSA signature pattern and replaces all occurrences
    with the emulator's encryption key.

    Args:
        blob_bytes: Serialized blob bytes (not compressed)

    Returns:
        bytes: Blob bytes with RSA signatures replaced
    """
    blob_bytes = bytearray(blob_bytes)
    search_pattern = b"\x30\x81\x9d\x30\x0d\x06\x09\x2a"
    replacement = encryption.BERstring
    pattern_length = 160

    start = 0
    while True:
        index = blob_bytes.find(search_pattern, start)
        if index == -1:
            break
        blob_bytes[index:index + pattern_length] = replacement
        start = index + pattern_length

    return bytes(blob_bytes)


def serialize_and_compress_blob(blob_dict):
    """
    Serialize blob dict, replace RSA signatures, compress, and add header.

    This provides a single function for the common serialize → replace → compress
    workflow that was previously duplicated in multiple places.

    Args:
        blob_dict: The blob dictionary to serialize

    Returns:
        bytes: Compressed blob with header (ready to write to file)
    """
    # Serialize the blob
    blob_bytes = optimized_blob_serialize(blob_dict)

    # Decompress if already compressed (shouldn't happen, but handle it)
    if blob_bytes.startswith(b"\x01\x43"):
        blob_bytes = zlib.decompress(blob_bytes[20:])

    # Replace RSA signatures
    blob_bytes = replace_rsa_signatures(blob_bytes)

    # Compress and add header
    compressed = zlib.compress(blob_bytes, 9)
    return b"\x01\x43" + struct.pack("<QQH", len(compressed) + 20, len(blob_bytes), 9) + compressed


def apply_blob_modifications(blob_dict, islan=True):
    """
    Apply all common blob modifications in the correct order.

    This centralizes the blob modification workflow to ensure consistent
    processing for both database and file-based blobs. The order is:
    1. Integrate custom files (mod_blob) - so custom content gets processed
    2. Remove DE/country restrictions - applies to base blob AND custom content
    3. Neuter unlock times (if configured)
    4. Disable Steam3 purchasing (if configured)

    Args:
        blob_dict: The blob dictionary to modify (modified in-place)
        islan: True for LAN blob, False for WAN blob

    Returns:
        dict: The modified blob dictionary (same object, modified in-place)
    """
    # Create execdict wrapper for compatibility with existing functions
    execdict = {"blob": blob_dict}

    # 1. Integrate custom files FIRST - so restrictions can be removed from them too
    integrate_customs_files(execdict, islan)

    # 2. Remove DE/country restrictions (applies to base blob AND custom content)
    remove_de_restrictions(execdict)

    # 3. Neuter unlock times (if configured)
    neuter_unlock_times(execdict)

    # 4. Disable Steam3 purchasing (if configured)
    if globalvars.config['disable_steam3_purchasing'].lower() == 'true':
        disable_steam3_purchasing(execdict)

    return execdict["blob"]


def update_subscription_id_in_xml(xml_file_path, old_id, new_id):
    if not os.path.exists(xml_file_path):
        log.warning(f"XML file '{xml_file_path}' not found.")
        return

    try:
        tree = ET.parse(xml_file_path)
        root = tree.getroot()
        old_id_str = str(old_id)
        new_id_str = str(new_id)

        # Replace <SubscriptionRecord SubscriptionId="{old_id_str}">
        for elem in root.iter('SubscriptionRecord'):
            if elem.get('SubscriptionId') == old_id_str:
                elem.set('SubscriptionId', new_id_str)

        # Replace <SubscriptionId>{old_id_str}</SubscriptionId>
        for elem in root.iter('SubscriptionId'):
            if elem.text == old_id_str:
                elem.text = new_id_str

        # Write the updated XML back to file
        tree.write(xml_file_path, encoding='utf-8', xml_declaration=True)
        log.info(f"Updated XML file '{xml_file_path}' with new subscription ID.")
    except ET.ParseError as e:
        log.warning(f"Error parsing XML file: {e}")


def integrate_customs_files(execdict, islan):
    execdict_temp_01 = {}
    execdict_temp_02 = {}
    # Skip mod_blob integration for blob version 1 and earlier

    # Only blob version 2+ have compatible data structures
    if globalvars.record_ver < 2:
        log.debug(f"Skipping mod_blob integration for blob version {globalvars.record_ver} (requires version 2+)")
        return

    for file in os.walk("files/mod_blob"):
        for customblobfile in file[2]:
            if (
                customblobfile.endswith((".py", ".bin", ".xml"))
                and customblobfile not in ["2ndcdr.py", "1stcdr.py"]
                and not customblobfile.startswith(("firstblob", "secondblob"))
            ):
                log.info("Found extra blob: " + customblobfile)
                execdict_update = {}

                if customblobfile.endswith(".bin"):
                    with open("files/mod_blob/" + customblobfile, "rb") as f:
                        blob = f.read()

                    if blob[0:2] == b"\x01\x43":
                        blob = zlib.decompress(blob[20:])
                    # OPTIMIZATION: Use blob_unserialize directly, then blob_replace_dict_optimized
                    execdict_update = blobs.blob_unserialize(blob)

                    log.info("Integrating Custom Applications (bin)")
                    blobs.blob_replace_dict_optimized(execdict_update, globalvars.replace_string_cdr(islan))

                elif customblobfile.endswith(".py"):
                    with open("files/mod_blob/" + customblobfile, 'r') as m:
                        userblobstr_upd = m.read()
                    log.info("Integrating Custom Applications (py)")
                    # OPTIMIZATION: Parse first, then blob_replace_dict_optimized
                    # Find the dict part after "blob = "
                    eq_pos = userblobstr_upd.find("=")
                    if eq_pos != -1:
                        dict_str = userblobstr_upd[eq_pos + 1:].strip()
                        execdict_update = ast.literal_eval(dict_str)
                    else:
                        execdict_update = ast.literal_eval(userblobstr_upd[7:])
                    # Convert to bytes and then do replacements
                    execdict_update = utilities.blobs.convert_to_bytes_deep(execdict_update)
                    blobs.blob_replace_dict_optimized(execdict_update, globalvars.replace_string_cdr(islan))

                elif customblobfile.endswith(".xml"):
                    contentdescriptionrecord_file = ContentDescriptionRecord.from_xml_file("files/mod_blob/" + customblobfile)
                    execdict_update = contentdescriptionrecord_file.to_dict(True)
                    # XML files also need URL replacement
                    execdict_update = utilities.blobs.convert_to_bytes_deep(execdict_update)
                    blobs.blob_replace_dict_optimized(execdict_update, globalvars.replace_string_cdr(islan))
                else:
                    return  # Fail gracefully if an unknown file is encountered

                # Ensure bytes conversion for .bin files (already done for .py and .xml above)
                if customblobfile.endswith(".bin"):
                    execdict_update = utilities.blobs.convert_to_bytes_deep(execdict_update)

                # Keys to skip during merge (these are CDR metadata fields, not actual content)
                # VersionNumber and LastChangedExistingAppOrSubscriptionTime should not be overwritten
                SKIP_KEYS = {
                    b"\x00\x00\x00\x00",  # VersionNumber
                    b"\x03\x00\x00\x00",  # LastChangedExistingAppOrSubscriptionTime
                }

                # Integrate execdict_update into execdict["blob"]
                for k in execdict_update:
                    if k in SKIP_KEYS:
                        continue  # Skip metadata keys during merge

                    if k in execdict["blob"]:
                        # Existing key in execdict["blob"], need to handle duplicates
                        main_dict = execdict["blob"][k]

                        if k in [b"\x01\x00\x00\x00", b"\x02\x00\x00\x00"] and customblobfile.endswith(".xml"):  # Application or Subscription Records
                            # Get the set of existing keys as integers
                            main_keys_int = set(int.from_bytes(key, 'little') for key in main_dict.keys())
                            max_key = 30000  # Start from -1 if empty

                            # Prepare new entries to merge
                            new_entries = {}

                            for key, subdict in execdict_update[k].items():
                                if key in main_dict:
                                    # Key exists; generate a new unique key
                                    max_key += 1
                                    new_key_int = max_key
                                    new_key = new_key_int.to_bytes(4, 'little')
                                    # Get the subscription name from the subdictionary (b"\x02\x00\x00\x00")
                                    subscription_name = subdict.get(b"\x02\x00\x00\x00", b"").decode('latin-1').strip('\x00')

                                    # TODO Should probably do the same for applicationid's and update the publickey ids as well
                                    # Trigger message box to notify ID change, including subscription name
                                    old_key_int = int().from_bytes(key, 'little')
                                    new_key_int = int().from_bytes(new_key, 'little')
                                    if key != new_key:
                                        log.warning("=" * 60)
                                        log.warning(f"SUBSCRIPTION ID CHANGED: {old_key_int} -> {new_key_int}")
                                        log.warning(f"Subscription Name: {subscription_name}")
                                        log.warning("=" * 60)

                                        # Write to changelog file (overwrite on first write per session, append after)
                                        global _subscription_changelog_initialized
                                        changelog_path = "custom_subscription_id_changes.txt"
                                        file_mode = "a" if _subscription_changelog_initialized else "w"
                                        with open(changelog_path, file_mode, encoding="utf-8") as changelog:
                                            if not _subscription_changelog_initialized:
                                                changelog.write("Custom Subscription ID Changes Log\n")
                                                changelog.write("=" * 40 + "\n\n")
                                                _subscription_changelog_initialized = True
                                            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                            changelog.write(f"[{timestamp}] Subscription ID Change\n")
                                            changelog.write(f"  Old ID: {old_key_int}\n")
                                            changelog.write(f"  New ID: {new_key_int}\n")
                                            changelog.write(f"  Subscription Name: {subscription_name}\n")
                                            changelog.write(f"  Source File: {customblobfile}\n")
                                            changelog.write("-" * 40 + "\n")

                                    # Update the b"\x01\x00\x00\x00" key in the subdictionary
                                    subdict[b"\x01\x00\x00\x00"] = new_key

                                    # Add the subdictionary with the new key to new_entries
                                    new_entries[new_key] = subdict

                                    # **Update the XML file with the new subscription ID**
                                    update_subscription_id_in_xml("files/mod_blob/" + customblobfile, old_key_int, new_key_int)
                                else:
                                    # Key does not exist; add it directly
                                    new_entries[key] = subdict

                            # Merge new entries into the main dictionary
                            main_dict.update(new_entries)
                            execdict["blob"][k] = main_dict
                        else:
                            # For other keys, update directly
                            execdict["blob"][k].update(execdict_update[k])
                    else:
                        # Key does not exist in execdict["blob"], add it directly
                        execdict["blob"][k] = execdict_update[k]

    # Regenerate app-to-subscription index after all custom files are merged
    regenerate_app_to_subscription_index(execdict["blob"])


def merge_xml_into_cached_blobs(xml_path):
    """
    Merge an approved XML file directly into cached LAN and WAN blobs.

    This function reads the existing cached secondblob_lan.bin and secondblob_wan.bin,
    parses the XML file, merges the new application/subscription data, applies
    restriction removal, and saves the updated blobs back to cache.

    Note: This function is skipped for blob version 3 and earlier as the data
    structures may not be compatible. Only blob version 4+ supports this merging.

    Args:
        xml_path: Path to the XML file to merge (e.g., files/mod_blob/123.xml)

    Returns:
        tuple: (success: bool, message: str)
    """
    # Skip for blob version 1 and earlier - only version 2+ supported
    if globalvars.record_ver < 2:
        return False, f"Skipped: mod_blob merging not supported for blob version {globalvars.record_ver} (requires version 4+)"

    try:
        if not os.path.exists(xml_path):
            return False, f"XML file not found: {xml_path}"

        # Parse the XML file
        try:
            cdr_record = ContentDescriptionRecord.from_xml_file(xml_path)
            xml_data = cdr_record.to_dict(True)  # iscustom=True to skip VersionNumber etc.
            xml_data = utilities.blobs.convert_to_bytes_deep(xml_data)
        except Exception as e:
            return False, f"Failed to parse XML: {e}"

        # Process both LAN and WAN blobs
        results = []
        for islan in [True, False]:
            blob_type = "LAN" if islan else "WAN"
            blob_filename = "secondblob_lan.bin" if islan else "secondblob_wan.bin"
            blob_path = os.path.join(CACHE_DIR, blob_filename)
            temp_path = os.path.join(CACHE_DIR, f"{blob_filename}.temp")

            if not os.path.exists(blob_path):
                results.append(f"{blob_type}: cache file not found, skipping")
                continue

            try:
                # Read and decompress existing blob
                with open(blob_path, "rb") as f:
                    blob_data = f.read()

                if blob_data[0:2] == b"\x01\x43":
                    blob_data = zlib.decompress(blob_data[20:])

                blob_dict = blobs.blob_unserialize(blob_data)

                # Merge XML data into blob
                _merge_cdr_data(blob_dict, xml_data)

                # Ensure all version records have DepotEncryptionKey
                _ensure_version_records_have_depot_encryption_key(blob_dict)

                # Regenerate app-to-subscription index after merge
                regenerate_app_to_subscription_index(blob_dict)

                # Replace encryption keys for any new apps
                _replace_encryption_keys(blob_dict)

                # Apply restriction removal to the merged blob (including new content)
                execdict = {"blob": blob_dict}
                remove_de_restrictions(execdict)
                blob_dict = execdict["blob"]

                # Serialize, replace RSA signatures, and compress using centralized function
                final_blob = serialize_and_compress_blob(blob_dict)

                # Write to temp file first, then rename (atomic operation)
                with open(temp_path, "wb") as f:
                    f.write(final_blob)

                # Rename temp to final (atomic on most filesystems)
                if os.path.exists(blob_path):
                    os.remove(blob_path)
                os.rename(temp_path, blob_path)

                results.append(f"{blob_type}: merged successfully")
                log.info(f"Merged XML {xml_path} into {blob_filename}")

            except Exception as e:
                results.append(f"{blob_type}: failed - {e}")
                log.error(f"Failed to merge XML into {blob_filename}: {e}")
                # Clean up temp file if it exists
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except:
                        pass

        success = all("successfully" in r for r in results)
        return success, "; ".join(results)

    except Exception as e:
        log.error(f"Error in merge_xml_into_cached_blobs: {e}")
        return False, str(e)


def merge_custom_blob_into_cache(file_path, islan):
    """
    Merge a custom blob file (.xml, .py, or .bin) directly into cached blob.

    This applies restriction removal to ensure any DE/country restrictions in the
    merged content are removed. It does NOT trigger neuter_unlock_times.

    Args:
        file_path: Path to the custom blob file
        islan: True for LAN blob, False for WAN blob

    Returns:
        tuple: (success: bool, message: str)
    """
    import ast
    import pprint

    try:
        if not os.path.exists(file_path):
            return False, f"File not found: {file_path}"

        filename = os.path.basename(file_path)
        blob_type = "LAN" if islan else "WAN"
        blob_filename = "secondblob_lan.bin" if islan else "secondblob_wan.bin"
        blob_path = os.path.join(CACHE_DIR, blob_filename)
        temp_path = os.path.join(CACHE_DIR, f"{blob_filename}.temp")

        if not os.path.exists(blob_path):
            return False, f"{blob_type}: cache file not found"

        # Parse the custom file based on extension
        # OPTIMIZATION: Use dict-based blob_replace_dict_optimized instead of string-based blob_replace
        try:
            if file_path.endswith(".xml"):
                cdr_record = ContentDescriptionRecord.from_xml_file(file_path)
                custom_data = cdr_record.to_dict(True)
                custom_data = utilities.blobs.convert_to_bytes_deep(custom_data)
                blobs.blob_replace_dict_optimized(custom_data, globalvars.replace_string_cdr(islan))
            elif file_path.endswith(".py"):
                with open(file_path, 'r') as f:
                    content = f.read()
                # OPTIMIZATION: Parse first, then use blob_replace_dict_optimized
                eq_pos = content.find("=")
                if eq_pos != -1:
                    dict_str = content[eq_pos + 1:].strip()
                    custom_data = ast.literal_eval(dict_str)
                else:
                    custom_data = ast.literal_eval(content[7:])  # Skip "blob = "
                custom_data = utilities.blobs.convert_to_bytes_deep(custom_data)
                blobs.blob_replace_dict_optimized(custom_data, globalvars.replace_string_cdr(islan))
            elif file_path.endswith(".bin"):
                with open(file_path, "rb") as f:
                    blob = f.read()
                if blob[0:2] == b"\x01\x43":
                    blob = zlib.decompress(blob[20:])
                # OPTIMIZATION: Use blob_unserialize directly, then blob_replace_dict_optimized
                custom_data = blobs.blob_unserialize(blob)
                custom_data = utilities.blobs.convert_to_bytes_deep(custom_data)
                blobs.blob_replace_dict_optimized(custom_data, globalvars.replace_string_cdr(islan))
            else:
                return False, f"Unsupported file type: {file_path}"
        except Exception as e:
            return False, f"Failed to parse {filename}: {e}"

        # Read and decompress existing blob
        with open(blob_path, "rb") as f:
            blob_data = f.read()

        if blob_data[0:2] == b"\x01\x43":
            blob_data = zlib.decompress(blob_data[20:])

        blob_dict = blobs.blob_unserialize(blob_data)

        # Merge custom data into blob
        _merge_cdr_data(blob_dict, custom_data)

        # Ensure all version records have DepotEncryptionKey
        _ensure_version_records_have_depot_encryption_key(blob_dict)

        # Regenerate app-to-subscription index after merge
        regenerate_app_to_subscription_index(blob_dict)

        # Replace encryption keys for any new apps
        _replace_encryption_keys(blob_dict)

        # Apply restriction removal to the merged blob (including new content)
        execdict = {"blob": blob_dict}
        remove_de_restrictions(execdict)
        blob_dict = execdict["blob"]

        # Serialize, replace RSA signatures, and compress using centralized function
        final_blob = serialize_and_compress_blob(blob_dict)

        # Write to temp file first, then rename
        with open(temp_path, "wb") as f:
            f.write(final_blob)

        if os.path.exists(blob_path):
            os.remove(blob_path)
        os.rename(temp_path, blob_path)

        return True, f"{blob_type}: merged {filename} successfully"

    except Exception as e:
        log.error(f"Failed to merge {file_path} into {blob_type} cache: {e}")
        # Clean up temp file if it exists
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass
        return False, str(e)


def check_and_merge_mod_blob_files():
    """
    Check mod_blob folder for new/modified files and merge them into cached blobs.

    This function tracks which files have been merged using a hash file.
    Only new or modified files are merged, without triggering a full neuter.

    Note: mod_blob merging is skipped for blob version 3 and earlier as the data
    structures may not be compatible with modern mod_blob files. Only blob version
    4+ supports mod_blob merging.

    Returns:
        int: Number of files merged
    """
    import hashlib
    import json

    # Skip mod_blob merging for blob version 3 and earlier
    # Only blob version 4+ have compatible data structures for mod_blob merging
    if globalvars.record_ver < 2:
        log.debug(f"Skipping mod_blob merge for blob version {globalvars.record_ver} (requires version 4+)")
        return 0

    mod_blob_dir = "files/mod_blob"
    hash_file_path = os.path.join(CACHE_DIR, "mod_blob_hashes.json")

    if not os.path.exists(mod_blob_dir):
        return 0

    # Load existing hashes
    existing_hashes = {}
    if os.path.exists(hash_file_path):
        try:
            with open(hash_file_path, 'r') as f:
                existing_hashes = json.load(f)
        except:
            existing_hashes = {}

    files_merged = 0
    new_hashes = {}

    # Scan mod_blob directory for supported files
    for root, dirs, files in os.walk(mod_blob_dir):
        for filename in files:
            if (filename.endswith((".py", ".bin", ".xml")) and
                filename not in ["2ndcdr.py", "1stcdr.py"] and
                not filename.startswith(("firstblob", "secondblob"))):

                file_path = os.path.join(root, filename)

                # Calculate file hash
                try:
                    with open(file_path, 'rb') as f:
                        file_hash = hashlib.sha256(f.read()).hexdigest()
                except Exception as e:
                    log.warning(f"Could not read {file_path}: {e}")
                    continue

                new_hashes[file_path] = file_hash

                # Check if file is new or modified
                if file_path not in existing_hashes or existing_hashes[file_path] != file_hash:
                    log.info(f"Found new/modified mod_blob file: {filename}")

                    # Merge into both LAN and WAN blobs
                    for islan in [True, False]:
                        success, message = merge_custom_blob_into_cache(file_path, islan)
                        if success:
                            log.info(message)
                        else:
                            log.error(f"Failed to merge {filename}: {message}")

                    files_merged += 1

    # Save updated hashes
    if new_hashes:
        try:
            with open(hash_file_path, 'w') as f:
                json.dump(new_hashes, f, indent=2)
        except Exception as e:
            log.warning(f"Could not save mod_blob hashes: {e}")

    # Reload blobs into memory after merging
    if files_merged > 0:
        load_blobs_to_memory()

    return files_merged


def regenerate_app_to_subscription_index(blob_dict):
    """
    Regenerate the app-to-subscription index from existing subscriptions.

    This ensures all apps in all subscriptions are properly indexed,
    which is required for purchasing to work correctly.

    Args:
        blob_dict: The blob dictionary to update
    """
    SUBS_KEY = b"\x02\x00\x00\x00"
    APP_SUB_INDEX_KEY = b"\x04\x00\x00\x00"
    SUB_APP_IDS_KEY = b"\x06\x00\x00\x00"  # AppIdsRecord within subscription

    if SUBS_KEY not in blob_dict:
        return

    # Initialize or get existing index
    if APP_SUB_INDEX_KEY not in blob_dict:
        blob_dict[APP_SUB_INDEX_KEY] = {}

    # Build a mapping of app_id -> set of subscription_ids
    app_to_subs = {}

    for sub_id_bytes, sub_data in blob_dict[SUBS_KEY].items():
        if SUB_APP_IDS_KEY in sub_data:
            for app_id_bytes in sub_data[SUB_APP_IDS_KEY].keys():
                if app_id_bytes not in app_to_subs:
                    app_to_subs[app_id_bytes] = {}
                app_to_subs[app_id_bytes][sub_id_bytes] = b''

    # Update the index - merge new subscriptions into existing app entries
    for app_id_bytes, sub_ids_dict in app_to_subs.items():
        if app_id_bytes in blob_dict[APP_SUB_INDEX_KEY]:
            # Merge with existing
            blob_dict[APP_SUB_INDEX_KEY][app_id_bytes].update(sub_ids_dict)
        else:
            # Add new
            blob_dict[APP_SUB_INDEX_KEY][app_id_bytes] = sub_ids_dict

    log.debug(f"Regenerated app-to-subscription index for {len(app_to_subs)} apps")


def _merge_cdr_data(main_blob, new_data):
    """
    Merge new CDR data into existing blob dictionary.

    Args:
        main_blob: The existing blob dictionary to update
        new_data: The new data to merge (from XML)
    """
    # Key mappings
    VERSION_KEY = b"\x00\x00\x00\x00"  # CDR version - ignore during merge
    APPS_KEY = b"\x01\x00\x00\x00"
    SUBS_KEY = b"\x02\x00\x00\x00"
    TIMESTAMP_KEY = b"\x03\x00\x00\x00"  # LastChangedExistingAppOrSubscriptionTime - ignore during merge
    APP_SUB_INDEX_KEY = b"\x04\x00\x00\x00"
    PUBLIC_KEYS_KEY = b"\x05\x00\x00\x00"
    PRIVATE_KEYS_KEY = b"\x06\x00\x00\x00"

    # Keys to ignore from custom blobs (preserve main blob values)
    IGNORED_KEYS = [VERSION_KEY, TIMESTAMP_KEY, PRIVATE_KEYS_KEY]

    for key, value in new_data.items():
        # Skip version and timestamp keys - preserve main blob values
        if key in IGNORED_KEYS:
            continue

        if key not in main_blob:
            # Key doesn't exist, add it directly
            main_blob[key] = value
            continue

        if key in [APPS_KEY, SUBS_KEY]:
            # For applications and subscriptions, merge individual entries
            for entry_id, entry_data in value.items():
                if entry_id in main_blob[key]:
                    # Entry exists, update it (overwrite with new data)
                    main_blob[key][entry_id] = entry_data
                else:
                    # New entry, add it
                    main_blob[key][entry_id] = entry_data

        elif key in [PUBLIC_KEYS_KEY, PRIVATE_KEYS_KEY]:
            # For encryption keys, merge entries
            for entry_id, entry_data in value.items():
                main_blob[key][entry_id] = entry_data

        elif key == APP_SUB_INDEX_KEY:
            # For app-to-subscription index, merge entries
            for app_id, sub_ids in value.items():
                main_blob[key][app_id] = sub_ids

        elif isinstance(value, dict) and isinstance(main_blob[key], dict):
            # For other dict values, update recursively
            main_blob[key].update(value)
        else:
            # For scalar values from custom XMLs, don't overwrite main blob values
            pass


def _replace_encryption_keys(blob_dict):
    """
    Replace encryption keys in blob with emulator's keys.

    Args:
        blob_dict: The blob dictionary to update
    """
    PUBLIC_KEYS_KEY = b"\x05\x00\x00\x00"

    if PUBLIC_KEYS_KEY in blob_dict:
        for app_id in blob_dict[PUBLIC_KEYS_KEY]:
            # Replace the public key with emulator's BERstring
            blob_dict[PUBLIC_KEYS_KEY][app_id] = encryption.BERstring


def _ensure_version_records_have_depot_encryption_key(blob_dict):
    """
    Ensure all version records in application records have a DepotEncryptionKey field.

    This is called after merging custom blobs to ensure version records always have
    the DepotEncryptionKey field (b'\\x05\\x00\\x00\\x00') with at least a null-terminated
    value (b'\\x00').

    Args:
        blob_dict: The blob dictionary to update
    """
    APPS_KEY = b"\x01\x00\x00\x00"
    VERSIONS_KEY = b"\x0c\x00\x00\x00"  # VersionsRecord key in app record
    DEPOT_ENCRYPTION_KEY = b"\x05\x00\x00\x00"  # DepotEncryptionKey field in version record

    if APPS_KEY not in blob_dict:
        return

    for app_id, app_data in blob_dict[APPS_KEY].items():
        if not isinstance(app_data, dict):
            continue

        if VERSIONS_KEY not in app_data:
            continue

        versions = app_data[VERSIONS_KEY]
        if not isinstance(versions, dict):
            continue

        for version_id, version_data in versions.items():
            if not isinstance(version_data, dict):
                continue

            # Ensure DepotEncryptionKey exists with at least null terminator
            if DEPOT_ENCRYPTION_KEY not in version_data:
                version_data[DEPOT_ENCRYPTION_KEY] = b'\x00'
            elif version_data[DEPOT_ENCRYPTION_KEY] is None or version_data[DEPOT_ENCRYPTION_KEY] == b'':
                version_data[DEPOT_ENCRYPTION_KEY] = b'\x00'


# =============================================================================
# OPTIMIZED DATABASE QUERY EXECUTION
# =============================================================================

# Connection pool for reusing database connections
_connection_pool = {}
_pool_lock = None

def _get_pool_lock():
    """Lazy initialization of pool lock."""
    global _pool_lock
    if _pool_lock is None:
        import threading
        _pool_lock = threading.Lock()
    return _pool_lock


def _get_pooled_connection(db_config):
    """Get a connection from the pool or create a new one."""
    host, port, user, password, database = db_config
    key = (host, port, database)

    with _get_pool_lock():
        if key in _connection_pool:
            conn = _connection_pool[key]
            try:
                # Test if connection is still alive
                conn.ping()
                return conn
            except:
                # Connection is dead, remove from pool
                del _connection_pool[key]

        # Create new connection
        conn = mariadb.connect(
            user=user,
            password=password,
            host=host,
            port=int(port),
            database=database
        )
        conn.autocommit = True
        _connection_pool[key] = conn
        return conn


def _execute_query_thread(db_config, query, query_name):
    """
    Execute a single database query in a separate thread.

    Args:
        db_config: tuple of (host, port, user, password, database)
        query: SQL query string to execute
        query_name: Name for logging/identification

    Returns:
        tuple of (query_name, results_list)
    """
    host, port, user, password, database = db_config
    try:
        conn = mariadb.connect(
            user=user,
            password=password,
            host=host,
            port=int(port),
            database=database
        )
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SET time_zone = '+00:00'")
        cur.execute(query)
        results = cur.fetchall()
        conn.close()
        return (query_name, results)
    except mariadb.Error as e:
        log.error(f"Error executing query {query_name}: {e}")
        return (query_name, [])


def execute_queries_sequential(conn, queries_dict):
    """
    Execute multiple queries sequentially on a SINGLE connection.

    This is faster than parallel execution when:
    1. Queries are fast individually
    2. Connection overhead would dominate
    3. MariaDB query cache benefits from sequential execution

    Args:
        conn: Active database connection
        queries_dict: dict mapping query_name -> SQL query string

    Returns:
        dict mapping query_name -> list of result rows
    """
    results = {}
    cur = conn.cursor()

    for query_name, query in queries_dict.items():
        try:
            cur.execute(query)
            results[query_name] = cur.fetchall()
        except mariadb.Error as e:
            log.error(f"Error executing query {query_name}: {e}")
            results[query_name] = []

    return results


def execute_queries_parallel(db_config, queries_dict, max_workers=5):
    """
    Execute multiple database queries in parallel using ThreadPoolExecutor.

    Args:
        db_config: tuple of (host, port, user, password, database)
        queries_dict: dict mapping query_name -> SQL query string
        max_workers: Maximum number of parallel connections

    Returns:
        dict mapping query_name -> list of result rows
    """
    results = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_execute_query_thread, db_config, query, name): name
            for name, query in queries_dict.items()
        }

        for future in as_completed(futures):
            query_name, query_results = future.result()
            results[query_name] = query_results

    return results


def execute_queries_batched(db_config, queries_dict, batch_size=4):
    """
    Execute queries in batches - a hybrid approach.

    Opens `batch_size` connections and distributes queries across them.
    Better than full parallel (too many connections) or full sequential (too slow).

    Args:
        db_config: tuple of (host, port, user, password, database)
        queries_dict: dict mapping query_name -> SQL query string
        batch_size: Number of concurrent connections to use

    Returns:
        dict mapping query_name -> list of result rows
    """
    host, port, user, password, database = db_config
    query_items = list(queries_dict.items())
    results = {}

    # Create batch_size connections
    connections = []
    for _ in range(min(batch_size, len(query_items))):
        try:
            conn = mariadb.connect(
                user=user,
                password=password,
                host=host,
                port=int(port),
                database=database
            )
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute("SET time_zone = '+00:00'")
            connections.append((conn, cur))
        except mariadb.Error as e:
            log.error(f"Error creating batch connection: {e}")

    if not connections:
        return results

    # Distribute queries round-robin across connections
    def execute_batch(conn_cur, queries):
        """Execute a list of queries on a single connection."""
        conn, cur = conn_cur
        batch_results = {}
        for query_name, query in queries:
            try:
                cur.execute(query)
                batch_results[query_name] = cur.fetchall()
            except mariadb.Error as e:
                log.error(f"Error executing query {query_name}: {e}")
                batch_results[query_name] = []
        return batch_results

    # Split queries into batches
    batches = [[] for _ in range(len(connections))]
    for i, item in enumerate(query_items):
        batches[i % len(connections)].append(item)

    # Execute batches in parallel
    with ThreadPoolExecutor(max_workers=len(connections)) as executor:
        futures = [
            executor.submit(execute_batch, connections[i], batches[i])
            for i in range(len(connections))
        ]

        for future in as_completed(futures):
            batch_results = future.result()
            results.update(batch_results)

    # Close connections
    for conn, cur in connections:
        try:
            conn.close()
        except:
            pass

    return results


def get_db_version(db_host, db_port, db_user, db_pass):
    try:
        conn2 = mariadb.connect(
            user=db_user,
            password=db_pass,
            host=db_host,
            port=int(db_port),
            database="ContentDescriptionDB"

        )
        cur = conn2.cursor()
    
        cur.execute("select @@version as version;")
        for version in cur:
            log.debug("Found MariaDB version " + str(version[0]))
            return version[0]
    except mariadb.Error as e:
        log.error(f"Error connecting to MariaDB Platform: {e}")
        return

def construct_blob_from_cddb(db_host, db_port, db_user, db_pass, cddb, timestamp, working_dir):
    """
    Construct a blob dictionary from the ContentDescriptionDB database.

    OPTIMIZATION: This function now uses caching to avoid repeated expensive
    temporal queries when the timestamp hasn't changed.
    """
    log.info(f"construct_blob_from_cddb: Entered with host={db_host}:{db_port}, db={cddb}")
    # Check cache first
    cached = get_cached_blob_dict(cddb, timestamp)
    if cached is not None:
        log.info(f"Using cached blob dict from previous query (timestamp: {timestamp})")
        return cached

    log.debug(f"Building blob dict from database {cddb} for timestamp {timestamp}")
    build_start = time.time()

    log.info(f"construct_blob_from_cddb: Connecting to MariaDB at {db_host}:{db_port}...")
    try:
        conn2 = mariadb.connect(
            user=db_user,
            password=db_pass,
            host=db_host,
            port=int(db_port),
            database=cddb,
            connect_timeout=10  # Add 10 second timeout to prevent infinite hang
        )
    except mariadb.Error as e:
        log.error(f"Error connecting to MariaDB Platform: {e}")
        return
    log.info("construct_blob_from_cddb: MariaDB connection established")
    conn2.autocommit = True

    cur = conn2.cursor()
    cur2 = conn2.cursor()
    cur3 = conn2.cursor()
    cur4 = conn2.cursor()
    cur.execute("SET time_zone = '+00:00'")
    cur2.execute("SET time_zone = '+00:00'")
    cur3.execute("SET time_zone = '+00:00'")
    cur4.execute("SET time_zone = '+00:00'")
    blob_dict = {}

    ##############  START  ##############
    #BLOB VERSION
    #print(f"SELECT version FROM blob_version FOR SYSTEM_TIME AS OF TIMESTAMP'{timestamp}'")
    cur.execute(f"SELECT version FROM blob_version FOR SYSTEM_TIME AS OF TIMESTAMP'{timestamp}'")
    for data in cur:
        blob_dict[b'\x00\x00\x00\x00'] = struct.pack('<H', data[0])
        blob_version = data[0]

    if timestamp < "2003-09-09 18_50_46":
        #APPLICATIONS
        blob_dict[b'\x01\x00\x00\x00'] = {}

        # Fetch applications
        app_query = f"SELECT * FROM applications FOR SYSTEM_TIME AS OF TIMESTAMP '{timestamp}'"
        cur.execute(app_query)
        applications = cur.fetchall()

        # Organize applications data
        app_data = {}
        for row in applications:
            app_id = struct.pack('<i', row[0])
            app_data[app_id] = {}
            app_data[app_id][b'\x01\x00\x00\x00'] = struct.pack('<i', row[0]) #app_id
            app_data[app_id][b'\x02\x00\x00\x00'] = bytes(row[1], 'UTF-8') + b'\x00' #app_name
            if blob_version == 1:
                app_data[app_id][b'\x03\x00\x00\x00'] = struct.pack('<i', row[5]) #gcf_ver
                app_data[app_id][b'\x04\x00\x00\x00'] = bytes(row[6], 'UTF-8') + b'\x00' #won_ver
                app_data[app_id][b'\x05\x00\x00\x00'] = bytes(row[2], 'UTF-8') + b'\x00' #inst_dir
                app_data[app_id][b'\x06\x00\x00\x00'] = struct.pack('<i', row[3]) #min_size
                app_data[app_id][b'\x07\x00\x00\x00'] = struct.pack('<i', row[4]) #min_size
                app_data[app_id][b'\x08\x00\x00\x00'] = {}
                app_data[app_id][b'\x08\x00\x00\x00'][b'\x00\x00\x00\x00'] = {} #launch info
                app_data[app_id][b'\x08\x00\x00\x00'][b'\x00\x00\x00\x00'][b'\x01\x00\x00\x00'] = bytes(row[7], 'UTF-8') + b'\x00' #launch name
                app_data[app_id][b'\x08\x00\x00\x00'][b'\x00\x00\x00\x00'][b'\x02\x00\x00\x00'] = bytes(row[8], 'UTF-8') + b'\x00' #command line
                app_data[app_id][b'\x08\x00\x00\x00'][b'\x00\x00\x00\x00'][b'\x03\x00\x00\x00'] = b'\x00\x00\x00\x00'
                app_data[app_id][b'\x08\x00\x00\x00'][b'\x00\x00\x00\x00'][b'\x04\x00\x00\x00'] = b'\x00'
                app_data[app_id][b'\x08\x00\x00\x00'][b'\x00\x00\x00\x00'][b'\x05\x00\x00\x00'] = b'\x00'
                app_data[app_id][b'\x08\x00\x00\x00'][b'\x00\x00\x00\x00'][b'\x06\x00\x00\x00'] = b'\x00'
                app_data[app_id][b'\x09\x00\x00\x00'] = {}
                app_data[app_id][b'\x09\x00\x00\x00'][b'\x00\x00\x00\x00'] = bytes.fromhex(row[10].replace('\\x', '')) #icon
                app_data[app_id][b'\x0a\x00\x00\x00'] = struct.pack('<i', row[11]) #0a
                app_data[app_id][b'\x0b\x00\x00\x00'] = struct.pack('<b', row[12]) #0b
            elif blob_version == 2:
                app_data[app_id][b'\x03\x00\x00\x00'] = bytes(row[2], 'UTF-8') + b'\x00' #inst_dir
                app_data[app_id][b'\x04\x00\x00\x00'] = struct.pack('<i', row[3]) #min_size
                app_data[app_id][b'\x05\x00\x00\x00'] = struct.pack('<i', row[4]) #min_size
                app_data[app_id][b'\x06\x00\x00\x00'] = {}
                app_data[app_id][b'\x06\x00\x00\x00'][b'\x00\x00\x00\x00'] = {} #launch info
                app_data[app_id][b'\x06\x00\x00\x00'][b'\x00\x00\x00\x00'][b'\x01\x00\x00\x00'] = bytes(row[7], 'UTF-8') + b'\x00' #launch name
                app_data[app_id][b'\x06\x00\x00\x00'][b'\x00\x00\x00\x00'][b'\x02\x00\x00\x00'] = bytes(row[8], 'UTF-8') + b'\x00' #command line
                app_data[app_id][b'\x06\x00\x00\x00'][b'\x00\x00\x00\x00'][b'\x03\x00\x00\x00'] = b'\x00\x00\x00\x00'
                app_data[app_id][b'\x06\x00\x00\x00'][b'\x00\x00\x00\x00'][b'\x04\x00\x00\x00'] = b'\x01'
                app_data[app_id][b'\x06\x00\x00\x00'][b'\x00\x00\x00\x00'][b'\x05\x00\x00\x00'] = b'\x01'
                app_data[app_id][b'\x06\x00\x00\x00'][b'\x00\x00\x00\x00'][b'\x06\x00\x00\x00'] = b'\x00'
                app_data[app_id][b'\x07\x00\x00\x00'] = {}
                app_data[app_id][b'\x07\x00\x00\x00'][b'\x00\x00\x00\x00'] = bytes.fromhex(row[10].replace('\\x', '')) #icon
                app_data[app_id][b'\x08\x00\x00\x00'] = b'\xff\xff\xff\xff'
                app_data[app_id][b'\x09\x00\x00\x00'] = b'\x01'
                app_data[app_id][b'\x0a\x00\x00\x00'] = {}
                app_data[app_id][b'\x0a\x00\x00\x00'][b'\x00\x00\x00\x00'] = {}
                app_data[app_id][b'\x0a\x00\x00\x00'][b'\x00\x00\x00\x00'][b'\x01\x00\x00\x00'] = bytes(row[9], 'UTF-8') + b'\x00'
                app_data[app_id][b'\x0a\x00\x00\x00'][b'\x00\x00\x00\x00'][b'\x02\x00\x00\x00'] = b'\x00\x00\x00\x00'
                app_data[app_id][b'\x0a\x00\x00\x00'][b'\x00\x00\x00\x00'][b'\x03\x00\x00\x00'] = b'\x00'
                app_data[app_id][b'\x0a\x00\x00\x00'][b'\x00\x00\x00\x00'][b'\x04\x00\x00\x00'] = {}
                app_data[app_id][b'\x0a\x00\x00\x00'][b'\x00\x00\x00\x00'][b'\x04\x00\x00\x00'][b'\x00\x00\x00\x00'] = ''
                app_data[app_id][b'\x0b\x00\x00\x00'] = struct.pack('<i', row[5]) #gcf_ver
            elif blob_version == 3:
                app_data[app_id][b'\x03\x00\x00\x00'] = bytes(row[2], 'UTF-8') + b'\x00' #inst_dir
                app_data[app_id][b'\x04\x00\x00\x00'] = struct.pack('<i', row[3]) #min_size
                app_data[app_id][b'\x05\x00\x00\x00'] = struct.pack('<i', row[4]) #min_size
                app_data[app_id][b'\x06\x00\x00\x00'] = {} #launch_options
                app_data[app_id][b'\x07\x00\x00\x00'] = bytes.fromhex(row[10].replace('\\x', '')) #icon
                app_data[app_id][b'\x08\x00\x00\x00'] = b'\xff\xff\xff\xff'
                app_data[app_id][b'\x09\x00\x00\x00'] = b'\x01'
                app_data[app_id][b'\x0a\x00\x00\x00'] = {}
                app_data[app_id][b'\x0b\x00\x00\x00'] = struct.pack('<i', row[5]) #gcf_ver

                # Fetch launch options
                launch_query = f"SELECT * FROM apps_launch FOR SYSTEM_TIME AS OF TIMESTAMP '{timestamp}'"
                cur.execute(launch_query)
                launch_options = cur.fetchall()
                for row in launch_options:
                    app_id = struct.pack('<i', row[0])
                    launch_id = struct.pack('<i', row[1])
                    if app_id in app_data:
                        app_data[app_id][b'\x06\x00\x00\x00'][launch_id] = {
                            b'\x01\x00\x00\x00': bytes(row[2], 'UTF-8') + b'\x00',
                            b'\x02\x00\x00\x00': bytes(row[3], 'UTF-8') + b'\x00',
                            b'\x03\x00\x00\x00': struct.pack('<i', row[4]),
                            b'\x04\x00\x00\x00': struct.pack('<B', row[5]),
                            b'\x05\x00\x00\x00': struct.pack('<B', row[6]),
                            b'\x06\x00\x00\x00': struct.pack('<B', row[7]),
                        }

                # Fetch versions
                version_query = f"SELECT * FROM apps_versions FOR SYSTEM_TIME AS OF TIMESTAMP '{timestamp}' ORDER BY app_id, order_id"
                launch_query = f"SELECT * FROM apps_launch_ids FOR SYSTEM_TIME AS OF TIMESTAMP '{timestamp}' ORDER BY app_id, order_id"
                cur.execute(version_query)
                versions = cur.fetchall()
                cur.execute(launch_query)
                launch_ids = cur.fetchall()
                launch_ids_dict = defaultdict(list)
                for row in launch_ids:
                    launch_ids_dict[(row[0], row[1])].append(row[3])
                for row in versions:
                    app_id = struct.pack('<i', row[0])
                    order_id = struct.pack('<i', row[4])
                    launch_id_app = launch_ids_dict.get((row[0], row[4]), None)
                    if app_id in app_data:
                        launch_data = {}
                        if launch_id_app != None:
                            for launch_id in launch_id_app:
                                launch_data[struct.pack('<i', launch_id)] = b''
                        version_data = {
                            b'\x01\x00\x00\x00': bytes(row[1], 'UTF-8') + b'\x00',
                            b'\x02\x00\x00\x00': struct.pack('<i', row[2]),
                            b'\x03\x00\x00\x00': struct.pack('<B', row[3]),
                            b'\x04\x00\x00\x00': launch_data
                        }
                        app_data[app_id][b'\x0a\x00\x00\x00'][order_id] = version_data


                # Copy data to blob_dict
        for app_id, data in app_data.items():
            blob_dict[b'\x01\x00\x00\x00'][app_id] = data
    else:
        # OPTIMIZATION: Execute all queries in parallel for the modern path
        # This provides 2-4x speedup for database operations
        db_config = (db_host, db_port, db_user, db_pass, cddb)

        # Define all queries to execute in parallel
        parallel_queries = {
            'applications': f"SELECT * FROM applications FOR SYSTEM_TIME AS OF TIMESTAMP '{timestamp}'",
            'apps_launch': f"SELECT * FROM apps_launch FOR SYSTEM_TIME AS OF TIMESTAMP '{timestamp}'",
            'apps_versions': f"SELECT * FROM apps_versions FOR SYSTEM_TIME AS OF TIMESTAMP '{timestamp}' ORDER BY app_id, order_id",
            'encryption_keys': f"SELECT * FROM encryption_keys FOR SYSTEM_TIME AS OF TIMESTAMP '{timestamp}' ORDER BY app_id, key_id",
            'apps_launch_ids': f"SELECT * FROM apps_launch_ids FOR SYSTEM_TIME AS OF TIMESTAMP '{timestamp}' ORDER BY app_id, order_id",
            'apps_depots': f"SELECT * FROM apps_depots FOR SYSTEM_TIME AS OF TIMESTAMP '{timestamp}'",
            'apps_ext_info': f"SELECT * FROM apps_ext_info FOR SYSTEM_TIME AS OF TIMESTAMP '{timestamp}'",
            'apps_country_ext_info': f"SELECT * FROM apps_country_ext_info FOR SYSTEM_TIME AS OF TIMESTAMP '{timestamp}'",
            'subscriptions': f"SELECT * FROM subscriptions FOR SYSTEM_TIME AS OF TIMESTAMP'{timestamp}'",
            'subs_discount': f"SELECT * FROM subs_discount FOR SYSTEM_TIME AS OF TIMESTAMP'{timestamp}'",
            'subs_qualifiers': f"SELECT * FROM subs_qualifiers FOR SYSTEM_TIME AS OF TIMESTAMP'{timestamp}'",
            'subs_ext_info': f"SELECT * FROM subs_ext_info FOR SYSTEM_TIME AS OF TIMESTAMP'{timestamp}' ORDER BY sub_id",
            'blob_datetime': f"SELECT date_time FROM blob_datetime FOR SYSTEM_TIME AS OF TIMESTAMP'{timestamp}'",
            'apps_count': f"SELECT count FROM apps_count FOR SYSTEM_TIME AS OF TIMESTAMP'{timestamp}'",
            'apps_subs': f"SELECT app_id, sub_id FROM apps_subs FOR SYSTEM_TIME AS OF TIMESTAMP'{timestamp}'",
            'rsa_keys': f"SELECT app_id, rsa_key FROM rsa_keys FOR SYSTEM_TIME AS OF TIMESTAMP'{timestamp}'"
        }

        # OPTIMIZATION: Use batched query execution (4 connections, queries distributed)
        # This is more efficient than full parallel (16 connections) or sequential
        query_results = execute_queries_batched(db_config, parallel_queries, batch_size=4)

        # Extract results for use below
        applications = query_results.get('applications', [])
        launch_options = query_results.get('apps_launch', [])
        versions = query_results.get('apps_versions', [])
        keys = query_results.get('encryption_keys', [])
        launch_ids = query_results.get('apps_launch_ids', [])
        depots = query_results.get('apps_depots', [])
        ext_infos = query_results.get('apps_ext_info', [])
        country_ext_infos = query_results.get('apps_country_ext_info', [])
        subscriptions_data = query_results.get('subscriptions', [])
        sub_discounts = query_results.get('subs_discount', [])
        sub_disc_qualifiers = query_results.get('subs_qualifiers', [])
        sub_ext_infos = query_results.get('subs_ext_info', [])

        #APPLICATIONS
        blob_dict[b'\x01\x00\x00\x00'] = {}

        # Organize applications data
        app_data = {}
        for row in applications:
            app_id = struct.pack('<i', row[0])
            app_data[app_id] = {
                b'\x01\x00\x00\x00': struct.pack('<i', row[1]), #alt_app_id
                b'\x02\x00\x00\x00': bytes(row[2], 'UTF-8') + b'\x00', #app_name
                b'\x03\x00\x00\x00': bytes(row[3], 'UTF-8') + b'\x00', #inst_dir
                b'\x04\x00\x00\x00': struct.pack('<i', row[4]), #min_size
                b'\x05\x00\x00\x00': struct.pack('<i', row[5]), #max_size
                b'\x06\x00\x00\x00': {}, #launch_options
                b'\x07\x00\x00\x00': {}, #empty
                b'\x08\x00\x00\x00': struct.pack('<i', row[6]), #on_first_launch
                b'\x09\x00\x00\x00': struct.pack('<B', row[7]), #app_bandwidth_greedy
                b'\x0a\x00\x00\x00': {}, #versions
                b'\x0b\x00\x00\x00': struct.pack('<i', row[8]), #current_ver
                b'\x0c\x00\x00\x00': {}, #depots
                b'\x0d\x00\x00\x00': struct.pack('<i', row[9]) #trickle_ver
            }
            if row[17] != None: app_data[app_id][b'\x0e\x00\x00\x00'] = {}
            if row[10] != None: app_data[app_id][b'\x0f\x00\x00\x00'] = bytes(row[10], 'UTF-8') + b'\x00'
            if row[11] != None: app_data[app_id][b'\x10\x00\x00\x00'] = struct.pack('<i', row[11])
            if row[12] != None: app_data[app_id][b'\x11\x00\x00\x00'] = bytes(row[12], 'UTF-8') + b'\x00'
            if row[13] != None: app_data[app_id][b'\x12\x00\x00\x00'] = struct.pack('<B', row[13])
            if row[14] != None: app_data[app_id][b'\x13\x00\x00\x00'] = struct.pack('<B', row[14])
            if row[15] != None: app_data[app_id][b'\x14\x00\x00\x00'] = struct.pack('<B', row[15])
            if row[16] != None: app_data[app_id][b'\x15\x00\x00\x00'] = struct.pack('<i', row[16])
            if row[18] != None: app_data[app_id][b'\x16\x00\x00\x00'] = {} #country_ext_info

        # Process launch options (pre-fetched in parallel)
        for row in launch_options:
            app_id = struct.pack('<i', row[0])
            launch_id = struct.pack('<i', row[1])
            if app_id in app_data:
                app_data[app_id][b'\x06\x00\x00\x00'][launch_id] = {
                    b'\x01\x00\x00\x00': bytes(row[2], 'UTF-8') + b'\x00',
                    b'\x02\x00\x00\x00': bytes(row[3], 'UTF-8') + b'\x00',
                    b'\x03\x00\x00\x00': struct.pack('<i', row[4]),
                    b'\x04\x00\x00\x00': struct.pack('<B', row[5]),
                    b'\x05\x00\x00\x00': struct.pack('<B', row[6]),
                    b'\x06\x00\x00\x00': struct.pack('<B', row[7]),
                }
                if row[8] != None: app_data[app_id][b'\x06\x00\x00\x00'][launch_id][b'\x07\x00\x00\x00'] = bytes(row[8], 'UTF-8') + b'\x00'

        # Process versions (pre-fetched in parallel)
        keys_dict = {(row[0], row[2]): row[1] for row in keys}
        launch_ids_dict = defaultdict(list)
        for row in launch_ids:
            launch_ids_dict[(row[0], row[1])].append(row[3])
        for row in versions:
            app_id = struct.pack('<i', row[0])
            order_id = struct.pack('<i', row[8])
            key = keys_dict.get((row[0], row[9]), None)
            launch_id_app = launch_ids_dict.get((row[0], row[8]), None)
            if app_id in app_data:
                launch_data = {}
                if launch_id_app != None:
                    for launch_id in launch_id_app:
                        launch_data[struct.pack('<i', launch_id)] = b''
                version_data = {
                    b'\x01\x00\x00\x00': bytes(row[1], 'UTF-8') + b'\x00',
                    b'\x02\x00\x00\x00': struct.pack('<i', row[2]),
                    b'\x03\x00\x00\x00': struct.pack('<B', row[3]),
                    b'\x04\x00\x00\x00': launch_data,
                    b'\x05\x00\x00\x00': b'\x00',
                    b'\x06\x00\x00\x00': struct.pack('<B', row[4]),
                    b'\x07\x00\x00\x00': struct.pack('<B', row[5])
                }
                if key != None: version_data[b'\x05\x00\x00\x00'] = bytes(key, 'UTF-8') + b'\x00'
                if row[6] != None: version_data[b'\x08\x00\x00\x00'] = struct.pack('<B', row[6])
                if row[7] != None: version_data[b"__slack__"] = b'\x00' * row[7]
                app_data[app_id][b'\x0a\x00\x00\x00'][order_id] = version_data

        # Process depots (pre-fetched in parallel)
        for row in depots:
            app_id = struct.pack('<i', row[0])
            depot_order = struct.pack('<i', row[4])
            if app_id in app_data:
                app_data[app_id][b'\x0c\x00\x00\x00'][depot_order] = {
                    b'\x01\x00\x00\x00': struct.pack('<i', row[1]),
                    b'\x02\x00\x00\x00': bytes(row[2], 'UTF-8') + b'\x00' if row[2] else b'\x00',
                    b'\x03\x00\x00\x00': struct.pack('<B', row[3])
                }
                if row[5]: app_data[app_id][b'\x0c\x00\x00\x00'][depot_order][b'\x04\x00\x00\x00'] = bytes(row[5], 'UTF-8') + b'\x00'

        # Process extensions info (pre-fetched in parallel)
        for row in ext_infos:
            app_id = struct.pack('<i', row[0])
            info_name = row[1]
            if app_id in app_data:
                app_data[app_id][b'\x0e\x00\x00\x00'][info_name] = bytes(row[2], 'UTF-8') + b'\x00'

        # Process country-specific info (pre-fetched in parallel)
        country_ext_infos_dict = defaultdict(list)
        for row in country_ext_infos:
            country_ext_infos_dict[(row[0], row[1])].append((row[3], row[4]))
        for row in country_ext_infos:
            app_id = struct.pack('<i', row[1])
            order_id = struct.pack('<i', row[0])
            country_ext_infos_id_app = country_ext_infos_dict.get((row[0], row[1]), None)
            if b'\x16\x00\x00\x00' in app_data[app_id]:
                if app_id in app_data:
                    country_ext_infos_data = {}
                    if country_ext_infos_id_app != None:
                        for country_ext_infos_id in country_ext_infos_id_app:
                            country_ext_infos_data[country_ext_infos_id[0]] = (bytes(country_ext_infos_id[1], 'UTF-8')  + b'\x00')
                    app_data[app_id][b'\x16\x00\x00\x00'][order_id] = {
                        b'\x01\x00\x00\x00': bytes(row[2], 'UTF-8') + b'\x00',
                        b'\x02\x00\x00\x00': country_ext_infos_data
                    }

        # Copy data to blob_dict
        for app_id, data in app_data.items():
            blob_dict[b'\x01\x00\x00\x00'][app_id] = data

    if timestamp < "2003-09-09 18_50_46":
        #SUBSCRIPTIONS
        # Fetch all required data at once
        cur.execute(f"SELECT * FROM subscriptions FOR SYSTEM_TIME AS OF TIMESTAMP'{timestamp}'")
        subscriptions = cur.fetchall()

        sub_data = {}
        # Initialize the dictionary
        blob_dict[b'\x02\x00\x00\x00'] = {}
        for row in subscriptions:
            sub_id = struct.pack('<i', row[0])
            sub_data[sub_id] = {}
            sub_data[sub_id][b'\x01\x00\x00\x00'] = struct.pack('<i', row[0]) #sub_id
            sub_data[sub_id][b'\x02\x00\x00\x00'] = bytes(row[1], 'UTF-8') + b'\x00' #sub_name
            sub_data[sub_id][b'\x03\x00\x00\x00'] = b'\x00\x80\x8eC3\x02\x00\x00'
            sub_data[sub_id][b'\x04\x00\x00\x00'] = b'\x00\x00\x00\x00'
            sub_data[sub_id][b'\x05\x00\x00\x00'] = b'\x01'
            sub_data[sub_id][b'\x06\x00\x00\x00'] = {}
            subs_list = row[2].split(",")
            for app in subs_list:
                if app != "NULL":
                    sub_data[sub_id][b'\x06\x00\x00\x00'][struct.pack('<i', int(app))] = ''
            sub_data[sub_id][b'\x07\x00\x00\x00'] = b'\xff\xff\xff\xff'
            sub_data[sub_id][b'\x08\x00\x00\x00'] = b'\xff\xff\xff\xff'

                # Copy data to blob_dict
        for sub_id, data in sub_data.items():
            blob_dict[b'\x02\x00\x00\x00'][sub_id] = data
    else:
        #SUBSCRIPTIONS (pre-fetched in parallel)
        packed_values_cache = {}

        def get_packed_value(fmt, value):
            if (fmt, value) not in packed_values_cache:
                packed_values_cache[(fmt, value)] = struct.pack(fmt, value)
            return packed_values_cache[(fmt, value)]

        blob_dict[b'\x02\x00\x00\x00'] = {}

        # Process pre-fetched subscription data
        sub_ext_infos_dict = defaultdict(list)
        for row in sub_ext_infos:
            sub_ext_infos_dict[(row[0])].append((row[1], row[2]))

        sub_discount_dict = defaultdict(list)
        for row in sub_discounts:
            sub_discount_dict[(row[1])].append((row[0], row[2], row[3]))

        sub_disc_qualifiers_dict = defaultdict(list)
        for row in sub_disc_qualifiers:
            sub_disc_qualifiers_dict[(row[2])].append((row[0], row[1], row[3], row[4]))

        # Process the subscriptions (pre-fetched)
        subs_list = []
        for data in subscriptions_data:
            sub_id = get_packed_value('<i', data[0])
            subs_list.append(data[0])

            sub_data = blob_dict[b'\x02\x00\x00\x00'][sub_id] = {}
            sub_data[b'\x01\x00\x00\x00'] = get_packed_value('<i', data[1])
            sub_data[b'\x02\x00\x00\x00'] = bytes(data[2], 'UTF-8') + b'\x00'
            sub_data[b'\x03\x00\x00\x00'] = get_packed_value('<H', data[3])
            sub_data[b'\x04\x00\x00\x00'] = get_packed_value('<i', data[4])
            sub_data[b'\x06\x00\x00\x00'] = {}
            sub_data[b'\x07\x00\x00\x00'] = get_packed_value('<i', data[6])
            sub_data[b'\x08\x00\x00\x00'] = get_packed_value('<i', data[7])
            if data[8] != None: sub_data[b'\x0b\x00\x00\x00'] = get_packed_value('<B', data[8])
            if data[9] != None: sub_data[b'\x0c\x00\x00\x00'] = get_packed_value('<B', data[9])
            if data[10] != None: sub_data[b'\x0d\x00\x00\x00'] = get_packed_value('<i', data[10])
            if data[11] != None: sub_data[b'\x0e\x00\x00\x00'] = get_packed_value('<i', data[11])
            if data[12] != None: sub_data[b'\x0f\x00\x00\x00'] = get_packed_value('<i', data[12])
            if data[13] != None: sub_data[b'\x10\x00\x00\x00'] = get_packed_value('<B', data[13])
            if data[14] != None: sub_data[b'\x11\x00\x00\x00'] = get_packed_value('<i', data[14])
            if data[15] != None: sub_data[b'\x12\x00\x00\x00'] = bytes(data[15], 'UTF-8') + b'\x00'
            if data[16] != None: sub_data[b'\x13\x00\x00\x00'] = get_packed_value('<B', data[16])
            if data[17] != None: sub_data[b'\x14\x00\x00\x00'] = get_packed_value('<B', data[17])
            if data[18] != None: sub_data[b'\x15\x00\x00\x00'] = get_packed_value('<i', data[18])
            if data[19] != None: sub_data[b'\x16\x00\x00\x00'] = get_packed_value('<B', data[19])
            if data[20] != None: sub_data[b'\x17\x00\x00\x00'] = {}

            # Process sub_appids
            if data[5]:
                sub_appids = data[5].split(',')
                sub_apps_dict = sub_data[b'\x06\x00\x00\x00']
                for app in sub_appids:
                    app_id = get_packed_value('<i', int(app))
                    sub_apps_dict[app_id] = b''

            # Fetch discount data for this subscription
            discounts = sub_discount_dict.get(str(data[0]), [])
            qualifiers = sub_disc_qualifiers_dict.get(str(data[0]), [])
            for discount in discounts:
                order_id = get_packed_value('<i', discount[0])
                discount_name = bytes(discount[1], 'UTF-8') + b'\x00'
                discount_price = get_packed_value('<i', discount[2])

                for qualifier in qualifiers:
                    qualifier_dict = {
                        get_packed_value('<i', qualifier[1]): {
                            b'\x01\x00\x00\x00': bytes(qualifier[2], 'UTF-8') + b'\x00',
                            b'\x02\x00\x00\x00': get_packed_value('<i', qualifier[3])
                        }
                    }

                discount_data = sub_data.setdefault(b'\x0a\x00\x00\x00', {})
                discount_data[order_id] = {
                    b'\x01\x00\x00\x00': discount_name,
                    b'\x02\x00\x00\x00': discount_price,
                    b'\x03\x00\x00\x00': qualifier_dict
                }

        for row in sub_ext_infos:
            if row[0] in subs_list:
                sub_id = struct.pack('<i', row[0])
                sub_ext_infos_id_sub = sub_ext_infos_dict.get((row[0]), None)
                if b'\x17\x00\x00\x00' in blob_dict[b'\x02\x00\x00\x00'][sub_id]:
                    sub_ext_infos_data = {}
                    if sub_ext_infos_id_sub != None:
                        for sub_ext_infos_id in sub_ext_infos_id_sub:
                            sub_ext_infos_data[sub_ext_infos_id[0].encode('UTF-8')] = (bytes(sub_ext_infos_id[1], 'UTF-8') + b'\x00')
                    blob_dict[b'\x02\x00\x00\x00'][sub_id][b'\x17\x00\x00\x00'] = sub_ext_infos_data

    #BLOB_DATE
    if timestamp < "2003-09-09 18_50_46":
        # Old path - execute query directly
        cur.execute(f"SELECT date_time FROM blob_datetime FOR SYSTEM_TIME AS OF TIMESTAMP'{timestamp}'")
        for data in cur:
            data_temp = bytes.fromhex(data[0].replace('\\x', ''))
            blob_dict[b'\x03\x00\x00\x00'] = data_temp
    else:
        # Modern path - use pre-fetched data
        blob_datetime_results = query_results.get('blob_datetime', [])
        for data in blob_datetime_results:
            data_temp = bytes.fromhex(data[0].replace('\\x', ''))
            blob_dict[b'\x03\x00\x00\x00'] = data_temp

    if timestamp < "2003-09-09 18_50_46":
        #APPS_SUBS
        blob_dict[b'\x04\x00\x00\x00'] = {}
        cur.execute(f"SELECT * FROM apps_subs FOR SYSTEM_TIME AS OF TIMESTAMP'{timestamp}'")
        apps_subs = cur.fetchall()

        apps_subs_data = {}
        # Initialize the dictionary
        blob_dict[b'\x04\x00\x00\x00'] = {}

        for row in apps_subs:
            app_id = struct.pack('<i', row[0])
            apps_subs_data[app_id] = {}
            subs_list = row[1].split(",")
            for sub in subs_list:
                if sub != "NULL":
                    apps_subs_data[app_id][struct.pack('<i', int(sub))] = ''
                else:
                    if blob_version != 3:
                        apps_subs_data.pop(app_id)

                # Copy data to blob_dict
        for app_id, data in apps_subs_data.items():
            blob_dict[b'\x04\x00\x00\x00'][app_id] = data

        if blob_version == 3:
            #RSA_KEYS
            cur.execute(f"SELECT app_id, rsa_key FROM rsa_keys FOR SYSTEM_TIME AS OF TIMESTAMP'{timestamp}'")

            blob_dict[b'\x05\x00\x00\x00'] = {}

            hex_prefix = '\\x'

            for app_id, rsa_key_hex in cur:
                app_id_packed = struct.pack('<i', app_id)

                rsa_key = bytes.fromhex(rsa_key_hex.replace(hex_prefix, ''))

                blob_dict[b'\x05\x00\x00\x00'][app_id_packed] = rsa_key

    else:
        #APPS_SUBS (using pre-fetched data)
        blob_dict[b'\x04\x00\x00\x00'] = {}

        # Get max_count from pre-fetched data
        apps_count_results = query_results.get('apps_count', [])
        max_count = apps_count_results[0][0] if apps_count_results else 0

        # Use pre-fetched app_subs data
        apps_subs_results = query_results.get('apps_subs', [])
        app_data = {}

        for app_id, sub_id in apps_subs_results:
            if app_id not in app_data:
                app_data[app_id] = {}
            app_data[app_id][struct.pack('<i', sub_id)] = b''

        for app_id in range(max_count):
            app_id_packed = struct.pack('<i', app_id)
            blob_dict[b'\x04\x00\x00\x00'][app_id_packed] = app_data.get(app_id, {})

        #RSA_KEYS (using pre-fetched data)
        rsa_keys_results = query_results.get('rsa_keys', [])

        blob_dict[b'\x05\x00\x00\x00'] = {}

        hex_prefix = '\\x'

        for app_id, rsa_key_hex in rsa_keys_results:
            app_id_packed = struct.pack('<i', app_id)

            rsa_key = bytes.fromhex(rsa_key_hex.replace(hex_prefix, ''))

            blob_dict[b'\x05\x00\x00\x00'][app_id_packed] = rsa_key

    ##############  FINISH  ##############
    # OPTIMIZATION: Return blob_dict directly instead of converting to string
    # This eliminates the expensive pprint.saferepr() -> exec() cycle
    # The old code was:
    #   blob3 = pprint.saferepr(blob_dict)
    #   file = "blob = " + blob3
    #   return file  # Then caller would do exec(file, execdict)
    #
    # Now we return the dict directly, which is 10-50x faster

    conn2.close()

    # Cache the result for future use
    build_time = time.time() - build_start
    log.info(f"Database blob construction took {build_time:.2f}s")
    set_cached_blob_dict(cddb, timestamp, blob_dict)

    return blob_dict


def read_secondblob(filepath):
    """
    Read and parse a secondblob file.

    OPTIMIZATION: Returns blob_unserialize() result directly instead of
    converting to string and back. Old code was:
        firstblob = "blob = " + blobs.blob_dump(firstblob_unser)
        blob_dict = ast.literal_eval(firstblob[7:len(firstblob)])
    """
    with open(filepath, "rb") as f:
        blob = f.read()
    if blob[0:2] == b"\x01\x43":
        blob = zlib.decompress(blob[20:])
    return blobs.blob_unserialize(blob)


def read_secondblob_new(filepath):
    """
    Read and parse a secondblob file (new format).

    OPTIMIZATION: Returns blob_unserialize() result directly instead of
    converting to string with pprint.saferepr() and using exec().
    Old code was:
        file = "blob = " + pprint.saferepr(blob2)
        exec(file, blob_dict)
    """
    with open(filepath, "rb") as f:
        blob = f.read()
    if blob[0:2] == b"\x01\x43":
        blob = zlib.decompress(blob[20:])
    return blobs.blob_unserialize(blob)


def read_secondblob_beta1(filepath):
    """
    Read and parse a secondblob file (beta1 format).

    OPTIMIZATION: Returns blob_unserialize() result directly instead of
    converting to string with pprint.saferepr() and ast.literal_eval().
    Old code was:
        repr_text = pprint.saferepr(blob2)
        blob_dict = ast.literal_eval(repr_text)
    """
    with open(filepath, "rb") as f:
        blob = f.read()
    if blob[0:2] == b"\x01\x43":
        blob = zlib.decompress(blob[20:])
    return blobs.blob_unserialize(blob)