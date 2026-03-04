import struct

from steam3.Responses.auth_responses import build_account_info_response
from steam3.cm_packet_utils import CMPacket

from steam3 import config
from steam3.ClientManager.client import Client
from steam3.Responses.friends_responses import build_AcceptFriendResponse, build_AddFriendResponse, build_InviteFriendResponse, build_SetIgnoreFriendResponse, build_friendslist_response, build_persona_message
from steam3.Types.community_types import PersonaStateFlags, PlayerState, RequestedPersonaStateFlags_self
from steam3.Types.steamid import SteamID
from steam3.cm_packet_utils import CMPacket
from steam3.utilities import decipher_persona_flags
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
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved Remove Friend Request")
    request = packet.CMRequest

    friendID = struct.unpack_from('<I', request.data, 0)[0] // 2
    print(f"Remove friend id: {friendID}")
    client_obj.remove_friends(friendID)

    return [build_friendslist_response(client_obj, proto=packet.is_proto)]


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
    jobID = 0
    friendSteamID = None
    searchStr = ""

    if packet.is_proto:
        # Parse protobuf format
        from steam3.protobufs.steammessages_clientserver_friends_pb2 import CMsgClientAddFriend
        proto_msg = CMsgClientAddFriend()
        try:
            proto_msg.ParseFromString(request.data)
            if proto_msg.HasField('steamid_to_add') and proto_msg.steamid_to_add != 0:
                friendSteamID = SteamID.from_raw(proto_msg.steamid_to_add)
            if proto_msg.HasField('accountname_or_email_to_add'):
                searchStr = proto_msg.accountname_or_email_to_add
            cmserver_obj.log.info(f"{client_address} Client Requested to Add Friend (protobuf): steamid={friendSteamID.get_accountID()}, search={searchStr}")
        except Exception as e:
            cmserver_obj.log.error(f"Failed to parse CMsgClientAddFriend: {e}")
            return -1
    else:
        # Parse legacy clientmsg format
        jobID, friendSteamID_raw = struct.unpack_from('<QQ', request.data, 0)
        searchStr = request.data[16:].decode('latin-1').rstrip("\x00")
        friendSteamID = SteamID.from_raw(friendSteamID_raw)
        if len(searchStr) > 0:
            cmserver_obj.log.info(f"{client_address} Client Requested to Add Friend\n data: {request.data}")
        else:
            cmserver_obj.log.info(f"{client_address} Client Accepted A Friend Request\n data: {friendSteamID.get_accountID()}")

        # send list of people with similar names
        if request.eMsgID == 0x02C9:  # Old style add friend packet
            packet.eMsgID = 0x0301
            cmserver_obj.log.info(f"[old style] Username searched: {searchStr} Friends UserID: {friendSteamID.get_accountID()}")
            isold = True
        else:  # new style add friend packet
            cmserver_obj.log.info(f"[new style] Job ID: {jobID} Userid: {friendSteamID.get_accountID}, searchStr: {searchStr}")
            packet.eMsgID = 0x0318

    if friendSteamID and friendSteamID.get_accountID() != 0:
        return build_AcceptFriendResponse(cmserver_obj, client_obj, request, friendSteamID.get_accountID(), jobID, proto=packet.is_proto)

    return build_AddFriendResponse(cmserver_obj, client_obj, isold, request, searchStr, jobID, proto=packet.is_proto)


def handle_RequestFriendData(cmserver_obj, packet: CMPacket, client_obj: Client):
    """responds with persona state response
    packetid: 815
    b'R\x00\x00\x00\x01\x00\x00\x00\x02\x00\x00\x00\x01\x00\x10\x01'"""
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved Friend Data Request")
    request = packet.CMRequest

    accountIDs = []

    if packet.is_proto:
        # Parse protobuf format
        from steam3.protobufs.steammessages_clientserver_friends_pb2 import CMsgClientRequestFriendData
        proto_msg = CMsgClientRequestFriendData()
        try:
            proto_msg.ParseFromString(request.data)
            persona_flag = proto_msg.persona_state_requested if proto_msg.HasField('persona_state_requested') else 0
            for friend_steamid in proto_msg.friends:
                steamID = SteamID.from_integer(friend_steamid)
                accountIDs.append(steamID.get_accountID())
        except Exception as e:
            cmserver_obj.log.error(f"Failed to parse CMsgClientRequestFriendData: {e}")
            return -1
    else:
        # Parse legacy clientmsg format
        # persona flag == PersonaStateFlag_none
        persona_flag, usercount = struct.unpack_from('<II', request.data, 0)

        # Initialize the offset after the first 8 bytes (which we've already read)
        offset = 8

        print(f"Friend Data Request Persona Flag: {decipher_persona_flags(persona_flag)}")
        # Loop over usercount to read each Steam ID (8 bytes each)
        while usercount > 0:
            # Unpack 8 bytes from the current offset as a Steam ID
            steamIDBytes = struct.unpack_from('<Q', request.data, offset)[0]
            steamID = SteamID.from_integer(steamIDBytes)
            accountIDs.append(steamID.get_accountID())

            # Advance the offset by 8 bytes for the next Steam ID
            offset += 8
            usercount -= 1  # Decrement the usercount

    return build_persona_message(client_obj, persona_flag, accountIDs, proto=packet.is_proto)


def handle_GetFriendsUserInfo(cmserver_obj, packet: CMPacket, client_obj: Client):

    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Client requested friendslist user info")

    # 1) Read the 4?byte count
    nbAsked = struct.unpack_from('<I', request.data, 0)[0]

    requestedAccountIDs = []
    offset = 4     # skip past that 4?byte integer

    for _ in range(nbAsked):
        # 2) unpack a single 8?byte little?endian SteamID
        steamid_int = struct.unpack_from('<Q', request.data, offset)[0]
        offset += 8

        # 3) convert to SteamID and pull the accountID
        steamid = SteamID.from_integer(steamid_int)
        requestedAccountIDs.append(steamid.get_accountID())

    #return build_contactlist_user_info(client_obj, requestedAccountIDs)
    return build_persona_message(client_obj, 0x02, requestedAccountIDs)


def handle_SetIgnoreFriend(cmserver_obj, packet: CMPacket, client_obj: Client):
    """data: b'\x02\x00\x00\x00\x01\x00\x10\x01\x0c\x00\x00\x00\x01\x00\x10\x01\x01'"""
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Client Requested To Un/Block Friend")

    requestingSteamID, blockedSteamID, toBlock = struct.unpack_from('<QQB', request.data, 0)
    blockedSteamID = SteamID.from_raw(blockedSteamID)
    result = client_obj.block_friend(blockedSteamID.get_accountID(), toBlock)

    return build_SetIgnoreFriendResponse(cmserver_obj, client_obj, blockedSteamID, result)


def handle_ClientChangeStatus(cmserver_obj, packet: CMPacket, client_obj: Client):
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"{client_address} Client Change Status Request")

    if packet.is_proto:
        # Parse protobuf format
        from steam3.protobufs.steammessages_clientserver_friends_pb2 import CMsgClientChangeStatus
        proto_msg = CMsgClientChangeStatus()
        proto_msg.ParseFromString(request.data)
        userStateFlag = proto_msg.persona_state if proto_msg.HasField('persona_state') else 1
        pktNickname = proto_msg.player_name if proto_msg.HasField('player_name') else ""
    else:
        # Parse binary format
        userStateFlag = int.from_bytes(request.data[0:1], 'little')
        pktNickname = request.data[1:].decode('latin-1').rstrip("\x00")

    # Clamp to valid PlayerState range to avoid enum errors
    max_valid_state = max(ps.value for ps in PlayerState)
    if userStateFlag > max_valid_state:
        cmserver_obj.log.warning(f"Received unknown PlayerState {userStateFlag}, clamping to online (1)")
        userStateFlag = 1  # Default to online

    # Last byte is to say true/false if it is a known nickname
    if userStateFlag > 0 or userStateFlag is not None:
        nickname = client_obj.update_status_info(cmserver_obj, PlayerState(userStateFlag), username = pktNickname)
    else:
        client_obj.exit_app(cmserver_obj)
    packet_list = [
        build_persona_message(client_obj, RequestedPersonaStateFlags_self, [client_obj.accountID], proto=packet.is_proto),
        build_account_info_response(cmserver_obj, client_obj, pktNickname, proto=packet.is_proto)
    ]

    return packet_list
