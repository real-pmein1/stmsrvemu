from io import BytesIO
from steam3.messages.responses.MsgClientGetLobbyListResponse import MsgClientGetLobbyListResponse
from steam3.messages.responses.MsgClientGetLobbyMetadataResponse import MsgClientGetLobbyMetadataResponse
from steam3.Types.keyvaluesystem import KeyValuesSystem, KVS_TYPE_STRING


def serialize_metadata_to_keyvalues(metadata_dict: dict) -> bytes:
    """
    Serialize a metadata dictionary to KeyValues binary format.

    The 2008 Steam client expects lobby metadata in KeyValues binary format:
    - Type byte + null-terminated key + value for each entry
    - 0x08 terminator at the end

    Args:
        metadata_dict: Dictionary of metadata key-value pairs

    Returns:
        Binary KeyValues serialized data
    """
    if not metadata_dict:
        return b''

    kvs = KeyValuesSystem()

    # Add each metadata key-value pair to the root
    for key, value in metadata_dict.items():
        # All lobby metadata values are strings
        kvs.root.set_value(key, KVS_TYPE_STRING, str(value))

    # Serialize to binary
    out_stream = BytesIO()
    kvs.serialize(out_stream)
    return out_stream.getvalue()


def build_GetLobbyListResponse(client_obj, game_id, lobbies):
    """
    Build a lobby list response with properly serialized KeyValues metadata.

    Based on 2008 client analysis (UpdateLobbyMetadataFromLobbyListMsg):
    - Metadata must be in KeyValues binary format
    - Format per lobby: steamID (8), members (4), max_members (4), metadata_len (4), metadata_bytes
    """
    resp = MsgClientGetLobbyListResponse(client_obj)
    resp.game_id = game_id
    for lobby in lobbies:
        resp.lobby_ids.append(lobby.steamID)

        # Get metadata dict and serialize to KeyValues binary
        metadata_dict = lobby.metadata if hasattr(lobby, 'metadata') else {}
        if isinstance(metadata_dict, dict):
            metadata_bytes = serialize_metadata_to_keyvalues(metadata_dict)
        else:
            # Already bytes (shouldn't happen but handle gracefully)
            metadata_bytes = metadata_dict if metadata_dict else b''

        member_count = lobby.get_member_count() if hasattr(lobby, 'get_member_count') else 0
        member_limit = lobby.member_limit if hasattr(lobby, 'member_limit') else 0

        resp.metadata_blocks.append((lobby.steamID, member_count, member_limit, metadata_bytes))
    return resp.to_clientmsg()


def build_GetLobbyMetadataResponse(client_obj, lobby=None, lobby_steam_id=None, metadata_dict=None, members=0, members_max=0):
    """
    Build a lobby metadata response with properly serialized KeyValues metadata.

    Based on 2008 client analysis (CClientJobReceiveLobbyData):
    - Metadata must be in KeyValues binary format
    - Format: steamID (8), metadata_len (4), metadata_bytes, [members_max (4), members (4)]

    Can be called two ways:
    1. With lobby object: build_GetLobbyMetadataResponse(client_obj, lobby)
    2. With direct params: build_GetLobbyMetadataResponse(client_obj, lobby_steam_id=id, metadata_dict={}, members=N, members_max=M)
    """
    resp = MsgClientGetLobbyMetadataResponse(client_obj)

    if lobby is not None:
        # Called with lobby object
        resp.lobby_id = lobby.steamID if hasattr(lobby, 'steamID') else lobby.steam_id

        # Get metadata dict and serialize to KeyValues binary
        meta = lobby.metadata if hasattr(lobby, 'metadata') else {}
        if isinstance(meta, dict):
            resp.metadata = serialize_metadata_to_keyvalues(meta)
        else:
            resp.metadata = meta if meta else b''

        resp.members_max = lobby.member_limit if hasattr(lobby, 'member_limit') else (lobby.max_members if hasattr(lobby, 'max_members') else 0)
        resp.members = lobby.get_member_count() if hasattr(lobby, 'get_member_count') else 0

    elif lobby_steam_id is not None:
        # Called with direct parameters
        resp.lobby_id = lobby_steam_id

        if metadata_dict and isinstance(metadata_dict, dict):
            resp.metadata = serialize_metadata_to_keyvalues(metadata_dict)
        elif metadata_dict:
            resp.metadata = metadata_dict  # Already bytes
        else:
            resp.metadata = b''

        resp.members_max = members_max
        resp.members = members

    return resp.to_clientmsg()
