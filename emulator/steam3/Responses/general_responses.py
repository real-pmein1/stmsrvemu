import copy
import logging
import struct
import traceback
from datetime import datetime

import globalvars
from steam3.Types.emsg import EMsg
from steam3.Types.steam_types import EServerType, SystemIMType

from steam3.cm_packet_utils import CMResponse
from steam3.messages.MsgClientCMList import MsgClientCMList
from steam3.messages.MsgClientMarketingMessageUpdate import MsgClientMarketingMessageUpdate
from steam3.messages.MsgClientMarketingMessageUpdate2 import MsgClientMarketingMessageUpdate2
from steam3.messages.MsgClientRequestedClientStats import ClientStat, MsgClientRequestedClientStats
from steam3.messages.responses.MsgClientAvailableServers import MsgClientServersAvailable
from steam3.messages.responses.MsgClientServerList import MsgClientServerList

log = logging.getLogger('GeneralResponses')


def build_client_newsupdate_response(client_obj):
    """
    Build a ClientNewsUpdate response packet.

    News update types (ENewsUpdateType):
      k_EAppNews = 0x0      - App-specific news (9 bytes: type + news_id + app_id)
      k_ESteamAds = 0x1     - Steam ads (29 bytes: type + 7 uint32 fields)
      k_ESteamNews = 0x2    - Steam news (29 bytes: type + 7 uint32 fields)
      k_ECDDBUpdate = 0x3   - CDR database update (unused in client code)
      k_EClientUpdate = 0x4 - Client update notification (14 bytes: type + news_id + versions + reload_cddb)

    Packet structure:
      - m_usNumNewsUpdates (uint16): Number of news items
      - For each news item:
        - eNewsUpdateType (uint8)
        - Variable data based on type
    """
    packet = CMResponse(eMsgID=EMsg.ClientNewsUpdate, client_obj=client_obj)

    # Sample app news data (type 0)
    news_items = [
        (0x02B7, 0x0514), (0x02AF, 0x09C4), (0x02AE, 0x0140), (0x02A8, 0x012C),
        (0x02A9, 0x017C), (0x0297, 0x04B0), (0x028B, 0x076C), (0x0283, 0x00DC),
        (0x027D, 0x00F0), (0x0265, 0x0168), (0x0244, 0x0521), (0x0244, 0x051D),
        (0x0204, 0x000A), (0x0203, 0x05DC), (0x01F4, 0x00D3), (0x01F2, 0x00DB),
        (0x01F2, 0x0154), (0x01F2, 0x0118), (0x01EC, 0x05DE), (0x01EB, 0x0050),
        (0x01EB, 0x001E), (0x01EB, 0x0046), (0x01E6, 0x03EA), (0x01E1, 0x0014),
        (0x01E1, 0x003C), (0x01E1, 0x0032), (0x01E1, 0x0028), (0x01E1, 0x0082),
    ]

    # Build packet: header (uint16 count) + news entries
    # Header: m_usNumNewsUpdates as uint16
    packet.data = struct.pack('<H', len(news_items))

    # Each app news entry: type (uint8) + news_id (uint32) + app_id (uint32) = 9 bytes
    news_type = 0  # k_EAppNews
    for news_id, app_id in news_items:
        packet.data += struct.pack('<BII', news_type, news_id, app_id)

    """find_closest_news_update = NewsManager.find_closest_news_update()
    packet.data = b'$\x01\x00\xd3\x05\x00\x00|$\x00\x00\x00\xd3\x05\x00\x00\xd0\x11\x00\x00\x00\xd1\x05\x00\x00\x903\x00\x00\x00\xd1\x05\x00\x00\x9a3\x00\x00\x00\xd1\x05\x00\x00\xae3\x00\x00\x00\xd1\x05\x00\x00\xb83\x00\x00\x00\xd1\x05\x00\x00\xc23\x00\x00\x00\xcb\x05\x00\x00\xb8\x01\x00\x00\x00\xce\x05\x00\x00@\x01\x00\x00\x00\xce\x05\x00\x00\xdc\x00\x00\x00\x00\xce\x05\x00\x00\x90\x01\x00\x00\x00\xce\x05\x00\x00T\x01\x00\x00\x00\xce\x05\x00\x00|\x01\x00\x00\x00\xce\x05\x00\x00\x9a\x01\x00\x00\x00\xce\x05\x00\x00\xa4\x01\x00\x00\x00\xce\x05\x00\x00\xdb\x00\x00\x00\x00\xca\x05\x00\x00\x98!\x00\x00\x00\xc8\x05\x00\x00\xf0(\x00\x00\x00\xc8\x05\x00\x00\xb4(\x00\x00\x00\xc6\x05\x00\x00`\t\x00\x00\x00\xc3\x05\x00\x00d2\x00\x00\x00\xc3\x05\x00\x00n2\x00\x00\x00\xc1\x05\x00\x00\xa4\x10\x00\x00\x00\xc1\x05\x00\x00\x86\x10\x00\x00\x00\xc0\x05\x00\x00\x80\x07\x00\x00\x00\xb3\x05\x00\x00\xea$\x00\x00\x00\xb3\x05\x00\x00h$\x00\x00\x00\xb3\x05\x00\x00r$\x00\x00\x00\xbe\x05\x00\x00T$\x00\x00\x00\xbb\x05\x00\x00\xcc)\x00\x00\x00\xba\x05\x00\x00\xec\t\x00\x00\x00\xba\x05\x00\x00\x00\n\x00\x00\x00\xb9\x05\x00\x00\xf4$\x00\x00\x00\xad\x05\x00\x00\xdc(\x00\x00\x00\xa2\x05\x00\x00\x0c0\x00\x00\x00\x9f\x05\x00\x00*0\x00\x00\x00\x98\x05\x00\x00\xa0\n\x00\x00\x00\x98\x05\x00\x00\xaa\n\x00\x00\x00\x94\x05\x00\x00\x04\x1f\x00\x00\x00\x8e\x05\x00\x00\xa0\x0f\x00\x00\x00\x8d\x05\x00\x00\xd40\x00\x00\x00\x8d\x05\x00\x00\xde0\x00\x00\x00\x8d\x05\x00\x00\xe80\x00\x00\x00\x8d\x05\x00\x00\xf20\x00\x00\x00\x86\x05\x00\x004!\x00\x00\x00\x82\x05\x00\x00\x160\x00\x00\x00}\x05\x00\x00\x10\'\x00\x00\x00y\x05\x00\x00x\x05\x00\x00\x00x\x05\x00\x00P\x00\x00\x00\x00x\x05\x00\x00\n\x00\x00\x00\x00s\x05\x00\x00\x8a/\x00\x00\x00s\x05\x00\x00\x94/\x00\x00\x00s\x05\x00\x00\x9e/\x00\x00\x00s\x05\x00\x00D/\x00\x00\x00s\x05\x00\x00N/\x00\x00\x00s\x05\x00\x00X/\x00\x00\x00s\x05\x00\x00b/\x00\x00\x00s\x05\x00\x00l/\x00\x00\x00s\x05\x00\x00v/\x00\x00\x00s\x05\x00\x00\x80/\x00\x00\x00r\x05\x00\x00\x1c%\x00\x00\x00r\x05\x00\x00&%\x00\x00\x00n\x05\x00\x00\xfa\n\x00\x00\x00m\x05\x00\x00\xf0\n\x00\x00\x00c\x05\x00\x00\xc0+\x00\x00\x00Y\x05\x00\x00\x92\x18\x00\x00\x00M\x05\x00\x00\xc8(\x00\x00\x00a\x05\x00\x00@\x1f\x00\x00\x00a\x05\x00\x00\x8a\x1b\x00\x00\x00a\x05\x00\x00\x12\x1b\x00\x00\x00a\x05\x00\x00^\x1f\x00\x00\x00a\x05\x00\x00\xa8\x1b\x00\x00\x00a\x05\x00\x00b\x1b\x00\x00\x00a\x05\x00\x00\xe0\x1a\x00\x00\x00a\x05\x00\x00\x90\x1f\x00\x00\x00a\x05\x00\x00l\x1b\x00\x00\x00`\x05\x00\x00~\x18\x00\x00\x00`\x05\x00\x00L\x18\x00\x00\x00`\x05\x00\x00T\x06\x00\x00\x00`\x05\x00\x00r\x0b\x00\x00\x00`\x05\x00\x00V\x18\x00\x00\x00`\x05\x00\x00\xae\x0b\x00\x00\x00`\x05\x00\x00^\x06\x00\x00\x00`\x05\x00\x00\x9a\x06\x00\x00\x00`\x05\x00\x00h\x06\x00\x00\x00`\x05\x00\x00@\x06\x00\x00\x00`\x05\x00\x00T\x0b\x00\x00\x00`\x05\x00\x00j\x18\x00\x00\x00`\x05\x00\x00^\x0b\x00\x00\x00`\x05\x00\x00\x86\x06\x00\x00\x00`\x05\x00\x008\x18\x00\x00\x00`\x05\x00\x00h\x0b\x00\x00\x00`\x05\x00\x00t\x18\x00\x00\x00`\x05\x00\x00J\x06\x00\x00\x00`\x05\x00\x00B\x18\x00\x00\x00O\x05\x00\x00\xdc\x05\x00\x00\x00O\x05\x00\x00\xf0\x05\x00\x00\x00O\x05\x00\x00\xde\x05\x00\x00\x00O\x05\x00\x00\xf2\x05\x00\x00\x00O\x05\x00\x00\xe6\x05\x00\x00\x00L\x05\x00\x00\xbe(\x00\x00\x00N\x05\x00\x00\xb8$\x00\x00\x00J\x05\x00\x00\xb6\r\x00\x00\x00I\x05\x00\x00\xba,\x00\x00\x00E\x05\x00\x00\xf6\x1d\x00\x00\x00;\x05\x00\x002\n\x00\x00\x004\x05\x00\x00\xb6\x12\x00\x00\x004\x05\x00\x00\xa0(\x00\x00\x005\x05\x00\x00\xd7\x00\x00\x00\x00+\x05\x00\x00\x1a\'\x00\x00\x00*\x05\x00\x00\x1e\x1e\x00\x00\x00\x1a\x05\x00\x00*\r\x00\x00\x00\x1a\x05\x00\x00\x8e\r\x00\x00\x00\x18\x05\x00\x00\xc4\t\x00\x00\x00\x18\x05\x00\x00\xce\t\x00\x00\x00\x1c\x05\x00\x00,\x01\x00\x00\x00\x1c\x05\x00\x00\xf0\x00\x00\x00\x00\x16\x05\x00\x00P\n\x00\x00\x00\x16\x05\x00\x00<\n\x00\x00\x00\x16\x05\x00\x00F\n\x00\x00\x00\x14\x05\x00\x00L\x1d\x00\x00\x00\xa0\x04\x00\x00\xcc\x0b\x00\x00\x00\x0f\x05\x00\x00\xca+\x00\x00\x00\x0f\x05\x00\x00\x1e\n\x00\x00\x00\x0f\x05\x00\x00\x8d\x13\x00\x00\x00\x0b\x05\x00\x00\x12 \x00\x00\x00\x0b\x05\x00\x00& \x00\x00\x00\x0b\x05\x00\x000 \x00\x00\x00\x0b\x05\x00\x00: \x00\x00\x00\x0b\x05\x00\x00\x08 \x00\x00\x001\x04\x00\x00\x1c \x00\x00\x00\xfb\x04\x00\x00\x8a\x0c\x00\x00\x00\xfb\x04\x00\x00\xc6\x0c\x00\x00\x00\xfb\x04\x00\x00\xd0\x0c\x00\x00\x00\xfb\x04\x00\x00\x80\x0c\x00\x00\x00\xf7\x04\x00\x00\xce,\x00\x00\x00\xf3\x04\x00\x00\x9c,\x00\x00\x00\xef\x04\x00\x00\x96\x0f\x00\x00\x00\xef\x04\x00\x00\xba\x1d\x00\x00\x00\xef\x04\x00\x00\xc4\x1d\x00\x00\x00\xef\x04\x00\x00`"\x00\x00\x00\xef\x04\x00\x00t"\x00\x00\x00\xef\x04\x00\x00\x82\x0f\x00\x00\x00\xed\x04\x00\x00\xac\r\x00\x00\x00\xe4\x04\x00\x00\xc2\x10\x00\x00\x00\xd5\x04\x00\x00\x18\x01\x00\x00\x00\xd7\x04\x00\x00<\x0f\x00\x00\x00\xa8\x04\x00\x00R\x1c\x00\x00\x00\x9f\x04\x00\x00h\x1f\x00\x00\x00\xa2\x04\x00\x00\x9b\r\x00\x00\x00\x9d\x04\x00\x00\xde\x12\x00\x00\x00\x9d\x04\x00\x00\x94\x11\x00\x00\x00\x98\x04\x00\x00\x82\n\x00\x00\x00\x9a\x04\x00\x00\xbc\x0c\x00\x00\x00\x99\x04\x00\x00\xb0\x04\x00\x00\x00\x94\x04\x00\x00\xac\x12\x00\x00\x00\x94\x04\x00\x00\\\x12\x00\x00\x00\x94\x04\x00\x00f\x12\x00\x00\x00\x94\x04\x00\x00\x84\x12\x00\x00\x00\x94\x04\x00\x00\x98\x12\x00\x00\x00\x94\x04\x00\x00\xa2\x12\x00\x00\x00\x91\x04\x00\x00\xaa\x19\x00\x00\x00\x8a\x04\x00\x00\xac!\x00\x00\x00\x84\x04\x00\x00\x8c\x19\x00\x00\x00\x84\x04\x00\x00n\x19\x00\x00\x00\x84\x04\x00\x00\x82\x19\x00\x00\x00\x7f\x04\x00\x00\xda\x11\x00\x00\x00\x7f\x04\x00\x00\xe4\x11\x00\x00\x00i\x04\x00\x00\x9e\x0c\x00\x00\x00u\x04\x00\x00\x98\x08\x00\x00\x00u\x04\x00\x00Z#\x00\x00\x00u\x04\x00\x00\xde\x08\x00\x00\x00u\x04\x00\x00d#\x00\x00\x00u\x04\x00\x00\xfc\x08\x00\x00\x00u\x04\x00\x00n#\x00\x00\x00u\x04\x00\x00\x06\t\x00\x00\x00u\x04\x00\x00x#\x00\x00\x00u\x04\x00\x00\x10\t\x00\x00\x00u\x04\x00\x00\x82#\x00\x00\x00u\x04\x00\x00\x1a\t\x00\x00\x00u\x04\x00\x00\x8c#\x00\x00\x00u\x04\x00\x00$\t\x00\x00\x00u\x04\x00\x00\xa0#\x00\x00\x00u\x04\x00\x00.\t\x00\x00\x00u\x04\x00\x00\xaa#\x00\x00\x00u\x04\x00\x008\t\x00\x00\x00u\x04\x00\x00B\t\x00\x00\x00u\x04\x00\x002#\x00\x00\x00u\x04\x00\x00F#\x00\x00\x00u\x04\x00\x00P#\x00\x00\x00h\x04\x00\x00\x94\x0c\x00\x00\x00[\x04\x00\x00\xa8\x11\x00\x00\x00[\x04\x00\x00\xb2\x11\x00\x00\x00[\x04\x00\x00\xbc\x11\x00\x00\x00[\x04\x00\x00\xc6\x11\x00\x00\x00[\x04\x00\x00\x9e\x11\x00\x00\x00J\x04\x00\x00\x14\x19\x00\x00\x00X\x04\x00\x00\n\n\x00\x00\x00O\x04\x00\x00\xee\x0c\x00\x00\x00O\x04\x00\x00p\r\x00\x00\x00O\x04\x00\x00 \r\x00\x00\x00O\x04\x00\x00H\r\x00\x00\x00O\x04\x00\x00\xf8\x0c\x00\x00\x00O\x04\x00\x00z\r\x00\x00\x00O\x04\x00\x00R\r\x00\x00\x00O\x04\x00\x00\x02\r\x00\x00\x00O\x04\x00\x00\x84\r\x00\x00\x00O\x04\x00\x00\\\r\x00\x00\x00O\x04\x00\x00\x0c\r\x00\x00\x00O\x04\x00\x004\r\x00\x00\x00O\x04\x00\x00\x98\r\x00\x00\x00O\x04\x00\x00\xe4\x0c\x00\x00\x00O\x04\x00\x00\xa2\r\x00\x00\x00O\x04\x00\x00\x16\r\x00\x00\x00O\x04\x00\x00>\r\x00\x00\x00H\x04\x00\x00\xea\x03\x00\x00\x00H\x04\x00\x00\xeb\x03\x00\x00\x00H\x04\x00\x00\xd8\t\x00\x00\x00H\x04\x00\x00\xe2\t\x00\x00\x00H\x04\x00\x00\xd4\x17\x00\x00\x00H\x04\x00\x00\xd0 \x00\x00\x00H\x04\x00\x00\xe7\t\x00\x00\x00F\x04\x00\x00\xc2\x1a\x00\x00\x00F\x04\x00\x00\xcc\x1a\x00\x00\x00F\x04\x00\x00&\x1b\x00\x00\x00F\x04\x00\x00\xf4\x1a\x00\x00\x00*\x04\x00\x00\xdc\x1e\x00\x00\x00*\x04\x00\x00\xe6\x1e\x00\x00\x008\x04\x00\x00D\x11\x00\x00\x006\x04\x00\x00 \x1c\x00\x00\x00/\x04\x00\x00\x96\x19\x00\x00\x00\x1d\x04\x00\x00\xb8\x1a\x00\x00\x00\x1d\x04\x00\x00\x1c\x1b\x00\x00\x00\x1d\x04\x00\x00\xd6\x1a\x00\x00\x00\x1d\x04\x00\x00\xa4\x1a\x00\x00\x00\x17\x04\x00\x00J\x1f\x00\x00\x00\x13\x04\x00\x00\x82\x1e\x00\x00\x00\x11\x04\x00\x00x\x1e\x00\x00\x00\x0b\x04\x00\x00\xfc\x1c\x00\x00\x00\x07\x04\x00\x00\x94\x1b\x00\x00\x00\x04\x04\x00\x00\xb0\x1d\x00\x00\x00\x03\x04\x00\x00\xe2\x1d\x00\x00\x00\xff\x03\x00\x00\xa6\x18\x00\x00\x00\xfb\x03\x00\x00(\x00\x00\x00\x00\xfb\x03\x00\x00\x14\x00\x00\x00\x00\xf8\x03\x00\x00x\n\x00\x00\x00\xf2\x03\x00\x00\x8c\x0f\x00\x00\x00\xf0\x03\x00\x00\xa4\x06\x00\x00\x00\xec\x03\x00\x00v\x1b\x00\x00\x00\xec\x03\x00\x00\xfe\x1a\x00\x00\x00\xec\x03\x00\x00D\x1b\x00\x00\x00\xec\x03\x00\x00\x08\x1b\x00\x00\x00\xec\x03\x00\x00N\x1b\x00\x00\x00\xec\x03\x00\x00X\x1b\x00\x00\x00\xec\x03\x00\x000\x1b\x00\x00\x00\xec\x03\x00\x00:\x1b\x00\x00\x00\xeb\x03\x00\x00t\t\x00\x00\x00\xe9\x03\x00\x00\xf8\x11\x00\x00\x00\xe9\x03\x00\x00\x02\x12\x00\x00\x00\xe5\x03\x00\x00h\x01\x00\x00\x00\xe1\x03\x00\x00$\x13\x00\x00\x00\xda\x03\x00\x00\x90\x1a\x00\x00\x00\xda\x03\x00\x00\x9a\x1a\x00\x00\x00\xda\x03\x00\x00\xae\x1a\x00\x00\x00\xcb\x03\x00\x00F\x00\x00\x00\x00\xc4\x03\x00\x00\xc8\x19\x00\x00\x00\xc4\x03\x00\x00\xd2\x19\x00\x00\x00\xc1\x03\x00\x004\x08\x00\x00\x00\x8d\x03\x00\x00\x1e\x00\x00\x00\x00m\x03\x00\x00\xcc\x10\x00\x00\x00f\x03\x00\x00\xc0\x12\x00\x00\x00%\x03\x00\x00H\x08\x00\x00\x00!\x03\x00\x00F\x0f\x00\x00\x00!\x03\x00\x00\xce\x1d\x00\x00\x00!\x03\x00\x00P\x0f\x00\x00\x00!\x03\x00\x00x\x0f\x00\x00\x00\x12\x03\x00\x00\x04\x10\x00\x00\x00\x0c\x03\x00\x000\x11\x00\x00\x00\x0b\x03\x00\x00\xf6\x0e\x00\x00\x00\x0b\x03\x00\x00\x00\x0f\x00\x00\x00\xee\x02\x00\x00\xd3\x00\x00\x00\x00\xde\x02\x00\x00f\r\x00\x00\x00\xda\x02\x00\x00\xb8\x0b\x00\x00\x00\xda\x02\x00\x00\xc2\x0b\x00\x00\x00\xc5\x02\x00\x00\x14\x05\x00\x00\x00\x8b\x02\x00\x00l\x07\x00\x00\x00D\x02\x00\x00\x1d\x05\x00\x00\x00D\x02\x00\x00!\x05\x00\x00\x00\x02\x02\x00\x00\x82\x00\x00\x00\x00\xe1\x01\x00\x002\x00\x00\x00\x00\xe1\x01\x00\x00<\x00\x00\x00\x00\t\x01\x00\x00\\\x00\x00\x00'
"""

    return packet


def build_system_message(client_obj, msg_type: SystemIMType, message_body: str = "", ack_required: bool = False, message_id: int = None):
    """
    Build a SystemIM message for various system notifications.
    
    Args:
        client_obj: The client object
        msg_type: SystemIMType enum value (e.g., guestPassReceived, guestPassGranted)
        message_body: The message text to display
        ack_required: Whether client acknowledgment is required
        message_id: Unique message ID (auto-generated if None)
    
    Returns:
        CMResponse packet
    """
    from steam3.messages.MsgClientSystemIM import MsgClientSystemIM
    import time
    
    packet = CMResponse(eMsgID=EMsg.ClientSystemIM, client_obj=client_obj)
    
    # Generate unique message ID if not provided
    if message_id is None:
        message_id = int(time.time() * 1000000)  # Microsecond timestamp
    
    # Create SystemIM message
    system_im = MsgClientSystemIM(
        system_im_type=int(msg_type),
        message_body=message_body,
        ack_required=ack_required,
        message_id=message_id
    )
    
    packet.data = system_im.serialize()
    packet.length = len(packet.data)
    
    return packet


def build_guest_pass_received_notification(client_obj, sender_name: str, package_name: str = ""):
    """
    Build a SystemIM notification for when a user receives a guest pass.
    
    Args:
        client_obj: The receiving client
        sender_name: Name of the user who sent the guest pass
        package_name: Name of the package/game (optional)
    
    Returns:
        CMResponse packet
    """
    if package_name:
        message = f"You have received a guest pass for {package_name} from {sender_name}."
    else:
        message = f"You have received a guest pass from {sender_name}."
    
    return build_system_message(
        client_obj,
        SystemIMType.guestPassReceived,
        message,
        ack_required=True
    )


def build_guest_pass_granted_notification(client_obj, recipient_name: str, package_name: str = ""):
    """
    Build a SystemIM notification for when a user's guest pass is granted/activated.
    
    Args:
        client_obj: The client who granted the pass
        recipient_name: Name of the recipient
        package_name: Name of the package/game (optional)
    
    Returns:
        CMResponse packet
    """
    if package_name:
        message = f"Your guest pass for {package_name} has been granted to {recipient_name}."
    else:
        message = f"Your guest pass has been granted to {recipient_name}."
    
    return build_system_message(
        client_obj,
        SystemIMType.guestPassGranted,
        message,
        ack_required=True
    )


def build_cmlist_response(client_obj, proto=False):
    """
    Build a CMList response packet with eMsgID 0x030F.

    :param client_obj: The Client object.
    :param proto: Whether to use protobuf format (True) or binary format (False).
    :return: A CMResponse or CMProtoResponse instance.
    """
    from steam3.messages.responses.MsgClientCMList import CMListResponse

    response = CMListResponse(client_obj)
    response.add_ip_addresses_for_client()

    if proto:
        return response.to_protobuf()
    else:
        return response.to_clientmsg()


def build_ClientEncryptPct_response(client_obj):
    """
    Build a chat eMsgID packet with eMsgID 0x0310.

    :param client_obj: The Client object.
    :return: A ChatCommandPacket instance.

    NOTE:
    between when clients started forcing encryption and 08/12/2007, official steam sent: \x64\x00\x00\x00
    """
    packet = CMResponse(eMsgID = EMsg.ClientEncryptPct, client_obj = client_obj)

    packet.data = struct.pack('<I',
                              0)  # always 0

    return packet


def build_General_response(client_obj, eResult):
    """
    Generic reply

    :param client_obj: The Client object.
    :return: A ChatCommandPacket instance.
    """
    packet = CMResponse(eMsgID = EMsg.GenericReply, client_obj = client_obj)

    packet.data = struct.pack('<I',
                              eResult)

    return packet


def build_GeneralAck(client_obj, packet, client_address, cmserver_obj, eresult = b''):

    if not cmserver_obj.is_tcp:  # TCP
        """ packet = CMResponse(eMsgID = EMsg.GenericReply, client_obj = client_obj)

        packet.data = struct.pack('<I', 1)
        packet.length = len(packet.data)
        cmserver_obj.sendReply(client_obj, [packet])
        else:  # UDP"""
        packet_reply = copy.copy(packet)
        packet_reply.packetid = b'\x07'
        packet_reply.size = 0
        packet_reply.data_len = 0
        packet_reply.destination_id = packet.source_id
        packet_reply.source_id = packet.destination_id  # Swap .to and .from_
        packet_reply.last_recv_seq = packet.sequence_num
        packet_reply.sequence_num = 0
        packet_reply.split_pkt_cnt = 0
        packet_reply.seq_of_first_pkt = 0
        packet_reply.data = eresult  # Assuming data should be an empty bytes object

        # Serialize the packet
        packet = packet_reply.serialize()

        cmserver_obj.socket.sendto(packet, client_address)


def build_ClientMarketingMessageUpdate(client_obj):
    """
    Build a marketing message update packet.

    Uses MsgClientMarketingMessageUpdate2 (EMsg 5510) for CDR dates June 2010 or later,
    otherwise uses MsgClientMarketingMessageUpdate (EMsg 5420).

    Queries the MarketingMessages database table for 3-5 messages closest to
    and not past the CDR date.
    """
    from steam3 import database

    # Default fallback message IDs from 07/02/2009 16:06:06
    fallback_gids = [
        18162464089635255,
        18162464022650639,
        18162464324102804,
        18162464299885654,
        18162464076565563,
    ]

    # Parse CDR date to determine which message format to use
    cdr_datetime_str = getattr(globalvars, 'CDDB_datetime', None)
    use_v2 = False

    if cdr_datetime_str:
        try:
            cdr_date = datetime.strptime(cdr_datetime_str, "%m/%d/%Y %H:%M:%S")
            # Use v2 format if CDR date is June 2010 or later
            cutoff_date = datetime(2010, 6, 1)
            use_v2 = cdr_date >= cutoff_date
        except ValueError as e:
            log.warning(f"Failed to parse CDR datetime '{cdr_datetime_str}': {e}")

    # Query database for marketing messages
    gids = []
    if cdr_datetime_str:
        try:
            gids = database.get_marketing_messages_by_date(cdr_datetime_str, count=5)
        except Exception as e:
            log.warning(f"Failed to query marketing messages from database: {e}")

    # Use fallback if no messages found
    if not gids:
        log.debug("Using fallback marketing message GIDs")
        gids = fallback_gids

    if use_v2:
        # Use MarketingMessageUpdate2 format (with flags)
        packet = CMResponse(eMsgID=EMsg.ClientMarketingMessageUpdate2, client_obj=client_obj)
        msg_update = MsgClientMarketingMessageUpdate2()
        for gid in gids:
            msg_update.add_marketing_message(gid, flags=0)
    else:
        # Use original MarketingMessageUpdate format
        packet = CMResponse(eMsgID=EMsg.ClientMarketingMessageUpdate, client_obj=client_obj)
        msg_update = MsgClientMarketingMessageUpdate()
        for gid in gids:
            msg_update.add_marketing_message(gid)

    # Serialize the packet
    packet.data = msg_update.serialize()

    return packet


def build_ClientRequestValidationMail_Response(client_obj, eresult):

    packet = CMResponse(eMsgID = EMsg.ClientRequestValidationMailResponse, client_obj = client_obj)

    packet.data = struct.pack('<I',
                              eresult)

    return packet


def build_ClientServersAvailable(client_obj):
    try:
        packet = CMResponse(eMsgID = EMsg.ClientServersAvailable, client_obj = client_obj)
        message = MsgClientServersAvailable()
        message.add_server(EServerType.AM)
        message.add_server(EServerType.CM)
        message.add_server(EServerType.Shell)
        message.add_server(EServerType.UFS)
        message.add_server(EServerType.MMS)
        message.add_server(EServerType.GMS)
        message.add_server(EServerType.GM)
        message.add_server(EServerType.UDS)
        message.add_server(EServerType.DP)
        message.add_server(EServerType.Econ)
        message.add_server(EServerType.GC)
        message.add_server(EServerType.DRMS)
        message.add_server(EServerType.contentstats)
        message.add_server(EServerType.PICS)
        message.add_server(EServerType.LBS)
        message.add_server(EServerType.AppInformation)
        message.add_server(EServerType.WG)
        message.add_server(EServerType.FS)
        message.add_server(EServerType.FTS)
        message.add_server(EServerType.Seeder)
        message.add_server(EServerType.SLC)
        message.add_server(EServerType.VS)
        message.add_server(EServerType.FBS)
        message.add_server(EServerType.FG)
        message.add_server(EServerType.Console)
        message.add_server(EServerType.SM)
        message.add_server(EServerType.Community) # Same as DSS
        message.add_server(EServerType.ATS)
        message.add_server(EServerType.Client)
        message.add_server(EServerType.CS)
        message.add_server(EServerType.BS)
        message.add_server(EServerType.SS)
        message.add_server(EServerType.PS)
        message.add_server(EServerType.IS)
        message.add_server(EServerType.EPM)
        message.add_server(EServerType.OGS)
        # 2010 servers
        message.add_server(EServerType.MPAS)
        message.add_server(EServerType.GCH)

        message.add_server(EServerType.UCM)
        message.add_server(EServerType.Trade)
        message.add_server(EServerType.CRE)
        message.add_server(EServerType.UGSAggregate)
        message.add_server(EServerType.Quest)
        message.add_server(EServerType.Steam2Emulator)
        packet.data = message.serialize()

        packet.length = len(packet.data)
        return packet
    except Exception as e:
        traceback.print_exc()
        print(e)
        return -1


def build_MsgClientServerList(client_obj):
    try:
        # Initialize the message using the MsgClientServerList class
        server_list_msg = MsgClientServerList(client_obj)

        # Add servers to the list
        server_list_msg.add_server(EServerType.AM, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.CM, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.UFS, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.MMS, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.GMS, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.UDS, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.DP, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.Econ, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.GC, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.DRMS, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.contentstats, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.PICS, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.LBS, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.AppInformation, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.WG, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.FS, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.VS, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.Shell, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.GM, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.Seeder, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.SLC, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.SM, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.Console, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.Community, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.ATS, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.Client, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.CS, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.CCS, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.BS, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.DFS, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.PS, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.IS, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.FTS, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.EPM, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.OGS, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.FBS, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.FG, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.SS, globalvars.server_ip, 27017)
        # 2010 servers
        server_list_msg.add_server(EServerType.MPAS, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.GCH, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.UCM, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.Trade, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.CRE, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.UGSAggregate, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.Quest, globalvars.server_ip, 27017)
        server_list_msg.add_server(EServerType.Steam2Emulator, globalvars.server_ip, 27017)

        # Return the proper CMResponse packet
        return server_list_msg.to_clientmsg()

    except Exception as e:
        traceback.print_exc()
        print(e)
        return -1

def build_MsgClientRequestedStats(client_obj):
    packet = CMResponse(eMsgID=EMsg.ClientRequestedClientStats, client_obj=client_obj)

    message = MsgClientRequestedClientStats()
    message.add_requested_stats(ClientStat.p2pConnectionsUDP)
    message.add_requested_stats(ClientStat.p2pConnectionsRelay)
    message.add_requested_stats(ClientStat.p2pGamesConnections)
    message.add_requested_stats(ClientStat.p2pVoiceConnections)
    message.add_requested_stats(ClientStat.p2pBytesDownloaded)
    packet.data = message.serialize()
    packet.length = len(packet.data)

    return packet