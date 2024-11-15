import binascii
import hashlib
import os
import re
import struct

import globalvars
import steam3
import steam3.globals
import steam3.globals as cm_globalvars
import utils
from steam3 import config, database
from steam3.ClientManager import Client_Manager
from steam3.ClientManager.client import Client
from steam3.Responses.purchase_responses import build_GetPurchaseReceiptsResponse
from steam3.Types import get_enum_name
from steam3.Types.Objects.AppOwnershipTicket import Steam3AppOwnershipTicket
from steam3.Types.community_types import PersonaStateFlags, PlayerState
from steam3.Types.steam_types import EInstanceFlag, EResult, EType, EUniverse
from steam3.Types.steamid import SteamID
from steam3.cm_packet_utils import CMPacket, CMResponse, ExtendedMsgHdr
from steam3.messages.ClientAnonLogOn_Deprecated import ClientAnonLogOn_Deprecated
from steam3.messages.MsgClientAnonUserLogOn_Deprecated import ClientAnonUserLogOn_Deprecated
from steam3.messages.MsgClientCreateAccount3 import ClientCreateAccount3
from steam3.messages.MsgClientInformOfCreateAccount import ClientInformOfCreateAccount
from steam3.messages.MsgClientLogOnWithCredentials_Deprecated import ClientLogOnWithCredentials_Deprecated
from steam3.Responses.vac_responses import build_vacbanstatus
from steam3.Responses.general_responses import build_ClientEncryptPct_response, build_ClientMarketingMessageUpdate, build_GeneralAck, build_General_response, build_client_newsupdate_response, build_cmserver_list_response, build_system_message
from steam3.Responses.friends_responses import build_friendslist_response, build_persona_message, send_statuschange_to_friends
from steam3.Responses.auth_responses import build_ClientChangePasswordResponse, build_CreateAccountResponse, build_GameConnectTokensResponse, build_GetAppOwnershipTicketResponse, build_LicenseResponse, build_MsgClientServerList, build_MsgClientSessionToken, build_OneTimeWGAuthPassword, build_account_info_response, build_client_logoff, build_emailaddressinfo, build_login_failure, build_login_response, build_old_GameConnectToken_response
from steam3.Responses.guestpass_responses import build_updated_guestpast_list_request
from steam3.utilities import is_valid_email, read_until_null_byte


def handle_ClientLogin(cmserver_obj, packet: CMPacket, client_obj: Client, eresult = 1, machineID_info = None):
    request = packet.CMRequest
    client_address = client_obj.ip_port

    cmserver_obj.sendReply(client_obj, [build_login_response(client_obj, client_address, eresult)])
    appid_range_list = client_obj.login_User(cmserver_obj, machineID_info)

    cmserver_obj.sendReply(client_obj, [build_client_newsupdate_response(client_obj)])

    cmserver_obj.sendReply(client_obj, [build_account_info_response(cmserver_obj, client_obj)])

    cmserver_obj.sendReply(client_obj, [build_emailaddressinfo(cmserver_obj, client_obj)])

    # Check for any vacbans on the account
    if appid_range_list:
        for firstappid, lastappid in appid_range_list:
            cmserver_obj.sendReply(client_obj, [build_vacbanstatus(client_obj, firstappid, lastappid)])
            cmserver_obj.sendReply(client_obj, [build_vacbanstatus(client_obj, firstappid, lastappid, True)])  # vacbanstatus2
    else:
        cmserver_obj.sendReply(client_obj, [build_vacbanstatus(client_obj, 0, 0)])
        cmserver_obj.sendReply(client_obj, [build_vacbanstatus(client_obj, 0, 0, True)])  # vacbanstatus2

    cmserver_obj.sendReply(client_obj, [build_friendslist_response(client_obj)])

    cmserver_obj.sendReply(client_obj, [build_LicenseResponse(client_obj)])

    cmserver_obj.sendReply(client_obj, [build_updated_guestpast_list_request(client_obj)])

    cmserver_obj.sendReply(client_obj, [build_GetPurchaseReceiptsResponse(client_obj)])

    # TODO send after mid 2008: ClientPreviousClickAndBuyAccount b'&\x03\x00\x00$\x02\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xef\x1d\x98\x00\x01\x01\x00\x10\x01\t\xe0A\x00\x00\x00MessageObject\x00\x07AccountNum\x00rUl\x06\x00\x00\x00\x00\x01CountryCode\x00US\x00\x07PaymentID\x00\xcfCn]\xfaW\x80\x01\x01State\x00WA\x00\x08\x08'

    # TODO send after 10/2009: ClientAppMinutesPlayedData b'\x83\x15\x00\x00$\x02\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xefmw\xea\x02\x01\x00\x10\x01\xfc\xdf\x8b\x00\x16\x00\x00\x00\xb8\x01\x00\x00\x15\x06\x00\x00\x00\x00\x00\x00\xf4\x01\x00\x00\x96\x00\x00\x00\x00\x00\x00\x00\x1c\xa2\x00\x00A\x05\x00\x00\x00\x00\x00\x00\xd0\x11\x00\x00\x82\x00\x00\x00\x00\x00\x00\x00\x14#\x00\x00;\x01\x00\x00\x00\x00\x00\x00d2\x00\x00J\x00\x00\x00\x00\x00\x00\x00>D\x00\x00\x12\x03\x00\x00\x00\x00\x00\x00DH\x00\x00}\x00\x00\x00\x00\x00\x00\x00\xb8V\x00\x00B\x01\x00\x00\x00\x00\x00\x00\xb4_\x00\x00 \x00\x00\x00\x00\x00\x00\x00\x84g\x00\x00(\x00\x00\x00\x00\x00\x00\x00\xb0h\x00\x00,\x00\x00\x00\x00\x00\x00\x00\xfcq\x00\x00v\x00\x00\x00\x00\x00\x00\x00h~\x00\x00{\x01\x00\x00\x00\x00\x00\x00L\x81\x00\x00[\x00\x00\x00\x00\x00\x00\x00\x88\x90\x00\x00\xf9\x00\x00\x00\x00\x00\x00\x00\x90\x01\x00\x00\x89\x01\x00\x00\x89\x01\x00\x00,\x92\x00\x00\xc4\x00\x00\x00\x00\x00\x00\x00(\xa0\x00\x00\xbe\x00\x00\x00\x00\x00\x00\x00\x18\x92\x00\x00\xdd\x00\x00\x00\x00\x00\x00\x00\x92\x0e\x00\x00a\x00\x00\x00\x00\x00\x00\x00,\x97\x00\x00R\x00\x00\x00R\x00\x00\x00'
    if globalvars.steamui_ver <= 52: # FIXME, figure out when this packet is deprecated, 52 is random guess
        cmserver_obj.sendReply(client_obj, [build_old_GameConnectToken_response(client_obj)])
    else:
        cmserver_obj.sendReply(client_obj, [build_GameConnectTokensResponse(client_obj)])

    cmserver_obj.sendReply(client_obj, [build_cmserver_list_response(client_obj)])

    cmserver_obj.sendReply(client_obj, [build_OneTimeWGAuthPassword(cmserver_obj, client_obj)])

    # TODO send after 10/2009: ClientNewLoginKey b'W\x15\x00\x00$\x02\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xefmw\xea\x02\x01\x00\x10\x01\xfc\xdf\x8b\x00\xe7\xb8\x15\x0btkYSOakV+9QgDQIydsw\x00'

    cmserver_obj.sendReply(client_obj, [build_MsgClientSessionToken(cmserver_obj, client_obj)])

    cmserver_obj.sendReply(client_obj, [build_MsgClientServerList(cmserver_obj, client_obj)])

    cmserver_obj.sendReply(client_obj, [build_ClientEncryptPct_response(client_obj)])

    # TODO send this after 01/2009 ClientMarketingMessageUpdate
    if globalvars.steamui_ver <= 689: # Figure out which SteamUI version when this packet was TRULY implemented
        cmserver_obj.sendReply(client_obj, [build_ClientMarketingMessageUpdate(client_obj)])

    friends_list_steamids = []

    cmserver_obj.sendReply(client_obj, [build_persona_message(client_obj, PersonaStateFlags.status | PersonaStateFlags.playerName |PersonaStateFlags.lastSeen | PersonaStateFlags.presence, [client_obj.steamID])])
    for friend_entry, friend_relationship in client_obj.get_friends_list_from_db():
        friend_steamid = int(friend_entry.accountID)
        if friend_steamid in Client_Manager.clients_by_steamid:
            friends_list_steamids.append(friend_steamid)
            cmserver_obj.sendReply(Client_Manager.clients_by_steamid[friend_steamid], [build_persona_message(Client_Manager.clients_by_steamid[friend_steamid], PersonaStateFlags.status | PersonaStateFlags.playerName | PersonaStateFlags.sourceId |PersonaStateFlags.lastSeen | PersonaStateFlags.presence, [client_obj.steamID])])
            cmserver_obj.sendReply(client_obj, [build_persona_message(client_obj, PersonaStateFlags.status | PersonaStateFlags.playerName | PersonaStateFlags.sourceId | PersonaStateFlags.lastSeen | PersonaStateFlags.presence, friends_list_steamids)])

    send_statuschange_to_friends(client_obj, cmserver_obj, Client_Manager, PlayerState.online)

    # send 755 - set heartbeat rate
    return -1


def handle_New_ClientLogin(cmserver_obj, packet: CMPacket, client_obj: Client):
    # TODO not sure if this packet was ever used
    """
    struct __attribute__((packed)) __attribute__((aligned(2))) MsgClientUserLogOnNew_t
    {
      uint32 m_unProtocolVer;
      uint32 m_unIPPrivateObfuscated;
      uint32 m_unIPPublic;
      uint64 m_ulLogonCookie;
      uint64 m_ulSteamID_TBD;
      char m_rgchAccountName[64];
      char m_rgchPassword[20];
      uint32 m_nClientVersion;
      uint32 m_nBootStrapperVersion;
      uint32 m_cellID;
      uint32 m_cPreviousConnections;
      uint8 m_nVersionMachineIDInfo;
      uint8 m_qosLevel;
    }; """
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved New Client Login [NoImp]")
    request = packet.CMRequest
    #user_id = client_ref.steamID

    protocol_ver = 0
    obfuscated_private_ip = None ^ 0xBAADF00D
    public_ip = 0
    qosLevel = 0
    accountName = b'' # 64 chars max
    password = b'' # 20 chars max
    steamID_TBD = 0 # 64bit
    language = b'' #null terminated
    versionmachineID_info = False # 1 byte
    clientVersion = 0
    bootstrapversion = 0
    cellid = 0 #4 byte

    return -1


def handle_AnonGameServerLogin(cmserver_obj, packet, client_obj):
    """ Dedicated Servers use this when logging in
    Not sure what the difference between anonlogin and anongameserverlogin is... 2008 shows they are different..
    steamui_457: b'\x10\x00\x01\x00\x9e\x14*\xf2\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00english\x00\xc9\x01\x00\x00'
    Respond only with the following packets in this order:
    logon response
    client news update
    client cmlist
    client encrypt pct
    """
    client_address = client_obj.ip_port

    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved Anonymous GameServer Login")
    request = packet.CMRequest
    try:
        message = ClientAnonLogOn_Deprecated(request.data[8:])
        client_obj.is_in_app = True
        #print(message)
    except:
        cmserver_obj.log.info(f"Error parsing ClientAnonLogOn!")
        pass

    cmserver_obj.sendReply(client_obj, [build_login_response(client_obj, client_address, EResult.OK)])
    cmserver_obj.sendReply(client_obj, [build_client_newsupdate_response(client_obj)])
    cmserver_obj.sendReply(client_obj, [build_cmserver_list_response(client_obj)])
    cmserver_obj.sendReply(client_obj, [build_ClientEncryptPct_response(client_obj)])
    return -1

def handle_AnonUserLogin(cmserver_obj, packet, client_obj):
    """This message is used during create account"""
    client_address = client_obj.ip_port

    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved Anonymous User Login")
    request = packet.CMRequest
    try:
        steamid_instance = request.clientId2.to_bytes(4, "little")
        #steamid_accountid = request.accountID.to_bytes(4, "little")
        #full_steamid = steamid_accountid + steamid_instance
        if SteamID.get_type_from_bytes(steamid_instance) == EType.ANONUSER:
            #print(request.accountID, request.clientId2)
            #current_globalid = struct.pack("<Q", full_steamid)
            #anon_globalID = SteamID.get_new_anon_global_id(SteamID(current_globalid))
            #anon_globalID = anon_globalID.to_bytes(8, "little")

            cm_globalvars.anonUsersCount += 1
            client_obj.accountID = cm_globalvars.anonUsersCount #int(anon_globalID[0:4]).from_bytes(4, "little")
            #client_obj.clientID2 = int(anon_globalID[4:8]).from_bytes(4, "little")

            message = ClientAnonUserLogOn_Deprecated(request.data)
            client_obj.is_in_app = False
            #print(message)

            cmserver_obj.sendReply(client_obj, [build_client_newsupdate_response(client_obj)])
            cmserver_obj.sendReply(client_obj, [build_login_response(client_obj, client_address, EResult.OK)])
    except Exception as e:
        cmserver_obj.log.info(f"Error parsing ClientAnonUserLogOn_Deprecated!\n Error: {e}")

    return -1

def handle_RegisterAuthTIcket(cmserver_obj, packet: CMPacket, client_obj: Client):
    """data: b'\x19\x00\x01\x00\xa4\x00\x00\x00\x00\x00\x00\x00\x08\x00\x00\x00\x01\x00\x10\x01\x07
    \x00\x00\x00\xe8\xe0\x87H\xe8\xe0\x87H\x00\x00\x00\x00D\xb4\xdffT\xc2\xdff\x9e\xb8\xcfY\r\x82XM
    \xde\x0e\x84\xb15\xcb\x85L\xfcCS\x89\x0c\xf8>\x94e\xa4\xfbn\xa6\x0b\x04\x8c\xfd\xf3\x84\xb1D4
    \xce\x17\x97uwa(\xc8ur\xfb\xfa\xd6\xc4C\xfes\xe7*\x16\x01\x15\x82\xeeQ\x12\x9a\xef\xc9\xc4q\xb7
    \xef\xe6\xcc\x93\x8b\x9b&b\x03Sl\x19\xb9Nx\xf9\x7f\xf0qy\x03T3\x93^\x1e\xe8\xef\xed\x83\x9c`\n2
    \xd1\x948\xb6\x1f\xb1\xd9m\xd59g\xd5\x0e\x8aZla\xd3c\xe3\xa0\xbc\x04x'"""
    client_address = client_obj.ip_port

    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved Client Login With Credentials")
    request = packet.CMRequest
    data = request.data
    protocol_version = struct.unpack_from('<I', data, 0)
    ownership_ticket = Steam3AppOwnershipTicket()
    ownership_ticket.parse_ticket(data[4:])

    return [build_GeneralAck(packet, client_address, cmserver_obj.serversocket)]
def handle_LogOff(cmserver_obj, packet: CMPacket, client_obj: Client):
    request = packet.CMRequest
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved Client Logoff request")
    client_obj.logoff_User(cmserver_obj)

    return [build_client_logoff(client_obj, client_address)]


def handle_ClientLogOn_WithCredentials(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    struct MsgClientLogOnWithCredentials_t
    {
      uint32 m_unProtocolVer;
      uint32 m_unIPPrivateObfuscated;
      uint32 m_unIPPublic;
      uint64 m_ulLogonCookie;
      uint32 m_unTicketLength;
      char m_rgchAccountName[64];
      char m_rgchPassword[20];
      uint32 m_qosLevel;
    };
    """
    client_address = client_obj.ip_port

    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved Client Login With Credentials")
    request = packet.CMRequest
    data = request.data

    logon = ClientLogOnWithCredentials_Deprecated(data)

    print(logon)

    client_obj.protocol_version = logon.protocol
    client_obj.publicIP = logon.public_ip
    client_obj.privateIP = logon.obfuscated_ip
    machineID_info = None
    if globalvars.steamui_ver >= 382 and logon.protocol < 65555:
        machineID_object = logon.machine_id.get_message_objects()

        # Assuming each message object is a dictionary and taking the first one for example
        # if machineID_object and isinstance(machineID_object[0], dict):
        obj = machineID_object[0]
        machineID_info = (obj.get('BB3', 'N/A'), obj.get('FF2', 'N/A'), obj.get('3B3', 'N/A'))

    # if request.clientId2 == 0x01100001:  # if it is a normal client, do normal login. otherwise just send login response
    #    handle_ClientLogin(cmserver_obj, packet, client_obj)

    # TODO: Check the username in the packet to the username in the ticket
    #   Do any other checks which may prevent unauthorized users from stealing accounts and/or logging into other peoples accounts
    #   Such as figuring out a way to prevent tickets from being copy/pasted into a custom client to login to someone elses account
    if globalvars.steamui_ver == 333 or logon.protocol >= 65558:
        error_code = database.compare_password_digests(logon.email, logon.ticket.password_digest_hex)
    else:
        error_code = database.check_user_information(logon.email, logon.password)

    if error_code != 1:
        cmserver_obj.log.warning(f"({client_address[0]}:{client_address[1]}): Failed Login, Incorrect Credentials Or User Does not Exist")
        cmserver_obj.sendReply(client_obj, [build_login_failure(client_obj, error_code)], b"\x05")
        cmserver_obj.serversocket.disconnect()
        return -1

    handle_ClientLogin(cmserver_obj, packet, client_obj, error_code, machineID_info)

    return -1

def handle_ClientChangeStatus(cmserver_obj, packet: CMPacket, client_obj: Client):
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"{client_address} Client Change Status Request")

    user_state = int.from_bytes(request.data[0:1], 'little')

    pkt_nickname = request.data[1:].decode('latin-1').rstrip("\x00")

    if user_state > 0 or user_state is not None:
        nickname = client_obj.update_status_info(cmserver_obj, PlayerState(user_state), username = pkt_nickname)
    else:
        client_obj.exit_app(cmserver_obj)

    # Create reply
    return build_account_info_response(cmserver_obj, client_obj, pkt_nickname)


def handle_ClientChangePassword(cmserver_obj, packet: CMPacket, client_obj: Client):
    """2024-06-06 16:04:40     CMUDP27017    CRITICAL packetid: ClientPasswordChange (804)
    data: b'123456\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x0012345\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'"""

    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"{client_address} Client Change Password Request")

    original_password = read_until_null_byte(request.data[0:19])
    new_password = read_until_null_byte(request.data[20:])

    # FIXME deal with this properly currently in version 479, it sends the changepassword to the auth and CM... need to figure out what to do

    error_code = 1 # database.check_user_information(Client.email, logon.password)

    #if error_code != 1:
    #    Incorrect original password!
    #    cmserver_obj.sendReply(client_obj, [build_login_failure(packet.CMRequest, error_code)])
    #    cmserver_obj.serversocket.disconnect()
    #    return -1

    return build_ClientChangePasswordResponse(cmserver_obj, client_obj, error_code)


def handle_GetAppOwnershipTicket(cmserver_obj, packet: CMPacket, client_obj: Client):
    """data: b'\xcd\x00\x00\x00'"""
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"{client_address} App Ownership Ticket Request")
    appID, = struct.unpack('<I', request.data)

    # FIXME This is a hack to prevent versions 521 and 522 from crashing during login.. not sure of the side effects of this
    """if globalvars.steamui_ver == 521 or globalvars.steamui_ver == 522:
        return -1
    else:"""
    return build_GetAppOwnershipTicketResponse(cmserver_obj, client_obj, appID)


def handle_InformOfCreateAccount(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    data: b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00cmtest_2\x0012345\x00teste1@test.com\x00What is the name of your pet?\x00rees\x00'"""
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"{client_address} Informed of Creating an New Account")

    parsed_message = ClientInformOfCreateAccount(request.data)

    #cmserver_obj.log.debug(f"{parsed_message}")

    build_GeneralAck(packet, client_address, cmserver_obj.serversocket)
    return -1

def handle_CreateAccount2(cmserver_obj, packet: CMPacket, client_obj: Client):
    """Same as CreateAccount3 except the response only contains a status and no steamid"""
    return handle_CreateAccount(cmserver_obj, packet, client_obj, True)


def handle_CreateAccount(cmserver_obj, packet: CMPacket, client_obj: Client, isVersion2 = False):
    """ data: b'\x00cmtest_4\x0012345\x00dfsad@fds.com\x00What is the name of your school?\x00erter\x00'"""
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"{client_address} Create New Account V3")

    parsed_message = ClientCreateAccount3(request.data)

    cmserver_obj.log.debug(f"{parsed_message}")

    steamID = 0
    result = 0

    # TODO NOTE:
    #  these are the max values for each:
    #  Q_strncpy(this->m_rgchAccountName, pchAccountName, 64);
    #   Q_strncpy(this->m_rgchPassword, pchPassword, 20);
    #   Q_strncpy(this->m_rgchEmail, pchEmail, 322);
    #   Q_strncpy(this->m_rgchQuestion, pchQuestion, 255);
    #   Q_strncpy(this->m_rgchAnswer, pchAnswer, 255);

    # Check if the CreateAccount function is enabled
    if not steam3.globals.function_status['CreateAccount']['Enabled']:
        result = EResult.Disabled

    # Ensure the password is UTF-8 compatible
    try:
        parsed_message.password.encode('utf-8')
    except UnicodeEncodeError:
        result = EResult.IllegalPassword

    # Ensure the username contains only alphanumeric characters and underscores
    if not all(char.isalnum() or char == '_' for char in parsed_message.username):
        result = EResult.InvalidName

    # Ensure the email does not contain any illegal characters
    if not is_valid_email(parsed_message.email):
        result = EResult.InvalidEmail

    if result == 0:
        # Get password crypto variables
        # Generate a random 8-byte salt
        salt = os.urandom(8)
        # Hash the password with the salt
        hashed_password = hashlib.sha1(salt[:4] + parsed_message.password.encode() + salt[4:]).digest()
        password_digest = binascii.hexlify(hashed_password[0:16]).decode()
        # Convert salt to hex for storage
        password_salt = binascii.hexlify(salt).decode()

        # Get personal question answer crypto variables
        # Generate a random 8-byte salt
        salt = os.urandom(8)
        # Hash the answer to the question with the salt
        hashed_answer = hashlib.sha1(salt[:4] + parsed_message.security_answer.encode() + salt[4:]).digest()
        answertoguestion_digest = binascii.hexlify(hashed_answer[0:16]).decode()
        # Convert salt to hex for storage
        answertoguestion_salt = binascii.hexlify(salt).decode()

        steamID, result = database.create_user(unique_username=parsed_message.username,
                                               account_email_address=parsed_message.email,
                                               personal_question=parsed_message.security_question,
                                               passphrase_salt=password_salt,
                                               salted_passphrase_digest=password_digest,
                                               answer_to_question_salt=answertoguestion_salt,
                                               salted_answer_to_question_digest=answertoguestion_digest)

        if steamID is not None:
            full_steamID = SteamID()
            full_steamID.set_accountID(steamID)
            full_steamID.set_universe(EUniverse(int(config['universe'])))
            full_steamID.set_type(EType.INDIVIDUAL)
            full_steamID.set_instance(EInstanceFlag.ALL)
            steamID = full_steamID.get_integer_format()
            print(steamID)
    else:
        cmserver_obj.log.warning(f"{client_address[0]}:{client_address[1]} - Account Creation Failed Due To Error: {get_enum_name(EResult, result)}")

    return build_CreateAccountResponse(client_obj, result, steamID, isVersion2)