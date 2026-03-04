import logging
import os
import struct
import sys
import io
import zlib
import numpy as np
import glob
from datetime import datetime

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

    def write_neutered(self, fileid, filechunks_lan, filemode, filechunks_wan, path, version):
        """
        Write a file's chunks to separate LAN and WAN storage files.

        This method writes neutered content with LAN/WAN split using v3 format
        (64-bit: header >QQQ, chunks >QQ).

        Args:
            fileid: The file ID
            filechunks_lan: List of chunk data for LAN
            filemode: File mode (1=plain, 2=encrypted+compressed, 3=encrypted)
            filechunks_wan: List of chunk data for WAN
            path: Base path for output files
            version: Storage version string for filename
        """
        # Create per-file data files
        datafile_lan = path + self.name + "_" + str(fileid) + "_lan.data"
        datafile_wan = path + self.name + "_" + str(fileid) + "_wan.data"
        indexfile_lan = path + self.name + "_" + str(version) + "_lan.index"
        indexfile_wan = path + self.name + "_" + str(version) + "_wan.index"

        f = open(datafile_lan, "a+b")
        w = open(datafile_wan, "a+b")
        fi = open(indexfile_lan, "ab")
        wi = open(indexfile_wan, "ab")

        f.seek(0, 2)
        w.seek(0, 2)

        # v3 format: header >QQQ (24 bytes), chunks >QQ (16 bytes each)
        outindex = struct.pack(">QQQ", fileid, len(filechunks_lan) * 16, filemode)
        outindex_wan = struct.pack(">QQQ", fileid, len(filechunks_wan) * 16, filemode)

        for chunk in filechunks_lan:
            outfilepos = f.tell()
            outindex = outindex + struct.pack(">QQ", outfilepos, len(chunk))
            f.write(chunk)

        for chunk_wan in filechunks_wan:
            outfilepos_wan = w.tell()
            outindex_wan = outindex_wan + struct.pack(">QQ", outfilepos_wan, len(chunk_wan))
            w.write(chunk_wan)

        fi.write(outindex)
        wi.write(outindex_wan)

        f.close()
        fi.close()
        w.close()
        wi.close()

        self.indexes[fileid] = outindex[24:]
        self.filemodes[fileid] = filemode


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
        self.year = ""
        self.current = datetime.strptime(globalvars.CDDB_datetime, "%m/%d/%Y %H:%M:%S")
        if self.name == "261" and (datetime(2006, 10, 12) <= self.current < datetime(2006, 11, 6)):
            self.year = "_2006"
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
        elif os.path.isfile(manifestpathnew + self.name + "_" + self.ver + self.year + ".v3.manifest"):
            self.indexfile = config["storagedir"] + self.name + self.year + ".v3.index"
            self.datafile = config["storagedir"] + self.name + self.year + ".v3.data"

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

    def write_neutered(self, fileid, filechunks_lan, filemode, filechunks_wan, path, version, storage_format=None):
        """
        Write a file's chunks to separate LAN and WAN storage files.

        This method writes neutered content with LAN/WAN split. The format is
        determined by storage_format parameter or self.storage_type.

        Args:
            fileid: The file ID
            filechunks_lan: List of chunk data for LAN
            filemode: File mode (1=plain, 2=encrypted+compressed, 3=encrypted)
            filechunks_wan: List of chunk data for WAN
            path: Base path for output files
            version: Storage version string for filename
            storage_format: Override format ('v2', 'v3', 'v4'). If None, uses self.storage_type
        """
        # Determine format to use
        fmt = storage_format if storage_format else getattr(self, 'storage_type', 'v3')

        # Create per-file data files
        datafile_lan = path + self.name + "_" + str(fileid) + "_lan.data"
        datafile_wan = path + self.name + "_" + str(fileid) + "_wan.data"
        indexfile_lan = path + self.name + "_" + str(version) + "_lan.index"
        indexfile_wan = path + self.name + "_" + str(version) + "_wan.index"

        f = open(datafile_lan, "a+b")
        w = open(datafile_wan, "a+b")
        fi = open(indexfile_lan, "ab")
        wi = open(indexfile_wan, "ab")

        f.seek(0, 2)
        w.seek(0, 2)

        if fmt == "v2":
            # v2 format: header >LLL (12 bytes), chunks >LL (8 bytes each)
            outindex = struct.pack(">LLL", fileid, len(filechunks_lan) * 8, filemode)
            outindex_wan = struct.pack(">LLL", fileid, len(filechunks_wan) * 8, filemode)

            for chunk in filechunks_lan:
                outfilepos = f.tell()
                outindex = outindex + struct.pack(">LL", outfilepos, len(chunk))
                f.write(chunk)

            for chunk_wan in filechunks_wan:
                outfilepos_wan = w.tell()
                outindex_wan = outindex_wan + struct.pack(">LL", outfilepos_wan, len(chunk_wan))
                w.write(chunk_wan)

            header_size = 12

        elif fmt == "v4":
            # v4 format: header >LLQ (16 bytes), chunks >QL (12 bytes each)
            outindex = struct.pack(">LLQ", fileid, len(filechunks_lan) * 12, filemode)
            outindex_wan = struct.pack(">LLQ", fileid, len(filechunks_wan) * 12, filemode)

            for chunk in filechunks_lan:
                outfilepos = f.tell()
                outindex = outindex + struct.pack(">QL", outfilepos, len(chunk))
                f.write(chunk)

            for chunk_wan in filechunks_wan:
                outfilepos_wan = w.tell()
                outindex_wan = outindex_wan + struct.pack(">QL", outfilepos_wan, len(chunk_wan))
                w.write(chunk_wan)

            header_size = 16

        else:
            # v3 format (default): header >QQQ (24 bytes), chunks >QQ (16 bytes each)
            outindex = struct.pack(">QQQ", fileid, len(filechunks_lan) * 16, filemode)
            outindex_wan = struct.pack(">QQQ", fileid, len(filechunks_wan) * 16, filemode)

            for chunk in filechunks_lan:
                outfilepos = f.tell()
                outindex = outindex + struct.pack(">QQ", outfilepos, len(chunk))
                f.write(chunk)

            for chunk_wan in filechunks_wan:
                outfilepos_wan = w.tell()
                outindex_wan = outindex_wan + struct.pack(">QQ", outfilepos_wan, len(chunk_wan))
                w.write(chunk_wan)

            header_size = 24

        fi.write(outindex)
        wi.write(outindex_wan)

        f.close()
        fi.close()
        w.close()
        wi.close()

        self.indexes[fileid] = outindex[header_size:]
        self.filemodes[fileid] = filemode


class Steam2Storage(object):
    class BlobContainer:
        def __init__(self):
            pass

    @staticmethod
    def _chunk_cache_path(appid, version, fileid, chunkid, suffix=""):
        return os.path.join("files", "cache",
                            f"{appid}_{version}",
                            f"{appid}_{fileid}{suffix}.data")

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

        if config["public_ip"] != "0.0.0.0":
            if islan:
                self.suffix = "_lan"
            else:
                self.suffix = "_wan"
        else:
            self.suffix = ""

        branch_id = (int(self.name), int(self.ver))
        blobcontainers, checksums, datreferences = self.get_blobdata(self.known_blobs, branch_id)

        self.file_data_info = {}
        for fileid in sorted(datreferences):
            id, filedata, checksums_list = datreferences[fileid]
            filesize, offset, filemode = filedata

            if len(id) == 2:
                datid = id
            elif len(id) >= 3:
                datid = (id[0], id[1], blobcontainers[id].datachecksum)
            else:
                self.log.error("bad id")
                continue

            datfile_path = self.known_dats.get(datid)

            if datfile_path is None and len(datid) >= 3:
                short_id = (datid[0], datid[1])
                datfile_path = self.known_dats.get(short_id)

            if datfile_path is None:
                self.log.error(
                    "Data file not found for datid: %s  (tried %s)",
                    datid,
                    datid if len(datid) == 2 else short_id
                )
                continue

            self.file_data_info[fileid] = {
                'datfile':  datfile_path,
                'offset':   offset,
                'filemode': filemode,
                'checksums': checksums_list,
                'filesize': filesize
            }

            self.filemodes[fileid] = filemode
            # Ensure all fileid entries point to the same .dat file during initialization

    def readfile(self, fileid):
        if fileid not in self.indexes:
            self.log.error("FileID does not exist!")
            sys.exit()
        with open(self.datafile, "rb") as f:
            start, length = np.frombuffer(self.indexes[fileid], dtype = np.uint64).reshape(-1, 2).T
            filechunks = [f.read(length[i]) for i in range(len(start))]
        return filechunks, self.filemodes[fileid]

    def readchunk(self, fileid, chunkid):
        """
        Thin wrapper: grab exactly one chunk via readchunks().
        """
        chunks, mode = self.readchunks(fileid, chunkid, 1)
        return (chunks[0] if chunks else b""), mode

    def readchunks(self, fileid, first_chunk, maxchunks):
        """
        Try the cache .data file exactly like storage.readchunks(),
        otherwise fall back to the original .dat-based logic.
        """
        info = self.file_data_info.get(fileid)
        if info is None:
            self.log.error("FileID does not exist!")
            return [], 0

        # Build cache path (same naming as storage class)
        cache_path = os.path.join(
            "files", "cache",
            f"{self.name}_{self.ver}",
            f"{self.name}_{fileid}{self.suffix}.data"
        )
        index_path = os.path.join(
            "files", "cache",
            f"{self.name}_{self.ver}",
            f"{self.name}_{self.ver}{self.suffix}.index"
        )
        # 1) Cached .data exists?  Use index file to pull compressed blobs.
        if os.path.isfile(cache_path):
            # Derive .index path from your .dat path
            dat_path = info["datfile"]
            idx_path =  index_path

            if not os.path.isfile(idx_path):
                self.log.error("Index file not found for cache: %s", idx_path)
                return [], info["filemode"]

            # Load the same index table the storage class uses
            indexes, _ = readindexes(idx_path)
            index = indexes.get(fileid)
            if index is None:
                self.log.error("No index entry for fileid %d in %s", fileid, idx_path)
                return [], info["filemode"]

            # Open the per-file cache once
            if getattr(self, "f", False):
                self.f.close()
                self.f = False
            self.f = open(cache_path, "rb")

            filechunks = []
            # Walk the index, starting at first_chunk
            pos = first_chunk * 16
            while pos < len(index) and len(filechunks) < maxchunks:
                start, length = struct.unpack(">QQ", index[pos:pos+16])
                self.f.seek(start)
                filechunks.append(self.f.read(length))
                pos += 16

            self.f.close()
            self.f = False
            return filechunks, self.filemodes[fileid]

        # 2) Fallback: read straight out of the .dat
        checksums   = info["checksums"]
        total_chunks = len(checksums)
        if first_chunk >= total_chunks:
            self.log.error("Invalid chunkid %d for fileid %d", first_chunk, fileid)
            return [], info["filemode"]

        filechunks = []
        dat_path   = info["datfile"]
        base_off   = info["offset"]

        # slice out up to maxchunks
        for cid in range(first_chunk, min(first_chunk + maxchunks, total_chunks)):
            comp_size, _ = checksums[cid]
            # cumulative offset for this chunk
            chunk_off = base_off + sum(sz for sz, _ in checksums[:cid])

            with open(dat_path, "rb") as df:
                df.seek(chunk_off)
                data = df.read(comp_size)
                if len(data) != comp_size:
                    self.log.error(
                        "Failed to read %d bytes at %d in %s",
                        comp_size, chunk_off, dat_path
                    )
                filechunks.append(data)

        return filechunks, info["filemode"]

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
        # Determine cache directory from appid and version
        if len(id) == 3:
            appid, version, crc = id[0], id[1], id[2]
        else:
            appid, version = id[0], id[1]
        cache_dir = os.path.join("files", "cache", f"{appid}_{version}")

        # Look for any cached .checksums file: e.g. "123_456_lan.checksums" or "123_456.checksums"
        checksum_pattern = os.path.join(cache_dir, f"{appid}_{version}*.checksums")
        checksum_files = glob.glob(checksum_pattern)

        # Look for any cached .manifest file
        manifest_pattern = os.path.join(cache_dir, f"{appid}_{version}*.manifest")
        manifest_files = glob.glob(manifest_pattern)

        # Prepare blobcontainers, checksums, datreferences
        # (we'll fill checksumbin and manifest later)
        blobcontainers = {}
        checksums = {}
        datreferences = {}

        # If we have a cached checksums blob, load it now
        if checksum_files:
            cached_checksums_path = checksum_files[0]
            self.log.info(f"Loading cached checksums from {cached_checksums_path}")
            with open(cached_checksums_path, "rb") as f:
                cached_checksumbin = f.read()
            # We'll still need filedata and newchecksums below, so defer assignment
        else:
            cached_checksumbin = None

        # If we have a cached manifest blob, load it now
        if manifest_files:
            cached_manifest_path = manifest_files[0]
            self.log.info(f"Loading cached manifest from {cached_manifest_path}")
            with open(cached_manifest_path, "rb") as f:
                cached_manifest = f.read()
        else:
            cached_manifest = None

        # === Existing blob-loading logic ===
        new_known_blobs = {}
        for key, value in known_blobs.items():
            if key[0] == id[0]:
                new_known_blobs.update({(key[0], key[1]): value})
        blobname = new_known_blobs[id]
        blobdata = open(blobname, "rb").read()
        b = SDKBlob(blobdata)

        parentver = b.get_i32(11)
        parentcrc = f"{b.get_i32(12):08x}"

        if not (id[0], parentver) in new_known_blobs:
            parentver = 0xffffffff

        if parentver == 0xffffffff:
            pass
        else:
            if len(id) == 2:
                parentid = (id[0], parentver)
            elif len(id) >= 3:
                parentid = (id[0], parentver, parentcrc)
            else:
                self.log.error("bad id")
            found = False
            for key, value in new_known_blobs.items():
                if parentid == key:
                    found = True
                    break
            if not found:
                parentver = 0xffffffff
                self.log.error("parent blob doesn't exist:", parentid)
            blobcontainers, checksums, datreferences = self.get_blobdata(new_known_blobs, parentid)

        # Parse checksums out of the blob so we know filedata & newchecksums
        filedata, newchecksums, _ = self.parse_checksums(b.get_raw(4))

        for fileid in newchecksums:
            if fileid in checksums:
                self.log.debug(f"overwritten fileid from {id} to {parentid}: {fileid:d}")
            checksums[fileid] = newchecksums[fileid]
            datreferences[fileid] = (id, filedata[fileid], newchecksums[fileid])

        # Build indextable & checksumtable only if no cached checksums
        if cached_checksumbin is None:
            last_id = max(checksums.keys())
            indextable = bytearray()
            checksumtable = bytearray()
            indexcount = last_id + 1
            checksumoffset = 0

            for fid in range(indexcount):
                if fid not in checksums:
                    indextable += struct.pack("<II", 0, 0)
                else:
                    num = len(checksums[fid])
                    indextable += struct.pack("<II", num, checksumoffset)
                    checksumoffset += num
                    for _, chk in checksums[fid]:
                        checksumtable += chk

            checksumdata = (
                b"\x21\x37\x89\x14"
                + struct.pack("<III", 1, indexcount, checksumoffset)
                + indextable
                + checksumtable
            )
            signature = b.get_raw(9)
            computed_checksumbin = checksumdata + signature
        else:
            computed_checksumbin = None

        # Finally, assign the checksumbin into both self and the container
        final_checksumbin = cached_checksumbin or computed_checksumbin
        self.checksumbin = final_checksumbin
        blobcontainers[id] = self.BlobContainer()
        blobcontainers[id].checksumbin = final_checksumbin
        blobcontainers[id].filedata = filedata
        blobcontainers[id].checksums = newchecksums
        blobcontainers[id].datachecksum = "%08x" % b.get_i32(7)

        # Assign manifest: use cached if available, else raw from blob
        if cached_manifest is not None:
            blobcontainers[id].manifest = cached_manifest
        else:
            blobcontainers[id].manifest = b.get_raw(3, 0)

        return blobcontainers, checksums, datreferences


    @staticmethod
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


class StorageBeta(object):
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
        storages_path = os.path.normpath("betastorages/")

        # Check if the path ends with the normalized storage paths
        if normalized_path.endswith(storages_path):
            manifestpathbeta = config["betamanifestdir"]
        else:
            self.log.error("Path to storages directory is not set to files/betastorages!")
            return

        if config["public_ip"] != "0.0.0.0":
            if islan:
                self.suffix = "_lan"
            else:
                self.suffix = "_wan"
        else:
            self.suffix = ""

        if os.path.isfile("files/cache/beta/" + self.name + "_" + self.ver + "/" + self.name + "_" + self.ver + ".manifest"):

            self.indexfile = "files/cache/beta/" + self.name + "_" + self.ver + "/" + self.name + "_" + self.ver + self.suffix + ".index"
            self.datafile = "files/cache/beta/" + self.name + "_" + self.ver + "/" + self.name + "_" + self.ver + self.suffix + ".data"

            (self.indexes, self.filemodes) = readindexes(self.indexfile)
            self.storage_type = "beta"
        elif os.path.isfile(manifestpathbeta + self.name + "_" + self.ver + ".manifest"):
            self.indexfile = config["betastoragedir"] + self.name + "_" + self.ver + ".index"
            self.datafile = config["betastoragedir"] + self.name + "_" + self.ver + ".data"

            (self.indexes, self.filemodes) = readindexes_tane(self.indexfile)
            if os.path.isfile("files/cache/beta/" + self.name + "_" + self.ver + "/" + self.name + "_" + self.ver + self.suffix + ".index"):
                (index2, mode2) = readindexes_tane("files/cache/beta/" + self.name + "_" + self.ver + "/" + self.name + "_" + self.ver + self.suffix + ".index")
                for fileid in index2:
                    self.indexes[fileid] = index2[fileid]
                    self.filemodes[fileid] = mode2[fileid]
            self.storage_type = "beta"

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
            if self.storage_type == "beta":
                filechunks = []
                index = self.indexes[fileid]

                if os.path.isfile("files/cache/beta/" + self.name + "_" + self.ver + "/" + self.name + "_" + str(fileid) + self.suffix + ".data"):
                    if self.f:
                        self.f.close()
                        self.f = False
                    self.f = open("files/cache/beta/" + self.name + "_" + self.ver + "/" + self.name + "_" + str(fileid) + self.suffix + ".data", "rb")

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

    def write_neutered(self, fileid, filechunks_lan, filemode, filechunks_wan, path, version):
        """
        Write a file's chunks to separate LAN and WAN storage files.

        This method writes neutered content with LAN/WAN split using v4 format
        (mixed: header >LLQ, chunks >QL) which is typical for beta storages.

        Args:
            fileid: The file ID
            filechunks_lan: List of chunk data for LAN
            filemode: File mode (1=plain, 2=encrypted+compressed, 3=encrypted)
            filechunks_wan: List of chunk data for WAN
            path: Base path for output files
            version: Storage version string for filename
        """
        # Create per-file data files
        datafile_lan = path + self.name + "_" + str(fileid) + "_lan.data"
        datafile_wan = path + self.name + "_" + str(fileid) + "_wan.data"
        indexfile_lan = path + self.name + "_" + str(version) + "_lan.index"
        indexfile_wan = path + self.name + "_" + str(version) + "_wan.index"

        f = open(datafile_lan, "a+b")
        w = open(datafile_wan, "a+b")
        fi = open(indexfile_lan, "ab")
        wi = open(indexfile_wan, "ab")

        f.seek(0, 2)
        w.seek(0, 2)

        # v4 format: header >LLQ (16 bytes), chunks >QL (12 bytes each)
        outindex = struct.pack(">LLQ", fileid, len(filechunks_lan) * 12, filemode)
        outindex_wan = struct.pack(">LLQ", fileid, len(filechunks_wan) * 12, filemode)

        for chunk in filechunks_lan:
            outfilepos = f.tell()
            outindex = outindex + struct.pack(">QL", outfilepos, len(chunk))
            f.write(chunk)

        for chunk_wan in filechunks_wan:
            outfilepos_wan = w.tell()
            outindex_wan = outindex_wan + struct.pack(">QL", outfilepos_wan, len(chunk_wan))
            w.write(chunk_wan)

        fi.write(outindex)
        wi.write(outindex_wan)

        f.close()
        fi.close()
        w.close()
        wi.close()

        self.indexes[fileid] = outindex[16:]
        self.filemodes[fileid] = filemode


# =============================================================================
# NEUTER STORAGE WRITER - Lightweight class for neuter.py compatibility
# =============================================================================

class NeuterStorageWriter:
    """
    Lightweight storage writer for neutering operations.

    This class provides a simplified interface for neuter.py to write
    neutered content without requiring full storage initialization.
    It reads existing indexes from .orig.index if available (to track
    already-processed files) and provides write_neutered() for output.

    Replaces the standalone NeuterStorage, NeuterStorage03, and NeuterStorage04 classes.
    """

    def __init__(self, storagename, path, storage_format='v3'):
        """
        Initialize the neuter storage writer.

        Args:
            storagename: The storage name (typically appid as string)
            path: Base path for storage files
            storage_format: Storage format ('v2', 'v3', or 'v4')
        """
        self.name = str(storagename)
        self.path = path
        self.storage_format = storage_format

        # Read existing indexes from .orig.index if available
        self.indexfile = path + self.name + ".orig.index"

        if storage_format == 'v2':
            (self.indexes, self.filemodes) = readindexes_old(self.indexfile)
        elif storage_format == 'v4':
            (self.indexes, self.filemodes) = readindexes_tane(self.indexfile)
        else:  # v3 (default)
            (self.indexes, self.filemodes) = readindexes(self.indexfile)

    def writefile(self, fileid, filechunks_lan, filemode, filechunks_wan, path, version):
        """
        Write a file's chunks to separate LAN and WAN storage files.

        This is the main method called by neuter.py. Signature matches
        the original NeuterStorage* classes for compatibility.

        Args:
            fileid: The file ID
            filechunks_lan: List of chunk data for LAN
            filemode: File mode (1=plain, 2=encrypted+compressed, 3=encrypted)
            filechunks_wan: List of chunk data for WAN
            path: Base path for output files
            version: Storage version string for filename
        """
        # Create per-file data files
        datafile_lan = path + self.name + "_" + str(fileid) + "_lan.data"
        datafile_wan = path + self.name + "_" + str(fileid) + "_wan.data"
        indexfile_lan = path + self.name + "_" + str(version) + "_lan.index"
        indexfile_wan = path + self.name + "_" + str(version) + "_wan.index"

        f = open(datafile_lan, "a+b")
        w = open(datafile_wan, "a+b")
        fi = open(indexfile_lan, "ab")
        wi = open(indexfile_wan, "ab")

        f.seek(0, 2)
        w.seek(0, 2)

        if self.storage_format == "v2":
            # v2 format: header >LLL (12 bytes), chunks >LL (8 bytes each)
            outindex = struct.pack(">LLL", fileid, len(filechunks_lan) * 8, filemode)
            outindex_wan = struct.pack(">LLL", fileid, len(filechunks_wan) * 8, filemode)

            for chunk in filechunks_lan:
                outfilepos = f.tell()
                outindex = outindex + struct.pack(">LL", outfilepos, len(chunk))
                f.write(chunk)

            for chunk_wan in filechunks_wan:
                outfilepos_wan = w.tell()
                outindex_wan = outindex_wan + struct.pack(">LL", outfilepos_wan, len(chunk_wan))
                w.write(chunk_wan)

            header_size = 12

        elif self.storage_format == "v4":
            # v4 format: header >LLQ (16 bytes), chunks >QL (12 bytes each)
            outindex = struct.pack(">LLQ", fileid, len(filechunks_lan) * 12, filemode)
            outindex_wan = struct.pack(">LLQ", fileid, len(filechunks_wan) * 12, filemode)

            for chunk in filechunks_lan:
                outfilepos = f.tell()
                outindex = outindex + struct.pack(">QL", outfilepos, len(chunk))
                f.write(chunk)

            for chunk_wan in filechunks_wan:
                outfilepos_wan = w.tell()
                outindex_wan = outindex_wan + struct.pack(">QL", outfilepos_wan, len(chunk_wan))
                w.write(chunk_wan)

            header_size = 16

        else:
            # v3 format (default): header >QQQ (24 bytes), chunks >QQ (16 bytes each)
            outindex = struct.pack(">QQQ", fileid, len(filechunks_lan) * 16, filemode)
            outindex_wan = struct.pack(">QQQ", fileid, len(filechunks_wan) * 16, filemode)

            for chunk in filechunks_lan:
                outfilepos = f.tell()
                outindex = outindex + struct.pack(">QQ", outfilepos, len(chunk))
                f.write(chunk)

            for chunk_wan in filechunks_wan:
                outfilepos_wan = w.tell()
                outindex_wan = outindex_wan + struct.pack(">QQ", outfilepos_wan, len(chunk_wan))
                w.write(chunk_wan)

            header_size = 24

        fi.write(outindex)
        wi.write(outindex_wan)

        f.close()
        fi.close()
        w.close()
        wi.close()

        self.indexes[fileid] = outindex[header_size:]
        self.filemodes[fileid] = filemode

    def close(self):
        """Close any open file handles (for compatibility)."""
        pass

