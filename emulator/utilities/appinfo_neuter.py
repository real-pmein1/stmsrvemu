"""
===============================================================================
AppInfo VDF Neutering with Index Generation
===============================================================================

This module provides neutering (IP address replacement) for 2010+ single appinfo
VDF files and automatic index generation for fast random access.

The neutering process:
1. Reads the source appinfo.vdf file
2. Replaces all IP addresses and server references with emulator server IPs
3. Writes the neutered file to the cache directory
4. Generates a .aidx index file for fast random access

Usage:
    from utilities.appinfo_neuter import neuter_appinfo_file, check_and_neuter_appinfo

    # Neuter a single file
    neuter_appinfo_file("files/appcache/2010_2011/appinfo.2010-04-24.vdf",
                        "files/cache/appinfo/2010_2011/lan/appinfo.2010-04-24.vdf",
                        is_lan=True)

    # Check and neuter if needed (with cache validation)
    cache_path = check_and_neuter_appinfo("04/24/2010 00:00:00", is_lan=True)

===============================================================================
"""

import os
import re
import logging
import struct
from datetime import datetime
from typing import Optional, Tuple

from config import get_config
from steam3.Types.appinfo_index import AppInfoIndex

log = logging.getLogger("AppInfoNeuter")
config = get_config()


# Patterns to search for and replace in appinfo files
# These are common Steam server references that need to be replaced
IP_PATTERNS = [
    # Standard IP:port patterns
    (rb'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d{2,5})', 'ip_port'),
    # URLs with IP addresses
    (rb'http://(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', 'url_ip'),
]

# Known Steam server hostnames that should be neutered
STEAM_HOSTNAMES = [
    b'steampowered.com',
    b'steamcommunity.com',
    b'steamstatic.com',
    b'steamgames.com',
    b'valvesoftware.com',
]


def get_server_ip(is_lan: bool) -> bytes:
    """Get the appropriate server IP based on connection type."""
    if is_lan:
        ip = config.get("server_ip", "127.0.0.1")
    else:
        public_ip = config.get("public_ip", "0.0.0.0")
        if public_ip == "0.0.0.0":
            ip = config.get("server_ip", "127.0.0.1")
        else:
            ip = public_ip
    return ip.encode('ascii')


def neuter_appinfo_bytes(data: bytes, is_lan: bool) -> bytes:
    """
    Neuter appinfo data by replacing IP addresses and server references.

    This is a simple byte-level replacement that preserves the VDF structure.
    We only replace IPs in string values (which are null-terminated).

    :param data: Raw appinfo VDF file bytes
    :param is_lan: Whether to use LAN (internal) IP
    :return: Neutered data bytes
    """
    server_ip = get_server_ip(is_lan)

    # Convert to bytearray for in-place modifications
    result = bytearray(data)

    # Replace IP:port patterns
    # This regex finds IP addresses followed by a port number
    ip_port_pattern = re.compile(rb'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d{2,5})')

    # Find all matches and their positions
    matches = list(ip_port_pattern.finditer(data))

    # Process matches in reverse order to maintain correct positions
    for match in reversed(matches):
        old_ip = match.group(1)
        port = match.group(2)

        # Skip if it's already our server IP
        if old_ip == server_ip:
            continue

        # Create replacement: our IP with the same port
        replacement = server_ip + b':' + port

        # Calculate padding needed to maintain same length
        old_len = match.end() - match.start()
        new_len = len(replacement)

        if new_len < old_len:
            # Pad with spaces to maintain length (safer for binary formats)
            replacement = replacement + b' ' * (old_len - new_len)
        elif new_len > old_len:
            # Truncate port if needed (shouldn't happen in practice)
            replacement = replacement[:old_len]

        # Apply replacement
        result[match.start():match.end()] = replacement

    return bytes(result)


def neuter_appinfo_file(source_path: str, cache_path: str, is_lan: bool) -> bool:
    """
    Neuter an appinfo VDF file and generate its index.

    :param source_path: Path to the source (un-neutered) appinfo.vdf file
    :param cache_path: Path where the neutered file should be written
    :param is_lan: Whether to use LAN (internal) IP addresses
    :return: True if successful, False otherwise
    """
    try:
        # Read source file
        with open(source_path, 'rb') as f:
            data = f.read()

        log.info(f"Neutering appinfo: {source_path} -> {cache_path} (LAN={is_lan})")

        # Neuter the data
        neutered_data = neuter_appinfo_bytes(data, is_lan)

        # Ensure cache directory exists
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)

        # Write neutered file
        with open(cache_path, 'wb') as f:
            f.write(neutered_data)

        # Generate index for the neutered file
        try:
            index = AppInfoIndex.generate_from_vdf(cache_path)
            if index.save():
                log.info(f"Generated index with {len(index)} apps: {cache_path}.aidx")
            else:
                log.warning(f"Failed to save index for {cache_path}")
        except Exception as e:
            log.error(f"Failed to generate index for {cache_path}: {e}")
            # Continue even if index fails - file is still usable

        return True

    except Exception as e:
        log.error(f"Failed to neuter appinfo file {source_path}: {e}")
        return False


def neuter_dual(source_path: str, lan_cache_path: str, wan_cache_path: str) -> Tuple[bool, bool]:
    """
    Neuter an appinfo file for both LAN and WAN in one operation.

    :param source_path: Path to the source (un-neutered) appinfo.vdf file
    :param lan_cache_path: Path for the LAN-neutered file
    :param wan_cache_path: Path for the WAN-neutered file
    :return: Tuple of (lan_success, wan_success)
    """
    try:
        # Read source file once
        with open(source_path, 'rb') as f:
            data = f.read()

        lan_success = False
        wan_success = False

        # Generate LAN version
        try:
            neutered_lan = neuter_appinfo_bytes(data, is_lan=True)
            os.makedirs(os.path.dirname(lan_cache_path), exist_ok=True)
            with open(lan_cache_path, 'wb') as f:
                f.write(neutered_lan)

            # Generate index
            index = AppInfoIndex.generate_from_vdf(lan_cache_path)
            index.save()
            lan_success = True
            log.info(f"Neutered LAN appinfo: {lan_cache_path}")
        except Exception as e:
            log.error(f"Failed to neuter LAN appinfo: {e}")

        # Generate WAN version
        try:
            neutered_wan = neuter_appinfo_bytes(data, is_lan=False)
            os.makedirs(os.path.dirname(wan_cache_path), exist_ok=True)
            with open(wan_cache_path, 'wb') as f:
                f.write(neutered_wan)

            # Generate index
            index = AppInfoIndex.generate_from_vdf(wan_cache_path)
            index.save()
            wan_success = True
            log.info(f"Neutered WAN appinfo: {wan_cache_path}")
        except Exception as e:
            log.error(f"Failed to neuter WAN appinfo: {e}")

        return lan_success, wan_success

    except Exception as e:
        log.error(f"Failed to read source file {source_path}: {e}")
        return False, False


def needs_regeneration(source_path: str, cache_path: str) -> bool:
    """
    Check if the cache file needs to be regenerated.

    :param source_path: Path to the source file
    :param cache_path: Path to the cache file
    :return: True if regeneration is needed
    """
    # Check if cache file exists
    if not os.path.exists(cache_path):
        return True

    # Check if index exists
    index_path = cache_path + ".aidx"
    if not os.path.exists(index_path):
        return True

    # Check if source is newer than cache
    try:
        source_mtime = os.path.getmtime(source_path)
        cache_mtime = os.path.getmtime(cache_path)
        if source_mtime > cache_mtime:
            return True
    except OSError:
        return True

    return False


def find_source_appinfo_2010_2011(start_date_str: str) -> Optional[str]:
    """
    Find the source appinfo.vdf file for the given date in the 2010_2011 era.

    :param start_date_str: CDR date string in format "MM/DD/YYYY HH:MM:SS"
    :return: Path to the source file or None if not found
    """
    from utilities.appinfo_utils import DEFAULT_APPINFO_SOURCE_PATH
    from utilities.filesystem_utils import normalize_path

    source_path = os.path.join(DEFAULT_APPINFO_SOURCE_PATH, "2010_2011")

    if not os.path.isdir(source_path):
        return None

    start_date = datetime.strptime(start_date_str, "%m/%d/%Y %H:%M:%S")

    candidates = []
    for file_name in os.listdir(source_path):
        if not (file_name.startswith("appinfo.") and file_name.endswith(".vdf")):
            continue

        # Extract date from filename
        date_part = file_name[len("appinfo."):-len(".vdf")]
        # Handle files like "appinfo.2010-04-24-1.vdf"
        date_str = date_part.rsplit("-", 1)[0] if date_part.count("-") > 2 else date_part

        try:
            file_date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            continue

        file_path = normalize_path(source_path, file_name)
        candidates.append((file_date, file_path))

    if not candidates:
        return None

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


def find_source_appinfo_2012_above(start_date_str: str) -> Optional[str]:
    """
    Find the source appinfo.vdf file for the given date in the 2012+ era.

    :param start_date_str: CDR date string in format "MM/DD/YYYY HH:MM:SS"
    :return: Path to the source file or None if not found
    """
    from utilities.appinfo_utils import DEFAULT_APPINFO_SOURCE_PATH
    from utilities.filesystem_utils import normalize_path

    source_path = os.path.join(DEFAULT_APPINFO_SOURCE_PATH, "2012_above")

    if not os.path.isdir(source_path):
        return None

    start_date = datetime.strptime(start_date_str, "%m/%d/%Y %H:%M:%S")

    candidates = []
    for file_name in os.listdir(source_path):
        if not (file_name.startswith("appinfo.") and file_name.endswith(".vdf")):
            continue

        date_part = file_name[len("appinfo."):-len(".vdf")]
        date_str = date_part.rsplit("-", 1)[0] if date_part.count("-") > 2 else date_part

        try:
            file_date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            continue

        file_path = normalize_path(source_path, file_name)
        candidates.append((file_date, file_path))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0])

    best_path = None
    for file_date, file_path in candidates:
        if file_date <= start_date:
            best_path = file_path
        else:
            break

    if best_path is None:
        best_path = candidates[0][1]

    return best_path


def check_and_neuter_appinfo_2010_2011(start_date_str: str, is_lan: bool) -> Optional[str]:
    """
    Check if neutered cache exists for the given date, create if needed.

    :param start_date_str: CDR date string in format "MM/DD/YYYY HH:MM:SS"
    :param is_lan: Whether to use LAN IP addresses
    :return: Path to the cached (and indexed) appinfo file, or None if failed
    """
    from utilities.appinfo_utils import DEFAULT_APPINFO_CACHE_PATH

    # Find source file
    source_path = find_source_appinfo_2010_2011(start_date_str)
    if not source_path:
        log.warning(f"No source appinfo file found for date {start_date_str}")
        return None

    # Determine cache path
    conn_folder = "lan" if is_lan else "wan"
    source_name = os.path.basename(source_path)
    cache_dir = os.path.join(DEFAULT_APPINFO_CACHE_PATH, "2010_2011", conn_folder)
    cache_path = os.path.join(cache_dir, source_name)

    # Check if regeneration is needed
    if needs_regeneration(source_path, cache_path):
        if not neuter_appinfo_file(source_path, cache_path, is_lan):
            return None

    return cache_path


def check_and_neuter_appinfo_2012_above(start_date_str: str, is_lan: bool) -> Optional[str]:
    """
    Check if neutered cache exists for the given date (2012+ era), create if needed.

    :param start_date_str: CDR date string in format "MM/DD/YYYY HH:MM:SS"
    :param is_lan: Whether to use LAN IP addresses
    :return: Path to the cached (and indexed) appinfo file, or None if failed
    """
    from utilities.appinfo_utils import DEFAULT_APPINFO_CACHE_PATH

    source_path = find_source_appinfo_2012_above(start_date_str)
    if not source_path:
        log.warning(f"No source appinfo file found for date {start_date_str} (2012+)")
        return None

    conn_folder = "lan" if is_lan else "wan"
    source_name = os.path.basename(source_path)
    cache_dir = os.path.join(DEFAULT_APPINFO_CACHE_PATH, "2012_above", conn_folder)
    cache_path = os.path.join(cache_dir, source_name)

    if needs_regeneration(source_path, cache_path):
        if not neuter_appinfo_file(source_path, cache_path, is_lan):
            return None

    return cache_path


def pregenerate_appinfo_caches(era: str = "2010_2011") -> dict:
    """
    Pre-generate all appinfo caches for faster first-request response.

    :param era: Either "2010_2011" or "2012_above"
    :return: Dict with counts: {'generated': N, 'skipped': N, 'errors': N}
    """
    from utilities.appinfo_utils import DEFAULT_APPINFO_SOURCE_PATH, DEFAULT_APPINFO_CACHE_PATH
    from utilities.filesystem_utils import normalize_path

    result = {'generated': 0, 'skipped': 0, 'errors': 0}

    source_dir = os.path.join(DEFAULT_APPINFO_SOURCE_PATH, era)
    if not os.path.isdir(source_dir):
        log.warning(f"Source directory not found: {source_dir}")
        return result

    # Find all appinfo VDF files
    vdf_files = [f for f in os.listdir(source_dir)
                 if f.startswith("appinfo.") and f.endswith(".vdf")]

    for vdf_file in vdf_files:
        source_path = normalize_path(source_dir, vdf_file)

        # Paths for LAN and WAN caches
        lan_cache = os.path.join(DEFAULT_APPINFO_CACHE_PATH, era, "lan", vdf_file)
        wan_cache = os.path.join(DEFAULT_APPINFO_CACHE_PATH, era, "wan", vdf_file)

        lan_needs = needs_regeneration(source_path, lan_cache)
        wan_needs = needs_regeneration(source_path, wan_cache)

        if not lan_needs and not wan_needs:
            result['skipped'] += 1
            continue

        try:
            if lan_needs and wan_needs:
                # Generate both at once
                lan_ok, wan_ok = neuter_dual(source_path, lan_cache, wan_cache)
                if lan_ok or wan_ok:
                    result['generated'] += 1
                else:
                    result['errors'] += 1
            else:
                # Generate just the one that's needed
                if lan_needs:
                    if neuter_appinfo_file(source_path, lan_cache, is_lan=True):
                        result['generated'] += 1
                    else:
                        result['errors'] += 1
                if wan_needs:
                    if neuter_appinfo_file(source_path, wan_cache, is_lan=False):
                        result['generated'] += 1
                    else:
                        result['errors'] += 1

        except Exception as e:
            log.error(f"Failed to pre-generate cache for {vdf_file}: {e}")
            result['errors'] += 1

    log.info(f"Pre-generation complete for {era}: {result['generated']} generated, "
             f"{result['skipped']} skipped, {result['errors']} errors")
    return result
