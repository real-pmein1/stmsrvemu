from steam3.Types.MessageObject import MessageObject
from steam3.Types.keyvalue_class import KVS_TYPE_INT, KVS_TYPE_STRING, KVS_TYPE_UINT64


class PurchaseReceipt(MessageObject):
    line_item_count = 0
    def __init__(self, transaction_id, package_id, purchase_status, result_detail, transaction_time, payment_method, country_code, base_price, total_discount, tax, shipping, currency_code, acknowledged, line_item_count):
        # Initialize the base MessageObject with an empty data dictionary
        super().__init__(data={})
        # Set initial values with specific keys for the PurchaseReceipt using provided parameters
        self.setValue('TransactionID', transaction_id, KVS_TYPE_UINT64)
        self.setValue('PackageID', package_id, KVS_TYPE_INT)
        self.setValue('PurchaseStatus', purchase_status, KVS_TYPE_INT)
        self.setValue('ResultDetail', result_detail, KVS_TYPE_INT)
        self.setValue('TransactionTime', transaction_time, KVS_TYPE_INT)
        self.setValue('PaymentMethod', payment_method, KVS_TYPE_INT)
        self.setValue('CountryCode', country_code, KVS_TYPE_STRING)
        self.setValue('BasePrice', base_price, KVS_TYPE_INT)
        self.setValue('TotalDiscount', total_discount, KVS_TYPE_INT)
        self.setValue('Tax', tax, KVS_TYPE_INT)
        self.setValue('Shipping', shipping, KVS_TYPE_INT)
        self.setValue('CurrencyCode', currency_code, KVS_TYPE_INT)
        self.setValue('Acknowledged', acknowledged, KVS_TYPE_INT)
        self.setValue('LineItemCount', self.line_item_count, KVS_TYPE_INT)

    def add_line_item(self, line_item_str, packageID, base_price, total_discount, tax, is_shipped, currency_code):
        self.line_item_count += 1
        self.setSubKey(line_item_str)
        self.setValue('PackageID', packageID, KVS_TYPE_INT)
        self.setValue('BasePrice', base_price, KVS_TYPE_INT)
        self.setValue('TotalDiscount', total_discount, KVS_TYPE_INT)
        self.setValue('Tax', tax, KVS_TYPE_INT)
        self.setValue('Shipping', is_shipped, KVS_TYPE_INT)
        self.setValue('CurrencyCode', currency_code, KVS_TYPE_INT)
        self.setSubKeyEnd()

    """def add_card_info(self, card_id = 0, credit_card_type = 0, card_number = "",
            card_holder_name = "", card_exp_year = "", card_exp_month = "", card_cvv2 = "", time_last_updated = 0):
        self.setSubKey('cardinfo')
        self.add_key_value_uint64('CardID', card_id )
        self.add_key_value_int('CreditCardType', credit_card_type)
        self.add_key_value_string('CardNumber', card_number)
        self.add_key_value_string('CardHolderName', card_holder_name)
        self.add_key_value_string('CardExpYear', card_exp_year)
        self.add_key_value_string('CardExpMonth', card_exp_month)
        self.add_key_value_string('CardCVV2', card_cvv2)
        self.add_key_value_int('TimeLastUpdated', time_last_updated)"""


    def __repr__(self):
        # Display all data stored in this PurchaseReceipt for debugging
        return f"<PurchaseReceipt {self.data}>"


"""line items format:
LineItem = CPurchaseReceiptInfo::GetLineItem(receipt, nLineItemIndex); == "LineItems" <--- sub key
*nPackageID = CPurchaseLineItemInfo::GetPackageID( & lineItemInfo);
*nBaseCost = CPurchaseLineItemInfo::GetBasePrice( & lineItemInfo);
*nDiscount = CPurchaseLineItemInfo::GetTotalDiscount( & lineItemInfo);
*nTax = CPurchaseLineItemInfo::GetTax( & lineItemInfo);
*nShipping = CPurchaseLineItemInfo::GetShipping( & lineItemInfo);
*eCurrencyCode = CPurchaseLineItemInfo::GetCurrencyCode( & lineItemInfo);



CPurchaseGiftInfo::SetGiftMessage(char const*)	.text	002900FE	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	.
CPurchaseGiftInfo::SetGifteeAccountID(long long)	.text	0028F910	0000004C	0000002C	0000000C	R	.	.	.	.	S	B	T	.
CPurchaseGiftInfo::SetGifteeEmail(char const*)	.text	00290136	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	.
CPurchaseGiftInfo::SetGifteeName(char const*)	.text	002900C6	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	.
CPurchaseGiftInfo::SetIsGift(bool)	.text	0028E32E	0000003E	0000001C	00000008	R	.	.	.	.	S	B	T	.
CPurchaseGiftInfo::SetSentiment(char const*)	.text	0029008E	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	.
CPurchaseGiftInfo::SetSignature(char const*)	.text	00290056	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	.

CPurchaseLineItemInfo::SetBasePrice(uint)	.text	0028EAAC	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	.
CPurchaseLineItemInfo::SetCurrencyCode(ECurrencyCode)	.text	0028E9CC	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	.
CPurchaseLineItemInfo::SetGID(ulong long)	.text	0028FC42	0000004A	0000002C	0000000C	R	.	.	.	.	S	B	T	.
CPurchaseLineItemInfo::SetPackageID(uint)	.text	0028EAE4	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	.
CPurchaseLineItemInfo::SetShipping(uint)	.text	0028EA04	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	.
CPurchaseLineItemInfo::SetTax(uint)	.text	0028EA3C	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	.
CPurchaseLineItemInfo::SetTotalDiscount(uint)	.text	0028EA74	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	.
CPurchaseLineItemInfo::SetTransactionID(ulong long)	.text	0028FBF8	0000004A	0000002C	0000000C	R	.	.	.	.	S	B	T	.


CPurchaseReceiptInfo::SetAcknowledged(bool)	.text	0028EB54	0000003E	0000001C	00000008	R	.	.	.	.	S	B	T	.
CPurchaseReceiptInfo::SetBasePrice(uint)	.text	0028EC72	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	.
CPurchaseReceiptInfo::SetCountryCode(char const*)	.text	0029094E	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	.
CPurchaseReceiptInfo::SetCurrencyCode(ECurrencyCode)	.text	0028EB92	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	.
CPurchaseReceiptInfo::SetLineItemCount(uint)	.text	0028EB1C	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	.
CPurchaseReceiptInfo::SetPackageID(uint)	.text	0028ED8A	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	.
CPurchaseReceiptInfo::SetPaymentMethod(EPaymentMethod)	.text	0028ECAA	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	.
CPurchaseReceiptInfo::SetPurchaseStatus(EPurchaseStatus)	.text	0028ED52	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	.
CPurchaseReceiptInfo::SetResultDetail(EPurchaseResultDetail)	.text	0028ED1A	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	.
CPurchaseReceiptInfo::SetShipping(uint)	.text	0028EBCA	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	.
CPurchaseReceiptInfo::SetTax(uint)	.text	0028EC02	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	.
CPurchaseReceiptInfo::SetTotalDiscount(uint)	.text	0028EC3A	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	.
CPurchaseReceiptInfo::SetTransactionID(ulong long)	.text	0028FC8C	0000004A	0000002C	0000000C	R	.	.	.	.	S	B	T	.
CPurchaseReceiptInfo::SetTransactionTime(uint)	.text	0028ECE2	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	.
"""