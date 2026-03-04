import struct
from io import BytesIO
import sys

# Stop Windows from faceplanting when printing non-ASCII
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

class MarketingMessage2:
    def __init__(self, message_size=0, marketingMessageId=0, url="", marketingMessageFlags=0, leftover_bytes=0):
        self.message_size = message_size
        self.marketingMessageId = marketingMessageId
        self.url = url
        self.marketingMessageFlags = marketingMessageFlags
        self.leftover_bytes = leftover_bytes

class ClientMsg2:
    def __init__(self):
        self.messagesCount = 0
        self.marketingMessages = []

    def deSerialize(self, byte_buffer: bytes):
        self.marketingMessages = []

        if not byte_buffer:
            self.messagesCount = 0
            return

        # --- Auto-sync to first record ---
        # Record layout is: u32 size + u64 gid + "http..."
        # So find first "http" and rewind 12 bytes.
        http_pos = byte_buffer.find(b"http")
        if http_pos != -1 and http_pos >= 12:
            start = http_pos - 12
        else:
            # Fallback: assume buffer starts on a record boundary
            start = 0

        stream = BytesIO(byte_buffer)
        stream.seek(start)

        # Parse records until EOF or invalid record
        while True:
            record_start = stream.tell()

            size_bytes = stream.read(4)
            if len(size_bytes) < 4:
                break

            unMessageSize = struct.unpack("<I", size_bytes)[0]

            # Minimum: 4(size) + 8(gid) + 1(null) + 4(flags) = 17
            if unMessageSize < 17:
                # Not a real record boundary; stop
                break

            record_end = record_start + unMessageSize
            if record_end > len(byte_buffer):
                # Record claims to extend past payload; stop
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

            consumed = stream.tell() - record_start
            leftover = unMessageSize - consumed
            if leftover > 0:
                stream.seek(leftover, 1)

            self.marketingMessages.append(
                MarketingMessage2(
                    message_size=unMessageSize,
                    marketingMessageId=gid,
                    url=url,
                    marketingMessageFlags=flags,
                    leftover_bytes=max(leftover, 0),
                )
            )

            if stream.tell() >= len(byte_buffer):
                break

        self.messagesCount = len(self.marketingMessages)

    def read_null_terminated_string_bounded(self, stream: BytesIO, record_end: int) -> str:
        chars = bytearray()
        while True:
            if stream.tell() >= record_end:
                break
            b = stream.read(1)
            if not b or b == b"\x00":
                break
            chars.extend(b)
        try:
            return chars.decode("utf-8")
        except UnicodeDecodeError:
            return chars.decode("utf-8", errors="replace")


# ---- Hard-coded packet buffer (your new one) ----
buffer = b"\x86\x15\x00\x00$\x02\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xefmw\xea\x02\x01\x00\x10\x01\xb7\xc2i\x00\x918\xc8M\x07\x00\x00\x00O\x00\x00\x00\xcb \xd7G\xa5\xbe\xc0\x10http://cdn.store.steampowered.com/message/1207174317219455179/\x00\x02\x00\x00\x00O\x00\x00\x00\xfcg\xd1G\xa5\xbe\xc0\x10http://cdn.store.steampowered.com/message/1207174317219080188/\x00\x02\x00\x00\x00O\x00\x00\x00\x89H'G\xa5\xbe\xc0\x10http://cdn.store.steampowered.com/message/1207174317207931017/\x00\x02\x00\x00\x00O\x00\x00\x00s\xb9\xa9F\xa5\xbe\xc0\x10http://cdn.store.steampowered.com/message/1207174317199702387/\x00\x00\x00\x00\x00O\x00\x00\x00\x0b\xc8\xceF\xa5\xbe\xc0\x10http://cdn.store.steampowered.com/message/1207174317202130955/\x00\x02\x00\x00\x00O\x00\x00\x00\xb8\x87\xbeX\x8f\xbe\xc4\x10http://cdn.store.steampowered.com/message/1208300122920617912/\x00\x02\x00\x00\x00O\x00\x00\x00\x90\xc6yF\xa5\xbe\xc0\x10http://cdn.store.steampowered.com/message/1207174317196560016/\x00\x02\x00\x00\x00"

# Keep your exact calling convention
msg = ClientMsg2()
msg.deSerialize(buffer[36:])

print(f"message count: {msg.messagesCount}")
for m in msg.marketingMessages:
    print(f"ID: {m.marketingMessageId}, URL: {m.url}, Flags: {m.marketingMessageFlags}, Size: {m.message_size}, Leftover: {m.leftover_bytes}")
