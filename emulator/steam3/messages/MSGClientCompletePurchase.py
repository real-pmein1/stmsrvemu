import struct


class MSGClientCompletePurchase:
    """
    Handles MsgClientCompletePurchase_t packet structure.
    
    struct MsgClientCompletePurchase_t
    {
        GID_t m_TransID;
    };
    """
    
    def __init__(self, client_obj, data: bytes = None):
        self.client_obj = client_obj
        self.transaction_id = 0
        
        if data:
            self.deserialize(data)
    
    def deserialize(self, data: bytes):
        """Parse the CompletePurchase packet data"""
        try:
            if len(data) < 8:
                raise ValueError(f"Data too short for CompletePurchase: {len(data)} < 8")
            
            # Extract and fix transaction ID in one operation
            self.transaction_id = self._fix_transaction_id(data)
            
        except (struct.error, ValueError) as e:
            raise ValueError(f"Failed to parse CompletePurchase packet: {e}")
    
    def _fix_transaction_id(self, data: bytes) -> int:
        """
        Extract and fix transaction ID from packet data.
        Applies the same fix as fix_transactionID utility.

        Note: Steam client sends GID_t with the high/low 32-bit parts swapped.
        """
        raw_transactionID = struct.unpack("<Q", data)[0]
        # Split into low and high parts (swapped by client)
        new_low_part = (raw_transactionID >> 32) & 0xFFFFFFFF
        new_high_part = raw_transactionID & 0xFFFFFFFF
        # Swap the parts back to reconstruct the original transaction ID
        fixed_transactionID = (new_high_part << 32) | new_low_part

        # Debug logging - remove after fixing issue
        import logging
        log = logging.getLogger("MSGClientCompletePurchase")
        log.debug(f"TransactionID: raw=0x{raw_transactionID:016X} ({raw_transactionID}), fixed=0x{fixed_transactionID:016X} ({fixed_transactionID})")

        return fixed_transactionID
    
    def __str__(self):
        return f"MSGClientCompletePurchase(transaction_id={self.transaction_id})"
    
    def __repr__(self):
        return self.__str__()