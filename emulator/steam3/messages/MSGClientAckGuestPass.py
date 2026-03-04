import struct
from steam3.cm_packet_utils import CMResponse
from steam3.Types.emsg import EMsg


class MSGClientAckGuestPass:
    """
    MsgClientAckGuestPass - Acknowledge receipt of a guest pass
    
    Fields:
        guest_pass_id (int): 64-bit GID of the guest pass being acknowledged
    """
    
    def __init__(self, client_obj, data: bytes = None, version: int = None):
        self.client_obj = client_obj
        self.guest_pass_id = 0
        
        if data:
            self.deserialize(data)
    
    def deserialize(self, data: bytes):
        """Parse the binary data using struct.unpack_from"""
        if len(data) < 8:
            raise ValueError("Insufficient data for MSGClientAckGuestPass")
        
        self.guest_pass_id = struct.unpack_from("<Q", data, 0)[0]
    
    def to_clientmsg(self):
        """Build CMResponse packet for this message"""
        raise NotImplementedError("MSGClientAckGuestPass is request-only")
    
    def to_protobuf(self):
        """Return protobuf representation if available"""
        raise NotImplementedError("No protobuf equivalent for MSGClientAckGuestPass")
    
    def __str__(self):
        return f"MSGClientAckGuestPass(guest_pass_id=0x{self.guest_pass_id:016X})"
    
    def __repr__(self):
        return self.__str__()