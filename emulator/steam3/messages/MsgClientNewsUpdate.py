import struct
from io import BytesIO
from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse


class MsgClientNewsUpdate:
    """
    Message for sending news updates to the client.
    Based on decompiled CClientJobNewsItemUpdateMsg::BYieldingRunClientJob analysis.

    Message format:
    - Header: m_usNumNewsUpdates (uint16, 2 bytes)
    - For each news item:
      - eNewsUpdateType (uint8, 1 byte)
      - Data structure based on type:

    Supports multiple news update types (ENewsUpdateType enum):
    - Type 0: k_EAppNews - App news updates (AppNewsItemUpdate_t, 8 bytes)
      ClientAppNewsItemUpdate_t callback with m_uNewsID, m_uAppID
    - Type 1: k_ESteamAds - Steam ads (SteamNewsItemUpdate_t, 28 bytes = 0x1C)
      ClientSteamNewsItemUpdate_t callback with filtering conditions
    - Type 2: k_ESteamNews - Steam news (SteamNewsItemUpdate_t, 28 bytes = 0x1C)
      ClientSteamNewsItemUpdate_t callback with filtering conditions
    - Type 3: k_ECDDBUpdate - CDDB update (structure unknown)
    - Type 4: k_EClientUpdate - Client updates (SteamNewsClientUpdate_t, 14 bytes)
      ClientSteamNewsClientUpdate_t callback for client version updates
    """
    
    def __init__(self, client_obj, data=None):
        self.client_obj = client_obj
        self.m_usNumNewsUpdates = 0
        self.news_items = []
        
        if data is not None:
            self.deserialize(data)
    
    def deserialize(self, data):
        """Deserialize news update packet data
        
        Args:
            data (bytes): Binary packet data to deserialize
            
        Raises:
            struct.error: If data is malformed or incomplete
        """
        import struct
        offset = 0
        
        # Read header: number of news updates
        if len(data) < 2:
            raise struct.error("Insufficient data for news update header")
            
        self.m_usNumNewsUpdates = struct.unpack_from('<H', data, offset)[0]
        offset += 2
        
        # Read each news item
        self.news_items = []
        for i in range(self.m_usNumNewsUpdates):
            if offset >= len(data):
                raise struct.error(f"Insufficient data for news item {i}")
                
            # Read news type
            news_type = struct.unpack_from('<B', data, offset)[0]
            offset += 1
            
            if news_type == 0:
                # AppNewsItemUpdate_t (8 bytes)
                if offset + 8 > len(data):
                    raise struct.error("Insufficient data for app news update")
                news_id, app_id = struct.unpack_from('<II', data, offset)
                offset += 8
                self.news_items.append({
                    'type': 0,
                    'news_id': news_id,
                    'app_id': app_id
                })
                
            elif news_type in [1, 2]:
                # SteamNewsItemUpdate_t (28 bytes)
                if offset + 28 > len(data):
                    raise struct.error("Insufficient data for steam news update")
                fields = struct.unpack_from('<IIIIIII', data, offset)
                offset += 28
                self.news_items.append({
                    'type': news_type,
                    'news_id': fields[0],
                    'have_sub_id': fields[1],
                    'not_have_sub_id': fields[2],
                    'have_app_id': fields[3],
                    'not_have_app_id': fields[4],
                    'have_app_id_installed': fields[5],
                    'have_played_app_id': fields[6]
                })
                
            elif news_type == 4:
                # SteamNewsClientUpdate_t (13 bytes = 0xD)
                if offset + 13 > len(data):
                    raise struct.error("Insufficient data for client update")
                fields = struct.unpack_from('<IIIB', data, offset)
                offset += 13
                self.news_items.append({
                    'type': 4,
                    'news_id': fields[0],
                    'steam_version': fields[1],       # m_unCurrentBootstrapperVersion
                    'steamui_version': fields[2],     # m_unCurrentClientVersion
                    'reload_cddb': bool(fields[3])
                })
                
            else:
                raise struct.error(f"Unknown news update type: {news_type}")
        
        # Update counter to match parsed items
        self.m_usNumNewsUpdates = len(self.news_items)
    
    def add_app_news_update(self, news_id, app_id):
        """Add type 0 (k_EAppNews - app news) update
        
        Creates AppNewsItemUpdate_t structure (8 bytes):
        - m_uNewsID (uint32): News item identifier
        - m_uAppID (uint32): Application/game identifier
        
        Args:
            news_id (int): News item identifier
            app_id (int): Application/game identifier for the news
        """
        news_item = {
            'type': 0,
            'news_id': news_id,
            'app_id': app_id
        }
        self.news_items.append(news_item)
        self.m_usNumNewsUpdates += 1
    
    def add_steam_news_item_update(self, news_id, have_sub_id=0, not_have_sub_id=0,
                                   have_app_id=0, not_have_app_id=0,
                                   have_app_id_installed=0, have_played_app_id=0, update_type=1):
        """Add type 1-2 (k_ESteamAds/k_ESteamNews - steam news item) update
        
        Creates SteamNewsItemUpdate_t structure (28 bytes = 0x1C):
        - m_uNewsID (uint32): News item identifier
        - m_uHaveSubID (uint32): Show only if client has this subscription ID
        - m_uNotHaveSubID (uint32): Show only if client doesn't have this subscription ID  
        - m_uHaveAppID (uint32): Show only if client owns this app ID
        - m_uNotHaveAppID (uint32): Show only if client doesn't own this app ID
        - m_uHaveAppIDInstalled (uint32): Show only if client has this app installed
        - m_uHavePlayedAppID (uint32): Show only if client has played this app
        
        Args:
            news_id (int): News item identifier
            have_sub_id (int): Filter - show only if client has subscription
            not_have_sub_id (int): Filter - show only if client lacks subscription
            have_app_id (int): Filter - show only if client owns app
            not_have_app_id (int): Filter - show only if client doesn't own app
            have_app_id_installed (int): Filter - show only if app is installed
            have_played_app_id (int): Filter - show only if client played app
            update_type (int): News update type (1 or 2)
        """
        news_item = {
            'type': update_type,  # 1 or 2
            'news_id': news_id,
            'have_sub_id': have_sub_id,
            'not_have_sub_id': not_have_sub_id,
            'have_app_id': have_app_id,
            'not_have_app_id': not_have_app_id,
            'have_app_id_installed': have_app_id_installed,
            'have_played_app_id': have_played_app_id
        }
        self.news_items.append(news_item)
        self.m_usNumNewsUpdates += 1
    
    def add_client_update(self, news_id, steam_version, steamui_version, reload_cddb=True):
        """Add type 4 (k_EClientUpdate - client update)

        Creates SteamNewsClientUpdate_t structure (13 bytes = 0xD):
        - m_uNewsID (uint32): News item identifier
        - m_unCurrentBootstrapperVersion (uint32): Steam/bootstrapper version
        - m_unCurrentClientVersion (uint32): SteamUI/client version
        - m_bReloadCDDB (uint8): Whether to reload CDDB

        Args:
            news_id (int): News ID for the client update
            steam_version (int): Steam/bootstrapper version (m_unCurrentBootstrapperVersion)
            steamui_version (int): SteamUI/client version (m_unCurrentClientVersion)
            reload_cddb (bool): Whether to reload CDDB after update
        """
        news_item = {
            'type': 4,
            'news_id': news_id,
            'steam_version': steam_version,
            'steamui_version': steamui_version,
            'reload_cddb': reload_cddb
        }
        self.news_items.append(news_item)
        self.m_usNumNewsUpdates += 1
    
    def to_clientmsg(self):
        """Build the CMResponse packet
        
        Creates binary packet matching the format expected by 
        CClientJobNewsItemUpdateMsg::BYieldingRunClientJob:
        
        Packet structure:
        - m_usNumNewsUpdates (uint16): Number of news items
        - For each news item:
          - eNewsUpdateType (uint8): News type (0, 1, 2, or 4) 
          - Variable data based on type
        
        Returns:
            CMResponse: Packet ready to send to client
        """
        packet = CMResponse(EMsg.ClientNewsUpdate, self.client_obj)
        buffer = BytesIO()
        
        # Write header with number of news updates (uint16)
        buffer.write(struct.pack('<H', self.m_usNumNewsUpdates))
        
        # Write each news item
        for news_item in self.news_items:
            news_type = news_item['type']
            
            # Validate news type
            if news_type not in [0, 1, 2, 4]:
                raise ValueError(f"Invalid news update type: {news_type}")
                
            buffer.write(struct.pack('<B', news_type))
            
            if news_type == 0:
                # k_EAppNews - AppNewsItemUpdate_t (8 bytes)
                buffer.write(struct.pack('<II',
                    news_item['news_id'],
                    news_item['app_id']
                ))

            elif news_type in [1, 2]:
                # k_ESteamAds/k_ESteamNews - SteamNewsItemUpdate_t (28 bytes = 0x1C)
                buffer.write(struct.pack('<IIIIIII',
                    news_item['news_id'],
                    news_item['have_sub_id'],
                    news_item['not_have_sub_id'],
                    news_item['have_app_id'],
                    news_item['not_have_app_id'],
                    news_item['have_app_id_installed'],
                    news_item['have_played_app_id']
                ))

            elif news_type == 4:
                # k_EClientUpdate - SteamNewsClientUpdate_t (14 bytes total)
                # struct BaseNewsItemUpdate_t:
                #   uint8 m_eNewsUpdateType;          (1 byte) - written above on line 223
                #   uint32 m_uNewsID;                 (4 bytes) - written below
                # struct SteamNewsClientUpdate_t : BaseNewsItemUpdate_t:
                #   uint32 m_unCurrentBootstrapperVersion;  (4 bytes)
                #   uint32 m_unCurrentClientVersion;        (4 bytes)
                #   uint8 m_bReloadCDDB;                    (1 byte)
                buffer.write(struct.pack('<IIIB',
                    news_item['news_id'],                        # m_uNewsID (BaseNewsItemUpdate_t)
                    news_item['steam_version'],                  # m_unCurrentBootstrapperVersion
                    news_item['steamui_version'],                # m_unCurrentClientVersion
                    1 if news_item['reload_cddb'] else 0         # m_bReloadCDDB
                ))
        
        packet.data = buffer.getvalue()
        packet.length = len(packet.data)
        return packet
    
    def __repr__(self):
        return f"MsgClientNewsUpdate(num_updates={self.m_usNumNewsUpdates}, items={len(self.news_items)})"