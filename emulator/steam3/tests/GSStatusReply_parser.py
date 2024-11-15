import struct
from io import BytesIO

class GSStatusReply:
    def __init__(self, is_secured=0):
        self.is_secured = is_secured  # 4-byte integer representing whether the game server is secured

    def serialize(self):
        """ Serializes the is_secured field to a 4-byte integer. """
        stream = BytesIO()

        # Write the is_secured field as a 4-byte int
        stream.write(struct.pack('<I', self.is_secured))  # '<I' for little-endian unsigned int

        return stream.getvalue()

    @classmethod
    def deserialize(cls, byte_buffer):
        """ Deserializes the byte buffer to extract the is_secured field. """
        stream = BytesIO(byte_buffer)

        # Read the is_secured field (4-byte int)
        is_secured = struct.unpack('<I', stream.read(4))[0]

        return cls(is_secured)

# Example Usage
# Serialize an is_secured value
status = GSStatusReply(is_secured=1)
serialized_data = status.serialize()
print(f"Serialized Data: {serialized_data.hex()}")

packet = b'\x06\x03\x00\x00\x01\xd0\xea>\x1f\x00@\x01a4@\x00\x01\x00\x00\x00'

# Deserialize the same data back into a GSStatusReply object
deserialized_status = GSStatusReply.deserialize(packet[16:])
print(f"Deserialized is_secured: {deserialized_status.is_secured}")