import mariadb
import struct
import random
import time
from io import BytesIO

import globalvars
from steam3.Types.MessageObject.KeyRegistration import KeyRegistration
from steam3.ClientManager.client_permissions import PERM_PURCHASE
from steam3.utilities import fix_transactionID
from utilities.database.base_dbdriver import Steam3TransactionAddressRecord, Steam3TransactionsRecord
from steam3 import utilities
from steam3.ClientManager.client import Client
from steam3.Responses.general_responses import build_General_response
from steam3.Responses.guestpass_responses import build_GetGiftTargetListResponse
from steam3.Responses.purchase_responses import build_GetFinalPriceResponse, build_GetLegacyGameKeyResponse, build_GetVIPStatusResponse, build_InitPurchaseResponse, build_PurchaseResponse, build_LookupKeyResponse, build_GetPurchaseReceiptsResponse
from steam3.Types.MessageObject import MessageObject
from steam3.Types.keyvaluesystem import KVS_TYPE_STRING, KeyValuesSystem, registry_key_to_dict
from steam3.Types.steam_types import EPaymentMethod, EPurchaseResultDetail, EResult, EPurchaseStatus, ECurrencyCode
from steam3.cm_packet_utils import CMPacket
from steam3.messages.MSGClientInitPurchase import MSGClientInitPurchase
from steam3.messages.MSGClientGetFinalPrice import MSGClientGetFinalPrice
from steam3.messages.MSGClientCompletePurchase import MSGClientCompletePurchase
from steam3.messages.MSGClientGetPurchaseReceipts import MSGClientGetPurchaseReceipts
from steam3.messages.responses.MSGClientGetPurchaseReceiptsResponse import MSGClientGetPurchaseReceiptsResponse
from steam3.messages.MSGClientGetLicenses import MSGClientGetLicenses
from steam3.messages.responses.MSGClientLicenseList import MSGClientLicenseList
from steam3.messages.MSGClientPurchaseWithMachineID import MSGClientPurchaseWithMachineID
from steam3.messages.MSGClientCancelPurchase import MSGClientCancelPurchase
from steam3.messages.MSGClientCancelLicense import MSGClientCancelLicense
from steam3.messages.MSGClientAckPurchaseReceipt import MSGClientAckPurchaseReceipt
from steam3.messages.MSGClientLookupKey import MSGClientLookupKey
from steam3.messages.MSGClientGetVIPStatus import MSGClientGetVIPStatus

from config import get_config
config = get_config()


def _is_guestpass_disabled():
    """Check if the guestpass system is disabled in config."""
    cfg = get_config()
    return cfg.get('disable_guestpass_system', 'false').lower() == 'true'


def _lookup_subscription_by_game_code(game_code: int, territory_code: int = None):
    """
    Helper function to look up a subscription by game code in CDR.
    Handles both ContentDescriptionRecord objects and plain dict CDR formats.

    Args:
        game_code: The game code from the decoded CD key
        territory_code: Optional territory code to match

    Returns:
        CDRSubscriptionRecord if found, None otherwise
    """
    from utilities.contentdescriptionrecord import CDRSubscriptionRecord

    if not globalvars.CDR_DICTIONARY:
        return None

    # First check CDR_obj which is the parsed ContentDescriptionRecord object
    # CDR_DICTIONARY is the raw dict, CDR_obj is the parsed object with methods
    if hasattr(globalvars, 'CDR_obj') and globalvars.CDR_obj is not None:
        if hasattr(globalvars.CDR_obj, 'get_subscription_by_game_code'):
            return globalvars.CDR_obj.get_subscription_by_game_code(game_code, territory_code)

    # CDR_DICTIONARY is a plain dict - manually search through subscriptions
    if isinstance(globalvars.CDR_DICTIONARY, dict):
        # Subscriptions are stored under key b"\x02\x00\x00\x00"
        subs_dict = globalvars.CDR_DICTIONARY.get(b"\x02\x00\x00\x00", {})

        candidates = []
        for sub_key, sub_data in subs_dict.items():
            # Parse subscription ID from key
            if isinstance(sub_key, bytes) and len(sub_key) == 4:
                sub_id = int.from_bytes(sub_key, byteorder='little')
            else:
                continue

            # Create CDRSubscriptionRecord from raw dict data
            sub = CDRSubscriptionRecord(sub_id)
            sub.parse(sub_data)

            # Get the subscription's GameCode
            sub_game_code = sub.GameCode
            if sub_game_code is None:
                continue

            # Convert bytes to int if needed
            if isinstance(sub_game_code, bytes):
                try:
                    sub_game_code = int.from_bytes(sub_game_code, byteorder='little')
                except Exception:
                    continue
            else:
                try:
                    sub_game_code = int(sub_game_code)
                except Exception:
                    continue

            # Check if game code matches
            if sub_game_code != game_code:
                continue

            # If territory_code is specified, check it too
            if territory_code is not None:
                sub_territory = sub.TerritoryCode
                if sub_territory is not None:
                    if isinstance(sub_territory, bytes):
                        try:
                            sub_territory = int.from_bytes(sub_territory, byteorder='little')
                        except Exception:
                            sub_territory = None
                    else:
                        try:
                            sub_territory = int(sub_territory)
                        except Exception:
                            sub_territory = None

                    # If subscription has a territory code, it must match
                    if sub_territory is not None and sub_territory != 0:
                        if sub_territory != territory_code:
                            continue

            candidates.append(sub)

        if not candidates:
            return None

        # Prefer non-disabled subscriptions
        for sub in candidates:
            is_disabled = sub.IsDisabled
            if is_disabled is not None:
                if isinstance(is_disabled, bytes):
                    is_disabled = int.from_bytes(is_disabled, byteorder='little')
                if not is_disabled:
                    return sub

        # Return first candidate if all are disabledv
        return candidates[0]

    return None

def handle_GetGiftTargetList(cmserver_obj, packet: CMPacket, client_obj: Client):
    client_address = client_obj.ip_port
    cmserver_obj.log.info(
        f"({client_address[0]}:{client_address[1]}): Recieved Gift Target List Request"
    )

    # If guestpass system is disabled, return empty list
    if _is_guestpass_disabled():
        cmserver_obj.log.debug("Guestpass system is disabled, returning empty gift target list")
        return -1

    request = packet.CMRequest

    packageID = struct.unpack("<I", request.data)[0]

    friends_list = client_obj.grab_potential_gift_targets(packageID)

    build_GetGiftTargetListResponse(cmserver_obj, client_obj, friends_list, packageID)

    return -1


def handle_GetVIPStatus(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle VIP status request for Click and Buy payment method.

    packetid: 837
    struct MsgClientGetVIPStatus_t {
        EPaymentMethod m_ePaymentMethod;  // 4 bytes
    };

    Response: MsgVIPStatusResponse_t (9 bytes)
    - EResult m_EResult
    - EPaymentMethod m_ePaymentMethod
    - bool m_bVipUser
    """
    client_address = client_obj.ip_port
    request = packet.CMRequest

    # Parse the request to get the payment method
    msg = MSGClientGetVIPStatus(client_obj, request.data)

    cmserver_obj.log.info(
        f"({client_address[0]}:{client_address[1]}): Received Get VIP Status request "
        f"for payment method: {msg.payment_method}"
    )

    # For Click and Buy (EPaymentMethod.ClickAndBuy = 32), return VIP status
    # The client only processes the response if payment_method == ClickAndBuy

    # TODO technically i believe that click and buy needs to be setup on the steampowered website before VIP would be true, otherwise it would return a dialog saying you dont have it setup for click and buy
    is_vip = True  # Server-side: always grant VIP status for Click and Buy

    return [build_GetVIPStatusResponse(client_obj, payment_method=msg.payment_method, is_vip=is_vip)]


def handle_InitPurchase(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Process an old Steam3 purchase packet using the new CDR parser, tax calculation,
    and permission/PO box checks.

    Steps:
      1. Parse the packet using KeyValuesSystem.
      2. Retrieve the subscription record from CDR.
      3. Check user permissions via client_obj.get_permissions().
      4. Check shipping address for PO boxes.
      5. Verify the subscription is not already owned.
      6. Compute base cost, discounts, and taxes.
      7. Process payment and address information.
    """
    # Default purchase result.
    purchase_result = EPurchaseResultDetail.NoDetail
    random_paypal_token = None

    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received Init Purchase Request")
    request = packet.CMRequest

    try:
        # Parse the request using the message class
        msg = MSGClientInitPurchase(client_obj, request.data)
        
        product_count = msg.package_count
        payment_method = msg.payment_method
        transactionID = msg.payment_id
        include_storepaymentinfo = msg.store_payment_info
        subscriptionID = msg.package_id
        
        # Parse MessageObject data
        message_objects = msg.get_message_objects()
        addressinfo_dict = {}
        shippinginfo_dict = {}
        giftinfo_dict = {}
        cbaccountinfo_dict = {}

        for obj in message_objects:
            # Detect CBAccountInfoMsg (Click and Buy) by presence of AccountNum field
            if "AccountNum" in obj:
                cbaccountinfo_dict.update(obj)
            elif "addressinfo" in obj or any(k in obj for k in ["name", "Address1", "City", "CountryCode"]):
                addressinfo_dict.update(obj)
            elif "shippinginfo" in obj or "IsGift" not in obj:
                if addressinfo_dict and obj != addressinfo_dict:  # Different from billing address
                    shippinginfo_dict.update(obj)
            elif "IsGift" in obj or "GifteeEmail" in obj:
                giftinfo_dict.update(obj)
        
        gift_entryID = 0
        address_entryID = 0
        shippingaddress_entryID = None
        payment_entryID = 0
        discountedamount = 0
        shippingamount = 0
        
    except Exception as e:
        cmserver_obj.log.error(f"({client_address[0]}:{client_address[1]}): Failed to parse InitPurchase: {e}")
        purchase_result = EPurchaseResultDetail.InvalidData
        return [build_InitPurchaseResponse(client_obj, EResult.Fail, EPaymentMethod.CreditCard, 0, returned_result=purchase_result)]

    # 2. Retrieve the subscription.
    subscriptionvar = None
    if globalvars.CDR_DICTIONARY is not None:
        if hasattr(globalvars.CDR_DICTIONARY, 'get_subscription'):
            # CDR_DICTIONARY is a ContentDescriptionRecord object
            subscriptionvar = globalvars.CDR_DICTIONARY.get_subscription(subscriptionID)
        elif isinstance(globalvars.CDR_DICTIONARY, dict):
            # CDR_DICTIONARY is a plain dict, look up subscription by ID
            subs = globalvars.CDR_DICTIONARY.get(b"\x02\x00\x00\x00", {})
            sub_key = struct.pack('<I', subscriptionID)
            if sub_key in subs:
                # Create CDRSubscriptionRecord from raw dict data
                from utilities.contentdescriptionrecord import CDRSubscriptionRecord
                subscriptionvar = CDRSubscriptionRecord(subscriptionID)
                subscriptionvar.parse(subs[sub_key])
    
    if subscriptionvar is None:
        cmserver_obj.log.error(f"({client_address[0]}:{client_address[1]}): Subscription {subscriptionID} not found in CDR")
        purchase_result = EPurchaseResultDetail.InvalidPackage
        return [build_InitPurchaseResponse(client_obj, EResult.Fail,payment_method, transactionID, returned_result=purchase_result)]

    # 2.1 Check client permissions.
    if not (client_obj.get_permissions() & PERM_PURCHASE):
        purchase_result = EPurchaseResultDetail.ContactSupport
        return [build_InitPurchaseResponse(client_obj, EResult.Fail,payment_method, transactionID, returned_result=purchase_result)]

    # 3. Check for PO box usage in shipping address (if shipping info is present).
    if shippinginfo_dict:
        # A simple case-insensitive check for "PO Box" or "P.O. Box"
        addr_line = shippinginfo_dict.get('Address1', '').upper()
        if "PO BOX" in addr_line or "P.O. BOX" in addr_line:
            purchase_result = EPurchaseResultDetail.CannotShipToPOBox
            return [build_InitPurchaseResponse(client_obj, EResult.Fail,payment_method, transactionID, returned_result=purchase_result)]

    # 3.2 Check if subscription is already owned (database query for current state).
    if client_obj.owns_subscription(subscriptionID):
        cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): User already owns subscription {subscriptionID}")
        purchase_result = EPurchaseResultDetail.AlreadyPurchased
        return [build_InitPurchaseResponse(client_obj, EResult.Fail,payment_method, transactionID, returned_result=purchase_result)]

    # 4. Use the base_cost property.
    base_cost = subscriptionvar.base_cost
    if base_cost is None:
        cmserver_obj.log.error(f"({client_address[0]}:{client_address[1]}): Subscription {subscriptionID} has no cost information")
        purchase_result = EPurchaseResultDetail.InvalidPackage
        return [build_InitPurchaseResponse(client_obj, EResult.Fail, payment_method, transactionID, returned_result=purchase_result)]

    # 5. Determine if the subscription is shippable.
    # FIXME is it better to just rely on a shipping price/amount rather than the 'shipped' flag?
    if subscriptionvar.is_shipped:
        domestic_shipping = subscriptionvar.domestic_shipping_cost
        shippingamount = domestic_shipping if domestic_shipping is not None else 0

    # 6. Process discount qualifiers.
    if subscriptionvar.has_discounts:
        discount_found = False
        for discount in subscriptionvar.DiscountsRecord.values():
            # If there are no discount qualifiers, we can use this discount unconditionally.
            if not discount.DiscountQualifiers:
                discountedamount = (int.from_bytes(discount.DiscountInCents, byteorder='little')
                                    if isinstance(discount.DiscountInCents, bytes)
                                    else int(discount.DiscountInCents))
                discount_found = True
                break
            else:
                for dq in discount.DiscountQualifiers.values():
                    qualifier_sub_id = (int.from_bytes(dq.SubscriptionId, byteorder='little')
                                        if isinstance(dq.SubscriptionId, bytes)
                                        else int(dq.SubscriptionId))
                    # Use database ownership check for discount qualifiers
                    if client_obj.owns_subscription(qualifier_sub_id):
                        discountedamount = (int.from_bytes(discount.DiscountInCents, byteorder='little')
                                            if isinstance(discount.DiscountInCents, bytes)
                                            else int(discount.DiscountInCents))
                        discount_found = True
                        break
            if discount_found:
                break

    # 7. Calculate taxes.
    tax_rate = client_obj.get_tax_rate_for_address(addressinfo_dict)
    taxes = int(round(base_cost * tax_rate))

    # 8. Get guest pass information using the preloaded global subscription_pass_list.
    # Skip if guestpass system is disabled
    if _is_guestpass_disabled():
        accompanying_guestpasses = {}
    elif subscriptionID in globalvars.subscription_pass_list:
        accompanying_guestpasses = globalvars.subscription_pass_list[subscriptionID]
    else:
        accompanying_guestpasses = {}

    # 9. Process payment details.
    if payment_method == EPaymentMethod.CreditCard:
        # Get the primary (payment) address once.
        address_entryID = client_obj.get_addressEntryID(
            addressinfo_dict.get('name'),
            addressinfo_dict.get('Address1'),
            addressinfo_dict.get('Address2'),
            addressinfo_dict.get('City'),
            addressinfo_dict.get('PostCode'),
            addressinfo_dict.get('state'),
            addressinfo_dict.get('CountryCode'),
            addressinfo_dict.get('Phone')
        )

        if subscriptionvar.is_shipped:
            # Default shipping address equals the primary address.
            shippingaddress_entryID = address_entryID

            cmserver_obj.log.debug("Item is shippable")
            domestic_shipping = subscriptionvar.domestic_shipping_cost
            shippingamount = domestic_shipping if domestic_shipping is not None else 0
            if shippinginfo_dict:
                # Compare shipping and payment address dictionaries.
                if not utilities.compare_dictionaries(addressinfo_dict, shippinginfo_dict):
                    # If they differ, update the shipping address entry.
                    shippingaddress_entryID = client_obj.get_addressEntryID(
                        shippinginfo_dict.get('name'),
                        shippinginfo_dict.get('Address1'),
                        shippinginfo_dict.get('Address2'),
                        shippinginfo_dict.get('City'),
                        shippinginfo_dict.get('PostCode'),
                        shippinginfo_dict.get('state'),
                        shippinginfo_dict.get('CountryCode'),
                        shippinginfo_dict.get('Phone')
                    )

        payment_entryID = client_obj.get_or_set_paymentcardinfo(
            addressinfo_dict.get('CreditCardType'),
            addressinfo_dict.get('CardNumber'),
            addressinfo_dict.get('CardHolderName'),
            addressinfo_dict.get('CardExpYear'),
            addressinfo_dict.get('CardExpMonth'),
            addressinfo_dict.get('CardCVV2')
        )
    elif payment_method == EPaymentMethod.PayPal:
        # TODO Generate Paypal Token ID for cloned website
        random_paypal_token = utilities.generate_token(20)
        payment_entryID = client_obj.add_external_transactioninfo(subscriptionID,
                                                                   EPaymentMethod.PayPal,
                                                                   random_paypal_token)
    elif payment_method == EPaymentMethod.ClickAndBuy:
        # Click and Buy payment method handling
        # CBAccountInfoMsg MessageObject contains: AccountNum (int64), State (string), CountryCode (string)
        # See CUser::InitClickAndBuyPurchase in decompiled client code
        if not cbaccountinfo_dict:
            cmserver_obj.log.error(f"({client_address[0]}:{client_address[1]}): Click and Buy payment missing CBAccountInfo")
            purchase_result = EPurchaseResultDetail.InvalidData
            return [build_InitPurchaseResponse(client_obj, EResult.Fail, payment_method, transactionID, returned_result=purchase_result)]

        cb_account_num = cbaccountinfo_dict.get('AccountNum', 0)
        cb_state = cbaccountinfo_dict.get('State', '')
        cb_country_code = cbaccountinfo_dict.get('CountryCode', '')

        cmserver_obj.log.info(
            f"({client_address[0]}:{client_address[1]}): Click and Buy purchase - "
            f"AccountNum={cb_account_num}, State={cb_state}, Country={cb_country_code}"
        )

        # Store Click and Buy account info as external transaction
        # Token format: account_num|state|country_code for reference
        cb_token = f"{cb_account_num}|{cb_state}|{cb_country_code}"
        payment_entryID = client_obj.add_external_transactioninfo(subscriptionID,
                                                                   EPaymentMethod.ClickAndBuy,
                                                                   cb_token)
    else:
        cmserver_obj.log.error(f"({client_address[0]}:{client_address[1]}): Invalid or Unsupported payment method {payment_method}")

    gift_info = None
    if giftinfo_dict.get('IsGift', 0) == 1:
        gift_info = {
             "GifterAccountID": client_obj.steamID,
             "GifteeEmail": giftinfo_dict.get('GifteeEmail'),
             "GifteeAccountID": giftinfo_dict.get('GifteeAccountID'),
             "GiftMessage": giftinfo_dict.get('GiftMessage'),
             "GifteeName": giftinfo_dict.get('GifteeName'),
             "Sentiment": giftinfo_dict.get('Sentiment'),
             "Signature": giftinfo_dict.get('Signature')
        }

    if (shippingaddress_entryID is not None) and payment_method not in (EPaymentMethod.PayPal, EPaymentMethod.ClickAndBuy):
        shippingaddress_entryID = address_entryID
        cmserver_obj.log.debug("Shipped item: shipping address set to address entry ID")

    if shippingaddress_entryID is not None and shippingamount == 0:
        cmserver_obj.log.debug("Shipped item with 0 shipping cost")
        shippingaddress_entryID = None

    transactionID = client_obj.add_new_steam3_transaction(
        payment_method,
        payment_entryID,
        subscriptionID,
        address_entryID,
        base_cost,
        discountedamount,
        taxes,
        shippingamount,
        shippingaddress_entryID,
        accompanying_guestpasses,
        gift_info  # Pass gift_info dictionary (or None if not a gift)
    )

    return [build_InitPurchaseResponse(client_obj, EResult.OK, payment_method, transactionID, purchase_result, random_paypal_token)]

#paypal bought as gift (from client):
#response might be: InitPayPalPurchaseResponse
#packetid: 711
#b'\x01\x00\x00\x00\x04\x00\x00\x00\xff\xff\xff\xff\xff\xff\xff\xff\x00\xd5\x01\x00\x00\x00MessageObject\x00\x02IsGift\x00\x01\x00\x00\x00\x01GifteeEmail\x00dsafas@fdfgs.gfhfg\x00\x07GifteeAccountID\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01GiftMessage\x00I hope you enjoy these games!\x00\x01GifteeName\x00dsafas\x00\x01Sentiment\x00ntest\x00\x01Signature\x00test\x00\x08\x08'

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

    result: 1 = OK, 2 = FAIL
    """
    client_address = client_obj.ip_port
    request = packet.CMRequest
    request_data = request.data
    packet_size = len(request_data)
    appid = struct.unpack("<I", request_data[:4])[0]

    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received Client Get Legacy Game Key for appid: {appid}")
    
    try:
        conn = mariadb.connect(
            user=config["database_username"],
            password=config["database_password"],
            host=config["database_host"],
            port=int(config["database_port"]),
            database=config["database"]
        )
        cur2 = conn.cursor()
        cur2.execute("SELECT * FROM LegacyGameKeys WHERE appid = %s", (appid,))
        data = cur2.fetchall()
        conn.close()
        
        if len(data) > 0:
            key_list = []
            for keys in data:
                key_list.append(keys[1])
            cdkey = key_list[random.randint(0, len(key_list) - 1)].encode()
            result = 1
        else:
            cdkey = b""
            result = 2
    except mariadb.Error as e:
        cmserver_obj.log.error(f"Error connecting to MariaDB Platform: {e}")
        cdkey = b""
        result = 2
    
    #cdkey = b'37A7R-AL9CF-WR3WT-Y4L4F-FLR33'
    return [build_GetLegacyGameKeyResponse(request, appid, cdkey, result)]


def handle_RegisterKey(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle a Key Registration/Activation Request.
    This activates a product key for the user account.

    Based on decompiled CClientJobPurchaseWithActivationCode:
    - Client sends k_EMsgClientRegisterKey with ActivationCodeInfo MessageObject
    - Server should respond with k_EMsgClientPurchaseResponse containing PurchaseReceipt
    - Early clients expect specific transaction flow with purchase receipts

    Flow:
    1. Decode the CD key to extract game_code and territory_code
    2. Look up the matching subscription in CDR by game_code
    3. Create a license for that subscription
    4. Return PurchaseReceipt to client
    """
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received Key Registration Request")

    request = packet.CMRequest
    request_data = request.data

    # Parse the message data - early clients send ActivationCodeInfo as MessageObject
    try:
        # Check for MessageObject format (2008 clients use this)
        if len(request_data) >= 2 and int.from_bytes(request_data[:2], 'little') == 0:
            # Extract payload after header
            payload = request_data[2:]

            # Parse using MessageObject to get ActivationCodeInfo
            from steam3.Types.MessageObject import MessageObject
            msg_obj = MessageObject(payload)
            activation_code = msg_obj.getValue("Key", "")

            if not activation_code:
                cmserver_obj.log.error("No Key field found in MessageObject")
                return [build_PurchaseResponse(client_obj, transactionID=0, errorcode=EResult.InvalidParam)]
        else:
            # Fallback: try KeyRegistration parsing for newer clients
            kr = KeyRegistration(raw_data=request_data)
            activation_code = kr.key

    except Exception as e:
        cmserver_obj.log.error(f"Error parsing key registration request: {e}")
        return [build_PurchaseResponse(client_obj, transactionID=0, errorcode=EResult.InvalidParam)]

    cmserver_obj.log.info(f"Activating key: {activation_code}")

    # Decode the CD key to extract game code and territory information
    from steam3.Types.CDKeyDecoder import decode_cdkey
    key_info = decode_cdkey(activation_code)

    if not key_info:
        cmserver_obj.log.warning(f"Could not decode key format: {activation_code}")
        return [build_PurchaseResponse(
            client_obj,
            transactionID=0,
            errorcode=EResult.Fail,
            purchase_detail=EPurchaseResultDetail.BadActivationCode
        )]

    cmserver_obj.log.info(
        f"Decoded key: game_code={key_info.game_code}, "
        f"territory={key_info.territory_code}, "
        f"serial={key_info.serial_number}, "
        f"valid_checksum={key_info.is_valid}"
    )

    if not key_info.is_valid:
        cmserver_obj.log.warning(f"Key {activation_code} has invalid checksum")
        return [build_PurchaseResponse(
            client_obj,
            transactionID=0,
            errorcode=EResult.Fail,
            purchase_detail=EPurchaseResultDetail.BadActivationCode
        )]

    # Look up the subscription in CDR by game code and territory code
    try:
        if not globalvars.CDR_DICTIONARY:
            cmserver_obj.log.error("CDR_DICTIONARY not loaded - cannot look up subscription by game code")
            return [build_PurchaseResponse(
                client_obj,
                transactionID=0,
                errorcode=EResult.Fail,
                purchase_detail=EPurchaseResultDetail.ContactSupport
            )]

        subscription = None

        if hasattr(globalvars.CDR_DICTIONARY, 'get_subscription_by_game_code'):
            # CDR_DICTIONARY is a ContentDescriptionRecord object
            # First try to find subscription with both game_code and territory_code
            subscription = globalvars.CDR_DICTIONARY.get_subscription_by_game_code(
                key_info.game_code,
                key_info.territory_code
            )
            # If not found with territory, try just game_code
            if subscription is None:
                subscription = globalvars.CDR_DICTIONARY.get_subscription_by_game_code(
                    key_info.game_code,
                    None
                )
        elif isinstance(globalvars.CDR_DICTIONARY, dict):
            # CDR_DICTIONARY is a plain dict, iterate through subscriptions to find by game code
            from utilities.contentdescriptionrecord import CDRSubscriptionRecord
            subs = globalvars.CDR_DICTIONARY.get(b"\x02\x00\x00\x00", {})

            # Search for matching subscription
            for sub_key, sub_data in subs.items():
                temp_sub = CDRSubscriptionRecord(int.from_bytes(sub_key, 'little'))
                temp_sub.parse(sub_data)

                # Get game code from subscription
                sub_game_code = temp_sub.GameCode
                if isinstance(sub_game_code, bytes):
                    sub_game_code = int.from_bytes(sub_game_code, 'little')
                elif sub_game_code is not None:
                    sub_game_code = int(sub_game_code)

                if sub_game_code is None or sub_game_code != key_info.game_code:
                    continue

                # Check territory code if provided
                if key_info.territory_code is not None:
                    sub_territory = temp_sub.TerritoryCode
                    if isinstance(sub_territory, bytes):
                        sub_territory = int.from_bytes(sub_territory, 'little')
                    elif sub_territory is not None:
                        sub_territory = int(sub_territory)

                    if sub_territory is not None and sub_territory == key_info.territory_code:
                        subscription = temp_sub
                        break
                else:
                    # No territory filter, accept first match
                    subscription = temp_sub
                    break

            # If not found with territory, try without territory filter
            if subscription is None and key_info.territory_code is not None:
                for sub_key, sub_data in subs.items():
                    temp_sub = CDRSubscriptionRecord(int.from_bytes(sub_key, 'little'))
                    temp_sub.parse(sub_data)

                    sub_game_code = temp_sub.GameCode
                    if isinstance(sub_game_code, bytes):
                        sub_game_code = int.from_bytes(sub_game_code, 'little')
                    elif sub_game_code is not None:
                        sub_game_code = int(sub_game_code)

                    if sub_game_code is not None and sub_game_code == key_info.game_code:
                        subscription = temp_sub
                        break

        if subscription is None:
            cmserver_obj.log.warning(
                f"No subscription found in CDR for game_code={key_info.game_code}, "
                f"territory={key_info.territory_code}"
            )
            return [build_PurchaseResponse(
                client_obj,
                transactionID=0,
                errorcode=EResult.Fail,
                purchase_detail=EPurchaseResultDetail.BadActivationCode
            )]

        # Get subscription ID
        sub_id = subscription.SubscriptionId
        if isinstance(sub_id, bytes):
            package_id = int.from_bytes(sub_id, byteorder='little')
        else:
            package_id = int(sub_id)

        # Get subscription name for logging
        sub_name = subscription.Name
        if isinstance(sub_name, bytes):
            sub_name = sub_name.rstrip(b'\x00').decode('utf-8', errors='ignore')

        cmserver_obj.log.info(
            f"Found subscription: ID={package_id}, Name='{sub_name}' "
            f"for game_code={key_info.game_code}"
        )

    except Exception as e:
        cmserver_obj.log.error(f"Error looking up subscription in CDR: {e}")
        return [build_PurchaseResponse(
            client_obj,
            transactionID=0,
            errorcode=EResult.Fail,
            purchase_detail=EPurchaseResultDetail.ContactSupport
        )]

    # Create the license for this subscription
    try:
        import steam3
        from steam3.Responses.auth_responses import build_ClientLicenseList_response
        from datetime import datetime

        account_id = int(client_obj.accountID)

        # Check if user already owns this subscription
        if steam3.database.user_has_subscription(account_id, package_id):
            cmserver_obj.log.warning(
                f"User {account_id} already owns subscription {package_id}"
            )
            return [build_PurchaseResponse(
                client_obj,
                transactionID=0,
                errorcode=EResult.Fail,
                purchase_detail=EPurchaseResultDetail.AlreadyPurchased
            )]

        # Create the license record for this CD key activation
        result = steam3.database.create_cdkey_license(
            account_id=account_id,
            package_id=package_id,
            cd_key=activation_code,
            game_code=key_info.game_code,
            territory_code=key_info.territory_code,
            serial_number=key_info.serial_number
        )

        if result != EResult.OK:
            cmserver_obj.log.error(f"Failed to create license: {result}")
            return [build_PurchaseResponse(
                client_obj,
                transactionID=0,
                errorcode=result,
                purchase_detail=EPurchaseResultDetail.ContactSupport
            )]

        cmserver_obj.log.info(
            f"Successfully activated key for user {account_id}, "
            f"package={package_id} ({sub_name})"
        )

        # Create a transaction record for the CD key activation
        # This is needed so the client can acknowledge the purchase receipt
        transaction_id = client_obj.add_new_steam3_transaction(
            transaction_type=EPaymentMethod.ActivationCode,
            transaction_entry_id=0,  # No payment entry for CD key
            package_id=package_id,
            address_entry_id=None,
            base_cost=0,  # CD key is free (already paid for at retail)
            discounts=0,
            tax_cost=0,
            shipping_cost=0,
            shipping_entry_id=None,
            guest_passes_included=None,
            gift_info=None
        )

        if transaction_id is None:
            cmserver_obj.log.error(f"Failed to create transaction record for CD key activation")
            # Still return success since the license was created, but use 0 as fallback
            transaction_id = 0

        cmserver_obj.log.info(f"Created transaction {transaction_id} for CD key activation")

        # Create transaction details for the purchase receipt
        transaction_time = datetime.now()
        transaction_details = {
            'app_id': package_id,
            'package_id': package_id,
            'activation_method': 'cdkey',
            'cd_key': activation_code,
            'transaction_time': transaction_time,
            'game_code': key_info.game_code,
            'territory_code': key_info.territory_code,
            'serial_number': key_info.serial_number,
            'transaction_id': transaction_id,
        }

        # Build responses:
        # 1. PurchaseResponse with PurchaseReceipt (client adds to VecPurchaseReceipts)
        # 2. Updated license list (so client knows about the new license)
        responses = [
            build_PurchaseResponse(
                client_obj,
                transactionID=transaction_id,
                errorcode=EResult.OK,
                transaction_details=transaction_details,
                purchase_detail=EPurchaseResultDetail.NoDetail
            ),
            build_ClientLicenseList_response(client_obj)
        ]

        return responses

    except Exception as e:
        cmserver_obj.log.error(f"Database error during key activation: {e}")
        import traceback
        traceback.print_exc()
        return [build_PurchaseResponse(
            client_obj,
            transactionID=0,
            errorcode=EResult.Fail,
            purchase_detail=EPurchaseResultDetail.ContactSupport
        )]


def handle_GetFinalPrice(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Process a GetFinalPrice request.
    Steps:
      1. Parse the packet using the message class.
      2. Retrieve and validate the transaction.
      3. Retrieve the transaction record via client_obj.get_transaction.
      4. Extract pricing details.
      5. If shipping is included, use MessageObject to serialize shipping address data.
      6. Finally, call build_GetFinalPriceResponse with all the data.
    """
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received Get Final Price Request")
    request = packet.CMRequest

    try:
        # Parse the request using the message class
        msg = MSGClientGetFinalPrice(client_obj, request.data)
        fixed_transactionID = msg.transaction_id
    except Exception as e:
        cmserver_obj.log.error(f"({client_address[0]}:{client_address[1]}): Failed to parse GetFinalPrice: {e}")
        return [build_GetFinalPriceResponse(client_obj, EResult.Fail, 0)]

    # Validate the transaction using the new client method.
    dbresult = client_obj.validate_transaction(fixed_transactionID)
    if dbresult in (1, 2, 3):
        return [build_GetFinalPriceResponse(client_obj, EResult.Fail, fixed_transactionID)]

    # Retrieve the transaction record.
    transaction = client_obj.get_transaction(fixed_transactionID)
    if not transaction:
        return [build_GetFinalPriceResponse(client_obj, EResult.Fail, fixed_transactionID)]
    transaction_entry: Steam3TransactionsRecord = transaction[0]

    # Extract pricing details.
    base_cost_cents = transaction_entry.BaseCostInCents
    discounts_cents = transaction_entry.DiscountsInCents
    tax_cost_cents = transaction_entry.TaxCostInCents
    shipping_cost_cents = transaction_entry.ShippingCostInCents
    include_shipping = bool(transaction_entry.ShippingEntryID)

    shipping_data = b""
    if include_shipping:
        # Retrieve shipping address info from transaction details tuple
        # Format: (transaction, cc_entry, external_entry, address, shipping)
        shipping_entry: Steam3TransactionAddressRecord = transaction[4]

        if shipping_entry:
            # Use MessageObject to build the shipping address message.
            ship_obj = MessageObject()
            # Split name into first and last name
            name_parts = (shipping_entry.Name or "").split()
            ship_obj.setValue('FirstName', name_parts[0] if name_parts else "", KVS_TYPE_STRING)
            ship_obj.setValue('LastName', name_parts[-1] if len(name_parts) > 1 else "", KVS_TYPE_STRING)
            ship_obj.setValue('Address1', shipping_entry.Address1 or "", KVS_TYPE_STRING)
            ship_obj.setValue('Address2', shipping_entry.Address2 or "", KVS_TYPE_STRING)
            ship_obj.setValue('City', shipping_entry.City or "", KVS_TYPE_STRING)
            ship_obj.setValue('PostCode', shipping_entry.PostCode or "", KVS_TYPE_STRING)
            ship_obj.setValue('State', shipping_entry.State or "", KVS_TYPE_STRING)
            ship_obj.setValue('CountryCode', shipping_entry.CountryCode or "", KVS_TYPE_STRING)
            ship_obj.setValue('Phone', shipping_entry.Phone or "", KVS_TYPE_STRING)
            shipping_data = ship_obj.serialize()

    # Now that all details are gathered, call build_GetFinalPriceResponse.
    return [build_GetFinalPriceResponse(client_obj, EResult.OK, fixed_transactionID,
                                        base_cost_cents, discounts_cents, tax_cost_cents,
                                        shipping_cost_cents, include_shipping, shipping_data)]


def handle_CancelLicense(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    NOTE: I am not entirely sure if this was EVER used. it may have been for recurring payment subscriptions

    struct MsgClientCancelLicense_t
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
    return [build_General_response(client_obj, eResult)]


def handle_CancelPurchase(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle cancel purchase request.

    struct MsgClientCancelPurchase_t {
        GID_t m_TransID;  // 8 bytes - 64-bit transaction ID
    };

    Flow:
    1. Parse the 64-bit transaction ID from the request
    2. Validate the transaction (check not found, completed, cancelled, expired)
    3. If valid (code 0), mark as cancelled in database
    4. Return success/failure response

    validate_transaction return codes:
        0 = Valid and ready for processing
        1 = Transaction not found
        2 = Transaction already completed
        3 = Transaction already cancelled
        4 = Transaction expired (older than 24 hours)
    """
    client_address = client_obj.ip_port
    request = packet.CMRequest

    try:
        # Parse the request using the message class
        msg = MSGClientCancelPurchase(client_obj, request.data)
        transaction_id = msg.transaction_id

        cmserver_obj.log.info(
            f"({client_address[0]}:{client_address[1]}): Cancel Purchase request "
            f"for transaction 0x{transaction_id:016X}"
        )

        # Validate the transaction
        validation_result = client_obj.validate_transaction(transaction_id)

        if validation_result != 0:
            # Map validation codes to appropriate log messages
            error_messages = {
                1: "Transaction not found",
                2: "Transaction already completed",
                3: "Transaction already cancelled",
                4: "Transaction expired"
            }
            error_msg = error_messages.get(validation_result, "Unknown validation error")
            cmserver_obj.log.warning(
                f"({client_address[0]}:{client_address[1]}): Cannot cancel transaction "
                f"0x{transaction_id:016X}: {error_msg}"
            )
            return [build_General_response(client_obj, EResult.Fail)]

        # Cancel the transaction
        if client_obj.cancel_transaction(transaction_id):
            cmserver_obj.log.info(
                f"({client_address[0]}:{client_address[1]}): Successfully cancelled "
                f"transaction 0x{transaction_id:016X}"
            )
            return [build_General_response(client_obj, EResult.OK)]
        else:
            cmserver_obj.log.error(
                f"({client_address[0]}:{client_address[1]}): Failed to cancel "
                f"transaction 0x{transaction_id:016X} in database"
            )
            return [build_General_response(client_obj, EResult.Fail)]

    except Exception as e:
        cmserver_obj.log.error(
            f"({client_address[0]}:{client_address[1]}): Exception cancelling purchase: {e}"
        )
        return [build_General_response(client_obj, EResult.Fail)]

def handle_GetPurchaseReceipts(cmserver_obj, packet: CMPacket, client_obj: Client):
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received Get Purchase Receipts Request")
    request = packet.CMRequest
    
    try:
        # Parse the request using the message class
        msg = MSGClientGetPurchaseReceipts(client_obj, request.data)
        
        # Get purchase receipts from the client's transaction history
        receipts = client_obj.get_purchase_receipts(msg.unacknowledged_only)
        
        cmserver_obj.log.debug(f"Sending {len(receipts)} purchase receipts (unacknowledged_only={msg.unacknowledged_only})")
        return [build_GetPurchaseReceiptsResponse(client_obj, receipts)]
        
    except Exception as e:
        cmserver_obj.log.error(f"({client_address[0]}:{client_address[1]}): Failed to handle GetPurchaseReceipts: {e}")
        # Return empty receipts on error
        return [build_GetPurchaseReceiptsResponse(client_obj, [])]

def handle_CompletePurchase(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Processes the complete purchase request.
      1. Retrieves and validates the transactionID.
      2. Calls the new complete_transaction method to finalize it.
      3. Retrieves the updated transaction record.
      4. Builds and returns a purchase response.
    """
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received Complete Purchase Request")

    request = packet.CMRequest
    
    try:
        # Parse the request using the message class
        msg = MSGClientCompletePurchase(client_obj, request.data)
        fixed_transactionID = msg.transaction_id
        cmserver_obj.log.debug(f"({client_address[0]}:{client_address[1]}): CompletePurchase transactionID={fixed_transactionID} (0x{fixed_transactionID:016X}), accountID={client_obj.accountID}")
    except Exception as e:
        cmserver_obj.log.error(f"({client_address[0]}:{client_address[1]}): Failed to parse CompletePurchase: {e}")
        return [build_PurchaseResponse(client_obj, transactionID=0, errorcode=EResult.Fail)]

    # Validate the transaction.
    dbresult = client_obj.validate_transaction(fixed_transactionID)
    cmserver_obj.log.debug(f"({client_address[0]}:{client_address[1]}): validate_transaction result={dbresult} for transactionID={fixed_transactionID}")
    if dbresult != 0:
        # Handle all non-zero results as failures
        # 1 = Not found, 2 = Already completed, 3 = Cancelled, 4 = Expired
        error_msgs = {1: "not found", 2: "already completed", 3: "cancelled", 4: "expired"}
        cmserver_obj.log.warning(f"({client_address[0]}:{client_address[1]}): Transaction {fixed_transactionID} validation failed: {error_msgs.get(dbresult, 'unknown error')}")
        return [build_PurchaseResponse(client_obj, transactionID=fixed_transactionID, errorcode=EResult.Fail)]

    # Complete the transaction.
    transaction_details = client_obj.complete_transaction(fixed_transactionID)

    # Check if transaction completion failed
    if transaction_details is None:
        cmserver_obj.log.error(f"({client_address[0]}:{client_address[1]}): Failed to complete transaction {fixed_transactionID}")
        return [build_PurchaseResponse(client_obj, transactionID=fixed_transactionID, errorcode=EResult.Fail)]

    # Send email notifications using utilities/sendmail.py
    try:
        from config import get_config
        from utilities.sendmail import send_purchase_receipt_email, send_gift_received_email

        config = get_config()
        if config.get('smtp_serverip'):
            # transaction_details is a tuple: (transaction, cc_entry, external_entry, address, shipping)
            transaction_record = transaction_details[0]

            # Send purchase confirmation email to buyer
            if client_obj.email and transaction_record:
                # Calculate amounts from transaction record
                subtotal_cents = transaction_record.BaseCostInCents
                discount_cents = transaction_record.DiscountsInCents
                tax_cents = transaction_record.TaxCostInCents
                shipping_cents = transaction_record.ShippingCostInCents
                total_cents = subtotal_cents - discount_cents + tax_cents + shipping_cents

                # Format amounts
                subtotal = f"{subtotal_cents / 100:.2f}"
                tax = f"{tax_cents / 100:.2f}"
                total = f"{total_cents / 100:.2f}"

                # Get payment info from cc_entry if available
                cc_entry = transaction_details[1] if len(transaction_details) > 1 else None
                payment_method = "Credit Card"
                card_last_four = "****"
                if cc_entry:
                    payment_method = getattr(cc_entry, 'CardType', 'Credit Card') or 'Credit Card'
                    card_number = getattr(cc_entry, 'CardNumber', '')
                    if card_number:
                        card_last_four = card_number[-4:] if len(card_number) >= 4 else card_number

                # Build items list for the receipt
                items = [{
                    'name': f"Package {transaction_record.PackageID}",
                    'price': subtotal
                }]

                # Get transaction date
                date_confirmed = transaction_record.TransactionDate or "N/A"

                try:
                    send_purchase_receipt_email(
                        to_email=client_obj.email,
                        username=client_obj.username,
                        items=items,
                        subtotal=subtotal,
                        tax=tax,
                        total=total,
                        currency="USD",
                        payment_method=payment_method,
                        card_last_four=card_last_four,
                        confirmation_number=str(fixed_transactionID),
                        date_confirmed=date_confirmed
                    )
                    cmserver_obj.log.info(f"Purchase confirmation email sent to {client_obj.email}")
                except Exception as email_error:
                    cmserver_obj.log.error(f"Failed to send purchase email: {email_error}")

            # Send gift notification email if this is a gift purchase
            if transaction_record and getattr(transaction_record, 'GifteeEmail', None):
                recipient_email = transaction_record.GifteeEmail
                gift_message = getattr(transaction_record, 'GiftMessage', '') or ''
                gift_recipient_name = getattr(transaction_record, 'GifteeName', '') or ''

                # Get package name (use PackageID as fallback)
                game_name = f"Package {transaction_record.PackageID}"

                try:
                    send_gift_received_email(
                        to_email=recipient_email,
                        recipient_email=recipient_email,
                        sender_username=client_obj.username,
                        sender_email=client_obj.email or '',
                        sender_avatar_url='',
                        game_name=game_name,
                        game_header_image='',
                        gift_code=str(fixed_transactionID),
                        gift_recipient_name=gift_recipient_name,
                        gift_message=gift_message,
                        gift_sentiment='Enjoy!',
                        gift_signature=client_obj.username
                    )
                    cmserver_obj.log.info(f"Gift notification email sent to {recipient_email}")
                except Exception as email_error:
                    cmserver_obj.log.error(f"Failed to send gift email: {email_error}")
    except ImportError as e:
        cmserver_obj.log.debug(f"Email module not available, skipping email notifications: {e}")
    except Exception as e:
        cmserver_obj.log.error(f"Error sending email notifications: {e}")

    # After successful purchase completion, send updated license list
    purchase_response = build_PurchaseResponse(client_obj, fixed_transactionID, EResult.OK, transaction_details)
    if purchase_response is None:
        cmserver_obj.log.error(f"({client_address[0]}:{client_address[1]}): Failed to build purchase response for transaction {fixed_transactionID}")
        return [build_PurchaseResponse(client_obj, transactionID=fixed_transactionID, errorcode=EResult.Fail)]
    responses = [purchase_response]

    # Send license list after successful purchase (as per CClientJobLicenseList behavior)
    from steam3.Responses.auth_responses import build_ClientLicenseList_response
    license_response = build_ClientLicenseList_response(client_obj)
    if license_response != -1:
        cmserver_obj.log.debug(f"Sending license list after successful purchase completion")
        responses.append(license_response)
    
    # Send SystemIM notifications for any guest passes created from this purchase
    # Skip if guestpass system is disabled
    if _is_guestpass_disabled():
        cmserver_obj.log.debug("Guestpass system is disabled, skipping guest pass notifications")
        return responses

    try:
        # Get the transaction to check if it contains guest pass information
        transaction = client_obj.get_transaction(fixed_transactionID)
        if transaction and transaction[0].PassInformation:
            import json
            from steam3.Responses.general_responses import build_guest_pass_granted_notification
            
            try:
                pass_info = json.loads(transaction[0].PassInformation)
                
                # Check for guest passes granted to this user
                if 'guestpasses' in pass_info or 'giftpasses' in pass_info:
                    for pass_type in ['guestpasses', 'giftpasses']:
                        if pass_type in pass_info:
                            for sub_id, details in pass_info[pass_type].items():
                                # Get package name from CDR if available
                                package_name = ""
                                if hasattr(globalvars, 'CDR_DICTIONARY') and globalvars.CDR_DICTIONARY:
                                    subscription = None
                                    if hasattr(globalvars.CDR_DICTIONARY, 'get_subscription'):
                                        # CDR_DICTIONARY is a ContentDescriptionRecord object
                                        subscription = globalvars.CDR_DICTIONARY.get_subscription(int(sub_id))
                                    elif isinstance(globalvars.CDR_DICTIONARY, dict):
                                        # CDR_DICTIONARY is a plain dict, look up subscription by ID
                                        subs = globalvars.CDR_DICTIONARY.get(b"\x02\x00\x00\x00", {})
                                        sub_key = struct.pack('<I', int(sub_id))
                                        if sub_key in subs:
                                            # Create CDRSubscriptionRecord from raw dict data
                                            from utilities.contentdescriptionrecord import CDRSubscriptionRecord
                                            subscription = CDRSubscriptionRecord(int(sub_id))
                                            subscription.parse(subs[sub_key])
                                    
                                    if subscription and hasattr(subscription, 'Name'):
                                        package_name = subscription.Name
                                
                                # Send notification for granted guest pass
                                notification = build_guest_pass_granted_notification(
                                    client_obj,
                                    "yourself",  # Since this is from their own purchase
                                    package_name
                                )
                                responses.append(notification)
                                cmserver_obj.log.debug(f"Sending guest pass granted notification for package {sub_id}")
                                
            except json.JSONDecodeError:
                cmserver_obj.log.warning(f"Invalid JSON in PassInformation for transaction {fixed_transactionID}")
            
    except Exception as e:
        cmserver_obj.log.error(f"Error sending guest pass notifications: {e}")
    
    return responses


def handle_PurchaseWithMachineID(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle purchase with machine ID validation.
    This is similar to InitPurchase but includes machine ID verification.
    """
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received Purchase With Machine ID Request")
    request = packet.CMRequest
    
    try:
        # Parse the request using the message class
        msg = MSGClientPurchaseWithMachineID(client_obj, request.data)
        
        # Implement machine ID validation logic
        cmserver_obj.log.info(f"Purchase request with machine ID: 0x{msg.machine_id:08X}")
        
        # Validate machine ID against client's registered machine ID
        if hasattr(client_obj, 'is_machineID_set') and client_obj.is_machineID_set:
            # For fraud prevention, we could check against a database of known machine IDs
            # For now, we accept any machine ID but log it for monitoring
            cmserver_obj.log.debug(f"Machine ID validation: Client has machine ID set")
        else:
            cmserver_obj.log.warning(f"Purchase attempt without machine ID validation")
            return [build_PurchaseResponse(client_obj, transactionID=msg.payment_id, errorcode=EResult.InvalidParam)]
        
        # For now, return a simple purchase response indicating success
        return [build_PurchaseResponse(client_obj, transactionID=msg.payment_id, errorcode=EResult.OK)]
        
    except Exception as e:
        cmserver_obj.log.error(f"({client_address[0]}:{client_address[1]}): Failed to handle PurchaseWithMachineID: {e}")
        return [build_PurchaseResponse(client_obj, transactionID=0, errorcode=EResult.Fail)]


def handle_LookupKey(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle key lookup request - check if a product key is valid and what it unlocks.
    Returns proper LookupKeyResponse with ActivationCodeInfo if key is found.

    Flow:
    1. Decode the CD key to extract game_code and territory_code
    2. Look up the matching subscription in CDR by game_code
    3. Return ActivationCodeInfo with subscription details
    """
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received Key Lookup Request")
    request = packet.CMRequest

    try:
        # Parse the request using the message class
        msg = MSGClientLookupKey(client_obj, request.data)

        cmserver_obj.log.info(f"Looking up key: {msg.key}")

        # Decode the CD key to extract game code and territory information
        from steam3.Types.CDKeyDecoder import decode_cdkey
        from steam3.Types.MessageObject.ActivationCodeInfo import ActivationCodeInfo

        key_info = decode_cdkey(msg.key)

        if not key_info:
            cmserver_obj.log.warning(f"Could not decode key format: {msg.key}")
            return [build_LookupKeyResponse(
                client_obj,
                EResult.Fail,
                EPurchaseResultDetail.BadActivationCode
            )]

        cmserver_obj.log.info(
            f"Decoded key: game_code={key_info.game_code}, "
            f"territory={key_info.territory_code}, "
            f"serial={key_info.serial_number}, "
            f"valid_checksum={key_info.is_valid}"
        )

        if not key_info.is_valid:
            cmserver_obj.log.warning(f"Key {msg.key} has invalid checksum")
            return [build_LookupKeyResponse(
                client_obj,
                EResult.Fail,
                EPurchaseResultDetail.BadActivationCode
            )]

        # Look up the subscription in CDR by game code and territory code
        if not globalvars.CDR_DICTIONARY:
            cmserver_obj.log.error("CDR_DICTIONARY not loaded - cannot look up subscription by game code")
            return [build_LookupKeyResponse(
                client_obj,
                EResult.Fail,
                EPurchaseResultDetail.ContactSupport
            )]

        subscription = None

        if hasattr(globalvars.CDR_DICTIONARY, 'get_subscription_by_game_code'):
            # CDR_DICTIONARY is a ContentDescriptionRecord object
            # First try to find subscription with both game_code and territory_code
            subscription = globalvars.CDR_DICTIONARY.get_subscription_by_game_code(
                key_info.game_code,
                key_info.territory_code
            )
            # If not found with territory, try just game_code
            if subscription is None:
                subscription = globalvars.CDR_DICTIONARY.get_subscription_by_game_code(
                    key_info.game_code,
                    None
                )
        elif isinstance(globalvars.CDR_DICTIONARY, dict):
            # CDR_DICTIONARY is a plain dict, iterate through subscriptions to find by game code
            from utilities.contentdescriptionrecord import CDRSubscriptionRecord
            subs = globalvars.CDR_DICTIONARY.get(b"\x02\x00\x00\x00", {})

            # Search for matching subscription
            for sub_key, sub_data in subs.items():
                temp_sub = CDRSubscriptionRecord(int.from_bytes(sub_key, 'little'))
                temp_sub.parse(sub_data)

                # Get game code from subscription
                sub_game_code = temp_sub.GameCode
                if isinstance(sub_game_code, bytes):
                    sub_game_code = int.from_bytes(sub_game_code, 'little')
                elif sub_game_code is not None:
                    sub_game_code = int(sub_game_code)

                if sub_game_code is None or sub_game_code != key_info.game_code:
                    continue

                # Check territory code if provided
                if key_info.territory_code is not None:
                    sub_territory = temp_sub.TerritoryCode
                    if isinstance(sub_territory, bytes):
                        sub_territory = int.from_bytes(sub_territory, 'little')
                    elif sub_territory is not None:
                        sub_territory = int(sub_territory)

                    if sub_territory is not None and sub_territory == key_info.territory_code:
                        subscription = temp_sub
                        break
                else:
                    # No territory filter, accept first match
                    subscription = temp_sub
                    break

            # If not found with territory, try without territory filter
            if subscription is None and key_info.territory_code is not None:
                for sub_key, sub_data in subs.items():
                    temp_sub = CDRSubscriptionRecord(int.from_bytes(sub_key, 'little'))
                    temp_sub.parse(sub_data)

                    sub_game_code = temp_sub.GameCode
                    if isinstance(sub_game_code, bytes):
                        sub_game_code = int.from_bytes(sub_game_code, 'little')
                    elif sub_game_code is not None:
                        sub_game_code = int(sub_game_code)

                    if sub_game_code is not None and sub_game_code == key_info.game_code:
                        subscription = temp_sub
                        break

        if subscription is None:
            cmserver_obj.log.warning(
                f"No subscription found in CDR for game_code={key_info.game_code}, "
                f"territory={key_info.territory_code}"
            )
            return [build_LookupKeyResponse(
                client_obj,
                EResult.Fail,
                EPurchaseResultDetail.BadActivationCode
            )]

        # Get subscription ID (package ID)
        sub_id = subscription.SubscriptionId
        if isinstance(sub_id, bytes):
            package_id = int.from_bytes(sub_id, byteorder='little')
        else:
            package_id = int(sub_id)

        # Get subscription name for logging
        sub_name = subscription.Name
        if isinstance(sub_name, bytes):
            sub_name = sub_name.rstrip(b'\x00').decode('utf-8', errors='ignore')

        cmserver_obj.log.info(
            f"Found subscription: ID={package_id}, Name='{sub_name}' "
            f"for game_code={key_info.game_code}"
        )

        # Create ActivationCodeInfo with decoded data and CDR info
        activation_info = ActivationCodeInfo()
        activation_info.set_Key(msg.key)
        activation_info.set_GameCode(key_info.game_code)
        activation_info.set_SalesTerritoryCode(key_info.territory_code)
        activation_info.set_SerialNumber(key_info.serial_number)
        activation_info.set_PackageID(package_id)

        # Return success with activation info
        return [build_LookupKeyResponse(
            client_obj,
            EResult.OK,
            EPurchaseResultDetail.NoDetail,
            activation_info
        )]

    except Exception as e:
        cmserver_obj.log.error(f"({client_address[0]}:{client_address[1]}): Failed to handle LookupKey: {e}")
        import traceback
        traceback.print_exc()
        return [build_LookupKeyResponse(client_obj, EResult.Fail, EPurchaseResultDetail.ContactSupport)]


def handle_AckPurchaseReceipt(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Method flow:
    - do normal transactionid checks, expiration check, completed check, already acknowledged check
    - if OK, set DateAcknowledged to the current date and time in the steam3transactions table for this transaction
    - After acknowledgment, send license list to client (as per CClientJobLicenseList)
    struct MsgClientAckPurchaseReceipt_t
    {
      GID_t m_TransID;
    };
    """
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received Ack Purchase Receipt Request")
    request = packet.CMRequest
    fixed_transactionID = fix_transactionID(request)
    client_obj.set_receipt_acknowledged(fixed_transactionID)
    
    # After acknowledging receipt, send updated license list
    from steam3.Responses.auth_responses import build_ClientLicenseList_response
    license_response = build_ClientLicenseList_response(client_obj)
    if license_response != -1:
        cmserver_obj.log.debug(f"Sending license list after purchase receipt acknowledgment")
        return [license_response]
    
    return -1


def handle_ClientGetLicenses(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle ClientGetLicenses (EMsg 728) - client requesting their license list.
    This is called when the client wants to refresh their licenses.
    """
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received Get Licenses Request")

    request = packet.CMRequest

    try:
        # Parse the request (format is the same for both proto and clientmsg)
        msg = MSGClientGetLicenses(client_obj, request.data)

        # Build license list response with appropriate format
        from steam3.Responses.auth_responses import build_ClientLicenseList_response
        response = build_ClientLicenseList_response(client_obj, proto=packet.is_proto)

        if response == -1:
            cmserver_obj.log.error(f"Failed to build license list for client {client_obj.steamID}")
            return []

        cmserver_obj.log.debug(f"Sending license list to client {client_obj.steamID}")
        return [response]

    except Exception as e:
        cmserver_obj.log.error(f"({client_address[0]}:{client_address[1]}): Failed to handle GetLicenses: {e}")
        return []


def handle_PreviousClickAndBuyAccount(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle request for previous Click and Buy account information.
    This is used to retrieve previously stored payment method details.
    """
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received Previous Click and Buy Account Request")
    request = packet.CMRequest
    
    try:
        # Implement Click and Buy account retrieval
        # Query database for previously stored Click and Buy account info
        try:
            # Check if client has any previous Click and Buy transactions
            import steam3
            
            # Query for previous Click and Buy payment entries
            previous_accounts = steam3.database.get_user_payment_methods(client_obj.accountID, EPaymentMethod.ClickAndBuy)
            
            if previous_accounts:
                cmserver_obj.log.info(f"Found {len(previous_accounts)} previous Click and Buy accounts")
                # Return the most recent account info
                return [build_General_response(client_obj, EResult.OK)]
            else:
                cmserver_obj.log.info(f"No previous Click and Buy accounts found")
                return [build_General_response(client_obj, EResult.NoMatch)]
                
        except Exception as e:
            cmserver_obj.log.error(f"Error retrieving Click and Buy account: {e}")
            return [build_General_response(client_obj, EResult.Fail)]

    except Exception as e:
        cmserver_obj.log.error(f"({client_address[0]}:{client_address[1]}): Failed to handle PreviousClickAndBuyAccount: {e}")
        return [build_General_response(client_obj, EResult.Fail)]
