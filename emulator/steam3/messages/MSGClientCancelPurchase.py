import struct
from steam3.cm_packet_utils import CMResponse
from steam3.Types.emsg import EMsg


class MSGClientCancelPurchase:
    """
    MsgClientCancelPurchase - Cancel an existing purchase transaction
    
    Fields:
        transaction_id (int): 64-bit transaction ID to cancel
    """
    
    def __init__(self, client_obj, data: bytes = None, version: int = None):
        self.client_obj = client_obj
        self.transaction_id = 0
        
        if data:
            self.deserialize(data)
    
    def deserialize(self, data: bytes):
        """Parse the binary data using struct.unpack_from"""
        if len(data) < 8:
            raise ValueError("Insufficient data for MSGClientCancelPurchase")
        
        self.transaction_id = struct.unpack_from("<Q", data, 0)[0]
    
    def to_clientmsg(self):
        """Build CMResponse packet for this message"""
        raise NotImplementedError("MSGClientCancelPurchase is request-only")
    
    def to_protobuf(self):
        """Return protobuf representation if available"""
        raise NotImplementedError("No protobuf equivalent for MSGClientCancelPurchase")
    
    def __str__(self):
        return f"MSGClientCancelPurchase(transaction_id=0x{self.transaction_id:016X})"
    
    def __repr__(self):
        return self.__str__()