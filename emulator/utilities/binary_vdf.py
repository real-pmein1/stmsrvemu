"""
Binary KeyValues (VDF) reader and writer.

This is the format the appinfo and packageinfo caches store each entry's payload
in, and the format the client expects those entries back in :

    BYTE    type
    cstr    name
    ...     value, depending on the type
    ...
    BYTE    0x08        end of the current key

Neutering these files cannot be done with a flat byte replacement. A string
value is null terminated, so padding a shortened replacement with nulls ends the
string early and leaves the parser reading the padding as the next type byte,
which corrupts everything after it. Values have to be replaced inside the parsed
tree and the tree written back out, which is what this module exists for.
"""

import logging
import struct
from collections import OrderedDict

log = logging.getLogger('BINVDF')

# KeyValues types
KV_NONE = 0x00  # nested key
KV_STRING = 0x01
KV_INT32 = 0x02
KV_FLOAT32 = 0x03
KV_POINTER = 0x04
KV_WSTRING = 0x05
KV_COLOR = 0x06
KV_UINT64 = 0x07
KV_END = 0x08
KV_INT64 = 0x0A

TEXT_VDF_MARKERS = (b'"', b'{', b'/', b'\r', b'\n', b'\t', b' ')


class BinaryVdfError(Exception):
    pass


class KeyValue(object):
    """One value in a binary KeyValues tree."""

    __slots__ = ('type', 'name', 'value')

    def __init__(self, kv_type, name, value):
        self.type = kv_type
        self.name = name
        self.value = value

    def __repr__(self):
        if self.type == KV_NONE:
            return "KeyValue(%r, %d children)" % (self.name, len(self.value))
        return "KeyValue(%r, %r)" % (self.name, self.value)

    @property
    def is_key(self):
        return self.type == KV_NONE

    def get(self, name, default = None):
        """Look up a child by name, case insensitively as steam does."""
        if not self.is_key:
            return default

        wanted = name.lower() if isinstance(name, str) else name.decode('latin-1').lower()
        for child in self.value:
            child_name = child.name.lower() if isinstance(child.name, str) else child.name
            if child_name == wanted:
                return child

        return default

    def walk(self):
        """Yield every KeyValue in this subtree, depth first."""
        yield self
        if self.is_key:
            for child in self.value:
                for item in child.walk():
                    yield item


def looks_like_text_vdf(data):
    """True when the buffer holds a text VDF rather than a binary one."""
    head = data[:1]
    return head in TEXT_VDF_MARKERS


# ---------------------------------------------------------------------------
# reading
# ---------------------------------------------------------------------------

def _read_cstring(data, offset):
    end = data.find(b'\x00', offset)
    if end < 0:
        raise BinaryVdfError("Unterminated string at %d" % offset)
    return data[offset:end], end + 1


def _read_wstring(data, offset):
    end = offset
    while True:
        if end + 2 > len(data):
            raise BinaryVdfError("Unterminated wide string at %d" % offset)
        if data[end:end + 2] == b'\x00\x00':
            break
        end += 2
    return data[offset:end], end + 2


def read_keyvalues(data, offset = 0):
    """
    Read one binary KeyValues block.

    Returns (list of KeyValue, offset just past the block's 0x08 terminator).
    """
    entries = []

    while True:
        if offset >= len(data):
            raise BinaryVdfError("Truncated KeyValues at %d" % offset)

        kv_type = data[offset]
        offset += 1

        if kv_type == KV_END:
            return entries, offset

        name, offset = _read_cstring(data, offset)

        if kv_type == KV_NONE:
            children, offset = read_keyvalues(data, offset)
            entries.append(KeyValue(kv_type, name, children))
        elif kv_type == KV_STRING:
            value, offset = _read_cstring(data, offset)
            entries.append(KeyValue(kv_type, name, value))
        elif kv_type == KV_WSTRING:
            value, offset = _read_wstring(data, offset)
            entries.append(KeyValue(kv_type, name, value))
        elif kv_type in (KV_INT32, KV_POINTER, KV_COLOR):
            width = 3 if kv_type == KV_COLOR else 4
            entries.append(KeyValue(kv_type, name, data[offset:offset + width]))
            offset += width
        elif kv_type == KV_FLOAT32:
            entries.append(KeyValue(kv_type, name, data[offset:offset + 4]))
            offset += 4
        elif kv_type in (KV_UINT64, KV_INT64):
            entries.append(KeyValue(kv_type, name, data[offset:offset + 8]))
            offset += 8
        else:
            raise BinaryVdfError("Unknown KeyValues type 0x%02x at %d" % (kv_type, offset - 1))


def skip_keyvalues(data, offset = 0):
    """Walk past a binary KeyValues block without building the tree."""
    depth = 0

    while True:
        if offset >= len(data):
            raise BinaryVdfError("Truncated KeyValues at %d" % offset)

        kv_type = data[offset]
        offset += 1

        if kv_type == KV_END:
            if depth == 0:
                return offset
            depth -= 1
            continue

        offset = data.find(b'\x00', offset) + 1
        if offset <= 0:
            raise BinaryVdfError("Unterminated name")

        if kv_type == KV_NONE:
            depth += 1
        elif kv_type == KV_STRING:
            offset = data.find(b'\x00', offset) + 1
            if offset <= 0:
                raise BinaryVdfError("Unterminated string")
        elif kv_type == KV_WSTRING:
            _, offset = _read_wstring(data, offset)
        elif kv_type == KV_COLOR:
            offset += 3
        elif kv_type in (KV_INT32, KV_POINTER, KV_FLOAT32):
            offset += 4
        elif kv_type in (KV_UINT64, KV_INT64):
            offset += 8
        else:
            raise BinaryVdfError("Unknown KeyValues type 0x%02x at %d" % (kv_type, offset - 1))


# ---------------------------------------------------------------------------
# writing
# ---------------------------------------------------------------------------

def write_keyvalues(entries):
    """Serialize a list of KeyValue back into a binary KeyValues block."""
    out = bytearray()

    for entry in entries:
        out.append(entry.type)
        out += entry.name
        out.append(0)

        if entry.type == KV_NONE:
            out += write_keyvalues(entry.value)
        elif entry.type == KV_STRING:
            out += entry.value
            out.append(0)
        elif entry.type == KV_WSTRING:
            out += entry.value
            out += b'\x00\x00'
        else:
            out += entry.value

    out.append(KV_END)

    return bytes(out)


def to_dict(entries):
    """Turn a KeyValue list into nested dicts, for inspection and tooling."""
    result = OrderedDict()

    for entry in entries:
        name = entry.name.decode('latin-1', errors = 'replace')
        if entry.type == KV_NONE:
            result[name] = to_dict(entry.value)
        elif entry.type == KV_STRING:
            result[name] = entry.value.decode('latin-1', errors = 'replace')
        elif entry.type == KV_INT32:
            result[name] = struct.unpack('<i', entry.value)[0]
        elif entry.type == KV_FLOAT32:
            result[name] = struct.unpack('<f', entry.value)[0]
        elif entry.type in (KV_UINT64, KV_INT64):
            result[name] = struct.unpack('<Q', entry.value)[0]
        else:
            result[name] = entry.value

    return result
