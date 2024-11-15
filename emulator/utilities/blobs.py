import struct
import zlib

import utils
import logging

log = logging.getLogger("neuter")

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


def blob_dump(blob, spacer = ""):
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