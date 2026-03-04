import struct
from io import BytesIO
from steam3.cm_packet_utils import CMResponse
from steam3.Types.emsg import EMsg
from steam3.Types.steam_types import EResult


class MSGClientRedeemGuestPassResponse:
    """
    MsgClientRedeemGuestPassResponse - Response to guest pass redemption request
    
    Fields:
        result (EResult): Result of the guest pass redemption operation
        guest_pass_id (int): 64-bit GID of the guest pass that was redeemed
        package_id (int): Package ID that was granted (if successful)
    """
    
    def __init__(self, client_obj, data: bytes = None, version: int = None):
        self.client_obj = client_obj
        self.result = EResult.Invalid
        self.guest_pass_id = 0
        self.package_id = 0
        
        if data:
            self.deserialize(data)
    
    def deserialize(self, data: bytes):
        """Parse the binary data using struct.unpack_from"""
        if len(data) < 16:
            raise ValueError("Insufficient data for MSGClientRedeemGuestPassResponse")
        
        (result_raw, 
         self.guest_pass_id, 
         self.package_id) = struct.unpack_from("<IQI", data, 0)
        self.result = EResult(result_raw)
    
    def to_clientmsg(self):
        """Build CMResponse packet for this message"""
        packet = CMResponse(EMsg.ClientRedeemGuestPassResponse, self.client_obj)
        
        buffer = BytesIO()
        buffer.write(struct.pack("<IQI", 
                                self.result.value, 
                                self.guest_pass_id,
                                self.package_id))
        
        packet.data = buffer.getvalue()
        packet.length = len(packet.data)
        return packet
    
    def to_protobuf(self):
        """Return protobuf representation if available"""
        raise NotImplementedError("No protobuf equivalent for MSGClientRedeemGuestPassResponse")
    
    def __str__(self):
        return (f"MSGClientRedeemGuestPassResponse(result={self.result}, "
                f"guest_pass_id=0x{self.guest_pass_id:016X}, package_id={self.package_id})")
    
    def __repr__(self):
        return self.__str__()