# steam3/messages/MsgClientUFSGetFileListForApp.py
import struct
from io import BytesIO
from steam3.cm_packet_utils import CMResponse
from steam3.Types.emsg import EMsg
from steam3.Types.remotefile import RemoteFile
from steam3.protobufs.steammessages_clientserver_ufs_pb2 import CMsgClientUFSGetFileListForAppResponse


class MsgClientUFSGetFileListForAppResponse:
    def __init__(self, client_obj):
        self.files = []
        self.client_obj = client_obj

    def to_protobuf(self):
        packet = CMResponse(eMsgID=EMsg.ClientUFSGetFileListForAppResponse, client_obj=self.client_obj)
        response_message = CMsgClientUFSGetFileListForAppResponse()
        if self.files:
            for file in self.files:
                new_file = response_message.files.add()
                new_file.app_id = file.app_id
                new_file.file_name = file.name
                new_file.sha_file = file.sha
                new_file.time_stamp = file.time
                new_file.raw_file_size = file.size

        packet.data = response_message.SerializeToString()
        packet.length = len(packet.data)
        return packet

    def to_clientmsg(self):
        packet = CMResponse(eMsgID=EMsg.ClientUFSGetFileListForAppResponse, client_obj=self.client_obj)
        stream = BytesIO()

        stream.write(struct.pack("<I", len(self.files)))
        if self.files:
            for file in self.files:
                stream.write(struct.pack("<I", file.app_id))
                stream.write(file.name.encode("utf-8") + b"\x00")
                if len(file.sha) != 20:
                    raise ValueError("SHA must be exactly 20 bytes.")
                stream.write(file.sha)
                stream.write(struct.pack("<Q", file.time))
                stream.write(struct.pack("<I", file.size))
        else:
            stream.write(b'\x00\x00\x00\x00')

        packet.data = stream.getvalue()
        packet.length = len(packet.data)
        return packet

    def __str__(self):
        return f"MsgClientUFSGetFileListForAppResponse(Files=[{', '.join(str(file) for file in self.files)}])"


# Example Usage
"""if __name__ == "__main__":
    # Example files
    example_files = [
        RemoteFile(app_id=1234, name="file1.txt", sha=b'\x00' * 20, time=1633024800, size=1024),
        RemoteFile(app_id=5678, name="file2.log", sha=b'\xff' * 20, time=1633028400, size=2048),
    ]

    # Create and populate the response
    response = MsgClientUFSGetFileListForAppResponse()
    response.files = example_files

    # Serialize and print
    serialized_data = response.serialize()
    print(f"Serialized Data: {serialized_data.hex()}")

    # Print the string representation
    print(response)"""