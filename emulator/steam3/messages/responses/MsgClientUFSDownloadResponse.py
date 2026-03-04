import struct
from steam3.cm_packet_utils import CMResponse
from steam3.Types.emsg import EMsg
from steam3.Types.steam_types import EResult # EResult might not be directly used but good for context

class MsgClientUFSDownloadResponse:
    def __init__(self, client_obj, result=None, app_id=None, file_size=None, raw_file_size=None, sha_file=None, time_stamp=None, packetData=None):
        self.result = result  # EResult (int32)
        self.app_id = app_id  # uint32
        self.file_size = file_size  # uint32
        self.raw_file_size = raw_file_size  # uint32
        self.sha_file = sha_file  # 20-byte array
        self.time_stamp = time_stamp  # uint64
        self.client_obj = client_obj
        if packetData:
            self.deserialize(packetData)

    def to_clientmsg(self):
        if self.result is None:
            raise ValueError("Result (EResult) must be set.")
        if self.app_id is None:
            raise ValueError("App ID must be set.")
        if self.file_size is None:
            raise ValueError("File size must be set.")
        if self.raw_file_size is None:
            raise ValueError("Raw file size must be set.")
        if self.sha_file is None or len(self.sha_file) != 20:
            raise ValueError("SHA file hash must be a 20-byte array.")
        if self.time_stamp is None:
            raise ValueError("Timestamp must be set.")
        packet = CMResponse(eMsgID=EMsg.ClientUFSDownloadResponse, client_obj=self.client_obj)

        # FIXED: Correct field order from IDA Pro analysis
        # Offset 0: result (4 bytes)
        # Offset 4: app_id (4 bytes)
        # Offset 8: raw_file_size (4 bytes) - FIXED: was file_size
        # Offset 12: file_size (4 bytes) - FIXED: was raw_file_size
        # Offset 16: sha (20 bytes)
        # Offset 36: timestamp (8 bytes)
        packet.data = struct.pack(
            '<iIII20sQ',
            int(self.result),
            self.app_id,
            self.raw_file_size,    # FIXED: Swapped with file_size
            self.file_size,        # FIXED: Swapped with raw_file_size
            self.sha_file,
            self.time_stamp,
        )

        packet.length = len(packet.data)
        return packet

    def to_protobuf(self):
        packet = CMResponse(eMsgID=EMsg.ClientUFSDownloadResponse, client_obj=self.client_obj)
        from steam3.protobufs import steammessages_clientserver_ufs_pb2 as ufs_pb2
        body = ufs_pb2.CMsgClientUFSDownloadResponse()
        if self.result is None:
            raise ValueError("Result (EResult) must be set.")
        if self.app_id is None:
            raise ValueError("App ID must be set.")
        if self.file_size is None:
            raise ValueError("File size must be set.")
        if self.raw_file_size is None:
            raise ValueError("Raw file size must be set.")
        if self.sha_file is None or len(self.sha_file) != 20:
            raise ValueError("SHA file hash must be a 20-byte array.")
        if self.time_stamp is None:
            raise ValueError("Timestamp must be set.")
        body.eresult = int(self.result)
        body.app_id = self.app_id
        body.file_size = self.file_size
        body.raw_file_size = self.raw_file_size
        body.sha_file = self.sha_file
        body.time_stamp = self.time_stamp
        packet.data = body.SerializeToString()
        packet.length = len(packet.data)
        return packet

    def deserialize(self, data):

        # Minimum body length: 4 (result) + 4 (app_id) + 4 (raw_file_size) + 4 (file_size) + 20 (sha) + 8 (timestamp) = 44 bytes
        if len(data) < 44:
            raise ValueError("Message body too short for UFSDownloadResponse content.")

        # FIXED: Correct field order from IDA Pro analysis
        self.result = EResult(struct.unpack_from('<i', data)[0])
        self.app_id = struct.unpack_from('<I', data, 4)[0]
        self.raw_file_size = struct.unpack_from('<I', data, 8)[0]   # FIXED: Swapped with file_size
        self.file_size = struct.unpack_from('<I', data, 12)[0]      # FIXED: Swapped with raw_file_size
        self.sha_file = struct.unpack_from('<20s', data, 16)[0]
        self.time_stamp = struct.unpack_from('<Q', data, 36)[0]

        return self

    def __repr__(self):
        sha_hex = self.sha_file.hex() if self.sha_file else "None"
        return (f"<{self.__class__.__name__}"
                f"result: {self.result!r} ({EResult(self.result).name if self.result is not None else 'N/A'}), "
                f"app_id: {self.app_id}, file_size: {self.file_size}, raw_file_size: {self.raw_file_size}, "
                f"sha_file: {sha_hex}, time_stamp: {self.time_stamp}>")


# Example usage:
"""if __name__ == '__main__':
    sample_sha = b'\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10\x11\x12\x13\x14'
    
    # Create a message instance
    msg_resp = MsgClientUFSDownloadResponse(result=EResult.OK, 
                                            app_id=480, 
                                            file_size=10240, 
                                            raw_file_size=10000, 
                                            sha_file=sample_sha, 
                                            time_stamp=1678886400)
    print(f"Original message: {msg_resp!r}")

    # Serialize the message
    serialized_data = bytes(msg_resp)
    print(f"Serialized data length: {len(serialized_data)}")

    # Deserialize the message
    new_msg_resp = MsgClientUFSDownloadResponse()
    new_msg_resp.deserialize(serialized_data)
    print(f"Deserialized message: {new_msg_resp!r}")

    assert new_msg_resp.result == EResult.OK
    assert new_msg_resp.app_id == 480
    assert new_msg_resp.file_size == 10240
    assert new_msg_resp.raw_file_size == 10000
    assert new_msg_resp.sha_file == sample_sha
    assert new_msg_resp.time_stamp == 1678886400

    # Test serialization errors
    try:
        error_msg = MsgClientUFSDownloadResponse(app_id=123) # Missing other fields
        bytes(error_msg)
    except ValueError as e:
        print(f"Caught expected error for incomplete message: {e}")

    try:
        error_msg_sha = MsgClientUFSDownloadResponse(result=EResult.OK, app_id=1, file_size=1, raw_file_size=1, sha_file=b'short', time_stamp=1)
        bytes(error_msg_sha)
    except ValueError as e:
        print(f"Caught expected error for invalid SHA: {e}")

    # Test deserialization error: Body too short
    try:
        short_body_data = msg_resp.serialize_header() + struct.pack('<iI', EResult.OK, 480) # Only result and app_id
        MsgClientUFSDownloadResponse().deserialize(short_body_data)
    except ValueError as e:
        print(f"Caught expected error for short body: {e}")

    print("MsgClientUFSDownloadResponse tests completed.")
"""