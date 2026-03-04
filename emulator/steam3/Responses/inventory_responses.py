"""
Inventory response builder functions for TF2-era item system (2008/2009).

These functions create CMResponse packets for inventory operations.
"""
from typing import List

from steam3.ClientManager.client import Client
from steam3.Types.emsg import EMsg
from steam3.Types.steam_types import EResult
from steam3.Types.Objects.PersistentItem import PersistentItem
from steam3.cm_packet_utils import CMResponse
from steam3.messages.responses.MsgClientLoadItemsResponse import MsgClientLoadItemsResponse
from steam3.messages.responses.MsgClientUpdateInvPosResponse import MsgClientUpdateInvPosResponse
from steam3.messages.responses.MsgClientDropItemResponse import MsgClientDropItemResponse
from steam3.messages.responses.MsgClientItemGranted import MsgClientItemGranted


def build_LoadItemsResponse(client_obj: Client, result: int, items: List[PersistentItem] = None) -> CMResponse:
    """
    Build a ClientLoadItemsResponse packet (EMsg 886).

    Args:
        client_obj: The client object
        result: EResult code
        items: List of PersistentItem objects to send

    Returns:
        CMResponse packet ready to send
    """
    response = MsgClientLoadItemsResponse(client_obj=client_obj, result=result)

    if items:
        for item in items:
            response.add_item(item)

    packet = CMResponse(eMsgID=EMsg.ClientLoadItemsResponse, client_obj=client_obj)
    packet.data = response.serialize()
    return packet


def build_UpdateInvPosResponse(client_obj: Client, result: int) -> CMResponse:
    """
    Build a ClientUpdateInvPosResponse packet (EMsg 882).

    Args:
        client_obj: The client object
        result: EResult code

    Returns:
        CMResponse packet ready to send
    """
    response = MsgClientUpdateInvPosResponse(client_obj=client_obj, result=result)

    packet = CMResponse(eMsgID=EMsg.ClientUpdateInvPosResponse, client_obj=client_obj)
    packet.data = response.serialize()
    return packet


def build_DropItemResponse(client_obj: Client, result: int) -> CMResponse:
    """
    Build a ClientDropItemResponse packet (EMsg 884).

    Args:
        client_obj: The client object
        result: EResult code

    Returns:
        CMResponse packet ready to send
    """
    response = MsgClientDropItemResponse(client_obj=client_obj, result=result)

    packet = CMResponse(eMsgID=EMsg.ClientDropItemResponse, client_obj=client_obj)
    packet.data = response.serialize()
    return packet


def build_ItemGrantedNotification(client_obj: Client, item: PersistentItem) -> CMResponse:
    """
    Build a ClientItemGranted notification packet (EMsg 887).
    Used to notify the client when they receive a new item.

    Args:
        client_obj: The client object
        item: The PersistentItem that was granted

    Returns:
        CMResponse packet ready to send
    """
    response = MsgClientItemGranted(client_obj=client_obj, item=item)

    packet = CMResponse(eMsgID=EMsg.ClientItemGranted, client_obj=client_obj)
    packet.data = response.serialize()
    return packet
