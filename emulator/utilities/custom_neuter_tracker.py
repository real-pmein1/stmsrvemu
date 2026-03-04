"""
Custom Neuter Config Tracker

Tracks which custom neuter configuration files have been processed,
detects changes, and handles cache invalidation/re-neutering.

Also includes mod_pkg folder tracking for incremental pkg updates (merged from mod_pkg_tracker.py).
"""
import os
import json
import hashlib
import zlib
import re
import shutil
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Set

log = logging.getLogger("custom_neuter_tracker")

# Paths
TRACKING_FILE = os.path.join("files", "cache", "custom_neuter_tracking.json")
CUSTOM_NEUTER_PATH = os.path.join("files", "configs", "custom_neuter")
MOD_PKG_BASE = os.path.join("files", "mod_pkg")
CACHE_BASE = os.path.join("files", "cache")

# Config type patterns
PKG_PATTERN = re.compile(r"^(pkgsteam|pkgsteamui)_(\d+)\.json$")
PKG_RANGE_PATTERN = re.compile(r"^(pkgsteam|pkgsteamui)_(\d+)-(\d+)\.json$")
PKG_GLOBAL_PATTERN = re.compile(r"^(pkgsteam|pkgsteamui)_global\.json$")
STORAGE_SPECIFIC_PATTERN = re.compile(r"^storage_(\d+)_(\d+)\.json$")
STORAGE_GENERAL_PATTERN = re.compile(r"^storage_(\d+)\.json$")
STORAGE_GLOBAL_PATTERN = re.compile(r"^storage_global\.json$")
APPINFO_PATTERN = re.compile(r"^appinfo_(.+)\.json$")
BLOB_PATTERN = re.compile(r"^blob_(.+)\.json$")


# ============================================================================
# TRACKING STATE MANAGEMENT
# ============================================================================

def load_tracking_state() -> dict:
    """Load tracking state from JSON file."""
    if not os.path.exists(TRACKING_FILE):
        return {
            "version": 1,
            "configs": {},
            "invalidated": {"pkg": [], "storage": []},
            "mod_pkg": {}
        }

    try:
        with open(TRACKING_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
            # Ensure all keys exist for backwards compatibility
            if "mod_pkg" not in state:
                state["mod_pkg"] = {}
            if "invalidated" not in state:
                state["invalidated"] = {"pkg": [], "storage": []}
            return state
    except Exception as e:
        log.warning(f"Failed to load tracking state: {e}")
        return {
            "version": 1,
            "configs": {},
            "invalidated": {"pkg": [], "storage": []},
            "mod_pkg": {}
        }


def save_tracking_state(state: dict) -> None:
    """Persist tracking state to disk."""
    state["last_checked"] = datetime.utcnow().isoformat() + "Z"
    os.makedirs(os.path.dirname(TRACKING_FILE), exist_ok=True)
    try:
        with open(TRACKING_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        log.error(f"Failed to save tracking state: {e}")


def get_file_info(filepath: str) -> dict:
    """Get file metadata for tracking."""
    stat = os.stat(filepath)
    with open(filepath, "rb") as f:
        file_hash = hashlib.md5(f.read()).hexdigest()
    return {
        "mtime": stat.st_mtime,
        "size": stat.st_size,
        "hash": file_hash
    }


# ============================================================================
# PERIODIC CONFIG CHANGE DETECTION
# ============================================================================

import time as _time

# Global state for periodic checking
_last_config_check_time = 0.0
_CONFIG_CHECK_INTERVAL = 5.0  # Check at most every 5 seconds
_last_config_dir_mtime = 0.0


def _get_config_dir_mtime() -> float:
    """Get the modification time of the custom neuter config directory."""
    if not os.path.isdir(CUSTOM_NEUTER_PATH):
        return 0.0
    try:
        # Get max mtime of directory and all json files in it
        dir_mtime = os.path.getmtime(CUSTOM_NEUTER_PATH)
        max_mtime = dir_mtime
        for filename in os.listdir(CUSTOM_NEUTER_PATH):
            if filename.endswith(".json"):
                filepath = os.path.join(CUSTOM_NEUTER_PATH, filename)
                try:
                    file_mtime = os.path.getmtime(filepath)
                    max_mtime = max(max_mtime, file_mtime)
                except OSError:
                    pass
        return max_mtime
    except OSError:
        return 0.0


def check_configs_if_needed() -> bool:
    """
    Lightweight check if custom neuter configs have changed.

    Called during PKG validation to detect config changes between blob updates.
    Uses mtime-based detection for efficiency.

    Returns:
        True if configs were checked and changes were found/processed
        False if no check was needed or no changes found
    """
    global _last_config_check_time, _last_config_dir_mtime

    current_time = _time.time()

    # Rate limit: don't check more often than every CONFIG_CHECK_INTERVAL seconds
    if current_time - _last_config_check_time < _CONFIG_CHECK_INTERVAL:
        return False

    _last_config_check_time = current_time

    # Quick mtime check - if directory hasn't changed, skip full scan
    current_mtime = _get_config_dir_mtime()
    if current_mtime == _last_config_dir_mtime:
        return False

    _last_config_dir_mtime = current_mtime

    # Something changed - run full config check
    log.debug("Custom neuter config directory changed, running full check")
    result = check_custom_neuter_configs(is_cold_start=False)

    return bool(result.get("new") or result.get("modified") or result.get("deleted"))


# ============================================================================
# CUSTOM NEUTER CONFIG SCANNING
# ============================================================================

def scan_custom_neuter_configs() -> Dict[str, dict]:
    """Scan all current config files and return their metadata."""
    configs = {}
    if not os.path.isdir(CUSTOM_NEUTER_PATH):
        return configs

    for filename in os.listdir(CUSTOM_NEUTER_PATH):
        if filename.endswith(".json"):
            filepath = os.path.join(CUSTOM_NEUTER_PATH, filename)
            if os.path.isfile(filepath):
                try:
                    configs[filename] = get_file_info(filepath)
                except Exception as e:
                    log.warning(f"Failed to get file info for {filepath}: {e}")

    return configs


def parse_config_type(filename: str) -> Tuple[str, dict]:
    """
    Parse config filename to determine type and identifiers.

    Returns: (config_type, identifiers)
    config_type: "pkg", "pkg_range", "pkg_global", "storage", "storage_general",
                 "storage_global", "appinfo", "blob", "unknown"
    """
    # PKG specific version
    match = PKG_PATTERN.match(filename)
    if match:
        return "pkg", {"pkg_type": match.group(1), "version": int(match.group(2))}

    # PKG range
    match = PKG_RANGE_PATTERN.match(filename)
    if match:
        return "pkg_range", {
            "pkg_type": match.group(1),
            "start": int(match.group(2)),
            "end": int(match.group(3))
        }

    # PKG global
    match = PKG_GLOBAL_PATTERN.match(filename)
    if match:
        return "pkg_global", {"pkg_type": match.group(1)}

    # Storage specific (appid + version)
    match = STORAGE_SPECIFIC_PATTERN.match(filename)
    if match:
        return "storage", {"appid": int(match.group(1)), "version": int(match.group(2))}

    # Storage general (appid only, all versions)
    match = STORAGE_GENERAL_PATTERN.match(filename)
    if match:
        return "storage_general", {"appid": int(match.group(1))}

    # Storage global
    match = STORAGE_GLOBAL_PATTERN.match(filename)
    if match:
        return "storage_global", {}

    # Appinfo
    match = APPINFO_PATTERN.match(filename)
    if match:
        return "appinfo", {"identifier": match.group(1)}

    # Blob
    match = BLOB_PATTERN.match(filename)
    if match:
        return "blob", {"identifier": match.group(1)}

    return "unknown", {}


def detect_config_changes(tracked_state: dict, current_files: dict) -> Tuple[List[str], List[str], List[str]]:
    """
    Compare tracked state against current files.

    Returns: (new_configs, modified_configs, deleted_configs)
    """
    new_configs = []
    modified_configs = []
    deleted_configs = []

    tracked_configs = tracked_state.get("configs", {})

    # Find new and modified
    for filename, file_info in current_files.items():
        if filename not in tracked_configs:
            new_configs.append(filename)
        else:
            tracked = tracked_configs[filename]
            # Quick check: mtime and size
            if file_info["mtime"] != tracked.get("mtime") or file_info["size"] != tracked.get("size"):
                # Confirm with hash
                if file_info["hash"] != tracked.get("hash"):
                    modified_configs.append(filename)

    # Find deleted
    for filename in tracked_configs:
        if filename not in current_files:
            deleted_configs.append(filename)

    return new_configs, modified_configs, deleted_configs


def mark_config_processed(state: dict, filename: str, file_info: dict, affected_caches: List[str]) -> None:
    """Update tracking state for a processed config."""
    state["configs"][filename] = {
        "mtime": file_info["mtime"],
        "size": file_info["size"],
        "hash": file_info["hash"],
        "processed_at": datetime.utcnow().isoformat() + "Z",
        "affected_caches": affected_caches
    }


# ============================================================================
# CACHE INVALIDATION
# ============================================================================

def mark_invalidated(state: dict, cache_type: str, cache_ids: List[str]) -> None:
    """Mark caches for on-demand re-neutering."""
    if cache_type not in state["invalidated"]:
        state["invalidated"][cache_type] = []

    for cache_id in cache_ids:
        if cache_id not in state["invalidated"][cache_type]:
            state["invalidated"][cache_type].append(cache_id)


def clear_invalidated(state: dict, cache_type: str, cache_id: str) -> None:
    """Remove a cache from the invalidated list after re-neutering."""
    if cache_type in state["invalidated"] and cache_id in state["invalidated"][cache_type]:
        state["invalidated"][cache_type].remove(cache_id)


def is_invalidated(state: dict, cache_type: str, cache_id: str) -> bool:
    """Check if a cache is marked for re-neutering."""
    return cache_id in state.get("invalidated", {}).get(cache_type, [])


def get_cached_pkg_versions(pkg_type: str) -> List[int]:
    """Get list of cached package versions for a pkg type."""
    versions = []
    # Check internal (LAN) and external (WAN) directories
    for subdir in ["internal", "external"]:
        cache_path = os.path.join(CACHE_BASE, subdir)
        if os.path.isdir(cache_path):
            # Map pkg_type to filename prefix
            if pkg_type == "pkgsteam":
                prefix = "Steam_"
            elif pkg_type == "pkgsteamui":
                prefix = "SteamUI_"
            else:
                prefix = pkg_type + "_"

            for filename in os.listdir(cache_path):
                if filename.startswith(prefix) and filename.endswith(".pkg"):
                    try:
                        version_str = filename[len(prefix):-4]  # Remove prefix and .pkg
                        versions.append(int(version_str))
                    except ValueError:
                        pass
    return list(set(versions))


def get_cached_storage_ids() -> List[Tuple[int, int]]:
    """Get list of cached storage (appid, version) tuples."""
    storage_ids = []
    if os.path.isdir(CACHE_BASE):
        # Look for directories like "240_75"
        pattern = re.compile(r"^(\d+)_(\d+)$")
        for entry in os.listdir(CACHE_BASE):
            match = pattern.match(entry)
            if match:
                entry_path = os.path.join(CACHE_BASE, entry)
                if os.path.isdir(entry_path):
                    storage_ids.append((int(match.group(1)), int(match.group(2))))
    return storage_ids


def invalidate_pkg_cache(pkg_type: str, version: int) -> bool:
    """
    Remove cached pkg files for a specific version.

    Returns: True if files were deleted
    """
    deleted = False

    # Map pkg_type to filename
    if pkg_type == "pkgsteam":
        filename = f"Steam_{version}.pkg"
    elif pkg_type == "pkgsteamui":
        filename = f"SteamUI_{version}.pkg"
    else:
        filename = f"{pkg_type}_{version}.pkg"

    # Internal (LAN) cache
    lan_path = os.path.join(CACHE_BASE, "internal", filename)
    if os.path.exists(lan_path):
        os.remove(lan_path)
        deleted = True
        log.info(f"Invalidated LAN pkg cache: {lan_path}")

    # External (WAN) cache
    wan_path = os.path.join(CACHE_BASE, "external", filename)
    if os.path.exists(wan_path):
        os.remove(wan_path)
        deleted = True
        log.info(f"Invalidated WAN pkg cache: {wan_path}")

    # Also check betav2 subdirectories
    for subdir in ["internal/betav2", "external/betav2"]:
        beta_path = os.path.join(CACHE_BASE, subdir, filename)
        if os.path.exists(beta_path):
            os.remove(beta_path)
            deleted = True
            log.info(f"Invalidated beta pkg cache: {beta_path}")

    return deleted


def invalidate_pkg_cache_range(pkg_type: str, start: int, end: int) -> List[int]:
    """Invalidate all cached pkg versions within a range."""
    invalidated = []
    cached_versions = get_cached_pkg_versions(pkg_type)

    for version in cached_versions:
        if start <= version <= end:
            if invalidate_pkg_cache(pkg_type, version):
                invalidated.append(version)

    return invalidated


def invalidate_all_pkg_cache(pkg_type: str) -> List[int]:
    """Invalidate all cached pkgs of a type (for global configs)."""
    invalidated = []
    cached_versions = get_cached_pkg_versions(pkg_type)

    for version in cached_versions:
        if invalidate_pkg_cache(pkg_type, version):
            invalidated.append(version)

    return invalidated


def invalidate_storage_cache(appid: int, version: int) -> bool:
    """
    Remove cached storage files for a specific appid/version.

    Removes: files/cache/{appid}_{version}/ directory
    """
    cache_path = os.path.join(CACHE_BASE, f"{appid}_{version}")

    if os.path.isdir(cache_path):
        shutil.rmtree(cache_path)
        log.info(f"Invalidated storage cache: {cache_path}")
        return True

    return False


def invalidate_storage_cache_all_versions(appid: int) -> List[int]:
    """Invalidate all cached versions for a storage appid."""
    invalidated = []
    cached_storages = get_cached_storage_ids()

    for cached_appid, version in cached_storages:
        if cached_appid == appid:
            if invalidate_storage_cache(appid, version):
                invalidated.append(version)

    return invalidated


def invalidate_all_storage_cache() -> List[Tuple[int, int]]:
    """Invalidate all storage caches (for global configs)."""
    invalidated = []
    cached_storages = get_cached_storage_ids()

    for appid, version in cached_storages:
        if invalidate_storage_cache(appid, version):
            invalidated.append((appid, version))

    return invalidated


# ============================================================================
# MAIN CHECK FUNCTION
# ============================================================================

def check_custom_neuter_configs(is_cold_start: bool = False) -> dict:
    """
    Main entry point - called on cold-start and blob changes.

    Args:
        is_cold_start: True if this is during server startup

    Returns: dict with counts of processed changes
    """
    result = {
        "new": 0,
        "modified": 0,
        "deleted": 0,
        "invalidated_pkgs": [],
        "invalidated_storages": [],
        "errors": []
    }

    # 1. Load tracked state
    tracked_state = load_tracking_state()
    state_file_existed = os.path.exists(TRACKING_FILE)

    # 2. Scan current config files
    current_files = scan_custom_neuter_configs()

    if not current_files and not tracked_state.get("configs"):
        # No custom neuter configs exist and none were tracked
        log.debug("No custom neuter configs found")
        return result

    # 3. Detect changes
    new_configs, modified_configs, deleted_configs = detect_config_changes(
        tracked_state, current_files
    )

    # 4. Bootstrap handling (first run with no state file)
    if not state_file_existed and is_cold_start:
        log.info("First run: checking for untracked custom neuter configs")

        # Only process configs that have matching caches without tracking
        for filename in new_configs[:]:  # Copy list since we modify it
            config_type, identifiers = parse_config_type(filename)

            # Check if cache exists but wasn't tracked
            cache_exists = _check_cache_exists_for_config(config_type, identifiers)

            if cache_exists:
                # Cache exists but no tracking - needs re-neutering
                log.info(f"Found untracked config with existing cache: {filename}")
            else:
                # No cache, just record the config state without neutering
                mark_config_processed(
                    tracked_state, filename, current_files[filename], []
                )
                new_configs.remove(filename)

        # Save initial state for configs without caches
        save_tracking_state(tracked_state)

    # 5. Process new and modified configs
    for filename in new_configs + modified_configs:
        try:
            affected = _process_config_change(
                filename, current_files[filename], tracked_state
            )

            if filename in new_configs:
                result["new"] += 1
            else:
                result["modified"] += 1

            result["invalidated_pkgs"].extend(affected.get("pkgs", []))
            result["invalidated_storages"].extend(affected.get("storages", []))

        except Exception as e:
            result["errors"].append(f"{filename}: {str(e)}")
            log.error(f"Error processing {filename}: {e}")

    # 6. Handle deleted configs
    for filename in deleted_configs:
        try:
            _process_config_deletion(filename, tracked_state)
            result["deleted"] += 1
        except Exception as e:
            result["errors"].append(f"delete {filename}: {str(e)}")
            log.error(f"Error handling deleted config {filename}: {e}")

    # 7. Save updated state
    save_tracking_state(tracked_state)

    if result["new"] or result["modified"] or result["deleted"]:
        log.info(f"Custom neuter config changes: new={result['new']}, "
                 f"modified={result['modified']}, deleted={result['deleted']}")

    return result


def _check_cache_exists_for_config(config_type: str, identifiers: dict) -> bool:
    """Check if cache files exist for a config type."""
    if config_type == "pkg":
        pkg_type = identifiers["pkg_type"]
        version = identifiers["version"]

        # Map to filename
        if pkg_type == "pkgsteam":
            filename = f"Steam_{version}.pkg"
        elif pkg_type == "pkgsteamui":
            filename = f"SteamUI_{version}.pkg"
        else:
            filename = f"{pkg_type}_{version}.pkg"

        lan_path = os.path.join(CACHE_BASE, "internal", filename)
        wan_path = os.path.join(CACHE_BASE, "external", filename)
        return os.path.exists(lan_path) or os.path.exists(wan_path)

    elif config_type in ("storage", "storage_general"):
        appid = identifiers["appid"]
        version = identifiers.get("version")
        if version:
            cache_path = os.path.join(CACHE_BASE, f"{appid}_{version}")
            return os.path.isdir(cache_path)
        else:
            # General storage config - check if any version exists
            for cached_appid, _ in get_cached_storage_ids():
                if cached_appid == appid:
                    return True
            return False

    return False


def _process_config_change(filename: str, file_info: dict, state: dict) -> dict:
    """
    Process a new or modified config file.

    Returns: dict with affected cache IDs
    """
    affected = {"pkgs": [], "storages": []}
    config_type, identifiers = parse_config_type(filename)

    if config_type == "pkg":
        pkg_type = identifiers["pkg_type"]
        version = identifiers["version"]

        if invalidate_pkg_cache(pkg_type, version):
            affected["pkgs"].append(f"{pkg_type}_{version}")

        mark_config_processed(state, filename, file_info, affected["pkgs"])

    elif config_type == "pkg_range":
        pkg_type = identifiers["pkg_type"]
        start, end = identifiers["start"], identifiers["end"]

        invalidated = invalidate_pkg_cache_range(pkg_type, start, end)
        affected["pkgs"] = [f"{pkg_type}_{v}" for v in invalidated]

        mark_config_processed(state, filename, file_info, affected["pkgs"])

    elif config_type == "pkg_global":
        pkg_type = identifiers["pkg_type"]

        # Mark all as invalidated for on-demand re-neutering
        cached_versions = get_cached_pkg_versions(pkg_type)
        cache_ids = [f"{pkg_type}_{v}" for v in cached_versions]
        mark_invalidated(state, "pkg", cache_ids)

        log.info(f"Marked {len(cache_ids)} {pkg_type} pkgs for on-demand re-neutering")

        mark_config_processed(state, filename, file_info, cache_ids)

    elif config_type == "storage":
        appid = identifiers["appid"]
        version = identifiers["version"]

        if invalidate_storage_cache(appid, version):
            cache_id = f"{appid}_{version}"
            affected["storages"].append(cache_id)

        mark_config_processed(state, filename, file_info, affected["storages"])

    elif config_type == "storage_general":
        appid = identifiers["appid"]

        invalidated = invalidate_storage_cache_all_versions(appid)
        affected["storages"] = [f"{appid}_{v}" for v in invalidated]

        mark_config_processed(state, filename, file_info, affected["storages"])

    elif config_type == "storage_global":
        # Mark all storages as invalidated for on-demand re-neutering
        cached_storages = get_cached_storage_ids()
        cache_ids = [f"{appid}_{ver}" for appid, ver in cached_storages]
        mark_invalidated(state, "storage", cache_ids)

        log.info(f"Marked {len(cache_ids)} storages for on-demand re-neutering")

        mark_config_processed(state, filename, file_info, cache_ids)

    else:
        # Unknown or appinfo/blob types - just record without invalidation
        mark_config_processed(state, filename, file_info, [])

    return affected


def _process_config_deletion(filename: str, state: dict) -> None:
    """
    Handle a deleted config file.

    Re-neuters affected caches without the deleted rules.
    """
    tracked_config = state["configs"].get(filename, {})
    affected_caches = tracked_config.get("affected_caches", [])
    config_type, identifiers = parse_config_type(filename)

    log.info(f"Config deleted: {filename}, invalidating {len(affected_caches)} affected caches")

    # Invalidate affected caches (they will be re-neutered without the deleted rules)
    for cache_id in affected_caches:
        if config_type.startswith("pkg"):
            # Parse cache_id like "pkgsteam_45"
            match = re.match(r"(\w+)_(\d+)", cache_id)
            if match:
                pkg_type, version = match.group(1), int(match.group(2))
                invalidate_pkg_cache(pkg_type, version)

        elif config_type.startswith("storage"):
            # Parse cache_id like "240_75"
            match = re.match(r"(\d+)_(\d+)", cache_id)
            if match:
                appid, version = int(match.group(1)), int(match.group(2))
                invalidate_storage_cache(appid, version)

    # Remove from tracking
    if filename in state["configs"]:
        del state["configs"][filename]


# ============================================================================
# STORAGE RE-NEUTERING
# ============================================================================

def trigger_storage_reneuter(appid: int, version: int) -> bool:
    """
    Trigger re-neutering of a single storage.

    This is called after invalidating a storage cache when a custom neuter
    config has changed.

    Args:
        appid: The application ID
        version: The version number

    Returns:
        True if neutering was successful, False otherwise
    """
    try:
        # Import here to avoid circular imports
        from neuter import neuter_single_storage
        return neuter_single_storage(appid, version)
    except Exception as e:
        log.error(f"Failed to trigger storage re-neuter for {appid}_{version}: {e}")
        return False


# ============================================================================
# ON-DEMAND RE-NEUTERING CHECK
# ============================================================================

def check_on_demand_reneuter(cache_type: str, cache_id: str) -> bool:
    """
    Check if a cache needs on-demand re-neutering (for global config changes).

    Call this before serving a cached pkg/storage.

    Args:
        cache_type: "pkg" or "storage"
        cache_id: Cache identifier (e.g., "pkgsteam_45" or "240_75")

    Returns: True if cache was invalidated and needs re-neutering
    """
    state = load_tracking_state()

    if not is_invalidated(state, cache_type, cache_id):
        return False

    log.info(f"On-demand re-neutering needed for {cache_type} {cache_id}")

    if cache_type == "pkg":
        match = re.match(r"(\w+)_(\d+)", cache_id)
        if match:
            pkg_type, version = match.group(1), int(match.group(2))
            invalidate_pkg_cache(pkg_type, version)

    elif cache_type == "storage":
        match = re.match(r"(\d+)_(\d+)", cache_id)
        if match:
            appid, version = int(match.group(1)), int(match.group(2))
            invalidate_storage_cache(appid, version)

    # Clear from invalidated list
    clear_invalidated(state, cache_type, cache_id)
    save_tracking_state(state)

    return True


# ============================================================================
# MOD_PKG TRACKING (merged from mod_pkg_tracker.py)
# ============================================================================

def compute_crc32(filepath: str) -> str:
    """
    Compute CRC32 of a file.

    Args:
        filepath: Path to the file

    Returns:
        8-character hex string of CRC32
    """
    with open(filepath, 'rb') as f:
        crc = zlib.crc32(f.read()) & 0xffffffff
    return f"{crc:08x}"


def get_mod_pkg_files_with_crc(pkg_type: str, version: int) -> dict:
    """
    Get dict of files that should be in pkg with their CRCs.

    Scans in priority order (later overrides earlier):
    1. mod_pkg/{type}/global/
    2. mod_pkg/{type}/{start}-{end}/ (matching ranges)
    3. mod_pkg/{type}/{version}/

    Args:
        pkg_type: 'steam' or 'steamui'
        version: The pkg version number

    Returns:
        dict: {relative_path: (full_path, crc32_hex)}
    """
    files = {}
    base_path = os.path.join(MOD_PKG_BASE, pkg_type)

    if not os.path.isdir(base_path):
        return files

    def scan_dir(dir_path):
        """Scan directory recursively, adding files to the dict."""
        if not os.path.isdir(dir_path):
            return
        for root, dirs, filenames in os.walk(dir_path):
            for fname in filenames:
                full_path = os.path.join(root, fname)
                rel_path = os.path.relpath(full_path, dir_path)
                # Normalize path separators to forward slashes
                rel_path = rel_path.replace('\\', '/')
                try:
                    crc = compute_crc32(full_path)
                    files[rel_path] = (full_path, crc)
                except Exception as e:
                    log.warning(f"Failed to compute CRC for {full_path}: {e}")

    # Scan in priority order (later overrides earlier)
    # 1. Global (lowest priority)
    scan_dir(os.path.join(base_path, "global"))

    # 2. Matching range folders
    try:
        for item in os.listdir(base_path):
            if '-' not in item:
                continue
            item_path = os.path.join(base_path, item)
            if not os.path.isdir(item_path):
                continue
            try:
                start, end = map(int, item.split('-'))
                if start <= version <= end:
                    scan_dir(item_path)
            except ValueError:
                continue
    except OSError:
        pass

    # 3. Version-specific (highest priority)
    scan_dir(os.path.join(base_path, str(version)))

    return files


def load_mod_pkg_tracking(pkg_type: str, version: int) -> Optional[dict]:
    """
    Load mod_pkg tracking data from the tracking state.

    Args:
        pkg_type: 'steam' or 'steamui'
        version: The pkg version number

    Returns:
        dict: {relative_path: crc32_hex} or None if not tracked
    """
    state = load_tracking_state()
    key = f"{pkg_type}_{version}"
    return state.get("mod_pkg", {}).get(key)


def save_mod_pkg_tracking(pkg_type: str, version: int, files: dict) -> None:
    """
    Save mod_pkg tracking data to the tracking state.

    Args:
        pkg_type: 'steam' or 'steamui'
        version: The pkg version number
        files: dict {relative_path: crc32_hex}
    """
    state = load_tracking_state()
    key = f"{pkg_type}_{version}"
    if "mod_pkg" not in state:
        state["mod_pkg"] = {}
    state["mod_pkg"][key] = files
    save_tracking_state(state)


def get_tracking_file_path(pkg_cache_path: str) -> Optional[str]:
    """
    Get the pkg_type and version from a cached pkg path.

    Args:
        pkg_cache_path: Path to the cached .pkg file

    Returns:
        Tuple (pkg_type, version) or (None, None) if unknown
    """
    pkg_filename = os.path.basename(pkg_cache_path)

    if pkg_filename.startswith('Steam_'):
        pkg_type = 'steam'
        version_str = pkg_filename[6:-4]  # Remove "Steam_" and ".pkg"
    elif pkg_filename.startswith('SteamUI_'):
        pkg_type = 'steamui'
        version_str = pkg_filename[8:-4]  # Remove "SteamUI_" and ".pkg"
    elif pkg_filename.startswith('PLATFORM_'):
        pkg_type = 'steamui'  # PLATFORM is alternate name for SteamUI
        version_str = pkg_filename[9:-4]
    else:
        return None, None

    try:
        version = int(version_str)
        return pkg_type, version
    except ValueError:
        return None, None


def extract_pkg_info(filename) -> tuple:
    """
    Extract pkg_type and version from pkg filename.

    Args:
        filename: Pkg filename (str or bytes)

    Returns:
        tuple: (pkg_type, version) or (None, None) if unknown
    """
    if isinstance(filename, bytes):
        filename = filename.decode('latin-1')

    # Remove path if present
    filename = os.path.basename(filename)

    if filename.startswith('Steam_'):
        try:
            version = int(filename[6:].split('.')[0])
            return 'steam', version
        except ValueError:
            return None, None
    elif filename.startswith('SteamUI_'):
        try:
            version = int(filename[8:].split('.')[0])
            return 'steamui', version
        except ValueError:
            return None, None
    elif filename.startswith('PLATFORM_'):
        try:
            version = int(filename[9:].split('.')[0])
            return 'steamui', version
        except ValueError:
            return None, None

    return None, None


def compute_mod_pkg_changes(cached_files: dict, expected_files: dict) -> tuple:
    """
    Compare cached tracking against current mod_pkg state.

    Args:
        cached_files: {rel_path: crc} from tracking
        expected_files: {rel_path: (full_path, crc)} from mod_pkg scan

    Returns:
        tuple: (files_to_remove, files_to_add, files_to_update)
        - files_to_remove: set of rel_paths to remove from pkg
        - files_to_add: dict {rel_path: full_path} to add to pkg
        - files_to_update: dict {rel_path: full_path} to replace in pkg
    """
    cached_paths = set(cached_files.keys()) if cached_files else set()
    expected_paths = set(expected_files.keys())

    # Files in cached but not in expected = need to remove
    files_to_remove = cached_paths - expected_paths

    files_to_add = {}
    files_to_update = {}

    for rel_path in expected_paths:
        full_path, expected_crc = expected_files[rel_path]

        if rel_path not in cached_paths:
            # New file - needs to be added
            files_to_add[rel_path] = full_path
        elif cached_files.get(rel_path) != expected_crc:
            # CRC changed - file was modified, needs update
            files_to_update[rel_path] = full_path

    return files_to_remove, files_to_add, files_to_update


def apply_incremental_update(pkg_cache_path: str, pkg_type: str, version: int) -> bool:
    """
    Apply incremental updates to a cached pkg file.

    Compares tracking against current mod_pkg state and patches differences
    without doing a full rebuild.

    Args:
        pkg_cache_path: Path to cached .pkg file
        pkg_type: 'steam' or 'steamui'
        version: pkg version number

    Returns:
        True if pkg is now valid (either unchanged or successfully patched)
        False if pkg doesn't exist or couldn't be patched (needs full rebuild)
    """
    if not os.path.isfile(pkg_cache_path):
        return False  # No cached pkg exists - needs full rebuild

    # Load current tracking data
    cached_files = load_mod_pkg_tracking(pkg_type, version)

    # Get current mod_pkg state
    expected_files = get_mod_pkg_files_with_crc(pkg_type, version)

    if cached_files is None:
        # No tracking data - pkg was built before tracking system
        # This prevents unnecessary re-neutering when just switching blobs

        if not expected_files:
            # No mod_pkg files exist - accept cache as valid, establish empty baseline
            log.debug(f"No tracking data and no mod_pkg files for {pkg_cache_path}, using existing cache")
            save_mod_pkg_tracking(pkg_type, version, {})
            return True

        # There ARE mod_pkg files that need to be applied to this cached pkg
        # Treat all mod_pkg files as new additions since we have no baseline
        log.info(f"No tracking data for {pkg_cache_path}, applying {len(expected_files)} mod_pkg file(s)")

        # Import Package class here to avoid circular imports
        from utilities.packages import Package

        # Load the cached pkg
        try:
            with open(pkg_cache_path, 'rb') as f:
                pkg = Package(f.read())
        except Exception as e:
            log.error(f"Failed to load cached pkg {pkg_cache_path}: {e}")
            return False

        # Apply all mod_pkg files (treat as additions)
        for rel_path, (full_path, _) in expected_files.items():
            try:
                with open(full_path, 'rb') as f:
                    file_data = f.read()
                pkg_path = rel_path.encode('latin-1')
                pkg.put_file(pkg_path, file_data)
            except Exception as e:
                log.error(f"Failed to add file {rel_path}: {e}")
                return False

        # Save the updated pkg
        try:
            with open(pkg_cache_path, 'wb') as f:
                f.write(pkg.pack())
        except Exception as e:
            log.error(f"Failed to save updated pkg {pkg_cache_path}: {e}")
            return False

        # Establish tracking baseline
        new_tracking = {rel_path: crc for rel_path, (_, crc) in expected_files.items()}
        save_mod_pkg_tracking(pkg_type, version, new_tracking)
        log.info(f"Applied mod_pkg files and established tracking for {pkg_type} v{version}")
        return True

    # Compute what needs to change
    to_remove, to_add, to_update = compute_mod_pkg_changes(cached_files, expected_files)

    # If nothing changed, pkg is valid - fast path
    if not to_remove and not to_add and not to_update:
        return True

    # Log what we're doing
    if to_remove:
        log.info(f"Removing {len(to_remove)} file(s) from {pkg_type} v{version}: {to_remove}")
    if to_add:
        log.info(f"Adding {len(to_add)} file(s) to {pkg_type} v{version}: {set(to_add.keys())}")
    if to_update:
        log.info(f"Updating {len(to_update)} file(s) in {pkg_type} v{version}: {set(to_update.keys())}")

    # Import Package class here to avoid circular imports
    from utilities.packages import Package

    # Load the cached pkg
    try:
        with open(pkg_cache_path, 'rb') as f:
            pkg = Package(f.read())
    except Exception as e:
        log.error(f"Failed to load cached pkg {pkg_cache_path}: {e}")
        return False

    # Apply removals
    for rel_path in to_remove:
        pkg_path = rel_path.encode('latin-1')
        pkg.remove_file(pkg_path)

    # Apply additions and updates (put_file handles both)
    for rel_path, full_path in {**to_add, **to_update}.items():
        try:
            with open(full_path, 'rb') as f:
                file_data = f.read()
            pkg_path = rel_path.encode('latin-1')
            pkg.put_file(pkg_path, file_data)
        except Exception as e:
            log.error(f"Failed to add/update file {rel_path}: {e}")
            return False

    # Save the updated pkg
    try:
        with open(pkg_cache_path, 'wb') as f:
            f.write(pkg.pack())
    except Exception as e:
        log.error(f"Failed to save updated pkg {pkg_cache_path}: {e}")
        return False

    # Update tracking with new state
    new_tracking = {rel_path: crc for rel_path, (_, crc) in expected_files.items()}
    save_mod_pkg_tracking(pkg_type, version, new_tracking)

    log.info(f"Successfully patched {pkg_cache_path}")
    return True


def validate_and_update_cached_pkg(pkg_cache_path: str, pkg_type: str, version: int) -> bool:
    """
    Main entry point: validate cached pkg and apply incremental updates if needed.

    This is the function that should be called before using a cached pkg file.

    Args:
        pkg_cache_path: Path to cached .pkg file
        pkg_type: 'steam' or 'steamui'
        version: pkg version number

    Returns:
        True if cached pkg is valid/updated and ready to use
        False if pkg needs full rebuild (doesn't exist, or no tracking baseline)
    """
    return apply_incremental_update(pkg_cache_path, pkg_type, version)


def check_all_cached_pkgs():
    """
    Check and update all cached pkg files against current mod_pkg state.

    Called during startup and blob changes to ensure all cached pkgs are current.
    Uses incremental updates when possible.
    """
    cache_dirs = [
        CACHE_BASE,
        os.path.join(CACHE_BASE, 'internal'),
        os.path.join(CACHE_BASE, 'external'),
        os.path.join(CACHE_BASE, 'betav2'),
        os.path.join(CACHE_BASE, 'internal', 'betav2'),
        os.path.join(CACHE_BASE, 'external', 'betav2'),
    ]

    for cache_dir in cache_dirs:
        if not os.path.isdir(cache_dir):
            continue

        try:
            for filename in os.listdir(cache_dir):
                if not filename.endswith('.pkg'):
                    continue

                filepath = os.path.join(cache_dir, filename)
                pkg_type, version = extract_pkg_info(filename)

                if pkg_type is None:
                    continue

                # Apply incremental updates (or skip if no changes)
                apply_incremental_update(filepath, pkg_type, version)
        except OSError as e:
            log.warning(f"Failed to scan cache directory {cache_dir}: {e}")
