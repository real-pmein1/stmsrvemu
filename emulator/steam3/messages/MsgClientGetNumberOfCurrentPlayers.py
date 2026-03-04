from __future__ import annotations
import struct
from steam3.Types.GameID import GameID


class MsgClientGetNumberOfCurrentPlayers:
    """Client request for current player count of a game."""

    def __init__(self, data: bytes | None = None):
        self.game_id: GameID = GameID()
        if data is not None:
            self.deserialize(data)

    def deserialize(self, data: bytes) -> None:
        """Parse the 64-bit game ID from the request body."""
        if len(data) < 8:
            raise ValueError("ClientGetNumberOfCurrentPlayers payload too short")
        self.game_id = GameID(struct.unpack_from("<Q", data, 0)[0])

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"MsgClientGetNumberOfCurrentPlayers(game_id={int(self.game_id)})"
