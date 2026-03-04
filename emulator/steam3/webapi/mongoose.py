#!/usr/bin/env python3
from __future__ import annotations
import typing
from enum import Enum, auto
import asyncio
import os
import random
import time
from aiohttp import web

# Enums
class LanguageEnum(Enum):
    ENGLISH = auto()
    GERMAN = auto()
    FRENCH = auto()
    ITALIAN = auto()
    KOREAN = auto()
    SPANISH = auto()
    SIMPLIFIED_CHINESE = auto()
    TRADITIONAL_CHINESE = auto()
    RUSSIAN = auto()
    THAI = auto()
    JAPANESE = auto()
    PORTUGUESE = auto()
    POLISH = auto()
    DANISH = auto()
    DUTCH = auto()
    FINNISH = auto()
    NORWEGIAN = auto()
    SWEDISH = auto()
    HUNGARIAN = auto()
    CZECH = auto()
    ROMANIAN = auto()
    TURKISH = auto()
    ARABIC = auto()
    BULGARIAN = auto()
    GREEK = auto()
    UKRAINIAN = auto()
    VIETNAMESE = auto()
    # Placeholder for unknown or default
    UNKNOWN = auto()

class ResultTypeEnum(Enum):
    OK = 0
    FAIL = 1  # Generic fail
    SERVICE_UNAVAILABLE = 2
    INVALID_PASSWORD = 3
    PASSWORD_MISMATCH = 4
    MISSING_FIELDS = 5
    SPACE_IN_FIELD = 6      # Corresponds to "space" error from validation
    INVALID_EMAIL_FORMAT = 7 # Corresponds to "email" error from validation
    # Add other specific errors as needed
    ACCOUNT_ALREADY_EXISTS = 8 # Example if createAccount could return this
    # Generic error from web interface for validation
    VALIDATION_ERROR = 9 
    NOT_IMPLEMENTED = 10 # For stubbed methods


# Constants from SteamWebServerConstants.h
API_STEAMPOWERED_COM_HOSTNAME = "api.steampowered.com"
CRASH_STEAMPOWERED_COM_HOSTNAME = "crash.steampowered.com"
CLIENT_DOWNLOAD_STEAMPOWERED_COM_HOSTNAME = "client-download.steampowered.com"
CLIENTCONFIG_AKAMAI_STEAMSTATIC_COM_HOSTNAME = "clientconfig.akamai.steamstatic.com"
CLOUD_STEAMPOWERED_COM_HOSTNAME = "cloud.steampowered.com"
MEDIA_STEAMPOWERED_COM_HOSTNAME = "media.steampowered.com"
CDN_STEAMPOWERED_COM_HOSTNAME = "cdn.steampowered.com"
STORE_STEAMPOWERED_COM_HOSTNAME = "store.steampowered.com"
HELP_STEAMPOWERED_COM_HOSTNAME = "help.steampowered.com"
CM_STEAMPOWERED_COM_HOSTNAME = "cm.steampowered.com"
STEAMCOMMUNITY_COM_HOSTNAME = "steamcommunity.com"
STEAM_CHAT_COM_HOSTNAME = "steam-chat.com"
STEAMCDN_A_AKAMAIHD_NET_HOSTNAME = "steamcdn-a.akamaihd.net"
STEAMCOMMUNITY_A_AKAMAIHD_NET_HOSTNAME = "steamcommunity-a.akamaihd.net"
STEAMSTORE_A_AKAMAIHD_NET_HOSTNAME = "steamstore-a.akamaihd.net"
CS_STEAMCONTENT_COM_HOSTNAME = "cs.steamcontent.com"

# =============================================================================
# Configuration and Global Variables
# =============================================================================

# Constants (you may adjust these as needed)
RSA_ENCRYPTED_KEY_LENGTH = 256      # In C++ code this is checked.
ENCRYPTION_KEY_LENGTH = 16          # Dummy encryption key length.
STEAM_APP_ID_WINUI = 480            # Expected app id.
SESSION_TIMEOUT = 180               # Session expires after 3 minutes inactivity.

# Global server state
server_id = random.randint(1000, 9999)  # Randomly chosen server id.
server_load = 0.0                     # Dummy server load (could be updated dynamically).
config = {"cellid": "100"}            # Use this config value for cell/cellid.

# Global session store: keys are session ids (as strings) and values are Session objects.
sessions = {}

class SteamWebServerInterfacePy:
    """
    Python port of SteamWebServerInterface.
    """
    def __init__(self):
        pass

    def getCrashSteampoweredComHost(self) -> str:
        """Returns the hostname for crash.steampowered.com."""
        return CRASH_STEAMPOWERED_COM_HOSTNAME

    def getApiSteampoweredComHost(self) -> str:
        """Returns the hostname for api.steampowered.com."""
        return API_STEAMPOWERED_COM_HOSTNAME

    def getClientDownloadSteampoweredComHost(self) -> str:
        """Returns the hostname for client-download.steampowered.com."""
        return CLIENT_DOWNLOAD_STEAMPOWERED_COM_HOSTNAME

    def getClientConfigAkamaiSteamStaticHost(self) -> str:
        """Returns the hostname for clientconfig.akamai.steamstatic.com."""
        return CLIENTCONFIG_AKAMAI_STEAMSTATIC_COM_HOSTNAME

    def getCloudSteampoweredComHost(self) -> str:
        """Returns the hostname for cloud.steampowered.com."""
        return CLOUD_STEAMPOWERED_COM_HOSTNAME

    def getJoinHtmlPageLabels(self, language: LanguageEnum) -> dict:
        """
        Returns a dictionary of labels for the join HTML page.
        The language parameter is currently unused but kept for compatibility.
        """
        # In C++: getJoinHtmlPageLabels(char accountName[200], char password[200], char confirmPassword[200], char email[200], char confirm[200], Language language)
        # strcpy(accountName, "Account name");
        # strcpy(password, "Password");
        # strcpy(confirmPassword, "Confirm password");
        # strcpy(email, "Email");
        # strcpy(confirm, "Continue");
        return {
            "accountName": "Account name",
            "password": "Password",
            "confirmPassword": "Confirm password",
            "email": "Email",
            "confirm": "Continue",
        }

    def writeJoinHtmlPageHeader(self, out_stream: list, language: LanguageEnum, error_message: str = None):
        """
        Writes the HTML header for the join page to the out_stream.
        language: Currently unused.
        error_message: An optional error message to display.
        """
        # In C++: void SteamWebServerInterface::writeJoinHtmlPageHeader(PrintStream * out, Language language, const char * errorMessage)
        # out->print("<html>");
        # out->print("<body style='background:white'>");
        # out->print("<table>");
        # out->print("<tr><td><h1>Create account</h1></td></tr>");
        # if (errorMessage)	out->printf("<tr><td>%s</td></tr>", errorMessage);
        # out->print("<tr><td>");
        out_stream.append("<html>")
        out_stream.append("<body style='background:white'>")
        out_stream.append("<table>")
        out_stream.append("<tr><td><h1>Create account</h1></td></tr>")
        if error_message:
            out_stream.append(f"<tr><td>{error_message}</td></tr>")
        out_stream.append("<tr><td>")

    def writeJoinHtmlPageFooter(self, out_stream: list, language: LanguageEnum):
        """
        Writes the HTML footer for the join page to the out_stream.
        language: Currently unused.
        """
        # In C++: void SteamWebServerInterface::writeJoinHtmlPageFooter(PrintStream * out, Language language)
        # out->print("</td></tr>");
        # out->print("</table>");
        # out->print("</body>");
        # out->print("</html>");
        out_stream.append("</td></tr>")
        out_stream.append("</table>")
        out_stream.append("</body>")
        out_stream.append("</html>")

    def writeJoinResultHtmlPage(self, out_stream: list, account_name: str, password: str, email: str, language: LanguageEnum, result: ResultTypeEnum, steam_global_id: int = 0):
        """
        Writes the HTML result page after a join attempt.
        language: Passed to getJoinHtmlPageLabels.
        result: The result of the account creation.
        steam_global_id: The Steam Global ID if creation was successful.
        """
        # In C++: void SteamWebServerInterface::writeJoinResultHtmlPage(PrintStream * out, const char * accountName, const char * password, const char * email, Language language, ResultType result, ULONGLONG steamGlobalId)

        if result == ResultTypeEnum.OK:
            labels = self.getJoinHtmlPageLabels(language)
            steam_global_id_str = str(steam_global_id)

            out_stream.append("<html>")
            out_stream.append("<body style='background:white'>")
            out_stream.append("<table>")
            out_stream.append("<tr><td><h1>Account created</h1></td></tr>")
            out_stream.append("<tr><td>")
            out_stream.append("<table>")
            out_stream.append(f"<tr><td>{labels['accountName']}</td><td>:</td><td><span title='{steam_global_id_str}'>{account_name}</span></td></tr>")
            out_stream.append(f"<tr><td>{labels['password']}</td><td>:</td><td>*****</td></tr>") # Password is intentionally obscured
            out_stream.append(f"<tr><td>{labels['email']}</td><td>:</td><td>{email}</td></tr>")
            out_stream.append("</table>")
            out_stream.append("</td></tr>")
            out_stream.append("</table>")
            out_stream.append("</body>")
            out_stream.append("</html>")
        else:
            # Using result.name for a more descriptive error message if it's an enum
            error_message_str = result.name if isinstance(result, Enum) else str(result)

            out_stream.append("<html>")
            out_stream.append("<body style='background:white'>")
            out_stream.append("<table>")
            out_stream.append("<tr><td><h1>Account creation failed</h1></td></tr>")
            out_stream.append(f"<tr><td>{error_message_str}</td></tr>")
            out_stream.append("</table>")
            out_stream.append("</body>")
            out_stream.append("</html>")

    def validateNewAccountParameters(self, account_name: str, password: str, email: str) -> str | None:
        """
        Validates new account parameters.
        Returns an error string ("space", "email") if validation fails, otherwise None.
        The password parameter is currently unused in validation logic but kept for compatibility.
        """
        # In C++: const char * SteamWebServerInterface::validateNewAccountParameters(const char * accountName, const char * password, const char * email)
        # if (strchr(accountName, ' ') || strchr(email, ' ')) return "space";
        # if (!strchr(email, '@') || !strchr(email, '.')) return "email";
        # return 0;

        if ' ' in account_name or ' ' in email:
            return "space"
        if '@' not in email or '.' not in email:
            return "email"

        return None

    def writeChangePasswordHtmlPageHeader(self, out_stream: list, language: LanguageEnum, error_message: str = None):
        """
        Writes the HTML header for the change password page to the out_stream.
        language: Currently unused.
        error_message: An optional error message to display.
        """
        # In C++: void SteamWebServerInterface::writeChangePasswordHtmlPageHeader(PrintStream * out, Language language, const char * errorMessage)
        out_stream.append("<html>")
        out_stream.append("<body style='background:white'>")
        out_stream.append("<table>")
        out_stream.append("<tr><td><h1>Change password</h1></td></tr>")
        if error_message:
            out_stream.append(f"<tr><td>{error_message}</td></tr>")
        out_stream.append("<tr><td>")

    def getChangePasswordHtmlPageLabels(self, language: LanguageEnum) -> dict:
        """
        Returns a dictionary of labels for the change password HTML page.
        The language parameter is currently unused but kept for compatibility.
        """
        # In C++: void SteamWebServerInterface::getChangePasswordHtmlPageLabels(char password[200], char newPassword[200], char confirmPassword[200], char confirm[200], Language language)
        # strcpy(password, "Password");
        # strcpy(newPassword, "New password");
        # strcpy(confirmPassword, "Confirm password");
        # strcpy(confirm, "Continue");
        return {
            "password": "Password",
            "newPassword": "New password",
            "confirmPassword": "Confirm password",
            "confirm": "Continue",
        }

    def writeChangePasswordHtmlPageFooter(self, out_stream: list, language: LanguageEnum):
        """
        Writes the HTML footer for the change password page to the out_stream.
        language: Currently unused.
        """
        # In C++: void SteamWebServerInterface::writeChangePasswordHtmlPageFooter(PrintStream * out, Language language)
        # out->print("</td></tr>");
        # out_stream.append("</table>");
        # out_stream.append("</body>");
        # out_stream.append("</html>");
        out_stream.append("</td></tr>")
        out_stream.append("</table>")
        out_stream.append("</body>")
        out_stream.append("</html>")

    def writeChangePasswordResultHtmlPage(self, out_stream: list, password: str, language: LanguageEnum, result: ResultTypeEnum):
        """
        Writes the HTML result page after a change password attempt.
        password: The password (unused in this specific HTML generation).
        language: Currently unused.
        result: The result of the password change.
        """
        # In C++: void SteamWebServerInterface::writeChangePasswordResultHtmlPage(PrintStream * out, const char * password, Language language, ResultType result)
        if result == ResultTypeEnum.OK:
            out_stream.append("<html>")
            out_stream.append("<body style='background:white'>")
            out_stream.append("<table>")
            out_stream.append("<tr><td><h1>Password changed</h1></td></tr>")
            out_stream.append("</table>")
            out_stream.append("</body>")
            out_stream.append("</html>")
        else:
            error_message_str = result.name if isinstance(result, Enum) else str(result)
            out_stream.append("<html>")
            out_stream.append("<body style='background:white'>")
            out_stream.append("<table>")
            out_stream.append("<tr><td><h1>Password change failed</h1></td></tr>")
            out_stream.append(f"<tr><td>{error_message_str}</td></tr>")
            out_stream.append("</table>")
            out_stream.append("</body>")
            out_stream.append("</html>")

    def writeChangeEmailHtmlPageHeader(self, out_stream: list, language: LanguageEnum, error_message: str = None):
        """
        Writes the HTML header for the change email page to the out_stream.
        language: Currently unused.
        error_message: An optional error message to display.
        """
        # In C++: void SteamWebServerInterface::writeChangeEmailHtmlPageHeader(PrintStream * out, Language language, const char * errorMessage)
        out_stream.append("<html>")
        out_stream.append("<body style='background:white'>")
        out_stream.append("<table>")
        out_stream.append("<tr><td><h1>Change email</h1></td></tr>")
        if error_message:
            out_stream.append(f"<tr><td>{error_message}</td></tr>")
        out_stream.append("<tr><td>")

    def getChangeEmailHtmlPageLabels(self, language: LanguageEnum) -> dict:
        """
        Returns a dictionary of labels for the change email HTML page.
        The language parameter is currently unused but kept for compatibility.
        """
        # In C++: void SteamWebServerInterface::getChangeEmailHtmlPageLabels(char password[200], char email[200], char confirm[200], Language language)
        # strcpy(password, "Password");
        # strcpy(email, "New email");
        # strcpy(confirm, "Continue");
        return {
            "password": "Password",
            "email": "New email",
            "confirm": "Continue",
        }

    def writeChangeEmailHtmlPageFooter(self, out_stream: list, language: LanguageEnum):
        """
        Writes the HTML footer for the change email page to the out_stream.
        language: Currently unused.
        """
        # In C++: void SteamWebServerInterface::writeChangeEmailHtmlPageFooter(PrintStream * out, Language language)
        # out->print("</td></tr>");
        # out_stream.append("</table>");
        # out_stream.append("</body>");
        # out_stream.append("</html>");
        out_stream.append("</td></tr>")
        out_stream.append("</table>")
        out_stream.append("</body>")
        out_stream.append("</html>")

    def writeChangeEmailResultHtmlPage(self, out_stream: list, email: str, language: LanguageEnum, result: ResultTypeEnum):
        """
        Writes the HTML result page after a change email attempt.
        email: The email (unused in this specific HTML generation).
        language: Currently unused.
        result: The result of the email change.
        """
        # In C++: void SteamWebServerInterface::writeChangeEmailResultHtmlPage(PrintStream * out, const char * password, Language language, ResultType result)
        # Note: C++ signature has 'password', subtask asks for 'email'.
        if result == ResultTypeEnum.OK:
            out_stream.append("<html>")
            out_stream.append("<body style='background:white'>")
            out_stream.append("<table>")
            out_stream.append("<tr><td><h1>Email changed</h1></td></tr>")
            out_stream.append("</table>")
            out_stream.append("</body>")
            out_stream.append("</html>")
        else:
            error_message_str = result.name if isinstance(result, Enum) else str(result)
            out_stream.append("<html>")
            out_stream.append("<body style='background:white'>")
            out_stream.append("<table>")
            out_stream.append("<tr><td><h1>Email change failed</h1></td></tr>")
            out_stream.append(f"<tr><td>{error_message_str}</td></tr>")
            out_stream.append("</table>")
            out_stream.append("</body>")
            out_stream.append("</html>")

    def validateChangeEmailParameters(self, email: str) -> str | None:
        """
        Validates change email parameters.
        Returns "email" if validation fails, otherwise None.
        """
        # In C++: const char * SteamWebServerInterface::validateChangeEmailParameters(const char * email)
        # if (!strchr(email, '@') || !strchr(email, '.')) return "email";
        # return 0;

        if '@' not in email or '.' not in email:
            return "email"

        return None

    # crash.steampowered.com interfaces
    def onCrashSubmit(self, crash_properties: typing.Dict[str, str], minidump: typing.Any = None) -> int:
        """
        Handles crash submission.
        minidump: Optional InputStream for the minidump.
        Returns a CrashID (ULONGLONG).
        """
        # In C++: virtual ULONGLONG onCrashSubmit(HashMap<const char*,char*> * crashProperties, InputStream * minidump=0)=0;
        raise NotImplementedError("onCrashSubmit is not implemented.")

    # api.steampowered.com interfaces
    def getCMServers(self, cell_id: int, servers_out_list: typing.List[str]) -> bool:
        """
        Gets the CM servers list.
        cell_id: The cell ID.
        servers_out_list: An output list to be populated with server addresses (e.g., strings).
        Returns true if successful, false otherwise. (Addresses are not deleted by caller).
        """
        # In C++: virtual bool getCMServers(DWORD cellId, Vector<InetAddress*> * servers)=0;
        # The servers_out_list is conceptually the Vector<InetAddress*> * servers
        raise NotImplementedError("getCMServers is not implemented.")

    def getWebSocketCMServers(self, cell_id: int, servers_out_list: typing.List[str]) -> bool:
        """
        Gets the WebSocket CM servers list.
        cell_id: The cell ID.
        servers_out_list: An output list to be populated with server addresses (e.g., strings).
        Returns true if successful, false otherwise. (Addresses are not deleted by caller).
        """
        # In C++: virtual bool getWebSocketCMServers(DWORD cellId, Vector<InetAddress*> * servers) = 0;
        raise NotImplementedError("getWebSocketCMServers is not implemented.")

    def getContentServers3(self, cell_id: int, servers_out_list: typing.List[str]) -> bool:
        """
        Gets the content servers 3 list.
        cell_id: The cell ID.
        servers_out_list: An output list to be populated with server addresses (e.g., strings).
        Returns true if successful, false otherwise. (Addresses are not deleted by caller).
        """
        # In C++: virtual bool getContentServers3(DWORD cellId, Vector<InetAddress*> * servers) = 0;
        raise NotImplementedError("getContentServers3 is not implemented.")

    def checkLoginKey(self, steam_global_id: int, login_key: str) -> bool:
        """
        Checks if the specified loginKey matches the one generated on the CM server.
        steam_global_id: The user's Steam Global ID.
        login_key: The login key to check. (CM_LOGIN_KEY_LENGTH+1 in C++)
        Returns true if the key matches, false otherwise.
        """
        # In C++: virtual bool checkLoginKey(ULONGLONG steamGlobalId, const char loginKey[CM_LOGIN_KEY_LENGTH+1])=0;
        raise NotImplementedError("checkLoginKey is not implemented.")

    def getSteamAppNames(self, names_out_dict: typing.Dict[int, str]) -> bool:
        """
        Gets steam app names.
        names_out_dict: An output dictionary to be populated with app_id (int) -> app_name (str).
        Returns true if successful, false otherwise.
        """
        # In C++: virtual bool getSteamAppNames(HashMap<DWORD, char *> * names) = 0;
        raise NotImplementedError("getSteamAppNames is not implemented.")

    def getSteamAppNews(self, app_id: int, count: int, max_content_length: int, news_out_list: typing.List[typing.Any]) -> bool:
        """
        Gets steam app news.
        app_id: The application ID.
        count: Maximum number of news items to retrieve.
        max_content_length: Maximum length for the content of each news item.
        news_out_list: An output list to be populated with SteamAppNews objects (structure TBD, use typing.Any for now).
        Returns true if successful, false otherwise.
        """
        # In C++: virtual bool getSteamAppNews(DWORD appId, DWORD count, DWORD maxContentLength, Vector<SteamAppNews> * news)=0;
        # SteamAppNews structure would need to be defined in Python (e.g., as a class or dict).
        raise NotImplementedError("getSteamAppNews is not implemented.")

    def getSteamAppGlobalAchievementPercentages(self, app_id: int, percentages_out_dict: typing.Dict[str, float]) -> bool:
        """
        Gets global achievement percentages for a Steam app.
        app_id: The application ID.
        percentages_out_dict: An output dictionary to be populated with achievement_id (str) -> percentage (float).
        Returns true if successful, false otherwise. (Max percentage is 100.0).
        """
        # In C++: virtual bool getSteamAppGlobalAchievementPercentages(DWORD appId, HashMap<const char*,float> * globalAchievementPercentages)=0;
        raise NotImplementedError("getSteamAppGlobalAchievementPercentages is not implemented.")

    # client-download.steampowered.com interfaces
    def getSteamClientManifests(self) -> typing.List[typing.Any]:
        """
        Gets Steam client manifests.
        Returns a list of SteamClientManifest objects (structure TBD, use typing.Any for now).
        (Result will be deleted by caller in C++).
        """
        # In C++: virtual Vector<SteamClientManifest*> * getSteamClientManifests()=0;
        # SteamClientManifest structure would need to be defined in Python.
        raise NotImplementedError("getSteamClientManifests is not implemented.")

    def getSteamClientLauncherFiles(self) -> typing.List[typing.Any]:
        """
        Gets Steam client launcher files.
        Returns a list of File objects (structure/type TBD, use typing.Any for now).
        (Result will be deleted by caller in C++; extension used for SHA verification).
        """
        # In C++: virtual Vector<File*> * getSteamClientLauncherFiles() = 0;
        # File structure/type would need to be defined/handled in Python.
        raise NotImplementedError("getSteamClientLauncherFiles is not implemented.")

    # clientconfig.akamai.steamstatic.com interfaces
    def getAppInfo(self, app_id: int) -> typing.Any | None:
        """
        Gets the AppInfo for a given app ID.
        app_id: The application ID.
        Returns an AppInfo object (structure TBD, use typing.Any) or None if unknown.
        (AppInfo is not deleted by caller in C++).
        """
        # In C++: virtual AppInfo * getAppInfo(DWORD appId)=0;
        # AppInfo structure would need to be defined in Python.
        raise NotImplementedError("getAppInfo is not implemented.")

    # cloud.steampowered.com interfaces
    def isCloudExternalStorageAccessGranted(self, request: typing.Any) -> bool:
        """
        Checks if cloud external storage access is granted based on the request.
        request: The HttpServerRequest object (use typing.Any for now).
        Checks URL/headers for security tokens from CM server for upload/download.
        Returns true if access is granted, false otherwise.
        """
        # In C++: virtual bool isCloudExternalStorageAccessGranted(HttpServerRequest * request)=0;
        # HttpServerRequest structure/type would need to be defined/handled in Python.
        raise NotImplementedError("isCloudExternalStorageAccessGranted is not implemented.")

    def getCloudExternalStorageRoot(self) -> typing.Any:
        """
        Gets the root folder for storing SteamCloud files.
        Returns a File object (structure/type TBD, e.g., a path string or a custom object, use typing.Any).
        """
        # In C++: virtual File * getCloudExternalStorageRoot()=0;
        # File structure/type would need to be defined/handled in Python.
        raise NotImplementedError("getCloudExternalStorageRoot is not implemented.")

    # media.steampowered.com, cdn.steampowered.com, etc. interfaces
    def getMedia(self, host: str, url: str, parameters: typing.Dict[str, str], parameters_digest: int, size_out_container: typing.List[int], secured: bool) -> typing.Any:
        """
        Gets a media stream and its size.
        host: The host for the media.
        url: The URL for the media.
        parameters: Dictionary of parameters.
        parameters_digest: Digest of the parameters.
        size_out_container: A list containing one integer, to be filled with the size of the media.
        secured: Boolean indicating if a secured connection is used.
        Returns an InputStream object (use typing.Any for now).
        """
        # In C++: virtual InputStream * getMedia(const char * host, const char * url, HashMap<const char*, const char*> * parameters, DWORD parametersDigest, DWORD * size, bool secured)=0;
        # InputStream structure/type would need to be defined/handled in Python.
        # size_out_container[0] is used to simulate the DWORD* size output.
        raise NotImplementedError("getMedia is not implemented.")

    # cm.steampowered.com interfaces
    def getCMServer(self) -> typing.Any | None:
        """
        Gets the CM server instance.
        Returns the CMServer object (use typing.Any for now) to register the websocket port,
        or None if not available.
        """
        # In C++: virtual CMServer * getCMServer() = 0;
        # CMServer structure/type would need to be defined/handled in Python.
        raise NotImplementedError("getCMServer is not implemented.")

    def getMaxWebSocketCMServerConnections(self) -> int:
        """
        Gets the maximum web socket CM server connections.
        Returns the maximum number of connections, or -1 for unlimited.
        """
        # In C++: virtual DWORD getMaxWebSocketCMServerConnections() = 0;
        raise NotImplementedError("getMaxWebSocketCMServerConnections is not implemented.")

    # steamcommunity-a.akamaihd.net interfaces
    def getEmoticonPng(self, name: str, large: bool) -> typing.Any:
        """
        Gets a PNG format emoticon.
        name: The name of the emoticon.
        large: If true, returns the large (54x54) version, otherwise the small (18x18) version.
        Returns an InputStream object (use typing.Any for now) for the PNG data.
        """
        # In C++: virtual InputStream * getEmoticonPng(const char * name, bool large) = 0;
        # InputStream structure/type would need to be defined/handled in Python.
        raise NotImplementedError("getEmoticonPng is not implemented.")

    # www.steamcommunity.com interfaces
    def newSteamLoginCookie(self, steam_global_id: int) -> str:
        """
        Creates a new Steam login cookie.
        steam_global_id: The user's Steam Global ID.
        Returns the cookie string (token for "steamLogin" HTTP cookie).
        (Result is freed by caller in C++).
        """
        # In C++: virtual char * newSteamLoginCookie(ULONGLONG steamGlobalId) = 0;
        raise NotImplementedError("newSteamLoginCookie is not implemented.")

    def checkSteamLoginCookie(self, steam_global_id: int, cookie: str) -> bool:
        """
        Verifies the "steamLogin" HTTP cookie.
        steam_global_id: The user's Steam Global ID.
        cookie: The cookie string to verify.
        Returns true if the cookie is valid, false otherwise.
        """
        # In C++: virtual bool checkSteamLoginCookie(ULONGLONG steamGlobalId, const char * cookie) = 0;
        raise NotImplementedError("checkSteamLoginCookie is not implemented.")

    # steam-chat.com interfaces
    def getCloudURLHost(self, is_https_out_list: typing.List[bool]) -> str:
        """
        Gets the SteamCloud HTTP storage host.
        is_https_out_list: A list containing one boolean, to be filled with true if HTTPS is mandatory.
        Returns the hostname string. (HTTPS is mandatory as of 2018/10/25).
        """
        # In C++: virtual const char * getCloudURLHost(bool * isHttps) = 0;
        # is_https_out_list[0] is used to simulate the bool* isHttps output.
        raise NotImplementedError("getCloudURLHost is not implemented.")

    def getCloudURLPath(self, ugc_id: int, filename: str, filesha: str, for_upload: bool, http_headers_registry_out_dict: typing.Dict[str, typing.Any]) -> str:
        """
        Gets the SteamCloud HTTP storage absolute upload/download path and associated HTTP headers.
        ugc_id: The UGC ID.
        filename: The name of the file.
        filesha: The SHA hash of the file.
        for_upload: True if the path is for an upload, false for download.
        http_headers_registry_out_dict: An output dictionary to be populated with HTTP headers to be passed.
                                         (Corresponds to RegistryKey * httpHeaders in C++)
        Returns the absolute path string.
        (The URL or headers may include security tokens).
        """
        # In C++: virtual char * getCloudURLPath(ULONGLONG ugcId, const char * filename, const char * filesha, bool forUpload, RegistryKey * httpHeaders) = 0;
        # http_headers_registry_out_dict is conceptually the RegistryKey * httpHeaders.
        raise NotImplementedError("getCloudURLPath is not implemented.")

    def getChatIconOutputStream(self, partition: str, file_name: str) -> typing.Any:
        """
        Gets an output stream to store chat icons.
        partition: The partition for the icon.
        file_name: The file name of the icon.
        Returns an OutputStream object (use typing.Any for now).
        (Stream to be deleted by caller in C++; file accessible via CDN).
        """
        # In C++: virtual OutputStream * getChatIconOutputStream(const char * partition, const char * fileName) = 0;
        # OutputStream structure/type would need to be defined/handled in Python.
        raise NotImplementedError("getChatIconOutputStream is not implemented.")

steam_web_interface = SteamWebServerInterfacePy()

# =============================================================================
# Session Class and Helpers
# =============================================================================

class Session:
    def __init__(self, session_id, client_ip, encryption_key):
        self.session_id = session_id
        self.client_ip = client_ip
        self.encryption_key = encryption_key
        self.attributes = {}
        self.last_accessed = time.time()

def generate_session_id(client_ip):
    """Generate a new session id (a random 64-bit integer)."""
    return str(random.getrandbits(64))

async def cleanup_sessions():
    """Periodically remove sessions that have been inactive for more than SESSION_TIMEOUT seconds."""
    while True:
        now = time.time()
        expired = [sid for sid, sess in sessions.items() if now - sess.last_accessed > SESSION_TIMEOUT]
        for sid in expired:
            del sessions[sid]
            print(f"Session {sid} expired and removed.")
        await asyncio.sleep(60)

# =============================================================================
# Dummy Provider / Crypto Functions
# =============================================================================

def symmetric_decrypt_app_ticket(encrypted_app_ticket, key):
    """
    Dummy decryption function. In a real implementation you would
    decrypt the ticket using the provided key.
    Here we simply simulate a valid ticket if any value is given.
    """
    if not encrypted_app_ticket:
        return None
    # For example, return a dummy ticket with a fixed app id and steam global id.
    return {"steam_global_id": 0xABCDEF, "app_id": STEAM_APP_ID_WINUI}

def validate_app_ticket(ticket):
    """
    Dummy validation of the ticket.
    In production, you would check that the decrypted ticket is valid.
    """
    return ticket is not None

# =============================================================================
# Dummy Filesystem Stub
# =============================================================================

def handle_depot_filesystem(depot_id, service):
    """
    Stub for filesystem code.
    In production, this would access the filesystem to serve files or process depot data.
    """
    return f"Depot {depot_id} with service '{service}' accessed (filesystem stub)."

def get_dummy_content_servers(cell_id, max_results):
    """
    Return a dummy list of content servers.
    Each server is represented as a dictionary.
    """
    servers = []
    # Dummy CDN server.
    servers.append({
        "type": "CDN",
        "contentServerId": 1,
        "hostname": "cdn.example.com",
        "ipPort": "192.168.1.1:8081",
        "load": 0.3,
        "weightLoad": 0.3
    })
    # Dummy Content Server.
    servers.append({
        "type": "CS",
        "contentServerId": 2,
        "hostname": "cs.example.com",
        "ipPort": "192.168.1.2:8080",
        "load": 0.5,
        "weightLoad": 0.5,
        "cellId": cell_id
    })
    return servers[:max_results]

# =============================================================================
# VDF Serialization Helper
# =============================================================================

def serialize_vdf(data, indent=0):
    """
    Serialize a nested dictionary into a Valve Data Format (VDF)?like text.
    For example, the structure:
        {"status": {"csid": "123", "load": "0.5", "cell": "100"}}
    becomes:
        "status"
        {
            "csid"    "123"
            "load"    "0.5"
            "cell"    "100"
        }
    """
    lines = []
    ind = "    " * indent
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f'{ind}"{key}"')
            lines.append(f'{ind}' + '{')
            lines.append(serialize_vdf(value, indent + 1))
            lines.append(f'{ind}' + '}')
        else:
            lines.append(f'{ind}"{key}"\t"{value}"')
    return "\n".join(lines)

async def send_vdf_response(response_data_dict: dict, status_code: int = 200) -> web.Response:
    """
    Serializes a dictionary to VDF and returns an aiohttp.web.Response.
    """
    vdf_text = serialize_vdf(response_data_dict)
    return web.Response(text=vdf_text, content_type='text/plain', status=status_code)

async def send_json_response(response_data_dict: dict, status_code: int = 200) -> web.Response:
    """
    Serializes a dictionary to JSON and returns an aiohttp.web.Response.
    """
    return web.json_response(data=response_data_dict, status=status_code)



# =============================================================================
# Middlewares
# =============================================================================

@web.middleware
async def log_middleware(request, handler):
    """
    Simple logging middleware that prints the client IP, method, and URL.
    """
    client_ip = request.remote
    method = request.method
    url = str(request.url)
    print(f"Connection from {client_ip}: {method} {url}")
    return await handler(request)

@web.middleware
async def steam_nonce_middleware(request, handler):
    """
    Middleware to check for the header "x-steam-nonce" in the request.
    If present, the same header is set on the response.
    """
    response = await handler(request)
    nonce = request.headers.get("x-steam-nonce")
    if nonce:
        response.headers["x-steam-nonce"] = nonce
    return response

# =============================================================================
# Request Handlers / Endpoints
# =============================================================================

async def server_status(request):
    """
    GET /server-status
    Returns a VDF registry with keys "csid", "load", and "cell".
    """
    print(f"{request.remote} - Server status requested")
    status_dict = {
        "csid": str(server_id),
        "load": f"{server_load:.2f}",
        "cell": config.get("cellid", "unknown")
    }
    vdf_data = {"status": status_dict}
    text = serialize_vdf(vdf_data)
    return web.Response(text=text, content_type='text/plain')

async def server_list(request):
    """
    GET /serverlist/{cell_id}/{max_results}
    Returns a VDF registry listing dummy content servers.
    """
    cell_id = request.match_info.get('cell_id')
    max_results = request.match_info.get('max_results')
    try:
        cell_id_int = int(cell_id)
        max_results_int = int(max_results)
    except ValueError:
        return web.Response(status=404, text="Not Found")

    print(f"{request.remote} - Servers list requested for cell {cell_id_int} ({max_results_int} results max)")
    servers = get_dummy_content_servers(cell_id_int, max_results_int)

    serverlist_dict = {}
    for index, server in enumerate(servers):
        key = str(index)
        if server['type'] == "CDN":
            server_dict = {
                "type": "CDN",
                "vhost": server['hostname'],
                "host": server['ipPort'],
                "load": f"{server['load']}",
                "weightedload": f"{server['weightLoad']}",
                "sourceid": str(server['contentServerId']),
                "numentriesinclientlist": "1",
                "https_support": "optional"
            }
        elif server['type'] == "CS":
            server_dict = {
                "type": "CS",
                "sourceid": str(server['contentServerId']),
                "cell": str(server.get('cellId', '')),
                "load": f"{server['load']}",
                "weightedload": f"{server['weightLoad']}",
                "host": server['ipPort'],
                "vhost": server['hostname'],
                "usetokenauth": "1",
                "numentriesinclientlist": "1",
                "https_support": "optional"
            }
        elif server['type'] == "SteamCache":
            server_dict = {
                "type": "SteamCache",
                "sourceid": str(server['contentServerId']),
                "cell": str(server.get('cellId', '')),
                "load": f"{server['load']}",
                "weightedload": f"{server['weightLoad']}",
                "host": server['ipPort'],
                "vhost": server['hostname'],
                "numentriesinclientlist": "1",
                "https_support": "optional"
            }
        else:
            server_dict = {}
        serverlist_dict[key] = server_dict

    vdf_data = {"serverlist": serverlist_dict}
    text = serialize_vdf(vdf_data)
    return web.Response(text=text, content_type='text/plain')

async def init_session(request):
    """
    POST /initsession
    Expects POST parameters "sessionkey" and "appticket".
    On success a new session is created (lasting at least 3 minutes) and a
    VDF registry response is sent back containing the session id, req-counter, and csid.
    """
    if request.method != 'POST':
        return web.Response(status=405, text="Method Not Allowed")

    data = await request.post()
    encoded_session_key = data.get("sessionkey")
    encoded_encrypted_app_ticket = data.get("appticket")
    if not encoded_session_key or not encoded_encrypted_app_ticket:
        print(f"{request.remote} - Required parameters not found")
        return web.Response(status=401, text="Unauthorized")

    # In a real implementation these values would be URL-decoded and binary data processed.
    session_key = encoded_session_key
    encrypted_app_ticket = encoded_encrypted_app_ticket

    if len(session_key) != RSA_ENCRYPTED_KEY_LENGTH:
        print(f"{request.remote} - Invalid session key length")
        return web.Response(status=401, text="Unauthorized")

    # Simulate obtaining the decrypted encryption key.
    encryption_key = "X" * ENCRYPTION_KEY_LENGTH  # dummy value

    # Simulate symmetric decryption of the app ticket.
    ticket = symmetric_decrypt_app_ticket(encrypted_app_ticket, encryption_key)
    if not ticket:
        return web.Response(status=401, text="Unauthorized")

    # Validate the ticket.
    if ticket.get("app_id") != STEAM_APP_ID_WINUI or not validate_app_ticket(ticket):
        print(f"{request.remote} - Invalid app ticket: {ticket}")
        return web.Response(status=401, text="Unauthorized")

    # Generate a new session id and create a session.
    client_ip = request.remote
    session_id = generate_session_id(client_ip)
    session = Session(session_id, client_ip, encryption_key)
    sessions[session_id] = session

    # Build the response registry.
    response_dict = {
        "sessionid": session_id,
        "req-counter": "0",
        "csid": str(server_id)
    }
    vdf_data = {"response": response_dict}
    text = serialize_vdf(vdf_data)
    resp = web.Response(text=text, content_type='text/plain')
    resp.set_cookie("sessionid", session_id, max_age=SESSION_TIMEOUT)
    print(f"{client_ip} - User opened session {session_id}")
    return resp

async def auth_depot(request):
    """
    POST /authdepot
    Requires a valid session (found via the cookie "sessionid") and POST parameter "appticket".
    The decrypted app ticket is validated and then stored into the session attributes.
    """
    if request.method != 'POST':
        return web.Response(status=405, text="Method Not Allowed")

    session_id = request.cookies.get("sessionid")
    if not session_id or session_id not in sessions:
        print(f"{request.remote} - Session not found")
        return web.Response(status=401, text="Unauthorized")

    session = sessions[session_id]
    session.last_accessed = time.time()  # update last access time

    data = await request.post()
    encoded_encrypted_app_ticket = data.get("appticket")
    if not encoded_encrypted_app_ticket:
        print(f"{request.remote} - Required parameter 'appticket' not found")
        return web.Response(status=401, text="Unauthorized")

    # Simulate decryption using the session's encryption key.
    ticket = symmetric_decrypt_app_ticket(encoded_encrypted_app_ticket, session.encryption_key)
    if not ticket or not validate_app_ticket(ticket):
        print(f"{request.remote} - Invalid ticket in authdepot")
        return web.Response(status=401, text="Unauthorized")

    print(f"{request.remote} - User #{hex(ticket.get('steam_global_id', 0))} authenticated for depot {ticket.get('app_id')}")
    # Save the ticket in the session attributes under a key based on app id.
    key_name = f"CS_APP_TICKET_{ticket.get('app_id')}"
    session.attributes[key_name] = ticket
    return web.Response(status=200, text="OK")

async def depot_handler(request):
    """
    Handles any request to /depot/{depot_id}/{service}
    This stub logs the request and calls a dummy filesystem function.
    """
    depot_id = request.match_info.get('depot_id')
    service = request.match_info.get('service')
    print(f"{request.remote} - Depot requested: depot_id={depot_id}, service={service}")
    result = handle_depot_filesystem(depot_id, service)
    return web.Response(text=result, content_type='text/plain')

def string_to_language_enum(lang_str: str) -> LanguageEnum:
    """Converts a language string to LanguageEnum member."""
    try:
        return LanguageEnum[lang_str.upper()]
    except KeyError:
        # Fallback for common variations or simple cases
        if lang_str.lower() == "simplified_chinese":
            return LanguageEnum.SIMPLIFIED_CHINESE
        if lang_str.lower() == "traditional_chinese":
            return LanguageEnum.TRADITIONAL_CHINESE
        return LanguageEnum.ENGLISH # Default

async def join_get_handler(request: web.Request) -> web.Response:
    """Handles GET requests for the /join/ page."""
    query_params = request.query
    error_msg = query_params.get("error")
    language_str = query_params.get("l", "english") 

    language_enum = string_to_language_enum(language_str)
    language_value_for_form = language_enum.value # Integer value for hidden field

    html_parts = []
    steam_web_interface.writeJoinHtmlPageHeader(html_parts, language_enum, error_message=error_msg)
    
    labels = steam_web_interface.getJoinHtmlPageLabels(language_enum)

    form_html = f"""
    <form method="POST" action="/join/">
        <input type="hidden" name="l" value="{language_str}">
        <input type="hidden" name="language_value" value="{language_value_for_form}">
        <table>
            <tr><td>{labels['accountName']}:</td><td><input type="text" name="accountname" size="30"></td></tr>
            <tr><td>{labels['password']}:</td><td><input type="password" name="password" size="30"></td></tr>
            <tr><td>{labels['confirmPassword']}:</td><td><input type="password" name="confirmpassword" size="30"></td></tr>
            <tr><td>{labels['email']}:</td><td><input type="text" name="email" size="30"></td></tr>
            <tr><td colspan="2"><input type="submit" value="{labels['confirm']}"></td></tr>
        </table>
    </form>
    """
    html_parts.append(form_html)
    
    steam_web_interface.writeJoinHtmlPageFooter(html_parts, language_enum)
    
    return web.Response(text="".join(html_parts), content_type='text/html')

async def join_post_handler(request: web.Request) -> web.Response:
    """Handles POST requests for the /join/ page (account creation attempt)."""
    form_data = await request.post()
    
    language_str = form_data.get("l", "english")
    language_enum: LanguageEnum
    try:
        language_value = int(form_data.get("language_value", LanguageEnum.ENGLISH.value))
        language_enum = LanguageEnum(language_value)
    except ValueError:
        language_enum = LanguageEnum.ENGLISH # Default if parsing or enum conversion fails

    account_name = form_data.get("accountname")
    password = form_data.get("password")
    confirm_password = form_data.get("confirmpassword")
    email = form_data.get("email")

    # Basic validation
    if not all([account_name, password, confirm_password, email]):
        # The error string 'missing_fields' can be mapped to a ResultTypeEnum if desired for internal logging,
        # but for URL redirection, a simple string is often clear.
        return web.HTTPFound(f'/join/?l={language_str}&error=missing_fields') 
    
    if password != confirm_password:
        return web.HTTPFound(f'/join/?l={language_str}&error=password_mismatch')

    account_name_lower = account_name.lower() # Consistent with C++ join.h

    validation_error_str = steam_web_interface.validateNewAccountParameters(account_name_lower, password, email)
    if validation_error_str:
        # validation_error_str is "space" or "email". These are kept as strings for URL.
        return web.HTTPFound(f'/join/?l={language_str}&error={validation_error_str}')

    # Simulate account creation attempt
    # In C++, this would involve:
    # CMServer * cmServer = steam_web_interface->getCMServer();
    # if (cmServer) result = cmServer->getServerInterface()->createAccount(account_name_lower, password, email, &created_steam_global_id);
    # else result = Result_ServiceUnavailable;
    
    # Since getCMServer() and subsequent calls are stubs, we simulate this.
    result_code_enum = ResultTypeEnum.SERVICE_UNAVAILABLE # Default simulated result
    created_steam_global_id = 0
    
    # Example of how one might try to call the stubbed methods (optional for this step):
    # try:
    #     cm_server = steam_web_interface.getCMServer() # This will raise NotImplementedError
    #     if cm_server:
    #         # Conceptual: result_code_enum, created_steam_global_id = cm_server.getServerInterface().createAccount(...)
    #         pass # This part is also not implemented
    #     else:
    #         result_code_enum = ResultTypeEnum.SERVICE_UNAVAILABLE 
    # except NotImplementedError:
    #     result_code_enum = ResultTypeEnum.NOT_IMPLEMENTED


    html_parts = []
    # Note: The C++ code uses `accountName` (original case) for the result page, not `account_name_lower`.
    # Let's stick to `account_name` as per the C++ `writeJoinResultHtmlPage` call in `join.h`
    steam_web_interface.writeJoinResultHtmlPage(html_parts, account_name, password, email, language_enum, result_code_enum, created_steam_global_id)
    
    return web.Response(text="".join(html_parts), content_type='text/html')

async def change_password_get_handler(request: web.Request) -> web.Response:
    """Handles GET requests for the /changepassword/ page."""
    query_params = request.query
    error_msg = query_params.get("error")
    language_str = query_params.get("l", "english")

    language_enum = string_to_language_enum(language_str)
    language_value_for_form = language_enum.value

    html_parts = []
    steam_web_interface.writeChangePasswordHtmlPageHeader(html_parts, language_enum, error_message=error_msg)
    
    labels = steam_web_interface.getChangePasswordHtmlPageLabels(language_enum)

    form_html = f"""
    <form method="POST" action="/changepassword/">
        <input type="hidden" name="l" value="{language_str}">
        <input type="hidden" name="language_value" value="{language_value_for_form}">
        <table>
            <tr><td>{labels['password']}:</td><td><input type="password" name="password" size="30"></td></tr>
            <tr><td>{labels['newPassword']}:</td><td><input type="password" name="newpassword" size="30"></td></tr>
            <tr><td>{labels['confirmPassword']}:</td><td><input type="password" name="confirmpassword" size="30"></td></tr>
            <tr><td colspan="2"><input type="submit" value="{labels['confirm']}"></td></tr>
        </table>
    </form>
    """
    html_parts.append(form_html)
    
    steam_web_interface.writeChangePasswordHtmlPageFooter(html_parts, language_enum)
    
    return web.Response(text="".join(html_parts), content_type='text/html')

async def change_password_post_handler(request: web.Request) -> web.Response:
    """Handles POST requests for the /changepassword/ page."""
    form_data = await request.post()
    
    language_str = form_data.get("l", "english")
    language_enum: LanguageEnum
    try:
        language_value = int(form_data.get("language_value", LanguageEnum.ENGLISH.value))
        language_enum = LanguageEnum(language_value)
    except ValueError:
        language_enum = LanguageEnum.ENGLISH

    password = form_data.get("password")
    new_password = form_data.get("newpassword")
    confirm_password = form_data.get("confirmpassword")

    if not all([password, new_password, confirm_password]):
        return web.HTTPFound(f'/changepassword/?l={language_str}&error=missing_fields')
    
    if new_password != confirm_password:
        return web.HTTPFound(f'/changepassword/?l={language_str}&error=password_mismatch')

    # Simulate password change logic (dependencies are stubs)
    simulated_result_code_enum = ResultTypeEnum.OK 

    html_parts = []
    steam_web_interface.writeChangePasswordResultHtmlPage(html_parts, password, language_enum, simulated_result_code_enum)
    
    return web.Response(text="".join(html_parts), content_type='text/html')

async def change_email_get_handler(request: web.Request) -> web.Response:
    """Handles GET requests for the /changeemail/ page."""
    query_params = request.query
    error_msg = query_params.get("error")
    language_str = query_params.get("l", "english")

    language_enum = string_to_language_enum(language_str)
    language_value_for_form = language_enum.value

    html_parts = []
    steam_web_interface.writeChangeEmailHtmlPageHeader(html_parts, language_enum, error_message=error_msg)
    
    labels = steam_web_interface.getChangeEmailHtmlPageLabels(language_enum)

    form_html = f"""
    <form method="POST" action="/changeemail/">
        <input type="hidden" name="l" value="{language_str}">
        <input type="hidden" name="language_value" value="{language_value_for_form}">
        <table>
            <tr><td>{labels['password']}:</td><td><input type="password" name="password" size="30"></td></tr>
            <tr><td>{labels['email']}:</td><td><input type="text" name="email" size="30"></td></tr>
            <tr><td colspan="2"><input type="submit" value="{labels['confirm']}"></td></tr>
        </table>
    </form>
    """
    html_parts.append(form_html)
    
    steam_web_interface.writeChangeEmailHtmlPageFooter(html_parts, language_enum)
    
    return web.Response(text="".join(html_parts), content_type='text/html')

async def change_email_post_handler(request: web.Request) -> web.Response:
    """Handles POST requests for the /changeemail/ page."""
    form_data = await request.post()
    
    language_str = form_data.get("l", "english")
    language_enum: LanguageEnum
    try:
        language_value = int(form_data.get("language_value", LanguageEnum.ENGLISH.value))
        language_enum = LanguageEnum(language_value)
    except ValueError:
        language_enum = LanguageEnum.ENGLISH

    password = form_data.get("password")
    new_email = form_data.get("email")

    if not all([password, new_email]):
        return web.HTTPFound(f'/changeemail/?l={language_str}&error=missing_fields')

    validation_error_str = steam_web_interface.validateChangeEmailParameters(new_email)
    if validation_error_str:
        # validation_error_str is "email". Kept as string for URL.
        return web.HTTPFound(f'/changeemail/?l={language_str}&error={validation_error_str}')

    # Simulate email change logic (dependencies are stubs)
    simulated_result_code_enum = ResultTypeEnum.OK

    html_parts = []
    steam_web_interface.writeChangeEmailResultHtmlPage(html_parts, new_email, language_enum, simulated_result_code_enum)
    
    return web.Response(text="".join(html_parts), content_type='text/html')

async def get_cm_list_handler(request: web.Request) -> web.Response:
    """Handles GET requests for /api/getcmlist/ to provide CM and WebSocket CM server lists."""
    query_params = request.query
    try:
        cell_id = int(query_params.get("cellid", "0"))
    except ValueError:
        cell_id = 0

    cm_servers_list = []
    ws_servers_list = []
    
    cm_servers_result_data: typing.Any = []
    ws_servers_result_data: typing.Any = []

    try:
        # Note: getCMServers expects an output list to populate.
        # The boolean return indicates success.
        success_cm = steam_web_interface.getCMServers(cell_id=cell_id, servers_out_list=cm_servers_list)
        if success_cm:
            cm_servers_result_data = cm_servers_list # This would be a list of server strings
        else:
            # This case implies the method is implemented but failed to get data.
            # For this exercise, we'll treat it as if data wasn't populated or an error occurred.
            cm_servers_result_data = {"error": "Failed to retrieve CM servers"} 
    except NotImplementedError:
        cm_servers_result_data = {"error": "getCMServers not implemented"}
    except Exception as e: # Catch any other unexpected error from the call
        cm_servers_result_data = {"error": f"Error calling getCMServers: {str(e)}"}


    try:
        # Note: getWebSocketCMServers expects an output list to populate.
        success_ws = steam_web_interface.getWebSocketCMServers(cell_id=cell_id, servers_out_list=ws_servers_list)
        if success_ws:
            ws_servers_result_data = ws_servers_list # This would be a list of server strings
        else:
            ws_servers_result_data = {"error": "Failed to retrieve WebSocket CM servers"}
    except NotImplementedError:
        ws_servers_result_data = {"error": "getWebSocketCMServers not implemented"}
    except Exception as e: # Catch any other unexpected error from the call
        ws_servers_result_data = {"error": f"Error calling getWebSocketCMServers: {str(e)}"}

    response_data = {
        "response": {
            # Ensure data is VDF-serializable (e.g. lists of strings, or dicts for errors)
            "cm_servers": cm_servers_result_data if isinstance(cm_servers_result_data, dict) else \
                          [str(s) for s in cm_servers_result_data], # Convert to list of strings if not error
            "ws_servers": ws_servers_result_data if isinstance(ws_servers_result_data, dict) else \
                          [str(s) for s in ws_servers_result_data], # Convert to list of strings if not error
        }
    }
    
    # The VDF serializer expects keys and values to be strings or nested dicts.
    # If cm_servers_result_data or ws_servers_result_data are lists, they need to be converted
    # to a dict structure for serialize_vdf, e.g. {"0": "server1", "1": "server2"}
    
    final_response_data = {"response": {}}
    if isinstance(response_data["response"]["cm_servers"], dict): # Error case
        final_response_data["response"]["cm_servers"] = response_data["response"]["cm_servers"]
    else: # List of servers
        final_response_data["response"]["cm_servers"] = {str(i): s for i, s in enumerate(response_data["response"]["cm_servers"])}

    if isinstance(response_data["response"]["ws_servers"], dict): # Error case
        final_response_data["response"]["ws_servers"] = response_data["response"]["ws_servers"]
    else: # List of servers
        final_response_data["response"]["ws_servers"] = {str(i): s for i, s in enumerate(response_data["response"]["ws_servers"])}
        
    return await send_vdf_response(final_response_data)

# =============================================================================
# App Factory Functions (for two different ports)
# =============================================================================

def create_content_app():
    """
    Create the content server app (e.g. on port 8080)
    This app registers all endpoints including those that use sessions.
    """
    app = web.Application(middlewares=[log_middleware, steam_nonce_middleware])
    app.router.add_get('/server-status', server_status)
    app.router.add_get('/serverlist/{cell_id}/{max_results}', server_list)
    app.router.add_post('/initsession', init_session)
    app.router.add_post('/authdepot', auth_depot)
    app.router.add_route('*', '/depot/{depot_id}/{service}', depot_handler)
    
    # Register join handlers
    app.router.add_get('/join/', join_get_handler)
    app.router.add_post('/join/', join_post_handler)
    
    # Register change password handlers
    app.router.add_get('/changepassword/', change_password_get_handler)
    app.router.add_post('/changepassword/', change_password_post_handler)

    # Register change email handlers
    app.router.add_get('/changeemail/', change_email_get_handler)
    app.router.add_post('/changeemail/', change_email_post_handler)

    # Register CM list handler
    app.router.add_get('/api/getcmlist/', get_cm_list_handler)
    
    return app

def create_cdn_app():
    """
    Create the CDN cached content server app (e.g. on port 8081)
    In this example the CDN app only registers endpoints that do not require session management.
    """
    app = web.Application(middlewares=[log_middleware, steam_nonce_middleware])
    app.router.add_get('/server-status', server_status)
    # Optionally add /serverlist if the CDN server is to serve server lists.
    app.router.add_route('*', '/depot/{depot_id}/{service}', depot_handler)
    return app

# =============================================================================
# Main: Start Two Servers Concurrently
# =============================================================================

async def start_servers():
    content_app = create_content_app()
    cdn_app = create_cdn_app()

    # Create runners and sites for the two apps.
    content_runner = web.AppRunner(content_app)
    await content_runner.setup()
    content_site = web.TCPSite(content_runner, "0.0.0.0", 8080)

    cdn_runner = web.AppRunner(cdn_app)
    await cdn_runner.setup()
    cdn_site = web.TCPSite(cdn_runner, "0.0.0.0", 8081)

    await content_site.start()
    await cdn_site.start()

    print("Servers started:")
    print(" - Content server on port 8080")
    print(" - CDN cached content server on port 8081")
    # Run forever.
    while True:
        await asyncio.sleep(3600)

def main():
    loop = asyncio.get_event_loop()
    try:
        # Schedule the session cleanup task.
        loop.create_task(cleanup_sessions())
        # Start both servers concurrently.
        loop.run_until_complete(start_servers())
    except KeyboardInterrupt:
        print("Server shutting down...")
    finally:
        loop.close()

if __name__ == '__main__':
    main()
