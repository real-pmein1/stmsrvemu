"""ClientMsg parser for `EMsg.ClientUFSDeleteFileRequest`.

This packet is used by legacy clients to delete a file from the user file
storage (UFS).  The binary layout, derived from the deprecated C++
implementation in `tinserver`, is::

    uint32 app_id
    char   file_name[]  # UTF-8, null-terminated

The protobuf variant of this packet adds an ``is_explicit_delete`` flag, but
the clientmsg version only carries the application ID and file name.
"""

from __future__ import annotations

import struct
from typing import Optional


class MsgClientUFSDeleteFileRequest:
    """Represents a binary ``ClientUFSDeleteFileRequest`` message.

    Args:
        data (bytes | None): Optional body data to deserialize immediately.

    Attributes:
        app_id (int): Application identifier owning the file.
        file_name (str): Path of the file to remove.
    """

    def __init__(self, data: bytes | None = None) -> None:
        self.app_id: int = 0
        self.file_name: str = ""
        if data is not None:
            self.deserialize(data)

    def deserialize(self, data: bytes) -> "MsgClientUFSDeleteFileRequest":
        """Populate fields from *data*.

        Args:
            data (bytes): Raw message body.

        Returns:
            MsgClientUFSDeleteFileRequest: ``self`` for chaining.
        """

        if len(data) < 4:
            raise ValueError("DeleteFileRequest too short for app_id")

        self.app_id = struct.unpack_from("<I", data, 0)[0]

        name_bytes = data[4:]
        end = name_bytes.find(b"\x00")
        if end == -1:
            end = len(name_bytes)
        self.file_name = name_bytes[:end].decode("utf-8", errors="replace")

        return self

    def serialize(self) -> bytes:
        """Serialize the message body.

        Returns:
            bytes: Binary representation matching the clientmsg layout.
        """

        name = self.file_name.encode("utf-8") + b"\x00"
        return struct.pack("<I", self.app_id) + name

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<MsgClientUFSDeleteFileRequest app_id={self.app_id} file='{self.file_name}'>"


__all__ = ["MsgClientUFSDeleteFileRequest"]

