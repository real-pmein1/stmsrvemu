from datetime import datetime
from typing import Dict, List, Optional

from steam3.ClientManager.client import Client


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
        self.permissions: Dict[str, Dict[str, bool]] = permissions  # Dictionary containing permission tiers
        self.member_limit: int = member_limit
        self.clientlist: List[Client] = []  # List to hold client objects from ClientManager/client.py
        self.voicechat_clientlist: List[Client] = []  # List to hold client objects using voice chat

    def add_client(self, client: Client) -> None:
        if len(self.clientlist) < self.member_limit:
            self.clientlist.append(client)
        else:
            raise Exception("Member limit reached")

    def remove_client(self, client: Client) -> None:
        if client in self.clientlist:
            self.clientlist.remove(client)
        if client in self.voicechat_clientlist:
            self.voicechat_clientlist.remove(client)

    def add_voicechat_client(self, client: Client) -> None:
        if client in self.clientlist:
            self.voicechat_clientlist.append(client)
        else:
            raise Exception("Client is not a member of the chatroom")

    def remove_voicechat_client(self, client: Client) -> None:
        if client in self.voicechat_clientlist:
            self.voicechat_clientlist.remove(client)

    def get_chat_history(self, db_driver: cm_dbdriver, chatroom_id: int) -> List[ChatRoomHistory]:
        session = db_driver.get_session()
        history: List[ChatRoomHistory] = session.query(ChatRoomHistory).filter_by(chatroomID=chatroom_id).all()
        return history

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