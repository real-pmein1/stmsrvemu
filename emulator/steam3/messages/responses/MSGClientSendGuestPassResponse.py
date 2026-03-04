import struct
from io import BytesIO
from steam3.cm_packet_utils import CMResponse
from steam3.Types.emsg import EMsg
from steam3.Types.steam_types import EResult


class MSGClientSendGuestPassResponse:
    """
    MsgClientSendGuestPassResponse - Response to guest pass sending request
    
    Fields:
        result (EResult): Result of the guest pass send operation
        guest_pass_id (int): 64-bit GID of the guest pass that was sent
    """
    
    def __init__(self, client_obj, data: bytes = None, version: int = None):
        self.client_obj = client_obj
        self.result = EResult.Invalid
        self.guest_pass_id = 0
        
        if data:
            self.deserialize(data)
    
    def deserialize(self, data: bytes):
        """Parse the binary data using struct.unpack_from"""
        if len(data) < 12:
            raise ValueError("Insufficient data for MSGClientSendGuestPassResponse")
        
        (result_raw, self.guest_pass_id) = struct.unpack_from("<IQ", data, 0)
        self.result = EResult(result_raw)
    
    def to_clientmsg(self):
        """Build CMResponse packet for this message"""
        packet = CMResponse(EMsg.ClientSendGuestPassResponse, self.client_obj)
        
        buffer = BytesIO()
        buffer.write(struct.pack("<IQ", self.result.value, self.guest_pass_id))
        
        packet.data = buffer.getvalue()
        packet.length = len(packet.data)
        return packet
    
    def to_protobuf(self):
        """Return protobuf representation if available"""
        raise NotImplementedError("No protobuf equivalent for MSGClientSendGuestPassResponse")
    
    def __str__(self):
        return f"MSGClientSendGuestPassResponse(result={self.result}, guest_pass_id=0x{self.guest_pass_id:016X})"
    
    def __repr__(self):
        return self.__str__()