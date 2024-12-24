import io
import os
import struct
import sys
import zlib
import config

import globalvars
from utilities.blobs import SDKBlob
from utilities.storages import Steam2Storage

config_var = config.get_config()
def gen_id_from_filename(filename):
    parts = os.path.basename(filename).split(".")[0].split("_")
    if len(parts) == 4:
        appid, appver, crc, _ = parts
        appid = int(appid)
        appver = int(appver)
        id = (appid, appver, crc)

    elif len(parts) == 2:
        appid, appver = parts
        appid = int(appid)
        appver = int(appver)

        id = (appid, appver)

    else:
        raise Exception("Nonstandard filename format", filename)

    return id

def find_blob_file(appId, appVersion):
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
def check_for_entry(app_id, version):
    # Create a tuple for app_id and version to match the dictionary keys
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
    # print(f"No entry found for App ID {app_id} and Version {version}.")
    return None


def scan_directories(blob_directory, dat_directory):
    # Initialize known_blobs and known_dats
    globalvars.known_blobs = {}
    globalvars.known_dats = {}

    # Scan blob_directory for both blob and dat files
    try:
        for filename in os.listdir(blob_directory):
            filepath = os.path.join(blob_directory, filename)
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
            fingerprintdata += struct.pack("<I", fileid_start + i)

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


def extract_checksumbin(blobname):
    def _get_checksums(known_blobs, id, blobcontainers, checksums):
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

            if parentid not in known_blobs:
                raise Exception("Parent blob does not exist:", parentid)

            _get_checksums(known_blobs, parentid, blobcontainers, checksums)

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

    # Load all known blobs in the directory
    blobdir = config_var["steam2sdkdir"]

    known_blobs = {}
    for filename in os.listdir(blobdir):
        if filename.lower().endswith(".blob"):
            id = gen_id_from_filename(filename)
            if id in known_blobs:
                raise Exception("Duplicate blob ID?", id)
            known_blobs[id] = os.path.join(blobdir, filename)

    # Start checksum aggregation with the branch blob
    branch_id = gen_id_from_filename(blobname)
    appid, appver = branch_id[:2]

    blobcontainers = {}
    checksums = {}

    _get_checksums(known_blobs, branch_id, blobcontainers, checksums)

    # Cache the checksums if the configuration allows
    if config_var["cache_sdk_depot"].lower() == "true":
        checksumfilename = os.path.join("files/cache/", f"{appid}.checksums")
        with open(checksumfilename, "wb") as of:
            of.write(blobcontainers[branch_id]["checksumbin"])

    # Return the aggregated checksum binary data
    return bytes(blobcontainers[branch_id]["checksumbin"])


# FIXME this needs to reuse the checksum function above, instead of rewriting the method inside itself
def generate_index_bytes(blobname, dat_directory, output_directory="files/cache/"):
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