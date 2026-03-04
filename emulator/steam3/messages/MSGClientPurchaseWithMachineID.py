import struct
from steam3.Types.steam_types import EPaymentMethod
from steam3.cm_packet_utils import CMResponse
from steam3.Types.emsg import EMsg


class MSGClientPurchaseWithMachineID:
    """
    MsgClientPurchaseWithMachineID - Purchase request with machine identifier for validation
    
    Fields:
        package_count (int): Number of packages to purchase
        payment_method (EPaymentMethod): Payment method being used
        payment_id (int): Transaction/payment ID
        machine_id (int): Unique machine identifier for validation
        package_id (int): Package/subscription ID to purchase
    """
    
    def __init__(self, client_obj, data: bytes = None, version: int = None):
        self.client_obj = client_obj
        self.package_count = 0
        self.payment_method = EPaymentMethod.CreditCard
        self.payment_id = 0
        self.machine_id = 0
        self.package_id = 0
        
        if data:
            self.deserialize(data)
    
    def deserialize(self, data: bytes):
        """Parse the binary data using struct.unpack_from"""
        if len(data) < 24:
            raise ValueError("Insufficient data for MSGClientPurchaseWithMachineID")
        
        # Unpack the fixed-size header
        (self.package_count, 
         payment_method_raw,
         self.payment_id,
         self.machine_id,
         self.package_id) = struct.unpack_from("<IIQII", data, 0)
        
        self.payment_method = EPaymentMethod(payment_method_raw)
    
    def to_clientmsg(self):
        """Build CMResponse packet for this message"""
        raise NotImplementedError("MSGClientPurchaseWithMachineID is request-only")
    
    def to_protobuf(self):
        """Return protobuf representation if available"""
        raise NotImplementedError("No protobuf equivalent for MSGClientPurchaseWithMachineID")
    
    def __str__(self):
        return (f"MSGClientPurchaseWithMachineID(packages={self.package_count}, "
                f"method={self.payment_method}, payment_id={self.payment_id}, "
                f"machine_id=0x{self.machine_id:08X}, package_id={self.package_id})")
    
    def __repr__(self):
        return self.__str__()