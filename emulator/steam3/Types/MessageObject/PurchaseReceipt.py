from steam3.Types.MessageObject import MessageObject
from steam3.Types.keyvalue_class import KVS_TYPE_INT, KVS_TYPE_STRING, KVS_TYPE_UINT64
import logging

logger = logging.getLogger(__name__)


class PurchaseReceipt(MessageObject):
    """
    PurchaseReceipt MessageObject for Steam3 purchase responses.

    Protocol differences:
        - Protocol >= 65555: Includes CurrencyCode field and extended line item fields (TransactionID, GID)
        - Protocol < 65555: Legacy format without CurrencyCode and basic line items
    """

    # Protocol version threshold for new receipt format
    PROTOCOL_THRESHOLD = 65555

    line_item_count = 0

    def __init__(self, transaction_id, package_id, purchase_status, result_detail, transaction_time,
                 payment_method, country_code, base_price, total_discount, tax, shipping, currency_code,
                 acknowledged, line_item_count, protocol_version=0):
        # Initialize the base MessageObject with an empty data dictionary
        super().__init__(data={})

        # Store protocol version for use in add_line_item
        self.protocol_version = protocol_version

        # Explicitly convert all values to their expected types
        # This ensures enums (IntEnum) are properly serialized as integers
        self.transaction_id_int = int(transaction_id) if transaction_id else 0
        package_id_int = int(package_id) if package_id else 0
        purchase_status_int = int(purchase_status) if purchase_status else 0
        result_detail_int = int(result_detail) if result_detail else 0
        transaction_time_int = int(transaction_time) if transaction_time else 0
        payment_method_int = int(payment_method) if payment_method else 0
        base_price_int = int(base_price) if base_price else 0
        total_discount_int = int(total_discount) if total_discount else 0
        tax_int = int(tax) if tax else 0
        shipping_int = int(shipping) if shipping else 0
        currency_code_int = int(currency_code) if currency_code else 0
        acknowledged_int = 1 if acknowledged else 0
        line_item_count_int = int(line_item_count) if line_item_count else 0
        country_code_str = str(country_code) if country_code else "US"

        # Log the receipt creation for debugging
        logger.debug(f"Creating PurchaseReceipt: PackageID={package_id_int}, TransactionID={self.transaction_id_int}, "
                    f"PurchaseStatus={purchase_status_int}, ResultDetail={result_detail_int}, "
                    f"ProtocolVersion={protocol_version}")

        # Set initial values with specific keys for the PurchaseReceipt using provided parameters
        # IMPORTANT: PackageID must be non-zero for client's BInitFromSteam3 to succeed
        self.setValue('TransactionID', self.transaction_id_int, KVS_TYPE_UINT64)
        self.setValue('PackageID', package_id_int, KVS_TYPE_INT)
        self.setValue('PurchaseStatus', purchase_status_int, KVS_TYPE_INT)
        self.setValue('ResultDetail', result_detail_int, KVS_TYPE_INT)
        self.setValue('TransactionTime', transaction_time_int, KVS_TYPE_INT)
        self.setValue('PaymentMethod', payment_method_int, KVS_TYPE_INT)
        self.setValue('CountryCode', country_code_str, KVS_TYPE_STRING)
        self.setValue('BasePrice', base_price_int, KVS_TYPE_INT)
        self.setValue('TotalDiscount', total_discount_int, KVS_TYPE_INT)
        self.setValue('Tax', tax_int, KVS_TYPE_INT)
        self.setValue('Shipping', shipping_int, KVS_TYPE_INT)

        # Protocol >= 65555: Include CurrencyCode field
        if protocol_version >= self.PROTOCOL_THRESHOLD:
            self.setValue('CurrencyCode', currency_code_int, KVS_TYPE_INT)

        self.setValue('Acknowledged', acknowledged_int, KVS_TYPE_INT)
        # LineItemCount is set when add_line_item is called
        self.line_item_count = line_item_count_int

    def add_line_item(self, packageID, base_price, total_discount, tax, shipping, currency_code,
                      transaction_id=None, gid=None):
        """
        Add a line item under the 'lineitems' subkey with numeric index.

        Structure expected by client (from CPurchaseReceiptInfo::GetLineItem):
        lineitems/
            0/
                PackageID, BasePrice, TotalDiscount, Tax, Shipping, CurrencyCode
                [Protocol >= 65555 only: TransactionID, GID]
            1/
                ...

        Args:
            packageID: Package ID for this line item
            base_price: Base price in cents
            total_discount: Total discount in cents
            tax: Tax amount in cents
            shipping: Shipping cost in cents
            currency_code: Currency code (e.g., ECurrencyCode.USD)
            transaction_id: Optional transaction ID (used for protocol >= 65555)
            gid: Optional GID (used for protocol >= 65555)
        """
        # Enter the 'lineitems' parent subkey
        self.setSubKey('lineitems')
        # Enter the numeric index subkey (0, 1, 2, ...)
        self.setSubKey(str(self.line_item_count))
        self.setValue('PackageID', packageID, KVS_TYPE_INT)
        self.setValue('BasePrice', base_price, KVS_TYPE_INT)
        self.setValue('TotalDiscount', total_discount, KVS_TYPE_INT)
        self.setValue('Tax', tax, KVS_TYPE_INT)
        self.setValue('Shipping', shipping, KVS_TYPE_INT)
        self.setValue('CurrencyCode', currency_code, KVS_TYPE_INT)

        # Protocol >= 65555: Include TransactionID and GID in line items
        if self.protocol_version >= self.PROTOCOL_THRESHOLD:
            # Use provided transaction_id or fall back to receipt's transaction_id
            line_txn_id = int(transaction_id) if transaction_id else self.transaction_id_int
            line_gid = int(gid) if gid else 0
            self.setValue('TransactionID', line_txn_id, KVS_TYPE_UINT64)
            self.setValue('GID', line_gid, KVS_TYPE_UINT64)

        # Exit the numeric index subkey
        self.setSubKeyEnd()
        # Exit the 'lineitems' subkey
        self.setSubKeyEnd()

        # Update the line item count and the LineItemCount field
        self.line_item_count += 1
        self.setValue('LineItemCount', self.line_item_count, KVS_TYPE_INT)

    def add_card_info(self, credit_card_type, card_last_4_digits, card_holder_name,
                      card_exp_year, card_exp_month):
        """
        Add card info under the 'cardinfo' subkey.

        Structure expected by client (from CCardInfo getters in steamclient):
        cardinfo/
            CreditCardType (int)
            CardLast4Digits (string)
            CardHolderName (string)  - full name, NOT first/last separate
            CardExpYear (string)
            CardExpMonth (string)
        """
        self.setSubKey('cardinfo')
        self.setValue('CreditCardType', credit_card_type, KVS_TYPE_INT)
        self.setValue('CardLast4Digits', card_last_4_digits or "", KVS_TYPE_STRING)
        self.setValue('CardHolderName', card_holder_name or "", KVS_TYPE_STRING)
        self.setValue('CardExpYear', card_exp_year or "", KVS_TYPE_STRING)
        self.setValue('CardExpMonth', card_exp_month or "", KVS_TYPE_STRING)
        self.setSubKeyEnd()

    def __repr__(self):
        # Display all data stored in this PurchaseReceipt for debugging
        return f"<PurchaseReceipt {self.data}>"

#Example:
"""if __name__ == "__main__":
    import pprint
    from datetime import datetime, timedelta
    import pprint
    import json
    import struct

    # Create a PurchaseReceipt instance with some dummy values.
    now = datetime.now()
    now_ts = int(now.timestamp())
    receipt = PurchaseReceipt(
        transaction_id = 1234567890123456789,
        package_id = 101,
        purchase_status = 1,
        result_detail = 0,
        transaction_time = now_ts,
        payment_method = 2,
        country_code = "US",
        base_price = 999,
        total_discount = 100,
        tax = 50,
        shipping = 0,
        currency_code = 840,  # e.g., USD code (840)
        acknowledged = 0,
        line_item_count = 0
    )

    # Add one line item.
    receipt.add_line_item(packageID=202, base_price=499, total_discount=50, tax=25, shipping=0, currency_code=840)

    # Add card info
    receipt.add_card_info(
        credit_card_type=1,
        card_last_4_digits="1234",
        card_holder_name="John Doe",
        card_exp_year="2025",
        card_exp_month="12"
    )

    # Serialize the PurchaseReceipt.
    serialized_bytes = receipt.serialize()
    print("Serialized bytes:")
    print(serialized_bytes)

    # Now, create a new MessageObject instance using the serialized bytes.
    new_msg_obj = MessageObject(serialized_bytes)
    # Parse the serialized data into a dictionary.
    parsed_dict = new_msg_obj.parse()

    print("\nParsed dictionary:")
    pprint.pprint(new_msg_obj.get_message_objects())
    for obj in new_msg_obj.get_message_objects():
        print(obj)"""
