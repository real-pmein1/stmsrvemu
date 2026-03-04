"""
Purchase Database Module

This module handles all purchase/transaction related database operations for Steam3.
Designed to be clean, simple, and follow a clear separation of concerns.

Tables used:
- Steam3TransactionsRecord: Tracks ongoing and completed transactions
- Steam3TransactionAddressRecord: Billing and shipping addresses
- Steam3CCRecord: Credit card payment info
- ExternalPurchaseInfoRecord: PayPal and other external payments
- Steam3LicenseRecord: Granted licenses after purchase completion
- GuestPassRegistry: Guest passes granted from purchases
- TransactionGuestPasses: Links transactions to guest passes
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional, Tuple, List, Dict, Any

from sqlalchemy.orm import Session

from steam3.Types.globalid import generate_globalid
from utilities.database.base_dbdriver import (
    Steam3TransactionsRecord,
    Steam3TransactionAddressRecord,
    Steam3CCRecord,
    ExternalPurchaseInfoRecord,
    Steam3LicenseRecord,
    GuestPassRegistry,
    TransactionGuestPasses
)
from steam3.Types.steam_types import EPaymentMethod, EPurchaseResultDetail, EResult

log = logging.getLogger("PURCHASEDB")


class PurchaseDatabase:
    """
    Handles all purchase and transaction database operations.

    This class provides a clean interface for:
    - Creating and managing transactions
    - Storing payment information
    - Managing addresses
    - Completing purchases and granting licenses
    - Handling purchase receipts
    """

    def __init__(self, session: Session):
        self.session = session

    # =========================================================================
    # Address Management
    # =========================================================================

    def get_or_create_address(
        self,
        account_id: int,
        name: str,
        address1: str,
        address2: str,
        city: str,
        postcode: str,
        state: str,
        country_code: str,
        phone: str
    ) -> Optional[int]:
        """
        Get existing address entry or create a new one.
        Returns the address entry ID.
        """
        try:
            # Look for existing matching address
            entry = self.session.query(Steam3TransactionAddressRecord).filter(
                Steam3TransactionAddressRecord.AccountID == account_id,
                Steam3TransactionAddressRecord.Name == name,
                Steam3TransactionAddressRecord.Address1 == address1,
                Steam3TransactionAddressRecord.Address2 == address2,
                Steam3TransactionAddressRecord.City == city,
                Steam3TransactionAddressRecord.PostCode == postcode,
                Steam3TransactionAddressRecord.State == state,
                Steam3TransactionAddressRecord.CountryCode == country_code,
                Steam3TransactionAddressRecord.Phone == phone
            ).first()

            if entry:
                return entry.UniqueID

            # Create new address entry
            new_entry = Steam3TransactionAddressRecord(
                AccountID=account_id,
                Name=name,
                Address1=address1,
                Address2=address2 or "",
                City=city,
                PostCode=postcode,
                State=state,
                CountryCode=country_code,
                Phone=phone
            )
            self.session.add(new_entry)
            self.session.commit()
            return new_entry.UniqueID

        except Exception as e:
            log.error(f"Error in get_or_create_address: {e}")
            self.session.rollback()
            return None

    def get_address(self, address_id: int) -> Optional[Steam3TransactionAddressRecord]:
        """Get address record by ID."""
        try:
            return self.session.query(Steam3TransactionAddressRecord).filter_by(
                UniqueID=address_id
            ).first()
        except Exception as e:
            log.error(f"Error getting address {address_id}: {e}")
            return None

    # =========================================================================
    # Payment Information Management
    # =========================================================================

    def get_or_create_cc_entry(
        self,
        account_id: int,
        card_type: int,
        card_number: str,
        holder_name: str,
        exp_year: int,
        exp_month: int,
        cvv2: int
    ) -> Optional[int]:
        """
        Get existing credit card entry or create a new one.
        Returns the CC entry ID.
        """
        try:
            # Check for existing card (by last 4 digits and holder name)
            last_four = card_number[-4:] if card_number else ""

            existing = self.session.query(Steam3CCRecord).filter(
                Steam3CCRecord.AccountID == account_id,
                Steam3CCRecord.CardNumber.endswith(last_four),
                Steam3CCRecord.CardHolderName == holder_name
            ).first()

            if existing:
                return existing.UniqueID

            # Create new entry
            new_entry = Steam3CCRecord(
                AccountID=account_id,
                CardType=card_type,
                CardNumber=card_number,
                CardHolderName=holder_name,
                CardExpYear=exp_year,
                CardExpMonth=exp_month,
                CardCVV2=cvv2,
                DateAdded=datetime.now().strftime("%m/%d/%Y %H:%M:%S")
            )
            self.session.add(new_entry)
            self.session.commit()
            return new_entry.UniqueID

        except Exception as e:
            log.error(f"Error in get_or_create_cc_entry: {e}")
            self.session.rollback()
            return None

    def create_external_payment_entry(
        self,
        account_id: int,
        package_id: int,
        payment_method: EPaymentMethod,
        transaction_data: str
    ) -> Optional[int]:
        """
        Create an external payment entry (PayPal, ClickAndBuy, etc).
        Returns the entry ID.
        """
        try:
            new_entry = ExternalPurchaseInfoRecord(
                AccountID=account_id,
                PackageID=package_id,
                TransactionType=int(payment_method),
                TransactionData=transaction_data,
                DateAdded=datetime.now().strftime("%m/%d/%Y %H:%M:%S")
            )
            self.session.add(new_entry)
            self.session.commit()
            return new_entry.UniqueID

        except Exception as e:
            log.error(f"Error creating external payment entry: {e}")
            self.session.rollback()
            return None

    # =========================================================================
    # Transaction Management
    # =========================================================================

    def create_transaction(
        self,
        account_id: int,
        package_id: int,
        payment_type: EPaymentMethod,
        payment_entry_id: int,
        address_entry_id: Optional[int],
        base_cost_cents: int,
        discount_cents: int,
        tax_cents: int,
        shipping_cents: int = 0,
        shipping_entry_id: Optional[int] = None,
        pass_information: Optional[Dict] = None,
        gift_info: Optional[Dict] = None
    ) -> Optional[int]:
        """
        Create a new transaction record.
        Returns the transaction ID (UniqueID) - a 64-bit GlobalID.
        """
        try:
            log.debug(f"create_transaction called: account_id={account_id}, package_id={package_id}")
            current_time = datetime.now()
            current_time_str = current_time.strftime("%m/%d/%Y %H:%M:%S")

            # Generate a proper 64-bit GlobalID for the transaction
            transaction_id = generate_globalid(current_time)

            new_entry = Steam3TransactionsRecord(
                UniqueID=transaction_id,
                AccountID=account_id,
                PaymentType=int(payment_type),
                PaymentEntryID=payment_entry_id,
                PackageID=package_id,
                AddressEntryID=address_entry_id,
                ShippingEntryID=shipping_entry_id,
                TransactionDate=current_time_str,
                BaseCostInCents=base_cost_cents,
                DiscountsInCents=discount_cents,
                TaxCostInCents=tax_cents,
                ShippingCostInCents=shipping_cents,
                PassInformation=json.dumps(pass_information) if pass_information else "{}",
            )

            # Add gift information if provided
            if gift_info:
                new_entry.GifterAccountID = gift_info.get('GifterAccountID')
                new_entry.GifteeEmail = gift_info.get('GifteeEmail')
                new_entry.GifteeAccountID = gift_info.get('GifteeAccountID')
                new_entry.GiftMessage = gift_info.get('GiftMessage')
                new_entry.GifteeName = gift_info.get('GifteeName')
                new_entry.Sentiment = gift_info.get('Sentiment')
                new_entry.Signature = gift_info.get('Signature')

            self.session.add(new_entry)
            self.session.commit()

            log.debug(f"Created transaction {new_entry.UniqueID} for account {account_id}, package {package_id}")
            return new_entry.UniqueID

        except Exception as e:
            log.error(f"Error creating transaction: {e}")
            self.session.rollback()
            return None

    def get_transaction(self, account_id: int, transaction_id: int) -> Optional[Steam3TransactionsRecord]:
        """Get a transaction record by ID and account."""
        try:
            return self.session.query(Steam3TransactionsRecord).filter(
                Steam3TransactionsRecord.UniqueID == transaction_id,
                Steam3TransactionsRecord.AccountID == account_id
            ).first()
        except Exception as e:
            log.error(f"Error getting transaction {transaction_id}: {e}")
            return None

    def get_transaction_details(
        self,
        account_id: int,
        transaction_id: int
    ) -> Optional[Tuple[Steam3TransactionsRecord, Any, Any, Any, Any]]:
        """
        Get complete transaction details including related records.
        Returns tuple: (transaction, cc_entry, external_entry, address, shipping_address)
        """
        try:
            transaction = self.get_transaction(account_id, transaction_id)
            if not transaction:
                return None

            cc_entry = None
            external_entry = None
            address = None
            shipping = None

            # Get credit card entry if applicable
            if transaction.PaymentType == int(EPaymentMethod.CreditCard) and transaction.PaymentEntryID:
                cc_entry = self.session.query(Steam3CCRecord).filter_by(
                    UniqueID=transaction.PaymentEntryID
                ).first()

            # Get external payment entry if applicable
            if transaction.PaymentType in (int(EPaymentMethod.PayPal), int(EPaymentMethod.ClickAndBuy)):
                external_entry = self.session.query(ExternalPurchaseInfoRecord).filter_by(
                    UniqueID=transaction.PaymentEntryID
                ).first()

            # Get address entries
            if transaction.AddressEntryID:
                address = self.get_address(transaction.AddressEntryID)

            if transaction.ShippingEntryID:
                shipping = self.get_address(transaction.ShippingEntryID)

            return (transaction, cc_entry, external_entry, address, shipping)

        except Exception as e:
            log.error(f"Error getting transaction details {transaction_id}: {e}")
            return None

    def validate_transaction(self, account_id: int, transaction_id: int) -> int:
        """
        Validate a transaction.

        Returns:
            0 = Valid and ready for processing
            1 = Transaction not found
            2 = Transaction already completed
            3 = Transaction cancelled
            4 = Transaction expired (older than 24 hours)
        """
        try:
            log.debug(f"validate_transaction called: account_id={account_id}, transaction_id={transaction_id}")
            transaction = self.get_transaction(account_id, transaction_id)

            if not transaction:
                log.warning(f"validate_transaction: Transaction {transaction_id} not found for account {account_id}")
                return 1

            if transaction.DateCompleted:
                return 2

            if transaction.DateCancelled:
                return 3

            # Check if transaction is too old (24 hour expiry)
            try:
                trans_date = transaction.TransactionDate
                if isinstance(trans_date, datetime):
                    created = trans_date
                elif isinstance(trans_date, str):
                    # Try common date formats
                    for fmt in ("%m/%d/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                        try:
                            created = datetime.strptime(trans_date, fmt)
                            break
                        except ValueError:
                            continue
                    else:
                        created = None
                else:
                    created = None

                if created and (datetime.now() - created).total_seconds() > 86400:  # 24 hours
                    return 4
            except:
                pass

            return 0

        except Exception as e:
            log.error(f"Error validating transaction {transaction_id}: {e}")
            return 1

    def cancel_transaction(self, account_id: int, transaction_id: int) -> bool:
        """Cancel a transaction."""
        try:
            transaction = self.get_transaction(account_id, transaction_id)
            if not transaction:
                return False

            if transaction.DateCompleted or transaction.DateCancelled:
                return False

            transaction.DateCancelled = datetime.now().strftime("%m/%d/%Y %H:%M:%S")
            self.session.commit()

            log.debug(f"Cancelled transaction {transaction_id}")
            return True

        except Exception as e:
            log.error(f"Error cancelling transaction {transaction_id}: {e}")
            self.session.rollback()
            return False

    def complete_transaction(self, account_id: int, transaction_id: int) -> Optional[Dict]:
        """
        Complete a transaction and grant the license.

        This method:
        1. Marks the transaction as completed
        2. Creates a license record (if not a gift)
        3. Processes any guest passes
        4. Returns transaction details for the purchase response
        """
        try:
            log.debug(f"complete_transaction called: account_id={account_id}, transaction_id={transaction_id}")
            transaction = self.get_transaction(account_id, transaction_id)
            if not transaction:
                log.error(f"Transaction {transaction_id} not found for account {account_id}")
                # Try to find any transaction with this ID to debug
                any_trans = self.session.query(Steam3TransactionsRecord).filter(
                    Steam3TransactionsRecord.UniqueID == transaction_id
                ).first()
                if any_trans:
                    log.error(f"Transaction {transaction_id} exists but belongs to account {any_trans.AccountID}, not {account_id}")
                else:
                    log.error(f"No transaction with UniqueID={transaction_id} exists in database")
                return None

            # Mark as completed
            current_time = datetime.now().strftime("%m/%d/%Y %H:%M:%S")
            transaction.DateCompleted = current_time

            # Get purchase country code from address
            purchase_country = None
            if transaction.AddressEntryID:
                address = self.get_address(transaction.AddressEntryID)
                if address:
                    purchase_country = address.CountryCode

            # If not a gift, create the license
            if not transaction.GifteeAccountID or int(transaction.GifteeAccountID or 0) == 0:
                license_entry = Steam3LicenseRecord(
                    AccountID=account_id,
                    PackageID=transaction.PackageID,
                    DateAdded=current_time,
                    LicenseType=1,  # Purchase
                    LicenseFlags=0,
                    PaymentType=transaction.PaymentType,
                    PurchaseCountryCode=purchase_country,
                    TimeLimit=0,
                    MinutesUsed=0,
                    TimeNextProcess=0,
                    ChangeNumber=0,
                    OwnerAccountID=account_id,
                    MasterPackageID=transaction.PackageID
                )
                self.session.add(license_entry)
                self.session.flush()  # Flush to get the auto-generated UniqueID
                transaction.LicenseEntryID = license_entry.UniqueID

            # Process guest passes if any
            if transaction.PassInformation and transaction.PassInformation != "{}":
                try:
                    pass_info = json.loads(transaction.PassInformation)
                    self._process_guest_passes(transaction, pass_info)
                except json.JSONDecodeError:
                    log.warning(f"Invalid PassInformation JSON in transaction {transaction_id}")

            self.session.commit()

            log.info(f"Completed transaction {transaction_id} for account {account_id}")

            # Return transaction details for purchase response
            return self.get_transaction_details(account_id, transaction_id)

        except Exception as e:
            log.error(f"Error completing transaction {transaction_id}: {e}")
            self.session.rollback()
            return None

    def _process_guest_passes(self, transaction: Steam3TransactionsRecord, pass_info: Dict):
        """Process guest passes from a completed transaction."""
        for pass_type in ['guestpasses', 'giftpasses']:
            if pass_type not in pass_info:
                continue

            for sub_id_str, details in pass_info[pass_type].items():
                sub_id = int(sub_id_str)
                quantity = details.get('quantity', 1)
                time_limit = details.get('time_limit', 0)
                time_unit = details.get('time_unit', 'days')
                app_requirement = details.get('app_requirement', 0)

                for _ in range(quantity):
                    guest_pass = GuestPassRegistry(
                        PackageID=sub_id,
                        TimeCreated=datetime.now().strftime("%m/%d/%Y %H:%M:%S"),
                        PassTimeLimit=time_limit,
                        PassTimeLimitUnit=time_unit,
                        AppIDOwnedRequirement=app_requirement,
                        SenderAccountID=transaction.AccountID
                    )
                    self.session.add(guest_pass)
                    self.session.flush()

                    # Link to transaction
                    link = TransactionGuestPasses(
                        transaction_id=transaction.UniqueID,
                        guest_pass_id=guest_pass.UniqueID
                    )
                    self.session.add(link)

    # =========================================================================
    # Purchase Receipt Management
    # =========================================================================

    def get_purchase_receipts(
        self,
        account_id: int,
        unacknowledged_only: bool = False
    ) -> List[Steam3TransactionsRecord]:
        """
        Get purchase receipts for an account.

        Args:
            account_id: The account ID
            unacknowledged_only: If True, only return unacknowledged receipts

        Returns:
            List of completed transaction records (sorted by TransactionDate ascending)
        """
        try:
            query = self.session.query(Steam3TransactionsRecord).filter(
                Steam3TransactionsRecord.AccountID == account_id,
                Steam3TransactionsRecord.DateCompleted.isnot(None)
            )

            if unacknowledged_only:
                query = query.filter(Steam3TransactionsRecord.DateAcknowledged.is_(None))

            # Sort by transaction time ascending (as per client's ComparePurchaseReceiptsByTimeAscending)
            return query.order_by(Steam3TransactionsRecord.TransactionDate.asc()).all()

        except Exception as e:
            log.error(f"Error getting purchase receipts for account {account_id}: {e}")
            return []

    def acknowledge_receipt(self, account_id: int, transaction_id: int) -> bool:
        """Mark a purchase receipt as acknowledged."""
        try:
            log.debug(f"Acknowledging transaction {transaction_id} (0x{transaction_id:016X}) for account {account_id}")
            transaction = self.get_transaction(account_id, transaction_id)
            if not transaction:
                log.warning(f"Transaction {transaction_id} (0x{transaction_id:016X}) not found for account {account_id}")
                # Log existing transactions for this account to help debug
                existing = self.session.query(Steam3TransactionsRecord).filter(
                    Steam3TransactionsRecord.AccountID == account_id
                ).limit(5).all()
                if existing:
                    log.debug(f"Existing transactions for account {account_id}: {[t.UniqueID for t in existing]}")
                return False

            transaction.DateAcknowledged = datetime.now().strftime("%m/%d/%Y %H:%M:%S")
            self.session.commit()

            log.debug(f"Acknowledged receipt for transaction {transaction_id}")
            return True

        except Exception as e:
            log.error(f"Error acknowledging receipt {transaction_id}: {e}")
            self.session.rollback()
            return False

    # =========================================================================
    # License Management
    # =========================================================================

    def grant_license(
        self,
        account_id: int,
        package_id: int,
        license_type: int = 1,
        payment_type: int = 0,
        country_code: str = None
    ) -> bool:
        """
        Grant a license to an account (for key activations, gifts, etc).
        """
        try:
            # Check if license already exists
            existing = self.session.query(Steam3LicenseRecord).filter(
                Steam3LicenseRecord.AccountID == account_id,
                Steam3LicenseRecord.PackageID == package_id
            ).first()

            if existing:
                log.debug(f"License for package {package_id} already exists for account {account_id}")
                return True

            current_time = datetime.now().strftime("%m/%d/%Y %H:%M:%S")

            license_entry = Steam3LicenseRecord(
                AccountID=account_id,
                PackageID=package_id,
                DateAdded=current_time,
                LicenseType=license_type,
                LicenseFlags=0,
                PaymentType=payment_type,
                PurchaseCountryCode=country_code,
                TimeLimit=0,
                MinutesUsed=0,
                TimeNextProcess=0,
                ChangeNumber=0,
                OwnerAccountID=account_id,
                MasterPackageID=package_id
            )
            self.session.add(license_entry)
            self.session.commit()

            log.info(f"Granted license for package {package_id} to account {account_id}")
            return True

        except Exception as e:
            log.error(f"Error granting license: {e}")
            self.session.rollback()
            return False

    def get_licenses(self, account_id: int) -> List[Steam3LicenseRecord]:
        """Get all licenses for an account."""
        try:
            return self.session.query(Steam3LicenseRecord).filter(
                Steam3LicenseRecord.AccountID == account_id
            ).all()
        except Exception as e:
            log.error(f"Error getting licenses for account {account_id}: {e}")
            return []

    def owns_package(self, account_id: int, package_id: int) -> bool:
        """Check if an account owns a package."""
        try:
            return self.session.query(Steam3LicenseRecord).filter(
                Steam3LicenseRecord.AccountID == account_id,
                Steam3LicenseRecord.PackageID == package_id
            ).first() is not None
        except Exception as e:
            log.error(f"Error checking package ownership: {e}")
            return False

    # =========================================================================
    # User Payment Methods
    # =========================================================================

    def get_user_payment_methods(
        self,
        account_id: int,
        payment_type: Optional[EPaymentMethod] = None
    ) -> List:
        """Get stored payment methods for a user."""
        try:
            if payment_type == EPaymentMethod.CreditCard or payment_type is None:
                cc_entries = self.session.query(Steam3CCRecord).filter(
                    Steam3CCRecord.AccountID == account_id
                ).all()

                if payment_type == EPaymentMethod.CreditCard:
                    return cc_entries
            else:
                cc_entries = []

            if payment_type in (EPaymentMethod.PayPal, EPaymentMethod.ClickAndBuy) or payment_type is None:
                query = self.session.query(ExternalPurchaseInfoRecord).filter(
                    ExternalPurchaseInfoRecord.AccountID == account_id
                )
                if payment_type:
                    query = query.filter(ExternalPurchaseInfoRecord.TransactionType == int(payment_type))
                external_entries = query.all()
            else:
                external_entries = []

            return cc_entries + external_entries

        except Exception as e:
            log.error(f"Error getting payment methods for account {account_id}: {e}")
            return []

    # =========================================================================
    # Guest Pass / Gift Pass Management
    # =========================================================================

    def create_guest_pass(
        self,
        package_id: int,
        source_package_id: int,
        sender_account_id: int,
        expiration_days: int = 30,
        pass_time_limit: int = 0,
        pass_time_limit_unit: str = "Day",
        app_owned_requirement: int = 0,
        pass_type: int = 0,  # 0 = GuestPass, 1 = Gift
        sender_email: str = "",
        sender_name: str = "",
        gift_message: str = None,
        signature: str = None,
        sentiment: str = None
    ) -> int:
        """
        Create a new guest pass or gift pass in the database.

        Args:
            package_id: The subscription/package this pass grants
            source_package_id: The subscription that created this pass
            sender_account_id: Account ID of the pass owner
            expiration_days: Days until the pass expires if not sent
            pass_time_limit: Duration of pass once activated (for guest passes)
            pass_time_limit_unit: Time unit for pass_time_limit
            app_owned_requirement: AppID that must be owned to use this pass
            pass_type: 0 = GuestPass (temporary), 1 = Gift (permanent)
            sender_email: Email address of the sender
            sender_name: Display name of the sender
            gift_message: Personal message with gift (for gifts)
            signature: Gift card signature
            sentiment: Gift card sentiment

        Returns:
            The UniqueID of the created pass, or 0 on failure
        """
        from datetime import timedelta

        try:
            now = datetime.now()
            expiration = now + timedelta(days=expiration_days)

            new_pass = GuestPassRegistry(
                PackageID=package_id,
                SourcePackageID=source_package_id,
                TimeCreated=now,
                TimeExpiration=expiration,
                TimeSent=0,
                TimeAcked=0,
                TimeRedeemed=0,
                TimeActivationExpires=None,
                Sent=0,
                Acked=0,
                Redeemed=0,
                RecipientAddress=None,
                RecipientAccountID=None,
                SenderAddress=sender_email,
                SenderName=sender_name,
                PassTimeLimit=pass_time_limit,
                PassTimeLimitUnit=pass_time_limit_unit,
                AppIDOwnedRequirement=app_owned_requirement,
                SenderAccountID=sender_account_id,
                PassType=pass_type,
                State=0,  # Available
                GiftMessage=gift_message,
                Signature=signature,
                Sentiment=sentiment
            )

            self.session.add(new_pass)
            self.session.commit()
            log.info(f"Created guest pass {new_pass.UniqueID} for package {package_id}")
            return new_pass.UniqueID

        except Exception as e:
            self.session.rollback()
            log.error(f"Error creating guest pass: {e}")
            return 0

    def get_guest_pass_by_id(self, pass_id: int) -> Optional[GuestPassRegistry]:
        """
        Get a guest pass by its unique ID.

        Args:
            pass_id: The guest pass unique ID

        Returns:
            GuestPassRegistry record or None
        """
        try:
            return self.session.query(GuestPassRegistry).filter_by(
                UniqueID=pass_id
            ).first()
        except Exception as e:
            log.error(f"Error getting guest pass {pass_id}: {e}")
            return None

    def get_passes_to_give(self, account_id: int) -> List[GuestPassRegistry]:
        """
        Get all guest passes that the user can give to others.

        These are passes owned by the user that are in Available state
        and have not expired.

        Args:
            account_id: The owner's account ID

        Returns:
            List of GuestPassRegistry records
        """
        try:
            now = datetime.now()
            entries = self.session.query(GuestPassRegistry).filter(
                GuestPassRegistry.SenderAccountID == account_id,
                GuestPassRegistry.State == 0,  # Available
                GuestPassRegistry.TimeExpiration > now
            ).all()
            return entries
        except Exception as e:
            log.error(f"Error getting passes to give for account {account_id}: {e}")
            return []

    def get_passes_to_redeem(self, account_id: int) -> List[GuestPassRegistry]:
        """
        Get all guest passes that have been sent to the user and can be redeemed.

        Args:
            account_id: The recipient's account ID

        Returns:
            List of GuestPassRegistry records
        """
        try:
            # Get passes sent to this user's account ID (state 1=Sent or 2=Acknowledged)
            entries = self.session.query(GuestPassRegistry).filter(
                GuestPassRegistry.RecipientAccountID == account_id,
                GuestPassRegistry.State.in_([1, 2])  # Sent or Acknowledged
            ).all()
            return entries
        except Exception as e:
            log.error(f"Error getting passes to redeem for account {account_id}: {e}")
            return []

    def get_passes_to_redeem_by_email(self, email: str) -> List[GuestPassRegistry]:
        """
        Get all guest passes sent to an email that can be redeemed.

        Args:
            email: The recipient's email address

        Returns:
            List of GuestPassRegistry records
        """
        try:
            entries = self.session.query(GuestPassRegistry).filter(
                GuestPassRegistry.RecipientAddress.ilike(email),
                GuestPassRegistry.RecipientAccountID.is_(None),
                GuestPassRegistry.State.in_([1, 2])  # Sent or Acknowledged
            ).all()
            return entries
        except Exception as e:
            log.error(f"Error getting passes by email {email}: {e}")
            return []

    def send_guest_pass(
        self,
        pass_id: int,
        recipient_account_id: int = None,
        recipient_email: str = None
    ) -> bool:
        """
        Mark a guest pass as sent to a recipient.

        Args:
            pass_id: The guest pass ID
            recipient_account_id: Recipient's account ID (if sending to friend)
            recipient_email: Recipient's email (if sending to non-friend)

        Returns:
            True on success, False on failure
        """
        try:
            import time
            entry = self.session.query(GuestPassRegistry).filter_by(UniqueID=pass_id).first()
            if not entry:
                log.warning(f"Guest pass {pass_id} not found")
                return False

            current_time = int(time.time())

            if recipient_account_id is not None:
                entry.RecipientAccountID = recipient_account_id
            if recipient_email:
                entry.RecipientAddress = recipient_email

            entry.Sent = 1
            entry.TimeSent = current_time
            entry.State = 1  # Sent

            self.session.commit()
            log.info(f"Guest pass {pass_id} sent")
            return True

        except Exception as e:
            self.session.rollback()
            log.error(f"Error sending guest pass {pass_id}: {e}")
            return False

    def acknowledge_guest_pass(self, pass_id: int, recipient_account_id: int = None) -> bool:
        """
        Mark a guest pass as acknowledged by the recipient.

        Args:
            pass_id: The guest pass ID
            recipient_account_id: Account ID to link (if was sent by email)

        Returns:
            True on success, False on failure
        """
        try:
            import time
            entry = self.session.query(GuestPassRegistry).filter_by(UniqueID=pass_id).first()
            if not entry:
                log.warning(f"Guest pass {pass_id} not found")
                return False

            current_time = int(time.time())

            entry.Acked = 1
            entry.TimeAcked = current_time
            entry.State = 2  # Acknowledged

            # Link to account if was sent by email
            if recipient_account_id and entry.RecipientAccountID is None:
                entry.RecipientAccountID = recipient_account_id

            self.session.commit()
            log.info(f"Guest pass {pass_id} acknowledged")
            return True

        except Exception as e:
            self.session.rollback()
            log.error(f"Error acknowledging guest pass {pass_id}: {e}")
            return False

    def redeem_guest_pass(
        self,
        pass_id: int,
        redeemer_account_id: int,
        activation_expires: datetime = None
    ) -> Tuple[bool, int]:
        """
        Mark a guest pass as redeemed and grant the license.

        Args:
            pass_id: The guest pass ID
            redeemer_account_id: The account that redeemed the pass
            activation_expires: When the activated license expires (for guest passes)

        Returns:
            Tuple of (success, package_id)
        """
        try:
            import time
            entry = self.session.query(GuestPassRegistry).filter_by(UniqueID=pass_id).first()
            if not entry:
                log.warning(f"Guest pass {pass_id} not found")
                return (False, 0)

            if entry.State == 3:  # Already redeemed
                log.warning(f"Guest pass {pass_id} already redeemed")
                return (False, entry.PackageID)

            package_id = entry.PackageID
            is_gift = entry.PassType == 1  # 1 = Gift

            # Check if user already owns this package
            if self.owns_package(redeemer_account_id, package_id):
                log.warning(f"Account {redeemer_account_id} already owns package {package_id}")
                return (False, package_id)

            # Grant the license
            # license_type: 1 = guest pass (temporary), 2 = gift
            license_type = 2 if is_gift else 1
            if not self.grant_license(redeemer_account_id, package_id, license_type=license_type):
                log.error(f"Failed to grant license for package {package_id}")
                return (False, package_id)

            current_time = int(time.time())

            entry.Redeemed = 1
            entry.TimeRedeemed = current_time
            entry.State = 3  # Redeemed

            if activation_expires:
                entry.TimeActivationExpires = activation_expires

            # Link to account if not already linked
            if entry.RecipientAccountID is None:
                entry.RecipientAccountID = redeemer_account_id

            self.session.commit()
            log.info(f"Guest pass {pass_id} redeemed by account {redeemer_account_id} for package {package_id}")
            return (True, package_id)

        except Exception as e:
            self.session.rollback()
            log.error(f"Error redeeming guest pass {pass_id}: {e}")
            return (False, 0)

    def expire_guest_pass(self, pass_id: int) -> bool:
        """Mark a guest pass as expired."""
        try:
            entry = self.session.query(GuestPassRegistry).filter_by(UniqueID=pass_id).first()
            if not entry:
                return False

            entry.State = 4  # Expired
            self.session.commit()
            log.info(f"Guest pass {pass_id} expired")
            return True

        except Exception as e:
            self.session.rollback()
            log.error(f"Error expiring guest pass {pass_id}: {e}")
            return False

    def revoke_guest_pass(self, pass_id: int) -> bool:
        """Mark a guest pass as revoked."""
        try:
            entry = self.session.query(GuestPassRegistry).filter_by(UniqueID=pass_id).first()
            if not entry:
                return False

            entry.State = 5  # Revoked
            self.session.commit()
            log.info(f"Guest pass {pass_id} revoked")
            return True

        except Exception as e:
            self.session.rollback()
            log.error(f"Error revoking guest pass {pass_id}: {e}")
            return False

    def get_expired_passes(self) -> List[GuestPassRegistry]:
        """
        Get all passes that have passed their send expiration date
        but are still in Available, Sent, or Acknowledged state.

        Returns:
            List of GuestPassRegistry records that need to be expired
        """
        try:
            now = datetime.now()
            entries = self.session.query(GuestPassRegistry).filter(
                GuestPassRegistry.TimeExpiration < now,
                GuestPassRegistry.State.in_([0, 1, 2])  # Available, Sent, Acknowledged
            ).all()
            return entries
        except Exception as e:
            log.error(f"Error getting expired passes: {e}")
            return []

    def link_pass_to_transaction(self, transaction_id: int, pass_id: int) -> bool:
        """Link a guest pass to a transaction."""
        try:
            link = TransactionGuestPasses(
                transaction_id=transaction_id,
                guest_pass_id=pass_id
            )
            self.session.add(link)
            self.session.commit()
            return True
        except Exception as e:
            self.session.rollback()
            log.error(f"Error linking pass {pass_id} to transaction {transaction_id}: {e}")
            return False

    def get_passes_for_transaction(self, transaction_id: int) -> List[GuestPassRegistry]:
        """Get all guest passes linked to a transaction."""
        try:
            links = self.session.query(TransactionGuestPasses).filter_by(
                transaction_id=transaction_id
            ).all()
            pass_ids = [link.guest_pass_id for link in links]
            if not pass_ids:
                return []
            entries = self.session.query(GuestPassRegistry).filter(
                GuestPassRegistry.UniqueID.in_(pass_ids)
            ).all()
            return entries
        except Exception as e:
            log.error(f"Error getting passes for transaction {transaction_id}: {e}")
            return []

    # =========================================================================
    # Pending SystemIM Queue (for guest pass notifications)
    # =========================================================================

    def queue_pending_system_im(
        self,
        recipient_account_id: int,
        message_type: int,
        message_body: str = None,
        message_id: int = None,
        ack_required: bool = True,
        guest_pass_id: int = None
    ) -> int:
        """
        Queue a SystemIM notification for later delivery.

        Args:
            recipient_account_id: Account to notify
            message_type: SystemIMType enum value
            message_body: Message text
            message_id: Optional unique message identifier
            ack_required: Whether acknowledgment is required
            guest_pass_id: Optional related guest pass ID

        Returns:
            The UniqueID of the queued message, or 0 on failure
        """
        from utilities.database.base_dbdriver import PendingSystemIM

        try:
            pending = PendingSystemIM(
                RecipientAccountID=recipient_account_id,
                MessageType=message_type,
                MessageBody=message_body,
                MessageID=message_id,
                AckRequired=1 if ack_required else 0,
                TimeCreated=datetime.now(),
                Delivered=0,
                GuestPassID=guest_pass_id
            )
            self.session.add(pending)
            self.session.commit()
            log.debug(f"Queued SystemIM for account {recipient_account_id}")
            return pending.UniqueID

        except Exception as e:
            self.session.rollback()
            log.error(f"Error queueing SystemIM: {e}")
            return 0

    def get_pending_system_ims(self, account_id: int) -> List:
        """Get all pending SystemIM messages for an account."""
        from utilities.database.base_dbdriver import PendingSystemIM

        try:
            entries = self.session.query(PendingSystemIM).filter(
                PendingSystemIM.RecipientAccountID == account_id,
                PendingSystemIM.Delivered == 0
            ).order_by(PendingSystemIM.TimeCreated).all()
            return entries
        except Exception as e:
            log.error(f"Error getting pending SystemIMs for account {account_id}: {e}")
            return []

    def mark_system_im_delivered(self, im_id: int) -> bool:
        """Mark a pending SystemIM as delivered."""
        from utilities.database.base_dbdriver import PendingSystemIM

        try:
            entry = self.session.query(PendingSystemIM).filter_by(UniqueID=im_id).first()
            if not entry:
                return False

            entry.Delivered = 1
            entry.TimeDelivered = datetime.now()
            self.session.commit()
            return True

        except Exception as e:
            self.session.rollback()
            log.error(f"Error marking SystemIM {im_id} as delivered: {e}")
            return False
