from steam3.Types.MessageObject import MessageObject
from steam3.Types.keyvalue_class import KVS_TYPE_INT, KVS_TYPE_STRING, KVS_TYPE_UINT64


class CardInfo(MessageObject):
    def __init__(self, card_id, credit_card_type, card_number, card_holder_name, card_exp_year, card_exp_month, card_cvv2, time_last_updated=None):
        # Initialize the base MessageObject with an empty data dictionary
        super().__init__(data={})
        # Set initial values with specific keys for CardInfo using provided parameters
        self.setValue('CardID', card_id if card_id is not None else "Not Assigned", KVS_TYPE_UINT64)
        self.setValue('CreditCardType', credit_card_type, KVS_TYPE_INT)
        self.setValue('CardNumber', card_number, KVS_TYPE_STRING)
        self.setValue('CardHolderName', card_holder_name, KVS_TYPE_STRING)
        self.setValue('CardExpYear', card_exp_year, KVS_TYPE_STRING)
        self.setValue('CardExpMonth', card_exp_month, KVS_TYPE_STRING)
        self.setValue('CardCVV2', card_cvv2, KVS_TYPE_STRING)
        self.setValue('TimeLastUpdated', time_last_updated if time_last_updated is not None else "Not Set", KVS_TYPE_INT)

    def __repr__(self):
        # Display all data stored in this CardInfo for debugging
        return f"<CardInfo {self.data}>"

"""card info format:
 if ( CPurchaseReceiptInfo::GetPaymentMethod(receipt) == k_EPaymentMethodNone )
    return 0;
  CPurchaseReceiptInfo::GetCardInfo(receipt);   <--- sub key
  CCardInfo::GetCreditCardType(&cardInfo);
  CCardInfo::GetCardLast4Digits(&cardInfo) && pchCardLast4Digits
  CCardInfo::GetCardHolderFirstName(&cardInfo) && pchCardHolderFirstName
  CCardInfo::GetCardHolderLastName(&cardInfo) && pchCardHolderLastName
  CCardInfo::GetCardExpYear(&cardInfo) && pchCardExpYear
  CCardInfo::GetCardExpMonth(&cardInfo) && pchCardExpMonth
"""


"""class CardInfo(MessageObject):
    def __init__(self, card_id, credit_card_type, card_number, card_holder_name, card_exp_year, card_exp_month, card_cvv2, time_last_updated=None):
        # Initialize the base MessageObject with an empty data dictionary
        super().__init__(data={})
        # Set initial values with specific keys for CardInfo using provided parameters
        self.add_key_value_uint64('CardID', card_id )
        self.add_key_value_int('CreditCardType', credit_card_type)
        self.add_key_value_string('CardNumber', card_number)
        self.add_key_value_string('CardHolderName', card_holder_name)
        self.add_key_value_string('CardExpYear', card_exp_year)
        self.add_key_value_string('CardExpMonth', card_exp_month)
        self.add_key_value_string('CardCVV2', card_cvv2)
        self.add_key_value_int('TimeLastUpdated', time_last_updated)

    def __repr__(self):
        # Display all data stored in this CardInfo for debugging
        return f"<CardInfo {self.data}>"""