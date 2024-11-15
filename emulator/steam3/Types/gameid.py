from enum import Enum
import zlib

from steam3.utilities import BitVector64


class GameType(Enum):
    """
    Represents various types of games.
    """
    App = 0
    GameMod = 1
    Shortcut = 2
    P2P = 3

    @classmethod
    def from_code(cls, code):
        for item in cls:
            if item.value == code:
                return item
        return None


class GameID:
    def __init__(self, id=0):
        self.gameid = BitVector64(id)

    @classmethod
    def from_app_id(cls, nAppID):
        return cls(nAppID)

    @classmethod
    def from_mod(cls, nAppID, modPath):
        instance = cls()
        instance.AppID = nAppID
        instance.AppType = GameType.GameMod
        instance.ModID = zlib.crc32(modPath.encode('utf-8')) & 0xFFFFFFFF
        return instance

    @classmethod
    def from_shortcut(cls, exePath, appName):
        instance = cls()
        combined = (exePath or '') + (appName or '')
        instance.AppID = 0
        instance.AppType = GameType.Shortcut
        instance.ModID = zlib.crc32(combined.encode('utf-8')) & 0xFFFFFFFF
        return instance

    def set(self, gameId):
        self.gameid.Data = gameId

    def to_ulong(self):
        return self.gameid.Data

    def __str__(self):
        return str(self.gameid.Data)

    @property
    def AppID(self):
        return self.gameid[0, 0xFFFFFF]

    @AppID.setter
    def AppID(self, value):
        self.gameid[0, 0xFFFFFF] = value

    @property
    def AppType(self):
        return GameType.from_code(self.gameid[24, 0xFF])

    @AppType.setter
    def AppType(self, value):
        self.gameid[24, 0xFF] = value.value

    @property
    def ModID(self):
        return self.gameid[32, 0xFFFFFFFF]

    @ModID.setter
    def ModID(self, value):
        self.gameid[32, 0xFFFFFFFF] = value
        self.gameid[63, 0xFF] = 1

    @property
    def IsMod(self):
        return self.AppType == GameType.GameMod

    @property
    def IsShortcut(self):
        return self.AppType == GameType.Shortcut

    @property
    def IsP2PFile(self):
        return self.AppType == GameType.P2P

    @property
    def IsSteamApp(self):
        return self.AppType == GameType.App

    def __eq__(self, other):
        if not isinstance(other, GameID):
            return False
        return self.gameid.Data == other.gameid.Data

    def __hash__(self):
        return hash(self.gameid.Data)

    @staticmethod
    def from_ulong(id):
        return GameID(id)

    def __int__(self):
        return self.gameid.Data

"""# Example usage
game_id = GameID(123456789)
print(game_id)
print(game_id.to_ulong())
game_id.AppID = 12345
print(game_id.AppID)
game_id.AppType = GameType.App
print(game_id.IsSteamApp)"""


"""from enum import Enum
import zlib
import struct

class GameIDType(Enum):
    APP = 0
    GAMEMOD = 1
    SHORTCUT = 2
    P2P = 3

class GameID:
    def __init__(self, appId=None, modId=None, gameId=None, exePath=None, appName=None, modPath=None):
        self.gameId = 0
        self.gameIdDetail = None
        if gameId is not None:
            self.gameId = gameId
            self.gameIdDetail = self._parse_gameIdDetail(gameId)
        elif appId is not None and modId is None and exePath is None:
            self.gameIdDetail = self._create_gameIdDetail(appId, GameIDType.APP, 0)
        elif appId is not None and modId is not None:
            self.gameIdDetail = self._create_gameIdDetail(appId, GameIDType.GAMEMOD, modId)
        elif appId is not None and modPath is not None:
            self._set_mod_gameIdDetail(appId, modPath)
        elif exePath is not None and appName is not None:
            self._set_shortcut_gameIdDetail(exePath, appName)
        else:
            self.gameId = 0

    def _create_gameIdDetail(self, appId, type, modId):
        gameIdDetail = {
            "appId": appId,
            "type": type,
            "modId": modId
        }
        return gameIdDetail

    def _set_mod_gameIdDetail(self, appId, modPath):
        cleanedName = modPath.split('/')[-1].split('.')[0]
        self.gameIdDetail = self._create_gameIdDetail(appId, GameIDType.GAMEMOD, self._calculate_crc(cleanedName))

    def _set_shortcut_gameIdDetail(self, exePath, appName):
        self.gameIdDetail = self._create_gameIdDetail(0, GameIDType.SHORTCUT, self._calculate_crc(exePath + appName))

    def _calculate_crc(self, data):
        return zlib.crc32(data.encode()) | 0x80000000

    def setShortcut(self):
        self.gameIdDetail = self._create_gameIdDetail(0, GameIDType.SHORTCUT, 0)

    def setP2PFile(self):
        self.gameIdDetail = self._create_gameIdDetail(0, GameIDType.P2P, 0)

    def getGameId(self):
        return self.gameId

    def isMod(self):
        return (self.gameIdDetail["type"] == GameIDType.GAMEMOD)

    def isShortcut(self):
        return (self.gameIdDetail["type"] == GameIDType.SHORTCUT)

    def isP2PFile(self):
        return (self.gameIdDetail["type"] == GameIDType.P2P)

    def isSteamApp(self):
        return (self.gameIdDetail["type"] == GameIDType.APP)

    def getModId(self):
        return self.gameIdDetail["modId"]

    def getAppId(self):
        return self.gameIdDetail["appId"]

    def isValid(self):
        return self.gameId != 0

    def reset(self):
        self.gameId = 0

    def _parse_gameIdDetail(self, gameId):
        appId = gameId & 0xFFFFFF
        type = (gameId >> 24) & 0xFF
        modId = (gameId >> 32) & 0xFFFFFFFF
        return self._create_gameIdDetail(appId, GameIDType(type), modId)

    def __repr__(self):
        return f"<GameID {self.gameId}>"

# Example usage:
game_id_instance = GameID(gameId=123456789012345)
print(game_id_instance.getAppId())  # Should print the parsed appId
print(game_id_instance.isMod())  # Should print whether the gameId represents a mod
print(game_id_instance.getModId())  # Should print the parsed modId
"""