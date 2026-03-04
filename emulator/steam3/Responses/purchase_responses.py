from __future__ import annotations
import struct
from datetime import datetime
from steam3.messages.responses.MsgClientPurchaseResponse import MsgClientPurchaseResponse
from steam3.messages.responses.MSGVIPStatusResponse import MSGVIPStatusResponse
from steam3.Types.MessageObject.PurchaseReceipt import PurchaseReceipt

from steam3 import database, utilities
from steam3.ClientManager.client import Client
from steam3.Types.emsg import EMsg
from steam3.Types.steam_types import ECurrencyCode, EPaymentMethod, EPurchaseResultDetail, EPurchaseStatus, EResult
from steam3.cm_packet_utils import CMResponse


def build_InitPurchaseResponse(client_obj, eResult, payment_method, transactionID, returned_result: EPurchaseResultDetail, paypal_token = None):
    """
    MsgClientInitPurchaseResponse_t
    {
      EResult m_EResult;
      EPurchaseResultDetail m_EPurchaseResultDetail;
      EPaymentMethod m_ePaymentMethod;
      GID_t m_TransID;
      char m_rgchPayPalToken[21];
    };
    """
    packet = CMResponse(eMsgID = EMsg.ClientInitPurchaseResponse, client_obj = client_obj)

    ePurchaseResultDetail = returned_result

    if payment_method == int(EPaymentMethod.PayPal) and paypal_token:
        paypal_token = utilities.generate_token(20).encode('ascii')

        print(f"paypaltoken: {paypal_token}\n"
              f"transactionID: {transactionID}")

    packet.data = struct.pack('IIIQ',
                              eResult,
                              ePurchaseResultDetail,
                              payment_method,
                              transactionID)

    if payment_method == EPaymentMethod.PayPal:
        packet.data += paypal_token + b'\x00'

    return packet


def build_GetVIPStatusResponse(client_obj, payment_method=EPaymentMethod.ClickAndBuy, is_vip=True):
    """
    Build VIP status response using the message class.

    Based on IDA analysis of steamclient_linux.so:
    - Client sends k_EMsgClientGetVIPStatus with EPaymentMethod
    - Server responds with k_EMsgClientVIPStatusResponse (9 bytes):
      - EResult (4 bytes)
      - EPaymentMethod (4 bytes)
      - bool is_vip (1 byte)
    - CClientJobVIPStatusResponse only processes if payment_method == ClickAndBuy

    Args:
        client_obj: Client object
        payment_method: Payment method being checked (should match request)
        is_vip: Whether user has VIP status for this payment method
    """
    msg = MSGVIPStatusResponse(client_obj)
    msg.result = EResult.OK
    msg.payment_method = payment_method
    msg.is_vip = is_vip

    return msg.to_clientmsg()


def build_PurchaseResponse(client_obj, transactionID=0, errorcode=EResult.OK, transaction_details=None, purchase_detail=EPurchaseResultDetail.NoDetail):
    """Build a ClientPurchaseResponse packet.
    
    This response contains the result of a purchase operation and includes
    a PurchaseReceipt MessageObject if the purchase was successful.
    
    Based on decompiled CClientJobPurchaseWithActivationCode expectations:
    - Contains EResult and EPurchaseResultDetail
    - Includes PurchaseReceiptInfo as MessageObject when successful
    - Early clients add this to their VecPurchaseReceipts collection
    
    Args:
        client_obj: Client object
        transactionID: Transaction ID (for logging/debugging)
        errorcode: EResult code (OK for success, Fail for error)  
        transaction_details: Transaction details for creating receipt
        purchase_detail: EPurchaseResultDetail for additional error info
    
    Returns:
        CMResponse packet or None on error
    """
    try:
        packet = MsgClientPurchaseResponse(client_obj)
        packet.eResult = EResult(errorcode)
        packet.purchaseDetails = purchase_detail
        packet.transactionID = transactionID
        packet.transaction_details = transaction_details  # snake_case to match class attribute
        return packet.to_clientmsg()
    except Exception as e:
        print(f"Error building PurchaseResponse: {e}")
        return None


def build_LookupKeyResponse(client_obj, result=EResult.OK, detail=EPurchaseResultDetail.NoDetail, activation_info=None):
    """Build a ClientLookupKeyResponse packet.
    
    Based on decompiled CClientJobLookupActivationCode expectations:
    - Contains EResult and EPurchaseResultDetail
    - Includes ActivationCodeInfo as MessageObject when successful
    - Early clients extract GameCode, PackageID, SalesTerritoryCode from the info
    
    Args:
        client_obj: Client object
        result: EResult code
        detail: EPurchaseResultDetail for additional info
        activation_info: ActivationCodeInfo object (required for success)
    
    Returns:
        CMResponse packet
    """
    from steam3.messages.responses.MsgClientLookupKey_response import MsgClientLookupKeyResponse
    
    response = MsgClientLookupKeyResponse(client_obj, activation_info)
    response.eResult = result
    response.ePurchaseResultDetail = detail
    response.activationInfo = activation_info
    
    return response.to_clientmsg()


def build_GetLegacyGameKeyResponse(client_obj, appid, gamekey, EResult):
    """
    struct MsgClientGetLegacyGameKeyResponse_t
    {
      int32 m_nAppID;
      EResult m_EResult;
      int32 m_cubKey; <---cdkey size
    };
    Also contains string cdkey up to 64 characters long at end of message

    """
    packet = CMResponse(eMsgID = EMsg.ClientGetLegacyGameKeyResponse, client_obj = client_obj)

    packet.data = struct.pack('III',
                              appid,
                              EResult,
                              len(gamekey))

    packet.data += gamekey + b"\x00"

    return packet

#TODO the response contains the following, Taken From Second Blob:
# 4byte eResult
# 4byte basecost  [b'\x02\x00\x00\x00'[b'subid'][b'\x04\x00\x00\x00']
# 4byte total discount [b'\x02\x00\x00\x00'[b'subid'][b'\x0a\x00\x00\x00']
#   if discount isnt null, we want DiscountInCents:
#   [b'\x02\x00\x00\x00'[b'subid'][b'\x0a\x00\x00\x00'][b'\x02\x00\x00\x00']
# 4byte tax get based on state / country
# 4byte shipping cost:
#       domestic: [b'\x02\x00\x00\x00'[b'subid'][b'\x0d\x00\x00\x00']
#       international shipping: [b'\x02\x00\x00\x00'[b'subid'][b'\x0e\x00\x00\x00']
# 1byte is shipping address attached:
#     RequiresShippingAddress:  [b'\x02\x00\x00\x00'[b'subid'][b'\x0c\x00\x00\x00']
# if yes add message object
# message object containing shipping address
# Guestpass information:
#   [b'\x02\x00\x00\x00'[b'subid'][b'\x17\x00\x00\x00']
#   key: OnPurchaseGrantGuestPassPackage(1) <appid>
def build_GetFinalPriceResponse(client_obj, eresult, transactionID, base_cost_cents=0, discounts_cents=0,
                                tax_cost_cents=0, shipping_cost_cents=0, include_shipping=False,
                                shipping_data=b""):
    """
    Builds the final price response packet.

    The client expects this structure:
    struct MsgClientGetFinalPriceResponse_t {
        EResult m_EResult;
        uint32 m_nBaseCost;
        uint32 m_nTotalDiscount;
        uint32 m_nTax;
        uint32 m_nShippingCost;
        bool m_bShippingAddressAttached;
        // MessageObject data follows if m_bShippingAddressAttached is true
    };
    """
    packet = CMResponse(eMsgID=EMsg.ClientGetFinalPriceResponse, client_obj=client_obj)

    # Pack the pricing details in the correct order expected by client
    packet.data = struct.pack('<IIIIIB',
                              eresult,
                              base_cost_cents,
                              discounts_cents,
                              tax_cost_cents,
                              shipping_cost_cents,
                              int(include_shipping))

    # Append shipping data if shipping is included.
    if include_shipping and shipping_data:
        packet.data += shipping_data

    return packet

"""      if ( eMsg == EMsg::k_EMsgClientLookupKeyResponse )
      {
        CClientMsg<MsgClientLookupKeyResponse_t>::CClientMsg(
          (CClientMsg<MsgClientLookupKeyResponse_t> *const)&msg,
          pNetPacket);
        callback.m_EResult = CClientMsg<MsgClientLookupKeyResponse_t>::Body((CClientMsg<MsgClientLookupKeyResponse_t> *const)&msg)->m_eResult;
        callback.m_EDetail = CClientMsg<MsgClientLookupKeyResponse_t>::Body((CClientMsg<MsgClientLookupKeyResponse_t> *const)&msg)->m_eDetail;
        if ( callback.m_EResult == EResult::k_EResultOK )
        {
          CActivationCodeInfo::CActivationCodeInfo(&acInfo);
          CMessageObject::BReadFromMsg<ExtendedClientMsgHdr_t>(&acInfo, &msg);
          callback.m_nGameCode = CActivationCodeInfo::GetGameCode(&acInfo);
          callback.m_nPackageID = CActivationCodeInfo::GetPackageID(&acInfo);
          callback.m_nSalesTerritoryCode = CActivationCodeInfo::GetSalesTerritoryCode(&acInfo);
          CActivationCodeInfo::~CActivationCodeInfo(&acInfo);"""
"""
def build_LookupKeyResponse(client_obj, eresult, epurchase_result_detail, activation_code_info=None):
    
    Build LookupKeyResponse packet based on client expectations.
    
    Based on client decompiled code:
    - callback.m_EResult = Body()->m_eResult 
    - callback.m_EDetail = Body()->m_eDetail
    - if EResult is OK, reads CActivationCodeInfo from message
    
    Args:
        client_obj: Client object  
        eresult: EResult value
        epurchase_result_detail: EPurchaseResultDetail value
        activation_code_info: ActivationCodeInfo object (required if eresult is OK)
    
    Returns:
        CMResponse packet
    
	
    from steam3.messages.responses.MsgClientLookupKey_response import MsgClientLookupKeyResponse
    
    response = MsgClientLookupKeyResponse(client_obj, activation_code_info)
    response.eResult = eresult
    response.ePurchaseResultDetail = epurchase_result_detail
    return response.to_clientmsg()"""


def build_GetPurchaseReceiptsResponse(client_obj, receipts=None):
    """
    Build GetPurchaseReceiptsResponse packet containing purchase receipts.
    
    Args:
        client_obj: Client object
        receipts: List of PurchaseReceipt objects
    
    Returns:
        CMResponse packet
    """
    from steam3.messages.responses.MSGClientGetPurchaseReceiptsResponse import MSGClientGetPurchaseReceiptsResponse
    
    response = MSGClientGetPurchaseReceiptsResponse(client_obj, receipts or [])
    return response.to_clientmsg()