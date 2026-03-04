import struct
from typing import List
from datetime import datetime, timedelta

import globalvars
from steam3.Types.Constants import news_updates


class NewsManager:
    def __init__(self):
        self.news_entries: List[bytes] = []

    def create_appnews(self, appid: int, newsid: int) -> None:
        """
        Packs the app news entry (type 0 / k_EAppNews).

        Structure (9 bytes total):
        - eNewsUpdateType (uint8): 0
        - m_uNewsID (uint32): News ID
        - m_uAppID (uint32): Application ID
        """
        newstype = 0
        buffer = struct.pack('<BII', newstype, newsid, appid)
        self.news_entries.append(buffer)

    def create_adnews_2005(self, news_str: str) -> None:
        """
        Packs 1 as a byte, followed by the news_str (ensuring it's less than 255 bytes including null terminator),
        and adds it to the news entries.
        """
        if len(news_str) >= 255:
            raise ValueError("String is too long to fit in the buffer")
        if news_str[-1] != '\0':
            news_str += '\0'

        packed_str = news_str.encode('latin-1')
        buffer = struct.pack('B', 1) + packed_str
        self.news_entries.append(buffer)

    def create_steamnews(self, newsID: int, haveSubID: int, notHaveSubID: int, haveAppID: int, notHaveAppID: int, haveAppIDInstalled: int, havePlayedAppID: int, isAd: bool) -> None:
        """
        Packs the Steam news entry (type 1 = k_ESteamAds or type 2 = k_ESteamNews).

        Structure (29 bytes total):
        - eNewsUpdateType (uint8): 1 (ad) or 2 (news)
        - m_uNewsID (uint32): News ID
        - m_uHaveSubID (uint32): Show only if user has this subscription
        - m_uNotHaveSubID (uint32): Show only if user doesn't have this subscription
        - m_uHaveAppID (uint32): Show only if user owns this app
        - m_uNotHaveAppID (uint32): Show only if user doesn't own this app
        - m_uHaveAppIDInstalled (uint32): Show only if user has this app installed
        - m_uHavePlayedAppID (uint32): Show only if user has played this app
        """
        ad_byte = 1 if isAd else 2
        buffer = struct.pack('<BIIIIIII', ad_byte, newsID, haveSubID, notHaveSubID, haveAppID, notHaveAppID, haveAppIDInstalled, havePlayedAppID)
        self.news_entries.append(buffer)

    def create_clientupdatenews(self, newsID: int, bootstrapVersion: int, clientVersion: int, shouldReloadCDDB: bool) -> None:
        """
        Packs the client update news entry (type 4 / k_EClientUpdate).

        Structure (14 bytes total):
        - eNewsUpdateType (uint8): 4
        - m_uNewsID (uint32): News ID
        - m_unCurrentBootstrapperVersion (uint32): Steam/bootstrapper version
        - m_unCurrentClientVersion (uint32): SteamUI/client version
        - m_bReloadCDDB (uint8): Whether to reload CDR (1 = yes, 0 = no)

        When m_bReloadCDDB is set, client will fetch fresh CDR.
        """
        reload_byte = 1 if shouldReloadCDDB else 0
        buffer = struct.pack('<BIIIB', 4, newsID, bootstrapVersion, clientVersion, reload_byte)
        self.news_entries.append(buffer)

    def serialize(self) -> bytes:
        """
        Serializes the news entries by prepending the news count as uint16 (m_usNumNewsUpdates)
        followed by all news entry byte buffers.

        Packet structure:
        - m_usNumNewsUpdates (uint16): Number of news entries
        - News entries: Variable-length data based on entry types
        """
        news_count = len(self.news_entries)
        # IDA analysis confirms m_usNumNewsUpdates is uint16 (2 bytes)
        news_count_buffer = struct.pack('<H', news_count)
        full_news_buffer = b''.join(self.news_entries)
        return news_count_buffer + full_news_buffer

    # FIXME this is temporary until we have a proper solution for storing these
    @staticmethod
    def find_closest_news_update() -> bytes:
        """
        Find the closest news update entry to the given date and time.

        :param client_news_updates: Dictionary where keys are datetime strings and values are byte data.
        :param target_datetime: The target datetime as a string in the format '%Y-%m-%d %H:%M:%S'.
        :return: The byte data of the closest news update.
        """
        target_datetime = globalvars.current_blob_datetime
        client_news_updates = news_updates.client_news_updates
        # Parse the target date using the known target format
        target_dt = datetime.strptime(target_datetime, '%m/%d/%Y %H:%M:%S')

        # Find the closest date
        closest_date = None
        smallest_diff = timedelta.max

        for key in client_news_updates:
            try:
                # Parse each date in the dictionary using its known format
                entry_dt = datetime.strptime(key, '%Y-%m-%d %H:%M:%S')
                # Calculate the time difference
                diff = abs(entry_dt - target_dt)
                if diff < smallest_diff:
                    smallest_diff = diff
                    closest_date = key
            except ValueError:
                # Skip entries that don't match the format
                continue

        # Return the byte data of the closest entry
        if closest_date is not None:
            return client_news_updates[closest_date]

        # If no entries exist, return None or handle as needed
        return None

# Example usage:
# manager = NewsManager()
# manager.create_appnews(1234, 5678)
# manager.create_adnews_2005("Breaking News!")
# serialized_data = manager.serialize()
# print(serialized_data)