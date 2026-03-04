"""
Guest Pass and Gift Pass type definitions.

This module contains enums and types for the guest pass and gift pass system.
Guest passes are temporary licenses that can be sent to friends to try games.
Gift passes are permanent licenses that can be gifted to other users.
"""
from enum import IntEnum
from steam3.Types import SteamIntEnum


class EBillingType(SteamIntEnum):
    """
    Subscription billing types from the CDR.
    Determines how a subscription is billed and whether it's a guest pass or gift.
    """
    NoCost = 0                    # Free subscription
    BillOnceOnly = 1              # One-time payment
    BillMonthly = 2               # Monthly recurring
    ProofOfPrepurchaseOnly = 3    # CD key / retail purchase
    GuestPass = 4                 # Temporary guest pass (time-limited)
    HardwarePromo = 5             # Hardware bundle promotion
    Gift = 6                      # Permanent gift to another user
    AutoGrant = 7                 # Automatically granted subscription
    OEMTicket = 8                 # OEM license ticket
    RecurringOption = 9           # Recurring payment option
    BillOnceOrCDKey = 10          # One-time or CD key
    Repurchaseable = 11           # Can be purchased again
    FreeOnDemand = 12             # Free-to-play on demand
    Rental = 13                   # Rental subscription
    CommercialLicense = 14        # Commercial/business license
    FreeCommercialLicense = 15    # Free commercial license
    NumBillingTypes = 16


class EGuestPassState(IntEnum):
    """
    State of a guest pass in the database.
    """
    Available = 0       # Pass is available to be sent
    Sent = 1            # Pass has been sent to a recipient
    Acknowledged = 2    # Recipient has acknowledged receiving the pass
    Redeemed = 3        # Pass has been redeemed/activated
    Expired = 4         # Pass has expired (either send window or activation)
    Revoked = 5         # Pass has been revoked


class EGuestPassType(IntEnum):
    """
    Type of guest pass based on billing type of target subscription.
    """
    GuestPass = 0       # Temporary, time-limited license (billing type 4)
    Gift = 1            # Permanent gift (billing type 6)


class ETimeUnit(IntEnum):
    """
    Time unit for guest pass duration.
    Maps to InitialTimeUnit extended info key values.
    """
    Second = 0
    Minute = 1
    Hour = 2
    Day = 3
    Week = 4
    Month = 5
    Year = 6

    @classmethod
    def from_string(cls, value: str) -> 'ETimeUnit':
        """Convert string time unit to enum value."""
        mapping = {
            'second': cls.Second,
            'seconds': cls.Second,
            'minute': cls.Minute,
            'minutes': cls.Minute,
            'hour': cls.Hour,
            'hours': cls.Hour,
            'day': cls.Day,
            'days': cls.Day,
            'week': cls.Week,
            'weeks': cls.Week,
            'month': cls.Month,
            'months': cls.Month,
            'year': cls.Year,
            'years': cls.Year,
        }
        return mapping.get(value.lower().strip(), cls.Day)

    def to_seconds(self, value: int) -> int:
        """Convert a time value in this unit to seconds."""
        multipliers = {
            self.Second: 1,
            self.Minute: 60,
            self.Hour: 3600,
            self.Day: 86400,
            self.Week: 604800,
            self.Month: 2592000,  # 30 days
            self.Year: 31536000,  # 365 days
        }
        return value * multipliers.get(self, 86400)


class GuestPassInfo:
    """
    Data class representing a guest pass for serialization.

    This class holds all the information about a guest pass that gets
    serialized and sent to the client in the UpdateGuestPassesList message.

    Attributes match the CGuestPassInfo KeyValues structure from the client:
    - GID: Unique guest pass identifier
    - PackageID: The subscription/package this pass grants
    - TimeCreated: When the pass was created (Unix timestamp)
    - TimeExpiration: When the pass expires for sending (Unix timestamp)
    - TimeSent: When the pass was sent (0 if not sent)
    - TimeAcked: When the pass was acknowledged (0 if not acked)
    - TimeRedeemed: When the pass was redeemed (0 if not redeemed)
    - RecipientAddress: Email or Steam account info of recipient
    - SenderAddress: Email of sender
    - SenderName: Display name of sender
    """

    def __init__(
        self,
        gid: int = 0,
        package_id: int = 0,
        time_created: int = 0,
        time_expiration: int = 0,
        time_sent: int = 0,
        time_acked: int = 0,
        time_redeemed: int = 0,
        recipient_address: str = "",
        sender_address: str = "",
        sender_name: str = ""
    ):
        self.gid = gid
        self.package_id = package_id
        self.time_created = time_created
        self.time_expiration = time_expiration
        self.time_sent = time_sent
        self.time_acked = time_acked
        self.time_redeemed = time_redeemed
        self.recipient_address = recipient_address
        self.sender_address = sender_address
        self.sender_name = sender_name

    @classmethod
    def from_db_record(cls, record) -> 'GuestPassInfo':
        """
        Create a GuestPassInfo from a database GuestPassRegistry record.

        Args:
            record: GuestPassRegistry database record

        Returns:
            GuestPassInfo instance
        """
        from steam3.utilities import datetime_to_unix

        return cls(
            gid=record.UniqueID,
            package_id=record.PackageID or 0,
            time_created=datetime_to_unix(record.TimeCreated) if record.TimeCreated else 0,
            time_expiration=datetime_to_unix(record.TimeExpiration) if record.TimeExpiration else 0,
            time_sent=record.TimeSent or 0,
            time_acked=record.TimeAcked or 0,
            time_redeemed=record.TimeRedeemed or 0,
            recipient_address=record.RecipientAddress or "",
            sender_address=record.SenderAddress or "",
            sender_name=record.SenderName or ""
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'GID': self.gid,
            'PackageID': self.package_id,
            'TimeCreated': self.time_created,
            'TimeExpiration': self.time_expiration,
            'TimeSent': self.time_sent,
            'TimeAcked': self.time_acked,
            'TimeRedeemed': self.time_redeemed,
            'RecipientAddress': self.recipient_address,
            'SenderAddress': self.sender_address,
            'SenderName': self.sender_name,
        }

    def __repr__(self):
        return (f"GuestPassInfo(gid={self.gid}, package_id={self.package_id}, "
                f"time_created={self.time_created}, time_expiration={self.time_expiration}, "
                f"sent={self.time_sent}, acked={self.time_acked}, redeemed={self.time_redeemed})")
