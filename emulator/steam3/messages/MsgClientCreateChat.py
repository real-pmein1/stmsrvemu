from __future__ import annotations
import struct
from steam3.Types.steamid import SteamID
from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse


class MsgClientCreateChat:
    """Request to create a chatroom or lobby.

    This message exists in two layouts. Early versions did not include
    ``m_ulSteamIDClan``; later versions inserted the field after
    ``m_ulGameID``. The presence of the clan SteamID is determined by the
    size of the binary header excluding the trailing chatroom name.

    Attributes mirror the C structure. All SteamID fields are represented
    by :class:`SteamID` objects.
    """

    # C++ structure has chatRoomFlags as 1 byte (uint8), not 4 bytes
    # This matches the C++ exactly: type(4) + gameId(8) + clanGlobalId(8) + 
    # officerPermission(4) + memberPermission(4) + allPermission(4) + 
    # membersMax(4) + chatRoomFlags(1) + friendChatGlobalId(8) + invitedGlobalId(8)
    _FMT_WITH_CLAN = "<iQQIIIIBQQ"
    _FMT_NO_CLAN = "<iQIIIIBQQ"

    def __init__(self, client_obj, data: bytes | None = None) -> None:
        """Initialise the message.

        Args:
            client_obj: Client issuing the request.
            data: Optional payload to deserialize.
        """
        self.client_obj = client_obj
        self.m_eType = 0
        self.m_ulGameID = 0
        self.m_ulSteamIDClan = SteamID()
        self.m_rgfPermissionOfficer = 0
        self.m_rgfPermissionMember = 0
        self.m_rgfPermissionAll = 0
        self.m_cMembersMax = 0
        self.m_bLocked = 0  # chatRoomFlags as byte
        self.m_ulSteamIDFriendChat = SteamID()
        self.m_ulSteamIDInvited = SteamID()
        self.chatroom_name = ""

        if data is not None:
            self.deserialize(data)

    def deserialize(self, data: bytes) -> None:
        """Parse the binary payload into structured fields."""
        header_with = struct.calcsize(self._FMT_WITH_CLAN)
        header_without = struct.calcsize(self._FMT_NO_CLAN)

        if len(data) >= header_with + 1:
            fmt = self._FMT_WITH_CLAN
            header_size = header_with
            (
                self.m_eType,
                self.m_ulGameID,
                clan_id,
                self.m_rgfPermissionOfficer,
                self.m_rgfPermissionMember,
                self.m_rgfPermissionAll,
                self.m_cMembersMax,
                self.m_bLocked,
                friend_id,
                invited_id,
            ) = struct.unpack_from(fmt, data, 0)
            self.m_ulSteamIDClan = SteamID.from_raw(clan_id)
        else:
            fmt = self._FMT_NO_CLAN
            header_size = header_without
            (
                self.m_eType,
                self.m_ulGameID,
                self.m_rgfPermissionOfficer,
                self.m_rgfPermissionMember,
                self.m_rgfPermissionAll,
                self.m_cMembersMax,
                self.m_bLocked,
                friend_id,
                invited_id,
            ) = struct.unpack_from(fmt, data, 0)
            self.m_ulSteamIDClan = SteamID()

        self.m_ulSteamIDFriendChat = SteamID.from_raw(friend_id)
        self.m_ulSteamIDInvited = SteamID.from_raw(invited_id)
        name_bytes = data[header_size:]
        self.chatroom_name = name_bytes.split(b"\x00", 1)[0].decode("utf-8", errors="ignore")

    def to_clientmsg(self, version: int | None = None) -> CMResponse:
        """Serialize the message back to a CMRequest.

        Args:
            version: 1 for the legacy format without ``m_ulSteamIDClan`` or
                2 for the newer layout. If ``None``, version 2 is used when a
                non-zero clan SteamID is present.
        """
        if version is None:
            version = 2 if int(self.m_ulSteamIDClan) else 1

        packet = CMResponse(eMsgID=EMsg.ClientCreateChat, client_obj=self.client_obj)
        if version == 2:
            header = struct.pack(
                self._FMT_WITH_CLAN,
                self.m_eType,
                self.m_ulGameID,
                int(self.m_ulSteamIDClan),
                self.m_rgfPermissionOfficer,
                self.m_rgfPermissionMember,
                self.m_rgfPermissionAll,
                self.m_cMembersMax,
                self.m_bLocked,
                int(self.m_ulSteamIDFriendChat),
                int(self.m_ulSteamIDInvited),
            )
        else:
            header = struct.pack(
                self._FMT_NO_CLAN,
                self.m_eType,
                self.m_ulGameID,
                self.m_rgfPermissionOfficer,
                self.m_rgfPermissionMember,
                self.m_rgfPermissionAll,
                self.m_cMembersMax,
                self.m_bLocked,
                int(self.m_ulSteamIDFriendChat),
                int(self.m_ulSteamIDInvited),
            )
        packet.data = header + self.chatroom_name.encode("utf-8") + b"\x00"
        packet.length = len(packet.data)
        return packet

    def to_protobuf(self):
        """This message has no protobuf equivalent."""
        raise NotImplementedError("to_protobuf not implemented")

    def __str__(self) -> str:
        return (
            f"Chat Type: {self.m_eType}, Game ID: {self.m_ulGameID}, "
            f"Clan Steam ID: {int(self.m_ulSteamIDClan)}, "
            f"Permissions Officer: {self.m_rgfPermissionOfficer}, "
            f"Permissions Member: {self.m_rgfPermissionMember}, "
            f"Permissions All: {self.m_rgfPermissionAll}, Max Members: {self.m_cMembersMax}, "
            f"Locked: {self.m_bLocked}, Friend Chat Steam ID: {int(self.m_ulSteamIDFriendChat)}, "
            f"Invited Steam ID: {int(self.m_ulSteamIDInvited)}, chatroom name: {self.chatroom_name}"
        )
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