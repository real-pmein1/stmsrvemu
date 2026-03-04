from __future__ import annotations
import struct


class MsgClientDRMDownloadRequest:
    """
    Python implementation of MsgClientDRMDownloadRequest_t.
    Parses and serializes a byte string based on the structure.
    """

    def __init__(self, client_obj=None, data: bytes | None = None):
        self.client_obj = client_obj
        self.download_flags = 0
        self.download_types_known = 0
        self.guid_drm = b""
        self.guid_split = b""
        self.guid_merge = b""
        self.executable_filename = None
        self.absolute_path = None
        if data:
            self.deserialize(data)

    @classmethod
    def from_bytes(cls, data: bytes):
        """
        Parses a byte string to populate the message fields.

        :param data: Byte string containing the serialized message.
        :return: An instance of MsgClientDRMDownloadRequest.
        """
        if len(data) < 58:  # Minimum size required for parsing
            raise ValueError("Data is too short to parse MsgClientDRMDownloadRequest_t.")

        instance = cls()

        # Parse the fixed-size fields
        instance.download_flags, instance.download_types_known = struct.unpack_from('<II', data, 0)

        # Extract GUIDs (16 bytes each)
        instance.guid_drm = data[8:24]
        instance.guid_split = data[24:40]
        instance.guid_merge = data[40:56]

        # Parse remaining bytes
        remaining_data = data[56:]
        if remaining_data:
            parts = remaining_data.split(b'\x00', 2)
            if len(parts) >= 2:
                instance.executable_filename = parts[0].decode('utf-8', errors='ignore')
                instance.absolute_path = parts[1].decode('utf-8', errors='ignore')

        return instance

    def serialize(self) -> bytes:
        """
        Serializes the message fields into a byte string.

        :return: Byte string containing the serialized message.
        """
        # Pack the fixed-size fields
        header = struct.pack('<II', self.download_flags, self.download_types_known)

        # Append the GUIDs
        base_data = header + self.guid_drm + self.guid_split + self.guid_merge

        # Append the executable filename and path
        if self.executable_filename and self.absolute_path:
            remaining_data = (
                self.executable_filename.encode('utf-8') + b'\x00' +
                self.absolute_path.encode('utf-8') + b'\x00'
            )
            return base_data + remaining_data
        else:
            return base_data


    def to_clientmsg(self):
        from steam3.cm_packet_utils import CMResponse
        from steam3.Types.emsg import EMsg

        packet = CMResponse(eMsgID=EMsg.ClientDRMDownloadRequest,
                            client_obj=self.client_obj)
        packet.data = self.serialize()
        packet.length = len(packet.data)
        return packet

    def __str__(self):
        """
        Returns a human-readable string representation of the message.

        :return: String representation of the MsgClientDRMDownloadRequest.
        """
        return (
            f"MsgClientDRMDownloadRequest(\n"
            f"  download_flags={self.download_flags},\n"
            f"  download_types_known={self.download_types_known},\n"
            f"  guid_drm={self.guid_drm.hex()},\n"
            f"  guid_split={self.guid_split.hex()},\n"
            f"  guid_merge={self.guid_merge.hex()},\n"
            f"  executable_filename={self.executable_filename},\n"
            f"  absolute_path={self.absolute_path}\n"
            f")"
        )
		
    __repr__ = __str__