
import struct
import globalvars
from steam3.Types.wrappers import AccountID
from steam3.Types.steamid import SteamID

from steam3.messages.responses.MsgClientPersonaState import PersonaStateMessage
from steam3.messages.responses.MsgClientFriendsList import FriendsListResponse
from steam3 import database


from steam3.Types.community_types import FriendRelationship, PersonaStateFlags, PlayerState, RequestedPersonaStateFlags_inFriendsList_friend, RequestedPersonaStateFlags_inFriendsList_other, RequestedPersonaStateFlags_self
from steam3.Types.chat_types import ClanRelationship
from steam3.Types.emsg import EMsg
from steam3.Types.steam_types import EResult, EUniverse
from steam3.cm_packet_utils import CMResponse


def build_InviteFriendResponse(client_obj, Result = 1):
    packet = CMResponse(eMsgID = EMsg.ClientInviteFriendResponse, client_obj = client_obj)

    packet.data = struct.pack('I',
                            Result)  # This is an result code

    return packet


def build_friendslist_response(client_obj, proto=False):
    """
    Build a chat eMsgID packet with eMsgID 0x02FF for the contact list.

    :param client_obj: User object for the client requesting the contact list.
    :return: A ChatCommandPacket instance

    Note: isIncremental might be used if a friend list is too big for a single packet.
    """
    # print("Sending friendslist with relationship info")
    packet = CMResponse(eMsgID = EMsg.ClientFriendsList, client_obj = client_obj)
    isIncremental = 0
    clientId2 = 0x01100001
    #packet.data = struct.pack('I', 1)
    # Query friends from database
    friends = client_obj.friends_list  # client_obj.get_friends_list_from_db()
    # print(f"friends count: {len(friends)}")
    if friends is None or len(friends) == 0:
        print("no friends in friendlist")
        packet.data = struct.pack('<HB', 0, isIncremental) + b'\x00'  # 0 friends in list
        packet.length = len(packet.data)
        return packet
    friend_data = b''
    for friend, relationship in friends:
        friendSteamID = SteamID.createSteamIDFromAccountID(friend.accountID) # Friends accountID
        # print(f"Friends in list accountid: {int(friendSteamID)}")

        # Pack and append data
        friend_data += struct.pack('<Q', friendSteamID)
        friend_data += struct.pack('B', relationship)  # relationship
        # print(f"userid: {friend.accountID} {relationship}")

    # isIncremental 0x01 or 0x00 are the only valid entries for this byte
    packet.data = struct.pack('<HB', len(friends), isIncremental)  # number of friends in list

    packet.data += friend_data

    return packet


def build_incremental_friendslist_update(client_obj, friend_accountID, relationship):
    """
    Build an incremental friendslist update packet containing just one friend entry.

    This is used to notify clients about friend request changes (new requests, acceptances, etc.)
    without sending the entire friends list.

    :param client_obj: User object for the client receiving the update.
    :param friend_accountID: The accountID of the friend whose relationship changed.
    :param relationship: The new relationship value (FriendRelationship enum).
    :return: A CMResponse packet with isIncremental=1 containing just the changed entry.
    """
    packet = CMResponse(eMsgID=EMsg.ClientFriendsList, client_obj=client_obj)
    isIncremental = 1  # This is an incremental update

    friendSteamID = SteamID.createSteamIDFromAccountID(friend_accountID)

    # Pack header: friend count (1) + is_incremental (1)
    packet.data = struct.pack('<HB', 1, isIncremental)

    # Pack the single friend entry
    packet.data += struct.pack('<Q', friendSteamID.get_integer_format())
    packet.data += struct.pack('B', int(relationship))

    packet.length = len(packet.data)
    return packet


"""def build_contactlist_user_info(client_obj, asked):
    packet = CMResponse(eMsgID=0x02FE, client_obj=client_obj)

    # Type indicating "all contact list"
    state_flag = 0x02
    nbInfo = 0

    # Use a mutable bytearray to start
    packed_data = bytearray()

    # Reserve space for nbInfo (2 bytes)
    start_nbInfo_pos = len(packed_data)
    packed_data += b'\x00\x00'  # Placeholder for nbInfo

    # Pack the type
    packed_data += struct.pack('<I', state_flag)

    # Process each account in the asked list
    for accountId in asked:
        accountId_half = accountId // 2
        nickname = client_obj.get_friends_nickname(accountId_half)

        if nickname:
            nbInfo += 1
            packed_data += struct.pack('<II',
                                       accountId,
                                       clientId2)

            nickname_bytes = nickname.encode('latin-1') + b'\x00'
            packed_data += nickname_bytes

    # Update nbInfo at the reserved position
    nbInfo_bytes = struct.pack('<H', nbInfo)
    packed_data[start_nbInfo_pos:start_nbInfo_pos + 2] = nbInfo_bytes  # Update the nbInfo in the packet

    # Convert the bytearray to bytes before assigning to packet.data
    packet.data = bytes(packed_data)

    return packet"""

class friend_obj_empty:
    """Empty class for making stuff...?"""
    def __init__(self):
        pass


def build_persona_message(clientOBJ, stateFlags, accountIDList, proto=False):
    """
    Build a persona state message using the new PersonaStateMessage class.

    This packet holds a maximum of 10 users per packet. Only the fields corresponding
    to the supported flags are populated:
      - 0x1: PersonaState (persona_state, game_id, game_server_ip, game_server_port)
      - 0x2: Player name (player_name)
      - 0x4: Query Port (query_port)
      - 0x8: SteamID source (steam_id_source)
      - 0x10: Presence (ip_address_cm and avatar_hash)
      - 0x40: Last Seen (last_logoff, last_logon)
      - 0x80: Clan Info (clan_rank)
      - 0x100: Extra Info (game_extra_info, game_id_real)
      - 0x200: Game Data Blob (metadata)

    :param clientOBJ: The client object.
    :param stateFlags: The bitmask flag indicating which fields to include.
    :param accountIDList: A list of accountID values.
    :param proto: Whether to use protobuf format (True) or binary format (False).
    :return: A CMResponse/CMProtoResponse packet with the serialized PersonaStateMessage.

    NOTE: Flags 1 and 2 should ALWAYS be present!
    """
    from steam3.ClientManager import Client_Manager  # assumed import
    import logging
    log = logging.getLogger("PersonaMessage")
    # Create a new PersonaStateMessage instance
    psm = PersonaStateMessage(clientOBJ)
    psm.status_flags = stateFlags
    rank = None  # This will be set if clan info is available.

    log.debug(f"build_persona_message: for client {clientOBJ.accountID}, accountIDList={accountIDList}")

    for accountID in accountIDList:
        # Convert to int for consistent dictionary lookup
        accountID_int = int(accountID) if hasattr(accountID, '__int__') else accountID
        friend_obj = Client_Manager.get_client_by_accountID(accountID_int)
        log.debug(f"  Looking up accountID {accountID_int}: friend_obj={friend_obj}, client_state={getattr(friend_obj, 'client_state', 'N/A') if friend_obj else 'None'}")
        if int(accountID) == int(clientOBJ.accountID):
            # it's you - use the real object so you have .steamID, etc.
            friend_obj = clientOBJ
            log.debug(f"    -> Using self (clientOBJ)")
        elif friend_obj is None:
            log.debug(f"    -> Friend NOT found in clientsByAccountID, creating empty object with offline state")
            friend_obj = friend_obj_empty()
            friend_obj.client_state = 0
            friend_obj.appID = 0
            friend_obj.app_ip_port = [0, 0]
            friend_obj.steamID = SteamID.createSteamIDFromAccountID(accountID_int)
        else:
            log.debug(f"    -> Friend found! client_state={friend_obj.client_state}")
        friend_data = {}
        # Use accountID * 2 as the friend_id, as in the original build_persona_message.
        friendSteamID = friend_obj.steamID #SteamID().create_normal_user_steamID(accountID, EUniverse.PUBLIC)
        friend_data['friend_id'] = friendSteamID.get_integer_format()

        if stateFlags & PersonaStateFlags.status:
            # Explicitly convert to int to ensure proper serialization
            persona_state_val = int(friend_obj.client_state) if friend_obj.client_state is not None else 0
            friend_data['persona_state'] = persona_state_val
            friend_data['game_id'] = friend_obj.appID
            friend_data['game_server_ip'] = friend_obj.app_ip_port[0]
            friend_data['game_server_port'] = friend_obj.app_ip_port[1]
            log.debug(f"    -> Setting persona_state={persona_state_val} for friend {accountID_int}")

        if stateFlags & PersonaStateFlags.playerName:
            friend_data['player_name'] = clientOBJ.get_friends_nickname(accountID)

        if stateFlags & PersonaStateFlags.queryPort:
            friend_data['query_port'] = 0xFFFF

        if stateFlags & PersonaStateFlags.sourceId:
            client_clans_id, rank = clientOBJ.get_main_clan(accountID, ClanRelationship.member)
            friend_data['steam_id_source'] = client_clans_id if client_clans_id else 0

        if stateFlags & PersonaStateFlags.presence:
            friend_data['ip_address_cm'] = 0  # default IP (could be replaced with globalvars.server_ip if needed)
            avatarID = clientOBJ.get_friend_avatarID(accountID)
            if avatarID is None:
                friend_data['avatar_hash'] = b'fef49e7fa7e1997310d705b2a6158ff8dc1cdfeb'
            else:
                try:
                    friend_data['avatar_hash'] = bytes.fromhex(avatarID.decode('latin-1'))
                except Exception as e:
                    friend_data['avatar_hash'] = avatarID

        if stateFlags & PersonaStateFlags.chatMetadata:
            # If client_obj offers metadata for friends, use it; otherwise default to empty.
            friend_data['metadata_blob'] = (clientOBJ.get_friend_metadata_blob(accountID)
                                            if hasattr(clientOBJ, "get_friend_metadata_blob")
                                            else b'')

        if stateFlags & PersonaStateFlags.lastSeen:
            last_login, last_logoff = clientOBJ.get_friend_lastseen(accountID)
            friend_data['last_logoff'] = last_logoff
            friend_data['last_logon'] = last_login

        if stateFlags & PersonaStateFlags.clanInfo:
            friend_data['clan_rank'] = rank if rank else 0

        if stateFlags & PersonaStateFlags.extraInfo:
            friend_data['game_extra_info'] = database.get_app_name(friend_obj.appID)
            friend_data['game_id_real'] = friend_obj.appID

        if stateFlags & PersonaStateFlags.gameDataBlob:
            friend_data['metadata'] = b''

        psm.friends.append(friend_data)

    if proto:
        return psm.to_protobuf()
    else:
        return psm.to_clientmsg()


def build_AddFriendResponse(cmserver_obj, client_obj, isold, request, searchStr, jobID, proto=False):
    from steam3.ClientManager import Client_Manager

    if isold:
        packet = CMResponse(eMsgID = 0x0301, client_obj = client_obj)
    else:
        packet = CMResponse(eMsgID = 0x0318, client_obj = client_obj)

    packet_data = bytearray(struct.pack('<Q', jobID))
    friendsAccountID = database.find_user_by_name(searchStr)
    cmserver_obj.log.debug(f"[build_AddFriendResponse] found accountid: {friendsAccountID}")
    if friendsAccountID is None:
        if request.eMsgID == 0x02C9:  # old style
            packet_data += struct.pack('IIH', 0, 0, EResult.Invalid)  # 10 null bytes to signify no user found
        else:  # new style
            packet_data += struct.pack('III', 0, 0, EResult.AccountNotFound) + b"\x00"  # account not found
        packet.data = bytes(packet_data)
        packet.length = len(packet.data)
        return packet

    friendsSteamID = SteamID.createSteamIDFromAccountID(friendsAccountID)
    packet_data += struct.pack('<Q', friendsSteamID.get_integer_format())
    cmserver_obj.log.debug(f"[build_AddFriendResponse] found account steamid: {friendsSteamID}")
    if friendsAccountID == client_obj.accountID:
        if request.eMsgID == 0x02C9:  # old style
            packet_data += struct.pack('H', EResult.Invalid)  # if we find ourself we send 2 null bytes
        else:  # new style
            packet_data += struct.pack('I', EResult.InvalidParam) + b"\x00"
        packet.data = bytes(packet_data)
        packet.length = len(packet.data)
        return packet

    result = client_obj.add_friend(friendsAccountID)

    if not result:  # error adding friend to list, perhaps already there?
        packet_data += struct.pack('IIH', 0, 0, 0)  # 10 null bytes to signify no user found
        packet.data = bytes(packet_data)
        packet.length = len(packet.data)
        return packet

    addFriend_eResult = EResult.OK
    packet_data += struct.pack('<I', addFriend_eResult)
    packet_data += searchStr.encode('latin-1') + b'\x00'  # Append the name and a null terminator to the packed data

    friends_clientobj = Client_Manager.get_client_by_accountID(AccountID(friendsAccountID))
    cmserver_obj.log.debug(f"[build_AddFriendResponse] found account clientobj: {friends_clientobj}")

    if friends_clientobj and friends_clientobj.objCMServer:  # Recipient is online and has a valid CM server
        # Refresh requestee's friends list from DB (the after_insert trigger created their entry)
        friends_clientobj.get_friends_list_from_db()

        # Check if recipient uses newer protocol (> 65550) - auto-accept friend request
        if friends_clientobj.protocol_version and friends_clientobj.protocol_version > 65550 and globalvars.config['auto_friend_later_clients'].lower() == "true":
            # Auto-accept: Update both sides to "friend" relationship
            client_obj.add_friend(friendsAccountID, FriendRelationship.friend)
            friends_clientobj.get_friends_list_from_db()  # Refresh after relationship update
            client_obj.get_friends_list_from_db()

            # Send FULL friends list to recipient (auto-accepted)
            friends_clientobj.objCMServer.sendReply(friends_clientobj, [build_friendslist_response(friends_clientobj)])
            # Send recipient persona info for all their friends including the new one
            for friend_entry, _ in friends_clientobj.friends_list:
                friends_clientobj.objCMServer.sendReply(friends_clientobj, [build_persona_message(
                    friends_clientobj, RequestedPersonaStateFlags_inFriendsList_friend, [friend_entry.accountID]
                )])

            # Send FULL friends list to requester
            cmserver_obj.sendReply(client_obj, [build_friendslist_response(client_obj)])
            # Send requester persona info for all their friends including the new one
            for friend_entry, _ in client_obj.friends_list:
                cmserver_obj.sendReply(client_obj, [build_persona_message(
                    client_obj, RequestedPersonaStateFlags_inFriendsList_friend, [friend_entry.accountID]
                )])
        else:
            # Older protocol recipient - send friend request notification
            # Send recipient an INCREMENTAL update with the new friend request (relationship=2 requestRecipient)
            # This triggers the friend request dialog in older clients
            # IMPORTANT: Use the recipient's CM server to send, not the requester's!
            # This ensures proper delivery when clients are on different connection types (UDP vs TCP)
            friends_clientobj.objCMServer.sendReply(friends_clientobj, [build_incremental_friendslist_update(
                friends_clientobj, client_obj.accountID, FriendRelationship.requestRecipient
            )])
            friends_clientobj.objCMServer.sendReply(friends_clientobj, [build_persona_message(
                friends_clientobj, RequestedPersonaStateFlags_inFriendsList_other, [client_obj.accountID]
            )])

            # Send requester an INCREMENTAL update showing they sent a request (relationship=4 requestInitiator)
            cmserver_obj.sendReply(client_obj, [build_incremental_friendslist_update(
                client_obj, friendsAccountID, FriendRelationship.requestInitiator
            )])
            cmserver_obj.sendReply(client_obj, [build_persona_message(
                client_obj, RequestedPersonaStateFlags_inFriendsList_other, [friendsAccountID]
            )])
    else:
        # Friend is offline - send requester incremental update and friend's persona state (offline)
        cmserver_obj.sendReply(client_obj, [build_incremental_friendslist_update(
            client_obj, friendsAccountID, FriendRelationship.requestInitiator
        )])
        cmserver_obj.sendReply(client_obj, [build_persona_message(
            client_obj, RequestedPersonaStateFlags_inFriendsList_other, [friendsAccountID]
        )])

    packet.data = bytes(packet_data)

    return packet


def build_AcceptFriendResponse(cmserver_obj, client_obj, request, friendsAccountID, jobID, proto=False):
    from steam3.ClientManager import Client_Manager

    if request.eMsgID == 0x02C9:  # Old style add friend packet
        packet = CMResponse(eMsgID=0x0301, client_obj=client_obj)
    else:  # new style add friend packet
        packet = CMResponse(eMsgID=0x0318, client_obj=client_obj)

    packet_data = bytearray(struct.pack('<Q', jobID))

    requesterSteamID = SteamID.createSteamIDFromAccountID(friendsAccountID)  # the id of the user requesting to add a user to their list
    packet_data += struct.pack('<Q', requesterSteamID)

    if friendsAccountID == client_obj.accountID:
        if request.eMsgID == 0x02C9:  # old style
            packet_data += struct.pack('H', EResult.Invalid)  # if we find ourself we send 2 null bytes
        else:  # new style
            packet_data += struct.pack('I', EResult.InvalidParam) + b"\x00"
        packet.data = bytes(packet_data)
        packet.length = len(packet.data)
        return packet

    # Update acceptor's relationship to "friend"
    # Note: add_friend() also updates the inverse entry (requester's side) in the database
    result = client_obj.add_friend(friendsAccountID, FriendRelationship.friend)

    addFriend_eResult = EResult.OK
    packet_data += struct.pack('<I', addFriend_eResult)
    searchStr = client_obj.get_friends_nickname(friendsAccountID)  # Get the friend's nickname
    packet_data += searchStr.encode('latin-1') + b'\x00'  # Append the name and a null terminator to the packed data

    # Refresh acceptor's friends list from DB
    client_obj.get_friends_list_from_db()

    friends_clientobj = Client_Manager.get_client_by_accountID(friendsAccountID)
    if friends_clientobj and friends_clientobj.objCMServer:  # Original requester is online and has valid CM server
        # Refresh requester's friendslist from DB so their in-memory list is updated
        friends_clientobj.get_friends_list_from_db()

        # Send FULL friends list to requester (original friend request sender)
        # IMPORTANT: Use the requester's CM server to send, not the acceptor's!
        # This ensures proper delivery when clients are on different connection types (UDP vs TCP)
        friends_clientobj.objCMServer.sendReply(friends_clientobj, [build_friendslist_response(friends_clientobj)])
        # Send requester persona info for all their friends including the new one
        for friend_entry, _ in friends_clientobj.friends_list:
            friends_clientobj.objCMServer.sendReply(friends_clientobj, [build_persona_message(
                friends_clientobj, RequestedPersonaStateFlags_inFriendsList_friend, [friend_entry.accountID]
            )])

        # Send FULL friends list to acceptor
        cmserver_obj.sendReply(client_obj, [build_friendslist_response(client_obj)])
        # Send acceptor persona info for all their friends including the new one
        for friend_entry, _ in client_obj.friends_list:
            cmserver_obj.sendReply(client_obj, [build_persona_message(
                client_obj, RequestedPersonaStateFlags_inFriendsList_friend, [friend_entry.accountID]
            )])
    else:
        # Requester is offline - send FULL friends list to acceptor only
        cmserver_obj.sendReply(client_obj, [build_friendslist_response(client_obj)])
        # Send acceptor persona info for all their friends
        for friend_entry, _ in client_obj.friends_list:
            cmserver_obj.sendReply(client_obj, [build_persona_message(
                client_obj, RequestedPersonaStateFlags_inFriendsList_friend, [friend_entry.accountID]
            )])

    packet.data = bytes(packet_data)

    return packet


def send_statuschange_to_friends(client_obj, cmserver_obj, Client_Manager, user_state):
    if not client_obj:
        return -1

    # Notify online friends about the user's status change
    if client_obj.friends_list:
        for friend_entry, friend_relationship in client_obj.get_friends_list_from_db():
            # Access friendsaccountID attribute from the FriendsList tuple
            friendsAccountID = AccountID(friend_entry.accountID)
            # Check if friends are online currently:
            client_friend = Client_Manager.get_client_by_accountID(friendsAccountID)
            if client_friend and client_friend.objCMServer:
                # Use the friend's proto preference for their message
                reply_packet = build_persona_message(client_friend, RequestedPersonaStateFlags_inFriendsList_friend, [client_obj.accountID], proto=client_friend.is_proto)
                # IMPORTANT: Use the friend's CM server to send, not the user's!
                # This ensures proper delivery when clients are on different connection types (UDP vs TCP)
                client_friend.objCMServer.sendReply(client_friend, [reply_packet])

    if client_obj.username is None:
        client_obj.username = "[Unset]"

    # Always send the user their own updated persona state (regardless of friends list)
    # This ensures the client UI shows the correct status after login or status change
    if user_state != PlayerState.offline:
        # Use the client's proto preference for their message
        reply_packet = build_persona_message(client_obj, RequestedPersonaStateFlags_self, [client_obj.accountID], proto=client_obj.is_proto)
        cmserver_obj.sendReply(client_obj, [reply_packet])

    return -1

def build_SetIgnoreFriendResponse(cmserver_obj, client_obj, friendSteamID, status):
    """
    struct MsgClientSetIgnoreFriendResponse_t
    {
      uint64 m_ulFriendID;
      EResult m_eResult;
    };
    """
    from steam3.ClientManager import Client_Manager
    packet = CMResponse(eMsgID = EMsg.ClientSetIgnoreFriendResponse, client_obj = client_obj)

    packet.data = struct.pack('<QI',
                              friendSteamID,
                              status)

    cmserver_obj.sendReply(client_obj, [packet])
    if status:
        cmserver_obj.sendReply(client_obj, [build_friendslist_response(client_obj)])

        friendAccountID = int(friendSteamID.get_accountID())
        friendOBJ = Client_Manager.get_client_by_accountID(friendAccountID)
        if friendOBJ and friendOBJ.objCMServer:
            # IMPORTANT: Use the friend's CM server to send, not the requester's!
            friendOBJ.objCMServer.sendReply(friendOBJ, [build_friendslist_response(friendOBJ)])

    return -1