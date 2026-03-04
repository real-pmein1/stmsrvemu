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


def print_set_flags(flags):
    all_flags = {
            EAccountFlags.PersonaNameSet:            "PersonaNameSet",
            EAccountFlags.Unbannable:                "Unbannable",
            EAccountFlags.PasswordSet:               "PasswordSet",
            EAccountFlags.Support:                   "Support",
            EAccountFlags.Admin:                     "Admin",
            EAccountFlags.Supervisor:                "Supervisor",
            EAccountFlags.AppEditor:                 "AppEditor",
            EAccountFlags.HWIDSet:                   "HWIDSet",
            EAccountFlags.PersonalQASet:             "PersonalQASet",
            EAccountFlags.VacBeta:                   "VacBeta",
            EAccountFlags.Debug:                     "Debug",
            EAccountFlags.Disabled:                  "Disabled",
            EAccountFlags.LimitedUser:               "LimitedUser",
            EAccountFlags.LimitedUserForce:          "LimitedUserForce",
            EAccountFlags.EmailValidated:            "EmailValidated",
            EAccountFlags.MarketingTreatment:        "MarketingTreatment",
            EAccountFlags.OGGInviteOptOut:           "OGGInviteOptOut",
            EAccountFlags.ForcePasswordChange:       "ForcePasswordChange",
            EAccountFlags.ForceEmailVerification:    "ForceEmailVerification",
            EAccountFlags.LogonExtraSecurity:        "LogonExtraSecurity",
            EAccountFlags.LogonExtraSecurityDisabled:"LogonExtraSecurityDisabled",
            EAccountFlags.Steam2MigrationComplete:   "Steam2MigrationComplete",
            EAccountFlags.NeedLogs:                  "NeedLogs",
            EAccountFlags.Lockdown:                  "Lockdown",
            EAccountFlags.MasterAppEditor:           "MasterAppEditor",
            EAccountFlags.BannedFromWebAPI:          "BannedFromWebAPI",
            EAccountFlags.ClansOnlyFromFriends:      "ClansOnlyFromFriends",
            EAccountFlags.GlobalModerator:           "GlobalModerator",
            EAccountFlags.ParentalSettings:          "ParentalSettings",
            EAccountFlags.ThirdPartySupport:         "ThirdPartySupport",
            EAccountFlags.NeedsSSANextSteamLogon:    "NeedsSSANextSteamLogon"
    }

    print("Flags set:")
    for flag_value, flag_name in all_flags.items():
        if flags & flag_value:
            print(f" - {flag_name}")


# Example usage
#flags = 524292  # Example flags value (LogonExtraSecurity | PersonaNameSet)
flags = int.from_bytes(b'\x85\x00\x00\x00', 'little')
print_set_flags(flags)