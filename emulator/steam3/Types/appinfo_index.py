"""
AppInfo Index System for fast random-access lookups.

Index files (.aidx) are generated from neutered appinfo.vdf files
to enable O(log n) lookups by app_id without parsing the entire file.

Index files are stored alongside the neutered VDF files:
  files/cache/appinfo/2010_2011/lan/appinfo.2010-04-24.vdf.aidx
  files/cache/appinfo/2010_2011/wan/appinfo.2010-04-24.vdf.aidx
  files/cache/appinfo/2012_above/lan/appinfo.2012-01-30.vdf.aidx
  etc.
"""

import os
import struct
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, BinaryIO

log = logging.getLogger("AppInfoIndex")


# AppInfo VDF magic numbers
APPINFO_MAGIC_V1 = 0x02464456      # VDF\x02 - 2010-2012
APPINFO_MAGIC_V2_A = 0x06564424    # $DV\x06 - 2012-2014
APPINFO_MAGIC_V2_B = 0x07564425    # 2014 variant
APPINFO_MAGIC_V2_C = 0x07564426    # &DV\x07 - 2014+ with SHA
APPINFO_MAGIC_V2_D = 0x07564427    # Newer variant


@dataclass
class AppInfoIndexEntry:
    """Single app entry in the index."""
    app_id: int
    file_offset: int       # Byte offset in the VDF file where this app starts
    data_size: int         # Total bytes for this app entry (including sections)
    change_number: int     # Cached change number for quick lookup


class AppInfoIndex:
    """
    Manages .aidx index files for fast appinfo lookup.

    Index File Format (.aidx):
        Header (24 bytes):
            char[4]  magic       = "AIDX"
            uint32   version     = 1
            uint32   format      = original VDF format magic
            uint32   numApps     = number of app entries
            uint32   reserved[2] = 0 (future use)

        Entries (16 bytes each, sorted by app_id):
            uint32   app_id
            uint32   file_offset
            uint32   data_size
            uint32   change_number
    """

    MAGIC = b"AIDX"
    VERSION = 1
    HEADER_SIZE = 24
    ENTRY_SIZE = 16

    def __init__(self, index_path: str = None):
        """
        Initialize an AppInfoIndex.

        :param index_path: Path to .aidx file (optional, can set later)
        """
        self.index_path = index_path
        self.entries: Dict[int, AppInfoIndexEntry] = {}
        self.sorted_app_ids: List[int] = []
        self.format_version: int = 0
        self.vdf_path: str = None

    @classmethod
    def generate_from_vdf(cls, vdf_path: str) -> 'AppInfoIndex':
        """
        Generate an index from a neutered appinfo.vdf file.

        This parses the VDF file and records byte offsets for each app,
        allowing fast random access later.

        :param vdf_path: Path to the appinfo.vdf file
        :return: AppInfoIndex instance (not yet saved)
        """
        index = cls()
        index.vdf_path = vdf_path
        index.index_path = vdf_path + ".aidx"

        with open(vdf_path, 'rb') as f:
            # Read and validate magic
            magic_bytes = f.read(4)
            if len(magic_bytes) < 4:
                raise ValueError(f"File too short: {vdf_path}")

            magic = struct.unpack('<I', magic_bytes)[0]
            index.format_version = magic

            # Skip universe (4 bytes)
            f.read(4)

            # Parse based on format
            if magic == APPINFO_MAGIC_V1:
                index._parse_v1_for_index(f)
            elif magic in (APPINFO_MAGIC_V2_A, APPINFO_MAGIC_V2_B):
                index._parse_v2_for_index(f)
            elif magic in (APPINFO_MAGIC_V2_C, APPINFO_MAGIC_V2_D):
                index._parse_v2_plus_for_index(f)
            else:
                raise ValueError(f"Unknown appinfo format: 0x{magic:08X}")

        # Sort app IDs for binary search
        index.sorted_app_ids = sorted(index.entries.keys())

        log.info(f"Generated index for {vdf_path}: {len(index.entries)} apps")
        return index

    def _parse_v1_for_index(self, f: BinaryIO):
        """Parse V1 format (2010-2012) to build index."""
        while True:
            # Record position before reading appId
            app_start = f.tell()

            app_id_bytes = f.read(4)
            if len(app_id_bytes) < 4:
                break

            app_id = struct.unpack('<I', app_id_bytes)[0]
            if app_id == 0:
                break

            # Read state, lastChange, changeNumber (12 bytes)
            header_data = f.read(12)
            if len(header_data) < 12:
                break

            state, last_change, change_number = struct.unpack('<III', header_data)

            # Skip sections until we hit terminator (0x00)
            self._skip_sections(f)

            # Calculate data size
            app_end = f.tell()
            data_size = app_end - app_start

            # Store entry
            self.entries[app_id] = AppInfoIndexEntry(
                app_id=app_id,
                file_offset=app_start,
                data_size=data_size,
                change_number=change_number
            )

    def _parse_v2_for_index(self, f: BinaryIO):
        """Parse V2 format (2012-2014) to build index."""
        while True:
            app_start = f.tell()

            app_id_bytes = f.read(4)
            if len(app_id_bytes) < 4:
                break

            app_id = struct.unpack('<I', app_id_bytes)[0]
            if app_id == 0:
                break

            # Read size prefix
            size_bytes = f.read(4)
            if len(size_bytes) < 4:
                break
            size = struct.unpack('<I', size_bytes)[0]

            # Read state, lastChange, changeNumber from the data
            header_data = f.read(12)
            if len(header_data) < 12:
                break

            state, last_change, change_number = struct.unpack('<III', header_data)

            # Skip remaining data (size - 12 bytes we already read)
            remaining = size - 12
            if remaining > 0:
                f.seek(remaining, 1)  # SEEK_CUR

            # Calculate total size (appId + size + data)
            app_end = f.tell()
            data_size = app_end - app_start

            self.entries[app_id] = AppInfoIndexEntry(
                app_id=app_id,
                file_offset=app_start,
                data_size=data_size,
                change_number=change_number
            )

    def _parse_v2_plus_for_index(self, f: BinaryIO):
        """Parse V2+ format (2014+) with token and SHA to build index."""
        while True:
            app_start = f.tell()

            app_id_bytes = f.read(4)
            if len(app_id_bytes) < 4:
                break

            app_id = struct.unpack('<I', app_id_bytes)[0]
            if app_id == 0:
                break

            # Read size prefix
            size_bytes = f.read(4)
            if len(size_bytes) < 4:
                break
            size = struct.unpack('<I', size_bytes)[0]

            # Read state, lastChange (8 bytes)
            f.read(8)

            # Read token (8 bytes) and SHA (20 bytes) = 28 bytes
            f.read(28)

            # Read changeNumber
            change_bytes = f.read(4)
            if len(change_bytes) < 4:
                break
            change_number = struct.unpack('<I', change_bytes)[0]

            # Skip remaining data
            # V2+ header inside data: state(4) + lastChange(4) + token(8) + sha(20) + changeNumber(4) = 40
            remaining = size - 40
            if remaining > 0:
                f.seek(remaining, 1)

            app_end = f.tell()
            data_size = app_end - app_start

            self.entries[app_id] = AppInfoIndexEntry(
                app_id=app_id,
                file_offset=app_start,
                data_size=data_size,
                change_number=change_number
            )

    def _skip_sections(self, f: BinaryIO):
        """Skip through sections until hitting terminator (0x00)."""
        while True:
            section_type = f.read(1)
            if len(section_type) == 0 or section_type[0] == 0:
                break
            # Skip KeyValues data until end marker (0x08)
            self._skip_keyvalues(f)

    def _skip_keyvalues(self, f: BinaryIO):
        """Skip a KeyValues structure."""
        while True:
            value_type = f.read(1)
            if len(value_type) == 0:
                break

            vtype = value_type[0]
            if vtype == 0x08:  # End marker
                break

            # Skip name (null-terminated string)
            self._skip_string(f)

            if vtype == 0x00:  # Nested key
                self._skip_keyvalues(f)
            elif vtype == 0x01:  # String
                self._skip_string(f)
            elif vtype == 0x02:  # Int32
                f.read(4)
            elif vtype == 0x03:  # Float
                f.read(4)
            elif vtype == 0x05:  # Wide string
                self._skip_wstring(f)
            elif vtype == 0x06:  # Color (3 bytes)
                f.read(3)
            elif vtype == 0x07:  # UInt64
                f.read(8)
            else:
                # Unknown type, try to continue
                log.warning(f"Unknown KeyValue type: {vtype}")
                break

    def _skip_string(self, f: BinaryIO):
        """Skip a null-terminated string."""
        while True:
            b = f.read(1)
            if len(b) == 0 or b[0] == 0:
                break

    def _skip_wstring(self, f: BinaryIO):
        """Skip a null-terminated wide string."""
        while True:
            w = f.read(2)
            if len(w) < 2:
                break
            if w[0] == 0 and w[1] == 0:
                break

    def load(self) -> bool:
        """
        Load index from .aidx file.

        :return: True if loaded successfully, False otherwise
        """
        if not self.index_path or not os.path.exists(self.index_path):
            return False

        try:
            with open(self.index_path, 'rb') as f:
                # Read header
                header = f.read(self.HEADER_SIZE)
                if len(header) < self.HEADER_SIZE:
                    return False

                magic = header[0:4]
                if magic != self.MAGIC:
                    log.warning(f"Invalid index magic: {magic}")
                    return False

                version, format_ver, num_apps = struct.unpack('<III', header[4:16])

                if version != self.VERSION:
                    log.warning(f"Unsupported index version: {version}")
                    return False

                self.format_version = format_ver

                # Read entries
                self.entries.clear()
                for _ in range(num_apps):
                    entry_data = f.read(self.ENTRY_SIZE)
                    if len(entry_data) < self.ENTRY_SIZE:
                        break

                    app_id, file_offset, data_size, change_number = struct.unpack(
                        '<IIII', entry_data
                    )

                    self.entries[app_id] = AppInfoIndexEntry(
                        app_id=app_id,
                        file_offset=file_offset,
                        data_size=data_size,
                        change_number=change_number
                    )

                self.sorted_app_ids = sorted(self.entries.keys())
                log.debug(f"Loaded index {self.index_path}: {len(self.entries)} apps")
                return True

        except Exception as e:
            log.error(f"Failed to load index {self.index_path}: {e}")
            return False

    def save(self) -> bool:
        """
        Save index to .aidx file.

        :return: True if saved successfully, False otherwise
        """
        if not self.index_path:
            log.error("No index path set")
            return False

        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.index_path), exist_ok=True)

            with open(self.index_path, 'wb') as f:
                # Write header
                header = bytearray(self.HEADER_SIZE)
                header[0:4] = self.MAGIC
                struct.pack_into('<III', header, 4,
                                 self.VERSION,
                                 self.format_version,
                                 len(self.entries))
                # reserved[2] are already 0
                f.write(header)

                # Write entries sorted by app_id
                for app_id in sorted(self.entries.keys()):
                    entry = self.entries[app_id]
                    entry_data = struct.pack('<IIII',
                                             entry.app_id,
                                             entry.file_offset,
                                             entry.data_size,
                                             entry.change_number)
                    f.write(entry_data)

            log.info(f"Saved index {self.index_path}: {len(self.entries)} apps")
            return True

        except Exception as e:
            log.error(f"Failed to save index {self.index_path}: {e}")
            return False

    def get_app_location(self, app_id: int) -> Optional[AppInfoIndexEntry]:
        """
        Get file offset and size for an app.

        :param app_id: The app ID to look up
        :return: AppInfoIndexEntry or None if not found
        """
        return self.entries.get(app_id)

    def get_all_app_ids(self) -> List[int]:
        """
        Get sorted list of all app IDs in the index.

        :return: List of app IDs
        """
        return self.sorted_app_ids.copy()

    def get_change_number(self, app_id: int) -> Optional[int]:
        """
        Get cached change number for an app.

        :param app_id: The app ID
        :return: Change number or None if not found
        """
        entry = self.entries.get(app_id)
        return entry.change_number if entry else None

    def __len__(self) -> int:
        return len(self.entries)

    def __contains__(self, app_id: int) -> bool:
        return app_id in self.entries


def get_or_create_index(vdf_path: str, force_regenerate: bool = False) -> Optional[AppInfoIndex]:
    """
    Get an index for a VDF file, creating it if needed.

    :param vdf_path: Path to the appinfo.vdf file
    :param force_regenerate: Force regeneration even if index exists
    :return: AppInfoIndex or None on error
    """
    index_path = vdf_path + ".aidx"

    # Check if we need to regenerate
    needs_regen = force_regenerate or not os.path.exists(index_path)

    if not needs_regen:
        # Check if VDF is newer than index
        vdf_mtime = os.path.getmtime(vdf_path)
        idx_mtime = os.path.getmtime(index_path)
        if vdf_mtime > idx_mtime:
            needs_regen = True

    if needs_regen:
        try:
            index = AppInfoIndex.generate_from_vdf(vdf_path)
            index.save()
            return index
        except Exception as e:
            log.error(f"Failed to generate index for {vdf_path}: {e}")
            return None
    else:
        index = AppInfoIndex(index_path)
        if index.load():
            index.vdf_path = vdf_path
            return index
        else:
            # Index load failed, try regenerating
            try:
                index = AppInfoIndex.generate_from_vdf(vdf_path)
                index.save()
                return index
            except Exception as e:
                log.error(f"Failed to regenerate index for {vdf_path}: {e}")
                return None
