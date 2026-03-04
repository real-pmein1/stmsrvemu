import struct
from steam3.cm_packet_utils import CMResponse
from steam3.Types.emsg import EMsg
from steam3.Types.steam_types import EResult # EResult might not be directly used but good for context

UFS_FILE_CHUNK_MAX_LEN = 0x2800 # 10240 bytes, as defined in C++ source

class MsgClientUFSDownloadChunkResponse:
    def __init__(self, client_obj, result=None, sha_file=None, offset=None, data=None, packetData=None):
        # FIXED: Removed result field - chunks don't have result codes per IDA Pro analysis
        # Chunk structure from client code (EYieldingDownloadFile):
        # Offset 0: sha_file (20 bytes)
        # Offset 20: offset (4 bytes)
        # Offset 24+: data (variable length)
        self.sha_file = sha_file  # 20-byte array, SHA of the entire file
        self.offset = offset  # uint32, offset of this chunk in the file
        # data is the actual chunk data, up to UFS_FILE_CHUNK_MAX_LEN
        self.data = data if data is not None else b''
        self.client_obj = client_obj
        if packetData:
            self.deserialize(packetData)

    def to_clientmsg(self):
        if self.sha_file is None or len(self.sha_file) != 20:
            raise ValueError("SHA file hash must be a 20-byte array.")
        if self.offset is None:
            raise ValueError("Offset must be set.")

        packet = CMResponse(eMsgID=EMsg.ClientUFSDownloadChunk, client_obj=self.client_obj)

        chunk_size = len(self.data)
        if chunk_size > UFS_FILE_CHUNK_MAX_LEN:
            raise ValueError(f"Data length {chunk_size} exceeds UFS_FILE_CHUNK_MAX_LEN {UFS_FILE_CHUNK_MAX_LEN}")

        # FIXED: Correct structure from IDA Pro analysis (EYieldingDownloadFile)
        # Offset 0: sha_file (20 bytes)
        # Offset 20: offset (4 bytes)
        # Offset 24: data (variable length)
        # NO result field, NO length field
        packet.data = struct.pack('<20sI', self.sha_file, self.offset)
        packet.data += self.data

        packet.length = len(packet.data)
        return packet

    def to_protobuf(self):
        packet = CMResponse(eMsgID=EMsg.ClientUFSDownloadChunk, client_obj=self.client_obj)
        from steam3.protobufs import steammessages_clientserver_ufs_pb2 as ufs_pb2
        body = ufs_pb2.CMsgClientUFSFileChunk()
        if self.sha_file is None or len(self.sha_file) != 20:
            raise ValueError("SHA file hash must be a 20-byte array.")
        if self.offset is None:
            raise ValueError("Offset must be set.")
        # Protobuf format matches the correct structure
        body.sha_file = self.sha_file
        body.file_start = self.offset
        body.data = self.data
        packet.data = body.SerializeToString()
        packet.length = len(packet.data)
        return packet

    def deserialize(self, data_bytes):

        # FIXED: Correct structure from IDA Pro analysis
        # Minimum body length: 20 (sha_file) + 4 (offset) = 24 bytes
        if len(data_bytes) < 24:
            raise ValueError("Message body too short for UFSDownloadChunkResponse content (missing metadata).")

        self.sha_file = struct.unpack_from('<20s', data_bytes, 0)[0]
        self.offset = struct.unpack_from('<I', data_bytes, 20)[0]

        # Everything after offset 24 is the chunk data
        self.data = data_bytes[24:]

        chunk_size = len(self.data)
        if chunk_size > UFS_FILE_CHUNK_MAX_LEN:
            raise ValueError(f"Chunk data size {chunk_size} exceeds UFS_FILE_CHUNK_MAX_LEN {UFS_FILE_CHUNK_MAX_LEN}")

        return self

    def __repr__(self):
        sha_hex = self.sha_file.hex() if self.sha_file else "None"
        return (f"<{self.__class__.__name__}"
                f"sha_file: {sha_hex}, offset: {self.offset}, "
                f"data_bytes: {len(self.data) if self.data else 0}>")


# Example usage:
"""if __name__ == '__main__':
    sample_sha_chunk = b'\x0a\x0b\x0c\x0d\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d'
    sample_chunk_data = b"This is a part of the downloaded file."

    # Create a message instance
    msg_chunk_resp = MsgClientUFSDownloadChunkResponse(result=EResult.OK,
                                                       sha_file=sample_sha_chunk,
                                                       offset=2048,
                                                       data=sample_chunk_data)
    print(f"Original message: {msg_chunk_resp!r}")

    # Serialize the message
    serialized_chunk_data = bytes(msg_chunk_resp)
    print(f"Serialized data length: {len(serialized_chunk_data)}")

    # Deserialize the message
    new_msg_chunk_resp = MsgClientUFSDownloadChunkResponse()
    new_msg_chunk_resp.deserialize(serialized_chunk_data)
    print(f"Deserialized message: {new_msg_chunk_resp!r}")

    assert new_msg_chunk_resp.result == EResult.OK
    assert new_msg_chunk_resp.sha_file == sample_sha_chunk
    assert new_msg_chunk_resp.offset == 2048
    assert new_msg_chunk_resp.length == len(sample_chunk_data)
    assert new_msg_chunk_resp.data == sample_chunk_data

    # Test with empty data (e.g., final chunk might be empty with OK status, or an error chunk)
    empty_data_chunk = MsgClientUFSDownloadChunkResponse(result=EResult.EOF, # Example: End Of File
                                                         sha_file=sample_sha_chunk,
                                                         offset=4096,
                                                         data=b"")
    print(f"Empty data chunk message: {empty_data_chunk!r}")
    serialized_empty_chunk = bytes(empty_data_chunk)
    deserialized_empty_chunk = MsgClientUFSDownloadChunkResponse().deserialize(serialized_empty_chunk)
    print(f"Deserialized empty data chunk: {deserialized_empty_chunk!r}")
    assert deserialized_empty_chunk.data == b""
    assert deserialized_empty_chunk.length == 0
    assert deserialized_empty_chunk.result == EResult.EOF

    # Test serialization errors
    try:
        error_msg = MsgClientUFSDownloadChunkResponse(sha_file=sample_sha_chunk) # Missing fields
        bytes(error_msg)
    except ValueError as e:
        print(f"Caught expected error for incomplete message: {e}")

    # Test deserialization error: Body too short
    try:
        # Header + result + partial sha
        header_only = MsgClientUFSDownloadChunkResponse(result=EResult.OK, sha_file=sample_sha_chunk, offset=0, data=b'').serialize_header()
        partial_body_data = header_only + struct.pack('<i10s', EResult.Fail, sample_sha_chunk[:10])
        MsgClientUFSDownloadChunkResponse().deserialize(partial_body_data)
    except ValueError as e:
        print(f"Caught expected error for short body: {e}")

    print("MsgClientUFSDownloadChunkResponse tests completed.")"""
