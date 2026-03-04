# steam3/messages/MsgClientUFSGetFileListForApp.py
import struct
from io import BytesIO
from steam3.cm_packet_utils import CMResponse
from steam3.Types.emsg import EMsg
from steam3.Types.remotefile import RemoteFile
from steam3.protobufs.steammessages_clientserver_ufs_pb2 import CMsgClientUFSGetFileListForAppResponse


class MsgClientUFSGetFileListForAppResponse:
    """
    UFS Get File List For App Response message.

    Protocol differences:
        - Protocol >= 65557: New format (AppID + FileCount + [SHA + Timestamp(4) + FileSize + Filename] per file)
        - Protocol < 65557: Legacy format (FileCount + [AppID + Filename + SHA + Timestamp(8) + FileSize] per file)
    """

    # Protocol version threshold for new message format
    PROTOCOL_THRESHOLD = 65557

    def __init__(self, client_obj):
        self.files = []
        self.client_obj = client_obj

    def _get_protocol_version(self) -> int:
        """Get the client's protocol version for format decisions."""
        return getattr(self.client_obj, 'protocol_version', 0) or 0

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

        protocol_version = self._get_protocol_version()

        if protocol_version >= self.PROTOCOL_THRESHOLD:
            # New format (protocol >= 65557): AppID + FileCount + [SHA + Timestamp(4) + FileSize + Filename]
            # Get app_id from first file, or 0 if no files
            app_id = self.files[0].app_id if self.files else 0
            stream.write(struct.pack("<I", app_id))           # App ID (4 bytes)
            stream.write(struct.pack("<I", len(self.files)))  # File count (4 bytes)

            for file in self.files:
                # Ensure SHA is exactly 20 bytes
                sha_bytes = file.sha[:20].ljust(20, b'\x00') if file.sha else b'\x00' * 20
                stream.write(sha_bytes)                           # SHA1 (20 bytes)
                stream.write(struct.pack("<I", file.time))        # Timestamp (4 bytes, not 8)
                stream.write(struct.pack("<I", file.size))        # File size (4 bytes)
                stream.write(file.name.encode("utf-8") + b"\x00") # Filename (null-terminated)
        else:
            # Legacy format (protocol < 65557): FileCount + [AppID + Filename + SHA + Timestamp(8) + FileSize]
            stream.write(struct.pack("<I", len(self.files)))  # File count (4 bytes)

            if self.files:
                for file in self.files:
                    stream.write(struct.pack("<I", file.app_id))      # App ID (4 bytes)
                    stream.write(file.name.encode("utf-8") + b"\x00") # Filename (null-terminated)
                    # Ensure SHA is exactly 20 bytes
                    if file.sha and len(file.sha) != 20:
                        sha_bytes = file.sha[:20].ljust(20, b'\x00')
                    else:
                        sha_bytes = file.sha if file.sha else b'\x00' * 20
                    stream.write(sha_bytes)                           # SHA1 (20 bytes)
                    stream.write(struct.pack("<Q", file.time))        # Timestamp (8 bytes)
                    stream.write(struct.pack("<I", file.size))        # File size (4 bytes)

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