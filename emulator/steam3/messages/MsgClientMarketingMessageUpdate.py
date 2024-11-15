import struct
from io import BytesIO
import datetime

from config import get_config


class MarketingMessage:
    def __init__(self, marketingMessageId=0, url=""):
        self.marketingMessageId = marketingMessageId
        self.url = url

class MsgClientMarketingMessageUpdate:
    def __init__(self):
        self.marketingMessageUpdateTime = int(datetime.datetime.utcnow().timestamp())  # Set current UTC time as int
        self.messagesCount = 0
        self.marketingMessages = []
        self.config = get_config()

    def add_marketing_message(self, messageID):
        """Adds a marketing message by appending the messageID to config['http_ip']/message/"""
        url = f"{self.config['http_ip']}/message/{messageID}"
        marketing_message = MarketingMessage(marketingMessageId=messageID, url=url)
        self.marketingMessages.append(marketing_message)
        self.messagesCount += 1

    def serialize(self):
        """Serialize the data into a byte packet"""
        stream = BytesIO()

        # Write marketingMessageUpdateTime (int32)
        stream.write(struct.pack('<i', self.marketingMessageUpdateTime))

        # Write the number of marketing messages (uint32)
        stream.write(struct.pack('<I', self.messagesCount))

        # Serialize each marketing message
        for message in self.marketingMessages:
            # Write marketingMessageId (int64)
            stream.write(struct.pack('<Q', message.marketingMessageId))

            # Write the URL followed by a null byte
            stream.write(message.url.encode('utf-8') + b'\x00')

        return stream.getvalue()

    def deSerialize(self, byte_buffer):
        """Deserialize the data from a byte packet"""
        stream = BytesIO(byte_buffer)

        # Read marketingMessageUpdateTime (int32)
        self.marketingMessageUpdateTime = struct.unpack('<i', stream.read(4))[0]
        self.marketingMessageUpdateTime = datetime.datetime.utcfromtimestamp(self.marketingMessageUpdateTime).strftime('%m/%d/%Y %H:%M:%S')

        # Read the messagesCount (DWORD = uint32)
        self.messagesCount = struct.unpack('<I', stream.read(4))[0]

        # Read all marketing messages
        for _ in range(self.messagesCount):
            # Read each marketing message
            message = MarketingMessage()

            # Read marketingMessageId (int64)
            message.marketingMessageId = struct.unpack('<Q', stream.read(8))[0]

            # Read URL (until null byte)
            message.url = self.read_null_terminated_string(stream)

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


# Example usage
"""config = {'http_ip': 'http://example.com'}

# Create a MsgClientMarketingMessageUpdate instance
msg_update = MsgClientMarketingMessageUpdate()

# Add marketing messages with message IDs
msg_update.add_marketing_message(1234567890)
msg_update.add_marketing_message(987654321)

# Serialize the packet
serialized_packet = msg_update.serialize()

# Print the serialized data
print(f"Serialized Packet: {serialized_packet}")

# Deserialize the packet
msg_update_de = MsgClientMarketingMessageUpdate()
packet = b",\x15\x00\x00$\x02\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xef\xc4\xa0\x9b\x01\x01\x00\x10\x01\xa0'\x0e\x00\xee\xdaLJ\x08\x00\x00\x00\xb7\xf9N4\xaa\x86@\x00http://cdn.store.steampowered.com/message/18162464089635255/\x00\x0f\xdfP0\xaa\x86@\x00http://cdn.store.steampowered.com/message/18162464022650639/\x00\x94\xaaHB\xaa\x86@\x00http://cdn.store.steampowered.com/message/18162464324102804/\x00V$\xd7@\xaa\x86@\x00http://cdn.store.steampowered.com/message/18162464299885654/\x00;\x8c\x873\xaa\x86@\x00http://cdn.store.steampowered.com/message/18162464076565563/\x00\xe9\xc1\xf42\xaa\x86@\x00http://cdn.store.steampowered.com/message/18162464066945513/\x00B\xb2\xde6\xaa\x86@\x00http://cdn.store.steampowered.com/message/18162464132608578/\x00\xa8\x99L7\xaa\x86@\x00http://cdn.store.steampowered.com/message/18162464139811240/\x00"
msg_update_de.deSerialize(packet[36:])

# Output deserialized data
print(f"Update Time: {msg_update_de.marketingMessageUpdateTime}")
for message in msg_update_de.marketingMessages:
    print(f"ID: {message.marketingMessageId}, URL: {message.url}")"""