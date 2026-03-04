"""NOTES:
    - 1122 uses single appinfo files but expects change number..
    - 1238 expects changeid, probably single appinfo v1"""
import logging
import struct

from datetime import datetime
import globalvars

from steam3.cm_packet_utils import MultiMsg
from steam3.messages.responses.MsgClientAppInfoResponse_Obsolete import MsgClientAppInfoResponse_Obsolete
from steam3.messages.responses.MsgClientAppInfoResponse_2010 import MsgClientAppInfoResponse_2010
from steam3.messages.responses.MsgClientAppInfoChanges_response import MsgClientAppInfoChanges
from steam3.Managers.appinfo_tracker import get_appinfo_tracker
from utilities import time
from utilities.appinfo_utils import (
    find_appid_change_numbers_2010_2011,
    find_appid_change_numbers_2012_above,
    find_appid_files_2009,
    create_4byte_id_from_date,
    get_appinfo_era,
)

# Cutoff date for 2010-2011 single appinfo format
# CDR dates after this use the single appinfo.vdf file with V1 format
SINGLE_APPINFO_CUTOFF_DATE = datetime(2010, 4, 27)

# Cutoff date for 2012+ format
ERA_2012_ABOVE_START = datetime(2012, 1, 1)

# Maximum number of app IDs to send in appinfo responses
# Sending more than this causes client crashes
MAX_APPINFO_COUNT = 50

log = logging.getLogger("AppInfoResponses")


"""00000000 struct MsgClientAppInfoResponse_t // sizeof=0x4
00000000 {
00000000     uint32 m_cNumApps;
00000004 };
"""
def build_appinfo_response(client_obj, app_info_requests, is_deprecated=False):
    """
    Build the appinfo response for clients.

    Tracks which appinfos have been sent to each client and only sends unsent ones.
    Resets tracking on blob/CDR changes.

    :param client_obj: The client object associated with the request
    :param app_info_requests: List of AppInfoRequest objects containing appId, requestAllSections,
                              and localAppInfoSectionsCRC32 for CRC comparison
    :param is_deprecated: Whether to use the deprecated (obsolete) format
    :return: MultiMsg packet with the response
    """
    client_address = str(client_obj.ip_port[0])
    client_id = client_obj.connectionid

    # Get tracker and check for blob changes
    tracker = get_appinfo_tracker()
    tracker.reset_on_blob_change(globalvars.CDDB_datetime)

    # Extract requested appids
    requested_appids = [req.appId for req in app_info_requests]
    original_count = len(requested_appids)

    # Filter to only unsent appids
    unsent_appids = tracker.get_unsent_appids(client_id, requested_appids)

    if not unsent_appids:
        # All requested appids have already been sent - return empty response
        log.info(f"Client {client_obj.ip_port}: All {original_count} appids already sent, returning empty response")
        return build_empty_appinfo_response(client_obj)

    # Filter requests to only unsent appids
    unsent_requests = [req for req in app_info_requests if req.appId in unsent_appids]

    log.info(f"Client {client_obj.ip_port}: Requested {original_count} appids, {len(unsent_requests)} unsent")

    # Limit to MAX_APPINFO_COUNT to prevent client crashes
    if len(unsent_requests) > MAX_APPINFO_COUNT:
        log.warning(f"Limiting unsent appinfo requests from {len(unsent_requests)} to {MAX_APPINFO_COUNT} to prevent client crash")
        unsent_requests = unsent_requests[:MAX_APPINFO_COUNT]

    # Build packet for unsent appids
    multi_packet = MultiMsg()
    multi_packet.targetJobID = -1
    multi_packet.sourceJobID = -1

    # Determine if connection is local or external
    if str(client_address) in globalvars.server_network or globalvars.public_ip == "0.0.0.0":
        islan = True
    else:
        islan = False

    # Parse CDR date to determine which handler to use
    current_cdr_date = datetime.strptime(globalvars.CDDB_datetime, "%m/%d/%Y %H:%M:%S")

    if is_deprecated:
        # Handle both ContentDescriptionRecord object and raw dict formats
        # Re-parse CDR date after updating
        current_cdr_date = datetime.strptime(globalvars.CDDB_datetime, "%m/%d/%Y %H:%M:%S")

        # Check if we should use the 2010-2011 single appinfo format
        if current_cdr_date >= SINGLE_APPINFO_CUTOFF_DATE:
            # Use 2010-2011 handler with full request objects for section filtering
            packet = MsgClientAppInfoResponse_2010(client_obj, unsent_requests, islan=islan)
        else:
            # For deprecated format pre-2010, extract app IDs for the obsolete handler
            appid_list = [req.appId for req in unsent_requests]
            packet = MsgClientAppInfoResponse_Obsolete(client_obj, appid_list, True, globalvars.CDDB_datetime, islan=islan)
    else:
        # Check if we should use the 2010-2011 single appinfo format
        if current_cdr_date >= SINGLE_APPINFO_CUTOFF_DATE:
            # Use 2010-2011 handler with full request objects for section filtering
            packet = MsgClientAppInfoResponse_2010(client_obj, unsent_requests, islan=islan)
        else:
            # Use obsolete handler for 2009 and earlier
            appid_list = [req.appId for req in unsent_requests]
            packet = MsgClientAppInfoResponse_Obsolete(client_obj, appid_list, False, islan=islan)

    packet = packet.to_clientmsg()

    multi_packet.set_compressed()
    multi_packet.add_message(packet)
    multi_packet.serialize()

    # Mark these appids as sent
    sent_appids = [req.appId for req in unsent_requests]
    tracker.mark_appids_sent(client_id, sent_appids)

    return multi_packet


def build_empty_appinfo_response(client_obj):
    """
    Build an empty appinfo response (0 apps).

    Used when all requested appids have already been sent to the client.

    :param client_obj: The client object associated with the request
    :return: MultiMsg packet with empty response (0 apps)
    """
    multi_packet = MultiMsg()
    multi_packet.targetJobID = -1
    multi_packet.sourceJobID = -1

    # Create response with 0 apps
    # Format: uint32 m_cNumApps = 0
    empty_response = struct.pack('<I', 0)

    multi_packet.set_compressed()
    multi_packet.add_message(empty_response)
    multi_packet.serialize()

    return multi_packet


def build_appinfochanges_response(client_obj, last_change_number, do_fullupdate = False):
    """Constructs the server response for AppInfo changes based on the client's request.

    :param client_obj: The client object associated with the request.
    :param last_change_number: The last change number known to the server.
    :param do_fullupdate: Boolean indicating whether a full update is requested.
    :return: A properly structured packet for AppInfoChanges.
    """

    current_cdr_date = datetime.strptime(globalvars.CDDB_datetime, "%m/%d/%Y %H:%M:%S")
    current_changeid = create_4byte_id_from_date(current_cdr_date)

    # Determine the appinfo era
    era = get_appinfo_era(globalvars.CDDB_datetime)

    found_appinfo_list = []

    if last_change_number <= 0:
        if era == "2012_above":
            # 2012+ era uses V2/V2+ format
            found_appinfo_list = find_appid_change_numbers_2012_above(globalvars.CDDB_datetime, client_obj.isLan)
        elif era == "2010_2011":
            # 2010-2011 era uses V1 format
            found_appinfo_list = find_appid_change_numbers_2010_2011(globalvars.CDDB_datetime, client_obj.isLan)
        else:
            # 2009_2010 era uses individual appinfo files
            found_appinfo_list = find_appid_files_2009(globalvars.CDDB_datetime, client_obj.isLan)

    if int(last_change_number).to_bytes(4, "little") == current_changeid:
        packet = MsgClientAppInfoChanges(client_obj)
        packet.current_change_number = last_change_number
        packet.force_full_update = 0
        packet.app_ids = []
        packet = packet.to_clientmsg()
        return packet

    packet = MsgClientAppInfoChanges(client_obj)
    packet.current_change_number = int().from_bytes(current_changeid, "little")
    packet.force_full_update = do_fullupdate

    # Populate app IDs from app_data_list into the message
    if found_appinfo_list:
        # Handle both formats:
        # - 2009 format: list of tuples (appid, file_path)
        # - 2010-2011 format: list of plain integers (appid)
        if isinstance(found_appinfo_list[0], tuple):
            app_ids_list = [appid for appid, _ in found_appinfo_list]
        else:
            app_ids_list = list(found_appinfo_list)

        # Limit to MAX_APPINFO_COUNT to prevent client crashes
        # The client should only get appinfo it specifically requests anyway
        original_count = len(app_ids_list)
        if original_count > MAX_APPINFO_COUNT:
            log.warning(f"Limiting appinfo changes from {original_count} to {MAX_APPINFO_COUNT} to prevent client crash")
            app_ids_list = app_ids_list[:MAX_APPINFO_COUNT]

        packet.app_ids = app_ids_list
    else:
        packet.app_ids = []

    # Serialize the message to create the buffer
    packet = packet.to_clientmsg()
    multi_packet = MultiMsg()
    multi_packet.targetJobID = -1
    multi_packet.sourceJobID = -1
    #multi_packet.set_compressed()

    multi_packet.add_message(packet)

    multi_packet.serialize()
    #packet = packet.to_clientmsg()

    return multi_packet

