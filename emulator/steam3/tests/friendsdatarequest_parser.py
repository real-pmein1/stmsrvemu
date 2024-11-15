import struct
from io import BytesIO


class Body:
    def __init__(self):
        self.requestedPersonaStateFlags = 0
        self.requestedSteamGlobalIds = []


class MsgClient:
    def __init__(self):
        self.body = Body()

    def deserialize(self, byte_data: bytes):
        """Parses the byte data and populates the body with requestedPersonaStateFlags and requestedSteamGlobalIds."""
        stream = BytesIO(byte_data)

        # First, deserialize the base ClientMsg (this might be a placeholder depending on what needs to be done)
        self.client_msg_deserialize(stream)

        # Read requestedPersonaStateFlags (4 bytes, int32)
        self.body.requestedPersonaStateFlags = struct.unpack('<I', stream.read(4))[0]

        # Read requestsCount (4 bytes, int32)
        requests_count = struct.unpack('<I', stream.read(4))[0]

        # Read the requested steamGlobalIds (8 bytes each, int64)
        for _ in range(requests_count):
            steam_global_id = struct.unpack('<Q', stream.read(8))[0]
            self.body.requestedSteamGlobalIds.append(steam_global_id)





packet = b'/\x03\x00\x00$\x02\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xef\xc4\xa0\x9b\x01\x01\x00\x10\x01\x00v/\x00R\x00\x00\x00\x03\x00\x00\x00\x0fI\x94\x01\x01\x00\x10\x01\xba\r\x00\x00\x00\x00p\x018\r\x00\x00\x00\x00p\x01'


size = 36

msg_client = MsgClient()
msg_client.deserialize(packet[36:])

# Output the parsed data
print(f"Requested Persona State Flags: {msg_client.body.requestedPersonaStateFlags}")
print(f"Requested Steam Global IDs: {msg_client.body.requestedSteamGlobalIds}")