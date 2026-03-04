import struct


class MsgClientUFSDownloadRequest:
    def __init__(self, data=None):
        self.app_id = None
        self.filename = None
        if data:
            self.deserialize(data)

    def deserialize(self, data):

        if len(data) < 4:
            raise ValueError("Message body too short for app_id")

        self.app_id = struct.unpack_from('<I', data)[0]
        
        filename_bytes = data[4:]
        
        try:
            null_terminator_index = filename_bytes.index(b'\x00')
            self.filename = filename_bytes[:null_terminator_index].decode('utf-8')
        except ValueError:
            # If no null terminator is found, assume the rest of the bytes are the filename
            # This might not be strictly correct depending on the exact protocol,
            # but it's a reasonable assumption for now.
            self.filename = filename_bytes.decode('utf-8')
        
        return self

    def __repr__(self):
        return f"<{self.__class__.__name__} app_id: {self.app_id}, filename: '{self.filename}'>"


# Example usage:
"""if __name__ == '__main__':
    # Create a message instance
    msg_req = MsgClientUFSDownloadRequest(app_id=12345, filename="path/to/remote/file.txt")
    print(f"Original message: {msg_req!r}")

    # Serialize the message
    serialized_data = bytes(msg_req)
    print(f"Serialized data: {serialized_data!r}")
    print(f"Serialized length: {len(serialized_data)}")

    # Deserialize the message
    new_msg_req = MsgClientUFSDownloadRequest()
    new_msg_req.deserialize(serialized_data)
    print(f"Deserialized message: {new_msg_req!r}")

    # Test with body only for deserialize, assuming header is handled by a higher layer
    # This requires a mock header or manual header addition if we were to use ClientMsg's deserialize directly
    
    # Test serialization without setting attributes (should raise ValueError)
    try:
        error_msg = MsgClientUFSDownloadRequest()
        bytes(error_msg)
    except ValueError as e:
        print(f"Caught expected error for incomplete message: {e}")

    # Test deserialization with potentially malformed data
    print("\nTesting deserialization with potentially malformed data:")
    
    # Missing filename null terminator (should still parse if that's the end of buffer)
    # Header needs to be appropriate for ClientMsg if we parse it fully
    # For now, let's assume deserialize is called with body data after header processing
    mock_header_len = 0 # Simplified: in real scenario, this would be ClientMsgHdr size
    
    # Simulate body data for app_id=789, filename="test.dat" (no null terminator)
    # This part of the test is a bit tricky without fully mocking the header behavior
    # Let's assume deserialize is primarily for the body part for now
    body_only_no_null = struct.pack('<I', 789) + "test.dat".encode('utf-8')
    
    # To test deserialize fully, we need a valid header part first.
    # Let's construct a minimal valid header for ClientMsg.
    # EMsg (4 bytes), targetJobID (8 bytes), sourceJobID (8 bytes)
    # For simplicity, let's assume these are zero for now
    # Actual ClientMsg.serialize_header() would do this.
    # Let's try to serialize and then deserialize to verify.
    
    msg_for_full_test = MsgClientUFSDownloadRequest(app_id=789, filename="test.dat")
    full_serialized = msg_for_full_test.serialize() # This includes header

    deserialized_full_test = MsgClientUFSDownloadRequest().deserialize(full_serialized)
    print(f"Full serialize/deserialize test: {deserialized_full_test!r}")
    assert deserialized_full_test.app_id == 789
    assert deserialized_full_test.filename == "test.dat"

    print("MsgClientUFSDownloadRequest tests completed.")"""
