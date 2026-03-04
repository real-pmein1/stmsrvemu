"""
Clan Response Builders - Helper functions for building clan-related responses

Implements response builders for:
- ClientClanState (822): Clan state updates
- Clan invitation notifications
"""

import logging
import struct
from io import BytesIO
from steam3.Types.steamid import SteamID
from steam3.Types.emsg import EMsg
from steam3.Types.steam_types import EType, EUniverse, EInstanceFlag
from steam3.Types.community_types import ClanStateFlags, ClanAccountFlags
from steam3.messages.MsgClientClanState import MsgClientClanState
from steam3.cm_packet_utils import CMResponse

log = logging.getLogger("ClanResponses")


def build_ClanState_from_db(client_obj, clan_registry, member_count=0, online_count=0, flags=None):
    """
    Build ClientClanState response from database models.

    Args:
        client_obj: Client object
        clan_registry: CommunityClanRegistry database object
        member_count: Total number of members
        online_count: Number of online members
        flags: ClanStateFlags bitfield (default: name + userCounts)

    Returns:
        CMResponse object with serialized clan state
    """
    try:
        if flags is None:
            flags = ClanStateFlags.name | ClanStateFlags.userCounts

        msg = MsgClientClanState()

        # Build clan SteamID (Type=CLAN, Universe=PUBLIC)
        clan_steamid = SteamID.create_clan_id(clan_registry.UniqueID, EUniverse.PUBLIC)
        msg.steam_id_clan = int(clan_steamid)
        msg.clan_state_flags = flags

        # Set account flags
        is_public = clan_registry.clan_status == 1 if hasattr(clan_registry, 'clan_status') else True
        msg.m_bPublic = is_public
        msg.m_bLarge = member_count >= 100  # Threshold for "large" clan
        msg.m_bLocked = not is_public
        msg.m_bDisabled = False

        # Include name info if requested
        if flags & ClanStateFlags.name:
            msg.name_info = {
                "clan_name": clan_registry.clan_name if hasattr(clan_registry, 'clan_name') else "",
                "avatar_sha": b"\x00" * 20  # No avatar for now
            }

        # Include user counts if requested
        if flags & ClanStateFlags.userCounts:
            msg.user_counts = {
                "members": member_count,
                "online": online_count,
                "in_chat": 0,
                "in_game": 0
            }

        # Include events if requested (empty for now)
        if flags & ClanStateFlags.events:
            msg.events = []

        # Include announcements if requested (empty for now)
        if flags & ClanStateFlags.announcements:
            msg.announcements = []

        # Serialize and build response
        serialized_data = msg.serialize()
        response = CMResponse(eMsgID=EMsg.ClientClanState, client_obj=client_obj)
        response.data = serialized_data
        response.length = len(serialized_data)

        log.debug(f"Built ClanState for clan {clan_registry.UniqueID} ({clan_registry.clan_name}): "
                  f"members={member_count}, online={online_count}")

        return response

    except Exception as e:
        log.error(f"Error building ClanState from DB: {e}", exc_info=True)
        return None


def build_ClanState_response(client_obj, clan, flags=0x0F):
    """
    Build ClientClanState response message (EMsg 822)

    Args:
        client_obj: Client object
        clan: Clan object from ClanManager
        flags: ClanStateFlags bitfield (default 0x0F = all data)

    Returns:
        CMResponse object with serialized clan state
    """
    try:
        msg = MsgClientClanState()

        # Set basic clan info
        msg.steam_id_clan = clan.steam_id
        msg.clan_state_flags = flags

        # Set account flags
        msg.m_bPublic = clan.is_public
        msg.m_bLarge = clan.is_large_clan()
        msg.m_bLocked = not clan.is_public  # Private clans are "locked"
        msg.m_bDisabled = False  # Could add disabled status to Clan class

        # Include name info if requested
        if flags & ClanStateFlags.name:
            msg.name_info = {
                "clan_name": clan.name,
                "avatar_id": ""  # Could add avatar support to Clan class
            }

        # Include user counts if requested
        if flags & ClanStateFlags.userCounts:
            online_count = _count_online_members(clan)
            msg.user_counts = {
                "members": clan.get_member_count(),
                "online": online_count,
                "in_chat": 0,  # Would need to track clan chat separately
                "in_game": 0   # Would need to track game status
            }

        # Include announcements if requested
        if flags & ClanStateFlags.announcements:
            # Could populate from clan.events if is_announcement=True
            msg.announcements = []

        # Include events if requested
        if flags & ClanStateFlags.events:
            # Populate from clan.events
            msg.events = []
            for event_id, event in clan.events.items():
                if not event.is_announcement:  # Only include events, not announcements
                    msg.events.append({
                        "event_id": event.event_id,
                        "event_time": int(event.start_time.timestamp()),
                        "headline": event.name,
                        "game_id": event.game_id,
                        "just_posted": False  # Could add timestamp comparison
                    })

        # Serialize and build response
        serialized_data = msg.serialize()
        response = CMResponse(eMsgID=EMsg.ClientClanState, client_obj=client_obj)
        response.data = serialized_data
        response.length = len(serialized_data)

        return response

    except Exception as e:
        log.error(f"Error building ClanState response: {e}", exc_info=True)
        return None


def send_clan_invite_notification(cmserver_obj, clan_steam_id, invitee_steam_id, inviter_steam_id):
    """
    Send clan invitation notification to invitee via FriendsList update.

    Steam protocol sends clan invitations through the friends list system.
    The invitee sees the invitation in their friends list.

    Args:
        cmserver_obj: CM server object
        clan_steam_id: Steam ID of the clan
        invitee_steam_id: Steam ID of user being invited
        inviter_steam_id: Steam ID of user who sent the invitation
    """
    try:
        from steam3.ClientManager import Client_Manager

        # Find invitee client
        invitee_client = Client_Manager.get_client_by_steamid(invitee_steam_id)

        if invitee_client:
            # Invitee is online - send friends list update with clan relationship
            from steam3.Responses.friends_responses import build_friends_list_response

            # The FriendsList response will include the clan with 'invited' relationship
            # This is how the Steam client knows about the invitation
            response = build_friends_list_response(invitee_client)

            invitee_client.sendReply([response])

            log.info(f"Sent clan invite notification to {invitee_steam_id:016x} for clan {clan_steam_id:016x}")
        else:
            # Invitee is offline - invitation will be delivered when they login
            # The friends list handler will pick up the invitation from the database
            log.debug(f"Invitee {invitee_steam_id:016x} is offline, invitation will be delivered at login")

    except Exception as e:
        log.error(f"Error sending clan invite notification: {e}", exc_info=True)


def _count_online_members(clan):
    """
    Count how many clan members are currently online.

    Args:
        clan: Clan object

    Returns:
        int: Number of online members
    """
    from steam3.ClientManager import Client_Manager
    from steam3.Types.chat_types import ChatRelationship

    online_count = 0
    for member_steam_id, member in clan.members.items():
        if member.relationship == ChatRelationship.member:
            # Check if user is online
            client = Client_Manager.get_client_by_steamid(member_steam_id)
            if client:
                online_count += 1

    return online_count


def build_ClanInvite_response(client_obj, clan_steam_id, inviter_steam_id):
    """
    Build a clan invitation message (sent as part of friends list).

    Note: In the actual Steam protocol, clan invitations are delivered through
    the FriendsList message (EMsg 767), not as a separate message type.

    This function is provided for potential future use or alternate implementations.

    Args:
        client_obj: Client object receiving the invitation
        clan_steam_id: Steam ID of the clan
        inviter_steam_id: Steam ID of the user who sent the invitation

    Returns:
        Dict with invitation details (for use in FriendsList)
    """
    return {
        "steam_id": clan_steam_id,
        "relationship": 2,  # ChatRelationship.invited
        "inviter_id": inviter_steam_id
    }
