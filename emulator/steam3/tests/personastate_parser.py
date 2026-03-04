import socket
import struct
from datetime import datetime
from enum import IntFlag
from io import BytesIO
from enum import Enum, IntFlag

import pprint



class KeyValueClass:
    KVS_TYPE_KEY = 0
    KVS_TYPE_STRING = 1
    KVS_TYPE_INT = 2
    KVS_TYPE_FLOAT = 3
    KVS_TYPE_PTR = 4
    KVS_TYPE_WSTRING = 5
    KVS_TYPE_COLOR = 6
    KVS_TYPE_UINT64 = 7
    KVS_TYPE_NO_MORE = 8
    KVS_TYPE_DWORDPREFIXED_STRING = 9
    KVS_TYPE_INT64 = 10
    KVS_TYPE_NO_MORE_2 = 11

    def __init__(self):
        self.data = {}
        self.current_dict = self.data
        self.stack = []

    def parse(self, byte_data):
        self.data = {}
        self.current_dict = self.data
        self.stack = []

        data = byte_data
        while data:
            value_type, data = data[0], data[1:]
            if value_type == self.KVS_TYPE_NO_MORE and data[0] == self.KVS_TYPE_NO_MORE:
                break
            elif value_type == self.KVS_TYPE_NO_MORE and data[0] != self.KVS_TYPE_NO_MORE:
                if self.stack:
                    self.current_dict = self.stack.pop()
                continue
            elif value_type == self.KVS_TYPE_KEY:
                key, data = self._read_null_terminated_string(data)
                new_dict = {}
                self.current_dict[key] = new_dict
                self.stack.append(self.current_dict)
                self.current_dict = new_dict
                continue
            key, data = self._read_null_terminated_string(data)
            value, data = self._parse_value(value_type, data)
            self.current_dict[key] = value

    @staticmethod
    def _read_null_terminated_string(data):
        parts = data.split(b'\x00', 1)
        if len(parts) == 2:
            return parts[0].decode(), parts[1]
        raise ValueError("String not null-terminated")

    def _parse_value(self, value_type, data):
        if value_type == self.KVS_TYPE_STRING:
            value, data = self._read_null_terminated_string(data)
        elif value_type == self.KVS_TYPE_INT:
            value, data = struct.unpack_from('<i', data, 0)[0], data[4:]
        elif value_type == self.KVS_TYPE_FLOAT:
            value, data = struct.unpack_from('<f', data, 0)[0], data[4:]
        elif value_type == self.KVS_TYPE_PTR:
            ptr_size = 4 if len(data) >= 4 else 8  # Presumably a mistake in logic; let's assume it's always 4 for now
            value, data = struct.unpack_from(f'<{"I" if ptr_size == 4 else "Q"}', data, 0)[0], data[ptr_size:]
        elif value_type == self.KVS_TYPE_COLOR:
            value, data = struct.unpack_from('<I', data, 0)[0], data[4:]
        elif value_type in (self.KVS_TYPE_INT64, self.KVS_TYPE_UINT64):
            value, data = struct.unpack_from('<Q', data, 0)[0], data[8:]
        elif value_type == self.KVS_TYPE_WSTRING:
            value, data = self._read_null_terminated_wstring(data)
        else:
            # print(data)
            return None, data  # Handle unsupported types without breaking the flow

        return value, data  # Ensure a tuple is always returned

    def serialize(self, custom_data = None):
        # Determine the source of data to serialize
        if custom_data is not None:
            data_to_serialize = custom_data
        else:
            data_to_serialize = self.data

        byte_data = b''
        for key, value in data_to_serialize.items():
            if key == "SubKeyEnd":
                byte_data += b"\x08"
            elif key == "SubKeyStart":
                byte_data += self.KVS_TYPE_KEY.to_bytes(1, 'little') + key.encode() + b'\x00'
            else:
                value_type, value_data = self._serialize_value_type(value)
                byte_data += value_type.to_bytes(1, 'little') + key.encode() + b'\x00' + value_data

        # Append the end of message object markers
        byte_data += self.KVS_TYPE_NO_MORE.to_bytes(1, 'little') * 2
        return byte_data

    @staticmethod
    def _read_null_terminated_wstring(data):
        parts = data.split(b'\x00\x00', 1)
        if len(parts) == 2:
            return parts[0].decode('utf-16-le'), parts[1] + b'\x00\x00'
        else:
            raise ValueError("WString not null-terminated")

    def _serialize_value_type(self, value):
        if isinstance(value, str):
            return self.KVS_TYPE_STRING, value.encode() + b'\x00'
        elif isinstance(value, int):
            if -2147483648 <= value <= 2147483647:
                return self.KVS_TYPE_INT, struct.pack('<i', value)
            else:
                return self.KVS_TYPE_INT64, struct.pack('<Q', value)
        elif isinstance(value, float):
            return self.KVS_TYPE_FLOAT, struct.pack('<f', value)
        elif isinstance(value, tuple) and len(value) == 2:
            ptr_value, size = value
            if size == 4:
                return self.KVS_TYPE_PTR, struct.pack('<I', ptr_value)
            elif size == 8:
                return self.KVS_TYPE_PTR, struct.pack('<Q', ptr_value)
            else:
                raise ValueError("Unsupported pointer size")
        elif isinstance(value, bytes) and len(value) == 4:
            return self.KVS_TYPE_COLOR, struct.pack('<I', int.from_bytes(value, byteorder = 'little'))
        elif isinstance(value, str) and value.startswith("0x"):
            return self.KVS_TYPE_DWORDPREFIXED_STRING, int(value, 16).to_bytes(4, byteorder = 'little')
        elif isinstance(value, bytes) and len(value) == 8:
            return self.KVS_TYPE_INT64, struct.pack('<Q', value)
        else:
            raise TypeError("Unsupported value type for serialization")


class MessageObject:
    def __init__(self, data = None):
        self.data = data
        self.kv_class = KeyValueClass()
        self.message_objects = []

    def parse(self):
        start = 0
        while True:
            start = self.data.find(b'MessageObject\x00', start)
            if start == -1:
                break
            end = self.data.find(b'MessageObject\x00', start + 1)
            if end == -1:
                end = len(self.data)
            message_data = self.data[start:end]
            kv = KeyValueClass()
            kv.parse(message_data[len('MessageObject\x00'):])
            self.message_objects.append(kv.data)
            start = end

    def get(self, key):
        return self.kv_class.data.get(key, None)

    def getValue(self, key, default = ""):
        return self.data.get(key, default)

    def setValue(self, key, value):
        self.data[key] = value

    def setSubKey(self, key):
        self.data["SubKeyStart"] = key

    def setSubKeyEnd(self):
        self.data["SubKeyEnd"] = None

    def serialize(self):
        # Serialize the MessageObject, including a special prefix and suffix
        return b"\x00MessageObject\x00" + self.kv_class.serialize(self.data) + b"\x08\x08"

    def get_message_objects(self):
        return self.message_objects


class Universe(Enum):
    INVALID = 0
    PUBLIC = 1
    BETA = 2
    INTERNAL = 3
    DEV = 4


class Type(Enum):
    INVALID = 0
    INDIVIDUAL = 1
    MULTISEAT = 2
    GAMESERVER = 3
    ANON_GAMESERVER = 4
    PENDING = 5
    CONTENT_SERVER = 6
    CLAN = 7
    CHAT = 8
    P2P_SUPER_SEEDER = 9
    ANON_USER = 10


class InstanceFlag(IntFlag):
    ALL = 0xFFFFFFFF
    ALL2 = 0xFF
    NONE = 0
    DESKTOP = 1  # The regular Steam instance
    CONSOLE = 2  # Steam through console
    WEB = 4  # Access via a web browser


class SteamID:
    def __init__(self, steamid: int = 0) -> None:
        self.steamid: int = steamid
        self.universe: Universe = Universe.INVALID
        self.type: Type = Type.INVALID
        self.instance: InstanceFlag = InstanceFlag.ALL
        self.account_number: int = 0
        self._parse_steamid()

    def _parse_steamid(self) -> None:
        self.universe = Universe((self.steamid >> 56) & 0xFF)
        self.type = Type((self.steamid >> 52) & 0x0F)
        self.instance = InstanceFlag((self.steamid >> 32) & 0xFFFFF)
        self.account_number = (self.steamid & 0xFFFFFFFF) // 2

    def set_universe(self, universe: Universe) -> None:
        self.universe = universe
        self._update_steamid()

    def set_type(self, type: Type) -> None:
        self.type = type
        self._update_steamid()

    def set_instance(self, instance: InstanceFlag) -> None:
        self.instance = instance
        self._update_steamid()

    def set_account_number(self, account_number: int) -> None:
        self.account_number = account_number
        self._update_steamid()

    def _update_steamid(self) -> None:
        self.steamid = (self.universe.value << 56) | (self.type.value << 52) | (self.instance.value << 32) | self.account_number

    def get_integer_format(self) -> int:
        return self.steamid

    def get_raw_bytes_format(self) -> bytes:
        return self.steamid.to_bytes(8, byteorder = 'little', signed = False)

    def __repr__(self) -> str:
        return (f"SteamID(universe={self.universe}, type={self.type}, "
                f"instance={self.instance}, account_number={self.account_number})")


class PersonaStateFlags(IntFlag):
    none = 0x00
    status = 0x01
    playerName = 0x02
    queryPort = 0x04
    sourceId = 0x08  # clan or game server steamID
    presence = 0x10
    chatMetadata = 0x20
    lastSeen = 0x40
    clanInfo = 0x80
    extraInfo = 0x100
    gameDataBlob = 0x200
    clanTag = 0x400
    facebook = 0x800
    richPresence = 0x1000
    broadcastId = 0x2000
    gameLobbyId = 0x4000
    watchingBroadcast = 0x8000


def decipher_persona_flags(value):
    """
    Decodes an integer to find the active flags set, ideally helping someone who struggles
    with the concept that light switches need to be turned on to work.
    """
    # Pull out the flags like pulling teeth, painful but necessary
    flags = [flag.name for flag in PersonaStateFlags if flag & PersonaStateFlags(value)]
    return flags if flags else ['none']  # Giving you an out when inevitably nothing makes sense


def read_null_terminated_string(stream, max_length):
    """
    Reads a null-terminated string from the stream, up to max_length bytes.
    Stops at the first null byte or after max_length bytes are read.
    """
    string_bytes = bytearray()

    for _ in range(max_length):
        byte = stream.read(1)
        if byte == b'\x00' or not byte:  # Stop at null byte or if there's nothing to read
            break
        string_bytes.extend(byte)

    return string_bytes.decode('utf-8')


class PersonaStateMessage:
    def __init__(self):
        self.flags = None
        self.friends = []
        self.status_flags = 0
        self.persona_state = 0
        self.game_id = 0
        self.game_server_ip = 0
        self.game_server_port = 0
        self.player_name = ''
        self.query_port = 0
        self.steam_id_source = 0
        self.ip_address_cm = 0
        self.avatar_hash = b''
        self.metadata_blob = b''
        self.last_logoff = 0
        self.last_logon = 0
        self.clan_rank = 0
        self.game_extra_info = ''
        self.lobby_id = 0
        self.game_id_real = 0
        self.game_data_blob_size = 0
        self.metadata = b''
        self.lobby_id = 0
        self.game_id_real = 0
        self.game_data_blob_size = 0
        self.metadata = b''

    def deserialize(self, buffer: bytes):
        stream = BytesIO(buffer)

        # Deserialize the CClientMsg<MsgClientPersonaState_t> equivalent
        # Read the number of friends
        friends_count = struct.unpack('<H', stream.read(2))[0]
        print("friends count:", friends_count)
        self.status_flags = struct.unpack('<I', stream.read(4))[0]
        print("status flags:", self.status_flags)
        #print(f"Friend Data Request Persona Flag: {decipher_persona_flags(self.status_flags)}")
        self.flags = decipher_persona_flags(self.status_flags)
        for i in range(friends_count):
            # Deserialize each friend's data
            friend_id = struct.unpack('<Q', stream.read(8))[0]
            # print()
            if friend_id == 0:
                continue

            friend_data = {
                    'friend_id':SteamID(friend_id),
            }

            if self.status_flags & 1:  # PersonaState
                friend_data['persona_state'] = struct.unpack('<B', stream.read(1))[0]
                friend_data['game_id'] = struct.unpack('<I', stream.read(4))[0]
                raw_game_server_ip = stream.read(4)
                friend_data['game_server_ip'] = socket.inet_ntoa(raw_game_server_ip)
                friend_data['game_server_port'] = struct.unpack('<H', stream.read(2))[0]
                # print(friend_data['persona_state'], friend_data['game_id'], friend_data['game_server_ip'], friend_data['game_server_port'])

            if self.status_flags & 2:  # Player name
                friend_data['player_name'] = read_null_terminated_string(stream, 64)
                # print(friend_data['player_name'])
            if self.status_flags & 4:  # Query Port
                friend_data['query_port'] = struct.unpack('<H', stream.read(2))[0]
                # print(friend_data['query_port'])
            if self.status_flags & 8:  # SteamID source
                friend_data['steam_id_source'] = struct.unpack('<Q', stream.read(8))[0]
                # print(friend_data['steam_id_source'])
            if self.status_flags & 0x10:  # IP address CM + Avatar Hash
                raw_ip_address_cm = stream.read(4)
                friend_data['ip_address_cm'] = socket.inet_ntoa(raw_ip_address_cm)
                friend_data['avatar_hash'] = stream.read(20)
                # print(friend_data['ip_address_cm'], friend_data['avatar_hash'])
            if self.status_flags & 0x20:  # Metadata Blob
                metadata_size = struct.unpack('<I', stream.read(4))[0]
                friend_data['metadata_blob'] = stream.read(metadata_size)
                # print(metadata_size, friend_data['metadata_blob'])
            if self.status_flags & 0x40:  # Last Logoff and Logon
                friend_data['last_logoff'] = datetime.utcfromtimestamp(struct.unpack('<I', stream.read(4))[0])
                friend_data['last_logon'] = datetime.utcfromtimestamp(struct.unpack('<I', stream.read(4))[0])
                # print(friend_data['last_logoff'], friend_data['last_logon'])
            if self.status_flags & 0x80:  # Clan Rank
                friend_data['clan_rank'] = struct.unpack('<I', stream.read(4))[0]
                # print(friend_data['clan_rank'])
            if self.status_flags & 0x100:  # Game Extra Info
                friend_data['game_extra_info'] = read_null_terminated_string(stream, 64)
                friend_data['game_id_real'] = struct.unpack('<Q', stream.read(8))[0]
                # print(friend_data['game_extra_info'], friend_data['game_id_real'])
            if self.status_flags & 0x200:  # Game Data Blob Size
                friend_data['game_data_blob_size'] = struct.unpack('<I', stream.read(4))[0]
                friend_data['metadata'] = stream.read(friend_data['game_data_blob_size'])
                # print(friend_data['game_data_blob_size'], friend_data['metadata'])

            if self.status_flags & 0x400:  # Clan Tag
                friend_data['clan_tag'] = read_null_terminated_string(stream, 64)

            if self.status_flags & 0x800:  # Facebook Data
                friend_data['facebook_data'] = {
                        'string':read_null_terminated_string(stream, 64),
                        'id':    struct.unpack('<Q', stream.read(8))[0]
                }
            if self.status_flags & 0x1000:  # KeyValue type system
                kv_parser = KeyValueClass()
                key_value_blob_size = struct.unpack('<I', stream.read(4))[0]
                key_value_blob = stream.read(key_value_blob_size)
                try:
                    kv_parser.parse(key_value_blob)
                    friend_data['key_value_data'] = kv_parser.data
                except Exception as e:
                    friend_data['key_value_data'] = f"Error parsing KeyValue data: {e}"

            if self.status_flags & 0x2000:  # Broadcast ID
                friend_data['broadcast_id'] = struct.unpack('<Q', stream.read(8))[0]

            if self.status_flags & 0x4000:  # Game Lobby ID
                friend_data['game_lobby_id'] = struct.unpack('<Q', stream.read(8))[0]

            if self.status_flags & 0x8000:  # Streaming Info
                friend_data['streaming_info'] = {
                        'account_id':  struct.unpack('<I', stream.read(4))[0],
                        'app_id':      struct.unpack('<I', stream.read(4))[0],
                        'viewer_count':struct.unpack('<I', stream.read(4))[0],
                        'title':       read_null_terminated_string(stream, 64)
                }

            self.friends.append(friend_data)
        # Check for any unread bytes at the end of the buffer

        remaining_bytes = stream.read()
        if remaining_bytes:
            print(f"Unread bytes remaining: {remaining_bytes.hex()}")

        return self


# Example buffer (you should replace this with real data to parse):
"""example_buffer = (
    struct.pack('<I', 1) +  # status_flags: PersonaState flag (just as an example)
    struct.pack('<I', 1) +  # Number of friends
    struct.pack('<Q', 76561198000000001) +  # Friend SteamID (example)
    struct.pack('<B', 3) +  # PersonaState (example)
    struct.pack('<I', 12345) +  # GameID
    struct.pack('<I', 1234567890) +  # GameServerIP
    struct.pack('<H', 27015)  # GameServerPort
)"""
packet = b'\xfe\x02\x00\x00\xa0\xb9\xf4\x00\x01\x00\x10\x01\xea<\x15\x00\x01\x00_\x01\x00\x00\xa0\xb9\xf4\x00\x01\x00\x10\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00benjaminspratt\x00\xff\xff\x00\x00\x00\x00\x00\x00\x00\x00\xbb=\xa5H\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00*\xd1\x85GP\xd1\x85G\x00\x00\x00\x00\x00\x00\x00\x00\x00'



packet = packet[36:]
# Deserialize the example buffer
message = PersonaStateMessage()
message.deserialize(packet)
print(message.flags)
# Output the parsed data
for friend in message.friends:
    print(friend)