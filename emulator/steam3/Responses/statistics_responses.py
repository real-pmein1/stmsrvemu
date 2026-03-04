import os
import glob
import struct
import zlib
from steam3.ClientManager.client import Client
from steam3.Types.GameID import GameID
from steam3.Types.emsg import EMsg
from steam3.Types.steam_types import EResult
from steam3.cm_packet_utils import CMResponse
from steam3.messages.responses.MSGClientGetUserStatsResponse import MSGClientGetUserStatsResponse
from steam3.messages.responses.MSGClientStoreUserStatsResponse import MSGClientStoreUserStatsResponse
from steam3.messages.MSGClientStatsUpdated import MSGClientStatsUpdated
import globalvars
from utilities.database import statistics_db


def build_GetUserStatsResponse(client_obj: Client, errorcode=EResult.OK, gameID_int=0, steamID_raw=b"\x00", schema_version=0, user_id=None):
    """
    Builds a response packet for GetUserStats with the following structure:

      struct MsgClientGetUserStatsResponse_t {
          uint64 m_ulGameID;        // 8 bytes: the game ID.
          uint32 m_eResult;         // 4 bytes: result code (e.g., OK, Fail).
          uint8  m_bSchemaAttached; // 1 byte: 1 if a stat schema is attached; 0 otherwise.
          int32  m_cStats;          // 4 bytes: number of stat entries (set to 0 for now).
          uint32 m_crcStats;        // 4 bytes: CRC32 checksum of stats (set to 0 for now).
          // Followed immediately by:
          //   if m_bSchemaAttached is 1 the raw binary contents of the stat schema file follow.
      };

    This function works as follows:
      - If schema_version is 0, then we load a schema file from disk and attach its contents.
      - If globalvars.steamui_ver <= 1053, we search in "files\statschemas\2009-2010\" for files
        matching "UserGameStats_<gameid>_v*.bin" and choose the file with the highest numeric version.
      - If globalvars.steamui_ver > 1053, we search in "files\statschemas\2010-2023\" for files
        matching "UserGameStatsSchema_<gameid>_v*.bin" and choose the file with the highest numeric version.
      - The file's raw bytes are appended after the fixed header.
      - The stats count is set to 0 and crcStats to 0. The caller may append stored statistics if needed.
    """
    # Here we wrap the game ID; note that MsgGetUserStatsResponse.to_clientmsg will cast it back to int.
    gameID = GameID(gameID_int)

    # Default values if no schema is attached:
    b_schema_attached = False
    schema_data = b""
    stats = {}
    crc_stats = zlib.crc32(b"")
    if user_id is not None:
        try:
            stats = statistics_db.get_user_stats(user_id, gameID_int)
            crc_stats = zlib.crc32(repr(stats).encode('utf-8'))
        except Exception:
            stats = {}

    if schema_version == 0:
        b_schema_attached = True
        gameid_str = str(gameID_int)

        """if globalvars.steamui_ver <= 1053:
            base_path = os.path.join("files", "statschemas", "2009-2010")
            pattern = os.path.join(base_path, f"UserGameStats_{gameid_str}_v*.bin")
            files = glob.glob(pattern)
            if files:
                def extract_version(filename):
                    try:
                        base = os.path.basename(filename)
                        parts = base.split("_v")
                        if len(parts) >= 2:
                            version_str = parts[1].split(".bin")[0]
                            return int(version_str)
                    except Exception:
                        return 0
                files.sort(key=extract_version, reverse=True)
                if len(files) > 1:
                    globalvars.log.debug(
                        f"Multiple stat schemas found for {gameID_int}, using {os.path.basename(files[0])}")
                schema_file = files[0]
                schema_data = open(schema_file, "rb").read()
            else:
                schema_data = b""
        else:"""
        base_path = os.path.join("files", "statschemas", "2010-2023")
        pattern = os.path.join(base_path, f"UserGameStatsSchema_{gameid_str}_v*.bin")
        files = glob.glob(pattern)
        if files:
            def extract_version(filename):
                try:
                    base = os.path.basename(filename)
                    parts = base.split("_v")
                    if len(parts) >= 2:
                        version_str = parts[1].split(".bin")[0]
                        return int(version_str)
                except Exception:
                    return 0
            files.sort(key=extract_version, reverse=True)
            if len(files) > 1:
                globalvars.log.debug(
                    f"Multiple stat schemas found for {gameID_int}, using {os.path.basename(files[0])}")
            schema_file = files[0]
            schema_data = open(schema_file, "rb").read()
        else:
            schema_data = b""

    # Build the response packet using the MSGClientGetUserStatsResponse class.
    response = MSGClientGetUserStatsResponse(client_obj)
    response.gameID = gameID_int
    response.result = errorcode
    response.schema_attached = b_schema_attached
    response.schema_data = schema_data
    response.crc_stats = crc_stats
    
    # Convert stats dictionary to the key/value format expected by client
    # stats is a dict of stat_name -> value, we need stat_id -> value
    response.stats_data = {}
    if stats:
        # For now, we'll use a simple mapping where stat names become numeric IDs
        # This should be replaced with proper schema parsing to get real stat IDs
        for i, (stat_name, stat_value) in enumerate(stats.items(), 1):
            try:
                # Try to convert value to int (for int stats)
                response.stats_data[i] = int(stat_value)
            except (ValueError, TypeError):
                try:
                    # Try to convert float to int representation
                    import struct
                    response.stats_data[i] = struct.unpack('<I', struct.pack('<f', float(stat_value)))[0]
                except (ValueError, TypeError):
                    # Default to 0 if conversion fails
                    response.stats_data[i] = 0
    
    response.stats_count = len(response.stats_data)
    client_msg = response.to_clientmsg()
    return client_msg


def build_GetUserStats_response(client_obj: Client, result: EResult, gameID: int, user_stats=None, schema_data: bytes = b""):
    """
    Build response for ClientGetUserStats using new message classes.
    """
    response = MSGClientGetUserStatsResponse(client_obj)
    response.gameID = gameID
    response.result = result
    response.schema_attached = len(schema_data) > 0
    response.schema_data = schema_data
    
    # Convert user_stats to stats_data format
    response.stats_data = {}
    if user_stats and result == EResult.OK:
        # UserStats has a .stats StatDict with stat_id -> value mappings
        if hasattr(user_stats, 'stats') and user_stats.stats:
            # user_stats.stats is already a dict of stat_id -> value
            for stat_id, value in user_stats.stats.items():
                try:
                    # Ensure stat_id fits in 16-bit unsigned integer range (0-65535)
                    stat_id_int = int(stat_id) & 0xFFFF
                    response.stats_data[stat_id_int] = int(value)
                except (ValueError, TypeError):
                    # Skip invalid entries
                    continue
        else:
            # Fallback: assume user_stats is a dict itself
            for key, value in (user_stats.items() if hasattr(user_stats, 'items') else []):
                try:
                    # If key is already numeric, use it as stat_id
                    stat_id = int(key) if isinstance(key, str) and key.isdigit() else hash(key) & 0xFFFF
                    response.stats_data[stat_id] = int(value)
                except (ValueError, TypeError):
                    # Skip invalid entries
                    continue
    
    response.stats_count = len(response.stats_data)
    response.crc_stats = zlib.crc32(repr(response.stats_data).encode('utf-8')) & 0xFFFFFFFF
    
    return response.to_clientmsg()


def build_StoreUserStats_response(client_obj: Client, result: EResult, gameID: int,
                                 stats_crc: int, failed_validation_stats: dict = None):
    """
    Build response for ClientStoreUserStats using new message classes.

    Note: The failed_validation_stats parameter is accepted for API compatibility but
    not used in the response. The 16-byte response format is compatible with all client
    versions - newer 2009+ clients that support failed validation simply clear their
    local pending stats unconditionally when receiving this shorter response.
    """
    response = MSGClientStoreUserStatsResponse(client_obj)
    response.gameID = gameID
    response.result = result
    response.statsCrc = stats_crc
    # Note: failedValidationStats not included in 16-byte response format

    return response.to_clientmsg()


def build_StatsUpdated_notification(client_obj: Client, steam_id: int, gameID: int,
                                   stats_crc: int, updated_stats: dict):
    """
    Build ClientStatsUpdated notification for game servers.
    """
    notification = MSGClientStatsUpdated(client_obj)
    notification.steamID = steam_id
    notification.gameID = gameID
    notification.statsCrc = stats_crc
    notification.updatedStats = updated_stats
    
    return notification.to_clientmsg()

