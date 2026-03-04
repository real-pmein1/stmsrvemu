import struct
from collections import defaultdict
from io import BytesIO
from enum import Enum, IntEnum


class SteamIntEnum(IntEnum):
    @classmethod
    def get_name(cls, value):
        # Attempt to find a member with the given value and return its name; if not found, return 'Unknown'
        return cls(value).name if value in cls._value2member_map_ else 'Unknown'


# Meta function to get the enum name from its integer value
def get_enum_name(enum_class, value):
    return enum_class.get_name(value)

class AppInfoSections(SteamIntEnum):
    AppInfoSection_unknown = 0
    AppInfoSection_all = 1
    AppInfoSection_common = 2
    AppInfoSection_first = 2
    AppInfoSection_extended = 3
    AppInfoSection_config = 4
    AppInfoSection_stats = 5
    AppInfoSection_install = 6
    AppInfoSection_depots = 7
    AppInfoSection_VAC = 8
    AppInfoSection_DRM = 9
    AppInfoSection_UFS = 10
    AppInfoSection_OGG = 11
    AppInfoSection_items = 12
    AppInfoSection_policies = 13
    AppInfoSection_sysReqs = 14
    AppInfoSection_community = 15
    AppInfoSection_albummetadata = 16
    AppInfoSection_max = 17

class AppInfoRequest:
    def __init__(self):
        self.appId = None
        self.requestAllSections = False
        self.localAppInfoSectionsCRC32 = defaultdict(int)


class MsgClientAppInfoRequest:
    def __init__(self):
        self.appInfoRequests = []
        self.appInfoRequestsCount = 0

    def deserialize(self, data_stream):
        # Read the total number of app info requests (DWORD)
        self.appInfoRequestsCount = struct.unpack('<I', data_stream.read(4))[0]

        # Expected count of app info requests
        expected_count = self.appInfoRequestsCount

        # Continue looping until we've parsed the expected number of requests.
        while len(self.appInfoRequests) < expected_count:
            if len(data_stream.getvalue()) - data_stream.tell() < 8:
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
                        # Read CRC32 value (DWORD) for this section
                        crc32_value = struct.unpack('<I', data_stream.read(4))[0]
                        appInfoRequest.localAppInfoSectionsCRC32[section] = crc32_value

            # Append the newly parsed request.
            self.appInfoRequests.append(appInfoRequest)

packet = b'`\x03\x00\x00$\x02\x00\xff\xff\xff\xff\xff\xff\xff\xffP\x00\x00\x00\x00\x00\x00\x00\xef\x02\x00\x00\x00\x01\x00\x10\x01\x00\x00\x00\x00\x01\x00\x00\x00\xe8\x1c\x00\x00\x00\x00\x00\x00'

# Example
appinfo_packet = BytesIO(packet[36:])

msg = MsgClientAppInfoRequest()
#msg.is_obsolete = True
msg.deserialize(appinfo_packet)

# Access the parsed data
count = 0
for request in msg.appInfoRequests:
    print(f"App ID: {request.appId}, Request All Sections: {request.requestAllSections}")
    for section, crc32 in request.localAppInfoSectionsCRC32.items():
        print(f"  Section {get_enum_name(AppInfoSections, section)}: CRC32 = {crc32}")
    count += 1

print(f"final appinfo actual count: {msg.appInfoRequestsCount} loop count: {count}")
