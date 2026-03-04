# steam_models.py

from dataclasses import dataclass, field
from typing import Union, Dict, Optional

# --- your existing enums / types ---
from steam3.Types.community_types import (
    LobbyComparison,
    LobbyFilterType,
    LobbyDistanceFilter,
    LobbyType,
)
from steam3.Types.Objects.chatroom_metadata import ChatRoomMetadata


# --- LobbyFilter + factory functions ---------------------------------------


@dataclass
class LobbyFilter:
    key: str = ""
    value: str = ""
    comparison: LobbyComparison = LobbyComparison.equal
    type: LobbyFilterType = LobbyFilterType.stringCompare

    def __repr__(self):
        return (f"LobbyFilter(key={self.key!r}, value={self.value!r}, "
                f"comparison={self.comparison.name}, type={self.type.name})")

def LobbyFilter_compare(
    key: str,
    comparision: LobbyComparison,
    value: Union[str, int]
) -> LobbyFilter:
    """
    C overloads:
      LobbyFilter_compare(const char* key, LobbyComparision cmp, const char* value);
      LobbyFilter_compare(const char* key, LobbyComparision cmp, SIGNEDDWORD value);
    """
    return LobbyFilter(
        key=key,
        value=str(value),
        comparision=comparision,
        type=LobbyFilterType.stringCompare
    )

def LobbyFilter_near(key: str, value: int) -> LobbyFilter:
    """LobbyFilter_near(const char* key, SIGNEDDWORD value);"""
    return LobbyFilter(
        key=key,
        value=str(value),
        comparision=LobbyComparison.notEqual,
        type=LobbyFilterType.nearValue
    )

def LobbyFilter_slotsAvailable(slotsAvailable: int) -> LobbyFilter:
    """LobbyFilter_slotsAvailable(DWORD slotsAvailable);"""
    return LobbyFilter(
        key="slotsAvailable",
        value=str(slotsAvailable),
        comparision=LobbyComparison.notEqual,
        type=LobbyFilterType.slotsAvailable
    )

def LobbyFilter_distance(distance: LobbyDistanceFilter) -> LobbyFilter:
    """LobbyFilter_distance(LobbyDistanceFilter distance);"""
    return LobbyFilter(
        key="distance",
        value=str(distance.value),
        comparision=LobbyComparison.notEqual,
        type=LobbyFilterType.distance
    )

def LobbyFilter_maxResults(maxResults: int) -> LobbyFilter:
    """LobbyFilter_maxResults(DWORD maxResults);"""
    return LobbyFilter(
        key="maxResults",
        value=str(maxResults),
        comparision=LobbyComparison.notEqual,
        type=LobbyFilterType.maxResults
    )

def base_genericFree(filter_obj: LobbyFilter) -> None:
    """No-op under Python?s GC; present for API parity."""
    pass

def base_free(filter_obj: LobbyFilter) -> None:
    """Alias for base_genericFree."""
    base_genericFree(filter_obj)


# --- Lobby ------------------------------------------------------------------

@dataclass
class Lobby:
    lobbyGlobalId:   int
    membersCount:    int
    membersMax:      int
    lobbyType:       LobbyType
    lobbyFlags:      int
    cellId:          int
    distance:        float
    weight:          int
    metadata:        Optional[ChatRoomMetadata] = None

def base_genericFree_lobby(l: Lobby) -> None:
    pass

def base_free_lobby(l: Lobby) -> None:
    base_genericFree_lobby(l)


# --- LobbyMember ------------------------------------------------------------

@dataclass
class LobbyMember:
    nickname: str
    metadata: Optional[ChatRoomMetadata] = None

def base_genericDelete_member(m: LobbyMember) -> None:
    pass

def base_genericFree_member(m: LobbyMember) -> None:
    pass

def base_free_member(m: LobbyMember) -> None:
    pass


# --- LobbyData --------------------------------------------------------------

@dataclass
class LobbyData:
    appId:          int
    lobby:          Lobby
    ownerGlobalId:  int
    members:        Dict[int, LobbyMember] = field(default_factory=dict)

def base_genericFree_lobbyData(ld: LobbyData) -> None:
    pass

def base_free_lobbyData(ld: LobbyData) -> None:
    base_genericFree_lobbyData(ld)


# --- ProfileSummary ---------------------------------------------------------

@dataclass
class ProfileSummary:
    steamGlobalId: int
    creationTime:  int
    headline:      str
    summary:       str
    url:           str
    country:       str
    state:         str
    city:          str

def base_genericFree_profile(p: ProfileSummary) -> None:
    pass

def base_free_profile(p: ProfileSummary) -> None:
    base_genericFree_profile(p)

from dataclasses import dataclass

@dataclass
class LobbyIds:
    appId: int
    lobbyGlobalId: int

def base_genericFree_lobbyIds(li: LobbyIds) -> None:
    """No-op under Python?s GC; present for API parity."""
    pass

def base_free_lobbyIds(li: LobbyIds) -> None:
    """Alias for base_genericFree_lobbyIds."""
    base_genericFree_lobbyIds(li)

