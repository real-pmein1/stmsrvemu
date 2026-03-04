
import os
import os.path
import sys
import struct
import zlib
import logging

from config import get_config
from utilities import steam2_sdk_utils
from utilities.steam2_sdk_utils import parse_checksums
from utilities.blobs import SDKBlob
from logger import STORAGENEUTER

log = logging.getLogger('GCFCHKSUM')
config = get_config()

# Set logger level based on config - if storage_neutor is disabled, suppress these logs
if config.get("storage_neutor", "false").lower() != "true":
    log.setLevel(logging.CRITICAL + 1)  # Suppress all logging
else:
    log.setLevel(STORAGENEUTER)  # Allow STORAGENEUTER level and above


class Checksum:

    def __init__(self, checksumdata = ""):
        self.numfiles = None
        self.totalchecksums = None
        self.checksumliststart = None
        self.checksumdata = checksumdata

        if len(checksumdata):
            self.initialize()

    def loadfromfile(self, filename):
        f = open(filename, "rb")
        self.checksumdata = f.read()
        f.close()

        self.initialize()

    def initialize(self):
        (dummy, dummy2, numfiles, totalchecksums) = struct.unpack("<LLLL", self.checksumdata[:16])

        self.numfiles = numfiles
        self.totalchecksums = totalchecksums
        self.checksumliststart = numfiles * 8 + 16

    def numchecksums(self, fileid):
        checksumpointer = fileid * 8 + 16
        (numchecksums, checksumstart) = struct.unpack("<LL", self.checksumdata[checksumpointer:checksumpointer + 8])

        return numchecksums

    def getchecksum(self, fileid, chunkid):
        checksumpointer = fileid * 8 + 16
        (numchecksums, checksumstart) = struct.unpack("<LL", self.checksumdata[checksumpointer:checksumpointer + 8])
        start = self.checksumliststart + (checksumstart + chunkid) * 4
        crc = struct.unpack("<I", self.checksumdata[start:start + 4])[0]

        return crc

    def validate(self, fileid, chunkid, chunk):

        crc = self.getchecksum(fileid, chunkid)
        crcb = crc.crc(chunk, 0) ^ zlib.crc32(chunk, 0)

        if crc != crcb:
            log.warning("CRC error: %i %s %s" % (fileid, hex(crc), hex(crcb)))
            return False
        else:
            return True


class Checksum2: # v3 storage
    def __init__(self, arg, ver, islan, is_extra):
        if islan:
            suffix = "_lan"
        else:
            suffix = "_wan"

        if type(arg) == int:
            appId = arg
            verId = ver
            with open(self.filename(appId, verId, suffix, is_extra), "rb") as f:
                self.checksumdata = f.read()
        else:
            self.checksumdata = arg

        (formatcode, dummy, numfiles, totalchecksums) = struct.unpack("<LLLL", self.checksumdata[:16])

        self.numfiles = numfiles
        self.totalchecksums = totalchecksums
        self.checksumliststart = numfiles * 8 + 16

    def numchecksums(self, fileid):
        checksumpointer = fileid * 8 + 16
        return struct.unpack("<L", self.checksumdata[checksumpointer:checksumpointer + 4])[0]

    def getchecksum(self, fileid, chunkid):
        checksumpointer = fileid * 8 + 16
        checksumstart = struct.unpack("<L", self.checksumdata[checksumpointer + 4:checksumpointer + 8])[0]
        start = self.checksumliststart + (checksumstart + chunkid) * 4
        return struct.unpack("<I", self.checksumdata[start:start + 4])[0]

    def getchecksums_raw(self, fileid):
        checksumpointer = fileid * 8 + 16
        (numchecksums, checksumstart) = struct.unpack("<LL", self.checksumdata[checksumpointer:checksumpointer + 8])
        start = self.checksumliststart + checksumstart * 4
        return self.checksumdata[start:start + numchecksums * 4]

    def validate(self, fileid, chunkid, chunk):
        crc = self.getchecksum(fileid, chunkid)
        crcb = (zlib.adler32(chunk, 0) ^ zlib.crc32(chunk, 0)) & 0xffffffff

        if crc != crcb:
            logging.warning("CRC error: %i %s %s" % (fileid, hex(crc), hex(crcb)))
            return False
        else:
            return True

    def validate_chunk(self, fileid, chunkid, chunk, filename):
        """Validate chunk and fix CRC in file if mismatch (used by neuter)."""
        stored_crc = self.getchecksum(fileid, chunkid)
        chunk_crc = (zlib.adler32(chunk, 0) ^ zlib.crc32(chunk, 0)) & 0xffffffff

        if stored_crc != chunk_crc:
            self.fix_crc(fileid, chunkid, chunk, filename)
            return False
        return True

    def fix_crc(self, fileid, chunkid, chunk, filename):
        """Update the checksum in the file for a modified chunk."""
        chunk_crc = (zlib.adler32(chunk, 0) ^ zlib.crc32(chunk, 0)) & 0xffffffff

        with open(filename, "rb") as f:
            checksumdata = bytearray(f.read())

        # Calculate position: same logic as getchecksum
        checksumpointer = fileid * 8 + 16
        checksumstart = struct.unpack("<L", checksumdata[checksumpointer + 4:checksumpointer + 8])[0]
        pos = self.checksumliststart + (checksumstart + chunkid) * 4

        # Update the checksum
        checksumdata[pos:pos + 4] = struct.pack("<I", chunk_crc)

        with open(filename, "wb") as f:
            f.write(checksumdata)

        # NOTE: Commented out to reduce log verbosity - uncomment for checksum debugging
        # log.storageneuter(f"Fixed CRC for file {fileid} chunk {chunkid} to {hex(chunk_crc)}")

    @classmethod
    def filename(cls, appId, verId, suffix, is_extra):
        if os.path.isfile("files/cache/" + str(appId) + "_" + str(verId) + "/" + str(appId) + "_" + str(verId) + suffix + ".checksums"):
            log.storageneuter("Sending files/cache/" + str(appId) + "_" + str(verId) + "/" + str(appId) + "_" + str(verId) + suffix + ".checksums")
            return os.path.join("files/cache/" + str(appId) + "_" + str(verId) + "/", str(appId) + "_" + str(verId) + suffix + ".checksums")
        elif os.path.isfile("files/cache/" + str(appId) + "_" + str(verId) + "/" + str(appId) + ".checksums"):
            log.storageneuter("Sending files/cache/" + str(appId) + "_" + str(verId) + "/" + str(appId) + ".checksums")
            return os.path.join("files/cache/" + str(appId) + "_" + str(verId) + "/", "%i.checksums" % (appId))
            
        elif os.path.isfile(os.path.join(config["storagedir"], "%i.v3.checksums" % (appId))) and not is_extra:
            log.storageneuter("Sending " + config["storagedir"] + "%i.v3.checksums" % (appId) + " for version " + str(verId))
            return os.path.join(config["storagedir"], "%i.v3.checksums" % (appId))
        elif os.path.isfile(os.path.join(config["storagedir"], "%i.v3e.checksums" % (appId))) and is_extra:
            log.storageneuter("Sending " + config["storagedir"] + "%i.v3e.checksums" % (appId) + " for version " + str(verId))
            return os.path.join(config["storagedir"], "%i.v3e.checksums" % (appId))
        elif os.path.isfile(os.path.join(config["storagedir"], "%i.checksums" % (appId))) and not is_extra:
            log.storageneuter("Sending " + config["storagedir"] + "%i.checksums" % (appId) + " for version " + str(verId))
            return os.path.join(config["storagedir"], "%i.checksums" % (appId))
        elif os.path.isfile(os.path.join(config["v3storagedir2"], "%i.checksums" % (appId))) and is_extra:
            log.storageneuter("Sending " + config["v3storagedir2"] + "%i.checksums" % (appId) + " for version " + str(verId))
            return os.path.join(config["v3storagedir2"], "%i.checksums" % (appId))
        else:
            log.error("Checksums not found for %s %s " % (appId, verId))


class Checksum3: # v2 storage
    def __init__(self, arg):
        if type(arg) == int:
            appId = arg
            with open(self.filename(appId), "rb") as f:
                self.checksumdata = f.read()
        else:
            self.checksumdata = arg

        (formatcode, dummy, numfiles, totalchecksums) = struct.unpack("<LLLL", self.checksumdata[:16])

        self.numfiles = numfiles
        self.totalchecksums = totalchecksums
        self.checksumliststart = numfiles * 8 + 16

    def numchecksums(self, fileid):
        checksumpointer = fileid * 8 + 16
        return struct.unpack("<L", self.checksumdata[checksumpointer:checksumpointer + 4])[0]

    def getchecksum(self, fileid, chunkid):
        checksumpointer = fileid * 8 + 16
        checksumstart = struct.unpack("<L", self.checksumdata[checksumpointer + 4:checksumpointer + 8])[0]
        start = self.checksumliststart + (checksumstart + chunkid) * 4
        return struct.unpack("<I", self.checksumdata[start:start + 4])[0]

    def getchecksums_raw(self, fileid):
        checksumpointer = fileid * 8 + 16
        (numchecksums, checksumstart) = struct.unpack("<LL", self.checksumdata[checksumpointer:checksumpointer + 8])
        start = self.checksumliststart + checksumstart * 4
        return self.checksumdata[start:start + numchecksums * 4]

    def validate(self, fileid, chunkid, chunk):
        crc = self.getchecksum(fileid, chunkid)
        crcb = (zlib.adler32(chunk, 0) ^ zlib.crc32(chunk, 0)) & 0xffffffff

        if crc != crcb:
            logging.warning("CRC error: %i %s %s" % (fileid, hex(crc), hex(crcb)))
            return False
        else:
            return True

    def validate_chunk(self, fileid, chunkid, chunk, filename):
        """Validate chunk and fix CRC in file if mismatch (used by neuter)."""
        stored_crc = self.getchecksum(fileid, chunkid)
        chunk_crc = (zlib.adler32(chunk, 0) ^ zlib.crc32(chunk, 0)) & 0xffffffff

        if stored_crc != chunk_crc:
            self.fix_crc(fileid, chunkid, chunk, filename)
            return False
        return True

    def fix_crc(self, fileid, chunkid, chunk, filename):
        """Update the checksum in the file for a modified chunk."""
        chunk_crc = (zlib.adler32(chunk, 0) ^ zlib.crc32(chunk, 0)) & 0xffffffff

        with open(filename, "rb") as f:
            checksumdata = bytearray(f.read())

        # Calculate position: same logic as getchecksum
        checksumpointer = fileid * 8 + 16
        checksumstart = struct.unpack("<L", checksumdata[checksumpointer + 4:checksumpointer + 8])[0]
        pos = self.checksumliststart + (checksumstart + chunkid) * 4

        # Update the checksum
        checksumdata[pos:pos + 4] = struct.pack("<I", chunk_crc)

        with open(filename, "wb") as f:
            f.write(checksumdata)

        # NOTE: Commented out to reduce log verbosity - uncomment for checksum debugging
        # log.storageneuter(f"Fixed CRC for file {fileid} chunk {chunkid} to {hex(chunk_crc)}")

    @classmethod
    def filename(cls, appId):
        if os.path.isfile(os.path.join(config["storagedir"], "%i.v2.checksums" % (appId))):
            log.storageneuter("Sending " + config["storagedir"] + "%i.v2.checksums" % (appId))
            return os.path.join(config["storagedir"], "%i.v2.checksums" % (appId))
        else:
            log.storageneuter("Sending " + config["v2storagedir"] + "%i.checksums" % (appId))
            return os.path.join(config["v2storagedir"], "%i.checksums" % (appId))


class Checksum4: #v4 storage
    def __init__(self, arg):
        if type(arg) == int:
            appId = arg
            with open(self.filename(appId), "rb") as f:
                self.checksumdata = f.read()
        else:
            self.checksumdata = arg

        (formatcode, dummy, numfiles, totalchecksums) = struct.unpack("<LLLL", self.checksumdata[:16])

        self.numfiles = numfiles
        self.totalchecksums = totalchecksums
        self.checksumliststart = numfiles * 8 + 16

    def numchecksums(self, fileid):
        checksumpointer = fileid * 8 + 16
        return struct.unpack("<L", self.checksumdata[checksumpointer:checksumpointer + 4])[0]

    def getchecksum(self, fileid, chunkid):
        checksumpointer = fileid * 8 + 16
        checksumstart = struct.unpack("<L", self.checksumdata[checksumpointer + 4:checksumpointer + 8])[0]
        start = self.checksumliststart + (checksumstart + chunkid) * 4
        return struct.unpack("<I", self.checksumdata[start:start + 4])[0]

    def getchecksums_raw(self, fileid):
        checksumpointer = fileid * 8 + 16
        (numchecksums, checksumstart) = struct.unpack("<LL", self.checksumdata[checksumpointer:checksumpointer + 8])
        start = self.checksumliststart + checksumstart * 4
        return self.checksumdata[start:start + numchecksums * 4]

    def validate(self, fileid, chunkid, chunk):
        crc = self.getchecksum(fileid, chunkid)
        crcb = (zlib.adler32(chunk, 0) ^ zlib.crc32(chunk, 0)) & 0xffffffff

        if crc != crcb:
            logging.warning("CRC error: %i %s %s" % (fileid, hex(crc), hex(crcb)))
            return False
        else:
            return True

    def validate_chunk(self, fileid, chunkid, chunk, filename):
        """Validate chunk and fix CRC in file if mismatch (used by neuter)."""
        stored_crc = self.getchecksum(fileid, chunkid)
        chunk_crc = (zlib.adler32(chunk, 0) ^ zlib.crc32(chunk, 0)) & 0xffffffff

        if stored_crc != chunk_crc:
            self.fix_crc(fileid, chunkid, chunk, filename)
            return False
        return True

    def fix_crc(self, fileid, chunkid, chunk, filename):
        """Update the checksum in the file for a modified chunk."""
        chunk_crc = (zlib.adler32(chunk, 0) ^ zlib.crc32(chunk, 0)) & 0xffffffff

        with open(filename, "rb") as f:
            checksumdata = bytearray(f.read())

        # Calculate position: same logic as getchecksum
        checksumpointer = fileid * 8 + 16
        checksumstart = struct.unpack("<L", checksumdata[checksumpointer + 4:checksumpointer + 8])[0]
        pos = self.checksumliststart + (checksumstart + chunkid) * 4

        # Update the checksum
        checksumdata[pos:pos + 4] = struct.pack("<I", chunk_crc)

        with open(filename, "wb") as f:
            f.write(checksumdata)

        # NOTE: Commented out to reduce log verbosity - uncomment for checksum debugging
        # log.storageneuter(f"Fixed CRC for file {fileid} chunk {chunkid} to {hex(chunk_crc)}")

    @classmethod
    def filename(cls, appId):
        if os.path.isfile(os.path.join(config["storagedir"], "%i.v4.checksums" % (appId))):
            log.storageneuter("Sending " + config["storagedir"] + "%i.v4.checksums" % (appId))
            return os.path.join(config["storagedir"], "%i.v4.checksums" % (appId))
        else:
            log.storageneuter("Sending " + config["v4storagedir"] + "%i.checksums" % (appId))
            return os.path.join(config["v4storagedir"], "%i.checksums" % (appId))


import os
import zlib
import struct
import logging

class SDKChecksum:
    CHUNK_SIZE = 0x8000

    def __init__(self, arg, suffix=None):
        # ---- Handle (appId, version) + suffix case ----
        if isinstance(arg, tuple):
            appId, version = arg

            cache_dir = os.path.join("files", "cache", f"{appId}_{version}")
            cs_file = os.path.join(cache_dir, f"{appId}_{version}{suffix}.checksums")

            # Decide if we need to regenerate
            needs_regen = True
            if os.path.isfile(cs_file):
                cs_mtime = os.path.getmtime(cs_file)
                # only consider the matching suffix .data files
                data_paths = [
                    os.path.join(cache_dir, fn)
                    for fn in os.listdir(cache_dir or "")
                    if fn.startswith(f"{appId}_") and fn.endswith(f"_{suffix}.data")
                ]
                if data_paths:
                    latest_data = max(os.path.getmtime(p) for p in data_paths)
                    if latest_data <= cs_mtime:
                        needs_regen = False
                else:
                    # no neutered files yet ? existing .checksums is valid
                    needs_regen = False

            if not needs_regen:
                # load existing .checksums
                with open(cs_file, "rb") as f:
                    raw_cs_data = f.read()

            else:
                # ---- Pull raw checksum blob ----
                blob_fname = self.find_blob_file(appId, version)
                if not blob_fname:
                    raise Exception(f"Blob file not found for appId: {appId}, version: {version}")
                with open(blob_fname, "rb") as bf:
                    blob = bf.read()


                b = SDKBlob(blob)
                raw_cs_data = b.get_raw(4)
                cs_bytes = bytearray(raw_cs_data)

                # ---- Parse & build offset map ----
                filedata, checksums_raw, cs_data_offset = parse_checksums(raw_cs_data)
                self.filedata      = filedata
                self.checksums_raw = checksums_raw
                self.build_checksums()

                # ---- Recompute CRCs for each fileId, but only the matching suffix .data files ----
                for fileid, (num_chunks, chunk_start) in self.checksum_offsets.items():
                    data_path = os.path.join(cache_dir, f"{appId}_{fileid}{suffix}.data")
                    if not os.path.isfile(data_path):
                        continue

                    with open(data_path, "rb") as df:
                        blob_chunk = df.read()
                    try:
                        data = zlib.decompress(blob_chunk)
                    except zlib.error:
                        data = blob_chunk

                    total_chunks = (len(data) + self.CHUNK_SIZE - 1) // self.CHUNK_SIZE
                    for chunkid in range(min(total_chunks, num_chunks)):
                        start = chunkid * self.CHUNK_SIZE
                        piece = data[start:start + self.CHUNK_SIZE]
                        new_crc = (zlib.adler32(piece, 0) ^ zlib.crc32(piece, 0)) & 0xFFFFFFFF
                        off = cs_data_offset + (chunk_start + chunkid) * 4
                        cs_bytes[off:off+4] = struct.pack("<I", new_crc)

                # ---- Write updated .checksums back to disk ----
                os.makedirs(cache_dir, exist_ok=True)
                new_raw = bytes(cs_bytes)
                with open(cs_file, "wb") as f:
                    f.write(new_raw)

                raw_cs_data = new_raw

            # ---- Finally parse into in?memory structures ----
            self.filedata, self.checksums_raw, _ = parse_checksums(raw_cs_data)
            self.build_checksums()

        else:
            # raw-data path unchanged (suffix ignored)
            raw_cs_data = arg
            self.filedata, self.checksums_raw, _ = parse_checksums(raw_cs_data)
            self.build_checksums()

    def build_checksums(self):
        self.numfiles = max(self.checksums_raw.keys()) + 1 if self.checksums_raw else 0
        self.totalchecksums = sum(len(chk) for chk in self.checksums_raw.values())
        self.checksum_offsets = {}
        self.checksum_list = []

        offset = 0
        for fid in range(self.numfiles):
            chunks = self.checksums_raw.get(fid, [])
            self.checksum_offsets[fid] = (len(chunks), offset)
            for _, chk_bytes in chunks:
                self.checksum_list.append(struct.unpack("<I", chk_bytes)[0])
            offset += len(chunks)

    def numchecksums(self, fileid):
        return self.checksum_offsets.get(fileid, (0,0))[0]

    def getchecksum(self, fileid, chunkid):
        num, start = self.checksum_offsets.get(fileid, (0,0))
        if chunkid >= num:
            raise Exception(f"ChunkID {chunkid} out of range for FileID {fileid}")
        return self.checksum_list[start + chunkid]

    def getchecksums_raw(self, fileid):
        num, start = self.checksum_offsets.get(fileid, (0,0))
        vals = self.checksum_list[start:start+num]
        return b"".join(struct.pack("<I", v) for v in vals)

    def validate(self, fileid, chunkid, chunk):
        crc  = self.getchecksum(fileid, chunkid)
        crcb = (zlib.adler32(chunk) ^ zlib.crc32(chunk)) & 0xFFFFFFFF
        if crc != crcb:
            logging.warning(
                f"CRC mismatch: file={fileid} chunk={chunkid} "
                f"stored=0x{crc:08X} got=0x{crcb:08X}"
            )
            return False
        return True

    @classmethod
    def find_blob_file(cls, appId, version):
        blob_dir = config['steam2sdkdir']
        for fn in os.listdir(blob_dir):
            if fn.endswith(".blob"):
                parts = fn.split(".")[0].split("_")
                if len(parts) >= 2 and int(parts[0]) == appId and int(parts[1]) == version:
                    return os.path.join(blob_dir, fn)
        return None

    def __repr__(self):
        return f"<SDKChecksum files={self.numfiles} totalChunks={self.totalchecksums}>"



class Checksums:
    def __init__(self, checksumdata = ""):
        self.numfiles = None
        self.totalchecksums = None
        self.checksumliststart = None
        self.numchecksums = None
        self.checksumstart = None
        self.checksums = None
        self.checksums_raw = None
        if len(checksumdata):
            self.checksumdata = checksumdata
            self.initialize()

    def load_from_file(self, filename):
        f = open(filename, "rb")
        self.checksumdata = f.read()
        f.close()

        self.initialize()

    def initialize(self):
        (dummy, dummy2, numfiles, totalchecksums) = struct.unpack("<LLLL", self.checksumdata[:16])

        self.numfiles = numfiles
        self.totalchecksums = totalchecksums
        self.checksumliststart = numfiles * 8 + 16

        self.numchecksums = {}
        self.checksumstart = {}
        self.checksums = {}
        self.checksums_raw = {}
        for fileid in range(self.numfiles):
            checksumpointer = fileid * 8 + 16
            (self.numchecksums[fileid], self.checksumstart[fileid]) = struct.unpack("<LL", self.checksumdata[checksumpointer:checksumpointer + 8])

            filechecksums = []
            start = self.checksumliststart + self.checksumstart[fileid] * 4
            end = start + self.numchecksums[fileid] * 4
            self.checksums_raw[fileid] = self.checksumdata[start:end]
            for i in range(self.numchecksums[fileid]):
                checksum = struct.unpack("<I", self.checksumdata[start:start + 4])[0]
                filechecksums.append(checksum)
                start += 4

            self.checksums[fileid] = filechecksums

    def validate(self, fileid, file):
        if len(file) != self.numchecksums[fileid]:
            logging.error("Differing amount of chunks in file and checksum list. File: %s List: %s" % (len(file), self.numchecksums[fileid]))
            sys.exit()

        for chunkid in range(len(file)):
            result = self.validate_chunk(fileid, chunkid, file[chunkid])
            if not result:
                return False

        return True

    def validate_chunk(self, fileid, chunkid, chunk, filename):

        try:
            stored_crc = self.checksums[fileid][chunkid]
        except IndexError:
            logging.error("Checksum error. Tried to check a chunkid that doesn't have a checksum. Chunk %s in file %s" % (chunkid, fileid))
            return False

        chunk_crc = (zlib.adler32(chunk, 0) ^ zlib.crc32(chunk, 0)) & 0xffffffff

        if stored_crc != chunk_crc:
            # print "Checksum failed!"
            # logging.warning("CRC error: %i %i stored: %s chunk: %s" %  (fileid, chunkid, hex(stored_crc), hex(chunk_crc)))
            self.fix_crc(fileid, chunkid, chunk, filename)
            return False
        else:
            return True

    def fix_crc(self, fileid, chunkid, chunk, filename):
        log = logging.getLogger("converter")
        clientid = ""
        f = open(filename, "rb")
        checksumdata = f.read()
        f.close()
        stored_crc = self.checksums[fileid][chunkid]
        chunk_crc = (zlib.adler32(chunk, 0) ^ zlib.crc32(chunk, 0)) & 0xffffffff
        log.storageneuter("Fixing CRC from " + str(stored_crc) + " to " + str(chunk_crc) + " on FileID " + str(fileid))

        (dummy, dummy2, numfiles, totalchecksums) = struct.unpack("<LLLL", checksumdata[:16])

        numfiles = numfiles
        totalchecksums = totalchecksums
        checksumliststart = numfiles * 8 + 16

        numchecksums = {}
        checksumstart = {}
        checksums = {}
        checksums_raw = {}
        checksumpointer = fileid * 8 + 16
        (numchecksums[fileid], checksumstart[fileid]) = struct.unpack("<LL", checksumdata[checksumpointer:checksumpointer + 8])

        filechecksums = []
        start = checksumliststart + checksumstart[fileid] * 4
        end = start + numchecksums[fileid] * 4
        checksums_raw[fileid] = checksumdata[start:end]
        log.storageneuter(len(checksumdata))  # 132844
        log.storageneuter(len(checksumdata[0:start]))  # 67192
        log.storageneuter(len(checksumdata[start:start + 4]))  # 4
        log.storageneuter(len(checksumdata[start + 4:len(checksumdata)]))  # 65648
        checksumdatanew = checksumdata[0:start]
        log.storageneuter(len(checksumdatanew))  # 67192
        checksumdatanew_temp = ""
        log.storageneuter("Checksum count: " + str(range(numchecksums[fileid])))
        for i in range(numchecksums[fileid]):
            checksum = struct.unpack("<I", checksumdata[start:start + 4])[0]
            log.storageneuter(struct.unpack("<I", checksumdata[start:start + 4]))  # 1132535908
            log.storageneuter("Checksum: " + str(checksum))  # 1132535908
            if checksum == stored_crc:
                log.storageneuter("CRC CHANGED!")
                # print(struct.pack("<i", chunk_crc)) #-1711041001
                # print(type((checksumdata[start:start+4])[0]))
                checksumdatanew_temp = struct.pack("<I", chunk_crc)
                log.storageneuter(struct.unpack("<I", checksumdatanew_temp))
                log.storageneuter(len(checksumdatanew_temp))
                checksumdatanew += checksumdatanew_temp
                log.storageneuter(len(checksumdatanew))
            else:
                log.storageneuter("Stored only")
                # print(struct.pack("<i", stored_crc)) #-1711041001
                # print(type((checksumdata[start:start+4])[0]))
                checksumdatanew_temp = struct.pack("<I", checksum)
                log.storageneuter(struct.unpack("<I", checksumdatanew_temp))
                log.storageneuter(len(checksumdatanew_temp))
                checksumdatanew += checksumdatanew_temp
                log.storageneuter(len(checksumdatanew))
            # filechecksums.append(checksum)
            start += 4
        log.storageneuter(len(checksumdatanew))
        log.storageneuter(len(checksumdata[start:len(checksumdata)]))
        checksumdatanew += checksumdata[start:len(checksumdata)]
        log.storageneuter(len(checksumdatanew))
        for i in range(numchecksums[fileid]):
            checksum = struct.unpack("<I", checksumdatanew[start:start + 4])
            #if checksum == chunk_crc:
                #print("Checksum validated")
            # filechecksums.append(checksum)
            start += 4

        if len(checksumdata) != len(checksumdatanew):
            log.storageneuter("Old and new checksums are different sizes: " + str(len(checksumdata)) + " to " + str(len(checksumdatanew)))
            sys.exit()
        else:
            log.storageneuter("Old and new checksums are correct sizes.")

        f = open(filename, "wb")
        f.write(checksumdatanew)
        f.close()