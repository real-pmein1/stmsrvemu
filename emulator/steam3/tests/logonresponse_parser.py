import struct
from datetime import datetime
from io import BytesIO
import socket

class EAccountFlags:
    NormalUser = 0
    PersonaNameSet = 1
    Unbannable = 2
    PasswordSet = 4
    Support = 8
    Admin = 16
    Supervisor = 32
    AppEditor = 64
    HWIDSet = 128
    PersonalQASet = 256
    VacBeta = 512
    Debug = 1024
    Disabled = 2048
    LimitedUser = 4096
    LimitedUserForce = 8192
    EmailValidated = 16384
    MarketingTreatment = 32768
    OGGInviteOptOut = 65536
    ForcePasswordChange = 131072
    ForceEmailVerification = 262144
    LogonExtraSecurity = 524288
    LogonExtraSecurityDisabled = 1048576
    Steam2MigrationComplete = 2097152
    NeedLogs = 4194304
    Lockdown = 8388608
    MasterAppEditor = 16777216
    BannedFromWebAPI = 33554432
    ClansOnlyFromFriends = 67108864
    GlobalModerator = 134217728
    ParentalSettings = 268435456
    ThirdPartySupport = 536870912
    NeedsSSANextSteamLogon = 1073741824


class MsgClientLogOnResponse:
    def __init__(self):
        self.m_EResult = 0
        self.m_nOutOfGameHeartbeatRateSec = 0
        self.m_nInGameHeartbeatRateSec = 0
        self.m_ulLogonCookie = 0
        self.m_unIPPublic = 0
        self.m_RTime32ServerRealTime = 0
        self.account_flags = []

    def deserialize(self, buffer: bytes):
        """
        Parses the byte buffer to extract MsgClientLogOnResponse fields.
        """
        stream = BytesIO(buffer)
        try:
            # Read m_EResult (4 bytes, int32)
            self.m_EResult = struct.unpack('<I', stream.read(4))[0]

            # Read m_nOutOfGameHeartbeatRateSec (4 bytes, int32)
            self.m_nOutOfGameHeartbeatRateSec = struct.unpack('<I', stream.read(4))[0]

            # Read m_nInGameHeartbeatRateSec (4 bytes, int32)
            self.m_nInGameHeartbeatRateSec = struct.unpack('<I', stream.read(4))[0]

            # Read m_ulLogonCookie (8 bytes, uint64)
            self.m_ulLogonCookie = struct.unpack('<Q', stream.read(8))[0]

            # Read m_unIPPublic (4 bytes, uint32)
            self.m_unIPPublic = struct.unpack('<I', stream.read(4))[0]

            # Convert the integer to IP address
            self.m_unIPPublic = socket.inet_ntoa(struct.pack('!I', self.m_unIPPublic))

            # Read m_RTime32ServerRealTime (4 bytes, uint32)
            self.m_RTime32ServerRealTime = struct.unpack('<I', stream.read(4))[0]
            self.m_RTime32ServerRealTime = datetime.utcfromtimestamp(self.m_RTime32ServerRealTime).strftime('%m/%d/%Y %H:%M:%S')

            # Read 4 bytes for account flags
            account_flags_bytes = struct.unpack('<I', stream.read(4))[0]

            # Determine which flags are set
            self.account_flags = self.get_set_flags(account_flags_bytes)

        except Exception as e:
            pass

        # Print any extra bytes in the buffer
        remaining_bytes = stream.read()
        if remaining_bytes:
            print(f"Extra bytes found: {remaining_bytes.hex()}")

        return self

    def get_set_flags(self, flags_value):
        """
        Given a flags value, returns the list of set flags.
        """
        set_flags = []
        for flag_name, flag_value in EAccountFlags.__dict__.items():
            if isinstance(flag_value, int) and (flags_value & flag_value):
                set_flags.append(flag_name)
        return set_flags


# Example buffer (replace this with actual data)
packet = b'\xef\x02\x00\x00\xa0\xb9\xf4\x00\x01\x00\x10\x01\xea<\x15\x00\x01\x00\x00\x00\t\x00\x00\x00\t\x00\x00\x00\xa0\xb9\xf4\x00\x01\x00\x10\x01\x10\xed\xcaP\x85\xd1\x85G\x85\x00\x00\x00'


packet = packet[16:]

# Deserialize the example buffer
logon_response = MsgClientLogOnResponse()
logon_response.deserialize(packet)

# Output the parsed data
print(f"Result: {logon_response.m_EResult}")
print(f"Out of Game Heartbeat Rate: {logon_response.m_nOutOfGameHeartbeatRateSec} sec")
print(f"In Game Heartbeat Rate: {logon_response.m_nInGameHeartbeatRateSec} sec")
print(f"Logon Cookie: {logon_response.m_ulLogonCookie}")
print(f"Public IP: {logon_response.m_unIPPublic}")
print(f"Server Real Time: {logon_response.m_RTime32ServerRealTime}")
print(f"Account Flags: {', '.join(logon_response.account_flags) if logon_response.account_flags else 'None'}")