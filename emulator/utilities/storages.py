import logging
import os
import struct
import sys
import io
import re
import numpy as np

from collections import defaultdict
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA1
from Crypto.PublicKey import RSA

import globalvars
from utilities.blobs import SDKBlob
from utilities.encryption import config
from utilities.indexes import readindexes, readindexes_old, readindexes_tane


class Old_Storage(object):
    def __init__(self, storagename, path, suffix = ""):
        self.name = str(storagename)

        self.indexfile = path + self.name + suffix + ".index"
        self.datafile = path + self.name + suffix + ".data"

        (self.indexes, self.filemodes) = readindexes(self.indexfile)

        self.f = False

    def readchunk(self, fileid, chunkid):
        index = self.indexes[fileid]

        if not self.f:
            self.f = open(self.datafile, "rb")

        pos = chunkid * 16

        (start, length) = struct.unpack(">QQ", index[pos:pos + 16])

        self.f.seek(start)
        file = self.f.read(length)

        return file, self.filemodes[fileid]

    def readchunks(self, fileid, chunkid, maxchunks):

        filechunks = []
        index = self.indexes[fileid]

        if not self.f:
            self.f = open(self.datafile, "rb")

        indexstart = chunkid * 16

        for pos in range(indexstart, len(index), 16):
            (start, length) = struct.unpack(">QQ", index[pos:pos + 16])

            self.f.seek(start)
            filechunks.append(self.f.read(length))

            maxchunks -= 1

            if maxchunks == 0:
                break

        return filechunks, self.filemodes[fileid]

    def readfile(self, fileid):

        filechunks = []
        index = self.indexes[fileid]

        if not self.f:
            self.f = open(self.datafile, "rb")

        for pos in range(0, len(index), 16):
            (start, length) = struct.unpack(">QQ", index[pos:pos + 16])

            self.f.seek(start)
            filechunks.append(self.f.read(length))

        return filechunks, self.filemodes[fileid]

    def writefile(self, fileid, filechunks, filemode):

        if fileid in self.indexes:
            print("FileID already exists!")
            sys.exit()

        if self.f:
            self.f.close()
            self.f = False
        f = open(self.datafile, "a+b")
        fi = open(self.indexfile, "ab")

        f.seek(0, 2)  # this is a hack to get the f.tell() to show the correct position

        outindex = struct.pack(">QQQ", fileid, len(filechunks) * 16, filemode)

        for chunk in filechunks:
            outfilepos = f.tell()

            outindex += struct.pack(">QQ", outfilepos, len(chunk))

            f.write(chunk)

        fi.write(outindex)

        f.close()
        fi.close()

        self.indexes[fileid] = outindex[12:]
        self.filemodes[fileid] = filemode

    def close(self):
        if self.f:
            self.f.close()
            self.f = False


class Storage(object):
    def __init__(self, storagename, path, version, islan = False):
        self.log = logging.getLogger('Storage')
        self.manifest = None
        self.version = None
        self.app = None
        self.name = str(storagename)
        self.ver = str(version)

        # Normalize the path to ensure consistent path separators
        normalized_path = os.path.normpath(path)

        # Use os.path.join to create normalized comparisons for storage paths
        storages_path = os.path.normpath("storages/")
        beta1_path = os.path.normpath("storages/beta1/")

        # Check if the path ends with the normalized storage paths
        if normalized_path.endswith(storages_path) or normalized_path.endswith(beta1_path):
            manifestpathnew = config["manifestdir"]
            manifestpathold = config["v2manifestdir"]
            manifestpathxtra = config["v3manifestdir2"]
            manifestpathtane = config["v4manifestdir"]
        else:
            self.log.error("Path to storages directory is not set to files/storages!")
            return

        if config["public_ip"] != "0.0.0.0":
            if islan:
                self.suffix = "_lan"
            else:
                self.suffix = "_wan"
        else:
            self.suffix = ""

        # if os.path.isfile("files/cache/" + self.name + "_" + self.ver + "/" + self.name + "_" + self.ver + self.suffix + ".checksums"):

        # self.indexfile = "files/cache/" + self.name + "_" + self.ver + "/" + self.name + "_" + self.ver + self.suffix + ".index"

        # (self.indexes, self.filemodes) = readindexes(self.indexfile)
        # self.storage_type = "v3"
        if os.path.isfile("files/cache/" + self.name + "_" + self.ver + "/" + self.name + "_" + self.ver + ".manifest"):

            self.indexfile = "files/cache/" + self.name + "_" + self.ver + "/" + self.name + self.suffix + ".index"
            self.datafile = "files/cache/" + self.name + "_" + self.ver + "/" + self.name + self.suffix + ".data"

            (self.indexes, self.filemodes) = readindexes(self.indexfile)
            self.storage_type = "v3"
        elif os.path.isfile(manifestpathnew + self.name + "_" + self.ver + ".v4.manifest"):
            self.indexfile = config["storagedir"] + self.name + ".v4.index"
            self.datafile = config["storagedir"] + self.name + ".v4.data"

            (self.indexes, self.filemodes) = readindexes_tane(self.indexfile)
            if os.path.isfile("files/cache/" + self.name + "_" + self.ver + "/" + self.name + "_" + self.ver + self.suffix + ".index"):
                (index2, mode2) = readindexes_tane("files/cache/" + self.name + "_" + self.ver + "/" + self.name + "_" + self.ver + self.suffix + ".index")
                for fileid in index2:
                    self.indexes[fileid] = index2[fileid]
                    self.filemodes[fileid] = mode2[fileid]
            self.storage_type = "v4"
        elif os.path.isfile(manifestpathtane + self.name + "_" + self.ver + ".manifest"):
            self.indexfile = config["v4storagedir"] + self.name + ".index"
            self.datafile = config["v4storagedir"] + self.name + ".data"

            (self.indexes, self.filemodes) = readindexes_tane(self.indexfile)
            if os.path.isfile("files/cache/" + self.name + "_" + self.ver + "/" + self.name + "_" + self.ver + self.suffix + ".index"):
                (index2, mode2) = readindexes_tane("files/cache/" + self.name + "_" + self.ver + "/" + self.name + "_" + self.ver + self.suffix + ".index")
                for fileid in index2:
                    self.indexes[fileid] = index2[fileid]
                    self.filemodes[fileid] = mode2[fileid]
            self.storage_type = "v4"
        elif os.path.isfile(manifestpathnew + self.name + "_" + self.ver + ".v2.manifest"):
            self.indexfile = config["storagedir"] + self.name + ".v2.index"
            self.datafile = config["storagedir"] + self.name + ".v2.data"

            (self.indexes, self.filemodes) = readindexes_old(self.indexfile)
            if os.path.isfile("files/cache/" + self.name + "_" + self.ver + "/" + self.name + "_" + self.ver + self.suffix + ".index"):
                (index2, mode2) = readindexes_old("files/cache/" + self.name + "_" + self.ver + "/" + self.name + "_" + self.ver + self.suffix + ".index")
                for fileid in index2:
                    self.indexes[fileid] = index2[fileid]
                    self.filemodes[fileid] = mode2[fileid]
            self.storage_type = "v2"
        elif os.path.isfile(manifestpathold + self.name + "_" + self.ver + ".manifest"):
            self.indexfile = config["v2storagedir"] + self.name + ".index"
            self.datafile = config["v2storagedir"] + self.name + ".data"

            (self.indexes, self.filemodes) = readindexes_old(self.indexfile)
            if os.path.isfile("files/cache/" + self.name + "_" + self.ver + "/" + self.name + "_" + self.ver + self.suffix + ".index"):
                (index2, mode2) = readindexes_old("files/cache/" + self.name + "_" + self.ver + "/" + self.name + "_" + self.ver + self.suffix + ".index")
                for fileid in index2:
                    self.indexes[fileid] = index2[fileid]
                    self.filemodes[fileid] = mode2[fileid]
            self.storage_type = "v2"
        elif os.path.isfile(manifestpathnew + self.name + "_" + self.ver + ".v3e.manifest"):
            self.indexfile = config["storagedir"] + self.name + ".v3e.index"
            self.datafile = config["storagedir"] + self.name + ".v3e.data"

            (self.indexes, self.filemodes) = readindexes(self.indexfile)
            if os.path.isfile("files/cache/" + self.name + "_" + self.ver + "/" + self.name + "_" + self.ver + self.suffix + ".index"):
                (index2, mode2) = readindexes("files/cache/" + self.name + "_" + self.ver + "/" + self.name + "_" + self.ver + self.suffix + ".index")
                for fileid in index2:
                    self.indexes[fileid] = index2[fileid]
                    self.filemodes[fileid] = mode2[fileid]
            self.storage_type = "v3e"
        elif os.path.isfile(manifestpathnew + self.name + "_" + self.ver + ".v3.manifest"):
            self.indexfile = config["storagedir"] + self.name + ".v3.index"
            self.datafile = config["storagedir"] + self.name + ".v3.data"

            (self.indexes, self.filemodes) = readindexes(self.indexfile)
            if os.path.isfile("files/cache/" + self.name + "_" + self.ver + "/" + self.name + "_" + self.ver + self.suffix + ".index"):
                (index2, mode2) = readindexes("files/cache/" + self.name + "_" + self.ver + "/" + self.name + "_" + self.ver + self.suffix + ".index")
                for fileid in index2:
                    self.indexes[fileid] = index2[fileid]
                    self.filemodes[fileid] = mode2[fileid]
            self.storage_type = "v3"
        elif os.path.isfile(manifestpathxtra + self.name + "_" + self.ver + ".manifest"):
            self.indexfile = config["v3storagedir2"] + self.name + ".index"
            self.datafile = config["v3storagedir2"] + self.name + ".data"

            (self.indexes, self.filemodes) = readindexes(self.indexfile)
            if os.path.isfile("files/cache/" + self.name + "_" + self.ver + "/" + self.name + "_" + self.ver + self.suffix + ".index"):
                (index2, mode2) = readindexes("files/cache/" + self.name + "_" + self.ver + "/" + self.name + "_" + self.ver + self.suffix + ".index")
                for fileid in index2:
                    self.indexes[fileid] = index2[fileid]
                    self.filemodes[fileid] = mode2[fileid]
            self.storage_type = "v3"
        else:
            self.indexfile = config["storagedir"] + self.name + ".index"
            self.datafile = config["storagedir"] + self.name + ".data"

            (self.indexes, self.filemodes) = readindexes(self.indexfile)
            if os.path.isfile("files/cache/" + self.name + "_" + self.ver + "/" + self.name + "_" + self.ver + self.suffix + ".index"):
                (index2, mode2) = readindexes("files/cache/" + self.name + "_" + self.ver + "/" + self.name + "_" + self.ver + self.suffix + ".index")
                for fileid in index2:
                    self.indexes[fileid] = index2[fileid]
                    self.filemodes[fileid] = mode2[fileid]
            self.storage_type = "v3"

        self.f = False

    def readchunk(self, fileid, chunkid):
        index = self.indexes[fileid]

        if not self.f:
            self.f = open(self.datafile, "rb")

        pos = chunkid * 16

        (start, length) = struct.unpack(">QQ", index[pos:pos + 16])

        self.f.seek(start)
        file = self.f.read(length)

        return file, self.filemodes[fileid]

    def readchunks(self, fileid, chunkid, maxchunks):
        try:
            if self.storage_type == "v3":
                filechunks = []
                index = self.indexes[fileid]

                if os.path.isfile("files/cache/" + self.name + "_" + self.ver + "/" + self.name + "_" + str(fileid) + self.suffix + ".data"):
                    if self.f:
                        self.f.close()
                        self.f = False
                    self.f = open("files/cache/" + self.name + "_" + self.ver + "/" + self.name + "_" + str(fileid) + self.suffix + ".data", "rb")

                    indexstart = chunkid * 16

                    for pos in range(indexstart, len(index), 16):
                        (start, length) = struct.unpack(">QQ", index[pos:pos + 16])

                        self.f.seek(start)
                        filechunks.append(self.f.read(length))

                        maxchunks -= 1

                        if maxchunks == 0:
                            break
                    self.f.close()
                    self.f = False
                    return filechunks, self.filemodes[fileid]

                if not self.f:
                    self.f = open(self.datafile, "rb")

                indexstart = chunkid * 16

                for pos in range(indexstart, len(index), 16):
                    (start, length) = struct.unpack(">QQ", index[pos:pos + 16])

                    self.f.seek(start)
                    filechunks.append(self.f.read(length))

                    maxchunks -= 1

                    if maxchunks == 0:
                        break

                return filechunks, self.filemodes[fileid]

            elif self.storage_type == "v4":
                filechunks = []
                index = self.indexes[fileid]

                if os.path.isfile("files/cache/" + self.name + "_" + self.ver + "/" + self.name + "_" + str(fileid) + self.suffix + ".data"):
                    if self.f:
                        self.f.close()
                        self.f = False
                    self.f = open("files/cache/" + self.name + "_" + self.ver + "/" + self.name + "_" + str(fileid) + self.suffix + ".data", "rb")

                    indexstart = chunkid * 12

                    for pos in range(indexstart, len(index), 12):
                        (start, length) = struct.unpack(">QL", index[pos:pos + 12])

                        self.f.seek(start)
                        filechunks.append(self.f.read(length))

                        maxchunks -= 1

                        if maxchunks == 0:
                            break
                    self.f.close()
                    self.f = False
                    return filechunks, self.filemodes[fileid]

                if not self.f:
                    self.f = open(self.datafile, "rb")

                indexstart = chunkid * 12

                for pos in range(indexstart, len(index), 12):
                    (start, length) = struct.unpack(">QL", index[pos:pos + 12])

                    self.f.seek(start)
                    filechunks.append(self.f.read(length))

                    maxchunks -= 1

                    if maxchunks == 0:
                        break

                return filechunks, self.filemodes[fileid]

            else:
                filechunks = []
                index = self.indexes.get(fileid)
                if index is None:
                    # Handle the case where the index is missing
                    self.log.warning(f"File ID {fileid} not found in indexes.")
                    return
                if os.path.isfile("files/cache/" + self.name + "_" + self.ver + "/" + self.name + "_" + str(fileid) + self.suffix + ".data"):
                    if self.f:
                        self.f.close()
                        self.f = False
                    self.f = open("files/cache/" + self.name + "_" + self.ver + "/" + self.name + "_" + str(fileid) + self.suffix + ".data", "rb")

                    indexstart = chunkid * 8

                    for pos in range(indexstart, len(index), 8):
                        (start, length) = struct.unpack(">LL", index[pos:pos + 8])

                        self.f.seek(start)
                        filechunks.append(self.f.read(length))

                        maxchunks -= 1

                        if maxchunks == 0:
                            break
                    self.f.close()
                    self.f = False
                    return filechunks, self.filemodes[fileid]

                f = open(self.datafile, "rb")

                indexstart = chunkid * 8

                for pos in range(indexstart, len(index), 8):
                    (start, length) = struct.unpack(">LL", index[pos:pos + 8])

                    f.seek(start)
                    filechunks.append(f.read(length))

                    maxchunks -= 1

                    if maxchunks == 0:
                        break

                return filechunks, self.filemodes[fileid]
        except Exception as e:
            self.log.error(f"There was a issue reading your chunks!!! {e}")

    def readfile(self, fileid):
        if fileid not in self.indexes:
            self.log.error("FileID does not exist!")
            sys.exit()
        with open(self.datafile, "rb") as f:
            start, length = np.frombuffer(self.indexes[fileid], dtype = np.uint64).reshape(-1, 2).T
            filechunks = [f.read(length[i]) for i in range(len(start))]
        return filechunks, self.filemodes[fileid]

    def writefile(self, fileid, filechunks, filemode):
        if fileid in self.indexes:
            self.log.error("FileID already exists!")
            sys.exit()
        if os.path.exists(self.datafile):
            os.remove(self.datafile)
        with open(self.datafile, "a+b") as f, open(self.indexfile, "ab") as fi:
            f.seek(0, 2)  # this is a hack to get the f.tell() to show the correct position
            outindex = np.array([fileid, len(filechunks) * 16, filemode], dtype = np.uint64).tobytes()
            for chunk in filechunks:
                outfilepos = f.tell()
                outindex += np.array([outfilepos, len(chunk)], dtype = np.uint64).tobytes()
                f.write(chunk)
            fi.write(outindex)
        self.indexes[fileid] = outindex[12:]
        self.filemodes[fileid] = filemode


class Steam2Storage(object):
    class BlobContainer:
        def __init__(self):
            pass

    def __init__(self, storagename, _, version, islan = False):
        self.log = logging.getLogger('SDKDepot')
        self.manifest = None
        self.version = None
        self.app = None
        self.name = str(storagename)
        self.ver = str(version)
        self.islan = islan

        self.indexes = {}
        self.filemodes = {}
        self.datafile = None
        self.f = None
        self.blob_directory = config['steam2sdkdir']
        self.dat_directory = config['steam2sdkdir']
        self.checksumbin = None
        self.known_blobs = globalvars.known_blobs  # Use the globally scanned blob files
        self.known_dats = globalvars.known_dats  # Use the globally scanned dat files

        branch_id = (int(self.name), int(self.ver))
        blobcontainers, checksums, datreferences = self.get_blobdata(self.known_blobs, branch_id)

        self.file_data_info = {}
        for fileid in sorted(datreferences):
            id, filedata, checksums_list = datreferences[fileid]
            filesize, offset, filemode = filedata

            # Determine datid
            if len(id) == 2:
                datid = id
            elif len(id) == 3:
                datid = (id[0], id[1], blobcontainers[id].datachecksum)
            else:
                self.log.error("bad id")

            datfile_path = self.known_dats.get(datid)
            if datfile_path is None:
                self.log.error("Data file not found for datid:", datid)

            self.file_data_info[fileid] = {
                    'datfile':  datfile_path,
                    'offset':   offset,
                    'filemode': filemode,
                    'checksums':checksums_list,
                    'filesize': filesize
            }

            self.filemodes[fileid] = filemode

    def readchunk(self, fileid, chunkid):
        file_info = self.file_data_info.get(fileid)
        if file_info is None:
            self.log.error("FileID does not exist!")

        datfile_path = file_info['datfile']
        offset = file_info['offset']
        filemode = file_info['filemode']
        checksums = file_info['checksums']

        if chunkid >= len(checksums):
            self.log.error("Invalid chunkid")

        compr_size, checksum = checksums[chunkid]

        # Calculate chunk offset
        chunk_offset = offset + sum(compr_size for compr_size, _ in checksums[:chunkid])

        with open(datfile_path, 'rb') as f:
            f.seek(chunk_offset)
            chunk_data = f.read(compr_size)
            if len(chunk_data) != compr_size:
                self.log.error("Failed to read chunk data")

        return chunk_data, filemode

    def readchunks(self, fileid, chunkid, maxchunks):
        file_info = self.file_data_info.get(fileid)
        if file_info is None:
            self.log.error("FileID does not exist!")

        datfile_path = file_info['datfile']
        offset = file_info['offset']
        filemode = file_info['filemode']
        checksums = file_info['checksums']

        chunks = []
        total_chunks = len(checksums)

        if chunkid >= total_chunks:
            self.log.error("Invalid chunkid")

        num_chunks_to_read = min(maxchunks, total_chunks - chunkid)

        # Calculate starting offset
        chunk_offset = offset + sum(compr_size for compr_size, _ in checksums[:chunkid])

        with open(datfile_path, 'rb') as f:
            f.seek(chunk_offset)
            for i in range(num_chunks_to_read):
                compr_size, checksum = checksums[chunkid + i]
                chunk_data = f.read(compr_size)
                if len(chunk_data) != compr_size:
                    self.log.error("Failed to read chunk data")
                chunks.append(chunk_data)

        return chunks, filemode

    def readfile(self, fileid):
        file_info = self.file_data_info.get(fileid)
        if file_info is None:
            self.log.error("FileID does not exist!")

        datfile_path = file_info['datfile']
        offset = file_info['offset']
        filemode = file_info['filemode']
        checksums = file_info['checksums']

        chunks = []
        with open(datfile_path, 'rb') as f:
            f.seek(offset)
            for compr_size, checksum in checksums:
                chunk_data = f.read(compr_size)
                if len(chunk_data) != compr_size:
                    self.log.error("Failed to read chunk data")
                chunks.append(chunk_data)

        return chunks, filemode

    # Implement writefile if needed (placeholder)
    def writefile(self, fileid, filechunks, filemode):
        raise NotImplementedError("Write operation is not supported in this class.")

    # Utility functions from steam2_sdk_depot.py
    @staticmethod
    def parse_checksums(checksumdata):
        log = logging.getLogger('SDKDepot')
        bio = io.BytesIO(checksumdata)
        if bio.read(4) != b"4rE4":
            log.error("Bad starting magic")

        version, num_fileblocks, num_items, offset1, offset2, blocksize, largest_num_blocks = struct.unpack("<IIIIIII", bio.read(28))

        if blocksize != 0x8000:
            log.error("Differing blocksize!", blocksize)

        if version not in (0, 1):
            log.error("Unknown version!", version)

        if offset1 != 0x20:
            log.error("Bad offset1", hex(offset1))

        if offset2 != 0x20 + 0x10 * num_fileblocks:
            log.error("Bad offset2", hex(offset2), 0x20 + 0x10 * num_fileblocks)

        fileblocks = []
        for i in range(num_fileblocks):
            fileid_start, filecount, offset, dummy4 = struct.unpack("<IIII", bio.read(16))
            fileblocks.append((fileid_start, filecount, offset))

            if dummy4 != 0:
                log.error("Unknown dummy4", dummy4)

        max_blocks = 0
        numfiles = 0

        filedata = {}
        checksums = {}
        highest_fileid = -1

        fingerprintdata = bytearray()

        for fileid_start, filecount, offset in fileblocks:
            if bio.tell() != offset:
                log.error("Offset doesn't match expected")

            numfiles += filecount
            for i in range(filecount):
                fileid = fileid_start + i
                fingerprintdata += struct.pack("<I", fileid)

                highest_fileid = max(highest_fileid, fileid)

                if version == 0:
                    filesize, offset, num_blocks = struct.unpack("<III", bio.read(12))

                elif version == 1:
                    filesize, offset, num_blocks = struct.unpack("<QQI", bio.read(20))

                else:
                    log.error("Unknown Version", version)

                filemode = num_blocks >> 24
                num_blocks = num_blocks & 0x00ffffff

                if filemode not in (1, 2, 3):
                    log.error("Bad filemode!", filemode)

                max_blocks = max(max_blocks, num_blocks)

                if fileid in filedata:
                    log.error("duplicate fileid", fileid)

                filedata[fileid] = (filesize, offset, filemode)

                if fileid in checksums:
                    log.error("duplicate fileid", fileid)

                checksums[fileid] = []
                for j in range(num_blocks):
                    compr_size = struct.unpack("<I", bio.read(4))[0]
                    checksum = bio.read(4)
                    fingerprintdata += checksum

                    checksums[fileid].append((compr_size, checksum))

        if bio.read() != b"4rE4":
            log.error("Bad ending magic")

        if max_blocks != largest_num_blocks:
            log.error("Max blocks doesn't match", max_blocks, largest_num_blocks)

        if numfiles != num_items:
            log.error("Numfiles doesn't match", numfiles, num_items)

        return filedata, checksums, fingerprintdata

    def get_blobdata(self, known_blobs, id):
        blobname = known_blobs[id]
        blobdata = open(blobname, "rb").read()
        # Placeholder for SDKBlob; implement or import as needed
        b = SDKBlob(blobdata)

        parentver = b.get_i32(11)
        parentcrc = f"{b.get_i32(12):08x}"

        if parentver == 0xffffffff:
            blobcontainers = {}
            checksums = {}
            datreferences = {}

        else:
            if len(id) == 2:
                parentid = (id[0], parentver)
            elif len(id) == 3:
                parentid = (id[0], parentver, parentcrc)
            else:
                self.log.error("bad id")

            if parentid not in known_blobs:
                self.log.error("parent blob doesn't exist:", parentid)

            blobcontainers, checksums, datreferences = self.get_blobdata(known_blobs, parentid)

        filedata, newchecksums, _ = self.parse_checksums(b.get_raw(4))

        for fileid in newchecksums:
            if fileid in checksums:
                self.log.debug(f"overwritten fileid from {id} to {parentid}: {fileid:d}")

            checksums[fileid] = newchecksums[fileid]

            datreferences[fileid] = (id, filedata[fileid], newchecksums[fileid])

        last_id = max(checksums.keys())

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
        self.checksumbin = checksumdata + signature
        blobcontainers[id] = self.BlobContainer()
        blobcontainers[id].checksumbin = checksumdata + signature
        blobcontainers[id].filedata = filedata
        blobcontainers[id].checksums = newchecksums
        blobcontainers[id].datachecksum = "%08x" % b.get_i32(7)
        blobcontainers[id].manifest = b.get_raw(3, 0)

        return blobcontainers, checksums, datreferences

    @staticmethod
    def gen_id_from_filename(filename):
        log = logging.getLogger('SDKDepot')
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
            log.error("Nonstandard filename format", filename)

        return id