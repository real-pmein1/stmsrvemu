import time

from steam3.Types.MessageObject import MessageObject
from steam3.Types.keyvalue_class import KVS_TYPE_INT, KVS_TYPE_INT64, KVS_TYPE_STRING, KVS_TYPE_UINT64


class MicroTransaction(MessageObject):
    transactionsCount = 0

    def __init__(self, appId, currency, language, copy=None, input_stream=None):
        super().__init__()
        if copy is not None:
            self.data = copy.data.copy()
            self.lineitemsCount = copy.lineitemsCount
        elif input_stream is not None:
            self.parse(input_stream)
            self.lineitemsCount = 0
            for _ in self.subkeys.get("lineitems", {}).keys():
                self.lineitemsCount += 1
        else:
            self.set_TransactionId(-1)
            self.set_OrderId(0)
            self.set_AppId(appId)
            self.set_Currency(currency)
            self.set_isVAT(True)
            self.set_Total(0)
            self.set_Tax(0)
            self.set_Language(language)
            self.set_SandBox(False)
            self.lineitemsCount = 0
            self.add_subkey("lineitems")

    def compile(self):
        transactionId = int(time.time())
        transactionId <<= 32
        transactionId += MicroTransaction.transactionsCount
        MicroTransaction.transactionsCount += 1

        self.set_TransactionId(transactionId)
        self.set_OrderId(transactionId)

        totalAmount = 0
        for ind in range(self.lineitemsCount):
            totalAmount += self.get_LineAmount(ind)

        if not self.get_isVAT():
            totalAmount += self.get_Tax()

        self.set_Total(totalAmount)

    def get_TransactionId(self):
        return self.getValue("TransID", -1)

    def get_OrderId(self):
        return self.getValue("OrderID", 0)

    def get_AppId(self):
        return self.getValue("appid", 0)

    def get_Currency(self):
        return self.getValue("currency", 0)

    def get_isVAT(self):
        return self.getValue("VAT", 0) != 0

    def get_Total(self):
        return self.getValue("total", 0)

    def get_Tax(self):
        return self.getValue("tax", 0)

    def get_Language(self):
        return self.getValue("language", 0)

    def is_SandBox(self):
        return self.getValue("SandBox", 0) != 0

    def get_BillingCurrency(self):
        return self.getValue("BillingCurrency", 0)

    def get_BillingTotal(self):
        return self.getValue("BillingTotal", 0)

    def is_RequiresCachedPmtMethod(self):
        return self.getValue("RequiresCachedPmtMethod", 0) != 0

    def is_Refundable(self):
        return self.getValue("Refundable", 0) != 0

    def set_TransactionId(self, value):
        self.setValue("TransID", value, KVS_TYPE_UINT64)

    def set_OrderId(self, value):
        self.setValue("OrderID", value, KVS_TYPE_UINT64)

    def set_AppId(self, value):
        self.setValue("appid", value, KVS_TYPE_INT)

    def set_Currency(self, value):
        self.setValue("currency", value, KVS_TYPE_INT)

    def set_isVAT(self, value):
        self.setValue("VAT", value, KVS_TYPE_INT)

    def set_Total(self, value):
        self.setValue("total", value, KVS_TYPE_INT64)

    def set_Tax(self, value):
        self.setValue("tax", value, KVS_TYPE_INT64)

    def set_Language(self, value):
        self.setValue("language", value, KVS_TYPE_INT)

    def set_SandBox(self, value):
        self.setValue("SandBox", value, KVS_TYPE_INT)

    def set_BillingCurrency(self, value):
        self.setValue("BillingCurrency", value, KVS_TYPE_INT)

    def set_BillingTotal(self, value):
        self.setValue("BillingTotal", value, KVS_TYPE_INT64)

    def set_RequiresCachedPmtMethod(self, value):
        self.setValue("RequiresCachedPmtMethod", value, KVS_TYPE_INT)

    def set_Refundable(self, value):
        self.setValue("Refundable", value, KVS_TYPE_INT)

    def add_Line(self, definitionId, description, amountInCents, quantity):
        self.lineitemsCount += 1
        line_key = f"lineitem_{self.lineitemsCount}"
        self.setSubKey(line_key)
        self.setValue("Definition", definitionId, KVS_TYPE_INT)
        self.setValue("description", description, KVS_TYPE_STRING)
        self.setValue("amount", amountInCents, KVS_TYPE_INT)
        self.setValue("quantity", quantity, KVS_TYPE_INT)
        self.setSubKeyEnd()

    def get_LineCount(self):
        return self.lineitemsCount

    def get_LineDefinitionId(self, line):
        return self.getValue(f"lineitem_{line}_Definition", 0)

    def get_LineDescription(self, line):
        return self.getValue(f"lineitem_{line}_description", "")

    def get_LineAmount(self, line):
        return self.getValue(f"lineitem_{line}_amount", 0)

    def get_LineQuantity(self, line):
        return self.getValue(f"lineitem_{line}_quantity", 0)

    def __repr__(self):
        return (f"<MicroTransaction TransactionID={self.get_TransactionId()} "
                f"OrderID={self.get_OrderId()} AppID={self.get_AppId()} "
                f"Currency={self.get_Currency()} VAT={self.get_isVAT()} "
                f"Total={self.get_Total()} Tax={self.get_Tax()} "
                f"Language={self.get_Language()} SandBox={self.is_SandBox()} "
                f"BillingCurrency={self.get_BillingCurrency()} "
                f"BillingTotal={self.get_BillingTotal()} "
                f"RequiresCachedPmtMethod={self.is_RequiresCachedPmtMethod()} "
                f"Refundable={self.is_Refundable()} LineItems={self.lineitemsCount}>")