import struct
from datetime import datetime
from enum import IntFlag
from io import BytesIO

class PersonaStateFlags(IntFlag):
    none = 0x00
    status = 0x01
    playerName = 0x02
    queryPort = 0x04
    sourceId = 0x08 # clan or game server steamID
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

    def __repr__(self):
        return f"<PersonaStateMessage(friends={self.friends}, status_flags={self.status_flags}, persona_state={self.persona_state})>"

    def __str__(self):
        friend_info = ", ".join([f"Friend ID: {friend['friend_id']}, Persona State: {friend['persona_state']}" for friend in self.friends])
        return (
                f"PersonaStateMessage:\n"
                f"  Status Flags: {self.status_flags}\n"
                f"  Persona State: {self.persona_state}\n"
                f"  Friends: [{friend_info}]\n"
        )

    def serialize(self) -> bytes:
        stream = BytesIO()

        friends_count = len(self.friends)
        stream.write(struct.pack('<H', friends_count))
        stream.write(struct.pack('<I', self.status_flags))

        for friend_data in self.friends:
            stream.write(struct.pack('<Q', friend_data['friend_id']))

            if friend_data['friend_id'] == 0:
                continue

            if self.status_flags & 1:
                stream.write(struct.pack('<B', friend_data['persona_state'] or 0))
                stream.write(struct.pack('<I', friend_data['game_id'] or 0))
                stream.write(struct.pack('<I', friend_data['game_server_ip'] or 0))
                stream.write(struct.pack('<H', friend_data['game_server_port'] or 0))

            if self.status_flags & 2:
                player_name = friend_data['player_name'] or ""
                player_name_bytes = player_name.encode('utf-8')
                stream.write(player_name_bytes + b'\x00' * (64 - len(player_name_bytes)))

            if self.status_flags & 4:
                stream.write(struct.pack('<H', friend_data['query_port'] or 0))

            if self.status_flags & 8:
                stream.write(struct.pack('<Q', friend_data['steam_id_source'] or 0))

            if self.status_flags & 0x10:
                stream.write(struct.pack('<I', friend_data['ip_address_cm'] or 0))
                avatar_hash = friend_data['avatar_hash'] or b'\x00' * 20
                stream.write(avatar_hash)

            if self.status_flags & 0x20:
                metadata_blob = friend_data['metadata_blob'] or b''
                stream.write(struct.pack('<I', len(metadata_blob)))
                stream.write(metadata_blob)

            if self.status_flags & 0x40:
                last_logoff = int(friend_data['last_logoff'].timestamp()) if friend_data['last_logoff'] else 0
                last_logon = int(friend_data['last_logon'].timestamp()) if friend_data['last_logon'] else 0
                stream.write(struct.pack('<I', last_logoff))
                stream.write(struct.pack('<I', last_logon))

            if self.status_flags & 0x80:
                stream.write(struct.pack('<I', friend_data['clan_rank'] or 0))

            if self.status_flags & 0x100:
                game_extra_info = friend_data['game_extra_info'] or ""
                game_extra_info_bytes = game_extra_info.encode('utf-8')
                stream.write(game_extra_info_bytes + b'\x00' * (64 - len(game_extra_info_bytes)))
                stream.write(struct.pack('<Q', friend_data['game_id_real'] or 0))

            if self.status_flags & 0x200:
                metadata = friend_data['metadata'] or b''
                stream.write(struct.pack('<I', len(metadata)))
                stream.write(metadata)

        return stream.getvalue()

    def deserialize(self, buffer: bytes):
        stream = BytesIO(buffer)
        friends_count = struct.unpack('<H', stream.read(2))[0]
        self.status_flags = struct.unpack('<I', stream.read(4))[0]

        # Display the status flags with their actual names
        flag_names = decipher_persona_flags(self.status_flags)
        print(f"Friends count: {friends_count}, Status flags: {self.status_flags} ({', '.join(flag_names)})")

        for i in range(friends_count):
            friend_id = struct.unpack('<Q', stream.read(8))[0]
            print(f"Friend ID: {friend_id}")

            if friend_id == 0:
                continue

            friend_data = {
                    'friend_id':       friend_id,
                    'persona_state':   None,
                    'game_id':         None,
                    'game_server_ip':  None,
                    'game_server_port':None,
                    'player_name':     None,
                    'query_port':      None,
                    'steam_id_source': None,
                    'ip_address_cm':   None,
                    'avatar_hash':     None,
                    'metadata_blob':   None,
                    'last_logoff':     None,
                    'last_logon':      None,
                    'clan_rank':       None,
                    'game_extra_info': None,
                    'game_id_real':    None,
                    'metadata':        None,
            }

            if self.status_flags & 1:
                friend_data['persona_state'] = struct.unpack('<B', stream.read(1))[0]
                friend_data['game_id'] = struct.unpack('<I', stream.read(4))[0]
                friend_data['game_server_ip'] = struct.unpack('<I', stream.read(4))[0]
                friend_data['game_server_port'] = struct.unpack('<H', stream.read(2))[0]
                print(f"Persona State: {friend_data['persona_state']}, Game ID: {friend_data['game_id']}, Server IP: {friend_data['game_server_ip']}, Server Port: {friend_data['game_server_port']}")

            if self.status_flags & 2:
                friend_data['player_name'] = read_null_terminated_string(stream, 64)
                print(f"Player Name: {friend_data['player_name']}")

            if self.status_flags & 4:
                friend_data['query_port'] = struct.unpack('<H', stream.read(2))[0]
                print(f"Query Port: {friend_data['query_port']}")

            if self.status_flags & 8:
                friend_data['steam_id_source'] = struct.unpack('<Q', stream.read(8))[0]
                print(f"Steam ID Source: {friend_data['steam_id_source']}")

            if self.status_flags & 0x10:
                friend_data['ip_address_cm'] = struct.unpack('<I', stream.read(4))[0]
                friend_data['avatar_hash'] = stream.read(20)
                print(f"IP Address CM: {friend_data['ip_address_cm']}, Avatar Hash: {friend_data['avatar_hash']}")

            if self.status_flags & 0x20:
                metadata_size = struct.unpack('<I', stream.read(4))[0]
                friend_data['metadata_blob'] = stream.read(metadata_size)
                print(f"Metadata Blob Size: {metadata_size}, Blob: {friend_data['metadata_blob']}")

            if self.status_flags & 0x40:
                friend_data['last_logoff'] = datetime.utcfromtimestamp(struct.unpack('<I', stream.read(4))[0])
                friend_data['last_logon'] = datetime.utcfromtimestamp(struct.unpack('<I', stream.read(4))[0])
                print(f"Last Logoff: {friend_data['last_logoff']}, Last Logon: {friend_data['last_logon']}")

            if self.status_flags & 0x80:
                friend_data['clan_rank'] = struct.unpack('<I', stream.read(4))[0]
                print(f"Clan Rank: {friend_data['clan_rank']}")

            if self.status_flags & 0x100:
                friend_data['game_extra_info'] = read_null_terminated_string(stream, 64)
                friend_data['game_id_real'] = struct.unpack('<Q', stream.read(8))[0]
                print(f"Game Extra Info: {friend_data['game_extra_info']}, Game ID Real: {friend_data['game_id_real']}")

            if self.status_flags & 0x200:
                friend_data['game_data_blob_size'] = struct.unpack('<I', stream.read(4))[0]
                friend_data['metadata'] = stream.read(friend_data['game_data_blob_size'])
                print(f"Game Data Blob Size: {friend_data['game_data_blob_size']}, Metadata: {friend_data['metadata']}")

            self.friends.append(friend_data)

        return self


# Example deserialization from a byte buffer
buffer = b'\xfe\x02\x00\x00$\x02\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xef\xc4\xa0\x9b\x01\x01\x00\x10\x01\x00v/\x00\x02\x00R\x00\x00\x00\xba\r\x00\x00\x00\x00p\x01leekspin\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x008\r\x00\x00\x00\x00p\x01loituma\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'

message = PersonaStateMessage()
message.deserialize(buffer[36:])
#print(message)