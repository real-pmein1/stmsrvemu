import struct


class MsgClientFileToDownload:
    """
    Represents MsgClientFileToDownload_t structure.
    """

    def __init__(self):
        self.ip_dfs = 0
        self.port_dfs = 0
        self.url = ""

    def deserialize(self, data):
        """
        Parses a byte string into MsgClientFileToDownload_t fields.
        :param data: Byte string containing the serialized structure.
        :return: Remaining bytes after parsing.
        """
        if len(data) < 134:  # 4 bytes (IP) + 2 bytes (Port) + 128 bytes (URL)
            raise ValueError("Data is too short to parse MsgClientFileToDownload_t.")

        self.ip_dfs, self.port_dfs = struct.unpack_from('<IH', data, 0)
        self.url = data[6:134].split(b'\x00', 1)[0].decode('utf-8', errors='ignore')
        return data[134:]

    def serialize(self):
        """
        Serializes the MsgClientFileToDownload_t fields into a byte string.
        :return: Byte string containing the serialized structure.
        """
        url_bytes = self.url.encode('utf-8')
        url_bytes = url_bytes[:127] + b'\x00' if len(url_bytes) > 127 else url_bytes.ljust(128, b'\x00')
        return struct.pack('<IH', self.ip_dfs, self.port_dfs) + url_bytes

    def __str__(self):
        """
        Returns a human-readable string representation of the structure.
        """
        return (
            f"MsgClientFileToDownload(\n"
            f"  ip_dfs={self.ip_dfs},\n"
            f"  port_dfs={self.port_dfs},\n"
            f"  url={self.url}\n"
            f")"
        )


class MsgClientDRMDownloadResponse:
    """
    Represents MsgClientDRMDownloadResponse_t structure.
    """

    def __init__(self):
        self.result = 0
        self.app_id = 0
        self.blob_download_type = 0
        self.merge_guid = b""
        self.file = MsgClientFileToDownload()

    def deserialize(self, data):
        """
        Parses a byte string into MsgClientDRMDownloadResponse_t fields.
        :param data: Byte string containing the serialized structure.
        """
        if len(data) < 30:  # Minimum size without MsgClientFileToDownload_t
            raise ValueError("Data is too short to parse MsgClientDRMDownloadResponse_t.")

        self.result, self.app_id, self.blob_download_type = struct.unpack_from('<III', data, 0)
        self.merge_guid = data[12:28]
        remaining_data = data[28:]
        remaining_data = self.file.deserialize(remaining_data)
        return remaining_data

    def serialize(self):
        """
        Serializes the MsgClientDRMDownloadResponse_t fields into a byte string.
        :return: Byte string containing the serialized structure.
        """
        base = struct.pack('<III', self.result, self.app_id, self.blob_download_type) + self.merge_guid
        return base + self.file.serialize()

    def __str__(self):
        """
        Returns a human-readable string representation of the structure.
        """
        return (
            f"MsgClientDRMDownloadResponse(\n"
            f"  result={self.result},\n"
            f"  app_id={self.app_id},\n"
            f"  blob_download_type={self.blob_download_type},\n"
            f"  merge_guid={self.merge_guid.hex()},\n"
            f"  file={str(self.file)}\n"
            f")"
        )