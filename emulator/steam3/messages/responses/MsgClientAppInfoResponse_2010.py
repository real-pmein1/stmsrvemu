"""
MsgClientAppInfoResponse for 2010-2011 clients.

Uses the single appinfo.vdf V1 format where the server reads from
a combined appinfo file and sends the requested app data.

Response format (per IDA analysis of CAppInfoCache::BUpdateAppDataFromBuffer):
- Header: m_cNumApps (uint32)
- For each app:
  - AppId (uint32)
  - ChangeNumber (uint32)
  - Sections: repeated [sectionType (uint8), KeyValues binary] until sectionType==0
"""
import logging
import struct
import zlib
from datetime import datetime
from typing import List, Optional

import globalvars

log = logging.getLogger("MsgClientAppInfoResponse_2010")

# Maximum number of apps to send in a single response to prevent client crashes
MAX_APPINFO_RESPONSE = 200

from steam3.Types.emsg import EMsg
from steam3.Types.steam_types import AppInfoSections
from steam3.cm_packet_utils import CMResponse
from utilities.appinfo_utils import (
    get_multiple_app_data_2010_2011,
    get_multiple_app_data_2012_above,
    get_appinfo_era,
    create_4byte_id_from_date,
)


# Map section names (from AppInfoParser) to section IDs
SECTION_NAME_TO_ID = {
    "All": 1,
    "Common": 2,
    "Extended": 3,
    "Config": 4,
    "Stats": 5,
    "Install": 6,
    "Depots": 7,
    "VAC": 8,
    "DRM": 9,
    "UFS": 10,
    "OGG": 11,
    "Items": 12,
    "Policies": 13,
    "SystemRequirements": 14,
    "Community": 15,
}

# Reverse mapping: ID to name
SECTION_ID_TO_NAME = {v: k for k, v in SECTION_NAME_TO_ID.items()}


class MsgClientAppInfoResponse_2010:
    """
    Response class for 2010-2011 appinfo requests.
    Reads app data from the single appinfo.vdf file (V1 format).

    Only sends sections that:
    1. Were requested by the client (via section flags)
    2. Have different CRCs than what the client has (or client has no CRC)
    """

    def __init__(self, client_obj, app_info_requests, islan=False):
        """
        :param client_obj: The client object associated with the request
        :param app_info_requests: List of AppInfoRequest objects from MsgClientAppInfoRequest
                                  Each contains: appId, requestAllSections, localAppInfoSectionsCRC32
        :param islan: Whether this is a LAN connection
        """
        self.app_info_requests = app_info_requests
        self.client_obj = client_obj
        self.islan = islan
        self.packet_buffer = bytearray()

    def to_clientmsg(self):
        """
        Serializes the response into a CMResponse packet.

        Response format:
        - uint32: Number of apps
        - For each app:
          - uint32: AppId
          - uint32: ChangeNumber
          - Sections data (sectionType byte + KeyValues binary, terminated by 0x00)
        """
        packet = CMResponse(eMsgID=EMsg.ClientAppInfoResponse, client_obj=self.client_obj)

        # Limit the number of requests to prevent client crashes
        requests_to_process = self.app_info_requests
        if len(requests_to_process) > MAX_APPINFO_RESPONSE:
            log.warning(f"Limiting appinfo request from {len(self.app_info_requests)} to {MAX_APPINFO_RESPONSE} to prevent client crash")
            requests_to_process = self.app_info_requests[:MAX_APPINFO_RESPONSE]

        # Extract app IDs from requests
        app_ids = [req.appId for req in requests_to_process]

        # Determine which era to use and get app data
        era = get_appinfo_era(globalvars.CDDB_datetime)
        if era == "2012_above":
            app_data_list = get_multiple_app_data_2012_above(
                globalvars.CDDB_datetime,
                app_ids,
                self.islan
            )
        else:
            # Use 2010_2011 for both 2010_2011 and 2009_2010 eras
            app_data_list = get_multiple_app_data_2010_2011(
                globalvars.CDDB_datetime,
                app_ids,
                self.islan
            )

        # Create a lookup for app data by app_id
        app_data_by_id = {app.app_id: app for app in app_data_list}

        # Build response buffer
        temp_buffer = bytearray()
        successful_count = 0

        for request in requests_to_process:
            app_data = app_data_by_id.get(request.appId)
            if not app_data:
                log.debug(f"App {request.appId} not found in appinfo cache")
                continue

            app_buffer = self._serialize_app_data(app_data, request)
            if app_buffer:
                temp_buffer.extend(app_buffer)
                successful_count += 1

        # Write header: number of apps
        self.packet_buffer = bytearray()
        self.packet_buffer.extend(struct.pack('<I', successful_count))

        # Append all app data
        self.packet_buffer.extend(temp_buffer)

        log.debug(f"Built appinfo response: {successful_count} apps, {len(self.packet_buffer)} bytes")

        packet.data = bytes(self.packet_buffer)
        return packet

    def _serialize_app_data(self, app_data, request):
        """
        Serializes a single ApplicationData object to the wire format,
        filtering sections based on what the client requested.

        Format:
        - uint32: AppId
        - uint32: ChangeNumber
        - For each section: uint8 sectionType + KeyValues binary data
        - uint8: 0x00 (end marker)

        :param app_data: ApplicationData from the appinfo file
        :param request: AppInfoRequest containing section flags and CRCs
        """
        if not app_data:
            return None

        buffer = bytearray()

        # Write AppId
        buffer.extend(struct.pack('<I', app_data.app_id))

        # Write ChangeNumber - use the one from appinfo or generate from CDR date
        change_number = 0
        if app_data.change_number is not None and app_data.change_number > 0:
            change_number = app_data.change_number
            buffer.extend(struct.pack('<I', change_number))
        else:
            # Generate change number from CDR date
            current_cdr_date = datetime.strptime(globalvars.CDDB_datetime, "%m/%d/%Y %H:%M:%S")
            change_id_bytes = create_4byte_id_from_date(current_cdr_date)
            buffer.extend(change_id_bytes)
            change_number = struct.unpack('<I', change_id_bytes)[0]

        # Get the sections_raw dict from app_data
        sections_raw = getattr(app_data, 'sections_raw', {})
        if not sections_raw:
            log.warning(f"App {app_data.app_id} has no sections_raw data")
            # Still write the terminator
            buffer.append(0x00)
            return buffer

        # Determine which sections to send
        sections_to_send = self._get_sections_to_send(app_data, request, sections_raw)

        if not sections_to_send:
            log.debug(f"App {app_data.app_id}: No sections to send (client has all)")
            # Even if no sections to send, we still write the app with terminator
            buffer.append(0x00)
            return buffer

        # Sort sections by section ID and write them
        sorted_sections = sorted(sections_to_send, key=lambda x: x[0])

        for section_id, raw_bytes in sorted_sections:
            # raw_bytes already includes the section type byte at the start
            # (from AppInfoParser.adjust_raw_bytes)
            buffer.extend(raw_bytes)

        # Write end marker
        buffer.append(0x00)

        log.debug(f"App {app_data.app_id}: Serialized {len(sorted_sections)} sections, "
                  f"{len(buffer)} bytes, changeNumber={change_number}")

        return buffer

    def _get_sections_to_send(self, app_data, request, sections_raw):
        """
        Determines which sections to send based on:
        1. requestAllSections flag - if True, send all sections
        2. Section flags in localAppInfoSectionsCRC32 - only send requested sections
        3. CRC comparison - only send if CRC differs or client doesn't have the section

        :return: List of (section_id, raw_bytes) tuples to send
        """
        sections_to_send = []

        # If requestAllSections is True, send all available sections
        if request.requestAllSections:
            for section_name, raw_bytes in sections_raw.items():
                section_id = SECTION_NAME_TO_ID.get(section_name, 0)
                if section_id > 0:
                    sections_to_send.append((section_id, raw_bytes))
            return sections_to_send

        # Otherwise, only send sections that were explicitly requested
        # The client sends CRCs for sections it has
        for section_enum, client_crc in request.localAppInfoSectionsCRC32.items():
            # section_enum is AppInfoSections enum
            section_id = section_enum.value
            section_name = SECTION_ID_TO_NAME.get(section_id)

            if not section_name:
                continue

            if section_name not in sections_raw:
                continue

            raw_bytes = sections_raw[section_name]

            # Calculate server CRC for this section's data
            # Note: raw_bytes includes the section type byte, but CRC is typically
            # computed on the KeyValues data only. We need to skip the first byte.
            if len(raw_bytes) > 1:
                server_crc = zlib.crc32(raw_bytes[1:]) & 0xFFFFFFFF
            else:
                server_crc = 0

            # Only send if CRC differs (client needs update) or client CRC is 0 (new section)
            if client_crc == 0 or client_crc != server_crc:
                sections_to_send.append((section_id, raw_bytes))

        return sections_to_send

    @staticmethod
    def _get_section_id(section_name):
        """
        Maps section name to section ID.
        """
        return SECTION_NAME_TO_ID.get(section_name, 0)

    def get_packet_buffer(self):
        """Returns the serialized packet buffer."""
        return bytes(self.packet_buffer)
