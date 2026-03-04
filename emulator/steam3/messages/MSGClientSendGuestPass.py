import struct
from steam3.cm_packet_utils import CMResponse
from steam3.Types.emsg import EMsg


class MSGClientSendGuestPass:
    """
    MsgClientSendGuestPass - Send a guest pass to another user by email or AccountID
    
    Fields:
        guest_pass_id (int): 64-bit GID of the guest pass to send
        is_resend (bool): Whether this is a resend of an existing guest pass
        account_id (int): Target AccountID (0xFFFFFFFF if sending by email)
        email_address (str): Email address to send to (if account_id is 0xFFFFFFFF)
    """
    
    def __init__(self, client_obj, data: bytes = None, version: int = None):
        self.client_obj = client_obj
        self.guest_pass_id = 0
        self.is_resend = False
        self.account_id = 0
        self.email_address = ""
        
        if data:
            self.deserialize(data)
    
    def deserialize(self, data: bytes):
        """Parse the binary data using struct.unpack_from"""
        if len(data) < 13:  # Q + B + I = 8 + 1 + 4 = 13 minimum
            raise ValueError("Insufficient data for MSGClientSendGuestPass")
        
        # Unpack fixed header
        (self.guest_pass_id, 
         is_resend_byte,
         self.account_id) = struct.unpack_from("<QBI", data, 0)
        
        self.is_resend = bool(is_resend_byte)
        
        # Extract email address (null-terminated string after fixed header)
        email_start = struct.calcsize("<QBI")
        if email_start < len(data):
            # Find null terminator
            email_end = data.find(b'\x00', email_start)
            if email_end == -1:
                email_end = len(data)
            
            try:
                self.email_address = data[email_start:email_end].decode('utf-8')
            except UnicodeDecodeError:
                self.email_address = data[email_start:email_end].decode('utf-8', errors='ignore')
    
    def to_clientmsg(self):
        """Build CMResponse packet for this message"""
        raise NotImplementedError("MSGClientSendGuestPass is request-only")
    
    def to_protobuf(self):
        """Return protobuf representation if available"""
        raise NotImplementedError("No protobuf equivalent for MSGClientSendGuestPass")
    
    def __str__(self):
        return (f"MSGClientSendGuestPass(guest_pass_id=0x{self.guest_pass_id:016X}, "
                f"is_resend={self.is_resend}, account_id={self.account_id}, "
                f"email='{self.email_address}')")
    
    def __repr__(self):
        return self.__str__()