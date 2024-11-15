import random
import secrets
import string
import struct
from datetime import datetime
from random import getrandbits

import globalvars
import utils
from steam3 import database, utilities
from steam3.ClientManager.client import Client
from steam3.Types.MessageObject.License import License_Deprecated
from steam3.Types.Objects.AppOwnershipTicket import Steam3AppOwnershipTicket
from steam3.Types.Objects.PreProtoBuf.gameConnectToken import GameConnectToken
from steam3.Types.emsg import EMsg
from steam3.Types.steam_types import EAccountFlags, ELicenseFlags, ELicenseType, EPaymentMethod, EResult, EServerType
from steam3.cm_packet_utils import CMResponse
from steam3.messages.MsgClientEmailAddrInfo import MsgClientEmailAddrInfo
from steam3.utilities import add_time_to_current_uint32, create_GlobalID, generate_64bit_token, get_current_time_uint32, ip_port_to_packet_format
from utilities import encryption


def build_login_response(client_obj, client_address, eresult):
    """struct MsgClientLogOnResponse_t
    {
      int32 m_EResult;
      int32 m_nOutOfGameHeartbeatRateSec;
      int32 m_nInGameHeartbeatRateSec;
      uint64 m_ulLogonCookie; / steamid
      uint32 m_unIPPublic;
      uint32 m_RTime32ServerRealTime;
    };
    + 32bit (4 byte) account flags
    """
    packet = CMResponse(eMsgID = EMsg.ClientLogOnResponse, client_obj = client_obj)

    accountFlags = client_obj.get_accountflags()

    # FIXME: to fail a login, set result to a failure int and set everything else to 0
    packet.data = struct.pack('I I I I I I',
                              eresult,
                              9,  # outOfGameHeartbeatRateSec
                              9,  # inGameHeartbeatRateSec
                              client_obj.steamID * 2,
                              client_obj.clientID2,
                              int(utils.reverse_ip_bytes(client_address[0])))
    if globalvars.steamui_ver > 85:
        packet.data += struct.pack('<I', get_current_time_uint32())
    if globalvars.steamui_ver >= 288:
        packet.data += struct.pack('<I', accountFlags)

    packet.length = len(packet.data)
    return packet


def build_login_failure(client_obj, error_code):
    packet = CMResponse(eMsgID = EMsg.ClientLoggedOff, client_obj = client_obj)

    # TODO figure out how to prevent a user that does not exist, or uses an incorrect password from logging in
    # This only is an issue if a user resets the DB but still has a steam client that had an old user that auto-logged in
    # THIS IS NOT FUNCTIONAL AT THE MOMENT
    # print("failed login")
    packet.data = struct.pack('I',
                              error_code)  # eresult)

    return packet


def build_client_logoff(client_obj, client_address):
    packet = CMResponse(eMsgID = EMsg.ClientLoggedOff, client_obj = client_obj)

    packet.data = struct.pack('I',
                              EResult.OK)

    return packet


def build_account_info_response(cmserver_obj, client_obj: Client, pkt_nickname = None):
    packet = CMResponse(eMsgID = EMsg.ClientAccountInfo, client_obj = client_obj)

    nickname = client_obj.check_username(pkt_nickname)  # grab the nickname since we dont have it during login

    name = nickname.encode('latin-1')  # user nickname
    #print(f"nickname: {nickname}")
    # TODO 2005 ONLY CONTAINS NICKNAME! NEED TO FIGURE OUT WHEN LANGUAGE WAS ADDED
    # FIXME Official Steam used the clients IP address to set the country, which is then used for purchases and such

    if cmserver_obj.config['override_ip_country_region'].lower() == 'false':
        lang = utilities.get_country_code(client_obj.ip_port[0])
    else:
        lang = cmserver_obj.config['override_ip_country_region'] # 2 letter country code, used for checking restrictions

    packet.data = b"\x00" + name + b'\x00' + lang.upper().encode('latin-1') + b'\x00'

    return packet


def build_old_GameConnectToken_response(client_obj):
    """This is the old connecttoken packet, it contains a single token with no timestamp"""
    packet = CMResponse(eMsgID = EMsg.ClientGameConnectToken, client_obj = client_obj)

    # Below is the bytes of an actual token
    # data.extend(b'\x2a\xab\xf7\x04\xa6\x60\xde\xb4\x70\x0f\x45\x00\x01\x00\x10\x01') # Taken from ymgve 2005 packet dump

    steam_globalID = create_GlobalID(client_obj.steamID * 2, client_obj.clientId2)
    token1 = GameConnectToken(getrandbits(64), steam_globalID)

    packet.data = token1.serialize_single_deprecated()

    return packet


def build_GameConnectTokensResponse(client_obj):

    packet = CMResponse(eMsgID = EMsg.ClientGameConnectTokens, client_obj = client_obj)

    game_connect_token_length = struct.calcsize('<QQI')  # Size of GameConnectToken structure
    packet.data = struct.pack('I', game_connect_token_length)

    # FIXME test code, grab from DB or figure out how this is supposed to be used
    # Information taken from TINServer
    num_tokens = 2
    packet.data += struct.pack('I', num_tokens)  # Number of tokens

    steam_globalID = create_GlobalID(client_obj.steamID * 2, client_obj.clientID2)

    token1 = GameConnectToken(getrandbits(64), steam_globalID, int(datetime.utcnow().timestamp()))
    token2 = GameConnectToken(getrandbits(64), steam_globalID, int(datetime.utcnow().timestamp()))

    packet.data += token1.serialize()
    packet.data += token2.serialize()

    if globalvars.steamui_ver > 624:
        maximum_tokens = 10
        packet.data += struct.pack('I', maximum_tokens)

    return packet


def build_LicenseResponse(client_obj):
    """
    Build a chat eMsgID packet with eMsgID 0x030C.

    :param client_obj: The MsgHdr_deprecated object.
    :return: A ChatCommandPacket instance.
    """
    packet = CMResponse(eMsgID = 0x030C, client_obj = client_obj)

    license_count = 1
    packet.data = struct.pack('II',
                              EResult.OK,
                              license_count)  # license count

    # STEAM3 LICENSE TEST - NO NOT ENABLE FOR LIVE

    #license_test = License_Deprecated(
    #        package_id = 76,
    #        time_created = get_current_time_uint32(),
    #        time_next_process = 0,
    #        minute_limit = 0,
    #        minutes_used = 0,
    #        payment_method = int(EPaymentMethod.CreditCard),
    #        purchase_country_code = 'US',
    #        flags = int(ELicenseFlags.NONE),
    #        license_type = int(ELicenseType.SinglePurchase)
    #)
    #packet.data += license_test.serialize()

    return packet

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


def build_MsgClientSessionToken(cmserver_obj, client_obj: Client):
    """ This token is used for authenticated content downloading in Steam2."""
    packet = CMResponse(eMsgID = EMsg.ClientSessionToken, client_obj = client_obj)

    client_obj.session_token = generate_64bit_token().encode('latin-1')

    packet.data = client_obj.session_token

    return packet


def build_MsgClientServerList(cmserver_obj, client_obj: Client):
    packet = CMResponse(eMsgID = EMsg.ClientServerList, client_obj = client_obj)

    serverlist_count = 14

    packet.data = struct.pack('<I',
                              serverlist_count)

    # FIXME should really only send the appropriate servers based on the protocol or steamui version

    packet.data += struct.pack('I', EServerType.AM) + ip_port_to_packet_format(globalvars.server_ip, 27017)
    packet.data += struct.pack('I', EServerType.CM) + ip_port_to_packet_format(globalvars.server_ip, 27017)
    packet.data += struct.pack('I', EServerType.UFS) + ip_port_to_packet_format(globalvars.server_ip, 27017)
    packet.data += struct.pack('I', EServerType.DP) + ip_port_to_packet_format(globalvars.server_ip, 27017)
    packet.data += struct.pack('I', EServerType.contentstats) + ip_port_to_packet_format(globalvars.server_ip, 27017)
    packet.data += struct.pack('I', EServerType.PICS) + ip_port_to_packet_format(globalvars.server_ip, 27017)
    packet.data += struct.pack('I', EServerType.AppInformation) + ip_port_to_packet_format(globalvars.server_ip, 27017)
    packet.data += struct.pack('I', EServerType.WG) + ip_port_to_packet_format(globalvars.server_ip, 27017)
    packet.data += struct.pack('I', EServerType.FS) + ip_port_to_packet_format(globalvars.server_ip, 27017)
    packet.data += struct.pack('I', EServerType.VS) + ip_port_to_packet_format(globalvars.server_ip, 27017)
    packet.data += struct.pack('I', EServerType.Shell) + ip_port_to_packet_format(globalvars.server_ip, 27017)
    packet.data += struct.pack('I', EServerType.ATS) + ip_port_to_packet_format(globalvars.server_ip, 27017)
    packet.data += struct.pack('I', EServerType.Client) + ip_port_to_packet_format(globalvars.server_ip, 27017)
    packet.data += struct.pack('I', EServerType.BS) + ip_port_to_packet_format(globalvars.server_ip, 27017)

    return packet


def build_ClientChangePasswordResponse(cmserver_obj, client_obj: Client, error_code):

    packet = CMResponse(eMsgID = EMsg.ClientPasswordChangeResponse, client_obj = client_obj)

    packet.data = struct.pack('<I',
                              error_code)
    return packet


def build_GetAppOwnershipTicketResponse(cmserver_obj, client_obj: Client, appID):
    """
    struct MsgClientGetAppOwnershipTicketResponse_t
    {
      EResult m_eResult;
      uint32 m_nAppID;
      uint32 m_cubTicketLength;
      uint32 m_cubSignatureLength;
    };
    """
    packet = CMResponse(eMsgID = EMsg.ClientGetAppOwnershipTicketResponse, client_obj = client_obj)
    # FIXME:  Need to check database for apps owned by user, need to determine when a signature gets added and when it does not
    # error_code = database.check_user_owns_app(client_obj.steamID, appID)

    packet.data = struct.pack('<I',
                              EResult.OK)
    packet.data += struct.pack('<I',
                               appID)

    globalSteamID = int(client_obj.steamID * 2).to_bytes(4, 'little') + client_obj.clientID2.to_bytes(4, 'little')

    appOwnershipTicket = Steam3AppOwnershipTicket(
            ticket_length = 48,
            steam_id = struct.unpack("<Q",globalSteamID)[0],
            ticket_version = 2,
            app_id = appID,
            public_ip = client_obj.publicIP,
            private_ip = client_obj.privateIP,
            app_ownership_ticket_flags = 0,
            time_issued = get_current_time_uint32(),
            time_expire = add_time_to_current_uint32(minutes = 60))

    # Add it to the registry if it does not exist, otherwise use the unexpired ticket
    # result = client_obj.set_DBappTicket(appID, appOwnershipTicket)

    # if result is False:
    serialized_ticket, signature_length = appOwnershipTicket.serialize(True)
    # else:
    #    serialized_ticket = result.serialize()

    packet.data += struct.pack('<II',
                               len(serialized_ticket) - signature_length,
                               signature_length)

    packet.data += serialized_ticket

    return packet



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
    if isVersion2:
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
        packet.data = data.serialize
        return packet

    cmserver_obj.log.error(f"User {client_obj.steamID} does not have an email address - How could this happen?!")
    return -1