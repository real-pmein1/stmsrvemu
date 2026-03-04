import struct
import logging
from steam3.messages.MsgClientChatMsg import MsgClientChatMsg
from steam3 import chatroom_manager
from steam3.ClientManager.client import Client
from steam3.Types.chat_types import ChatActionResult, ChatRoomEnterResponse, ChatRoomType
from steam3.Types.emsg import EMsg
from steam3.Types.steam_types import EInstanceFlag, EResult, EType, EUniverse
from steam3.Types.steamid import SteamID
from steam3.cm_packet_utils import CMResponse
from steam3.messages.MsgClientCreateChat import MsgClientCreateChat

log = logging.getLogger("ChatResponses")


def build_send_friendsmsg(client_obj: Client, message):
    packet = CMResponse(eMsgID = 0x02CE, client_obj = client_obj)  # Assuming CMPacket is defined somewhere

    # Prepare message content and calculate packet length
    message_content = message.message.encode('latin-1') + b'\x00'  # Null-terminated
    #packet.length = 24 + len(message_content)

    packet.data = struct.pack('QI',
                               message.fromSteamID.get_integer_format(),
                               message.type)  # type attribute, with default

    packet.data += message_content  # message attribute

    packet.length = len(packet.data)
    return packet

def build_ChatroomMsg(client_obj: Client, chatroom_id: int, sender_id: int, entry_type, message_data: bytes):
    """
    Build a MsgClientChatMsg response to broadcast to chatroom members.
    """
    msg = MsgClientChatMsg(client_obj)
    msg.chatGlobalId = chatroom_id
    msg.memberGlobalId = sender_id
    msg.entryType = entry_type
    msg.data = message_data
    return msg.to_clientmsg()

def build_CreateChat_response(client_obj, chatroom_id: int, room_type: ChatRoomType, friend_chat_id: int = 0, success: bool = True):
    """
    struct MsgClientCreateChatResponse_t
    {
      EResult m_eResult;
      uint64 m_ulSteamIDChat;
      EChatRoomType m_eType;
      uint64 m_ulSteamIDFriendChat;
    };
    """
    createResponse = CMResponse(eMsgID = EMsg.ClientCreateChatResponse, client_obj = client_obj)
    
    # Format string: < indicates little-endian, I for uint32, Q for uint64
    format_str = '<IQIQ'
    
    result = EResult.OK if success else EResult.Fail

    # Pack the data according to the specified format
    createResponse.data = struct.pack(
            format_str,
            int(result),  # EResult (uint32)
            chatroom_id,  # uint64 m_ulSteamIDChat
            int(room_type),  # EChatRoomType (uint32)
            friend_chat_id  # uint64 m_ulSteamIDFriendChat
    )

    createResponse.length = len(createResponse.data)
    return createResponse


def build_ChatEnter_response(client_obj, chatroom, enter_result: ChatRoomEnterResponse, chatroom_id: int = None):
    """MsgClientChatEnter_t
    {
      uint64 m_ulSteamIDChat;
      uint64 m_ulSteamIDFriendChat;
      uint32 m_EChatRoomType;
      uint64 m_ulSteamIDOwner;
      uint64 m_ulSteamIDClan;
      uint8 m_bLocked;
      uint32 m_EChatRoomEnterResponse;
      uint32 m_cMembersTotal;
      char m_rgchChatRoomName[];  // null-terminated
      // followed by ChatMemberInfo for each member
    };"""
    from steam3.Types.MessageObject.ChatMemberInfo import ChatMemberInfo

    packet = CMResponse(eMsgID = EMsg.ClientChatEnter, client_obj = client_obj)

    if chatroom is None:
        # Error case - send minimal response
        format_str = '<QQIQQBII'
        packet.data = struct.pack(
            format_str,
            chatroom_id or 0,  # uint64 m_ulSteamIDChat
            0,  # uint64 m_ulSteamIDFriendChat
            int(ChatRoomType.MUC),  # uint32 EChatRoomType
            0,  # uint64 m_ulSteamIDOwner
            0,  # uint64 m_ulSteamIDClan
            0,  # uint8 m_bLocked
            int(enter_result),  # uint32 EChatRoomEnterResponse
            0,  # uint32 m_cMembersTotal
        )
        # Null-terminated room name for error case
        packet.data += b'\x00'
        # maxMembersCount at the end
        packet.data += struct.pack('<I', 0)
    else:
        # Valid chatroom - populate with real data
        format_str = '<QQIQQBII'
        member_count = len(chatroom.members) if hasattr(chatroom, 'members') else 1

        # Convert owner accountID to full Steam ID (client expects 64-bit Steam ID)
        owner_steam_id = SteamID.createSteamIDFromAccountID(chatroom.owner_id)

        # DEBUG: Log chatroom details for permissions investigation
        log.debug(f"ChatEnter Response - Chatroom Details:")
        log.debug(f"  chatroom.steam_id: {chatroom.steam_id:016x}")
        log.debug(f"  chatroom.owner_id (accountID): {chatroom.owner_id}")
        log.debug(f"  owner_steam_id (64-bit): {int(owner_steam_id):016x}")
        log.debug(f"  chatroom.room_type: {chatroom.room_type}")
        log.debug(f"  member_count: {member_count}")
        log.debug(f"  enter_result: {enter_result}")
        if hasattr(chatroom, 'member_permission'):
            log.debug(f"  chatroom.member_permission: 0x{chatroom.member_permission:04x}")

        packet.data = struct.pack(
            format_str,
            chatroom.steam_id,  # uint64 m_ulSteamIDChat
            0,  # uint64 m_ulSteamIDFriendChat
            int(chatroom.room_type),  # uint32 EChatRoomType
            int(owner_steam_id),  # uint64 m_ulSteamIDOwner (full Steam ID, not accountID)
            chatroom.clan_id if hasattr(chatroom, 'clan_id') else 0,  # uint64 m_ulSteamIDClan
            1 if (hasattr(chatroom, 'locked') and chatroom.locked) else 0,  # uint8 m_bLocked
            int(enter_result),  # uint32 EChatRoomEnterResponse
            member_count,  # uint32 m_cMembersTotal
        )

        # Null-terminated room name (not fixed 128 bytes for newer format)
        name = chatroom.name if hasattr(chatroom, 'name') else 'Steam3ChatRoom'
        packet.data += (name + '\x00').encode('utf-8', errors='replace')

        # Append ChatMemberInfo for each member in the chatroom
        # Uses KeyValues binary serialization format (same as tinserver)
        if hasattr(chatroom, 'members'):
            log.debug(f"  Serializing {len(chatroom.members)} members using KeyValues format:")
            for member_steam_id, member in chatroom.members.items():
                # Ensure member_steam_id is int for proper serialization
                steam_id_int = int(member_steam_id)
                permissions = member.permissions
                details = 0  # Details (rank info) - reserved for future use

                # DEBUG: Log each member's info
                log.debug(f"    Member SteamID: {steam_id_int:016x}, "
                         f"Permissions: 0x{permissions:04x}, "
                         f"IsOwner: {int(SteamID.from_raw(steam_id_int).get_accountID()) == chatroom.owner_id}")

                # Create ChatMemberInfo object and serialize using KeyValues format
                member_info = ChatMemberInfo()
                member_info.set_SteamID(steam_id_int)
                member_info.set_Permissions(permissions)
                member_info.set_Details(details)

                member_data = member_info.serialize()
                log.debug(f"    Serialized ChatMemberInfo (KeyValues, {len(member_data)} bytes): {member_data.hex()}")
                packet.data += member_data
        else:
            log.warning(f"  WARNING: chatroom has no 'members' attribute!")

        # Add maxMembersCount at the end (expected by client per tinserver format)
        max_members = chatroom.max_members if hasattr(chatroom, 'max_members') else 0
        packet.data += struct.pack('<I', max_members)

    packet.length = len(packet.data)
    return packet


def build_ChatAction_response(client_obj, chatroom_id: int, target_id: int, action, action_result: ChatActionResult):
    """
    Build response for chat actions like kick, ban, etc.
    MsgClientChatActionResult_t structure based on IDA analysis
    """
    from steam3.Types.emsg import EMsg
    
    packet = CMResponse(eMsgID = EMsg.ClientChatActionResult, client_obj = client_obj)
    
    # MsgClientChatActionResult_t format
    format_str = '<QQII'
    packet.data = struct.pack(
        format_str,
        chatroom_id,  # uint64 m_ulSteamIDChat
        target_id,    # uint64 m_ulSteamIDUserActedOn
        int(action),  # uint32 m_eChatAction
        int(action_result)  # uint32 m_eResult
    )
    
    packet.length = len(packet.data)
    return packet


def build_ChatMessage_broadcast(client_obj, chatroom_id: int, sender_id: int, message_type, message_data: bytes):
    """
    Build a chat message broadcast to be sent to all chatroom members.
    MsgClientChatMsg_t structure based on IDA analysis
    """
    from steam3.Types.emsg import EMsg

    packet = CMResponse(eMsgID = EMsg.ClientChatMsg, client_obj = client_obj)

    # MsgClientChatMsg_t format: memberGlobalId, chatGlobalId, entryType, data
    format_str = '<QQI'
    packet.data = struct.pack(
        format_str,
        sender_id,    # uint64 m_ulSteamIDChatter (sender)
        chatroom_id,  # uint64 m_ulSteamIDChat (chatroom)
        int(message_type)  # uint32 m_eChatEntryType
    )

    packet.data += message_data
    packet.length = len(packet.data)
    return packet


def build_ChatEnter(client_obj: Client, chatroom_account_id: int, enter_result: ChatRoomEnterResponse, member_info_list: list = None):
    """
    Wrapper function for chatroom.py compatibility.
    Builds ChatEnter response given a chatroom accountID (not full chatroom object).

    Args:
        client_obj: The client object
        chatroom_account_id: The chatroom's accountID
        enter_result: ChatRoomEnterResponse enum value
        member_info_list: Optional list of ChatMemberInfo objects
    """
    from steam3.Types.MessageObject.ChatMemberInfo import ChatMemberInfo

    packet = CMResponse(eMsgID = EMsg.ClientChatEnter, client_obj = client_obj)

    # Look up chatroom to get full details
    chatroom = None
    try:
        chatroom = chatroom_manager.get_chatroom_by_id(chatroom_account_id)
    except:
        pass

    if chatroom is None or enter_result != ChatRoomEnterResponse.success:
        # Error case - build minimal response
        # Generate Steam ID from accountID
        chat_steam_id = SteamID()
        chat_steam_id.set_from_identifier(chatroom_account_id, EUniverse.PUBLIC, EType.CHAT, EInstanceFlag.ALL)

        format_str = '<QQIQQBII'
        packet.data = struct.pack(
            format_str,
            int(chat_steam_id),  # uint64 m_ulSteamIDChat
            0,  # uint64 m_ulSteamIDFriendChat
            int(ChatRoomType.MUC),  # uint32 EChatRoomType
            0,  # uint64 m_ulSteamIDOwner
            0,  # uint64 m_ulSteamIDClan
            0,  # uint8 m_bLocked
            int(enter_result),  # uint32 EChatRoomEnterResponse
            0,  # uint32 m_cMembersTotal
        )
        # Error case: null-terminated name followed by maxMembersCount
        packet.data += b'\x00'  # null-terminated empty name
        packet.data += struct.pack('<I', 0)  # maxMembersCount = 0
        packet.length = len(packet.data)
        return [packet]

    # Valid chatroom - populate with real data
    format_str = '<QQIQQBII'
    member_count = chatroom.get_member_count() if hasattr(chatroom, 'get_member_count') else 1

    # Convert owner accountID to full Steam ID (client expects 64-bit Steam ID)
    owner_steam_id = SteamID.createSteamIDFromAccountID(chatroom.owner_accountID)

    packet.data = struct.pack(
        format_str,
        int(chatroom.steamID),  # uint64 m_ulSteamIDChat
        0,  # uint64 m_ulSteamIDFriendChat
        int(chatroom.chatType),  # uint32 EChatRoomType
        int(owner_steam_id),  # uint64 m_ulSteamIDOwner (full Steam ID, not accountID)
        chatroom.associated_groupID or 0,  # uint64 m_ulSteamIDClan
        1 if (chatroom.flags & 0x01) else 0,  # uint8 m_bLocked
        int(enter_result),  # uint32 EChatRoomEnterResponse
        member_count,  # uint32 m_cMembersTotal
    )

    name = chatroom.name if hasattr(chatroom, 'name') else 'Steam3ChatRoom'
    chatroom_name = (name + '\x00').encode('utf-8', errors='replace')

    packet.data += chatroom_name

    # Append ChatMemberInfo list if provided
    # Uses KeyValues binary serialization format (same as tinserver)
    if member_info_list:
        for member_info in member_info_list:
            if isinstance(member_info, ChatMemberInfo):
                # ChatMemberInfo object - serialize directly using KeyValues format
                packet.data += member_info.serialize()
            elif hasattr(member_info, 'serialize'):
                # Legacy MessageObject path - use its serialize method
                packet.data += member_info.serialize()
            elif isinstance(member_info, dict):
                # Direct dict format - create ChatMemberInfo and serialize
                info = ChatMemberInfo()
                info.set_SteamID(int(member_info.get('steam_id', 0)))
                info.set_Permissions(member_info.get('permissions', 0))
                info.set_Details(member_info.get('details', 0))
                packet.data += info.serialize()

    # Add maxMembersCount at the end (expected by client per tinserver format)
    max_members = 0  # Default to 0 (unlimited)
    if chatroom and hasattr(chatroom, 'max_members'):
        max_members = chatroom.max_members
    packet.data += struct.pack('<I', max_members)

    packet.length = len(packet.data)
    return [packet]  # Return as list for compatibility with sendReply