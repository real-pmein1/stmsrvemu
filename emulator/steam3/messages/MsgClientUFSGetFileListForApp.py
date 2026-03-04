from __future__ import annotations

import struct
from typing import List


class MsgClientUFSGetFileListForApp:
    """Represents ``EMsg.ClientUFSGetFileListForApp`` in clientmsg form.

    The deprecated binary layout used by legacy Steam clients is::

        uint32 app_count
        uint32 app_ids[app_count]

    Args:
        data (bytes | None): Optional body data to immediately parse.

    Attributes:
        app_ids (List[int]): Application identifiers requested by the client.
    """

    def __init__(self, data: bytes | None = None) -> None:
        self.app_ids: List[int] = []
        if data is not None:
            self.deserialize(data)

    def deserialize(self, data: bytes) -> "MsgClientUFSGetFileListForApp":
        """Deserialize *data* into :attr:`app_ids`.

        Args:
            data (bytes): Raw message body.

        Returns:
            MsgClientUFSGetFileListForApp: ``self`` for chaining.
        """

        if len(data) < 4:
            raise ValueError("UFSGetFileListForApp body too short for count")

        offset = 0
        app_count = struct.unpack_from("<I", data, offset)[0]
        offset += 4

        self.app_ids = []
        for _ in range(app_count):
            if len(data) < offset + 4:
                raise ValueError("Truncated app ID array")
            app_id = struct.unpack_from("<I", data, offset)[0]
            offset += 4
            self.app_ids.append(app_id)

        return self

    def serialize(self) -> bytes:
        """Serialize :attr:`app_ids` into binary form."""
        parts = [struct.pack("<I", len(self.app_ids))]
        for app_id in self.app_ids:
            parts.append(struct.pack("<I", app_id))
        return b"".join(parts)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<MsgClientUFSGetFileListForApp app_ids={self.app_ids}>"


__all__ = ["MsgClientUFSGetFileListForApp"]
