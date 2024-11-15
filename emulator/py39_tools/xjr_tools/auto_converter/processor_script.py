import argparse, os, struct, sys, time, zlib, shutil, io

from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA1
from Crypto.PublicKey import RSA

from blob import *

import logging

# Configure logging to write errors to errors.txt
logging.basicConfig(filename='errors.txt', level=logging.ERROR, format='%(asctime)s %(levelname)s:%(message)s')

def move_to_processed(file_path):
    """
    Moves the given file to a subfolder named 'processed_files'.
    Creates the subfolder if it does not exist.
    """
    directory = os.path.dirname(file_path)
    processed_dir = os.path.join(directory, "processed_files")
    os.makedirs(processed_dir, exist_ok=True)
    destination = os.path.join(processed_dir, os.path.basename(file_path))
    shutil.move(file_path, destination)
    print(f"Moved '{file_path}' to '{destination}'")

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


class BlobContainer:
    def __init__(self):
        pass


def get_blobdata(known_blobs, id):
    try:
        blobname = known_blobs[id]  # Try to get the blob file for the given id
    except KeyError:
        print(f"Skipping version {id[1]} for depot {id[0]} as it doesn't exist.")
        return {}, {}, {}  # Return empty containers to prevent further processing

    blobdata = open(blobname, "rb").read()
    b = Blob(blobdata)

    # Move the .blob file after reading its data
    move_to_processed(blobname)
    # a few blobs have the wrong parent version, force it to always be current-1
    # parentver = b.get_i32(11)
    parentver = (id[1] - 1) & 0xffffffff
    parentcrc = "%08x" % b.get_i32(12)

    if parentver == 0xffffffff or parentcrc == "00000000":
        blobcontainers = {}
        checksums = {}
        datreferences = {}

    else:
        if len(id) == 2:
            parentid = (id[0], parentver)
        elif len(id) == 3:
            parentid = (id[0], parentver, parentcrc)
        else:
            raise Exception("bad id")

        if parentid not in known_blobs:
            print("parent blob doesn't exist:", parentid)

        blobcontainers, checksums, datreferences = get_blobdata(known_blobs, parentid)

    filedata, newchecksums, _ = parse_checksums(b.get_raw(4))

    for fileid in newchecksums:
        if fileid in checksums:
            print("overwritten fileid from %s to %s: %d" % (id, parentid, fileid))

        checksums[fileid] = newchecksums[fileid]

        datreferences[fileid] = (id, filedata[fileid], newchecksums[fileid])

    if len(checksums) > 0:
        last_id = max(checksums.keys())
    else:
        last_id = -1

    indextable = bytearray()
    checksumtable = bytearray()

    indexcount = last_id + 1
    checksumoffset = 0

    for fileid in range(last_id + 1):
        if fileid not in checksums:
            indextable += struct.pack("<II", 0, 0)

        else:
            numchecksums = len(checksums[fileid])

            indextable += struct.pack("<II", numchecksums, checksumoffset)
            checksumoffset += numchecksums

            for _, checksum in checksums[fileid]:
                checksumtable += checksum

    checksumdata = b"\x21\x37\x89\x14" + struct.pack("<III", 1, indexcount, checksumoffset) + indextable + checksumtable

    signature = b.get_raw(9)

    blobcontainers[id] = BlobContainer()
    blobcontainers[id].checksumbin = checksumdata + signature
    blobcontainers[id].filedata = filedata
    blobcontainers[id].checksums = newchecksums
    blobcontainers[id].datachecksum = "%08x" % b.get_i32(7)
    blobcontainers[id].manifest = b.get_raw(3, 0)

    return blobcontainers, checksums, datreferences


def gen_id_from_filename(filename):
    parts = os.path.basename(filename).split(".")[0].split("_")
    if len(parts) == 4:
        appid, appver, crc, hash = parts
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("blobname", help="Filename of last version blob")
    parser.add_argument("-d", "--datdir", help="Directory of .dat files, writes storage .index and .data if present")
    parser.add_argument("-m", "--manifests", action="store_true", help="Write out all manifests")
    parser.add_argument("-o", "--outdir", default=".", help="Output directory, default is current directory")
    args = parser.parse_args()

    if os.path.isfile("secondblob.bin"):
        cdr = Blob(open("secondblob.bin", "rb").read())
    else:
        print("secondblob.bin is missing, no signature verification is done")
        cdr = None

    blobdir = os.path.dirname(args.blobname)
    if blobdir == "":
        blobdir = "."

    known_blobs = {}
    for filename in os.listdir(blobdir):
        if filename.lower().endswith(".blob"):
            id = gen_id_from_filename(filename)
            if id in known_blobs:
                raise Exception("Duplicate blob ID?", id)

            known_blobs[id] = os.path.join(blobdir, filename)

    known_dats = {}
    if args.datdir:
        for filename in os.listdir(args.datdir):
            if filename.lower().endswith(".dat"):
                id = gen_id_from_filename(filename)
                if id in known_dats:
                    raise Exception("Duplicate dat ID?", id)

                known_dats[id] = os.path.join(args.datdir, filename)

    branch_id = gen_id_from_filename(args.blobname)
    appid, appver = branch_id[0:2]

    blobcontainers, checksums, datreferences = get_blobdata(known_blobs, branch_id)

    pubkey = None
    if cdr is not None:
        try:
            pubkeybin = cdr.get_raw(5, appid)
            pubkey = RSA.import_key(pubkeybin)
        except:
            print("Public key for appid not in CDR, skipping verification:", appid)

    if pubkey is not None:
        for id in sorted(blobcontainers):
            fulldata = blobcontainers[id].checksumbin
            checksumdata = fulldata[:-128]
            signature = fulldata[-128:]

            h = SHA1.new(checksumdata)
            res = pkcs1_15.new(pubkey).verify(h, signature)
            print("Signature verified OK", id)

    checksumfilename = os.path.join(args.outdir, "%d.checksums" % appid)
    of = open(checksumfilename, "wb")
    of.write(blobcontainers[branch_id].checksumbin)
    of.close()

    print("Created client checksums for", branch_id)

    if args.manifests:
        for id in sorted(blobcontainers):
            manifestfilename = os.path.join(args.outdir, "%d_%d.manifest" % id[0:2])
            of = open(manifestfilename, "wb")
            of.write(blobcontainers[id].manifest)
            of.close()

            print("created manifest for", id)

    if args.datdir:
        indexdata = bytearray()
        datptr = 0
        current_f = None

        datafilename = os.path.join(args.outdir, "%d.data" % appid)
        of = open(datafilename, "wb")
        for fileid in sorted(datreferences):
            id, filedata, checksums = datreferences[fileid]

            if len(id) == 2:
                datid = id
            elif len(id) == 3:
                datid = (id[0], id[1], blobcontainers[id].datachecksum)
            else:
                raise Exception("bad id")

            if datid not in known_dats:
                print(f"Data file for {datid} not found in known_dats.")
                continue  # Skip processing for this datid

            dat_file_path = known_dats[datid]
            if not os.path.isfile(dat_file_path):
                print(f"Data file '{dat_file_path}' does not exist.")
                continue  # Skip processing for this file

            if datid != current_f:
                if current_f != None:
                    f.close()
                    # Move the .dat file after processing
                    move_to_processed(known_dats[current_f])

                f = open(dat_file_path, "rb")
                current_f = datid

            filesize, offset, filemode = filedata

            f.seek(offset)

            indexdata += struct.pack(">QQQ", fileid, len(checksums) * 16, filemode)

            for compr_size, checksum in checksums:
                block = f.read(compr_size)
                if len(block) != compr_size:
                    raise Exception("bad block read!")

                if datptr != of.tell():
                    raise Exception("bad output data position!")

                indexdata += struct.pack(">QQ", datptr, compr_size)

                of.write(block)

                datptr += compr_size

        if current_f != None:
            f.close()
            # Move the last .dat file after processing
            move_to_processed(known_dats[current_f])

        of.close()

        indexfilename = os.path.join(args.outdir, "%d.index" % appid)
        of = open(indexfilename, "wb")
        of.write(indexdata)
        of.close()

        print("created index and data for", id)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.error("Exception in processor_script.py: %s", str(e))
        sys.exit(1)