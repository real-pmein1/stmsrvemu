import ast
import importlib
import os
import pprint
import xml.etree.ElementTree as ET
import struct
import zlib
import datetime
from typing import Optional, Dict, Any, Union, List


class BillingTypeVar:
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


def get_element_text(element: ET.Element, tag: str) -> Optional[str]:
    subelement = element.find(tag)
    if subelement is not None and subelement.text is not None:
        return subelement.text.strip()
    else:
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


def current_timestamp() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class CDRLaunchOptionsRecord:
    def __init__(self, index=None):
        self.index: Optional[int] = index
        self.Description: Optional[str] = None
        self.CommandLine: Optional[str] = None
        self.AppIconIdx: Optional[int] = None
        self.NoDesktopShortcut: Optional[bool] = None
        self.NoStartMenuShortcut: Optional[bool] = None
        self.LongRunningUnattended: Optional[bool] = None
        self.ValidOSList: Optional[str] = None

        self.mapping = {
            b"\x01\x00\x00\x00": "Description",
            b"\x02\x00\x00\x00": "CommandLine",
            b"\x03\x00\x00\x00": "AppIconIdx",
            b"\x04\x00\x00\x00": "NoDesktopShortcut",
            b"\x05\x00\x00\x00": "NoStartMenuShortcut",
            b"\x06\x00\x00\x00": "LongRunningUnattended",
            b"\x07\x00\x00\x00": "ValidOSList",
        }

        self.single_byte_keys = {
                b"\x04\x00\x00\x00",
                b"\x05\x00\x00\x00",
                b"\x06\x00\x00\x00",
        }

    def to_dict(self) -> Dict[bytes, Any]:
        result = {}
        for key, attr in self.mapping.items():
            value = getattr(self, attr)
            if value is not None:
                if key in self.single_byte_keys:
                    # Serialize as single byte
                    result[key] = struct.pack("B", int(bool(value)))
                    # print(f"Packed single-byte boolean {attr}: {packed_value}")  # Debug
                else:
                    result[key] = convert_to_bytes(value)
                    # print(f"Packed {attr}: {packed_value}")  # Debug
        return result

    @staticmethod
    def from_dict(data: Dict[bytes, Any], index: int) -> "CDRLaunchOptionsRecord":
        record = CDRLaunchOptionsRecord(index)
        mapping = record.mapping
        for key, attr in mapping.items():
            if key in data:
                value = data[key]
                setattr(record, attr, value)
        return record

    @staticmethod
    def from_xml(option_record: ET.Element) -> "CDRLaunchOptionsRecord":
        index = convert_to_int(option_record.get("LaunchOptionIdx"))
        launch_option = CDRLaunchOptionsRecord(index)
        launch_option.Description = get_element_text(option_record, "Description")
        launch_option.CommandLine = get_element_text(option_record, "CommandLine")
        launch_option.AppIconIdx = convert_to_int(
            get_element_text(option_record, "AppIconIdx")
        )
        launch_option.NoDesktopShortcut = bool(
            int(get_element_text(option_record, "bNoDesktopShortcut") or 0)
        )
        launch_option.NoStartMenuShortcut = bool(
            int(get_element_text(option_record, "bNoStartMenuShortcut") or 0)
        )
        launch_option.LongRunningUnattended = bool(
            int(get_element_text(option_record, "bLongRunningUnattended") or 0)
        )
        launch_option.ValidOSList = get_element_text(option_record, "ValidOSList")
        return launch_option

    def __repr__(self):
        return (
            f"CDRLaunchOptionsRecord(index={self.index}, "
            f"Description={self.Description!r}, "
            f"CommandLine={self.CommandLine!r}, "
            f"IconIndex={self.AppIconIdx}, "
            f"NoDesktopShortcut={self.NoDesktopShortcut}, "
            f"NoStartMenuShortcut={self.NoStartMenuShortcut}, "
            f"LongRunningUnattended={self.LongRunningUnattended}, "
            f"ValidOSList={self.ValidOSList!r})"
        )


class CDRApplicationVersionRecord:
    def __init__(self, index=None):
        self.index: Optional[int] = index
        self.Description: Optional[str] = None
        self.VersionId: Optional[int] = None
        self.IsNotAvailable: Optional[bool] = None
        self.LaunchOptionIdsRecord: List[int] = []
        self.DepotEncryptionKey: Optional[str] = None
        self.IsEncryptionKeyAvailable: Optional[bool] = None
        self.IsRebased: Optional[bool] = None
        self.IsLongVersionRoll: Optional[bool] = None

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

        self.single_byte_keys = {
                b"\x03\x00\x00\x00",
                b"\x06\x00\x00\x00",
                b"\x07\x00\x00\x00",
                b"\x08\x00\x00\x00",
        }


    def to_dict(self) -> Dict[bytes, Any]:
        result = {}
        for key, attr in self.mapping.items():
            value = getattr(self, attr)
            if key == b"\x05\x00\x00\x00":
                if value is None:
                    result[key] = b"\x00"
            if value is not None:
                if key in self.single_byte_keys:
                    # Serialize as single byte
                    result[key] = struct.pack("B", int(bool(value)))
                    # print(f"Packed single-byte boolean {attr}: {packed_value}")  # Debug
                else:
                    if attr == "LaunchOptionIdsRecord":
                        # It's a list of integers
                        result[key] = {convert_to_bytes(idx): b"" for idx in value}
                    elif attr == "DepotEncryptionKey":
                        if value == b'':
                            result[key] = b'\x00'
                    elif isinstance(value, bool):
                        result[key] = convert_to_bytes(int(value))
                    elif isinstance(value, int):
                        result[key] = convert_to_bytes(value)
                    else:
                        result[key] = convert_to_bytes(value)
        return result

    @staticmethod
    def from_dict(data: Dict[bytes, Any], index: int) -> "CDRApplicationVersionRecord":
        record = CDRApplicationVersionRecord(index)
        mapping = record.mapping
        for key, attr in mapping.items():
            if key in data:
                value = data[key]
                setattr(record, attr, value)
        return record

    @staticmethod
    def from_xml(version_record: ET.Element) -> "CDRApplicationVersionRecord":
        index = convert_to_int(version_record.get("VersionId"))
        version = CDRApplicationVersionRecord(index)
        version.Description = get_element_text(version_record, "Description")
        version.VersionId = convert_to_int(
            get_element_text(version_record, "VersionId")
        )
        version.IsNotAvailable = bool(
            int(get_element_text(version_record, "bIsNotAvailable") or 0)
        )
        version.IsEncryptionKeyAvailable = bool(
            int(get_element_text(version_record, "bIsEncryptionKeyAvailable") or 0)
        )
        version.IsRebased = bool(
            int(get_element_text(version_record, "bIsRebased") or 0)
        )
        version.IsLongVersionRoll = bool(
            int(get_element_text(version_record, "bIsLongVersionRoll") or 0)
        )
        version.DepotEncryptionKey = get_element_text(
            version_record, "DepotEncryptionKey"
        )
        # Parse LaunchOptionIdsRecord
        for option_id_element in version_record.findall(
            ".//LaunchOptionIdsRecord/LaunchOptionId"
        ):
            option_id = convert_to_int(option_id_element.text)
            if option_id is not None:
                version.LaunchOptionIdsRecord.append(option_id)
        return version

    def __repr__(self):
        return (
            f"CDRApplicationVersionRecord(index={self.index}, "
            f"Description={self.Description!r}, "
            f"VersionId={self.VersionId}, "
            f"IsNotAvailable={self.IsNotAvailable}, "
            f"LaunchOptionIdsRecord={self.LaunchOptionIdsRecord}, "
            f"DepotEncryptionKey={self.DepotEncryptionKey!r}, "
            f"IsEncryptionKeyAvailable={self.IsEncryptionKeyAvailable}, "
            f"IsRebased={self.IsRebased}, "
            f"IsLongVersionRoll={self.IsLongVersionRoll})"
        )


class CDRFilesystemRecord:
    def __init__(self, index=None):
        self.index: Optional[int] = index
        self.AppId: Optional[int] = None
        self.MountName: Optional[str] = None
        self.IsOptional: Optional[bool] = None
        self.ValidOSList: Optional[str] = None

        self.mapping = {
            b"\x01\x00\x00\x00": "AppId",
            b"\x02\x00\x00\x00": "MountName",
            b"\x03\x00\x00\x00": "IsOptional",
            b"\x04\x00\x00\x00": "ValidOSList",
        }
        self.single_byte_keys = {
            b"\x03\x00\x00\x00",
        }

    def to_dict(self) -> Dict[bytes, Any]:
        result = {}
        for key, attr in self.mapping.items():
            value = getattr(self, attr)
            # Special handling for MountName (key b"\x02\x00\x00\x00")
            if key == b"\x02\x00\x00\x00":
                if value is not None:
                    result[key] = convert_to_bytes(value)
                    # print(f"Packed {attr}: {packed_value}")  # Debug
                else:
                    result[key] = b'\x00'
                    # print(f"Packed {attr} as empty: {packed_value}")  # Debug
                continue  # Move to the next key
            if value is not None:
                if key in self.single_byte_keys:
                    # Serialize as single byte
                    result[key] = struct.pack("B", int(bool(value)))
                    # print(f"Packed single-byte boolean {attr}: {packed_value}")  # Debug
                else:
                    if isinstance(value, bool):
                        result[key] = convert_to_bytes(int(value))
                    elif isinstance(value, int):
                        result[key] = convert_to_bytes(value)
                    else:
                        result[key] = convert_to_bytes(value)
        return result

    @staticmethod
    def from_dict(data: Dict[bytes, Any], index: int) -> "CDRFilesystemRecord":
        record = CDRFilesystemRecord(index)
        mapping = record.mapping
        for key, attr in mapping.items():
            if key in data:
                value = data[key]
                setattr(record, attr, value)
        return record

    @staticmethod
    def from_xml(fs_record: ET.Element) -> "CDRFilesystemRecord":
        filesystem = CDRFilesystemRecord()
        filesystem.index = convert_to_int(fs_record.get("FilesystemIdx"))
        filesystem.AppId = convert_to_int(get_element_text(fs_record, "AppId"))
        filesystem.MountName = get_element_text(fs_record, "MountName")
        filesystem.IsOptional = bool(
            int(get_element_text(fs_record, "IsOptional") or 0)
        )
        filesystem.ValidOSList = get_element_text(fs_record, "ValidOSList")
        return filesystem

    def __repr__(self):
        return (
            f"CDRFilesystemRecord(index={self.index}, "
            f"AppId={self.AppId}, "
            f"MountName={self.MountName!r}, "
            f"IsOptional={self.IsOptional}, "
            f"ValidOSList={self.ValidOSList!r})"
        )


class CDRAppRegionRecord:
    def __init__(self, index=None):
        self.index: Optional[int] = index
        self.CountryList: Optional[str] = None
        self.AppUserDefinedRecord: Dict[str, Any] = {}
        self.FilesystemsRecord: Dict[int, CDRFilesystemRecord] = {}

        self.mapping = {
            b"\x01\x00\x00\x00": "CountryList",
            b"\x02\x00\x00\x00": "AppUserDefinedRecord",
            b"\x03\x00\x00\x00": "FilesystemsRecord",
        }

    def to_dict(self) -> Dict[bytes, Any]:
        result = {}
        for key, attr in self.mapping.items():
            value = getattr(self, attr)
            if value:
                if attr == "AppUserDefinedRecord":
                    value_dict = {
                        convert_to_bytes(k): convert_to_bytes(v)
                        for k, v in value.items()
                    }
                    result[key] = value_dict
                elif attr == "FilesystemsRecord":
                    value_dict = {
                        convert_to_bytes(idx): fs.to_dict() for idx, fs in value.items()
                    }
                    result[key] = value_dict
                else:
                    result[key] = convert_to_bytes(value)
        return result

    @staticmethod
    def from_dict(data: Dict[bytes, Any], index: int) -> "CDRAppRegionRecord":
        record = CDRAppRegionRecord(index)
        mapping = record.mapping
        for key, attr in mapping.items():
            if key in data:
                value = data[key]
                setattr(record, attr, value)
        return record

    @staticmethod
    def from_xml(region_record: ET.Element) -> 'CDRAppRegionRecord':
        record = CDRAppRegionRecord()
        record.index = convert_to_int(region_record.get('Idx'))
        record.CountryList = get_element_text(region_record, 'CountryList')
        # Parse AppUserDefinedRecord
        user_defined_elem = region_record.find('AppUserDefinedRecord')
        if user_defined_elem is not None:
            for item in user_defined_elem:
                record.AppUserDefinedRecord[item.tag] = item.text
        # Parse FilesystemsRecord
        for fs_record in region_record.findall(".//FilesystemsRecord/FilesystemRecord"):
            fs = CDRFilesystemRecord.from_xml(fs_record)
            record.FilesystemsRecord[fs.index] = fs
        return record

    def __repr__(self):
        return (
            f"CDRAppRegionRecord(index={self.index}, "
            f"CountryList={self.CountryList!r}, "
            f"AppUserDefinedRecord={self.AppUserDefinedRecord}, "
            f"FilesystemsRecord={self.FilesystemsRecord})"
        )


class CDRApplicationRecord:
    def __init__(self, index=None):
        self.index: Optional[int] = index
        self.AppId: Optional[int] = None
        self.Name: Optional[str] = None
        self.InstallDirName: Optional[str] = None
        self.MinCacheFileSizeMB: Optional[int] = None
        self.MaxCacheFileSizeMB: Optional[int] = None
        self.AppLaunchOptionsRecord: Dict[int, CDRLaunchOptionsRecord] = {}
        self.AppIconsRecord: Dict[int, Any] = {}
        self.OnFirstLaunch: Optional[int] = None
        self.IsBandwidthGreedy: Optional[bool] = None
        self.AppVersionsRecord: Dict[int, CDRApplicationVersionRecord] = {}
        self.CurrentVersionId: Optional[int] = None
        self.FilesystemsRecord: Dict[int, CDRFilesystemRecord] = {}
        self.TrickleVersionId: Optional[int] = None
        self.AppUserDefinedRecord: Dict[str, str] = {}
        self.BetaVersionPassword: Optional[str] = None
        self.BetaVersionId: Optional[int] = None
        self.LegacyInstallDirName: Optional[str] = None
        self.SkipMFPOverwrite: Optional[bool] = None
        self.UseFilesystemDvr: Optional[bool] = None
        self.ManifestOnlyApp: Optional[bool] = None
        self.AppOfManifestOnlyCache: Optional[int] = None
        self.RegionSpecificRecords: Dict[int, CDRAppRegionRecord] = {}

        self.mapping = {
            b"\x01\x00\x00\x00": "AppId",
            b"\x02\x00\x00\x00": "Name",
            b"\x03\x00\x00\x00": "InstallDirName",
            b"\x04\x00\x00\x00": "MinCacheFileSizeMB",
            b"\x05\x00\x00\x00": "MaxCacheFileSizeMB",
            b"\x06\x00\x00\x00": "AppLaunchOptionsRecord",
            b"\x07\x00\x00\x00": "AppIconsRecord",
            b"\x08\x00\x00\x00": "OnFirstLaunch",
            b"\x09\x00\x00\x00": "IsBandwidthGreedy",
            b"\x0a\x00\x00\x00": "AppVersionsRecord",
            b"\x0b\x00\x00\x00": "CurrentVersionId",
            b"\x0c\x00\x00\x00": "FilesystemsRecord",
            b"\x0d\x00\x00\x00": "TrickleVersionId",
            b"\x0e\x00\x00\x00": "AppUserDefinedRecord",
            b"\x0f\x00\x00\x00": "BetaVersionPassword",
            b"\x10\x00\x00\x00": "BetaVersionId",
            b"\x11\x00\x00\x00": "LegacyInstallDirName",
            b"\x12\x00\x00\x00": "SkipMFPOverwrite",
            b"\x13\x00\x00\x00": "UseFilesystemDvr",
            b"\x14\x00\x00\x00": "ManifestOnlyApp",
            b"\x15\x00\x00\x00": "AppOfManifestOnlyCache",
            b"\x16\x00\x00\x00": "RegionSpecificRecords",
        }

    def to_dict(self) -> Dict[bytes, Any]:
        result = {}
        for key, attr in self.mapping.items():
            value = getattr(self, attr)
            if attr == "IsBandwidthGreedy" or attr == "SkipMFPOverwrite" or attr == "UseFilesystemDvr" or attr == "ManifestOnlyApp":
                if value is not None:
                    # Serialize as 2-byte unsigned short
                    result[key] = struct.pack("<B", int(bool(value)))
                else:
                    result[key] = b'\x00'
            else:
                if value is not None:
                    if attr == "AppLaunchOptionsRecord":
                        # It's a dict of CDRLaunchOptionsRecord instances
                        value_dict = {
                            convert_to_bytes(idx): opt.to_dict()
                            for idx, opt in value.items()
                        }
                        result[key] = value_dict
                    elif attr == "AppIconsRecord":
                        # Assuming AppIconsRecord is a dict of raw data
                        value_dict = {
                            convert_to_bytes(idx): data for idx, data in value.items()
                        }
                        result[key] = value_dict
                    elif attr == "AppVersionsRecord":
                        # It's a dict of CDRApplicationVersionRecord instances
                        value_dict = {
                            convert_to_bytes(idx): ver.to_dict()
                            for idx, ver in value.items()
                        }
                        result[key] = value_dict
                    elif attr == "FilesystemsRecord":
                        # It's a dict of CDRFilesystemRecord instances
                        value_dict = {
                            convert_to_bytes(idx): fs.to_dict() for idx, fs in value.items()
                        }
                        result[key] = value_dict
                    elif attr == "AppUserDefinedRecord":
                        # It's a dict of string key-value pairs
                        value_dict = {
                            convert_to_bytes(k): (convert_to_bytes(v) or b'\x00')
                            for k, v in value.items()
                        }
                        result[key] = value_dict
                    elif attr == "RegionSpecificRecords":
                        # It's a dict of CDRAppRegionRecord instances
                        value_dict = {
                            convert_to_bytes(idx): reg.to_dict()
                            for idx, reg in value.items()
                        }
                        if value_dict != {}:
                            result[key] = value_dict
                    elif isinstance(value, bool):
                        # Serialize as single byte for other bools
                        result[key] = convert_to_bytes(int(value))
                    elif isinstance(value, int):
                        # Serialize integers appropriately
                        result[key] = convert_to_bytes(value)
                    else:
                        # Serialize other types using convert_to_bytes
                        result[key] = convert_to_bytes(value)
        return result

    @staticmethod
    def from_dict(data: Dict[bytes, Any], index: int) -> "CDRApplicationRecord":
        record = CDRApplicationRecord(index)
        mapping = record.mapping
        for key, attr in mapping.items():
            if key in data:
                value = data[key]
                setattr(record, attr, value)
        return record

    @staticmethod
    def from_xml(app_record: ET.Element) -> "CDRApplicationRecord":
        app_id = convert_to_int(get_element_text(app_record, "AppId"))
        app = CDRApplicationRecord(app_id)
        app.AppId = app_id
        app.Name = get_element_text(app_record, "Name")
        app.InstallDirName = get_element_text(app_record, "InstallDirName")
        app.MinCacheFileSizeMB = convert_to_int(
            get_element_text(app_record, "MinCacheFileSizeMB")
        )
        app.MaxCacheFileSizeMB = convert_to_int(
            get_element_text(app_record, "MaxCacheFileSizeMB")
        )
        app.OnFirstLaunch = convert_to_int(
            get_element_text(app_record, "OnFirstLaunch")
        )
        app.IsBandwidthGreedy = bool(
            int(get_element_text(app_record, "IsBandwidthGreedy") or 0)
        )
        app.CurrentVersionId = convert_to_int(
            get_element_text(app_record, "CurrentVersionId")
        )
        app.TrickleVersionId = convert_to_int(
            get_element_text(app_record, "TrickleVersionId")
        )
        app.BetaVersionPassword = get_element_text(app_record, "BetaVersionPassword")
        app.BetaVersionId = convert_to_int(
            get_element_text(app_record, "BetaVersionId")
        )
        app.LegacyInstallDirName = get_element_text(app_record, "LegacyInstallDirName")
        app.SkipMFPOverwrite = bool(
            int(get_element_text(app_record, "SkipMFPOverwrite") or 0)
        )
        app.UseFilesystemDvr = bool(
            int(get_element_text(app_record, "UseFilesystemDvr") or 0)
        )
        app.ManifestOnlyApp = bool(
            int(get_element_text(app_record, "ManifestOnlyApp") or 0)
        )
        app.AppOfManifestOnlyCache = convert_to_int(
            get_element_text(app_record, "AppOfManifestOnlyCache")
        )
        # Parse AppLaunchOptionsRecord
        for option_record in app_record.findall(
            ".//AppLaunchOptionsRecord/AppLaunchOptionRecord"
        ):
            launch_option = CDRLaunchOptionsRecord.from_xml(option_record)
            app.AppLaunchOptionsRecord[launch_option.index] = launch_option
        # Parse AppVersionsRecord
        for version_record in app_record.findall(
            ".//AppVersionsRecord/AppVersionRecord"
        ):
            version = CDRApplicationVersionRecord.from_xml(version_record)
            app.AppVersionsRecord[version.index] = version
        # Parse FilesystemsRecord
        for fs_record in app_record.findall(".//FilesystemsRecord/FilesystemRecord"):
            filesystem = CDRFilesystemRecord.from_xml(fs_record)
            app.FilesystemsRecord[filesystem.index] = filesystem
        # Parse AppUserDefinedRecord
        user_defined_elem = app_record.find("AppUserDefinedRecord")
        if user_defined_elem is not None:
            for item in user_defined_elem:
                app.AppUserDefinedRecord[item.tag] = item.text
        # Parse RegionSpecificRecords
        for region_record in app_record.findall(
            ".//RegionSpecificRecords/AppRegionRecord"
        ):
            region = CDRAppRegionRecord.from_xml(region_record)
            app.RegionSpecificRecords[region.index] = region
        return app

    def __repr__(self):
        return (
            f"\nCDRApplicationRecord(AppId={self.AppId}, "
            f"\nName={self.Name!r}, "
            f"\nInstallDirName={self.InstallDirName!r}, "
            f"\nMinCacheFileSizeMB={self.MinCacheFileSizeMB}, "
            f"\nMaxCacheFileSizeMB={self.MaxCacheFileSizeMB}, "
            f"\nAppLaunchOptionsRecord={self.AppLaunchOptionsRecord}, "
            f"\nAppIconsRecord={self.AppIconsRecord}, "
            f"\nOnFirstLaunch={self.OnFirstLaunch}, "
            f"\nIsBandwidthGreedy={self.IsBandwidthGreedy}, "
            f"\nAppVersionsRecord={self.AppVersionsRecord}, "
            f"\nCurrentVersionId={self.CurrentVersionId}, "
            f"\nFilesystemsRecord={self.FilesystemsRecord}, "
            f"\nTrickleVersionId={self.TrickleVersionId}, "
            f"\nAppUserDefinedRecord={self.AppUserDefinedRecord}, "
            f"\nBetaVersionPassword={self.BetaVersionPassword!r}, "
            f"\nBetaVersionId={self.BetaVersionId}, "
            f"\nLegacyInstallDirName={self.LegacyInstallDirName}, "
            f"\nSkipMFPOverwrite={self.SkipMFPOverwrite}, "
            f"\nUseFilesystemDvr={self.UseFilesystemDvr}, "
            f"\nManifestOnlyApp={self.ManifestOnlyApp}, "
            f"\nAppOfManifestOnlyCache={self.AppOfManifestOnlyCache}, "
            f"\nRegionSpecificRecords={self.RegionSpecificRecords})\n"
        )


class OptionalRateLimitRecord:
    def __init__(self):
        self.index: Optional[int] = None
        self.LimitInMB: Optional[int] = None
        self.PeriodInSeconds: Optional[int] = None

        self.mapping = {
            b"\x01\x00\x00\x00": "LimitInMB",
            b"\x02\x00\x00\x00": "PeriodInSeconds",
        }

    def to_dict(self) -> Dict[bytes, Any]:
        result = {}
        for key, attr in self.mapping.items():
            value = getattr(self, attr)
            if value is not None:
                result[key] = convert_to_bytes(value)
        return result

    @staticmethod
    def from_dict(data: Dict[bytes, Any]) -> "OptionalRateLimitRecord":
        record = OptionalRateLimitRecord()
        mapping = record.mapping
        for key, attr in mapping.items():
            if key in data:
                value = data[key]
                setattr(record, attr, value)
        return record

    @staticmethod
    def from_xml(ratelimit_record: ET.Element) -> "OptionalRateLimitRecord":
        record = OptionalRateLimitRecord()
        record.LimitInMB = convert_to_int(ratelimit_record.get("Limit"))
        period_in_minutes = convert_to_int(
            get_element_text(ratelimit_record, "PeriodInMinutes")
        )
        if period_in_minutes is not None:
            record.PeriodInSeconds = period_in_minutes * 60
        return record

    def __repr__(self):
        return (
            f"\nOptionalRateLimitRecord(LimitInMB={self.LimitInMB}, "
            f"\nPeriodInSeconds={self.PeriodInSeconds})\n"
        )


class CDRDiscountQualifierRecord:
    def __init__(self, index=None):
        self.index: Optional[int] = index
        self.Name: Optional[str] = None
        self.SubscriptionId: Optional[int] = None

        self.mapping = {
            b"\x01\x00\x00\x00": "Name",
            b"\x02\x00\x00\x00": "SubscriptionId",
        }

    def to_dict(self) -> Dict[bytes, Any]:
        result = {}
        for key, attr in self.mapping.items():
            value = getattr(self, attr)
            if value is not None:
                if isinstance(value, int):
                    result[key] = convert_to_bytes(value)
                else:
                    result[key] = convert_to_bytes(value)
        return result

    @staticmethod
    def from_dict(data: Dict[bytes, Any], index: int) -> "CDRDiscountQualifierRecord":
        record = CDRDiscountQualifierRecord(index)
        mapping = record.mapping
        for key, attr in mapping.items():
            if key in data:
                value = data[key]
                setattr(record, attr, value)
        return record

    @staticmethod
    def from_xml(qualifier_record: ET.Element) -> "CDRDiscountQualifierRecord":
        record = CDRDiscountQualifierRecord()
        record.index = convert_to_int(qualifier_record.get("id"))
        record.Name = get_element_text(qualifier_record, "Name")
        record.SubscriptionId = convert_to_int(
            get_element_text(qualifier_record, "SubscriptionId")
        )
        return record

    def __repr__(self):
        return (
            f"\nCDRDiscountQualifierRecord(index={self.index}, "
            f"\nName={self.Name!r}, "
            f"\nSubscriptionId={self.SubscriptionId})\n"
        )


class CDRDiscountRecord:
    def __init__(self, index=None):
        self.index: Optional[int] = index
        self.Name: Optional[str] = None
        self.DiscountInCents: Optional[int] = None
        self.DiscountQualifiers: Dict[int, CDRDiscountQualifierRecord] = {}

        self.mapping = {
            b"\x01\x00\x00\x00": "Name",
            b"\x02\x00\x00\x00": "DiscountInCents",
            b"\x03\x00\x00\x00": "DiscountQualifiers",
        }

    def to_dict(self) -> Dict[bytes, Any]:
        result = {}
        for key, attr in self.mapping.items():
            value = getattr(self, attr)
            if value:
                if attr == "DiscountQualifiers":
                    value_dict = {
                        convert_to_bytes(idx): dq.to_dict() for idx, dq in value.items()
                    }
                    result[key] = value_dict
                elif isinstance(value, int):
                    result[key] = convert_to_bytes(value)
                else:
                    result[key] = convert_to_bytes(value)
        return result

    @staticmethod
    def from_dict(data: Dict[bytes, Any], index: int) -> "CDRDiscountRecord":
        record = CDRDiscountRecord(index)
        mapping = record.mapping
        for key, attr in mapping.items():
            if key in data:
                value = data[key]
                setattr(record, attr, value)
        return record

    @staticmethod
    def from_xml(discount_record: ET.Element) -> 'CDRDiscountRecord':
        record = CDRDiscountRecord()
        record.index = convert_to_int(discount_record.get('id'))
        record.Name = get_element_text(discount_record, 'Name')
        record.DiscountInCents = convert_to_int(get_element_text(discount_record, 'DiscountInCents'))
        # Parse DiscountQualifiers
        for qualifier_record in discount_record.findall('.//SubscriptionDiscountQualifiersRecord/SubscriptionDiscountQualifierRecord'):
            dq = CDRDiscountQualifierRecord.from_xml(qualifier_record)
            record.DiscountQualifiers[dq.index] = dq
        return record

    def __repr__(self):
        return (
            f"\nCDRDiscountRecord(index={self.index}, "
            f"\nName={self.Name!r}, "
            f"\nDiscountInCents={self.DiscountInCents}, "
            f"\nDiscountQualifiers={self.DiscountQualifiers})\n"
        )


class CDRSubscriptionRecord:
    def __init__(self, index=None):
        self.index: Optional[int] = index
        self.SubscriptionId: Optional[int] = None
        self.Name: Optional[str] = None
        self.BillingType: Optional[int] = None
        self.CostInCents: Optional[int] = None
        self.AppIdsRecord: Dict[int, bytes] = {}
        self.RunAppId: Optional[int] = None
        self.OnSubscribeRunLaunchOptionIndex: Optional[int] = None
        self.OptionalRateLimitRecord: Optional[OptionalRateLimitRecord] = None
        self.DiscountsRecord: Dict[int, CDRDiscountRecord] = {}
        self.IsPreorder: Optional[bool] = None
        self.RequiresShippingAddress: Optional[bool] = None
        self.DomesticCostInCents: Optional[int] = None
        self.InternationalCostInCents: Optional[int] = None
        self.RequiredKeyType: Optional[int] = None
        self.IsCyberCafe: Optional[bool] = None
        self.GameCode: Optional[int] = None
        self.GameCodeDescription: Optional[str] = None
        self.IsDisabled: Optional[bool] = None
        self.RequiresCD: Optional[bool] = None
        self.TerritoryCode: Optional[int] = None
        self.IsSteam3Subscription: Optional[bool] = None
        self.ExtendedInfoRecord: Dict[str, str] = {}

        self.mapping = {
            b"\x01\x00\x00\x00": "SubscriptionId",
            b"\x02\x00\x00\x00": "Name",
            b"\x03\x00\x00\x00": "BillingType", # 2 bytes
            b"\x04\x00\x00\x00": "CostInCents",
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

        self.single_byte_keys = {
                b"\x0b\x00\x00\x00",
                b"\x0c\x00\x00\x00",
                b"\x10\x00\x00\x00",
                b"\x13\x00\x00\x00",
                b"\x14\x00\x00\x00",
                b"\x16\x00\x00\x00",
        }

    def to_dict(self) -> Dict[bytes, Any]:
        result = {}
        for key, attr in self.mapping.items():
            value = getattr(self, attr)
            if value is not None:  # Explicitly check for None
                if attr == "BillingType":  # BillingType is 2 bytes
                    result[key] = struct.pack("<H", int(value))
                elif key in self.single_byte_keys:
                    result[key] = struct.pack("B", int(bool(value)))
                else:
                    if attr == "AppIdsRecord":
                        result[key] = {
                                app_id:b"" for app_id in value.keys()
                        }
                    if attr in ["CostInCents", "RunAppId", "OnSubscribeRunLaunchOptionIndex", "DomesticCostInCents", "InternationalCostInCents", "RequiredKeyType", ]:
                        result[key] = struct.pack("<I", int(value))
                    elif attr == "OptionalRateLimitRecord":
                        # FIXME formally support this type, i dont believe it is used clientside at all though
                        # result[key] = value.to_dict()
                        pass
                    elif attr == "DiscountsRecord":
                        value_dict = {
                                convert_to_bytes(idx):disc.to_dict()
                                for idx, disc in value.items()
                        }
                        result[key] = value_dict
                        if value_dict != {}:
                            result[key] = value_dict
                    elif attr == "ExtendedInfoRecord":
                        value_dict = {
                                convert_to_bytes(k):(convert_to_bytes(v) or b'\x00')
                                for k, v in value.items()
                        }
                        if value_dict != {}:
                            result[key] = value_dict
                    elif isinstance(value, int):
                        result[key] = convert_to_bytes(value)
                    else:
                        result[key] = convert_to_bytes(value)
        return result

    @staticmethod
    def from_dict(data: Dict[bytes, Any], index: int) -> "CDRSubscriptionRecord":
        record = CDRSubscriptionRecord(index)
        mapping = record.mapping
        for key, attr in mapping.items():
            if key in data:
                value = data[key]
                setattr(record, attr, value)
        return record

    @staticmethod
    def from_xml(subscription_record):
        sub = CDRSubscriptionRecord()
        sub.SubscriptionId = convert_to_int(
            subscription_record.findtext("SubscriptionId")
        )
        sub.Name = subscription_record.findtext("Name")
        billing_type_str = subscription_record.findtext("BillingType")
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
        sub.BillingType = billing_type_map.get(billing_type_str, 0)
        # print(sub.BillingType)
        sub.CostInCents = subscription_record.findtext("CostInCents")
        sub.RunAppId = subscription_record.findtext("OnSubscribeRunAppId")
        sub.OnSubscribeRunLaunchOptionIndex = subscription_record.findtext(
            "OnSubscribeRunLaunchOptionIdx"
        )

        # Parse AppIdsRecord
        for app_id_element in subscription_record.findall(
            ".//SubscriptionAppIdsRecord/AppId"
        ):
            app_id = struct.pack("<I", int(app_id_element.text))
            sub.AppIdsRecord[app_id] = b""

        # Parse OptionalRateLimitRecord and DiscountsRecord
        all_discounts_elem = subscription_record.findtext('AllDiscountsRecord')
        if all_discounts_elem is not None:
            # OptionalRateLimitRecord
            rate_limit_elem = all_discounts_elem.findtext('OptionalRateLimitRecord')
            if rate_limit_elem is not None:
                sub.OptionalRateLimitRecord = OptionalRateLimitRecord.from_xml(rate_limit_elem)
            # DiscountsRecord
            for discount_elem in all_discounts_elem.findall('SubscriptionDiscountRecord'):
                discount = CDRDiscountRecord.from_xml(discount_elem)
                sub.DiscountsRecord[discount.index] = discount
        return sub

    def __repr__(self):
        return (
            f"\nCDRSubscriptionRecord(SubscriptionId={self.SubscriptionId}, "
            f"\nName={self.Name!r}, "
            f"\nBillingType={self.BillingType}, "
            f"\nCostInCents={self.CostInCents}, "
            f"\nAppIdsRecord={self.AppIdsRecord}, "
            f"\nRunAppId={self.RunAppId}, "
            f"\nOnSubscribeRunLaunchOptionIndex={self.OnSubscribeRunLaunchOptionIndex}, "
            f"\nOptionalRateLimitRecord={self.OptionalRateLimitRecord}, "
            f"\nDiscountsRecord={self.DiscountsRecord},"
            f"\nIsPreorder={self.IsPreorder}, "
            f"\nRequiresShippingAddress={self.RequiresShippingAddress}, "
            f"\nDomesticCostInCents={self.DomesticCostInCents}, "
            f"\nInternationalCostInCents={self.InternationalCostInCents}, "
            f"\nRequiredKeyType={self.RequiredKeyType}, "
            f"\nIsCyberCafe={self.IsCyberCafe}, "
            f"\nGameCode={self.GameCode}, "
            f"\nGameCodeDescription={self.GameCodeDescription}, "
            f"\nIsDisabled={self.IsDisabled}, "
            f"\nRequiresCD={self.RequiresCD}, "
            f"\nTerritoryCode={self.TerritoryCode}, "
            f"\nIsSteam3Subscription={self.IsSteam3Subscription}, "
            f"\nExtendedInfoRecord={self.ExtendedInfoRecord})\n"
        )


class IndexAppIdToSubscriptionIdsRecord:
    def __init__(self, application_id=None):
        self.application_id: Optional[int] = application_id
        self.subscriptions: Dict[int, None] = {}

    def to_dict(self) -> Dict[bytes, Any]:
        return {convert_to_bytes(sub_id): b"" for sub_id in self.subscriptions.keys()}

    @staticmethod
    def from_dict(
        data: Dict[bytes, Any], application_id: int
    ) -> "IndexAppIdToSubscriptionIdsRecord":
        record = IndexAppIdToSubscriptionIdsRecord(application_id)
        record.subscriptions = data
        return record

    @staticmethod
    def from_xml(element: ET.Element) -> "IndexAppIdToSubscriptionIdsRecord":
        app_id = convert_to_int(element.get("AppId"))
        record = IndexAppIdToSubscriptionIdsRecord(app_id)
        for sub_id_elem in element.findall("SubscriptionId"):
            sub_id = convert_to_int(sub_id_elem.text)
            if sub_id is not None:
                record.subscriptions[sub_id] = None
        return record

    def __repr__(self):
        return (
            f"\nIndexAppIdToSubscriptionIdsRecord(application_id={self.application_id}, "
            f"\nsubscriptions={list(self.subscriptions.keys())})\n"
        )


class PublicKeyRecord:
    def __init__(self, application_id=None):
        self.application_id: Optional[int] = application_id
        self.key_data: Optional[bytes] = None

    def to_dict(self) -> bytes:
        return self.key_data

    @staticmethod
    def from_dict(data: bytes, application_id: int) -> "PublicKeyRecord":
        record = PublicKeyRecord(application_id)
        record.key_data = data
        return record

    @staticmethod
    def from_xml(element: ET.Element) -> "PublicKeyRecord":
        app_id = convert_to_int(element.get("KeyIdx"))
        record = PublicKeyRecord(app_id)
        text = element.text.strip() if element.text else ""
        if text.startswith("0x"):
            text = text[2:]
        record.key_data = bytes.fromhex(text)
        return record

    def __repr__(self):
        key_data_hex = self.key_data.hex() if self.key_data else None
        return (
            f"\nPublicKeyRecord(application_id={self.application_id}, "
            f"\nkey_data=0x{key_data_hex})\n"
        )


class EncryptedPrivateKeyRecord:
    def __init__(self, application_id=None):
        self.application_id: Optional[int] = application_id
        self.key_data: Optional[bytes] = None

    def to_dict(self) -> bytes:
        return self.key_data

    @staticmethod
    def from_dict(data: bytes, application_id: int) -> "EncryptedPrivateKeyRecord":
        record = EncryptedPrivateKeyRecord(application_id)
        record.key_data = data
        return record

    @staticmethod
    def from_xml(element: ET.Element) -> "EncryptedPrivateKeyRecord":
        app_id = convert_to_int(element.get("KeyIdx"))
        record = EncryptedPrivateKeyRecord(app_id)
        text = element.text.strip() if element.text else ""
        if text.startswith("0x"):
            text = text[2:]
        record.key_data = bytes.fromhex(text)
        return record

    def __repr__(self):
        key_data_hex = self.key_data.hex() if self.key_data else None
        return (
            f"\nEncryptedPrivateKeyRecord(application_id={self.application_id}, "
            f"\nkey_data=0x{key_data_hex})\n"
        )


class ContentDescriptionRecord:
    mapping = {
        b"\x00\x00\x00\x00": "VersionNumber",
        b"\x01\x00\x00\x00": "ApplicationsRecord",
        b"\x02\x00\x00\x00": "SubscriptionsRecord",
        b"\x03\x00\x00\x00": "LastChangedExistingAppOrSubscriptionTime",
        b"\x04\x00\x00\x00": "IndexAppIdToSubscriptionIdsRecord",
        b"\x05\x00\x00\x00": "AllAppsPublicKeysRecord",
        b"\x06\x00\x00\x00": "AllAppsEncryptedPrivateKeysRecord",
    }

    def __init__(self):
        self.VersionNumber: Optional[int] = None
        self.ApplicationsRecord: Dict[int, CDRApplicationRecord] = {}
        self.SubscriptionsRecord: Dict[int, CDRSubscriptionRecord] = {}
        self.LastChangedExistingAppOrSubscriptionTime: Optional[str] = None
        self.IndexAppIdToSubscriptionIdsRecord: Dict[
            int, IndexAppIdToSubscriptionIdsRecord
        ] = {}
        self.AllAppsPublicKeysRecord: Dict[int, PublicKeyRecord] = {}
        self.AllAppsEncryptedPrivateKeysRecord: Dict[int, EncryptedPrivateKeyRecord] = {}

    def to_dict(self, iscustom: bool = False) -> Dict[bytes, Any]:
        result = {}
        for key, attr in self.mapping.items():
            value = getattr(self, attr)
            if value:
                if attr == "ApplicationsRecord":
                    # Serialize ApplicationsRecord using each application's to_dict
                    value_dict = {
                        convert_to_bytes(app_id): app.to_dict()
                        for app_id, app in value.items()
                    }
                    result[key] = value_dict
                elif attr == "SubscriptionsRecord":
                    # Serialize SubscriptionsRecord using each subscription's to_dict
                    value_dict = {
                        convert_to_bytes(sub_id): sub.to_dict()
                        for sub_id, sub in value.items()
                    }
                    result[key] = value_dict
                elif attr == "IndexAppIdToSubscriptionIdsRecord":
                    # Serialize IndexAppIdToSubscriptionIdsRecord using each record's to_dict
                    value_dict = {
                        convert_to_bytes(idx): record.to_dict()
                        for idx, record in value.items()
                    }
                    result[key] = value_dict
                elif attr == "AllAppsPublicKeysRecord":
                    # Serialize AllAppsPublicKeysRecord using each public key's to_dict
                    value_dict = {
                        convert_to_bytes(app_id): key_rec.to_dict()
                        for app_id, key_rec in value.items()
                    }
                    result[key] = value_dict
                elif attr == "AllAppsEncryptedPrivateKeysRecord":
                    # Serialize AllAppsEncryptedPrivateKeysRecord using each encrypted key's to_dict
                    value_dict = {
                        convert_to_bytes(app_id): key_rec.to_dict()
                        for app_id, key_rec in value.items()
                    }
                    result[key] = value_dict
                else:
                    # Handle simple attributes (e.g., VersionNumber, LastChangedExistingAppOrSubscriptionTime)
                    if not iscustom:
                        result[key] = convert_to_bytes(value)
        return result

    @staticmethod
    def from_dict(data: Dict[bytes, Any]) -> "ContentDescriptionRecord":
        return generic_from_dict(ContentDescriptionRecord, data)

    @staticmethod
    def from_xml_file(file_path: str) -> "ContentDescriptionRecord":
        tree = ET.parse(file_path)
        root = tree.getroot()
        cdr = ContentDescriptionRecord()
        cdr.VersionNumber = convert_to_int(get_element_text(root, "VersionNum"))
        cdr.LastChangedExistingAppOrSubscriptionTime = get_element_text(
            root, "LastChangedExistingAppOrSubscriptionTime"
        )

        # Parse Applications
        for app_record in root.findall(".//AllAppsRecord/AppRecord"):
            app = CDRApplicationRecord.from_xml(app_record)
            if app.AppId is not None:
                cdr.ApplicationsRecord[app.AppId] = app

        # Parse Subscriptions
        for sub_record in root.findall(".//AllSubscriptionsRecord/SubscriptionRecord"):
            sub = CDRSubscriptionRecord.from_xml(sub_record)
            if sub.SubscriptionId is not None:
                cdr.SubscriptionsRecord[sub.SubscriptionId] = sub

        # Parse Public Keys
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

        # Parse IndexAppIdToSubscriptionIdsRecord
        for index_elem in root.findall(".//IndexAppIdToSubscriptionIdsRecord"):
            index_record = IndexAppIdToSubscriptionIdsRecord.from_xml(index_elem)
            if index_record.application_id is not None:
                cdr.IndexAppIdToSubscriptionIdsRecord[index_record.application_id] = (
                    index_record
                )

        return cdr

    @staticmethod
    def from_py_file(py_file_path: str) -> "ContentDescriptionRecord":
        """
        Loads a CDR from a Python file that defines a 'blob' dictionary variable.
        """
        # Step 1: Ensure the file exists
        if not os.path.exists(py_file_path):
            raise FileNotFoundError(f"The file {py_file_path} does not exist.")

        # Step 2: Read the file's content as text
        with open(py_file_path, "r") as file:
            file_content = file.read()

        # Step 3: Extract the 'blob' definition line
        blob_start = file_content.find("blob =")
        if blob_start == -1:
            raise AttributeError(
                f"The file {py_file_path} does not define a variable called 'blob'."
            )

        # Step 4: Parse the content of the 'blob' variable
        blob_content = file_content[blob_start + len("blob =") :].strip()

        try:
            # Step 5: Use `ast.literal_eval` to safely evaluate the blob content as a dictionary
            blob = ast.literal_eval(blob_content)
        except (SyntaxError, ValueError) as e:
            raise ValueError(f"Failed to parse the 'blob' content: {e}")

        # Step 6: Create and return the ContentDescriptionRecord from the 'blob' dictionary
        return ContentDescriptionRecord.from_dict(blob)

    def __repr__(self):
        return (
            f"\nContentDescriptionRecord(VersionNumber={self.VersionNumber}, "
            f"\nApplicationsRecord={self.ApplicationsRecord}, "
            f"\nSubscriptionsRecord={self.SubscriptionsRecord}, "
            f"\nLastChangedExistingAppOrSubscriptionTime={self.LastChangedExistingAppOrSubscriptionTime!r}, "
            f"\nIndexAppIdToSubscriptionIdsRecord={self.IndexAppIdToSubscriptionIdsRecord}, "
            f"\nAllAppsPublicKeysRecord={self.AllAppsPublicKeysRecord}, "
            f"\nAllAppsEncryptedPrivateKeysRecord={self.AllAppsEncryptedPrivateKeysRecord})"
        )


# At the top of your script, after all class definitions
NESTED_CLASS_MAPPING = {
    "ApplicationsRecord": CDRApplicationRecord,
    "SubscriptionsRecord": CDRSubscriptionRecord,
    "IndexAppIdToSubscriptionIdsRecord": IndexAppIdToSubscriptionIdsRecord,
    "AllAppsPublicKeysRecord": PublicKeyRecord,
    "AllAppsEncryptedPrivateKeysRecord": EncryptedPrivateKeyRecord,
    "RegionSpecificRecords": CDRAppRegionRecord,
    "AppLaunchOptionsRecord": CDRLaunchOptionsRecord,
    "AppVersionsRecord": CDRApplicationVersionRecord,
    "FilesystemsRecord": CDRFilesystemRecord,
    "OptionalRateLimitRecord": OptionalRateLimitRecord,
    "DiscountsRecord": CDRDiscountRecord,
    "DiscountQualifiers": CDRDiscountQualifierRecord,
    # Add other mappings as necessary
}


def generic_from_dict(cls, data: Dict[bytes, Any], index: Optional[int] = None):
    """
    Generic method to instantiate a class from a dictionary.
    It handles nested classes based on the NESTED_CLASS_MAPPING.
    """
    instance = cls(index) if index is not None else cls()
    for key, attr in cls.mapping.items():
        if key in data:
            value = data[key]
            nested_cls = NESTED_CLASS_MAPPING.get(attr)

            if nested_cls:
                if isinstance(value, dict):
                    # If the nested attribute expects a dictionary of records
                    for sub_key, sub_val in value.items():
                        sub_index = convert_to_int(sub_key)
                        if sub_index is not None:
                            nested_instance = generic_from_dict(
                                nested_cls, sub_val, sub_index
                            )
                            getattr(instance, attr)[sub_index] = nested_instance
                else:
                    # If the nested attribute expects a single record
                    nested_instance = generic_from_dict(nested_cls, value)
                    setattr(instance, attr, nested_instance)
            else:
                # Handle simple attributes
                # Determine the attribute type based on the class definition
                current_attr = getattr(instance, attr, None)
                if isinstance(current_attr, bool):
                    setattr(instance, attr, bool(convert_to_int(value)))
                elif isinstance(current_attr, int):
                    setattr(instance, attr, convert_to_int(value))
                elif isinstance(current_attr, dict):
                    # For attributes like AppIconsRecord which are dicts of raw bytes
                    setattr(
                        instance, attr, {convert_to_int(k): v for k, v in value.items()}
                    )
                else:
                    # Assume string or other types
                    if isinstance(value, bytes):
                        decoded_value = value.strip(b"\x00")
                        setattr(instance, attr, decoded_value)
                    else:
                        setattr(instance, attr, value)
    return instance