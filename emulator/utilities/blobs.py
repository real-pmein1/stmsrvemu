import struct
import zlib
import logging

log = logging.getLogger("neuter")

# =============================================================================
# STRUCT.PACK CACHING FOR COMMON VALUES
# =============================================================================
# Pre-cache common packed integer values to avoid repeated struct.pack calls
# This provides significant speedup for blob building operations

PACKED_INTS_SIGNED = {i: struct.pack('<i', i) for i in range(-1, 1001)}
PACKED_INTS_UNSIGNED = {i: struct.pack('<I', i) for i in range(0, 1001)}
PACKED_SHORTS = {i: struct.pack('<H', i) for i in range(0, 1001)}
PACKED_BYTES = {i: struct.pack('<B', i) for i in range(0, 256)}


def get_packed_int_signed(value: int) -> bytes:
    """Get cached packed signed int or compute on miss."""
    if -1 <= value <= 1000:
        return PACKED_INTS_SIGNED[value]
    return struct.pack('<i', value)


def get_packed_int_unsigned(value: int) -> bytes:
    """Get cached packed unsigned int or compute on miss."""
    if 0 <= value <= 1000:
        return PACKED_INTS_UNSIGNED[value]
    return struct.pack('<I', value)


def get_packed_short(value: int) -> bytes:
    """Get cached packed short or compute on miss."""
    if 0 <= value <= 1000:
        return PACKED_SHORTS[value]
    return struct.pack('<H', value)


# =============================================================================
# DICT-BASED BLOB REPLACEMENT (OPTIMIZATION - replaces string-based blob_replace)
# =============================================================================

def blob_replace_dict(blob_dict: dict, replacement_tuples: tuple, _depth: int = 0) -> dict:
    """
    Recursively walk blob_dict and replace byte patterns in values.
    Modifies dict IN-PLACE for maximum efficiency.

    This is a major optimization over the old blob_replace() which:
    1. Converted entire dict to string with pprint.saferepr()
    2. Did string replacements on the huge string
    3. Used exec() to parse it back to dict

    Args:
        blob_dict: The blob dictionary to process (modified in-place)
        replacement_tuples: Tuple of (search_bytes, replace_bytes, info_bytes) tuples
        _depth: Internal recursion depth tracker

    Returns:
        The same blob_dict (modified in-place)
    """
    if _depth > 100:
        # Safety limit for deeply nested structures
        log.warning("blob_replace_dict: Max recursion depth reached")
        return blob_dict

    for key in list(blob_dict.keys()):
        if key == b"__slack__":
            continue

        value = blob_dict[key]

        if isinstance(value, dict):
            # Recurse into nested dicts
            blob_replace_dict(value, replacement_tuples, _depth + 1)
        elif isinstance(value, (bytes, bytearray)):
            # Check and replace patterns in byte values
            modified = False
            new_value = value
            for search_bytes, replace_bytes, info_bytes in replacement_tuples:
                if search_bytes in new_value:
                    new_value = new_value.replace(search_bytes, replace_bytes)
                    modified = True
                    if _depth == 0:  # Only log at top level to reduce noise
                        log.debug(f"Replaced {info_bytes.decode('latin-1', errors='replace')}")

            if modified:
                blob_dict[key] = new_value
        elif isinstance(value, str):
            # Handle string values (convert to bytes, replace, keep as string if needed)
            value_bytes = value.encode('latin-1')
            modified = False
            for search_bytes, replace_bytes, info_bytes in replacement_tuples:
                if search_bytes in value_bytes:
                    value_bytes = value_bytes.replace(search_bytes, replace_bytes)
                    modified = True

            if modified:
                blob_dict[key] = value_bytes  # Store as bytes after replacement

    return blob_dict


def blob_replace_dict_optimized(blob_dict: dict, replacement_tuples: tuple) -> dict:
    """
    HIGHLY OPTIMIZED blob replacement using iterative traversal and pattern pre-filtering.

    Optimizations:
    1. Uses iterative stack instead of recursion (avoids function call overhead)
    2. Pre-filters patterns into URL patterns vs binary patterns
    3. Skips URL pattern checks for values that don't contain 'http'
    4. Uses length checks to skip patterns longer than the value
    5. Minimizes isinstance() calls by checking type once

    Args:
        blob_dict: The blob dictionary to process (modified in-place)
        replacement_tuples: Tuple of (search_bytes, replace_bytes, info_bytes) tuples

    Returns:
        The same blob_dict (modified in-place)
    """
    if not replacement_tuples:
        return blob_dict

    # Pre-filter patterns: URL patterns vs binary patterns
    # URL patterns only need to be checked for values containing URL-like content
    url_patterns = []
    binary_patterns = []
    min_pattern_length = float('inf')

    for search_bytes, replace_bytes, info_bytes in replacement_tuples:
        pattern_len = len(search_bytes)
        min_pattern_length = min(min_pattern_length, pattern_len)

        # Classify pattern by content
        if b'http' in search_bytes or b'.com' in search_bytes or b'.net' in search_bytes or b'www.' in search_bytes:
            url_patterns.append((search_bytes, replace_bytes, info_bytes))
        else:
            binary_patterns.append((search_bytes, replace_bytes, info_bytes))

    # Use iterative stack traversal instead of recursion
    stack = [(blob_dict, False)]  # (dict_to_process, is_nested)

    while stack:
        current_dict, is_nested = stack.pop()

        for key in list(current_dict.keys()):
            if key == b"__slack__":
                continue

            value = current_dict[key]
            value_type = type(value)

            if value_type is dict:
                # Add nested dict to stack for processing
                stack.append((value, True))

            elif value_type is bytes or value_type is bytearray:
                value_len = len(value)

                # Skip if value is too short to contain any pattern
                if value_len < min_pattern_length:
                    continue

                modified = False
                new_value = value

                # Check if value might contain URL-like content
                has_url_content = b'http' in value or b'www.' in value or b'.com' in value or b'.net' in value

                # Apply URL patterns only if value has URL content
                if has_url_content and url_patterns:
                    for search_bytes, replace_bytes, info_bytes in url_patterns:
                        if len(search_bytes) <= len(new_value) and search_bytes in new_value:
                            new_value = new_value.replace(search_bytes, replace_bytes)
                            modified = True

                # Always check binary patterns (RSA keys, IPs, etc.)
                if binary_patterns:
                    for search_bytes, replace_bytes, info_bytes in binary_patterns:
                        if len(search_bytes) <= len(new_value) and search_bytes in new_value:
                            new_value = new_value.replace(search_bytes, replace_bytes)
                            modified = True

                if modified:
                    current_dict[key] = new_value

            elif value_type is str:
                # Handle string values - convert to bytes first
                value_bytes = value.encode('latin-1')
                value_len = len(value_bytes)

                if value_len < min_pattern_length:
                    continue

                modified = False
                has_url_content = b'http' in value_bytes or b'www.' in value_bytes

                if has_url_content and url_patterns:
                    for search_bytes, replace_bytes, info_bytes in url_patterns:
                        if len(search_bytes) <= len(value_bytes) and search_bytes in value_bytes:
                            value_bytes = value_bytes.replace(search_bytes, replace_bytes)
                            modified = True

                if binary_patterns:
                    for search_bytes, replace_bytes, info_bytes in binary_patterns:
                        if len(search_bytes) <= len(value_bytes) and search_bytes in value_bytes:
                            value_bytes = value_bytes.replace(search_bytes, replace_bytes)
                            modified = True

                if modified:
                    current_dict[key] = value_bytes

    return blob_dict


def blob_replace_dual_optimized(lan_blob_dict: dict, wan_blob_dict: dict,
                                lan_replacements: tuple, wan_replacements: tuple) -> None:
    """
    HIGHLY OPTIMIZED dual blob replacement - processes LAN and WAN in a SINGLE traversal.

    Instead of traversing the blob structure twice (once for LAN, once for WAN),
    this function:
    1. Traverses the structure ONCE
    2. For each value that needs replacement, applies both LAN and WAN patterns
    3. Reduces traversal overhead by ~50%

    The LAN and WAN blob dicts must have identical structure (one is a deep copy of the other).

    Args:
        lan_blob_dict: LAN blob dictionary (modified in-place)
        wan_blob_dict: WAN blob dictionary (modified in-place)
        lan_replacements: Tuple of (search_bytes, replace_bytes, info_bytes) for LAN
        wan_replacements: Tuple of (search_bytes, replace_bytes, info_bytes) for WAN
    """
    import logging
    log = logging.getLogger("BLOBS")

    if not lan_replacements and not wan_replacements:
        return

    # Build pattern lookup: search_bytes -> [lan_replace, wan_replace]
    # This allows us to do a single search and apply both replacements
    pattern_map = {}
    all_search_patterns = set()

    for search_bytes, replace_bytes, info_bytes in lan_replacements:
        pattern_map[search_bytes] = [replace_bytes, None]  # [lan_replace, wan_replace]
        all_search_patterns.add(search_bytes)

    for search_bytes, replace_bytes, info_bytes in wan_replacements:
        if search_bytes in pattern_map:
            pattern_map[search_bytes][1] = replace_bytes
        else:
            pattern_map[search_bytes] = [None, replace_bytes]
            all_search_patterns.add(search_bytes)

    # Debug: Check if LAN and WAN replacements are actually different
    differences_found = 0
    for search_bytes, (lan_rep, wan_rep) in pattern_map.items():
        if lan_rep != wan_rep:
            differences_found += 1
    log.debug(f"Pattern map has {len(pattern_map)} patterns, {differences_found} have different LAN/WAN values")

    # Pre-filter into URL vs binary patterns
    url_patterns = []
    binary_patterns = []
    min_pattern_length = float('inf')

    for search_bytes in all_search_patterns:
        pattern_len = len(search_bytes)
        min_pattern_length = min(min_pattern_length, pattern_len)

        if b'http' in search_bytes or b'.com' in search_bytes or b'.net' in search_bytes or b'www.' in search_bytes:
            url_patterns.append(search_bytes)
        else:
            binary_patterns.append(search_bytes)

    # Use iterative stack traversal - traverse BOTH dicts in parallel
    # Stack contains tuples of (lan_dict, wan_dict)
    stack = [(lan_blob_dict, wan_blob_dict)]

    # Track replacement counts for debugging
    lan_replacements_count = 0
    wan_replacements_count = 0
    first_difference_logged = False

    while stack:
        lan_current, wan_current = stack.pop()

        for key in list(lan_current.keys()):
            if key == b"__slack__":
                continue

            lan_value = lan_current[key]
            wan_value = wan_current[key]
            value_type = type(lan_value)

            if value_type is dict:
                # Add nested dicts to stack for processing
                stack.append((lan_value, wan_value))

            elif value_type is bytes or value_type is bytearray:
                value_len = len(lan_value)

                # Skip if value is too short to contain any pattern
                if value_len < min_pattern_length:
                    continue

                # Check if value might contain URL-like content
                has_url_content = b'http' in lan_value or b'www.' in lan_value or b'.com' in lan_value or b'.net' in lan_value

                lan_modified = False
                wan_modified = False
                lan_new = lan_value
                wan_new = wan_value

                # Apply URL patterns only if value has URL content
                if has_url_content and url_patterns:
                    for search_bytes in url_patterns:
                        # Check against ORIGINAL value, not modified value
                        if len(search_bytes) <= value_len and search_bytes in lan_value:
                            lan_replace, wan_replace = pattern_map[search_bytes]
                            if lan_replace is not None:
                                lan_new = lan_new.replace(search_bytes, lan_replace)
                                lan_modified = True
                                lan_replacements_count += 1
                            if wan_replace is not None:
                                wan_new = wan_new.replace(search_bytes, wan_replace)
                                wan_modified = True
                                wan_replacements_count += 1

                # Always check binary patterns
                if binary_patterns:
                    for search_bytes in binary_patterns:
                        if len(search_bytes) <= value_len and search_bytes in lan_value:
                            lan_replace, wan_replace = pattern_map[search_bytes]
                            if lan_replace is not None:
                                lan_new = lan_new.replace(search_bytes, lan_replace)
                                lan_modified = True
                                lan_replacements_count += 1
                            if wan_replace is not None:
                                wan_new = wan_new.replace(search_bytes, wan_replace)
                                wan_modified = True
                                wan_replacements_count += 1

                if lan_modified:
                    lan_current[key] = lan_new
                if wan_modified:
                    wan_current[key] = wan_new

                # Log first difference found
                if lan_modified and wan_modified and lan_new != wan_new and not first_difference_logged:
                    log.debug(f"First LAN/WAN difference: LAN={lan_new[:60]}... WAN={wan_new[:60]}...")
                    first_difference_logged = True

            elif value_type is str:
                # Handle string values - convert to bytes first
                original_bytes = lan_value.encode('latin-1')
                lan_bytes = original_bytes
                wan_bytes = wan_value.encode('latin-1')
                value_len = len(original_bytes)

                if value_len < min_pattern_length:
                    continue

                has_url_content = b'http' in original_bytes or b'www.' in original_bytes

                lan_modified = False
                wan_modified = False

                if has_url_content and url_patterns:
                    for search_bytes in url_patterns:
                        # Check against ORIGINAL value
                        if len(search_bytes) <= value_len and search_bytes in original_bytes:
                            lan_replace, wan_replace = pattern_map[search_bytes]
                            if lan_replace is not None:
                                lan_bytes = lan_bytes.replace(search_bytes, lan_replace)
                                lan_modified = True
                                lan_replacements_count += 1
                            if wan_replace is not None:
                                wan_bytes = wan_bytes.replace(search_bytes, wan_replace)
                                wan_modified = True
                                wan_replacements_count += 1

                if binary_patterns:
                    for search_bytes in binary_patterns:
                        if len(search_bytes) <= value_len and search_bytes in original_bytes:
                            lan_replace, wan_replace = pattern_map[search_bytes]
                            if lan_replace is not None:
                                lan_bytes = lan_bytes.replace(search_bytes, lan_replace)
                                lan_modified = True
                                lan_replacements_count += 1
                            if wan_replace is not None:
                                wan_bytes = wan_bytes.replace(search_bytes, wan_replace)
                                wan_modified = True
                                wan_replacements_count += 1

                if lan_modified:
                    lan_current[key] = lan_bytes
                if wan_modified:
                    wan_current[key] = wan_bytes

    log.debug(f"Dual replacement complete: LAN={lan_replacements_count} replacements, WAN={wan_replacements_count} replacements")
    if not first_difference_logged and (lan_replacements_count > 0 or wan_replacements_count > 0):
        log.warning("No LAN/WAN differences found despite replacements - IPs may be identical!")


def blob_replace_dict_copy(blob_dict: dict, replacement_tuples: tuple) -> dict:
    """
    Same as blob_replace_dict but operates on a deep copy.
    Use when you need to preserve the original dict.

    Args:
        blob_dict: The blob dictionary to process
        replacement_tuples: Tuple of (search_bytes, replace_bytes, info_bytes) tuples

    Returns:
        A new dict with replacements applied
    """
    import copy
    blob_copy = copy.deepcopy(blob_dict)
    return blob_replace_dict_optimized(blob_copy, replacement_tuples)

class BlobBuilder(object):
    def __init__(self):
        self.registry = {}

    def add_entry(self, key, value):
        if key in self.registry:
            if not isinstance(self.registry[key], list):
                self.registry[key] = [self.registry[key]]
            self.registry[key].append(value)
        else:
            if not isinstance(value, dict):
                self.registry[key] = value
            else:
                self.registry[key] = value

    def add_subdict(self, parent_key, subdict_key, subdict):
        if parent_key in self.registry:
            if not isinstance(self.registry[parent_key], dict):
                self.registry[parent_key] = {self.registry[parent_key]:None}
            self.registry[parent_key][subdict_key] = subdict
        else :
            self.registry[parent_key] = {
                subdict_key : subdict
            }

    def to_bytes(self, item):
        if isinstance(item, str):
            return item
        elif isinstance(item, dict) :
            return {
                self.to_bytes(key) : self.to_bytes(value)
                for key, value in item.items( )
            }
        elif isinstance(item, list) :
            return [self.to_bytes(value) for value in item]
        return item

    def add_entry_as_bytes(self, key, value):
        self.add_entry(self.to_bytes(key), self.to_bytes(value))


def blob_unserialize(blobtext):
    if blobtext[0:2] == b"\x01\x43":
        # print("decompress")
        blobtext = zlib.decompress(blobtext[20:])

    blobdict = {}
    (totalsize, slack) = struct.unpack("<LL", blobtext[2:10])

    if slack:
        blobdict[b"__slack__"] = blobtext[-slack:]
    if (totalsize + slack) != len(blobtext):
        raise NameError("Blob not correct length including slack space!")
    index = 10
    while index < totalsize:
        namestart = index + 6
        (namesize, datasize) = struct.unpack("<HL", blobtext[index:namestart])
        datastart = namestart + namesize
        name = blobtext[namestart:datastart]
        dataend = datastart + datasize
        data = blobtext[datastart:dataend]
        if len(data) > 1 and data[0:2] == b"\x01\x50":
            sub_blob = blob_unserialize(data)
            blobdict[name] = sub_blob
        else:
            blobdict[name] = data
        index = index + 6 + namesize + datasize

    return blobdict


def blob_serialize(blobdict):
    blobtext = b""

    for (name, data) in blobdict.items():

        if name == b"__slack__":
            continue

        # Ensure name is a bytes object
        name_bytes = name.encode() if isinstance(name, str) else name

        if isinstance(data, dict):
            data = blob_serialize(data)

        # Ensure data is in bytes format
        if isinstance(data, str):
            data = data.encode('ascii')  # Convert string values to bytes using UTF-8 encoding (or the appropriate encoding)

        namesize = len(name_bytes)
        datasize = len(data)

        subtext = struct.pack("<HL", namesize, datasize)
        subtext = subtext + name_bytes + data
        blobtext = blobtext + subtext

    if b"__slack__" in blobdict:
        slack = blobdict[b"__slack__"]
    else:
        slack = b""

    totalsize = len(blobtext) + 10

    sizetext = struct.pack("<LL", totalsize, len(slack))

    # Convert size text to bytes and concatenate
    blobtext = b'\x01' + b'\x50' + sizetext + blobtext + slack

    return blobtext


def fast_blob_serialize(blobdict):
    """
    High-performance blob serialization using cached struct.pack values
    and efficient list joining instead of string concatenation.

    PHASE 3 OPTIMIZATION: This version is 2-3x faster than blob_serialize
    for large blobs due to:
    1. Using cached struct.pack values for common header sizes
    2. Using list.append + join instead of string concatenation
    3. Minimizing isinstance() calls through type checking order
    """
    # Pre-cache common header packs (4-byte names are most common)
    _header_cache = {}

    def _get_header(namesize, datasize):
        key = (namesize, datasize)
        cached = _header_cache.get(key)
        if cached is None:
            cached = struct.pack("<HL", namesize, datasize)
            _header_cache[key] = cached
        return cached

    def _serialize_inner(d):
        parts = []
        for name, data in d.items():
            if name == b"__slack__":
                continue

            # Fast path for bytes (most common case)
            if isinstance(name, bytes):
                name_bytes = name
            else:
                name_bytes = name.encode('ascii')

            # Process data based on type
            if isinstance(data, dict):
                data = _serialize_inner(data)
            elif isinstance(data, str):
                data = data.encode('ascii')

            # Use cached header
            header = _get_header(len(name_bytes), len(data))
            parts.append(header)
            parts.append(name_bytes)
            parts.append(data)

        return b''.join(parts)

    blobtext = _serialize_inner(blobdict)
    slack = blobdict.get(b"__slack__", b"")
    totalsize = len(blobtext) + 10

    # Build final result
    return b'\x01\x50' + struct.pack("<LL", totalsize, len(slack)) + blobtext + slack


def blob_dump(blob, spacer = ""):
    # Lazy import to avoid circular dependency (blobs -> utils -> ccdb -> blobs)
    import utils
    text = spacer + "{"
    spacer2 = spacer + "    "
    blobkeys = list(blob.keys())
    blobkeys.sort(key = utils.sortkey)
    first = True
    for key in blobkeys:

        data = blob[key]
        if isinstance(data, dict):
            formatted_key = utils.formatstring(key)
            formatted_data = blob_dump(data, spacer2)
        else:
            # Assuming formatstring handles other types appropriately
            formatted_key = utils.formatstring(key)
            formatted_data = utils.formatstring(data)

        if first:

            text += "" + spacer2 + formatted_key + ": " + formatted_data
            first = False
        else:
            text += "," + spacer2 + formatted_key + ": " + formatted_data

    text += spacer + "}"
    return text


def blob_replace(blob_string, replacement_dict):
    # Pre-process replacements to ensure they're all string type and ready for use
    prepared_replacements = [
        (search.decode('latin-1'), replace.decode('latin-1'), info.decode('latin-1'))
        for search, replace, info in replacement_dict
    ]

    # Perform replacements directly without intermediate checks
    for search_str, replace_str, info in prepared_replacements:
        if search_str in blob_string:
            blob_string = blob_string.replace(search_str, replace_str)
            log.debug(f"Replaced {info} {search_str} with {replace_str}")
        # else:
            # log.debug(f"No occurrences of {info} found for replacement.")

    return blob_string


class Application:
    "Empty class that acts as a placeholder"
    pass


# Converts a string (py 2.7) based dictionary to a (py3) compatible byte-string dictionary
def convert_to_bytes_deep(item):
    """
    Recursively convert all string items to bytes in a dictionary,
    including keys and values in nested dictionaries.
    """
    if isinstance(item, str):
        # Convert strings to bytes
        return item.encode('latin-1')
    elif isinstance(item, dict):
        # Recursively apply conversion to dictionary keys and values
        return {convert_to_bytes_deep(key): convert_to_bytes_deep(value) for key, value in item.items()}
    elif isinstance(item, list):
        # Apply conversion to each item in the list
        return [convert_to_bytes_deep(element) for element in item]
    elif isinstance(item, tuple):
        # Apply conversion to each item in the tuple
        return tuple(convert_to_bytes_deep(element) for element in item)
    else:
        # Return the item as is if it's not a string, dict, list, or tuple
        return item

def get_app_list(blob) :
    subblob = blob[b"\x01\x00\x00\x00"]

    app_list = {}

    for appblob in subblob :
        app = Application()
        app.id          = struct.unpack("<L", appblob)[0]
        app.binid       = appblob
        app.version     = struct.unpack("<L", subblob[appblob][b"\x0b\x00\x00\x00"])[0]
        app.size        = struct.unpack("<L", subblob[appblob][b"\x05\x00\x00\x00"])[0]
        app.name        = subblob[appblob][b"\x02\x00\x00\x00"][:-1]

        if b"\x10\x00\x00\x00" in subblob[appblob] :
            if subblob[appblob][b"\x10\x00\x00\x00"] == b"\xff\xff\xff\xff" :
                app.betaversion = app.version
            else :
                app.betaversion = struct.unpack("<L", subblob[appblob][b"\x10\x00\x00\x00"])[0]
        else :
            app.betaversion = app.version

        app_list[app.id] = app

    return app_list


import io, struct, zlib


class SDKBlob:
    def __init__(self, binblob):
        self.origblob = binblob
        self.kv = {}
        self.cached = {}

        if binblob[0:2] == b"\x01\x43":
            packedsize, dunno1, unpackedsize, dunno2, compressionlevel = struct.unpack("<IIIIH", binblob[2:20])

            if compressionlevel != 9:
                raise Exception("Unknown compression level!")

            if len(binblob) != packedsize:
                raise Exception("Wrong packed size!", len(binblob), packedsize)

            if dunno1 != 0 or dunno2 != 0:
                raise Exception("dunnos not zero", hex(dunno1), hex(dunno2))

            binblob = zlib.decompress(binblob[20:])

            if len(binblob) != unpackedsize:
                raise Exception("Wrong unpacked size!", len(binblob), unpackedsize)

        bio = io.BytesIO(binblob)

        magic = bio.read(2)
        if magic != b"\x01\x50":
            raise Exception("Wrong blob magic", magic)

        totalsize, slacksize = struct.unpack("<II", bio.read(8))

        if len(binblob) != totalsize + slacksize:
            raise Exception("Wrong bloblen!", len(binblob), totalsize + slacksize)

        while bio.tell() < totalsize:
            keysize, valuesize = struct.unpack("<HI", bio.read(6))
            key = bio.read(keysize)
            value = bio.read(valuesize)
            if key in self.kv:
                raise Exception("duplicate key!", key)

            self.kv[key] = value

        self.slackdata = bio.read(slacksize)

        if self.slackdata != b"\x00" * slacksize:
            raise Exception("Non-zero slack!")

        tail = bio.read()

        if len(tail) != 0:
            raise Exception("Nonzero size at the end!", tail)

    def _get(self, as_blob, *path):
        if len(path) == 0:
            raise Exception("Empty path!")

        key = path[0]
        if type(key) is int:
            key = struct.pack("<I", key)

        if as_blob or len(path) >= 2:
            if key not in self.cached:
                b = SDKBlob(self.kv[key])
                self.cached[key] = b

        if len(path) == 1:
            if as_blob:
                return self.cached[key]

            else:
                return self.kv[key]

        else:
            return self.cached[key]._get(as_blob, *path[1:])

    def _iterate(self, key_ints = False, as_blob = False):
        keys = self.kv.keys()
        if key_ints:
            keys = [(struct.unpack("<I", key)[0], key) for key in keys]
            keys.sort()
        else:
            keys = [(key, key) for key in keys]

        for outkey, key in keys:
            if as_blob:
                if key not in self.cached:
                    b = SDKBlob(self.kv[key])
                    self.cached[key] = b

                yield outkey, self.cached[key]

            else:
                yield outkey, self.kv[key]

    def get_blob(self, *path):
        return self._get(True, *path)

    def get_i32(self, *path):
        return struct.unpack("<I", self._get(False, *path))[0]

    def get_i64(self, *path):
        return struct.unpack("<Q", self._get(False, *path))[0]

    def get_raw(self, *path):
        return self._get(False, *path)

    def get_str(self, *path):
        s = self._get(False, *path)
        if s[-1] == 0:
            s = s[:-1]

        return s

    def iterate_blobs(self, key_ints = False):
        for key, value in self._iterate(key_ints, True):
            yield key, value

    def iterate_str(self, key_ints = False):
        for key, s in self._iterate(key_ints, False):
            if s[-1] == 0:
                s = s[:-1]

            yield key, s