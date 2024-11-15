import pprint
import struct

from steam3 import database, utilities
from steam3.ClientManager.client import Client
from steam3.Types.MessageObject import MessageObject
from steam3.Types.emsg import EMsg
from steam3.Types.keyvalue_class import KVS_TYPE_STRING
from steam3.Types.steam_types import EPaymentMethod, EPurchaseResultDetail, EResult
from steam3.cm_packet_utils import CMResponse
from utilities.database.base_dbdriver import Steam3TransactionAddressRecord, Steam3TransactionsRecord


def build_InitPurchaseResponse(client_obj, payment_method, transactionID):
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
    #TODO add check to ensure user has permissions to purchase anything

    eResult = EResult.OK
    ePurchaseResultDetail = EPurchaseResultDetail.NoDetail
    paypal_token = b'\x00' * 20

    if payment_method == int(EPaymentMethod.PayPal):
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


def build_GetVIPStatusResponse(client_obj):
    """
    MsgVIPStatusResponse_t
    {
      EResult m_EResult;
      EPaymentMethod m_ePaymentMethod;
      bool m_bVipUser;
    };
    """
    packet = CMResponse(eMsgID = EMsg.ClientVIPStatusResponse, client_obj = client_obj)

    packet.data = struct.pack('IB',
                              EPaymentMethod.ClickAndBuy,
                              1)

    return packet


def build_PurchaseResponse(client_obj, transactionID = 0, errorcode = 1):

    """ Newer client response: (clientpurchaseresponse)
       body.result = (ResultType) in->readInt32();
    body.detail = (PurchaseResultDetail) in->readInt32();
    body.receipt = new PurchaseReceipt( in);

     OR for older clients:
     (ClientGetPurchaseReceiptsResponse)
    out->writeInt32(body.purchaseReceipts->size());

		Iterator<PurchaseReceipt*> * receipts=body.purchaseReceipts->iterator();
		while (receipts->hasNext())
		{
			PurchaseReceipt * receipt=receipts->next();
			receipt->persist(out);
		}
		delete receipts;

    or the response could be this for clients after version 457:
    struct
    PurchaseResponse_t
    {
    EResult m_EResult;
    EPurchaseResultDetail m_EPurchaseResultDetail;
    int32 m_iReceiptIndex;
    };

    or """
    # TODO eventually support ALL purchase detail results? >:D support a real payment system that goes directly into my (BENS) pocket >:D

    # TODO set receipt ack in sql to 0 until we get the acknowledgement from them
    packet = CMResponse(eMsgID = EMsg.ClientPurchaseResponse, client_obj = client_obj)

    packet.data = struct.pack('<II',
                              int(EResult.OK),
                              EPurchaseResultDetail.NoDetail)
    # TODO if this is a response to cdkey activation (transactionID = 0)

    # RECEIPT CONTAINS KEY lineitems for all items that are paid for

    return packet


def build_GetLegacyGameKeyResponse(client_obj, appid, gamekey):
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
                              client_obj.eResult,
                              len(gamekey))

    packet.data += gamekey + b"\x00"

    return packet


def build_GetFinalPriceResponse(client_obj, transactionID):
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

    packet = CMResponse(eMsgID = EMsg.ClientGetFinalPriceResponse, client_obj = client_obj)

    transaction = client_obj.get_transaction(transactionID)
    transaction_entry: Steam3TransactionsRecord = transaction[0]


    if transaction_entry:
        eResult = EResult.OK
        packet.data = struct.pack('I', eResult)
    else:
        eResult = EResult.Fail
        packet.data = struct.pack('I', eResult)
        return packet

    include_shipping = True if transaction_entry.ShippingEntryID else False
    # Convert the string values to integer cents
    base_cost_cents = transaction_entry.BaseCostInCents
    discounts_cents = transaction_entry.DiscountsInCents
    tax_cost_cents = transaction_entry.TaxCostInCents
    shipping_cost_cents = transaction_entry.ShippingCostInCents

    # Pack the data
    packet.data = struct.pack('<IIIIIB',
                              eResult,
                              base_cost_cents,
                              discounts_cents,
                              tax_cost_cents,
                              shipping_cost_cents,
                              include_shipping)

    if include_shipping:
        # FIXME this is broken.. the setValue name stuff
        shipping_entry: Steam3TransactionAddressRecord = transaction[5]
        name_parts = shipping_entry.Name.split()
        first_name = name_parts[0]
        last_name = name_parts[-1]
        print(name_parts)
        pprint.pprint(shipping_entry)
        shipaddress_object = MessageObject()
        shipaddress_object.setValue('FirstName', first_name, KVS_TYPE_STRING)
        shipaddress_object.setValue('LastName', last_name, KVS_TYPE_STRING)
        shipaddress_object.setValue('Address1', shipping_entry.Address1, KVS_TYPE_STRING)
        shipaddress_object.setValue('Address2', shipping_entry.Address2, KVS_TYPE_STRING)
        shipaddress_object.setValue('City', shipping_entry.City, KVS_TYPE_STRING)
        shipaddress_object.setValue('PostCode', shipping_entry.PostCode, KVS_TYPE_STRING)
        shipaddress_object.setValue('State', shipping_entry.State, KVS_TYPE_STRING)
        shipaddress_object.setValue('CountryCode', shipping_entry.CountryCode, KVS_TYPE_STRING)
        shipaddress_object.setValue('Phone', shipping_entry.Phone, KVS_TYPE_STRING)

        packet.data += shipaddress_object.serialize()

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

def build_GetPurchaseReceiptsResponse(client_obj):
    """
    # 4byte eResult
    """
    packet = CMResponse(eMsgID = EMsg.ClientGetPurchaseReceiptsResponse, client_obj = client_obj)

    packet.data = struct.pack('<I',
                              0)

    return packet