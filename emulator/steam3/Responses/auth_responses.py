import random
import hashlib
import secrets
import socket
import string
import struct
import sys
import traceback
from datetime import datetime
from random import getrandbits

import globalvars
from steam3 import utilities
from steam3.ClientManager.client import Client
from steam3.Types.Objects.AppOwnershipTicket import Steam3AppOwnershipTicket
from steam3.Types.Objects.PreProtoBuf.gameConnectToken import GameConnectToken
from steam3.Types.emsg import EMsg
from steam3.Types.steam_types import EResult, EServerType
from steam3.cm_packet_utils import CMProtoResponse, CMResponse
from steam3.messages.MsgClientEmailAddrInfo import MsgClientEmailAddrInfo
from steam3.messages.responses.MsgClientGetAppOwnershipTicket_Response import GetAppOwnershipTicketResponse
from steam3.messages.responses.MsgClientLogon_Response import LogonResponse
from steam3.utilities import add_time_to_current_uint32, create_GlobalID, generate_64bit_token, get_current_time_uint32, ip_port_to_packet_format
from steam3.protobufs.steammessages_clientserver_login_pb2 import CMsgClientLogonResponse


def build_logon_response(client_obj, client_address, eresult, is_anon = False, proto = False):
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
    response.steam_id = client_obj.steamID
    response.client_id = client_obj.clientID2
    response.public_ip = int.from_bytes(socket.inet_aton(client_address[0]), 'little')
    response.server_time = get_current_time_uint32()
    response.is_anon = is_anon

    if not is_anon:
        response.account_flags = client_obj.get_accountflags()

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


def build_client_logoff(client_obj, client_address):
    packet = CMResponse(eMsgID = EMsg.ClientLoggedOff, client_obj = client_obj)

    packet.data = struct.pack('I',
                              EResult.OK)

    return packet


def build_account_info_response(cmserver_obj, client_obj: Client, pkt_nickname = None):
    packet = CMResponse(eMsgID = EMsg.ClientAccountInfo, client_obj = client_obj)

    nickname = client_obj.check_username(pkt_nickname)  # grab the nickname since we dont have it during login

    name = nickname.encode('latin-1')  # user nickname
    # print(f"nickname: {nickname}")
    # TODO 2005 ONLY CONTAINS NICKNAME! NEED TO FIGURE OUT WHEN LANGUAGE WAS ADDED
    # FIXME Official Steam used the clients IP address to set the country, which is then used for purchases and such

    if cmserver_obj.config['override_ip_country_region'].lower() == 'false':
        lang = utilities.get_country_code(client_obj.ip_port[0])
    else:
        lang = cmserver_obj.config['override_ip_country_region']  # 2 letter country code, used for checking restrictions

    # TODO implement these custom fields, it seems 2009+ has an option for these fields, not sure  what steam does with the data
    # Optional fields: hashed password components
    """
    salt_password = secrets.token_bytes(8)  # Simulate a random salt (8 bytes)
    sha_digest_password = hashlib.sha1(b"example_password").digest()  # Simulated SHA-1 digest (20 bytes)"""

    packet.data = b"\x00" + name + b'\x00' + lang.upper().encode('latin-1') + b'\x00'

    return packet


def build_old_GameConnectToken_response(client_obj):
    """This is the old connecttoken packet, it contains a single token with no timestamp"""
    packet = CMResponse(eMsgID = EMsg.ClientGameConnectToken, client_obj = client_obj)

    # Below is the bytes of an actual token
    # data.extend(b'\x2a\xab\xf7\x04\xa6\x60\xde\xb4\x70\x0f\x45\x00\x01\x00\x10\x01') # Taken from ymgve 2005 packet dump
    # FIXME grab from database
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

    # license_test = License_Deprecated(
    #        package_id = 76,
    #        time_created = get_current_time_uint32(),
    #        time_next_process = 0,
    #        minute_limit = 0,
    #        minutes_used = 0,
    #        payment_method = int(EPaymentMethod.CreditCard),
    #        purchase_country_code = 'US',
    #        flags = int(ELicenseFlags.NONE),
    #        license_type = int(ELicenseType.SinglePurchase)
    # )
    # packet.data += license_test.serialize()

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

    client_obj.set_new_sessionkey(generate_64bit_token().encode('latin-1'))

    packet.data = client_obj.session_token

    return packet


def build_MsgClientServerList(cmserver_obj, client_obj: Client):
    packet = CMResponse(eMsgID = EMsg.ClientServerList, client_obj = client_obj)

    serverlist_count = 29

    packet.data = struct.pack('<I',
                              serverlist_count)

    # FIXME should really only send the appropriate servers based on the protocol or steamui version

    packet.data += struct.pack('I', EServerType.AM) + ip_port_to_packet_format(globalvars.server_ip, 27017)
    packet.data += struct.pack('I', EServerType.CM) + ip_port_to_packet_format(globalvars.server_ip, 27017)
    packet.data += struct.pack('I', EServerType.UFS) + ip_port_to_packet_format(globalvars.server_ip, 27017)
    packet.data += struct.pack('I', EServerType.UDS) + ip_port_to_packet_format(globalvars.server_ip, 27017)
    packet.data += struct.pack('I', EServerType.DP) + ip_port_to_packet_format(globalvars.server_ip, 27017)
    packet.data += struct.pack('I', EServerType.Econ) + ip_port_to_packet_format(globalvars.server_ip, 27017)
    packet.data += struct.pack('I', EServerType.GC) + ip_port_to_packet_format(globalvars.server_ip, 27017)
    packet.data += struct.pack('I', EServerType.contentstats) + ip_port_to_packet_format(globalvars.server_ip, 27017)
    packet.data += struct.pack('I', EServerType.PICS) + ip_port_to_packet_format(globalvars.server_ip, 27017)
    packet.data += struct.pack('I', EServerType.LBS) + ip_port_to_packet_format(globalvars.server_ip, 27017)
    packet.data += struct.pack('I', EServerType.AppInformation) + ip_port_to_packet_format(globalvars.server_ip, 27017)
    packet.data += struct.pack('I', EServerType.WG) + ip_port_to_packet_format(globalvars.server_ip, 27017)
    packet.data += struct.pack('I', EServerType.FS) + ip_port_to_packet_format(globalvars.server_ip, 27017)
    packet.data += struct.pack('I', EServerType.VS) + ip_port_to_packet_format(globalvars.server_ip, 27017)
    packet.data += struct.pack('I', EServerType.Shell) + ip_port_to_packet_format(globalvars.server_ip, 27017)
    packet.data += struct.pack('I', EServerType.Community) + ip_port_to_packet_format(globalvars.server_ip, 27017)
    packet.data += struct.pack('I', EServerType.ATS) + ip_port_to_packet_format(globalvars.server_ip, 27017)
    packet.data += struct.pack('I', EServerType.Client) + ip_port_to_packet_format(globalvars.server_ip, 27017)
    packet.data += struct.pack('I', EServerType.CS) + ip_port_to_packet_format(globalvars.server_ip, 27017)
    packet.data += struct.pack('I', EServerType.BS) + ip_port_to_packet_format(globalvars.server_ip, 27017)

    # 2010 stuff
    packet.data += struct.pack('I', EServerType.MPAS) + ip_port_to_packet_format(globalvars.server_ip, 27017)
    packet.data += struct.pack('I', EServerType.GCH) + ip_port_to_packet_format(globalvars.server_ip, 27017)
    packet.data += struct.pack('I', EServerType.MMS) + ip_port_to_packet_format(globalvars.server_ip, 27017)
    packet.data += struct.pack('I', EServerType.UCM) + ip_port_to_packet_format(globalvars.server_ip, 27017)
    packet.data += struct.pack('I', EServerType.Trade) + ip_port_to_packet_format(globalvars.server_ip, 27017)
    packet.data += struct.pack('I', EServerType.CRE) + ip_port_to_packet_format(globalvars.server_ip, 27017)
    packet.data += struct.pack('I', EServerType.UGSAggregate) + ip_port_to_packet_format(globalvars.server_ip, 27017)
    packet.data += struct.pack('I', EServerType.Quest) + ip_port_to_packet_format(globalvars.server_ip, 27017)
    packet.data += struct.pack('I', EServerType.Steam2Emulator) + ip_port_to_packet_format(globalvars.server_ip, 27017)
    return packet


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

    global_steam_id = create_GlobalID(client_obj.steamID * 2, client_obj.clientID2)
    ticket_version = 4 if globalvars.steamui_ver > 1238 else 2

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
        packet.data = data.serialize()
        return packet

    cmserver_obj.log.error(f"User {client_obj.steamID} does not have an email address - How could this happen?!")
    return -1


def build_ClientNewLoginKey(cmserver_obj, client_obj: Client):
    """
    Builds the MsgClientNewLoginKey_t structure.

    :param cmserver_obj: The CM server object containing relevant data.
    :param client_obj: The client object containing relevant data.

    loginkey code was taken from TINServer.
    """
    try:
        packet = CMResponse(eMsgID = EMsg.ClientNewLoginKey, client_obj = client_obj)

        # Generate the unique ID for the login key
        unique_id = secrets.token_bytes(4)

        # Seed data and Steam global ID for the digest
        seed = struct.pack("<I", random.randint(0, 0xFFFFFFFF))  # Random 4-byte seed
        steam_global_id = struct.pack("<Q", client_obj.steamID + client_obj.clientID2)  # Steam Global ID (uint64)

        # Generate the SHA-1 digest
        digester = hashlib.sha1()
        digester.update(seed)
        digester.update(steam_global_id)
        digester.update(seed)
        digest = digester.digest()

        # Process the digest to create the login key
        login_key = [(digest[i] % 95) + 32 for i in range(20)]
        login_key_bytes = bytes(login_key)  # Convert to a bytes object

        # Save loginkey to client object and database
        client_obj.set_new_loginkey(unique_id, login_key_bytes[:-1].decode('ascii'))

        # Pack unique_id and login_key_bytes into the packet data
        packet.data = struct.pack("<I20s", int.from_bytes(unique_id, "little"), login_key_bytes) + b'\x00'

        return packet
    except Exception as e:
        cmserver_obj.log.error(f"Error building ClientNewLoginKey: {e}")
        return -1