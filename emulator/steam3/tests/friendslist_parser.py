import struct
from io import BytesIO

class MsgClientFriendsList:
    def __init__(self):
        self.m_cFriends = 0          # Number of friends (int16)
        self.m_bIncremental = 0      # Incremental flag (uint8)
        self.friends = []            # List to store friend entries

    def deserialize(self, buffer: bytes):
        """
        Parses the byte buffer to extract MsgClientFriendsList fields.
        """
        stream = BytesIO(buffer)

        # Read m_cFriends (2 bytes, int16)
        self.m_cFriends = struct.unpack('<h', stream.read(2))[0]

        # Read m_bIncremental (1 byte, uint8)
        self.m_bIncremental = struct.unpack('<B', stream.read(1))[0]

        # Parse each friend entry
        for _ in range(self.m_cFriends):
            # Read friendID (8 bytes, uint64)
            friend_id = struct.unpack('<Q', stream.read(8))[0]

            # Read ubFriendRelationship (1 byte, uint8)
            friend_relationship = struct.unpack('<B', stream.read(1))[0]

            # Store the friend entry as a dictionary
            self.friends.append({
                'friend_id': friend_id,
                'friend_relationship': friend_relationship
            })

        # Check for extra bytes
        remaining_bytes = stream.read()
        if remaining_bytes:
            print(f"Extra bytes in buffer: {remaining_bytes.hex()}")

        return self

    def print_friends(self):
        """
        Helper function to print the list of friends.
        """
        print(f"Number of Friends: {self.m_cFriends}")
        print(f"Incremental Update: {bool(self.m_bIncremental)}")
        for idx, friend in enumerate(self.friends):
            print(f"Friend {idx + 1}:")
            print(f"  Friend ID: {friend['friend_id']}")
            print(f"  Relationship: {friend['friend_relationship']}")

# Example usage
# Construct an example buffer
# Let's say we have 2 friends in the list
# m_cFriends = 2 (int16)
# m_bIncremental = 1 (uint8)
# Friend entries:
#   - FriendID: 76561198000000001, Relationship: 3
#   - FriendID: 76561198000000002, Relationship: 2

"""buffer = (
    struct.pack('<h', 2) +             # m_cFriends
    struct.pack('<B', 1) +             # m_bIncremental
    struct.pack('<Q', 76561198000000001) +  # FriendID 1
    struct.pack('<B', 3) +             # Relationship 1
    struct.pack('<Q', 76561198000000002) +  # FriendID 2
    struct.pack('<B', 2)               # Relationship 2
)"""
packet = b'\xff\x02\x00\x00$\x02\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xef\xc4\xa0\x9b\x01\x01\x00\x10\x01\x00v/\x00\x03\x00\x00\x0fI\x94\x01\x01\x00\x10\x01\x038\r\x00\x00\x00\x00p\x01\x03\xba\r\x00\x00\x00\x00p\x01\x03'



packet = packet[36:]
# Deserialize the buffer
friends_list = MsgClientFriendsList()
friends_list.deserialize(packet)

# Output the parsed data
friends_list.print_friends()