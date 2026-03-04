"""
Guest Pass Manager implementation.

This manager handles the complete guest pass lifecycle:
- Creation of guest passes when OnPurchaseGrantGuestPassPackage subscriptions are purchased
- Retrieval of passes for users (to give and to redeem)
- Sending passes to recipients (by email or account ID)
- Acknowledgment of received passes
- Redemption of passes (granting temporary or permanent licenses)
- Expiration checking and cleanup

Guest passes are created when a user purchases a subscription that has extended info
keys like OnPurchaseGrantGuestPassPackage, OnPurchaseGrantGuestPassPackage1, etc.
These keys point to target subscription IDs that determine the pass behavior based
on their billing type:
- Billing Type 4 (GuestPass): Temporary, time-limited license
- Billing Type 6 (Gift): Permanent gift license

Extended info keys on the target subscription define the pass behavior:
- GrantExpirationDays: Days until the pass expires if not sent
- GrantPassesCount: Number of passes to grant (default 1)
- InitialPeriod: Duration of the activated pass (for guest passes)
- InitialTimeUnit: Time unit for InitialPeriod (Day, Week, Month, etc.)
- AppIDOwnedRequired: AppID that must be owned to use this pass

Database operations are delegated to PurchaseDatabase in utilities/database/purchase_db.py
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

import globalvars


log = logging.getLogger('GUESTPASS')


def _get_purchase_db():
    """Get a PurchaseDatabase instance with the current session."""
    from steam3 import database
    from utilities.database.purchase_db import PurchaseDatabase
    return PurchaseDatabase(database.session)


class GuestPassManager:
    """
    Centralized manager for guest pass and gift pass operations.
    """

    def __init__(self):
        self._cache = {}

    def grant_passes_for_subscription(
        self,
        account_id: int,
        purchased_subscription_id: int,
        is_gift_purchase: bool = False,
        gift_recipient_id: Optional[int] = None,
        transaction_id: Optional[int] = None
    ) -> List[int]:
        """
        Grant guest passes/gift passes when a subscription is purchased.

        This method should be called after a successful purchase of a subscription
        that has OnPurchaseGrantGuestPassPackage extended info keys.

        For gift purchases (when buying a subscription as a gift for someone else):
        - If the subscription has billing type 6 (Gift), the passes go to the recipient
        - If it's a guest pass (type 4), passes still go to the purchaser

        Args:
            account_id: The purchaser's account ID
            purchased_subscription_id: The subscription ID that was purchased
            is_gift_purchase: True if this was a gift purchase for another user
            gift_recipient_id: Account ID of gift recipient (if is_gift_purchase)
            transaction_id: Optional transaction ID to link passes to

        Returns:
            List of created guest pass IDs
        """
        from steam3 import database
        from steam3.Types.guestpass_types import EGuestPassType

        created_pass_ids = []
        purchase_db = _get_purchase_db()

        try:
            # Get the subscription record from CDR
            sub_record = globalvars.CDR_DICTIONARY.get_subscription(purchased_subscription_id)
            if not sub_record:
                log.warning(f"Subscription {purchased_subscription_id} not found in CDR")
                return created_pass_ids

            # Check if this subscription grants guest passes
            if not sub_record.has_guestpass_packages():
                log.debug(f"Subscription {purchased_subscription_id} has no guest pass packages")
                return created_pass_ids

            # Get all target subscription IDs from OnPurchaseGrantGuestPassPackage keys
            target_sub_ids = sub_record.get_guest_pass_subscription_ids()
            log.info(f"Subscription {purchased_subscription_id} grants passes for: {target_sub_ids}")

            for target_sub_id in target_sub_ids:
                # Get the target subscription to determine pass type and parameters
                target_sub = globalvars.CDR_DICTIONARY.get_subscription(target_sub_id)
                if not target_sub:
                    log.warning(f"Target subscription {target_sub_id} not found in CDR")
                    continue

                # Get pass configuration from target subscription's extended info
                pass_info = target_sub.get_guest_pass_info()

                # Determine pass type from billing type
                billing_type = target_sub.BillingType
                if isinstance(billing_type, bytes):
                    billing_type = int.from_bytes(billing_type, 'little')

                # Billing type 4 = GuestPass, 6 = Gift
                pass_type = EGuestPassType.Gift if billing_type == 6 else EGuestPassType.GuestPass
                is_permanent_gift = (pass_type == EGuestPassType.Gift)

                # Get number of passes to create
                pass_count = 1
                if 'GrantPassesCount' in pass_info:
                    try:
                        pass_count = int(pass_info['GrantPassesCount'])
                    except (ValueError, TypeError):
                        pass_count = 1

                # Get expiration days (days to send the pass before it expires)
                grant_expiration_days = 30  # Default 30 days to send
                if 'GrantExpirationDays' in pass_info:
                    try:
                        grant_expiration_days = int(pass_info['GrantExpirationDays'])
                    except (ValueError, TypeError):
                        grant_expiration_days = 30

                # Get activation duration for guest passes (not applicable to gifts)
                initial_period = 0
                initial_time_unit = 'Day'
                if not is_permanent_gift:
                    if 'InitialPeriod' in pass_info:
                        try:
                            initial_period = int(pass_info['InitialPeriod'])
                        except (ValueError, TypeError):
                            initial_period = 0
                    if 'InitialTimeUnit' in pass_info:
                        initial_time_unit = pass_info['InitialTimeUnit']

                # Get required app ID (if any)
                app_owned_required = 0
                if 'AppIDOwnedRequired' in pass_info:
                    try:
                        app_owned_required = int(pass_info['AppIDOwnedRequired'])
                    except (ValueError, TypeError):
                        app_owned_required = 0

                # Determine the owner of the passes
                # For gift purchases with billing type 6 (Gift), passes go to recipient
                pass_owner_id = account_id
                if is_gift_purchase and is_permanent_gift and gift_recipient_id:
                    pass_owner_id = gift_recipient_id
                    log.info(f"Gift purchase: passes for sub {target_sub_id} go to recipient {gift_recipient_id}")

                # Get sender info for the passes
                sender_email = ""
                sender_name = ""
                try:
                    user_record = database.get_user_by_accountid(account_id)
                    if user_record:
                        sender_email = user_record.AccountEmailAddress or ""
                        sender_name = user_record.UniqueUserName or ""
                except Exception as e:
                    log.warning(f"Could not get sender info: {e}")

                # Create the passes using PurchaseDatabase
                for i in range(pass_count):
                    pass_id = purchase_db.create_guest_pass(
                        package_id=target_sub_id,
                        source_package_id=purchased_subscription_id,
                        sender_account_id=pass_owner_id,
                        expiration_days=grant_expiration_days,
                        pass_time_limit=initial_period,
                        pass_time_limit_unit=initial_time_unit,
                        app_owned_requirement=app_owned_required,
                        pass_type=pass_type.value,
                        sender_email=sender_email,
                        sender_name=sender_name
                    )

                    if pass_id:
                        created_pass_ids.append(pass_id)
                        log.info(f"Created {'gift' if is_permanent_gift else 'guest'} pass {pass_id} "
                                 f"for package {target_sub_id} owned by account {pass_owner_id}")

                        # Link to transaction if provided
                        if transaction_id:
                            purchase_db.link_pass_to_transaction(transaction_id, pass_id)

        except Exception as e:
            log.error(f"Error granting passes for subscription {purchased_subscription_id}: {e}")

        return created_pass_ids

    def get_passes_to_give(self, account_id: int) -> List:
        """
        Get all guest passes that the user can give to others.

        These are passes owned by the user that have not been sent yet
        and have not expired.

        Args:
            account_id: The owner's account ID

        Returns:
            List of GuestPassRegistry records
        """
        purchase_db = _get_purchase_db()
        return purchase_db.get_passes_to_give(account_id)

    def get_passes_to_redeem(self, account_id: int) -> List:
        """
        Get all guest passes that have been sent to the user and can be redeemed.

        These are passes sent to the user that have not been redeemed yet.

        Args:
            account_id: The recipient's account ID

        Returns:
            List of GuestPassRegistry records
        """
        from steam3 import database

        purchase_db = _get_purchase_db()

        # Get passes sent to this user's account ID
        passes_by_account = purchase_db.get_passes_to_redeem(account_id)

        # Also check for passes sent to the user's email
        try:
            user_record = database.get_user_by_accountid(account_id)
            if user_record and user_record.AccountEmailAddress:
                email = user_record.AccountEmailAddress
                passes_by_email = purchase_db.get_passes_to_redeem_by_email(email)

                # Combine and deduplicate
                all_pass_ids = set(p.UniqueID for p in passes_by_account)
                for p in passes_by_email:
                    if p.UniqueID not in all_pass_ids:
                        passes_by_account.append(p)
        except Exception as e:
            log.warning(f"Error checking email passes: {e}")

        return passes_by_account

    def send_pass(
        self,
        pass_id: int,
        sender_account_id: int,
        recipient_account_id: Optional[int] = None,
        recipient_email: Optional[str] = None,
        is_resend: bool = False
    ) -> Tuple[bool, str]:
        """
        Send a guest pass to a recipient.

        Args:
            pass_id: The guest pass ID to send
            sender_account_id: The sender's account ID (must own the pass)
            recipient_account_id: Recipient's account ID (if sending to friend)
            recipient_email: Recipient's email (if sending to non-friend)
            is_resend: True if this is resending a previously sent pass

        Returns:
            Tuple of (success, error_message or success_message)
        """
        from steam3.Types.guestpass_types import EGuestPassState

        purchase_db = _get_purchase_db()

        try:
            guest_pass = purchase_db.get_guest_pass_by_id(pass_id)

            if not guest_pass:
                return (False, "Guest pass not found")

            if guest_pass.SenderAccountID != sender_account_id:
                return (False, "Guest pass not owned by sender")

            # Check expiration
            now = datetime.utcnow()
            if guest_pass.TimeExpiration and guest_pass.TimeExpiration < now:
                purchase_db.expire_guest_pass(pass_id)
                return (False, "Guest pass has expired")

            # Check if already sent (unless resending)
            if guest_pass.State == EGuestPassState.Sent.value and not is_resend:
                return (False, "Guest pass already sent")

            # Check if already redeemed
            if guest_pass.State in [EGuestPassState.Redeemed.value, EGuestPassState.Revoked.value]:
                return (False, "Guest pass already used")

            # Send the pass
            actual_recipient = recipient_account_id if (recipient_account_id and recipient_account_id != 0xFFFFFFFF) else None
            success = purchase_db.send_guest_pass(pass_id, actual_recipient, recipient_email)

            if not success:
                return (False, "Failed to send guest pass")

            # Queue a SystemIM notification for the recipient
            self._queue_guest_pass_notification(
                recipient_account_id=actual_recipient,
                recipient_email=recipient_email,
                pass_id=pass_id,
                notification_type='received'
            )

            log.info(f"Guest pass {pass_id} sent to "
                     f"{'account ' + str(recipient_account_id) if actual_recipient else 'email ' + str(recipient_email)}")
            return (True, "Guest pass sent successfully")

        except Exception as e:
            log.error(f"Error sending guest pass {pass_id}: {e}")
            return (False, f"Error sending guest pass: {e}")

    def acknowledge_pass(self, pass_id: int, recipient_account_id: int) -> Tuple[bool, str]:
        """
        Acknowledge receipt of a guest pass.

        Args:
            pass_id: The guest pass ID to acknowledge
            recipient_account_id: The recipient's account ID

        Returns:
            Tuple of (success, error_message or success_message)
        """
        purchase_db = _get_purchase_db()

        try:
            guest_pass = purchase_db.get_guest_pass_by_id(pass_id)

            if not guest_pass:
                return (False, "Guest pass not found")

            # Verify the recipient
            is_recipient = (
                guest_pass.RecipientAccountID == recipient_account_id or
                self._is_email_match(guest_pass.RecipientAddress, recipient_account_id)
            )

            if not is_recipient:
                return (False, "Not the recipient of this pass")

            # Acknowledge the pass
            success = purchase_db.acknowledge_guest_pass(pass_id, recipient_account_id)

            if not success:
                return (False, "Failed to acknowledge guest pass")

            log.info(f"Guest pass {pass_id} acknowledged by account {recipient_account_id}")
            return (True, "Guest pass acknowledged")

        except Exception as e:
            log.error(f"Error acknowledging guest pass {pass_id}: {e}")
            return (False, f"Error acknowledging guest pass: {e}")

    def redeem_pass(self, pass_id: int, redeemer_account_id: int) -> Tuple[bool, int, str]:
        """
        Redeem a guest pass.

        For guest passes (billing type 4): Creates a temporary license
        For gift passes (billing type 6): Creates a permanent license

        Args:
            pass_id: The guest pass ID to redeem
            redeemer_account_id: The account redeeming the pass

        Returns:
            Tuple of (success, package_id, error_message or success_message)
        """
        from steam3.Types.guestpass_types import EGuestPassState, EGuestPassType, ETimeUnit

        purchase_db = _get_purchase_db()

        try:
            guest_pass = purchase_db.get_guest_pass_by_id(pass_id)

            if not guest_pass:
                return (False, 0, "Guest pass not found")

            # Verify the redeemer is the recipient
            is_recipient = (
                guest_pass.RecipientAccountID == redeemer_account_id or
                self._is_email_match(guest_pass.RecipientAddress, redeemer_account_id)
            )

            if not is_recipient:
                return (False, 0, "Not the recipient of this pass")

            # Check if already redeemed
            if guest_pass.State == EGuestPassState.Redeemed.value:
                return (False, guest_pass.PackageID, "Guest pass already redeemed")

            # Check for expiration
            if guest_pass.State == EGuestPassState.Expired.value:
                return (False, 0, "Guest pass has expired")

            package_id = guest_pass.PackageID
            is_permanent = (guest_pass.PassType == EGuestPassType.Gift.value)

            # Calculate license expiration for guest passes
            activation_expires = None
            if not is_permanent and guest_pass.PassTimeLimit and guest_pass.PassTimeLimitUnit:
                time_unit = ETimeUnit.from_string(guest_pass.PassTimeLimitUnit)
                duration_seconds = time_unit.to_seconds(guest_pass.PassTimeLimit)
                activation_expires = datetime.utcnow() + timedelta(seconds=duration_seconds)

            # Redeem the pass (this also grants the license via PurchaseDatabase)
            success, result_package_id = purchase_db.redeem_guest_pass(
                pass_id, redeemer_account_id, activation_expires
            )

            if not success:
                if result_package_id:
                    return (False, result_package_id, "Failed to redeem guest pass - may already own")
                return (False, 0, "Failed to redeem guest pass")

            log.info(f"Guest pass {pass_id} redeemed by account {redeemer_account_id} "
                     f"for package {result_package_id} ({'permanent' if is_permanent else 'temporary'})")

            return (True, result_package_id, "Guest pass redeemed successfully")

        except Exception as e:
            log.error(f"Error redeeming guest pass {pass_id}: {e}")
            return (False, 0, f"Error redeeming guest pass: {e}")

    def check_expirations(self) -> int:
        """
        Check for expired guest passes and update their state.

        This should be called periodically (e.g., on server startup or hourly).

        Returns:
            Number of passes that were expired
        """
        purchase_db = _get_purchase_db()

        try:
            # Get passes that need to be expired
            expired_passes = purchase_db.get_expired_passes()

            count = 0
            for guest_pass in expired_passes:
                if purchase_db.expire_guest_pass(guest_pass.UniqueID):
                    count += 1

                    # Queue notification for the owner
                    self._queue_guest_pass_notification(
                        recipient_account_id=guest_pass.SenderAccountID,
                        pass_id=guest_pass.UniqueID,
                        notification_type='expired'
                    )

            if count > 0:
                log.info(f"Expired {count} guest passes")

            return count

        except Exception as e:
            log.error(f"Error checking expirations: {e}")
            return 0

    def revoke_pass(self, pass_id: int, revoker_account_id: int) -> Tuple[bool, str]:
        """
        Revoke a guest pass (e.g., when a gift is declined).

        Args:
            pass_id: The guest pass ID to revoke
            revoker_account_id: The account revoking (must be sender or recipient)

        Returns:
            Tuple of (success, error_message or success_message)
        """
        from steam3.Types.guestpass_types import EGuestPassState

        purchase_db = _get_purchase_db()

        try:
            guest_pass = purchase_db.get_guest_pass_by_id(pass_id)

            if not guest_pass:
                return (False, "Guest pass not found")

            # Only sender or recipient can revoke
            is_sender = guest_pass.SenderAccountID == revoker_account_id
            is_recipient = (
                guest_pass.RecipientAccountID == revoker_account_id or
                self._is_email_match(guest_pass.RecipientAddress, revoker_account_id)
            )

            if not is_sender and not is_recipient:
                return (False, "Not authorized to revoke this pass")

            # Cannot revoke already redeemed passes
            if guest_pass.State == EGuestPassState.Redeemed.value:
                return (False, "Cannot revoke redeemed pass")

            # Store recipient info before revoking
            recipient_id = guest_pass.RecipientAccountID
            sender_id = guest_pass.SenderAccountID

            if not purchase_db.revoke_guest_pass(pass_id):
                return (False, "Failed to revoke guest pass")

            # Notify the other party
            if is_sender and recipient_id:
                # Sender revoked, notify recipient
                self._queue_guest_pass_notification(
                    recipient_account_id=recipient_id,
                    pass_id=pass_id,
                    notification_type='revoked'
                )
            elif is_recipient:
                # Recipient declined, notify sender
                self._queue_guest_pass_notification(
                    recipient_account_id=sender_id,
                    pass_id=pass_id,
                    notification_type='declined'
                )

            log.info(f"Guest pass {pass_id} revoked by account {revoker_account_id}")
            return (True, "Guest pass revoked")

        except Exception as e:
            log.error(f"Error revoking guest pass {pass_id}: {e}")
            return (False, f"Error revoking guest pass: {e}")

    def _is_email_match(self, pass_email: Optional[str], account_id: int) -> bool:
        """Check if a pass's recipient email matches an account's email."""
        if not pass_email:
            return False

        from steam3 import database

        try:
            user_record = database.get_user_by_accountid(account_id)
            if user_record and user_record.AccountEmailAddress:
                return pass_email.lower() == user_record.AccountEmailAddress.lower()
        except Exception:
            pass

        return False

    def _queue_guest_pass_notification(
        self,
        recipient_account_id: Optional[int],
        pass_id: int,
        notification_type: str,
        recipient_email: Optional[str] = None
    ):
        """
        Queue a SystemIM notification for guest pass events.

        If the user is online, sends immediately. If offline, queues for later delivery.

        Args:
            recipient_account_id: Account to notify
            pass_id: The related guest pass ID
            notification_type: Type of notification (received, granted, expired, revoked, declined)
            recipient_email: Email address if notifying by email
        """
        from steam3.Types.steam_types import SystemIMType

        if not recipient_account_id:
            # TODO: Handle email-only notifications
            return

        # Map notification type to SystemIM type
        type_map = {
            'received': SystemIMType.guestPassReceived,
            'granted': SystemIMType.guestPassGranted,
            'revoked': SystemIMType.giftRevoked,
            'expired': SystemIMType.guestPassReceived,  # Use same type, message body differs
            'declined': SystemIMType.giftRevoked
        }

        im_type = type_map.get(notification_type, SystemIMType.guestPassReceived)

        # Create notification message body
        message_body = f"Guest pass notification: {notification_type}"

        purchase_db = _get_purchase_db()

        try:
            # Check if user is online
            from steam3.ClientManager.client_manager import connected_clients
            is_online = recipient_account_id in connected_clients

            if is_online:
                # Send immediately
                client = connected_clients.get(recipient_account_id)
                if client:
                    from steam3.Responses.general_responses import build_system_im_notification
                    try:
                        notification = build_system_im_notification(
                            client,
                            im_type,
                            message_body
                        )
                        # The notification will be sent by the CM server
                        # We just log it here
                        log.debug(f"Queued immediate SystemIM notification for account {recipient_account_id}")
                    except Exception as e:
                        log.warning(f"Could not send immediate notification: {e}")
            else:
                # Queue for later delivery using PurchaseDatabase
                purchase_db.queue_pending_system_im(
                    recipient_account_id=recipient_account_id,
                    message_type=im_type.value,
                    message_body=message_body,
                    ack_required=True,
                    guest_pass_id=pass_id
                )
                log.debug(f"Queued pending SystemIM notification for offline account {recipient_account_id}")

        except Exception as e:
            log.warning(f"Error queueing notification: {e}")


# Global instance
_manager = None


def get_manager() -> GuestPassManager:
    """Get the singleton GuestPassManager instance."""
    global _manager
    if _manager is None:
        _manager = GuestPassManager()
    return _manager
