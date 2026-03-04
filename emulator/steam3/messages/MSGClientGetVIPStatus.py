import struct
from steam3.Types.steam_types import EPaymentMethod
from steam3.cm_packet_utils import CMResponse
from steam3.Types.emsg import EMsg


class MSGClientGetVIPStatus:
    """
    MsgClientGetVIPStatus - Request VIP status for a specific payment method (e.g., Click and Buy)
    
    Fields:
        payment_method (EPaymentMethod): Payment method to check VIP status for
    """
    
    def __init__(self, client_obj, data: bytes = None, version: int = None):
        self.client_obj = client_obj
        self.payment_method = EPaymentMethod.CreditCard
        
        if data:
            self.deserialize(data)
    
    def deserialize(self, data: bytes):
        """Parse the binary data using struct.unpack_from"""
        if len(data) < 4:
            raise ValueError("Insufficient data for MSGClientGetVIPStatus")
        
        payment_method_raw = struct.unpack_from("<I", data, 0)[0]
        self.payment_method = EPaymentMethod(payment_method_raw)
    
    def to_clientmsg(self):
        """Build CMResponse packet for this message"""
        raise NotImplementedError("MSGClientGetVIPStatus is request-only")
    
    def to_protobuf(self):
        """Return protobuf representation if available"""
        raise NotImplementedError("No protobuf equivalent for MSGClientGetVIPStatus")
    
    def __str__(self):
        return f"MSGClientGetVIPStatus(payment_method={self.payment_method})"
    
    def __repr__(self):
        return self.__str__()