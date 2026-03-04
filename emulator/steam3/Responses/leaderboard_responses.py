from steam3.Types.steam_types import EResult, ELeaderboardDataRequest as LeaderboardDataRequest
from steam3.Types.steamid import SteamID
from steam3.cm_packet_utils import ExtendedMsgHdr
from steam3.messages.responses.MsgClientLBSGetLBEntriesResponse import MsgClientLBSGetLBEntriesResponse
from steam3.messages.responses.MsgClientLBSSetScoreResponse import MsgClientLBSSetScoreResponse
from steam3.messages.responses.MsgClientLBSFindOrCreateLBResponse import MsgFindOrCreateLBResponse
from steam3 import database


class LeaderboardEntryData:
    """Simple data class to hold leaderboard entry data for wire serialization."""
    def __init__(self, steam_global_id: int, global_rank: int, score: int, details: list):
        self.steam_global_id = steam_global_id
        self.global_rank = global_rank
        self.score = score
        self.details = details


def _convert_db_entry_to_response_entry(db_entry):
    """Convert a database LeaderboardEntry to LeaderboardEntryData for the response."""
    # Convert accountID to full SteamID (64-bit)
    steam_global_id = SteamID.static_create_normal_account_steamid(db_entry.friendRegistryID)

    # Convert details BLOB to list of ints
    details = []
    if db_entry.details:
        details_blob = db_entry.details
        details = [int.from_bytes(details_blob[i:i+4], 'little')
                   for i in range(0, len(details_blob), 4)]

    return LeaderboardEntryData(
        steam_global_id=steam_global_id,
        global_rank=db_entry.rank,
        score=db_entry.score,
        details=details
    )


def build_ClientLBSFindOrCreate_response(client_obj, lbObj, isProtobuf = False):
    response = MsgFindOrCreateLBResponse(client_obj)

    response.result        = EResult.OK   # OK
    response.leaderboard   = lbObj.UniqueID
    response.entry_count   = database.count_entries(lbObj.UniqueID)
    response.sort_method   = lbObj.sort_method
    response.display_type  = lbObj.display_type
    response.name          = lbObj.name
    # Check if the packet is a protobuf packet
    if isProtobuf:
        return response.to_protobuf()
    else:
        return response.to_clientmsg()


def build_ClientLBSGetEntries_response(client_obj, cmserver_obj, parser, request, isProtobuf = False):
    response = MsgClientLBSGetLBEntriesResponse(client_obj)
    if client_obj:
        lb = database.get_leaderboard_by_id(parser.leaderboard)
        if lb:
            db_entries = []
            # dispatch by request type
            if parser.request == LeaderboardDataRequest.Global:
                db_entries = database.get_entries_range(
                    lb.UniqueID,
                    parser.range_start,
                    parser.range_end
                )
                response.result = EResult.OK
            elif parser.request == LeaderboardDataRequest.GlobalAroundUser:
                db_entries = database.get_around_user_entries(
                    lb.UniqueID,
                    client_obj.accountID,
                    parser.range_start,
                    parser.range_end
                )
                response.result = EResult.OK
            elif parser.request == LeaderboardDataRequest.Friends:
                db_entries = database.get_friends_entries(
                    lb.UniqueID,
                    client_obj.accountID,
                    parser.range_start,
                    parser.range_end
                )
                response.result = EResult.OK
            else:
                cmserver_obj.log.error(
                    "Invalid leaderboard entries request type : %u", parser.request
                )
                response.result = EResult.OK  # real server behaviour

            # Convert database entries to response format
            for db_entry in db_entries:
                response.entries.append(_convert_db_entry_to_response_entry(db_entry))

            if response.result == EResult.OK:
                response.leaderboard_entry_count = database.get_entry_count(lb.UniqueID)
        else:
            response.result = EResult.InvalidParam
    else:
        response.result = EResult.InvalidParam

    if isProtobuf:
        return response.to_protobuf()
    else:
        return response.to_clientmsg()


def build_ClientLBSSetScore_Response(client_obj, parser, request, isProtobuf = False):
    response = MsgClientLBSSetScoreResponse(client_obj)
    if client_obj:
        lb = database.get_leaderboard_by_id(parser.leaderboard)
        if lb:
            response.result = EResult.OK
            prev_rank = database.get_player_global_rank(lb.UniqueID, client_obj.accountID)

            response.score_changed = database.set_score(
                lb.UniqueID,
                client_obj.accountID,
                parser.score,
                parser.details,
                parser.method
            )
            response.leaderboard_entry_count = database.get_entry_count(lb.UniqueID)

            if response.score_changed:
                response.previous_global_rank = prev_rank
                response.new_global_rank = database.get_player_global_rank(lb.UniqueID, client_obj.accountID)
        else:
            response.result = EResult.InvalidParam
    else:
        response.result = EResult.InvalidParam

    if isProtobuf:
        return response.to_protobuf()
    else:
        return response.to_clientmsg()
