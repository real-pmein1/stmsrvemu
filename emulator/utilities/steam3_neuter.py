"""
Steam3 (SteamPipe) content neutering.

Follows the same path the Steam2 storage neutering takes : the neutered content
is generated once into the cache folder and served in place of the original when
a client asks for it, with separate LAN and WAN variants.

The difference is what a Steam3 manifest binds. A chunk is addressed by the SHA1
of its own uncompressed data, so neutering a chunk changes the URL it lives at,
and the manifest that points at it has to be rewritten :

    chunk sha, crc, cb_compressed       change
    chunk offset, cb_original, size     unchanged (neutering is length preserving)
    file sha_content                    recomputed over the neutered file
    unique_chunks, total_compressed     recomputed
    manifest crc and signature          recomputed

The manifest keeps its original gid, because that is what the CDR / appinfo
points the client at, and it is re-signed with our network key - the neuter
replaces the client's content manifest signing key with that same key, so the
rewritten manifest verifies for real.

Neutering is applied per file rather than per chunk : the file is reassembled
from its chunks, neutered, then split again on the original chunk boundaries.
That keeps every offset valid and avoids missing a replacement that straddles a
chunk boundary.
"""

import logging
import os
import threading
import zlib
from hashlib import sha1

import globalvars
from config import get_config
from utilities.steam3_chunkstore import zip_compress
from utilities.steam3_manifest import MANIFEST_VERSION_DEPRECATED, MANIFEST_VERSION_PROTO

log = logging.getLogger('NEUTER3')

config = get_config()

# The Steam3 content system only exists from this blob date onwards, so there is
# nothing to neuter for an older blob and the whole sweep is skipped.
CONTENT3_MIN_BLOB_DATE = "2010-04-29"

# How much of the neighbouring chunks a neuter window carries, so a replacement
# landing across a chunk boundary is still found. Worked out from the longest
# replacement rule in use, within these bounds.
MIN_WINDOW_OVERLAP = 4096
MAX_WINDOW_OVERLAP = 1024 * 1024


class MissingChunkError(Exception):
    pass


class LengthChangedError(Exception):
    pass

# one lock per (depot, gid, suffix) so two clients asking for the same depot at
# the same time do not neuter it twice
_locks = {}
_locks_guard = threading.Lock()


def _get_lock(key):
    with _locks_guard:
        lock = _locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _locks[key] = lock
        return lock


def _crypto():
    from steam3 import cm_crypto
    return cm_crypto


def is_enabled():
    return str(config.get('content3_neuter_enabled', "true")).lower() == "true"


def get_blob_date():
    """The blob date as YYYY-MM-DD, however far initialization has got."""
    date = getattr(globalvars, 'formatted_underscore_date', '') or ''
    if date:
        return date

    # log_blob_information() has not run yet, work it out from the raw timestamp
    cddb = getattr(globalvars, 'CDDB_datetime', None)
    if isinstance(cddb, str) and cddb:
        try:
            from datetime import datetime
            return datetime.strptime(cddb, "%m/%d/%Y %H:%M:%S").strftime("%Y-%m-%d")
        except ValueError:
            pass

    return (config.get('steam_date', '') or '').replace('^', '-')


def is_supported_blob():
    """True when the loaded blob is recent enough to have Steam3 content."""
    date = get_blob_date()
    if not date:
        return False
    return date >= CONTENT3_MIN_BLOB_DATE


def suffix_for(islan):
    """The cache suffix a request gets, matching the Steam2 content server."""
    if config.get("public_ip", "0.0.0.0") == "0.0.0.0":
        return ""
    return "_lan" if islan else "_wan"


def islan_for_address(address):
    """True when a client address belongs to our own network."""
    try:
        return str(address) in globalvars.server_network
    except Exception:
        return False


# ---------------------------------------------------------------------------
# file level neutering
# ---------------------------------------------------------------------------

def neuter_file_data(data, depot_id, filename, islan):
    """
    Run the existing neuter machinery over a reassembled file.

    Reuses readchunk_neuter, so a Steam3 depot is neutered by exactly the same
    rules (and the same custom neuter configs) as a Steam2 storage.
    """
    from utilities.neuter import readchunk_neuter

    previous = getattr(globalvars, 'CURRENT_APPID_VERSION', '')
    globalvars.CURRENT_APPID_VERSION = "Depot %u %s: " % (depot_id, filename)

    try:
        return readchunk_neuter(data, depot_id, islan, False)
    finally:
        globalvars.CURRENT_APPID_VERSION = previous


def _max_replacement_span(depot_id, islan):
    """
    The longest span of bytes any replacement rule can touch from the point it
    matches, which is how much of the neighbouring chunks has to be visible for
    a replacement that straddles a chunk boundary to be found.
    """
    from utilities.custom_neutering import parse_json
    from utilities.neuter import ips_to_replace

    span = MIN_WINDOW_OVERLAP

    for group in (globalvars.replace_string(islan),
                  globalvars.replace_string_name_space(islan, False),
                  globalvars.replace_string_name(islan, False)):
        for entry in group:
            span = max(span, len(entry[0]))

    for search in ips_to_replace:
        span = max(span, len(search))

    for search in globalvars.ip_addresses:
        span = max(span, len(search), 16)

    custom = parse_json("storage", str(depot_id))
    if custom:
        for rep in custom[1]:
            try:
                search = rep["_search_bytes"][islan]
                replace = rep["_replace_bytes"][islan]
            except (KeyError, TypeError, IndexError):
                continue

            reach = len(search)
            start = rep.get("start_position_from_found_bytes")
            if start is not None:
                reach = max(reach, int(start) + len(replace))
            span = max(span, reach)

    return min(span, MAX_WINDOW_OVERLAP)


def _iter_file_chunks(repository, depot_id, entry, islan, overlap):
    """
    Walk a manifest entry chunk by chunk, neutering each one inside a window
    that also holds the tail of the previous chunk and the head of the next one.

    A replacement straddling a boundary is found in both windows, at the same
    offset and against the same original bytes, so each side writes its own half
    of the replacement and the two halves line up. Only one chunk is ever
    emitted per window, which keeps the memory in use down to a few chunks no
    matter how large the file is.

    Yields (chunk, neutered_data, changed).
    """
    depot = repository.get_depot(depot_id)
    if not depot or not depot.chunkstore:
        return

    chunks = sorted(entry.chunks, key = lambda chunk:chunk.offset)

    def read(index):
        if index < 0 or index >= len(chunks):
            return None
        data = depot.chunkstore.get_chunk(chunks[index].sha, depot.key)
        if data is None:
            raise MissingChunkError("Depot %u chunk %s missing"
                                    % (depot_id, chunks[index].sha.hex()))
        return data

    previous = None
    current = read(0)
    following = read(1)

    for index, chunk in enumerate(chunks):
        head = previous[-overlap:] if previous else b''
        tail = following[:overlap] if following else b''

        window = head + current + tail
        neutered = neuter_file_data(window, depot_id, entry.filename, islan)

        if len(neutered) != len(window):
            raise LengthChangedError("%s changed length while neutering (%d -> %d)"
                                     % (entry.filename, len(window), len(neutered)))

        data = neutered[len(head):len(head) + len(current)]

        yield chunk, data, data != current

        # the lookback context must stay the original bytes, so both sides of a
        # boundary match against the same thing
        previous = current
        current = following
        following = read(index + 2)


# ---------------------------------------------------------------------------
# depot neutering
# ---------------------------------------------------------------------------

def neuter_manifest(repository, depot_id, gid, islan, suffix = None):
    """
    Neuter one depot manifest and everything it points at.

    Writes the neutered chunks and the rewritten manifests into the repository
    cache, then returns True when anything was changed, False when the depot
    needed no neutering, and None on error.
    """
    from utilities import encryption

    depot_id = int(depot_id)
    gid = int(gid)

    if suffix is None:
        suffix = suffix_for(islan)

    depot = repository.get_depot(depot_id)
    if not depot:
        return None

    if not depot.key:
        log.error("Encryption key for depot %u not available, cannot neuter it", depot_id)
        return None

    manifest = repository.get_manifest(depot_id, gid, decrypt = True)
    if manifest is None:
        log.error("Depot %u manifest gid %u not available, cannot neuter it", depot_id, gid)
        return None

    if manifest.filenames_encrypted:
        log.error("Depot %u manifest gid %u could not be decrypted, cannot neuter it", depot_id, gid)
        return None

    log.info("Neutering depot %u manifest gid %u%s (%d entries)",
             depot_id, gid, suffix or "", len(manifest.entries))

    modified_files = 0
    modified_chunks = 0

    overlap = _max_replacement_span(depot_id, islan)
    log.debug("Depot %u neuter window overlap : %d bytes", depot_id, overlap)

    for entry in manifest.entries:
        if entry.is_directory or not entry.chunks:
            continue

        content = sha1()
        changed = False

        try:
            # each rewritten chunk is stored as soon as it is produced, so
            # nothing but the current window is ever held in memory
            for chunk, data, chunk_changed in _iter_file_chunks(repository, depot_id, entry, islan, overlap):
                content.update(data)

                if not chunk_changed:
                    continue

                changed = True

                body = zip_compress(data)

                chunk.sha = sha1(data).digest()
                chunk.crc = zlib.adler32(data) & 0xFFFFFFFF
                chunk.cb_compressed = len(body)

                repository.write_neutered_chunk(depot_id, chunk.sha,
                                                _crypto().symmetric_encrypt(body, depot.key), suffix)
                modified_chunks += 1

        except (MissingChunkError, LengthChangedError, OSError) as e:
            # the entry is half rewritten at this point, and serving a manifest
            # with a partially neutered file would install corrupt content, so
            # the whole manifest is abandoned and the original keeps being served
            log.error("Depot %u manifest gid %u%s abandoned, %s failed : %s",
                      depot_id, gid, suffix or "", entry.filename, e)
            return None

        if not changed:
            continue

        modified_files += 1
        entry.sha_content = content.digest()

    if not modified_files:
        log.info("Depot %u manifest gid %u%s needs no neutering", depot_id, gid, suffix or "")
        repository.mark_manifest_unneutered(depot_id, gid, suffix)
        return False

    # rebuild everything the rewritten chunks invalidated
    manifest.unique_chunks = len({chunk.sha for _, chunk in manifest.iter_chunks()})
    manifest.total_compressed_size = sum(chunk.cb_compressed for _, chunk in manifest.iter_chunks())
    manifest.total_size = sum(entry.size for entry in manifest.entries if not entry.is_directory)

    manifest.encrypt_filenames(depot.key)

    for version in (MANIFEST_VERSION_PROTO, MANIFEST_VERSION_DEPRECATED):
        if version == MANIFEST_VERSION_PROTO:
            manifest.sign(encryption.network_key)
        body = manifest.serialize_zipped(version)
        repository.write_neutered_manifest(depot_id, gid, version, body, suffix)

    log.info("Neutered depot %u manifest gid %u%s : %d file(s), %d chunk(s)",
             depot_id, gid, suffix or "", modified_files, modified_chunks)

    return True


def ensure_neutered(repository, depot_id, gid, islan):
    """
    Make sure the neutered variant of a manifest exists, generating it on the
    first request for it. Returns the cache suffix to serve the request with.
    """
    if not is_enabled():
        return ""

    suffix = suffix_for(islan)
    if not suffix:
        return ""

    key = (int(depot_id), int(gid), suffix)

    if repository.is_neuter_generated(*key):
        return suffix

    with _get_lock(key):
        if repository.is_neuter_generated(*key):
            return suffix

        try:
            neuter_manifest(repository, depot_id, gid, islan, suffix)
        except Exception:
            log.error("Error neutering depot %u manifest gid %u%s", depot_id, gid, suffix, exc_info = True)

    return suffix


def neuter_depot(repository, depot_id, gid = None, force = True):
    """
    Pre-generate the neutered content of a depot for both LAN and WAN.

    Entry point for a manual / console driven neuter run, so a depot does not
    have to be neutered while a client waits on the first manifest request.
    With force off, anything already generated is left alone.
    """
    depot = repository.get_depot(depot_id)
    if not depot:
        log.error("Unknown depot %s", depot_id)
        return False

    gids = [int(gid)] if gid is not None else depot.gids
    if not gids:
        log.error("Depot %s has no manifest to neuter", depot_id)
        return False

    ok = True
    for depot_gid in gids:
        for islan in (True, False):
            suffix = suffix_for(islan)
            if not suffix:
                continue
            if not force and repository.is_neuter_generated(depot_id, depot_gid, suffix):
                log.debug("Depot %s manifest gid %s%s already neutered", depot_id, depot_gid, suffix)
                continue
            if neuter_manifest(repository, depot_id, depot_gid, islan, suffix) is None:
                ok = False

    return ok


def neuter_all_depots(repository, force = True):
    """Pre-generate the neutered content of every depot the repository holds."""
    results = {}
    for depot_id in repository.list_depot_ids():
        depot = repository.get_depot(depot_id)
        if not depot or not depot.manifests:
            continue
        results[depot_id] = neuter_depot(repository, depot_id, force = force)
    return results


# ---------------------------------------------------------------------------
# startup and blob change sweep
# ---------------------------------------------------------------------------

_sweep_lock = threading.Lock()
_sweep_running = False


def _run_sweep(blob_changed):
    global _sweep_running

    from utilities.steam3_content import get_repository

    try:
        repository = get_repository()

        if blob_changed:
            # a new blob can bring new depots with it, and invalidates whatever
            # was neutered against the previous one
            repository.reload()
            repository.clear_neutered()
            log.info("Blob changed, regenerating neutered Steam3 content")

        depots = [depot_id for depot_id in repository.list_depot_ids()
                  if repository.get_depot(depot_id) and repository.get_depot(depot_id).manifests]

        if not depots:
            log.debug("No Steam3 depots to neuter")
            return

        log.info("Neutering Steam3 content for %d depot(s)", len(depots))

        # on a plain startup only whatever is missing gets generated, a blob
        # change invalidated everything and has to redo all of it
        results = neuter_all_depots(repository, force = blob_changed)

        failed = [depot_id for depot_id, ok in results.items() if not ok]
        if failed:
            log.error("Steam3 content neutering failed for depot(s) : %s",
                      ", ".join(str(depot_id) for depot_id in failed))

        log.info("Steam3 content neutering complete (%d depot(s))", len(results))

    except Exception:
        log.error("Error while neutering Steam3 content", exc_info = True)
    finally:
        with _sweep_lock:
            _sweep_running = False


def check_content3_neutering(blob_changed = False, background = True):
    """
    Neuter the Steam3 content, at startup and whenever the blob changes.

    Skipped entirely for a blob older than the Steam3 content system, and for a
    startup where everything was already generated this stays a cheap no-op
    because each depot carries a marker in the cache.
    """
    global _sweep_running

    if not is_enabled():
        log.debug("Steam3 content neutering is disabled")
        return False

    if not is_supported_blob():
        log.debug("Blob date %s is older than %s, skipping Steam3 content neutering",
                  get_blob_date() or "unknown", CONTENT3_MIN_BLOB_DATE)
        return False

    with _sweep_lock:
        if _sweep_running:
            log.debug("Steam3 content neutering already running")
            return False
        _sweep_running = True

    if not background:
        _run_sweep(blob_changed)
        return True

    # generating can take a while on a big depot, so it must not hold up startup
    thread = threading.Thread(target = _run_sweep, args = (blob_changed,),
                              name = "Content3Neuter", daemon = True)
    thread.start()

    return True
