import mmap
import os
import logging
import sys
from io import BytesIO

from utilities.manifests import *


class GCF_block_entry(object):
    def __init__(self):
        self.first_data_block_index = None
        self.file_data_size = None


class GCF(object):
    def __init__(self, filename):
        log = logging.getLogger("converter")

        self.f = open(filename, "rb")
        self.filesize = os.path.getsize(filename)
        self.mapped_file = mmap.mmap(self.f.fileno(), 0, access = mmap.ACCESS_READ)

        # Read the header using memory-mapped file
        header = self.mapped_file.read(44)
        (self.header_dummy1,
         self.header_dummy2,
         self.gcfversion,
         self.appid,
         self.appversion,
         self.header_dummy3,
         self.header_dummy4,
         self.filesize,
         self.blocksize,
         self.blockcount,
         self.header_dummy5) = struct.unpack("<LLLLLLLLLLL", header)

        if self.header_dummy1 != 1 or self.header_dummy2 != 1 or self.gcfversion != 6:
            log.error("Invalid version numbers: " + str(self.header_dummy1) + str(self.header_dummy2) + str(self.gcfversion))
            sys.exit()

        if self.header_dummy3 != 0 or self.header_dummy4 != 0:
            log.debug("Unknown dummy3 and dummy4 values: " + str(self.header_dummy3) + str(self.header_dummy4))  # sys.exit()

        if self.filesize != os.path.getsize(filename):
            log.error("File size in header doesn't match real file size " + str(self.filesize) + str(os.path.getsize(filename)))
            sys.exit()

        if self.blocksize != 8192:
            log.error("Unknown blocksize: " + str(self.blocksize))
            sys.exit()

        log.debug("Header data - appid: %i appver: %i blockcount: %i dummy5: %i" % (self.appid, self.appversion, self.blockcount, self.header_dummy5))

        block_header = self.mapped_file.read(32)
        (blockcount,
         blocksused,
         dummy0,
         dummy1,
         dummy2,
         dummy3,
         dummy4,
         checksum) = struct.unpack("<LLLLLLLL", block_header)

        if blockcount != self.blockcount:
            log.error("Different block counts in header and block header: " + str(self.blockcount) + str(blockcount))
            sys.exit()

        if dummy1 != 0 or dummy2 != 0 or dummy3 != 0 or dummy4 != 0:
            log.error("Dummy values different than expected " + str(dummy1) + str(dummy2) + str(dummy3) + str(dummy4))
            sys.exit()

        log.debug("Block header - blocks used: %i, dummy0: %i" % (blocksused, dummy0))

        block_data = BytesIO(self.mapped_file.read(self.blockcount * 28))
        self.block_entries = {}
        for i in range(self.blockcount):
            b = GCF_block_entry()
            (b.entry_type, b.file_data_offset, b.file_data_size, b.first_data_block_index, b.next_block_entry_index, b.prev_block_entry_index, b.dir_index) = struct.unpack("<LLLLLLL", block_data.read(28))
            self.block_entries[i] = b

        frag_header = self.mapped_file.read(16)
        (blockcount, dummy0, dummy1, checksum) = struct.unpack("<LLLL", frag_header)

        if blockcount != self.blockcount:
            log.error("Different block counts in header and frag header: " + str(self.blockcount) + str(blockcount))
            sys.exit()

        log.debug("Frag header - dummy0: %i dummy1: %i" % (dummy0, dummy1))

        frag_data = BytesIO(self.mapped_file.read(blockcount * 4))
        self.frag_entries = {}
        for i in range(blockcount):
            self.frag_entries[i] = struct.unpack("<L", frag_data.read(4))[0]

        self.manifest_index = self.mapped_file.tell()
        manifest_header = self.mapped_file.read(56)
        manifest_size = struct.unpack("<L", manifest_header[24:28])[0]
        manifest_binary = self.mapped_file.read(manifest_size - 56)

        self.manifest_data = manifest_header + manifest_binary
        self.manifest = Manifest(self.manifest_data)

        self.mapped_file.seek(self.manifest_index + manifest_size)

        dirmap_header = self.mapped_file.read(8)
        dirmap_data = BytesIO(self.mapped_file.read(self.manifest.num_items * 4))
        self.dirmap_entries = {}
        for i in range(self.manifest.num_items):
            self.dirmap_entries[i] = struct.unpack("<L", dirmap_data.read(4))[0]

        checksum_header = self.mapped_file.read(8)
        # print("GCF Checksum header: " + str(checksum_header))
        (dummy0, checksumsize) = struct.unpack("<LL", checksum_header)
        # print dummy0, checksumsize

        self.checksum_data = self.mapped_file.read(checksumsize)
        block_header = self.mapped_file.read(24)
        (appversion, blockcount, blocksize, self.firstblockoffset, blocksused, checksum) = struct.unpack("<LLLLLL", block_header)

        # print hex(self.firstblockoffset)

    def get_file(self, dirid):
        log = logging.getLogger("converter")
        if self.manifest.dir_entries[dirid].fileid == 0xffffffff:
            log.error("Tried to read directory file " + str(dirid))
            sys.exit()

        nextblock = self.dirmap_entries[dirid]

        while nextblock < self.blockcount:
            b = self.block_entries[nextblock]
            nextdata = b.first_data_block_index
            datasize = b.file_data_size

            while True:
                index = self.firstblockoffset + nextdata * self.blocksize
                self.mapped_file.seek(index)

                nextdata = self.frag_entries[nextdata]
                if nextdata < self.blockcount:
                    datasize -= self.blocksize
                    yield self.mapped_file.read(self.blocksize)
                else:
                    yield self.mapped_file.read(datasize)
                    break

            nextblock = b.next_block_entry_index

    # Remember to close the mapped file and the file descriptor when done
    def close(self):
        self.mapped_file.close()
        self.f.close()