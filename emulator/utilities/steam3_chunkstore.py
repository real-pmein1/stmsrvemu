"""
Steam3 (SteamPipe) chunk store reader - ".csm" / ".csd" file pairs.

A chunk store is the on-disk container that Steam uses for depot content in the
Steam3 content system.  It is split in two files :

    <name>.csm      chunk store manifest (index)
    <name>.csd      chunk store data (payload)

CSM layout (all little endian) :

    DWORD   magic               'SCFS' (0x53464353)
    DWORD   headerSize          always 0x14
    DWORD   format              2 = backup (clear), 3 = retail (encrypted)
    DWORD   depotId
    DWORD   uniqueChunksCount
    uniqueChunksCount * {
        BYTE[20]    chunkSHA
        ULONGLONG   chunkOffset             offset inside the .csd
        DWORD       chunkSize               uncompressed size (may be 0/unknown)
        DWORD       chunkCompressedSize     number of bytes stored in the .csd
    }

The payload stored in the .csd at chunkOffset is, for :

    format 2 (backup)   'PK' zip or 'VZ' vzip compressed chunk data
    format 3 (retail)   the above, symmetrically encrypted with the depot key

Which means a retail chunk store already holds the exact byte stream a Steam3
content server has to hand back to a client, and can be streamed straight
through without ever touching the depot key.

Mirrors tinserver's api/steamapi/archives/steaminstaller/ChunkStore.cpp
"""

import logging
import lzma
import os
import re
import struct
import threading
import zipfile
from io import BytesIO

log = logging.getLogger('CSTORE')


def _crypto():
    # imported lazily : steam3's package init brings up the CM database, which
    # must not happen just because a tool wants to read a chunk store
    from steam3 import cm_crypto
    return cm_crypto

CHUNKSTORE_MAGIC = 0x53464353  # 'SCFS'
CHUNKSTORE_HEADER_SIZE = 0x14

CHUNKSTORE_FORMAT_BACKUP = 2  # chunk payload stored in the clear
CHUNKSTORE_FORMAT_RETAIL = 3  # chunk payload encrypted with the depot key

# entry: sha(20) + offset(8) + size(4) + compressed size(4)
_CHUNK_ENTRY = struct.Struct('<20sQII')

# "92_depotcache_1.csm", "228983_depotcache_2.csm", ...
_CSM_NAME_RE = re.compile(r'^(?P<depot>\d+)_depotcache(?:_(?P<part>\d+))?\.csm$', re.IGNORECASE)


class ChunkStoreError(Exception):
    pass


class ChunkEntry(object):
    """A single chunk as described by the chunk store manifest."""

    __slots__ = ('sha', 'offset', 'size', 'compressed_size')

    def __init__(self, sha, offset, size, compressed_size):
        self.sha = sha
        self.offset = offset
        self.size = size
        self.compressed_size = compressed_size

    def __repr__(self):
        return ("ChunkEntry(sha=%s, offset=%d, size=%d, compressed_size=%d)"
                % (self.sha.hex(), self.offset, self.size, self.compressed_size))


def is_vzip(data):
    return len(data) > 2 and data[:2] == b'VZ'


def is_zip(data):
    return len(data) > 2 and data[:2] == b'PK'


def vzip_decompress(data):
    """Decompress a Valve 'VZ' (LZMA1) compressed chunk."""
    if not is_vzip(data):
        raise ChunkStoreError("Not vzip data")
    if data[-2:] != b'zv':
        raise ChunkStoreError("Invalid vzip footer")

    # 'VZ' + version byte + uint32 timestamp/crc + 5 bytes lzma properties
    properties = data[7:12]
    checksum, decompressed_size = struct.unpack('<II', data[-10:-2])

    filters = [lzma._decode_filter_properties(lzma.FILTER_LZMA1, properties)]
    decompressor = lzma.LZMADecompressor(lzma.FORMAT_RAW, filters = filters)
    decompressed = decompressor.decompress(data[12:-10], max_length = decompressed_size)

    if len(decompressed) != decompressed_size:
        raise ChunkStoreError("vzip size mismatch (%d != %d)" % (len(decompressed), decompressed_size))

    return decompressed


def zip_decompress(data):
    """Decompress a 'PK' zipped chunk (single entry archive)."""
    with zipfile.ZipFile(BytesIO(data)) as archive:
        names = archive.namelist()
        if not names:
            raise ChunkStoreError("Empty zip chunk")
        return archive.read(names[0])


def decompress_chunk(data):
    """Decompress a chunk payload, whichever container Valve used for it."""
    if is_vzip(data):
        return vzip_decompress(data)
    if is_zip(data):
        return zip_decompress(data)
    raise ChunkStoreError("Unknown chunk data format : %s" % data[:2].hex())


def zip_compress(data, entry_name = "z"):
    """Wrap raw chunk data the way a content server does before encrypting."""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(entry_name, data)
    return buffer.getvalue()


class ChunkStore(object):
    """A single .csm/.csd pair."""

    def __init__(self, csm_path, csd_path = None):
        self.csm_path = csm_path
        self.csd_path = csd_path or find_matching_data_file(csm_path)

        self.depot_id = 0
        self.format = 0
        self.chunk_count = 0
        self.chunks = {}  # bytes(sha20) -> ChunkEntry

        self._lock = threading.Lock()

        self._parse()

    def __repr__(self):
        return ("ChunkStore(depot=%d, format=%d, chunks=%d, file=%s)"
                % (self.depot_id, self.format, self.chunk_count, os.path.basename(self.csm_path)))

    # -- parsing ------------------------------------------------------------

    def _parse(self):
        if not os.path.isfile(self.csm_path):
            raise ChunkStoreError("Chunk store manifest not found : %s" % self.csm_path)
        if not os.path.isfile(self.csd_path):
            raise ChunkStoreError("Chunk store data not found : %s" % self.csd_path)

        with open(self.csm_path, 'rb') as f:
            header = f.read(CHUNKSTORE_HEADER_SIZE)
            if len(header) < CHUNKSTORE_HEADER_SIZE:
                raise ChunkStoreError("Truncated chunk store manifest : %s" % self.csm_path)

            magic, header_size, fmt, depot_id, chunk_count = struct.unpack('<IIIII', header)

            if magic != CHUNKSTORE_MAGIC:
                raise ChunkStoreError("Invalid chunk store manifest : %s" % self.csm_path)
            if header_size != CHUNKSTORE_HEADER_SIZE:
                raise ChunkStoreError("Invalid chunk store manifest header size : %08x" % header_size)
            if fmt not in (CHUNKSTORE_FORMAT_BACKUP, CHUNKSTORE_FORMAT_RETAIL):
                raise ChunkStoreError("Unknown chunk store manifest format : %08x" % fmt)

            self.format = fmt
            self.depot_id = depot_id
            self.chunk_count = chunk_count

            index = f.read(chunk_count * _CHUNK_ENTRY.size)
            if len(index) < chunk_count * _CHUNK_ENTRY.size:
                raise ChunkStoreError("Truncated chunk store index : %s" % self.csm_path)

        for offset in range(0, chunk_count * _CHUNK_ENTRY.size, _CHUNK_ENTRY.size):
            sha, chunk_offset, size, compressed_size = _CHUNK_ENTRY.unpack_from(index, offset)
            self.chunks[sha] = ChunkEntry(sha, chunk_offset, size, compressed_size)

        log.debug("Loaded chunk store %s", self)

    # -- lookups ------------------------------------------------------------

    @property
    def is_encrypted(self):
        return self.format == CHUNKSTORE_FORMAT_RETAIL

    def has_chunk(self, sha):
        return sha in self.chunks

    def get_chunk_entry(self, sha):
        return self.chunks.get(sha)

    def iter_chunk_shas(self):
        return iter(self.chunks.keys())

    # -- data ---------------------------------------------------------------

    def read_stored_chunk(self, sha):
        """Return the chunk bytes exactly as they are stored inside the .csd."""
        entry = self.chunks.get(sha)
        if entry is None:
            return None

        with self._lock:
            with open(self.csd_path, 'rb') as f:
                f.seek(entry.offset)
                data = f.read(entry.compressed_size)

        if len(data) != entry.compressed_size:
            raise ChunkStoreError("Truncated chunk %s in %s" % (sha.hex(), self.csd_path))

        return data

    def get_transport_chunk(self, sha, depot_key = None):
        """
        Return the chunk in the form a Steam3 content server sends it :
        symmetrically encrypted (with the depot key) compressed chunk data.

        A retail chunk store is already stored in that exact form, so no key is
        needed and the bytes are passed straight through.
        """
        data = self.read_stored_chunk(sha)
        if data is None:
            return None

        if self.is_encrypted:
            return data

        if not depot_key:
            raise ChunkStoreError("Depot %u key required to serve a backup format chunk store" % self.depot_id)

        return _crypto().symmetric_encrypt(data, depot_key)

    def get_compressed_chunk(self, sha, depot_key = None):
        """Return the decrypted, still compressed ('PK'/'VZ') chunk data."""
        data = self.read_stored_chunk(sha)
        if data is None:
            return None

        if self.is_encrypted:
            if not depot_key:
                raise ChunkStoreError("Depot %u key required to decrypt chunk store" % self.depot_id)
            data = _crypto().symmetric_decrypt(data, depot_key)

        return data

    def get_chunk(self, sha, depot_key = None):
        """Return the fully decrypted and decompressed chunk data."""
        data = self.get_compressed_chunk(sha, depot_key)
        if data is None:
            return None
        return decompress_chunk(data)


class DepotChunkStore(object):
    """
    All chunk store parts belonging to a single depot.

    Steam splits large depots over several numbered parts
    ("<depot>_depotcache_1.csd", "<depot>_depotcache_2.csd", ...); this groups
    them behind one lookup so callers only deal with a depot id.
    """

    def __init__(self, depot_id):
        self.depot_id = depot_id
        self.stores = []
        self._index = {}  # bytes(sha20) -> ChunkStore

    def __repr__(self):
        return "DepotChunkStore(depot=%d, parts=%d, chunks=%d)" % (self.depot_id, len(self.stores), len(self._index))

    def add_store(self, store):
        if store.depot_id != self.depot_id:
            raise ChunkStoreError("Chunk store depot mismatch : %u != %u" % (store.depot_id, self.depot_id))

        self.stores.append(store)
        for sha in store.iter_chunk_shas():
            # first part wins, matching the way steam reads its own caches
            self._index.setdefault(sha, store)

    @property
    def chunk_count(self):
        return len(self._index)

    def has_chunk(self, sha):
        return sha in self._index

    def iter_chunk_shas(self):
        return iter(self._index.keys())

    def get_chunk_entry(self, sha):
        store = self._index.get(sha)
        return store.get_chunk_entry(sha) if store else None

    def get_transport_chunk(self, sha, depot_key = None):
        store = self._index.get(sha)
        return store.get_transport_chunk(sha, depot_key) if store else None

    def get_compressed_chunk(self, sha, depot_key = None):
        store = self._index.get(sha)
        return store.get_compressed_chunk(sha, depot_key) if store else None

    def get_chunk(self, sha, depot_key = None):
        store = self._index.get(sha)
        return store.get_chunk(sha, depot_key) if store else None


def find_matching_data_file(csm_path):
    """
    Locate the .csd matching a .csm, tolerating any letter case (file names are
    case sensitive on linux and not on windows).
    """
    stem = os.path.splitext(csm_path)[0]

    for candidate in (stem + '.csd', stem + '.CSD'):
        if os.path.isfile(candidate):
            return candidate

    directory = os.path.dirname(csm_path) or '.'
    wanted = os.path.basename(stem).lower() + '.csd'

    if os.path.isdir(directory):
        for name in os.listdir(directory):
            if name.lower() == wanted:
                return os.path.join(directory, name)

    return stem + '.csd'


def list_files_by_extension(directory, extensions):
    """List files in a directory by extension, ignoring letter case."""
    if not os.path.isdir(directory):
        return []

    extensions = tuple(extension.lower() for extension in extensions)

    return sorted(os.path.join(directory, name) for name in os.listdir(directory)
                  if name.lower().endswith(extensions) and os.path.isfile(os.path.join(directory, name)))


def find_chunk_stores(directory):
    """
    Load every .csm/.csd pair found in a directory.

    Returns a dict of depot id -> DepotChunkStore.
    """
    depots = {}

    if not os.path.isdir(directory):
        return depots

    for csm_path in list_files_by_extension(directory, ('.csm',)):
        try:
            store = ChunkStore(csm_path)
        except Exception as e:
            log.error("Unable to load chunk store %s : %s", csm_path, e)
            continue

        depot = depots.get(store.depot_id)
        if depot is None:
            depot = DepotChunkStore(store.depot_id)
            depots[store.depot_id] = depot

        try:
            depot.add_store(store)
        except ChunkStoreError as e:
            log.error("%s", e)

    return depots


def parse_chunkstore_filename(filename):
    """Return (depot_id, part) for a "<depot>_depotcache_<part>.csm" name."""
    match = _CSM_NAME_RE.match(os.path.basename(filename))
    if not match:
        return None, None
    part = match.group('part')
    return int(match.group('depot')), int(part) if part else 1
