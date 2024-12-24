import struct

class MsgClientCreateChat:
    def __init__(self, data):
        self.parse(data)

    def parse(self, data):
        # Unpacking each field from the binary data
        (
            self.m_eType,                  # enum EChatRoomType (4 bytes)
            self.m_ulGameID,               # unsigned long long (8 bytes)
            self.m_ulSteamIDClan,          # unsigned long long (8 bytes)
            self.m_rgfPermissionOfficer,   # unsigned int (4 bytes)
            self.m_rgfPermissionMember,    # unsigned int (4 bytes)
            self.m_rgfPermissionAll,       # unsigned int (4 bytes)
            self.m_cMembersMax,            # unsigned int (4 bytes)
            self.m_bLocked,                # unsigned char (1 byte)
            self.m_ulSteamIDFriendChat,    # unsigned long long (8 bytes)
            self.m_ulSteamIDInvited        # unsigned long long (8 bytes)
        ) = struct.unpack_from('<IQQIIIIBQQ', data, 0)
        self.chatroom_name = data[struct.calcsize('<IQQIIIIBQQ'):].decode('utf-8').rstrip('\x00')

    def __str__(self):
        return (f"Chat Type: {self.m_eType}, Game ID: {self.m_ulGameID}, Clan Steam ID: {self.m_ulSteamIDClan}, "
                f"Permissions Officer: {self.m_rgfPermissionOfficer}, Permissions Member: {self.m_rgfPermissionMember}, "
                f"Permissions All: {self.m_rgfPermissionAll}, Max Members: {self.m_cMembersMax}, "
                f"Locked: {self.m_bLocked}, Friend Chat Steam ID: {self.m_ulSteamIDFriendChat}, "
                f"Invited Steam ID: {self.m_ulSteamIDInvited}, chatroom name: {self.chatroom_name}")

"""    (b'\x02\x00\x00\x00' <-- type
     b'\x00\x00\x00\x00\x00\x00\x00\x00' <-- gameid
     b'\x00\x00\x00\x00\x00\x00\x00\x00' <-- clanid
     b'\x1a\x01\x00\x00' <-- admin/officer permissions
     b'\x1a\x01\x00\x00' <--member permissions
     b'\n\x00\x00\x00'  <-- all permissions
     b'\x00\x00\x00\x00'  <-- members max
     b'\x01' <-- locked
     b'\x06\x00\x00\x00\x01\x00\x10\x01'  <-- chatroom was created with this friend
     b'\n\x00\x00\x00\x01\x00\x10\x01' <-- invited this user
     b'\x00') <------ name"""

"""packetid: 809 / ClientCreateChat
b'\x03\x00\x00\x00\xf4\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x1a\x01\x00\x00\x1a\x01\x00\x00\x08\x00\x00\x00\x04\x00\x00\x00
\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00(unnamed)\x00'

b'\x03\x00\x00\x00
\xf4\x01\x00\x00\x00\x00\x00\x00
\x00\x00\x00\x00\x00\x00\x00\x00
\x1a\x01\x00\x00
\x1a\x01\x00\x00
\x08\x00\x00\x00
\x04\x00\x00\x00
\x01
\x00\x00\x00\x00\x00\x00\x00\x00
\x00\x00\x00\x00\x00\x00\x00\x00
(unnamed)\x00'
2024-11-19 00:17:31     CMUDP27017    INFO     (192.168.3.180:53879): Client Create Chatroom Request
Chat Type: 3, Game ID: 500, Clan Steam ID: 0, Permissions Officer: 282, Permissions Member: 282, Permissions All: 8, Max Members: 4, Locked: 1, Friend Chat Steam ID: 0, Invited Steam ID: 0"""