import struct
from steam3.cm_packet_utils import CMResponse
from steam3.Types.emsg import EMsg
from steam3.Types.MessageObject.PurchaseReceipt import PurchaseReceipt


class MSGClientGetPurchaseReceiptsResponse:
    """
    Handles MsgClientGetPurchaseReceiptsResponse_t packet structure.
    
    struct MsgClientGetPurchaseReceiptsResponse_t
    {
        int32 m_cReceipts;
    };
    
    Followed by PurchaseReceipt MessageObjects for each receipt.
    """
    
    def __init__(self, client_obj, receipts=None):
        self.client_obj = client_obj
        self.receipts = receipts or []
    
    def add_receipt(self, receipt: PurchaseReceipt):
        """Add a purchase receipt to the response"""
        self.receipts.append(receipt)
    
    def to_clientmsg(self):
        """Build and return a CMResponse for GetPurchaseReceiptsResponse"""
        packet = CMResponse(eMsgID=EMsg.ClientGetPurchaseReceiptsResponse, client_obj=self.client_obj)
        
        # Pack the receipt count
        packet.data = struct.pack('<i', len(self.receipts))
        
        # Serialize each receipt
        for receipt in self.receipts:
            packet.data += receipt.serialize()
        
        packet.length = len(packet.data)
        return packet
    
    def __str__(self):
        return f"MSGClientGetPurchaseReceiptsResponse(receipt_count={len(self.receipts)})"
    
    def __repr__(self):
        return self.__str__()