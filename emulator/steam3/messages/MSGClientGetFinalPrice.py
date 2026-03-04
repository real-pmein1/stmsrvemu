import struct


class MSGClientGetFinalPrice:
    """
    Handles MsgClientGetFinalPrice_t packet structure.
    
    Contains only a transaction ID (GID_t m_TransID).
    """
    
    def __init__(self, client_obj, data: bytes = None):
        self.client_obj = client_obj
        self.transaction_id = 0
        
        if data:
            self.deserialize(data)
    
    def deserialize(self, data: bytes):
        """Parse the GetFinalPrice packet data"""
        try:
            if len(data) < 8:
                raise ValueError(f"Data too short for GetFinalPrice: {len(data)} < 8")
            
            # Extract and fix transaction ID in one operation
            self.transaction_id = self._fix_transaction_id(data)
            
        except (struct.error, ValueError) as e:
            raise ValueError(f"Failed to parse GetFinalPrice packet: {e}")
    
    def _fix_transaction_id(self, data: bytes) -> int:
        """
        Extract and fix transaction ID from packet data.
        Applies the same fix as fix_transactionID utility.
        """
        transactionID = struct.unpack("<Q", data)[0]
        # Split into low and high parts (swapped)
        new_low_part = (transactionID >> 32) & 0xFFFFFFFF
        new_high_part = transactionID & 0xFFFFFFFF
        # Swap the parts back to reconstruct the original transaction ID
        fixed_transactionID = (new_high_part << 32) | new_low_part
        return fixed_transactionID
    
    def __str__(self):
        return f"MSGClientGetFinalPrice(transaction_id={self.transaction_id})"
    
    def __repr__(self):
        return self.__str__()