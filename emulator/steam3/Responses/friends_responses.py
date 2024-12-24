import socket
import struct

import globalvars
import utils
from steam3 import database


from steam3.Types.community_types import ClanRelationship, FriendRelationship, PersonaStateFlags, PlayerState
from steam3.Types.emsg import EMsg
from steam3.Types.steam_types import EResult, EType, EInstanceFlag, EUniverse
from steam3.Types.steamid import SteamID
from steam3.cm_packet_utils import CMResponse


def build_InviteFriendResponse(client_obj, Result = 1):
    packet = CMResponse(eMsgID = EMsg.ClientInviteFriendResponse, client_obj = client_obj)

    packet.data = struct.pack('I',
                            Result)  # This is an result code

    return packet


def build_friendslist_response(client_obj):
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
        friend_id = friend.accountID  # Friends accountID
        # print(f"Friends in list accountid: {int(friend_id)}")
        chat_id = friend_id * 2  # turn the accountID back into what the steam client uses...

        # Pack and append data
        friend_data += struct.pack('<I', chat_id)
        friend_data += struct.pack('<I', clientId2)
        friend_data += struct.pack('B', relationship)  # relationship
        # print(f"userid: {friend.accountID} {relationship}")
    # isIncremental 0x01 or 0x00 are the only valid entries for this byte
    packet.data = struct.pack('<HB', len(friends), isIncremental)# number of friends in list

    packet.data += friend_data

    return packet


"""def build_contactlist_user_info(client_obj, asked):
    packet = CMResponse(eMsgID=0x02FE, client_obj=client_obj)

    clientId2 = 0x01100001
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


def build_persona_message(client_obj, state_flag, steamid_list):
    """This packet seems to only hold a MAXIMUM of 10 users per packet"""
    from steam3.ClientManager import Client_Manager

    packet = CMResponse(eMsgID = EMsg.ClientPersonaState, client_obj = client_obj)

    # Preparing packet data
    data = bytearray()
    clientId2 = 0x01100001
    rank = None
    data.extend(struct.pack('<HI',
                            len(steamid_list), int(state_flag)))

    for steamid in steamid_list:
        friend_obj = Client_Manager.clients_by_steamid.get(steamid)
        if friend_obj is None:
            friend_obj = friend_obj_empty()
            friend_obj.client_state = 0
            friend_obj.appID = 0
            friend_obj.app_ip_port = [0, 0]

        data += struct.pack('<II',
                            steamid * 2,
                            clientId2)

        if state_flag & PersonaStateFlags.status:
            data += (struct.pack('<BIIH',
                                 friend_obj.client_state,
                                 friend_obj.appID,
                                 friend_obj.app_ip_port[0],
                                 friend_obj.app_ip_port[1]))

        if state_flag & PersonaStateFlags.playerName:
            # print("Player Name: string (playername)")
            name = client_obj.get_friends_nickname(steamid)
            data += name.encode('latin-1') + b'\x00'

        if state_flag & PersonaStateFlags.queryPort:
            # This always seems to be 0xFFFF, no matter what the client is doing.
            # print("Query Port: 2 byte int")
            resetPortMask = 0xFFFF
            data += struct.pack('<H',
                                resetPortMask)

        if state_flag & PersonaStateFlags.sourceId:
            # print("Source ID: steamID 64 bit, gameserver or clan/chatroom id")
            #TODO grab sourceID from client_obj if they are in a clan
            client_clans_id, rank = client_obj.get_main_clan(steamid, ClanRelationship.member)
            if client_clans_id:
                sourceID = SteamID()
                sourceID.set_type(EType.CLAN)
                sourceID.set_instance(EInstanceFlag.ALL)  #clans should always be 0
                sourceID.set_universe(EUniverse.PUBLIC)
                sourceID.set_accountID(client_clans_id)
                sourceID._update_steamid()
                data += sourceID.get_raw_bytes_format()

                target_slice = slice(2, 6)
                current_flags = int.from_bytes(data[target_slice], byteorder='little')

                if not current_flags & PersonaStateFlags.clanInfo:
                    current_flags |= PersonaStateFlags.clanInfo

                # Write back the updated flags into the buffer
                data[target_slice.start:target_slice.stop] = current_flags.to_bytes(4, byteorder='little')
            else:
                data += struct.pack('<Q', 0)

        if state_flag & PersonaStateFlags.presence:
            # FIXME TINserver does not include the cmserver IP, but IDA shows it is infact used in 2007/2008

            # Commenting this out fixed the ip being part of the interpreted avatar hash.
            # NOTE: sometime after mid-2009, this is no longer part of the presence section
            data += struct.pack('>I',0)  # utils.ip_to_int(globalvars.server_ip))

            avatarID = client_obj.get_friend_avatarID(steamid)
            if avatarID is None:
                avatarID = b'fef49e7fa7e1997310d705b2a6158ff8dc1cdfeb'  # Default ? Avatar
                data += avatarID + b'\x00'
            else:
                # Try db provided hash, then ask forgiveness.
                try:
                    avatar_bytes = bytes.fromhex(avatarID.decode('latin-1'))
                    data += avatar_bytes + b'\x00'
                except Exception as e:
                    print(f"Error decoding avatarID: {e}")
                    # Ensure avatarID is null-terminated even in case of decoding failure
                    #avatarID += b'\x00'
                    data += avatarID + b'\x00'

        if state_flag & PersonaStateFlags.chatMetadata:
            #print("Metadata size: unsigned 4 bytes")
            #print("Metadata") # messageobject
            data += b'\x00' # Do not know what is supposed to go here...

        if state_flag & PersonaStateFlags.lastSeen:
            last_login, last_logoff = client_obj.get_friend_lastseen(steamid)
            data += last_logoff
            data += last_login
            # TODO At some point, this also includes the 'last online' field
        if state_flag & PersonaStateFlags.clanInfo:
            # Clan Rank
            if rank:
                data += struct.pack('<I', rank)
            else:
                data += struct.pack('<I', 0)
        if state_flag & PersonaStateFlags.extraInfo:
            #print("Game extra info (game name): 64-byte string")
            data += database.get_app_name(friend_obj.appID)
            # set to the currently playing APPID
            #print("Game/AppID: 64 bit int")
            data += struct.pack('<Q', friend_obj.appID)
        if state_flag & PersonaStateFlags.gameDataBlob:
            print("Game data blob size (or count?): 4 bytes")
            data += struct.pack('<I', 0)
            data += b'\x00'
        if state_flag & PersonaStateFlags.clanTag:
            # TODO I have not seen this flag in use in any packet captures
            #  According to Steamcooker's code, this is always a null byte for players
            #  But set for clans
            data += b'\x00'
        if state_flag & PersonaStateFlags.facebook:
            # NOTE: this is deprecated in later steam clients
            # TODO grab this information from community_profile for the user in question
            data += b'\x00'
            data += struct.pack('<Q', 0)
        if state_flag & PersonaStateFlags.richPresence:
            # print("Rich presence: 0x00")
            # TODO grab from rich presence, put in key/value format
            data += b'\x00'
        if state_flag & PersonaStateFlags.broadcastId:
            # TODO grab streaming ID from DB
            data += struct.pack('<Q', 0)
        if state_flag & PersonaStateFlags.gameLobbyId:
            # TODO grab streaming ID from DB
            data += struct.pack('<Q', 0)
        if state_flag & PersonaStateFlags.watchingBroadcast:
            # TODO grab broadcast info from DB
            data += struct.pack('<I', 0)  # accountid
            data += struct.pack('<I', 0)  # appid
            data += struct.pack('<I', 0)  # viewer count
            data += b'\x00' # broadcast/stream title

    packet.length = len(data)
    packet.data = bytes(data)

    return packet


def build_AddFriendResponse(cmserver_obj, client_obj, isold, request, requester_userid, searchStr, jobID):
    from steam3.ClientManager import Client_Manager

    if isold:
        packet = CMResponse(eMsgID = 0x0301, client_obj = client_obj)
    else:
        packet = CMResponse(eMsgID = 0x0318, client_obj = client_obj)

    packet_data = bytearray(struct.pack('<Q', jobID))
    friends_userid = database.find_user_by_name(searchStr)

    if friends_userid is None:
        if request.eMsgID == 0x02C9:  # old style
            packet_data += struct.pack('IIH', 0, 0, EResult.Invalid)  # 10 null bytes to signify no user found
        else:  # new style
            packet_data += struct.pack('III', 0, 0, EResult.AccountNotFound) + b"\x00"  # account not found
        packet.data = bytes(packet_data)
        packet.length = len(packet.data)
        return packet

    chatId = friends_userid * 2  # the id of the user requesting to add a user to their list
    clientId2 = 0x01100001
    packet_data += struct.pack('<I', chatId)
    packet_data += struct.pack('<I', clientId2)

    if friends_userid == requester_userid:
        if request.eMsgID == 0x02C9:  # old style
            packet_data += struct.pack('H', EResult.Invalid)  # if we find ourself we send 2 null bytes
        else:  # new style
            packet_data += struct.pack('I', EResult.InvalidParam) + b"\x00"
        packet.data = bytes(packet_data)
        packet.length = len(packet.data)
        return packet

    result = client_obj.add_friend(friends_userid)

    if not result:  # error adding friend to list, perhaps already there?
        packet_data += struct.pack('IIH', 0, 0, 0)  # 10 null bytes to signify no user found
        packet.data = bytes(packet_data)
        packet.length = len(packet.data)
        return packet

    addFriend_eResult = EResult.OK
    packet_data += struct.pack('<I', addFriend_eResult)
    packet_data += searchStr.encode('latin-1') + b'\x00'  # Append the name and a null terminator to the packed data

    friends_clientobj = Client_Manager.clients_by_steamid.get(friends_userid)

    if friends_clientobj:  # make sure they are online..
        cmserver_obj.sendReply(friends_clientobj, [build_friendslist_response(friends_clientobj)])  # send friend an updated list
        cmserver_obj.sendReply(friends_clientobj, [build_persona_message(friends_clientobj, client_obj.client_state, [client_obj.steamID])])
        cmserver_obj.sendReply(client_obj, [build_persona_message(client_obj, friends_clientobj.client_state, [friends_userid])])
    else:
        cmserver_obj.sendReply(client_obj, [build_persona_message(client_obj, PlayerState.offline, [friends_userid])])

    cmserver_obj.sendReply(client_obj, [build_friendslist_response(client_obj)])

    packet.data = bytes(packet_data)

    return packet


def build_AcceptFriendResponse(cmserver_obj, client_obj, request, friends_userid, jobID):
    from steam3.ClientManager import Client_Manager

    if request.eMsgID == 0x02C9:  # Old style add friend packet
        packet = CMResponse(eMsgID=0x0301, client_obj=client_obj)
    else:  # new style add friend packet
        packet = CMResponse(eMsgID=0x0318, client_obj=client_obj)

    clientId2 = 0x01100001
    packet_data = bytearray(struct.pack('<Q', jobID))

    chatId = friends_userid * 2  # the id of the user requesting to add a user to their list
    packet_data += struct.pack('<I', chatId)
    packet_data += struct.pack('<I', clientId2)

    if friends_userid == client_obj.steamID:
        if request.eMsgID == 0x02C9:  # old style
            packet_data += struct.pack('H', EResult.Invalid)  # if we find ourself we send 2 null bytes
        else:  # new style
            packet_data += struct.pack('I', EResult.InvalidParam) + b"\x00"
        packet.data = bytes(packet_data)
        packet.length = len(packet.data)
        return packet

    result = client_obj.add_friend(friends_userid, FriendRelationship.friend)

    addFriend_eResult = EResult.OK
    packet_data += struct.pack('<I', addFriend_eResult)
    searchStr = client_obj.get_friends_nickname(friends_userid)  # Get the friend's nickname
    packet_data += searchStr.encode('latin-1') + b'\x00'  # Append the name and a null terminator to the packed data

    friends_clientobj = Client_Manager.clients_by_steamid.get(friends_userid)
    if friends_clientobj:  # make sure they are online..
        cmserver_obj.sendReply(friends_clientobj, [build_friendslist_response(friends_clientobj)])  # send friend an updated list
        #cmserver_obj.sendReply(friends_clientobj, [build_contactlist_user_info(friends_clientobj, [friends_clientobj.steamID * 2])])
        cmserver_obj.sendReply(friends_clientobj, [build_persona_message(client_obj, PersonaStateFlags.status | PersonaStateFlags.playerName | PersonaStateFlags.sourceId |PersonaStateFlags.lastSeen | PersonaStateFlags.presence, [client_obj.steamID])])
        cmserver_obj.sendReply(client_obj, [build_persona_message(friends_clientobj, PersonaStateFlags.status | PersonaStateFlags.playerName | PersonaStateFlags.sourceId |PersonaStateFlags.lastSeen | PersonaStateFlags.presence, [friends_userid])])

    cmserver_obj.sendReply(client_obj, [build_friendslist_response(client_obj)])
    #cmserver_obj.sendReply(client_obj, [build_contactlist_user_info(client_obj, [friends_userid * 2])])

    packet.data = bytes(packet_data)

    return packet


def send_statuschange_to_friends(client_obj, cmserver_obj, Client_Manager, user_state):
    if client_obj and client_obj.friends_list:
        for friend_entry, friend_relationship in client_obj.get_friends_list_from_db():
            # Access friendsaccountID attribute from the FriendsList object
            friend_steamid = int(friend_entry.accountID)
            # Check if friend_steamid is in clients_by_steamid
            #for friendid in Client_Manager.clients_by_steamid:
            #print(f"currently online: {friendid}")

            #print(f"friend accountid: {friend_steamid}")
            if friend_steamid in Client_Manager.clients_by_steamid:
                client_friend = Client_Manager.clients_by_steamid.get(friend_steamid)
                if client_friend:
                    reply_packet = build_persona_message(client_friend,  PersonaStateFlags.status | PersonaStateFlags.playerName | PersonaStateFlags.sourceId | PersonaStateFlags.lastSeen | PersonaStateFlags.presence, [client_obj.steamID])
                    cmserver_obj.sendReply(client_friend, [reply_packet])

    if client_obj.username is None:
        client_obj.username = "[Unset]"

    if user_state != PlayerState.offline:
        reply_packet = build_persona_message(client_obj, PersonaStateFlags.status | PersonaStateFlags.playerName | PersonaStateFlags.sourceId |PersonaStateFlags.lastSeen | PersonaStateFlags.presence, [client_obj.steamID])
        cmserver_obj.sendReply(client_obj, [reply_packet])

    return -1

def build_SetIgnoreFriendResponse(cmserver_obj, client_obj, friends_steamID, friends_clientID2, status):
    """
    struct MsgClientSetIgnoreFriendResponse_t
    {
      uint64 m_ulFriendID;
      EResult m_eResult;
    };
    """
    from steam3.ClientManager import Client_Manager
    packet = CMResponse(eMsgID = EMsg.ClientSetIgnoreFriendResponse, client_obj = client_obj)

    packet.data = struct.pack('<III',
                              friends_steamID,
                              friends_clientID2,
                              status)

    cmserver_obj.sendReply(client_obj, [packet])
    if status:
        cmserver_obj.sendReply(client_obj, [build_friendslist_response(client_obj)])

        friends_accountID = (friends_steamID // 2)

        if friends_accountID in Client_Manager.clients_by_steamid:
            client_friend = Client_Manager.clients_by_steamid.get(friends_accountID)
            if client_friend:
                cmserver_obj.sendReply(client_friend, [build_friendslist_response(client_friend)])

    return -1