from steam3.Types.MessageObject import MessageObject
from steam3.Types.keyvalue_class import KVS_TYPE_INT


class WalletInfo(MessageObject):
    def __init__(self, input_stream=None):
        super().__init__()
        if input_stream is not None:
            self.parse(input_stream)
        else:
            self.set_hasWallet(False)

    def get_hasWallet(self):
        return self.getValue("HasWallet", 0) != 0

    def get_balance(self):
        return self.getValue("nAmount", 0) / 100.0

    def get_currency(self):
        return self.getValue("eCurrencyCode", 0)

    def get_balanceDelayed(self):
        return self.getValue("nAmountDelayed", 0) / 100.0

    def get_currencyDelayed(self):
        return self.getValue("eCurrencyCodeDelayed", 0)

    def set_hasWallet(self, value):
        self.setValue("HasWallet", value, KVS_TYPE_INT)

    def set_balance(self, value):
        self.setValue("nAmount", int(value * 100.0), KVS_TYPE_INT)

    def set_currency(self, value):
        self.setValue("eCurrencyCode", value, KVS_TYPE_INT)

    def set_balanceDelayed(self, value):
        self.setValue("nAmountDelayed", int(value * 100.0), KVS_TYPE_INT)

    def set_currencyDelayed(self, value):
        self.setValue("eCurrencyCodeDelayed", value, KVS_TYPE_INT)

    def __repr__(self):
        return (f"<WalletInfo hasWallet={self.get_hasWallet()} "
                f"balance={self.get_balance()} currency={self.get_currency()} "
                f"balanceDelayed={self.get_balanceDelayed()} currencyDelayed={self.get_currencyDelayed()}>")