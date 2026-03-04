#!/usr/bin/env python3
"""
Refactored Administration Server

Packet format:
  HEADER (4 bytes) + CMD (1 byte) + LENGTH (4 bytes, big-endian) + PAYLOAD + CHECKSUM (2 bytes)

Supported command codes:
  - User management:       b'\x0A', b'\x0B', b'\x0C', b'\x0D'
  - Subscription commands: b'\x16', b'\x17', b'\x20'..b'\x25'
  - Admin commands:        b'\x0E', b'\x1E', b'\x11', b'\x13'
  - Handshake:             b'\x01'
  - Login:                 b'\x02'
  - Log off:               b'\x04'
  - Heartbeat:             b'\x05' # Keep session alive, prevent timeout
  - FTP Review commands:   b'\x40' (list), b'\x41' (approve), b'\x42' (deny)
  - Streaming request:     b'\xFF'
  - List Blobs:            b'\x30' # For remote_admintool
  - Swap Blob:             b'\x31' # For remote_admintool
  - Directory Lookups:     b'\x12', b'\x03', ... (handled by DIR_COMMAND_MAP)
  - Find Content Servers:  b'\x50' 
  - Blobmgr List Blobs:    b'\x63' # For blobmgr.py
  - Blobmgr Swap Blob:     b'\x62' # For blobmgr.py
  - Get Full Dir List:     b'\x70' # For full directory server list
  - Add DirServer Entry:   b'\x71' # Add entry to DirServerManager
  - Del DirServer Entry:   b'\x72' # Remove entry from DirServerManager
  - Get Full Content List: b'\x73' # For full content server list
  - Add ContentSrv Entry:  b'\x74' # Add entry to ContentServerManager
  - Del ContentSrv Entry:  b'\x75' # Remove entry from ContentServerManager
  - Get IP Whitelist:      b'\x80'
  - Get IP Blacklist:      b'\x81'
  - Add to IP Whitelist:   b'\x82'
  - Add to IP Blacklist:   b'\x83'
  - Del from IP Whitelist: b'\x84'
  - Del from IP Blacklist: b'\x85'
  - Restart Server Thread: b'\x90' (hot-reload with code changes)
  - Get Restartable Servers: b'\x91'
  - Restart Server No Reload: b'\x92' (restart without code reload)


Includes an attempted login limit and stub streaming function.
"""

import binascii
import logging
import os
import zlib
import socket
import struct
from bisect import bisect_right
from zlib import decompress
from struct import unpack
import time
import shutil
import json
from datetime import datetime
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from Crypto.Cipher import AES
from Crypto.Protocol.KDF import scrypt

import globalvars
import utils
from utilities.database.admin_db import admin_dbdriver
from utilities.database.ftp_db import ftp_dbdriver
from utilities.database.cmdb import cm_dbdriver
from utilities.database import ccdb
from utilities.database.base_dbdriver import (
    ChatRoomRegistry,
    CommunityClanRegistry,
    ClientInventoryItems,
)
from utilities.networkhandler import TCPNetworkHandler
import servers.managers.dirlistmanager as dirlistmanager 
import servers.managers.contentlistmanager as contentlistmanager
from utilities.impsocket import ImpSocket
from utilities import blobs, server_stats, thread_handler
from utilities.cdr_manipulator import merge_xml_into_cached_blobs, cache_cdr
from servers.permissions import (
    EDIT_ADMINS,
    EDIT_USERS,
    CONFIG_EDIT,
    SERVER_LIST_EDIT,
    FTP_APPROVAL,
    FTP_USER_MANAGE,
    SUBSCRIPTION_EDIT,
    CHATROOM_MANAGE,
    CLAN_MANAGE,
    NEWS_MANAGE,
    LICENSE_MANAGE,
    TOKEN_MANAGE,
    INVENTORY_EDIT,
)

# --- Constants ---
HEADER = b"\xbe\xee\xee\xff"
EXPECTED_HEADER = HEADER
MAX_LOGIN_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 300
CMD_LOGOFF = b'\x04'
CMD_HEARTBEAT = b'\x05'  # Heartbeat command for admin tool inactivity tracking
CMD_FIND_CONTENT_SERVERS_BY_APPID = b'\x50'
CMD_INTERACTIVE_CONTENT_SERVER_FINDER = b'\x51'
CMD_LIST_BLOBS = b'\x30'  # Remote admin tool - list blobs
CMD_SWAP_BLOB = b'\x31'   # Remote admin tool - swap blob
CMD_BLOBMGR_LIST_BLOBS = b'\x63'
CMD_BLOBMGR_SWAP_BLOB = b'\x62'
CMD_GET_FULL_DIRSERVER_LIST = b'\x70'
CMD_ADD_DIRSERVER_ENTRY = b'\x71'
CMD_DEL_DIRSERVER_ENTRY = b'\x72'
CMD_GET_FULL_CONTENTSERVER_LIST = b'\x73'
CMD_ADD_CONTENTSERVER_ENTRY = b'\x74' 
CMD_DEL_CONTENTSERVER_ENTRY = b'\x75'
CMD_GET_IP_WHITELIST = b'\x80' 
CMD_GET_IP_BLACKLIST = b'\x81' 
CMD_ADD_TO_IP_WHITELIST = b'\x82' 
CMD_ADD_TO_IP_BLACKLIST = b'\x83' 
CMD_DEL_FROM_IP_WHITELIST = b'\x84'
CMD_DEL_FROM_IP_BLACKLIST = b'\x85'
CMD_RESTART_SERVER_THREAD = b'\x90'  # Hot reload (reloads code from disk)
CMD_GET_RESTARTABLE_SERVERS = b'\x91'
CMD_RESTART_SERVER_NO_RELOAD = b'\x92'  # Restart without code reload
CMD_GET_DETAILED_BLOB_LIST = b'\x32' # Command for Detailed Blob List
CMD_EDIT_ADMIN_RIGHTS = b'\x34'
CMD_REMOVE_ADMIN = b'\x35'
CMD_LIST_ADMINS = b'\x36'
CMD_CREATE_ADMIN = b'\x37'
CMD_CHANGE_ADMIN_USERNAME = b'\x38'
CMD_CHANGE_ADMIN_EMAIL = b'\x39'
CMD_CHANGE_ADMIN_PASSWORD = b'\x3A'
CMD_LIST_USER_SUBSCRIPTIONS = b'\x20'
CMD_ADD_SUBSCRIPTION = b'\x21'
CMD_REMOVE_SUBSCRIPTION = b'\x22'
CMD_LIST_GUEST_PASSES = b'\x23'
CMD_ADD_GUEST_PASS = b'\x24'
CMD_REMOVE_GUEST_PASS = b'\x25'
CMD_LIST_FTP_USERS = b'\x43'
CMD_ADD_FTP_USER = b'\x44'
CMD_REMOVE_FTP_USER = b'\x45'
CMD_CONTENT_PURGE = b'\x60'
CMD_GET_SERVER_STATS = b'\x61'
CMD_GET_LIVE_LOG = b'\xA0'
CMD_GET_AUTH_STATS = b'\xA1'
CMD_SET_RATE_LIMIT = b'\xA2'
CMD_GET_BW_STATS = b'\xA3'
CMD_GET_CONN_COUNT = b'\xA4'
CMD_EDIT_CONFIG = b'\xA5'
CMD_TOGGLE_FEATURE = b'\xA6'
CMD_GET_SESSION_REPORT = b'\xA7'
CMD_SET_FTP_QUOTA = b'\xA8'
CMD_HOT_RELOAD_CONFIG = b'\xA9'
CMD_CHATROOM_OP = b'\xB0'
CMD_CLAN_OP = b'\xB1'
CMD_GIFT_OP = b'\xB2'
CMD_NEWS_OP = b'\xB3'
CMD_LICENSE_OP = b'\xB4'
CMD_TOKEN_OP = b'\xB5'
CMD_INVENTORY_OP = b'\xB6'

def compute_checksum(data: bytes) -> bytes:
    checksum = sum(data) % 65536
    return struct.pack('>H', checksum)

def verify_checksum(data: bytes, checksum: bytes) -> bool:
    return compute_checksum(data) == checksum

def build_packet(cmd: bytes, payload: bytes) -> bytes:
    length = len(payload)
    header_part = HEADER + cmd + struct.pack('>I', length)
    packet_without_checksum = header_part + payload
    checksum = compute_checksum(packet_without_checksum)
    return packet_without_checksum + checksum

def parse_packet(packet: bytes):
    if len(packet) < 11:
        raise ValueError("Packet too short")
    if packet[:4] != HEADER:
        raise ValueError("Invalid header")
    cmd = packet[4:5]
    length = struct.unpack('>I', packet[5:9])[0]
    if len(packet) != 4 + 1 + 4 + length + 2:
        raise ValueError(f"Packet length mismatch. Expected: {4+1+4+length+2}, Got: {len(packet)}")
    payload = packet[9:9+length]
    checksum = packet[-2:]
    if not verify_checksum(packet[:-2], checksum):
        raise ValueError("Checksum verification failed")
    return cmd, payload

def recv_full_packet(sock):
    """Read an entire packet from the socket using length prefix."""
    header = sock.recv_all(9)
    if not header or len(header) < 9:
        return None
    if header[:4] != HEADER:
        raise ValueError("Invalid header")
    length = struct.unpack('>I', header[5:9])[0]
    body = sock.recv_all(length + 2)
    if not body or len(body) < length + 2:
        return None
    return header + body

def derive_key(shared_secret, salt):
    return scrypt(shared_secret, salt, 32, N=2**14, r=8, p=1)

def encrypt_message(key, plaintext):
    cipher = AES.new(key, AES.MODE_CFB)
    ciphertext = cipher.iv + cipher.encrypt(plaintext)
    logging.debug(f"Encrypting message. IV: {cipher.iv.hex()}")
    return ciphertext

def decrypt_message(key, ciphertext):
    iv = ciphertext[:16]
    if len(iv) != 16:
        raise ValueError("Invalid IV length for decryption")
    cipher = AES.new(key, AES.MODE_CFB, iv=iv)
    return cipher.decrypt(ciphertext[16:])

def stream_status():
    return "Streaming: In 1024B/s, Out 2048B/s, Connections: 3"
# --- Administration Server Class ---
class administrationserver(TCPNetworkHandler):
    DIR_COMMAND_MAP = {
        b'\x12': "AUTHSERV",
        b'\x03': "CONFIGSERV",
    }

    @staticmethod
    def get_restartable_servers():
        """
        Get the list of actually registered servers from thread_handler.
        Returns a list of server identifiers that can be restarted.
        CM servers (CMTCP27014, CMTCP27017, CMUDP27014, CMUDP27017) are consolidated into "CMSERVER".
        """
        servers = list(thread_handler.server_registry.keys())
        # Consolidate CM servers into a single CMSERVER entry
        cm_servers = [s for s in servers if s.startswith('CMTCP') or s.startswith('CMUDP')]
        non_cm_servers = [s for s in servers if not (s.startswith('CMTCP') or s.startswith('CMUDP'))]
        if cm_servers:
            non_cm_servers.append('CMSERVER')
        return non_cm_servers


    def __init__(self, port, config):
        self.server_type = "AdminServer"
        self.config = config 
        self.database = admin_dbdriver(config)
        self.ftp_database = ftp_dbdriver(config)
        self.community_db = cm_dbdriver(config)
        self.authenticated_ips = globalvars.authenticated_ips
        self.client_info = {}
        self.client_last_heartbeat = {}
        self.logged_in_admins = {}  # Maps username -> client_address for duplicate login prevention
        super(administrationserver, self).__init__(config, port, self.server_type)
        self.log = logging.getLogger(self.server_type)
        self.auth_stats = {"success": 0, "failure": 0}
        self.rate_limit_kbps = int(config.get('rate_limit', '0'))
        self.bandwidth_usage = {"tx": 0, "rx": 0}
        self.feature_flags = {}
        self.ftp_quota = {}
        self._load_ftp_quota()

        # Initialize blob cache with lazy loading support
        self._blob_cache = None  # None = not loaded yet (lazy loading)
        self._blob_cache_lock = threading.Lock()
        self._blob_cache_loading = False

    @property
    def blob_cache(self):
        """Lazy-loading property for blob cache. Loads on first access."""
        self._ensure_blob_cache_loaded()
        return self._blob_cache

    @blob_cache.setter
    def blob_cache(self, value):
        """Setter for blob cache (used during cache population)."""
        self._blob_cache = value

    def _ensure_blob_cache_loaded(self):
        """Lazy load blob cache on first access with thread safety."""
        if self._blob_cache is not None:
            return  # Already loaded

        with self._blob_cache_lock:
            if self._blob_cache is not None:
                return  # Double-check after acquiring lock

            if self._blob_cache_loading:
                return  # Another thread is loading

            self._blob_cache_loading = True
            try:
                self._cache_blob_information()
            finally:
                self._blob_cache_loading = False

    def formatstring(self, text) :
        if len(text) == 4 and text[2] == "\x00" :
            return ("'\\x%02x\\x%02x\\x%02x\\x%02x'") % (ord(text[0]), ord(text[1]), ord(text[2]), ord(text[3]))
        else :
            return repr(text)

    def blob_dump(self, blob, spacer = "") :

        text = spacer + "{"
        spacer2 = spacer + "    "

        try:
            blobkeys = blob.keys()
        except:
            blobkeys = {blob}
        #blobkeys.sort(sortfunc)
        first = True
        for key in blobkeys :

            data = blob[key]


            if type(data) == str :
                if first :
                    text = text + "\n" + spacer2 + formatstring(key) + ": " + formatstring(data)
                    first = False
                else :
                    text = text + ",\n" + spacer2 + formatstring(key) + ": " + formatstring(data)
            else :
                if first :
                    text = text + "\n" + spacer2 + formatstring(key) + ":\n" + blob_dump(data, spacer2)
                    first = False
                else :
                    text = text + ",\n" + spacer2 + formatstring(key) + ":\n" + blob_dump(data, spacer2)

        text = text + "\n" + spacer + "}"

        return text

    def blob_unserialize(self, blobtext) :
        blobdict = {}
        (totalsize, slack) = unpack("<LL", blobtext[2:10])

        if slack :
            blobdict["__slack__"] = blobtext[-(slack):]


        if (totalsize + slack) != len(blobtext) :
            raise NameError("Blob not correct length including slack space!")
        index = 10
        while index < totalsize :
            namestart = index + 6
            (namesize, datasize) = unpack("<HL", blobtext[index:namestart])
            datastart = namestart + namesize
            name = blobtext[namestart:datastart]
            dataend = datastart + datasize
            data = blobtext[datastart:dataend]
            if len(data) > 1 and data[0] == chr(0x01) and data[1] == chr (0x50) :
                sub_blob = self.blob_unserialize(data)
                blobdict[name] = sub_blob
            else :
                blobdict[name] = data
            index = index + 6 + namesize + datasize

        return blobdict
    def _cache_blob_information(self):
        """Cache blob information on server startup to improve performance.

        Optimizations applied:
        - Parallel execution: File and database operations run concurrently
        - Lazy loading: Cache is only loaded on first access
        - Firstblob caching: Avoid redundant file reads
        - os.scandir: Faster directory iteration
        - Database WHERE clause: Filter at DB level, not Python
        """
        # FIXME: Need to implement cache invalidation when blob tables are modified
        # in database operations (INSERT, UPDATE, DELETE on blob-related tables)

        start_time = time.time()
        self.log.info("Loading blob information (with parallel optimization)...")

        try:
            # DISABLED: Try to load from persistent cache first
            # Commenting out persistent cache loading to force fresh data every time
            # if self._load_cached_blob_information():
            #     self.log.info(f"Loaded blob cache from persistent storage: {len(self._blob_cache['file_blobs'])} file blobs, {len(self._blob_cache['db_blobs'])} database blobs")
            #     return

            # Initialize cache structure
            self._blob_cache = {'file_blobs': [], 'db_blobs': []}

            # Run file and database operations in PARALLEL for ~50% speedup
            # Both methods append to different keys, so they're thread-safe
            with ThreadPoolExecutor(max_workers=2, thread_name_prefix='BlobCache') as executor:
                file_future = executor.submit(self._cache_file_based_blobs)
                db_future = executor.submit(self._cache_database_blobs)

                # Wait for both to complete and propagate any exceptions
                exceptions = []
                for future in as_completed([file_future, db_future]):
                    try:
                        future.result()
                    except Exception as e:
                        exceptions.append(e)

                if exceptions:
                    for exc in exceptions:
                        self.log.error(f"Error in blob cache thread: {exc}")

            # DISABLED: Save the cache to persistent storage
            # Commenting out cache saving to disable persistent caching
            # self._save_cached_blob_information()

            elapsed = time.time() - start_time
            self.log.info(f"Blob information loaded: {len(self._blob_cache['file_blobs'])} file blobs, {len(self._blob_cache['db_blobs'])} database blobs (took {elapsed:.2f}s)")

        except Exception as e:
            self.log.error(f"Error loading blob information: {e}")
            # Initialize with empty cache if loading fails
            self._blob_cache = {'file_blobs': [], 'db_blobs': []}

    def _get_blobs_folder_size(self):
        """Calculate total size of files/blobs folder efficiently."""
        blob_base_dir = self.config.get("blobdir", "files/blobs/")
        
        if not os.path.isdir(blob_base_dir):
            return 0
        
        total_size = 0
        try:
            # Use os.scandir for efficient traversal
            with os.scandir(blob_base_dir) as entries:
                for entry in entries:
                    if entry.is_file():
                        total_size += entry.stat().st_size
        except OSError:
            return 0
        
        return total_size

    def _get_cache_file_path(self):
        """Get the path to the blob cache file."""
        cache_dir = "files/cache"
        os.makedirs(cache_dir, exist_ok=True)
        return os.path.join(cache_dir, "blob_cache.dat")

    def _load_cached_blob_information(self):
        """Load blob information from persistent cache if valid."""
        cache_file = self._get_cache_file_path()
        
        if not os.path.exists(cache_file):
            return False
        
        try:
            with open(cache_file, 'rb') as f:
                # Read the first 4 bytes (folder size)
                size_bytes = f.read(4)
                if len(size_bytes) != 4:
                    return False
                
                cached_folder_size = struct.unpack('<L', size_bytes)[0]
                
                # Get current folder size
                current_folder_size = self._get_blobs_folder_size()
                
                # Check if sizes match (within 4-byte limit, truncate if needed)
                current_size_truncated = current_folder_size & 0xFFFFFFFF
                
                if cached_folder_size != current_size_truncated:
                    self.log.info(f"Blob folder size mismatch: cached={cached_folder_size}, current={current_size_truncated}. Regenerating cache.")
                    # Remove invalid cache file
                    os.unlink(cache_file)
                    return False
                
                # Read and decompress the cached data
                compressed_data = f.read()
                cache_json = zlib.decompress(compressed_data)
                self.blob_cache = json.loads(cache_json.decode('utf-8'))
                
                return True
                
        except (OSError, json.JSONDecodeError, zlib.error, struct.error) as e:
            self.log.warning(f"Failed to load blob cache: {e}")
            # Remove corrupted cache file
            try:
                os.unlink(cache_file)
            except OSError:
                pass
            return False

    def _save_cached_blob_information(self):
        """Save blob information to persistent cache."""
        cache_file = self._get_cache_file_path()
        
        try:
            # Get current folder size and truncate to 4 bytes if needed
            folder_size = self._get_blobs_folder_size() & 0xFFFFFFFF
            
            # Serialize and compress the cache data
            cache_json = json.dumps(self.blob_cache, separators=(',', ':')).encode('utf-8')
            compressed_data = zlib.compress(cache_json, level=6)
            
            # Write to cache file: 4-byte size header + compressed data
            with open(cache_file, 'wb') as f:
                f.write(struct.pack('<L', folder_size))
                f.write(compressed_data)
            
            self.log.debug(f"Blob cache saved to {cache_file} (size: {len(compressed_data)} bytes compressed)")
            
        except (OSError, json.JSONEncodeError, zlib.error) as e:
            self.log.error(f"Failed to save blob cache: {e}")

    def ReadBlob(self, file):
        try:
            with open(file, 'rb') as f:
                data = f.read()
                f.close()
                if data[0:2] == b"\x01\x43":  # Fixed: bytes comparison
                    data = decompress(data[20:])
                data = self.blob_unserialize(data)
                
                # Safely extract version information
                steam_ver_bytes = data.get(b'\x01\x00\x00\x00')
                steamui_ver_bytes = data.get(b'\x02\x00\x00\x00')
                
                if steam_ver_bytes and steamui_ver_bytes:
                    SteamVersion = int.from_bytes(steam_ver_bytes, byteorder='little')
                    SteamUI = int.from_bytes(steamui_ver_bytes, byteorder='little')
                    return [SteamVersion, SteamUI]
                else:
                    self.log.warning(f"Missing version keys in blob: {file}")
                    return [0, 0]  # Default versions instead of failing
        except Exception as e:
            self.log.error(f"Error reading blob {file}: {e}")
            return None
    def _cache_file_based_blobs(self):
        """Cache file-based blob information using the exact logic from billysb_blob_manager.

        Optimizations applied:
        - os.scandir() instead of Path.iterdir() for faster directory iteration
        - Pre-cache all firstblob reads to avoid redundant file I/O (N reads -> M reads where M << N)
        - Cache package existence checks to avoid redundant filesystem calls
        """
        blob_base_dir = self.config.get("blobdir", "files/blobs/")
        packagedir = self.config.get("packagedir", "files/packages/")

        # Process files in the blobs directory
        if not os.path.isdir(blob_base_dir):
            self.log.warning(f"Blob directory not found: {blob_base_dir}")
            return

        # Initialize data structures exactly like billysb_blob_manager
        first_blobs = []
        second_blobs = []
        first_blob_dates = []
        second_blob_dates = []
        blob_rows = []

        # OPTIMIZATION: Caches for avoiding redundant I/O
        firstblob_info_cache = {}  # filename -> [steam_version, steamui_version]
        steam_pkg_cache = {}       # version -> bool (exists)
        steamui_pkg_cache = {}     # version -> bool (exists)

        try:
            # OPTIMIZATION: Use os.scandir() instead of Path.iterdir() for faster iteration
            # os.scandir() returns DirEntry objects with cached stat info
            with os.scandir(blob_base_dir) as entries:
                blob_files = sorted(
                    [e for e in entries if e.is_file()],
                    key=lambda x: x.name
                )

            # First pass: Process all files to build data structures (like billysb_blob_manager PopulateRows)
            current_year = None

            for item in blob_files:
                filename = item.name

                if filename.startswith("secondblob.bin"):
                    # Extract datetime from filename using exact billysb_blob_manager logic
                    # Expected format: "secondblob.bin.YYYY-MM-DD HH_MM_SS - description"
                    try:
                        # Remove 'secondblob.bin.' prefix
                        name_part = filename[len("secondblob.bin."):]
                        # Split by ' - ' to separate datetime and description
                        parts = name_part.split(' - ', 1)
                        date_str = parts[0]
                        # Parse datetime from filename
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d %H_%M_%S')
                        # Format the date and time separately
                        date_part = date_obj.strftime('%Y/%m/%d')
                        time_part = date_obj.strftime('%H:%M:%S')

                        # Combine with a larger space between date and time
                        date_display = f"{date_part}   {time_part}"
                        description = parts[1] if len(parts) > 1 else ""
                        # Check if custom
                        is_custom = '(C)' in filename

                        # Build row structure (steam/steamui versions will be filled later)
                        new_row = [
                            'Yes' if is_custom else 'No',  # Custom
                            '',  # Placeholder for Steam version
                            '',  # Placeholder for SteamUI version
                            date_display,  # Date
                            description,   # Description
                            filename       # Filename
                        ]
                        second_blobs.append(filename)
                        second_blob_dates.append((date_obj.timestamp(), filename))
                        blob_rows.append(new_row)
                    except Exception as e:
                        self.log.warning(f"Error parsing secondblob filename '{filename}': {e}")
                        continue

                elif filename.startswith("firstblob.bin"):
                    # Handle firstblob using exact billysb_blob_manager logic
                    try:
                        # Remove 'firstblob.bin.' prefix
                        name_part = filename[len("firstblob.bin."):]
                        # Remove ' (C)' suffix if present
                        if ' (' in name_part:
                            name_part = name_part.split(' (')[0]
                        # Parse datetime from filename
                        date_obj = datetime.strptime(name_part, '%Y-%m-%d %H_%M_%S')
                        first_blobs.append(filename)
                        first_blob_dates.append((date_obj.timestamp(), filename))
                        # Update landmarks based on year
                        if current_year != date_obj.year:
                            current_year = date_obj.year
                    except Exception as e:
                        self.log.warning(f"Error parsing firstblob filename '{filename}': {e}")
                        continue

            # After populating, sort the lists (like billysb_blob_manager)
            first_blob_dates.sort()
            second_blob_dates.sort()
            first_blob_timestamps = [date for date, filename in first_blob_dates]

            # OPTIMIZATION: Pre-read ALL unique firstblobs once (batch read)
            # This reduces N redundant reads to just M unique reads (where M = number of firstblobs)
            for _, fname in first_blob_dates:
                if fname not in firstblob_info_cache:
                    first_blob_path = os.path.join(blob_base_dir, fname)
                    try:
                        firstblob_info_cache[fname] = self.ReadBlob(first_blob_path)
                    except Exception as e:
                        self.log.warning(f"Error pre-reading firstblob '{fname}': {e}")
                        firstblob_info_cache[fname] = None

            # Now populate Steam/SteamUI versions using exact billysb_blob_manager FirstBlobThread logic
            for i in range(len(blob_rows)):
                second_blob_date = second_blob_dates[i][0]

                # Find the insertion point for SecondBlobDate in the sorted FirstBlobTimestamps
                idx = bisect_right(first_blob_timestamps, second_blob_date) - 1

                # Ensure we have a valid index and that the FirstBlobDate is not newer than SecondBlobDate
                if idx >= 0:
                    # Check if the found FirstBlobDate at idx is either an exact match or older than SecondBlobDate
                    if abs(first_blob_timestamps[idx] - second_blob_date) < 1 or first_blob_timestamps[idx] <= second_blob_date:
                        first_target = first_blob_dates[idx][1]
                    else:
                        first_target = None
                else:
                    first_target = None

                # OPTIMIZATION: Use cached firstblob info instead of re-reading file
                if first_target is not None:
                    info = firstblob_info_cache.get(first_target)
                else:
                    info = None

                # Update the table row with Steam and SteamUI versions
                if info is None:
                    blob_rows[i][1] = 'Unknown'
                    blob_rows[i][2] = 'Unknown'
                    steam_version = 'Unknown'
                    steamui_version = 'Unknown'
                else:
                    blob_rows[i][1] = str(info[0])
                    blob_rows[i][2] = str(info[1])
                    steam_version = str(info[0])
                    steamui_version = str(info[1])

                # OPTIMIZATION: Check package existence with caching
                pkg_exists = False
                uipkg_exists = False
                if packagedir and steam_version != 'Unknown':
                    if steam_version not in steam_pkg_cache:
                        steam_pkg_cache[steam_version] = os.path.exists(
                            os.path.join(packagedir, f"steam_{steam_version}.pkg"))
                    pkg_exists = steam_pkg_cache[steam_version]
                if packagedir and steamui_version != 'Unknown':
                    if steamui_version not in steamui_pkg_cache:
                        steamui_pkg_cache[steamui_version] = os.path.exists(
                            os.path.join(packagedir, f"steamui_{steamui_version}.pkg"))
                    uipkg_exists = steamui_pkg_cache[steamui_version]

                # Build final blob info structure
                blob_info = {
                    "Filename": blob_rows[i][5],      # filename
                    "SteamVersion": blob_rows[i][1],   # steam version
                    "SteamUIVersion": blob_rows[i][2], # steamui version
                    "Date": blob_rows[i][3],          # date display
                    "steam_pkg_exists": pkg_exists,
                    "steamui_pkg_exists": uipkg_exists,
                    "Custom": blob_rows[i][0],        # custom yes/no
                    "Description": blob_rows[i][4],   # description
                    "Type": "File"
                }

                # Use _blob_cache directly (not property) to avoid lazy-loading recursion
                self._blob_cache['file_blobs'].append(blob_info)

        except Exception as e:
            self.log.error(f"Error caching file-based blobs: {e}")
    
    def _read_firstblob_info(self, file_path):
        """Read firstblob information using exact billysb_blob_manager ReadBlob logic."""
        from zlib import decompress
        from struct import unpack
        
        with open(file_path, 'rb') as f:
            data = f.read()
            
        if data[0:2] == b"\x01\x43":
            data = decompress(data[20:])
            
        data = self._blob_unserialize(data)
        steam_version = int.from_bytes(data[b'\x01\x00\x00\x00'], byteorder='little')
        steamui_version = int.from_bytes(data[b'\x02\x00\x00\x00'], byteorder='little')
        return [steam_version, steamui_version]
        
    def _blob_unserialize(self, blobtext):
        """Blob unserialization logic from billysb_blob_manager blobreader.py."""
        from struct import unpack
        
        blobdict = {}
        (totalsize, slack) = unpack("<LL", blobtext[2:10])

        if slack:
            blobdict["__slack__"] = blobtext[-(slack):]

        pos = 10
        while pos < totalsize + 2:
            (keysize,) = unpack("<L", blobtext[pos:pos + 4])
            pos += 4
            key = blobtext[pos:pos + keysize]
            pos += keysize

            (datatype, datasize) = unpack("<LL", blobtext[pos:pos + 8])
            pos += 8

            if datatype == 1:
                blobdict[key] = blobtext[pos:pos + datasize]
            elif datatype == 2:
                blobdict[key] = self._blob_unserialize(blobtext[pos:pos + datasize])
            else:
                blobdict[key] = blobtext[pos:pos + datasize]

            pos += datasize

        return blobdict




    def _cache_database_blobs(self):
        """Cache database blob information using the same logic as billysb_blob_manager.

        Optimizations applied:
        - WHERE clause filtering at DB level (not Python) for ~85% faster queries
        - bisect_right for O(log n) firstblob matching instead of O(n) list comprehension
        - Package existence checks moved outside database loop (done after DB connection closes)
        - Cached package existence checks to avoid repeated filesystem calls
        - Database indexes on filename columns for faster LIKE queries
        """
        try:
            # Ensure database indexes exist for optimal query performance
            self._ensure_blob_indexes()

            # Import database connection utilities
            from sqlalchemy import create_engine, text

            # Get database configuration
            db_config = self.config
            database_host = db_config.get('database_host', '127.0.0.1')
            database_port = int(db_config.get('database_port', '3306'))
            database_username = db_config.get('database_username', 'stmserver')
            database_password = db_config.get('database_password', 'stmserver')
            packagedir = self.config.get("packagedir", "files/packages/")

            # Create database connection
            db_url = f"mysql+pymysql://{database_username}:{database_password}@{database_host}:{database_port}/"
            engine = create_engine(db_url)
            connection = engine.connect()

            # First, get configurations (firstblob info)
            # OPTIMIZATION: Add WHERE clause to filter at DB level instead of Python
            configurations_dict = {}
            firstblob_dates = []  # List of (timestamp, filename) tuples for binary search
            try:
                configurations_query = text("""
                    SELECT filename, steam_pkg, steamui_pkg, ccr_blobdatetime
                    FROM ClientConfigurationDB.configurations
                    WHERE filename LIKE 'firstblob.bin.%'
                """)
                configurations_result = connection.execute(configurations_query).fetchall()

                for row in configurations_result:
                    filename = row[0]
                    date_str = filename.replace('firstblob.bin.', '').replace(' (C)', '')
                    try:
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d %H_%M_%S')
                        timestamp = date_obj.timestamp()
                        configurations_dict[filename] = {
                            'steam_pkg': row[1],
                            'steamui_pkg': row[2],
                            'date': date_obj,
                            'timestamp': timestamp
                        }
                        firstblob_dates.append((timestamp, filename))
                    except ValueError:
                        self.log.warning(f"Skipping invalid filename format: {filename}")
                        continue
            except Exception as e:
                self.log.error(f"Failed to query configurations table: {e}")
                return

            # Sort firstblob_dates by timestamp for binary search (O(n log n) once)
            firstblob_dates.sort(key=lambda x: x[0])
            firstblob_timestamps = [ts for ts, _ in firstblob_dates]

            # Now get secondblob data - NO filesystem checks in this loop
            # OPTIMIZATION: Add WHERE clause to filter at DB level instead of Python
            try:
                filename_query = text("""
                    SELECT
                        filename,
                        blob_datetime,
                        comments,
                        is_custom
                    FROM
                        BetaContentDescriptionDB.filename
                    WHERE filename LIKE 'secondblob.bin.%'
                    UNION
                    SELECT
                        filename,
                        blob_datetime,
                        comments,
                        is_custom
                    FROM
                        ContentDescriptionDB.filename
                    WHERE filename LIKE 'secondblob.bin.%'
                """)
                filename_result = connection.execute(filename_query).fetchall()

                for row in filename_result:
                    filename = row[0] or ''
                    blob_datetime = row[1] or ''
                    comments = row[2] or ''
                    is_custom = row[3] or 0

                    date_str = filename.replace('secondblob.bin.', '')

                    try:
                        # Split to separate datetime and description
                        parts = date_str.split(' - ', 1)
                        date_time_str = parts[0].strip()

                        # Remove ' (C)' or similar suffixes if no description was found
                        if len(parts) == 1 and ' (' in date_time_str:
                            date_time_str = date_time_str.split(' (')[0].strip()

                        # Parse datetime
                        date_obj = datetime.strptime(date_time_str, '%Y-%m-%d %H_%M_%S')
                        secondblob_timestamp = date_obj.timestamp()

                        # Find matching firstblob using binary search - O(log n) instead of O(n)
                        steam_version = 'Unknown'
                        steamui_version = 'Unknown'

                        # Use bisect_right to find insertion point, then go back one to get
                        # the most recent firstblob that is <= secondblob date
                        idx = bisect_right(firstblob_timestamps, secondblob_timestamp) - 1
                        if idx >= 0:
                            matched_fname = firstblob_dates[idx][1]
                            steam_version = configurations_dict[matched_fname]['steam_pkg']
                            steamui_version = configurations_dict[matched_fname]['steamui_pkg']

                        # Format date for display
                        date_part = date_obj.strftime('%Y/%m/%d')
                        time_part = date_obj.strftime('%H:%M:%S')
                        date_display = f"{date_part}   {time_part}"

                        # Skip specific unwanted versions
                        if steam_version == "7" and steamui_version == "16":
                            continue

                        # Store blob info WITHOUT package existence (will be filled in later)
                        blob_info = {
                            "Filename": filename,
                            "SteamVersion": steam_version,
                            "SteamUIVersion": steamui_version,
                            "Date": date_display,
                            "steam_pkg_exists": False,  # Will be updated after DB loop
                            "steamui_pkg_exists": False,  # Will be updated after DB loop
                            "Custom": "Yes" if is_custom else "No",
                            "Description": comments,
                            "Type": "DB"
                        }

                        # Use _blob_cache directly (not property) to avoid lazy-loading recursion
                        self._blob_cache['db_blobs'].append(blob_info)

                    except ValueError:
                        self.log.warning(f"Invalid date format in filename: {filename}")
                    except Exception as e:
                        self.log.error(f"Error processing database blob '{filename}': {e}")

            except Exception as e:
                self.log.error(f"Failed to query filename table: {e}")
            finally:
                connection.close()
                engine.dispose()

            # Now check package existence AFTER database connection is closed
            # This separates DB operations from filesystem operations
            if packagedir:
                steam_pkg_cache = {}
                steamui_pkg_cache = {}

                # Use _blob_cache directly (not property) to avoid lazy-loading recursion
                for blob_info in self._blob_cache['db_blobs']:
                    steam_version = blob_info["SteamVersion"]
                    steamui_version = blob_info["SteamUIVersion"]

                    # Check steam package existence with caching
                    if steam_version != 'Unknown':
                        if steam_version not in steam_pkg_cache:
                            steam_pkg_cache[steam_version] = os.path.exists(
                                os.path.join(packagedir, f"steam_{steam_version}.pkg"))
                        blob_info["steam_pkg_exists"] = steam_pkg_cache[steam_version]

                    # Check steamui package existence with caching
                    if steamui_version != 'Unknown':
                        if steamui_version not in steamui_pkg_cache:
                            steamui_pkg_cache[steamui_version] = os.path.exists(
                                os.path.join(packagedir, f"steamui_{steamui_version}.pkg"))
                        blob_info["steamui_pkg_exists"] = steamui_pkg_cache[steamui_version]

        except Exception as e:
            self.log.error(f"Error caching database blobs: {e}")

    def _ensure_blob_indexes(self):
        """Create database indexes for blob-related tables to optimize queries.

        Creates indexes on the filename columns used in WHERE clauses:
        - ClientConfigurationDB.configurations.filename
        - BetaContentDescriptionDB.filename.filename
        - ContentDescriptionDB.filename.filename

        These indexes significantly improve query performance when filtering
        by filename patterns like 'firstblob.bin.%' and 'secondblob.bin.%'.
        """
        try:
            from sqlalchemy import create_engine, text

            db_config = self.config
            database_host = db_config.get('database_host', '127.0.0.1')
            database_port = int(db_config.get('database_port', '3306'))
            database_username = db_config.get('database_username', 'stmserver')
            database_password = db_config.get('database_password', 'stmserver')

            db_url = f"mysql+pymysql://{database_username}:{database_password}@{database_host}:{database_port}/"
            engine = create_engine(db_url)

            # Index definitions for blob-related tables
            indexes = [
                # Index on configurations.filename for firstblob lookups
                "CREATE INDEX IF NOT EXISTS idx_config_filename ON ClientConfigurationDB.configurations (filename)",
                # Index on BetaContentDescriptionDB.filename.filename for secondblob lookups
                "CREATE INDEX IF NOT EXISTS idx_beta_filename ON BetaContentDescriptionDB.filename (filename)",
                # Index on ContentDescriptionDB.filename.filename for secondblob lookups
                "CREATE INDEX IF NOT EXISTS idx_content_filename ON ContentDescriptionDB.filename (filename)",
            ]

            with engine.connect() as connection:
                for index_sql in indexes:
                    try:
                        connection.execute(text(index_sql))
                        connection.commit()
                    except Exception as e:
                        # Index might already exist or table doesn't exist
                        # This is non-fatal, just log and continue
                        self.log.debug(f"Index creation note: {e}")

            engine.dispose()
            self.log.debug("Blob table indexes verified/created")

        except Exception as e:
            # Non-fatal error - queries will still work, just slower
            self.log.warning(f"Could not ensure blob indexes (non-fatal): {e}")

    def _get_available_blobs(self):
        """Return a simple listing of available secondblob files."""
        blob_base_dir = self.config.get("blobdir", "files/blobs/")
        cdr_dir = os.path.join(blob_base_dir, "contentdescriptionrecords")
        blobs = []
        if os.path.isdir(cdr_dir):
            for entry in sorted(os.listdir(cdr_dir)):
                if entry.endswith(('.bin', '.py')):
                    blobs.append({'id': entry, 'name': entry})
        return blobs

    def _get_blob_filenames_for_blobmgr(self):
        """Return available blob filenames with basic metadata.

        The legacy implementation only returned a flat list of file names which
        required the client to perform additional stat calls to provide useful
        context to the operator.  The revised function includes the file size
        and last modification time for each entry and gracefully handles
        missing directories.  All paths are relative to the configured
        ``blobdir`` and the result is structured as ``{"first": [...],
        "second": [...]}`` where each element of the list is a dictionary with
        ``name``, ``size`` and ``mtime`` keys.
        """

        blob_base_dir = self.config.get("blobdir", "files/blobs/")
        first_dir = os.path.join(blob_base_dir, "clientconfigrecords")
        second_dir = os.path.join(blob_base_dir, "contentdescriptionrecords")
        result = {"first": [], "second": []}

        def _collect(dir_path, key):
            if not os.path.isdir(dir_path):
                self.log.debug(f"Blob directory missing: {dir_path}")
                return
            for entry in sorted(os.listdir(dir_path)):
                if not entry.endswith((".bin", ".py")):
                    continue
                file_path = os.path.join(dir_path, entry)
                try:
                    stat_res = os.stat(file_path)
                    result[key].append({
                        "name": entry,
                        "size": stat_res.st_size,
                        "mtime": stat_res.st_mtime,
                    })
                except OSError as e:
                    self.log.warning(f"Failed to stat {file_path}: {e}")

        _collect(first_dir, "first")
        _collect(second_dir, "second")
        return result

    def _validate_blob_filename(self, filename: str) -> bool:
        """Basic security checks for blob file names provided by clients."""
        if not filename:
            return False
        if "/" in filename or "\\" in filename:
            return False
        if filename.startswith('.'):
            return False
        return filename.endswith(('.bin', '.py'))

    def _perform_blob_swap(self, first_blob_name: str, second_blob_name: str) -> bool:
        """Swap active blobs with the provided filenames.

        The filenames are validated using :func:`_validate_blob_filename` to
        prevent directory traversal attacks.  A number of detailed log messages
        are emitted to aid in debugging failed swaps.  Returns ``True`` on
        success.
        """

        if not (self._validate_blob_filename(first_blob_name) and self._validate_blob_filename(second_blob_name)):
            self.log.error(f"Invalid blob names: '{first_blob_name}', '{second_blob_name}'")
            return False

        blob_base_dir = self.config.get("blobdir", "files/blobs/")
        first_blob_source_dir = os.path.join(blob_base_dir, "clientconfigrecords")
        second_blob_source_dir = os.path.join(blob_base_dir, "contentdescriptionrecords")
        first_blob_source_path = os.path.join(first_blob_source_dir, first_blob_name)
        second_blob_source_path = os.path.join(second_blob_source_dir, second_blob_name)
        active_blob_dest_dir = "files"
        os.makedirs(active_blob_dest_dir, exist_ok=True)
        first_blob_dest_path = os.path.join(active_blob_dest_dir, "firstblob.bin")
        second_blob_dest_path = os.path.join(active_blob_dest_dir, "secondblob.bin")

        self.log.info(
            f"Attempting blob swap. Source first: '{first_blob_source_path}', Source second: '{second_blob_source_path}'"
        )
        self.log.info(
            f"Destination first: '{first_blob_dest_path}', Destination second: '{second_blob_dest_path}'"
        )

        try:
            if not os.path.exists(first_blob_source_path):
                self.log.error(f"Src firstblob not found: {first_blob_source_path}")
                return False
            if not os.path.exists(second_blob_source_path):
                self.log.error(f"Src secondblob not found: {second_blob_source_path}")
                return False
            shutil.copy2(first_blob_source_path, first_blob_dest_path)
            self.log.info(f"Copied {first_blob_name} to {first_blob_dest_path}")
            shutil.copy2(second_blob_source_path, second_blob_dest_path)
            self.log.info(f"Copied {second_blob_name} to {second_blob_dest_path}")
            self.log.info("Blobs copied successfully. Attempting live reload...")
            reload_attempted = False
            if hasattr(utils, 'check_secondblob_changed'):
                try:
                    utils.check_secondblob_changed()
                    self.log.info("Called utils.check_secondblob_changed().")
                    reload_attempted = True
                except Exception as e:
                    self.log.error(f"Error calling utils.check_secondblob_changed(): {e}")
            if not reload_attempted and hasattr(ccdb, 'load_filesys_blob'):
                try:
                    ccdb.load_filesys_blob()
                    self.log.info("Called ccdb.load_filesys_blob().")
                except Exception as e:
                    self.log.error(f"Error calling ccdb.load_filesys_blob(): {e}")
            elif not reload_attempted:
                self.log.warning("Could not find reload functions.")
            return True
        except (IOError, OSError) as e:
            self.log.error(f"Blob copy error: {e}")
            return False
        except Exception as e:
            self.log.error(f"Unexpected blob swap error: {e}")
            return False

    def handle_list_blobs_request(self, sock, client_address, decrypted_data):
        """Return a simple list of available blob identifiers for the remote admin tool."""
        self.log.info(f"Received list blobs request (CMD {CMD_LIST_BLOBS.hex()}) from {client_address}")
        info = self.client_info.get(client_address, {})
        if not info.get('authenticated'):
            self.send_error(sock, client_address, "Authentication required."); return
        if not (info.get('user_rights', 0) & CONFIG_EDIT):
            self.send_error(sock, client_address, "Permission denied."); return
        try:
            blob_entries = self._get_available_blobs()
            blob_str = "|".join(f"{b['id']},{b.get('name','')}" for b in blob_entries)
            key = self.client_info[client_address]['key']
            encrypted_response = encrypt_message(key, blob_str.encode('latin-1'))
            self._send_packet(sock, build_packet(CMD_LIST_BLOBS, encrypted_response))
            self.log.info(f"Sent blob list to {client_address}")
        except Exception as e:
            self.log.error(f"Error building blob list for {client_address}: {e}")
            self.send_error(sock, client_address, "Failed to get blob list")

    def handle_swap_blob_request(self, sock, client_address, decrypted_data):
        """Handle a blob swap request from the remote admin tool."""
        self.log.info(f"Received swap blob request (CMD {CMD_SWAP_BLOB.hex()}) from {client_address}")
        info = self.client_info.get(client_address, {})
        if not info.get('authenticated'):
            self.send_error(sock, client_address, "Authentication required."); return
        if not (info.get('user_rights', 0) & CONFIG_EDIT):
            self.send_error(sock, client_address, "Permission denied."); return
        try:
            blob_id = decrypted_data.decode('latin-1').strip()
            if not blob_id:
                self.send_error(sock, client_address, "Missing blob identifier."); return

            if blob_id.startswith('secondblob'):
                first_blob_name = blob_id.replace('secondblob', 'firstblob', 1)
            else:
                first_blob_name = 'firstblob.bin'

            self.log.info(
                f"Client {client_address} requested swap to blob id '{blob_id}'"
            )
            swap_success = self._perform_blob_swap(first_blob_name, blob_id)
            key = self.client_info[client_address]['key']
            if swap_success:
                response_message = f"Swapped to {blob_id}".encode('latin-1')
                encrypted_response = encrypt_message(key, response_message)
                self._send_packet(sock, build_packet(CMD_SWAP_BLOB, encrypted_response))
            else:
                self.send_error(
                    sock,
                    client_address,
                    f"Failed to swap blobs: {first_blob_name}, {blob_id}",
                )
        except Exception as e:
            self.log.error(f"Error handling swap blob for {client_address}: {e}")
            self.send_error(sock, client_address, "Failed to process swap request")

    def handle_client(self, client_socket, client_address):
        utils.load_admin_ips()
        # ``peer_password`` is stored as text in the configuration. Ensure it is
        # consistently treated as bytes before deriving session keys so the
        # client and server generate identical results.
        shared_secret = (self.config.get('peer_password') or globalvars.peer_password).encode('utf-8')
        ip_address = client_address[0]
        self.log.info(f"Connection from {ip_address}")
        while True:
            try:
                data = recv_full_packet(client_socket)
                if data:
                    self.bandwidth_usage['rx'] += len(data)
                if not data:
                    break
                self.client_last_heartbeat[client_address] = time.time()
                try: cmd, payload = parse_packet(data)
                except Exception as e: self.send_error(client_socket, client_address, f"Packet parsing error: {str(e)}"); continue
                if cmd == b'\x01' and client_address in self.client_info and not self.check_client_heartbeat(client_address):
                    self.log.warning(f"Redundant handshake from {client_address}; ignoring.")
                    continue
                if client_address not in self.client_info or self.check_client_heartbeat(client_address):
                    if cmd == b'\x01':
                        self.handle_client_handshake(client_socket, client_address, shared_secret, payload)
                        continue
                    else:
                        self.send_error(client_socket, client_address, "Client must handshake first")
                        continue
                key = self.client_info[client_address].get('key')
                try: decrypted_data = decrypt_message(key, payload)
                except Exception as e: self.send_error(client_socket, client_address, f"Decryption failed: {str(e)}"); continue

                if cmd in self.DIR_COMMAND_MAP: self.handle_directory_lookup(client_socket, client_address, cmd, decrypted_data)
                elif cmd == CMD_LIST_BLOBS: self.handle_list_blobs_request(client_socket, client_address, decrypted_data)
                elif cmd == CMD_SWAP_BLOB: self.handle_swap_blob_request(client_socket, client_address, decrypted_data)
                elif cmd == CMD_FIND_CONTENT_SERVERS_BY_APPID: self.handle_find_content_servers_by_appid(client_socket, client_address, decrypted_data)
                elif cmd == CMD_INTERACTIVE_CONTENT_SERVER_FINDER: self.handle_interactive_content_server_finder(client_socket, client_address, decrypted_data)
                elif cmd == CMD_BLOBMGR_LIST_BLOBS: self.handle_blobmgr_list_request(client_socket, client_address, decrypted_data)
                elif cmd == CMD_BLOBMGR_SWAP_BLOB: self.handle_blobmgr_swap_request(client_socket, client_address, decrypted_data)
                elif cmd == CMD_GET_FULL_DIRSERVER_LIST: self.handle_get_full_dirserver_list(client_socket, client_address, decrypted_data)
                elif cmd == CMD_ADD_DIRSERVER_ENTRY: self.handle_add_dirserver_entry(client_socket, client_address, decrypted_data)
                elif cmd == CMD_DEL_DIRSERVER_ENTRY: self.handle_del_dirserver_entry(client_socket, client_address, decrypted_data)
                elif cmd == CMD_GET_FULL_CONTENTSERVER_LIST: self.handle_get_full_contentserver_list(client_socket, client_address, decrypted_data)
                elif cmd == CMD_ADD_CONTENTSERVER_ENTRY: self.handle_add_contentserver_entry(client_socket, client_address, decrypted_data)
                elif cmd == CMD_DEL_CONTENTSERVER_ENTRY: self.handle_del_contentserver_entry(client_socket, client_address, decrypted_data)
                elif cmd == CMD_GET_IP_WHITELIST: self.handle_get_ip_list(client_socket, client_address, cmd, decrypted_data)
                elif cmd == CMD_GET_IP_BLACKLIST: self.handle_get_ip_list(client_socket, client_address, cmd, decrypted_data)
                elif cmd == CMD_ADD_TO_IP_WHITELIST: self.handle_add_to_ip_list(client_socket, client_address, cmd, decrypted_data)
                elif cmd == CMD_ADD_TO_IP_BLACKLIST: self.handle_add_to_ip_list(client_socket, client_address, cmd, decrypted_data)
                elif cmd == CMD_DEL_FROM_IP_WHITELIST: self.handle_del_from_ip_list(client_socket, client_address, cmd, decrypted_data)
                elif cmd == CMD_DEL_FROM_IP_BLACKLIST: self.handle_del_from_ip_list(client_socket, client_address, cmd, decrypted_data)
                elif cmd == CMD_RESTART_SERVER_THREAD: self.handle_restart_server_thread(client_socket, client_address, decrypted_data, reload_code=True)
                elif cmd == CMD_RESTART_SERVER_NO_RELOAD: self.handle_restart_server_thread(client_socket, client_address, decrypted_data, reload_code=False)
                elif cmd == CMD_GET_RESTARTABLE_SERVERS: self.handle_get_restartable_servers(client_socket, client_address, decrypted_data)
                elif cmd == CMD_EDIT_ADMIN_RIGHTS: self.handle_edit_admin_rights(client_socket, client_address, decrypted_data)
                elif cmd == CMD_REMOVE_ADMIN: self.handle_remove_admin(client_socket, client_address, decrypted_data)
                elif cmd == CMD_LIST_ADMINS: self.handle_list_admins(client_socket, client_address, decrypted_data)
                elif cmd == CMD_CREATE_ADMIN: self.handle_create_admin(client_socket, client_address, decrypted_data)
                elif cmd == CMD_CHANGE_ADMIN_USERNAME: self.handle_change_admin_username(client_socket, client_address, decrypted_data)
                elif cmd == CMD_CHANGE_ADMIN_EMAIL: self.handle_change_admin_email(client_socket, client_address, decrypted_data)
                elif cmd == CMD_CHANGE_ADMIN_PASSWORD: self.handle_change_admin_password(client_socket, client_address, decrypted_data)
                elif cmd == CMD_GET_DETAILED_BLOB_LIST: self.handle_get_detailed_blob_list(client_socket, client_address, decrypted_data)
                elif cmd == CMD_CONTENT_PURGE: self.handle_content_purge(client_socket, client_address, decrypted_data)
                elif cmd == CMD_GET_SERVER_STATS: self.handle_get_server_statistics(client_socket, client_address, decrypted_data)
                elif cmd == CMD_GET_LIVE_LOG: self.handle_get_live_log(client_socket, client_address, decrypted_data)
                elif cmd == CMD_GET_AUTH_STATS: self.handle_get_auth_stats(client_socket, client_address, decrypted_data)
                elif cmd == CMD_SET_RATE_LIMIT: self.handle_set_rate_limit(client_socket, client_address, decrypted_data)
                elif cmd == CMD_GET_BW_STATS: self.handle_get_bw_stats(client_socket, client_address, decrypted_data)
                elif cmd == CMD_GET_CONN_COUNT: self.handle_get_connection_count(client_socket, client_address, decrypted_data)
                elif cmd == CMD_EDIT_CONFIG: self.handle_edit_config(client_socket, client_address, decrypted_data)
                elif cmd == CMD_TOGGLE_FEATURE: self.handle_toggle_feature(client_socket, client_address, decrypted_data)
                elif cmd == CMD_GET_SESSION_REPORT: self.handle_get_session_report(client_socket, client_address, decrypted_data)
                elif cmd == CMD_SET_FTP_QUOTA: self.handle_set_ftp_quota(client_socket, client_address, decrypted_data)
                elif cmd == CMD_HOT_RELOAD_CONFIG: self.handle_hot_reload_config(client_socket, client_address, decrypted_data)
                elif cmd == CMD_CHATROOM_OP: self.execute_chatroom_command(client_socket, client_address, decrypted_data)
                elif cmd == CMD_CLAN_OP: self.execute_clan_command(client_socket, client_address, decrypted_data)
                elif cmd == CMD_GIFT_OP: self.execute_gift_command(client_socket, client_address, decrypted_data)
                elif cmd == CMD_NEWS_OP: self.execute_news_command(client_socket, client_address, decrypted_data)
                elif cmd == CMD_LICENSE_OP: self.execute_license_command(client_socket, client_address, decrypted_data)
                elif cmd == CMD_TOKEN_OP: self.execute_token_command(client_socket, client_address, decrypted_data)
                elif cmd == CMD_INVENTORY_OP: self.execute_inventory_command(client_socket, client_address, decrypted_data)
                elif cmd == b'\x02': self.handle_client_login(client_socket, client_address, decrypted_data)
                elif cmd == CMD_LOGOFF: self.handle_client_logout(client_socket, client_address)
                elif cmd == CMD_HEARTBEAT: self.handle_heartbeat(client_socket, client_address)
                elif cmd == b'\xFF': self.handle_streaming_request(client_socket, client_address)
                elif cmd in (b'\x0A', b'\x0B', b'\x0C', b'\x0D'): self.execute_usermanagement_command(client_socket, client_address, cmd, decrypted_data)
                elif cmd in (b'\x16', b'\x17', b'\x20', b'\x21', b'\x22', b'\x23', b'\x24', b'\x25'):
                    self.execute_subscription_command(client_socket, client_address, cmd, decrypted_data)
                elif cmd in (b'\x0E', b'\x1E', b'\x11', b'\x13'): self.execute_admin_command(client_socket, client_address, cmd, decrypted_data)
                elif cmd in (b'\x40', b'\x41', b'\x42', b'\x46', b'\x47', b'\x48', b'\x49', b'\x4A'): self.execute_ftp_review_command(client_socket, client_address, cmd, decrypted_data)
                elif cmd in (CMD_LIST_FTP_USERS, CMD_ADD_FTP_USER, CMD_REMOVE_FTP_USER):
                    self.execute_ftp_user_command(client_socket, client_address, cmd, decrypted_data)
                else: self.send_error(client_socket, client_address, "Unknown command")
            except Exception as ex: self.log.error(f"Error handling client {client_address}: {ex}"); break
    
    def handle_get_restartable_servers(self, sock, client_address, decrypted_data):
        self.log.info(f"Received get restartable servers list request (CMD {CMD_GET_RESTARTABLE_SERVERS.hex()}) from {client_address}")
        info = self.client_info.get(client_address, {})
        if not info.get('authenticated'):
            self.send_error(sock, client_address, "Authentication required."); return
        if not (info.get('user_rights', 0) & SERVER_LIST_EDIT):
            self.send_error(sock, client_address, "Permission denied."); return

        try:
            # Get the actual list of registered servers from thread_handler dynamically
            server_list = self.get_restartable_servers()

            # Include additional info about each server (status, port, class)
            server_info = []
            for identifier in server_list:
                info_data = thread_handler.get_server_info(identifier)
                if info_data:
                    server_info.append({
                        "identifier": identifier,
                        "class": info_data.get('class', 'Unknown'),
                        "port": info_data.get('port'),
                        "is_alive": info_data.get('is_alive', False),
                        "module": info_data.get('module', 'Unknown')
                    })
                else:
                    server_info.append({"identifier": identifier, "is_alive": False})

            json_payload = json.dumps(server_info)
            json_bytes = json_payload.encode('utf-8')

            key = self.client_info[client_address]['key']
            encrypted_response = encrypt_message(key, json_bytes)

            self._send_packet(sock, build_packet(CMD_GET_RESTARTABLE_SERVERS, encrypted_response))
            self.log.info(f"Sent encrypted restartable server list ({len(server_list)} servers) to {client_address}")

        except Exception as e:
            self.log.error(f"Error handling get restartable servers list request for {client_address}: {e}")
            self.send_error(sock, client_address, f"Failed to retrieve restartable servers list: {str(e)}")

    def handle_restart_server_thread(self, sock, client_address, decrypted_data, reload_code=True):
        """
        Handle a server restart request from the remote admin client.

        Args:
            sock: Client socket
            client_address: Client address tuple
            decrypted_data: Decrypted JSON payload containing server_identifier
            reload_code: If True, reload the Python module from disk (hot-reload for code changes).
                        If False, just restart the server with existing code.
        """
        action = "hot-reload" if reload_code else "restart"
        cmd_hex = CMD_RESTART_SERVER_THREAD.hex() if reload_code else CMD_RESTART_SERVER_NO_RELOAD.hex()
        self.log.info(f"Received {action} server thread request (CMD {cmd_hex}) from {client_address}")

        info = self.client_info.get(client_address, {})
        if not info.get('authenticated'):
            self.send_error(sock, client_address, "Authentication required."); return
        if not (info.get('user_rights', 0) & SERVER_LIST_EDIT):
            self.send_error(sock, client_address, "Permission denied."); return

        server_identifier = None
        try:
            json_string = decrypted_data.decode('utf-8')
            entry_data = json.loads(json_string)
            server_identifier = entry_data.get("server_identifier")

            if not server_identifier or not isinstance(server_identifier, str):
                self.send_error(sock, client_address, "Missing or invalid 'server_identifier' in JSON payload."); return

            # Validate against the actual server registry (case-insensitive match)
            registered_servers = self.get_restartable_servers()
            matched_identifier = None
            for reg_id in registered_servers:
                if reg_id.lower() == server_identifier.lower():
                    matched_identifier = reg_id
                    break

            if not matched_identifier:
                self.log.warning(f"Client {client_address} requested {action} for unregistered server: {server_identifier}")
                available = ', '.join(sorted(registered_servers))
                self.send_error(sock, client_address, f"Server '{server_identifier}' not found. Available: {available}")
                return

            self.log.info(f"Attempting to {action} server thread: {matched_identifier} (reload_code={reload_code}) as requested by {client_address}")

            # Special handling for CMSERVER - reload all steam3 modules
            if matched_identifier == 'CMSERVER':
                success, message, count = thread_handler.reload_steam3_modules()
                if success:
                    response_message = f"CMSERVER {action} complete: {message}"
                    self.log.info(response_message)
                else:
                    response_message = f"CMSERVER {action} failed: {message}"
                    self.log.error(response_message)
            else:
                # Use the thread_handler.restart_server with the reload_code flag for other servers
                success = thread_handler.restart_server(matched_identifier, reload_code=reload_code)

                if success:
                    if reload_code:
                        response_message = f"Hot-reload complete for server '{matched_identifier}'. Code changes applied."
                    else:
                        response_message = f"Restart complete for server '{matched_identifier}'."
                    self.log.info(response_message)
                else:
                    response_message = f"Failed to {action} server '{matched_identifier}'. Check server logs."
                    self.log.error(response_message)

            key = self.client_info[client_address]['key']
            encrypted_response = encrypt_message(key, response_message.encode('latin-1'))
            response_cmd = CMD_RESTART_SERVER_THREAD if reload_code else CMD_RESTART_SERVER_NO_RELOAD
            self._send_packet(sock, build_packet(response_cmd, encrypted_response))

        except json.JSONDecodeError:
            self.log.error(f"Invalid JSON for {action} server thread: {decrypted_data.decode('utf-8', errors='ignore')}")
            self.send_error(sock, client_address, "Invalid JSON format in request.")
        except Exception as e:
            self.log.error(f"Error handling {action} server thread for {client_address} server {server_identifier or 'UNKNOWN'}: {e}")
            self.send_error(sock, client_address, f"Failed to {action} server: {str(e)}")

    def handle_edit_admin_rights(self, sock, client_address, decrypted_data):
        self.log.info(f"Received edit admin rights request (CMD {CMD_EDIT_ADMIN_RIGHTS.hex()}) from {client_address}")
        info = self.client_info.get(client_address, {})
        if not info.get('authenticated'):
            self.send_error(sock, client_address, "Authentication required."); return
        if not (info.get('user_rights', 0) & EDIT_ADMINS):
            self.send_error(sock, client_address, "Permission denied."); return
        try:
            parts = decrypted_data.decode('latin-1').split('|', 1)
            if len(parts) != 2:
                self.send_error(sock, client_address, "Invalid payload for edit rights."); return
            username, rights = parts[0].strip(), int(parts[1].strip())
            if self.database.update_admin_rights(username, rights):
                self.send_success(sock, client_address, CMD_EDIT_ADMIN_RIGHTS, f"Rights updated for {username}")
            else:
                self.send_error(sock, client_address, "Failed to update admin rights")
        except Exception as e:
            self.log.error(f"Error editing admin rights for {client_address}: {e}")
            self.send_error(sock, client_address, "Exception updating admin rights")

    def handle_remove_admin(self, sock, client_address, decrypted_data):
        self.log.info(f"Received remove admin request (CMD {CMD_REMOVE_ADMIN.hex()}) from {client_address}")
        info = self.client_info.get(client_address, {})
        if not info.get('authenticated'):
            self.send_error(sock, client_address, "Authentication required."); return
        if not (info.get('user_rights', 0) & EDIT_ADMINS):
            self.send_error(sock, client_address, "Permission denied."); return
        try:
            username = decrypted_data.decode('latin-1').strip()
            if not username:
                self.send_error(sock, client_address, "Missing username"); return
            if self.database.remove_administrator(username):
                self.send_success(sock, client_address, CMD_REMOVE_ADMIN, f"Administrator {username} removed")
            else:
                self.send_error(sock, client_address, "Failed to remove administrator")
        except Exception as e:
            self.log.error(f"Error removing admin for {client_address}: {e}")
            self.send_error(sock, client_address, "Exception removing administrator")

    def handle_list_admins(self, sock, client_address, decrypted_data):
        self.log.info(f"Received list admins request (CMD {CMD_LIST_ADMINS.hex()}) from {client_address}")
        info = self.client_info.get(client_address, {})
        if not info.get('authenticated'):
            self.send_error(sock, client_address, "Authentication required."); return
        if not (info.get('user_rights', 0) & EDIT_ADMINS):
            self.send_error(sock, client_address, "Permission denied."); return
        try:
            admin_list = self.database.list_administrators()
            json_payload = json.dumps(admin_list)
            key = self.client_info[client_address]['key']
            encrypted_response = encrypt_message(key, json_payload.encode('utf-8'))
            self._send_packet(sock, build_packet(CMD_LIST_ADMINS, encrypted_response))
        except Exception as e:
            self.log.error(f"Error listing admins for {client_address}: {e}")
            self.send_error(sock, client_address, "Failed to list administrators")

    def handle_create_admin(self, sock, client_address, decrypted_data):
        self.log.info(f"Received create admin request (CMD {CMD_CREATE_ADMIN.hex()}) from {client_address}")
        info = self.client_info.get(client_address, {})
        if not info.get('authenticated'):
            self.send_error(sock, client_address, "Authentication required."); return
        if not (info.get('user_rights', 0) & EDIT_ADMINS):
            self.send_error(sock, client_address, "Permission denied."); return
        try:
            parts = decrypted_data.decode('latin-1').split('|')
            if len(parts) != 3:
                self.send_error(sock, client_address, "Invalid payload for create admin."); return
            username, password, rights = parts[0].strip(), parts[1].strip(), int(parts[2].strip())
            if self.database.create_administrator(username, password, rights):
                self.send_success(sock, client_address, CMD_CREATE_ADMIN, f"Administrator {username} created")
            else:
                self.send_error(sock, client_address, "Failed to create administrator")
        except Exception as e:
            self.log.error(f"Error creating admin for {client_address}: {e}")
            self.send_error(sock, client_address, "Exception creating administrator")

    def handle_change_admin_username(self, sock, client_address, decrypted_data):
        self.log.info(f"Received change admin username request (CMD {CMD_CHANGE_ADMIN_USERNAME.hex()}) from {client_address}")
        info = self.client_info.get(client_address, {})
        if not info.get('authenticated'):
            self.send_error(sock, client_address, "Authentication required."); return
        if not (info.get('user_rights', 0) & EDIT_ADMINS):
            self.send_error(sock, client_address, "Permission denied."); return
        try:
            parts = decrypted_data.decode('latin-1').split('|')
            if len(parts) != 2:
                self.send_error(sock, client_address, "Invalid payload for change username."); return
            old_name, new_name = parts[0].strip(), parts[1].strip()
            if self.database.change_admin_username(old_name, new_name):
                self.send_success(sock, client_address, CMD_CHANGE_ADMIN_USERNAME, f"Username changed: {old_name} -> {new_name}")
            else:
                self.send_error(sock, client_address, "Failed to change username")
        except Exception as e:
            self.log.error(f"Error changing admin username for {client_address}: {e}")
            self.send_error(sock, client_address, "Exception changing username")

    def handle_change_admin_email(self, sock, client_address, decrypted_data):
        self.log.info(f"Received change admin email request (CMD {CMD_CHANGE_ADMIN_EMAIL.hex()}) from {client_address}")
        info = self.client_info.get(client_address, {})
        if not info.get('authenticated'):
            self.send_error(sock, client_address, "Authentication required."); return
        if not (info.get('user_rights', 0) & EDIT_ADMINS):
            self.send_error(sock, client_address, "Permission denied."); return
        try:
            parts = decrypted_data.decode('latin-1').split('|')
            if len(parts) != 2:
                self.send_error(sock, client_address, "Invalid payload for change email."); return
            username, new_email = parts[0].strip(), parts[1].strip()
            if self.database.change_admin_email(username, new_email):
                self.send_success(sock, client_address, CMD_CHANGE_ADMIN_EMAIL, f"Email changed for {username}")
            else:
                self.send_error(sock, client_address, "Failed to change email")
        except Exception as e:
            self.log.error(f"Error changing admin email for {client_address}: {e}")
            self.send_error(sock, client_address, "Exception changing email")

    def handle_change_admin_password(self, sock, client_address, decrypted_data):
        self.log.info(f"Received change admin password request (CMD {CMD_CHANGE_ADMIN_PASSWORD.hex()}) from {client_address}")
        info = self.client_info.get(client_address, {})
        if not info.get('authenticated'):
            self.send_error(sock, client_address, "Authentication required."); return
        if not (info.get('user_rights', 0) & EDIT_ADMINS):
            self.send_error(sock, client_address, "Permission denied."); return
        try:
            parts = decrypted_data.decode('latin-1').split('|')
            if len(parts) != 2:
                self.send_error(sock, client_address, "Invalid payload for change password."); return
            username, new_pw = parts[0].strip(), parts[1].strip()
            if self.database.change_admin_password(username, new_pw):
                self.send_success(sock, client_address, CMD_CHANGE_ADMIN_PASSWORD, f"Password changed for {username}")
            else:
                self.send_error(sock, client_address, "Failed to change password")
        except Exception as e:
            self.log.error(f"Error changing admin password for {client_address}: {e}")
            self.send_error(sock, client_address, "Exception changing password")

    def handle_content_purge(self, sock, client_address, decrypted_data):
        self.log.info(f"Received content purge request (CMD {CMD_CONTENT_PURGE.hex()}) from {client_address}")
        info = self.client_info.get(client_address, {})
        if not info.get('authenticated'):
            self.send_error(sock, client_address, "Authentication required."); return
        if not (info.get('user_rights', 0) & SERVER_LIST_EDIT):
            self.send_error(sock, client_address, "Permission denied."); return
        try:
            payload = json.loads(decrypted_data.decode('utf-8'))
            appid = int(payload.get('appid', 0))
            version = int(payload.get('version', 0))
            purge_dir = os.path.join(self.config.get('contentdir', 'content'), str(appid), str(version))
            if os.path.isdir(purge_dir):
                shutil.rmtree(purge_dir)
                msg = "Purged" 
            else:
                msg = "Not found"
            key = self.client_info[client_address]['key']
            encrypted = encrypt_message(key, msg.encode('latin-1'))
            self._send_packet(sock, build_packet(CMD_CONTENT_PURGE, encrypted))
        except Exception as e:
            self.log.error(f"Error purging content for {client_address}: {e}")
            self.send_error(sock, client_address, "Failed to purge content")

    def handle_get_server_statistics(self, sock, client_address, decrypted_data):
        self.log.info(f"Received statistics request (CMD {CMD_GET_SERVER_STATS.hex()}) from {client_address}")
        info = self.client_info.get(client_address, {})
        if not info.get('authenticated'):
            self.send_error(sock, client_address, "Authentication required."); return
        if not (info.get('user_rights', 0) & SERVER_LIST_EDIT):
            self.send_error(sock, client_address, "Permission denied."); return
        try:
            stats = self.database.get_server_statistics()
            json_payload = json.dumps(stats).encode('utf-8')
            key = self.client_info[client_address]['key']
            encrypted_response = encrypt_message(key, json_payload)
            self._send_packet(sock, build_packet(CMD_GET_SERVER_STATS, encrypted_response))
        except Exception as e:
            self.log.error(f"Error retrieving statistics for {client_address}: {e}")
            self.send_error(sock, client_address, "Failed to get statistics")

    def handle_del_from_ip_list(self, sock, client_address, command_code, decrypted_data):
        self.log.info(f"Received delete from IP list request (CMD {command_code.hex()}) from {client_address}")
        info = self.client_info.get(client_address, {})
        if not info.get('authenticated'):
            self.send_error(sock, client_address, "Auth required."); return
        if not (info.get('user_rights', 0) & SERVER_LIST_EDIT):
            self.send_error(sock, client_address, "Permission denied."); return
        try:
            json_string = decrypted_data.decode('utf-8'); entry_data = json.loads(json_string)
            ip_to_remove = entry_data.get("ip_address")
            if not ip_to_remove or not isinstance(ip_to_remove, str): self.send_error(sock, client_address, "Missing or invalid 'ip_address'."); return
            if not ImpSocket.is_valid_ipv4(ip_to_remove): self.send_error(sock, client_address, f"Invalid IP format: {ip_to_remove}"); return
            success = False; list_type_str = ""; response_message_str = ""
            if command_code == CMD_DEL_FROM_IP_WHITELIST:
                list_type_str = "whitelist"; success = ImpSocket.remove_from_whitelist(ip_to_remove)
                if success: response_message_str = f"IP {ip_to_remove} removed from whitelist."
                else: response_message_str = f"IP {ip_to_remove} not found in whitelist or file error."
            elif command_code == CMD_DEL_FROM_IP_BLACKLIST:
                list_type_str = "blacklist"; success = ImpSocket.remove_from_blacklist(ip_to_remove)
                if success: response_message_str = f"IP {ip_to_remove} removed from blacklist."
                else: response_message_str = f"IP {ip_to_remove} not found in blacklist or file error."
            else: self.send_error(sock, client_address, "Internal error: Invalid command for del from IP list."); return
            if success: self.log.info(f"Removed {ip_to_remove} from {list_type_str} for {client_address}.")
            else: self.log.warning(f"Failed to remove {ip_to_remove} from {list_type_str}. Reason: {response_message_str}")
            response_message_bytes = response_message_str.encode('latin-1')
            key = self.client_info[client_address]['key']; encrypted_response = encrypt_message(key, response_message_bytes)
            self._send_packet(sock, build_packet(command_code, encrypted_response))
        except json.JSONDecodeError: self.log.error(f"Invalid JSON for del from IP list: {decrypted_data.decode('utf-8', errors='ignore')}"); self.send_error(sock, client_address, "Invalid JSON format.")
        except Exception as e: self.log.error(f"Error handling del from IP list for {client_address}: {e}"); self.send_error(sock, client_address, f"Failed to process del from IP list: {str(e)}")
        
    def handle_add_to_ip_list(self, sock, client_address, command_code, decrypted_data):
        self.log.info(f"Received add to IP list request (CMD {command_code.hex()}) from {client_address}")
        if not self.client_info.get(client_address, {}).get('authenticated'):
            self.send_error(sock, client_address, "Authentication required."); return
        try:
            json_string = decrypted_data.decode('utf-8'); entry_data = json.loads(json_string)
            ip_to_add = entry_data.get("ip_address")
            if not ip_to_add or not isinstance(ip_to_add, str): self.send_error(sock, client_address, "Missing or invalid 'ip_address'."); return
            if not ImpSocket.is_valid_ipv4(ip_to_add): self.send_error(sock, client_address, f"Invalid IP format: {ip_to_add}"); return
            success = False; list_type_str = ""; response_message_str = ""
            if command_code == CMD_ADD_TO_IP_WHITELIST:
                list_type_str = "whitelist"; success = ImpSocket.add_to_whitelist(ip_to_add)
                if success: response_message_str = f"IP {ip_to_add} added to whitelist."
                else: response_message_str = f"Failed to add {ip_to_add} to whitelist (already exists, LAN IP, or file error)."
            elif command_code == CMD_ADD_TO_IP_BLACKLIST:
                list_type_str = "blacklist"; success = ImpSocket.add_to_blacklist(ip_to_add)
                if success: response_message_str = f"IP {ip_to_add} added to blacklist."
                else: response_message_str = f"Failed to add {ip_to_add} to blacklist (already exists, LAN IP, or file error)."
            else: self.send_error(sock, client_address, "Internal error: Invalid command for add to IP list."); return
            if success: self.log.info(f"Added {ip_to_add} to {list_type_str} for {client_address}.")
            else: self.log.warning(f"Failed to add {ip_to_add} to {list_type_str}. Reason: {response_message_str}")
            response_message_bytes = response_message_str.encode('latin-1')
            key = self.client_info[client_address]['key']; encrypted_response = encrypt_message(key, response_message_bytes)
            self._send_packet(sock, build_packet(command_code, encrypted_response))
        except json.JSONDecodeError: self.log.error(f"Invalid JSON for add to IP list: {decrypted_data.decode('utf-8', errors='ignore')}"); self.send_error(sock, client_address, "Invalid JSON format.")
        except Exception as e: self.log.error(f"Error handling add to IP list for {client_address}: {e}"); self.send_error(sock, client_address, f"Failed to process add to IP list: {str(e)}")

    def handle_get_ip_list(self, sock, client_address, command_code, decrypted_data):
        self.log.info(f"Received get IP list request (CMD {command_code.hex()}) from {client_address}")
        if not self.client_info.get(client_address, {}).get('authenticated'):
            self.send_error(sock, client_address, "Authentication required."); return
        try:
            ip_list = []; list_type_str = ""
            if command_code == CMD_GET_IP_WHITELIST: ip_list = ImpSocket.get_whitelist(); list_type_str = "whitelist"
            elif command_code == CMD_GET_IP_BLACKLIST: ip_list = ImpSocket.get_blacklist(); list_type_str = "blacklist"
            else: self.send_error(sock, client_address, "Internal error: Invalid command for IP list."); return
            self.log.info(f"Retrieved {list_type_str} for {client_address}: {len(ip_list)} IPs")
            json_payload = json.dumps(ip_list, indent=2); json_bytes = json_payload.encode('utf-8')
            key = self.client_info[client_address]['key']; encrypted_response = encrypt_message(key, json_bytes)
            self._send_packet(sock, build_packet(command_code, encrypted_response))
            self.log.info(f"Sent encrypted IP {list_type_str} to {client_address}")
        except Exception as e: self.log.error(f"Error handling get IP list for {client_address}: {e}"); self.send_error(sock, client_address, f"Failed to get IP list: {str(e)}")

    def handle_del_contentserver_entry(self, sock, client_address, decrypted_data):
        self.log.info(f"Received delete ContentServer entry request (CMD {CMD_DEL_CONTENTSERVER_ENTRY.hex()}) from {client_address}")
        if not self.client_info.get(client_address, {}).get('authenticated'):
            self.send_error(sock, client_address, "Authentication required."); return
        try:
            json_string = decrypted_data.decode('utf-8'); entry_data = json.loads(json_string)
            server_id_hex = entry_data.get("server_id")
            if not server_id_hex or not isinstance(server_id_hex, str):
                self.send_error(sock, client_address, "Missing or invalid 'server_id' (hex string) in JSON payload."); return
            try:
                server_id_bytes = bytes.fromhex(server_id_hex)
                if len(server_id_bytes) != 16: raise ValueError("Server ID hex string does not represent 16 bytes.")
            except ValueError as ve_hex:
                self.log.error(f"Invalid server_id hex from {client_address}: {server_id_hex} - {ve_hex}")
                self.send_error(sock, client_address, f"Invalid server_id format: {ve_hex}"); return
            removed = contentlistmanager.manager.remove_entry_by_id(server_id_bytes)
            response_message = b"Content server entry removed." if removed else b"Content server entry not found."
            self.log.info(f"{'Removed' if removed else 'Not found'} ContentServer ID: {server_id_hex}")
            key = self.client_info[client_address]['key']; encrypted_response = encrypt_message(key, response_message)
            self._send_packet(sock, build_packet(CMD_DEL_CONTENTSERVER_ENTRY, encrypted_response))
        except json.JSONDecodeError: self.log.error(f"Invalid JSON for del ContentServer: {decrypted_data.decode('utf-8', errors='ignore')}"); self.send_error(sock, client_address, "Invalid JSON format.")
        except Exception as e: self.log.error(f"Error handling del ContentServer for {client_address}: {e}"); self.send_error(sock, client_address, f"Failed to delete ContentServer: {str(e)}")

    def handle_add_contentserver_entry(self, sock, client_address, decrypted_data):
        self.log.info(f"Received add ContentServer entry request (CMD {CMD_ADD_CONTENTSERVER_ENTRY.hex()}) from {client_address}")
        if not self.client_info.get(client_address, {}).get('authenticated'):
            self.send_error(sock, client_address, "Authentication required."); return
        try:
            json_string = decrypted_data.decode('utf-8')
            entry_data = json.loads(json_string)
            required_fields = ["wan_ip", "lan_ip", "port", "region", "received_applist", "cellid", "is_permanent", "is_pkgcs"]
            for field in required_fields:
                if field not in entry_data: self.send_error(sock, client_address, f"Missing field: {field}"); return
            server_id_hex = entry_data.get("server_id"); server_id_bytes = None
            if server_id_hex:
                try: server_id_bytes = bytes.fromhex(server_id_hex)
                except ValueError as ve_hex: self.send_error(sock, client_address, f"Invalid server_id format: {ve_hex}"); return
                if len(server_id_bytes) != 16: self.send_error(sock, client_address, "Server ID must be 16-byte UUID hex."); return
            wan_ip = entry_data["wan_ip"]; lan_ip = entry_data["lan_ip"]; port = int(entry_data["port"]); region = entry_data["region"]
            received_applist = entry_data["received_applist"]; cellid = int(entry_data["cellid"])
            is_permanent = int(entry_data["is_permanent"]); is_pkgcs = bool(entry_data["is_pkgcs"])
            if not (isinstance(wan_ip, str) and isinstance(lan_ip, str) and isinstance(port, int) and isinstance(region, str) and isinstance(received_applist, list) and isinstance(cellid, int) and isinstance(is_permanent, int) and is_permanent in [0, 1] and isinstance(is_pkgcs, bool) and (server_id_bytes is None or isinstance(server_id_bytes, bytes)) ): 
                self.send_error(sock, client_address, "Invalid data types."); return
            if not (0 <= port <= 65535): self.send_error(sock, client_address, "Invalid port number."); return
            success = contentlistmanager.manager.add_contentserver_info(
                server_id=server_id_bytes,
                wan_ip=wan_ip,
                lan_ip=lan_ip,
                port=port,
                region=region,
                received_applist=received_applist,
                cellid=cellid,
                is_permanent=is_permanent,
                is_pkgcs=is_pkgcs,
            )
            response_message = b"Content server entry added/updated." if success else b"Failed to add/update content server."
            self.log.info(f"{'Added/updated' if success else 'Failed'} ContentServer entry for WAN {wan_ip}:{port}")
            key = self.client_info[client_address]['key']; encrypted_response = encrypt_message(key, response_message)
            self._send_packet(sock, build_packet(CMD_ADD_CONTENTSERVER_ENTRY, encrypted_response))
        except json.JSONDecodeError: self.log.error(f"Invalid JSON for add ContentServer: {decrypted_data.decode('utf-8', errors='ignore')}"); self.send_error(sock, client_address, "Invalid JSON format.")
        except (ValueError, TypeError) as ve: self.log.error(f"Type/Value error for add ContentServer: {ve}"); self.send_error(sock, client_address, f"Invalid data: {ve}")
        except Exception as e: self.log.error(f"Error handling add ContentServer for {client_address}: {e}"); self.send_error(sock, client_address, f"Failed to add ContentServer: {str(e)}")

    def handle_get_full_contentserver_list(self, sock, client_address, decrypted_data):
        self.log.info(f"Received get full ContentServer list request (CMD {CMD_GET_FULL_CONTENTSERVER_LIST.hex()}) from {client_address}")
        info = self.client_info.get(client_address, {})
        if not info.get('authenticated'):
            self.send_error(sock, client_address, "Auth required."); return
        if not (info.get('user_rights', 0) & SERVER_LIST_EDIT):
            self.send_error(sock, client_address, "Permission denied."); return
        try:
            full_list = contentlistmanager.manager.contentserver_list
            serializable_list = []
            for entry in full_list:
                server_id_hex = entry[9].hex() if isinstance(entry[9], bytes) else str(entry[9])
                wan_ip = entry[0].decode('latin-1') if isinstance(entry[0], bytes) else str(entry[0])
                lan_ip = entry[1].decode('latin-1') if isinstance(entry[1], bytes) else str(entry[1])
                region_str = entry[3].decode('latin-1', 'replace') if isinstance(entry[3], bytes) else str(entry[3])
                timestamp_val = entry[4]
                if isinstance(timestamp_val, datetime):
                    timestamp_str = timestamp_val.isoformat()
                elif isinstance(timestamp_val, (int, float)):
                    try:
                        timestamp_str = datetime.fromtimestamp(timestamp_val).isoformat()
                    except Exception:
                        timestamp_str = str(timestamp_val)
                else:
                    timestamp_str = str(timestamp_val)
                applist_norm = []
                for app in entry[5]:
                    if isinstance(app, (list, tuple)) and len(app) == 2:
                        a, v = app
                        if isinstance(a, bytes):
                            a = a.decode('latin-1')
                        if isinstance(v, bytes):
                            v = v.decode('latin-1')
                        applist_norm.append([a, v])
                    else:
                        applist_norm.append(app)
                serializable_list.append({
                    "server_id": server_id_hex,
                    "wan_ip": wan_ip,
                    "lan_ip": lan_ip,
                    "port": int(entry[2]),
                    "region": region_str,
                    "timestamp": timestamp_str,
                    "applist": applist_norm,
                    "is_permanent": int(entry[6]),
                    "is_pkgcs": bool(entry[7]),
                    "cellid": int(entry[8]),
                })
            json_payload = json.dumps(serializable_list, indent=2); json_bytes = json_payload.encode('utf-8')
            self.log.debug(f"Prepared full ContentServer JSON payload, length: {len(json_bytes)}")
            key = self.client_info[client_address]['key']; encrypted_response = encrypt_message(key, json_bytes)
            self._send_packet(sock, build_packet(CMD_GET_FULL_CONTENTSERVER_LIST, encrypted_response))
            self.log.info(f"Sent encrypted full ContentServer list to {client_address}")
        except Exception as e: self.log.error(f"Error getting full ContentServer list for {client_address}: {e}"); self.send_error(sock, client_address, f"Failed to get ContentServer list: {str(e)}")

    def handle_del_dirserver_entry(self, sock, client_address, decrypted_data):
        self.log.info(f"Received delete DirServer entry request (CMD {CMD_DEL_DIRSERVER_ENTRY.hex()}) from {client_address}")
        info = self.client_info.get(client_address, {})
        if not info.get('authenticated'):
            self.send_error(sock, client_address, "Auth required."); return
        if not (info.get('user_rights', 0) & SERVER_LIST_EDIT):
            self.send_error(sock, client_address, "Permission denied."); return
        try:
            json_string = decrypted_data.decode('utf-8'); entry_data = json.loads(json_string)
            required_fields = ["wan_ip", "lan_ip", "port", "server_type"]
            for field in required_fields:
                if field not in entry_data: self.send_error(sock, client_address, f"Missing field: {field}"); return
            wan_ip = entry_data["wan_ip"]; lan_ip = entry_data["lan_ip"]; port = int(entry_data["port"]); server_type = entry_data["server_type"]
            if not (isinstance(wan_ip, str) and isinstance(lan_ip, str) and isinstance(port, int) and isinstance(server_type, str)):
                self.send_error(sock, client_address, "Invalid data types."); return
            removed = dirlistmanager.manager.remove_entry(wan_ip, lan_ip, port, server_type)
            response_message = b"Directory server entry removed." if removed else b"DirServer entry not found."
            self.log.info(f"{'Removed' if removed else 'Not found'} DirServer entry: {server_type} at {wan_ip}:{port}")
            key = self.client_info[client_address]['key']; encrypted_response = encrypt_message(key, response_message)
            self._send_packet(sock, build_packet(CMD_DEL_DIRSERVER_ENTRY, encrypted_response))
        except json.JSONDecodeError: self.log.error(f"Invalid JSON for del DirServer: {decrypted_data.decode('utf-8', errors='ignore')}"); self.send_error(sock, client_address, "Invalid JSON format.")
        except (ValueError, TypeError) as ve: self.log.error(f"Type/Value error for del DirServer: {ve}"); self.send_error(sock, client_address, f"Invalid data: {ve}")
        except Exception as e: self.log.error(f"Error handling del DirServer for {client_address}: {e}"); self.send_error(sock, client_address, f"Failed to delete DirServer: {str(e)}")

    def handle_add_dirserver_entry(self, sock, client_address, decrypted_data):
        self.log.info(f"Received add DirServer entry request (CMD {CMD_ADD_DIRSERVER_ENTRY.hex()}) from {client_address}")
        info = self.client_info.get(client_address, {})
        if not info.get('authenticated'):
            self.send_error(sock, client_address, "Auth required."); return
        if not (info.get('user_rights', 0) & SERVER_LIST_EDIT):
            self.send_error(sock, client_address, "Permission denied."); return
        try:
            json_string = decrypted_data.decode('utf-8'); entry_data = json.loads(json_string)
            required_fields = ["wan_ip", "lan_ip", "port", "server_type", "permanent"]
            for field in required_fields:
                if field not in entry_data: self.send_error(sock, client_address, f"Missing field: {field}"); return
            wan_ip = entry_data["wan_ip"]; lan_ip = entry_data["lan_ip"]; port = int(entry_data["port"])
            server_type = entry_data["server_type"]; permanent = int(entry_data["permanent"])
            if not (isinstance(wan_ip, str) and isinstance(lan_ip, str) and isinstance(port, int) and isinstance(server_type, str) and isinstance(permanent, int) and permanent in [0, 1]):
                self.send_error(sock, client_address, "Invalid data types."); return
            dirlistmanager.manager.add_server_info(wan_ip, lan_ip, port, server_type, permanent)
            self.log.info(f"Added/updated DirServer entry: {server_type} at {wan_ip}:{port}")
            response_message = b"Directory server entry added/updated."
            key = self.client_info[client_address]['key']; encrypted_response = encrypt_message(key, response_message)
            self._send_packet(sock, build_packet(CMD_ADD_DIRSERVER_ENTRY, encrypted_response))
        except json.JSONDecodeError: self.log.error(f"Invalid JSON for add DirServer: {decrypted_data.decode('utf-8', errors='ignore')}"); self.send_error(sock, client_address, "Invalid JSON format.")
        except (ValueError, TypeError) as ve: self.log.error(f"Type/Value error for add DirServer: {ve}"); self.send_error(sock, client_address, f"Invalid data: {ve}")
        except Exception as e: self.log.error(f"Error handling add DirServer for {client_address}: {e}"); self.send_error(sock, client_address, f"Failed to add DirServer: {str(e)}")

    def handle_get_full_dirserver_list(self, sock, client_address, decrypted_data):
        self.log.info(f"Received get full DirServer list request (CMD {CMD_GET_FULL_DIRSERVER_LIST.hex()}) from {client_address}")
        info = self.client_info.get(client_address, {})
        if not info.get('authenticated'):
            self.send_error(sock, client_address, "Auth required."); return
        if not (info.get('user_rights', 0) & SERVER_LIST_EDIT):
            self.send_error(sock, client_address, "Permission denied."); return
        try:
            full_list = dirlistmanager.manager.dirserver_list; serializable_list = []
            for entry in full_list:
                serializable_list.append({"wan_ip": entry[0], "lan_ip": entry[1], "port": entry[2], "server_type": entry[3], "permanent": entry[4], "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S', entry[5]) if isinstance(entry[5], time.struct_time) else str(entry[5])})
            json_payload = json.dumps(serializable_list, indent=2); json_bytes = json_payload.encode('utf-8')
            self.log.debug(f"Prepared full DirServer JSON payload, length: {len(json_bytes)}")
            key = self.client_info[client_address]['key']; encrypted_response = encrypt_message(key, json_bytes)
            self._send_packet(sock, build_packet(CMD_GET_FULL_DIRSERVER_LIST, encrypted_response))
            self.log.info(f"Sent encrypted full DirServer list to {client_address}")
        except Exception as e: self.log.error(f"Error getting full DirServer list for {client_address}: {e}"); self.send_error(sock, client_address, f"Failed to get DirServer list: {str(e)}")

    def handle_blobmgr_swap_request(self, sock, client_address, decrypted_data):
        self.log.info(f"Received blobmgr swap blob request (CMD {CMD_BLOBMGR_SWAP_BLOB.hex()}) from {client_address}")
        if not self.client_info.get(client_address, {}).get('authenticated'):
            self.send_error(sock, client_address, "Auth required.")
            return
        try:
            # Parse the swap request to get blob information
            payload_str = decrypted_data.decode('utf-8')
            data = json.loads(payload_str)
            
            blob_filename = data.get('filename', '')
            blob_type = data.get('type', '')
            
            if not blob_filename:
                self.send_error(sock, client_address, "Missing blob filename.")
                return
                
            if blob_type not in ['File', 'DB']:
                self.send_error(sock, client_address, "Invalid blob type. Must be 'File' or 'DB'.")
                return

            self.log.info(f"Blob swap request: {blob_type} blob '{blob_filename}' from {client_address}")

            # Perform the appropriate swap based on blob type
            if blob_type == 'DB':
                swap_success = self._perform_database_blob_swap(blob_filename)
            else:  # File
                swap_success = self._perform_file_blob_swap(blob_filename)
            
            key = self.client_info[client_address]['key']
            if swap_success:
                response_message = f"Successfully swapped to {blob_type} blob: {blob_filename}".encode('utf-8')
            else:
                self.send_error(sock, client_address, f"Failed to swap to {blob_type} blob: {blob_filename}")
                return
                
            encrypted_response = encrypt_message(key, response_message)
            self._send_packet(sock, build_packet(CMD_BLOBMGR_SWAP_BLOB, encrypted_response))
            
        except UnicodeDecodeError:
            self.send_error(sock, client_address, "Invalid payload format for blob swap.")
        except json.JSONDecodeError:
            self.send_error(sock, client_address, "Invalid JSON payload for blob swap.")
        except Exception as e:
            self.log.error(f"Error handling blobmgr swap for {client_address}: {e}")
            self.send_error(sock, client_address, "Failed to process blob swap.")

    def _perform_database_blob_swap(self, blob_filename: str) -> bool:
        """Swap to a database blob by updating emulator.ini config."""
        try:
            # Parse the filename to extract date and time
            # Format: firstblob.bin.YYYY-MM-DD HH_MM_SS or secondblob.bin.YYYY-MM-DD HH_MM_SS - description
            if blob_filename.startswith('firstblob.bin.'):
                name_part = blob_filename[len("firstblob.bin."):]
            elif blob_filename.startswith('secondblob.bin.'):
                name_part = blob_filename[len("secondblob.bin."):]
            else:
                self.log.error(f"Invalid database blob filename format: {blob_filename}")
                return False
            parts = name_part.split(' - ', 1)
            date_time_str = parts[0].strip()
            
            # Remove ' (C)' or similar suffixes if no description was found
            if len(parts) == 1 and ' (' in date_time_str:
                date_time_str = date_time_str.split(' (')[0].strip()
            
            # Parse datetime
            date_obj = datetime.strptime(date_time_str, '%Y-%m-%d %H_%M_%S')
            steam_date = date_obj.strftime('%Y-%m-%d')
            steam_time = date_obj.strftime('%H_%M_%S')
            
            # Update emulator.ini
            import configparser
            config = configparser.ConfigParser()
            config.read('emulator.ini')

            
            # Update the config values
            config.set('config', 'steam_date', steam_date)
            config.set('config', 'steam_time', steam_time)
            
            # Save the config
            with open('emulator.ini', 'w') as configfile:
                config.write(configfile)
            
            self.log.info(f"Updated emulator.ini with steam_date={steam_date}, steam_time={steam_time}")
            
            # Update internal config
            self.config['steam_date'] = steam_date
            self.config['steam_time'] = steam_time
            
            return True
            
        except Exception as e:
            self.log.error(f"Error performing database blob swap: {e}")
            return False
    
    def _perform_file_blob_swap(self, blob_filename: str) -> bool:
        """Swap to a file-based blob by copying files to active location."""
        try:
            # Find the corresponding firstblob
            if not blob_filename.startswith('secondblob.bin.'):
                self.log.error(f"Invalid file blob filename format: {blob_filename}")
                return False
                
            # Extract date from secondblob filename to find matching firstblob
            name_part = blob_filename[len("secondblob.bin."):]
            parts = name_part.split(' - ', 1)
            date_str = parts[0]
            
            # Remove ' (C)' or similar suffixes if no description was found
            if len(parts) == 1 and ' (' in date_str:
                date_str = date_str.split(' (')[0].strip()
            
            # Look for matching firstblob
            blob_base_dir = self.config.get("blobdir", "files/blobs/")
            firstblob_name = None
            
            # First try exact match
            candidate_firstblob = f"firstblob.bin.{date_str}"
            if os.path.exists(os.path.join(blob_base_dir, candidate_firstblob)):
                firstblob_name = candidate_firstblob
            else:
                # Try with (C) suffix
                candidate_firstblob = f"firstblob.bin.{date_str} (C)"
                if os.path.exists(os.path.join(blob_base_dir, candidate_firstblob)):
                    firstblob_name = candidate_firstblob
                else:
                    # Find closest firstblob using cached data
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d %H_%M_%S')
                    second_timestamp = date_obj.timestamp()
                    
                    best_firstblob = None
                    best_timestamp = 0
                    
                    for filename in os.listdir(blob_base_dir):
                        if filename.startswith("firstblob.bin.") and filename.endswith(".bin"):
                            try:
                                fb_name_part = filename[len("firstblob.bin."):]
                                if ' (' in fb_name_part:
                                    fb_name_part = fb_name_part.split(' (')[0]
                                fb_date_obj = datetime.strptime(fb_name_part, '%Y-%m-%d %H_%M_%S')
                                fb_timestamp = fb_date_obj.timestamp()
                                
                                if fb_timestamp <= second_timestamp and fb_timestamp > best_timestamp:
                                    best_timestamp = fb_timestamp
                                    best_firstblob = filename
                            except:
                                continue
                    
                    firstblob_name = best_firstblob
            
            if not firstblob_name:
                self.log.error(f"Could not find matching firstblob for {blob_filename}")
                return False
            
            # Copy the blobs to active location
            first_blob_source_path = os.path.join(blob_base_dir, firstblob_name)
            second_blob_source_path = os.path.join(blob_base_dir, blob_filename)
            
            active_blob_dest_dir = "files"
            os.makedirs(active_blob_dest_dir, exist_ok=True)
            first_blob_dest_path = os.path.join(active_blob_dest_dir, "firstblob.bin")
            second_blob_dest_path = os.path.join(active_blob_dest_dir, "secondblob.bin")
            
            if not os.path.exists(first_blob_source_path):
                self.log.error(f"Source firstblob not found: {first_blob_source_path}")
                return False
            if not os.path.exists(second_blob_source_path):
                self.log.error(f"Source secondblob not found: {second_blob_source_path}")
                return False
            
            # Perform the copy
            shutil.copy2(first_blob_source_path, first_blob_dest_path)
            shutil.copy2(second_blob_source_path, second_blob_dest_path)
            
            self.log.info(f"Copied {firstblob_name} to {first_blob_dest_path}")
            self.log.info(f"Copied {blob_filename} to {second_blob_dest_path}")
            
            # Clear database config settings to indicate file-based blob is active
            import configparser
            config = configparser.ConfigParser()
            config.read('emulator.ini')
            
            if 'config' in config:
                if 'steam_date' in config['config']:
                    config.remove_option('config', 'steam_date')
                if 'steam_time' in config['config']:
                    config.remove_option('config', 'steam_time')
                
                with open('emulator.ini', 'w') as configfile:
                    config.write(configfile)
            
            # Update internal config
            if 'steam_date' in self.config:
                del self.config['steam_date']
            if 'steam_time' in self.config:
                del self.config['steam_time']
            
            self.log.info("Cleared database blob config settings")
            
            return True
            
        except Exception as e:
            self.log.error(f"Error performing file blob swap: {e}")
            return False
            
    def _get_current_blob_info(self):
        """Get information about the currently active blob."""
        try:
            # Check if using database blobs
            if 'steam_date' in self.config and 'steam_time' in self.config:
                return {
                    'type': 'DB',
                    'date': self.config['steam_date'],
                    'time': self.config['steam_time'],
                    'source': 'Database'
                }
            else:
                # File-based blob
                firstblob_path = os.path.join("files", "firstblob.bin")
                secondblob_path = os.path.join("files", "secondblob.bin")

                if os.path.exists(firstblob_path) and os.path.exists(secondblob_path):
                    first_mtime = os.path.getmtime(firstblob_path)
                    second_mtime = os.path.getmtime(secondblob_path)

                    return {
                        'type': 'File',
                        'first_modified': first_mtime,
                        'second_modified': second_mtime,
                        'source': 'File System'
                    }
                else:
                    return {
                        'type': 'File',
                        'source': 'File System (blobs not found)'
                    }
        except Exception as e:
            self.log.error(f"Error getting current blob info: {e}")
            return {'type': 'Unknown', 'source': 'Error'}
            
    def handle_blobmgr_list_request(self, sock, client_address, decrypted_data):
        """Handle blob list request - get blobs and send compressed.

        Supports 'type' parameter in request:
        - 'DB': Return database blobs (default)
        - 'File': Return file-based blobs from cache
        """
        self.log.info(f"Blob list request from {client_address}")

        if not self.client_info.get(client_address, {}).get('authenticated'):
            self.send_error(sock, client_address, "Authentication required.")
            return

        try:
            # Parse request to get blob type
            blob_type = 'DB'  # Default to database blobs
            try:
                if decrypted_data:
                    payload_str = decrypted_data.decode('utf-8')
                    request_data = json.loads(payload_str)
                    blob_type = request_data.get('type', 'DB')
                    self.log.info(f"Blob list request type: {blob_type}")
            except (json.JSONDecodeError, UnicodeDecodeError):
                # If parsing fails, use default (DB)
                self.log.debug("No type parameter in request, defaulting to DB")
                pass

            # If requesting file blobs, use the cached data
            if blob_type == 'File':
                self.log.info(f"Returning {len(self.blob_cache['file_blobs'])} file-based blobs from cache")
                blobs = self.blob_cache['file_blobs']

                # Get package directory for pkg existence info
                packagedir = self.config.get("packagedir", "files/packages/")
                available_steam_pkgs = set()
                available_steamui_pkgs = set()

                try:
                    if os.path.exists(packagedir):
                        files_in_dir = os.listdir(packagedir)
                        for filename in files_in_dir:
                            filename_lower = filename.lower()
                            if filename_lower.startswith("steam_") and filename_lower.endswith(".pkg"):
                                version = filename[6:-4]
                                available_steam_pkgs.add(version)
                            elif filename_lower.startswith("steamui_") and filename_lower.endswith(".pkg"):
                                version = filename[8:-4]
                                available_steamui_pkgs.add(version)
                except Exception as e:
                    self.log.error(f"Error scanning package directory: {e}")

                # Create response
                response = {
                    "blobs": blobs,
                    "available_steam_pkgs": list(available_steam_pkgs),
                    "available_steamui_pkgs": list(available_steamui_pkgs)
                }

                # Convert to JSON
                json_data = json.dumps(response, indent=None, separators=(',', ':'))
                response_bytes = json_data.encode('utf-8')

                self.log.info(f"JSON response size: {len(response_bytes)} bytes ({len(response_bytes)/1024/1024:.2f} MB)")

                # Compress the response
                import gzip
                compressed_bytes = gzip.compress(response_bytes, compresslevel=6)
                self.log.info(f"Compressed size: {len(compressed_bytes)} bytes - {100*(1-len(compressed_bytes)/len(response_bytes)):.1f}% reduction")

                # Encrypt and send
                key = self.client_info[client_address]['key']
                encrypted_response = encrypt_message(key, compressed_bytes)
                self._send_packet(sock, build_packet(CMD_BLOBMGR_LIST_BLOBS, encrypted_response))
                self.log.info(f"Sent {len(blobs)} file-based blobs to {client_address}")
                return

            # Otherwise, proceed with database blob query (original behavior)
            blobs = []

            # Create database connection (same approach as other methods)
            from sqlalchemy import create_engine, text
            from config import get_config
            from datetime import datetime

            # Get database configuration
            db_config = get_config()
            database_host = db_config.get('database_host', 'localhost')
            database_port = int(db_config.get('database_port', '3306'))
            database_username = db_config.get('database_username', 'stmserver')
            database_password = db_config.get('database_password', 'stmserver')

            # Get package directory and scan for available pkg files
            packagedir = self.config.get("packagedir", "files/packages/")
            available_steam_pkgs = set()
            available_steamui_pkgs = set()

            try:
                if os.path.exists(packagedir):
                    files_in_dir = os.listdir(packagedir)

                    for filename in files_in_dir:
                        filename_lower = filename.lower()
                        if filename_lower.startswith("steam_") and filename_lower.endswith(".pkg"):
                            # Extract version from steam_<version>.pkg (case insensitive)
                            version = filename[6:-4]  # Remove prefix and '.pkg' suffix, keeping original case for version
                            available_steam_pkgs.add(version)
                        elif filename_lower.startswith("steamui_") and filename_lower.endswith(".pkg"):
                            # Extract version from steamui_<version>.pkg (case insensitive)
                            version = filename[8:-4]  # Remove prefix and '.pkg' suffix, keeping original case for version
                            available_steamui_pkgs.add(version)

                else:
                    self.log.warning(f"Package directory not found: {packagedir}")
            except Exception as e:
                self.log.error(f"Error scanning package directory: {e}")

            # Create database connection
            db_url = f"mysql+pymysql://{database_username}:{database_password}@{database_host}:{database_port}/"
            engine = create_engine(db_url)
            connection = engine.connect()

            try:
                # First, get configurations (firstblob info)
                configurations_dict = {}
                configurations_query = text("""
                    SELECT filename, steam_pkg, steamui_pkg, ccr_blobdatetime
                    FROM ClientConfigurationDB.configurations
                """)
                configurations_result = connection.execute(configurations_query).fetchall()

                for row in configurations_result:
                    filename = row[0]
                    if filename.startswith('firstblob.bin'):
                        date_str = filename.replace('firstblob.bin.', '').replace(' (C)', '')
                        try:
                            date_obj = datetime.strptime(date_str, '%Y-%m-%d %H_%M_%S')
                            configurations_dict[filename] = {
                                'steam_pkg': row[1],
                                'steamui_pkg': row[2],
                                'date': date_obj
                            }
                        except ValueError:
                            # Skip invalid filename formats
                            continue

                # Now get secondblob data with proper dates and descriptions
                filename_query = text("""
                    SELECT
                        filename,
                        blob_datetime,
                        comments,
                        is_custom
                    FROM
                        BetaContentDescriptionDB.filename
                    UNION
                    SELECT
                        filename,
                        blob_datetime,
                        comments,
                        is_custom
                    FROM
                        ContentDescriptionDB.filename
                    ORDER BY filename;
                """)
                filename_result = connection.execute(filename_query).fetchall()

                blob_count = 0
                for row in filename_result:
                    filename = row[0] or ''
                    blob_datetime = row[1] or ''
                    comments = row[2] or ''
                    is_custom = row[3] or 0

                    if filename.startswith('secondblob.bin.'):
                        date_str = filename.replace('secondblob.bin.', '')

                        try:
                            # Split to separate datetime and description
                            parts = date_str.split(' - ', 1)
                            date_time_str = parts[0].strip()

                            # Remove ' (C)' or similar suffixes if no description was found
                            if len(parts) == 1 and ' (' in date_time_str:
                                date_time_str = date_time_str.split(' (')[0].strip()

                            # Parse datetime
                            date_obj = datetime.strptime(date_time_str, '%Y-%m-%d %H_%M_%S')

                            # Find matching firstblob for version info
                            steam_version = 'Unknown'
                            steamui_version = 'Unknown'

                            matching_firstblobs = [
                                (fname, config['date'])
                                for fname, config in configurations_dict.items()
                                if config['date'] <= date_obj
                            ]

                            if matching_firstblobs:
                                # Select the firstblob with the latest date
                                matching_firstblobs.sort(key=lambda x: x[1], reverse=True)
                                matched_fname = matching_firstblobs[0][0]
                                steam_version = configurations_dict[matched_fname]['steam_pkg'] or 'Unknown'
                                steamui_version = configurations_dict[matched_fname]['steamui_pkg'] or 'Unknown'

                            # Format date for display
                            date_part = date_obj.strftime('%m/%d/%Y')
                            time_part = date_obj.strftime('%I:%M:%S %p')
                            date_display = f"{date_part} {time_part}"

                            # Use comments for description, leave blank if no comments
                            description = comments.strip() if comments else ""

                            # Check if pkg files exist for this blob's versions
                            steam_version_str = str(steam_version).strip() if steam_version and steam_version != 'Unknown' else ''
                            steamui_version_str = str(steamui_version).strip() if steamui_version and steamui_version != 'Unknown' else ''

                            # Check package existence with proper logic
                            if not available_steam_pkgs and not available_steamui_pkgs:
                                # If no packages found at all, don't color anything red
                                steam_pkg_exists = True
                                steamui_pkg_exists = True
                            else:
                                # Check if specific versions exist
                                if steam_version_str and available_steam_pkgs:
                                    steam_pkg_exists = steam_version_str in available_steam_pkgs
                                elif not available_steam_pkgs:
                                    steam_pkg_exists = True  # No steam packages exist, so don't mark as missing
                                else:
                                    steam_pkg_exists = False  # Steam packages exist but this version is missing

                                if steamui_version_str and available_steamui_pkgs:
                                    steamui_pkg_exists = steamui_version_str in available_steamui_pkgs
                                elif not available_steamui_pkgs:
                                    steamui_pkg_exists = True  # No steamui packages exist, so don't mark as missing
                                else:
                                    steamui_pkg_exists = False  # SteamUI packages exist but this version is missing

                            blob_entry = {
                                "filename": filename,
                                "steam_version": str(steam_version),
                                "steamui_version": str(steamui_version),
                                "date": date_display,
                                "description": description,
                                "custom": "Yes" if is_custom else "No",
                                "steam_pkg_exists": steam_pkg_exists,
                                "steamui_pkg_exists": steamui_pkg_exists,
                                "type": "DB"
                            }
                            blobs.append(blob_entry)
                            blob_count += 1

                            # Log progress every 10000 blobs
                            if blob_count % 10000 == 0:
                                self.log.info(f"Processing blobs: {blob_count}...")

                        except ValueError:
                            # Skip blobs with invalid date formats
                            continue
                        except Exception as e:
                            # Log error but continue processing
                            self.log.warning(f"Error processing blob '{filename}': {e}")
                            continue

            except Exception as db_error:
                self.log.error(f"Database query error: {db_error}")
                blobs = []
            finally:
                # Always close database connection
                try:
                    connection.close()
                    engine.dispose()
                except:
                    pass

            self.log.info(f"Found {len(blobs)} total blobs in database")

            # Create response with all blobs and available pkg files
            response = {
                "blobs": blobs,
                "available_steam_pkgs": list(available_steam_pkgs),
                "available_steamui_pkgs": list(available_steamui_pkgs)
            }

            # Convert to JSON
            json_data = json.dumps(response, indent=None, separators=(',', ':'))
            response_bytes = json_data.encode('utf-8')

            self.log.info(f"JSON response size: {len(response_bytes)} bytes ({len(response_bytes)/1024/1024:.2f} MB)")

            # Compress the response to handle large data
            import gzip
            compressed_bytes = gzip.compress(response_bytes, compresslevel=6)
            self.log.info(f"Compressed size: {len(compressed_bytes)} bytes ({len(compressed_bytes)/1024/1024:.2f} MB) - {100*(1-len(compressed_bytes)/len(response_bytes)):.1f}% reduction")

            # Encrypt the compressed data
            key = self.client_info[client_address]['key']
            encrypted_response = encrypt_message(key, compressed_bytes)

            # Send compressed response
            self._send_packet(sock, build_packet(CMD_BLOBMGR_LIST_BLOBS, encrypted_response))
            self.log.info(f"Sent {len(blobs)} compressed blobs to {client_address}")

        except Exception as e:
            self.log.error(f"Error in blob list handler: {e}")
            import traceback
            self.log.error(traceback.format_exc())
            self.send_error(sock, client_address, "Failed to retrieve blob list.")

    def handle_find_content_servers_by_appid(self, sock, client_address, decrypted_data):
        self.log.info(f"Received find content servers by AppID from {client_address}")
        if not self.client_info.get(client_address, {}).get('authenticated'): self.send_error(sock, client_address, "Auth required."); return
        if len(decrypted_data) < 8: self.send_error(sock, client_address, "Invalid payload for content server lookup."); return
        try:
            appid, version = struct.unpack('>II', decrypted_data[:8]) 
            self.log.debug(f"Looking up content servers for AppID: {appid}, Ver: {version}, WAN")
            ip_list, count = contentlistmanager.manager.find_ip_address(appid=appid, version=version, islan=False)
            response_payload = struct.pack(">H", count) if count > 0 and ip_list else struct.pack(">H", 0)
            if count > 0 and ip_list:
                for ip_port_tuple in ip_list: response_payload += utils.encodeIP(ip_port_tuple) 
            key = self.client_info[client_address]['key']; encrypted_response = encrypt_message(key, response_payload)
            self._send_packet(sock, build_packet(CMD_FIND_CONTENT_SERVERS_BY_APPID, encrypted_response))
            self.log.info(f"Sent content server list for AppID {appid} to {client_address}")
        except struct.error as se: self.log.error(f"Struct unpack error for AppID/Version: {se}"); self.send_error(sock, client_address, "Invalid AppID/Version format.")
        except Exception as e: self.log.error(f"Error finding content servers for {client_address}: {e}"); self.send_error(sock, client_address, "Failed to get content server list.")

    def handle_interactive_content_server_finder(self, sock, client_address, decrypted_data):
        """Handle interactive content server finder request."""
        self.log.info(f"Received interactive content server finder request from {client_address}")
        if not self.client_info.get(client_address, {}).get('authenticated'):
            self.send_error(sock, client_address, "Authentication required.")
            return

        try:
            # Get all AppIDs and their versions from content servers
            appid_data = contentlistmanager.manager.get_all_appids_and_versions()

            # Create response payload with all AppIDs and versions
            response = {
                "appid_data": appid_data,
                "total_appids": len(appid_data)
            }

            # Convert to JSON
            import json
            json_data = json.dumps(response, indent=None, separators=(',', ':'))
            response_bytes = json_data.encode('utf-8')

            # Encrypt the response
            key = self.client_info[client_address]['key']
            encrypted_response = encrypt_message(key, response_bytes)

            # Send response
            self._send_packet(sock, build_packet(CMD_INTERACTIVE_CONTENT_SERVER_FINDER, encrypted_response))
            self.log.info(f"Sent interactive content server data for {len(appid_data)} AppIDs to {client_address}")

        except Exception as e:
            self.log.error(f"Error in interactive content server finder for {client_address}: {e}")
            import traceback
            self.log.error(traceback.format_exc())
            self.send_error(sock, client_address, "Failed to retrieve content server data.")

    def handle_directory_lookup(self, sock, client_address, command, decrypted_data):
        self.log.info(f"Received directory lookup command {command.hex()} from {client_address}")
        if not self.client_info.get(client_address, {}).get('authenticated'): self.send_error(sock, client_address, "Auth required."); return
        server_type_str = self.DIR_COMMAND_MAP.get(command)
        if not server_type_str: self.send_error(sock, client_address, "Internal server error: Dir command misconfiguration."); return
        try:
            result_bytes = dirlistmanager.manager.get_and_prep_server_list(server_type_str, islan=False, single=0)
            if result_bytes is None: self.send_error(sock, client_address, "Error retrieving server list from dir manager."); return
            key = self.client_info[client_address]['key']; encrypted_response = encrypt_message(key, result_bytes)
            self._send_packet(sock, build_packet(command, encrypted_response))
            self.log.info(f"Sent encrypted dir server list for {server_type_str} to {client_address}")
        except Exception as e: self.log.error(f"Error in dir lookup for {server_type_str} from {client_address}: {e}"); self.send_error(sock, client_address, "Failed to get dir list.")

    def check_client_heartbeat(self, client_address):
        if client_address in self.client_last_heartbeat:
            if time.time() - self.client_last_heartbeat[client_address] > int(self.config.get('admin_inactive_timeout', 300)): return True
        return False

    def cleanup_timed_out_admins(self):
        """Remove timed-out admin sessions from logged_in_admins."""
        timeout = int(self.config.get('admin_inactive_timeout', 300))
        now = time.time()
        timed_out = []
        for username, client_address in list(self.logged_in_admins.items()):
            last_heartbeat = self.client_last_heartbeat.get(client_address, 0)
            if last_heartbeat > 0 and (now - last_heartbeat) > timeout:
                timed_out.append(username)
                self.log.info(f"Admin session for '{username}' timed out (no heartbeat for {timeout}s)")
        for username in timed_out:
            client_address = self.logged_in_admins.pop(username, None)
            if client_address:
                self.client_info.pop(client_address, None)
                self.client_last_heartbeat.pop(client_address, None)

    def is_admin_already_logged_in(self, username):
        """Check if an admin is already logged in and their session is still active."""
        self.cleanup_timed_out_admins()
        if username in self.logged_in_admins:
            client_address = self.logged_in_admins[username]
            # Check if the session is still valid (not timed out)
            if not self.check_client_heartbeat(client_address):
                return True, client_address
        return False, None

    def handle_heartbeat(self, sock, client_address):
        """Handle heartbeat command from admin tool to keep session alive."""
        if client_address not in self.client_info:
            self.send_error(sock, client_address, "Not authenticated")
            return
        if not self.client_info[client_address].get('authenticated'):
            self.send_error(sock, client_address, "Not logged in")
            return
        # Heartbeat is already tracked in the main loop when data is received,
        # so we just send an OK response
        self.send_ok(sock, client_address)
        self.log.debug(f"Heartbeat received from {client_address}")

    def handle_client_handshake(self, sock, client_address, shared_secret, client_payload):
        if len(client_payload) < 16:
            self.send_error(sock, client_address, "Invalid handshake packet")
            return
        client_salt, client_encrypted = client_payload[:16], client_payload[16:]
        key = derive_key(shared_secret, client_salt)
        try:
            decrypted = decrypt_message(key, client_encrypted)
        except Exception as e:
            self.send_error(sock, client_address, f"Handshake decryption failed: {str(e)}")
            return
        # Older client utilities used a slightly longer identifier which
        # produced a 27 byte payload.  The administration server historically
        # rejected any payload that was not exactly 25 bytes, causing the
        # handshake to fail despite using the correct shared secret.  Accept any
        # identifier length provided it supplies at least the 16 byte client
        # nonce and terminates with the literal ``b"handshake"`` marker.
        if len(decrypted) < 25 or not decrypted.endswith(b"handshake"):
            self.send_error(sock, client_address, "Invalid handshake message")
            return
        response = encrypt_message(key, b"handshake successful")
        self._send_packet(sock, build_packet(b'\x01', response))
        self.client_info[client_address] = {'key': key, 'authenticated': False, 'login_attempts': 0, 'last_attempt_time': 0, 'connected_since': time.time()}
        self.log.info(f"Handshake successful with {client_address}")

    def handle_client_login(self, sock, client_address, decrypted_data):
        parts = decrypted_data.split(b'\x00')
        if len(parts) < 2: self.send_error(sock, client_address, "Login packet format error"); return
        username_str, password_str = parts[0].decode('latin-1'), parts[1].decode('latin-1')
        self.log.info(f"Login attempt from {client_address} for user '{username_str}'")
        client_data = self.client_info.get(client_address, {})
        now = time.time(); last_attempt_time = client_data.get('last_attempt_time', 0)
        login_attempts = client_data.get('login_attempts', 0)
        if now - last_attempt_time > LOGIN_WINDOW_SECONDS: login_attempts = 0
        if login_attempts >= MAX_LOGIN_ATTEMPTS: self.send_error(sock, client_address, "Too many failed login attempts."); return

        # Check if this admin is already logged in from another session
        already_logged_in, existing_address = self.is_admin_already_logged_in(username_str)
        if already_logged_in and existing_address != client_address:
            timeout = int(self.config.get('admin_inactive_timeout', 300))
            self.log.warning(f"User '{username_str}' already logged in from {existing_address}. Login blocked from {client_address}.")
            self.send_error(sock, client_address, f"Admin '{username_str}' is already logged in. Please wait for session timeout ({timeout}s) or logout from other session.")
            return

        is_valid_user, user_rights = self.database.validate_user(username_str, password_str)
        if is_valid_user:
            self.client_info[client_address].update({'authenticated': True, 'login_attempts': 0, 'user_rights': user_rights, 'username': username_str})
            self.logged_in_admins[username_str] = client_address  # Track logged-in admin
            self.auth_stats['success'] = self.auth_stats.get('success', 0) + 1
            self.send_ok(sock, client_address)
            self.log.info(f"User '{username_str}' logged in from {client_address} with rights: {user_rights}")
        else:
            login_attempts += 1
            self.client_info[client_address].update({'login_attempts': login_attempts, 'last_attempt_time': now})
            self.auth_stats['failure'] = self.auth_stats.get('failure', 0) + 1
            self.log.warning(f"Failed login for '{username_str}' from {client_address}. Attempt {login_attempts}/{MAX_LOGIN_ATTEMPTS}")
            self.send_error(sock, client_address, "User Login Failed")

    def handle_client_logout(self, sock, client_address):
        if client_address in self.client_info:
            # Remove from logged_in_admins if this client was logged in
            username = self.client_info[client_address].get('username')
            if username and username in self.logged_in_admins:
                if self.logged_in_admins[username] == client_address:
                    del self.logged_in_admins[username]
                    self.log.info(f"Admin '{username}' removed from logged_in_admins on logout")
            if self.client_info[client_address].get('key'): self.send_ok(sock, client_address)
            del self.client_info[client_address]
            if client_address in self.client_last_heartbeat: del self.client_last_heartbeat[client_address]
            sock.close(); self.log.info(f"Client {client_address} logged out and connection closed.")
        else: self.send_error(sock, client_address, "Client info not found for logout.") 

    def handle_streaming_request(self, sock, client_address):
        status = stream_status(); key = self.client_info[client_address]['key']
        self._send_packet(sock, build_packet(b'\xFF', encrypt_message(key, status.encode('latin-1'))))

    def execute_usermanagement_command(self, sock, client_address, cmd, decrypted_data):
        if not self.client_info.get(client_address, {}).get('authenticated'): self.send_error(sock, client_address, "Auth required."); return
        h_map = {b'\x0A':self.get_user_details_response, b'\x0B':self.parse_username_query, b'\x0C':self.parse_email_query, b'\x0D':self.list_users_response}
        handler = h_map.get(cmd)
        response_payload = handler(decrypted_data) if handler else b"Unknown user mgmt cmd"
        if isinstance(response_payload, str): response_payload = response_payload.encode('latin-1')
        self._send_packet(sock, build_packet(cmd, encrypt_message(self.client_info[client_address]['key'], response_payload)))

    def execute_subscription_command(self, sock, client_address, cmd, decrypted_data):
        info = self.client_info.get(client_address, {})
        if not info.get('authenticated'):
            self.send_error(sock, client_address, "Auth required."); return
        if not (info.get('user_rights', 0) & SUBSCRIPTION_EDIT):
            self.send_error(sock, client_address, "Permission denied."); return
        h_map = {
            b'\x16': self.parse_add_vac_ban,
            b'\x17': self.parse_remove_vac_ban,
            b'\x20': self.list_user_subscriptions,
            b'\x21': self.add_subscription_handler,
            b'\x22': self.remove_subscription_handler,
            b'\x23': self.list_guest_passes_handler,
            b'\x24': self.add_guest_pass_handler,
            b'\x25': self.remove_guest_pass_handler,
        }
        handler = h_map.get(cmd)
        response_payload = handler(decrypted_data) if handler else b"Unknown sub cmd"
        if isinstance(response_payload, str): self.send_error(sock, client_address, response_payload); return
        self._send_packet(sock, build_packet(cmd, encrypt_message(self.client_info[client_address]['key'], response_payload)))

    def execute_admin_command(self, sock, client_address, cmd, decrypted_data):
        info = self.client_info.get(client_address, {})
        if not info.get('authenticated'):
            self.send_error(sock, client_address, "Auth required."); return
        if not (info.get('user_rights', 0) & EDIT_USERS):
            self.send_error(sock, client_address, "Permission denied."); return
        h_map = {b'\x0E':self.create_user_handler, b'\x1E':self.beta1_create_user_handler, b'\x11':self.remove_user_handler, b'\x13':self.change_user_email_handler}
        handler = h_map.get(cmd)
        response_payload = handler(decrypted_data) if handler else b"Unknown admin cmd"
        if isinstance(response_payload, str): self.send_error(sock, client_address, response_payload); return
        self._send_packet(sock, build_packet(cmd, encrypt_message(self.client_info[client_address]['key'], response_payload)))
        
    def execute_ftp_review_command(self, sock, client_address, cmd, decrypted_data):
        info = self.client_info.get(client_address, {})
        if not info.get('authenticated'):
            self.send_error(sock, client_address, "Auth required."); return
        if not (info.get('user_rights', 0) & FTP_APPROVAL):
            self.send_error(sock, client_address, "Permission denied."); return
        h_map = {
            b'\x40': self.list_pending_ftp_uploads,
            b'\x41': self.approve_ftp_upload,
            b'\x42': self.deny_ftp_upload,
            b'\x46': self.list_approved_applications,
            b'\x47': self.get_approved_application,
            b'\x48': self.update_approved_application,
            b'\x49': self.approve_ftp_upload_with_subscriptions,
            b'\x4A': self.reparse_pending_from_xml,
            b'\x4B': self.delete_approved_application
        }
        handler = h_map.get(cmd)
        response_payload = handler(decrypted_data) if handler else b"Unknown FTP cmd"
        self._send_packet(sock, build_packet(cmd, encrypt_message(self.client_info[client_address]['key'], response_payload)))

    def execute_ftp_user_command(self, sock, client_address, cmd, decrypted_data):
        info = self.client_info.get(client_address, {})
        if not info.get('authenticated'):
            self.send_error(sock, client_address, "Auth required."); return
        if not (info.get('user_rights', 0) & FTP_USER_MANAGE):
            self.send_error(sock, client_address, "Permission denied."); return
        h_map = {
            CMD_LIST_FTP_USERS: self.list_ftp_users,
            CMD_ADD_FTP_USER: self.add_ftp_user,
            CMD_REMOVE_FTP_USER: self.remove_ftp_user,
        }
        handler = h_map.get(cmd)
        response_payload = handler(decrypted_data) if handler else b"Unknown FTP user cmd"
        self._send_packet(sock, build_packet(cmd, encrypt_message(self.client_info[client_address]['key'], response_payload)))

    def get_user_details_response(self, data):
        """Return username and email for a given user ID."""
        try:
            user_id = int(data.decode("latin-1").strip())
        except Exception:
            return b"error:invalid user id"
        result = self.database.get_user_by_userid(user_id)
        if isinstance(result, str):
            return result.encode("latin-1")
        username, email = result
        return f"{username}|{email}".encode("latin-1")

    def parse_username_query(self, data):
        """Lookup user(s) by username."""
        username = data.decode("latin-1").strip()
        result = self.database.get_user_by_username(username)
        if isinstance(result, str):
            return result.encode("latin-1")
        count = len(result)
        detail = "|".join(f"{uid},{info}" for uid, info in result)
        return f"{count}|{detail}".encode("latin-1")

    def parse_email_query(self, data):
        """Lookup user(s) by email address."""
        email = data.decode("latin-1").strip()
        result = self.database.get_users_by_email(email)
        if isinstance(result, str):
            return result.encode("latin-1")
        count = len(result)
        detail = "|".join(f"{uid},{name}" for uid, name in result)
        return f"{count}|{detail}".encode("latin-1")

    def list_users_response(self, data=None):
        """Return a list of all users in the database."""
        users = self.database.list_users()
        count = len(users)
        details = "|".join(f"{u[0]},{u[1]},{u[2]}" for u in users)
        return struct.pack(">I", count) + details.encode("latin-1")

    def parse_add_vac_ban(self, data):
        """Add a VAC ban to a user account."""
        try:
            parts = data.decode("latin-1").split("|")
            unique_id = int(parts[0])
            first_appid = int(parts[1])
            last_appid = int(parts[2])
            duration = int(parts[3])
        except Exception:
            return "error:invalid parameters"
        result = self.database.add_vac_ban_to_account(first_appid, last_appid, duration, unique_id)
        return result if isinstance(result, bytes) else result

    def parse_remove_vac_ban(self, data):
        """Remove a VAC ban from a user account."""
        try:
            parts = data.decode("latin-1").split("|")
            unique_id = int(parts[0])
            ban_id = int(parts[1])
        except Exception:
            return "error:invalid parameters"
        result = self.database.remove_vac_ban_from_account(ban_id, unique_id)
        return result if isinstance(result, bytes) else result

    def list_user_subscriptions(self, data):
        """Return subscriptions for a user."""
        try:
            unique_id = int(data.decode("latin-1").strip())
        except Exception:
            return struct.pack(">I", 0)
        subs = self.database.list_user_subscriptions(unique_id)
        if isinstance(subs, str):
            return subs.encode("latin-1")
        count = len(subs)
        detail = "|".join(f"{sid},{name}" for sid, name in subs)
        return struct.pack(">I", count) + detail.encode("latin-1")

    def add_subscription_handler(self, data):
        """Add a subscription to a user."""
        try:
            uid_str, sub_id = data.decode("latin-1").split("|", 1)
            unique_id = int(uid_str)
        except Exception:
            return b"error:invalid parameters"
        result = self.database.add_subscription(unique_id, sub_id)
        if result is True:
            return f"Subscription {sub_id} added to user {unique_id}".encode("latin-1")
        return b"error:failed to add subscription"

    def remove_subscription_handler(self, data):
        """Remove a subscription from a user."""
        try:
            uid_str, sub_id = data.decode("latin-1").split("|", 1)
            unique_id = int(uid_str)
            sub_i = int(sub_id)
        except Exception:
            return b"error:invalid parameters"
        result = self.database.remove_subscription_from_user(unique_id, sub_i)
        if result is True:
            return f"Subscription {sub_i} removed from user {unique_id}".encode("latin-1")
        return b"error:failed to remove subscription"

    def list_guest_passes_handler(self, data):
        """List guest passes for a user."""
        try:
            unique_id = int(data.decode("latin-1").strip())
        except Exception:
            return struct.pack(">I", 0)
        passes = self.database.list_guest_passes(unique_id)
        count = len(passes)
        detail = "|".join(f"{pid},{pkg}" for pid, pkg in passes)
        return struct.pack(">I", count) + detail.encode("latin-1")

    def add_guest_pass_handler(self, data):
        """Add a guest pass for a user."""
        try:
            uid_str, pkg = data.decode("latin-1").split("|", 1)
            unique_id = int(uid_str)
            pkg_i = int(pkg)
        except Exception:
            return b"error:invalid parameters"
        result = self.database.add_guest_pass(unique_id, pkg_i)
        if result is True:
            return f"Guest pass {pkg_i} added to user {unique_id}".encode("latin-1")
        return b"error:failed to add guest pass"

    def remove_guest_pass_handler(self, data):
        """Remove a guest pass from a user."""
        try:
            uid_str, pid = data.decode("latin-1").split("|", 1)
            unique_id = int(uid_str)
            pass_i = int(pid)
        except Exception:
            return b"error:invalid parameters"
        result = self.database.remove_guest_pass(unique_id, pass_i)
        if result is True:
            return f"Guest pass {pass_i} removed from user {unique_id}".encode("latin-1")
        return b"error:failed to remove guest pass"

    def create_user_handler(self, data):
        """Create a new user account."""
        parts = data.decode("latin-1").split("|")
        username = parts[0].strip() if parts else ""
        email = parts[1].strip() if len(parts) > 1 else ""
        if not username:
            return "error:missing username"
        result = self.database.create_user(username, account_email_address=email)
        return str(result).encode("latin-1") if not isinstance(result, bytes) else result

    def beta1_create_user_handler(self, data):
        """Create a Beta1 user account."""
        try:
            username, accountkey, salt, pw_hash = data.decode("latin-1").split("|")
        except ValueError:
            return "error:invalid parameters"
        result = self.database.create_beta1_user(username, accountkey, salt, pw_hash)
        return str(result).encode("latin-1") if not isinstance(result, bytes) else result

    def remove_user_handler(self, data):
        """Remove a user account."""
        try:
            unique_id = int(data.decode("latin-1").strip())
        except Exception:
            return "error:invalid user id"
        result = self.database.remove_user(unique_id)
        return result if isinstance(result, bytes) else result

    def change_user_email_handler(self, data):
        """Change a user's email address."""
        try:
            uid_str, new_email = data.decode("latin-1").split("|", 1)
            unique_id = int(uid_str)
        except Exception:
            return "error:invalid parameters"
        res = self.database.change_user_email(unique_id, new_email)
        if res is True:
            return f"Email changed for user {unique_id}".encode("latin-1")
        elif res is False:
            return b"error:failed to change email"
        else:
            return str(res).encode("latin-1")

    def list_pending_ftp_uploads(self, decrypted_data):
        """Return a summary string of pending FTP uploads."""
        result = self.ftp_database.get_pending_uploads()
        return result.encode("latin-1") if isinstance(result, str) else b""

    def approve_ftp_upload(self, decrypted_data):
        """Approve a pending FTP upload and move files to their final locations.

        All files (XML, DAT, BLOB) are tracked in file_paths. XML files go to
        mod_blob directory, DAT/BLOB files go to SDK depot directory.
        Auto-discovery is still performed as a fallback for any untracked files.
        """
        try:
            appid, admin_user, admin_ip = decrypted_data.decode("latin-1").split("|")
        except ValueError:
            return b"error:invalid parameters"
        pending = self.ftp_database.get_pending_upload_by_appid(appid)
        if not pending:
            return b"error:pending upload not found"

        # Get directory paths
        sdk_depot_dir = self.ftp_database.get_sdk_depot_directory()
        mod_blob_dir = self.ftp_database.get_mod_blob_directory()

        # Ensure directories exist
        os.makedirs(sdk_depot_dir, exist_ok=True)
        os.makedirs(mod_blob_dir, exist_ok=True)

        # Get the XML file path(s) from pending record
        file_paths = pending.get("file_paths", [])
        moved_files = []
        errors = []
        xml_dest_path = None
        temp_directory = None

        # Process all tracked files (XML, DAT, BLOB) and determine temp directory
        for file_path in file_paths:
            if not os.path.exists(file_path):
                errors.append(f"File not found: {file_path}")
                continue
            filename = os.path.basename(file_path)
            ext = os.path.splitext(filename)[1].lower()

            # Remember the temp directory for auto-discovery fallback
            if temp_directory is None:
                temp_directory = os.path.dirname(file_path)

            try:
                if ext == '.xml':
                    # XML files go to mod_blob directory
                    dest_path = os.path.join(mod_blob_dir, filename)
                    shutil.move(file_path, dest_path)
                    moved_files.append(dest_path)
                    xml_dest_path = dest_path
                elif ext in {'.dat', '.blob'}:
                    # DAT/BLOB files go to SDK depot directory
                    dest_path = os.path.join(sdk_depot_dir, filename)
                    shutil.move(file_path, dest_path)
                    moved_files.append(dest_path)
                else:
                    errors.append(f"Unknown file type: {filename}")
            except Exception as e:
                errors.append(f"Error moving {filename}: {e}")

        # Auto-discover any remaining depot files (fallback for untracked files)
        if temp_directory and os.path.isdir(temp_directory):
            try:
                for filename in os.listdir(temp_directory):
                    # Check if filename starts with appid followed by underscore
                    if filename.startswith(f"{appid}_"):
                        ext = os.path.splitext(filename)[1].lower()
                        if ext in {'.dat', '.blob'}:
                            src_path = os.path.join(temp_directory, filename)
                            dest_path = os.path.join(sdk_depot_dir, filename)
                            try:
                                shutil.move(src_path, dest_path)
                                moved_files.append(dest_path)
                            except Exception as e:
                                errors.append(f"Error moving depot {filename}: {e}")
            except Exception as e:
                errors.append(f"Error scanning temp directory: {e}")

        # After moving XML, trigger blob merge via cache_cdr
        if xml_dest_path and os.path.exists(xml_dest_path):
            try:
                logging.info(f"Triggering cache_cdr for LAN after approval of appid {appid}")
                cache_cdr(islan=True, isAppApproval_merge=True)
                logging.info(f"Triggering cache_cdr for WAN after approval of appid {appid}")
                cache_cdr(islan=False, isAppApproval_merge=True)
                logging.info(f"Blob merge completed for appid {appid}")
            except Exception as e:
                errors.append(f"Cache merge failed: {e}")
                logging.warning(f"Failed to merge appid {appid} into cached blobs: {e}")

        # Log the action with details
        details = f"Moved {len(moved_files)} files"
        if errors:
            details += f"; Errors: {'; '.join(errors)}"
        self.ftp_database.log_ftp_admin_action({"username": admin_user, "ip": admin_ip}, appid, "APPROVE", details)
        self.ftp_database.remove_pending_upload(appid)

        if errors:
            return f"approved with errors: {'; '.join(errors)}".encode("latin-1")
        return b"approved"

    def deny_ftp_upload(self, decrypted_data):
        """Deny a pending FTP upload and delete the uploaded files.

        Deletes all tracked files (XML, DAT, BLOB) and also auto-discovers
        any remaining depot files matching the appid as a fallback.
        """
        try:
            appid, admin_user, admin_ip = decrypted_data.decode("latin-1").split("|")
        except ValueError:
            return b"error:invalid parameters"
        pending = self.ftp_database.get_pending_upload_by_appid(appid)
        if not pending:
            return b"error:pending upload not found"

        # Delete all tracked files (XML, DAT, BLOB) and determine temp directory
        file_paths = pending.get("file_paths", [])
        deleted_files = []
        errors = []
        temp_directory = None

        for file_path in file_paths:
            # Remember the temp directory for auto-discovery fallback
            if temp_directory is None:
                temp_directory = os.path.dirname(file_path)

            if not os.path.exists(file_path):
                continue  # File already gone, not an error
            try:
                os.remove(file_path)
                deleted_files.append(file_path)
            except Exception as e:
                errors.append(f"Error deleting {file_path}: {e}")

        # Auto-discover any remaining depot files (fallback for untracked files)
        if temp_directory and os.path.isdir(temp_directory):
            try:
                for filename in os.listdir(temp_directory):
                    # Check if filename starts with appid followed by underscore
                    if filename.startswith(f"{appid}_"):
                        ext = os.path.splitext(filename)[1].lower()
                        if ext in {'.dat', '.blob'}:
                            file_path = os.path.join(temp_directory, filename)
                            try:
                                os.remove(file_path)
                                deleted_files.append(file_path)
                            except Exception as e:
                                errors.append(f"Error deleting depot {filename}: {e}")
            except Exception as e:
                errors.append(f"Error scanning temp directory: {e}")

        # Log the action with details
        details = f"Deleted {len(deleted_files)} files"
        if errors:
            details += f"; Errors: {'; '.join(errors)}"
        self.ftp_database.log_ftp_admin_action({"username": admin_user, "ip": admin_ip}, appid, "DENY", details)
        self.ftp_database.remove_pending_upload(appid)

        if errors:
            return f"denied with errors: {'; '.join(errors)}".encode("latin-1")
        return b"denied"

    def list_approved_applications(self, decrypted_data):
        """Return a summary string of all approved applications."""
        result = self.ftp_database.get_approved_applications_summary()
        return result.encode("latin-1") if isinstance(result, str) else b""

    def get_approved_application(self, decrypted_data):
        """Return details of a specific approved application as JSON."""
        try:
            appid = decrypted_data.decode("latin-1").strip()
        except Exception:
            return b'{"error": "invalid parameters"}'

        app_data = self.ftp_database.get_approved_application_by_appid(appid)
        if not app_data:
            return b'{"error": "application not found"}'

        return json.dumps(app_data).encode("utf-8")

    def update_approved_application(self, decrypted_data):
        """Update an approved application's name and/or subscriptions."""
        try:
            payload = json.loads(decrypted_data.decode("utf-8"))
            appid = payload.get("appid")
            app_names = payload.get("app_names")
            subscriptions = payload.get("subscriptions")
            admin_user = payload.get("admin_user", "unknown")
        except Exception as e:
            return f"error:invalid parameters - {e}".encode("latin-1")

        if not appid:
            return b"error:appid required"

        result = self.ftp_database.update_approved_application(
            appid,
            app_names=app_names,
            subscriptions=subscriptions,
            modified_by=admin_user
        )

        if result is True:
            # Also update the XML file if subscriptions were modified
            if subscriptions:
                app_data = self.ftp_database.get_approved_application_by_appid(appid)
                if app_data and app_data.get('xml_file_path'):
                    xml_path = app_data['xml_file_path']
                    if os.path.exists(xml_path):
                        try:
                            self._update_xml_subscriptions(xml_path, subscriptions)
                        except Exception as e:
                            return f"updated but XML error: {e}".encode("latin-1")
            return b"updated"
        return f"error: {result}".encode("latin-1")

    def approve_ftp_upload_with_subscriptions(self, decrypted_data):
        """Approve a pending FTP upload with modified subscriptions.

        All files (XML, DAT, BLOB) are tracked in file_paths. XML files go to
        mod_blob directory, DAT/BLOB files go to SDK depot directory.
        Auto-discovery is still performed as a fallback for any untracked files.
        """
        try:
            payload = json.loads(decrypted_data.decode("utf-8"))
            appid = payload.get("appid")
            subscriptions = payload.get("subscriptions", "")
            admin_user = payload.get("admin_user", "unknown")
            admin_ip = payload.get("admin_ip", "0.0.0.0")
        except Exception as e:
            return f"error:invalid parameters - {e}".encode("latin-1")

        if not appid:
            return b"error:appid required"

        pending = self.ftp_database.get_pending_upload_by_appid(appid)
        if not pending:
            return b"error:pending upload not found"

        # Get directory paths
        sdk_depot_dir = self.ftp_database.get_sdk_depot_directory()
        mod_blob_dir = self.ftp_database.get_mod_blob_directory()

        # Ensure directories exist
        os.makedirs(sdk_depot_dir, exist_ok=True)
        os.makedirs(mod_blob_dir, exist_ok=True)

        # Get the XML file path(s) from pending record
        file_paths = pending.get("file_paths", [])
        moved_files = []
        errors = []
        xml_dest_path = None
        temp_directory = None

        # Process all tracked files (XML, DAT, BLOB) and determine temp directory
        for file_path in file_paths:
            if not os.path.exists(file_path):
                errors.append(f"File not found: {file_path}")
                continue
            filename = os.path.basename(file_path)
            ext = os.path.splitext(filename)[1].lower()

            # Remember the temp directory for auto-discovery fallback
            if temp_directory is None:
                temp_directory = os.path.dirname(file_path)

            try:
                if ext == '.xml':
                    # Update subscriptions in XML before moving
                    if subscriptions:
                        self._update_xml_subscriptions(file_path, subscriptions)
                    dest_path = os.path.join(mod_blob_dir, filename)
                    shutil.move(file_path, dest_path)
                    moved_files.append(dest_path)
                    xml_dest_path = dest_path
                elif ext in {'.dat', '.blob'}:
                    # DAT/BLOB files go to SDK depot directory
                    dest_path = os.path.join(sdk_depot_dir, filename)
                    shutil.move(file_path, dest_path)
                    moved_files.append(dest_path)
                else:
                    errors.append(f"Unknown file type: {filename}")
            except Exception as e:
                errors.append(f"Error moving {filename}: {e}")

        # Auto-discover any remaining depot files (fallback for untracked files)
        if temp_directory and os.path.isdir(temp_directory):
            try:
                for filename in os.listdir(temp_directory):
                    # Check if filename starts with appid followed by underscore
                    if filename.startswith(f"{appid}_"):
                        ext = os.path.splitext(filename)[1].lower()
                        if ext in {'.dat', '.blob'}:
                            src_path = os.path.join(temp_directory, filename)
                            dest_path = os.path.join(sdk_depot_dir, filename)
                            try:
                                shutil.move(src_path, dest_path)
                                moved_files.append(dest_path)
                            except Exception as e:
                                errors.append(f"Error moving depot {filename}: {e}")
            except Exception as e:
                errors.append(f"Error scanning temp directory: {e}")

        # After moving XML, trigger blob merge via cache_cdr
        if xml_dest_path and os.path.exists(xml_dest_path):
            try:
                logging.info(f"Triggering cache_cdr for LAN after approval of appid {appid}")
                cache_cdr(islan=True, isAppApproval_merge=True)
                logging.info(f"Triggering cache_cdr for WAN after approval of appid {appid}")
                cache_cdr(islan=False, isAppApproval_merge=True)
                logging.info(f"Blob merge completed for appid {appid}")
            except Exception as e:
                errors.append(f"Cache merge failed: {e}")
                logging.warning(f"Failed to merge appid {appid} into cached blobs: {e}")

        # Log the action with details
        details = f"Moved {len(moved_files)} files with modified subscriptions"
        if errors:
            details += f"; Errors: {'; '.join(errors)}"
        self.ftp_database.log_ftp_admin_action({"username": admin_user, "ip": admin_ip}, appid, "APPROVE", details)

        # Add to approved applications table
        subs_to_store = subscriptions if subscriptions else pending.get('subscriptions', '')
        self.ftp_database.add_approved_application(
            appid=appid,
            app_names=pending.get('app_names', ''),
            subscriptions=subs_to_store,
            xml_file_path=xml_dest_path,
            approved_by=admin_user
        )

        self.ftp_database.remove_pending_upload(appid)

        if errors:
            return f"approved with errors: {'; '.join(errors)}".encode("latin-1")
        return b"approved"

    def _update_xml_subscriptions(self, xml_path, subscriptions_str):
        """
        Update subscription IDs in an XML file.
        subscriptions_str format: "id:name|id:name|..."
        """
        import xml.etree.ElementTree as ET

        if not subscriptions_str or not os.path.exists(xml_path):
            return

        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Parse the new subscriptions
        new_subs = {}
        for sub in subscriptions_str.split('|'):
            if ':' in sub:
                sub_id, sub_name = sub.split(':', 1)
                new_subs[sub_id.strip()] = sub_name.strip()

        # Update existing subscription records
        for sub_record in root.findall(".//AllSubscriptionsRecord/SubscriptionRecord"):
            sub_id_attr = sub_record.get("SubscriptionId")
            sub_id_elem = sub_record.find("SubscriptionId")

            old_id = None
            if sub_id_attr:
                old_id = sub_id_attr
            elif sub_id_elem is not None:
                old_id = sub_id_elem.text

            # Update if old ID is in new_subs mapping
            if old_id and old_id in new_subs:
                # Keep the same name but could update ID if needed
                pass  # For now, we keep original structure

            # Find corresponding new subscription by name
            name_elem = sub_record.find("Name")
            if name_elem is not None:
                current_name = name_elem.text or ""
                for new_id, new_name in new_subs.items():
                    if new_name == current_name:
                        if sub_id_attr is not None:
                            sub_record.set("SubscriptionId", new_id)
                        if sub_id_elem is not None:
                            sub_id_elem.text = new_id
                        break

        tree.write(xml_path, encoding='utf-8', xml_declaration=True)

    def reparse_pending_from_xml(self, decrypted_data):
        """
        Re-parse metadata from the XML file for a pending application.
        Data format: JSON with appid field
        Returns JSON with success, message, app_names, subscriptions
        """
        import xml.etree.ElementTree as ET

        try:
            data = json.loads(decrypted_data.decode("utf-8"))
            appid = data.get("appid", "").strip()
        except Exception:
            return json.dumps({"success": False, "message": "Invalid request format"}).encode("utf-8")

        if not appid:
            return json.dumps({"success": False, "message": "AppID is required"}).encode("utf-8")

        pending = self.ftp_database.get_pending_upload_by_appid(appid)
        if not pending:
            return json.dumps({"success": False, "message": "Application not found"}).encode("utf-8")

        # Find the XML file - check multiple possible locations
        xml_path = None
        uploader = pending.get('uploader', '')

        # First, try to find XML in the file_paths list
        for path in pending.get('file_paths', []):
            if path.endswith('.xml') and os.path.exists(path):
                xml_path = path
                break

        # If not found, search in common locations
        if not xml_path:
            possible_paths = [
                # User-specific temp folder (new location)
                os.path.join("files", "temp", uploader, f"{appid}.xml"),
                # Root temp folder (old location)
                os.path.join("files", "temp", f"{appid}.xml"),
                # ContentDescriptionDB.xml in user folder
                os.path.join("files", "temp", uploader, "ContentDescriptionDB.xml"),
                # ContentDescriptionDB.xml in root temp
                os.path.join("files", "temp", "ContentDescriptionDB.xml"),
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    xml_path = path
                    break

        if not xml_path:
            searched_paths = ", ".join(possible_paths) if 'possible_paths' in dir() else "file_paths list"
            return json.dumps({"success": False, "message": f"No XML file found. Searched: {searched_paths}"}).encode("utf-8")

        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()

            # Parse app names
            app_names = []
            for app_record in root.findall(".//AllAppsRecord/AppRecord"):
                name_elem = app_record.find("Name")
                if name_elem is not None and name_elem.text:
                    app_names.append(name_elem.text)
            app_names_str = ", ".join(app_names)

            # Parse subscriptions
            subs_list = []
            for sub_record in root.findall(".//AllSubscriptionsRecord/SubscriptionRecord"):
                sub_id = sub_record.get("SubscriptionId")
                if sub_id is None:
                    sub_id_elem = sub_record.find("SubscriptionId")
                    sub_id = sub_id_elem.text if sub_id_elem is not None else None
                name_elem = sub_record.find("Name")
                name = name_elem.text if name_elem is not None else "Unknown"
                if sub_id is not None:
                    subs_list.append(f"{sub_id}:{name}")
            subs_str = "|".join(subs_list)

            # Update the database entry
            from utilities.database.base_dbdriver import AwaitingReview
            entry = self.ftp_database.session.query(AwaitingReview).filter_by(appid=appid).first()
            if entry:
                entry.app_names = app_names_str
                entry.subscriptions = subs_str
                # Also update file_paths if the XML wasn't recorded there
                if not entry.file_paths or xml_path not in entry.file_paths:
                    if entry.file_paths:
                        entry.file_paths = entry.file_paths + "|" + xml_path
                    else:
                        entry.file_paths = xml_path
                self.ftp_database.session.commit()

            return json.dumps({
                "success": True,
                "message": f"Re-parsed: {len(subs_list)} subscriptions, {len(app_names)} apps",
                "app_names": app_names_str,
                "subscriptions": subs_str
            }).encode("utf-8")

        except Exception as e:
            return json.dumps({"success": False, "message": f"Error parsing XML: {e}"}).encode("utf-8")

    def delete_approved_application(self, decrypted_data):
        """Delete an approved application and its associated files.

        Removes the XML file from mod_blob, DAT/BLOB files from steam2_sdk_depots,
        and the database entry.

        Data format: "appid|admin_user|admin_ip"
        """
        try:
            appid, admin_user, admin_ip = decrypted_data.decode("latin-1").split("|")
        except ValueError:
            return b"error:invalid parameters"

        # Get the application data first
        app_data = self.ftp_database.get_approved_application_by_appid(appid)
        if not app_data:
            return b"error:application not found"

        # Get directory paths
        sdk_depot_dir = self.ftp_database.get_sdk_depot_directory()
        mod_blob_dir = self.ftp_database.get_mod_blob_directory()

        deleted_files = []
        errors = []

        # Delete the XML file from mod_blob
        xml_path = app_data.get('xml_file_path')
        if xml_path and os.path.exists(xml_path):
            try:
                os.remove(xml_path)
                deleted_files.append(xml_path)
                logging.info(f"Deleted XML file: {xml_path}")
            except Exception as e:
                errors.append(f"Error deleting XML {xml_path}: {e}")

        # Find and delete DAT/BLOB files matching appid pattern in steam2_sdk_depots
        if os.path.isdir(sdk_depot_dir):
            try:
                for filename in os.listdir(sdk_depot_dir):
                    # Check if filename starts with appid followed by underscore
                    if filename.startswith(f"{appid}_"):
                        ext = os.path.splitext(filename)[1].lower()
                        if ext in {'.dat', '.blob'}:
                            file_path = os.path.join(sdk_depot_dir, filename)
                            try:
                                os.remove(file_path)
                                deleted_files.append(file_path)
                                logging.info(f"Deleted depot file: {file_path}")
                            except Exception as e:
                                errors.append(f"Error deleting {file_path}: {e}")
            except Exception as e:
                errors.append(f"Error scanning SDK depot directory: {e}")

        # Remove the database entry
        db_result = self.ftp_database.remove_approved_application(appid)
        if db_result is not True:
            errors.append(f"Database error: {db_result}")

        # Log the admin action
        details = f"Deleted {len(deleted_files)} files"
        if errors:
            details += f"; Errors: {'; '.join(errors)}"
        self.ftp_database.log_ftp_admin_action({"username": admin_user, "ip": admin_ip}, appid, "DELETE", details)

        if errors:
            return f"deleted with errors: {'; '.join(errors)}".encode("latin-1")
        return b"deleted"

    # --- FTP user management ---
    FTP_ACCOUNTS_FILE = "ftpaccounts.txt"
    FTP_QUOTA_FILE = "ftpquota.json"

    def _load_ftp_quota(self):
        try:
            if os.path.exists(self.FTP_QUOTA_FILE):
                with open(self.FTP_QUOTA_FILE, "r") as f:
                    self.ftp_quota = json.load(f)
        except Exception:
            self.ftp_quota = {}

    def _save_ftp_quota(self):
        try:
            with open(self.FTP_QUOTA_FILE, "w") as f:
                json.dump(self.ftp_quota, f)
        except Exception:
            pass

    def list_ftp_users(self, decrypted_data):
        """List all FTP users from the database."""
        try:
            db_users = self.ftp_database.get_ftp_users()
            users = []
            for user in db_users:
                status = "LOCKED" if user.get('is_locked') else ""
                perm = user.get('permissions', 'r')
                if status:
                    users.append(f"{user['username']}:{perm}:{status}")
                else:
                    users.append(f"{user['username']}:{perm}")
            return "|".join(users).encode("latin-1") if users else b"No FTP users"
        except Exception as e:
            return f"error:{e}".encode('latin-1')

    def add_ftp_user(self, decrypted_data):
        """Add a new FTP user to the database."""
        try:
            username, password, perm = decrypted_data.decode('latin-1').split('|')
        except ValueError:
            return b"error:invalid parameters"
        try:
            result = self.ftp_database.add_ftp_user(
                username=username,
                password=password,
                permissions=perm,
                created_by="remote_admin"
            )
            if result is True:
                return b"added"
            return f"error:{result}".encode('latin-1')
        except Exception as e:
            return f"error:{e}".encode('latin-1')

    def remove_ftp_user(self, decrypted_data):
        """Remove an FTP user from the database."""
        username = decrypted_data.decode('latin-1').strip()
        try:
            result = self.ftp_database.remove_ftp_user(username)
            if result is True:
                return b"removed"
            return f"error:{result}".encode('latin-1')
        except Exception as e:
            return f"error:{e}".encode('latin-1')

    def _send_packet(self, sock, packet):
        try:
            self.bandwidth_usage['tx'] += len(packet)
            if self.rate_limit_kbps > 0:
                time.sleep(len(packet) / 1024 / self.rate_limit_kbps)
            
            # For large packets (like blob lists), send in chunks to prevent socket buffer overflow
            if len(packet) > 65536:  # 64KB threshold
                bytes_sent = 0
                chunk_size = 32768  # 32KB chunks
                while bytes_sent < len(packet):
                    chunk = packet[bytes_sent:bytes_sent + chunk_size]
                    sock.sendall(chunk)
                    bytes_sent += len(chunk)
                    # Small delay between chunks for large data
                    if bytes_sent < len(packet):
                        time.sleep(0.01)
            else:
                sock.sendall(packet)
        except Exception as e:
            self.log.error(f"Send error: {e}")

    def send_error(self, sock, client_address, error_message):
        error_payload = f"error:{error_message}".encode("latin-1") if isinstance(error_message, str) else b"error:" + error_message
        key = self.client_info.get(client_address, {}).get('key')
        payload_to_send = encrypt_message(key, error_payload) if key else error_payload
        packet = build_packet(b'\xEE', payload_to_send)
        self._send_packet(sock, packet)
        self.log.error(f"Sent error to {client_address}: {error_message}")
    def send_ok(self, sock, client_address):
        key = self.client_info.get(client_address, {}).get('key')
        if not key: self.log.error(f"No session key for {client_address} to send OK."); return
        self._send_packet(sock, build_packet(b'\x00', encrypt_message(key, b'')))

    def send_success(self, sock, client_address, cmd: bytes, message: str):
        """Send a success response with a meaningful message back to the client."""
        key = self.client_info.get(client_address, {}).get('key')
        if not key:
            self.log.error(f"No session key for {client_address} to send success message.")
            return
        payload = message.encode('latin-1')
        self._send_packet(sock, build_packet(cmd, encrypt_message(key, payload)))
        self.log.info(f"Sent success to {client_address}: {message}")

    def handle_get_detailed_blob_list(self, sock, client_address, decrypted_data):
        self.log.info(f"Received get detailed blob list request (CMD {CMD_GET_DETAILED_BLOB_LIST.hex()}) from {client_address}")
        if not self.client_info.get(client_address, {}).get('authenticated'):
            self.send_error(sock, client_address, "Authentication required.")
            return

        try:
            # Get current in-use blob information
            current_blob_info = self._get_current_blob_info()
            
            # Prepare response with both blob lists and current blob info
            response_data = {
                "file_blobs": self.blob_cache['file_blobs'],
                "db_blobs": self.blob_cache['db_blobs'],
                "current_blob": current_blob_info
            }

            # Send the response without compression
            json_payload = json.dumps(response_data, separators=(',', ':'))  # Remove whitespace
            json_bytes = json_payload.encode('utf-8')
            
            # DISABLED: Compress using gzip
            # import gzip
            # compressed_data = gzip.compress(json_bytes, compresslevel=9)
            
            key = self.client_info[client_address]['key']
            encrypted_response = encrypt_message(key, json_bytes)
            self._send_packet(sock, build_packet(CMD_GET_DETAILED_BLOB_LIST, encrypted_response))
            
            total_blobs = len(self.blob_cache['file_blobs']) + len(self.blob_cache['db_blobs'])
            self.log.info(f"Sent detailed blob list to {client_address} ({total_blobs} blobs, uncompressed {len(json_bytes)} bytes)")

        except Exception as e:
            self.log.error(f"Error handling get detailed blob list for {client_address}: {e}")
            self.send_error(sock, client_address, f"Failed to retrieve detailed blob list: {str(e)}")

    def _get_current_blob_info(self):
        """Get information about the currently in-use blob."""
        try:
            # Check which type of blob is currently in use based on config
            steam_date = self.config.get('steam_date', '')
            steam_time = self.config.get('steam_time', '')
            
            current_blob_info = {
                "SteamVersion": "Not Available",
                "SteamUIVersion": "Not Available", 
                "Date": "Not Available",
                "Type": "Unknown"
            }
            
            if steam_date and steam_time:
                # Database blob is in use
                date_display = f"{steam_date}   {steam_time}"
                current_blob_info["Date"] = date_display
                current_blob_info["Type"] = "DB"
                
                # Try to find version info from database blobs
                for db_blob in self.blob_cache['db_blobs']:
                    blob_date = db_blob.get('Date', '')
                    # More flexible date matching
                    if (steam_date in blob_date and steam_time in blob_date) or \
                       (steam_date.replace('/', '-') in blob_date and steam_time in blob_date):
                        current_blob_info["SteamVersion"] = db_blob.get('SteamVersion', 'Not Available')
                        current_blob_info["SteamUIVersion"] = db_blob.get('SteamUIVersion', 'Not Available')
                        current_blob_info["Date"] = db_blob.get('Date', date_display)
                        break
            else:
                # DISABLED: File-based blob support is disabled
                current_blob_info["Type"] = "None"
                current_blob_info["Date"] = "File-based blobs are disabled"
                # File-based blob is in use - check if firstblob.bin and secondblob.bin exist (DISABLED)
                # firstblob_path = os.path.join("files", "firstblob.bin")
                # secondblob_path = os.path.join("files", "secondblob.bin")
                # 
                # if os.path.exists(firstblob_path) and os.path.exists(secondblob_path):
                #     current_blob_info["Type"] = "File"
                #     try:
                #         # Read version info from firstblob
                #         with open(firstblob_path, "rb") as f:
                #             first_content = f.read()
                #         if first_content.startswith(b"\x01\x43"):
                #             first_content = zlib.decompress(first_content[20:])
                #         first_data = blobs.blob_unserialize(first_content)
                #         steam_ver = first_data.get(b'\x01\x00\x00\x00', b'Not Available')
                #         steamui_ver = first_data.get(b'\x02\x00\x00\x00', b'Not Available')
                #         current_blob_info["SteamVersion"] = steam_ver.decode('utf-8', 'replace') if isinstance(steam_ver, bytes) else str(steam_ver)
                #         current_blob_info["SteamUIVersion"] = steamui_ver.decode('utf-8', 'replace') if isinstance(steamui_ver, bytes) else str(steamui_ver)
                #         
                #         # Get date from secondblob
                #         with open(secondblob_path, "rb") as f:
                #             second_content = f.read()
                #         if second_content.startswith(b"\x01\x43"):
                #             second_content = zlib.decompress(second_content[20:])
                #         second_data = blobs.blob_unserialize(second_content)
                #         
                #         date_val = second_data.get(b"\x03\x00\x00\x00")
                #         if date_val:
                #             try:
                #                 from utilities.time import steamtime_to_datetime
                #                 current_blob_info["Date"] = steamtime_to_datetime(date_val)
                #             except:
                #                 current_blob_info["Date"] = "Invalid Date Format"
                #                 
                #     except Exception as e:
                #         self.log.warning(f"Error reading current blob info: {e}")
            
            return current_blob_info
            
        except Exception as e:
            self.log.error(f"Error getting current blob info: {e}")
            return {
                "SteamVersion": "Unknown",
                "SteamUIVersion": "Unknown",
                "Date": "Unknown", 
                "Type": "Unknown"
            }

    # ----- New monitoring and config handlers -----
    def handle_get_live_log(self, sock, client_address, decrypted_data):
        info = self.client_info.get(client_address, {})
        if not info.get('authenticated'):
            self.send_error(sock, client_address, "Authentication required."); return
        log_path = self.config.get('admin_log_file', 'admin.log')
        try:
            if os.path.exists(log_path):
                with open(log_path, 'r') as f:
                    lines = f.readlines()[-50:]
                payload = ''.join(lines).encode('latin-1')
            else:
                payload = b''
            self._send_packet(sock, build_packet(CMD_GET_LIVE_LOG, encrypt_message(info['key'], payload)))
        except Exception as e:
            self.send_error(sock, client_address, f"log error:{e}")

    def handle_get_auth_stats(self, sock, client_address, decrypted_data):
        info = self.client_info.get(client_address, {})
        if not info.get('authenticated'):
            self.send_error(sock, client_address, "Authentication required."); return
        payload = json.dumps(self.auth_stats).encode('latin-1')
        self._send_packet(sock, build_packet(CMD_GET_AUTH_STATS, encrypt_message(info['key'], payload)))

    def handle_set_rate_limit(self, sock, client_address, decrypted_data):
        info = self.client_info.get(client_address, {})
        if not info.get('authenticated'):
            self.send_error(sock, client_address, "Authentication required."); return
        try:
            new_limit = int(decrypted_data.decode('latin-1').strip())
            self.rate_limit_kbps = new_limit
            self.send_success(sock, client_address, CMD_SET_RATE_LIMIT, f"Rate limit set to {new_limit} kbps")
        except Exception:
            self.send_error(sock, client_address, "invalid rate")

    def handle_get_bw_stats(self, sock, client_address, decrypted_data):
        info = self.client_info.get(client_address, {})
        if not info.get('authenticated'):
            self.send_error(sock, client_address, "Authentication required."); return
        payload = json.dumps(self.bandwidth_usage).encode('latin-1')
        self._send_packet(sock, build_packet(CMD_GET_BW_STATS, encrypt_message(info['key'], payload)))

    def handle_get_connection_count(self, sock, client_address, decrypted_data):
        info = self.client_info.get(client_address, {})
        if not info.get('authenticated'):
            self.send_error(sock, client_address, "Authentication required."); return
        count = len(self.client_info)
        payload = str(count).encode('latin-1')
        self._send_packet(sock, build_packet(CMD_GET_CONN_COUNT, encrypt_message(info['key'], payload)))

    def handle_edit_config(self, sock, client_address, decrypted_data):
        info = self.client_info.get(client_address, {})
        if not info.get('authenticated'):
            self.send_error(sock, client_address, "Authentication required."); return
        if not (info.get('user_rights', 0) & CONFIG_EDIT):
            self.send_error(sock, client_address, "Permission denied."); return
        try:
            key_str, val_str = decrypted_data.decode('latin-1').split('|', 1)
            self.config[key_str] = val_str
            try:
                from config import save_config_value
                save_config_value(key_str, val_str)
            except Exception:
                pass
            self.send_success(sock, client_address, CMD_EDIT_CONFIG, f"Config '{key_str}' updated")
        except Exception as e:
            self.send_error(sock, client_address, f"config error:{e}")

    def handle_toggle_feature(self, sock, client_address, decrypted_data):
        info = self.client_info.get(client_address, {})
        if not info.get('authenticated'):
            self.send_error(sock, client_address, "Authentication required."); return
        if not (info.get('user_rights', 0) & CONFIG_EDIT):
            self.send_error(sock, client_address, "Permission denied."); return
        try:
            name, state = decrypted_data.decode('latin-1').split('|',1)
            new_state = bool(int(state))
            self.feature_flags[name] = new_state
            state_str = "enabled" if new_state else "disabled"
            self.send_success(sock, client_address, CMD_TOGGLE_FEATURE, f"Feature '{name}' {state_str}")
        except Exception:
            self.send_error(sock, client_address, "toggle error")

    def handle_get_session_report(self, sock, client_address, decrypted_data):
        info = self.client_info.get(client_address, {})
        if not info.get('authenticated'):
            self.send_error(sock, client_address, "Authentication required."); return
        report = []
        for addr, cinfo in self.client_info.items():
            entry = {
                'ip': addr[0],
                'port': addr[1],
                'username': cinfo.get('username', ''),
                'authenticated': cinfo.get('authenticated', False),
                'rights': cinfo.get('user_rights', 0),
                'connected_since': cinfo.get('connected_since')
            }
            report.append(entry)
        payload = json.dumps(report).encode('latin-1')
        self._send_packet(sock, build_packet(CMD_GET_SESSION_REPORT, encrypt_message(info['key'], payload)))

    def handle_set_ftp_quota(self, sock, client_address, decrypted_data):
        info = self.client_info.get(client_address, {})
        if not info.get('authenticated'):
            self.send_error(sock, client_address, "Authentication required."); return
        if not (info.get('user_rights', 0) & FTP_USER_MANAGE):
            self.send_error(sock, client_address, "Permission denied."); return
        try:
            username, quota, bw = decrypted_data.decode('latin-1').split('|')
            self.ftp_quota[username] = {'quota': int(quota), 'bw': int(bw)}
            self._save_ftp_quota()
            self.send_success(sock, client_address, CMD_SET_FTP_QUOTA, f"Quota set for {username}: {quota}MB, {bw}kbps")
        except Exception:
            self.send_error(sock, client_address, "quota error")

    def handle_hot_reload_config(self, sock, client_address, decrypted_data):
        """
        Hot reload for CMSERVER only.
        Reloads all files within the steam3 directory in the same way they load during initial start.
        """
        info = self.client_info.get(client_address, {})
        if not info.get('authenticated'):
            self.send_error(sock, client_address, "Authentication required."); return
        if not (info.get('user_rights', 0) & CONFIG_EDIT):
            self.send_error(sock, client_address, "Permission denied."); return
        try:
            from utilities import thread_handler

            # Hot reload all steam3 modules (CM server handler code)
            success, message, count = thread_handler.reload_steam3_modules()

            if success:
                self.log.info(f"CM server hot reload completed: {message}")
                # Send success response with details
                key = self.client_info[client_address]['key']
                response = f"CMSERVER hot reload: {message}"
                encrypted_response = encrypt_message(key, response.encode('latin-1'))
                self._send_packet(sock, build_packet(CMD_HOT_RELOAD_CONFIG, encrypted_response))
            else:
                self.log.error(f"CM server hot reload failed: {message}")
                self.send_error(sock, client_address, f"Hot reload failed: {message}")
        except Exception as e:
            self.log.error(f"Hot reload error: {e}", exc_info=True)
            self.send_error(sock, client_address, f"reload error:{e}")

    def execute_chatroom_command(self, sock, client_address, decrypted_data):
        info = self.client_info.get(client_address, {})
        if not info.get('authenticated'):
            self.send_error(sock, client_address, "Auth required."); return
        if not (info.get('user_rights', 0) & CHATROOM_MANAGE):
            self.send_error(sock, client_address, "Permission denied."); return
        try:
            payload = json.loads(decrypted_data.decode('utf-8'))
            action = payload.get('action')
            if action == 'list':
                rooms = self.community_db.session.query(ChatRoomRegistry).all()
                result = [{'id': r.UniqueID, 'name': r.chatroom_name} for r in rooms]
                resp = json.dumps(result).encode('utf-8')
            elif action == 'create':
                name = payload.get('name')
                if not name:
                    raise ValueError('name required')
                owner = int(payload.get('owner', 1))
                room = ChatRoomRegistry(chatroom_name=name,
                                        owner_accountID=owner,
                                        datetime=datetime.utcnow())
                self.community_db.session.add(room)
                self.community_db.session.commit()
                resp = json.dumps({'id': room.UniqueID}).encode('utf-8')
            elif action == 'remove':
                cid = int(payload.get('id', 0))
                self.community_db.session.query(ChatRoomRegistry).filter_by(UniqueID=cid).delete()
                self.community_db.session.commit()
                resp = b'ok'
            else:
                resp = b'error:unknown'
        except Exception as e:
            self.community_db.session.rollback()
            self.send_error(sock, client_address, f"chatroom:{e}")
            return
        self._send_packet(sock, build_packet(CMD_CHATROOM_OP, encrypt_message(info['key'], resp)))

    def execute_clan_command(self, sock, client_address, decrypted_data):
        info = self.client_info.get(client_address, {})
        if not info.get('authenticated'):
            self.send_error(sock, client_address, "Auth required."); return
        if not (info.get('user_rights', 0) & CLAN_MANAGE):
            self.send_error(sock, client_address, "Permission denied."); return
        try:
            payload = json.loads(decrypted_data.decode('utf-8'))
            action = payload.get('action')
            sess = self.community_db.session
            if action == 'list':
                clans = sess.query(CommunityClanRegistry).all()
                result = [{'id': c.UniqueID, 'name': c.clan_name, 'tag': c.clan_tag} for c in clans]
                resp = json.dumps(result).encode('utf-8')
            elif action == 'create':
                name = payload.get('name'); tag = payload.get('tag')
                if not name or not tag:
                    raise ValueError('name and tag required')
                owner = int(payload.get('owner', 1))
                clan = CommunityClanRegistry(clan_name=name, clan_tag=tag, owner_accountID=owner)
                sess.add(clan); sess.commit()
                resp = json.dumps({'id': clan.UniqueID}).encode('utf-8')
            elif action == 'remove':
                cid = int(payload.get('id', 0))
                sess.query(CommunityClanRegistry).filter_by(UniqueID=cid).delete()
                sess.commit(); resp = b'ok'
            else:
                resp = b'error:unknown'
        except Exception as e:
            self.community_db.session.rollback()
            self.send_error(sock, client_address, f"clan:{e}")
            return
        self._send_packet(sock, build_packet(CMD_CLAN_OP, encrypt_message(info['key'], resp)))

    def execute_gift_command(self, sock, client_address, decrypted_data):
        info = self.client_info.get(client_address, {})
        if not info.get('authenticated'):
            self.send_error(sock, client_address, "Auth required."); return
        if not (info.get('user_rights', 0) & SUBSCRIPTION_EDIT):
            self.send_error(sock, client_address, "Permission denied."); return
        self._send_packet(sock, build_packet(CMD_GIFT_OP, encrypt_message(info['key'], b'\x00')))

    def execute_news_command(self, sock, client_address, decrypted_data):
        info = self.client_info.get(client_address, {})
        if not info.get('authenticated'):
            self.send_error(sock, client_address, "Auth required."); return
        if not (info.get('user_rights', 0) & NEWS_MANAGE):
            self.send_error(sock, client_address, "Permission denied."); return
        try:
            from steam3.misc import newsupdate_db
            payload = json.loads(decrypted_data.decode('utf-8'))
            action = payload.get('action')
            if action == 'list':
                resp = json.dumps(list(newsupdate_db.client_news_updates.keys())).encode('utf-8')
            elif action == 'remove':
                ts = payload.get('timestamp')
                newsupdate_db.client_news_updates.pop(ts, None)
                resp = b'ok'
            else:
                resp = b'error'
        except Exception as e:
            self.send_error(sock, client_address, f"news:{e}")
            return
        self._send_packet(sock, build_packet(CMD_NEWS_OP, encrypt_message(info['key'], resp)))

    def execute_license_command(self, sock, client_address, decrypted_data):
        info = self.client_info.get(client_address, {})
        if not info.get('authenticated'):
            self.send_error(sock, client_address, "Auth required."); return
        if not (info.get('user_rights', 0) & LICENSE_MANAGE):
            self.send_error(sock, client_address, "Permission denied."); return
        try:
            payload = json.loads(decrypted_data.decode('utf-8'))
            uid = int(payload.get('user'))
            lic = self.community_db.get_user_owned_subscription_ids(uid)
            resp = json.dumps(lic).encode('utf-8')
        except Exception as e:
            self.send_error(sock, client_address, f"license:{e}")
            return
        self._send_packet(sock, build_packet(CMD_LICENSE_OP, encrypt_message(info['key'], resp)))

    def execute_token_command(self, sock, client_address, decrypted_data):
        info = self.client_info.get(client_address, {})
        if not info.get('authenticated'):
            self.send_error(sock, client_address, "Auth required."); return
        if not (info.get('user_rights', 0) & TOKEN_MANAGE):
            self.send_error(sock, client_address, "Permission denied."); return
        try:
            payload = json.loads(decrypted_data.decode('utf-8'))
            action = payload.get('action')
            user_id = int(payload.get('user'))
            if action == 'list':
                tokens = server_stats.list_connection_tokens(user_id)
                resp = json.dumps(tokens).encode('utf-8')
            elif action == 'revoke':
                token_hex = payload.get('token')
                server_stats.revoke_connection_token(user_id, token_hex)
                resp = b'ok'
            else:
                resp = b'error:unknown'
        except Exception as e:
            self.send_error(sock, client_address, f"token:{e}")
            return
        self._send_packet(sock, build_packet(CMD_TOKEN_OP, encrypt_message(info['key'], resp)))

    def execute_inventory_command(self, sock, client_address, decrypted_data):
        info = self.client_info.get(client_address, {})
        if not info.get('authenticated'):
            self.send_error(sock, client_address, "Auth required."); return
        if not (info.get('user_rights', 0) & INVENTORY_EDIT):
            self.send_error(sock, client_address, "Permission denied."); return
        try:
            payload = json.loads(decrypted_data.decode('utf-8'))
            user_id = int(payload.get('user'))
            items = self.community_db.session.query(ClientInventoryItems).filter_by(friendRegistryID=user_id).all()
            result = [{'item': it.itemID, 'app': it.appID, 'qty': it.quantity} for it in items]
            resp = json.dumps(result).encode('utf-8')
        except Exception as e:
            self.send_error(sock, client_address, f"inventory:{e}")
            return
        self._send_packet(sock, build_packet(CMD_INVENTORY_OP, encrypt_message(info['key'], resp)))

# End of administrationserver class
