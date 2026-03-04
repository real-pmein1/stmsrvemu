import binascii
import hashlib
import os
import struct
import traceback

import globalvars
import steam3
import steam3.globals
import steam3.globals as cm_globalvars
from steam3.messages.responses.MsgClientLoggedOff import MsgClientLoggedOff
from steam3 import config, database
from steam3.ClientManager import Client_Manager
from steam3.ClientManager.client import Client
from steam3.Responses.purchase_responses import build_GetPurchaseReceiptsResponse
from steam3.Types import get_enum_name
from steam3.Types.community_types import PersonaStateFlags, PlayerState, RequestedPersonaStateFlags_self
from steam3.Types.steam_types import EInstanceFlag, EResult, EType, EUniverse
from steam3.Types.wrappers import AccountID
from steam3.Types.steamid import SteamID
from steam3.cm_packet_utils import CMPacket
from steam3.messages.MsgClientAnonLogOn_Deprecated import MsgClientAnonLogOn_Deprecated
from steam3.messages.MsgClientAnonUserLogOn_Deprecated import ClientAnonUserLogOn_Deprecated
from steam3.messages.MsgClientCreateAccount3 import ClientCreateAccount3
from steam3.messages.MsgClientInformOfCreateAccount import ClientInformOfCreateAccount
from steam3.messages.MsgClientLogOnWithCredentials_Deprecated import ClientLogOnWithCredentials_Deprecated
from steam3.Responses.vac_responses import build_vacbanstatus
from steam3.Responses.general_responses import build_ClientEncryptPct_response, build_ClientMarketingMessageUpdate, build_ClientServersAvailable, build_GeneralAck,  build_MsgClientRequestedStats, build_MsgClientServerList, build_client_newsupdate_response, build_cmlist_response
from steam3.Responses.friends_responses import build_friendslist_response, build_persona_message, send_statuschange_to_friends
from steam3.Responses.auth_responses import build_ClientChangePasswordResponse, build_ClientLicenseList_response, build_ClientNewLoginKey,  build_CreateAccountResponse, build_GameConnectTokensResponse, build_GetAppOwnershipTicketResponse, build_MsgClientSessionToken, build_OneTimeWGAuthPassword, build_account_info_response, build_client_logoff, build_emailaddressinfo, build_login_failure, build_logon_response, build_old_GameConnectToken_response
from steam3.Responses.guestpass_responses import build_updated_guestpast_list_request
from steam3.Responses.clan_responses import build_ClanState_from_db
from steam3.messages.MsgClientLogonWithHash import ClientLogonWithHash
from steam3.messages.MsgClientRegisterAuthTicketWithCM import MsgClientRegisterAuthTicketWithCM
from steam3.utilities import is_valid_email, read_until_null_byte
from steam3.protobufs.steammessages_clientserver_pb2 import CMsgClientGetAppOwnershipTicket
from steam3.protobufs.steammessages_clientserver_login_pb2 import CMsgClientLogon
from utilities.ticket_utils import Steam2Ticket


def handle_ClientLogin(cmserver_obj, packet: CMPacket, client_obj: Client, eresult=1, machineID_info=None):
    client_address = client_obj.ip_port
    messages = []

    # Track whether this client uses protobuf messages
    client_obj.is_proto = packet.is_proto

    vacban_appid_range_list = client_obj.login_User(cmserver_obj, machineID_info)
    Client_Manager.add_or_update_client(client_obj)

    # Build the common list of messages.
    cmserver_obj.sendReply(client_obj, [build_logon_response(client_obj, client_address, eresult, proto=packet.is_proto)])

    messages.extend([
        build_client_newsupdate_response(client_obj),
        build_account_info_response(cmserver_obj, client_obj),
        build_emailaddressinfo(cmserver_obj, client_obj)
    ])

    for firstappid, lastappid in vacban_appid_range_list:
        messages.append(build_vacbanstatus(client_obj, firstappid, lastappid))
        messages.append(build_vacbanstatus(client_obj, firstappid, lastappid, True))

    messages.extend([
        build_friendslist_response(client_obj),
        build_ClientLicenseList_response(client_obj),
        build_updated_guestpast_list_request(client_obj),
        build_GetPurchaseReceiptsResponse(client_obj)
    ])
    # TODO send after mid 2008: ClientPreviousClickAndBuyAccount b'&\x03\x00\x00$\x02\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xef\x1d\x98\x00\x01\x01\x00\x10\x01\t\xe0A\x00\x00\x00MessageObject\x00\x07AccountNum\x00rUl\x06\x00\x00\x00\x00\x01CountryCode\x00US\x00\x07PaymentID\x00\xcfCn]\xfaW\x80\x01\x01State\x00WA\x00\x08\x08'

    # TODO send after 10/2009: ClientAppMinutesPlayedData b'\x83\x15\x00\x00$\x02\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xefmw\xea\x02\x01\x00\x10\x01\xfc\xdf\x8b\x00\x16\x00\x00\x00\xb8\x01\x00\x00\x15\x06\x00\x00\x00\x00\x00\x00\xf4\x01\x00\x00\x96\x00\x00\x00\x00\x00\x00\x00\x1c\xa2\x00\x00A\x05\x00\x00\x00\x00\x00\x00\xd0\x11\x00\x00\x82\x00\x00\x00\x00\x00\x00\x00\x14#\x00\x00;\x01\x00\x00\x00\x00\x00\x00d2\x00\x00J\x00\x00\x00\x00\x00\x00\x00>D\x00\x00\x12\x03\x00\x00\x00\x00\x00\x00DH\x00\x00}\x00\x00\x00\x00\x00\x00\x00\xb8V\x00\x00B\x01\x00\x00\x00\x00\x00\x00\xb4_\x00\x00 \x00\x00\x00\x00\x00\x00\x00\x84g\x00\x00(\x00\x00\x00\x00\x00\x00\x00\xb0h\x00\x00,\x00\x00\x00\x00\x00\x00\x00\xfcq\x00\x00v\x00\x00\x00\x00\x00\x00\x00h~\x00\x00{\x01\x00\x00\x00\x00\x00\x00L\x81\x00\x00[\x00\x00\x00\x00\x00\x00\x00\x88\x90\x00\x00\xf9\x00\x00\x00\x00\x00\x00\x00\x90\x01\x00\x00\x89\x01\x00\x00\x89\x01\x00\x00,\x92\x00\x00\xc4\x00\x00\x00\x00\x00\x00\x00(\xa0\x00\x00\xbe\x00\x00\x00\x00\x00\x00\x00\x18\x92\x00\x00\xdd\x00\x00\x00\x00\x00\x00\x00\x92\x0e\x00\x00a\x00\x00\x00\x00\x00\x00\x00,\x97\x00\x00R\x00\x00\x00R\x00\x00\x00'

    # GameConnectToken responses based on SteamUI version.
    if globalvars.steamui_ver <= 52:  # FIXME, figure out when this packet is deprecated, 52 is random guess
        messages.append(build_old_GameConnectToken_response(client_obj))
    else:
        messages.append(build_GameConnectTokensResponse(client_obj))

    messages.extend([
        build_cmlist_response(client_obj),
        build_OneTimeWGAuthPassword(cmserver_obj, client_obj)
    ])

    if globalvars.steamui_ver >= 1238:
        messages.append(build_ClientNewLoginKey(cmserver_obj, client_obj, proto=client_obj.is_proto))

    messages.extend([
        build_MsgClientSessionToken(cmserver_obj, client_obj),
        build_MsgClientServerList(client_obj),
        build_ClientEncryptPct_response(client_obj)
    ])

    if globalvars.steamui_ver >= 689:  # TODO send this after 01/2009 client versions
        messages.append(build_ClientMarketingMessageUpdate(client_obj))

    messages.extend([
        build_MsgClientRequestedStats(client_obj),
        build_persona_message(
            client_obj,
            RequestedPersonaStateFlags_self,
            [client_obj.accountID]
        )
    ])

    # todo send all packets via multimsg, this is how retail steam works
    """if globalvars.steamui_ver >= 270:
        multi_packet = MultiMsg()
        multi_packet.targetJobID = -1
        multi_packet.sourceJobID = -1
        for msg in messages:
            multi_packet.add_message(msg)
        multi_packet.serialize()
        result = multi_packet
    else:"""

    for msg in messages:
        if msg is not None:  # Filter out None values from builder functions that failed
            cmserver_obj.sendReply(client_obj, [msg])
    result = -1

    # Send clan state updates for all clans the user is a member of
    try:
        _send_user_clan_states(cmserver_obj, client_obj)
    except Exception as e:
        cmserver_obj.log.warning(f"Failed to send clan states: {e}")

    # Handle friend list updates (common to both modes)
    # Send online friends' status to the logging-in user
    friendsListAccountIDs = []
    cmserver_obj.log.debug(f"Processing friends list for {client_obj.username} (accountID={client_obj.accountID})")
    cmserver_obj.log.debug(f"clientsByAccountID keys: {list(Client_Manager.clientsByAccountID.keys())}")

    for friend_entry, friend_relationship in client_obj.get_friends_list_from_db():
        # Use plain int for dictionary lookup (AccountID wrapper has different hash)
        friendAccountID = int(friend_entry.accountID)
        cmserver_obj.log.debug(f"Checking if friend {friendAccountID} is online...")
        if friendAccountID in Client_Manager.clientsByAccountID:
            cmserver_obj.log.debug(f"Friend {friendAccountID} IS online!")
            friendsListAccountIDs.append(friendAccountID)
            # Notify the online friend that this user just logged in
            friend_client = Client_Manager.clientsByAccountID[friendAccountID]
            if friend_client.objCMServer:
                cmserver_obj.log.debug(f"Notifying friend {friendAccountID} that {client_obj.username} logged in")
                # IMPORTANT: Use the friend's CM server to send, not the logging-in user's!
                friend_client.objCMServer.sendReply(
                    friend_client,
                    [build_persona_message(
                        friend_client,
                        PersonaStateFlags.status | PersonaStateFlags.playerName | PersonaStateFlags.sourceId |
                        PersonaStateFlags.lastSeen | PersonaStateFlags.presence,
                        [int(client_obj.accountID)]  # Convert to int for consistency
                    )]
                )
        else:
            cmserver_obj.log.debug(f"Friend {friendAccountID} is NOT online")

    # Send all online friends' statuses to the logging-in user (outside loop for efficiency)
    cmserver_obj.log.debug(f"Online friends to notify {client_obj.username} about: {friendsListAccountIDs}")
    if friendsListAccountIDs:
        cmserver_obj.log.debug(f"Building persona message about {len(friendsListAccountIDs)} online friends for {client_obj.username}")
        persona_msg = build_persona_message(
            client_obj,
            PersonaStateFlags.status | PersonaStateFlags.playerName | PersonaStateFlags.sourceId |
            PersonaStateFlags.lastSeen | PersonaStateFlags.presence,
            friendsListAccountIDs
        )
        cmserver_obj.log.debug(f"Persona message built: {persona_msg}, data length: {len(persona_msg.data) if hasattr(persona_msg, 'data') else 'N/A'}")
        cmserver_obj.log.debug(f"Sending persona message to {client_obj.username} via {type(cmserver_obj).__name__}")
        cmserver_obj.sendReply(client_obj, [persona_msg])
        cmserver_obj.log.debug(f"Persona message sent to {client_obj.username}")
    else:
        cmserver_obj.log.debug(f"No online friends to notify {client_obj.username} about")

    send_statuschange_to_friends(client_obj, cmserver_obj, Client_Manager, PlayerState.online)

    # Handle auto-accepted friend requests (for protocol > 65550)
    # Send full friends list and persona info to both users
    if hasattr(client_obj, 'auto_accepted_friends') and client_obj.auto_accepted_friends:
        cmserver_obj.log.info(f"Auto-accepted {len(client_obj.auto_accepted_friends)} friend requests for {client_obj.username}")
        # Refresh the friends list after auto-acceptance
        client_obj.get_friends_list_from_db()

        # Send FULL friends list to the logging-in user
        cmserver_obj.sendReply(client_obj, [build_friendslist_response(client_obj)])
        # Send persona info for all friends
        for friend_entry, _ in client_obj.friends_list:
            cmserver_obj.sendReply(client_obj, [build_persona_message(
                client_obj,
                PersonaStateFlags.status | PersonaStateFlags.playerName | PersonaStateFlags.sourceId |
                PersonaStateFlags.lastSeen | PersonaStateFlags.presence,
                [friend_entry.accountID]
            )])

        # Notify any online auto-accepted friends
        for auto_accepted_accountID in client_obj.auto_accepted_friends:
            friend_client = Client_Manager.get_client_by_accountID(auto_accepted_accountID)
            if friend_client and friend_client.objCMServer:
                # Refresh their friends list
                friend_client.get_friends_list_from_db()
                # Send them the FULL friends list
                friend_client.objCMServer.sendReply(friend_client, [build_friendslist_response(friend_client)])
                # Send persona info for all their friends
                for friend_entry, _ in friend_client.friends_list:
                    friend_client.objCMServer.sendReply(friend_client, [build_persona_message(
                        friend_client,
                        PersonaStateFlags.status | PersonaStateFlags.playerName | PersonaStateFlags.sourceId |
                        PersonaStateFlags.lastSeen | PersonaStateFlags.presence,
                        [friend_entry.accountID]
                    )])

    # Send pending chatroom/lobby invites to the user who just logged in
    try:
        if steam3.chatroom_manager:
            steam3.chatroom_manager.send_pending_invites_to_user(int(client_obj.steamID))
    except Exception as e:
        cmserver_obj.log.warning(f"Failed to send pending invites to {client_obj.steamID}: {e}")

    # (Optionally: send heartbeat packet (755) here if needed)
    return result


def handle_ClientLogin_PB(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle a client login Protobuf message (CMsgClientLogon).

    :param cmserver_obj: The CMServer instance handling the connection.
    :param packet: The CMPacket containing the Protobuf message.
    :param client_obj: The Client object associated with the connection.
    """
    # Extract client address
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received Client Login (Protobuf)")

    # Extract the Protobuf payload
    protobuf_payload = packet.CMRequest.data

    # Parse the Protobuf message
    client_logon_msg = CMsgClientLogon()
    try:
        client_logon_msg.ParseFromString(protobuf_payload)
    except Exception as e:
        cmserver_obj.log.error(f"Failed to parse CMsgClientLogon: {e}")
        cmserver_obj.log.debug(f"Raw Protobuf payload (hex): {protobuf_payload.hex()}")
        cmserver_obj.sendReply(client_obj, [build_login_failure(client_obj, EResult.InvalidParam)])
        return -1

    # Print all fields in the message for debugging
    cmserver_obj.log.debug("Parsed CMsgClientLogon message fields:")
    for field_desc, value in client_logon_msg.ListFields():
        # Format bytes fields for better readability
        if field_desc.name == "steam2_auth_ticket":
            ticket = Steam2Ticket(value[4:])
            client_obj.publicIP = ticket.public_ip_str
            client_obj.privateIP = ticket.client_ip_str
            cmserver_obj.log.debug(f"{field_desc.name}: {ticket}")
        else:
            cmserver_obj.log.debug(f"{field_desc.name}: {value}")

    # Extract authentication fields
    account_name = client_logon_msg.account_name if client_logon_msg.HasField('account_name') else None
    password = client_logon_msg.password if client_logon_msg.HasField('password') else None

    # Set protocol version if provided
    if client_logon_msg.HasField('protocol_version'):
        client_obj.protocol_version = client_logon_msg.protocol_version

    # Validate required fields for authentication
    if not account_name or not password:
        cmserver_obj.log.warning(f"({client_address[0]}:{client_address[1]}): Missing account_name or password in protobuf logon")
        cmserver_obj.sendReply(client_obj, [build_login_failure(client_obj, EResult.InvalidParam)])
        return -1

    # Authenticate user - the function tries both email and username lookup
    error_code, accountID = database.check_user_information_by_username_or_email(account_name, password)

    if error_code != 1:
        cmserver_obj.log.warning(f"({client_address[0]}:{client_address[1]}): Failed Login (Protobuf), Incorrect Credentials Or User Does not Exist")
        cmserver_obj.sendReply(client_obj, [build_login_failure(client_obj, error_code)])
        return -1

    # Validate accountID
    if accountID is None or accountID <= 0:
        cmserver_obj.log.error(f"({client_address[0]}:{client_address[1]}): ACCOUNT ID IS INVALID after successful auth!")
        cmserver_obj.sendReply(client_obj, [build_login_failure(client_obj, EResult.InvalidParam)])
        return -1

    # Set up the SteamID for the authenticated user
    tempvarSteamID = SteamID()
    client_obj.steamID = tempvarSteamID.create_normal_user_steamID(accountID, EUniverse.PUBLIC)

    # Track that this client uses protobuf messages
    client_obj.is_proto = packet.is_proto

    # Continue with normal login flow
    handle_ClientLogin(cmserver_obj, packet, client_obj, error_code)

    return -1


def handle_New_ClientLogin(cmserver_obj, packet: CMPacket, client_obj: Client):
    # TODO implement new client login. not sure if this packet was ever used
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
    print('!!!!!!!!New Client Login Packet is Not Implemented!!!!!!!!!')

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
    # FIXME we dont do anything with the anon login information, perhaps logging it would be wise..
        message = MsgClientAnonLogOn_Deprecated(request.data)
        if client_obj.steamID != None:
            client_obj.is_in_app = True
        #print(message)
    except:
        cmserver_obj.log.info(f"Error parsing ClientAnonLogOn!")
        reply = MsgClientLoggedOff(client_obj)
        return reply.to_clientmsg()

    cmserver_obj.sendReply(client_obj, [build_ClientServersAvailable(client_obj)])
    cmserver_obj.sendReply(client_obj, [build_logon_response(client_obj, client_address, EResult.OK, True, packet.is_proto, True)])
    cmserver_obj.sendReply(client_obj, [build_client_newsupdate_response(client_obj)])
    cmserver_obj.sendReply(client_obj, [build_cmlist_response(client_obj)])
    cmserver_obj.sendReply(client_obj, [build_MsgClientServerList(client_obj)])
    cmserver_obj.sendReply(client_obj, [build_ClientEncryptPct_response(client_obj)])
    cmserver_obj.sendReply(client_obj, [build_MsgClientRequestedStats(client_obj)])

    return -1


def handle_AnonUserLogin(cmserver_obj, packet, client_obj):
    """This message is used during create account, password recovery, etc..."""
    client_address = client_obj.ip_port

    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved Anonymous User Login")
    request = packet.CMRequest
    try:
        #steamid_instance = request.clientId2.to_bytes(4, "little")
        #steamid_accountid = request.accountID.to_bytes(4, "little")
        #full_steamid = steamid_accountid + steamid_instance
        if request.steamID.is_anon_account():
            #print(request.accountID, request.clientId2)
            #current_globalid = struct.pack("<Q", full_steamid)
            #anon_globalID = SteamID.get_new_anon_global_id(SteamID(current_globalid))
            #anon_globalID = anon_globalID.to_bytes(8, "little")

            cm_globalvars.anonUsersCount += 1

            client_obj.steamID = request.steamID.set_accountID(cm_globalvars.anonUsersCount)  # int(anon_globalID[0:4]).from_bytes(4, "little")
            #client_obj.clientID2 = int(anon_globalID[4:8]).from_bytes(4, "little")

            message = ClientAnonUserLogOn_Deprecated(request.data) #FIXME parse this message correctly to gather important information
            client_obj.is_in_app = False
            #print(message)

            cmserver_obj.sendReply(client_obj, [build_client_newsupdate_response(client_obj)])
            cmserver_obj.sendReply(client_obj, [build_logon_response(client_obj, client_address, EResult.OK, True, packet.is_proto)])
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

    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved Client Register Auth Ticket With CM")
    request = packet.CMRequest

    # TODO hold this in the database? or validate? what can i do even if it isnt valid, the client does not expect a response
    if packet.is_proto:
        # Parse protobuf format
        from steam3.protobufs.steammessages_clientserver_pb2 import CMsgClientRegisterAuthTicketWithCM
        proto_msg = CMsgClientRegisterAuthTicketWithCM()
        try:
            proto_msg.ParseFromString(request.data)
            cmserver_obj.log.debug(f"Parsed protobuf auth ticket: protocol_version={proto_msg.protocol_version if proto_msg.HasField('protocol_version') else 'N/A'}")
        except Exception as e:
            cmserver_obj.log.warning(f"Failed to parse protobuf auth ticket: {e}")
    else:
        # Parse legacy clientmsg format
        message = MsgClientRegisterAuthTicketWithCM()
        parsed_message = message.deserialize(request.data)

    return -1  # The client does not expect any response to this


def handle_LogOff(cmserver_obj, packet: CMPacket, client_obj: Client):
    request = packet.CMRequest
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved Client Logoff request")
    client_obj.logoff_User(cmserver_obj)
    if not client_obj.socket:
        return -1  # we do not respond to TCP versions of this packet
    return [build_client_logoff(client_obj, client_address, proto=packet.is_proto)]


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

    # Append protocol and environment info to protocol_information.txt
    try:
        from datetime import datetime

        # Prefer pre-formatted date; otherwise derive from loaded CDR timestamps
        blob_date = globalvars.formatted_date
        if not blob_date:
            dt_obj = None
            if getattr(globalvars, 'CDDB_datetime', None):
                try:
                    dt_obj = datetime.strptime(globalvars.CDDB_datetime, "%m/%d/%Y %H:%M:%S")
                except Exception:
                    dt_obj = None
            if not dt_obj and getattr(globalvars, 'current_blob_datetime', None):
                try:
                    dt_obj = datetime.strptime(globalvars.current_blob_datetime, "%m/%d/%Y %H:%M:%S")
                except Exception:
                    dt_obj = None
            blob_date = dt_obj.strftime("%Y/%m/%d") if dt_obj else "Unknown"

        steam_ver = getattr(globalvars, 'steam_ver', 'Unknown')
        steamui_ver = getattr(globalvars, 'steamui_ver', 'Unknown')
        protocol_ver = int(getattr(logon, 'protocol', 0))

        entry = (
            "---------------------------\n"
            f"Blob Timestamp: {blob_date}\n"
            f"SteamVer: {steam_ver}  SteamUIVer: {steamui_ver}\n"
            f"Protocol Version: {protocol_ver}\n"
        )
        path = "protocol_information.txt"
        should_write = True
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                if entry in content:
                    should_write = False
        except Exception:
            # If we fail to read, fall back to attempting to write
            should_write = True

        if should_write:
            with open(path, "a", encoding="utf-8") as f:
                f.write(entry)
    except Exception as _e:
        # Do not interrupt login flow if logging fails
        try:
            cmserver_obj.log.debug(f"Failed to append protocol_information.txt: {_e}")
        except Exception:
            pass

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
        # Extract all 5 machineID types (any can be None/missing)
        machineID_info = {
            'BB3': obj.get('BB3'),   # Machine GUID
            'FF2': obj.get('FF2'),   # MAC Address
            '3B3': obj.get('3B3'),   # Disk ID
            'BBB': obj.get('BBB'),   # BIOS Serial
            '333': obj.get('333'),   # Custom Data
        }

    # if request.clientId2 == 0x01100001:  # if it is a normal client, do normal login. otherwise just send login response
    #    handle_ClientLogin(cmserver_obj, packet, client_obj)

    # TODO: Check the username in the packet to the username in the ticket
    #   Do any other checks which may prevent unauthorized users from stealing accounts and/or logging into other peoples accounts
    #   Such as figuring out a way to prevent tickets from being copy/pasted into a custom client to login to someone elses account
    if globalvars.steamui_ver == 333 or logon.protocol >= 65558:
        error_code, accountID = database.compare_password_digests(logon.email, logon.ticket.password_digest_hex)
    else:
        error_code, accountID = database.check_user_information(logon.email, logon.password)

    if error_code != 1:
        cmserver_obj.log.warning(f"({client_address[0]}:{client_address[1]}): Failed Login, Incorrect Credentials Or User Does not Exist")
        cmserver_obj.sendReply(client_obj, [build_login_failure(client_obj, error_code)], b"\x05")
        return -1
    tempvarSteamID = SteamID()
    if accountID <= 0:
        cmserver_obj.log.error("ACCOUNT ID IS INVALID!!!")
    client_obj.steamID = tempvarSteamID.create_normal_user_steamID(accountID, EUniverse.PUBLIC)
    handle_ClientLogin(cmserver_obj, packet, client_obj, error_code, machineID_info)

    return -1


def handle_ClientLogOn_WithHash(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Uses Login Key to verify login
    """
    client_address = client_obj.ip_port

    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved Client Login With Hash")
    request = packet.CMRequest
    data = request.data

    logon = ClientLogonWithHash(data)

    print(logon)

    client_obj.protocol_version = logon.protocol
    client_obj.publicIP = logon.public_ip
    client_obj.privateIP = logon.obfuscated_ip
    machineID_info = None
    if logon.machine_id_available:
        machineID_object = logon.machine_id.get_message_objects()

        # Assuming each message object is a dictionary and taking the first one for example
        # if machineID_object and isinstance(machineID_object[0], dict):
        obj = machineID_object[0]
        # Extract all 5 machineID types (any can be None/missing)
        machineID_info = {
            'BB3': obj.get('BB3'),   # Machine GUID
            'FF2': obj.get('FF2'),   # MAC Address
            '3B3': obj.get('3B3'),   # Disk ID
            'BBB': obj.get('BBB'),   # BIOS Serial
            '333': obj.get('333'),   # Custom Data
        }

    # if request.clientId2 == 0x01100001:  # if it is a normal client, do normal login. otherwise just send login response
    #    handle_ClientLogin(cmserver_obj, packet, client_obj)

    error_code, accountID = database.check_user_loginkey_information(logon.username, logon.login_key)

    if error_code != 1:
        cmserver_obj.log.warning(f"({client_address[0]}:{client_address[1]}): Failed Login, Incorrect Credentials Or User Does not Exist")
        cmserver_obj.sendReply(client_obj, [build_login_failure(client_obj, error_code)], b"\x05")
        return -1
    # Set the user object's login key if it is valid, we send a new one with out login response
    client_obj.login_key = logon.login_key
    tempvarSteamID = SteamID()
    client_obj.steamID = tempvarSteamID.set_steam_local_id(accountID, EUniverse.PUBLIC)

    handle_ClientLogin(cmserver_obj, packet, client_obj, error_code, machineID_info)

    return -1


def handle_ClientChangePassword(cmserver_obj, packet: CMPacket, client_obj: Client):
    """2024-06-06 16:04:40     CMUDP27017    CRITICAL packetid: ClientPasswordChange (804)
    data: b'123456\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x0012345\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'"""

    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"{client_address} Client Change Password Request")

    original_password = read_until_null_byte(request.data[0:19])
    new_password = read_until_null_byte(request.data[20:])

    # FIXME deal with this properly. currently in version 479, it sends the changepassword to the auth and CM... need to figure out what to do

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
    is_proto = packet.is_proto

    try:
        if is_proto:
            # Parse using Protobuf definition
            message = CMsgClientGetAppOwnershipTicket()
            message.ParseFromString(request.data)
            appID = message.app_id  # Access app_id field from Protobuf message
        else:
            appID = struct.unpack('<I', request.data[:4])[0]

        cmserver_obj.log.info(f"{client_address} App Ownership Ticket Request for AppID {appID}")
        return build_GetAppOwnershipTicketResponse(cmserver_obj, client_obj, appID, is_proto)

    except Exception as e:
        # Dump everything to the log?because your code clearly can?t handle even the simplest packet without keeling over.
        cmserver_obj.log.error(
            "FATAL in handle_GetAppOwnershipTicket:\n"
            "  Client: %s\n"
            "  Proto?: %s\n"
            "  Raw request.data: %r\n"
            "  Full packet repr: %r\n"
            "  Error: %s\n"
            "  Traceback:\n%s",
            client_address,
            is_proto,
            request.data,
            packet,
            e,
            traceback.format_exc()
        )
        # Re-raise so you get the full stack in your console and can finally figure out how to write non-fragile code.
        raise


def handle_InformOfCreateAccount(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    data: b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00cmtest_2\x0012345\x00teste1@test.com\x00What is the name of your pet?\x00rees\x00'"""
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"{client_address} Informed of Creating an New Account")

    parsed_message = ClientInformOfCreateAccount(request.data)

    #cmserver_obj.log.debug(f"{parsed_message}")

    build_GeneralAck(client_obj,packet,client_address,cmserver_obj)
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

    accountID = 0
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

        accountID, result = database.create_user(unique_username=parsed_message.username,
                                               account_email_address=parsed_message.email,
                                               personal_question=parsed_message.security_question,
                                               passphrase_salt=password_salt,
                                               salted_passphrase_digest=password_digest,
                                               answer_to_question_salt=answertoguestion_salt,
                                               salted_answer_to_question_digest=answertoguestion_digest)

        if accountID is not None:
            full_steamID = SteamID()
            full_steamID.set_accountID(accountID)
            full_steamID.set_universe(EUniverse(int(config['universe'])))
            full_steamID.set_type(EType.INDIVIDUAL)
            full_steamID.set_instance(EInstanceFlag.ALL)
            accountID = full_steamID.get_integer_format()
           #print(accountID)
    else:
        cmserver_obj.log.warning(f"{client_address[0]}:{client_address[1]} - Account Creation Failed Due To Error: {get_enum_name(EResult, result)}")

    return build_CreateAccountResponse(client_obj, result, accountID, isVersion2)


def handle_NewLoginKeyAccepted(cmserver_obj, packet: CMPacket, client_obj: Client):
    client_address = client_obj.ip_port
    request = packet.CMRequest

    cmserver_obj.log.debug(f"NewLoginKeyAccepted raw request.data: {request.data.hex()} (len={len(request.data)}, is_proto={packet.is_proto})")

    if packet.is_proto:
        # Parse as protobuf CMsgClientNewLoginKeyAccepted
        from steam3.protobufs.steammessages_clientserver_login_pb2 import CMsgClientNewLoginKeyAccepted
        proto_msg = CMsgClientNewLoginKeyAccepted()
        proto_msg.ParseFromString(request.data)
        loginkey_uniqueid = proto_msg.unique_id if proto_msg.HasField('unique_id') else 0
        cmserver_obj.log.debug(f"Parsed as protobuf, unique_id={loginkey_uniqueid}")
    elif len(request.data) >= 4:
        # Binary format: MsgClientNewLoginKeyAccepted_t { uint32 m_unUniqueId; }
        loginkey_uniqueid = int.from_bytes(request.data[0:4], 'little')
    else:
        loginkey_uniqueid = int.from_bytes(request.data.ljust(4, b'\x00'), 'little')

    # Convert stored value to integer - handle bytes, int, or None
    stored_uniqueid = client_obj.login_key_uniqueID
    if stored_uniqueid is None:
        stored_uniqueid_int = 0
    elif isinstance(stored_uniqueid, bytes):
        stored_uniqueid_int = int.from_bytes(stored_uniqueid, 'little')
    elif isinstance(stored_uniqueid, int):
        stored_uniqueid_int = stored_uniqueid
    else:
        # Handle string representation of bytes or other types
        try:
            stored_uniqueid_int = int(stored_uniqueid)
        except (ValueError, TypeError):
            stored_uniqueid_int = 0

    cmserver_obj.log.debug(f"login key uniqueid: {loginkey_uniqueid}, client object login key uniqueid: {stored_uniqueid_int} (raw: {stored_uniqueid})")

    if loginkey_uniqueid == stored_uniqueid_int:
        cmserver_obj.log.info(f"{client_address} Accepted The New Login Key")
        return -1
    else:
        cmserver_obj.log.warning(f"{client_address} Tried To Use The Login Key Of Another User!!")
        reply = MsgClientLoggedOff(client_obj)
        return reply.to_clientmsg()


def handle_ClientEmailChange(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle original email change request (EMsg 843).
    Body: char m_rgchEmail[322]
    """
    from steam3.messages.MsgClientEmailChange import MsgClientEmailChange
    from steam3.Responses.auth_responses import build_EmailChangeResponse

    client_address = client_obj.ip_port
    request = packet.CMRequest

    cmserver_obj.log.info(f"{client_address} Client Email Change Request (v1)")

    message = MsgClientEmailChange()
    message.deserialize(request.data)

    cmserver_obj.log.debug(f"Email change request: {message}")

    # TODO: Implement actual email change logic with database
    # For now, return success
    result = EResult.OK

    return build_EmailChangeResponse(client_obj, result)


def handle_ClientEmailChange2(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle email change request v2 (EMsg 894).
    Body: char m_rgchPassword[20], char m_rgchEmail[322], uint32 m_unTicketLength, byte[] ticket
    """
    from steam3.messages.MsgClientEmailChange2 import MsgClientEmailChange2
    from steam3.Responses.auth_responses import build_EmailChangeResponse

    client_address = client_obj.ip_port
    request = packet.CMRequest

    cmserver_obj.log.info(f"{client_address} Client Email Change Request (v2)")

    message = MsgClientEmailChange2()
    message.deserialize(request.data)

    cmserver_obj.log.debug(f"Email change request: {message}")

    # TODO: Verify password and ticket, then change email in database
    result = EResult.OK

    return build_EmailChangeResponse(client_obj, result)


def handle_ClientPasswordChange2(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle password change request v2 (EMsg 893).
    Body: char m_rgchOldPassword[20], char m_rgchNewPassword[20], uint32 m_unTicketLength, byte[] ticket
    """
    from steam3.messages.MsgClientPasswordChange2 import MsgClientPasswordChange2
    from steam3.Responses.auth_responses import build_ClientChangePasswordResponse

    client_address = client_obj.ip_port
    request = packet.CMRequest

    cmserver_obj.log.info(f"{client_address} Client Password Change Request (v2)")

    message = MsgClientPasswordChange2()
    message.deserialize(request.data)

    cmserver_obj.log.debug(f"Password change request: {message}")

    # TODO: Verify old password and ticket, then change password in database
    result = EResult.OK

    return build_ClientChangePasswordResponse(cmserver_obj, client_obj, result)


def handle_ClientPersonalQAChange(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle personal Q&A change request (EMsg 844).
    Body: int32 m_iPersonalQuestion, char m_rgchNewQuestion[255], char m_rgchNewAnswer[255]
    """
    from steam3.messages.MsgClientPersonalQAChange import MsgClientPersonalQAChange
    from steam3.Responses.auth_responses import build_SecretQAChangeResponse

    client_address = client_obj.ip_port
    request = packet.CMRequest

    cmserver_obj.log.info(f"{client_address} Client Personal Q&A Change Request (v1)")

    message = MsgClientPersonalQAChange()
    message.deserialize(request.data)

    cmserver_obj.log.debug(f"Personal Q&A change request: {message}")

    # TODO: Update secret question/answer in database
    result = EResult.OK

    return build_SecretQAChangeResponse(client_obj, result)


def handle_ClientPersonalQAChange2(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle personal Q&A change request v2 (EMsg 895).
    Body: char m_rgchPassword[20], int32 m_iPersonalQuestion, char m_rgchNewQuestion[255],
          char m_rgchNewAnswer[255], uint32 m_unTicketLength, byte[] ticket
    """
    from steam3.messages.MsgClientPersonalQAChange2 import MsgClientPersonalQAChange2
    from steam3.Responses.auth_responses import build_SecretQAChangeResponse

    client_address = client_obj.ip_port
    request = packet.CMRequest

    cmserver_obj.log.info(f"{client_address} Client Personal Q&A Change Request (v2)")

    message = MsgClientPersonalQAChange2()
    message.deserialize(request.data)

    cmserver_obj.log.debug(f"Personal Q&A change request: {message}")

    # TODO: Verify password and ticket, then update secret question/answer in database
    result = EResult.OK

    return build_SecretQAChangeResponse(client_obj, result)


def handle_ClientFavoritesList(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle client favorites list (EMsg 786).
    This is a fire-and-forget message - no response expected.
    Body: uint32 m_cFavorites, then repeated entries (appID, IP, port, flags, lastPlayed)
    """
    from steam3.messages.MsgClientFavoritesList import MsgClientFavoritesList

    client_address = client_obj.ip_port
    request = packet.CMRequest

    cmserver_obj.log.info(f"{client_address} Client Favorites List Received")

    message = MsgClientFavoritesList()
    message.deserialize(request.data)

    cmserver_obj.log.debug(f"Favorites list: {message}")

    # TODO: Store favorites list in database if needed
    # This is informational only - no response expected

    return -1


def handle_ClientRequestForgottenPasswordEmail(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle forgotten password email request (EMsg 5461).
    """
    from steam3.messages.MsgClientRequestForgottenPasswordEmail import MsgClientRequestForgottenPasswordEmail
    from steam3.Responses.auth_responses import build_RequestForgottenPasswordEmailResponse

    client_address = client_obj.ip_port
    request = packet.CMRequest

    cmserver_obj.log.info(f"{client_address} Client Request Forgotten Password Email")

    message = MsgClientRequestForgottenPasswordEmail()
    message.deserialize(request.data)

    cmserver_obj.log.debug(f"Forgotten password email request: {message}")

    # TODO: Send forgotten password email and check if secret question is required
    result = EResult.OK
    secret_question_required = False

    return build_RequestForgottenPasswordEmailResponse(client_obj, result, secret_question_required)


def handle_ClientResetForgottenPassword(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle reset forgotten password request (EMsg 5404).
    """
    from steam3.messages.MsgClientResetForgottenPassword import MsgClientResetForgottenPassword
    from steam3.Responses.auth_responses import build_ResetForgottenPasswordResponse

    client_address = client_obj.ip_port
    request = packet.CMRequest

    cmserver_obj.log.info(f"{client_address} Client Reset Forgotten Password")

    message = MsgClientResetForgottenPassword(client_obj)
    message.deSerialize(request.data)

    cmserver_obj.log.debug(f"Reset forgotten password request: {message}")

    # TODO: Verify email code and secret answer, then reset password
    result = EResult.OK

    return build_ResetForgottenPasswordResponse(client_obj, result)


def handle_ClientResetForgottenPassword4(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle reset forgotten password request v4 (EMsg 5551).
    """
    from steam3.messages.MsgClientResetForgottenPassword4 import MsgClientResetForgottenPassword4
    from steam3.Responses.auth_responses import build_ResetForgottenPasswordResponse

    client_address = client_obj.ip_port
    request = packet.CMRequest

    cmserver_obj.log.info(f"{client_address} Client Reset Forgotten Password (v4)")

    message = MsgClientResetForgottenPassword4()
    message.deserialize(request.data)

    cmserver_obj.log.debug(f"Reset forgotten password request: {message}")

    # TODO: Verify email code and secret answer, then reset password
    result = EResult.OK

    return build_ResetForgottenPasswordResponse(client_obj, result)


def handle_ClientInformOfResetForgottenPassword(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle inform of reset forgotten password request (EMsg 5406).
    """
    from steam3.messages.MsgClientInformOfResetForgottenPassword import MsgClientInformOfResetForgottenPassword
    from steam3.Responses.auth_responses import build_ResetForgottenPasswordResponse

    client_address = client_obj.ip_port
    request = packet.CMRequest

    cmserver_obj.log.info(f"{client_address} Client Inform Of Reset Forgotten Password")

    message = MsgClientInformOfResetForgottenPassword(client_obj)
    message.deSerialize(request.data)

    cmserver_obj.log.debug(f"Inform reset forgotten password request: {message}")

    # TODO: Process the password reset information
    result = EResult.OK

    return build_ResetForgottenPasswordResponse(client_obj, result)


def handle_ClientEmailChange3(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle email change request v3 (EMsg 5458).
    """
    from steam3.messages.MsgClientEmailChange3 import MsgClientEmailChange3
    from steam3.Responses.auth_responses import build_EmailChangeResponse

    client_address = client_obj.ip_port
    request = packet.CMRequest

    cmserver_obj.log.info(f"{client_address} Client Email Change Request (v3)")

    message = MsgClientEmailChange3()
    message.deserialize(request.data)

    cmserver_obj.log.debug(f"Email change request: {message}")

    # TODO: Verify password and confirmation code, then change email
    result = EResult.OK

    return build_EmailChangeResponse(client_obj, result)


def handle_ClientPersonalQAChange3(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle personal Q&A change request v3 (EMsg 5459).
    """
    from steam3.messages.MsgClientPersonalQAChange3 import MsgClientPersonalQAChange3
    from steam3.Responses.auth_responses import build_SecretQAChangeResponse

    client_address = client_obj.ip_port
    request = packet.CMRequest

    cmserver_obj.log.info(f"{client_address} Client Personal Q&A Change Request (v3)")

    message = MsgClientPersonalQAChange3()
    message.deserialize(request.data)

    cmserver_obj.log.debug(f"Personal Q&A change request: {message}")

    # TODO: Verify password and confirmation code, then update secret question/answer
    result = EResult.OK

    return build_SecretQAChangeResponse(client_obj, result)


def _send_user_clan_states(cmserver_obj, client_obj):
    """
    Send ClientClanState messages for all clans the user is a member of.

    This is called during login to inform the client about their clan memberships.
    """
    from steam3.Types.chat_types import ChatRelationship

    account_id = int(client_obj.accountID)
    cmserver_obj.log.debug(f"Fetching clan memberships for account {account_id}")

    # Get all clans where the user is a member (relationship=3 is member)
    clan_memberships = database.get_users_clan_list(account_id, ChatRelationship.member)

    if not clan_memberships:
        cmserver_obj.log.debug(f"No clan memberships found for account {account_id}")
        return

    cmserver_obj.log.info(f"Sending {len(clan_memberships)} clan state(s) to {client_obj.username}")

    for membership in clan_memberships:
        try:
            # Get the clan registry entry
            clan = database.get_clan_by_id(membership.CommunityClanID)
            if not clan:
                cmserver_obj.log.warning(f"Clan {membership.CommunityClanID} not found in registry")
                continue

            # Get member counts
            member_count = database.get_clan_member_count(clan.UniqueID)
            online_count = _count_online_clan_members(clan.UniqueID)

            # Build and send clan state
            response = build_ClanState_from_db(
                client_obj,
                clan,
                member_count=member_count,
                online_count=online_count
            )

            if response:
                cmserver_obj.sendReply(client_obj, [response])
                cmserver_obj.log.debug(f"Sent ClanState for clan {clan.UniqueID} ({clan.clan_name})")

        except Exception as e:
            cmserver_obj.log.warning(f"Error sending clan state for clan {membership.CommunityClanID}: {e}")


def _count_online_clan_members(clan_id: int) -> int:
    """Count how many members of a clan are currently online."""
    from steam3.Types.chat_types import ChatRelationship

    online_count = 0
    try:
        # Get all members of this clan
        members = database.get_clan_members(clan_id)
        if not members:
            return 0

        for member in members:
            if member.relationship == ChatRelationship.member:
                # Check if user is online
                if member.friendRegistryID in Client_Manager.clientsByAccountID:
                    online_count += 1

    except Exception as e:
        pass  # Return 0 on error

    return online_count
