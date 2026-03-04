"""CONTENT DESCRIPTION RECORD OBJECT CLASS
This class is for making the record easier to work with
!!!this only works with retail 2003+ blobs!!!!!!!"""

import binascii

import importlib
import os
import struct
import xml.etree.ElementTree as ET
import zlib

from typing import Optional, Dict, Any, Union, List
class BillingTypeVar(object):
    NoCost = 0
    BillOnceOnly = 1
    BillMonthly = 2
    ProofOfPrepurchaseOnly = 3
    GuestPass = 4
    HardwarePromo = 5
    Gift = 6
    AutoGrant = 7

def convert_to_int(value) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

def convert_to_bytes(value) -> Optional[bytes]:
    if value is None:
        return None
    elif isinstance(value, int):
        # Determine the appropriate format based on the value's range
        if -0x80000000 <= value <= 0x7FFFFFFF:
            # Signed 4-byte integer
            return struct.pack("<i", value)
        elif 0 <= value <= 0xFFFFFFFF:
            # Unsigned 4-byte integer
            return struct.pack("<I", value)
        elif -0x8000000000000000 <= value <= 0x7FFFFFFFFFFFFFFF:
            # Signed 8-byte integer
            return struct.pack("<q", value)
        elif 0 <= value <= 0xFFFFFFFFFFFFFFFF:
            # Unsigned 8-byte integer
            return struct.pack("<Q", value)
        else:
            raise ValueError(f"Integer value too large to pack: {value}")
    elif isinstance(value, str):
        return value.encode("utf-8") + b"\x00"
    elif isinstance(value, bytes):
        return value
    elif isinstance(value, dict):
        return {k: convert_to_bytes(v) for k, v in value.items()}
    else:
        return None



class CDRLaunchOptionsRecord:
    def __init__(self, index, record_blob=None):
        self.index = index
        self.Description = None
        self.CommandLine = None
        self.IconIndex = None
        self.NoDesktopShortcut = None
        self.NoStartMenuShortcut = None
        self.LongRunningUnattended = None
        self.ValidOSList = None

        self.mapping = {
            b"\x01\x00\x00\x00": "Description",
            b"\x02\x00\x00\x00": "CommandLine",
            b"\x03\x00\x00\x00": "IconIndex",
            b"\x04\x00\x00\x00": "NoDesktopShortcut",
            b"\x05\x00\x00\x00": "NoStartMenuShortcut",
            b"\x06\x00\x00\x00": "LongRunningUnattended",
            b"\x07\x00\x00\x00": "ValidOSList",  # also called Platform
        }

        if record_blob:
            self.parse(record_blob)

    def to_dict(self):
        result = {}
        for key, attr in self.mapping.items():
            value = getattr(self, attr)
            if value is not None:
                if attr in ['NoDesktopShortcut', 'NoStartMenuShortcut', 'LongRunningUnattended']:
                    # Handle value that might already be bytes
                    if isinstance(value, bytes):
                        result[key] = value[:1] if len(value) >= 1 else b'\x00'
                    else:
                        result[key] = int(value).to_bytes(1, 'little')
                else:
                    result[key] = convert_to_bytes(value)
        return result

    def parse(self, record_blob):
        for key, attr in self.mapping.items():
            if key in record_blob:
                setattr(self, attr, record_blob[key])

    @staticmethod
    def from_xml(option_record):
        launch_option = CDRLaunchOptionsRecord(
            index=convert_to_bytes(int(option_record.get("LaunchOptionIdx")))
        )
        launch_option.Description = option_record.find("Description").text
        launch_option.CommandLine = option_record.find("CommandLine").text
        launch_option.IconIndex = convert_to_bytes(int(option_record.find("AppIconIdx").text))
        launch_option.NoDesktopShortcut = struct.pack('?', int(option_record.find("bNoDesktopShortcut").text))[0]
        launch_option.NoStartMenuShortcut = struct.pack('?', int(option_record.find(
            "bNoStartMenuShortcut"
        ).text))[0]
        launch_option.LongRunningUnattended = struct.pack('?', int(option_record.find(
            "bLongRunningUnattended"
        ).text))[0]
        ValidOSList_element = option_record.find("ValidOSList")
        if ValidOSList_element is not None:
            launch_option.ValidOSList = ValidOSList_element.text
        return launch_option

    def __repr__(self):
        return (
            f"CDRLaunchOptionsRecord(\n"
            f"  index={self.index},\n"
            f"  Description={self.Description},\n"
            f"  CommandLine={self.CommandLine},\n"
            f"  IconIndex={self.IconIndex},\n"
            f"  NoDesktopShortcut={self.NoDesktopShortcut},\n"
            f"  NoStartMenuShortcut={self.NoStartMenuShortcut},\n"
            f"  LongRunningUnattended={self.LongRunningUnattended},\n"
            f"  ValidOSList={self.ValidOSList}\n"
            f")"
        )


class CDRApplicationVersionRecord:
    def __init__(self, index, record_blob=None):
        self.index = index
        self.Description = None
        self.VersionId = None
        self.IsNotAvailable = None
        self.LaunchOptionIdsRecord = {}
        self.DepotEncryptionKey = None
        self.IsEncryptionKeyAvailable = None
        self.IsRebased = None
        self.IsLongVersionRoll = None
        self.mapping = {
            b"\x01\x00\x00\x00": "Description",
            b"\x02\x00\x00\x00": "VersionId",
            b"\x03\x00\x00\x00": "IsNotAvailable",
            b"\x04\x00\x00\x00": "LaunchOptionIdsRecord",
            b"\x05\x00\x00\x00": "DepotEncryptionKey",
            b"\x06\x00\x00\x00": "IsEncryptionKeyAvailable",
            b"\x07\x00\x00\x00": "IsRebased",
            b"\x08\x00\x00\x00": "IsLongVersionRoll",
        }
        if record_blob:
            self.parse(record_blob)

    def to_dict(self):
        result = {}
        for key, attr in self.mapping.items():
            value = getattr(self, attr)

            # DepotEncryptionKey should always be included (even if empty)
            if attr == "DepotEncryptionKey":
                if value is None:
                    result[key] = b'\x00'
                else:
                    result[key] = convert_to_bytes(value)
                continue

            # Skip None values for other attributes (unless required)
            if value is None:
                continue

            if attr == "LaunchOptionIdsRecord" and isinstance(value, dict):
                result[key] = {k: v for k, v in value.items()}
            elif attr == "IsLongVersionRoll":
                # IsLongVersionRoll is optional - only output if non-zero
                if isinstance(value, bytes):
                    byte_val = value[:1] if len(value) >= 1 else b'\x00'
                else:
                    byte_val = int(value).to_bytes(1, 'little')
                # Only output if non-zero
                if byte_val != b'\x00':
                    result[key] = byte_val
            elif attr in ['IsNotAvailable', 'IsEncryptionKeyAvailable', 'IsRebased']:
                # Handle value that might already be bytes
                if isinstance(value, bytes):
                    result[key] = value[:1] if len(value) >= 1 else b'\x00'
                else:
                    result[key] = int(value).to_bytes(1, 'little')
            else:
                result[key] = convert_to_bytes(value)
        return result

    def parse(self, record_blob):
        for key, attr in self.mapping.items():
            value = record_blob.get(key)
            if value is not None:
                if attr == "LaunchOptionIdsRecord" and isinstance(value, dict):
                    self.LaunchOptionIdsRecord = value
                else:
                    setattr(self, attr, value)

    @staticmethod
    def from_xml(version_record):
        version_id = convert_to_bytes(int(version_record.find("VersionId").text))
        version = CDRApplicationVersionRecord(index=version_id)
        version.VersionId = convert_to_bytes(version_id)
        version.Description = (
            version_record.find("Description").text
            if version_record.find("Description") is not None
            else None
        )
        version.IsNotAvailable = (
            struct.pack('?',int(version_record.find("bIsNotAvailable").text))[0]
            if version_record.find("bIsNotAvailable") is not None
            else None
        )
        version.IsEncryptionKeyAvailable = (
            struct.pack('?',int(version_record.find("bIsEncryptionKeyAvailable").text))[0]
            if version_record.find("bIsEncryptionKeyAvailable") is not None
            else None
        )
        version.IsRebased = (
            struct.pack('?',int(version_record.find("bIsRebased").text))[0]
            if version_record.find("bIsRebased") is not None
            else None
        )
        version.IsLongVersionRoll = (
            struct.pack('?',int(version_record.find("bIsLongVersionRoll").text))[0]
            if version_record.find("bIsLongVersionRoll") is not None
            else None
        )
        encryption_key_element = version_record.find("DepotEncryptionKey")
        version.DepotEncryptionKey = (
            encryption_key_element.text if encryption_key_element is not None else None
        )
        # Parse LaunchOptionIdsRecord
        launch_option_ids = {}
        for option_id_element in version_record.findall(
            ".//LaunchOptionIdsRecord/LaunchOptionId"
        ):
            option_id = int(option_id_element.text)
            launch_option_ids[convert_to_bytes(option_id)] = b""
        version.LaunchOptionIdsRecord = launch_option_ids
        return version

    def __repr__(self):
        return (
            f"CDRApplicationVersionRecord(\n"
            f"  index={self.index},\n"
            f"  Description={self.Description},\n"
            f"  VersionId={self.VersionId},\n"
            f"  IsNotAvailable={self.IsNotAvailable},\n"
            f"  LaunchOptionIdsRecord={self.LaunchOptionIdsRecord},\n"
            f"  DepotEncryptionKey={self.DepotEncryptionKey},\n"
            f"  IsEncryptionKeyAvailable={self.IsEncryptionKeyAvailable},\n"
            f"  IsRebased={self.IsRebased},\n"
            f"  IsLongVersionRoll={self.IsLongVersionRoll}\n"
            f")"
        )


class CDRFilesystemRecord:
    def __init__(self, index, record_blob=None):
        self.index = index
        self.AppId = None
        self.MountName = None
        self.IsOptional = None
        self.ValidOSList = None
        self.mapping = {
            b"\x01\x00\x00\x00": "AppId",
            b"\x02\x00\x00\x00": "MountName",
            b"\x03\x00\x00\x00": "IsOptional",
            b"\x04\x00\x00\x00": "ValidOSList",
        }
        if record_blob:
            self.parse(record_blob)

    def to_dict(self):
        result = {}
        for key, attr in self.mapping.items():
            value = getattr(self, attr)
            if value is not None:
                if attr == 'IsOptional':
                    # Handle value that might already be bytes
                    if isinstance(value, bytes):
                        result[key] = value[:1] if len(value) >= 1 else b'\x00'
                    else:
                        result[key] = int(value).to_bytes(1, 'little')
                else:
                    result[key] = convert_to_bytes(value)
            else:
                if attr == "MountName":
                    result[key] = b'\x00'
        return result

    def parse(self, record_blob):
        for key, attr in self.mapping.items():
            if key in record_blob:
                setattr(self, attr, record_blob[key])

    @staticmethod
    def from_xml(fs_record):
        fs_idx = convert_to_bytes(int(fs_record.get("FilesystemIdx")))
        filesystem = CDRFilesystemRecord(index=fs_idx)
        filesystem.AppId = (
            convert_to_bytes(int(fs_record.find("AppId").text))
            if fs_record.find("AppId") is not None
            else None
        )
        filesystem.MountName = (
            fs_record.find("MountName").text
            if fs_record.find("MountName") is not None
            else None
        )
        filesystem.IsOptional = (
            int(fs_record.find("IsOptional").text)
            if fs_record.find("IsOptional") is not None
            else None
        )
        ValidOSList_element = fs_record.find("ValidOSList")
        filesystem.ValidOSList = (
            ValidOSList_element.text if ValidOSList_element is not None else None
        )

        return filesystem

    def __repr__(self):
        return (
            f"CDRFilesystemRecord(\n"
            f"  index={self.index},\n"
            f"  AppId={self.AppId},\n"
            f"  MountName={self.MountName},\n"
            f"  IsOptional={self.IsOptional}\n"
            f"  ValidOSList={self.ValidOSList}\n"
            f")"
        )


class CDRAppRegionRecord:
    def __init__(self, index=0, record_blob=None):
        self.index = index  # int, corresponds to 'Idx'
        self.CountryList = ""  # string
        self.AppUserDefinedRecord = {}  # dictionary
        self.FilesystemsRecord = {}  # dictionary of CDRFilesystemRecord

        # Mapping for to_dict conversion
        self.mapping = {
            b"\x01\x00\x00\x00": "CountryList",
            b"\x02\x00\x00\x00": "AppUserDefinedRecord",
            b"\x03\x00\x00\x00": "FilesystemsRecord",
        }

        if record_blob:
            self.parse(record_blob)

    def to_dict(self):
        result = {}
        for key, attr in self.mapping.items():
            value = getattr(self, attr)
            if value is not None:  # Only include non-None values
                if isinstance(value, dict):
                    # Handle dictionary (such as AppUserDefinedRecord or FilesystemsRecord)
                    result[key] = {
                        k: v.to_dict() if hasattr(v, "to_dict") else v
                        for k, v in value.items()
                    }
                else:
                    result[key] = value
        return result

    def parse(self, record_blob):
        for key, attr in self.mapping.items():
            if key in record_blob:
                value = record_blob[key]
                if attr == "FilesystemsRecord" and isinstance(value, dict):
                    # Delegate to CDRFilesystemRecord for each entry
                    parsed_records = {}
                    for idx, rec_blob in value.items():
                        parsed_records[idx] = CDRFilesystemRecord(idx, rec_blob)
                    setattr(self, attr, parsed_records)
                else:
                    setattr(self, attr, value)

    @staticmethod
    def from_xml(app_region_record):
        """
        Parses an XML element into a CDRAppRegionRecord instance.
        """
        index = convert_to_bytes(int(app_region_record.get("Idx")))
        country_list_elem = app_region_record.find("CountryList")
        country_list = country_list_elem.text if country_list_elem is not None else ""

        # Parsing AppUserDefinedRecord from XML
        # AppUserDefinedRecord uses element names as keys (e.g., <icon>value</icon>)
        app_user_defined_record = {}
        user_defined_elem = app_region_record.find(".//AppUserDefinedRecord")
        if user_defined_elem is not None:
            for child in user_defined_elem:
                # Key: encode without null terminator
                key = child.tag.encode('utf-8') if isinstance(child.tag, str) else child.tag
                value = child.text
                # Value: use convert_to_bytes which adds null terminator
                app_user_defined_record[key] = convert_to_bytes(value) if value is not None else b'\x00'

        # Parsing FilesystemsRecord from XML
        filesystems_record = {}
        for fs_record in app_region_record.findall(
            ".//FilesystemsRecord/FilesystemRecord"
        ):
            fs_idx = convert_to_bytes(int(fs_record.get("FilesystemIdx")))
            filesystems_record[fs_idx] = CDRFilesystemRecord.from_xml(fs_record)

        return CDRAppRegionRecord(
            index=index,
            record_blob={
                b"\x01\x00\x00\x00": country_list,
                b"\x02\x00\x00\x00": app_user_defined_record,
                b"\x03\x00\x00\x00": filesystems_record,
            },
        )

    def __repr__(self):
        return (
            f"CDRAppRegionRecord(\n"
            f"  index={self.index},\n"
            f"  CountryList={self.CountryList},\n"
            f"  AppUserDefinedRecord={self.AppUserDefinedRecord},\n"
            f"  FilesystemsRecord={self.FilesystemsRecord}\n"
            f")"
        )


class CDRApplicationRecord:
    def __init__(self, app_blob=None):
        self.AppId = None
        self.Name = None
        self.InstallDirName = None
        self.MinCacheFileSizeMB = None
        self.MaxCacheFileSizeMB = None
        self.LaunchOptionsRecord = {}
        self.AppIconsRecord = {}
        self.OnFirstLaunch = None
        self.IsBandwidthGreedy = None
        self.VersionsRecord = {}
        self.CurrentVersionId = None
        self.FilesystemsRecord = {}
        self.TrickleVersionId = None
        self.UserDefinedRecord = {}
        self.BetaVersionPassword = None
        self.BetaVersionId = None
        self.LegacyInstallDirName = None
        self.SkipMFPOverwrite = None
        self.UseFilesystemDvr = None
        self.ManifestOnlyApp = None
        self.AppOfManifestOnlyCache = None
        self.RegionSpecificRecord = {}

        self.mapping = {
            b"\x01\x00\x00\x00": "AppId",
            b"\x02\x00\x00\x00": "Name",
            b"\x03\x00\x00\x00": "InstallDirName",
            b"\x04\x00\x00\x00": "MinCacheFileSizeMB",
            b"\x05\x00\x00\x00": "MaxCacheFileSizeMB",
            b"\x06\x00\x00\x00": "LaunchOptionsRecord",
            b"\x07\x00\x00\x00": "AppIconsRecord",
            b"\x08\x00\x00\x00": "OnFirstLaunch",
            b"\x09\x00\x00\x00": "IsBandwidthGreedy",
            b"\x0a\x00\x00\x00": "VersionsRecord",
            b"\x0b\x00\x00\x00": "CurrentVersionId",
            b"\x0c\x00\x00\x00": "FilesystemsRecord",
            b"\x0d\x00\x00\x00": "TrickleVersionId",
            b"\x0e\x00\x00\x00": "UserDefinedRecord",
            b"\x0f\x00\x00\x00": "BetaVersionPassword",
            b"\x10\x00\x00\x00": "BetaVersionId",
            b"\x11\x00\x00\x00": "LegacyInstallDirName",
            b"\x12\x00\x00\x00": "SkipMFPOverwrite",
            b"\x13\x00\x00\x00": "UseFilesystemDvr",
            b"\x14\x00\x00\x00": "ManifestOnlyApp",
            b"\x15\x00\x00\x00": "AppOfManifestOnlyCache",
            b"\x16\x00\x00\x00": "RegionSpecificRecord",
        }

        if app_blob:
            self.parse(app_blob)

    def to_dict(self):
        result = {}

        # Optional fields that should only be output if they have meaningful values
        # (not just \x00 or empty - they must have been explicitly set with non-zero values)
        optional_boolean_fields = ["SkipMFPOverwrite", "UseFilesystemDvr", "ManifestOnlyApp"]

        for key, attr in self.mapping.items():
            value = getattr(self, attr)

            # AppIconsRecord should be included if it was set (even if empty dict)
            # Skip if value is None (not loaded/set)
            if attr == "AppIconsRecord":
                if value is None:
                    continue  # Skip if not loaded
                # Include even if empty dict
                result[key] = {k: v for k, v in value.items()}
                continue

            # FilesystemsRecord should always be included (even if empty)
            if attr == "FilesystemsRecord":
                if value is None or not value:
                    result[key] = {}
                elif isinstance(value, dict):
                    nested_dict = {idx: rec.to_dict() for idx, rec in value.items()}
                    result[key] = nested_dict
                continue

            # UserDefinedRecord - output all keys, including those with blank values
            if attr == "UserDefinedRecord":
                if value is None or not value:
                    continue  # Skip if empty dict - don't output empty UserDefinedRecord
                # Include all keys, even those with empty/blank values
                udr_result = {}
                for k, v in value.items():
                    # Preserve all keys - if value is None/empty/just null byte, use empty bytes
                    if v is None or v == b'' or v == '' or v == b'\x00':
                        udr_result[k] = b'\x00'  # Empty null-terminated string
                    else:
                        udr_result[k] = v
                if udr_result:  # Only include if there are keys
                    result[key] = udr_result
                continue

            if value is not None:
                # Skip empty dictionaries for RegionSpecificRecord
                if attr == "RegionSpecificRecord" and not value:
                    continue

                # Handle nested dictionaries for LaunchOptionsRecord, VersionsRecord, and RegionSpecificRecord
                if attr in [
                    "LaunchOptionsRecord",
                    "VersionsRecord",
                    "RegionSpecificRecord",
                ]:
                    if isinstance(value, dict):
                        nested_dict = {idx: rec.to_dict() for idx, rec in value.items()}
                        result[key] = nested_dict

                # Handle optional boolean fields - only output if non-zero
                elif attr in optional_boolean_fields:
                    # Handle value that might already be bytes
                    if isinstance(value, bytes):
                        byte_val = value[:1] if len(value) >= 1 else b'\x00'
                    else:
                        byte_val = int(value).to_bytes(1, 'little')
                    # Only output if non-zero
                    if byte_val != b'\x00':
                        result[key] = byte_val

                # Handle LegacyInstallDirName - only output if non-empty
                elif attr == "LegacyInstallDirName":
                    bytes_val = convert_to_bytes(value)
                    # Skip if empty (just null terminator)
                    if bytes_val and bytes_val != b'\x00':
                        result[key] = bytes_val

                # Convert any other values to bytes
                elif attr == "IsBandwidthGreedy":
                    # Handle value that might already be bytes
                    if isinstance(value, bytes):
                        result[key] = value[:1] if len(value) >= 1 else b'\x00'
                    else:
                        result[key] = int(value).to_bytes(1, 'little')
                else:
                    result[key] = convert_to_bytes(value)
            # Skip None values - don't add keys that weren't present in source

        return result

    def parse(self, app_blob):
        for key, value in app_blob.items():
            if key in self.mapping:
                attr = self.mapping[key]
                if attr in [
                    "LaunchOptionsRecord",
                    "VersionsRecord",
                    "FilesystemsRecord",
                    "RegionSpecificRecord",
                ] and isinstance(value, dict):
                    parsed_records = {}
                    for idx, rec_blob in value.items():
                        if attr == "LaunchOptionsRecord":
                            parsed_records[idx] = CDRLaunchOptionsRecord(idx, rec_blob)
                        elif attr == "VersionsRecord":
                            parsed_records[idx] = CDRApplicationVersionRecord(
                                idx, rec_blob
                            )
                        elif attr == "FilesystemsRecord":
                            parsed_records[idx] = CDRFilesystemRecord(idx, rec_blob)
                        elif attr == "RegionSpecificRecord":
                            parsed_records[idx] = CDRAppRegionRecord(idx, rec_blob)
                    setattr(self, attr, parsed_records)
                else:
                    setattr(self, attr, value)
            else:
                # Store any unknown keys
                setattr(self, key, value)

    @staticmethod
    def from_xml(app_record):
        app_id = int(app_record.find("AppId").text)
        app = CDRApplicationRecord()
        app.AppId = convert_to_bytes(app_id)
        app.Name = (
            app_record.find("Name").text
            if app_record.find("Name") is not None
            else None
        )
        app.InstallDirName = (
            app_record.find("InstallDirName").text
            if app_record.find("InstallDirName") is not None
            else None
        )
        app.MinCacheFileSizeMB = (
            convert_to_bytes(int(app_record.find("MinCacheFileSizeMB").text))
            if app_record.find("MinCacheFileSizeMB") is not None
            else None
        )
        app.MaxCacheFileSizeMB = (
            convert_to_bytes(int(app_record.find("MaxCacheFileSizeMB").text))
            if app_record.find("MaxCacheFileSizeMB") is not None
            else None
        )
        app.OnFirstLaunch = (
            convert_to_bytes(int(app_record.find("OnFirstLaunch").text))
            if app_record.find("OnFirstLaunch") is not None
            else None
        )
        app.IsBandwidthGreedy = (
            struct.pack('?', int(app_record.find("IsBandwidthGreedy").text))[0]
            if app_record.find("IsBandwidthGreedy") is not None
            else None
        )
        app.CurrentVersionId = (
            convert_to_bytes(int(app_record.find("CurrentVersionId").text))
            if app_record.find("CurrentVersionId") is not None
            else None
        )
        app.TrickleVersionId = (
            convert_to_bytes(int(app_record.find("TrickleVersionId").text))
            if app_record.find("TrickleVersionId") is not None
            else None
        )
        app.BetaVersionPassword = (
            app_record.find("BetaVersionPassword").text
            if app_record.find("BetaVersionPassword") is not None
            else None
        )
        app.BetaVersionId = (
            convert_to_bytes(int(app_record.find("BetaVersionId").text))
            if app_record.find("BetaVersionId") is not None
            else None
        )
        app.UseFilesystemDvr = (
            struct.pack('?', int(app_record.find("UseFilesystemDvr").text))[0]
            if app_record.find("UseFilesystemDvr") is not None
            else None
        )
        app.SkipMFPOverwrite = (
            struct.pack('?', int(app_record.find("SkipMFPOverwrite").text))[0]
            if app_record.find("SkipMFPOverwrite") is not None
            else None
        )
        app.ManifestOnlyApp = (
            struct.pack('?', int(app_record.find("ManifestOnlyApp").text))[0]
            if app_record.find("ManifestOnlyApp") is not None
            else None
        )
        app.AppOfManifestOnlyCache = (
            convert_to_bytes(int(app_record.find("AppOfManifestOnlyCache").text))
            if app_record.find("AppOfManifestOnlyCache") is not None
            else None
        )
        legacy_install_dir_element = app_record.find("LegacyInstallDirName")
        app.LegacyInstallDirName = (
            legacy_install_dir_element.text
            if legacy_install_dir_element is not None
            else None
        )

        # Parse VersionsRecord
        for version_record in app_record.findall(
            ".//AppVersionsRecord/AppVersionRecord"
        ):
            version = CDRApplicationVersionRecord.from_xml(version_record)
            app.VersionsRecord[convert_to_bytes(version.index)] = version

        # Parse LaunchOptionsRecord
        for option_record in app_record.findall(
            ".//AppLaunchOptionsRecord/AppLaunchOptionRecord"
        ):
            launch_option = CDRLaunchOptionsRecord.from_xml(option_record)
            app.LaunchOptionsRecord[convert_to_bytes(launch_option.index)] = (
                launch_option
            )

        # Parse FilesystemsRecord
        for fs_record in app_record.findall(".//FilesystemsRecord/FilesystemRecord"):
            filesystem = CDRFilesystemRecord.from_xml(fs_record)
            app.FilesystemsRecord[convert_to_bytes(filesystem.index)] = filesystem

        # Parse RegionSpecificRecord (contains region-specific overrides)
        for region_record in app_record.findall(
            ".//RegionSpecificRecord/AppRegionRecord"
        ):
            region_record_obj = CDRAppRegionRecord.from_xml(region_record)
            app.RegionSpecificRecord[convert_to_bytes(region_record_obj.index)] = (
                region_record_obj
            )

        # Parse UserDefinedRecord
        # Keys should NOT have null terminator, only values should
        user_defined_records = app_record.find(".//AppUserDefinedRecord")
        if user_defined_records is not None:
            for user_defined_key in user_defined_records:
                # Key: encode without null terminator
                key = user_defined_key.tag.encode('utf-8') if isinstance(user_defined_key.tag, str) else user_defined_key.tag
                value = user_defined_key.text
                # Value: use convert_to_bytes which adds null terminator
                app.UserDefinedRecord[key] = convert_to_bytes(value) if value is not None else b'\x00'

        return app

    def add_version(self, version_id, version_record):
        self.VersionsRecord[version_id] = version_record

    def remove_version(self, version_id):
        if version_id in self.VersionsRecord:
            del self.VersionsRecord[version_id]

    def add_launch_option(self, index, launch_option):
        self.LaunchOptionsRecord[index] = launch_option

    def remove_launch_option(self, index):
        if index in self.LaunchOptionsRecord:
            del self.LaunchOptionsRecord[index]

    def add_filesystem(self, index, filesystem):
        self.FilesystemsRecord[index] = filesystem

    def remove_filesystem(self, index):
        if index in self.FilesystemsRecord:
            del self.FilesystemsRecord[index]

    def add_regionspecificrecord(self, index, appregionrecord):
        self.RegionSpecificRecord[index] = appregionrecord

    def remove_regionspecificrecord(self, index):
        if index in self.RegionSpecificRecord:
            del self.RegionSpecificRecord[index]

    def __repr__(self):
        return (
            f"CDRApplicationRecord(\n"
            f"  AppId={self.AppId},\n"
            f"  Name={self.Name},\n"
            f"  InstallDirName={self.InstallDirName},\n"
            f"  MinCacheFileSizeMB={self.MinCacheFileSizeMB},\n"
            f"  MaxCacheFileSizeMB={self.MaxCacheFileSizeMB},\n"
            f"  LaunchOptionsRecord={self.LaunchOptionsRecord},\n"
            f"  AppIconsRecord={self.AppIconsRecord},\n"
            f"  OnFirstLaunch={self.OnFirstLaunch},\n"
            f"  IsBandwidthGreedy={self.IsBandwidthGreedy},\n"
            f"  VersionsRecord={self.VersionsRecord},\n"
            f"  CurrentVersionId={self.CurrentVersionId},\n"
            f"  FilesystemsRecord={self.FilesystemsRecord},\n"
            f"  TrickleVersionId={self.TrickleVersionId},\n"
            f"  UserDefinedRecord={self.UserDefinedRecord},\n"
            f"  BetaVersionPassword={self.BetaVersionPassword},\n"
            f"  BetaVersionId={self.BetaVersionId},\n"
            f"  LegacyInstallDirName={self.LegacyInstallDirName},\n"
            f"  SkipMFPOverwrite={self.SkipMFPOverwrite},\n"
            f"  UseFilesystemDvr={self.UseFilesystemDvr},\n"
            f"  ManifestOnlyApp={self.ManifestOnlyApp},\n"
            f"  AppOfManifestOnlyCache={self.AppOfManifestOnlyCache}\n"
            f"  RegionSpecificRecord={self.RegionSpecificRecord}\n"
            f")"
        )


class CDRDiscountQualifierRecord:
    def __init__(self, index, record_blob=None):
        self.index = index
        self.Name = None
        self.SubscriptionId = None
        self.IsDisqualifier = None

        self.mapping = {
            b"\x01\x00\x00\x00": "Name",
            b"\x02\x00\x00\x00": "SubscriptionId",
            b"\x03\x00\x00\x00": "IsDisqualifier",
        }

        if record_blob:
            self.parse(record_blob)

    def to_dict(self):
        result = {}
        for key, attr in self.mapping.items():
            value = getattr(self, attr)
            if value is not None:
                if attr == "IsDisqualifier":
                    # IsDisqualifier is BYTE (1 byte)
                    if isinstance(value, bytes):
                        result[key] = value[:1] if len(value) >= 1 else b'\x00'
                    else:
                        result[key] = struct.pack('<B', int(value))
                else:
                    result[key] = convert_to_bytes(value)
        return result

    def parse(self, record_blob):
        for key, attr in self.mapping.items():
            if key in record_blob:
                setattr(self, attr, record_blob[key])

    @staticmethod
    def from_xml(qualifier_record):
        qualifier_id = convert_to_bytes(int(qualifier_record.get("id")))
        qualifier = CDRDiscountQualifierRecord(index=qualifier_id)
        # Name is a string, don't pre-convert to bytes (to_dict handles it)
        qualifier.Name = qualifier_record.find("Name").text
        qualifier.SubscriptionId = convert_to_bytes(
            int(qualifier_record.find("SubscriptionId").text)
        )
        # IsDisqualifier is BYTE (1 byte)
        is_disqualifier_elem = qualifier_record.find("IsDisqualifier")
        if is_disqualifier_elem is not None:
            qualifier.IsDisqualifier = struct.pack('<B', int(is_disqualifier_elem.text))
        return qualifier

    def __repr__(self):
        return (
            f"CDRDiscountQualifierRecord(\n"
            f"  index={self.index},\n"
            f"  Name={self.Name},\n"
            f"  SubscriptionId={self.SubscriptionId}\n"
            f")"
        )


class CDRDiscountRecord:
    def __init__(self, index, record_blob=None):
        self.index = index
        self.Name = None
        self.DiscountInCents = None
        self.DiscountQualifiers = {}

        self.mapping = {
            b"\x01\x00\x00\x00": "Name",
            b"\x02\x00\x00\x00": "DiscountInCents",
            b"\x03\x00\x00\x00": "DiscountQualifiers",
        }

        if record_blob:
            self.parse(record_blob)

    def to_dict(self):
        result = {}
        for key, attr in self.mapping.items():
            value = getattr(self, attr)
            if value is not None:
                if attr == "DiscountQualifiers" and isinstance(value, dict):
                    result[key] = {idx: dq.to_dict() for idx, dq in value.items()}
                else:
                    result[key] = convert_to_bytes(value)
        return result

    def parse(self, record_blob):
        for key, attr in self.mapping.items():
            if key in record_blob:
                if attr == "DiscountQualifiers" and isinstance(record_blob[key], dict):
                    parsed_qualifiers = {}
                    for idx, qualifier_blob in record_blob[key].items():
                        parsed_qualifiers[idx] = CDRDiscountQualifierRecord(
                            idx, qualifier_blob
                        )
                    setattr(self, attr, parsed_qualifiers)
                else:
                    setattr(self, attr, record_blob[key])

    @staticmethod
    def from_xml(discount_record):
        discount_id = convert_to_bytes(int(discount_record.get("id")))
        discount = CDRDiscountRecord(index=discount_id)
        discount.Name = discount_record.find("Name").text
        discount.DiscountInCents = convert_to_bytes(int(discount_record.find("DiscountInCents").text))

        # Parse DiscountQualifiers
        for qualifier_record in discount_record.findall(
            ".//SubscriptionDiscountQualifierRecord"
        ):
            qualifier = CDRDiscountQualifierRecord.from_xml(qualifier_record)
            discount.DiscountQualifiers[convert_to_bytes(qualifier.index)] = qualifier

        return discount

    def add_qualifier(self, index, qualifier):
        self.DiscountQualifiers[index] = qualifier

    def remove_qualifier(self, index):
        if index in self.DiscountQualifiers:
            del self.DiscountQualifiers[index]

    def __repr__(self):
        return (
            f"CDRDiscountRecord(\n"
            f"  index={self.index},\n"
            f"  Name={self.Name},\n"
            f"  DiscountInCents={self.DiscountInCents},\n"
            f"  DiscountQualifiers={self.DiscountQualifiers}\n"
            f")"
        )


class OptionalRateLimitRecord:
    def __init__(self, index=None, record_blob=None):
        self.index = index
        self.LimitInMB = None
        self.PeriodInSeconds = None

        self.mapping = {
            b"\x01\x00\x00\x00": "LimitInMB",
            b"\x02\x00\x00\x00": "PeriodInSeconds",
        }

        if record_blob:
            self.parse(record_blob)

    def to_dict(self):
        result = {}
        for key, attr in self.mapping.items():
            value = getattr(self, attr)
            if value is not None:
                result[key] = convert_to_bytes(value)
        return result

    def parse(self, record_blob):
        for key, attr in self.mapping.items():
            if key in record_blob:
                setattr(self, attr, record_blob[key])

    @staticmethod
    def from_xml(ratelimit_record):
        rate_limit = OptionalRateLimitRecord()
        # LimitInMB is DWORD (4 bytes)
        limit_attr = ratelimit_record.get("Limit")
        if limit_attr is not None:
            rate_limit.LimitInMB = convert_to_bytes(int(limit_attr))
        # PeriodInSeconds is DWORD (4 bytes)
        period_elem = ratelimit_record.find("PeriodInMinutes")
        if period_elem is not None:
            rate_limit.PeriodInSeconds = convert_to_bytes(int(period_elem.text))
        return rate_limit

    def __repr__(self):
        return (
            f"OptionalRateLimitRecord(\n"
            f"  index={self.index},\n"
            f"  LimitInMB={self.LimitInMB},\n"
            f"  PeriodInSeconds={self.PeriodInSeconds}\n"
            f")"
        )


class CDRSubscriptionRecord:
    def __init__(self, index, record_blob=None):
        self.index = index
        self.SubscriptionId = None
        self.Name = None
        self.BillingType = None
        self.CostInCents = None
        self.PeriodInMinutes = None
        self.AppIdsRecord = {}
        self.RunAppId = None
        self.OnSubscribeRunLaunchOptionIndex = None
        self.OptionalRateLimitRecord = None
        self.DiscountsRecord = {}
        self.IsPreorder = None
        self.RequiresShippingAddress = None
        self.DomesticCostInCents = None
        self.InternationalCostInCents = None
        self.RequiredKeyType = None
        self.IsCyberCafe = None
        self.GameCode = None
        self.GameCodeDescription = None
        self.IsDisabled = None
        self.RequiresCD = None
        self.TerritoryCode = None
        self.IsSteam3Subscription = None
        self.ExtendedInfoRecord = {}

        self.mapping = {
            b"\x01\x00\x00\x00": "SubscriptionId",
            b"\x02\x00\x00\x00": "Name",
            b"\x03\x00\x00\x00": "BillingType",
            b"\x04\x00\x00\x00": "CostInCents",
            b"\x05\x00\x00\x00": "PeriodInMinutes",
            b"\x06\x00\x00\x00": "AppIdsRecord",
            b"\x07\x00\x00\x00": "RunAppId",
            b"\x08\x00\x00\x00": "OnSubscribeRunLaunchOptionIndex",
            b"\x09\x00\x00\x00": "OptionalRateLimitRecord",
            b"\x0a\x00\x00\x00": "DiscountsRecord",
            b"\x0b\x00\x00\x00": "IsPreorder",
            b"\x0c\x00\x00\x00": "RequiresShippingAddress",
            b"\x0d\x00\x00\x00": "DomesticCostInCents",
            b"\x0e\x00\x00\x00": "InternationalCostInCents",
            b"\x0f\x00\x00\x00": "RequiredKeyType",
            b"\x10\x00\x00\x00": "IsCyberCafe",
            b"\x11\x00\x00\x00": "GameCode",
            b"\x12\x00\x00\x00": "GameCodeDescription",
            b"\x13\x00\x00\x00": "IsDisabled",
            b"\x14\x00\x00\x00": "RequiresCD",
            b"\x15\x00\x00\x00": "TerritoryCode",
            b"\x16\x00\x00\x00": "IsSteam3Subscription",
            b"\x17\x00\x00\x00": "ExtendedInfoRecord",
        }
        if record_blob:
            self.parse(record_blob)

    def parse(self, record_blob):
        for key, attr in self.mapping.items():
            if key in record_blob:
                # Special handling for DiscountsRecord and OptionalRateLimitRecord.
                if attr == "DiscountsRecord" and isinstance(record_blob[key], dict):
                    parsed_discounts = {}
                    for idx, discount_blob in record_blob[key].items():
                        parsed_discounts[idx] = CDRDiscountRecord(idx, discount_blob)
                    setattr(self, attr, parsed_discounts)
                elif attr == "OptionalRateLimitRecord" and isinstance(record_blob[key], dict):
                    self.OptionalRateLimitRecord = OptionalRateLimitRecord(self.index, record_blob[key])
                elif attr == "BillingType":
                    # Retrieve the raw value.
                    raw = record_blob[key]
                    # If raw is not already bytes, encode it (using latin-1 to preserve binary values).
                    if not isinstance(raw, bytes):
                        raw = raw.encode('latin-1')
                    try:
                        # Unpack as unsigned short (2 bytes, little-endian).
                        value_int = struct.unpack('<H', raw)[0]
                    except Exception:
                        value_int = 0
                    setattr(self, attr, value_int)
                elif attr == "ExtendedInfoRecord":
                    # Ensure ExtendedInfoRecord is a normal dict with string keys and string values.
                    ext = record_blob[key]
                    new_ext = {}
                    if isinstance(ext, dict):
                        for k, v in ext.items():

                            new_k = k.decode('utf-8', errors='ignore') if isinstance(k, bytes) else str(k)
                            new_v = v.decode('utf-8', errors='ignore') if isinstance(v, bytes) else str(v)
                            new_ext[new_k] = new_v
                    else:
                        new_ext = { "": str(ext) }
                    setattr(self, attr, new_ext)
                else:
                    setattr(self, attr, record_blob[key])

    def to_dict(self):
        """Convert the subscription record to a dictionary format suitable for serialization."""
        # Fields that should be serialized as BYTE (1 byte)
        byte_fields = {"IsPreorder", "IsDisabled", "IsCyberCafe", "IsSteam3Subscription",
                       "RequiresCD", "RequiresShippingAddress"}
        result = {}
        for key, attr in self.mapping.items():
            value = getattr(self, attr)
            if value is not None:
                if attr == "DiscountsRecord":
                    # DiscountsRecord contains CDRDiscountRecord objects with their own to_dict
                    # Only output if it's a non-empty dict
                    if isinstance(value, dict) and value:
                        result[key] = {idx: discount.to_dict() for idx, discount in value.items()}
                    # Skip if None or empty dict
                elif attr == "OptionalRateLimitRecord" and hasattr(value, 'to_dict'):
                    # OptionalRateLimitRecord is an object with its own to_dict
                    result[key] = value.to_dict()
                elif attr == "AppIdsRecord" and isinstance(value, dict):
                    # AppIdsRecord is a simple dict, pass as-is
                    result[key] = value
                elif attr == "ExtendedInfoRecord":
                    # ExtendedInfoRecord is a simple dict with string keys/values
                    # Only output if it's a non-empty dict
                    if isinstance(value, dict) and value:
                        # Convert to bytes format for serialization
                        ext_result = {}
                        for k, v in value.items():
                            key_bytes = k.encode('latin-1') if isinstance(k, str) else k
                            val_bytes = v.encode('latin-1') if isinstance(v, str) else v
                            ext_result[key_bytes] = val_bytes
                        result[key] = ext_result
                    # Skip if None or empty dict
                elif attr == "BillingType":
                    # BillingType must be exactly 2 bytes (WORD)
                    if isinstance(value, bytes):
                        result[key] = value[:2] if len(value) >= 2 else value + b'\x00' * (2 - len(value))
                    else:
                        result[key] = struct.pack('<H', int(value))
                elif attr in byte_fields:
                    # BYTE fields must be exactly 1 byte
                    if isinstance(value, bytes):
                        result[key] = value[:1] if len(value) >= 1 else b'\x00'
                    else:
                        result[key] = struct.pack('<B', int(value))
                else:
                    result[key] = convert_to_bytes(value)
        return result

    def get_billing_type(self) -> str:
        """
        Returns the billing type as a human-readable string based on the stored integer.
        """
        billing_map = {
            0: "NoCost",
            1: "BillOnceOnly",
            2: "BillMonthly",
            3: "ProofOfPrepurchaseOnly",
            4: "GuestPass",
            5: "HardwarePromo",
            6: "Gift",
            7: "AutoGrant"
        }
        if self.BillingType is None:
            return "Unknown"
        try:
            bt_int = int(self.BillingType)
        except Exception:
            bt_int = 0
        return billing_map.get(bt_int, "Unknown")


    @staticmethod
    def from_xml(subscription_record):
        subscription_id = int(subscription_record.find("SubscriptionId").text)
        sub = CDRSubscriptionRecord(index=subscription_id)
        sub.SubscriptionId = convert_to_bytes(subscription_id)
        sub.Name = (
            subscription_record.find("Name").text
            if subscription_record.find("Name") is not None
            else None
        )
        billing_type_str = subscription_record.find("BillingType").text
        billing_type_map = {
            "NoCost": BillingTypeVar.NoCost,
            "BillOnceOnly": BillingTypeVar.BillOnceOnly,
            "BillMonthly": BillingTypeVar.BillMonthly,
            "ProofOfPrepurchaseOnly": BillingTypeVar.ProofOfPrepurchaseOnly,
            "GuestPass": BillingTypeVar.GuestPass,
            "HardwarePromo": BillingTypeVar.HardwarePromo,
            "Gift": BillingTypeVar.Gift,
            "AutoGrant": BillingTypeVar.AutoGrant,
        }
        # BillingType must be exactly 2 bytes (WORD)
        sub.BillingType = struct.pack('<H', billing_type_map.get(billing_type_str, 0))

        # BYTE fields (1 byte each) - convert string "0"/"1" to packed byte
        sub.IsPreorder = (
            struct.pack('<B', int(subscription_record.find("IsPreorder").text))
            if subscription_record.find("IsPreorder") is not None
            else None
        )
        sub.IsDisabled = (
            struct.pack('<B', int(subscription_record.find("IsDisabled").text))
            if subscription_record.find("IsDisabled") is not None
            else None
        )
        sub.IsCyberCafe = (
            struct.pack('<B', int(subscription_record.find("IsCyberCafe").text))
            if subscription_record.find("IsCyberCafe") is not None
            else None
        )
        sub.IsSteam3Subscription = (
            struct.pack('<B', int(subscription_record.find("IsSteam3Subscription").text))
            if subscription_record.find("IsSteam3Subscription") is not None
            else None
        )
        sub.RequiresCD = (
            struct.pack('<B', int(subscription_record.find("RequiresCD").text))
            if subscription_record.find("RequiresCD") is not None
            else None
        )
        # DWORD fields (4 bytes) - convert string to packed DWORD
        sub.RequiredKeyType = (
            struct.pack('<I', int(subscription_record.find("RequiredKeyType").text))
            if subscription_record.find("RequiredKeyType") is not None
            else None
        )
        sub.GameCode = (
            struct.pack('<I', int(subscription_record.find("GameCode").text))
            if subscription_record.find("GameCode") is not None
            else None
        )
        game_code_desc_element = subscription_record.find("GameCodeDesc")
        sub.GameCodeDescription = (
            game_code_desc_element.text if game_code_desc_element is not None else None
        )
        sub.TerritoryCode = (
            convert_to_bytes(int(subscription_record.find("TerritoryCode").text))
            if subscription_record.find("TerritoryCode") is not None
            else None
        )
        sub.CostInCents = (
            convert_to_bytes(int(subscription_record.find("CostInCents").text))
            if subscription_record.find("CostInCents") is not None
            else None
        )
        # RequiresShippingAddress must be BYTE (1 byte)
        sub.RequiresShippingAddress = (
            struct.pack('<B', int(subscription_record.find("RequiresShippingAddress").text))
            if subscription_record.find("RequiresShippingAddress") is not None
            else None
        )
        sub.DomesticCostInCents = (
            convert_to_bytes(int(subscription_record.find("DomesticShippingCost").text))
            if subscription_record.find("DomesticShippingCost") is not None
            else None
        )
        sub.InternationalCostInCents = (
            convert_to_bytes(int(subscription_record.find("InternationalShippingCost").text))
            if subscription_record.find("InternationalShippingCost") is not None
            else None
        )
        sub.RunAppId = (
            convert_to_bytes(int(subscription_record.find("OnSubscribeRunAppId").text))
            if subscription_record.find("OnSubscribeRunAppId") is not None
            else None
        )
        sub.OnSubscribeRunLaunchOptionIndex = (
            convert_to_bytes(int(subscription_record.find("OnSubscribeRunLaunchOptionIdx").text))
            if subscription_record.find("OnSubscribeRunLaunchOptionIdx") is not None
            else None
        )

        # Parse AppIdsRecord
        for app_id_element in subscription_record.findall(
            ".//SubscriptionAppIdsRecord/AppId"
        ):
            app_id = int(app_id_element.text)
            sub.AppIdsRecord[convert_to_bytes(app_id)] = b""

        # Parse OptionalRateLimitRecord
        rate_limit_record = subscription_record.find(
            ".//AllDiscountsRecord/OptionalRateLimitRecord"
        )
        if rate_limit_record is not None:
            sub.OptionalRateLimitRecord = OptionalRateLimitRecord.from_xml(
                rate_limit_record
            )

        # Parse ExtendedInfoRecord
        for extendedinfo_record in subscription_record.findall(
            ".//ExtendedInfoRecord/Record"
        ):
            key = extendedinfo_record.find("Key").text
            value = extendedinfo_record.find("Value").text
            sub.ExtendedInfoRecord[key] = value

        # Parse DiscountsRecord
        for discount_record in subscription_record.findall(
            ".//AllDiscountsRecord/SubscriptionDiscountRecord"
        ):
            discount = CDRDiscountRecord.from_xml(discount_record)
            sub.DiscountsRecord[convert_to_bytes(discount.index)] = discount

        return sub

    def add_discount(self, index, discount):
        self.DiscountsRecord[index] = discount

    def remove_discount(self, index):
        if index in self.DiscountsRecord:
            del self.DiscountsRecord[index]

    def add_app_id(self, app_id):
        self.AppIdsRecord[app_id] = b""

    def remove_app_id(self, app_id):
        if app_id in self.AppIdsRecord:
            del self.AppIdsRecord[app_id]

    # -------------------------
    # New Properties Added Here
    # -------------------------

    @property
    def is_shipped(self) -> bool:
        """
        Returns True if the subscription requires a shipping address,
        which is interpreted as a shippable product.
        """
        if self.RequiresShippingAddress is None:
            return False
        # Convert from bytes if necessary
        if isinstance(self.RequiresShippingAddress, bytes):
            value = int.from_bytes(self.RequiresShippingAddress, byteorder='little')
        else:
            value = int(self.RequiresShippingAddress)
        return value != 0

    @property
    def domestic_shipping_cost(self) -> int:
        """
        Returns the domestic shipping cost (in cents) if the subscription is shippable;
        otherwise returns None.
        """
        if not self.is_shipped or self.DomesticCostInCents is None:
            return None
        if isinstance(self.DomesticCostInCents, bytes):
            return int.from_bytes(self.DomesticCostInCents, byteorder='little', signed=True)
        return int(self.DomesticCostInCents)

    @property
    def international_shipping_cost(self) -> int:
        """
        Returns the international shipping cost (in cents) if the subscription is shippable;
        otherwise returns None.
        """
        if not self.is_shipped or self.InternationalCostInCents is None:
            return None
        if isinstance(self.InternationalCostInCents, bytes):
            return int.from_bytes(self.InternationalCostInCents, byteorder='little', signed=True)
        return int(self.InternationalCostInCents)

    @property
    def base_cost(self) -> int:
        """
        Returns the base cost (in cents) of the subscription.
        """
        if self.CostInCents is None:
            return None
        if isinstance(self.CostInCents, bytes):
            return int.from_bytes(self.CostInCents, byteorder='little', signed=True)
        return int(self.CostInCents)

    @property
    def has_discounts(self) -> bool:
        """
        Returns True if the subscription contains any discount records.
        """
        return bool(self.DiscountsRecord)

    @property
    def grants_guest_pass(self) -> bool:
        """
        Returns True if any line in the ExtendedInfoRecord contains
        'OnPurchaseGrantGuestPassPackage'.
        """
        if not self.ExtendedInfoRecord:
            return False
        # Check each value in the extended info; assuming values are strings.
        for value in self.ExtendedInfoRecord.values():
            if isinstance(value, str) and "OnPurchaseGrantGuestPassPackage" in value:
                return True
        return False

    @property
    def applications(self) -> list:
        """
        Returns a list of tuples for each application included with the subscription.
        Each tuple is of the form (app_id, app_name). The app name is looked up using
        the globally loaded ContentDescriptionRecord (globalvars.CDR_DICTIONARY).
        """
        apps = []
        # Assuming that the keys in AppIdsRecord are stored as 4-byte values.
        # Import globalvars here to access the global CDR_DICTIONARY.
        import globalvars
        for app_id_bytes in self.AppIdsRecord.keys():
            app_id = int.from_bytes(app_id_bytes, byteorder='little', signed=False)
            app_name = globalvars.CDR_DICTIONARY.get_app_name(app_id)
            apps.append((app_id, app_name))
        return apps

    def list_discounts(self) -> List[dict]:
        """
        Returns a list of all discounts for this subscription.
        Each discount is represented as a dictionary with:
          - 'name': Discount name (string)
          - 'amount_dollars': Discount amount in dollars (float)
          - 'qualifiers': A list of qualifier dictionaries, where each qualifier dict contains:
                - 'name': Qualifier name (string)
                - 'subscription_id': The qualifying subscription ID (int)
        """
        discounts_info = []
        for discount in self.DiscountsRecord.values():
            # Get discount name (decode if stored as bytes)
            discount_name = (
                discount.Name.decode('utf-8').rstrip('\x00')
                if isinstance(discount.Name, bytes)
                else discount.Name
            )
            # Convert discount amount from cents to dollars
            if discount.DiscountInCents is not None:
                if isinstance(discount.DiscountInCents, bytes):
                    discount_cents = int.from_bytes(discount.DiscountInCents, byteorder='little', signed=True)
                else:
                    discount_cents = int(discount.DiscountInCents)
                amount_dollars = discount_cents / 100.0
            else:
                amount_dollars = 0.0

            # Process discount qualifiers
            qualifiers_list = []
            for dq in discount.DiscountQualifiers.values():
                dq_name = (
                    dq.Name.decode('utf-8').rstrip('\x00')
                    if isinstance(dq.Name, bytes)
                    else dq.Name
                )
                dq_sub_id = dq.SubscriptionId
                if isinstance(dq_sub_id, bytes):
                    dq_sub_id = int.from_bytes(dq_sub_id, byteorder='little', signed=False)
                else:
                    dq_sub_id = int(dq_sub_id)
                qualifiers_list.append({
                    'name': dq_name,
                    'subscription_id': dq_sub_id
                })

            discounts_info.append({
                'name': discount_name,
                'amount_dollars': amount_dollars,
                'qualifiers': qualifiers_list
            })
        return discounts_info

    def list_discount_qualifiers(self, discount_identifier: Union[int, str]) -> List[dict]:
        """
        For a specific discount (identified by discount ID as an int or discount name as a str),
        returns a list of qualifier dictionaries. Each dictionary includes:
            - 'name': Qualifier name (string)
            - 'subscription_id': The qualifying subscription ID (int)
        If the discount is not found, returns an empty list.
        """
        discount = None
        if isinstance(discount_identifier, int):
            # Convert integer discount ID to 4-byte little-endian key
            discount_key = discount_identifier.to_bytes(4, byteorder='little', signed=False)
            discount = self.DiscountsRecord.get(discount_key)
        elif isinstance(discount_identifier, str):
            for d in self.DiscountsRecord.values():
                d_name = d.Name.decode('utf-8').rstrip('\x00') if isinstance(d.Name, bytes) else d.Name
                if d_name == discount_identifier:
                    discount = d
                    break

        if discount is None:
            return []

        qualifiers_list = []
        for dq in discount.DiscountQualifiers.values():
            dq_name = (
                dq.Name.decode('utf-8').rstrip('\x00')
                if isinstance(dq.Name, bytes)
                else dq.Name
            )
            dq_sub_id = dq.SubscriptionId
            if isinstance(dq_sub_id, bytes):
                dq_sub_id = int.from_bytes(dq_sub_id, byteorder='little', signed=False)
            else:
                dq_sub_id = int(dq_sub_id)
            qualifiers_list.append({
                'name': dq_name,
                'subscription_id': dq_sub_id
            })
        return qualifiers_list

    def get_discount_qualifier_subscription_ids(self, discount_identifier: Union[int, str]) -> List[int]:
        """
        For a specific discount (identified by discount ID as an int or discount name as a str),
        returns a list containing just the subscription IDs (as integers) of all its qualifiers.
        If the discount is not found, returns an empty list.
        """
        qualifiers = self.list_discount_qualifiers(discount_identifier)
        return [q['subscription_id'] for q in qualifiers]

    def get_billing_type(self) -> str:
        """
        Returns the billing type as a string.
        This method converts the stored billing type (usually stored as a packed value)
        back into a human-readable string.
        """
        billing_map = {
            0: "NoCost",
            1: "BillOnceOnly",
            2: "BillMonthly",
            3: "ProofOfPrepurchaseOnly",
            4: "GuestPass",
            5: "HardwarePromo",
            6: "Gift",
            7: "AutoGrant"
        }
        if self.BillingType is None:
            return "Unknown"
        try:
            # self.BillingType may be a byte (or int from a packed byte)
            bt_int = int(self.BillingType)
        except Exception:
            bt_int = 0
        return billing_map.get(bt_int, "Unknown")

    def get_guest_pass_subscription_ids(self) -> list:
        """
        Returns a list of all guest pass subscription IDs from ExtendedInfoRecord.
        It searches for keys starting with 'OnPurchaseGrantGuestPassPackage'
        (which may have an appended number) and returns all their values.
        """
        guest_pass_ids = []
        if not self.ExtendedInfoRecord:
            return guest_pass_ids

        for key, value in self.ExtendedInfoRecord.items():
            if key.startswith("OnPurchaseGrantGuestPassPackage"):
                # Attempt to convert the value to an integer if possible.
                try:
                    guest_pass_ids.append(int(value))
                except ValueError:
                    guest_pass_ids.append(value)
        return guest_pass_ids

    def get_guest_pass_info(self) -> dict:
        """
        Returns a dictionary containing guest pass information from ExtendedInfoRecord.
        The returned dictionary includes:
            - 'GrantPassesCount': value (if present)
            - 'InitialPeriod': value (if present)
            - 'InitialTimeUnit': value (if present)
            - 'GrantExpirationDays': value (if present)
        """
        keys_of_interest = ['GrantPassesCount', 'InitialPeriod', 'InitialTimeUnit', 'GrantExpirationDays']
        info = {}
        if not self.ExtendedInfoRecord:
            return info

        for key in keys_of_interest:
            if key in self.ExtendedInfoRecord:
                info[key] = self.ExtendedInfoRecord[key]
        return info



    def __repr__(self):
        return (
            f"CDRSubscriptionRecord(\n"
            f"  index={self.index},\n"
            f"  SubscriptionId={self.SubscriptionId},\n"
            f"  Name={self.Name},\n"
            f"  BillingType={self.BillingType},\n"
            f"  CostInCents={self.CostInCents},\n"
            f"  AppIdsRecord={self.AppIdsRecord},\n"
            f"  RunAppId={self.RunAppId},\n"
            f"  OnSubscribeRunLaunchOptionIndex={self.OnSubscribeRunLaunchOptionIndex},\n"
            f"  OptionalRateLimitRecord={self.OptionalRateLimitRecord},\n"
            f"  DiscountsRecord={self.DiscountsRecord},\n"
            f"  IsPreorder={self.IsPreorder},\n"
            f"  RequiresShippingAddress={self.RequiresShippingAddress},\n"
            f"  DomesticCostInCents={self.DomesticCostInCents},\n"
            f"  InternationalCostInCents={self.InternationalCostInCents},\n"
            f"  RequiredKeyType={self.RequiredKeyType},\n"
            f"  IsCyberCafe={self.IsCyberCafe},\n"
            f"  GameCode={self.GameCode},\n"
            f"  GameCodeDescription={self.GameCodeDescription},\n"
            f"  IsDisabled={self.IsDisabled},\n"
            f"  RequiresCD={self.RequiresCD},\n"
            f"  TerritoryCode={self.TerritoryCode},\n"
            f"  IsSteam3Subscription={self.IsSteam3Subscription},\n"
            f"  ExtendedInfoRecord={self.ExtendedInfoRecord}\n"
            f")"
        )


class IndexAppIdToSubscriptionIdsRecord:
    def __init__(self, application_id, subscriptions=None):
        self.application_id = application_id
        self.subscriptions = subscriptions if subscriptions is not None else {}

    def to_dict(self):
        return {k: v for k, v in self.subscriptions.items() if v is not None}

    def add_subscription(self, subscription_id):
        self.subscriptions[subscription_id] = b""

    def remove_subscription(self, subscription_id):
        if subscription_id in self.subscriptions:
            del self.subscriptions[subscription_id]

    @staticmethod
    def from_xml(element: ET.Element) -> "IndexAppIdToSubscriptionIdsRecord":
        app_id = convert_to_bytes(int(element.get("AppId")))
        record = IndexAppIdToSubscriptionIdsRecord(app_id)
        for sub_id_elem in element.findall("SubscriptionId"):
            sub_id = convert_to_bytes(convert_to_int(sub_id_elem.text))
            if sub_id is not None:
                record.subscriptions[sub_id] = None
        return record
    def __repr__(self):
        return (
            f"IndexAppIdToSubscriptionIdsRecord(\n"
            f"  application_id={self.application_id},\n"
            f"  subscriptions={self.subscriptions}\n"
            f")"
        )


class PublicKeyRecord:
    def __init__(self, application_id, key_data = None):
        self.application_id: Optional[int] = application_id
        self.key_data: Optional[bytes] = key_data

    def to_dict(self):
        return self.key_data

    @staticmethod
    def from_xml(element: ET.Element) -> "PublicKeyRecord":
        app_id = convert_to_bytes(convert_to_int(element.get("KeyIdx")))
        record = PublicKeyRecord(app_id)
        text = element.text.strip() if element.text else ""
        if text.startswith("0x"):
            text = text[2:]
        record.key_data = bytes.fromhex(text)
        return record

    def __repr__(self):
        return (
            f"PublicKeyRecord(\n"
            f"  application_id={self.application_id},\n"
            f"  key_data={self.key_data}\n"
            f")"
        )


class EncryptedPrivateKeyRecord:
    def __init__(self, application_id, key_data = None):
        self.application_id: Optional[int] = application_id
        self.key_data: Optional[bytes] = key_data

    def to_dict(self):
        return self.key_data

    @staticmethod
    def from_xml(element: ET.Element) -> "EncryptedPrivateKeyRecord":
        app_id = convert_to_bytes(convert_to_int(element.get("KeyIdx")))
        record = EncryptedPrivateKeyRecord(app_id)
        text = element.text.strip() if element.text else ""
        if text.startswith("0x"):
            text = text[2:]
        record.key_data = bytes.fromhex(text)
        return record

    def __repr__(self):
        return (
            f"EncryptedPrivateKeyRecord(\n"
            f"  application_id={self.application_id},\n"
            f"  key_data={self.key_data}\n"
            f")"
        )


class ContentDescriptionRecord:
    def __init__(self, blob=None):
        self.VersionNumber = None
        self.ApplicationsRecord = {}
        self.SubscriptionsRecord = {}
        self.LastChangedExistingAppOrSubscriptionTime = None
        self.IndexAppIdToSubscriptionIdsRecord = {}
        self.AllAppsPublicKeysRecord = {}
        self.AllAppsEncryptedPrivateKeysRecord = {}

        self.mapping = {
            "VersionNumber": b"\x00\x00\x00\x00",
            "ApplicationsRecord": b"\x01\x00\x00\x00",
            "SubscriptionsRecord": b"\x02\x00\x00\x00",
            "LastChangedExistingAppOrSubscriptionTime": b"\x03\x00\x00\x00",
            "IndexAppIdToSubscriptionIdsRecord": b"\x04\x00\x00\x00",
            "AllAppsPublicKeysRecord": b"\x05\x00\x00\x00",
            "AllAppsEncryptedPrivateKeysRecord": b"\x06\x00\x00\x00",
        }
        if blob:
            self.parse_blob(blob)

    def parse_blob(self, blob):
        # Ensure blob is a dictionary
        if not isinstance(blob, dict):
            raise TypeError("Expected blob to be a dictionary")

        for attr, key in self.mapping.items():
            value = blob.get(key)
            if value is not None:
                if attr == "ApplicationsRecord":
                    applications = {}
                    for app_id, app_blob in value.items():
                        applications[app_id] = CDRApplicationRecord(app_blob)
                    setattr(self, attr, applications)
                elif attr == "SubscriptionsRecord":
                    subscriptions = {}
                    for sub_id, sub_blob in value.items():
                        subscriptions[sub_id] = CDRSubscriptionRecord(sub_id, sub_blob)
                    setattr(self, attr, subscriptions)
                elif attr == "IndexAppIdToSubscriptionIdsRecord":
                    index_records = {}
                    for app_id, subs in value.items():
                        index_records[app_id] = IndexAppIdToSubscriptionIdsRecord(
                            app_id, subs
                        )
                    setattr(self, attr, index_records)
                elif attr == "AllAppsPublicKeysRecord":
                    keys = {}
                    for app_id, key_data in value.items():
                        keys[app_id] = PublicKeyRecord(app_id, key_data)
                    setattr(self, attr, keys)
                elif attr == "AllAppsEncryptedPrivateKeysRecord":
                    keys = {}
                    for app_id, key_data in value.items():
                        keys[app_id] = EncryptedPrivateKeyRecord(app_id, key_data)
                    setattr(self, attr, keys)
                elif attr == "VersionNumber":
                    self.VersionNumber = value
                else:
                    setattr(self, attr, value)
            else:
                setattr(self, attr, None)
        self.build_subscription_indices()

    def build_subscription_indices(self):
        """
        Creates two indices:
          1. freeweekends_subscriptions: a list of subscriptions (with SubscriptionId and Name)
             that have an ExtendedInfoRecord key "freeweekends".
          2. subscriptions_by_billing_type: a dictionary mapping each billing type (string)
             to a list of subscriptions (with SubscriptionId and Name).
        """
        self.freeweekends_subscriptions = []
        self.subscriptions_by_billing_type = {}
        # Iterate over each subscription in the parsed SubscriptionsRecord.
        for sub in self.SubscriptionsRecord.values():
            # Convert subscription ID and Name (if stored as bytes)
            if isinstance(sub.SubscriptionId, bytes):
                sub_id = int.from_bytes(sub.SubscriptionId, byteorder='little')
            else:
                sub_id = sub.SubscriptionId
            if isinstance(sub.Name, bytes):
                name = sub.Name.rstrip(b'\x00').decode('utf-8')
            else:
                name = sub.Name

            # Check for the "freeweekends" key in ExtendedInfoRecord.
            if sub.ExtendedInfoRecord and "freeweekends" in sub.ExtendedInfoRecord:
                self.freeweekends_subscriptions.append({
                    "SubscriptionId": sub_id,
                    "Name": name
                })

            # Get the billing type as a human-readable string
            billing_type = sub.get_billing_type()  # assuming get_billing_type() is defined in CDRSubscriptionRecord
            if billing_type not in self.subscriptions_by_billing_type:
                self.subscriptions_by_billing_type[billing_type] = []
            self.subscriptions_by_billing_type[billing_type].append({
                "SubscriptionId": sub_id,
                "Name": name
            })

    @staticmethod
    def from_xml_file(file_path):
        tree = ET.parse(file_path)
        root = tree.getroot()

        cdr = ContentDescriptionRecord()

        # Parse VersionNumber
        version_num_element = root.find("VersionNum")
        if version_num_element is not None:
            cdr.VersionNumber = convert_to_bytes(int(version_num_element.text))

        # Parse LastChangedExistingAppOrSubscriptionTime
        last_changed_time_element = root.find(
            "LastChangedExistingAppOrSubscriptionTime"
        )
        if last_changed_time_element is not None:
            cdr.LastChangedExistingAppOrSubscriptionTime = (
                last_changed_time_element.text
            )

        # Parse Subscriptions
        for subscription_record in root.findall(
            ".//AllSubscriptionsRecord/SubscriptionRecord"
        ):
            sub = CDRSubscriptionRecord.from_xml(subscription_record)
            cdr.SubscriptionsRecord[convert_to_bytes(sub.index)] = sub

        # Parse Applications
        for app_record in root.findall(".//AllAppsRecord/AppRecord"):
            app = CDRApplicationRecord.from_xml(app_record)
            if isinstance(app.AppId, bytes):
                # Convert bytes to an integer
                app_id = int.from_bytes(app.AppId, byteorder="little")
            else:
                # Assume app.AppId is already an integer
                app_id = int(app.AppId)

            cdr.ApplicationsRecord[convert_to_bytes(app_id)] = app


        for key_elem in root.findall(".//AllAppsPublicKeysRecord/AppPublicKeyData"):
            key_record = PublicKeyRecord.from_xml(key_elem)
            if key_record.application_id is not None:
                cdr.AllAppsPublicKeysRecord[key_record.application_id] = key_record

        # Parse Encrypted Private Keys
        for key_elem in root.findall(
            ".//AllAppsEncryptedPrivateKeysRecord/AppPrivateKeyData"
        ):
            key_record = EncryptedPrivateKeyRecord.from_xml(key_elem)
            if key_record.application_id is not None:
                cdr.AllAppsEncryptedPrivateKeysRecord[key_record.application_id] = (
                    key_record
                )

        return cdr

    def to_dict(self, iscustom = False):
        result = {}
        for attr, key in self.mapping.items():
            value = getattr(self, attr)
            if value is not None:
                if attr == "VersionNumber" and not iscustom:
                    result[key] = value
                if attr == "ApplicationsRecord":
                    apps_dict = {}
                    for app_id, app in value.items():
                        apps_dict[app_id] = app.to_dict()
                    result[key] = apps_dict
                elif attr == "SubscriptionsRecord":
                    subs_dict = {}
                    for sub_id, sub in value.items():
                        subs_dict[sub_id] = sub.to_dict()
                    result[key] = subs_dict
                elif attr == "IndexAppIdToSubscriptionIdsRecord" and not iscustom:
                    index_dict = {}
                    if len(value.items()) > 0:
                        for app_id, index_rec in value.items():
                            index_dict[app_id] = index_rec.to_dict()
                        result[key] = index_dict
                elif attr == "AllAppsPublicKeysRecord":
                    if value:  # Only include if there are actual keys
                        keys_dict = {}
                        for app_id, key_rec in value.items():
                            keys_dict[app_id] = key_rec.to_dict()
                        result[key] = keys_dict
                elif attr == "AllAppsEncryptedPrivateKeysRecord":
                    if value:  # Only include if there are actual keys
                        keys_dict = {}
                        for app_id, key_rec in value.items():
                            keys_dict[app_id] = key_rec.to_dict()
                        result[key] = keys_dict
                elif not iscustom:
                    if not iscustom:
                        result[key] = convert_to_bytes(value)
                    else:
                        result[key] = value
        return result

    def add_application(self, app_id, application_record):
        self.ApplicationsRecord[app_id] = application_record

    def remove_application(self, app_id):
        if app_id in self.ApplicationsRecord:
            del self.ApplicationsRecord[app_id]

    def add_subscription(self, sub_id, subscription_record):
        self.SubscriptionsRecord[sub_id] = subscription_record

    def remove_subscription(self, sub_id):
        if sub_id in self.SubscriptionsRecord:
            del self.SubscriptionsRecord[sub_id]

    def add_public_key(self, app_id, public_key_record):
        self.AllAppsPublicKeysRecord[app_id] = public_key_record

    def remove_public_key(self, app_id):
        if app_id in self.AllAppsPublicKeysRecord:
            del self.AllAppsPublicKeysRecord[app_id]

    def add_private_key(self, app_id, private_key_record):
        self.AllAppsEncryptedPrivateKeysRecord[app_id] = private_key_record

    def remove_private_key(self, app_id):
        if app_id in self.AllAppsEncryptedPrivateKeysRecord:
            del self.AllAppsEncryptedPrivateKeysRecord[app_id]

    def set_optional_rate_limit(self, rate_limit_record):
        self.OptionalRateLimitRecord = rate_limit_record

    def get_app_name(self, app_id):
        """
        Retrieve the name of an app from the ContentDescriptionRecord using an integer app_id.

        Args:
            cdr (ContentDescriptionRecord): The ContentDescriptionRecord object.
            app_id (int): The app ID as an integer.

        Returns:
            str: The name of the app if found, or None if the app ID is not in the record.
        """
        # Convert the integer app_id to the byte format used in the ApplicationsRecord
        app_id_bytes = app_id.to_bytes(4, "little", signed=False)

        # Access the ApplicationsRecord and fetch the corresponding application
        app_record = self.ApplicationsRecord.get(app_id_bytes)

        if app_record and app_record.Name:
            # Decode the app name from bytes to a string, stripping any null terminators
            if isinstance(app_record.Name, bytes):
                app_name = app_record.Name.rstrip(b"\x00").decode("utf-8")
            else:
                app_name = app_record.Name.rstrip("\x00")
            return app_name

        return None

    def get_subscription(self, identifier: Union[int, str]) -> Optional["CDRSubscriptionRecord"]:
        """
        Retrieve a subscription record by its identifier.

        Args:
            identifier: Either an integer subscription ID or a subscription name string.

        Returns:
            The matching CDRSubscriptionRecord if found, else None.
        """
        # If the identifier is an integer, assume it is the subscription ID.
        if isinstance(identifier, int):
            # Convert the integer to the 4-byte little-endian format used as keys in SubscriptionsRecord.
            sub_key = identifier.to_bytes(4, byteorder="little", signed=False)
            return self.SubscriptionsRecord.get(sub_key)

        # If the identifier is a string, search through the subscriptions by name.
        elif isinstance(identifier, str):
            for sub in self.SubscriptionsRecord.values():
                sub_name = sub.Name
                if isinstance(sub_name, bytes):
                    sub_name = sub_name.rstrip(b"\x00").decode("utf-8")
                if sub_name == identifier:
                    return sub

        return None

    def get_onpurchase_guest_passes_info(self) -> dict:
        """
        Iterates through all subscriptions in the CDR and extracts information for those subscriptions
        that grant passes via extended info keys starting with "OnPurchaseGrantGuestPassPackage".

        For each granting subscription:
          - Its ID (converted to int) is used as the root key.
          - For each extended info key (normalized to a string) that starts with
            "OnPurchaseGrantGuestPassPackage", its value is assumed to be the target (pass) subscription ID.
          - Then the method looks up that target subscription record using get_subscription.
          - If found and if that target subscription has an ExtendedInfoRecord, then:
                ? For billing type "GuestPass": add keys from the target record?s ExtendedInfoRecord:
                    - "InitialPeriod" is stored as "activation_period"
                    - "InitialTimeUnit" is stored as "time_unit"
                    - "GrantPassesCount" is stored as "pass_count"
                    - "GrantExpirationDays" is stored as "pass_expiration_days"
                    - "AppIDOwnedRequired" is stored as "app_owned_required"
                ? Otherwise, for other billing types (e.g. "Gift"): add only:
                    - "GrantPassesCount" as "pass_count"
                    - "AppIDOwnedRequired" as "app_owned_required"
          - The result is a dictionary whose keys are the granting subscription IDs (as int) and whose values are dictionaries.
            In each such sub-dictionary, the keys are the target subscription IDs (as int, or a string if conversion fails)
            and the values are dictionaries with the extracted details.
        """
        result = {}
        for sub in self.SubscriptionsRecord.values():
            # Skip if there is no extended info.
            if not sub.ExtendedInfoRecord:
                continue

            # Normalize the granting subscription's ExtendedInfoRecord: convert all keys and values to strings.
            normalized_ext = {}
            for k, v in sub.ExtendedInfoRecord.items():
                key_str = k.decode('utf-8', errors='ignore') if isinstance(k, bytes) else str(k)
                value_str = v.decode('utf-8', errors='ignore') if isinstance(v, bytes) else str(v)
                normalized_ext[key_str] = value_str

            # Get all keys that start with "OnPurchaseGrantGuestPassPackage"
            grant_keys = [key for key in normalized_ext.keys() if key.startswith("OnPurchaseGrantGuestPassPackage")]
            if not grant_keys:
                continue

            # Convert the granting subscription's ID to an int.
            try:
                if isinstance(sub.SubscriptionId, bytes):
                    grant_sub_id = int.from_bytes(sub.SubscriptionId, byteorder='little')
                else:
                    grant_sub_id = int(sub.SubscriptionId)
            except Exception:
                continue

            # Initialize the result for this granting subscription.
            result[grant_sub_id] = {}

            # Get the billing type of the granting subscription.
            billing = sub.get_billing_type()  # e.g., "Gift", "GuestPass", etc.

            # For each grant key, process its value (the target subscription id).
            for key in grant_keys:
                target_value = normalized_ext.get(key)
                if not target_value or target_value.strip() == "":
                    continue
                try:
                    target_sub_id = int(target_value[:-1])
                except Exception:
                    target_sub_id = target_value.strip()  # if conversion fails, keep as string

                info = {"BillingType": billing}
                # Look up the subscription record for the target subscription id.

                target_sub = self.get_subscription(target_sub_id)
                if target_sub and target_sub.ExtendedInfoRecord:
                    # Normalize the target subscription's ExtendedInfoRecord.
                    normalized_target = {}
                    for tk, tv in target_sub.ExtendedInfoRecord.items():
                        tk_str = tk.decode('utf-8', errors='ignore') if isinstance(tk, bytes) else str(tk)
                        tv_str = tv.decode('utf-8', errors='ignore') if isinstance(tv, bytes) else str(tv)
                        normalized_target[tk_str] = tv_str.rstrip('\x00')

                    # If billing type is "GuestPass", add extra keys.

                    for orig_key, target_key in [
                        ("InitialPeriod", "InitialPeriod"),
                        ("InitialTimeUnit", "InitialTimeUnit"),
                        ("GrantPassesCount", "GrantPassesCount"),
                        ("GrantExpirationDays", "GrantExpirationDays"),
                        ("AppIDOwnedRequired", "AppIDOwnedRequired")
                    ]:
                        if orig_key in normalized_target and normalized_target[orig_key]:
                            info[target_key] = normalized_target[orig_key]

                # Save this info under the target subscription id.
                result[grant_sub_id][target_sub_id] = info

        return result

    def get_freeweekend_subscriptions_info(self) -> dict:
        """
        Iterates through all subscription records in the CDR and returns a dictionary.

        For each subscription that contains an extended info key named 'FreeWeekend',
        creates an entry in the result dictionary with:
          - key: the subscription ID (converted to int)
          - value: a dictionary containing only the keys (if present):
                'FreeWeekend', 'ExpiryTime', and 'DontGrantIfAppIDOwned'
              from the subscription's ExtendedInfoRecord.

        Returns:
            A dictionary mapping subscription IDs (int) to a dictionary of selected extended info.
        """
        result = {}
        for sub in self.SubscriptionsRecord.values():
            # Skip subscriptions without ExtendedInfoRecord.
            if not sub.ExtendedInfoRecord:
                continue

            # Normalize ExtendedInfoRecord: convert keys and values to UTF-8 strings.
            normalized_ext = {}
            for k, v in sub.ExtendedInfoRecord.items():
                key_str = k.decode('utf-8', errors='ignore') if isinstance(k, bytes) else str(k)
                value_str = v.decode('utf-8', errors='ignore') if isinstance(v, bytes) else str(v)
                normalized_ext[key_str] = value_str

            # Check if the subscription contains the key 'FreeWeekend'
            if "FreeWeekend" not in normalized_ext:
                continue

            # Build a sub-dictionary with only the keys we care about.
            info = {}
            for wanted_key in ["FreeWeekend", "ExpiryTime", "DontGrantIfAppIDOwned"]:
                if wanted_key in normalized_ext:
                    info[wanted_key] = normalized_ext[wanted_key]

            # Convert the subscription ID to an integer.
            try:
                if isinstance(sub.SubscriptionId, bytes):
                    sub_id = int.from_bytes(sub.SubscriptionId, byteorder='little')
                else:
                    sub_id = int(sub.SubscriptionId)
            except Exception:
                continue

            result[sub_id] = info

        return result

    def get_subscription_by_game_code(
        self,
        game_code: int,
        territory_code: Optional[int] = None
    ) -> Optional["CDRSubscriptionRecord"]:
        """
        Find a subscription by its game code (from CD key decoding).

        CD keys encode a 7-bit game code that maps to subscription GameCode fields
        in the CDR. This method finds the matching subscription.

        Args:
            game_code: The 7-bit game code decoded from a CD key (0-127)
            territory_code: Optional 8-bit territory code to match (0-255).
                           If provided, both must match. If None, only game_code is matched.

        Returns:
            The matching CDRSubscriptionRecord if found, else None.
            If multiple subscriptions match, returns the first non-disabled one.
        """
        candidates = []

        for sub in self.SubscriptionsRecord.values():
            # Get the subscription's GameCode
            sub_game_code = sub.GameCode
            if sub_game_code is None:
                continue

            # Convert bytes to int if needed
            if isinstance(sub_game_code, bytes):
                try:
                    sub_game_code = int.from_bytes(sub_game_code, byteorder='little')
                except Exception:
                    continue
            else:
                try:
                    sub_game_code = int(sub_game_code)
                except Exception:
                    continue

            # Check if game code matches
            if sub_game_code != game_code:
                continue

            # If territory_code is specified, check it too
            if territory_code is not None:
                sub_territory = sub.TerritoryCode
                if sub_territory is not None:
                    if isinstance(sub_territory, bytes):
                        try:
                            sub_territory = int.from_bytes(sub_territory, byteorder='little')
                        except Exception:
                            sub_territory = None
                    else:
                        try:
                            sub_territory = int(sub_territory)
                        except Exception:
                            sub_territory = None

                    # If subscription has a territory code, it must match
                    if sub_territory is not None and sub_territory != 0:
                        if sub_territory != territory_code:
                            continue

            candidates.append(sub)

        if not candidates:
            return None

        # Prefer non-disabled subscriptions
        for sub in candidates:
            is_disabled = sub.IsDisabled
            if is_disabled is not None:
                if isinstance(is_disabled, bytes):
                    is_disabled = is_disabled[0] if is_disabled else 0
                if is_disabled:
                    continue
            return sub

        # Return first candidate if all are disabled
        return candidates[0] if candidates else None

    def get_subscription_id_by_game_code(
        self,
        game_code: int,
        territory_code: Optional[int] = None
    ) -> Optional[int]:
        """
        Find a subscription ID by game code (convenience method).

        Args:
            game_code: The 7-bit game code decoded from a CD key (0-127)
            territory_code: Optional 8-bit territory code to match (0-255)

        Returns:
            The subscription ID as an integer, or None if not found.
        """
        sub = self.get_subscription_by_game_code(game_code, territory_code)
        if sub is None:
            return None

        sub_id = sub.SubscriptionId
        if isinstance(sub_id, bytes):
            return int.from_bytes(sub_id, byteorder='little')
        return int(sub_id) if sub_id is not None else None

    def __repr__(self):
        return (
            f"ContentDescriptionRecord(\n"
            f"  VersionNumber={self.VersionNumber},\n"
            f"  ApplicationsRecord={self.ApplicationsRecord},\n"
            f"  SubscriptionsRecord={self.SubscriptionsRecord},\n"
            f"  LastChangedExistingAppOrSubscriptionTime={self.LastChangedExistingAppOrSubscriptionTime},\n"
            f"  IndexAppIdToSubscriptionIdsRecord={self.IndexAppIdToSubscriptionIdsRecord},\n"
            f"  AllAppsPublicKeysRecord={self.AllAppsPublicKeysRecord},\n"
            f"  AllAppsEncryptedPrivateKeysRecord={self.AllAppsEncryptedPrivateKeysRecord}\n"
            f")"
        )


class DictBlob:
    def __init__(self, filename):
        self.cdr = self.load_py_file(filename)

    def load_py_file(self, filename):

        # Extract a dynamic module name from the filename
        module_name = os.path.splitext(os.path.basename(filename))[0]

        # Create a module spec and load the module
        spec = importlib.util.spec_from_file_location(module_name, filename)
        blob_file = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(blob_file)

        # Access the 'data' attribute dynamically
        if not hasattr(blob_file, 'data'):
            raise AttributeError(f"The file {filename} does not define a 'data' attribute.")

        return ContentDescriptionRecord(blob_file.data)

    def __getattr__(self, item):
        return getattr(self.cdr, item)



class BinaryBlob:

    def __init__(self, filename):
        with open(filename, "rb") as f:
            blob_bin = f.read()
        self.cdr = ContentDescriptionRecord(self.blob_unserialize(blob_bin))

    def blob_unserialize(self, blobtext):
        if blobtext[0:2] == b"\x01\x43":
            # print("decompress")
            blobtext = zlib.decompress(blobtext[20:])

        blobdict = {}
        (totalsize, slack) = struct.unpack("<LL", blobtext[2:10])

        if slack:
            blobdict[b"__slack__"] = blobtext[-slack:]
        if (totalsize + slack) != len(blobtext):
            raise NameError("Blob not correct length including slack space!")
        index = 10
        while index < totalsize:
            namestart = index + 6
            (namesize, datasize) = struct.unpack("<HL", blobtext[index:namestart])
            datastart = namestart + namesize
            name = blobtext[namestart:datastart]
            dataend = datastart + datasize
            data = blobtext[datastart:dataend]
            if len(data) > 1 and data[0:2] == b"\x01\x50":
                sub_blob = self.blob_unserialize(data)
                blobdict[name] = sub_blob
            else:
                blobdict[name] = data
            index = index + 6 + namesize + datasize

        return blobdict

    def blob_serialize(self, blobdict):
        blobtext = b""

        for name, data in blobdict.items():

            if name == b"__slack__":
                continue

            # Ensure name is a bytes object
            name_bytes = name.encode() if isinstance(name, str) else name

            if isinstance(data, dict):
                data = self.blob_serialize(data)

            # Ensure data is in bytes format
            if isinstance(data, str):
                data = data.encode(
                    "ascii"
                )  # Convert string values to bytes using UTF-8 encoding (or the appropriate encoding)

            namesize = len(name_bytes)
            datasize = len(data)

            subtext = struct.pack("<HL", namesize, datasize)
            subtext = subtext + name_bytes + data
            blobtext = blobtext + subtext

        if b"__slack__" in blobdict:
            slack = blobdict[b"__slack__"]
        else:
            slack = b""

        totalsize = len(blobtext) + 10

        sizetext = struct.pack("<LL", totalsize, len(slack))

        # Convert size text to bytes and concatenate
        blobtext = b"\x01" + b"\x50" + sizetext + blobtext + slack

        return blobtext

    def blob_dump(self, blob, spacer=""):
        text = spacer + "{"
        spacer2 = spacer + "    "
        blobkeys = list(blob.keys())
        blobkeys.sort(key=self.sortkey)
        first = True
        for key in blobkeys:

            data = blob[key]
            if isinstance(data, dict):
                formatted_key = self.formatstring(key)
                formatted_data = self.blob_dump(data, spacer2)
            else:
                # Assuming formatstring handles other types appropriately
                formatted_key = self.formatstring(key)
                formatted_data = self.formatstring(data)

            if first:

                text += "" + spacer2 + formatted_key + ": " + formatted_data
                first = False
            else:
                text += "," + spacer2 + formatted_key + ": " + formatted_data

        text += spacer + "}"
        return text

    def blob_replace(self, blob_string, replacement_dict):
        # Pre-process replacements to ensure they're all string type and ready for use
        prepared_replacements = [
            (
                search.decode("latin-1"),
                replace.decode("latin-1"),
                info.decode("latin-1"),
            )
            for search, replace, info in replacement_dict
        ]

        # Perform replacements directly without intermediate checks
        for search_str, replace_str, info in prepared_replacements:
            if search_str in blob_string:
                blob_string = blob_string.replace(search_str, replace_str)
                # log.debug(f"Replaced {info} {search_str} with {replace_str}")
            # else:
            # log.debug(f"No occurrences of {info} found for replacement.")

        return blob_string

    def sortfunc(self, x):
        if isinstance(x, bytes) and len(x) == 4 and x[2] == 0x00:
            numx = struct.unpack("<L", x)[0]
            return numx
        else:
            return x

    def formatstring(self, text):
        if isinstance(text, bytes):
            if len(text) == 4 and text[2] == 0x00:
                return '"\\x%02x\\x%02x\\x%02x\\x%02x"' % (
                    text[0],
                    text[1],
                    text[2],
                    text[3],
                )
            else:
                # Exclude single quote (0x27) and backslash (0x5c) from direct output
                # to avoid breaking the string literal syntax
                return "'{}'".format(
                    "".join(chr(b) if 32 <= b <= 126 and b not in (0x27, 0x5c) else f"\\x{b:02x}" for b in text)
                )
        else:
            return repr(text)


"""Examples:

# List subscriptions based on certain criteria:
import globalvars

cdr = globalvars.CDR_DICTIONARY  # assuming you've loaded it via DictBlob or BinaryBlob
print("Subscriptions with 'freeweekends':")
for sub in cdr.freeweekends_subscriptions:
    print(f"  Subscription ID: {sub['SubscriptionId']}, Name: {sub['Name']}")

print("\nSubscriptions by Billing Type:")
for billing_type, subs in cdr.subscriptions_by_billing_type.items():
    print(f"Billing Type: {billing_type}")
    for sub in subs:
        print(f"  Subscription ID: {sub['SubscriptionId']}, Name: {sub['Name']}")

# Selecting a specific subscription by ID:
subscriptionvar = globalvars.CDR_DICTIONARY.get_subscription(123)

# List all discounts related to subscription:
discounts = subscriptionvar.list_discounts()
for disc in discounts:
    print(f"Discount: {disc['name']} (${disc['amount_dollars']:.2f})")
    for qualifier in disc['qualifiers']:
        print(f"  Qualifier: {qualifier['name']} (Subscription ID: {qualifier['subscription_id']})")

# List all qualifiers for the specific discount:
# Using discount ID (example: 1)
qualifiers = subscriptionvar.list_discount_qualifiers(1)
print("Qualifiers for discount 1:")
for q in qualifiers:
    print(q)

# Using discount name
qualifiers = subscriptionvar.list_discount_qualifiers("Holiday Discount")
print("Qualifiers for 'Holiday Discount':")
for q in qualifiers:
    print(q)

# Grab ALL subscriptionids (as list) for a specific discount from the qualifiers:
qualifier_ids = subscriptionvar.get_discount_qualifier_subscription_ids(1)
print("Subscription IDs for discount 1 qualifiers:", qualifier_ids)

# Get all giftpass/guestpass information related to the subscription:
if subscriptionvar:
    # Get billing type as a string
    print("Billing Type:", subscriptionvar.get_billing_type())

    # List all guest pass subscription IDs
    guest_pass_ids = subscriptionvar.get_guest_pass_subscription_ids()
    print("Guest Pass Subscription IDs:", guest_pass_ids)

    # Get the guest pass info dictionary
    guest_pass_info = subscriptionvar.get_guest_pass_info()
    print("Guest Pass Info:", guest_pass_info)
else:
    print("Subscription not found.")
    
    
# Get all gift/guest passes associated with the subscription:
passes_info = globalvars.CDR_DICTIONARY.get_onpurchase_guest_passes_info()
print("Gift Passes:", passes_info["giftpasses"])
print("Guest Passes:", passes_info["guestpasses"])
"""
