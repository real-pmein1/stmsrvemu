"""
Steam3 (SteamPipe) content server - "content3".

Serves depot manifests and depot chunks over HTTP the way Valve's content
servers do, from the .csm/.csd chunk stores and manifests indexed by
utilities.steam3_content.

Routes (mirrors tinserver's Content3ServerWebApp) :

    GET  /depot/<depotid>/manifest/<gid>/<version>   depot manifest
    GET  /depot/<depotid>/chunk/<sha1>               depot chunk
    GET  /serverlist/<cellid>/<maxresults>/          content server list
    GET  /server-status                              server identity and load
    POST /initsession/                               open a CS session   (deprecated auth)
    POST /authdepot/                                 authorise a depot   (deprecated auth)

Two client generations are supported :

    the deprecated CS flow, where the client opens a session with an RSA
    encrypted session key, authorises each depot with an app ownership ticket
    obtained from the CM, and signs every request with an x-steam-auth header

    the current CDN / SteamCache flow, where the client passes a CDN auth token
    (obtained from the CM over EMsgClientGetCDNAuthToken) as a query string

Both are accepted at the same time by default, so old and new clients can be
served by one instance.
"""

import http.server
import logging
import os
import re
import socket
import socketserver
import struct
import threading
import time
import urllib.parse
from datetime import datetime, timezone
from hashlib import sha1

import globalvars
from utilities import encryption
from utilities.steam3_content import get_repository
from utilities.steam3_manifest import MANIFEST_VERSION_DEPRECATED, MANIFEST_VERSION_PROTO

# Content3ServerType
CONTENT3_TYPE_CDN = "CDN"
CONTENT3_TYPE_CS = "CS"
CONTENT3_TYPE_STEAMCACHE = "SteamCache"

CONTENT3_TYPES = (CONTENT3_TYPE_CDN, CONTENT3_TYPE_CS, CONTENT3_TYPE_STEAMCACHE)

# authentication modes
AUTH_MODE_AUTO = "auto"  # accept a CS session or a CDN token, whichever is sent
AUTH_MODE_CS = "cs"
AUTH_MODE_CDN = "cdn"
AUTH_MODE_NONE = "none"

CONTENT_TYPE_MANIFEST = "application/x-steam-manifest"
CONTENT_TYPE_CHUNK = "application/x-steam-chunk"
CONTENT_TYPE_VDF = "text/vdf"

SESSION_TIMEOUT = 3600  # seconds a CS session survives without a request

RSA_ENCRYPTED_KEY_LENGTH = 128
ENCRYPTION_KEY_LENGTH = 32


# ---------------------------------------------------------------------------
# vdf (text key values) serialization, used by /serverlist and /server-status
# ---------------------------------------------------------------------------

def _vdf_escape(value):
    return str(value).replace('\\', '\\\\').replace('"', '\\"')


def serialize_vdf(name, contents, indent = 0):
    """
    Serialize a dict (values may be nested dicts) into the text key values
    format the steam client expects from /serverlist and /server-status.
    """
    pad = '\t' * indent
    out = ['%s"%s"' % (pad, _vdf_escape(name)), '%s{' % pad]

    for key, value in contents.items():
        if isinstance(value, dict):
            out.append(serialize_vdf(key, value, indent + 1))
        else:
            out.append('%s\t"%s"\t\t"%s"' % (pad, _vdf_escape(key), _vdf_escape(value)))

    out.append('%s}' % pad)

    return '\n'.join(out)


# ---------------------------------------------------------------------------
# CS sessions (deprecated app ownership ticket based authentication)
# ---------------------------------------------------------------------------

class Content3Session(object):
    __slots__ = ('session_id', 'key', 'tickets', 'address', 'last_seen')

    def __init__(self, session_id, key, address):
        self.session_id = session_id
        self.key = key
        self.tickets = {}  # app/depot id -> parsed app ownership ticket
        self.address = address
        self.last_seen = time.time()

    def touch(self):
        self.last_seen = time.time()

    def is_authorized(self, depot_id):
        return int(depot_id) in self.tickets


class Content3SessionManager(object):
    def __init__(self, timeout = SESSION_TIMEOUT):
        self.timeout = timeout
        self._sessions = {}
        self._lock = threading.Lock()

    def create(self, key, address):
        session_id = struct.unpack('<Q', os.urandom(8))[0] & 0x7FFFFFFFFFFFFFFF
        if not session_id:
            session_id = 1

        session = Content3Session(session_id, key, address)

        with self._lock:
            self._prune()
            self._sessions[session_id] = session

        return session

    def get(self, session_id):
        with self._lock:
            session = self._sessions.get(int(session_id))
            if session is None:
                return None
            if time.time() - session.last_seen > self.timeout:
                del self._sessions[int(session_id)]
                return None
            session.touch()
            return session

    def _prune(self):
        now = time.time()
        for session_id in [s for s, session in self._sessions.items() if now - session.last_seen > self.timeout]:
            del self._sessions[session_id]

    @property
    def count(self):
        with self._lock:
            return len(self._sessions)


def get_request_hash(session_id, request_counter, key, url):
    """
    The x-steam-auth hash : sha1 of the session id, the request counter, the
    session key and the requested url.

    Mirrors tinserver's Content3ServerTools::getRequestHash
    """
    digest = sha1()
    digest.update(struct.pack('<Q', session_id))
    digest.update(struct.pack('<Q', request_counter))
    digest.update(key)
    digest.update(url.encode('latin-1', errors = 'replace'))
    return digest.digest()


def parse_header_value(value):
    """
    Parse a 'name=value' parameter list into a dict, accepting the comma,
    semicolon and whitespace separators steam has used over the years.
    """
    parsed = {}

    if not value:
        return parsed

    for part in re.split(r'[;,\s]+', value):
        part = part.strip()
        if not part or '=' not in part:
            continue
        name, _, item = part.partition('=')
        parsed[name.strip().lower()] = item.strip().strip('"')

    return parsed


# ---------------------------------------------------------------------------
# request handler
# ---------------------------------------------------------------------------

class Content3RequestHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "Steam/1.0"
    sys_version = ""

    # -- plumbing -----------------------------------------------------------

    @property
    def owner(self):
        return self.server.owner

    @property
    def log(self):
        return self.server.owner.log

    def log_message(self, fmt, *args):
        # keep the stock handler out of stderr, everything goes to our logger
        self.log.debug("%s - %s", self.client_address[0], fmt % args)

    def log_error(self, fmt, *args):
        self.log.debug("%s - %s", self.client_address[0], fmt % args)

    def send_body(self, status, body, content_type = None, extra_headers = None):
        if isinstance(body, str):
            body = body.encode('utf-8')

        headers = dict(extra_headers or {})

        # steam echoes the session id back on every authenticated CS response
        session_id = getattr(self, 'steam_session_id', None)
        if session_id:
            headers.setdefault("x-steam-sid", str(session_id))

        self.send_response(status)
        if content_type:
            self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for name, value in headers.items():
            self.send_header(name, value)
        self.end_headers()

        if self.command != "HEAD" and body:
            self.wfile.write(body)

    def send_status(self, status, message = None):
        self.send_body(status, message or b'', "text/plain" if message else None)

    # -- routing ------------------------------------------------------------

    def do_GET(self):
        self._service()

    def do_HEAD(self):
        self._service()

    def do_POST(self):
        self._service()

    def _service(self):
        try:
            split = urllib.parse.urlsplit(self.path)
            segments = [urllib.parse.unquote(part) for part in split.path.strip('/').split('/') if part != '']
            query = split.query

            if not segments:
                self.send_status(404)
                return

            route = segments[0].lower()

            if route == "depot":
                self._depot(segments, query)
            elif route == "serverlist":
                self._serverlist(segments)
            elif route == "server-status":
                self._server_status()
            elif route == "initsession":
                self._initsession()
            elif route == "authdepot":
                self._authdepot()
            else:
                self.send_status(404)

        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            # the steam client drops connections mid transfer all the time
            self.close_connection = True
        except Exception:
            self.log.error("Error while handling %s", self.path, exc_info = True)
            try:
                self.send_status(500)
            except Exception:
                self.close_connection = True

    # -- /depot -------------------------------------------------------------

    def _depot(self, segments, query):
        if len(segments) < 3:
            self.send_status(404)
            return

        try:
            depot_id = int(segments[1])
        except ValueError:
            self.send_status(404)
            return

        service = segments[2].lower()

        if not self._authenticate_depot(depot_id, query):
            return

        if service == "manifest":
            if len(segments) < 4:
                self.send_status(404)
                return

            try:
                gid = int(segments[3])
            except ValueError:
                self.send_status(404)
                return

            # the trailing element is the manifest version the client wants,
            # 5 for the protobuf format and 4 for the deprecated one
            version = MANIFEST_VERSION_PROTO
            if len(segments) > 4:
                try:
                    version = int(segments[4])
                except ValueError:
                    self.send_status(404)
                    return

                if version not in (MANIFEST_VERSION_DEPRECATED, MANIFEST_VERSION_PROTO):
                    self.log.debug("Unknown manifest version for depot %u manifest gid %u : %s",
                                   depot_id, gid, segments[4])
                    self.send_status(404)
                    return

            self._do_manifest(depot_id, gid, version)

        elif service == "chunk":
            if len(segments) < 4:
                self.send_status(404)
                return

            self._do_chunk(depot_id, segments[3])

        else:
            self.send_status(404)

    def _do_manifest(self, depot_id, gid, version):
        self.log.debug("Depot %u manifest gid %u (version %u) requested", depot_id, gid, version)

        repository = self.owner.repository

        if repository.get_depot_key(depot_id) is None and not repository.has_depot_content(depot_id):
            self.log.error("Encryption key for depot %u not available", depot_id)
            self.send_status(500)
            return

        # the manifest is always fetched before its chunks, so this is where the
        # neutered variant of a depot gets generated on first use
        suffix = self.owner.prepare_neutered_content(depot_id, gid, self.client_address[0])

        body = repository.get_manifest_body(depot_id, gid, version, suffix)

        if body is None:
            self.log.error("Depot %u manifest gid %u not available", depot_id, gid)
            self.send_status(404)
            return

        self.log.debug("Sending depot %u manifest gid %u (%d bytes)", depot_id, gid, len(body))
        self.send_body(200, body, CONTENT_TYPE_MANIFEST)

    def _do_chunk(self, depot_id, chunk_sha_str):
        try:
            chunk_sha = bytes.fromhex(chunk_sha_str.strip())
        except ValueError:
            chunk_sha = b''

        if len(chunk_sha) != 20:
            self.log.error("Invalid depot %u chunk %s requested", depot_id, chunk_sha_str)
            self.send_status(404)
            return

        self.log.debug("Depot %u chunk %s requested", depot_id, chunk_sha_str)

        try:
            body = self.owner.repository.get_chunk_body(depot_id, chunk_sha,
                                                        self.owner.get_neuter_suffix(self.client_address[0]))
        except Exception as e:
            self.log.error("Error reading depot %u chunk %s : %s", depot_id, chunk_sha_str, e)
            self.send_status(500)
            return

        if body is None:
            self.log.error("Depot %u chunk %s not found", depot_id, chunk_sha_str)
            self.send_status(404)
            return

        self.log.debug("Sending depot %u chunk %s (%d bytes)", depot_id, chunk_sha_str, len(body))
        self.send_body(200, body, CONTENT_TYPE_CHUNK)

    # -- /serverlist --------------------------------------------------------

    def _serverlist(self, segments):
        cell_id = int(segments[1]) if len(segments) > 1 and segments[1].isdigit() else 0
        max_results = int(segments[2]) if len(segments) > 2 and segments[2].isdigit() else 1

        self.log.debug("Servers list requested for cell %u (%u results max)", cell_id, max_results)

        servers = self.owner.get_content_servers(cell_id, max_results)

        contents = {}
        for index, server in enumerate(servers):
            contents[str(index)] = server

        self.send_body(200, serialize_vdf("serverlist", contents), CONTENT_TYPE_VDF)

    # -- /server-status -----------------------------------------------------

    def _server_status(self):
        self.log.debug("Server status requested")

        status = {
                'csid': self.owner.content_server_id,
                'load': self.owner.get_load(),
                'cell': self.owner.cell_id,
        }

        self.send_body(200, serialize_vdf("status", status), CONTENT_TYPE_VDF)

    # -- /initsession, /authdepot (deprecated CS authentication) ------------

    def _read_post_parameters(self):
        try:
            length = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            length = 0

        body = self.rfile.read(length) if length else b''

        # values are url encoded binary, so they are kept as bytes
        parameters = {}
        for part in body.split(b'&'):
            if not part:
                continue
            name, _, value = part.partition(b'=')
            parameters[name.decode('latin-1').lower()] = urllib.parse.unquote_to_bytes(value.replace(b'+', b' '))

        return parameters

    def _initsession(self):
        parameters = self._read_post_parameters()

        session_key = parameters.get('sessionkey')
        encrypted_ticket = parameters.get('appticket')

        if not session_key or not encrypted_ticket:
            self.log.error("initsession - Required parameters not found")
            self.send_status(401)
            return

        if len(session_key) != RSA_ENCRYPTED_KEY_LENGTH:
            self.log.error("initsession - Invalid parameters length (%d)", len(session_key))
            self.send_status(401)
            return

        key = self.owner.decrypt_session_key(session_key)
        if not key or len(key) != ENCRYPTION_KEY_LENGTH:
            self.log.error("initsession - Unrecognized encrypted key")
            self.send_status(401)
            return

        ticket = self.owner.decrypt_app_ticket(key, encrypted_ticket)
        if ticket is None:
            self.log.error("initsession - Invalid ticket")
            self.send_status(401)
            return

        if not self.owner.validate_app_ownership_ticket(ticket):
            self.log.error("initsession - Invalid App (%s) ticket", ticket.app_id)
            self.send_status(401)
            return

        session = self.owner.sessions.create(key, self.client_address)
        session.tickets[int(ticket.app_id)] = ticket

        self.log.info("User #%s opened content session %d", ticket.steam_id, session.session_id)

        response = {
                'sessionid':   session.session_id,
                'req-counter': 0,
                'csid':        self.owner.content_server_id,
        }

        self.send_body(200, serialize_vdf("response", response), CONTENT_TYPE_VDF)

    def _authdepot(self):
        # /authdepot is signed like any other authenticated request
        session = self._authenticate_session_cs()
        if session is None:
            self.log.error("authdepot - Invalid session")
            self.send_status(401)
            return

        self.steam_session_id = session.session_id

        parameters = self._read_post_parameters()
        encrypted_ticket = parameters.get('appticket')

        if not encrypted_ticket:
            self.log.error("authdepot - Required parameters not found")
            self.send_status(401)
            return

        ticket = self.owner.decrypt_app_ticket(session.key, encrypted_ticket)
        if ticket is None or not self.owner.validate_app_ownership_ticket(ticket):
            self.log.error("authdepot - Invalid ticket")
            self.send_status(401)
            return

        session.tickets[int(ticket.app_id)] = ticket

        self.log.info("User #%s authenticated for depot %s", ticket.steam_id, ticket.app_id)

        self.send_body(200, b'')

    # -- authentication -----------------------------------------------------

    def _get_cs_session(self):
        steam_auth = parse_header_value(self.headers.get('x-steam-auth'))
        if not steam_auth:
            return None

        try:
            session_id = int(steam_auth.get('sessionid', 0))
        except ValueError:
            return None

        if not session_id:
            return None

        return self.owner.sessions.get(session_id)

    def _authenticate_session_cs(self):
        """Validate the x-steam-auth header. Returns the session, or None."""
        steam_auth = parse_header_value(self.headers.get('x-steam-auth'))

        try:
            session_id = int(steam_auth.get('sessionid', 0))
            request_counter = int(steam_auth.get('req-counter', 0))
        except ValueError:
            self.log.debug("Invalid x-steam-auth header")
            return None

        hash_string = steam_auth.get('hash')

        if not session_id or not request_counter or not hash_string:
            self.log.debug("Invalid x-steam-auth header")
            return None

        try:
            request_hash = bytes.fromhex(hash_string)
        except ValueError:
            request_hash = b''

        if len(request_hash) != 20:
            self.log.debug("Invalid x-steam-auth hash length")
            return None

        session = self.owner.sessions.get(session_id)
        if session is None:
            self.log.debug("Invalid session %d", session_id)
            return None

        expected = get_request_hash(session_id, request_counter, session.key, self.path)
        if request_hash != expected:
            self.log.debug("Invalid x-steam-auth hash")
            return None

        return session

    def _authenticate_depot(self, depot_id, query):
        """
        Authorise a depot request, accepting whichever of the two schemes the
        client used. Sends the error response itself and returns False on
        failure.
        """
        mode = self.owner.auth_mode

        if mode == AUTH_MODE_NONE:
            return True

        has_steam_auth = bool(self.headers.get('x-steam-auth'))

        if has_steam_auth and mode in (AUTH_MODE_AUTO, AUTH_MODE_CS):
            session = self._authenticate_session_cs()
            if session is None:
                self.send_status(401)
                return False

            if not session.is_authorized(depot_id):
                self.log.debug("Depot %u not authorized on session %d", depot_id, session.session_id)
                self.send_status(401)
                return False

            self.steam_session_id = session.session_id
            return True

        if mode == AUTH_MODE_CS:
            self.log.debug("Depot %u request without an x-steam-auth header", depot_id)
            self.send_status(401)
            return False

        # CDN / SteamCache : the token is passed as the query string. Steam no
        # longer sends one to steam cache servers, so an absent token is allowed
        if not query:
            return True

        if self.owner.require_cdn_token and not self.owner.repository.cdn_tokens.validate(depot_id, '?' + query):
            self.log.debug("Invalid CDN auth token for depot %u", depot_id)
            self.send_status(401)
            return False

        return True


class Content3HTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    # keep the listen backlog generous, steam opens a lot of parallel downloads
    request_queue_size = 64

    def __init__(self, address, handler, owner):
        self.owner = owner
        super().__init__(address, handler)

    def server_bind(self):
        # SO_REUSEADDR alone behaves differently on windows and linux, this
        # keeps a restart from tripping over a lingering socket on both
        try:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except OSError:
            pass
        super().server_bind()

    def handle_error(self, request, client_address):
        self.owner.log.debug("Connection error from %s", client_address, exc_info = True)


# ---------------------------------------------------------------------------
# server module
# ---------------------------------------------------------------------------

class content3server(threading.Thread):
    """Steam3 content server module."""

    def __init__(self, port, config):
        super().__init__()

        self.server_type = "Content3Server"
        self.port = int(port)
        self.config = config
        self.running = True
        self.log = logging.getLogger("Content3SRV")

        self.httpd = None
        self._stop_event = threading.Event()

        self.content_server_id = int(config.get('content3_server_id', config.get('content_server_id', 1)) or 1)
        self.cell_id = int(config.get('cellid', globalvars.cellid) or 0)

        self.server_advertise_type = self._read_server_type(config)
        self.auth_mode = (config.get('content3_auth_mode', AUTH_MODE_AUTO) or AUTH_MODE_AUTO).strip().lower()
        if self.auth_mode not in (AUTH_MODE_AUTO, AUTH_MODE_CS, AUTH_MODE_CDN, AUTH_MODE_NONE):
            self.auth_mode = AUTH_MODE_AUTO

        self.require_cdn_token = str(config.get('content3_require_cdn_token', "false")).lower() == "true"

        self.vhost = config.get('content3_vhost', '') or "cs.steamcontent.com"

        content_root = config.get('content3_content_dir', '') or None
        cache_root = None
        if str(config.get('content3_cache_enabled', "true")).lower() == "true":
            cache_root = config.get('content3_cache_dir', '') or None

        self.neuter_enabled = str(config.get('content3_neuter_enabled', "true")).lower() == "true"

        self.repository = get_repository(content_root, cache_root)
        self.sessions = Content3SessionManager()

        globalvars.servers.append(self)

    @staticmethod
    def _read_server_type(config):
        configured = (config.get('content3_server_type', CONTENT3_TYPE_STEAMCACHE) or '').strip()
        for known in CONTENT3_TYPES:
            if configured.lower() == known.lower():
                return known
        return CONTENT3_TYPE_STEAMCACHE

    # -- thread -------------------------------------------------------------

    def run(self):
        bind_ip = globalvars.server_ip or "0.0.0.0"

        try:
            self.httpd = Content3HTTPServer((bind_ip, self.port), Content3RequestHandler, self)
        except OSError as e:
            self.log.error("Content3 Server cannot bind %s:%d : %s", bind_ip, self.port, e)
            self.running = False
            return

        depots = self.repository.list_depot_ids()
        self.log.info("Steam3 Content Server listening on %s:%d (%d depot(s) available)",
                      bind_ip, self.port, len(depots))
        if depots:
            self.log.debug("Available depots : %s", ", ".join(str(depot) for depot in depots))

        try:
            self.httpd.serve_forever(poll_interval = 0.5)
        except Exception:
            self.log.error("Steam3 Content Server encountered an exception:", exc_info = True)
        finally:
            self.log.info("Steam3 Content Server thread terminating.")

    def stop(self):
        self.log.info("Stopping Steam3 Content Server on port %d", self.port)
        self._stop_event.set()
        self.running = False
        if self.httpd is not None:
            threading.Thread(target = self.httpd.shutdown, daemon = True).start()

    def cleanup(self):
        """Content3 Server specific cleanup routine"""
        self.log.info("Cleaning up Steam3 Content Server on port %d", self.port)
        self.stop()
        if self.httpd is not None:
            try:
                self.httpd.server_close()
            except Exception:
                pass
            self.httpd = None

    # -- content server list ------------------------------------------------

    def get_load(self):
        return self.sessions.count

    def get_advertised_address(self):
        ip = globalvars.public_ip if globalvars.public_ip not in ("", "0.0.0.0") else globalvars.server_ip
        return "%s:%d" % (ip, self.port)

    def get_content_servers(self, cell_id, max_results):
        """The entries returned by /serverlist, one per content server."""
        entry = {
                'type':                  self.server_advertise_type,
                'sourceid':              self.content_server_id,
                'host':                  self.get_advertised_address(),
                'vhost':                 self.vhost,
                'load':                  self.get_load(),
                'weightedload':          100,
                'numentriesinclientlist':1,
                'https_support':         "optional",
        }

        if self.server_advertise_type != CONTENT3_TYPE_CDN:
            # a CDN is global and carries no cell
            entry['cell'] = self.cell_id

        if self.server_advertise_type == CONTENT3_TYPE_CS:
            entry['usetokenauth'] = 1

        return [entry]

    # -- neutering ----------------------------------------------------------

    def get_neuter_suffix(self, client_ip):
        """The cache suffix a client is served from, "" when neutering is off."""
        if not self.neuter_enabled:
            return ""

        from utilities import steam3_neuter

        return steam3_neuter.suffix_for(steam3_neuter.islan_for_address(client_ip))

    def prepare_neutered_content(self, depot_id, gid, client_ip):
        """
        Generate the neutered variant of a depot if it does not exist yet, and
        return the suffix the request should be served from.
        """
        if not self.neuter_enabled:
            return ""

        from utilities import steam3_neuter

        islan = steam3_neuter.islan_for_address(client_ip)

        return steam3_neuter.ensure_neutered(self.repository, depot_id, gid, islan)

    # -- authentication helpers --------------------------------------------

    def decrypt_session_key(self, encrypted_key):
        """RSA decrypt the session key a client sends to /initsession."""
        for key in (encryption.network_key, encryption.main_key):
            if key is None:
                continue
            try:
                decrypted = encryption.aes_decrypt_no_IV(key, encrypted_key)
            except Exception:
                decrypted = None

            if decrypted and len(decrypted) == ENCRYPTION_KEY_LENGTH:
                return decrypted

        return None

    def decrypt_app_ticket(self, key, encrypted_ticket):
        """Decrypt and parse the app ownership ticket sent with a session."""
        from steam3.Types.Objects.AppOwnershipTicket import Steam3AppOwnershipTicket
        from steam3 import cm_crypto

        try:
            ticket_bytes = cm_crypto.symmetric_decrypt(encrypted_ticket, key)
        except Exception as e:
            self.log.error("Unable to decrypt app ticket : %s", e)
            return None

        try:
            return Steam3AppOwnershipTicket.deserialize(ticket_bytes)
        except Exception as e:
            self.log.error("Unable to parse app ticket : %s", e)
            return None

    def validate_app_ownership_ticket(self, ticket):
        """A ticket is accepted while it has not expired, as tinserver does."""
        if ticket is None:
            return False

        expires = ticket.time_expire

        if isinstance(expires, str):
            try:
                expires = datetime.strptime(expires, '%m/%d/%Y %H:%M:%S').replace(tzinfo = timezone.utc).timestamp()
            except ValueError:
                self.log.debug("Unparsable ticket expiration : %s", expires)
                return False

        try:
            return float(expires) >= time.time()
        except (TypeError, ValueError):
            return False
