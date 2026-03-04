import random
import struct

class SessionIDManager:
    # TODO add data type information (bug report, screenshot, etc) to sessionid info in self.context_ids
    def __init__(self):
        # Store each entry as a tuple (session_id_bytes, ip_address_string)
        self.context_ids = []

    def generate_32bit_sessionid(self):
        """Generate a 4-byte session ID in big-endian format."""
        random_number = random.getrandbits(32)
        return struct.pack('>I', random_number)  # 4-byte string, big-endian

    def add_new_context_id(self, ip_address):
        """
        Generate a new session ID and associate it with the provided IP address.
        Returns the new session ID bytes.
        """
        new_id = self.generate_32bit_sessionid()
        self.context_ids.append((new_id, ip_address))
        return new_id

    def match_byte_string(self, sessionid, ip_address):
        """
        Check if byte_string matches the session ID portion of any stored (id, ip) tuple.
        """
        for session_id, ip_str in self.context_ids:
            if session_id == sessionid and ip_str == ip_address:
                return True
        return False


"""
# Example usage
session_id_manager = SessionIDManager()

# Generate and add new context IDs
session_id_manager.add_new_context_id('127.0.0.1)
session_id_manager.add_new_context_id('0.0.0.0')

# Example byte string to match
byte_string_to_match = session_id_manager.context_ids[0]  # Using one of the generated IDs for demonstration

# Check if the byte string matches any of the stored context IDs
is_match = session_id_manager.match_byte_string(byte_string_to_match, '127.0.0.1')
print("Match found:", is_match)"""