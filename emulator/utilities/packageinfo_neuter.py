"""
Neutering for the packageinfo caches.

Unlike a storage chunk, a packageinfo entry cannot be neutered with a flat byte
replacement. Its payload is binary KeyValues, where a string value is null
terminated, so padding a shortened replacement out to the original length ends
the string early and leaves the parser treating the padding as the next type
byte. The payload is therefore parsed, replaced inside the tree, and written
back out, which lets replacements change length safely.

The per package sha is left alone on purpose. It is the PICS version identifier
steam assigns, not a hash of the stored bytes (no contiguous range of an entry
hashes to it), so it cannot be recomputed, and keeping it means a client goes on
treating its cached copy as current instead of refetching content we already
neutered.

Neutered files land in files/cache/packageinfo/<lan|wan>/, mirroring the way the
appinfo caches are laid out under files/cache/appinfo/.
"""

import logging
import os
import re
import threading

import globalvars
from config import get_config
from utilities.binary_vdf import KV_STRING, KV_WSTRING, read_keyvalues, write_keyvalues
from utilities.packageinfo_utils import (PackageInfoFile, find_source_files, get_cache_dir, get_cache_path,
                                         write_packageinfo)

log = logging.getLogger('PKGNEUTER')

config = get_config()

_lock = threading.Lock()

# an ip, optionally followed by a port, anywhere inside a string value
_IP_PORT_RE = re.compile(rb'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(:\d{1,5})?\b')

# the valve domains a package may point a client at, with any subdomain in front
STEAM_DOMAINS = (
        b'steampowered.com',
        b'steamcommunity.com',
        b'steamstatic.com',
        b'steamcontent.com',
        b'steamgames.com',
        b'valvesoftware.com',
        b'akamaihd.net',
)

_HOST_RE = re.compile(
        rb'\b(?:[A-Za-z0-9_-]+\.)*(?:' +
        rb'|'.join(domain.replace(b'.', rb'\.') for domain in STEAM_DOMAINS) +
        rb')\b')


def get_server_ip(is_lan):
    """The address clients should be pointed at, as bytes."""
    if is_lan:
        ip = config.get("server_ip", "127.0.0.1")
    else:
        ip = config.get("public_ip", "0.0.0.0")
        if ip == "0.0.0.0":
            ip = config.get("server_ip", "127.0.0.1")

    return ip.encode('latin-1')


def get_replacement_pairs(is_lan):
    """
    The (search, replace) pairs to apply inside string values.

    Reuses the same rules the rest of the neuter runs on, so a packageinfo file
    is rewritten consistently with everything else, but without the length
    padding those rules normally carry - the payload is re-serialized, so a
    replacement is free to change length.

    Those rules are written for binary blobs, where the value being matched sits
    between null terminators, so the sentinels are trimmed off both sides. A
    KeyValues string value holds no nulls of its own.
    """
    pairs = []

    for group in (globalvars.replace_string(is_lan),
                  globalvars.replace_string_name_space(is_lan, False),
                  globalvars.replace_string_name(is_lan, False)):
        for entry in group:
            search, replace = entry[0], entry[1]
            if not search or replace is None:
                continue

            search = search.strip(b'\x00')
            replace = replace.strip(b'\x00')

            if search and search != replace and b'\x00' not in search:
                pairs.append((search, replace))

    # longest first, so a specific rule wins over a shorter one it contains
    pairs.sort(key = lambda pair:len(pair[0]), reverse = True)

    return pairs


def neuter_string_value(value, is_lan, pairs = None):
    """Neuter one string value out of a KeyValues payload."""
    if not value:
        return value

    server_ip = get_server_ip(is_lan)

    for search, replace in (pairs if pairs is not None else get_replacement_pairs(is_lan)):
        if search in value:
            value = value.replace(search, replace)

    def swap_ip(match):
        address, port = match.group(1), match.group(2) or b''
        if address == server_ip:
            return match.group(0)
        return server_ip + port

    value = _IP_PORT_RE.sub(swap_ip, value)

    # anything still pointing at a valve host has to come back to us
    value = _HOST_RE.sub(server_ip, value)

    return value


def neuter_payload(payload, is_lan, pairs = None):
    """
    Neuter a binary KeyValues payload.

    Returns (payload, changed). The tree is only re-serialized when something
    actually changed, so an untouched package keeps its exact original bytes.
    """
    entries, _ = read_keyvalues(payload, 0)

    changed = False

    for entry in entries:
        for item in entry.walk():
            if item.type == KV_STRING:
                replaced = neuter_string_value(item.value, is_lan, pairs)
                if replaced != item.value:
                    item.value = replaced
                    changed = True
            elif item.type == KV_WSTRING:
                # wide strings are utf-16le, neuter the decoded form
                try:
                    text = item.value.decode('utf-16-le')
                except UnicodeDecodeError:
                    continue
                replaced = neuter_string_value(text.encode('latin-1', errors = 'ignore'), is_lan, pairs)
                try:
                    encoded = replaced.decode('latin-1').encode('utf-16-le')
                except UnicodeError:
                    continue
                if encoded != item.value:
                    item.value = encoded
                    changed = True

    if not changed:
        return payload, False

    return write_keyvalues(entries), True


def neuter_packageinfo_file(source_path, cache_path, is_lan):
    """Neuter one packageinfo file into the cache. Returns True on success."""
    try:
        source = PackageInfoFile(source_path)
    except Exception as e:
        log.error("Cannot read %s : %s", source_path, e)
        return False

    pairs = get_replacement_pairs(is_lan)

    packages = []
    changed_packages = 0

    for entry in source.iter_entries():
        payload = source.get_payload(entry.package_id)

        try:
            payload, changed = neuter_payload(payload, is_lan, pairs)
        except Exception as e:
            log.error("Failed to neuter package %u in %s : %s", entry.package_id, source_path, e)
            return False

        if changed:
            changed_packages += 1

        packages.append((entry.package_id, entry.sha, entry.change_number, payload))

    try:
        write_packageinfo(cache_path, source.magic, source.universe, packages)
    except OSError as e:
        log.error("Failed to write %s : %s", cache_path, e)
        return False

    log.info("Neutered %s -> %s (%s) : %d of %d package(s) changed",
             os.path.basename(source_path), cache_path, "LAN" if is_lan else "WAN",
             changed_packages, len(packages))

    return True


def needs_regeneration(source_path, cache_path):
    """True when the cached copy is missing or older than its source."""
    if not os.path.isfile(cache_path) or not os.path.getsize(cache_path):
        return True
    return os.path.getmtime(source_path) > os.path.getmtime(cache_path)


def check_and_neuter_packageinfo(is_lan = None, force = False, cache_dir = None):
    """
    Bring the neutered packageinfo caches up to date.

    With no is_lan both variants are generated, the same way the appinfo caches
    are kept for LAN and WAN separately.
    """
    sides = (True, False) if is_lan is None else (bool(is_lan),)

    sources = find_source_files()
    if not sources:
        log.debug("No packageinfo source files in %s", os.path.join("files", "package_schemas"))
        return {}

    results = {}

    with _lock:
        for side in sides:
            os.makedirs(get_cache_dir(side, cache_dir), exist_ok = True)

            for source_path in sources:
                cache_path = get_cache_path(source_path, side, cache_dir)

                if not force and not needs_regeneration(source_path, cache_path):
                    results[(source_path, side)] = True
                    continue

                results[(source_path, side)] = neuter_packageinfo_file(source_path, cache_path, side)

    failed = [path for (path, _), ok in results.items() if not ok]
    if failed:
        log.error("Failed to neuter %d packageinfo file(s)", len(set(failed)))

    return results


def get_packageinfo(source_path, is_lan, cache_dir = None):
    """
    Open the neutered copy of a packageinfo file, generating it if needed.

    Falls back to the untouched source when neutering fails, so a client still
    gets its package data.
    """
    cache_path = get_cache_path(source_path, is_lan, cache_dir)

    if needs_regeneration(source_path, cache_path):
        with _lock:
            if needs_regeneration(source_path, cache_path):
                if not neuter_packageinfo_file(source_path, cache_path, is_lan):
                    log.warning("Serving un-neutered %s", source_path)
                    return PackageInfoFile(source_path)

    try:
        return PackageInfoFile(cache_path)
    except Exception as e:
        log.error("Cannot read neutered %s : %s, falling back to the source", cache_path, e)
        return PackageInfoFile(source_path)
