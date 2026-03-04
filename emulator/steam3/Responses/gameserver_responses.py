import struct
from steam3.Types.steamid import SteamID

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
    """
    Build a GSApprove response to approve a player connection to a game server.

    Args:
        client_obj: The client connection object
        connect_token: The game connect token containing the player's steamGlobalId

    Returns:
        CMResponse packet with serialized MsgGSApprove
    """
    packet = CMResponse(eMsgID=EMsg.GSApprove, client_obj=client_obj)

    msg = MsgGSApprove(connect_token.steamGlobalId)
    packet.data = msg.serialize()
    packet.length = len(packet.data)
    return packet


def build_GSDeny(client_obj, steam_id=0, deny_reason=0, reason_text=""):
    """
    Build a GSDeny response to deny a player connection to a game server.

    Args:
        client_obj: The client connection object
        steam_id: The Steam ID of the player being denied
        deny_reason: The reason code for denial (EDenyReason enum)
        reason_text: Optional text explanation (only used if deny_reason == 7)

    Returns:
        CMResponse packet with serialized MsgGSDeny
    """
    packet = CMResponse(eMsgID=EMsg.GSDeny, client_obj=client_obj)

    msg = MsgGSDeny(steam_id, deny_reason, reason_text)
    packet.data = msg.serialize()
    packet.length = len(packet.data)
    return packet


def build_GSGetUserAchievementStatusResponse(client_obj, steamID: SteamID, achievement: str, unlocked: bool):
    """
    Build MsgGSGetUserAchievementStatusResponse matching client expectations.

    Message format (confirmed via IDA Pro analysis of steamclient):
        Body (9 bytes packed):
            - uint64 m_ulSteamID  (8 bytes at offset 0)
            - bool   m_bUnlocked  (1 byte at offset 8)
        Variable data:
            - Achievement name (null-terminated string)

    The client parses this as:
        1. Reads Steam ID from body (8 bytes)
        2. Reads achievement string via BReadStr() from variable data
        3. Reads unlocked flag from body offset 8 (1 byte)

    Args:
        client_obj: The client connection object
        steamID: The Steam ID of the user
        achievement: The achievement name string (max 128 characters)
        unlocked: Whether the achievement is unlocked

    Returns:
        CMResponse packet with properly formatted response
    """
    if len(achievement) > 128:
        raise ValueError("Achievement string exceeds 128 characters")

    packet = CMResponse(eMsgID=EMsg.GSGetUserAchievementStatusResponse, client_obj=client_obj)

    buffer = bytearray()

    # Body (9 bytes) - MUST come first before variable data
    buffer += struct.pack('<Q', steamID.get_integer_format())  # 8 bytes: m_ulSteamID
    buffer += struct.pack('<?', unlocked)                       # 1 byte: m_bUnlocked

    # Variable data - null-terminated achievement string (no padding needed)
    buffer += achievement.encode('utf-8') + b'\x00'

    packet.data = bytes(buffer)
    packet.length = len(packet.data)
    return packet


def build_GSAssociateWithClanResponse(client_obj, steam_id_clan: int, eresult: int = 1):
    """
    Build GSAssociateWithClanResponse (EMsg 939) to confirm clan association.

    Binary format:
        - uint64 m_ulSteamIDClan (8 bytes) - The clan Steam ID
        - uint32 m_eResult (4 bytes) - EResult code (1=OK, 2=Fail)

    Args:
        client_obj: The client connection object
        steam_id_clan: The Steam ID of the clan
        eresult: Result code (1=OK, 2=Fail)

    Returns:
        CMResponse packet with serialized response
    """
    packet = CMResponse(eMsgID=EMsg.GSAssociateWithClanResponse, client_obj=client_obj)

    buffer = struct.pack('<Q', steam_id_clan)  # 8 bytes: clan Steam ID
    buffer += struct.pack('<I', eresult)       # 4 bytes: EResult

    packet.data = buffer
    packet.length = len(buffer)
    return packet
