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
        Packs the newstype, appid, and newsid into a byte buffer and adds it to the news entries.
        """
        newstype = 0
        buffer = struct.pack('BII', newstype, appid, newsid)
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
        Packs isAd, newsID, haveSubID, notHaveSubID, haveAppID, notHaveAppID, haveAppIDInstalled, havePlayedAppID into a byte buffer
        and adds it to the news entries.
        """
        ad_byte = 1 if isAd else 2
        buffer = struct.pack('BIIIIIII', ad_byte, newsID, haveSubID, notHaveSubID, haveAppID, notHaveAppID, haveAppIDInstalled, havePlayedAppID)
        self.news_entries.append(buffer)

    def create_clientupdatenews(self, bootstrapVersion: int, clientVersion: int, shouldReloadCDDB: bool) -> None:
        """
        Packs the number 4 as a byte, followed by bootstrapVersion and clientVersion (32-bit unsigned ints), and shouldReloadCDDB (boolean as a byte) into a byte buffer
        and adds it to the news entries.
        """
        reload_byte = 1 if shouldReloadCDDB else 0
        buffer = struct.pack('BIIB', 4, bootstrapVersion, clientVersion, reload_byte)
        self.news_entries.append(buffer)

    def serialize(self) -> bytes:
        """
        Serializes the news entries by appending all the different byte buffers and returning the news count packed as a 32-bit integer
        followed by the full news buffer.
        """
        news_count = len(self.news_entries)
        news_count_buffer = struct.pack('I', news_count)
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