"""
MsgClientLookupKeyResponse - Server response to key lookup request

Based on client decompiled code:
struct MsgClientLookupKeyResponse_t {
    EResult m_eResult;
    EPurchaseResultDetail m_eDetail; 
    // CActivationCodeInfo follows if m_eResult == OK
};
"""
import struct
from steam3.Types.MessageObject.ActivationCodeInfo import ActivationCodeInfo
from steam3.Types.steam_types import EPurchaseResultDetail, EResult
from steam3.cm_packet_utils import CMResponse
from steam3.Types.emsg import EMsg


class MsgClientLookupKeyResponse:
    """
    Server response to ClientLookupKey request
    
    Fields:
        eResult (EResult): Success/failure result
        ePurchaseResultDetail (EPurchaseResultDetail): Additional purchase detail
        activationInfo (ActivationCodeInfo): Activation code information (if successful)
    """
    
    def __init__(self, client_obj, activation_code_info=None):
        self.client_obj = client_obj
        self.eResult = EResult.OK
        self.ePurchaseResultDetail = EPurchaseResultDetail.NoDetail  
        self.activationInfo = activation_code_info

    def to_protobuf(self):
        raise NotImplementedError("Protobuf version not implemented for LookupKeyResponse")

    def to_clientmsg(self):
        """Build CMResponse packet matching client expectations"""
        packet = CMResponse(eMsgID=EMsg.ClientLookupKeyResponse, client_obj=self.client_obj)
        
        # Pack fixed header: EResult + EPurchaseResultDetail
        packet.data = struct.pack("<II", int(self.eResult), int(self.ePurchaseResultDetail))
        
        # Based on client decompiled code at lines 179-186:
        # if ( callback.m_EResult == EResult::k_EResultOK )
        # {
        #   CActivationCodeInfo::CActivationCodeInfo(&acInfo);
        #   CMessageObject::BReadFromMsg<ExtendedClientMsgHdr_t>(&acInfo, &msg);
        #   ...
        # }
        # The client expects ActivationCodeInfo MessageObject data when result is OK
        if self.eResult == EResult.OK and self.activationInfo:
            packet.data += self.activationInfo.serialize()
        
        packet.length = len(packet.data)
        return packet

    def __str__(self):
        return f"MsgClientLookupKeyResponse(eResult={self.eResult}, ePurchaseResultDetail={self.ePurchaseResultDetail}, activationInfo={self.activationInfo})"