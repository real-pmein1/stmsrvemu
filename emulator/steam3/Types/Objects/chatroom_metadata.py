from steam3.Types.keyvaluesystem import KeyValuesSystem, RegistryKey, KVS_TYPE_STRING, KVS_TYPE_INT
from typing import Optional, List

CHAT_ROOM_METADATA = "ClChatRoom"
CHAT_ROOM_MEMBER_METADATA = "ClChatMember"


class ChatRoomMetadata(KeyValuesSystem):
    def __init__(self, type_name: Optional[str] = None):
        """
        Initialize the ChatRoomMetadata object.

        :param type_name: Optional type name for the registry key.
        """
        super().__init__()
        if type_name:
            self.get_registry_key().create_key(type_name)
        else:
            self.get_registry_key().create_key("")

    @classmethod
    def new_chat_room_metadata(cls) -> "ChatRoomMetadata":
        """
        Factory method to create a new chat room metadata object.
        """
        return cls(CHAT_ROOM_METADATA)

    @classmethod
    def new_chat_room_member_metadata(cls) -> "ChatRoomMetadata":
        """
        Factory method to create a new chat room member metadata object.
        """
        return cls(CHAT_ROOM_MEMBER_METADATA)

    def set_int32_value(self, value_name: str, value: int):
        """
        Set an integer value in the metadata.

        :param value_name: The name of the value to set.
        :param value: The integer value to set.
        """
        self.get_registry_key().get_key("").set_value(value_name, KVS_TYPE_INT, value)

    def set_string_value(self, value_name: str, value: str):
        """
        Set a string value in the metadata.

        :param value_name: The name of the value to set.
        :param value: The string value to set.
        """
        self.get_registry_key().get_key("").set_value(value_name, KVS_TYPE_STRING, value)

    def delete_value(self, value_name: str):
        """
        Delete a value from the metadata.

        :param value_name: The name of the value to delete.
        """
        key = self.get_registry_key().get_key("")
        if key:
            key.delete_key(value_name)

    def get_string_value(self, value_name: str) -> Optional[str]:
        """
        Get a string value from the metadata.

        :param value_name: The name of the value to retrieve.
        :return: The string value, or None if not found.
        """
        key = self.get_registry_key().get_key("")
        if key:
            return key.get_string_value(value_name)
        return None

    def get_values_names(self) -> List[str]:
        """
        Get all value names from the metadata.

        :return: A list of value names.
        """
        key = self.get_registry_key().get_key("")
        if key:
            return [element.name for element in key.get_elements() if element.is_value()]
        return []

    def get_type(self) -> Optional[str]:
        """
        Get the type of the chat room metadata.

        :return: The type of the metadata, or None if not set.
        """
        key = self.get_registry_key().get_key("")
        if key:
            return key.name
        return None