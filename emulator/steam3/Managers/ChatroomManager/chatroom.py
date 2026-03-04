import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from steam3.Types.wrappers import AccountID

from steam3.ClientManager import Client_Manager
from steam3.Responses.friends_responses import build_persona_message
from steam3.Types.MessageObject.ChatMemberInfo import ChatMemberInfo
from steam3.Types.steamid import SteamID
from steam3.messages.MsgClientChatMsg import MsgClientChatMsg
from steam3.messages.MsgClientChatMemberInfo import MsgClientChatMemberInfo
from steam3.messages.responses.MsgClientChatInvite import MsgClientChatInvite
from steam3.messages.responses.MsgClientPersonaState import PersonaStateMessage, chatroomPersonaStateMessage
from steam3.ClientManager.client import Client
from steam3.Types.chat_types import (
    ChatAction, ChatActionResult, ChatEntryType, ChatInfoType, ChatMemberRankDetails,
    ChatMemberStateChange, ChatPermission, ChatMemberStatus, ChatRoomEnterResponse,
    ChatRoomFlags, ChatRoomType, ChatRoomType2
)
from steam3.Types.community_types import PersonaStateFlags, RequestedPersonaStateFlags_chatMembers
from steam3.Types.chat_types import ClanRelationship
from steam3.Responses.chat_responses import (
    build_ChatEnter,
    build_ChatroomMsg,
)


chatroomlogger = logging.getLogger(f"chatrooms")
@dataclass
class ChatroomClient:
    clientObj: Client
    relationship: ChatMemberStatus
    rank_detail: ChatMemberRankDetails

    @property
    def is_member(self) -> bool:
        return self.relationship == ChatMemberStatus.MEMBER

    @property
    def is_invited(self) -> bool:
        return self.relationship == ChatMemberStatus.TO_BE_INVITED

class ChatRooms:
    from steam3 import database

    def __init__(self,
                 tempChatroomID: int,
                 chat_type: int,
                 owner_accountID: int,
                 associated_groupID: Optional[int],
                 applicationID: int,
                 name: str,
                 creation_time: datetime,
                 motd: str,
                 servermessage: int,
                 flags: int,
                 allPermissions,
                 memberPermissions,
                 officerPermissions,
                 member_limit: int):
        self.accountID: int = tempChatroomID
        self.chatType: ChatRoomType = chat_type

        self.chatSubType: ChatRoomType2 = ChatRoomType2.MUC
        if associated_groupID != 0:
            self.chatSubType = ChatRoomType2.clan
        elif self.chatType == ChatRoomType.lobby:
            self.chatSubType = ChatRoomType2.lobby

        self.owner_accountID: int = owner_accountID
        self.associated_groupID: Optional[int] = associated_groupID # Clanid
        self.applicationID: int = applicationID
        self.name: str = name
        self.creation_time: datetime = creation_time
        self.motd: str = motd
        self.servermessage: int = servermessage
        self.flags: int = flags
        self.allPermissions = allPermissions
        self.memberPermissions = memberPermissions
        self.officerPermissions = officerPermissions
        self.member_limit: int = member_limit
        self.clientlist: Dict[int, ChatroomClient] = {}
        self.voicechat_clientlist: List[Client] = []
        self.chat_history: List[Dict[str, str]] = []  # Holds current and past chat messages
        self.banned_users: set = set()  # Track banned users by ID
        self.muted_users: set = set()  # Track muted users by ID
        self.moderators: set = set()
        self.steamID: SteamID = SteamID()
        self.chatroomStartedWithAccountID = None

    def load_history(self) -> None:
        """
        Loads chat history from the database if the chatroom is permanent (type 2).
        """
        if self.chatType == ChatRoomType.MUC:
            self.chat_history = self.database.getChatRoomHistory(self.accountID)

    def add_message(self, clientObj, chatEntryType: ChatEntryType, message:  str):
        """
        Adds a chat message to the chatroom history and sends it to all clients.

        :param sender: The client sending the message.
        :param message: The message to send.
        """
        # Check if user is muted
        if self.is_user_muted(clientObj.accountID):
            clientObj.send_message("You are muted in this chatroom.")
            return False

        # Check temp mute
        """if self.is_temp_muted(clientObj.accountID):
            clientObj.send_message("You are temporarily muted in this chatroom.")
            return False"""
        new_message = {
            "sender": clientObj.accountID,
            "message": message,
            "timestamp": datetime.now().strftime("%m/%d/%Y %H:%M:%S")
            }

        if chatEntryType == ChatEntryType.ChatMsg:
            self.chat_history.append(new_message)
            if self.chatType != ChatRoomType.lobby:
                self.database.add_chatroom_msg_history(self, message, clientObj.accountID)

        self.broadcastMsg(clientObj, chatEntryType, message.encode('latin-1'))

    def add_client(self, client_obj: Client, *, notify_joiner: bool = True) -> list:
        """
        Register *client_obj* as a new member of this room.

        Returns a list of packets that must be sent **only** to the
        joining client (typically a single MsgClientChatEnter).
        All broadcasts are dispatched immediately from here.
        """
        if client_obj.accountID in self.clientlist:
            # Client is already present! what the fuck, why they doin this?
            return build_ChatEnter(client_obj, self.accountID, ChatRoomEnterResponse.error)

        if len(self.clientlist) == 1000:
            return build_ChatEnter(client_obj, self.accountID, ChatRoomEnterResponse.full)

        if self.getUserRelationToChat(client_obj.accountID) is ChatMemberStatus.BLOCKED:
            return build_ChatEnter(client_obj, self.accountID, ChatRoomEnterResponse.banned)

        if self.flags & (ChatRoomFlags.locked | ChatRoomFlags.unjoinable):
            return build_ChatEnter(client_obj, self.accountID, ChatRoomEnterResponse.notAllowed)

        # TODO: check if room has users which the incoming client has blocked - return with YouBlockedMember
        # TODO: check if entering client is blocked by anyone in the chatroom - MemberBlockedYou

        entryResponseStatus = ChatRoomEnterResponse.success
        rankDetails = ChatMemberRankDetails.NONE
        # Add the user to the membership list of the chatroom when they enter
        relationship = ChatMemberStatus.MEMBER
        self.database.set_chatroom_member(self.accountID, client_obj.accountID, relationship, rankDetails)

        # membership
        entry = ChatroomClient(
            clientObj=client_obj,
            relationship=relationship,
            rank_detail=rankDetails
        )
        self.clientlist[client_obj.accountID] = entry
        memberInfoList = []
        # Count members vs invitees
        member_count = sum(1 for e in self.clientlist.values() if e.is_member)
        invite_count = sum(1 for e in self.clientlist.values() if e.is_invited)

        if member_count > 1: # this is not the first client to join
            # Send the connecting user all of the member's persona information
            client_obj.sendReply(build_persona_message(client_obj, RequestedPersonaStateFlags_chatMembers, self.clientlist))

            for acct_id, entry in self.clientlist.items():
                client = entry.clientObj
                relationship = entry.relationship
                permissions = self.allPermissions
                rankDetails = ChatMemberRankDetails.NONE
                if relationship == ChatMemberStatus.MEMBER and self.chatSubType == ChatRoomType2.clan:
                    permissions = self.memberPermissions # This is a clan/group related permission setting only!
                    rankDetails = ChatMemberRankDetails.CLAN_MEMBER

                if self.owner_accountID == client.accountID:
                    permissions = ChatPermission.ownerDefault
                    if self.chatSubType == ChatRoomType2.clan:
                        rankDetails = ChatMemberRankDetails.CLAN_OWNER # This is a clan/group related permission setting only!
                    else:
                        rankDetails = ChatMemberRankDetails.CHAT_OWNER
                """elif self.chatSubType == ChatRoomType2.clan:
                    permissions = self.officerPermissions  # your the clan owner but not the chatroom owner?? DONT KNOW IF THIS IS CORRECT"""

                self.database.set_chatroom_member(self.accountID, client.accountID, relationship, rankDetails)
                memberInfo = ChatMemberInfo()
                memberInfo.set_SteamID(client.steamID)
                memberInfo.set_Permissions(permissions)
                memberInfo.set_Details(rankDetails)
                memberInfoList.append(memberInfo)

        elif member_count == 1 and invite_count == (len(self.clientlist) - 1):
            # This is the first client, so we do some initializing and send out invites
            members = self.database.get_pending_invites(self.accountID)
            for memberID in members:
                memberClientObj = Client_Manager.get_client_by_identifier(AccountID(memberID))
                if memberClientObj is not None:  # the user is online, so send the invite
                    self.sendInvites(client_obj,memberClientObj)

        """	// voice speakers
           	Vector<ULONGLONG> * voiceSpeakers=new Vector<ULONGLONG>();
           	chatroom->getVoiceSpeakers(voiceSpeakers);
           	
           	Iterator<ULONGLONG> * it=voiceSpeakers->iterator();
           	while (it->hasNext())
           	{
           		ULONGLONG voiceSpeakerGlobalId=it->next();
           		
           		MsgClientChatMemberInfo * info=new MsgClientChatMemberInfo();
           		response->add(info);
           		info->body.chatGlobalId=chatroom->getSteamGlobalId();
           		info->body.type=ChatInfoType_stateChange;
           		info->body.stateChange.memberGlobalId=voiceSpeakerGlobalId;
           		info->body.stateChange.change=ChatMemberStateChange_startedVoiceSpeak;
           		info->body.stateChange.actorGlobalId=voiceSpeakerGlobalId;
           	}"""

        # TODO: Broadcast member state change (entered) via MsgClientChatMemberInfo
        # Note: ChatEntryType doesn't have 'Entered' - member joins are broadcast via ChatMemberStateChange.entered
        self.broadcastMemberStateChange(client_obj, ChatMemberStateChange.entered)

        return build_ChatEnter(client_obj, self.accountID, entryResponseStatus, memberInfoList)

    def broadcastMsg(self, clientObj: Client, chatMsgType: ChatEntryType, chatMsg = b'') -> None:
        """
        Broadcasts a chat message to all clients in the chatroom.
        """
        for acct_id, entry in self.clientlist.items():
            member_client = entry.clientObj
            message = MsgClientChatMsg(member_client)
            message.chatGlobalId = self.accountID
            message.entryType = chatMsgType
            message.memberGlobalId = clientObj.steamID
            message.data = chatMsg

            member_client.sendReply([message.to_clientmsg()])

    def broadcastMemberStateChange(self, clientObj: Client, stateChange: ChatMemberStateChange, actorClientObj: Client = None) -> None:
        """
        Broadcasts a member state change (entered, left, kicked, banned, etc.) to all clients in the chatroom.

        :param clientObj: The client whose state changed (the subject)
        :param stateChange: The type of state change (entered, left, kicked, etc.)
        :param actorClientObj: The client who caused the change (e.g., who kicked). If None, uses clientObj.
        """
        if actorClientObj is None:
            actorClientObj = clientObj

        for acct_id, entry in self.clientlist.items():
            member_client = entry.clientObj
            message = MsgClientChatMemberInfo(member_client)
            message.chat_id = self.steamID
            message.info_type = ChatInfoType.stateChange
            message.user_steam_id = clientObj.steamID
            message.state_change = stateChange
            message.target_steam_id = actorClientObj.steamID

            member_client.sendReply([message.to_clientmsg()])

    def sendInvites(self, inviterClientAccountID, inviteeClientObj):
        """
        Send Invitations to users who are online and store invites for those who are offline.
        """
        if len(self.clientlist) >= self.member_limit:
            return ChatActionResult.chatFull

        inviteeClientObj = Client_Manager.get_client_by_identifier(inviteeClientObj)
        if inviteeClientObj is None:
            return ChatActionResult.success  # Invited User is not online, but we will store it for later by setting the member as invited in the database

        message = MsgClientChatInvite(inviteeClientObj)
        message.chatroomSteamID = self.steamID
        message.chat_room_type = self.chatType
        message.invitedSteamID = inviteeClientObj.steamID
        message.friend_chat_global_id = SteamID.static_create_normal_account_steamid(inviterClientAccountID)
        message.patronSteamID = SteamID.static_create_normal_account_steamid(inviterClientAccountID)
        message.chat_room_name = self.name
        message.game_id = self.applicationID # this is only useful for lobbys and possibly clan chatrooms

        inviteeClientObj.sendReply([message.to_clientmsg()])
        return ChatActionResult.success

    def _DoAction(self, actingClientObj, actedOnAccountID, actionPermission):
        if actingClientObj.accountID == actedOnAccountID:
            return ChatActionResult.notAllowedOnSelf  # cant do actions against yourself

        actedOnClientObj = Client_Manager.get_client_by_identifier(actedOnAccountID)
        actedOnClient_Relationship = self.getRelationship(actedOnClientObj)

        if actedOnClient_Relationship is None and actionPermission is not ChatAction.inviteChat:
            return ChatActionResult.error  # User does not exist in chatroom and this is not an invite!

        if actingClientObj.accountID == self.owner_accountID:
            return ChatActionResult.success  # The owner can do no wrong

        # TODO check if a lower teir (moderator/officer) user is attempting an action on a higher teir (owner) user

        if actedOnClient_Relationship == ChatMemberStatus.BLOCKED:
            return ChatActionResult.notAllowedOnBannedUser  # Cannot do any actions on a banned member

    def getUserPermissions(self, clientObj):
        if self.chatType == ChatRoomType.MUC:
            if self.chatSubType == ChatRoomType2.clan:
                raise Exception("Clans not supported yet!")# clan chatroom
            else:
                # Normal multi-user chat
                if clientObj.accountID == self.owner_accountID:
                    return ChatPermission.ownerDefault  # if this is the owner, return owner permissions
                else:
                    return self.allPermissions  # if anyone else, then return member permissions

    def getRelationship(self, client: Client):
        if client.accountID in self.clientlist:
            return self.clientlist[client.accountID].relationship
        return None

    def insertOrUpdate_ChatroomClient(self, client_obj: Client, relationship: ChatMemberStatus, rank_detail: ChatMemberRankDetails, inviterAccountID = None) -> ChatroomClient:
        """
        Create or update a ChatroomClient both in the database and in self.clients.

        - Persists the (relationship, rank_detail, inviterAccountID) via DAO.
        - If an entry already exists in self.clients, patches its fields.
        - Otherwise, builds a new ChatroomClient and stores it.

        :returns: the ChatroomClient instance in self.clients
        """
        acct = client_obj.accountID

        # 1) Persist to DB (will INSERT or UPDATE as needed)
        self.database.set_chatroom_member(
            self.accountID,
            acct,
            relationship,
            memberRankDetails=rank_detail,
            inviterAccountID=inviterAccountID
        )

        # 2) Upsert in-memory
        if acct in self.clientlist:
            entry = self.clientlist[acct]
            entry.relationship = relationship
            entry.rank_detail  = rank_detail
        else:
            entry = ChatroomClient(
                clientObj   = client_obj,
                relationship= relationship,
                rank_detail = rank_detail
            )
            self.clientlist[acct] = entry

        return entry

    def remove_member(self, accountID: int) -> bool:
        """
        Remove the given accountID from both the database and in-memory client list.

        :param accountID: Integer ID of the client to remove
        :return: True if removed successfully
        :raises ValueError: if the client is not in self.clientlist
        :raises NoResultFound: if the DAO reports no such DB entry
        """
        # 1) In-memory existence check
        if accountID not in self.clientlist:
            raise ValueError(f"Client {accountID} not found in chatroom {self.accountID}")

        # 2) Remove from DB (will raise NoResultFound if it wasn't there)
        self.database.remove_chatroom_member(self.accountID, accountID)

        # 3) Remove from in-memory dict
        del self.clientlist[accountID]

        return True

    def buildChatroomPersonaStateMessage(self, stateFlags):
        """
        Build a persona state message using the new PersonaStateMessage class.

        This packet holds a maximum of 10 users per packet. Only the fields corresponding
        to the supported flags are populated:
          - 0x8: SteamID source (steam_id_source)
          - 0x20: Lobby MetaData


        :param clientOBJ: The client object.
        :param stateFlags: The bitmask flag indicating which fields to include.
        :param accountIDList: A list of accountID values.
        :return: A CMResponse packet with the serialized PersonaStateMessage.
        """

        # Create a new PersonaStateMessage instance
        psm = chatroomPersonaStateMessage(self)
        psm.status_flags = PersonaStateFlags.none

        return psm.to_clientmsg()

    def get_member_count(self) -> int:
        """Returns the current number of members in the chatroom."""
        return len(self.clientlist)

    def getUserRelationToChat(self, accountID: int) -> ChatMemberStatus:
        """Gets the user's relationship to the chat from the database."""
        dbresult = self.database.get_chatroom_member(self.accountID, accountID)
        return dbresult.relationship if dbresult else ChatMemberStatus.NONE

    def is_empty(self) -> bool:
        """Returns True if the chatroom has no members."""
        return len(self.clientlist) == 0

    def should_auto_destroy(self) -> bool:
        """Returns True if the chatroom should be automatically destroyed."""
        # Auto-destroy lobbies when empty
        if self.chatType == ChatRoomType.lobby and self.is_empty():
            return True

        # Auto-destroy temporary rooms after inactivity
        if (self.chatType != ChatRoomType.MUC and
            self.is_empty() ):
            return True

        return False

# Example usage:
# Create an instance of ChatRooms
"""chatroom = ChatRooms(
    accountID=1,
    chatType=0,
    owner_accountID=1,
    associated_groupID=1,
    applicationID=1,
    name="Chat Room Name",
    creation_time=datetime.now(),
    motd="Message of the Day",
    servermessage=0,
    flags=0,
    allPermissions={
        'owner': {'can_kick': True, 'can_ban': True, 'can_mute': True},
        'moderator': {'can_kick': True, 'can_ban': False, 'can_mute': True},
        'member': {'can_kick': False, 'can_ban': False, 'can_mute': False},
        'default': {'can_kick': False, 'can_ban': False, 'can_mute': False}
    },
    member_limit=10
)"""

# Assume Client is a class from ClientManager/client.py
# client = Client(...)
# chatroom.add_client(client)