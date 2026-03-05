#!/usr/bin/env python3
"""
Networking module for Administration Client

Packet format (must match server):
  HEADER (4 bytes) + CMD (1 byte) + LENGTH (4 bytes, big-endian) + PAYLOAD + CHECKSUM (2 bytes)

Provides functions for encryption/decryption, packet building/parsing, and a stub streaming status.
"""

import os
import socket
import struct
import logging
import json
import inspect
import threading
import time
from typing import Optional, Tuple
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import scrypt

log = logging.getLogger('NETWORKING')

# --- Constants and Helpers ---
HEADER = b"\xbe\xee\xee\xff"

# Default socket timeout (in seconds) for communication with the
# administration server.  The original timeout of 5 seconds proved a bit
# aggressive when the server was under heavy load which caused otherwise
# valid responses (such as the blob list) to be missed.  A slightly longer
# timeout combined with a single retry helps the client handle these cases
# more gracefully.
SOCKET_TIMEOUT = 10
CMD_LOGOFF = b'\x04'
CMD_HEARTBEAT = b'\x05'       # Heartbeat command for inactivity timeout prevention
CMD_LIST_BLOBS = b'\x30'      # Command for List Available Blobs
CMD_SWAP_BLOB = b'\x31'       # Command for Swap Blob
CMD_LIST_AUTH_SERVERS = b'\x12' # Command for Listing Authentication Servers
CMD_LIST_CONFIG_SERVERS = b'\x03'# Command for Listing Configuration Servers
CMD_GET_FULL_DIRSERVER_LIST = b'\x70' # Command for Full DirServer List (JSON)
CMD_ADD_DIRSERVER_ENTRY = b'\x71'   # Command for Adding DirServer Entry (JSON)
CMD_DEL_DIRSERVER_ENTRY = b'\x72'   # Command for Deleting DirServer Entry (JSON)
CMD_GET_FULL_CONTENTSERVER_LIST = b'\x73' # Command for Full ContentServer List (JSON)
CMD_ADD_CONTENTSERVER_ENTRY = b'\x74'   # Command for Adding ContentServer Entry (JSON)
CMD_DEL_CONTENTSERVER_ENTRY = b'\x75'   # Command for Deleting ContentServer Entry (JSON)
CMD_GET_IP_WHITELIST = b'\x80'      # Command for Get IP Whitelist
CMD_GET_IP_BLACKLIST = b'\x81'      # Command for Get IP Blacklist
CMD_ADD_TO_IP_WHITELIST = b'\x82'   # Command to Add IP to Whitelist
CMD_ADD_TO_IP_BLACKLIST = b'\x83'   # Command to Add IP to Blacklist
CMD_DEL_FROM_IP_WHITELIST = b'\x84' # Command to Delete IP from Whitelist
CMD_DEL_FROM_IP_BLACKLIST = b'\x85' # Command to Delete IP from Blacklist
CMD_RESTART_SERVER_THREAD = b'\x90'   # Command to Restart a specific server thread (hot-reload with code changes)
CMD_GET_RESTARTABLE_SERVERS = b'\x91' # Command to Get list of restartable server threads
CMD_RESTART_SERVER_NO_RELOAD = b'\x92' # Command to Restart a server thread without code reload
CMD_GET_DETAILED_BLOB_LIST = b'\x32' # Command for Detailed Blob List
CMD_BLOBMGR_SWAP_BLOB = b'\x62'   # Swap blobs via blob manager
CMD_BLOBMGR_LIST_BLOBS = b'\x63'   # List blob filenames for blob manager
CMD_EDIT_ADMIN_RIGHTS = b'\x34'    # Edit administrator rights
CMD_REMOVE_ADMIN = b'\x35'         # Remove administrator
CMD_LIST_ADMINS = b'\x36'          # List administrators
CMD_CREATE_ADMIN = b'\x37'        # Create administrator
CMD_CHANGE_ADMIN_USERNAME = b'\x38' # Change admin username
CMD_CHANGE_ADMIN_EMAIL = b'\x39'
CMD_CHANGE_ADMIN_PASSWORD = b'\x3A'
CMD_CONTENT_PURGE = b'\x60'       # Purge content version
CMD_GET_SERVER_STATS = b'\x61'    # Get server statistics
# Subscription and guest pass management
CMD_LIST_USER_SUBSCRIPTIONS = b'\x20'
CMD_ADD_SUBSCRIPTION = b'\x21'
CMD_REMOVE_SUBSCRIPTION = b'\x22'
CMD_LIST_GUEST_PASSES = b'\x23'
CMD_ADD_GUEST_PASS = b'\x24'
CMD_REMOVE_GUEST_PASS = b'\x25'
CMD_LIST_AVAILABLE_SUBSCRIPTIONS = b'\x26'  # Command to list all available subscriptions from the blob
CMD_LIST_FTP_USERS = b'\x43'
CMD_ADD_FTP_USER = b'\x44'
CMD_REMOVE_FTP_USER = b'\x45'
# FTP upload review commands
CMD_LIST_PENDING_UPLOADS = b'\x40'
CMD_APPROVE_UPLOAD = b'\x41'
CMD_DENY_UPLOAD = b'\x42'
# Approved applications management commands
CMD_LIST_APPROVED_APPS = b'\x46'
CMD_GET_APPROVED_APP = b'\x47'
CMD_UPDATE_APPROVED_APP = b'\x48'
CMD_APPROVE_WITH_SUBS = b'\x49'
CMD_REPARSE_PENDING = b'\x4A'
CMD_DELETE_APPROVED_APP = b'\x4B'
# Monitoring and configuration commands
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
# Community and advanced management
CMD_CHATROOM_OP = b'\xB0'
CMD_CLAN_OP = b'\xB1'
CMD_GIFT_OP = b'\xB2'
CMD_NEWS_OP = b'\xB3'
CMD_LICENSE_OP = b'\xB4'
CMD_TOKEN_OP = b'\xB5'
CMD_INVENTORY_OP = b'\xB6'
# Command to terminate a user session
CMD_TERMINATE_SESSION = b'\xB7'
# Command to find content servers by AppID
CMD_FIND_CONTENT_SERVERS_BY_APPID = b'\x50'
CMD_INTERACTIVE_CONTENT_SERVER_FINDER = b'\x51'
# Add other command constants here as needed

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

def recv_full_packet(sock: socket.socket):
    """Receive an entire packet from the socket based on protocol framing."""
    header = b""
    while len(header) < 9:
        try:
            chunk = sock.recv(9 - len(header))
        except socket.timeout:
            raise TimeoutError("Timed out waiting for packet header")
        if not chunk:
            return None
        header += chunk
    if header[:4] != HEADER:
        raise ValueError("Invalid header")
    length = struct.unpack('>I', header[5:9])[0]
    body = b""
    remaining = length + 2
    while len(body) < remaining:
        try:
            # Limit chunk size to prevent buffer issues with large packets
            chunk_size = min(remaining - len(body), 65536)  # 64KB max per chunk
            chunk = sock.recv(chunk_size)
        except socket.timeout:
            raise TimeoutError("Timed out waiting for packet body")
        if not chunk:
            return None
        body += chunk
        
        # Log progress for large packets
        if remaining > 100000 and len(body) % 50000 == 0:  # Log every 50KB for large packets
            log.debug(f"Receiving large packet: {len(body)}/{remaining} bytes received")
    return header + body

def recv_and_parse(sock: socket.socket):
    packet = recv_full_packet(sock)
    if packet is None:
        raise ConnectionError("Connection closed while receiving packet")
    return parse_packet(packet)

def _log_outbound_packet(cmd: bytes, payload: bytes, params=None):
    """Internal helper to log outbound packets for instrumentation."""
    caller = inspect.stack()[1].function
    schema = []
    if params:
        for p in params:
            try:
                l = len(p)
            except TypeError:
                l = '?'  # type: ignore
            schema.append(f"{type(p).__name__}:{l}")
    log.info(f"OUTBOUND cmd={cmd.hex()} len={len(payload)} schema={schema} trigger={caller}")

def _log_inbound_packet(cmd: bytes, payload: bytes):
    """Internal helper to log inbound packets for instrumentation."""
    caller = inspect.stack()[1].function
    log.info(f"INBOUND cmd={cmd.hex()} len={len(payload)} handler={caller}")

def derive_key(shared_secret, salt):
    return scrypt(shared_secret, salt, 32, N=2**14, r=8, p=1)

def encrypt_message(key, plaintext):
    cipher = AES.new(key, AES.MODE_CFB)
    ciphertext = cipher.iv + cipher.encrypt(plaintext)
    log.debug(f"Encrypting message. IV: {cipher.iv.hex()}")
    return ciphertext

def decrypt_message(key, ciphertext):
    iv = ciphertext[:16]
    if len(iv) != 16:
        raise ValueError("Invalid IV length for decryption")
    cipher = AES.new(key, AES.MODE_CFB, iv=iv)
    return cipher.decrypt(ciphertext[16:])

def stream_status():
    return "Streaming: In 1024B/s, Out 2048B/s, Connections: 3"

client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_socket.settimeout(SOCKET_TIMEOUT)
symmetric_key = None
authenticated = False
current_blob_info = {}
# This identifier is combined with the literal string ``b"handshake"`` during
# the initial protocol exchange with the administration server.  The server
# expects the handshake payload to be exactly 25 bytes long (16 bytes of client
# identifier plus ``b"handshake"``).  The previous identifier was 18 bytes long
# which resulted in a 27 byte payload and caused the server to reject the
# connection.  Keep the identifier 16 bytes so the total payload length matches
# the server's expectation.
CLIENT_IDENTIFIER = b"AdminClientTool1"

# Heartbeat thread management
_heartbeat_thread = None
_heartbeat_stop_event = threading.Event()
_heartbeat_lock = threading.Lock()  # Protects socket access during heartbeat
HEARTBEAT_INTERVAL = 60  # Send heartbeat every 60 seconds (should be less than server timeout)

# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _socket_connected() -> bool:
    """Return ``True`` if the global ``client_socket`` appears to be connected.

    ``socket`` does not expose an explicit "connected" flag so we attempt to
    fetch the peer name.  If the call succeeds we assume the connection is
    alive.  Any ``OSError`` results in ``False`` which allows callers to
    recreate the connection on demand.
    """
    try:
        client_socket.getpeername()
        return True
    except OSError:
        return False


def get_local_ip() -> str:
    """Return the local IP address of the connected socket.

    This function safely retrieves the local IP from the current global
    ``client_socket``.  If the socket is not connected, it returns a
    fallback value of "0.0.0.0".
    """
    try:
        if _socket_connected():
            return client_socket.getsockname()[0]
    except OSError:
        pass
    return "0.0.0.0"


def ensure_authenticated() -> None:
    """Validate that the module has an active connection and session key.

    Many higher level helpers previously repeated the same boilerplate checks
    for a valid socket and symmetric key.  Centralising the logic here keeps the
    calling code concise and ensures all call sites perform the same
    verification.  A ``ConnectionError`` is raised if the preconditions are not
    met so the GUI layer can surface a friendly error message to the user.
    """
    if symmetric_key is None:
        raise ConnectionError("Symmetric key not established.")
    if not _socket_connected():
        raise ConnectionError("Client socket not connected.")


def _safe_recv() -> Optional[Tuple[bytes, bytes]]:
    """Receive and parse a packet from the server with common error handling.

    Returns a ``(cmd, payload)`` tuple on success or ``None`` if a socket error
    occurs.  The administration server occasionally performs expensive
    operations (for example generating a large blob list). During those periods
    the response may take slightly longer than the default timeout. This helper
    retries the receive once if a timeout occurs and converts all socket related
    errors into ``None`` so callers can decide how to proceed.
    """
    try:
        log.debug("Starting packet receive...")
        result = recv_and_parse(client_socket)
        log.debug("Packet receive completed successfully")
        return result
    except TimeoutError:
        log.warning("Timed out waiting for packet; retrying once...")
        try:
            log.debug("Retrying packet receive...")
            result = recv_and_parse(client_socket)
            log.debug("Retry packet receive completed successfully")
            return result
        except TimeoutError:
            log.error("Timed out waiting for packet on retry.")
            return None
    except Exception as e:
        log.error(f"Failed to receive packet: {e}")
        import traceback
        log.error(f"Traceback: {traceback.format_exc()}")
        return None


def _safe_send(packet: bytes) -> bool:
    """Wrapper around ``sendall`` that logs socket errors uniformly."""
    try:
        client_socket.sendall(packet)
        return True
    except Exception as e:
        log.error(f"Error sending packet to server: {e}")
        return False


def connect_and_login(config: dict, force: bool = False) -> bool:
    """Convenience helper that performs the full connection sequence.

    The previous client code required GUI layers to separately invoke the
    handshake and login routines.  The new helper consolidates these steps and
    optionally reuses an existing authenticated session unless ``force`` is
    specified.  This simplifies the calling pattern for tools such as the blob
    manager which only need a ready-to-use connection.
    """

    if authenticated and not force and _socket_connected():
        return True

    if not perform_handshake_and_authenticate(config, force=force):
        return False

    if not login_to_server(config["adminusername"], config["adminpassword"]):
        return False

    return True

def perform_handshake_and_authenticate(config_dict, force: bool = False):
    global symmetric_key, client_socket
    server_address = (config_dict['adminserverip'], int(config_dict['adminserverport']))

    connected = _socket_connected()

    if symmetric_key is not None and connected and not force:
        log.info("Reusing existing authenticated connection.")
        return True

    if not connected:
        try:
            client_socket.close()
        except Exception:
            pass
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.settimeout(SOCKET_TIMEOUT)
        try:
            client_socket.connect(server_address)
            log.info(f"Connected to {server_address}")
        except Exception as e:
            print(f"Connection to {server_address} failed: {e}")
            return False

    client_salt = os.urandom(16)
    symmetric_key = derive_key(config_dict['peer_password'].encode('utf-8'), client_salt)
    handshake_payload = CLIENT_IDENTIFIER + b"handshake"
    encrypted_handshake = encrypt_message(symmetric_key, handshake_payload)
    packet = build_packet(b'\x01', client_salt + encrypted_handshake)
    _log_outbound_packet(b'\x01', client_salt + encrypted_handshake)
    if not _safe_send(packet):
        return False

    result = _safe_recv()
    if result is None:
        print("Handshake response parse error: timeout")
        return False
    resp_cmd, resp_payload = result
    _log_inbound_packet(resp_cmd, resp_payload)
    try:
        response = decrypt_message(symmetric_key, resp_payload)
    except Exception as e:
        print(f"Handshake decryption error: {e}")
        return False
    if response == b"handshake successful":
        print("Handshake successful with server.")
        return True
    else:
        print("Handshake failed.")
        return False

def send_request_to_server(cmd: bytes, parameters: list, delimiter: str = '|'):
    """Send a structured request to the administration server.

    ``parameters`` are joined using ``delimiter`` before encryption.  Common
    connection validation and retry logic is handled here so callers can simply
    deal with the decrypted response bytes or ``None`` on failure.
    """

    log.debug(f"Sending request to server: cmd={cmd.hex()}")
    ensure_authenticated()

    payload_str = delimiter.join(str(p) for p in parameters)
    payload_bytes = payload_str.encode('latin-1')

    encrypted_payload = encrypt_message(symmetric_key, payload_bytes)
    packet = build_packet(cmd, encrypted_payload)
    _log_outbound_packet(cmd, payload_bytes, parameters)

    # Use lock to prevent conflicts with heartbeat thread
    with _heartbeat_lock:
        log.debug("Sending packet to server...")
        if not _safe_send(packet):
            log.error("Failed to send packet to server")
            return None

        log.debug("Waiting for server response...")
        result = _safe_recv()
    if result is None:
        log.error("No response received from server")
        return None
    resp_cmd, resp_payload = result

    log.debug(f"Received response: cmd={resp_cmd.hex()}, payload_size={len(resp_payload)}")
    _log_inbound_packet(resp_cmd, resp_payload)
    if resp_cmd == b"\xEE":
        decrypted_error = decrypt_message(symmetric_key, resp_payload).decode("latin-1", errors='replace')
        raise RuntimeError(f"Server error: {decrypted_error}")

    log.debug("Decrypting response payload...")
    decrypted_response = decrypt_message(symmetric_key, resp_payload)
    log.debug(f"Decrypted response size: {len(decrypted_response)} bytes")
    return decrypted_response
    

def send_raw_request_to_server(cmd: bytes, raw_payload_bytes: bytes):
    """Send an already serialised payload to the server.

    Used by components that operate directly on binary blob data.  The helper
    mirrors :func:`send_request_to_server` but skips parameter serialisation.
    """

    ensure_authenticated()

    encrypted_payload = encrypt_message(symmetric_key, raw_payload_bytes)
    packet = build_packet(cmd, encrypted_payload)
    _log_outbound_packet(cmd, raw_payload_bytes)

    # Use lock to prevent conflicts with heartbeat thread
    with _heartbeat_lock:
        if not _safe_send(packet):
            return None

        result = _safe_recv()
    if result is None:
        return None
    resp_cmd, resp_payload = result

    _log_inbound_packet(resp_cmd, resp_payload)
    if resp_cmd == b"\xEE":
        decrypted_error = decrypt_message(symmetric_key, resp_payload).decode("latin-1", errors='replace')
        raise RuntimeError(f"Server error: {decrypted_error}")
    try:
        return decrypt_message(symmetric_key, resp_payload)
    except Exception as e:
        log.error(f"Error decrypting response for CMD {cmd.hex()}: {e}")
        return None

# ---------------------------------------------------------------------------
# Heartbeat functionality for session keep-alive
# ---------------------------------------------------------------------------

def _send_heartbeat_internal() -> bool:
    """Send a heartbeat packet to the server (internal, no locking)."""
    global symmetric_key
    if symmetric_key is None:
        return False
    try:
        packet = build_packet(CMD_HEARTBEAT, encrypt_message(symmetric_key, b""))
        client_socket.sendall(packet)
        # Wait for response
        result = recv_and_parse(client_socket)
        if result is None:
            log.warning("Heartbeat: No response from server")
            return False
        cmd, payload = result
        if cmd == b"\x00":
            log.debug("Heartbeat successful")
            return True
        elif cmd == b"\xEE":
            decrypted_error = decrypt_message(symmetric_key, payload).decode('latin-1', errors='replace')
            log.warning(f"Heartbeat error: {decrypted_error}")
            return False
        else:
            log.warning(f"Heartbeat: Unexpected response CMD {cmd.hex()}")
            return False
    except Exception as e:
        log.error(f"Heartbeat failed: {e}")
        return False

def _heartbeat_loop():
    """Background thread that sends heartbeats at regular intervals."""
    global _heartbeat_stop_event
    log.info("Heartbeat thread started")
    while not _heartbeat_stop_event.is_set():
        # Wait for the interval or until stop is signaled
        if _heartbeat_stop_event.wait(timeout=HEARTBEAT_INTERVAL):
            break  # Stop was signaled

        if not authenticated:
            log.debug("Heartbeat: Not authenticated, skipping")
            continue

        with _heartbeat_lock:
            if not _socket_connected():
                log.warning("Heartbeat: Socket not connected, stopping heartbeat thread")
                break
            _send_heartbeat_internal()

    log.info("Heartbeat thread stopped")

def start_heartbeat_thread():
    """Start the heartbeat background thread."""
    global _heartbeat_thread, _heartbeat_stop_event

    # Stop any existing thread first
    stop_heartbeat_thread()

    _heartbeat_stop_event.clear()
    _heartbeat_thread = threading.Thread(target=_heartbeat_loop, daemon=True, name="HeartbeatThread")
    _heartbeat_thread.start()
    log.info("Heartbeat thread started")

def stop_heartbeat_thread():
    """Stop the heartbeat background thread."""
    global _heartbeat_thread, _heartbeat_stop_event

    if _heartbeat_thread is not None and _heartbeat_thread.is_alive():
        log.info("Stopping heartbeat thread...")
        _heartbeat_stop_event.set()
        _heartbeat_thread.join(timeout=5.0)
        if _heartbeat_thread.is_alive():
            log.warning("Heartbeat thread did not stop gracefully")
        else:
            log.info("Heartbeat thread stopped")
    _heartbeat_thread = None

def send_heartbeat() -> bool:
    """Manually send a heartbeat (thread-safe)."""
    with _heartbeat_lock:
        return _send_heartbeat_internal()

# ---------------------------------------------------------------------------
# Login and logout functions
# ---------------------------------------------------------------------------

def login_to_server(username: str, password: str) -> bool:
    global symmetric_key, client_socket, authenticated
    blob = username.encode("latin-1") + b"\x00" + password.encode("latin-1")
    if symmetric_key is None: print("Login Error: No session key."); return False
    pkt  = build_packet(b"\x02", encrypt_message(symmetric_key, blob))
    _log_outbound_packet(b"\x02", blob, [username, password])
    with _heartbeat_lock:
        client_socket.sendall(pkt)
    try:
        cmd, payload = recv_and_parse(client_socket)
        _log_inbound_packet(cmd, payload)
        if cmd == b"\xEE":
            decrypted_error = decrypt_message(symmetric_key, payload).decode('latin-1', errors='replace')
            log.error(f"Server error for login: {decrypted_error}"); print(f"Login failed: {decrypted_error}")
            authenticated = False
            return False
        elif cmd != b"\x00":
            log.error(f"Login failed: Unexpected CMD {cmd.hex()}"); print("Login failed: Unexpected response.")
            authenticated = False
            return False
        authenticated = True
        return True
    except TimeoutError:
        log.error("Login request timed out."); print("Login request timed out.")
        authenticated = False
        return False
    except Exception as e:
        log.error(f"Login response processing error: {e}"); print(f"Login error: {e}")
        authenticated = False
        return False

def logout_from_server():
    """Send a logoff command to the administration server."""
    global symmetric_key, client_socket, authenticated

    # Stop heartbeat thread before logout
    stop_heartbeat_thread()

    if symmetric_key is None:
        log.error("Logout Error: No session key established.")
        return False
    try:
        with _heartbeat_lock:
            packet = build_packet(CMD_LOGOFF, encrypt_message(symmetric_key, b""))
            _log_outbound_packet(CMD_LOGOFF, b"")
            if not _safe_send(packet):
                return False
            result = _safe_recv()
        if result is None:
            return False
        cmd, payload = result
        _log_inbound_packet(cmd, payload)
        if cmd == b"\x00":
            authenticated = False
            return True
        elif cmd == b"\xEE":
            decrypted_error = decrypt_message(symmetric_key, payload).decode("latin-1", errors="replace")
            log.error(f"Logout failed: {decrypted_error}")
        else:
            log.error(f"Unexpected logout response CMD {cmd.hex()}")
    except Exception as e:
        log.error(f"Logout request error: {e}")
    authenticated = False
    return False
def request_ip_list(command_code: bytes):
    log.info(f"Requesting IP list with command {command_code.hex()}.")
    try:
        response_payload_bytes = send_request_to_server(command_code, [])
        if response_payload_bytes is None:
            log.error(f"Failed to get IP list ({command_code.hex()}): No response payload.")
            return None
        try:
            json_string = response_payload_bytes.decode('utf-8')
            ip_list = json.loads(json_string)
            if not isinstance(ip_list, list):
                log.error(f"IP list response is not a list: {type(ip_list)}")
                return None
            log.info(f"Successfully received IP list ({command_code.hex()}): {len(ip_list)} IPs.")
            return ip_list
        except UnicodeDecodeError as ude:
            log.error(f"Failed to decode UTF-8 response for IP list ({command_code.hex()}): {ude}")
            return None
        except json.JSONDecodeError as jde:
            log.error(f"Failed to parse JSON for IP list ({command_code.hex()}): {jde}")
            return None
    except ConnectionError as ce:
        log.error(f"Connection error requesting IP list ({command_code.hex()}): {ce}")
        return None
    except RuntimeError as re: 
        log.error(f"Server error requesting IP list ({command_code.hex()}): {re}")
        return None
    except Exception as e:
        log.error(f"Unexpected error requesting IP list ({command_code.hex()}): {e}")
        return None

def request_add_ip_to_list(command_code: bytes, ip_address: str) :
    log.info(f"Requesting to add IP {ip_address} using command {command_code.hex()}.")
    if not ip_address: 
        log.error("IP address cannot be empty."); print("Error: IP address cannot be empty.")
        return "Error: IP address cannot be empty." 
    if symmetric_key is None:
        log.error("Cannot add IP to list: No session key."); print("Error: Not connected.")
        return None
    try:
        payload_dict = {"ip_address": ip_address}
        json_payload_bytes = json.dumps(payload_dict).encode('utf-8')
        response_payload_bytes = send_raw_request_to_server(command_code, json_payload_bytes)
        if response_payload_bytes is None:
            log.error(f"Failed to add IP {ip_address} to list ({command_code.hex()}): No response payload.")
            return None 
        try:
            response_message = response_payload_bytes.decode('latin-1')
            log.info(f"Response for add IP to list ({command_code.hex()}): {response_message}")
            return response_message
        except UnicodeDecodeError as ude:
            log.error(f"Failed to decode latin-1 response for add IP to list ({command_code.hex()}): {ude}")
            return "Error: Malformed server response."
    except ConnectionError as ce: log.error(f"Connection error: {ce}"); return None
    except RuntimeError as re: log.error(f"Server error: {re}"); return f"Server error: {re}" 
    except Exception as e: log.error(f"Unexpected error: {e}"); return None

def request_del_ip_from_list(command_code: bytes, ip_address: str) :
    log.info(f"Requesting to delete IP {ip_address} using command {command_code.hex()}.")
    if not ip_address:
        log.error("IP address cannot be empty for deletion."); print("Error: IP address cannot be empty.")
        return "Error: IP address cannot be empty."
    if symmetric_key is None:
        log.error("Cannot delete IP from list: No session key."); print("Error: Not connected.")
        return None
    try:
        payload_dict = {"ip_address": ip_address}
        json_payload_bytes = json.dumps(payload_dict).encode('utf-8')
        response_payload_bytes = send_raw_request_to_server(command_code, json_payload_bytes)
        if response_payload_bytes is None:
            log.error(f"Failed to delete IP {ip_address} from list ({command_code.hex()}): No response payload.")
            return None
        try:
            response_message = response_payload_bytes.decode('latin-1')
            log.info(f"Response for delete IP from list ({command_code.hex()}): {response_message}")
            return response_message
        except UnicodeDecodeError as ude:
            log.error(f"Failed to decode latin-1 response for delete IP from list ({command_code.hex()}): {ude}")
            return "Error: Malformed server response."
    except ConnectionError as ce: log.error(f"Connection error: {ce}"); return None
    except RuntimeError as re: log.error(f"Server error: {re}"); return f"Server error: {re}"
    except Exception as e: log.error(f"Unexpected error: {e}"); return None

def request_restartable_servers_list(raw=False):
    """
    Requests the list of restartable server thread identifiers from the server.

    Args:
        raw: If True, returns the full list of server info dicts.
             If False (default), returns just a list of identifier strings for backward compatibility.

    Returns:
        If raw=False: list of server identifier strings, or None on error.
        If raw=True: list of dicts with keys: identifier, class, port, is_alive, module
    """
    log.info(f"Requesting restartable server list with command {CMD_GET_RESTARTABLE_SERVERS.hex()}.")
    try:
        response_payload_bytes = send_request_to_server(CMD_GET_RESTARTABLE_SERVERS, [])
        if response_payload_bytes is None:
            log.error("Failed to get restartable server list: No response payload.")
            return None
        try:
            json_string = response_payload_bytes.decode('utf-8')
            server_list = json.loads(json_string)
            if not isinstance(server_list, list):
                log.error(f"Restartable server list response is not a list: {type(server_list)}")
                return None
            log.info(f"Successfully received restartable server list: {len(server_list)} servers.")

            if raw:
                # Return full server info dicts
                return server_list
            else:
                # Extract just identifiers for backward compatibility
                # Handle both old format (list of strings) and new format (list of dicts)
                identifiers = []
                for item in server_list:
                    if isinstance(item, str):
                        identifiers.append(item)
                    elif isinstance(item, dict) and 'identifier' in item:
                        identifiers.append(item['identifier'])
                return identifiers

        except UnicodeDecodeError as ude:
            log.error(f"Failed to decode UTF-8 response for restartable server list: {ude}")
            return None
        except json.JSONDecodeError as jde:
            log.error(f"Failed to parse JSON for restartable server list: {jde}")
            return None
    except ConnectionError as ce: log.error(f"Connection error: {ce}"); return None
    except RuntimeError as re: log.error(f"Server error: {re}"); return None
    except Exception as e: log.error(f"Unexpected error: {e}"); return None

def request_restart_server_thread(identifier: str, reload_code: bool = True):
    """
    Requests the server to restart a specific server thread.

    Args:
        identifier: The string identifier of the server thread.
        reload_code: If True (default), hot-reload the Python module from disk.
                    If False, just restart without reloading code.

    Returns:
        The server's response message string or None on error.
    """
    cmd = CMD_RESTART_SERVER_THREAD if reload_code else CMD_RESTART_SERVER_NO_RELOAD
    action = "hot-reload" if reload_code else "restart"
    log.info(f"Requesting to {action} server thread '{identifier}' using CMD {cmd.hex()}.")

    if not identifier:
        log.error("Server identifier cannot be empty."); print("Error: Server identifier cannot be empty.")
        return "Error: Server identifier cannot be empty."
    if symmetric_key is None:
        log.error(f"Cannot {action} server thread: No session key."); print("Error: Not connected.")
        return None
    try:
        payload_dict = {"server_identifier": identifier}
        json_payload_bytes = json.dumps(payload_dict).encode('utf-8')
        response_payload_bytes = send_raw_request_to_server(cmd, json_payload_bytes)
        if response_payload_bytes is None:
            log.error(f"Failed to {action} server thread '{identifier}': No response payload.")
            return None
        try:
            response_message = response_payload_bytes.decode('latin-1')
            log.info(f"Response for {action} server thread '{identifier}': {response_message}")
            return response_message
        except UnicodeDecodeError as ude:
            log.error(f"Failed to decode latin-1 response for {action} server thread: {ude}")
            return "Error: Malformed server response."
    except ConnectionError as ce: log.error(f"Connection error: {ce}"); return None
    except RuntimeError as re: log.error(f"Server error: {re}"); return f"Server error: {re}"
    except Exception as e: log.error(f"Unexpected error: {e}"); return None


def request_restart_server_no_reload(identifier: str):
    """
    Convenience function to restart a server thread without reloading code.
    Equivalent to request_restart_server_thread(identifier, reload_code=False).
    """
    return request_restart_server_thread(identifier, reload_code=False)


# Functions that were already present, ensure they use the updated request functions if necessary
def request_blob_list():
    response_payload = send_request_to_server(CMD_LIST_BLOBS, [])
    if response_payload is None:
        return None
    decoded = response_payload.decode('latin-1')
    blobs = []
    for entry in decoded.split('|'):
        if not entry:
            continue
        parts = entry.split(',', 1)
        blob_id = parts[0]
        name = parts[1] if len(parts) > 1 else parts[0]
        blobs.append({"id": blob_id, "name": name})
    return blobs

def request_blob_swap(blob_id: str) :
    response_payload = send_request_to_server(CMD_SWAP_BLOB, [blob_id])
    return response_payload.decode('latin-1') if response_payload else None

def request_blobmgr_swap(blob_filename: str, blob_type: str = None) :
    """Request the server to swap blobs based on filename and type."""
    if not blob_filename:
        return None
    
    # Auto-detect blob type if not provided (backward compatibility)
    if blob_type is None:
        if blob_filename.startswith('secondblob.bin.') or blob_filename.startswith('firstblob.bin.'):
            blob_type = 'DB'
        else:
            blob_type = 'File'
    
    # Send JSON payload with filename and type
    payload_data = {
        'filename': blob_filename,
        'type': blob_type
    }
    
    json_payload = json.dumps(payload_data)
    response_payload = send_raw_request_to_server(CMD_BLOBMGR_SWAP_BLOB, json_payload.encode('utf-8'))
    return response_payload.decode('utf-8') if response_payload else None

def request_blobmgr_file_list(blob_type='DB'):
    """Request blob list from server - handles compressed responses with 30000+ blobs.

    Args:
        blob_type: 'DB' for database blobs, 'File' for file-based blobs.
    """
    log.info(f"Requesting blob list from server (type={blob_type})...")

    try:
        # Send request to server with blob type as JSON payload
        payload_data = {'type': blob_type}
        json_payload = json.dumps(payload_data)
        response_payload = send_raw_request_to_server(CMD_BLOBMGR_LIST_BLOBS, json_payload.encode('utf-8'))
        if response_payload is None:
            log.error("No response received from server")
            return None
        
        log.info(f"Received response: {len(response_payload)} bytes ({len(response_payload)/1024/1024:.2f} MB)")
        
        # Try to decompress the response first (server now sends compressed data)
        decompressed_data = None
        try:
            import gzip
            decompressed_data = gzip.decompress(response_payload)
            log.info(f"Decompressed {len(response_payload)} bytes to {len(decompressed_data)} bytes ({len(decompressed_data)/1024/1024:.2f} MB)")
        except Exception as decomp_error:
            log.warning(f"Failed to decompress response, trying as uncompressed: {decomp_error}")
            # If decompression fails, use original data (backward compatibility)
            decompressed_data = response_payload
        
        # Decode UTF-8
        try:
            json_string = decompressed_data.decode('utf-8')
        except UnicodeDecodeError as e:
            log.error(f"Failed to decode response as UTF-8: {e}")
            return None
        
        log.info(f"Decoded JSON string: {len(json_string)} characters")
        
        # Parse JSON
        try:
            data = json.loads(json_string)
        except json.JSONDecodeError as e:
            log.error(f"Failed to parse JSON: {e}")
            # Only log first 500 characters to avoid flooding logs
            log.error(f"JSON content sample: {json_string[:500]}...")
            return None
        
        # Validate response structure
        if not isinstance(data, dict) or 'blobs' not in data:
            log.error(f"Invalid response format: {type(data)}")
            return None
        
        blobs = data['blobs']
        if not isinstance(blobs, list):
            log.error(f"Blobs field is not a list: {type(blobs)}")
            return None
        
        log.info(f"Successfully received {len(blobs)} blobs from server")
        
        # Log some statistics about the blob data
        if len(blobs) > 0:
            sample_blob = blobs[0]
            log.info(f"Sample blob: {sample_blob}")
            
            # Count different blob types
            type_counts = {}
            for blob in blobs:
                blob_type = blob.get('type', 'Unknown')
                type_counts[blob_type] = type_counts.get(blob_type, 0) + 1
            log.info(f"Blob types: {type_counts}")
        
        return data
        
    except Exception as e:
        log.error(f"Unexpected error in request_blobmgr_file_list: {e}")
        import traceback
        log.error(f"Traceback: {traceback.format_exc()}")
        return None

def request_edit_admin_rights(username: str, rights: str):
    response_payload = send_request_to_server(CMD_EDIT_ADMIN_RIGHTS, [username, rights])
    return response_payload.decode('latin-1') if response_payload else None

def request_remove_admin(username: str):
    response_payload = send_request_to_server(CMD_REMOVE_ADMIN, [username])
    return response_payload.decode('latin-1') if response_payload else None

def request_list_admins():
    response_payload = send_request_to_server(CMD_LIST_ADMINS, [])
    if response_payload is None:
        return None
    try:
        return json.loads(response_payload.decode('utf-8'))
    except Exception:
        return None

def request_create_admin(username: str, password: str, rights: str):
    payload = [username, password, rights]
    response_payload = send_request_to_server(CMD_CREATE_ADMIN, payload)
    return response_payload.decode('latin-1') if response_payload else None

def request_change_admin_username(old_username: str, new_username: str):
    payload = [old_username, new_username]
    response_payload = send_request_to_server(CMD_CHANGE_ADMIN_USERNAME, payload)
    return response_payload.decode('latin-1') if response_payload else None

def request_change_admin_email(username: str, new_email: str):
    payload = [username, new_email]
    response_payload = send_request_to_server(CMD_CHANGE_ADMIN_EMAIL, payload)
    return response_payload.decode('latin-1') if response_payload else None

def request_change_admin_password(username: str, new_password: str):
    payload = [username, new_password]
    response_payload = send_request_to_server(CMD_CHANGE_ADMIN_PASSWORD, payload)
    return response_payload.decode('latin-1') if response_payload else None

def request_list_user_subscriptions(user_id: int):
    payload = [user_id]
    resp = send_request_to_server(CMD_LIST_USER_SUBSCRIPTIONS, payload)
    return resp.decode('latin-1') if resp else None

def request_add_subscription(user_id: int, sub_id: str):
    payload = [user_id, sub_id]
    resp = send_request_to_server(CMD_ADD_SUBSCRIPTION, payload)
    return resp.decode('latin-1').rstrip('\x00') if resp else None

def request_remove_subscription(user_id: int, sub_id: str):
    payload = [user_id, sub_id]
    resp = send_request_to_server(CMD_REMOVE_SUBSCRIPTION, payload)
    return resp.decode('latin-1').rstrip('\x00') if resp else None

def request_list_available_subscriptions():
    """Request the list of all available subscriptions from the currently loaded blob.
    
    Returns:
        str: Response payload decoded as latin-1, or None if request failed.
    """
    log.info(f"Requesting available subscriptions list with command {CMD_LIST_AVAILABLE_SUBSCRIPTIONS.hex()}.")
    try:
        response_payload = send_request_to_server(CMD_LIST_AVAILABLE_SUBSCRIPTIONS, [])
        if response_payload is None:
            log.error("Failed to get available subscriptions list: No response payload.")
            return None
        
        return response_payload.decode('latin-1')
    except ConnectionError as ce:
        log.error(f"Connection error requesting available subscriptions: {ce}")
        return None
    except RuntimeError as re:
        log.error(f"Server error requesting available subscriptions: {re}")
        return None
    except Exception as e:
        log.error(f"Unexpected error requesting available subscriptions: {e}")
        return None

def request_list_guest_passes(user_id: int):
    payload = [user_id]
    resp = send_request_to_server(CMD_LIST_GUEST_PASSES, payload)
    return resp.decode('latin-1') if resp else None

def request_add_guest_pass(user_id: int, pass_id: str):
    payload = [user_id, pass_id]
    resp = send_request_to_server(CMD_ADD_GUEST_PASS, payload)
    return resp.decode('latin-1') if resp else None

def request_remove_guest_pass(user_id: int, pass_id: str):
    payload = [user_id, pass_id]
    resp = send_request_to_server(CMD_REMOVE_GUEST_PASS, payload)
    return resp.decode('latin-1') if resp else None

def request_list_ftp_users():
    resp = send_request_to_server(CMD_LIST_FTP_USERS, [])
    return resp.decode('latin-1') if resp else None

def request_add_ftp_user(username: str, password: str, perm: str):
    payload = [username, password, perm]
    resp = send_request_to_server(CMD_ADD_FTP_USER, payload)
    return resp.decode('latin-1') if resp else None

def request_remove_ftp_user(username: str):
    resp = send_request_to_server(CMD_REMOVE_FTP_USER, [username])
    return resp.decode('latin-1') if resp else None

def request_pending_ftp_uploads():
    resp = send_request_to_server(CMD_LIST_PENDING_UPLOADS, [])
    return resp.decode('latin-1') if resp else None

def request_approve_ftp_upload(appid: str, admin_user: str, admin_ip: str = "0.0.0.0"):
    payload = [appid, admin_user, admin_ip]
    resp = send_request_to_server(CMD_APPROVE_UPLOAD, payload)
    return resp.decode('latin-1') if resp else None

def request_deny_ftp_upload(appid: str, admin_user: str, admin_ip: str = "0.0.0.0"):
    payload = [appid, admin_user, admin_ip]
    resp = send_request_to_server(CMD_DENY_UPLOAD, payload)
    return resp.decode('latin-1') if resp else None

# Approved applications management functions
def request_list_approved_apps():
    """Get list of all approved applications."""
    resp = send_request_to_server(CMD_LIST_APPROVED_APPS, [])
    return resp.decode('latin-1') if resp else None

def request_get_approved_app(appid: str):
    """Get details of a specific approved application."""
    resp = send_request_to_server(CMD_GET_APPROVED_APP, [appid])
    if resp:
        try:
            return json.loads(resp.decode('utf-8'))
        except:
            return resp.decode('latin-1')
    return None

def request_update_approved_app(appid: str, app_names: str = None, subscriptions: str = None, admin_user: str = "unknown"):
    """Update an approved application's name and/or subscriptions."""
    payload = {
        'appid': appid,
        'admin_user': admin_user
    }
    if app_names is not None:
        payload['app_names'] = app_names
    if subscriptions is not None:
        payload['subscriptions'] = subscriptions
    resp = send_raw_request_to_server(CMD_UPDATE_APPROVED_APP, json.dumps(payload).encode('utf-8'))
    return resp.decode('latin-1') if resp else None

def request_approve_with_subscriptions(appid: str, subscriptions: str, admin_user: str, admin_ip: str = "0.0.0.0"):
    """Approve a pending upload with modified subscriptions."""
    payload = {
        'appid': appid,
        'subscriptions': subscriptions,
        'admin_user': admin_user,
        'admin_ip': admin_ip
    }
    resp = send_raw_request_to_server(CMD_APPROVE_WITH_SUBS, json.dumps(payload).encode('utf-8'))
    return resp.decode('latin-1') if resp else None

def request_reparse_pending(appid: str):
    """Re-parse metadata from XML for a pending upload."""
    payload = {'appid': appid}
    resp = send_raw_request_to_server(CMD_REPARSE_PENDING, json.dumps(payload).encode('utf-8'))
    return resp.decode('latin-1') if resp else None

def request_delete_approved_app(appid: str, admin_user: str = "unknown", admin_ip: str = "0.0.0.0"):
    """Delete an approved application and its associated files.

    Removes the XML file from mod_blob, DAT/BLOB files from steam2_sdk_depots,
    and the database entry.
    """
    payload = f"{appid}|{admin_user}|{admin_ip}"
    resp = send_raw_request_to_server(CMD_DELETE_APPROVED_APP, payload.encode('latin-1'))
    return resp.decode('latin-1') if resp else None

def request_content_purge(appid: int, version: int):
    payload = json.dumps({'appid': appid, 'version': version}).encode('utf-8')
    response_payload = send_raw_request_to_server(CMD_CONTENT_PURGE, payload)
    return response_payload.decode('latin-1') if response_payload else None

def request_find_content_servers_by_appid(appid: int, version: int):
    """Request list of content servers serving a specific appid/version."""
    payload = struct.pack('>II', appid, version)
    response_payload = send_raw_request_to_server(CMD_FIND_CONTENT_SERVERS_BY_APPID, payload)
    return response_payload

def request_interactive_content_server_finder():
    """Request all AppIDs and versions from content servers for interactive selection."""
    response_payload = send_request_to_server(CMD_INTERACTIVE_CONTENT_SERVER_FINDER, [])
    if response_payload is None:
        return None
    try:
        return json.loads(response_payload.decode('utf-8'))
    except Exception:
        return None

def request_server_statistics():
    response_payload = send_request_to_server(CMD_GET_SERVER_STATS, [])
    if response_payload is None:
        return None
    try:
        return json.loads(response_payload.decode('utf-8'))
    except Exception:
        return None

def request_server_list(command_code: bytes):
    return send_request_to_server(command_code, [])

def request_full_dirserver_json() :
    response_payload = send_request_to_server(CMD_GET_FULL_DIRSERVER_LIST, [])
    return response_payload.decode('utf-8') if response_payload else None

def request_add_dirserver_entry(server_details_json_bytes: bytes) :
    response_payload = send_raw_request_to_server(CMD_ADD_DIRSERVER_ENTRY, server_details_json_bytes)
    return response_payload.decode('latin-1') if response_payload else None

def request_del_dirserver_entry(server_identifier_json_bytes: bytes) :
    response_payload = send_raw_request_to_server(CMD_DEL_DIRSERVER_ENTRY, server_identifier_json_bytes)
    return response_payload.decode('latin-1') if response_payload else None

def request_full_contentserver_json() :
    response_payload = send_request_to_server(CMD_GET_FULL_CONTENTSERVER_LIST, [])
    return response_payload.decode('utf-8') if response_payload else None

def request_add_contentserver_entry(server_details_json_bytes: bytes) :
    response_payload = send_raw_request_to_server(CMD_ADD_CONTENTSERVER_ENTRY, server_details_json_bytes)
    return response_payload.decode('latin-1') if response_payload else None

def request_del_contentserver_entry(server_id_json_bytes: bytes) :
    response_payload = send_raw_request_to_server(CMD_DEL_CONTENTSERVER_ENTRY, server_id_json_bytes)
    return response_payload.decode('latin-1') if response_payload else None

def request_detailed_blob_list() :
    """
    Requests the detailed list of available blobs from the server.
    Returns a list of dictionaries, where each dictionary contains details of a blob,
    or None if an error occurs.
    """
    log.info(f"Requesting detailed blob list with command {CMD_GET_DETAILED_BLOB_LIST.hex()}.")
    try:
        # No parameters are needed for this command, so an empty list is passed.
        # send_request_to_server handles encoding an empty string for the payload.
        response_payload_bytes = send_request_to_server(CMD_GET_DETAILED_BLOB_LIST, [])
        
        if response_payload_bytes is None:
            log.error("Failed to get detailed blob list: No response payload received.")
            return None
        
        try:
            # DISABLED: Decompress the data first (compression disabled on server)
            # Server now sends uncompressed JSON directly
            log.debug("Processing uncompressed response (compression disabled)")
            json_string = response_payload_bytes.decode('utf-8')
            
            # OLD CODE (disabled):
            # import gzip
            # try:
            #     decompressed_data = gzip.decompress(response_payload_bytes)
            #     log.debug(f"Decompressed blob list: {len(response_payload_bytes)} -> {len(decompressed_data)} bytes")
            # except gzip.BadGzipFile:
            #     # Fallback for uncompressed data (backward compatibility)
            #     log.debug("Response not compressed, using as-is")
            #     decompressed_data = response_payload_bytes
            # 
            # json_string = decompressed_data.decode('utf-8')
            response_data = json.loads(json_string)
            
            # Handle new response format with separate file/db blobs and current blob info
            if isinstance(response_data, dict) and 'file_blobs' in response_data and 'db_blobs' in response_data:
                # New format: combine file and DB blobs into a single list
                file_blobs = response_data.get('file_blobs', [])
                db_blobs = response_data.get('db_blobs', [])
                current_blob = response_data.get('current_blob', {})
                
                detailed_blobs = file_blobs + db_blobs
                
                # Store current blob info for display
                global current_blob_info
                current_blob_info = current_blob
                
                log.info(f"Successfully received detailed blob list: {len(file_blobs)} file blobs, {len(db_blobs)} DB blobs")
                return detailed_blobs
            elif isinstance(response_data, list):
                # Legacy format: direct list of blobs
                log.info(f"Successfully received and parsed detailed blob list: {len(response_data)} blobs.")
                return response_data
            else:
                log.error(f"Detailed blob list response has unexpected format: {type(response_data)}")
                return None
        except UnicodeDecodeError as ude:
            log.error(f"Failed to decode UTF-8 response for detailed blob list: {ude}")
            print(f"Error: Malformed server response (UTF-8 decode failed).")
            return None
        except json.JSONDecodeError as jde:
            log.error(f"Failed to parse JSON for detailed blob list: {jde}")
            print(f"Error: Malformed server response (JSON parse failed).")
            return None
        except Exception as e:
            log.error(f"Failed to decompress detailed blob list: {e}")
            print(f"Error: Failed to decompress server response.")
            return None
            
    except ConnectionError as ce:
        # This exception is raised by send_request_to_server if symmetric_key is None or socket is invalid
        log.error(f"Connection error requesting detailed blob list: {ce}")
        print(f"Error: Not connected or connection issue.") # User-friendly message
        return None
    except RuntimeError as re: 
        # This exception is raised by send_request_to_server if server sends an error packet (CMD_ERROR)
        log.error(f"Server error requesting detailed blob list: {re}")
        print(f"{re}") # Server error message is already formatted
        return None
    except Exception as e:
        # Catch any other unexpected errors during the request.
        log.error(f"Unexpected error requesting detailed blob list: {e}")
        print(f"An unexpected error occurred.")
        return None

def request_live_log():
    resp = send_request_to_server(CMD_GET_LIVE_LOG, [])
    return resp.decode('latin-1') if resp else None

def request_auth_stats():
    resp = send_request_to_server(CMD_GET_AUTH_STATS, [])
    return resp.decode('latin-1') if resp else None

def request_set_rate_limit(limit_kbps: int):
    resp = send_request_to_server(CMD_SET_RATE_LIMIT, [limit_kbps])
    return resp.decode('latin-1') if resp else None

def request_bandwidth_usage():
    resp = send_request_to_server(CMD_GET_BW_STATS, [])
    return resp.decode('latin-1') if resp else None

def request_connection_count():
    resp = send_request_to_server(CMD_GET_CONN_COUNT, [])
    return resp.decode('latin-1') if resp else None

def request_edit_configuration(key: str, value: str):
    resp = send_request_to_server(CMD_EDIT_CONFIG, [key, value])
    return resp.decode('latin-1') if resp else None

def request_toggle_feature(name: str, state: bool):
    resp = send_request_to_server(CMD_TOGGLE_FEATURE, [name, int(state)])
    return resp.decode('latin-1') if resp else None

def request_user_session_report():
    resp = send_request_to_server(CMD_GET_SESSION_REPORT, [])
    return resp.decode('latin-1') if resp else None

def request_terminate_session(ip: str, port: int):
    resp = send_request_to_server(CMD_TERMINATE_SESSION, [ip, port])
    return resp.decode('latin-1') if resp else None

def request_set_ftp_quota(username: str, quota_mb: int, limit_kbps: int):
    resp = send_request_to_server(CMD_SET_FTP_QUOTA, [username, quota_mb, limit_kbps])
    return resp.decode('latin-1') if resp else None

def request_hot_reload_config():
    resp = send_request_to_server(CMD_HOT_RELOAD_CONFIG, [])
    return resp.decode('latin-1') if resp else None

def request_chatroom_op(payload: dict):
    resp = send_request_to_server(CMD_CHATROOM_OP, [json.dumps(payload)])
    return resp.decode('latin-1') if resp else None

def request_clan_op(payload: dict):
    resp = send_request_to_server(CMD_CLAN_OP, [json.dumps(payload)])
    return resp.decode('latin-1') if resp else None

def request_gift_op(payload: dict):
    resp = send_request_to_server(CMD_GIFT_OP, [json.dumps(payload)])
    return resp.decode('latin-1') if resp else None

def request_news_op(payload: dict):
    resp = send_request_to_server(CMD_NEWS_OP, [json.dumps(payload)])
    return resp.decode('latin-1') if resp else None

def request_license_op(payload: dict):
    resp = send_request_to_server(CMD_LICENSE_OP, [json.dumps(payload)])
    return resp.decode('latin-1') if resp else None

def request_token_op(payload: dict):
    resp = send_request_to_server(CMD_TOKEN_OP, [json.dumps(payload)])
    return resp.decode('latin-1') if resp else None

def request_inventory_op(payload: dict):
    resp = send_request_to_server(CMD_INVENTORY_OP, [json.dumps(payload)])
    return resp.decode('latin-1') if resp else None
