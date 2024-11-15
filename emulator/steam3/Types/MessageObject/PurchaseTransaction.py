from steam3.Types import MessageObject

class PurchaseTransaction:
    def __init__(self, data):
        self.message_objects = MessageObject(data)
        self.message_objects.parse()
        self.billing_info = {}
        self.shipping_info = {}
        self.gift_info = {}
        self.parse_transaction()

    def parse_transaction(self):
        objects = self.message_objects.get_message_objects()
        if len(objects) >= 1:
            # First message object is the billing information including credit card
            self.billing_info = objects[0]
        if len(objects) >= 2:
            # Second message object is the shipping address
            self.shipping_info = objects[1]
        if len(objects) >= 3:
            # Third message object is the gift information
            self.gift_info = objects[2]

    def get_billing_info(self):
        return self.billing_info

    def get_shipping_info(self):
        return self.shipping_info

    def get_gift_info(self):
        return self.gift_info

    def __str__(self):
        return (
            f"Billing Info: {self.get_billing_info()}\n"
            f"Shipping Info: {self.get_shipping_info()}\n"
            f"Gift Info: {self.get_gift_info()}"
        )

# Example:
#data = (
#    b"\x00MessageObject\x00"
#    b"\x00addressinfo\x00"
#    b"\x01name\x00ben test\x00"
#    b"\x01Address1\x00asdasdasds\x00"
#    b"\x01Address2\x00\x00"
#    b"\x01City\x00sdafd\x00"
#    b"\x01PostCode\x0012345\x00"
#    b"\x01state\x00AS\x00"
#    b"\x01CountryCode\x00US\x00"
#    b"\x01Phone\x001231231234\x00"
#    b"\x08"
#    b"\x02CreditCardType\x00\x01\x00\x00\x00"
#    b"\x01CardNumber\x004111111111111111\x00"
#    b"\x01CardHolderName\x00ben test\x00"
#    b"\x01CardExpYear\x002024\x00"
#    b"\x01CardExpMonth\x0005\x00"
#    b"\x01CardCVV2\x00111\x00"
#    b"\x08\x08"
#    b"\x00MessageObject\x00"
#    b"\x01name\x00ben test\x00"
#    b"\x01Address1\x00asdasdasds\x00"
#    b"\x01Address2\x00\x00"
#    b"\x01City\x00sdafd\x00"
#    b"\x01PostCode\x0012345\x00"
#    b"\x01state\x00AS\x00"
#    b"\x01CountryCode\x00US\x00"
#    b"\x01Phone\x001231231234\x00"
#    b"\x08\x08"
#    b"\x00MessageObject\x00"
#    b"\x02IsGift\x00\x01\x00\x00\x00"
#    b"\x01GifteeEmail\x00test@ben.com\x00"
#    b"\x07GifteeAccountID\x00\x00\x00\x00\x00\x00\x00\x00\x00"
#    b"\x01GiftMessage\x00I hope you enjoy these games!\x00"
#    b"\x01GifteeName\x00test\x00"
#    b"\x01Sentiment\x00Best Wishes\x00"
#    b"\x01Signature\x00test\x00"
#    b"\x08\x08"
#)
#
#transaction = PurchaseTransaction(data)
#print(transaction)