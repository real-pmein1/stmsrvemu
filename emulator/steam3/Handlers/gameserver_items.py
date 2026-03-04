"""
Gameserver item and group status handlers.

Handlers for gameserver messages related to:
- User group status checking
- Item loading, granting, creating, and deleting
- Item quantity updates
- Item blob data get/set
"""
import struct
from steam3.ClientManager.client import Client
from steam3.cm_packet_utils import CMPacket
from steam3.Responses.gameserver_item_responses import (
    build_GSGetUserGroupStatusResponse,
    build_GSLoadItemsResponse,
    build_GSGrantItemResponse,
    build_GSCreateItemResponse,
    build_GSDeleteTempItemResponse,
    build_GSDeleteAllTempItemsResponse,
    build_GSUpdateItemQuantityResponse,
    build_GSGetItemBlobResponse,
    build_GSSetItemBlobResponse,
)
from steam3.messages.MsgGSGetUserGroupStatus import MsgGSGetUserGroupStatus
from steam3.messages.MsgGSLoadItems import MsgGSLoadItems
from steam3.messages.MsgGSGrantItem import MsgGSGrantItem
from steam3.messages.MsgGSCreateItem import MsgGSCreateItem
from steam3.messages.MsgGSDeleteTempItem import MsgGSDeleteTempItem
from steam3.messages.MsgGSDeleteAllTempItems import MsgGSDeleteAllTempItems
from steam3.messages.MsgGSUpdateItemQuantity import MsgGSUpdateItemQuantity
from steam3.messages.MsgGSGetItemBlob import MsgGSGetItemBlob
from steam3.messages.MsgGSSetItemBlob import MsgGSSetItemBlob
from steam3.Types.Objects.PersistentItem import PersistentItem
from steam3.Managers.ItemSchemaManager import get_item_schema_manager
from utilities.database import inventory_db


def handle_GS_GetUserGroupStatus(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle GSGetUserGroupStatus request (EMsg 920).

    Checks if a user is a member of a specified Steam group.
    Returns the user's clan relationship and rank.
    """
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received GSGetUserGroupStatus")

    try:
        msg = MsgGSGetUserGroupStatus()
        msg.deserialize(request.data)

        cmserver_obj.log.debug(
            f"Group status check:\n"
            f"  User SteamID: {msg.steam_id_user}\n"
            f"  Group SteamID: {msg.steam_id_group}"
        )

        # Look up group membership from database
        clan_relationship, clan_rank = inventory_db.get_user_group_status(
            msg.steam_id_user,
            msg.steam_id_group
        )

        return build_GSGetUserGroupStatusResponse(
            client_obj,
            msg.steam_id_user,
            msg.steam_id_group,
            clan_relationship,
            clan_rank
        )

    except Exception as e:
        cmserver_obj.log.error(f"GSGetUserGroupStatus error: {e}")
        return -1


def handle_GS_LoadItems(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle GSLoadItems request (EMsg 916).

    Loads all items for a specified user from the database.
    Returns a list of PersistentItem objects.
    """
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received GSLoadItems")

    try:
        msg = MsgGSLoadItems()
        msg.deserialize(request.data)

        cmserver_obj.log.debug(f"Loading items for SteamID: {msg.steam_id}")

        # Load items from database
        items = []
        try:
            db_items = inventory_db.get_user_items(msg.steam_id, client_obj.appID)
            for db_item in db_items:
                items.append(PersistentItem.from_db_model(db_item))
            result = 1  # EResult_OK
        except Exception as e:
            cmserver_obj.log.error(f"Failed to load items: {e}")
            result = 2  # EResult_Fail

        cmserver_obj.log.debug(f"Loaded {len(items)} items for user")

        return build_GSLoadItemsResponse(client_obj, result, items)

    except Exception as e:
        cmserver_obj.log.error(f"GSLoadItems error: {e}")
        return build_GSLoadItemsResponse(client_obj, 2, [])


def handle_GS_GrantItem(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle GSGrantItem request (EMsg 924).

    Grants an existing item to a user.
    """
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received GSGrantItem")

    try:
        msg = MsgGSGrantItem()
        msg.deserialize(request.data)

        cmserver_obj.log.debug(
            f"Grant item request:\n"
            f"  Item ID: {msg.item_id}\n"
            f"  Target SteamID: {msg.steam_id_target}"
        )

        # Grant the item in the database
        success = inventory_db.grant_item(msg.item_id, msg.steam_id_target)

        if success:
            result = 1  # EResult_OK
            # Load the updated item to return in response
            db_item = inventory_db.get_item_by_id(msg.item_id)
            item = PersistentItem.from_db_model(db_item) if db_item else None
        else:
            result = 2  # EResult_Fail
            item = None

        return build_GSGrantItemResponse(
            client_obj,
            result,
            msg.steam_id_target,
            msg.item_id,
            item
        )

    except Exception as e:
        cmserver_obj.log.error(f"GSGrantItem error: {e}")
        return build_GSGrantItemResponse(client_obj, 2, 0, 0)


def handle_GS_CreateItem(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle GSCreateItem request (EMsg 912).

    Creates a new item for a user based on the definition index.
    Validates the definition index against the item schema.
    """
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received GSCreateItem")

    try:
        msg = MsgGSCreateItem()
        msg.deserialize(request.data)

        cmserver_obj.log.debug(
            f"Create item request:\n"
            f"  SteamID: {msg.steam_id}\n"
            f"  App ID: {msg.app_id}\n"
            f"  Definition Index: {msg.definition_index}\n"
            f"  Quality: {msg.quality}"
        )

        # Validate the definition index against the item schema
        schema_manager = get_item_schema_manager()
        if not schema_manager.is_valid_defindex(msg.app_id, msg.definition_index):
            cmserver_obj.log.warning(
                f"Invalid defindex {msg.definition_index} for app {msg.app_id}"
            )
            # Still allow creation for games without schemas or unknown items
            # Just log a warning

        # Get item info from schema if available
        item_def = schema_manager.get_item_definition(msg.app_id, msg.definition_index)
        if item_def:
            item_name = item_def.get('item_name', item_def.get('name', 'Unknown'))
            cmserver_obj.log.debug(f"Creating item: {item_name}")

        # Create the item in the database
        item_id, db_item = inventory_db.create_item(
            steam_id=msg.steam_id,
            app_id=msg.app_id,
            definition_index=msg.definition_index,
            quality=msg.quality,
            item_level=getattr(msg, 'item_level', 1),
            inventory_token=getattr(msg, 'inventory_token', 0),
            quantity=getattr(msg, 'quantity', 1),
            attributes=getattr(msg, 'attributes', None)
        )

        if item_id and db_item:
            result = 1  # EResult_OK
            item = PersistentItem.from_db_model(db_item)
        else:
            result = 2  # EResult_Fail
            item_id = 0
            item = None

        return build_GSCreateItemResponse(
            client_obj,
            result,
            msg.steam_id,
            item_id,
            item
        )

    except Exception as e:
        cmserver_obj.log.error(f"GSCreateItem error: {e}")
        return build_GSCreateItemResponse(client_obj, 2, 0, 0)


def handle_GS_DeleteTempItem(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle GSDeleteTempItem request (EMsg 926).

    Deletes a temporary item for a user.
    """
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received GSDeleteTempItem")

    try:
        msg = MsgGSDeleteTempItem()
        msg.deserialize(request.data)

        cmserver_obj.log.debug(
            f"Delete temp item request:\n"
            f"  SteamID: {msg.steam_id}\n"
            f"  Item ID: {msg.item_id}"
        )

        # Delete the item from the database
        success = inventory_db.delete_item(msg.item_id)
        result = 1 if success else 2  # EResult_OK or EResult_Fail

        return build_GSDeleteTempItemResponse(
            client_obj,
            result,
            msg.steam_id,
            msg.item_id
        )

    except Exception as e:
        cmserver_obj.log.error(f"GSDeleteTempItem error: {e}")
        return build_GSDeleteTempItemResponse(client_obj, 2, 0, 0)


def handle_GS_DeleteAllTempItems(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle GSDeleteAllTempItems request (EMsg 928).

    Deletes all temporary items for a user.
    """
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received GSDeleteAllTempItems")

    try:
        msg = MsgGSDeleteAllTempItems()
        msg.deserialize(request.data)

        cmserver_obj.log.debug(f"Delete all temp items for SteamID: {msg.steam_id}")

        # Delete all temporary items from the database
        deleted_count = inventory_db.delete_temp_items(msg.steam_id, client_obj.appID)
        result = 1  # EResult_OK (even if 0 items deleted)

        return build_GSDeleteAllTempItemsResponse(
            client_obj,
            result,
            msg.steam_id,
            deleted_count
        )

    except Exception as e:
        cmserver_obj.log.error(f"GSDeleteAllTempItems error: {e}")
        return build_GSDeleteAllTempItemsResponse(client_obj, 2, 0, 0)


def handle_GS_UpdateItemQuantity(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle GSUpdateItemQuantity request (EMsg 931).

    Updates the quantity of an item (for consumables, stackable items, etc).
    """
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received GSUpdateItemQuantity")

    try:
        msg = MsgGSUpdateItemQuantity()
        msg.deserialize(request.data)

        cmserver_obj.log.debug(
            f"Update item quantity request:\n"
            f"  Item ID: {msg.item_id}\n"
            f"  Owner SteamID: {msg.steam_id_owner}\n"
            f"  App ID: {msg.app_id}\n"
            f"  New Quantity: {msg.new_quantity}"
        )

        # Update the item quantity in the database
        success = inventory_db.update_item_quantity(msg.item_id, msg.new_quantity)

        if success:
            result = 1  # EResult_OK
        else:
            result = 2  # EResult_Fail

        return build_GSUpdateItemQuantityResponse(
            client_obj,
            result,
            msg.item_id,
            msg.new_quantity
        )

    except Exception as e:
        cmserver_obj.log.error(f"GSUpdateItemQuantity error: {e}")
        return build_GSUpdateItemQuantityResponse(client_obj, 2, 0, 0)


def handle_GS_GetItemBlob(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle GSGetItemBlob request.

    Gets the blob data attached to an item (up to 1024 bytes of custom data).
    """
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received GSGetItemBlob")

    try:
        msg = MsgGSGetItemBlob()
        msg.deserialize(request.data)

        cmserver_obj.log.debug(f"Get item blob for item ID: {msg.item_id}")

        # Get the blob data from the database
        blob_data = inventory_db.get_item_blob(msg.item_id)
        result = 1  # EResult_OK

        return build_GSGetItemBlobResponse(
            client_obj,
            result,
            msg.item_id,
            blob_data
        )

    except Exception as e:
        cmserver_obj.log.error(f"GSGetItemBlob error: {e}")
        return build_GSGetItemBlobResponse(client_obj, 2, 0, b'')


def handle_GS_SetItemBlob(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle GSSetItemBlob request.

    Sets the blob data attached to an item (up to 1024 bytes of custom data).
    """
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received GSSetItemBlob")

    try:
        msg = MsgGSSetItemBlob()
        msg.deserialize(request.data)

        cmserver_obj.log.debug(f"Set item blob for item ID: {msg.item_id}, size: {len(msg.blob_data)}")

        # Set the blob data in the database
        success = inventory_db.set_item_blob(msg.item_id, msg.blob_data)

        if success:
            result = 1  # EResult_OK
        else:
            result = 2  # EResult_Fail

        return build_GSSetItemBlobResponse(
            client_obj,
            result,
            msg.item_id
        )

    except Exception as e:
        cmserver_obj.log.error(f"GSSetItemBlob error: {e}")
        return build_GSSetItemBlobResponse(client_obj, 2, 0)
