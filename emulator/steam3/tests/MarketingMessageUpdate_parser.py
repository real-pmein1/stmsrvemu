import struct
from datetime import datetime
from io import BytesIO

class MarketingMessage:
    def __init__(self, unknown_flags=0, marketingMessageId=0, url="", marketingMessageFlags=0):
        self.unknown_flags = unknown_flags
        self.marketingMessageId = marketingMessageId
        self.url = url
        self.marketingMessageFlags = marketingMessageFlags

class ClientMsg:
    def __init__(self):
        self.marketingMessageUpdateTime = 0
        self.messagesCount = 0
        self.marketingMessages = []

    def deSerialize(self, byte_buffer):
        # Create BytesIO stream from the byte buffer
        stream = BytesIO(byte_buffer)

        # Read marketingMessageUpdateTime (int32)
        self.marketingMessageUpdateTime = struct.unpack('<i', stream.read(4))[0]
        self.marketingMessageUpdateTime = datetime.utcfromtimestamp(self.marketingMessageUpdateTime).strftime('%m/%d/%Y %H:%M:%S')
        # Read the messagesCount (DWORD = uint32)
        self.messagesCount = struct.unpack('<I', stream.read(4))[0]

        # Read all marketing messages
        for _ in range(self.messagesCount):
            # Read each marketing message
            message = MarketingMessage()

            # Read unknown_flags (int32)

            # Read marketingMessageId (int64)
            message.marketingMessageId = struct.unpack('<Q', stream.read(8))[0]

            # Read URL (until null byte)
            message.url = self.read_null_terminated_string(stream)

            # Read marketingMessageFlags (int32)
            #message.marketingMessageFlags = struct.unpack('<i', stream.read(4))[0]

            # Add the message to the list
            self.marketingMessages.append(message)

    def read_null_terminated_string(self, stream):
        """Reads a null-terminated string from the stream."""
        chars = []
        while True:
            char = stream.read(1)
            if char == b'\x00':  # Stop at the null byte
                break
            chars.append(char)
        return b''.join(chars).decode('utf-8')


buffer = b",\x15\x00\x00$\x02\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xef\xc4\xa0\x9b\x01\x01\x00\x10\x01\xa0'\x0e\x00\xee\xdaLJ\x08\x00\x00\x00\xb7\xf9N4\xaa\x86@\x00http://cdn.store.steampowered.com/message/18162464089635255/\x00\x0f\xdfP0\xaa\x86@\x00http://cdn.store.steampowered.com/message/18162464022650639/\x00\x94\xaaHB\xaa\x86@\x00http://cdn.store.steampowered.com/message/18162464324102804/\x00V$\xd7@\xaa\x86@\x00http://cdn.store.steampowered.com/message/18162464299885654/\x00;\x8c\x873\xaa\x86@\x00http://cdn.store.steampowered.com/message/18162464076565563/\x00\xe9\xc1\xf42\xaa\x86@\x00http://cdn.store.steampowered.com/message/18162464066945513/\x00B\xb2\xde6\xaa\x86@\x00http://cdn.store.steampowered.com/message/18162464132608578/\x00\xa8\x99L7\xaa\x86@\x00http://cdn.store.steampowered.com/message/18162464139811240/\x00"

# Deserialize it
msg = ClientMsg()
msg.deSerialize(buffer[36:])

# Print deserialized data
print(f"Update Time: {msg.marketingMessageUpdateTime}, message count: {msg.messagesCount}")
for message in msg.marketingMessages:
    print(f"ID: {message.marketingMessageId}, URL: {message.url}, Flags: {message.marketingMessageFlags}")