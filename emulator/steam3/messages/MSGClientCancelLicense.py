import struct
from steam3.cm_packet_utils import CMResponse
from steam3.Types.emsg import EMsg


class MSGClientCancelLicense:
    """
    MsgClientCancelLicense - Cancel/revoke a license for a specific package
    
    Fields:
        package_id (int): Package ID for the license to cancel
        reason (int): Reason code for cancellation
    """
    
    def __init__(self, client_obj, data: bytes = None, version: int = None):
        self.client_obj = client_obj
        self.package_id = 0
        self.reason = 0
        
        if data:
            self.deserialize(data)
    
    def deserialize(self, data: bytes):
        """Parse the binary data using struct.unpack_from"""
        if len(data) < 8:
            raise ValueError("Insufficient data for MSGClientCancelLicense")
        
        (self.package_id, self.reason) = struct.unpack_from("<II", data, 0)
    
    def to_clientmsg(self):
        """Build CMResponse packet for this message"""
        raise NotImplementedError("MSGClientCancelLicense is request-only")
    
    def to_protobuf(self):
        """Return protobuf representation if available"""
        raise NotImplementedError("No protobuf equivalent for MSGClientCancelLicense")
    
    def __str__(self):
        return f"MSGClientCancelLicense(package_id={self.package_id}, reason={self.reason})"
    
    def __repr__(self):
        return self.__str__()