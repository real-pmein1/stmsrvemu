import struct

UFS_FILE_CHUNK_MAX_LEN = 0x2800

class MsgClientUFSUploadFileChunk:
    def __init__(self, sha=None, offset=None, packetData=None):
        self.sha = sha  # 20-byte array
        self.offset = offset  # uint32
        self.length = None
        self.data = None
        if packetData:
            self.deserialize(packetData)


    def deserialize(self, packetData):
        if len(packetData) < 24:  # Must have SHA + offset, minimum structure
            raise ValueError("Message body too short for SHA and offset")

        # Read SHA (20 bytes)
        self.sha = struct.unpack_from('<20s', packetData)[0]
        # Read offset (4 bytes after SHA)
        self.offset = struct.unpack_from('<I', packetData, 20)[0]

        # Everything after 24 bytes is chunk data
        self.data = packetData[24:]

        # Length is simply the size of the chunk data
        self.length = len(self.data)

        if self.length > UFS_FILE_CHUNK_MAX_LEN:
            raise ValueError(
                f"Chunk too large! {self.length} bytes > max {UFS_FILE_CHUNK_MAX_LEN}"
            )
        return self

    def __repr__(self):
        sha_hex = self.sha.hex() if self.sha else "None"
        return (f"<{self.__class__.__name__} "
                f"sha: {sha_hex}, offset: {self.offset}, length: {self.length}, "
                f"data_len: {len(self.data) if self.data else 0}>")


# Example usage:
"""if __name__ == '__main__':
    # Create a message instance
    sample_sha = b'\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10\x11\x12\x13\x14'
    sample_data = b"This is some sample chunk data."
    msg_chunk = MsgClientUFSUploadFileChunk(sha=sample_sha, offset=1024, data=sample_data)
    print(f"Original message: {msg_chunk!r}")

    # Serialize the message
    serialized_data = bytes(msg_chunk)
    print(f"Serialized data length: {len(serialized_data)}")

    # Deserialize the message
    new_msg_chunk = MsgClientUFSUploadFileChunk()
    new_msg_chunk.deserialize(serialized_data)
    print(f"Deserialized message: {new_msg_chunk!r}")
    assert new_msg_chunk.sha == sample_sha
    assert new_msg_chunk.offset == 1024
    assert new_msg_chunk.length == len(sample_data)
    assert new_msg_chunk.data == sample_data

    # Test with empty data
    empty_data_msg = MsgClientUFSUploadFileChunk(sha=sample_sha, offset=0, data=b"")
    print(f"Empty data message: {empty_data_msg!r}")
    serialized_empty_data = bytes(empty_data_msg)
    deserialized_empty_data_msg = MsgClientUFSUploadFileChunk().deserialize(serialized_empty_data)
    print(f"Deserialized empty data message: {deserialized_empty_data_msg!r}")
    assert deserialized_empty_data_msg.data == b""
    assert deserialized_empty_data_msg.length == 0

    # Test serialization error: SHA too short
    try:
        error_msg_sha = MsgClientUFSUploadFileChunk(sha=b'short', offset=0, data=b'data')
        bytes(error_msg_sha)
    except ValueError as e:
        print(f"Caught expected error for invalid SHA: {e}")

    # Test serialization error: Data too long
    try:
        long_data = b'A' * (UFS_FILE_CHUNK_MAX_LEN + 1)
        error_msg_data = MsgClientUFSUploadFileChunk(sha=sample_sha, offset=0, data=long_data)
        bytes(error_msg_data)
    except ValueError as e:
        print(f"Caught expected error for oversized data: {e}")
        
    # Test deserialization error: Body too short
    try:
        short_body_data = msg_chunk.serialize_header() + struct.pack('<20sI', sample_sha, 0) # Missing length and data
        MsgClientUFSUploadFileChunk().deserialize(short_body_data)
    except ValueError as e:
        print(f"Caught expected error for short body (header + sha + partial offset): {e}")

    print("MsgClientUFSUploadFileChunk tests completed.")"""
