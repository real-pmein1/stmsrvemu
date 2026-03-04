"""
Gameserver item-related response builders.

These functions build response packets for gameserver item operations
including loading, granting, creating, deleting, quantity updates, and blob data.
"""
import struct
from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse
from steam3.messages.MsgGSKick import MsgGSKick
from steam3.messages.responses.MsgGSGetUserGroupStatusResponse import MsgGSGetUserGroupStatusResponse
from steam3.messages.responses.MsgGSLoadItemsResponse import MsgGSLoadItemsResponse
from steam3.messages.responses.MsgGSGrantItemResponse import MsgGSGrantItemResponse
from steam3.messages.responses.MsgGSCreateItemResponse import MsgGSCreateItemResponse
from steam3.messages.responses.MsgGSDeleteTempItemResponse import MsgGSDeleteTempItemResponse
from steam3.messages.responses.MsgGSDeleteAllTempItemsResponse import MsgGSDeleteAllTempItemsResponse
from steam3.messages.responses.MsgGSUpdateItemQuantityResponse import MsgGSUpdateItemQuantityResponse
from steam3.messages.responses.MsgGSGetItemBlobResponse import MsgGSGetItemBlobResponse
from steam3.messages.responses.MsgGSSetItemBlobResponse import MsgGSSetItemBlobResponse
from steam3.messages.MsgGSItemDropped import MsgGSItemDropped
from steam3.messages.MsgGSItemUpdated import MsgGSItemUpdated
from steam3.messages.MsgGSItemGranted import MsgGSItemGranted


def build_GSKick(client_obj, steam_id, deny_reason):
    """Build a GSKick response to kick a player from the game server."""
    packet = CMResponse(eMsgID=EMsg.GSKick, client_obj=client_obj)
    msg = MsgGSKick(steam_id=steam_id, deny_reason=deny_reason)
    packet.data = msg.serialize()
    packet.length = len(packet.data)
    return packet


def build_GSGetUserGroupStatusResponse(client_obj, steam_id_user, steam_id_group, clan_relationship, clan_rank):
    """Build a response for GSGetUserGroupStatus request."""
    packet = CMResponse(eMsgID=EMsg.GSGetUserGroupStatusResponse, client_obj=client_obj)
    msg = MsgGSGetUserGroupStatusResponse(
        steam_id_user=steam_id_user,
        steam_id_group=steam_id_group,
        clan_relationship=clan_relationship,
        clan_rank=clan_rank
    )
    packet.data = msg.serialize()
    packet.length = len(packet.data)
    return packet


def build_GSLoadItemsResponse(client_obj, result, items=None):
    """Build a response for GSLoadItems request."""
    packet = CMResponse(eMsgID=EMsg.GSLoadItemsResponse, client_obj=client_obj)
    msg = MsgGSLoadItemsResponse(result=result)
    if items:
        for item in items:
            msg.add_item(item)
    packet.data = msg.serialize()
    packet.length = len(packet.data)
    return packet


def build_GSGrantItemResponse(client_obj, result, steam_id_target, item_id=0, item=None):
    """Build a response for GSGrantItem request."""
    packet = CMResponse(eMsgID=EMsg.GSGrantItemResponse, client_obj=client_obj)
    msg = MsgGSGrantItemResponse(
        result=result,
        steam_id_target=steam_id_target,
        item_id=item_id,
        item=item
    )
    packet.data = msg.serialize()
    packet.length = len(packet.data)
    return packet


def build_GSCreateItemResponse(client_obj, result, steam_id, item_id=0, item=None):
    """Build a response for GSCreateItem request."""
    packet = CMResponse(eMsgID=EMsg.GSCreateItemResponse, client_obj=client_obj)
    msg = MsgGSCreateItemResponse(
        result=result,
        steam_id=steam_id,
        item_id=item_id,
        item=item
    )
    packet.data = msg.serialize()
    packet.length = len(packet.data)
    return packet


def build_GSDeleteTempItemResponse(client_obj, result, steam_id, item_id):
    """Build a response for GSDeleteTempItem request."""
    packet = CMResponse(eMsgID=EMsg.GSDeleteTempItemResponse, client_obj=client_obj)
    msg = MsgGSDeleteTempItemResponse(
        result=result,
        steam_id=steam_id,
        item_id=item_id
    )
    packet.data = msg.serialize()
    packet.length = len(packet.data)
    return packet


def build_GSDeleteAllTempItemsResponse(client_obj, result, steam_id, deleted_count=0):
    """Build a response for GSDeleteAllTempItems request."""
    packet = CMResponse(eMsgID=EMsg.GSDeleteAllTempItemsResponse, client_obj=client_obj)
    msg = MsgGSDeleteAllTempItemsResponse(
        result=result,
        steam_id=steam_id,
        deleted_count=deleted_count
    )
    packet.data = msg.serialize()
    packet.length = len(packet.data)
    return packet


def build_GSItemDropped(client_obj, steam_id, item_id):
    """Build a GSItemDropped notification to inform game server that an item was dropped."""
    packet = CMResponse(eMsgID=EMsg.GSItemDropped, client_obj=client_obj)
    msg = MsgGSItemDropped(steam_id=steam_id, item_id=item_id)
    packet.data = msg.serialize()
    packet.length = len(packet.data)
    return packet


def build_GSItemUpdated(client_obj, steam_id, item_id, new_position):
    """Build a GSItemUpdated notification to inform game server that an item was updated."""
    packet = CMResponse(eMsgID=EMsg.GSItemUpdated, client_obj=client_obj)
    msg = MsgGSItemUpdated(steam_id=steam_id, item_id=item_id, new_position=new_position)
    packet.data = msg.serialize()
    packet.length = len(packet.data)
    return packet


def build_GSItemGranted(client_obj, item):
    """Build a GSItemGranted notification to inform game server that an item was granted."""
    packet = CMResponse(eMsgID=EMsg.GSItemGranted, client_obj=client_obj)
    msg = MsgGSItemGranted(item=item)
    packet.data = msg.serialize()
    packet.length = len(packet.data)
    return packet


def build_GSUpdateItemQuantityResponse(client_obj, result, item_id, new_quantity):
    """Build a response for GSUpdateItemQuantity request."""
    packet = CMResponse(eMsgID=EMsg.GSUpdateItemQuantityResponse, client_obj=client_obj)
    msg = MsgGSUpdateItemQuantityResponse(
        result=result,
        item_id=item_id,
        new_quantity=new_quantity
    )
    packet.data = msg.serialize()
    packet.length = len(packet.data)
    return packet


def build_GSGetItemBlobResponse(client_obj, result, item_id, blob_data=b''):
    """Build a response for GSGetItemBlob request."""
    packet = CMResponse(eMsgID=EMsg.GSGetItemBlobResponse, client_obj=client_obj)
    msg = MsgGSGetItemBlobResponse(
        result=result,
        item_id=item_id,
        blob_data=blob_data
    )
    packet.data = msg.serialize()
    packet.length = len(packet.data)
    return packet


def build_GSSetItemBlobResponse(client_obj, result, item_id):
    """Build a response for GSSetItemBlob request."""
    packet = CMResponse(eMsgID=EMsg.GSSetItemBlobResponse, client_obj=client_obj)
    msg = MsgGSSetItemBlobResponse(
        result=result,
        item_id=item_id
    )
    packet.data = msg.serialize()
    packet.length = len(packet.data)
    return packet
