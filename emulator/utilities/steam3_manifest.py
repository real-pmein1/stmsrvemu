"""
Steam3 (SteamPipe) depot manifest reader / writer.

Two on-the-wire manifest versions exist and both are still requested by clients
depending on their age, so both are supported here :

    version 4   the deprecated, hand rolled binary format
    version 5   the protobuf format still in use today

Both are transported inside a zip archive holding a single entry, and both are
wrapped in the same "part" framing :

    DWORD   part magic
    ...     part content
    DWORD   part magic / end magic

The filenames inside a manifest are symmetrically encrypted with the depot key
when the manifest is served by a content server, and the client refuses a
manifest that carries no signature, hence encrypt_filenames() /
generate_fake_signature().

Mirrors tinserver's api/steamapi/filesystem/filesystem3/FileSystem3Manifest.cpp
and FileSystem3ManifestEntry.cpp
"""

import base64
import io
import logging
import os
import struct
import zipfile
import zlib
from hashlib import sha1

log = logging.getLogger('MANIFEST3')


def _crypto():
    # imported lazily : steam3's package init brings up the CM database, which
    # must not happen just because a tool wants to read a manifest
    from steam3 import cm_crypto
    return cm_crypto


def _pb():
    from steam3.protobufs import content_manifest_pb2
    return content_manifest_pb2

# ContentManifestPart
PART_DEPRECATED = 0x16349781
PART_METADATA = 0x1F4812BE
PART_PAYLOAD = 0x71F617D0
PART_SIGNATURE = 0x1B81B817
PART_END = 0x32C415AB

MANIFEST_DEPRECATED_FORMAT_VERSION = 4
MANIFEST_DEPRECATED_FLAGS = 0x2A

MANIFEST_VERSION_DEPRECATED = 4
MANIFEST_VERSION_PROTO = 5

SIGNATURE_LENGTH = 0x80

# FileSystem3ManifestEntryFlags
ENTRYFLAG_USERCONFIG = 0x00000001
ENTRYFLAG_VERSIONEDUSERCONFIG = 0x00000002
ENTRYFLAG_GCF2VPK = 0x00000004
ENTRYFLAG_READONLY = 0x00000008
ENTRYFLAG_HIDDEN = 0x00000010
ENTRYFLAG_EXECUTABLE = 0x00000020
ENTRYFLAG_DIRECTORY = 0x00000040
ENTRYFLAG_CUSTOMEXEC = 0x00000080
ENTRYFLAG_INSTALLSCRIPT = 0x00000100
ENTRYFLAG_SYMLINK = 0x00000200


class ManifestError(Exception):
    pass


# ---------------------------------------------------------------------------
# zip container
# ---------------------------------------------------------------------------

def is_zipped(data):
    return len(data) > 2 and data[:2] == b'PK'


def unwrap_manifest(data):
    """Strip the zip container a manifest is transported in."""
    if not is_zipped(data):
        return data

    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        if not names:
            raise ManifestError("Empty manifest archive")
        return archive.read(names[0])


def wrap_manifest(data, entry_name = "z"):
    """Put a serialized manifest back into its zip container."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(entry_name, data)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# path handling
# ---------------------------------------------------------------------------

PATHFORMAT_LINUX = 0x01
PATHFORMAT_WINDOWS = 0x02
PATHFORMAT_ABSOLUTE = 0x04
PATHFORMAT_EXPLICIT_RELATIVE = 0x08
PATHFORMAT_UNKNOWN_ENCRYPTED = 0x10


def get_path_format(path):
    has_slash = '/' in path
    has_counter_slash = '\\' in path
    is_absolute = (has_counter_slash and path[:1] == '\\') or (has_slash and path[:1] == '/')
    is_explicit_relative = path[:2] in ('./', '.\\')

    fmt = 0
    if has_slash:
        fmt |= PATHFORMAT_LINUX
    if has_counter_slash or not has_slash:
        fmt |= PATHFORMAT_WINDOWS
    if is_absolute:
        fmt |= PATHFORMAT_ABSOLUTE
    if is_explicit_relative:
        fmt |= PATHFORMAT_EXPLICIT_RELATIVE

    return fmt


def is_encrypted_path(path):
    # steam appends a \n to an encrypted (base64) path
    return path.endswith('\n')


def entry_sort_key(filename, path_format = 0):
    """
    Steam sorts manifest entries with an unsigned, uppercased byte comparison,
    and compares windows style paths with backslashes.
    """
    if path_format & PATHFORMAT_WINDOWS:
        filename = filename.replace('/', '\\')

    raw = bytearray(filename.encode('utf-8', errors = 'replace'))
    for index, char in enumerate(raw):
        if 0x61 <= char <= 0x7A:  # 'a' - 'z'
            raw[index] = char - 0x20
    return bytes(raw)


# ---------------------------------------------------------------------------
# little endian stream helpers
# ---------------------------------------------------------------------------

class _Reader(object):
    def __init__(self, data, offset = 0):
        self.data = data
        self.offset = offset

    def read(self, count):
        chunk = self.data[self.offset:self.offset + count]
        if len(chunk) != count:
            raise ManifestError("Truncated manifest")
        self.offset += count
        return chunk

    def uint32(self):
        return struct.unpack('<I', self.read(4))[0]

    def uint64(self):
        return struct.unpack('<Q', self.read(8))[0]

    def cstring(self):
        end = self.data.find(b'\x00', self.offset)
        if end < 0:
            raise ManifestError("Unterminated string in manifest")
        value = self.data[self.offset:end]
        self.offset = end + 1
        return value.decode('utf-8', errors = 'replace')

    @property
    def remaining(self):
        return len(self.data) - self.offset


def _size_prefixed(message_bytes):
    return struct.pack('<I', len(message_bytes)) + message_bytes


# ---------------------------------------------------------------------------
# manifest
# ---------------------------------------------------------------------------

class ManifestChunk(object):
    __slots__ = ('sha', 'crc', 'offset', 'cb_original', 'cb_compressed')

    def __init__(self, sha = b'', crc = 0, offset = 0, cb_original = 0, cb_compressed = 0):
        self.sha = sha
        self.crc = crc
        self.offset = offset
        self.cb_original = cb_original
        self.cb_compressed = cb_compressed

    def __repr__(self):
        return "ManifestChunk(sha=%s, offset=%d, size=%d)" % (self.sha.hex(), self.offset, self.cb_original)


class ManifestEntry(object):
    __slots__ = ('filename', 'size', 'flags', 'sha_filename', 'sha_content', 'chunks', 'linktarget')

    def __init__(self):
        self.filename = ''
        self.size = 0
        self.flags = 0
        self.sha_filename = b'\x00' * 20
        self.sha_content = b'\x00' * 20
        self.chunks = []
        self.linktarget = None

    def __repr__(self):
        return "ManifestEntry(%s, size=%d, flags=%08x, chunks=%d)" % (
            self.filename, self.size, self.flags, len(self.chunks))

    @property
    def is_directory(self):
        return (self.flags & ENTRYFLAG_DIRECTORY) != 0

    @property
    def is_file(self):
        return not self.is_directory

    @property
    def is_encrypted_filename(self):
        return is_encrypted_path(self.filename)


class Steam3Manifest(object):
    """A parsed Steam3 depot manifest, independent of the version it came in."""

    def __init__(self):
        self.depot_id = 0
        self.depot_gid = 0
        self.created_at = 0
        self.filenames_encrypted = False
        self.total_size = 0
        self.total_compressed_size = 0
        self.unique_chunks = 0
        self.crc_encrypted = 0
        self.crc_clear = 0
        self.signature = None
        self.entries = []
        self.path_format = 0
        self.source_version = MANIFEST_VERSION_PROTO

    def __repr__(self):
        return ("Steam3Manifest(depot=%d, gid=%d, entries=%d, encrypted=%s, version=%d)"
                % (self.depot_id, self.depot_gid, len(self.entries), self.filenames_encrypted, self.source_version))

    # -- parsing ------------------------------------------------------------

    @classmethod
    def from_bytes(cls, data):
        """Parse a manifest, with or without its zip container."""
        manifest = cls()
        manifest.parse(unwrap_manifest(data))
        return manifest

    @classmethod
    def from_file(cls, path):
        with open(path, 'rb') as f:
            return cls.from_bytes(f.read())

    def parse(self, data):
        reader = _Reader(data)
        part = reader.uint32()

        if part == PART_DEPRECATED:
            self._parse_deprecated(reader)
        elif part == PART_PAYLOAD:
            self._parse_proto(reader)
        else:
            raise ManifestError("Unexpected manifest content type : %08x" % part)

    def _parse_deprecated(self, reader):
        self.source_version = MANIFEST_VERSION_DEPRECATED

        format_version = reader.uint32()
        if format_version != MANIFEST_DEPRECATED_FORMAT_VERSION:
            raise ManifestError("Unknown deprecated format version : %u" % format_version)

        self.depot_id = reader.uint32()
        self.depot_gid = reader.uint64()
        self.created_at = reader.uint32()
        self.filenames_encrypted = reader.uint32() != 0
        self.total_size = reader.uint64()
        self.total_compressed_size = reader.uint64()
        self.unique_chunks = reader.uint32()

        entries_count = reader.uint32()
        entries_length = reader.uint32()

        self.crc_encrypted = reader.uint32()
        self.crc_clear = reader.uint32()

        flags = reader.uint32()
        if flags != MANIFEST_DEPRECATED_FLAGS:
            raise ManifestError("Unknown manifest flags #%08x" % flags)

        entries_block = reader.read(entries_length)
        computed_crc = zlib.crc32(entries_block) & 0xFFFFFFFF
        expected_crc = self.crc_encrypted if self.filenames_encrypted else self.crc_clear

        if expected_crc and computed_crc != expected_crc:
            raise ManifestError("Corrupted manifest (crc %08x != %08x)" % (computed_crc, expected_crc))

        entries_reader = _Reader(entries_block)
        for _ in range(entries_count):
            self.entries.append(self._parse_deprecated_entry(entries_reader))

        magic = reader.uint32()
        if magic != PART_DEPRECATED:
            raise ManifestError("Invalid manifest file format")

        self._refresh_path_format()

    @staticmethod
    def _parse_deprecated_entry(reader):
        entry = ManifestEntry()
        entry.filename = reader.cstring()
        entry.size = reader.uint64()
        entry.flags = reader.uint32()
        entry.sha_content = reader.read(20)
        entry.sha_filename = reader.read(20)

        for _ in range(reader.uint32()):
            chunk = ManifestChunk()
            chunk.sha = reader.read(20)
            chunk.crc = reader.uint32()
            chunk.offset = reader.uint64()
            chunk.cb_original = reader.uint32()
            chunk.cb_compressed = reader.uint32()
            entry.chunks.append(chunk)

        return entry

    def _parse_proto(self, reader):
        self.source_version = MANIFEST_VERSION_PROTO

        payload = _pb().ContentManifestPayload()
        payload_bytes = reader.read(reader.uint32())
        payload.ParseFromString(payload_bytes)

        part = reader.uint32()
        if part != PART_METADATA:
            raise ManifestError("Unexpected manifest content type : %08x" % part)

        metadata = _pb().ContentManifestMetadata()
        metadata.ParseFromString(reader.read(reader.uint32()))

        signature = _pb().ContentManifestSignature()
        part = reader.uint32()
        if part == PART_SIGNATURE:
            signature.ParseFromString(reader.read(reader.uint32()))
            part = reader.uint32()

        if part != PART_END:
            raise ManifestError("Unexpected manifest content type : %08x" % part)

        computed_crc = zlib.crc32(_size_prefixed(payload_bytes)) & 0xFFFFFFFF
        expected_crc = metadata.crc_encrypted if metadata.filenames_encrypted else metadata.crc_clear
        if expected_crc and computed_crc != expected_crc:
            log.warning("Depot %u manifest %u crc mismatch (%08x != %08x)",
                        metadata.depot_id, metadata.gid_manifest, computed_crc, expected_crc)

        self.depot_id = metadata.depot_id
        self.depot_gid = metadata.gid_manifest
        self.created_at = metadata.creation_time
        self.filenames_encrypted = metadata.filenames_encrypted
        self.total_size = metadata.cb_disk_original
        self.total_compressed_size = metadata.cb_disk_compressed
        self.unique_chunks = metadata.unique_chunks
        self.crc_encrypted = metadata.crc_encrypted
        self.crc_clear = metadata.crc_clear

        if signature.HasField('signature') and signature.signature:
            self.signature = signature.signature

        for mapping in payload.mappings:
            entry = ManifestEntry()
            entry.filename = mapping.filename
            entry.size = mapping.size
            entry.flags = mapping.flags
            entry.sha_filename = mapping.sha_filename
            entry.sha_content = mapping.sha_content
            if mapping.HasField('linktarget'):
                entry.linktarget = mapping.linktarget

            for chunk_data in mapping.chunks:
                chunk = ManifestChunk()
                chunk.sha = chunk_data.sha
                chunk.crc = chunk_data.crc
                chunk.offset = chunk_data.offset
                chunk.cb_original = chunk_data.cb_original
                chunk.cb_compressed = chunk_data.cb_compressed
                entry.chunks.append(chunk)

            self.entries.append(entry)

        self._refresh_path_format()

    def _refresh_path_format(self):
        if self.filenames_encrypted:
            self.path_format = PATHFORMAT_UNKNOWN_ENCRYPTED
            return

        fmt = 0
        for entry in self.entries:
            fmt |= get_path_format(entry.filename)
        self.path_format = fmt

    # -- serializing --------------------------------------------------------

    def _build_payload(self):
        payload = _pb().ContentManifestPayload()
        for entry in self.entries:
            mapping = payload.mappings.add()
            mapping.filename = entry.filename
            mapping.size = entry.size
            mapping.flags = entry.flags
            mapping.sha_filename = entry.sha_filename
            mapping.sha_content = entry.sha_content
            if entry.linktarget is not None:
                mapping.linktarget = entry.linktarget
            for chunk in entry.chunks:
                chunk_data = mapping.chunks.add()
                chunk_data.sha = chunk.sha
                chunk_data.crc = chunk.crc
                chunk_data.offset = chunk.offset
                chunk_data.cb_original = chunk.cb_original
                chunk_data.cb_compressed = chunk.cb_compressed
        return payload

    def compute_crc(self):
        """CRC of the size prefixed payload, the way the proto format wants it."""
        return zlib.crc32(_size_prefixed(self._build_payload().SerializeToString())) & 0xFFFFFFFF

    def _build_metadata(self):
        metadata = _pb().ContentManifestMetadata()
        metadata.depot_id = self.depot_id
        metadata.gid_manifest = self.depot_gid
        metadata.creation_time = self.created_at
        metadata.filenames_encrypted = self.filenames_encrypted
        metadata.cb_disk_original = self.total_size
        metadata.cb_disk_compressed = self.total_compressed_size
        metadata.unique_chunks = self.unique_chunks
        metadata.crc_encrypted = self.crc_encrypted
        metadata.crc_clear = self.crc_clear
        return metadata

    def get_signed_data(self):
        """
        The bytes covered by the manifest signature : everything in the
        container up to, but not including, the signature part.

        Recovered from a genuine valve signed manifest : the signature is
        RSA PKCS#1 v1.5 over the SHA1 of this range.
        """
        out = io.BytesIO()
        out.write(struct.pack('<I', PART_PAYLOAD))
        out.write(_size_prefixed(self._build_payload().SerializeToString()))
        out.write(struct.pack('<I', PART_METADATA))
        out.write(_size_prefixed(self._build_metadata().SerializeToString()))
        return out.getvalue()

    def serialize_proto(self):
        """Serialize as a version 5 (protobuf) manifest."""
        signature = _pb().ContentManifestSignature()
        if self.signature:
            signature.signature = self.signature

        out = io.BytesIO()
        out.write(self.get_signed_data())
        out.write(struct.pack('<I', PART_SIGNATURE))
        out.write(_size_prefixed(signature.SerializeToString()))
        out.write(struct.pack('<I', PART_END))

        return out.getvalue()

    def serialize_deprecated(self):
        """Serialize as a version 4 (pre protobuf) manifest."""
        entries_block = io.BytesIO()
        for entry in self.entries:
            entries_block.write(entry.filename.encode('utf-8') + b'\x00')
            entries_block.write(struct.pack('<QI', entry.size, entry.flags))
            entries_block.write(entry.sha_content)
            entries_block.write(entry.sha_filename)
            entries_block.write(struct.pack('<I', len(entry.chunks)))
            for chunk in entry.chunks:
                entries_block.write(chunk.sha)
                entries_block.write(struct.pack('<IQII', chunk.crc, chunk.offset,
                                                chunk.cb_original, chunk.cb_compressed))

        entries_bytes = entries_block.getvalue()
        entries_crc = zlib.crc32(entries_bytes) & 0xFFFFFFFF

        crc_encrypted = entries_crc if self.filenames_encrypted else self.crc_encrypted
        crc_clear = self.crc_clear if self.filenames_encrypted else entries_crc

        out = io.BytesIO()
        out.write(struct.pack('<II', PART_DEPRECATED, MANIFEST_DEPRECATED_FORMAT_VERSION))
        out.write(struct.pack('<IQI', self.depot_id, self.depot_gid, self.created_at))
        out.write(struct.pack('<I', 1 if self.filenames_encrypted else 0))
        out.write(struct.pack('<QQ', self.total_size, self.total_compressed_size))
        out.write(struct.pack('<I', self.unique_chunks))
        out.write(struct.pack('<II', len(self.entries), len(entries_bytes)))
        out.write(struct.pack('<II', crc_encrypted, crc_clear))
        out.write(struct.pack('<I', MANIFEST_DEPRECATED_FLAGS))
        out.write(entries_bytes)
        out.write(struct.pack('<I', PART_DEPRECATED))

        return out.getvalue()

    def serialize(self, version = MANIFEST_VERSION_PROTO):
        if int(version) == MANIFEST_VERSION_DEPRECATED:
            return self.serialize_deprecated()
        return self.serialize_proto()

    def serialize_zipped(self, version = MANIFEST_VERSION_PROTO, entry_name = "z"):
        """Serialize into the exact body a content server returns."""
        return wrap_manifest(self.serialize(version), entry_name)

    # -- filenames ----------------------------------------------------------

    def encrypt_filenames(self, depot_key):
        """Encrypt every filename with the depot key, as a content server does."""
        if self.filenames_encrypted:
            return

        for entry in self.entries:
            if entry.filename:
                plain = to_proto_path(entry.filename, self.path_format).encode('utf-8') + b'\x00'
                encrypted = _crypto().symmetric_encrypt(plain, depot_key)
                entry.filename = base64.b64encode(encrypted).decode('ascii') + '\n'

            if entry.linktarget:
                plain = entry.linktarget.encode('utf-8') + b'\x00'
                encrypted = _crypto().symmetric_encrypt(plain, depot_key)
                entry.linktarget = base64.b64encode(encrypted).decode('ascii') + '\n'

        self.entries.sort(key = lambda e:entry_sort_key(e.filename))

        self.filenames_encrypted = True
        self.crc_clear = 0
        self.crc_encrypted = self.compute_crc()

    def decrypt_filenames(self, depot_key):
        """Decrypt every filename with the depot key. Returns True on success."""
        if not self.filenames_encrypted:
            return True

        for entry in self.entries:
            if entry.filename:
                encrypted = base64.b64decode(entry.filename.strip())
                if len(encrypted) < 32 or len(encrypted) % 16:
                    # not a valid encrypted length, assumed to be already decrypted
                    return True
                decrypted = _crypto().symmetric_decrypt(encrypted, depot_key)
                if decrypted.endswith(b'\x00'):
                    decrypted = decrypted[:-1]
                entry.filename = from_proto_path(decrypted.decode('utf-8', errors = 'replace'))

            if entry.linktarget:
                encrypted = base64.b64decode(entry.linktarget.strip())
                if len(encrypted) >= 32 and not len(encrypted) % 16:
                    decrypted = _crypto().symmetric_decrypt(encrypted, depot_key)
                    if decrypted.endswith(b'\x00'):
                        decrypted = decrypted[:-1]
                    entry.linktarget = decrypted.decode('utf-8', errors = 'replace')

        self.filenames_encrypted = False
        self._refresh_path_format()
        self.entries.sort(key = lambda e:entry_sort_key(e.filename, self.path_format))
        self.crc_clear = self.compute_crc()

        return True

    def sign(self, rsa_key = None):
        """
        Sign the manifest so a neutered client accepts it.

        Steam verifies the manifest signature with the content manifest signing
        key that is baked into the client, and the neuter swaps that key for our
        own network key, so a manifest we rewrite can carry a real signature
        rather than the random one tinserver has to fall back on.
        """
        from utilities import encryption

        key = rsa_key or encryption.network_key
        if key is None:
            return self.generate_fake_signature()

        self.signature = encryption.rsa_sign_message(key, self.get_signed_data())
        return self.signature

    def verify_signature(self, rsa_key):
        """
        Check the signature against a public key.

        The signature covers the manifest as it was serialized, so this has to
        be called before decrypt_filenames(), which rewrites the payload.
        """
        from Crypto.Hash import SHA1
        from Crypto.Signature import pkcs1_15

        if not self.signature:
            return False

        try:
            pkcs1_15.new(rsa_key).verify(SHA1.new(self.get_signed_data()), self.signature)
            return True
        except (ValueError, TypeError):
            return False

    def generate_fake_signature(self):
        """
        Fallback for when no signing key is available : steam only validates
        that a signature is present unless it can verify it, so a random one
        gets a manifest accepted by a client whose verification was patched out.
        """
        self.signature = os.urandom(SIGNATURE_LENGTH)
        return self.signature

    def reset_signature(self):
        self.signature = None

    # -- lookups ------------------------------------------------------------

    def iter_chunks(self):
        for entry in self.entries:
            for chunk in entry.chunks:
                yield entry, chunk

    def get_chunk(self, sha):
        for entry in self.entries:
            for chunk in entry.chunks:
                if chunk.sha == sha:
                    return entry, chunk
        return None, None

    def get_entry(self, filename):
        for entry in self.entries:
            if entry.filename == filename:
                return entry
        return None


# ---------------------------------------------------------------------------
# path conversion
# ---------------------------------------------------------------------------

def from_proto_path(proto_path):
    """Turn a manifest path into an absolute, forward slashed path."""
    if is_encrypted_path(proto_path):
        return proto_path

    path_format = get_path_format(proto_path)

    if path_format & PATHFORMAT_EXPLICIT_RELATIVE:
        path = proto_path[1:]
    elif path_format & PATHFORMAT_ABSOLUTE:
        path = proto_path
    else:
        path = '/' + proto_path

    if path_format & PATHFORMAT_WINDOWS:
        path = path.replace('\\', '/')

    return path


def to_proto_path(absolute_path, path_format):
    """Turn an absolute path back into the form the manifest stores it in."""
    if is_encrypted_path(absolute_path):
        return absolute_path

    if path_format & PATHFORMAT_EXPLICIT_RELATIVE:
        path = '.' + absolute_path
    elif path_format & PATHFORMAT_ABSOLUTE:
        path = absolute_path
    else:
        path = absolute_path[1:] if absolute_path.startswith('/') else absolute_path

    if path_format & PATHFORMAT_WINDOWS:
        path = path.replace('/', '\\')

    return path


def filename_sha(filename, linktarget = None):
    """The sha1 steam stores in sha_filename."""
    digest = sha1()
    digest.update(filename.lower().encode('utf-8'))
    if linktarget:
        digest.update(linktarget.lower().encode('utf-8'))
    return digest.digest()
