import struct
from collections import defaultdict
from io import BytesIO
from steam3.Types.steam_types import AppInfoSections


class AppInfoRequest:
    def __init__(self):
        self.appId = None
        self.requestAllSections = False
        self.localAppInfoSectionsCRC32 = defaultdict(int)

    def __repr__(self):
        sections = {section.name: crc for section, crc in self.localAppInfoSectionsCRC32.items()}
        return f"AppInfoRequest(appId={self.appId}, requestAllSections={self.requestAllSections}, localAppInfoSectionsCRC32={sections})"

    def __str__(self):
        return self.__repr__()


class MsgClientAppInfoRequest:
    def __init__(self):
        self.appInfoRequests = []
        self.appInfoRequestsCount = 0
        self.is_obsolete = False  # Set by handler for 2008/2009 clients

    def deserialize(self, data_stream):
        # Safety check for empty/truncated data
        remaining = len(data_stream.getvalue()) - data_stream.tell()
        if remaining < 4:
            self.appInfoRequestsCount = 0
            return

        # Read the total number of app info requests (DWORD)
        self.appInfoRequestsCount = struct.unpack('<I', data_stream.read(4))[0]

        # Expected count of app info requests
        expected_count = self.appInfoRequestsCount

        # Continue looping until we've parsed the expected number of requests.
        while len(self.appInfoRequests) < expected_count:
            if len(data_stream.getvalue()) - data_stream.tell() < 8:
                print(f"[MsgClientAppInfoRequest] Not enough data remaining for request {len(self.appInfoRequests) + 1}/{expected_count}")
                print(data_stream.read())
                break  # Not enough data left, stop parsing

            appInfoRequest = AppInfoRequest()

            # Read the appId (DWORD)
            appInfoRequest.appId = struct.unpack('<I', data_stream.read(4))[0]

            # Read the requestedAppInfoSectionsFlags (DWORD)
            requestedAppInfoSectionsFlags = struct.unpack('<I', data_stream.read(4))[0]

            # Iterate through each possible section in AppInfoSections
            for section in AppInfoSections:
                if (requestedAppInfoSectionsFlags & (1 << section.value)) != 0:
                    if section == AppInfoSections.AppInfoSection_unknown:
                        # Preserve obsolete behavior; do nothing (or optionally log/warn)
                        continue
                    elif section == AppInfoSections.AppInfoSection_all:
                        appInfoRequest.requestAllSections = True
                    else:
                        # For obsolete format (2008/2009), there are no CRCs after section flags
                        # Only read CRCs for modern format (2010+)
                        if not self.is_obsolete:
                            # Check if there's enough data remaining before reading CRC32
                            remaining = len(data_stream.getvalue()) - data_stream.tell()
                            if remaining < 4:
                                # Not enough data for CRC32, skip (truncated packet)
                                break
                            # Read CRC32 value (DWORD) for this section
                            crc32_value = struct.unpack('<I', data_stream.read(4))[0]
                            appInfoRequest.localAppInfoSectionsCRC32[section] = crc32_value

            # Append the newly parsed request.
            self.appInfoRequests.append(appInfoRequest)

    def __repr__(self):
        return f"MsgClientAppInfoRequest(appInfoRequestsCount={self.appInfoRequestsCount}, appInfoRequests={self.appInfoRequests})"

    def __str__(self):
        return self.__repr__()
