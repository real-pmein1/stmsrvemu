import struct

from steam3.ClientManager import Client_Manager
from steam3.ClientManager.client import Client
from steam3.Responses.chat_responses import build_CreateChatResponse, build_EnterChatroomResponse, build_send_friendsmsg
from steam3.Types.wrappers import SteamID
from steam3.cm_packet_utils import CMPacket, ChatMessage
from steam3.Responses.general_responses import build_GeneralAck
from steam3.messages.MsgClientCreateChat import MsgClientCreateChat


def handle_FriendMessage(cmserver_obj, packet, client_obj):
    client_address = client_obj.ip_port
    request = packet.CMRequest
    message = ChatMessage()
    message.from_ = request.accountID
    message.to, message.sessionID, message.type = struct.unpack('<III', request.data[:12])
    message.message = request.data[12:].split(b'\x00', 1)[0].decode('latin-1')

    # Store the message in the list
    msg_obj = ChatMessage(message.from_, message.to, message.sessionID, message.type, message.message)
    #cmserver_obj.pending_messages.append(msg_obj)

    build_GeneralAck(client_obj,packet,client_address,cmserver_obj)
    client_friend = Client_Manager.get_client_by_identifier(SteamID(message.to // 2))
    cmserver_obj.sendReply(client_friend, [build_send_friendsmsg(client_friend, msg_obj)])
    return -1
def handle_ChatMessage(cmserver_obj, packet, client_obj):
    """packetid: 799
        b'\x02\x00\x00\x00\x01\x00\x10\x01
        \x04\x00\x00\x00\x00\x00\x88\x01\x01
        \x00\x00\x00hai\x00'
    """
    return -1

def handle_CreateChat(cmserver_obj, packet, client_obj):
    """packetid: 809
    b'\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00
    \x00\x00\x00\x1a\x01\x00\x00\x1a\x01\x00\x00\n\x00\x00\x00\x00\x00\x00
    \x00\x01\x04\x00\x00\x00\x01\x00\x10\x01\x06\x00\x00\x00\x01\x00\x10\x01\x00'"""


    # TODO FINISH THIS, store info in database.. use seperate chatroom manager?
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Client Create Chatroom Request")
    request = packet.CMRequest
    MsgCreateChat = MsgClientCreateChat(request.data)
    print(MsgCreateChat)

    return build_CreateChatResponse(client_obj, MsgCreateChat)

def handle_JoinChat(cmserver_obj, packet: CMPacket, client_obj: Client):
    """packetid: 801
    b'\x04\x00\x00\x00\x00\x00\x88\x00' -> steamID of room
    b'\x00' -> isvoicespeaker"""
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Client Join Chatroom Request")
    chatroomID = struct.unpack_from('<Q', request.data, 0)[0]
    return build_EnterChatroomResponse(client_obj, chatroomID)