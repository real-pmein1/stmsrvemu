"""
Clan Handlers - Handle clan-related client messages

Implements:
- ClientInviteUserToClan (744): Invite user to clan
- ClientAcknowledgeClanInvite (745): Accept/reject clan invitation
"""

import logging
from steam3.Types.steamid import SteamID
from steam3.Types.steam_types import EResult
from steam3.Types.chat_types import ChatRelationship
from steam3.cm_packet_utils import CMPacket
from steam3.ClientManager.client import Client
from steam3.messages.MsgClientInviteUserToClan import MsgClientInviteUserToClan
from steam3.messages.MsgClientAcknowledgeClanInvite import MsgClientAcknowledgeClanInvite
from steam3.Responses.clan_responses import (
    build_ClanState_response, send_clan_invite_notification
)

log = logging.getLogger("ClanHandlers")


def get_clan_manager():
    """Get the global clan manager instance from steam3"""
    import steam3
    return steam3.clan_manager


def handle_InviteUserToClan(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle ClientInviteUserToClan packet (EMsg 744)

    Client requests to invite another user to a clan.
    Server validates permissions and adds invitee with 'invited' relationship.
    """
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received ClientInviteUserToClan")

    try:
        # Parse the request
        msg = MsgClientInviteUserToClan(client_obj, request.data)

        cmserver_obj.log.debug(f"InviteUserToClan: clan={msg.clan_steam_id:016x}, "
                              f"inviter={int(client_obj.steamID):016x}, "
                              f"invitee={msg.invitee_steam_id:016x}")

        # Get clan manager
        clan_manager = get_clan_manager()

        # Perform invitation
        result = clan_manager.invite_to_clan(
            msg.clan_steam_id,
            int(client_obj.steamID),  # inviter
            msg.invitee_steam_id       # invitee
        )

        if result == EResult.OK:
            cmserver_obj.log.info(f"User {msg.invitee_steam_id:016x} invited to clan "
                                 f"{msg.clan_steam_id:016x} by {int(client_obj.steamID):016x}")

            # Send clan state update to inviter (implicit success confirmation)
            clan = clan_manager.get_clan(msg.clan_steam_id)
            if clan:
                response = build_ClanState_response(
                    client_obj, clan, flags=0x02  # Send user counts update
                )

                # Send invitation notification to invitee if online
                send_clan_invite_notification(
                    cmserver_obj, msg.clan_steam_id, msg.invitee_steam_id,
                    int(client_obj.steamID)
                )

                return response
        else:
            cmserver_obj.log.warning(f"Failed to invite user to clan: {result}")
            # Could send an error response here, but Steam client handles implicitly
            # by not receiving the clan state update

    except Exception as e:
        cmserver_obj.log.error(f"Error handling ClientInviteUserToClan: {e}", exc_info=True)

    return -1


def handle_AcknowledgeClanInvite(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle ClientAcknowledgeClanInvite packet (EMsg 745)

    Client accepts or rejects a clan invitation.
    If accepted, promote user from 'invited' to 'member' status.
    """
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received ClientAcknowledgeClanInvite")

    try:
        # Parse the request
        msg = MsgClientAcknowledgeClanInvite(client_obj, request.data)

        action_str = "ACCEPT" if msg.accept else "REJECT"
        cmserver_obj.log.debug(f"AcknowledgeClanInvite: clan={msg.clan_steam_id:016x}, "
                              f"user={int(client_obj.steamID):016x}, action={action_str}")

        # Get clan manager
        clan_manager = get_clan_manager()
        clan = clan_manager.get_clan(msg.clan_steam_id)

        if not clan:
            cmserver_obj.log.warning(f"Clan {msg.clan_steam_id:016x} not found")
            return -1

        if msg.accept:
            # Accept invitation - join the clan
            result = clan_manager.join_clan(msg.clan_steam_id, int(client_obj.steamID))

            if result == EResult.OK:
                cmserver_obj.log.info(f"User {int(client_obj.steamID):016x} joined clan "
                                     f"{msg.clan_steam_id:016x}")

                # Send full clan state to new member
                response = build_ClanState_response(
                    client_obj, clan, flags=0x0F  # Send all clan data
                )

                # Broadcast member count update to all clan members
                _broadcast_clan_update_to_members(cmserver_obj, clan, clan_manager)

                return response
            else:
                cmserver_obj.log.warning(f"Failed to join clan: {result}")
        else:
            # Reject invitation - remove from invited list
            cmserver_obj.log.info(f"User {int(client_obj.steamID):016x} rejected invitation to clan "
                                 f"{msg.clan_steam_id:016x}")

            # Simply remove the user from the clan members (invited status)
            clan.remove_member(int(client_obj.steamID))

            # Update database
            clan_id = int(SteamID.from_raw(msg.clan_steam_id).get_accountID())
            if clan_manager.database:
                clan_manager.database.set_clan_membership(
                    clan_id, int(client_obj.steamID),
                    ChatRelationship.none, 0
                )

    except Exception as e:
        cmserver_obj.log.error(f"Error handling ClientAcknowledgeClanInvite: {e}", exc_info=True)

    return -1


def _broadcast_clan_update_to_members(cmserver_obj, clan, clan_manager):
    """
    Broadcast clan state update to all clan members.
    Used when member count or other clan data changes.
    """
    from steam3.ClientManager import Client_Manager

    for member_steam_id, member in clan.members.items():
        if member.relationship == ChatRelationship.member:
            # Find online client
            target_client = Client_Manager.get_client_by_steamid(member_steam_id)
            if target_client:
                try:
                    response = build_ClanState_response(
                        target_client, clan, flags=0x02  # Send user counts
                    )
                    target_client.sendReply([response])
                except Exception as e:
                    log.warning(f"Failed to send clan update to {member_steam_id:016x}: {e}")
