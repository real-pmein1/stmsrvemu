import struct

from steam3.ClientManager.client import Client
from steam3.Types.community_types import ChatRoomEnterResponse, ChatRoomType
from steam3.Types.emsg import EMsg
from steam3.Types.steam_types import EInstanceFlag, EResult, EType, EUniverse
from steam3.Types.steamid import SteamID
from steam3.cm_packet_utils import CMResponse
from steam3.messages.MsgClientCreateChat import MsgClientCreateChat


def build_send_friendsmsg(client_obj: Client, message):
    packet = CMResponse(eMsgID = 0x02CE, client_obj = client_obj)  # Assuming CMPacket is defined somewhere

    # Prepare message content and calculate packet length
    message_content = message.message.encode('latin-1') + b'\x00'  # Null-terminated
    #packet.length = 24 + len(message_content)

    pos = 0
    clientId2 = 0x01100001

    packet.data = struct.pack('III',
                               message.from_,
                               message.sessionID,
                               message.type)  # type attribute, with default

    packet.data += message_content  # message attribute

    packet.length = len(packet.data)
    return packet


def build_CreateChatResponse(client_obj, chatinfo: MsgClientCreateChat):
    """
    struct MsgClientCreateChatResponse_t
    {
      EResult m_eResult; maybe ChatActionResult
      uint64 m_ulSteamIDChat;
      EChatRoomType m_eType;
      uint64 m_ulSteamIDFriendChat;
    };
    """
    packet = CMResponse(eMsgID = EMsg.ClientCreateChatResponse, client_obj = client_obj)
    # NOTE: if type 3, it is a game lobby, it is temporary and does not need to be added to the database

    # Format string: < indicates little-endian, i for int32, q for int64
    format_str = '<iqiq'

    # Pack the data according to the specified format
    packet.data = struct.pack(
            format_str, # int64
            EResult.OK,  # int32
            chatinfo.m_ulSteamIDClan,  # int64
            chatinfo.m_eType,  # int32
            chatinfo.m_ulSteamIDFriendChat
    )

    packet.length = len(packet.data)
    return packet


def build_EnterChatroomResponse(client_obj, chatroomID):
    """MsgClientChatEnter_t
    {
      uint64 m_ulSteamIDChat;  <-- chatroom steamid
      uint64 m_ulSteamIDFriendChat;  <-- friendsteamid (requesting user?? inviting user??)
      EChatRoomType m_EChatRoomType;
      uint64 m_ulSteamIDOwner; <--chatroom clients owner steamid, usually requesting user if user created chatroom
      uint64 m_ulSteamIDClan; <--clan owner steamid
      bool m_bLocked;
      EChatRoomEnterResponse m_EChatRoomEnterResponse;
      uint32 m_cMembersTotal;
    };"""
    packet = CMResponse(eMsgID = EMsg.ClientChatEnter, client_obj = client_obj)

    sourceID = SteamID()
    sourceID.set_type(EType.INDIVIDUAL)
    sourceID.set_instance(EInstanceFlag.ALL)
    sourceID.set_universe(EUniverse.PUBLIC)
    sourceID.set_accountID(123)
    sourceID._update_steamid()

    sourceID2 = SteamID()
    sourceID2.set_type(EType.CLAN)
    sourceID2.set_instance(EInstanceFlag.ALL)
    sourceID2.set_universe(EUniverse.PUBLIC)
    sourceID2.set_accountID(13)
    sourceID2._update_steamid()

    format_str = '<QQIQQBII'

    packet.data = struct.pack(
            format_str,
            chatroomID,  # int64
            sourceID.get_integer_format(),  # int64
            int(ChatRoomType.MUC),  # int32 MUC -> multi user chat
            76561197960265730,  # int64
            sourceID2.get_integer_format(),  # int64
            0,  # int8
            int(ChatRoomEnterResponse.success),  # int32
            3,  # int32
    )

    # The string after the message structure is a max 128 character long chatroom name
    packet.data += b'Steam3ChatRoom\n'.rjust(128, b'\x00')
    packet.length = len(packet.data)
    return packet