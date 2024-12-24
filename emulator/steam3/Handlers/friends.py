import struct

from steam3 import config
from steam3.ClientManager.client import Client
from steam3.Responses.friends_responses import build_AcceptFriendResponse, build_AddFriendResponse, build_InviteFriendResponse, build_SetIgnoreFriendResponse, build_friendslist_response, build_persona_message
from steam3.Types.community_types import PersonaStateFlags
from steam3.Types.steamid import SteamID
from steam3.cm_packet_utils import CMPacket
from steam3.utilities import decipher_persona_flags, getAccountId
from utilities.sendmail import send_friends_invite_email


def handle_InviteFriend(cmserver_obj, packet: CMPacket, client_obj: Client):
    """packetid: 793
    b'\x12\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00test@test.com\x00'"""

    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved Invite Friend Request")
    request = packet.CMRequest
    requestcount = struct.unpack("!I", request[:4])[0] # Not used ATM, for ratelimiting possibly?
    email_start_index = 12  # Adjust based on actual structure knowledge
    email_end_index = request.data.find(b'\x00', email_start_index)
    email_address = request.data[email_start_index:email_end_index].decode('latin-1')
    cmserver_obj.log.debug(f"RequestID: {requestcount} Email Address {email_address}")

    if config['smtp_enabled'].lower() == "true":
        send_friends_invite_email(email_address, client_address, client_obj.username)

    return [build_InviteFriendResponse(request)]


def handle_RemoveFriend(cmserver_obj, packet: CMPacket, client_obj: Client):
    # \xca\x02\x00\x00
    # \x02\x00\x00\x00
    # \x01\x00\x10\x01
    # \x00\x00\x00\x00
    # \x08\x00\x00\x00\x01\x00\x10\x01'

    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved  Remove User From Friends List")
    request = packet.CMRequest

    friendID = struct.unpack_from('<I', request.data, 0)[0] // 2
    print(f"remove friend id: {friendID}")
    client_obj.remove_friends(friendID)

    return [build_friendslist_response(client_obj)]


#2024-05-17 16:23:19     CMUDP27014    INFO     ('192.168.3.180', 53435) Client Requested to Add Friend
#2024-05-17 16:23:19     CMUDP27014    INFO     [new style] requestId: 4294967295, unknown1: 4294967295, unknown2: 8, unknown3: 17825793, searchStr:
#Empty nickname
#packet sent to client:
# 2024-05-17 16:23:19     CMUDP27014    INFO
# b'VS01 \x00\x06\x00\x00\x02\x00\x00\x00\x04\x00\x00\x07\x00\x00\x00\x0c\x00\x00\x00\x01\x00\x00\x00\x07\x00\x00\x00 \x00\x00\x00
# \x17\x03\x00\x00
# \x02\x00\x00\x00
# \x01\x00\x10\x01
# \x00\x00\x00\x00

# \xff\xff\xff\xff\xff\xff\xff\xff
# \x08\x00\x00\x00\x01\x00\x10\x01'

def handle_AddFriend(cmserver_obj, packet: CMPacket, client_obj: Client):
    client_address = client_obj.ip_port
    request = packet.CMRequest

    isold = False
    friends_userid = None
    jobID, friends_userid = struct.unpack_from('<QQ', request.data, 0)
    searchStr = request.data[16:].decode('latin-1').rstrip("\x00")
    friends_userid = SteamID(friends_userid)
    if len(searchStr) > 0:
        cmserver_obj.log.info(f"{client_address} Client Requested to Add Friend\n data: {request.data}")
    else:
        cmserver_obj.log.info(f"{client_address} Client Accepted A Friend Request\n data: {friends_userid.account_number}")

    # send list of people with similar names
    if request.eMsgID == 0x02C9:  # Old style add friend packet
        packet.eMsgID = 0x0301
        cmserver_obj.log.info(f"[old style] Username searched: {searchStr} Friends UserID: {friends_userid}")
        isold = True
        """jobID, friends_userid = struct.unpack_from('<QQ', request.data, 0)
        # when adding a friend: 
        # b'\r\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00test22\x00' """
        # accepting a friend request results in this:
        # b'\xff\xff\xff\xff\xff\xff\xff\xff\x04\x00\x00\x00\x01\x00\x10\x01'
    else:  # new style add friend packet
        """jobID, friends_userid = struct.unpack_from('<QQ', request.data, 0)
        searchStr = request.data[16:].decode('latin-1').rstrip("\x00")  # Assuming searchStr encoding is Latin-1"""
        cmserver_obj.log.info(f"[new style] Job ID: {jobID} Userid: {friends_userid}, searchStr: {searchStr}")
        packet.eMsgID = 0x0318

    if friends_userid.account_number != 0:
        return build_AcceptFriendResponse(cmserver_obj, client_obj, request, friends_userid.account_number, jobID)

    requester_userid = getAccountId(request)
    # unknown1 = struct.unpack_from('<I', request.data, 0)[0]

    return build_AddFriendResponse(cmserver_obj,  client_obj, isold, request, requester_userid, searchStr, jobID)


def handle_RequestFriendData(cmserver_obj, packet, client_obj):
    """responds with persona state response
    packetid: 815
    b'R\x00\x00\x00\x01\x00\x00\x00\x02\x00\x00\x00\x01\x00\x10\x01'"""
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved Friend Data Request")
    request = packet.CMRequest
    # persona flag == PersonaStateFlag_none
    persona_flag, usercount = struct.unpack_from('<II', request.data, 0)

    # Initialize the offset after the first 8 bytes (which we've already read)
    offset = 8
    steam_ids = []

    print(f"Friend Data Request Persona Flag: {decipher_persona_flags(persona_flag)}")
    # Loop over usercount to read each Steam ID (8 bytes each)
    while usercount > 0:
        # Unpack 8 bytes from the current offset as a Steam ID
        steam_id, clientID = struct.unpack_from('<II', request.data, offset)
        steam_ids.append(steam_id//2)

        # Advance the offset by 8 bytes for the next Steam ID
        offset += 8
        usercount -= 1  # Decrement the usercount

    return build_persona_message(client_obj, persona_flag, steam_ids)


def handle_GetFriendsUserInfo(cmserver_obj, packet: CMPacket, client_obj: Client):
    # TODO this packet is supposed to return a persona state packet, but something doesnt add-up atm
    #   b'\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x006\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xacJ\x00\x00\x00\x00\x00\x00\x00'
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Client requested friendslist user info")
    # Extract the number of asked contacts from eMsgID data
    nbAsked = struct.unpack_from('<I', request.data, 0)[0]
    # print(f"nbAsked: {nbAsked}")
    requested_friendids = []
    for ind in range(nbAsked):
        # Extract each asked accountId
        accountId = struct.unpack_from('<I', request.data, 4 + 8 * ind)[0]
        requested_friendids.append(accountId)
    #return build_contactlist_user_info(client_obj, requested_friendids)
    return build_persona_message(client_obj, 0x02, requested_friendids)

def handle_SetIgnoreFriend(cmserver_obj, packet: CMPacket, client_obj: Client):
    """data: b'\x02\x00\x00\x00\x01\x00\x10\x01\x0c\x00\x00\x00\x01\x00\x10\x01\x01'"""
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Client Requested To Un/Block Friend")

    requesting_steamID, requesting_clientID2, blocking_steamID, blocking_clientID2, toBlock = struct.unpack_from('<IIIIB', request.data, 0)
    result = client_obj.block_friend(blocking_steamID // 2, toBlock)

    return build_SetIgnoreFriendResponse(cmserver_obj, client_obj, blocking_steamID, blocking_clientID2, result)