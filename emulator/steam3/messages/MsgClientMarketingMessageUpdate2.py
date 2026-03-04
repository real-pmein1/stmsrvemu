import struct
from io import BytesIO
import datetime

from config import get_config


class MarketingMessage2:
    def __init__(self, marketingMessageId=0, url="", marketingMessageFlags=0):
        self.marketingMessageId = marketingMessageId
        self.url = url
        self.marketingMessageFlags = marketingMessageFlags


class MsgClientMarketingMessageUpdate2:
    def __init__(self):
        self.marketingMessageUpdateTime = int(datetime.datetime.utcnow().timestamp())  # kept (not used by v2)
        self.messagesCount = 0
        self.marketingMessages = []
        self.config = get_config()

    def add_marketing_message(self, messageID, flags=0):
        """Adds a marketing message by appending the messageID to config['http_ip']/message/"""
        url = f"{self.config['http_ip']}/message/{messageID}"
        marketing_message = MarketingMessage2(marketingMessageId=messageID, url=url, marketingMessageFlags=flags)
        self.marketingMessages.append(marketing_message)
        self.messagesCount += 1

    def serialize(self):
        """
        Serialize the data into a byte packet (v2 format)

        v2 record layout:
            uint32 size
            uint64 gid
            cstring url (null-terminated)
            uint32 flags
            (no padding emitted)
        """
        stream = BytesIO()

        for message in self.marketingMessages:
            url_bytes = message.url.encode("utf-8", errors="replace") + b"\x00"
            record_size = 4 + 8 + len(url_bytes) + 4  # size + gid + url\0 + flags

            stream.write(struct.pack("<I", record_size))
            stream.write(struct.pack("<Q", message.marketingMessageId))
            stream.write(url_bytes)
            stream.write(struct.pack("<I", int(message.marketingMessageFlags) & 0xFFFFFFFF))

        return stream.getvalue()

    def deSerialize(self, byte_buffer):
        """
        Deserialize the data from a byte packet (v2 format)

        v2 is a sequence of size-prefixed records. No header time/count in this payload.

        Keeps your prior working behavior:
          - auto-sync to first record boundary by finding b"http" and rewinding 12 bytes.
        """
        self.marketingMessages = []
        self.messagesCount = 0

        if not byte_buffer:
            return

        # --- Auto-sync to first record ---
        http_pos = byte_buffer.find(b"http")
        if http_pos != -1 and http_pos >= 12:
            start = http_pos - 12
        else:
            start = 0

        stream = BytesIO(byte_buffer)
        stream.seek(start)

        buf_len = len(byte_buffer)

        while True:
            record_start = stream.tell()

            size_bytes = stream.read(4)
            if len(size_bytes) < 4:
                break

            unMessageSize = struct.unpack("<I", size_bytes)[0]

            # Minimum: 4(size) + 8(gid) + 1(null) + 4(flags) = 17
            if unMessageSize < 17:
                break

            record_end = record_start + unMessageSize
            if record_end > buf_len:
                break

            gid_bytes = stream.read(8)
            if len(gid_bytes) < 8:
                break
            gid = struct.unpack("<Q", gid_bytes)[0]

            url = self.read_null_terminated_string_bounded(stream, record_end)

            flags_bytes = stream.read(4)
            if len(flags_bytes) < 4:
                break
            flags = struct.unpack("<I", flags_bytes)[0]

            # Skip any padding left inside the record
            consumed = stream.tell() - record_start
            leftover = unMessageSize - consumed
            if leftover > 0:
                stream.seek(leftover, 1)

            self.marketingMessages.append(MarketingMessage2(marketingMessageId=gid, url=url, marketingMessageFlags=flags))

            if stream.tell() >= buf_len:
                break

        self.messagesCount = len(self.marketingMessages)

    def read_null_terminated_string(self, stream):
        """(kept) Reads a null-terminated string from the stream."""
        chars = []
        while True:
            char = stream.read(1)
            if not char or char == b"\x00":
                break
            chars.append(char)
        return b"".join(chars).decode("utf-8", errors="replace")

    def read_null_terminated_string_bounded(self, stream, record_end: int):
        """(added) Reads a null-terminated string but won't read past record_end."""
        chars = bytearray()
        while True:
            if stream.tell() >= record_end:
                break
            b = stream.read(1)
            if not b or b == b"\x00":
                break
            chars.extend(b)
        return chars.decode("utf-8", errors="replace")
