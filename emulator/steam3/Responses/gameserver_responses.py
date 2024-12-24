import struct

from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse
from steam3.messages.MsgGSDeny import MsgGSDeny
from steam3.messages.MsgGSApprove import MsgGSApprove


def build_GSResponse(client_obj, errorcode = 1):
    # print(f"Responding to Gameserver Status Request")
    packet = CMResponse(eMsgID = EMsg.GSStatusReply, client_obj = client_obj)

    packet.data = struct.pack('I', errorcode)  # This is an errorcode, probably regular steam status?

    packet.length = len(packet.data)
    return packet

def build_GSApprove(client_obj, connect_token):
    # print(f"Responding to Gameserver Status Request")
    packet = CMResponse(eMsgID = EMsg.GSApprove, client_obj = client_obj)

    packet.data = MsgGSApprove(connect_token.steamGlobalId)

    packet.length = len(packet.data)
    return packet

def build_GSDeny(client_obj, steam_id=0, deny_reason=0, reason_text=""):
    # print(f"Responding to Gameserver Status Request")
    packet = CMResponse(eMsgID = EMsg.GSDeny, client_obj = client_obj)

    packet.data = MsgGSDeny(steam_id, deny_reason, reason_text)

    packet.length = len(packet.data)
    return packet


def build_GSGetUserAchievementStatusResponse(client_obj, steam_id: int, achievement: str, unlocked: bool) -> bytes:
    """
    Generate a byte buffer for MsgGSGetUserAchievementStatusResponse_t.

    Args:
        steam_id (int): The 64-bit Steam ID of the user.
        achievement (str): The achievement string (up to 128 characters).
        unlocked (bool): Whether the achievement is unlocked.

    Returns:
        bytes: The generated byte buffer.
    """
    # Validate achievement string length
    if len(achievement) > 128:
        raise ValueError("Achievement string exceeds 128 characters")

    packet = CMResponse(eMsgID = EMsg.GSGetUserAchievementStatusResponse, client_obj = client_obj)

    # Prepare achievement string with null termination
    achievement_encoded = achievement.encode('utf-8') + b'\x00'

    # Construct the byte buffer
    buffer = bytearray()

    # Steam ID (64-bit, split into two 32-bit integers for compatibility with function)
    buffer += struct.pack('<Q', steam_id)

    # Achievement string (null-terminated, up to 128 bytes)
    buffer += achievement_encoded
    buffer += b'\x00' * (128 - len(achievement_encoded))  # Pad to 128 bytes

    # Unlocked status (boolean, packed as 1 byte)
    buffer += struct.pack('<?', True)
    packet.data = bytes(buffer)
    return packet