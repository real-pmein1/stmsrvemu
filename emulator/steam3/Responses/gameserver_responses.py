import struct

from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse


def build_GSResponse(client_obj, errorcode = 1):
    # print(f"Responding to Gameserver Status Request")
    packet = CMResponse(eMsgID = EMsg.GSStatusReply, client_obj = client_obj)

    packet.data = struct.pack('I', errorcode)  # This is an errorcode, probably regular steam status?

    packet.length = len(packet.data)
    return packet