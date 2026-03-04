import struct

class MsgClientUFSLoginRequest:
    """
    Python equivalent of the C++ MsgClientUFSLoginRequest.
    Provides:
      * cm_session_token (bytes)
      * app_ids (list of int)
    """
    def __init__(self, data: bytes = None):
        # initialize fields
        self.cm_session_token = 0
        self.app_ids = []
        if data is not None:
            self.deserialize(data)

    def deserialize(self, data: bytes):
        """
        Parse a byte buffer into:
          1) a 8-byte little-endian unsigned cm_session_token
          2) a 4-byte little-endian unsigned app count
          3) that many 4-byte little-endian app IDs
        """
        offset = 0

        # cmSessionToken (uint64 stored as raw 8 bytes)
        self.cm_session_token = struct.unpack_from('<8s', data, offset)[0]
        offset += 8

        # appCount (uint32)
        app_count = struct.unpack_from('<I', data, offset)[0]
        offset += 4

        # appIds array
        self.app_ids = []
        for _ in range(app_count):
            app_id = struct.unpack_from('<I', data, offset)[0]
            offset += 4
            self.app_ids.append(app_id)

    def __str__(self):
        return (
            f"{self.__class__.__name__}("
            f"cm_session_token={self.cm_session_token}, "
            f"app_ids={self.app_ids}"
            f")"
        )
