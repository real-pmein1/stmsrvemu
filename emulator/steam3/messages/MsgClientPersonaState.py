import struct
from datetime import datetime
from io import BytesIO

from steam3.utilities import decipher_persona_flags, read_null_terminated_string


class PersonaStateMessage:
    def __init__(self):
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

    def serialize(self) -> bytes:
        stream = BytesIO()

        # Write the number of friends
        friends_count = len(self.friends)
        stream.write(struct.pack('<H', friends_count))

        # Write the status flags
        stream.write(struct.pack('<I', self.status_flags))

        for friend_data in self.friends:
            # Write each friend's data based on the status flags
            stream.write(struct.pack('<Q', friend_data['friend_id']))

            if friend_data['friend_id'] == 0:
                continue

            if self.status_flags & 1:  # PersonaState
                stream.write(struct.pack('<B', friend_data['persona_state'] or 0))
                stream.write(struct.pack('<I', friend_data['game_id'] or 0))
                stream.write(struct.pack('<I', friend_data['game_server_ip'] or 0))
                stream.write(struct.pack('<H', friend_data['game_server_port'] or 0))

            if self.status_flags & 2:  # Player name
                player_name = friend_data['player_name'] or ""
                player_name_bytes = player_name.encode('utf-8')
                stream.write(player_name_bytes + b'\x00' * (64 - len(player_name_bytes)))

            if self.status_flags & 4:  # Query Port
                stream.write(struct.pack('<H', friend_data['query_port'] or 0))

            if self.status_flags & 8:  # SteamID source
                stream.write(struct.pack('<Q', friend_data['steam_id_source'] or 0))

            if self.status_flags & 0x10:  # IP address CM + Avatar Hash
                stream.write(struct.pack('<I', friend_data['ip_address_cm'] or 0))
                avatar_hash = friend_data['avatar_hash'] or b'\x00' * 20
                stream.write(avatar_hash)

            if self.status_flags & 0x20:  # Metadata Blob
                metadata_blob = friend_data['metadata_blob'] or b''
                stream.write(struct.pack('<I', len(metadata_blob)))
                stream.write(metadata_blob)

            if self.status_flags & 0x40:  # Last Logoff and Logon
                last_logoff = int(friend_data['last_logoff'].timestamp()) if friend_data['last_logoff'] else 0
                last_logon = int(friend_data['last_logon'].timestamp()) if friend_data['last_logon'] else 0
                stream.write(struct.pack('<I', last_logoff))
                stream.write(struct.pack('<I', last_logon))

            if self.status_flags & 0x80:  # Clan Rank
                stream.write(struct.pack('<I', friend_data['clan_rank'] or 0))

            if self.status_flags & 0x100:  # Game Extra Info
                game_extra_info = friend_data['game_extra_info'] or ""
                game_extra_info_bytes = game_extra_info.encode('utf-8')
                stream.write(game_extra_info_bytes + b'\x00' * (64 - len(game_extra_info_bytes)))
                stream.write(struct.pack('<Q', friend_data['game_id_real'] or 0))

            if self.status_flags & 0x200:  # Game Data Blob Size
                metadata = friend_data['metadata'] or b''
                stream.write(struct.pack('<I', len(metadata)))
                stream.write(metadata)

        return stream.getvalue()

    def deserialize(self, buffer: bytes):
        stream = BytesIO(buffer)

        # Deserialize the CClientMsg<MsgClientPersonaState_t> equivalent
        # Read the number of friends
        friends_count = struct.unpack('<H', stream.read(2))[0]
        print("friends count:", friends_count)
        self.status_flags = struct.unpack('<I', stream.read(4))[0]
        print("status flags:", self.status_flags)
        print(f"Friend Data Request Persona Flag: {decipher_persona_flags(self.status_flags)}")
        for i in range(friends_count):
            # Deserialize each friend's data
            friend_id = struct.unpack('<Q', stream.read(8))[0]
            print("steamid:", friend_id)
            if friend_id == 0:
                continue

            friend_data = {
                    'friend_id':friend_id, 'persona_state':None, 'game_id':None, 'game_server_ip':None, 'game_server_port':None, 'player_name':None, 'query_port':None, 'steam_id_source':None, 'ip_address_cm':None, 'avatar_hash':None, 'metadata_blob':None, 'last_logoff':None, 'last_logon':None, 'clan_rank':None, 'game_extra_info':None, 'lobby_id':None, 'game_id_real':None
            }

            if self.status_flags & 1:  # PersonaState
                friend_data['persona_state'] = struct.unpack('<B', stream.read(1))[0]
                friend_data['game_id'] = struct.unpack('<I', stream.read(4))[0]
                friend_data['game_server_ip'] = struct.unpack('<I', stream.read(4))[0]
                friend_data['game_server_port'] = struct.unpack('<H', stream.read(2))[0]  # print(friend_data['persona_state'], friend_data['game_id'], friend_data['game_server_ip'], friend_data['game_server_port'])

            if self.status_flags & 2:  # Player name
                friend_data['player_name'] = read_null_terminated_string(stream, 64)  # print(friend_data['player_name'])
            if self.status_flags & 4:  # Query Port
                friend_data['query_port'] = struct.unpack('<H', stream.read(2))[0]  # print(friend_data['query_port'])
            if self.status_flags & 8:  # SteamID source
                friend_data['steam_id_source'] = struct.unpack('<Q', stream.read(8))[0]  # print(friend_data['steam_id_source'])
            if self.status_flags & 0x10:  # IP address CM + Avatar Hash
                friend_data['ip_address_cm'] = struct.unpack('<I', stream.read(4))[0]
                friend_data['avatar_hash'] = stream.read(20)  # print(friend_data['ip_address_cm'], friend_data['avatar_hash'])
            if self.status_flags & 0x20:  # Metadata Blob
                metadata_size = struct.unpack('<I', stream.read(4))[0]
                friend_data['metadata_blob'] = stream.read(metadata_size)  # print(metadata_size, friend_data['metadata_blob'])
            if self.status_flags & 0x40:  # Last Logoff and Logon
                friend_data['last_logoff'] = datetime.utcfromtimestamp(struct.unpack('<I', stream.read(4))[0])
                friend_data['last_logon'] = datetime.utcfromtimestamp(struct.unpack('<I', stream.read(4))[0])  # print(friend_data['last_logoff'], friend_data['last_logon'])
            if self.status_flags & 0x80:  # Clan Rank
                friend_data['clan_rank'] = struct.unpack('<I', stream.read(4))[0]  # print(friend_data['clan_rank'])
            if self.status_flags & 0x100:  # Game Extra Info
                friend_data['game_extra_info'] = read_null_terminated_string(stream, 64)
                friend_data['game_id_real'] = struct.unpack('<Q', stream.read(8))[0]  # print(friend_data['game_extra_info'], friend_data['game_id_real'])
            if self.status_flags & 0x200:  # Game Data Blob Size
                friend_data['game_data_blob_size'] = struct.unpack('<I', stream.read(4))[0]
                friend_data['metadata'] = stream.read(friend_data['game_data_blob_size'])  # print(friend_data['game_data_blob_size'], friend_data['metadata'])
            self.friends.append(friend_data)

        return self