"""
GuestPass MessageObject for serialization to the Steam client.

This module provides the GuestPass MessageObject class that serializes
guest pass information in the format expected by the Steam client's
CClientJobUpdateGuestPassesList message (798).
"""
from steam3.Types.MessageObject import MessageObject
from steam3.Types.keyvaluesystem import KVS_TYPE_INT, KVS_TYPE_STRING, KVS_TYPE_UINT64


class GuestPassMessageObject(MessageObject):
    """
    MessageObject for serializing a single guest pass.

    This class creates a properly formatted MessageObject containing
    guest pass data that can be serialized and sent to the client.

    The serialized format matches what the client expects in
    CClientJobUpdateGuestPassesList, with fields:
    - GID: uint64 - Unique guest pass identifier
    - PackageID: int32 - The subscription/package this pass grants
    - TimeCreated: int32 - Unix timestamp of when pass was created
    - TimeExpiration: int32 - Unix timestamp of when pass expires for sending
    - TimeSent: int32 - Unix timestamp of when pass was sent (0 if not sent)
    - TimeAcked: int32 - Unix timestamp of when pass was acknowledged
    - TimeRedeemed: int32 - Unix timestamp of when pass was redeemed
    - RecipientAddress: string - Email or Steam account info of recipient
    - SenderAddress: string - Email of sender
    - SenderName: string - Display name of sender
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
        """
        Initialize a GuestPass MessageObject.

        Args:
            gid: Unique guest pass identifier
            package_id: The subscription/package this pass grants
            time_created: Unix timestamp of when pass was created
            time_expiration: Unix timestamp of when pass expires for sending
            time_sent: Unix timestamp of when pass was sent (0 if not sent)
            time_acked: Unix timestamp of when pass was acknowledged
            time_redeemed: Unix timestamp of when pass was redeemed
            recipient_address: Email or Steam account info of recipient
            sender_address: Email of sender
            sender_name: Display name of sender
        """
        # Initialize the base MessageObject with an empty data dictionary
        super().__init__(data={})

        # Set all the guest pass fields with appropriate types
        self.setValue('GID', gid, KVS_TYPE_UINT64)
        self.setValue('PackageID', package_id, KVS_TYPE_INT)
        self.setValue('TimeCreated', time_created, KVS_TYPE_INT)
        self.setValue('TimeExpiration', time_expiration, KVS_TYPE_INT)
        self.setValue('TimeSent', time_sent, KVS_TYPE_INT)
        self.setValue('TimeAcked', time_acked, KVS_TYPE_INT)
        self.setValue('TimeRedeemed', time_redeemed, KVS_TYPE_INT)
        self.setValue('RecipientAddress', recipient_address, KVS_TYPE_STRING)
        self.setValue('SenderAddress', sender_address, KVS_TYPE_STRING)
        self.setValue('SenderName', sender_name, KVS_TYPE_STRING)

    @classmethod
    def from_guest_pass_info(cls, info: 'GuestPassInfo') -> 'GuestPassMessageObject':
        """
        Create a GuestPassMessageObject from a GuestPassInfo data class.

        Args:
            info: GuestPassInfo instance from steam3.Types.guestpass_types

        Returns:
            GuestPassMessageObject ready for serialization
        """
        return cls(
            gid=info.gid,
            package_id=info.package_id,
            time_created=info.time_created,
            time_expiration=info.time_expiration,
            time_sent=info.time_sent,
            time_acked=info.time_acked,
            time_redeemed=info.time_redeemed,
            recipient_address=info.recipient_address,
            sender_address=info.sender_address,
            sender_name=info.sender_name
        )

    @classmethod
    def from_db_record(cls, record) -> 'GuestPassMessageObject':
        """
        Create a GuestPassMessageObject directly from a database record.

        Args:
            record: GuestPassRegistry database record

        Returns:
            GuestPassMessageObject ready for serialization
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

    def __repr__(self):
        return (f"<GuestPassMessageObject GID={self.get('GID')} "
                f"PackageID={self.get('PackageID')} "
                f"Recipient={self.get('RecipientAddress')}>")


# Keep the deprecated class for backwards compatibility
class GuestPass_Deprecated(MessageObject):
    """
    Deprecated GuestPass class. Use GuestPassMessageObject instead.
    """
    def __init__(self, GID, PackageID, TimeCreated, TimeExpiration, TimeSent, TimeAcked, TimeRedeemed, RecipientAddress, SenderAddress, SenderName):
        # Initialize the base MessageObject with an empty data dictionary
        super().__init__(data={})
        # Set initial values
        self.setValue('GID', GID, KVS_TYPE_UINT64)
        self.setValue('PackageID', PackageID, KVS_TYPE_INT)
        self.setValue('TimeCreated', TimeCreated, KVS_TYPE_INT)
        self.setValue('TimeExpiration', TimeExpiration, KVS_TYPE_INT)
        self.setValue('TimeSent', TimeSent, KVS_TYPE_INT)
        self.setValue('TimeAcked', TimeAcked, KVS_TYPE_INT)
        self.setValue('TimeRedeemed', TimeRedeemed, KVS_TYPE_INT)
        self.setValue('RecipientAddress', RecipientAddress, KVS_TYPE_STRING)
        self.setValue('SenderAddress', SenderAddress, KVS_TYPE_STRING)
        self.setValue('SenderName', SenderName, KVS_TYPE_STRING)

    def __repr__(self):
        return f"<GuestPass {self.data}>"
