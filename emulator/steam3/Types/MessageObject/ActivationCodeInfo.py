from steam3.Types.MessageObject import MessageObject
from steam3.Types.keyvalue_class import KVS_TYPE_INT, KVS_TYPE_INT64, KVS_TYPE_STRING


class ActivationCodeInfo(MessageObject):
    def __init__(self, input_stream=None):
        super().__init__()
        if input_stream is not None:
            self.parse(input_stream)

    def get_GameCode(self):
        return self.getValue("GameCode", 0)

    def get_SalesTerritoryCode(self):
        return self.getValue("SalesTerritoryCode", 0)

    def get_Key(self):
        return self.getValue("Key", "")

    def get_PackageID(self):
        return self.getValue("PackageID", 0)

    def get_MaxUseCount(self):
        return self.getValue("MaxUseCount", 0)

    def get_Class(self):
        return self.getValue("Class", 0)

    def get_SerialNumber(self):
        return self.getValue("SerialNumber", 0)

    def get_InstanceName(self):
        return self.getValue("InstanceName", "")

    def set_GameCode(self, value):
        self.setValue("GameCode", value, KVS_TYPE_INT)

    def set_SalesTerritoryCode(self, value):
        self.setValue("SalesTerritoryCode", value, KVS_TYPE_INT)

    def set_Key(self, value):
        self.setValue("Key", value, KVS_TYPE_STRING)

    def set_PackageID(self, value):
        self.setValue("PackageID", value, KVS_TYPE_INT)

    def set_MaxUseCount(self, value):
        self.setValue("MaxUseCount", value, KVS_TYPE_INT)

    def set_Class(self, value):
        self.setValue("Class", value, KVS_TYPE_INT)

    def set_SerialNumber(self, value):
        self.setValue("SerialNumber", value, KVS_TYPE_INT)

    def set_InstanceName(self, value):
        self.setValue("InstanceName", value, KVS_TYPE_STRING)

    def __repr__(self):
        return (f"<ActivationCodeInfo GameCode={self.get_GameCode()} "
                f"SalesTerritoryCode={self.get_SalesTerritoryCode()} "
                f"Key='{self.get_Key()}' PackageID={self.get_PackageID()} "
                f"MaxUseCount='{self.get_MaxUseCount()}' Class='{self.get_Class()}' "
                f"SerialNumber='{self.get_SerialNumber()}' InstanceName='{self.get_InstanceName()}'>")

"""CActivationCodeInfo::SetClass(EActivationCodeClass)	.text	0028E3DC	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	.
CActivationCodeInfo::SetGameCode(int)	.text	0028E484	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	.
CActivationCodeInfo::SetInstanceName(char const*)	.text	002902F6	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	.
CActivationCodeInfo::SetKey(char const*)	.text	0029032E	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	.
CActivationCodeInfo::SetMaxUseCount(int)	.text	0028E36C	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	.
CActivationCodeInfo::SetPackageID(uint)	.text	0028E414	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	.
CActivationCodeInfo::SetSalesTerritoryCode(int)	.text	0028E44C	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	.
CActivationCodeInfo::SetSerialNumber(int)	.text	0028E3A4	00000037	0000001C	00000008	R	.	.	.	.	S	B	T	."""