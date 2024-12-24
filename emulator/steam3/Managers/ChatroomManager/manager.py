from datetime import datetime
from typing import Dict, List, Optional
from utilities.database.base_dbdriver import ChatRoomHistory
from steam3.ClientManager.client import Client
from steam3.Managers.ChatroomManager.chatroom import ChatRooms
from utilities.database.cmdb import cm_dbdriver
from uuid import uuid4


class ChatRoomManager:
    def __init__(self, db_driver: cm_dbdriver):
        """
        Initializes the ChatRoomManager with an empty list of chatrooms and a database driver.
        """
        self.chatrooms: Dict[int, ChatRooms] = {}  # Maps globalID to ChatRooms instances
        self.db_driver = db_driver

    def create_chatroom(self, chat_type: int, owner_accountID: int, name: str, motd: str,
                        applicationID: int, member_limit: int, permissions: Optional[Dict[str, Dict[str, bool]]] = None) -> ChatRooms:
        """
        Creates a new chatroom and adds it to the manager's list of active chatrooms.

        :param chat_type: Type of the chatroom (e.g., public, private).
        :param owner_accountID: Account ID of the owner.
        :param name: Name of the chatroom.
        :param motd: Message of the day.
        :param applicationID: Application ID associated with the chatroom.
        :param member_limit: Maximum number of members in the chatroom.
        :param permissions: Optional permissions dictionary.
        :return: The created ChatRooms instance.
        """
        global_id = int(uuid4().int % (10 ** 8))  # Generate a unique 8-digit global ID
        chatroom = ChatRooms(
            globalID=global_id,
            chat_type=chat_type,
            owner_accountID=owner_accountID,
            associated_groupID=None,  # Default to no associated group
            applicationID=applicationID,
            name=name,
            creation_time=datetime.now(),
            motd=motd,
            servermessage=0,
            flags=0,
            permissions=permissions or {
                'owner': {'can_kick': True, 'can_ban': True, 'can_mute': True},
                'moderator': {'can_kick': True, 'can_ban': False, 'can_mute': True},
                'member': {'can_kick': False, 'can_ban': False, 'can_mute': False},
                'default': {'can_kick': False, 'can_ban': False, 'can_mute': False},
            },
            member_limit=member_limit
        )
        self.chatrooms[global_id] = chatroom
        if chat_type != 3:
            self._save_chatroom_to_db(chatroom)  # Save the chatroom to the database
        return chatroom

    def remove_chatroom(self, globalID: int) -> None:
        """
        Removes a chatroom from the manager's list and deletes it from the database if it's permanent.

        :param globalID: The global ID of the chatroom to be removed.
        """
        if globalID in self.chatrooms:
            chatroom = self.chatrooms.pop(globalID)
            self._delete_chatroom_from_db(chatroom)

    def get_chatroom(self, globalID: int) -> Optional[ChatRooms]:
        """
        Retrieves a chatroom by its global ID.

        :param globalID: The global ID of the chatroom.
        :return: The ChatRooms instance or None if not found.
        """
        return self.chatrooms.get(globalID)

    def list_chatrooms(self) -> List[ChatRooms]:
        """
        Lists all active chatrooms.

        :return: A list of all active ChatRooms instances.
        """
        return list(self.chatrooms.values())

    def _save_chatroom_to_db(self, chatroom: ChatRooms) -> None:
        """
        Saves a chatroom to the database.
        """


    def _delete_chatroom_from_db(self, chatroom: ChatRooms) -> None:
        """
        Deletes a chatroom from the database.

        :param chatroom: The ChatRooms instance to be deleted.
        """
        session = self.db_driver.get_session()
        try:
            session.query(ChatRoomHistory).filter_by(chatroomID=chatroom.globalID).delete()
            session.commit()
        except Exception as e:
            session.rollback()
            raise e