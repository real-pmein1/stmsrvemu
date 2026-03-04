import struct


class MSGClientGetPurchaseReceipts:
    """
    Handles MsgClientGetPurchaseReceipts_t packet structure.
    
    struct MsgClientGetPurchaseReceipts_t
    {
        bool m_bUnacknowledgedOnly;
    };
    """
    
    def __init__(self, client_obj, data: bytes = None):
        self.client_obj = client_obj
        self.unacknowledged_only = False
        
        if data:
            self.deserialize(data)
    
    def deserialize(self, data: bytes):
        """Parse the GetPurchaseReceipts packet data"""
        try:
            if len(data) < 1:
                raise ValueError(f"Data too short for GetPurchaseReceipts: {len(data)} < 1")
            
            # Extract unacknowledged_only flag (1 byte)
            self.unacknowledged_only = struct.unpack_from("<?", data, 0)[0]
            
        except (struct.error, ValueError) as e:
            raise ValueError(f"Failed to parse GetPurchaseReceipts packet: {e}")
    
    def __str__(self):
        return f"MSGClientGetPurchaseReceipts(unacknowledged_only={self.unacknowledged_only})"
    
    def __repr__(self):
        return self.__str__()