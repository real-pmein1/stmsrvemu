import struct
import logging
from steam3.Types.steamid import SteamID
from steam3.ClientManager import Client_Manager
from steam3.Responses.general_responses import build_GeneralAck

from steam3.ClientManager.client import Client
from steam3.cm_packet_utils import CMPacket, ChatMessage
from steam3.messages.MsgClientCreateChat import MsgClientCreateChat
from steam3.messages.MSGClientJoinChat import MSGClientJoinChat
from steam3.messages.MsgClientChatMsg import MsgClientChatMsg
from steam3.messages.MsgClientChatAction import MsgClientChatAction
from steam3.messages.MsgClientChatInvite import MsgClientChatInvite
from steam3.Responses.chat_responses import (
    build_CreateChat_response, build_ChatEnter_response,
    build_ChatAction_response, build_send_friendsmsg
)
from steam3.Managers.ChatroomManager.manager import ChatroomManager
from steam3.Types.chat_types import (
    ChatRoomType, ChatEntryType, ChatAction, ChatActionResult,
    ChatRoomEnterResponse, ChatMemberStateChange
)
from steam3.Types.steam_types import EResult

log = logging.getLogger("ChatHandlers")

def get_chatroom_manager():
    """Get the global chatroom manager instance from steam3"""
    import steam3
    return steam3.chatroom_manager



def handle_ClientCreateChat(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle ClientCreateChat packet (EMsg 809)
    
    Based on 2008 client decompiled analysis:
    - This handler serves BOTH chatrooms AND lobbies  
    - Lobbies are chatrooms with ChatRoomType.lobby
    - Early clients expect unified handling via this single endpoint
    - Steam ID generation must use proper instance flags for client recognition
    """
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received ClientCreateChat")
    
    try:
        # Parse the request
        msg = MsgClientCreateChat(client_obj, request.data)
        
        room_type_str = "lobby" if msg.m_eType == ChatRoomType.lobby else "chatroom"
        cmserver_obj.log.debug(f"CreateChat ({room_type_str}): type={msg.m_eType}, gameId={msg.m_ulGameID}, "
                              f"membersMax={msg.m_cMembersMax}, flags/locked=0x{msg.m_bLocked:02x}, "
                              f"name='{msg.chatroom_name}'")
        
        # Get chatroom manager and create chatroom (handles both chatrooms and lobbies)
        chatroom_manager = get_chatroom_manager()
        
        # Note: owner_id should be an accountID, not a full SteamID64
        # Extract accountID from SteamIDs for invited_id as well
        # Convert to int explicitly since get_accountID() returns an AccountID wrapper
        invited_account_id = int(SteamID.from_raw(int(msg.m_ulSteamIDInvited)).get_accountID()) if int(msg.m_ulSteamIDInvited) != 0 else 0

        chat_steam_id = chatroom_manager.register_chatroom(
            owner_id=client_obj.accountID,  # Use accountID, not full SteamID
            room_type=ChatRoomType(msg.m_eType),
            name=msg.chatroom_name,
            clan_id=int(msg.m_ulSteamIDClan),
            game_id=msg.m_ulGameID,
            officer_permission=msg.m_rgfPermissionOfficer,
            member_permission=msg.m_rgfPermissionMember,
            all_permission=msg.m_rgfPermissionAll,
            max_members=msg.m_cMembersMax,
            flags=msg.m_bLocked,
            friend_chat_id=int(msg.m_ulSteamIDFriendChat),
            invited_id=invited_account_id  # Use accountID for invited user
        )
        
        # Build and send response
        if chat_steam_id != 0:
            final_chat_steam_id = chat_steam_id  # Use chatroom manager's ID
            
            # Build CreateChat response with the appropriate Steam ID
            response = build_CreateChat_response(
                client_obj, final_chat_steam_id, msg.m_eType, int(msg.m_ulSteamIDFriendChat), success=True
            )
            
            # Automatically enter the creator into the chatroom/lobby and send ChatEnter response
            chatroom = chatroom_manager.get_chatroom(chat_steam_id)
            cmserver_obj.log.debug(f"Looking up chatroom with Steam ID: {chat_steam_id:x}, found: {chatroom is not None}")
            
            if chatroom:
                # Enter the chatroom (works for both regular chats and lobbies)
                # Convert steamID to int for proper dict key storage and serialization
                enter_result = chatroom.enter_chatroom(int(client_obj.steamID), False)
                cmserver_obj.log.debug(f"Player entered chatroom with result: {enter_result}")

                # If entry was successful, broadcast member state change to existing members (if any)
                if enter_result == ChatRoomEnterResponse.success and len(chatroom.members) > 1:
                    chatroom_manager.broadcast_member_state_change(
                        chatroom, int(client_obj.steamID),
                        ChatMemberStateChange.entered,
                        int(client_obj.steamID)
                    )

                # Send pending invites to online users AFTER the owner has joined
                # This is critical for new rooms - invites are stored during register_chatroom()
                # but must be sent after the owner enters so they have a valid room to join
                if enter_result == ChatRoomEnterResponse.success and chatroom.pending_invites:
                    cmserver_obj.log.debug(f"Sending {len(chatroom.pending_invites)} pending invites for new chatroom")
                    for invitee_id, inviter_id in list(chatroom.pending_invites.items()):
                        chatroom_manager._send_invite_to_user(chatroom, inviter_id, invitee_id)

                # Send ChatEnter response for proper client sequence
                enter_response = build_ChatEnter_response(
                    client_obj, chatroom, enter_result, chatroom_id=final_chat_steam_id
                )
                cmserver_obj.log.debug(f"Sending CreateChat response and ChatEnter response")
                return [response, enter_response]
            else:
                cmserver_obj.log.warning(f"Failed to find chatroom with Steam ID: {chat_steam_id:x} for auto-enter")
                return response
        else:
            response = build_CreateChat_response(
                client_obj, 0, msg.m_eType, int(msg.m_ulSteamIDFriendChat), success=False
            )
        
        return response
        
    except Exception as e:
        cmserver_obj.log.error(f"Error handling ClientCreateChat: {e}")
        # Send failure response
        response = build_CreateChat_response(client_obj, 0, ChatRoomType.MUC, 0, success=False)
        return response


def handle_ClientJoinChat(cmserver_obj, packet: CMPacket, client_obj: Client):
    """Handle ClientJoinChat packet (EMsg 801)"""
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received ClientJoinChat")
    
    try:
        # Parse the request
        msg = MSGClientJoinChat(client_obj, request.data)
        
        cmserver_obj.log.debug(f"JoinChat: chatGlobalId={msg.chatGlobalId}, "
                              f"voiceSpeaker={msg.voiceSpeaker}")
        
        # Get chatroom manager and find chatroom
        chatroom_manager = get_chatroom_manager()
        chatroom = chatroom_manager.get_chatroom(msg.chatGlobalId)
        
        if chatroom:
            # Attempt to enter chatroom
            # Convert steamID to int for proper dict key storage and serialization
            enter_result = chatroom.enter_chatroom(int(client_obj.steamID), msg.voiceSpeaker)

            # If join was successful, broadcast member state change to existing members
            if enter_result == ChatRoomEnterResponse.success:
                chatroom_manager.broadcast_member_state_change(
                    chatroom, int(client_obj.steamID),
                    ChatMemberStateChange.entered,
                    int(client_obj.steamID)
                )

            # Build and return ChatEnter response
            response = build_ChatEnter_response(client_obj, chatroom, enter_result)
            return response
        else:
            # Chatroom doesn't exist
            response = build_ChatEnter_response(
                client_obj, None, ChatRoomEnterResponse.doesntExist, msg.chatGlobalId
            )
            return response
        
    except Exception as e:
        cmserver_obj.log.error(f"Error handling ClientJoinChat: {e}")
        # Send error response
        response = build_ChatEnter_response(client_obj, None, ChatRoomEnterResponse.error)
        return response


def handle_ClientChatInvite(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle ClientChatInvite packet (EMsg 800)

    This is sent by a client when they want to invite another user to a chatroom.
    The server should:
    1. Validate the inviter has permission to invite
    2. Forward the invite to the target user
    """
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received ClientChatInvite")

    try:
        # Parse the request
        msg = MsgClientChatInvite.deserialize(client_obj, request.data)

        cmserver_obj.log.debug(f"ChatInvite: invitee={msg.invitedSteamID:016x}, "
                              f"chatroom={msg.chatroomSteamID:016x}, "
                              f"patron={msg.patronSteamID:016x}, "
                              f"roomType={msg.chat_room_type}")

        # Get chatroom manager
        chatroom_manager = get_chatroom_manager()

        # Find the chatroom
        chatroom = chatroom_manager.get_chatroom(msg.chatroomSteamID)

        if chatroom is None:
            cmserver_obj.log.warning(f"ChatInvite: chatroom {msg.chatroomSteamID:016x} not found")
            return -1

        # Use full 64-bit steam IDs (members are stored by steam ID, not account ID)
        inviter_steam_id = int(client_obj.steamID)
        invitee_steam_id = msg.invitedSteamID

        # Verify the client sending the invite is a member with invite permission
        # For now, allow all members to invite (basic permission check)
        if not chatroom.is_member(inviter_steam_id):
            cmserver_obj.log.warning(f"ChatInvite: sender {client_obj.steamID} is not a member of chatroom")
            return -1

        # Send the invite to the target user
        from steam3.Types.chat_types import ChatActionResult
        result = chatroom_manager.invite_user_to_chatroom(
            msg.chatroomSteamID,
            inviter_steam_id,
            invitee_steam_id
        )

        if result == ChatActionResult.success:
            cmserver_obj.log.debug(f"ChatInvite: successfully invited {invitee_steam_id:016x} to chatroom")
        else:
            cmserver_obj.log.warning(f"ChatInvite: failed to invite {invitee_steam_id:016x} to chatroom: {result}")

    except Exception as e:
        cmserver_obj.log.error(f"Error handling ClientChatInvite: {e}")
        import traceback
        cmserver_obj.log.error(traceback.format_exc())

    return -1


def handle_ClientChatMsg(cmserver_obj, packet: CMPacket, client_obj: Client):
    """Handle ClientChatMsg packet (EMsg 799)"""
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received ClientChatMsg")

    try:
        # Parse the request
        msg = MsgClientChatMsg(client_obj, request.data)

        # Verify sender is the client
        if int(msg.memberGlobalId) != int(client_obj.steamID):
            cmserver_obj.log.warning(f"Chat message sender mismatch: {int(msg.memberGlobalId)} != {int(client_obj.steamID)}")
            return -1

        cmserver_obj.log.debug(f"ChatMsg: from={int(msg.memberGlobalId)}, "
                              f"chat={int(msg.chatGlobalId)}, type={msg.entryType}, "
                              f"dataLen={len(msg.data)}")

        # Get chatroom manager and send message
        # send_message_to_chatroom validates permissions, persists to DB, and broadcasts
        # to all members EXCEPT the sender (2008 client displays locally, no server echo needed)
        chatroom_manager = get_chatroom_manager()
        result = chatroom_manager.send_message_to_chatroom(
            int(msg.chatGlobalId),
            int(msg.memberGlobalId),
            msg.entryType,
            msg.data,
            exclude_player_id=int(msg.memberGlobalId)  # Exclude sender from broadcast
        )

        if result != EResult.OK:
            cmserver_obj.log.warning(f"Failed to send chat message: {result}")
        
    except Exception as e:
        cmserver_obj.log.error(f"Error handling ClientChatMsg: {e}")
    
    return -1


def handle_ClientChatAction(cmserver_obj, packet: CMPacket, client_obj: Client):
    """Handle ClientChatAction packet (EMsg 808)"""
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received ClientChatAction")

    try:
        # Parse the request
        msg = MsgClientChatAction(client_obj, request.data)

        cmserver_obj.log.debug(f"ChatAction: chat={int(msg.steam_id_chat)}, "
                              f"target={int(msg.steam_id_user_to_act_on)}, action={msg.action}")

        # Get chatroom manager and perform action
        chatroom_manager = get_chatroom_manager()
        chatroom = chatroom_manager.get_chatroom(int(msg.steam_id_chat))

        if chatroom:
            target_id = int(msg.steam_id_user_to_act_on)

            # Perform the action
            action_result = chatroom.perform_action(
                int(client_obj.steamID),
                target_id,
                msg.action
            )

            # If action was successful, broadcast state change to all members
            if action_result == ChatActionResult.success:
                # Map action to state change
                state_change = None
                if msg.action == ChatAction.kick:
                    state_change = ChatMemberStateChange.kicked
                elif msg.action == ChatAction.ban:
                    state_change = ChatMemberStateChange.banned
                elif msg.action == ChatAction.inviteChat:
                    # For invite, send invite message to target user
                    chatroom_manager.invite_user_to_chatroom(
                        int(msg.steam_id_chat),
                        int(client_obj.steamID),
                        target_id
                    )
                elif msg.action == ChatAction.closeChat:
                    # Close the chatroom
                    chatroom_manager.remove_chatroom(chatroom.chat_id)
                elif msg.action in (ChatAction.lockChat, ChatAction.unlockChat,
                                    ChatAction.setJoinable, ChatAction.setUnjoinable,
                                    ChatAction.setModerated, ChatAction.setUnmoderated,
                                    ChatAction.setInvisibleToFriends, ChatAction.setVisibleToFriends):
                    # Broadcast room info change for flag changes
                    chatroom_manager.broadcast_room_info_change(
                        chatroom, int(client_obj.steamID)
                    )

                # Broadcast state change if applicable
                if state_change is not None:
                    chatroom_manager.broadcast_member_state_change(
                        chatroom, target_id, state_change, int(client_obj.steamID)
                    )

            # Build and return response
            response = build_ChatAction_response(
                client_obj, int(msg.steam_id_chat),
                target_id, msg.action, action_result
            )
            return response
        else:
            # Chatroom doesn't exist - ChatActionResult already imported at module level
            response = build_ChatAction_response(
                client_obj, int(msg.steam_id_chat),
                int(msg.steam_id_user_to_act_on), msg.action,
                ChatActionResult.chatDoesntExist
            )
            return response

    except Exception as e:
        cmserver_obj.log.error(f"Error handling ClientChatAction: {e}")
        # Send error response - ChatActionResult already imported at module level
        response = build_ChatAction_response(
            client_obj, 0, 0, ChatAction.inviteChat, ChatActionResult.error
        )
        return response


def handle_FriendMessage(cmserver_obj, packet, client_obj):
    client_address = client_obj.ip_port
    request = packet.CMRequest
    message = ChatMessage()
    message.fromSteamID = request.steamID
    toSteamID, message.type = struct.unpack('<QI', request.data[:12])
    message.toSteamID = SteamID.from_integer(toSteamID)
    message.message = request.data[12:].split(b'\x00', 1)[0].decode('latin-1')

    log.debug(f"FriendMessage: from={int(message.fromSteamID):016x} to={int(message.toSteamID):016x} "
              f"type={message.type} msg='{message.message[:50]}...' if len(message.message) > 50 else message.message")

    # Store the message in the list
    msg_obj = ChatMessage(message.fromSteamID, message.toSteamID, message.type, message.message)

    build_GeneralAck(client_obj, packet, client_address, cmserver_obj)

    # Look up recipient by account ID - use get_client_by_accountID which handles int
    recipient_account_id = int(message.toSteamID.get_accountID())
    client_friend = Client_Manager.get_client_by_accountID(recipient_account_id)

    if client_friend is None:
        log.debug(f"FriendMessage: recipient {recipient_account_id} not found/not online")
        return -1

    if client_friend.objCMServer is None:
        log.debug(f"FriendMessage: recipient {recipient_account_id} has no CM server")
        return -1

    # IMPORTANT: Use the friend's CM server to send, not the sender's!
    # This ensures proper delivery when clients are on different connection types (UDP vs TCP)
    log.debug(f"FriendMessage: forwarding message to recipient {recipient_account_id}")
    client_friend.objCMServer.sendReply(client_friend, [build_send_friendsmsg(client_friend, msg_obj)])
    return -1
