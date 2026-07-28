"""
Steam packageinfo.vdf reader.

The package cache is one file holding every package, laid out as :

    DWORD   magic       0x06565525 or 0x06565527
    DWORD   universe
    repeated {
        DWORD       packageId           0xFFFFFFFF ends the file
        BYTE[20]    sha
        DWORD       changeNumber        only in the 0x06565527 format
        ...         binary KeyValues payload
    }

The sha is the PICS version identifier steam assigns to a package, not a hash of
the bytes on disk (verified against the shipped files : no contiguous range of
the entry hashes to it), so neutering a package does not have to recompute it,
and deliberately keeps it so a client keeps treating its cached copy as current.

Source files live in files/package_schemas/, and the neutered copies land in
files/cache/packageinfo/<lan|wan>/ alongside a .pidx index, mirroring the way
appinfo is cached under files/cache/appinfo/.
"""

import logging
import os
import re
import struct
import threading
from typing import Dict, List, Optional

from utilities.binary_vdf import (BinaryVdfError, looks_like_text_vdf, read_keyvalues, skip_keyvalues,
                                  write_keyvalues)

log = logging.getLogger('PKGINFO')

# packageinfo.vdf magic numbers
PACKAGEINFO_MAGIC_V1 = 0x06565525  # no change number
PACKAGEINFO_MAGIC_V2 = 0x06565527  # with change number

PACKAGEINFO_MAGICS = (PACKAGEINFO_MAGIC_V1, PACKAGEINFO_MAGIC_V2)

PACKAGE_TERMINATOR = 0xFFFFFFFF

SOURCE_DIR = os.path.join("files", "package_schemas")
CACHE_DIR = os.path.join("files", "cache", "packageinfo")

# "packageinfo.vdf", "packageinfo_19.vdf", "packageinfo.2013-01-25.vdf"
_NAME_RE = re.compile(r'^packageinfo(?:[._-](?P<tag>[0-9._-]+))?\.vdf$', re.IGNORECASE)


class PackageInfoError(Exception):
    pass


class PackageEntry(object):
    """One package inside a packageinfo file."""

    __slots__ = ('package_id', 'sha', 'change_number', 'offset', 'size', 'payload_offset', 'payload_size')

    def __init__(self, package_id, sha, change_number, offset, size, payload_offset, payload_size):
        self.package_id = package_id
        self.sha = sha
        self.change_number = change_number
        self.offset = offset            # start of the whole entry
        self.size = size                # entry length, header included
        self.payload_offset = payload_offset
        self.payload_size = payload_size

    def __repr__(self):
        return ("PackageEntry(id=%d, change=%s, payload=%d bytes)"
                % (self.package_id, self.change_number, self.payload_size))


class PackageInfoFile(object):
    """Parsed packageinfo.vdf, with random access to individual packages."""

    def __init__(self, path):
        self.path = path
        self.magic = 0
        self.universe = 0
        self.entries: Dict[int, PackageEntry] = {}

        self._lock = threading.Lock()

        self._parse()

    def __repr__(self):
        return ("PackageInfoFile(%s, magic=0x%08X, %d packages)"
                % (os.path.basename(self.path), self.magic, len(self.entries)))

    def __len__(self):
        return len(self.entries)

    def __contains__(self, package_id):
        return int(package_id) in self.entries

    @property
    def has_change_numbers(self):
        return self.magic == PACKAGEINFO_MAGIC_V2

    # -- parsing ------------------------------------------------------------

    def _parse(self):
        with open(self.path, 'rb') as f:
            data = f.read()

        if len(data) < 8:
            raise PackageInfoError("File too short : %s" % self.path)

        if looks_like_text_vdf(data):
            raise PackageInfoError("%s is a text VDF, not a binary package cache" % self.path)

        self.magic, self.universe = struct.unpack_from('<II', data, 0)

        if self.magic not in PACKAGEINFO_MAGICS:
            raise PackageInfoError("Unknown packageinfo format : 0x%08X" % self.magic)

        header_size = 24 + (4 if self.has_change_numbers else 0)

        offset = 8
        while offset + 4 <= len(data):
            package_id = struct.unpack_from('<I', data, offset)[0]
            if package_id == PACKAGE_TERMINATOR:
                break

            if offset + header_size > len(data):
                raise PackageInfoError("Truncated package entry at %d in %s" % (offset, self.path))

            sha = data[offset + 4:offset + 24]
            change_number = struct.unpack_from('<I', data, offset + 24)[0] if self.has_change_numbers else None

            payload_offset = offset + header_size

            try:
                payload_end = skip_keyvalues(data, payload_offset)
            except BinaryVdfError as e:
                raise PackageInfoError("Corrupt package %u in %s : %s" % (package_id, self.path, e))

            self.entries[package_id] = PackageEntry(
                    package_id, sha, change_number, offset, payload_end - offset,
                    payload_offset, payload_end - payload_offset)

            offset = payload_end

        log.debug("Parsed %s", self)

    # -- lookups ------------------------------------------------------------

    def package_ids(self) -> List[int]:
        return sorted(self.entries.keys())

    def get_entry(self, package_id) -> Optional[PackageEntry]:
        return self.entries.get(int(package_id))

    def _read(self, offset, size):
        with self._lock:
            with open(self.path, 'rb') as f:
                f.seek(offset)
                return f.read(size)

    def get_raw_entry(self, package_id) -> Optional[bytes]:
        """The entry exactly as stored, header included."""
        entry = self.get_entry(package_id)
        if entry is None:
            return None
        return self._read(entry.offset, entry.size)

    def get_payload(self, package_id) -> Optional[bytes]:
        """The binary KeyValues payload of a package."""
        entry = self.get_entry(package_id)
        if entry is None:
            return None
        return self._read(entry.payload_offset, entry.payload_size)

    def get_keyvalues(self, package_id):
        """The parsed KeyValues tree of a package."""
        payload = self.get_payload(package_id)
        if payload is None:
            return None
        entries, _ = read_keyvalues(payload, 0)
        return entries

    def iter_entries(self):
        for package_id in self.package_ids():
            yield self.entries[package_id]


# ---------------------------------------------------------------------------
# writing
# ---------------------------------------------------------------------------

def build_entry_header(magic, package_id, sha, change_number):
    header = struct.pack('<I', package_id) + sha
    if magic == PACKAGEINFO_MAGIC_V2:
        header += struct.pack('<I', change_number or 0)
    return header


def write_packageinfo(path, magic, universe, packages):
    """
    Write a packageinfo file.

    packages is an iterable of (package_id, sha, change_number, payload bytes).
    """
    os.makedirs(os.path.dirname(path) or '.', exist_ok = True)

    with open(path, 'wb') as f:
        f.write(struct.pack('<II', magic, universe))

        for package_id, sha, change_number, payload in packages:
            f.write(build_entry_header(magic, package_id, sha, change_number))
            f.write(payload)

        f.write(struct.pack('<I', PACKAGE_TERMINATOR))


def serialize_package_response(magic, universe, packages):
    """Build a packageinfo image in memory, for sending straight to a client."""
    out = bytearray(struct.pack('<II', magic, universe))

    for package_id, sha, change_number, payload in packages:
        out += build_entry_header(magic, package_id, sha, change_number)
        out += payload

    out += struct.pack('<I', PACKAGE_TERMINATOR)

    return bytes(out)


# ---------------------------------------------------------------------------
# source file discovery
# ---------------------------------------------------------------------------

def parse_packageinfo_filename(filename):
    """Return the tag part of a packageinfo file name, or None if it is not one."""
    match = _NAME_RE.match(os.path.basename(filename))
    if not match:
        return None
    return match.group('tag') or ''


def find_source_files(source_dir = None):
    """Every packageinfo file in the source folder, sorted by name."""
    source_dir = source_dir or SOURCE_DIR

    if not os.path.isdir(source_dir):
        return []

    found = []
    for name in os.listdir(source_dir):
        path = os.path.join(source_dir, name)
        if os.path.isfile(path) and parse_packageinfo_filename(name) is not None:
            found.append(path)

    return sorted(found)


def _tag_sort_key(tag):
    # "" sorts first, then numeric tags in numeric order, then anything else
    if not tag:
        return (0, 0, '')
    if tag.isdigit():
        return (1, int(tag), '')
    return (2, 0, tag)


def find_closest_source_file(tag = None, source_dir = None):
    """
    Pick the source packageinfo file to serve.

    With no tag the highest numbered file wins, which is the most complete one.
    """
    files = find_source_files(source_dir)
    if not files:
        return None

    if tag is not None:
        wanted = str(tag)
        for path in files:
            if parse_packageinfo_filename(path) == wanted:
                return path
        log.warning("No packageinfo file tagged %s, falling back", wanted)

    return max(files, key = lambda path:_tag_sort_key(parse_packageinfo_filename(path)))


# ---------------------------------------------------------------------------
# cache paths, mirroring the appinfo cache layout
# ---------------------------------------------------------------------------

def get_cache_dir(is_lan, cache_dir = None):
    return os.path.join(cache_dir or CACHE_DIR, "lan" if is_lan else "wan")


def get_cache_path(source_path, is_lan, cache_dir = None):
    return os.path.join(get_cache_dir(is_lan, cache_dir), os.path.basename(source_path))
