import struct
import logging

from config import get_config
from steam3.ClientManager.client import Client
from steam3.messages.responses.MSGClientSendGuestPassResponse import MSGClientSendGuestPassResponse
from steam3.messages.responses.MSGClientAckGuestPassResponse import MSGClientAckGuestPassResponse
from steam3.messages.responses.MSGClientRedeemGuestPassResponse import MSGClientRedeemGuestPassResponse
from steam3.Types.MessageObject.GuestPass import GuestPassMessageObject, GuestPass_Deprecated
from steam3.Types.emsg import EMsg
from steam3.Types.steam_types import EResult
from steam3.cm_packet_utils import CMResponse
from steam3.utilities import add_time_to_current_uint32, get_current_time_uint32
from steam3.messages.responses.MsgClientGetGiftTargetListResponse import (
    MsgClientGetGiftTargetListResponse,
)

log = logging.getLogger('GUESTPASS')


def _is_guestpass_disabled():
    """Check if the guestpass system is disabled in config."""
    config = get_config()
    return config.get('disable_guestpass_system', 'false').lower() == 'true'


def build_SendGuestPassResponse(client_obj: Client, errorcode = EResult.OK, guest_pass_id = 0):
    """Build response for sending a guest pass"""
    msg = MSGClientSendGuestPassResponse(client_obj)
    msg.result = errorcode
    msg.guest_pass_id = guest_pass_id
    
    return msg.to_clientmsg()


def build_SendAckGuestPassResponse(client_obj: Client, errorcode = EResult.OK, guest_pass_id = 0):
    """Build response for acknowledging a guest pass"""
    msg = MSGClientAckGuestPassResponse(client_obj)
    msg.result = errorcode
    msg.guest_pass_id = guest_pass_id
    
    return msg.to_clientmsg()


def build_RedeemGuestPassResponse(client_obj: Client, errorcode = EResult.OK, guest_pass_id = 0, package_id = 0):
    """Build response for redeeming a guest pass"""
    msg = MSGClientRedeemGuestPassResponse(client_obj)
    msg.result = errorcode
    msg.guest_pass_id = guest_pass_id
    msg.package_id = package_id
    
    return msg.to_clientmsg()

def build_GetGiftTargetListResponse(cmserver_obj, client_obj: Client, friends_list, packageID):
    """Send a ``MsgClientGetGiftTargetListResponse`` for each friend.

    Args:
        cmserver_obj: The connection manager server handling the request.
        client_obj (Client): The requesting client.
        friends_list (list[dict]): Friends and gift eligibility information.
        packageID (int): Package ID to check ownership against.
    """
    # If guestpass system is disabled, don't send any responses
    if _is_guestpass_disabled():
        log.debug("Guestpass system is disabled, skipping gift target list response")
        return -1

    client_address = client_obj.ip_port
    total_targets = len(friends_list)

    for friend in friends_list:
        msg = MsgClientGetGiftTargetListResponse(
            client_obj,
            package_id=packageID,
            steamid_friend=friend["steamid"],
            potential_gift_target=friend["index"],
            total_potential_targets=total_targets,
            valid_gift_target=1 if friend["valid"] else 0,
        )
        packet = msg.to_clientmsg()
        cmserver_obj.sendReply(client_obj, packet)

    return -1


def build_updated_guestpast_list_request(client_obj: Client):
    """
    Build the UpdateGuestPassesList response for a client.

    Response format:
        - Header: EResult (4 bytes), countGuestPassesToGive (4 bytes), countGuestPassesToRedeem (4 bytes)
        - Passes to give: [GuestPassMessageObject.serialize() for each pass]
        - Passes to redeem: [GuestPassMessageObject.serialize() for each pass]

    Note: Guest pass vs Gift determination:
        A pass is a Gift if the package ID's billing type (CDR) is not GuestPass (4)
        This only applies to Mid-2007 clients and later!
    """
    packet = CMResponse(eMsgID=EMsg.ClientUpdateGuestPassesList, client_obj=client_obj)

    # If guestpass system is disabled, return empty list
    if _is_guestpass_disabled():
        log.debug("Guestpass system is disabled, returning empty guest pass list")
        packet.data = struct.pack('<III', EResult.OK, 0, 0)
        return packet

    from steam3.Managers.GuestPassManager import GuestPassManager

    # Default to zero counts
    passes_to_give = []
    passes_to_redeem = []

    try:
        # Use GuestPassManager to get passes
        manager = GuestPassManager()
        account_id = client_obj.steamID

        # Get passes owned by user that can be given to others
        passes_to_give = manager.get_passes_to_give(account_id)

        # Get passes sent to user that can be redeemed
        passes_to_redeem = manager.get_passes_to_redeem(account_id)

        log.debug(f"UpdateGuestPassesList for account {account_id}: "
                  f"{len(passes_to_give)} to give, {len(passes_to_redeem)} to redeem")

    except Exception as e:
        log.error(f"Error getting guest passes for account {client_obj.steamID}: {e}")
        passes_to_give = []
        passes_to_redeem = []

    # Build the packet header
    packet.data = struct.pack('<III',
                              EResult.OK,
                              len(passes_to_give),
                              len(passes_to_redeem))

    # Serialize passes to give
    for pass_record in passes_to_give:
        try:
            msg_obj = GuestPassMessageObject.from_db_record(pass_record)
            packet.data += msg_obj.serialize()
        except Exception as e:
            log.warning(f"Error serializing pass to give {pass_record.UniqueID}: {e}")

    # Serialize passes to redeem
    for pass_record in passes_to_redeem:
        try:
            msg_obj = GuestPassMessageObject.from_db_record(pass_record)
            packet.data += msg_obj.serialize()
        except Exception as e:
            log.warning(f"Error serializing pass to redeem {pass_record.UniqueID}: {e}")

    return packet