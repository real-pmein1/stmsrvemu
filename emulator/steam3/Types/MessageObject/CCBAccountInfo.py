from steam3.Types.MessageObject import MessageObject
from steam3.Types.keyvalue_class import KVS_TYPE_INT, KVS_TYPE_INT64, KVS_TYPE_STRING


class ClickAndBuy_AccountInfo(MessageObject):
    """CCBAccountInfo::SetAccountNum(long long)	.text	0028F95C	0000004C	0000002C	0000000C	R	.	.	.	.	S	B	T	.
    CCBAccountInfo::SetCountryCode(char const*)	.text	0029016E	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	.
    CCBAccountInfo::SetPaymentID(ulong long)	.text	0028F9A8	0000004A	0000002C	0000000C	R	.	.	.	.	S	B	T	.
    CCBAccountInfo::SetState(char const*)	.text	002901A6	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	."""

    def __init__(self, accountnum, countrycode, paymentid, state):
        # Initialize the base MessageObject with an empty data dictionary
        super().__init__(data={})
        # Set initial values with specific keys for the License using provided parameters
        self.setValue('AccountNum', accountnum, KVS_TYPE_INT64)  # 4 byte int
        self.setValue('CountryCode', countrycode, KVS_TYPE_STRING)  # 4 byte int
        self.setValue('PaymentID', paymentid, KVS_TYPE_INT64)  # 4 byte int
        self.setValue('State', state, KVS_TYPE_STRING)  # 4 byte int

    def __repr__(self):
        # Display all data stored in this License for debugging
        return f"<ClickAndBuy_AccountInfo {self.data}>"