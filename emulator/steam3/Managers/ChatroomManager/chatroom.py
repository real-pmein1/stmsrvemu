from datetime import datetime
from typing import Dict, List, Optional

from utilities.database.base_dbdriver import ChatRoomHistory
from steam3.ClientManager.client import Client
from steam3.Types.community_types import ChatMemberStateChange, ChatPermission, ChatRoomType
from utilities.database.cmdb import cm_dbdriver


class ChatRooms:
    def __init__(self,
                 globalID: int,
                 chat_type: int,
                 owner_accountID: int,
                 associated_groupID: Optional[int],
                 applicationID: int,
                 name: str,
                 creation_time: datetime,
                 motd: str,
                 servermessage: int,
                 flags: int,
                 permissions: Dict[str, Dict[str, bool]],
                 member_limit: int):
        self.globalID: int = globalID
        self.chat_type: int = chat_type
        self.owner_accountID: int = owner_accountID
        self.associated_groupID: Optional[int] = associated_groupID
        self.applicationID: int = applicationID
        self.name: str = name
        self.creation_time: datetime = creation_time
        self.motd: str = motd
        self.servermessage: int = servermessage
        self.flags: int = flags
        self.permissions: Dict[str, Dict[str, bool]] = permissions
        self.member_limit: int = member_limit
        self.clientlist: List[Client] = []
        self.voicechat_clientlist: List[Client] = []
        self.chat_history: List[Dict[str, str]] = []  # Holds current and past chat messages
        self.banned_users: set = set()  # Track banned users by ID
        self.muted_users: set = set()  # Track muted users by ID

    def load_history(self, db_driver: cm_dbdriver) -> None:
        """
        Loads chat history from the database if the chatroom is permanent (type 2).
        """
        if self.chat_type == ChatRoomType.MUC:
            self.chat_history = self.get_chat_history(db_driver, self.globalID)

    def add_message(self, db_driver: cm_dbdriver, sender: Client, message: str) -> None:
        """
        Adds a chat message to the chatroom history and sends it to all clients.

        :param db_driver: Database driver for saving messages.
        :param sender: The client sending the message.
        :param message: The message to send.
        """
        new_message = {
            "sender": sender.username,
            "message": message,
            "timestamp": datetime.now().strftime("%m/%d/%Y %H:%M:%S")
        }
        self.chat_history.append(new_message)

        if self.chat_type != ChatRoomType.lobby:
            # Save the message to the database for permanent chatrooms
            session = db_driver.get_session()
            try:
                chat_history_entry = ChatRoomHistory(
                    chatroomID=self.globalID,
                    sender=sender.steamID,
                    message=message,
                    timestamp=datetime.now()
                )
                session.add(chat_history_entry)
                session.commit()
            except Exception as e:
                session.rollback()
                raise e

        # Send message to all connected clients
        for client in self.clientlist:
            client.send_message(f"{sender.username}: {message}")

    def add_client(self, client: Client) -> None:
        """
        Handles adding a client to the chatroom.
        """
        if len(self.clientlist) >= self.member_limit:
            raise Exception("Chatroom is full")

        if client in self.banned_users:
            client.send_message("You are banned from this chatroom.")
            return

        self.clientlist.append(client)
        self.broadcast_state_change(client, ChatMemberStateChange.entered)
        self.send_welcome_message(client)

    def remove_client(self, client: Client) -> None:
        """
        Handles removing a client from the chatroom.
        """
        if client in self.clientlist:
            self.clientlist.remove(client)
            self.broadcast_state_change(client, ChatMemberStateChange.left)

    def broadcast_state_change(self, client: Client, state_change: ChatMemberStateChange) -> None:
        """
        Broadcasts a member state change to all clients in the chatroom.
        """
        message = f"{client.username} has {state_change.name.lower()} the chatroom."
        for c in self.clientlist:
            c.send_message(message)

    def kick_client(self, client: Client, initiator: Client) -> None:
        """
        Kicks a client from the chatroom if the initiator has the right permissions.
        """
        if not self.has_permission(initiator, ChatPermission.kick):
            initiator.send_message("You do not have permission to kick users.")
            return

        self.remove_client(client)
        self.broadcast_state_change(client, ChatMemberStateChange.kicked)

    def ban_client(self, client: Client, initiator: Client) -> None:
        """
        Bans a client from the chatroom if the initiator has the right permissions.
        """
        if not self.has_permission(initiator, ChatPermission.ban):
            initiator.send_message("You do not have permission to ban users.")
            return

        self.banned_users.add(client)
        self.remove_client(client)
        self.broadcast_state_change(client, ChatMemberStateChange.banned)

    def mute_client(self, client: Client, initiator: Client) -> None:
        """
        Mutes a client in the chatroom if the initiator has the right permissions.
        """
        if not self.has_permission(initiator, ChatPermission.mute):
            initiator.send_message("You do not have permission to mute users.")
            return

        self.muted_users.add(client)
        client.send_message("You have been muted in this chatroom.")

    def has_permission(self, client: Client, permission: int) -> bool:
        """
        Checks if a client has a specific permission.
        """
        role = self.get_client_role(client)
        return self.permissions.get(role, {}).get(permission, False)

    def get_client_role(self, client: Client) -> str:
        """
        Returns the role of the client in the chatroom (e.g., owner, moderator, member).
        """
        if client.steamID == self.owner_accountID:
            return "owner"
        # Add logic for determining moderator or other roles
        return "member"

    def send_welcome_message(self, client: Client) -> None:
        """
        Sends a welcome message to a client entering the chatroom.
        """
        client.send_message(f"Welcome to {self.name}! Message of the day: {self.motd}")



# Example usage:
# Create an instance of ChatRooms
"""chatroom = ChatRooms(
    globalID=1,
    chat_type=0,
    owner_accountID=1,
    associated_groupID=1,
    applicationID=1,
    name="Chat Room Name",
    creation_time=datetime.now(),
    motd="Message of the Day",
    servermessage=0,
    flags=0,
    permissions={
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