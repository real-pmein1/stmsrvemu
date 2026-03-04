import logging
import random
import hashlib
import secrets
import socket
import string
import struct
from datetime import datetime
from random import getrandbits

import globalvars

log = logging.getLogger("cmauth")
from steam3 import utilities
from steam3.ClientManager.client import Client
from steam3.Types.Objects.AppOwnershipTicket import Steam3AppOwnershipTicket
from steam3.Types.Objects.PreProtoBuf.gameConnectToken import GameConnectToken
from steam3.Types.emsg import EMsg
from steam3.Types.steam_types import EAccountFlags, EInstanceFlag, EResult,  EType, EUniverse
from steam3.Types.steamid import SteamID
from steam3.cm_packet_utils import  CMResponse
from steam3.messages.MsgClientEmailAddrInfo import MsgClientEmailAddrInfo
from steam3.messages.responses.MsgClientGetAppOwnershipTicket_Response import GetAppOwnershipTicketResponse
from steam3.messages.responses.MsgClientLogon_Response import LogonResponse
from steam3.utilities import add_time_to_current_uint32, generate_64bit_token, get_current_time_uint32


def build_logon_response(client_obj, client_address, eresult, is_anon = False, proto = False, is_gameserver = False):
    """
    Build a LogonResponse object and serialize it.
    :param client_obj: The client object containing relevant data.
    :param client_address: Tuple of the client's IP address and port.
    :param eresult: The result of the login attempt.
    :param is_anon: Boolean indicating if the login is anonymous.
    :param proto: Boolean indicating if Protobuf serialization is required.
    :return: Serialized response packet.
    """
    response = LogonResponse(client_obj)

    # Populate common fields
    response.eresult = eresult

    if is_gameserver:
        # Create the SteamID instance
        steamID = SteamID()

        # Set the properties for the SteamID
        steamID.set_universe(EUniverse.PUBLIC)  # Universe = PUBLIC
        steamID.set_type(EType.GAMESERVER)      # Type = GAMESERVER
        steamID.set_instance(EInstanceFlag.ALL) # Instance = ALL

        response.steamID = steamID
    else:
        response.steamID = client_obj.steamID

    response.public_ip = int.from_bytes(socket.inet_aton(client_address[0]), 'little')
    response.server_time = get_current_time_uint32()
    response.is_anon = is_anon

    if not is_anon:
        response.account_flags = client_obj.get_accountflags()
    elif is_gameserver:
        response.account_flags = EAccountFlags.NormalUser

    # Serialize based on format
    if proto:
        return response.to_protobuf()
    else:
        return response.to_clientmsg()


def build_login_failure(client_obj, error_code):
    packet = CMResponse(eMsgID = EMsg.ClientLoggedOff, client_obj = client_obj)

    # TODO figure out how to prevent a user that does not exist, or uses an incorrect password from logging in
    # This only is an issue if a user resets the DB but still has a steam client that had an old user that auto-logged in and their ticket is still valid
    # THIS IS NOT FUNCTIONAL AT THE MOMENT
    # print("failed login")
    packet.data = struct.pack('I',
                              error_code)  # eresult)

    return packet


def build_client_logoff(client_obj, client_address, proto=False):
    from steam3.messages.responses.MsgClientLoggedOff import MsgClientLoggedOff

    response = MsgClientLoggedOff(client_obj)
    response.result = EResult.OK

    if proto:
        return response.to_protobuf()
    else:
        return response.to_clientmsg()


def build_account_info_response(cmserver_obj, client_obj: Client, pktNickname=None, proto=False):
    from steam3.messages.responses.MsgClientAccountInfo import AccountInfoResponse

    response = AccountInfoResponse(client_obj)

    # Grab the nickname since we don't have it during login
    nickname = client_obj.check_username(pktNickname)
    response.persona_name = nickname

    # TODO 2005 ONLY CONTAINS NICKNAME! NEED TO FIGURE OUT WHEN LANGUAGE WAS ADDED
    # FIXME Official Steam used the clients IP address to set the country, which is then used for purchases and such

    if cmserver_obj.config['override_ip_country_region'].lower() == 'false':
        lang = utilities.get_country_code(client_obj.ip_port[0])
    else:
        lang = cmserver_obj.config['override_ip_country_region']  # 2 letter country code, used for checking restrictions

    response.ip_country = lang.upper()

    # TODO implement these custom fields, it seems 2009+ has an option for these fields, not sure what steam does with the data
    # Optional fields: hashed password components
    """
    salt_password = secrets.token_bytes(8)  # Simulate a random salt (8 bytes)
    sha_digest_password = hashlib.sha1(b"example_password").digest()  # Simulated SHA-1 digest (20 bytes)"""

    if proto:
        return response.to_protobuf()
    else:
        return response.to_clientmsg()


def build_old_GameConnectToken_response(client_obj):
    """This is the old connecttoken packet, it contains a single token with no timestamp"""
    packet = CMResponse(eMsgID = EMsg.ClientGameConnectToken, client_obj = client_obj)

    # Below is the bytes of an actual token
    # data.extend(b'\x2a\xab\xf7\x04\xa6\x60\xde\xb4\x70\x0f\x45\x00\x01\x00\x10\x01') # Taken from ymgve 2005 packet dump
    # FIXME grab from database
    steam_globalID = client_obj.steamID.get_static_steam_global_id()
    token1 = GameConnectToken(getrandbits(64), steam_globalID)

    packet.data = token1.serialize_single_deprecated()

    return packet


def build_GameConnectTokensResponse(client_obj, proto=False):
    from steam3.messages.responses.MsgClientGameConnectTokens import GameConnectTokensResponse

    response = GameConnectTokensResponse(client_obj)

    # FIXME test code, grab from DB or figure out how this is supposed to be used
    # Information taken from TINServer
    response.generate_default_tokens(count=2)

    if proto:
        return response.to_protobuf()
    else:
        return response.to_clientmsg()


def build_ClientLicenseList_response(client_obj, proto=False):
    """
    Build a proper ClientLicenseList response using the modern License MessageObject.

    This replaces the deprecated build_LicenseResponse and sends actual license data
    from the database to the client. It combines licenses from two sources:
    1. Steam3LicenseRecord - modern Steam3 purchase system
    2. AccountSubscriptionsRecord - legacy Steam2 subscription system

    Args:
        client_obj: The client object requesting licenses
        proto: Whether to use protobuf format (True) or binary format (False)

    Returns:
        CMResponse/CMProtoResponse packet with license list or -1 on failure


    Example cs cz license:
        # license_test = Deprecated_License(
                # package_id = 76,
                # time_created = get_current_time_uint32(),
                # time_next_process = 0,
                # minute_limit = 0,
                # minutes_used = 0,
                # payment_method = int(EPaymentMethod.CreditCard),
                # purchase_country_code = 'US',
                # flags = int(ELicenseFlags.NONE),
                # license_type = int(ELicenseType.SinglePurchase)
        # )
        # packet.data += license_test.serialize()
    """
    try:
        from steam3.messages.responses.MSGClientLicenseList import MSGClientLicenseList

        # Create the license list message
        license_msg = MSGClientLicenseList(client_obj)

        # Track which package IDs we've added to avoid duplicates
        added_package_ids = set()

        # Get client's licenses from Steam3LicenseRecord table (modern purchases)
        licenses = client_obj.get_licenses()  # Returns Steam3LicenseRecord objects

        if licenses:
            for license_record in licenses:
                license_msg.add_license_from_db_record(license_record)
                added_package_ids.add(license_record.PackageID)

        # Get client's subscriptions from AccountSubscriptionsRecord table (legacy subscriptions)
        subscriptions = client_obj.get_subscriptions()  # Returns AccountSubscriptionsRecord objects

        if subscriptions:
            for sub_record in subscriptions:
                # Only add if not already added from Steam3LicenseRecord (avoid duplicates)
                if sub_record.SubscriptionID not in added_package_ids:
                    license_msg.add_license_from_subscription_record(sub_record)
                    added_package_ids.add(sub_record.SubscriptionID)

        # Return the serialized packet in appropriate format
        if proto:
            return license_msg.to_protobuf()
        else:
            return license_msg.to_clientmsg()

    except Exception as e:
        import logging
        log = logging.getLogger('auth_responses')
        log.error(f"Failed to build ClientLicenseList response: {e}")
        return -1


def build_OneTimeWGAuthPassword(cmserver_obj, client_obj: Client):
    def generate_random_string_with_null_byte(length = 15):
        characters = string.ascii_letters + string.digits
        random_string = ''.join(random.choice(characters) for _ in range(length))
        return random_string + '\0'

    packet = CMResponse(eMsgID = EMsg.ClientOneTimeWGAuthPassword, client_obj = client_obj)

    random_otp = generate_random_string_with_null_byte().encode('latin-1')
    if client_obj.set_onetime_pass(random_otp) and len(random_otp) <= 18:
        packet.data = b'\x00' + random_otp
    else:
        cmserver_obj.log.error(f"Error generating One Time Password! Either Too Long (> 17) Or cannot save to database!")
        return -1

    return packet


def build_MsgClientSessionToken(cmserver_obj, client_obj: Client, proto=False):
    """This token is used for authenticated content downloading in Steam2."""
    from steam3.messages.responses.MsgClientSessionToken import SessionTokenResponse

    response = SessionTokenResponse(client_obj)
    response.generate_token()

    if proto:
        return response.to_protobuf()
    else:
        return response.to_clientmsg()


def build_ClientChangePasswordResponse(cmserver_obj, client_obj: Client, error_code):

    packet = CMResponse(eMsgID = EMsg.ClientPasswordChangeResponse, client_obj = client_obj)

    packet.data = struct.pack('<I',
                              error_code)
    return packet


def build_GetAppOwnershipTicketResponse(cmserver_obj, client_obj: Client, appID, is_proto):
    """
    Build a GetAppOwnershipTicketResponse object and serialize it.
    :param cmserver_obj: The CM server object handling the request.
    :param client_obj: The client object requesting the ticket.
    :param app_id: The application ID.
    :param is_proto: Boolean indicating whether to serialize as Protobuf.
    :return: Serialized response packet.
    """
    response = GetAppOwnershipTicketResponse(client_obj)

    # Set common fields
    response.eresult = EResult.OK  # Assume success
    response.app_id = appID

    global_steam_id = client_obj.steamID.get_static_steam_global_id()
    ticket_version = 4 if globalvars.steamui_ver > 1238 else 2

    log.debug(f"AppOwnershipTicket request: AppID={appID}, SteamID={global_steam_id}, "
              f"TicketVersion={ticket_version} (steamui_ver={globalvars.steamui_ver}), Proto={is_proto}")

    # Create the app ownership ticket
    app_ownership_ticket = Steam3AppOwnershipTicket(
            steam_id = global_steam_id,
            ticket_version = ticket_version,
            app_id = appID,
            public_ip = client_obj.publicIP,
            private_ip = client_obj.privateIP,
            app_ownership_ticket_flags = 0,
            time_issued = get_current_time_uint32(),
            time_expire = add_time_to_current_uint32(days = 21),
    )
    app_ownership_ticket.vac_banned = client_obj.is_appid_vacbanned(appID)

    # Serialize the ticket
    response.ticket, response.signature_length = app_ownership_ticket.serialize(True)

    # Serialize the response
    if is_proto:
        return response.to_protobuf()
    else:
        return response.to_clientmsg()


def build_CreateAccountResponse(client_obj, eresult, steamID, isVersion2 = False):
    """struct MsgClientLogOnResponse_t
    {
      int32 m_EResult;
      int32 m_nOutOfGameHeartbeatRateSec;
      int32 m_nInGameHeartbeatRateSec;
      uint64 m_ulLogonCookie;
      uint32 m_unIPPublic;
      uint32 m_RTime32ServerRealTime;
    };
    + 32bit (4 byte) account flags
    """
    packet = CMResponse(eMsgID = EMsg.ClientCreateAccountResponse, client_obj = client_obj)
    # FIXME need to figure out why this is not working!
    if isVersion2:  # The response to createaccount2 only contains the eresult
        packet.data = struct.pack('I',
                                  eresult,
                                  )
    else:
        packet.data = struct.pack('IQ',
                                  eresult,
                                  steamID
                                  )

    packet.length = len(packet.data)
    return packet


def build_emailaddressinfo(cmserver_obj, client_obj: Client):
    packet = CMResponse(eMsgID = EMsg.ClientEmailAddrInfo, client_obj = client_obj)

    data = MsgClientEmailAddrInfo()
    db_data = client_obj.get_email_info()

    if db_data:
        data.contact_email, data.verified_email = db_data
        packet.data = data.serialize()
        return packet

    cmserver_obj.log.error(f"User {client_obj.steamID} does not have an email address - How could this happen?!")
    return None


def build_ClientNewLoginKey(cmserver_obj, client_obj: Client, proto: bool = False):
    """
    Builds the MsgClientNewLoginKey message.

    :param cmserver_obj: The CM server object containing relevant data.
    :param client_obj: The client object containing relevant data.
    :param proto: If True, use protobuf format; otherwise use binary MsgClientNewLoginKey_t.

    loginkey code was taken from TINServer.
    """
    try:
        # Generate the unique ID for the login key as an integer
        unique_id_int = int.from_bytes(secrets.token_bytes(4), 'little')

        # Seed data and Steam global ID for the digest
        seed = struct.pack("<I", random.randint(0, 0xFFFFFFFF))  # Random 4-byte seed
        steam_global_id = struct.pack("<Q", client_obj.steamID.get_static_steam_global_id())  # Steam Global ID (uint64)

        # Generate the SHA-1 digest
        digester = hashlib.sha1()
        digester.update(seed)
        digester.update(steam_global_id)
        digester.update(seed)
        digest = digester.digest()

        # Process the digest to create the login key
        login_key = [(digest[i] % 95) + 32 for i in range(20)]
        login_key_bytes = bytes(login_key)  # Convert to a bytes object
        login_key_str = login_key_bytes[:-1].decode('ascii')

        # Save loginkey to client object and database (store unique_id as integer)
        client_obj.set_new_loginkey(unique_id_int, login_key_str)

        log.debug(f"build_ClientNewLoginKey: proto={proto}, unique_id={unique_id_int}, login_key={login_key_str}")

        if proto:
            # Protobuf format for newer clients (2011+) - use CMProtoResponse for proper proto bit
            from steam3.cm_packet_utils import CMProtoResponse
            from steam3.protobufs.steammessages_clientserver_login_pb2 import CMsgClientNewLoginKey

            packet = CMProtoResponse(eMsgID=EMsg.ClientNewLoginKey, client_obj=client_obj)
            proto_msg = CMsgClientNewLoginKey()
            proto_msg.unique_id = unique_id_int
            proto_msg.login_key = login_key_str
            packet.set_response_message(proto_msg)
            packet.data = proto_msg.SerializeToString()
            log.debug(f"build_ClientNewLoginKey: using CMProtoResponse, data_len={len(packet.data)}, data={packet.data.hex()}")
        else:
            # Binary format: MsgClientNewLoginKey_t { uint32 m_unUniqueId; char m_rgchLoginKey[20]; }
            packet = CMResponse(eMsgID=EMsg.ClientNewLoginKey, client_obj=client_obj)
            packet.data = struct.pack("<I20s", unique_id_int, login_key_bytes) + b'\x00'
            log.debug(f"build_ClientNewLoginKey: using CMResponse, data_len={len(packet.data)}, data={packet.data.hex()}")

        return packet
    except Exception as e:
        cmserver_obj.log.error(f"Error building ClientNewLoginKey: {e}")
        import traceback
        cmserver_obj.log.error(traceback.format_exc())
        return -1


def build_EmailChangeResponse(client_obj: Client, result: EResult):
    """
    Build email change response (EMsg 891 - ClientEmailChangeResponse).
    Uses the deprecated response format which only contains result.
    """
    from steam3.messages.responses.MsgClientEmailChangeResponse_DEPRECATED import MsgClientEmailChangeResponse_DEPRECATED

    response = MsgClientEmailChangeResponse_DEPRECATED(client_obj=client_obj, result=result)
    return response.to_clientmsg()


def build_SecretQAChangeResponse(client_obj: Client, result: EResult):
    """
    Build secret Q&A change response (EMsg 892 - ClientSecretQAChangeResponse).
    """
    from steam3.messages.responses.MsgClientSecretQAChangeResponse import MsgClientSecretQAChangeResponse

    response = MsgClientSecretQAChangeResponse(client_obj=client_obj, result=result)
    return response.to_clientmsg()


def build_RequestForgottenPasswordEmailResponse(client_obj: Client, result: EResult, secret_question_required: bool = False):
    """
    Build forgotten password email response (EMsg 5402 - ClientRequestForgottenPasswordEmailResponse).
    """
    from steam3.messages.responses.MsgClientRequestForgottenPasswordEmailResponse import MsgClientRequestForgottenPasswordEmailResponse

    response = MsgClientRequestForgottenPasswordEmailResponse(
        client_obj=client_obj,
        result=result,
        secret_question_answer_required=secret_question_required
    )
    return response.to_clientmsg()


def build_ResetForgottenPasswordResponse(client_obj: Client, result: EResult):
    """
    Build reset forgotten password response (EMsg 5405 - ClientResetForgottenPasswordResponse).
    """
    from steam3.messages.responses.MsgClientResetForgottenPasswordResponse import MsgClientResetForgottenPasswordResponse

    response = MsgClientResetForgottenPasswordResponse(client_obj=client_obj, result=result)
    return response.to_clientmsg()


def build_PasswordChangeResponse(client_obj: Client, result: EResult):
    """
    Build password change response (EMsg 805 - ClientPasswordChangeResponse).
    """
    from steam3.messages.responses.MsgClientPasswordChangeResponse import MsgClientPasswordChangeResponse

    response = MsgClientPasswordChangeResponse(client_obj=client_obj, result=result)
    return response.to_clientmsg()


