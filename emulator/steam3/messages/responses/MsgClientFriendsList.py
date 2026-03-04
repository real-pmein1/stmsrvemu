import struct

from steam3.Types.steamid import SteamID
from steam3.cm_packet_utils import CMProtoResponse, CMResponse
from steam3.Types.emsg import EMsg
from steam3.protobufs.steammessages_clientserver_friends_pb2 import CMsgClientFriendsList


class FriendsListResponse:
    def __init__(self, client_obj):
        """
        Initialize the FriendsListResponse object with default values.
        """
        self.is_incremental = False
        self.friends = []  # List of tuples: (steamID: int, relationship: int)
        self.max_friend_count = 0
        self.active_friend_count = 0
        self.friends_limit_hit = False
        self.client_obj = client_obj

    def addFriend(self, steamID: int, relationship: int):
        """
        Add a friend to the friends list.

        :param steamID: The 64-bit Steam ID of the friend
        :param relationship: The friend relationship value (EFriendRelationship enum)
        """
        # Handle SteamID object or raw integer
        if hasattr(steamID, 'get_integer_format'):
            steamID = steamID.get_integer_format()
        elif hasattr(steamID, '__int__'):
            steamID = int(steamID)

        self.friends.append((steamID, relationship))

    def to_protobuf(self):
        """
        Convert the FriendsListResponse data to a Protobuf object.
        :return: A Protobuf serialized response.
        """
        packet = CMProtoResponse(eMsgID=EMsg.ClientFriendsList, client_obj=self.client_obj)
        friends_list_msg = CMsgClientFriendsList()

        friends_list_msg.bincremental = self.is_incremental

        for friend_steamid, relationship in self.friends:
            friend = friends_list_msg.friends.add()
            friend.ulfriendid = friend_steamid
            friend.efriendrelationship = relationship

        if self.max_friend_count > 0:
            friends_list_msg.max_friend_count = self.max_friend_count
        if self.active_friend_count > 0:
            friends_list_msg.active_friend_count = self.active_friend_count
        if self.friends_limit_hit:
            friends_list_msg.friends_limit_hit = self.friends_limit_hit

        packet.set_response_message(friends_list_msg)
        # Serialize the Protobuf message.
        serialized_response = friends_list_msg.SerializeToString()

        # Attach serialized data to the packet.
        packet.data = serialized_response
        packet.length = len(serialized_response)

        return packet

    def to_clientmsg(self):
        """
        Convert the FriendsListResponse data to a regular byte buffer.
        :return: A byte string.

        Binary format:
        - friend_count: uint16 (2 bytes)
        - is_incremental: uint8 (1 byte)
        - For each friend:
            - steamID: uint64 (8 bytes)
            - relationship: uint8 (1 byte)
        """
        packet = CMResponse(eMsgID=EMsg.ClientFriendsList, client_obj=self.client_obj)

        friend_count = len(self.friends)
        is_incremental_byte = 1 if self.is_incremental else 0

        # Pack header: friend count (2 bytes) + is_incremental (1 byte)
        packet.data = struct.pack('<HB', friend_count, is_incremental_byte)

        # Pack each friend entry
        for friend_steamid, relationship in self.friends:
            packet.data += struct.pack('<Q', friend_steamid)  # 64-bit Steam ID
            packet.data += struct.pack('B', relationship)      # 8-bit relationship

        packet.length = len(packet.data)
        return packet
