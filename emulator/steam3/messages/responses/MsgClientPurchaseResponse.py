from __future__ import annotations
import logging
import struct
from datetime import datetime
import traceback
from io import BytesIO

from steam3.Types.MessageObject.PurchaseReceipt import PurchaseReceipt
from steam3.Types.MessageObject import MessageObject
from steam3.Types.emsg import EMsg
from steam3.Types.steam_types import ECurrencyCode, EPaymentMethod, EPurchaseResultDetail, EPurchaseStatus, EResult
from steam3.cm_packet_utils import CMResponse

logger = logging.getLogger(__name__)


def debug_receipt_bytes(receipt_bytes: bytes, context: str = "Receipt"):
    """
    Debug helper to dump and verify receipt serialization.
    Logs the raw bytes and attempts to parse them back to verify correctness.
    """
    from steam3.Types.keyvaluesystem import KeyValuesSystem, RegistryKey

    logger.info(f"=== {context} Debug ===")
    logger.info(f"Serialized bytes ({len(receipt_bytes)} bytes): {receipt_bytes.hex()}")

    # Show first few bytes to identify format
    if len(receipt_bytes) > 0:
        first_byte = receipt_bytes[0]
        if first_byte == 0x00:
            logger.info(f"Format: Starts with 0x00 (KEY type) - has MessageObject wrapper")
        elif first_byte == 0x07:
            logger.info(f"Format: Starts with 0x07 (UINT64) - no wrapper, starts with TransactionID")
        elif first_byte == 0x02:
            logger.info(f"Format: Starts with 0x02 (INT) - no wrapper, starts with an INT value")
        else:
            logger.info(f"Format: Starts with 0x{first_byte:02x}")

    # Pretty print the bytes for easier reading
    hex_dump = ' '.join(f'{b:02x}' for b in receipt_bytes[:100])  # First 100 bytes
    logger.info(f"Hex dump (first 100 bytes): {hex_dump}")

    # Try to parse it back using KeyValuesSystem directly
    # The serialized data includes "MessageObject\0" wrapper, so fields are nested inside
    try:
        test_key = RegistryKey("test")
        KeyValuesSystem.deserialize_key(test_key, BytesIO(receipt_bytes))

        # Helper to recursively convert to dict
        def kv_to_dict(key):
            result = {}
            for element in key.get_elements():
                if element.is_value():
                    result[element.name] = element.value
                elif element.is_key():
                    result[element.name] = kv_to_dict(element)
            return result

        full_parsed = kv_to_dict(test_key)
        logger.info(f"Parsed back successfully: {list(full_parsed.keys())}")

        # The actual data is inside the MessageObject subkey
        parsed = full_parsed.get('MessageObject', full_parsed)
        if isinstance(parsed, dict):
            # Check critical fields
            pkg_id = parsed.get('PackageID', 'MISSING')
            logger.info(f"PackageID in parsed data: {pkg_id}")
            if pkg_id == 0:
                logger.warning(f"WARNING: PackageID is 0 - client will reject this receipt!")
            elif pkg_id == 'MISSING':
                logger.error(f"ERROR: PackageID field is MISSING from parsed data!")
            else:
                logger.info(f"PackageID looks good: {pkg_id}")

            # Log other important fields
            for field in ['TransactionID', 'PurchaseStatus', 'ResultDetail', 'PaymentMethod']:
                if field in parsed:
                    logger.info(f"  {field}: {parsed[field]}")
        else:
            logger.warning(f"Unexpected parsed structure: {type(parsed)}")

    except Exception as e:
        logger.error(f"Failed to parse receipt bytes back: {e}")
        import traceback
        logger.error(traceback.format_exc())

    logger.info(f"=== End {context} Debug ===")
class MsgClientPurchaseResponse:
    def __init__(self, client_obj):
        self.client_obj = client_obj
        self.eResult = EResult.Fail
        self.purchaseDetails = EPurchaseResultDetail.InvalidData
        self.transactionID = 0
        self.transaction_details = None

    def _get_protocol_version(self) -> int:
        """Get the client's protocol version for format decisions."""
        return getattr(self.client_obj, 'protocol_version', 0)

    def _create_error_receipt(self, purchase_status: EPurchaseStatus, result_detail: EPurchaseResultDetail) -> PurchaseReceipt:
        """
        Create a minimal receipt for error responses.
        The client ALWAYS expects a receipt in the response, even for failures.
        """
        return PurchaseReceipt(
            transaction_id   = self.transactionID if self.transactionID else 0,
            package_id       = 0,
            purchase_status  = purchase_status,
            result_detail    = result_detail,
            transaction_time = int(datetime.now().timestamp()),
            payment_method   = 0,
            country_code     = "US",
            base_price       = 0,
            total_discount   = 0,
            tax              = 0,
            shipping         = 0,
            currency_code    = ECurrencyCode.USD,
            acknowledged     = False,
            line_item_count  = 0,
            protocol_version = self._get_protocol_version()
        )

    def to_clientmsg(self):
        """
        Build and return a CMResponse for ClientPurchaseResponse.

        IMPORTANT: The client ALWAYS reads a PurchaseReceipt from the response,
        regardless of the EResult value. We must always include receipt data.
        """
        try:
            packet = CMResponse(eMsgID=EMsg.ClientPurchaseResponse,
            client_obj=self.client_obj)

            # Ensure enum values are converted to int for proper struct packing
            eresult_int = int(self.eResult)
            purchase_detail_int = int(self.purchaseDetails)

            logger.info(f"Building PurchaseResponse: EResult={eresult_int}, PurchaseDetail={purchase_detail_int}, "
                       f"TransactionID={self.transactionID}")

            packet.data = struct.pack(
            '<II',
            eresult_int,
            purchase_detail_int
            )

            receipt = None

            # For error responses, create a minimal error receipt
            # The client ALWAYS tries to read a receipt, so we must provide one
            if self.eResult != EResult.OK:
                logger.debug(f"Creating error receipt: eResult={self.eResult}, purchaseDetails={self.purchaseDetails}")
                receipt = self._create_error_receipt(
                    purchase_status=EPurchaseStatus.Failed,
                    result_detail=self.purchaseDetails
                )
                serialized = receipt.serialize()
                debug_receipt_bytes(serialized, "Error Receipt")
                packet.data += serialized
                packet.length = len(packet.data)
                return packet

            # Handle cdkey activation - check for activation_method in transaction_details
            # For CD key activations, transaction_details is a dict; for purchases, it's a tuple
            is_cdkey_activation = (self.transaction_details and
                                   isinstance(self.transaction_details, dict) and
                                   self.transaction_details.get('activation_method') == 'cdkey')

            if is_cdkey_activation:
                # This is a key activation response
                app_id = self.transaction_details.get('app_id', 0)
                package_id = self.transaction_details.get('package_id', app_id)  # Use package_id if available
                transaction_time_int = int(self.transaction_details.get('transaction_time', datetime.now()).timestamp())
                # Use the real transaction ID from transaction_details, or fall back to self.transactionID
                cdkey_transaction_id = self.transaction_details.get('transaction_id', self.transactionID)

                # CRITICAL: PackageID must be non-zero or client BInitFromSteam3 will fail
                # The client's GetPackageID returns 0 as default, and BInitFromSteam3 returns false if PackageID==0
                if package_id == 0:
                    logger.error(f"CD Key activation has package_id=0! transaction_details={self.transaction_details}")
                    logger.error("Client will reject this receipt - BInitFromSteam3 requires PackageID != 0")

                logger.info(f"Creating CD Key activation receipt: package_id={package_id}, app_id={app_id}, transaction_id={cdkey_transaction_id}")

                receipt = PurchaseReceipt(
                    transaction_id   = cdkey_transaction_id,
                    package_id       = package_id,
                    purchase_status  = EPurchaseStatus.Succeeded,
                    result_detail    = EPurchaseResultDetail.NoDetail,
                    transaction_time = transaction_time_int,
                    payment_method   = EPaymentMethod.ActivationCode,  # CD Key activation
                    country_code     = "US",
                    base_price       = 0,
                    total_discount   = 0,
                    tax              = 0,
                    shipping         = 0,
                    currency_code    = ECurrencyCode.USD,
                    acknowledged     = False,
                    line_item_count  = 0,
                    protocol_version = self._get_protocol_version()
                )

                # NOTE: Do NOT add lineitems for early client versions (pre-2009)
                # These clients don't use lineitems and the extra data may confuse parsing

                serialized = receipt.serialize()
                debug_receipt_bytes(serialized, "CD Key Activation Receipt")
                packet.data += serialized

            elif self.transactionID != 0:
                # Transaction details format: (transaction, cc_entry, external_entry, address, shipping)
                # Handle case where transaction_details is None (e.g., transaction lookup failed)
                if self.transaction_details is None:
                    logger.error(f"Transaction {self.transactionID} has no transaction_details - creating error receipt")
                    # Still need to include a receipt - client always reads one
                    receipt = self._create_error_receipt(
                        purchase_status=EPurchaseStatus.Failed,
                        result_detail=EPurchaseResultDetail.NoDetail
                    )
                    packet.data += receipt.serialize()
                    packet.length = len(packet.data)
                    return packet

                transaction_record = self.transaction_details[0]
                cc_entry = self.transaction_details[1] if len(self.transaction_details) > 1 else None
                # external_entry = self.transaction_details[2] if len(self.transaction_details) > 2 else None
                transaction_address_record = self.transaction_details[3] if len(self.transaction_details) > 3 else None

                # RECEIPT CONTAINS KEY lineitems for all items that are paid for
                if transaction_record:
                    try:
                        dt = datetime.strptime(
                        transaction_record.TransactionDate,
                        "%m/%d/%Y %H:%M:%S"
                        )
                        transaction_time_int = int(dt.timestamp())
                    except Exception:
                        transaction_time_int = 0

                    payment_method = transaction_record.PaymentType
                    country_code = (transaction_address_record.CountryCode
                                    if transaction_address_record and transaction_address_record.CountryCode
                                    else "US")
                    base_price     = transaction_record.BaseCostInCents
                    total_discount = transaction_record.DiscountsInCents
                    tax            = transaction_record.TaxCostInCents
                    shipping       = transaction_record.ShippingCostInCents
                    currency_code  = ECurrencyCode.USD
                    purchase_status = EPurchaseStatus.Succeeded
                    result_detail   = EPurchaseResultDetail.NoDetail

                    receipt = PurchaseReceipt(
                    transaction_id   = transaction_record.UniqueID,
                    package_id       = transaction_record.PackageID,
                    purchase_status  = purchase_status,
                    result_detail    = result_detail,
                    transaction_time = transaction_time_int,
                    payment_method   = payment_method,
                    country_code     = country_code,
                    base_price       = base_price,
                    total_discount   = total_discount,
                    tax              = tax,
                    shipping         = shipping,
                    currency_code    = currency_code,
                    acknowledged     = bool(transaction_record.DateAcknowledged),
                    line_item_count  = 0,
                    protocol_version = self._get_protocol_version()
                    )

                    receipt.add_line_item(
                    packageID     = transaction_record.PackageID,
                    base_price    = base_price,
                    total_discount= total_discount,
                    tax           = tax,
                    shipping      = shipping,
                    currency_code = currency_code
                    )

                    # Add card info if this was a credit card payment
                    if payment_method == int(EPaymentMethod.CreditCard) and cc_entry:
                        # Extract last 4 digits from card number
                        card_last_4 = cc_entry.CardNumber[-4:] if cc_entry.CardNumber else ""

                        receipt.add_card_info(
                            credit_card_type=cc_entry.CardType or 0,
                            card_last_4_digits=card_last_4,
                            card_holder_name=cc_entry.CardHolderName or "",
                            card_exp_year=str(cc_entry.CardExpYear) if cc_entry.CardExpYear else "",
                            card_exp_month=str(cc_entry.CardExpMonth) if cc_entry.CardExpMonth else ""
                        )
                else:
                    currency_code  = ECurrencyCode.USD
                    purchase_status = EPurchaseStatus.Succeeded
                    result_detail   = EPurchaseResultDetail.NoDetail
                    transaction_time_int = 0

                    receipt = PurchaseReceipt(
                    transaction_id   = self.transactionID,
                    package_id       = 0,
                    purchase_status  = purchase_status,
                    result_detail    = result_detail,
                    transaction_time = transaction_time_int,
                    payment_method   = 0,
                    country_code     = "US",
                    base_price       = 0,
                    total_discount   = 0,
                    tax              = 0,
                    shipping         = 0,
                    currency_code    = currency_code,
                    acknowledged     = False,
                    line_item_count  = 0,
                    protocol_version = self._get_protocol_version()
                    )

                packet.data += receipt.serialize()
            else:
                # No transactionID and no transaction_details - still need a receipt
                receipt = self._create_error_receipt(
                    purchase_status=EPurchaseStatus.Failed,
                    result_detail=self.purchaseDetails
                )
                packet.data += receipt.serialize()

            packet.length = len(packet.data)
            return packet

        except Exception as err:  # pylint: disable=broad-except
            # Capture the complete traceback and log it.
            logger.error("Error in to_clientmsg: %s\n%s",
            err, traceback.format_exc())
            # Re-raise so callers can still handle the failure if needed.
            raise
