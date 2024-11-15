import random
import struct


class SessionIDManager:
    def __init__(self):
        self.context_ids = []

    def generate_32bit_sessionid(self):
        random_number = random.getrandbits(32)  # Generate a 32-bit random number
        byte_string = struct.pack('>I', random_number)  # Pack it into a 4-byte string in big endian format
        return byte_string

    def add_new_context_id(self):
        new_id = self.generate_32bit_sessionid()
        self.context_ids.append(new_id)
        return new_id

    def match_byte_string(self, byte_string):
        return byte_string in self.context_ids


"""
# Example usage
session_id_manager = SessionIDManager()

# Generate and add new context IDs
session_id_manager.add_new_context_id()
session_id_manager.add_new_context_id()

# Example byte string to match
byte_string_to_match = session_id_manager.context_ids[0]  # Using one of the generated IDs for demonstration

# Check if the byte string matches any of the stored context IDs
is_match = session_id_manager.match_byte_string(byte_string_to_match)
print("Match found:", is_match)"""