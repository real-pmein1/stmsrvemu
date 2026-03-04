"""
Inventory handlers for TF2-era item system (2008/2009).

EMsg values:
- 881 (ClientUpdateInvPos): Update item position
- 882 (ClientUpdateInvPosResponse): Response
- 883 (ClientDropItem): Delete/drop an item
- 884 (ClientDropItemResponse): Response
- 885 (ClientLoadItems): Request to load items for an app
- 886 (ClientLoadItemsResponse): Response with item list
- 887 (ClientItemGranted): Notification when item is granted
- 5421 (ClientGetItemBlob): Get item blob data
- 5422 (ClientGetItemBlobResponse): Response with blob data
- 5423 (ClientSetItemBlob): Set item blob data
- 5424 (ClientSetItemBlobResponse): Response
"""

from steam3.ClientManager.client import Client
from steam3.Types.emsg import EMsg
from steam3.Types.steam_types import EResult
from steam3.Types.Objects.PersistentItem import PersistentItem
from steam3.cm_packet_utils import CMPacket, CMResponse
from steam3.messages.MsgClientLoadItems import MsgClientLoadItems
from steam3.messages.responses.MsgClientLoadItemsResponse import MsgClientLoadItemsResponse
from steam3.messages.MsgClientUpdateInvPos import MsgClientUpdateInvPos
from steam3.messages.responses.MsgClientUpdateInvPosResponse import MsgClientUpdateInvPosResponse
from steam3.messages.MsgClientDropItem import MsgClientDropItem
from steam3.messages.responses.MsgClientDropItemResponse import MsgClientDropItemResponse
from steam3.messages.MsgClientGetItemBlob import MsgClientGetItemBlob
from steam3.messages.responses.MsgClientGetItemBlobResponse import MsgClientGetItemBlobResponse
from steam3.messages.MsgClientSetItemBlob import MsgClientSetItemBlob
from steam3.messages.responses.MsgClientSetItemBlobResponse import MsgClientSetItemBlobResponse
from utilities.database import inventory_db


def handle_ClientLoadItems(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle EMsg 885 - ClientLoadItems request.
    Client requests all items for a specific app.
    """
    client_address = client_obj.ip_port
    request = packet.CMRequest
    data = request.data

    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): ClientLoadItems request")

    try:
        msg = MsgClientLoadItems(data)
        cmserver_obj.log.debug(f"LoadItems for app_id={msg.app_id}")

        # Get items from database via client class
        db_items = client_obj.get_inventory_items(msg.app_id)

        # Build response
        response = MsgClientLoadItemsResponse(result=EResult.OK, app_id=msg.app_id)

        for db_item in db_items:
            item = PersistentItem.from_db_model(db_item)
            response.add_item(item)

        cmserver_obj.log.debug(f"Sending {len(response.items)} items for app {msg.app_id}")

        # Build and send response packet
        reply = CMResponse(
            client_obj,
            EMsg.ClientLoadItemsResponse,
            response.serialize()
        )
        client_obj.sendReply(reply)

    except Exception as e:
        cmserver_obj.log.error(f"ClientLoadItems error: {e}")
        # Send error response
        response = MsgClientLoadItemsResponse(result=EResult.Fail)
        reply = CMResponse(
            client_obj,
            EMsg.ClientLoadItemsResponse,
            response.serialize()
        )
        client_obj.sendReply(reply)

    return -1


def handle_ClientUpdateInvPos(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle EMsg 881 - ClientUpdateInvPos request.
    Client requests to update an item's inventory position.
    """
    client_address = client_obj.ip_port
    request = packet.CMRequest
    data = request.data

    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): ClientUpdateInvPos request")

    try:
        msg = MsgClientUpdateInvPos(data)
        cmserver_obj.log.debug(
            f"UpdateInvPos: item_id={msg.item_id}, app_id={msg.app_id}, new_pos={msg.new_position}"
        )

        # Update position via client class
        result = client_obj.update_inventory_position(msg.item_id, msg.app_id, msg.new_position)

        # Build and send response
        response = MsgClientUpdateInvPosResponse(result=result)
        reply = CMResponse(
            client_obj,
            EMsg.ClientUpdateInvPosResponse,
            response.serialize()
        )
        client_obj.sendReply(reply)

    except Exception as e:
        cmserver_obj.log.error(f"ClientUpdateInvPos error: {e}")
        response = MsgClientUpdateInvPosResponse(result=EResult.Fail)
        reply = CMResponse(
            client_obj,
            EMsg.ClientUpdateInvPosResponse,
            response.serialize()
        )
        client_obj.sendReply(reply)

    return -1


def handle_ClientDropItem(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle EMsg 883 - ClientDropItem request.
    Client requests to delete/drop an item.
    """
    client_address = client_obj.ip_port
    request = packet.CMRequest
    data = request.data

    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): ClientDropItem request")

    try:
        msg = MsgClientDropItem(data)
        cmserver_obj.log.debug(f"DropItem: item_id={msg.item_id}, app_id={msg.app_id}")

        # Delete item via client class
        result = client_obj.drop_inventory_item(msg.item_id, msg.app_id)

        # Build and send response
        response = MsgClientDropItemResponse(result=result)
        reply = CMResponse(
            client_obj,
            EMsg.ClientDropItemResponse,
            response.serialize()
        )
        client_obj.sendReply(reply)

    except Exception as e:
        cmserver_obj.log.error(f"ClientDropItem error: {e}")
        response = MsgClientDropItemResponse(result=EResult.Fail)
        reply = CMResponse(
            client_obj,
            EMsg.ClientDropItemResponse,
            response.serialize()
        )
        client_obj.sendReply(reply)

    return -1


def handle_ClientGetItemBlob(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle EMsg 5421 - ClientGetItemBlob request.
    Client requests blob data attached to an item.
    """
    client_address = client_obj.ip_port
    request = packet.CMRequest
    data = request.data

    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): ClientGetItemBlob request")

    try:
        msg = MsgClientGetItemBlob(data)
        cmserver_obj.log.debug(f"GetItemBlob: item_id={msg.item_id}, app_id={msg.app_id}")

        # Get blob data from database
        blob_data = inventory_db.get_item_blob(msg.item_id)

        # Build and send response
        response = MsgClientGetItemBlobResponse(
            result=EResult.OK,
            item_id=msg.item_id,
            blob_data=blob_data
        )
        reply = CMResponse(
            client_obj,
            EMsg.ClientGetItemBlobResponse,
            response.serialize()
        )
        client_obj.sendReply(reply)

    except Exception as e:
        cmserver_obj.log.error(f"ClientGetItemBlob error: {e}")
        response = MsgClientGetItemBlobResponse(result=EResult.Fail, item_id=0, blob_data=b'')
        reply = CMResponse(
            client_obj,
            EMsg.ClientGetItemBlobResponse,
            response.serialize()
        )
        client_obj.sendReply(reply)

    return -1


def handle_ClientSetItemBlob(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
    Handle EMsg 5423 - ClientSetItemBlob request.
    Client requests to set blob data on an item.
    """
    client_address = client_obj.ip_port
    request = packet.CMRequest
    data = request.data

    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): ClientSetItemBlob request")

    try:
        msg = MsgClientSetItemBlob(data)
        cmserver_obj.log.debug(f"SetItemBlob: item_id={msg.item_id}, app_id={msg.app_id}, size={len(msg.blob_data)}")

        # Set blob data in database
        success = inventory_db.set_item_blob(msg.item_id, msg.blob_data)

        result = EResult.OK if success else EResult.Fail

        # Build and send response
        response = MsgClientSetItemBlobResponse(
            result=result,
            item_id=msg.item_id
        )
        reply = CMResponse(
            client_obj,
            EMsg.ClientSetItemBlobResponse,
            response.serialize()
        )
        client_obj.sendReply(reply)

    except Exception as e:
        cmserver_obj.log.error(f"ClientSetItemBlob error: {e}")
        response = MsgClientSetItemBlobResponse(result=EResult.Fail, item_id=0)
        reply = CMResponse(
            client_obj,
            EMsg.ClientSetItemBlobResponse,
            response.serialize()
        )
        client_obj.sendReply(reply)

    return -1
