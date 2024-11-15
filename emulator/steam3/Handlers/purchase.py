import pprint
import struct

import globalvars
from steam3 import utilities
from steam3.ClientManager.client import Client
from steam3.Responses.general_responses import build_GeneralAck, build_General_response
from steam3.Responses.guestpass_responses import build_GetGiftTargetListResponse
from steam3.Responses.purchase_responses import build_GetFinalPriceResponse, build_GetLegacyGameKeyResponse, build_GetVIPStatusResponse, build_InitPurchaseResponse, build_PurchaseResponse
from steam3.Types.MessageObject import MessageObject
from steam3.Types.steam_types import EPaymentMethod, EResult
from steam3.cm_packet_utils import CMPacket
from steam3.utilities import read_string


def handle_GetGiftTargetList(cmserver_obj, packet: CMPacket, client_obj: Client):
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved Gift Target List Request")
    request = packet.CMRequest

    packageID = struct.unpack("<I", request.data)[0]

    return build_GetGiftTargetListResponse(cmserver_obj, client_obj, packageID)


def handle_GetVIPStatus(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    packetid: 837
    b'\x20\x00\x00\x00' #purchase method
    struct MsgClientGetVIPStatus_t
    {
      EPaymentMethod m_ePaymentMethod;
    };
    """
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved Get VIP Status (Click and Buy) Request")
    request = packet.CMRequest
    return [build_GetVIPStatusResponse(request)]


def handle_InitPurchase(cmserver_obj, packet: CMPacket, client_obj: Client):
    """struct MsgClientInitPurchase_t
        {
          uint32 m_cPackages;
          EPaymentMethod m_ePaymentMethod;
          GID_t m_gidPaymentID;
          bool m_bStorePaymentInfo;
        };
        paypal:
        b'\x01\x00\x00\x00  - packages
        \x04\x00\x00\x00 - payment method
        \xff\xff\xff\xff\xff\xff\xff\xff - payment id
        \x00 - is gift ??
        \x1d\x00\x00\x00 - subscriptionid
        \x00MessageObject\x00\x02IsGift\x00\x00\x00\x00\x00\x08\x08'
    """
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

    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved Init Purchase Request")
    request = packet.CMRequest

    gift_entryID: int = 0
    address_entryID: int = 0
    shippingaddress_entryID: int or None = None
    payment_entryID: int = 0
    discountedamount: int = 0
    shippingamount: int = 0

    unpack_fmt: str  = "<IIQBI"

    product_count, payment_method, transactionID, include_storepaymentinfo, subscriptionID = struct.unpack(unpack_fmt, request.data[0:21])

    message_obj = MessageObject(data = request.data[struct.calcsize(unpack_fmt):])
    message_obj.parse()

    payment_method = EPaymentMethod(payment_method)
    subid_byte = int(subscriptionID).to_bytes(4, 'little')

    cdr_subiddictionary = globalvars.CDR_DICTIONARY[b'\x02\x00\x00\x00'][subid_byte]
    base_cost = int.from_bytes(cdr_subiddictionary[b'\x04\x00\x00\x00'], "little")

    #pprint.pprint(cdr_subiddictionary)

    if cdr_subiddictionary.get(b'\x0a\x00\x00\x00', {}) != {}:
        #FIXME use qualifiers to determin which discount to give!
        # Right now this just grabs the first discount in the dictionary
        discountedamount = int.from_bytes(cdr_subiddictionary[b'\x0a\x00\x00\x00'][b'\x01\x00\x00\x00'][b'\x02\x00\x00\x00'], "little")

    taxes: int = 0  # FIXME figure out how to calculate tax per location... thats a FUCK TON of work!

    accompanying_guestpasses = utilities.extract_guest_pass_packages(cdr_subiddictionary)

    # Only for Creditcard / Non-paypal or oneclick transactions
    if payment_method == EPaymentMethod.CreditCard:
        messageobj_dict = message_obj.message_objects[0]
        shippingobj_dict = message_obj.message_objects[1]
        giftobj_dict = message_obj.message_objects[2]

        # If shipping
        if cdr_subiddictionary.get(b'\x0c\x00\x00\x00', {}) != {}:
            print("ITEM IS A SHIPPED ITEM!")
            #pprint.pprint(cdr_subiddictionary.get(b'\x0c\x00\x00\x00', {}))
            # FIXME determine if shipping domesticly or internationally
            shippingamount = int.from_bytes(cdr_subiddictionary[b'\x0d\x00\x00\x00'], "little")
            # International shipping is \x0e\x00\x00\x00

            if shippingobj_dict != {}:
                shipping_address_comparison = utilities.compare_dictionaries(messageobj_dict, shippingobj_dict)

                if shipping_address_comparison is not True:
                    shippingaddress_entryID = client_obj.get_addressEntryID(shippingobj_dict['name'],
                                                                            shippingobj_dict['Address1'],
                                                                            shippingobj_dict['Address2'],
                                                                            shippingobj_dict['City'],
                                                                            shippingobj_dict['PostCode'],
                                                                            shippingobj_dict['state'],
                                                                            shippingobj_dict['CountryCode'],
                                                                            shippingobj_dict['Phone'])
            else:
                shippingaddress_entryID = None

        address_entryID = client_obj.get_addressEntryID(messageobj_dict['addressinfo']['name'],
                                                        messageobj_dict['addressinfo']['Address1'],
                                                        messageobj_dict['addressinfo']['Address2'],
                                                        messageobj_dict['addressinfo']['City'],
                                                        messageobj_dict['addressinfo']['PostCode'],
                                                        messageobj_dict['addressinfo']['state'],
                                                        messageobj_dict['addressinfo']['CountryCode'],
                                                        messageobj_dict['addressinfo']['Phone'])

        payment_entryID = client_obj.get_or_set_paymentcardinfo(messageobj_dict['CreditCardType'],
                                                                messageobj_dict['CardNumber'],
                                                                messageobj_dict['CardHolderName'],
                                                                messageobj_dict['CardExpYear'],
                                                                messageobj_dict['CardExpMonth'],
                                                                messageobj_dict['CardCVV2'],
                                                                address_entryID)
    elif payment_method == EPaymentMethod.PayPal:
        giftobj_dict = message_obj.message_objects[0]
        random_paypal_token = utilities.generate_token(20)

        payment_entryID = client_obj.add_external_transactioninfo(subscriptionID,
                                                                  EPaymentMethod.PayPal,
                                                                  random_paypal_token)
    else:
        cmserver_obj.log.error(f"Invalid or Unsupported payment method {payment_method}")

    if giftobj_dict['IsGift'] == 1:
        gift_entryID = client_obj.add_gift_transactioninfo(subscriptionID,
                                                           giftobj_dict['GifteeEmail'],
                                                           giftobj_dict['GifteeAccountID'],
                                                           giftobj_dict['GiftMessage'],
                                                           giftobj_dict['GifteeName'],
                                                           giftobj_dict['Sentiment'],
                                                           giftobj_dict['Signature'])

    if (shippingaddress_entryID != 0 or shippingaddress_entryID is not None) and payment_entryID != EPaymentMethod.PayPal:
        shippingaddress_entryID = address_entryID
        print("IS SHIPPED ITEM 2")

    if shippingaddress_entryID is not None and shippingamount == 0:
        print("IS SHIPPED ITEM WITH 0 DOLLAR SHIPPING COST")
        shippingaddress_entryID = None

    # save all other information to Steam3TransactionsRecord
    transactionID = client_obj.add_new_steam3_transaction(payment_method,
                                                          payment_entryID,
                                                          subscriptionID,
                                                          gift_entryID,
                                                          address_entryID,
                                                          base_cost,
                                                          discountedamount,
                                                          taxes,
                                                          shippingamount,
                                                          shippingaddress_entryID,
                                                          accompanying_guestpasses)
    #pprint.pprint(message_obj.parse())
    return [build_InitPurchaseResponse(client_obj, payment_method, transactionID)]
#paypal bought as gift (from client):
#response might be: InitPayPalPurchaseResponse
#packetid: 711
#b'\x01\x00\x00\x00\x04\x00\x00\x00\xff\xff\xff\xff\xff\xff\xff\xff\x00\xd5\x01\x00\x00\x00MessageObject\x00\x02IsGift\x00\x01\x00\x00\x00\x01GifteeEmail\x00dsafas@fdfgs.gfhfg\x00\x07GifteeAccountID\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01GiftMessage\x00I hope you enjoy these games!\x00\x01GifteeName\x00dsafas\x00\x01Sentiment\x00nigger\x00\x01Signature\x00test\x00\x08\x08'

#visa creditcard purchase (as gift from client):
#packetid: 711
#b'\x01\x00\x00\x00 <- package count
# \x02\x00\x00\x00  <-- payment method
# \xff\xff\xff\xff\xff\xff\xff\xff  <-- paymentID
# \x00 <-- store payment information
# \xd5\x01\x00\x00 <--- SubscriptionID / ProductID
# \x00MessageObject\x00
# \x00addressinfo\x00
# \x01name\x00ben test\x00
# \x01Address1\x00asdasdasds\x00
# \x01Address2\x00\x00
# \x01City\x00sdafd\x00
# \x01PostCode\x0012345\x00
# \x01state\x00AS\x00
# \x01CountryCode\x00US\x00
# \x01Phone\x001231231234\x00
# \x08
# \x02CreditCardType\x00\x01\x00\x00\x00
# \x01CardNumber\x004111111111111111\x00
# \x01CardHolderName\x00ben test\x00
# \x01CardExpYear\x002024\x00
# \x01CardExpMonth\x0005\x00
# \x01CardCVV2\x00111\x00
# \x08\x08
# \x00MessageObject\x00
# \x01name\x00ben test\x00
# \x01Address1\x00asdasdasds\x00
# \x01Address2\x00\x00
# \x01City\x00sdafd\x00
# \x01PostCode\x0012345\x00
# \x01state\x00AS\x00
# \x01CountryCode\x00US\x00
# \x01Phone\x001231231234\x00
# \x08\x08
# \x00MessageObject\x00
# \x02IsGift\x00\x01\x00\x00\x00
# \x01GifteeEmail\x00test@ben.com\x00
# \x07GifteeAccountID\x00\x00\x00\x00\x00\x00\x00\x00\x00
# \x01GiftMessage\x00I hope you enjoy these games!\x00
# \x01GifteeName\x00test\x00
# \x01Sentiment\x00Best Wishes\x00
# \x01Signature\x00test\x00
# \x08\x08'
def handle_GetLegacyGameKey(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    struct MsgClientGetLegacyGameKey_t
    {
      int32 m_nAppID;
    };
    packetid: 730
b'\xdc\x1e\x00\x00'
    """
    client_address = client_obj.ip_port
    request = packet.CMRequest
    request_data = request.data
    packet_size = len(request_data)
    appid = struct.unpack("<I", request_data[:4])[0]

    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved Client Get Legacy Game Key [NoImp]")
    cmserver_obj.log.info(f"({client_address[0]} appid: {appid}")

    #TODO query database for specific cdkey

    cdkey = b'123456789a'
    return [build_GetLegacyGameKeyResponse(request, appid, cdkey)]


def handle_RegisterKey(cmserver_obj, packet: CMPacket, client_obj: Client):
    # TODO handle this packet properly!
    """packetid: 743
        b'\x00\x00MessageObject\x00\x01Key\x00WJM2E-BWF2C-7D5NX-EGRZ5-G5SNN\x00\x08\x08'"""
    client_address = client_obj.ip_port

    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved Key Registration Request [partial implementation]")
    request = packet.CMRequest
    request_data = request.data
    packet_size = len(request_data)
    try:
        header = int.from_bytes(request_data[:2], 'little')
        if header:
            cmserver_obj.log.debug("ERROR Invalid purchase request header", request_data.decode('utf-8', errors = 'ignore'), packet_size - 16)
            return  # Run away because we can't handle headers, apparently

        # Grab the subject right after the alleged "header"
        subject = request_data[2:].split(b'\x00', 1)[0].decode('utf-8')

        next_index = len(subject) + 3  # Plus one for the null byte you forgot about
        types = []
        fields = []
        values = []
        ind = 0

        # Parse until we hit an 0x8, because magic numbers are "cool"
        while request_data[next_index] != 0x8:
            tmp = ""
            field_type = request_data[next_index]
            next_index += 1
            next_field, next_index = read_string(request_data, next_index)

            # You've got types, but Python's not C++, so handle with care
            if field_type == 1:
                value, next_index = read_string(request_data, next_index)
            elif field_type == 2:
                value = int.from_bytes(request_data[next_index:next_index + 4], 'little')
                next_index += 4
            elif field_type == 7:
                value = int.from_bytes(request_data[next_index:next_index + 8], 'little')
                next_index += 8
            else:
                cmserver_obj.log.debug("ERROR Invalid purchase request field type", request_data.decode('utf-8', errors = 'ignore'), packet_size - 16)
                return  # Because flexible error handling is for the weak

            types.append(field_type)
            fields.append(next_field)
            values.append(value)
            ind += 1

        # Check the footer, because your protocol design is apparently from the 90s
        end = int.from_bytes(request_data[next_index:next_index + 2], 'little')
        if end != 0x0808:
            cmserver_obj.log.debug("ERROR Invalid purchase request footer", request_data.decode('utf-8', errors = 'ignore'), packet_size - 16)
            return -1
    except Exception as e:
        cmserver_obj.log.error(f"register key: {e}")
        pass

    return [build_PurchaseResponse(request)]


def handle_GetFinalPrice(cmserver_obj, packet: CMPacket, client_obj: Client):
    client_address = client_obj.ip_port

    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved Get Final Price Request")
    request = packet.CMRequest

    fixed_transactionID = fix_transactionID(request)

    return build_GetFinalPriceResponse(client_obj, fixed_transactionID)


def fix_transactionID(request):
    transactionID = struct.unpack("<Q", request.data)[0]
    # Split into low and high parts (swapped)
    new_low_part = (transactionID >> 32) & 0xFFFFFFFF
    new_high_part = transactionID & 0xFFFFFFFF
    # Swap the parts back to reconstruct the original transaction ID
    fixed_transactionID = (new_high_part << 32) | new_low_part
    return fixed_transactionID


def handle_CancelLicense(cmserver_obj, packet: CMPacket, client_obj: Client):
    """struct MsgClientCancelLicense_t
    {
      uint32 m_unPackageID;
      int m_nReason;
    };
    b'\x00\x00\x00\x00 \x00\x00\x00\x00'
    """
    client_address = client_obj.ip_port

    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Requested To Cancel License [partial implementation]")
    request = packet.CMRequest
    eResult = EResult.OK
    #packageID, reason = struct.unpack('<II', request.data)

    fixed_transactionID = fix_transactionID(request)

    client_obj.cancel_transaction(fixed_transactionID)
    return build_General_response(client_obj, eResult)


def handle_CancelPurchase(cmserver_obj, packet: CMPacket, client_obj: Client):
    client_address = client_obj.ip_port

    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Requested To Cancel Purchase [partial implementation]")
    request = packet.CMRequest
    eResult = EResult.OK
    fixed_transactionID = fix_transactionID(request)
    client_obj.cancel_transaction(fixed_transactionID)
    return build_General_response(client_obj, eResult)

def handle_GetPurchaseReceipts(cmserver_obj, packet: CMPacket, client_obj: Client):
    client_address = client_obj.ip_port

    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved Get Purchase Receipts [partial implementation]")
    request = packet.CMRequest
    unAcknowledgedOnly = struct.unpack("B", request.data)[0]

    # TODO grab all receipts from database!

    return -1

def handle_CompletePurchase(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    packetid: 733
    b'\x00\x00\x00\x00\x08\x00\x00\x00'
    """
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved Complete Purchase Request [NO implementation]")
    request = packet.CMRequest
    fixed_transactionID = fix_transactionID(request)

    # TODO add all the sql magic for completing a transaction
    return build_PurchaseResponse(client_obj)


def handle_AckPurchaseReceipt(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    struct MsgClientAckPurchaseReceipt_t
    {
      GID_t m_TransID;
    };
    """
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved Complete Purchase Request [NO implementation]")
    request = packet.CMRequest
    fixed_transactionID = fix_transactionID(request)
    client_obj.set_receipt_acknowledged(fixed_transactionID)
    return -1 # This does not give a response... i dont think, anyway..