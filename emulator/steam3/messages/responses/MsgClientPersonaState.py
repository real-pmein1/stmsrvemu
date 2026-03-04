import struct
from datetime import datetime
from io import BytesIO
from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse, CMProtoResponse
from steam3.protobufs.steammessages_clientserver_friends_pb2 import CMsgClientPersonaState

from steam3.utilities import decipher_persona_flags, read_null_terminated_string

class PersonaStateMessage:
    """
    Represents a ClientPersonaState message.

    This class mirrors the style of LogonResponse by accepting a client object
    upon initialization and providing a to_clientmsg() method. It uses a list
    of friend dictionaries and a global status_flags field to determine which
    fields are serialized.
    """
    def __init__(self, client_obj):
        """
        Initialize the PersonaStateMessage with default values.

        :param client_obj: The client object associated with this message.steam3/messages/responses/MsgClientPersonaState.py
        """
        self.client_obj = client_obj
        self.friends = []        # List of dictionaries containing friend data.
        self.status_flags = 0    # Global status flags (bitmask) for the packet.

    def serialize(self) -> bytes:
        """
        Serialize the message to a bytes object in the format expected by the client.

        The structure is:
          - [2 bytes] Friend count (unsigned short)
          - [4 bytes] Global status flags (unsigned int)
          For each friend:
            - [8 bytes] friend_id (unsigned 64-bit)
            - (if flag 0x1) [1 byte] persona_state, [4 bytes] game_id, [4 bytes] game_server_ip, [2 bytes] game_server_port
            - (if flag 0x2) [variable] player_name (null-terminated string, max 64 bytes including null)
            - (if flag 0x4) [2 bytes] query_port
            - (if flag 0x8) [8 bytes] steam_id_source
            - (if flag 0x10) [4 bytes] ip_address_cm, [20 bytes] avatar_hash
            - (if flag 0x20) [4 bytes] metadata_blob length, [n bytes] metadata_blob
            - (if flag 0x40) [4 bytes] last_logoff, [4 bytes] last_logon
            - (if flag 0x80) [4 bytes] clan_rank
            - (if flag 0x100) [variable] game_extra_info (null-terminated string, max 64 bytes), [8 bytes] game_id_real
            - (if flag 0x200) [4 bytes] game_data_blob length, [n bytes] game data blob (metadata)
        """
        stream = BytesIO()
        # Only write friend entries with a valid (nonzero) friend_id.
        valid_friends = [f for f in self.friends if f.get('friend_id', 0) != 0]
        stream.write(struct.pack('<H', len(valid_friends)))
        stream.write(struct.pack('<I', self.status_flags))
        for friend in valid_friends:
            stream.write(struct.pack('<Q', friend.get('friend_id', 0)))
            if self.status_flags & 0x1:  # PersonaState
                stream.write(struct.pack('<B', friend.get('persona_state', 0)))
                stream.write(struct.pack('<I', friend.get('game_id', 0)))
                stream.write(struct.pack('<I', friend.get('game_server_ip', 0)))
                stream.write(struct.pack('<H', friend.get('game_server_port', 0)))
            if self.status_flags & 0x2:  # Player name (null-terminated string, max 64 bytes)
                name = friend.get('player_name', "") or ""
                name_bytes = name.encode('utf-8')[:63] + b'\x00'
                stream.write(name_bytes)
            if self.status_flags & 0x4:  # Query Port (2 bytes)
                stream.write(struct.pack('<H', friend.get('query_port', 0)))
            if self.status_flags & 0x8:  # SteamID source (8 bytes)
                stream.write(struct.pack('<Q', friend.get('steam_id_source', 0)))
            if self.status_flags & 0x10:  # IP address CM (4 bytes) + Avatar Hash (20 bytes)
                stream.write(struct.pack('<I', friend.get('ip_address_cm', 0)))
                avatar = friend.get('avatar_hash', b'')
                avatar = avatar.ljust(20, b'\x00')[:20]
                stream.write(avatar)
            if self.status_flags & 0x20:  # Metadata Blob
                meta_blob = friend.get('metadata_blob', b'')
                stream.write(struct.pack('<I', len(meta_blob)))
                stream.write(meta_blob)
            if self.status_flags & 0x40:  # Last Logoff and Logon
                last_logoff = friend.get('last_logoff')
                last_logon = friend.get('last_logon')
                off_ts = int(last_logoff.timestamp()) if isinstance(last_logoff, datetime) else 0
                on_ts = int(last_logon.timestamp()) if isinstance(last_logon, datetime) else 0
                stream.write(struct.pack('<I', off_ts))
                stream.write(struct.pack('<I', on_ts))
            if self.status_flags & 0x80:  # Clan Rank
                stream.write(struct.pack('<I', friend.get('clan_rank', 0)))
            if self.status_flags & 0x100:  # Game Extra Info (null-terminated string, max 64 bytes)
                extra_info = friend.get('game_extra_info', "") or ""
                if isinstance(extra_info, bytes):
                    extra_bytes = extra_info[:63] + b'\x00'
                else:
                    extra_bytes = extra_info.encode('utf-8')[:63] + b'\x00'
                stream.write(extra_bytes)
                stream.write(struct.pack('<Q', friend.get('game_id_real', 0)))
            if self.status_flags & 0x200:  # Game Data Blob
                blob = friend.get('metadata', b'')
                stream.write(struct.pack('<I', len(blob)))
                stream.write(blob)
        return stream.getvalue()

    def to_clientmsg(self):
        """
        Convert this PersonaStateMessage into a CMResponse packet.
        """
        packet = CMResponse(eMsgID=EMsg.ClientPersonaState, client_obj=self.client_obj)
        serialized = self.serialize()
        packet.data = serialized
        packet.length = len(serialized)
        return packet

    def to_protobuf(self):
        """
        Convert this PersonaStateMessage into a CMProtoResponse packet using protobuf serialization.
        """
        packet = CMProtoResponse(eMsgID=EMsg.ClientPersonaState, client_obj=self.client_obj)
        persona_state_msg = CMsgClientPersonaState()
        persona_state_msg.status_flags = self.status_flags

        valid_friends = [f for f in self.friends if f.get('friend_id', 0) != 0]
        for friend in valid_friends:
            friend_msg = persona_state_msg.friends.add()
            friend_msg.friendid = friend.get('friend_id', 0)

            if self.status_flags & 0x1:  # PersonaState
                friend_msg.persona_state = friend.get('persona_state', 0)
                friend_msg.game_played_app_id = friend.get('game_id', 0)
                friend_msg.game_server_ip = friend.get('game_server_ip', 0)
                friend_msg.game_server_port = friend.get('game_server_port', 0)

            if self.status_flags & 0x2:  # Player name
                player_name = friend.get('player_name', "")
                if player_name:
                    friend_msg.player_name = player_name

            if self.status_flags & 0x4:  # Query Port
                friend_msg.query_port = friend.get('query_port', 0)

            if self.status_flags & 0x8:  # SteamID source
                friend_msg.steamid_source = friend.get('steam_id_source', 0)

            if self.status_flags & 0x10:  # Avatar Hash
                avatar = friend.get('avatar_hash', b'')
                if avatar:
                    friend_msg.avatar_hash = avatar

            if self.status_flags & 0x40:  # Last Logoff and Logon
                last_logoff = friend.get('last_logoff')
                last_logon = friend.get('last_logon')
                if isinstance(last_logoff, datetime):
                    friend_msg.last_logoff = int(last_logoff.timestamp())
                elif last_logoff:
                    friend_msg.last_logoff = int(last_logoff)
                if isinstance(last_logon, datetime):
                    friend_msg.last_logon = int(last_logon.timestamp())
                elif last_logon:
                    friend_msg.last_logon = int(last_logon)

            if self.status_flags & 0x80:  # Clan Rank
                friend_msg.clan_rank = friend.get('clan_rank', 0)

            if self.status_flags & 0x100:  # Game Extra Info
                extra_info = friend.get('game_extra_info', "")
                if extra_info:
                    if isinstance(extra_info, bytes):
                        friend_msg.game_name = extra_info.decode('utf-8', errors='replace').rstrip('\x00')
                    else:
                        friend_msg.game_name = extra_info
                friend_msg.gameid = friend.get('game_id_real', 0)

            if self.status_flags & 0x200:  # Game Data Blob
                blob = friend.get('metadata', b'')
                if blob:
                    friend_msg.game_data_blob = blob

        packet.data = persona_state_msg.SerializeToString()
        return packet

    def __str__(self):
        return f"PersonaStateMessage(status_flags={self.status_flags}, friends={self.friends})"

    def __repr__(self):
        return self.__str__()


class chatroomPersonaStateMessage:
    """
    Represents a ClientPersonaState message for the Chatroom object.

    This class mirrors the style of LogonResponse by accepting a client object
    upon initialization and providing a to_clientmsg() method. It uses a list
    of friend dictionaries and a global status_flags field to determine which
    fields are serialized.
    """
    def __init__(self, chatroomObj):
        """
        Initialize the PersonaStateMessage with default values.

        :param client_obj: The client object associated with this message.
        """
        self.chatroom = chatroomObj
        self.status_flags = 0    # Global status flags (bitmask) for the packet.

    def serialize(self) -> bytes:
        """
        Serialize the message to a bytes object in the format expected by the client.

        The structure is:
          - [2 bytes] Friend count (unsigned short)
          - [4 bytes] Global status flags (unsigned int)
          For each friend:
            - [8 bytes] friend_id (unsigned 64-bit)
            - (if flag 0x8) [8 bytes] steam_id_source
            - (if flag 0x20) [4 bytes] metadata_blob length, [n bytes] metadata_blob
        """
        stream = BytesIO()
        # Only write friend entries with a valid (nonzero) friend_id.
        stream.write(struct.pack('<H', 1))
        stream.write(struct.pack('<I', self.status_flags))
        stream.write(struct.pack('<Q', friend.get('friend_id', 0)))
        if self.status_flags & 0x8:  # SteamID source (8 bytes)
            stream.write(struct.pack('<Q', chatroom))
        if self.status_flags & 0x20:  # Metadata Blob
            meta_blob = self.chatroom.accountID
            stream.write(struct.pack('<I', len(meta_blob)))
            stream.write(meta_blob)

        return stream.getvalue()

    def to_clientmsg(self):
        """
        Convert this PersonaStateMessage into a CMResponse packet.
        """
        packet = CMResponse(eMsgID=EMsg.ClientPersonaState, client_obj=self.client_obj)
        serialized = self.serialize()
        packet.data = serialized
        packet.length = len(serialized)
        return packet

    def __str__(self):
        return f"PersonaStateMessage(status_flags={self.status_flags}, friends={self.friends})"

    def __repr__(self):
        return self.__str__()