from steam3.messages.MsgClientCreateChat import MsgClientCreateChat


def handle_InviteUserToClan(cmserver_obj, packet, client_obj):
    # TODO FINISH THIS, store info in database.. use seperate chatroom manager?
    client_address = client_obj.ip_port
    request = packet.CMRequest
    MsgCreateChat = MsgClientCreateChat(request.data)
    print(MsgCreateChat)