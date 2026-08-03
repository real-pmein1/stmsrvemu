"""
Steam3 (SteamPipe) content repository.

Indexes everything the Steam3 content server needs to answer a client, from a
single on-disk tree :

    files/steam3content/
        depots/<depotid>/   <depot>_depotcache_<n>.csm / .csd     chunk stores
                            <depot>-manifest-<gid>.manif4         v4 manifest
                            <depot>-manifest-<gid>.manif5         v5 manifest
        keys/<depotid>.depotkey                                   32 byte AES key
        manifest_list/<depotid>_manifests.txt                     informational

Manifests downloaded from a real content server are stored exactly as they came
off the wire (a zip holding the serialized manifest, filenames already encrypted
with the depot key and carrying valve's signature).  Those are served back byte
for byte, which keeps the original signature intact.  A manifest stored in the
clear is encrypted with the depot key and given a fake signature on the fly, the
same way tinserver's Content3FileSystemProvider does it.

This module also owns the CDN auth token registry shared by the CM server (which
hands tokens out over EMsgClientGetCDNAuthToken) and the content server (which
validates them on every depot request).
"""

import logging
import os
import re
import threading
import time

from utilities.steam3_chunkstore import find_chunk_stores, list_files_by_extension
from utilities.steam3_manifest import MANIFEST_VERSION_PROTO, Steam3Manifest

log = logging.getLogger('CONTENT3')

DEFAULT_CONTENT_ROOT = os.path.join("files", "steam3content")

# "<depot>-manifest-<gid>.manif5", "<gid>.manifest", "<depot>_<gid>.manifest"
_MANIFEST_NAME_RES = (
        re.compile(r'^(?P<depot>\d+)-manifest-(?P<gid>\d+)\.manif(?P<version>\d+)$', re.IGNORECASE),
        re.compile(r'^(?P<depot>\d+)[_-](?P<gid>\d+)\.manifest$', re.IGNORECASE),
        re.compile(r'^(?P<gid>\d+)\.manifest$', re.IGNORECASE),
)

_MANIFEST_EXTENSIONS = ('.manif4', '.manif5', '.manifest')


def parse_manifest_filename(filename, default_depot_id = 0):
    """Return (depot_id, gid, version) for a stored manifest file name."""
    name = os.path.basename(filename)

    for pattern in _MANIFEST_NAME_RES:
        match = pattern.match(name)
        if not match:
            continue

        groups = match.groupdict()
        depot_id = int(groups.get('depot') or default_depot_id or 0)
        gid = int(groups['gid'])
        version = int(groups['version']) if groups.get('version') else 0

        return depot_id, gid, version

    return None, None, None


class DepotManifestFile(object):
    """One manifest file on disk, for one depot / gid / manifest version."""

    __slots__ = ('path', 'depot_id', 'gid', 'version')

    def __init__(self, path, depot_id, gid, version):
        self.path = path
        self.depot_id = depot_id
        self.gid = gid
        self.version = version

    def __repr__(self):
        return "DepotManifestFile(depot=%d, gid=%d, version=%d)" % (self.depot_id, self.gid, self.version)

    def read(self):
        with open(self.path, 'rb') as f:
            return f.read()


class Steam3Depot(object):
    """Everything known about a single depot."""

    def __init__(self, depot_id):
        self.depot_id = depot_id
        self.key = None
        self.chunkstore = None
        self.manifests = {}  # (gid, version) -> DepotManifestFile

    def __repr__(self):
        return ("Steam3Depot(id=%d, key=%s, chunks=%d, manifests=%d)"
                % (self.depot_id, self.key is not None,
                   self.chunkstore.chunk_count if self.chunkstore else 0, len(self.manifests)))

    @property
    def gids(self):
        return sorted({gid for gid, _ in self.manifests.keys()})

    def get_manifest_file(self, gid, version = 0):
        """
        Find the stored manifest for a gid, preferring the requested version and
        falling back to any other version we hold (it is converted on the fly).
        """
        entry = self.manifests.get((gid, int(version)))
        if entry:
            return entry

        # version unknown / not stored under that version : take whatever we have
        candidates = [entry for (stored_gid, _), entry in self.manifests.items() if stored_gid == gid]
        if not candidates:
            return None

        candidates.sort(key = lambda e:e.version, reverse = True)
        return candidates[0]


class CDNAuthTokenRegistry(object):
    """
    CDN auth tokens issued by the CM and validated by the content server.

    Steam appends the token to the request as a query string, so tokens are kept
    and compared in exactly the form the client sends them back.
    """

    def __init__(self, lifetime = 7 * 24 * 3600):
        self.lifetime = lifetime
        self._tokens = {}  # token string -> dict
        self._lock = threading.Lock()

    def issue(self, steam_id, app_id, depot_id, hostname = ''):
        """Issue a token for a depot. Returns (token, expiration timestamp)."""
        expires = int(time.time()) + self.lifetime
        token = "?token=%s" % os.urandom(16).hex()

        with self._lock:
            self._prune()
            self._tokens[token] = {
                    'steam_id': steam_id,
                    'app_id':   app_id,
                    'depot_id': depot_id,
                    'hostname': hostname,
                    'expires':  expires,
            }

        log.debug("Issued CDN auth token for depot %s (app %s), expires %s", depot_id, app_id, expires)
        return token, expires

    def validate(self, depot_id, token):
        """True when the token was issued for this depot and has not expired."""
        if not token:
            return False

        if not token.startswith('?'):
            token = '?' + token

        with self._lock:
            entry = self._tokens.get(token)
            if entry is None:
                return False
            if entry['expires'] < int(time.time()):
                del self._tokens[token]
                return False

        # a token issued for an app grants its depots too, so only reject a
        # token that was explicitly bound to a different depot
        return entry['depot_id'] in (0, depot_id) or entry['app_id'] in (0, depot_id)

    def get(self, token):
        with self._lock:
            return self._tokens.get(token)

    def _prune(self):
        now = int(time.time())
        for token in [t for t, e in self._tokens.items() if e['expires'] < now]:
            del self._tokens[token]


class Steam3ContentRepository(object):
    """Indexes files/steam3content and serves manifests and chunks from it."""

    def __init__(self, root = None, cache_root = None):
        self.root = root or DEFAULT_CONTENT_ROOT
        self.cache_root = cache_root

        self.depots = {}  # depot id -> Steam3Depot
        self.cdn_tokens = CDNAuthTokenRegistry()

        self._lock = threading.Lock()
        self._manifest_cache = {}  # (depot, gid, version) -> bytes

        self.reload()

    # -- indexing -----------------------------------------------------------

    @property
    def depots_root(self):
        return os.path.join(self.root, "depots")

    @property
    def keys_root(self):
        return os.path.join(self.root, "keys")

    def reload(self):
        """(Re)scan the content tree."""
        depots = {}

        keys = self._load_keys()

        if os.path.isdir(self.depots_root):
            for name in sorted(os.listdir(self.depots_root)):
                depot_path = os.path.join(self.depots_root, name)
                if not os.path.isdir(depot_path) or not name.isdigit():
                    continue

                depot_id = int(name)
                depot = Steam3Depot(depot_id)
                depot.key = keys.get(depot_id)

                for depot_of_store, chunkstore in find_chunk_stores(depot_path).items():
                    if depot_of_store == depot_id:
                        depot.chunkstore = chunkstore
                    else:
                        # a depot folder may hold a chunk store of another depot
                        other = depots.setdefault(depot_of_store, Steam3Depot(depot_of_store))
                        other.key = other.key or keys.get(depot_of_store)
                        other.chunkstore = chunkstore

                for path in list_files_by_extension(depot_path, _MANIFEST_EXTENSIONS):
                        manifest_depot, gid, version = parse_manifest_filename(path, depot_id)
                        if gid is None:
                            continue
                        if not version:
                            version = self._detect_manifest_version(path)

                        target = depot
                        if manifest_depot and manifest_depot != depot_id:
                            target = depots.setdefault(manifest_depot, Steam3Depot(manifest_depot))
                            target.key = target.key or keys.get(manifest_depot)

                        target.manifests[(gid, version)] = DepotManifestFile(path, target.depot_id, gid, version)

                existing = depots.get(depot_id)
                if existing:
                    existing.key = existing.key or depot.key
                    existing.chunkstore = existing.chunkstore or depot.chunkstore
                    existing.manifests.update(depot.manifests)
                else:
                    depots[depot_id] = depot

        # depots we only have a key for are still worth knowing about
        for depot_id, key in keys.items():
            depot = depots.setdefault(depot_id, Steam3Depot(depot_id))
            depot.key = depot.key or key

        with self._lock:
            self.depots = depots
            self._manifest_cache = {}

        log.info("Steam3 content repository loaded : %d depot(s) from %s", len(depots), self.root)
        for depot in depots.values():
            log.debug("  %s", depot)

        return depots

    def _load_keys(self):
        keys = {}

        if not os.path.isdir(self.keys_root):
            return keys

        for path in list_files_by_extension(self.keys_root, ('.depotkey',)):
            name = os.path.splitext(os.path.basename(path))[0]
            if not name.isdigit():
                continue

            try:
                with open(path, 'rb') as f:
                    key = f.read()
            except OSError as e:
                log.error("Unable to read depot key %s : %s", path, e)
                continue

            key = self._normalize_key(key)
            if key is None:
                log.error("Depot key %s is not a 32 byte key", path)
                continue

            keys[int(name)] = key

        return keys

    @staticmethod
    def _normalize_key(key):
        if len(key) == 32:
            return key

        # also accept a hex encoded key, with or without a trailing newline
        text = key.strip()
        if len(text) == 64:
            try:
                return bytes.fromhex(text.decode('ascii'))
            except (ValueError, UnicodeDecodeError):
                return None

        return None

    @staticmethod
    def _detect_manifest_version(path):
        try:
            manifest = Steam3Manifest.from_file(path)
            return manifest.source_version
        except Exception as e:
            log.error("Unable to identify manifest %s : %s", path, e)
            return MANIFEST_VERSION_PROTO

    # -- lookups ------------------------------------------------------------

    def get_depot(self, depot_id):
        return self.depots.get(int(depot_id))

    def get_depot_key(self, depot_id):
        depot = self.get_depot(depot_id)
        return depot.key if depot else None

    def list_depot_ids(self):
        return sorted(self.depots.keys())

    def get_latest_gid(self, depot_id):
        depot = self.get_depot(depot_id)
        if not depot:
            return None
        gids = depot.gids
        return gids[-1] if gids else None

    def has_depot_content(self, depot_id):
        depot = self.get_depot(depot_id)
        return bool(depot and (depot.manifests or depot.chunkstore))

    # -- manifests ----------------------------------------------------------

    def get_manifest(self, depot_id, gid, decrypt = False):
        """Return the parsed manifest for a depot / gid."""
        depot = self.get_depot(depot_id)
        if not depot:
            return None

        entry = depot.get_manifest_file(int(gid))
        if not entry:
            return None

        manifest = Steam3Manifest.from_bytes(entry.read())

        if decrypt and manifest.filenames_encrypted and depot.key:
            manifest.decrypt_filenames(depot.key)

        return manifest

    def get_manifest_body(self, depot_id, gid, version = MANIFEST_VERSION_PROTO, suffix = ""):
        """
        Return the exact HTTP body a content server answers a manifest request
        with : a zip holding the serialized manifest, filenames encrypted with
        the depot key and a signature present.

        A suffix ("_lan" / "_wan") selects the neutered variant, falling back to
        the untouched manifest when the depot needed no neutering.
        """
        depot_id = int(depot_id)
        gid = int(gid)
        version = int(version)

        cache_key = (depot_id, gid, version, suffix)

        with self._lock:
            cached = self._manifest_cache.get(cache_key)
        if cached is not None:
            return cached

        cached = self._read_disk_cache(cache_key)
        if cached is not None:
            with self._lock:
                self._manifest_cache[cache_key] = cached
            return cached

        if suffix:
            # no neutered variant for this depot, serve the original one
            return self.get_manifest_body(depot_id, gid, version)

        depot = self.get_depot(depot_id)
        if not depot:
            return None

        entry = depot.get_manifest_file(gid, version)
        if not entry:
            return None

        raw = entry.read()

        manifest = Steam3Manifest.from_bytes(raw)

        if manifest.filenames_encrypted and manifest.signature and entry.version == version:
            # stored exactly as a real content server sent it : pass it through
            # untouched so the original signature stays valid
            body = raw
        else:
            if not manifest.filenames_encrypted:
                if not depot.key:
                    log.error("Encryption key for depot %u not available", depot_id)
                    return None
                manifest.encrypt_filenames(depot.key)

            if version == MANIFEST_VERSION_PROTO:
                # we rebuilt the manifest, so valve's signature no longer covers
                # it : sign it with the key the neuter puts into the client
                manifest.sign()
            elif not manifest.signature:
                manifest.generate_fake_signature()

            body = manifest.serialize_zipped(version)

        with self._lock:
            self._manifest_cache[cache_key] = body
        self._write_disk_cache(cache_key, body)

        return body

    # -- chunks -------------------------------------------------------------

    def get_chunk_body(self, depot_id, chunk_sha, suffix = ""):
        """
        Return the exact HTTP body a content server answers a chunk request
        with : the compressed chunk, symmetrically encrypted with the depot key.

        A neutered chunk generated into the cache is served in place of the
        original one, the same way the Steam2 content server swaps in a neutered
        storage chunk.
        """
        depot_id = int(depot_id)

        if suffix:
            neutered = self._read_neutered_chunk(depot_id, chunk_sha, suffix)
            if neutered is not None:
                return neutered

        depot = self.get_depot(depot_id)
        if not depot or not depot.chunkstore:
            return None

        if not depot.chunkstore.has_chunk(chunk_sha):
            return None

        return depot.chunkstore.get_transport_chunk(chunk_sha, depot.key)

    def has_chunk(self, depot_id, chunk_sha):
        depot = self.get_depot(depot_id)
        return bool(depot and depot.chunkstore and depot.chunkstore.has_chunk(chunk_sha))

    # -- on disk cache ------------------------------------------------------

    def _cache_path(self, cache_key):
        if not self.cache_root:
            return None
        depot_id, gid, version, suffix = cache_key
        return os.path.join(self.cache_root, "depot", str(depot_id), "manifest",
                            "%d_%d%s" % (gid, version, suffix))

    def _chunk_cache_path(self, depot_id, chunk_sha, suffix):
        if not self.cache_root:
            return None
        return os.path.join(self.cache_root, "depot", str(int(depot_id)), "chunk",
                            "%s%s" % (chunk_sha.hex(), suffix))

    def _neuter_marker_path(self, depot_id, gid, suffix):
        if not self.cache_root:
            return None
        return os.path.join(self.cache_root, "depot", str(int(depot_id)), "manifest",
                            "%d%s.neutered" % (int(gid), suffix))

    def _read_disk_cache(self, cache_key):
        path = self._cache_path(cache_key)
        if not path or not os.path.isfile(path) or not os.path.getsize(path):
            return None
        try:
            with open(path, 'rb') as f:
                return f.read()
        except OSError as e:
            log.error("Unable to read manifest cache %s : %s", path, e)
            return None

    def _write_disk_cache(self, cache_key, body):
        path = self._cache_path(cache_key)
        if not path:
            return
        try:
            os.makedirs(os.path.dirname(path), exist_ok = True)
            with open(path, 'wb') as f:
                f.write(body)
        except OSError as e:
            log.error("Unable to write manifest cache %s : %s", path, e)

    def _read_neutered_chunk(self, depot_id, chunk_sha, suffix):
        path = self._chunk_cache_path(depot_id, chunk_sha, suffix)
        if not path or not os.path.isfile(path) or not os.path.getsize(path):
            return None
        try:
            with open(path, 'rb') as f:
                return f.read()
        except OSError as e:
            log.error("Unable to read neutered chunk %s : %s", path, e)
            return None

    # -- neutered content ---------------------------------------------------

    def write_neutered_chunk(self, depot_id, chunk_sha, body, suffix):
        """Store a neutered chunk, ready to be served as is."""
        path = self._chunk_cache_path(depot_id, chunk_sha, suffix)
        if not path:
            return

        os.makedirs(os.path.dirname(path), exist_ok = True)
        with open(path, 'wb') as f:
            f.write(body)

    def write_neutered_manifest(self, depot_id, gid, version, body, suffix):
        """Store a rewritten manifest and make it the one served from now on."""
        cache_key = (int(depot_id), int(gid), int(version), suffix)

        self._write_disk_cache(cache_key, body)
        with self._lock:
            self._manifest_cache[cache_key] = body

        self._mark_neuter_generated(depot_id, gid, suffix)

    def mark_manifest_unneutered(self, depot_id, gid, suffix):
        """Record that a depot was examined and needed no neutering."""
        self._mark_neuter_generated(depot_id, gid, suffix)

    def _mark_neuter_generated(self, depot_id, gid, suffix):
        path = self._neuter_marker_path(depot_id, gid, suffix)
        if not path:
            return
        try:
            os.makedirs(os.path.dirname(path), exist_ok = True)
            with open(path, 'wb') as f:
                f.write(b'')
        except OSError as e:
            log.error("Unable to write neuter marker %s : %s", path, e)

    def is_neuter_generated(self, depot_id, gid, suffix):
        path = self._neuter_marker_path(depot_id, gid, suffix)
        return bool(path) and os.path.isfile(path)

    def clear_neutered(self, depot_id = None):
        """Drop generated neutered content so it is rebuilt on the next request."""
        import shutil

        if not self.cache_root:
            return

        depots = [int(depot_id)] if depot_id is not None else self.list_depot_ids()

        for identifier in depots:
            path = os.path.join(self.cache_root, "depot", str(identifier))
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors = True)

        with self._lock:
            if depot_id is None:
                self._manifest_cache = {}
            else:
                self._manifest_cache = {key: value for key, value in self._manifest_cache.items()
                                        if key[0] != int(depot_id)}


# ---------------------------------------------------------------------------
# process wide repository, shared by the CM and the content server
# ---------------------------------------------------------------------------

_repository = None
_repository_lock = threading.Lock()


def get_repository(root = None, cache_root = None):
    """Return (and create on first use) the shared content repository."""
    global _repository

    if _repository is None:
        with _repository_lock:
            if _repository is None:
                _repository = Steam3ContentRepository(root, cache_root)

    return _repository


def reload_repository():
    repository = get_repository()
    return repository.reload()
