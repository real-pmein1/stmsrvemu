from __future__ import annotations
import struct
from steam3.ClientManager.client import Client
from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse
from steam3.Types.steam_types import EResult  # EResult might not be directly used but good for context

class MsgClientUFSUploadFileFinished:
    def __init__(self, client_obj: Client | None = None, result=None, sha=None, data: bytes | None = None):
        self.result = result  # EResult (int32)
        self.sha = sha  # 20-byte array
        self.client_obj = client_obj
        if data:
            self.deserialize(data)

    def to_clientmsg(self):
        packet = CMResponse(eMsgID=EMsg.ClientUFSUploadFileFinished, client_obj=self.client_obj)
        if self.result is None:
            raise ValueError("Result (EResult) must be set.")
        if self.sha is None or len(self.sha) != 20:
            raise ValueError("SHA hash must be a 20-byte array.")

        # struct.pack format: i for int32 (EResult), 20s for 20-byte SHA
        packet.data = struct.pack('<i20s', int(self.result), self.sha)

        packet.length = len(packet.data)
        return packet

    def to_protobuf(self):
        packet = CMResponse(eMsgID=EMsg.ClientUFSUploadFileFinished, client_obj=self.client_obj)
        from steam3.protobufs import steammessages_clientserver_ufs_pb2 as ufs_pb2
        if self.result is None:
            raise ValueError("Result (EResult) must be set.")
        if self.sha is None or len(self.sha) != 20:
            raise ValueError("SHA hash must be a 20-byte array.")
        body = ufs_pb2.CMsgClientUFSUploadFileFinished()
        body.eresult = int(self.result)
        body.sha_file = self.sha
        packet.data = body.SerializeToString()
        packet.length = len(packet.data)
        return packet

    def deserialize(self, data):

        if len(data) < 24: # 4 for EResult + 20 for SHA
            raise ValueError("Message body too short for EResult and SHA")

        self.result = EResult(struct.unpack_from('<i', data)[0])
        self.sha = struct.unpack_from('<20s', data, 4)[0]
        
        return self

    def __repr__(self):
        sha_hex = self.sha.hex() if self.sha else "None"
        return (f"<{self.__class__.__name__}"
                f"result: {self.result!r} ({EResult(self.result).name if self.result is not None else 'N/A'}), sha: {sha_hex}>")


# Example usage:
"""if __name__ == '__main__':
    # Create a message instance
    sample_sha_finished = b'\x14\x13\x12\x11\x10\x0f\x0e\x0d\x0c\x0b\x0a\x09\x08\x07\x06\x05\x04\x03\x02\x01'
    msg_finished = MsgClientUFSUploadFileFinished(result=EResult.OK, sha=sample_sha_finished)
    print(f"Original message: {msg_finished!r}")

    # Serialize the message
    serialized_data_finished = bytes(msg_finished)
    print(f"Serialized data length: {len(serialized_data_finished)}")

    # Deserialize the message
    new_msg_finished = MsgClientUFSUploadFileFinished()
    new_msg_finished.deserialize(serialized_data_finished)
    print(f"Deserialized message: {new_msg_finished!r}")
    assert new_msg_finished.result == EResult.OK
    assert new_msg_finished.sha == sample_sha_finished

    # Test serialization error: result not set
    try:
        error_msg_result = MsgClientUFSUploadFileFinished(sha=sample_sha_finished)
        bytes(error_msg_result)
    except ValueError as e:
        print(f"Caught expected error for missing result: {e}")

    # Test serialization error: SHA invalid
    try:
        error_msg_sha_finished = MsgClientUFSUploadFileFinished(result=EResult.Fail, sha=b'too_short_sha')
        bytes(error_msg_sha_finished)
    except ValueError as e:
        print(f"Caught expected error for invalid SHA: {e}")
        
    # Test deserialization error: Body too short
    try:
        # Construct just a header and a partial body (e.g., only EResult, missing SHA)
        header_only = MsgClientUFSUploadFileFinished(result=EResult.OK, sha=sample_sha_finished).serialize_header()
        partial_body_data = header_only + struct.pack('<i', EResult.AccessDenied) # Only 4 bytes for EResult
        
        MsgClientUFSUploadFileFinished().deserialize(partial_body_data)
    except ValueError as e:
        print(f"Caught expected error for short body (header + partial EResult): {e}")

    print("MsgClientUFSUploadFileFinished tests completed.")"""
