"""
===============================================================================
 Custom Neutering System for Steam File Types
===============================================================================

Description:
------------
This script enables automated binary patching ("neutering") of Steam-related
files such as appinfo caches, package metadata, CDR blobs, and storage chunks.

It uses declarative JSON configuration files to define what byte patterns to
search for, how to replace them, and how to pad the result if needed.

Supported file types:
  - appinfo      ?  appinfo_<id>.json / appinfo_global.json
  - pkgsteam     ?  pkgsteam_<version>.json / pkgsteam_global.json
  - pkgsteamui   ?  pkgsteamui_<version>.json / pkgsteamui_global.json
  - blob         ?  blob_global.json
  - storage      ?  storage_<appid>_<version>.json /
                    storage_<appid>.json /
                    storage_global.json

Features:
---------
- Priority-based rule loading: Specific ? General ? Global
- Pattern matching via raw byte strings or hex sequences (with optional wildcards)
- Support for offset-based replacement and fill-mode padding (null/space)
- Tag expansion for dynamic values (e.g., %CONTENT_SERVER%, %WAN_IP%)
- Smart detection of search/replace data types when not explicitly set
- Config-driven, extensible, and encoding-safe for binary manipulation

Configuration files must be placed in: files/configs/custom_neuter/

Python Version: 3.9.13 (64-bit Windows)
Encoding: 'latin-1' or 'ascii'
Created on 5/21/2025 07:15:00 PM

Author: ChatGPT, modified by a bitter, overworked goblin (Ben)
===============================================================================
"""

import json
import logging
import os
import re
import datetime

import globalvars
from config import get_config

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

CONFIG_CACHE = {}

VALID_TYPES = ["pkgsteam", "pkgsteamui", "app", "appinfo"]

# Built-in tags and their placeholder expansions
BUILT_IN_TAGS = {
    "FTP_SERVER": None,
    "TRACKER_SERVER": None,
    "MASTER_SERVER": None,
    "DIRECTORY_SERVER": None,
    "CONFIG_SERVER": None,
    "CONTENT_SERVER": None,
    "AUTH_SERVER": None,
    "CONTENTDIRECTORY_SERVER": None,
    "HARVEST_SERVER": None,
    "VAC_SERVER": None,
    "CSER_SERVER": None,
    "VALIDATION_SERVER": None,
    "CAFE_SERVER": None,
    "VTT_SERVER": None,
    "CLIENTUPDATE_SERVER": None,
    "CM_SERVER": None,
    "LAN_IP": None,
    "WAN_IP": None,
    "WAN_LAN_IP": None,
    "TIMESTAMP": None
}


def validate_tag_format(value: str, custom_tags: dict):
    """
    Validates that all tags in the given string are wrapped in '%' and are known.
    """
    while "%" in value:
        start = value.find("%")
        end = value.find("%", start + 1)
        if end == -1:
            raise ValueError(f"Unmatched '%' in tag: {value}")

        tag = value[start + 1:end]
        if tag not in BUILT_IN_TAGS and tag not in custom_tags:
            raise ValueError(f"Unknown tag '{tag}' in: {value}")

        # Remove the processed tag for the next iteration
        value = value[:start] + value[end + 1:]


def validate_hex_format(value: str):
    """
    Ensures a hex string follows the proper format: two-character groups separated by spaces.
    """
    groups = value.split()
    for group in groups:
        if len(group) != 2 or not all(c in "0123456789abcdef?" for c in group.lower()):
            raise ValueError(f"Invalid hex format: '{group}' in {value}")


def validate_replace_length(search_bytes: bytes, replace_bytes: bytes, start_position=None):
    """
    Validates that replace_bytes length does not exceed search_bytes unless start_position is specified.
    """
    if start_position is None and len(replace_bytes) > len(search_bytes):
        raise ValueError(
            f"replace_bytes length ({len(replace_bytes)}) exceeds search_bytes length ({len(search_bytes)})"
        )


def expand_tag_with_format(value: str, custom_tags: dict, islan: bool) -> bytes:
    """
    Expands all %TAG% placeholders in `value` using built?in server tags
    and any `custom_tags`.  Built?in tags map to IP:port values or raw IPs
    as defined in your config.py.

    Args:
        value:       The input string containing zero or more %TAG% entries.
        custom_tags: A dict of user?defined tags ? replacement strings.
        islan:       If True, use the local server_ip; otherwise use public_ip.

    Returns:
        A bytes object with all tags expanded.

    Raises:
        ValueError: If a %TAG% is unmatched or unknown.
    """
    cfg = get_config()
    result = bytearray()

    # Process each %TAG% in turn
    while "%" in value:
        start = value.find("%")
        end   = value.find("%", start + 1)
        if end == -1:
            raise ValueError(f"Unmatched '%' in tag: {value!r}")

        # Append any leading literal text
        literal = value[:start]
        if literal:
            result += literal.encode("latin-1")

        tag = value[start+1:end]

        # Built-in server tags ? "IP:port"
        if tag == "FTP_SERVER":
            ip   = cfg["server_ip"] if islan else cfg["public_ip"]
            port = cfg["ftp_server_port"]
            result += f"{ip}:{port}".encode("latin-1")

        elif tag == "TRACKER_SERVER":
            ip   = cfg["server_ip"] if islan else cfg["public_ip"]
            port = cfg["tracker_server_port"]
            result += f"{ip}:{port}".encode("latin-1")

        elif tag == "MASTER_SERVER":
            ip   = cfg["server_ip"] if islan else cfg["public_ip"]
            port = cfg["masterhl1_server_port"]
            result += f"{ip}:{port}".encode("latin-1")

        elif tag == "DIRECTORY_SERVER":
            ip   = cfg["server_ip"] if islan else cfg["public_ip"]
            port = cfg["dir_server_port"]
            result += f"{ip}:{port}".encode("latin-1")

        elif tag == "CONFIG_SERVER":
            ip   = cfg["server_ip"] if islan else cfg["public_ip"]
            port = cfg["config_server_port"]
            result += f"{ip}:{port}".encode("latin-1")

        elif tag == "CONTENT_SERVER":
            ip   = cfg["server_ip"] if islan else cfg["public_ip"]
            port = cfg["content_server_port"]
            result += f"{ip}:{port}".encode("latin-1")

        elif tag == "AUTH_SERVER":
            ip   = cfg["server_ip"] if islan else cfg["public_ip"]
            port = cfg["auth_server_port"]
            result += f"{ip}:{port}".encode("latin-1")

        elif tag == "CONTENTDIRECTORY_SERVER":
            ip   = cfg["server_ip"] if islan else cfg["public_ip"]
            port = cfg["contentdir_server_port"]
            result += f"{ip}:{port}".encode("latin-1")

        elif tag == "HARVEST_SERVER":
            ip   = cfg["server_ip"] if islan else cfg["public_ip"]
            port = cfg["harvest_server_port"]
            result += f"{ip}:{port}".encode("latin-1")

        elif tag == "VAC_SERVER":
            ip   = cfg["server_ip"] if islan else cfg["public_ip"]
            port = cfg["vac_server_port"]
            result += f"{ip}:{port}".encode("latin-1")

        elif tag == "CSER_SERVER":
            ip   = cfg["server_ip"] if islan else cfg["public_ip"]
            port = cfg["cser_server_port"]
            result += f"{ip}:{port}".encode("latin-1")

        elif tag == "VALIDATION_SERVER":
            ip   = cfg["server_ip"] if islan else cfg["public_ip"]
            port = cfg["validation_port"]
            result += f"{ip}:{port}".encode("latin-1")

        elif tag == "CAFE_SERVER":
            ip   = cfg["server_ip"] if islan else cfg["public_ip"]
            port = cfg["cafe_server_port"]
            result += f"{ip}:{port}".encode("latin-1")

        elif tag == "VTT_SERVER":
            ip   = cfg["server_ip"] if islan else cfg["public_ip"]
            port = cfg["vtt_server_port"]
            result += f"{ip}:{port}".encode("latin-1")

        elif tag == "CLIENTUPDATE_SERVER":
            ip   = cfg["server_ip"] if islan else cfg["public_ip"]
            port = cfg["clupd_server_port"]
            result += f"{ip}:{port}".encode("latin-1")

        elif tag == "CM_SERVER":
            ip   = cfg["server_ip"] if islan else cfg["public_ip"]
            port = cfg["cm_encrypted_server_port"]
            result += f"{ip}:{port}".encode("latin-1")

        # Raw IP tags (no port)
        elif tag == "LAN_IP":
            result += cfg["server_ip"].encode("latin-1")

        elif tag == "WAN_IP":
            result += cfg["public_ip"].encode("latin-1")

        elif tag == "WAN_LAN_IP":
            ip = cfg["server_ip"] if islan else cfg["public_ip"]
            result += ip.encode("latin-1")

        elif tag == "TIMESTAMP":
            result += datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S").encode("latin-1")

        elif tag.startswith("ENV_"):
            env_val = os.environ.get(tag[4:], "")
            result += env_val.encode("latin-1")

        # Custom user?defined tags
        elif tag in custom_tags:
            result += custom_tags[tag].encode("latin-1")

        else:
            raise ValueError(f"Unknown tag '{tag}' in: {value!r}")

        # Continue processing after the closing '%'
        value = value[end+1:]

    # Append any remaining literal text
    if value:
        result += value.encode("latin-1")

    return bytes(result)


def handle_replacements_on_file(file_path: str, replacements: list, custom_tags: dict, islan = False, dry_run = False):
    """Apply JSON replacements to a file on disk."""
    if not os.path.isfile(file_path):
        log.warning(f"File not found, skipping: {file_path}")
        return

    with open(file_path, "rb") as f:
        file_data = f.read()

    file_data = do_neuter(custom_tags, file_data, file_path, replacements, islan, dry_run=dry_run)

    if dry_run:
        return

    with open(file_path, "wb") as f:
        f.write(file_data)


# -------------------------------------------------------------------
# 1) VALID TYPES
# -------------------------------------------------------------------
#  Added blob & storage, removed the old generic "app"
VALID_TYPES = [
    "appinfo",    # appinfo_<id>.json  +  appinfo_global.json
    "pkgsteam",   # pkgsteam_<version>.json  +  pkgsteam_global.json
    "pkgsteamui", # pkgsteamui_<version>.json  +  pkgsteamui_global.json
    "blob",       # blob_global.json only
    "storage"     # storage_<appid>_<version>.json,
                  # storage_<appid>.json,
                  # storage_global.json
]

# -------------------------------------------------------------------
# 2) Guessing helper
# -------------------------------------------------------------------
HEX_RE = re.compile(r'^[0-9A-Fa-f\?]{2}(?: [0-9A-Fa-f\?]{2})*$')

def is_hex_string(s: str) -> bool:
    return bool(HEX_RE.match(s.strip()))

def hex_to_val_mask(token: str):
    """Convert a two-character hex token with ? wildcards into value and mask."""
    token = token.lower()
    if token == "??":
        return 0x00, 0x00
    hi, lo = token[0], token[1]
    val = (int(hi,16) if hi != "?" else 0) << 4 | (int(lo,16) if lo != "?" else 0)
    mask = (0xF0 if hi != "?" else 0) | (0x0F if lo != "?" else 0)
    return val, mask

def find_all_with_mask(data: bytes, values: list, masks: list):
    """Yield indices in data matching values/masks."""
    plen = len(values)
    if plen == 0:
        return []
    indexes = []
    limit = len(data) - plen + 1
    for i in range(limit):
        for j in range(plen):
            if (data[i+j] & masks[j]) != (values[j] & masks[j]):
                break
        else:
            indexes.append(i)
    return indexes

# -------------------------------------------------------------------
# 3) Enhanced process_replacement_section
# -------------------------------------------------------------------
def process_replacement_section(entry, custom_tags, islan=False):
    # keep the original text patterns around
    patt_str = entry["search_bytes"]
    repl_str = entry["replace_bytes"]

    # validate any %TAG% in the raw strings
    validate_tag_format(patt_str, custom_tags)
    validate_tag_format(repl_str, custom_tags)

    # decide data types if not explicitly set
    if "search_data_type" not in entry:
        entry["search_data_type"] = "hex" if is_hex_string(patt_str) else "bytes"
    if "replacement_data_type" not in entry:
        entry["replacement_data_type"] = "hex" if is_hex_string(repl_str) else "bytes"

    # convert into base bytes for mask calculations and precompute LAN/WAN
    def to_bytes(text, dtype, lan):
        if dtype == "hex":
            cleaned = text.replace(" ", "")
            tokens = [cleaned[i:i+2] for i in range(0, len(cleaned), 2)]
            out = bytearray()
            for tok in tokens:
                val = int(tok.replace("?", "0"), 16)
                out.append(val)
            return bytes(out)
        else:
            return expand_tag_with_format(text, custom_tags, lan)

    search_bytes = to_bytes(patt_str, entry["search_data_type"], False)
    replace_bytes = to_bytes(repl_str, entry["replacement_data_type"], False)

    entry["_search_bytes"] = {
        False: search_bytes,
        True: to_bytes(patt_str, entry["search_data_type"], True)
    }
    entry["_replace_bytes"] = {
        False: replace_bytes,
        True: to_bytes(repl_str, entry["replacement_data_type"], True)
    }

    # sanity-check hex groups
    if entry["search_data_type"] == "hex":
        validate_hex_format(patt_str)
    if entry["replacement_data_type"] == "hex":
        validate_hex_format(repl_str)

    # ensure we don?t overflow unless the rule allows an offset
    start_pos = entry.get("start_position_from_found_bytes")
    validate_replace_length(search_bytes, replace_bytes, start_pos)
    if start_pos is not None and start_pos < 0:
        raise ValueError("start_position_from_found_bytes must be >= 0")
    if start_pos is not None and start_pos + len(replace_bytes) > len(search_bytes):
        raise ValueError("start_position_from_found_bytes out of range")

    # rename
    entry["padding_type"] = entry.pop("fill_mode", "null")

    # hex search needs masks for wildcards
    if entry["search_data_type"] == "hex":
        cleaned = patt_str.replace(" ", "")
        tokens = [cleaned[i:i+2] for i in range(0, len(cleaned), 2)]
        vals = []
        masks = []
        for t in tokens:
            v, m = hex_to_val_mask(t)
            vals.append(v)
            masks.append(m)
        entry["_search_values"] = vals
        entry["_search_masks"] = masks
    else:
        entry["_search_values"] = None
        entry["_search_masks"] = None

    return entry


def parse_json(neuter_type: str, identifier: str = None):
    """
    Load in this order (if files exist):
      ? GLOBAL  ? *_global.json     (always)
      ? GENERAL ? storage_<appid>.json (only for storage)
      ? SPECIFIC?
         - exact:    <type>_<id>.json
         - ranges:   <type>_<start>-<end>.json
         - storage version: storage_<appid>_<version>.json
       (highest-priority)
    Returns (custom_tags, replacements_list).
    """
    if neuter_type not in VALID_TYPES:
        raise ValueError(f"Unsupported neuter type: {neuter_type}")

    key = (neuter_type, identifier)
    if key in CONFIG_CACHE:
        return CONFIG_CACHE[key]

    base = globalvars.custom_neuter_path
    if not os.path.isdir(base):
        return None

    def load_one(fname):
        full = os.path.join(base, fname)
        if not os.path.isfile(full):
            return {}
        try:
            with open(full, "r", encoding="latin-1") as f:
                data = json.load(f)
        except Exception as e:
            log.error(f"Failed to load {full}: {e}")
            return {}
        if not isinstance(data.get("custom_tags", {}), dict) or not isinstance(data.get("replacements", []), list):
            log.error(f"Schema error in {full}")
            return {}
        return data

    # 1) GLOBAL
    if neuter_type == "appinfo":
        global_cfg = load_one("appinfo_global.json")
    elif neuter_type in ("pkgsteam", "pkgsteamui"):
        global_cfg = load_one(f"{neuter_type}_global.json")
    elif neuter_type == "blob":
        global_cfg = load_one("blob_global.json")
    else:  # storage
        global_cfg = load_one("storage_global.json")

    # 2) GENERAL (storage only, app-wide)
    general_cfg = {}
    if neuter_type == "storage" and identifier:
        appid = identifier.split("_",1)[0]
        general_cfg = load_one(f"storage_{appid}.json")

    # 3) SPECIFIC configs (may be multiple, in priority order)
    specific_cfgs = []

    # 3a) storage version
    if neuter_type == "storage" and identifier and "_" in identifier:
        cfg = load_one(f"storage_{identifier}.json")
        if cfg:
            specific_cfgs.append(cfg)

    # 3b) appinfo exact
    if neuter_type == "appinfo" and identifier:
        cfg = load_one(f"appinfo_{identifier}.json")
        if cfg:
            specific_cfgs.append(cfg)

    # 3c) pkgsteam/pkgsteamui exact + range
    if neuter_type in ("pkgsteam", "pkgsteamui") and identifier:
        exact_fn = f"{neuter_type}_{identifier}.json"
        cfg = load_one(exact_fn)
        if cfg:
            specific_cfgs.append(cfg)
        # now any range files
        vid = int(identifier)
        for fname in sorted(os.listdir(base)):
            if not fname.startswith(f"{neuter_type}_") or not fname.endswith(".json"):
                continue
            rng = fname[len(neuter_type)+1:-5]
            m = re.match(r"^(\d+)-(\d+)$", rng)
            if m:
                start, end = map(int, m.groups())
                if start <= vid <= end:
                    cfg = load_one(fname)
                    if cfg:
                        specific_cfgs.append(cfg)

    if not global_cfg and not general_cfg and not any(specific_cfgs):
        return None

    # 4) MERGE TAGS (global ? general ? each specific)
    from collections import OrderedDict
    custom_tags = {}
    for part in (global_cfg, general_cfg, *specific_cfgs):
        custom_tags.update(part.get("custom_tags", {}))

    # 5) COLLECT REPLACEMENTS with precedence
    merged = OrderedDict()

    def add_entries(entries):
        for entry in entries:
            key = (entry.get("filename"), entry.get("search_bytes"), entry.get("start_position_from_found_bytes"))
            merged[key] = process_replacement_section(entry, custom_tags)

    # lowest priority first
    add_entries(global_cfg.get("replacements", []))
    add_entries(general_cfg.get("replacements", []))
    for part in specific_cfgs:
        add_entries(part.get("replacements", []))

    out_list = list(merged.values())

    result = (custom_tags, out_list)
    CONFIG_CACHE[key] = result
    return result


def do_neuter(custom_tags, file_pointer, filename, replacements, islan, dry_run=False):
    # normalize filename to a str for comparison
    file_str = filename.decode('latin-1') if isinstance(filename, (bytes, bytearray)) else filename
    for rep in replacements:
        # if this replacement has a "filename" key, skip it unless it matches
        if rep.get("filename") and rep["filename"] != file_str:
            continue
        padding_type = rep.get("padding_type", "null")
        start_position = rep.get("start_position_from_found_bytes")
        case_ins = rep.get("case_insensitive", False)

        search_bytes = rep["_search_bytes"][islan]
        replace_bytes = rep["_replace_bytes"][islan]

        if rep["search_data_type"] == "hex":
            indexes = find_all_with_mask(file_pointer, rep["_search_values"], rep["_search_masks"])
        else:
            haystack = file_pointer.lower() if case_ins else file_pointer
            needle = search_bytes.lower() if case_ins else search_bytes
            indexes = []
            pos = 0
            while True:
                idx = haystack.find(needle, pos)
                if idx == -1:
                    break
                indexes.append(idx)
                pos = idx + 1

        for index in reversed(indexes):
            if start_position is not None:
                position = index + start_position
                if dry_run:
                    log.debug(f"[DRY-RUN] {filename} offset {position}")
                    continue
                file_pointer = (file_pointer[:position] + replace_bytes +
                                file_pointer[position + len(replace_bytes):])
            else:
                padding = b"\x00" if padding_type == "null" else b" "
                padded_replace = replace_bytes + padding * (len(search_bytes) - len(replace_bytes))
                if dry_run:
                    log.debug(f"[DRY-RUN] {filename} offset {index}")
                    continue
                file_pointer = (file_pointer[:index] + padded_replace +
                                file_pointer[index + len(search_bytes):])

        if indexes:
            log.debug(f"Replacement applied in {filename} at {indexes}")
    return file_pointer


# -------------------------------------------------------------------
# Config Tracking for Appinfo Neuter Configs
# -------------------------------------------------------------------

APPINFO_CONFIG_HASH_FILE = os.path.join("files", "cache", "appinfo_neuter_config.hash")


def compute_appinfo_configs_hash() -> str:
    """
    Compute a combined hash of all appinfo-related neuter config files.
    This includes appinfo_global.json and all appinfo_*.json files.

    Returns:
        A hex string representing the combined hash of all config files,
        or empty string if no configs exist.
    """
    import hashlib

    base = globalvars.custom_neuter_path
    if not os.path.isdir(base):
        return ""

    hasher = hashlib.sha256()
    config_files = []

    # Find all appinfo config files
    try:
        for fname in sorted(os.listdir(base)):
            if fname.startswith("appinfo_") and fname.endswith(".json"):
                config_files.append(fname)
    except OSError as e:
        log.warning(f"Failed to list config directory: {e}")
        return ""

    if not config_files:
        return ""

    # Hash each config file's contents
    for fname in config_files:
        full_path = os.path.join(base, fname)
        try:
            with open(full_path, "rb") as f:
                content = f.read()
            # Include filename in hash to detect renames
            hasher.update(fname.encode("utf-8"))
            hasher.update(content)
        except Exception as e:
            log.warning(f"Failed to read config file {fname}: {e}")
            continue

    return hasher.hexdigest()


def load_appinfo_config_hash() -> str:
    """
    Load the previously saved appinfo config hash from the tracking file.

    Returns:
        The saved hash string, or empty string if not found.
    """
    if not os.path.isfile(APPINFO_CONFIG_HASH_FILE):
        return ""

    try:
        with open(APPINFO_CONFIG_HASH_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        log.warning(f"Failed to read config hash file: {e}")
        return ""


def save_appinfo_config_hash(hash_value: str):
    """
    Save the appinfo config hash to the tracking file.

    Args:
        hash_value: The hash string to save.
    """
    try:
        os.makedirs(os.path.dirname(APPINFO_CONFIG_HASH_FILE), exist_ok=True)
        with open(APPINFO_CONFIG_HASH_FILE, "w", encoding="utf-8") as f:
            f.write(hash_value)
    except Exception as e:
        log.error(f"Failed to save config hash file: {e}")


def check_appinfo_configs_changed() -> bool:
    """
    Check if appinfo neuter configs have changed since last run.
    This compares the current hash of all appinfo_*.json files against
    the previously saved hash.

    Returns:
        True if configs have changed (cache should be invalidated),
        False if configs are unchanged.
    """
    current_hash = compute_appinfo_configs_hash()
    saved_hash = load_appinfo_config_hash()

    if current_hash != saved_hash:
        if current_hash:
            log.info("Appinfo neuter configs have changed - cache will be invalidated")
        return True

    return False


def invalidate_appinfo_cache():
    """
    Invalidate the appinfo cache by removing all cached neutered files.
    This forces a complete re-neuter on next check_appinfo_cache() call.
    Also clears the in-memory config cache to ensure fresh configs are loaded.
    """
    import shutil

    # Clear in-memory config cache so fresh configs are loaded
    global CONFIG_CACHE
    CONFIG_CACHE.clear()
    log.debug("Cleared in-memory config cache")

    cache_base = os.path.join("files", "cache", "appinfo")
    if not os.path.isdir(cache_base):
        return

    try:
        for item in os.listdir(cache_base):
            item_path = os.path.join(cache_base, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
                log.debug(f"Removed appinfo cache folder: {item_path}")
        log.info("Appinfo cache invalidated due to config changes")
    except Exception as e:
        log.error(f"Failed to invalidate appinfo cache: {e}")


def update_appinfo_config_tracking():
    """
    Update the appinfo config tracking hash file with current config state.
    Call this after successfully processing appinfo files.
    """
    current_hash = compute_appinfo_configs_hash()
    if current_hash:
        save_appinfo_config_hash(current_hash)
        log.debug(f"Updated appinfo config tracking hash: {current_hash[:16]}...")

