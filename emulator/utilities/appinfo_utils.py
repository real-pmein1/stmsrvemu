import os
import struct
import logging
from datetime import datetime
from typing import Optional, List, Dict, Tuple
from steam3.Types.appinfo import AppInfoParser, ApplicationData
from steam3.Types.appinfo_index import AppInfoIndex, get_or_create_index
from utilities.filesystem_utils import normalize_path

log = logging.getLogger("AppInfoUtils")

# Use os.path.join for the default cache directory
DEFAULT_APPINFO_CACHE_PATH = os.path.join(
    "files",
    "cache",
    "appinfo",
)

# Source appinfo files location (before neutering/caching)
DEFAULT_APPINFO_SOURCE_PATH = os.path.join(
    "files",
    "appcache",
)

# Cache for parsed 2010-2011 appinfo files: {file_path: AppInfoParser}
_appinfo_parser_cache: Dict[str, AppInfoParser] = {}

# Cache for app data indexed by app_id: {(file_path, app_id): ApplicationData}
_app_data_cache: Dict[Tuple[str, int], ApplicationData] = {}

# Cache for AppInfoIndex objects: {file_path: AppInfoIndex}
_appinfo_index_cache: Dict[str, AppInfoIndex] = {}

# Track the last known blob datetime to detect blob changes
_last_blob_datetime: Optional[str] = None

def find_source_appid_files_2008(source_base_path=None):
    """
    Finds the source (non-neutered) appid VDF files for 2008.
    Used by check_appinfo_cache to find files that need to be neutered.

    :param source_base_path: Base path to source files (defaults to files/appcache/2008/)
    :return: List of tuples (appid, file_path) for source files
    """
    if source_base_path is None:
        source_base_path = os.path.join(DEFAULT_APPINFO_SOURCE_PATH, "2008")

    if not os.path.isdir(source_base_path):
        return []

    appid_file_paths = []

    for file_name in os.listdir(source_base_path):
        if file_name.startswith("app_") and file_name.endswith(".vdf"):
            try:
                appid = int(file_name.split("_")[1].replace(".vdf", ""))
            except ValueError:
                continue

            file_path = normalize_path(source_base_path, file_name)
            appid_file_paths.append((appid, file_path))

    # Sort by appid
    appid_file_paths.sort(key=lambda x: x[0])

    return appid_file_paths


def find_source_appid_files_2009(start_date_str, source_base_path=None):
    """
    Finds the source (non-neutered) appid VDF files for 2009-2010 based on the start date.
    Used by check_appinfo_cache to find files that need to be neutered.

    :param start_date_str: CDR date string in format "MM/DD/YYYY HH:MM:SS"
    :param source_base_path: Base path to source files (defaults to files/appcache/2009_2010/)
    :return: List of tuples (appid, file_path) for source files
    """
    if source_base_path is None:
        source_base_path = os.path.join(DEFAULT_APPINFO_SOURCE_PATH, "2009_2010")

    # Parse the start date
    start_date = datetime.strptime(start_date_str, "%m/%d/%Y %H:%M:%S")

    # Dictionary to store the latest file path and modification time for each appid
    appid_file_paths = {}

    # Collect all directories and sort them by date/time
    if not os.path.isdir(source_base_path):
        return []

    directories = [
        d for d in os.listdir(source_base_path)
        if os.path.isdir(normalize_path(source_base_path, d)) and "_" in d
    ]

    if not directories:
        return []

    directories = sorted(directories, key=lambda d: datetime.strptime(d, "%Y-%m-%d_%H-%M"))

    # Traverse the directories
    for directory in directories:
        dir_path = normalize_path(source_base_path, directory)
        dir_date = datetime.strptime(directory, "%Y-%m-%d_%H-%M")

        # If the directory's date is after the start date, stop processing further directories
        if dir_date > start_date:
            break

        # Process files in the current directory
        for file_name in os.listdir(dir_path):
            if file_name.startswith("app_") and file_name.endswith(".vdf"):
                try:
                    appid = int(file_name.split("_")[1].replace(".vdf", ""))
                except ValueError:
                    continue

                file_path = normalize_path(dir_path, file_name)
                file_mod_time = os.path.getmtime(file_path)

                # Only keep the latest file for each appid
                if appid not in appid_file_paths or file_mod_time > appid_file_paths[appid][1]:
                    appid_file_paths[appid] = (file_path, file_mod_time)

    # Remove modification times and sort by appid
    sorted_appid_files = sorted(
        [(appid, path_time[0]) for appid, path_time in appid_file_paths.items()],
        key=lambda x: x[0]
    )

    return sorted_appid_files


def find_appid_files_2009(start_date_str, isLanConnection):
    """
    Finds the latest appid VDF files for 2009-2010 based on the start date.
    Looks in the CACHE directory for already-neutered files.
    """
    if isLanConnection:
        connFolder = "lan"
    else:
        connFolder = "wan"

    base_path = os.path.join(DEFAULT_APPINFO_CACHE_PATH, "2009_2010", connFolder)

    # Parse the start date
    start_date = datetime.strptime(start_date_str, "%m/%d/%Y %H:%M:%S")

    # Dictionary to store the latest file path and modification time for each appid
    appid_file_paths = {}

    # Collect all directories and sort them by date/time
    directories = [
        d for d in os.listdir(base_path)
        if os.path.isdir(normalize_path(base_path, d)) and "_" in d
    ]
    directories = sorted(directories, key=lambda d: datetime.strptime(d, "%Y-%m-%d_%H-%M"))

    # Traverse the directories
    for directory in directories:
        dir_path = normalize_path(base_path, directory)
        dir_date = datetime.strptime(directory, "%Y-%m-%d_%H-%M")

        # If the directory's date is after the start date, stop processing further directories
        if dir_date > start_date:
            break

        # Process files in the current directory
        for file_name in os.listdir(dir_path):
            if file_name.startswith("app_") and file_name.endswith(".vdf"):
                try:
                    appid = int(file_name.split("_")[1].replace(".vdf", ""))
                except ValueError:
                    continue

                file_path = normalize_path(dir_path, file_name)
                file_mod_time = os.path.getmtime(file_path)

                # Only keep the latest file for each appid
                if appid not in appid_file_paths or file_mod_time > appid_file_paths[appid][1]:
                    appid_file_paths[appid] = (file_path, file_mod_time)

    # Remove modification times and sort by appid
    sorted_appid_files = sorted(
        [(appid, path_time[0]) for appid, path_time in appid_file_paths.items()],
        key=lambda x: x[0]
    )

    return sorted_appid_files


def find_appid_change_numbers_2010_2011(start_date_str, isLanConnection):
    """
    For the 2010_2011 folder layout with single appinfo snapshots named:
        appinfo.YYYY-MM-DD.vdf

    1) Ensures the neutered cache for the correct source file exists
    2) Uses the index if available for fast app ID lookup
    3) Returns a sorted list of app IDs from that snapshot.
    """
    # Check for blob changes and clear caches if needed
    check_blob_change_and_clear_cache(start_date_str)

    # Use the neutering check to ensure we have the correct cached file for the CDR date
    file_path = _get_or_create_neutered_cache_2010_2011(start_date_str, isLanConnection)
    if not file_path:
        return []

    # Try to use the index for fast lookup
    index = get_cached_index(file_path)
    if index:
        return index.get_all_app_ids()

    # Fallback to full parsing
    parser = get_cached_appinfo_parser_2010_2011(file_path)
    if parser:
        return parser.get_app_ids()

    return []


def create_4byte_id_from_date(end_date):
    """
    Create a repeatable 4-byte ID based on the given date.

    :param end_date: A datetime object representing the date.
    :return: A 4-byte ID as a little-endian integer.
    """
    # Calculate total seconds since epoch (1970-01-01)
    total_seconds = int(end_date.timestamp())

    # Ensure it fits within 4 bytes (truncate if necessary)
    id_4byte = total_seconds & 0xFFFFFFFF

    # Convert to little-endian bytes
    return struct.pack('<I', id_4byte)


def find_closest_appinfo_file_2010_2011(start_date_str, isLanConnection):
    """
    For the 2010_2011 folder layout with single appinfo snapshots named:
        appinfo.YYYY-MM-DD.vdf

    Finds the snapshot whose date is closest to, but not after, start_date.
    If all snapshots are after start_date, uses the earliest snapshot.

    Returns the full path to the selected appinfo file, or None if not found.
    """
    if isLanConnection:
        connFolder = "lan"
    else:
        connFolder = "wan"

    # First check the cache directory
    cache_path = os.path.join(DEFAULT_APPINFO_CACHE_PATH, "2010_2011", connFolder)
    # Then check the source directory
    source_path = os.path.join(DEFAULT_APPINFO_SOURCE_PATH, "2010_2011")

    # Parse the start date
    start_date = datetime.strptime(start_date_str, "%m/%d/%Y %H:%M:%S")

    # Try cache first, then source
    for base_path in [cache_path, source_path]:
        if not os.path.isdir(base_path):
            continue

        candidates = []
        for file_name in os.listdir(base_path):
            if not (file_name.startswith("appinfo.") and file_name.endswith(".vdf")):
                continue

            # Extract date from filename: "appinfo.YYYY-MM-DD.vdf" or "appinfo.YYYY-MM-DD-N.vdf"
            date_part = file_name[len("appinfo."):-len(".vdf")]
            # Handle files like "appinfo.2010-04-24-1.vdf"
            date_str = date_part.rsplit("-", 1)[0] if date_part.count("-") > 2 else date_part

            try:
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                continue

            file_path = normalize_path(base_path, file_name)
            candidates.append((file_date, file_path))

        if not candidates:
            continue

        # Sort by date
        candidates.sort(key=lambda x: x[0])

        # Find the best candidate: latest snapshot with date <= start_date
        best_path = None
        for file_date, file_path in candidates:
            if file_date <= start_date:
                best_path = file_path
            else:
                break

        # If no candidate was <= start_date, use earliest
        if best_path is None:
            best_path = candidates[0][1]

        return best_path

    return None


def get_cached_appinfo_parser_2010_2011(file_path):
    """
    Returns a cached AppInfoParser for the given file, parsing it if not cached.
    """
    global _appinfo_parser_cache

    if file_path in _appinfo_parser_cache:
        return _appinfo_parser_cache[file_path]

    if not os.path.exists(file_path):
        return None

    parser = AppInfoParser(file_path)
    _appinfo_parser_cache[file_path] = parser
    return parser


def get_app_data_2010_2011(start_date_str, app_id, isLanConnection):
    """
    Gets ApplicationData for a specific app_id from the 2010-2011 single appinfo file.
    Uses caching to avoid repeated parsing.

    IMPORTANT: This function ensures the neutered cache file corresponds to the
    source file closest to (but not after) the CDR date.

    :param start_date_str: CDR date string in format "MM/DD/YYYY HH:MM:SS"
    :param app_id: The app ID to look up
    :param isLanConnection: Whether this is a LAN connection
    :return: ApplicationData object or None if not found
    """
    global _app_data_cache

    # Check for blob changes and clear caches if needed
    check_blob_change_and_clear_cache(start_date_str)

    # Use the neutering check to ensure we have the correct cached file for the CDR date
    file_path = _get_or_create_neutered_cache_2010_2011(start_date_str, isLanConnection)
    if not file_path:
        return None

    cache_key = (file_path, app_id)
    if cache_key in _app_data_cache:
        return _app_data_cache[cache_key]

    parser = get_cached_appinfo_parser_2010_2011(file_path)
    if not parser:
        return None

    app_data = parser.get_application_by_id(app_id)
    if app_data:
        _app_data_cache[cache_key] = app_data

    return app_data


def get_multiple_app_data_2010_2011(start_date_str, app_ids, isLanConnection):
    """
    Gets ApplicationData for multiple app_ids from the 2010-2011 single appinfo file.
    More efficient than calling get_app_data_2010_2011 multiple times.

    IMPORTANT: This function ensures the neutered cache file corresponds to the
    source file closest to (but not after) the CDR date.

    :param start_date_str: CDR date string in format "MM/DD/YYYY HH:MM:SS"
    :param app_ids: List of app IDs to look up
    :param isLanConnection: Whether this is a LAN connection
    :return: List of ApplicationData objects (only those found)
    """
    global _app_data_cache

    # Check for blob changes and clear caches if needed
    check_blob_change_and_clear_cache(start_date_str)

    # Use the neutering check to ensure we have the correct cached file for the CDR date
    file_path = _get_or_create_neutered_cache_2010_2011(start_date_str, isLanConnection)
    if not file_path:
        return []

    parser = get_cached_appinfo_parser_2010_2011(file_path)
    if not parser:
        return []

    results = []
    for app_id in app_ids:
        cache_key = (file_path, app_id)
        if cache_key in _app_data_cache:
            results.append(_app_data_cache[cache_key])
        else:
            app_data = parser.get_application_by_id(app_id)
            if app_data:
                _app_data_cache[cache_key] = app_data
                results.append(app_data)

    return results


def _get_or_create_neutered_cache_2010_2011(start_date_str: str, isLanConnection: bool) -> Optional[str]:
    """
    Get the path to the neutered cache file for the 2010-2011 era, creating it if needed.

    This function:
    1. Finds the source file closest to (but not after) the CDR date
    2. Checks if a neutered cache exists for that specific source file
    3. Creates the neutered cache if needed
    4. Returns the path to the neutered cache file

    :param start_date_str: CDR date string in format "MM/DD/YYYY HH:MM:SS"
    :param isLanConnection: Whether this is a LAN connection
    :return: Path to the neutered cache file, or None if failed
    """
    try:
        from utilities.appinfo_neuter import check_and_neuter_appinfo_2010_2011
        return check_and_neuter_appinfo_2010_2011(start_date_str, isLanConnection)
    except ImportError:
        # Fallback if neuter module not available - just find existing cache
        log.warning("appinfo_neuter module not available, using fallback")
        return find_closest_appinfo_file_2010_2011(start_date_str, isLanConnection)


def clear_appinfo_cache():
    """
    Clears all cached appinfo data. Useful when CDR date changes.
    """
    global _appinfo_parser_cache, _app_data_cache, _appinfo_index_cache, _last_blob_datetime
    _appinfo_parser_cache.clear()
    _app_data_cache.clear()
    _appinfo_index_cache.clear()
    _last_blob_datetime = None
    log.info("Cleared all appinfo caches")


def check_blob_change_and_clear_cache(current_blob_datetime: str) -> bool:
    """
    Check if the blob datetime has changed and clear caches if so.

    This should be called before any appinfo data retrieval to ensure
    we're using the correct data for the current blob/CDR.

    :param current_blob_datetime: Current blob datetime string (from globalvars.CDDB_datetime)
    :return: True if blob changed (caches were cleared), False otherwise
    """
    global _last_blob_datetime

    if _last_blob_datetime is None:
        # First call - just record the datetime
        _last_blob_datetime = current_blob_datetime
        return False

    if _last_blob_datetime != current_blob_datetime:
        # Blob changed - clear all caches
        log.info(f"Blob datetime changed from {_last_blob_datetime} to {current_blob_datetime}, clearing caches")
        _last_blob_datetime = current_blob_datetime
        _appinfo_parser_cache.clear()
        _app_data_cache.clear()
        _appinfo_index_cache.clear()
        return True

    return False


# =============================================================================
# Indexed Access Functions (for large appinfo files)
# =============================================================================

def get_cached_index(vdf_path: str) -> Optional[AppInfoIndex]:
    """
    Get a cached AppInfoIndex for the given VDF file, creating it if necessary.

    :param vdf_path: Path to the appinfo VDF file
    :return: AppInfoIndex or None on error
    """
    global _appinfo_index_cache

    if vdf_path in _appinfo_index_cache:
        return _appinfo_index_cache[vdf_path]

    index = get_or_create_index(vdf_path)
    if index:
        _appinfo_index_cache[vdf_path] = index

    return index


def get_app_data_indexed(vdf_path: str, app_id: int) -> Optional[ApplicationData]:
    """
    Get ApplicationData for a single app using indexed random access.
    Much faster than parsing the entire file for large appinfo files.

    :param vdf_path: Path to the appinfo VDF file
    :param app_id: The app ID to look up
    :return: ApplicationData or None if not found
    """
    global _app_data_cache

    # Check cache first
    cache_key = (vdf_path, app_id)
    if cache_key in _app_data_cache:
        return _app_data_cache[cache_key]

    # Get or create the index
    index = get_cached_index(vdf_path)
    if not index:
        log.warning(f"Could not get index for {vdf_path}")
        return None

    # Look up the app in the index
    entry = index.get_app_location(app_id)
    if not entry:
        return None

    # Read the app data using indexed access
    app_data = AppInfoParser.read_single_app_indexed(
        vdf_path,
        app_id,
        entry.file_offset,
        entry.data_size,
        index.format_version
    )

    if app_data:
        _app_data_cache[cache_key] = app_data

    return app_data


def get_multiple_app_data_indexed(vdf_path: str, app_ids: List[int]) -> List[ApplicationData]:
    """
    Get ApplicationData for multiple apps using indexed random access.

    :param vdf_path: Path to the appinfo VDF file
    :param app_ids: List of app IDs to look up
    :return: List of ApplicationData objects (only those found)
    """
    global _app_data_cache

    # Get or create the index
    index = get_cached_index(vdf_path)
    if not index:
        log.warning(f"Could not get index for {vdf_path}")
        return []

    results = []
    entries_to_read = []

    for app_id in app_ids:
        cache_key = (vdf_path, app_id)
        if cache_key in _app_data_cache:
            results.append(_app_data_cache[cache_key])
        else:
            entry = index.get_app_location(app_id)
            if entry:
                entries_to_read.append((app_id, entry.file_offset, entry.data_size))

    # Read non-cached apps in batch
    if entries_to_read:
        app_data_list = AppInfoParser.read_multiple_apps_indexed(
            vdf_path,
            entries_to_read,
            index.format_version
        )

        for app_data in app_data_list:
            cache_key = (vdf_path, app_data.app_id)
            _app_data_cache[cache_key] = app_data
            results.append(app_data)

    return results


# =============================================================================
# 2012+ Era Functions
# =============================================================================

def find_closest_appinfo_file_2012_above(start_date_str: str, isLanConnection: bool) -> Optional[str]:
    """
    For the 2012_above folder layout with single appinfo snapshots.

    :param start_date_str: CDR date string in format "MM/DD/YYYY HH:MM:SS"
    :param isLanConnection: Whether this is a LAN connection
    :return: Path to the closest appinfo file, or None if not found
    """
    connFolder = "lan" if isLanConnection else "wan"

    # Check cache directory first, then source
    cache_path = os.path.join(DEFAULT_APPINFO_CACHE_PATH, "2012_above", connFolder)
    source_path = os.path.join(DEFAULT_APPINFO_SOURCE_PATH, "2012_above")

    start_date = datetime.strptime(start_date_str, "%m/%d/%Y %H:%M:%S")

    for base_path in [cache_path, source_path]:
        if not os.path.isdir(base_path):
            continue

        candidates = []
        for file_name in os.listdir(base_path):
            if not (file_name.startswith("appinfo.") and file_name.endswith(".vdf")):
                continue

            # Extract date from filename
            date_part = file_name[len("appinfo."):-len(".vdf")]
            date_str = date_part.rsplit("-", 1)[0] if date_part.count("-") > 2 else date_part

            try:
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                continue

            file_path = normalize_path(base_path, file_name)
            candidates.append((file_date, file_path))

        if not candidates:
            continue

        candidates.sort(key=lambda x: x[0])

        # Find best candidate: latest snapshot with date <= start_date
        best_path = None
        for file_date, file_path in candidates:
            if file_date <= start_date:
                best_path = file_path
            else:
                break

        if best_path is None:
            best_path = candidates[0][1]

        return best_path

    return None


def get_app_data_2012_above(start_date_str: str, app_id: int, isLanConnection: bool) -> Optional[ApplicationData]:
    """
    Gets ApplicationData for a specific app_id from 2012+ era appinfo files.
    Uses indexed access for efficiency.

    IMPORTANT: This function ensures the neutered cache file corresponds to the
    source file closest to (but not after) the CDR date.

    :param start_date_str: CDR date string in format "MM/DD/YYYY HH:MM:SS"
    :param app_id: The app ID to look up
    :param isLanConnection: Whether this is a LAN connection
    :return: ApplicationData object or None if not found
    """
    # Check for blob changes and clear caches if needed
    check_blob_change_and_clear_cache(start_date_str)

    # Use the neutering check to ensure we have the correct cached file for the CDR date
    file_path = _get_or_create_neutered_cache_2012_above(start_date_str, isLanConnection)
    if not file_path:
        return None

    return get_app_data_indexed(file_path, app_id)


def get_multiple_app_data_2012_above(start_date_str: str, app_ids: List[int], isLanConnection: bool) -> List[ApplicationData]:
    """
    Gets ApplicationData for multiple app_ids from 2012+ era appinfo files.
    Uses indexed access for efficiency.

    IMPORTANT: This function ensures the neutered cache file corresponds to the
    source file closest to (but not after) the CDR date.

    :param start_date_str: CDR date string in format "MM/DD/YYYY HH:MM:SS"
    :param app_ids: List of app IDs to look up
    :param isLanConnection: Whether this is a LAN connection
    :return: List of ApplicationData objects (only those found)
    """
    # Check for blob changes and clear caches if needed
    check_blob_change_and_clear_cache(start_date_str)

    # Use the neutering check to ensure we have the correct cached file for the CDR date
    file_path = _get_or_create_neutered_cache_2012_above(start_date_str, isLanConnection)
    if not file_path:
        return []

    return get_multiple_app_data_indexed(file_path, app_ids)


def _get_or_create_neutered_cache_2012_above(start_date_str: str, isLanConnection: bool) -> Optional[str]:
    """
    Get the path to the neutered cache file for the 2012+ era, creating it if needed.

    This function:
    1. Finds the source file closest to (but not after) the CDR date
    2. Checks if a neutered cache exists for that specific source file
    3. Creates the neutered cache if needed
    4. Returns the path to the neutered cache file

    :param start_date_str: CDR date string in format "MM/DD/YYYY HH:MM:SS"
    :param isLanConnection: Whether this is a LAN connection
    :return: Path to the neutered cache file, or None if failed
    """
    try:
        from utilities.appinfo_neuter import check_and_neuter_appinfo_2012_above
        return check_and_neuter_appinfo_2012_above(start_date_str, isLanConnection)
    except ImportError:
        # Fallback if neuter module not available - just find existing cache
        log.warning("appinfo_neuter module not available, using fallback")
        return find_closest_appinfo_file_2012_above(start_date_str, isLanConnection)


def find_appid_change_numbers_2012_above(start_date_str: str, isLanConnection: bool) -> List[int]:
    """
    Gets a sorted list of all app IDs from the 2012+ appinfo file.

    Ensures the neutered cache for the correct source file (closest to CDR date) exists.

    :param start_date_str: CDR date string in format "MM/DD/YYYY HH:MM:SS"
    :param isLanConnection: Whether this is a LAN connection
    :return: Sorted list of app IDs
    """
    # Check for blob changes and clear caches if needed
    check_blob_change_and_clear_cache(start_date_str)

    # Use the neutering check to ensure we have the correct cached file for the CDR date
    file_path = _get_or_create_neutered_cache_2012_above(start_date_str, isLanConnection)
    if not file_path:
        return []

    # Try to use the index for fast lookup
    index = get_cached_index(file_path)
    if index:
        return index.get_all_app_ids()

    # Fallback to full parsing if index fails
    parser = get_cached_appinfo_parser_2010_2011(file_path)
    if parser:
        return parser.get_app_ids()

    return []


# =============================================================================
# Universal Era Detection and Routing
# =============================================================================

# Cutoff dates for different appinfo eras
ERA_2010_2011_START = datetime(2010, 4, 27)
ERA_2012_ABOVE_START = datetime(2012, 1, 1)


def get_appinfo_era(start_date_str: str) -> str:
    """
    Determines which era of appinfo files to use based on the CDR date.

    :param start_date_str: CDR date string in format "MM/DD/YYYY HH:MM:SS"
    :return: One of "2009_2010", "2010_2011", or "2012_above"
    """
    start_date = datetime.strptime(start_date_str, "%m/%d/%Y %H:%M:%S")

    if start_date >= ERA_2012_ABOVE_START:
        return "2012_above"
    elif start_date >= ERA_2010_2011_START:
        return "2010_2011"
    else:
        return "2009_2010"


def get_app_data_by_era(start_date_str: str, app_id: int, isLanConnection: bool) -> Optional[ApplicationData]:
    """
    Gets ApplicationData for a specific app_id, automatically selecting the correct era.

    :param start_date_str: CDR date string in format "MM/DD/YYYY HH:MM:SS"
    :param app_id: The app ID to look up
    :param isLanConnection: Whether this is a LAN connection
    :return: ApplicationData object or None if not found
    """
    era = get_appinfo_era(start_date_str)

    if era == "2012_above":
        return get_app_data_2012_above(start_date_str, app_id, isLanConnection)
    elif era == "2010_2011":
        return get_app_data_2010_2011(start_date_str, app_id, isLanConnection)
    else:
        # For 2009_2010 era, we need individual files (existing behavior)
        # This is handled by the existing functions
        return None


def get_multiple_app_data_by_era(start_date_str: str, app_ids: List[int], isLanConnection: bool) -> List[ApplicationData]:
    """
    Gets ApplicationData for multiple app_ids, automatically selecting the correct era.

    :param start_date_str: CDR date string in format "MM/DD/YYYY HH:MM:SS"
    :param app_ids: List of app IDs to look up
    :param isLanConnection: Whether this is a LAN connection
    :return: List of ApplicationData objects (only those found)
    """
    era = get_appinfo_era(start_date_str)

    if era == "2012_above":
        return get_multiple_app_data_2012_above(start_date_str, app_ids, isLanConnection)
    elif era == "2010_2011":
        return get_multiple_app_data_2010_2011(start_date_str, app_ids, isLanConnection)
    else:
        # For 2009_2010 era, individual files are used
        return []
