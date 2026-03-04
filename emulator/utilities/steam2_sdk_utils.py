import io
import os
import struct
import sys
import zlib
import config
import logging
import glob
import time

import globalvars
from utilities.blobs import SDKBlob
from utilities.storages import Steam2Storage

config_var = config.get_config()
def gen_id_from_filename(filename):
    parts = os.path.basename(filename).split(".")[0].split("_")
    if len(parts) == 2:
        # Format: appid_version
        appid, appver = parts
        return (int(appid), int(appver))

    elif len(parts) >= 4:
        # Format: appid_version_crc_sha256 (renamed with integrity hashes)
        appid, appver, crc, sha256 = parts[0:4]
        return (int(appid), int(appver), crc)

    else:
        raise Exception("Nonstandard filename format", filename)


def find_blob_file_older(appId, appVersion):
    # Implement code to find the blob file for given appId and appVersion
    # Perhaps the blob files are stored in a directory named 'blobs'
    blob_dir = config_var['steam2sdkdir'] # Replace with the actual path to your blob files
    for filename in os.listdir(blob_dir):
        if filename.endswith(".blob"):
            parts = filename.split(".")[0].split("_")
            if len(parts) >= 2:
                file_appId = int(parts[0])
                file_appVersion = int(parts[1])
                if file_appId == appId and file_appVersion == appVersion:
                    return os.path.join(blob_dir, filename)
    return None


def find_blob_file_old(appId, appVersion):
    blob_dir = config_var['steam2sdkdir']
    match = None
    with os.scandir(blob_dir) as entries:
        for entry in entries:
            if entry.name.startswith(f"{str(appId)}_{str(appVersion)}") and entry.name.endswith(".blob"):
                match = entry.name
                break
    if match:
        return os.path.join(blob_dir, match)
    else:
        return None


def find_blob_file(appId, appVersion):
    blob_dir = config_var['steam2sdkdir']
    exact = os.path.join(blob_dir, f"{appId}_{appVersion}.blob")

    if os.path.exists(exact):
        return exact

    # fallback only if there may be suffixes
    pattern = os.path.join(blob_dir, f"{appId}_{appVersion}_*.blob")
    return next(glob.iglob(pattern), None)


def check_for_entry(app_id, version):
    # Create a tuple for appID and version to match the dictionary keys
    entry_id = (app_id, version)  # Using tuple instead of string

    # Print the contents of known_dats and known_blobs for debugging
    # print(repr(globalvars.known_dats), repr(globalvars.known_blobs))

    # Check in known_blobs
    if entry_id in globalvars.known_blobs:
        # print(f"Found entry in known_blobs: {globalvars.known_blobs[entry_id]}")
        return globalvars.known_blobs[entry_id]

    # Check in known_dats
    if entry_id in globalvars.known_dats:
        # print(f"Found entry in known_dats: {globalvars.known_dats[entry_id]}")
        return globalvars.known_dats[entry_id]

    # If not found in either, return None
    # print(f"No entry found for App ID {appID} and Version {version}.")
    return None


def scan_directories(blob_directory, dat_directory):
    # Initialize known_blobs and known_dats
    globalvars.known_blobs = {}
    globalvars.known_dats = {}

    # Scan blob_directory for both blob and dat files
    try:
        for entry in os.scandir(blob_directory):
            if entry.is_file():
                filepath = entry.path
                filename = entry.name
                if filename.lower().endswith(".blob"):
                    id = Steam2Storage.gen_id_from_filename(filename)
                    if id in globalvars.known_blobs:
                        raise Exception("Duplicate blob ID?", id)
                    globalvars.known_blobs[id] = filepath
                elif filename.lower().endswith(".dat"):
                    id = Steam2Storage.gen_id_from_filename(filename)
                    if id in globalvars.known_dats:
                        raise Exception("Duplicate dat ID?", id)
                    globalvars.known_dats[id] = filepath
    except FileNotFoundError:
        pass
        #print(f"Blob directory {blob_directory} not found.")
    except Exception as e:
        print(f"An error occurred scanning blob directory: {e}")

def parse_checksums(checksumdata):
    bio = io.BytesIO(checksumdata)
    if bio.read(4) != b"4rE4":
        raise Exception("Bad starting magic")

    version, num_fileblocks, num_items, offset1, offset2, blocksize, largest_num_blocks = struct.unpack("<IIIIIII", bio.read(28))

    if blocksize != 0x8000:
        raise Exception("Differing blocksize!", blocksize)

    if version not in (0, 1):
        raise Exception("Unknown version!", version)

    if offset1 != 0x20:
        raise Exception("Bad offset1", hex(offset1))

    if offset2 != 0x20 + 0x10 * num_fileblocks:
        raise Exception("Bad offset2", hex(offset2), 0x20 + 0x10 * num_fileblocks)

    fileblocks = []
    for i in range(num_fileblocks):
        fileid_start, filecount, offset, dummy4 = struct.unpack("<IIII", bio.read(16))
        fileblocks.append((fileid_start, filecount, offset))

        if dummy4 != 0:
            raise Exception("Unknown dummy4", dummy4)

    max_blocks = 0
    numfiles = 0

    filedata = {}
    checksums = {}
    highest_fileid = -1

    fingerprintdata = bytearray()

    for fileid_start, filecount, offset in fileblocks:
        if bio.tell() != offset:
            raise Exception("Offset doesn't match expected")

        numfiles += filecount
        for fileid in range(fileid_start, fileid_start + filecount):
            fingerprintdata += struct.pack("<I", fileid_start)

            highest_fileid = max(highest_fileid, fileid)

            if version == 0:
                filesize, offset, num_blocks = struct.unpack("<III", bio.read(12))

            elif version == 1:
                filesize, offset, num_blocks = struct.unpack("<QQI", bio.read(20))

            filemode = num_blocks >> 24
            num_blocks = num_blocks & 0x00ffffff

            if filemode not in (1, 2, 3):
                raise Exception("Bad filemode!", filemode)

            max_blocks = max(max_blocks, num_blocks)

            if fileid in filedata:
                raise Exception("duplicate fileid", fileid)

            filedata[fileid] = (filesize, offset, filemode)

            if fileid in checksums:
                raise Exception("duplicate fileid", fileid)

            checksums[fileid] = []
            for j in range(num_blocks):
                compr_size = struct.unpack("<I", bio.read(4))[0]
                checksum = bio.read(4)
                fingerprintdata += checksum

                checksums[fileid].append((compr_size, checksum))

    if bio.read() != b"4rE4":
        raise Exception("Bad ending magic")

    if max_blocks != largest_num_blocks:
        raise Exception("Max blocks doesn't match", max_blocks, largest_num_blocks)

    if numfiles != num_items:
        raise Exception("Numfiles doesn't match", numfiles, num_items)

    return filedata, checksums, fingerprintdata


def patch_checksums_for_neutered(chk_bytes: bytearray, cache_dir: str) -> bytearray:
    """
    For any chunk replacement files named "<appid>_<fileid>-<chunkid>.data"
    in cache_dir, recompute that single chunk?s CRC32/Adler32 and patch it
    into chk_bytes in place.
    """
    import glob, os, struct, zlib

    # 1) Build a map of exactly which (fileid,chunkid) have replacements
    replacements: dict[tuple[int,int], bytes] = {}
    for path in glob.glob(os.path.join(cache_dir, "*-*.data")):
        # filename = "<appid>_<fileid>-<chunkid>.data"
        base = os.path.basename(path).rsplit(".", 1)[0]
        _, fc = base.split("_", 1)        # "13-7" for fileid=13,chunkid=7
        fileid_str, chunkid_str = fc.split("-", 1)
        fid, cid = int(fileid_str), int(chunkid_str)
        with open(path, "rb") as f:
            replacements[(fid, cid)] = f.read()

    # 2) Walk the checksums table header to find where each chunk?s 4-byte entry lives
    off = 16  # skip the 16-byte header
    num_files = struct.unpack_from("<L", chk_bytes, 8)[0]
    list_base = 16 + num_files * 8

    for fid in range(num_files):
        n_blks, first = struct.unpack_from("<LL", chk_bytes, off)
        for i in range(n_blks):
            key = (fid, i)
            if key in replacements:
                data = replacements[key]
                # recompute exactly that chunk?s CRC32/Adler32
                new_crc = (zlib.adler32(data, 0) ^ zlib.crc32(data, 0)) & 0xFFFFFFFF
                crc_off = list_base + (first + i) * 4
                struct.pack_into("<I", chk_bytes, crc_off, new_crc)
        off += 8

    return chk_bytes


def extract_checksumbin(appid: int, version: int, out_dir: str, suffix) -> bytes:
    """
    Return the fully-merged *.checksums* binary for (appid, version).
    Also write it to disk when cache_sdk_depot == "true".
    """
    blob_dir   = config_var["steam2sdkdir"]
    branch_id  = gen_id_from_filename(f"{appid}_{version}.blob")

    # ------------------------------------------------------------------ helpers
    def _get_checksums(known_blobs, id, blobcontainers, checksums):
        # -- open the correct blob for *this* id
        new_known_blobs = {}
        for key, value in known_blobs.items():
            if key[0] == id[0]:
                new_known_blobs.update({(key[0], key[1]): value})
        blob_path  = new_known_blobs[id]
        blobdata   = open(blob_path, "rb").read()
        b          = SDKBlob(blobdata)

        # -- walk up the parent chain (field 11 = parent version, 12 = parent CRC)
        parentver  = b.get_i32(11)
        parentcrc  = "%08x" % b.get_i32(12)
        if parentver != 0xFFFFFFFF and parentcrc != "00000000":
            parent_id = (id[0], parentver) if len(id) == 2 else (id[0], parentver, parentcrc)
            if parent_id not in new_known_blobs:
                raise Exception("Parent blob does not exist:", parent_id)
            _get_checksums(new_known_blobs, parent_id, blobcontainers, checksums)

        # -- merge this blob?s checksums
        _, newchecksums, _ = parse_checksums(b.get_raw(4))
        for fid, blocks in newchecksums.items():
            checksums[fid] = blocks

        # -- build the checksum.bin chunk for *this* blob
        last_id = max(checksums) if checksums else -1
        indextable, checksumtable, checksumoffset = bytearray(), bytearray(), 0
        for fid in range(last_id + 1):
            if fid not in checksums:
                indextable += struct.pack("<II", 0, 0)
            else:
                n = len(checksums[fid])
                indextable += struct.pack("<II", n, checksumoffset)
                checksumoffset += n
                for _, csum in checksums[fid]:
                    checksumtable += csum

        checksumdata = (b"\x21\x37\x89\x14" +
                        struct.pack("<III", 1, last_id + 1, checksumoffset) +
                        indextable + checksumtable)

        signature = b.get_raw(9)
        blobcontainers[id] = {"checksumbin": checksumdata + signature}

    # ------------------------------------------------------------------ gather all blobs in the dir
    known_blobs = {}
    idx = (str(appid), str(version))
    #for fn in os.listdir(blob_dir):
    #    if fn.lower().endswith(".blob"):
    #        idx = gen_id_from_filename(fn)
    #        #if idx in known_blobs:
    #        #    raise Exception("Duplicate blob ID?", idx)
    #        known_blobs[idx] = os.path.join(blob_dir, fn)
    if os.path.isfile(os.path.join(blob_dir, idx[0] + "_" + idx[1] + ".blob")):
        i = version
        while i >= 0:
            known_blobs[(appid, i)] = os.path.join(blob_dir, idx[0] + "_" + str(i) + ".blob")
            i -= 1
    else:
        with os.scandir(blob_dir) as it:
            for entry in it:
                if entry.name.endswith(".blob") and entry.name.count("_") >= 2:
                    version_int = int(entry.name[entry.name.find('_') + 1 : entry.name.find('_', entry.name.find('_') + 1)])
                    if entry.name.startswith(idx[0] + "_") and version_int <= version:
                        known_blobs[(appid, version_int)] = os.path.join(blob_dir, entry.name)

    # ------------------------------------------------------------------ recurse and cache
    blobcontainers, checksums = {}, {}
    _get_checksums(known_blobs, branch_id, blobcontainers, checksums)

    # out_dir is now always ".../files/cache/<appid>_<version>"
    """os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir,
              f"{appid}_{version}{suffix}.checksums"),
              "wb") as f:
        f.write(blobcontainers[branch_id]["checksumbin"])"""

    return bytes(blobcontainers[branch_id]["checksumbin"])


# FIXME this needs to reuse the checksum function above, instead of rewriting the method inside itself
def generate_index_bytes(blobname, dat_directory, output_directory=os.path.join("files", "cache")):
    """
    Generates the index file from blob data and returns its content as bytes.

    Args:
        blobname (str): Path to the blob file for the specific version.
        dat_directory (str): Path to the directory containing .dat files.
        output_directory (str): Directory where temporary index and data files are stored.

    Returns:
        bytes: The content of the generated index file.
    """
    # Step 1: Scan directories for known blobs and dat files
    scan_directories(config_var["steam2sdkdir"], dat_directory)

    # Step 2: Extract blob information
    branch_id = gen_id_from_filename(blobname)
    appid, appver = branch_id[:2]

    # Step 3: Build blob containers and checksum data
    blobcontainers = {}
    checksums = {}

    def _get_checksums(known_blobs, id):
        blobname = known_blobs[id]
        blobdata = open(blobname, "rb").read()
        b = SDKBlob(blobdata)

        # Determine parent version and CRC
        parentver = (id[1] - 1) & 0xffffffff
        parentcrc = "%08x" % b.get_i32(12)

        # Process parent blob if applicable
        if parentver != 0xffffffff and parentcrc != "00000000":
            if len(id) == 2:
                parentid = (id[0], parentver)
            elif len(id) == 3:
                parentid = (id[0], parentver, parentcrc)
            else:
                raise Exception("Invalid ID format")

            if parentid not in globalvars.known_blobs:
                raise Exception("Parent blob does not exist:", parentid)

            _get_checksums(globalvars.known_blobs, parentid)

        # Parse the current blob's checksums
        _, newchecksums, _ = parse_checksums(b.get_raw(4))

        # Merge the new checksums into the aggregated list
        for fileid, blocks in newchecksums.items():
            checksums[fileid] = blocks

        # Build checksum binary data for the current blob
        if checksums:
            last_id = max(checksums.keys())
        else:
            last_id = -1

        indextable = bytearray()
        checksumtable = bytearray()

        indexcount = last_id + 1
        checksumoffset = 0

        for fileid in range(indexcount):
            if fileid not in checksums:
                indextable += struct.pack("<II", 0, 0)
            else:
                numchecksums = len(checksums[fileid])
                indextable += struct.pack("<II", numchecksums, checksumoffset)
                checksumoffset += numchecksums
                for _, checksum in checksums[fileid]:
                    checksumtable += checksum

        checksumdata = (
            b"\x21\x37\x89\x14"
            + struct.pack("<III", 1, indexcount, checksumoffset)
            + indextable
            + checksumtable
        )

        signature = b.get_raw(9)

        blobcontainers[id] = {
            "checksumbin": checksumdata + signature,
        }

    _get_checksums(globalvars.known_blobs, branch_id)

    # Step 4: Write and read index file
    indexdata = bytearray()
    datptr = 0
    current_f = None

    datafilename = os.path.join(output_directory, f"{appid}.data")
    with open(datafilename, "wb") as of:
        for fileid in sorted(checksums):
            id, filedata, checksum_blocks = checksums[fileid]

            if len(id) == 2:
                datid = id
            elif len(id) == 3:
                datid = (id[0], id[1], blobcontainers[id]["datachecksum"])
            else:
                raise Exception("Bad ID")

            if datid != current_f:
                if current_f is not None:
                    f.close()
                f = open(globalvars.known_dats[datid], "rb")
                current_f = datid

            filesize, offset, filemode = filedata
            f.seek(offset)

            indexdata += struct.pack(">QQQ", fileid, len(checksum_blocks) * 16, filemode)

            for compr_size, checksum in checksum_blocks:
                block = f.read(compr_size)
                if len(block) != compr_size:
                    raise Exception("Bad block read!")

                if datptr != of.tell():
                    raise Exception("Bad output data position!")

                indexdata += struct.pack(">QQ", datptr, compr_size)
                of.write(block)
                datptr += compr_size

        if current_f is not None:
            f.close()

    indexfilename = os.path.join(output_directory, f"{appid}.index")

    if config_var["cache_sdk_depot"].lower() == "true":
        with open(indexfilename, "wb") as of:
            of.write(indexdata)

    return bytes(indexdata)


# ---------------------------------------------------------------------------
#  Build a ?normal? v3-style .data/.index pair from an SDK blob depot
# ---------------------------------------------------------------------------
def build_index_and_data_from_checksums(appid: int, version: int,
                                        out_dir: str) -> bytes:
    """
    Write <appid>.data and return the bytes that should be saved as
    <appid>.index .

    Every chunk is looked up like this:
      1.  files/cache/<appid>_<ver>/<appid>_<fileid>-<cid>.data  (if exists)
      2.  original chunk inside the SDK .dat referenced by the blob chain

    The index format is identical to older v3 depots: for each chunk,
    two uint64 big-endian values (offset, length) pointing into the .data
    file.  Files that do not exist simply get a (0,0) entry.
    """

    log = logging.getLogger("SDKDepot")
    cache_dir = os.path.join("files", "cache", f"{appid}_{version}")
    data_path = os.path.join(out_dir,   f"{appid}.data")

    # ------------------------------------------------------------ helpers ---
    def _ensure_dirs():
        os.makedirs(out_dir,   exist_ok=True)
        os.makedirs(cache_dir, exist_ok=True)

    def _open_dat_file(path, cache={}):
        """Return a cached file handle for a .dat path."""
        if path not in cache:
            cache[path] = open(path, "rb")
        return cache[path]

    # ------------------------------------------------------ gather metadata
    _ensure_dirs()
    scan_directories(config_var['steam2sdkdir'],  # refresh global maps
                     config_var['steam2sdkdir'])

    # reuse the full Steam2Storage object just to harvest the metadata
    tmp_store = Steam2Storage(appid,
                              config_var['steam2sdkdir'],
                              version,
                              islan=False)       # we only read

    file_info = tmp_store.file_data_info                # {fileid: {...}}
    max_fileid = max(file_info)

    # The SDK checksum list for every file is already in file_info[fileid]['checksums']
    # where each entry = (compressed_size, adler/crc bytes)

    # --------------------------------------------------------- write data --
    index_bytes = bytearray()
    current_off = 0

    with open(data_path, "wb") as data_out:
        for fileid in range(max_fileid + 1):
            if fileid not in file_info:
                # pad with a dummy (0,0) entry so indices line up
                index_bytes += struct.pack(">QQ", 0, 0)
                continue

            info = file_info[fileid]
            dat_path     = info['datfile']
            file_offset  = info['offset']
            checksums    = info['checksums']   # list[(compr_size, checksum)]
            block_sizes  = [c[0] for c in checksums]

            for cid, compr_size in enumerate(block_sizes):
                # 1. neutered cache file?
                neutered_path = os.path.join(cache_dir,
                                             f"{appid}_{fileid}-{cid}.data")
                if os.path.isfile(neutered_path):
                    with open(neutered_path, "rb") as cf:
                        chunk_bytes = cf.read()
                else:
                    # 2. original bytes from .dat
                    fdat = _open_dat_file(dat_path)
                    fdat.seek(file_offset)
                    chunk_bytes = fdat.read(compr_size)

                # write out
                data_out.write(chunk_bytes)
                index_bytes += struct.pack(">QQ", current_off, len(chunk_bytes))
                current_off += len(chunk_bytes)

                # advance source pointer if we were reading original .dat
                file_offset += compr_size

    log.info("Wrote %s (%.2f MiB) and built index for %d files",
             data_path, current_off / (1024*1024), max_fileid + 1)
    return bytes(index_bytes)


def build_neutered_store(appid: int, version: int, out_dir: str, suffix) -> None:
    """
    Materialise the neutered SDK depot for (appid,version) into `out_dir`
    as <appid>.index , <appid>.data , <appid>.checksums .

    If they already exist we do nothing ? this makes the call idempotent
    and safe to run inside Storage.__init__().
    """
    if (os.path.exists(os.path.join(out_dir, f"{appid}.index")) and
        os.path.exists(os.path.join(out_dir, f"{appid}.data"))  and
        os.path.exists(os.path.join(out_dir, f"{appid}.checksums"))):
        return  # cache already present

    scan_directories(config_var['steam2sdkdir'],          # refresh global maps
                     config_var['steam2sdkdir'])

    # ---- 1. build a merged .checksums covering the full blob chain ----
    checksums_bin = extract_checksumbin(appid, version, out_dir, suffix)

    with open(os.path.join(out_dir, f"{appid}_{version}{suffix}.checksums"), "wb") as f:
        f.write(checksums_bin)

    # ---- 2. reuse the writer that already constructs .index / .data ----
    # (_get_checksums inside extract_checksumbin returned the bytes for the
    #  .index but we need them on disk for readindexes())
    # The helper below is already present in the file and returns the
    # index bytes after it has written <appid>.data:
    index_bytes = build_index_and_data_from_checksums(
                      appid, version, out_dir)

    with open(os.path.join(out_dir, f"{appid}_{version}{suffix}.index"), "wb") as f:
        f.write(index_bytes)
