import struct, cStringIO, sys, os

from manifest import *

class NCF_block_entry :
    pass
    
class NCF :
    def __init__(self, filename) :
        self.f = open(filename, "rb")

        header = self.f.read(44)
        (self.header_dummy1,
         self.header_dummy2,
         self.ncfversion, 
         self.appid, 
         self.appversion, 
         self.header_dummy3, 
         self.header_dummy4, 
         self.filesize, 
         self.blocksize, 
         self.blockcount, 
         self.header_dummy5) = struct.unpack("<LLLLLLLLLLL", header)
         
        #if self.header_dummy1 != 1 or self.header_dummy2 != 1 or self.ncfversion != 6 :
        #    print "Invalid version numbers:", self.header_dummy1, self.header_dummy2, self.ncfversion
        #    sys.exit()
        
        #if self.header_dummy3 != 0 or self.header_dummy4 != 0 :
        #    print "Unknown dummy3 and dummy4 values:", self.header_dummy3, self.header_dummy4
        #    #sys.exit()
            
        if self.filesize != 0 :
            print "File size in header doesn't match real file size", self.filesize, os.path.getsize(filename)
            sys.exit()

        if self.blocksize != 0 :
            print "Unknown blocksize:", self.blocksize
            sys.exit()
            
        print "Header data - appid: %i appver: %i blockcount: %i dummy5: %i" % (self.appid,
            self.appversion, self.blockcount, self.header_dummy5)
            
        #block_header = self.f.read(32)
        #(blockcount,
        # blocksused,
        # dummy0,
        # dummy1,
        # dummy2,
        # dummy3,
        # dummy4,
        # checksum) = struct.unpack("<LLLLLLLL", block_header)

        #if blockcount != self.blockcount :
        #    print "Different block counts in header and block header:", self.blockcount, blockcount
        #    sys.exit()

        #if dummy1 != 0 or dummy2 != 0 or dummy3 != 0 or dummy4 != 0 :
        #    print "Dummy values different than expected", dummy1, dummy2, dummy3, dummy4
        #    sys.exit()

        #print "Block header - blocks used: %i, dummy0: %i" % (blocksused, dummy0)
        
        #block_data = cStringIO.StringIO(self.f.read(self.blockcount * 28))
        #self.block_entries = {}
        #for i in range(self.blockcount) :
        #    b = NCF_block_entry()
        #    (b.entry_type, b.file_data_offset, b.file_data_size, b.first_data_block_index, b.next_block_entry_index, b.prev_block_entry_index, b.dir_index) = struct.unpack("<LLLLLLL", block_data.read(28))
        #    self.block_entries[i] = b

        #frag_header = self.f.read(16)
        #(blockcount, dummy0, dummy1, checksum) = struct.unpack("<LLLL", frag_header)

        #if blockcount != self.blockcount :
        #    print "Different block counts in header and frag header:", self.blockcount, blockcount
        #    sys.exit()
        
        #print "Frag header - dummy0: %i dummy1: %i" % (dummy0, dummy1)

        #frag_data = cStringIO.StringIO(self.f.read(blockcount * 4))
        #self.frag_entries = {}
        #for i in range(blockcount) :
        #    self.frag_entries[i] = struct.unpack("<L", frag_data.read(4))[0]

        self.manifest_index = self.f.tell()
        manifest_header = self.f.read(56)
        manifest_size = struct.unpack("<L", manifest_header[24:28])[0]
        manifest_binary = self.f.read(manifest_size - 56)

        self.manifest_data = manifest_header + manifest_binary
        self.manifest = Manifest(self.manifest_data)
        
        self.f.seek(self.manifest_index + manifest_size)

        dirmap_header = self.f.read(8)
        dirmap_data = cStringIO.StringIO(self.f.read(self.manifest.num_items * 4))
        self.dirmap_entries = {}
        for i in range(self.manifest.num_items) :
            self.dirmap_entries[i] = struct.unpack("<L", dirmap_data.read(4))[0]

        checksum_header = self.f.read(8)
        (dummy0, checksumsize) = struct.unpack("<LL", checksum_header)
        print dummy0, checksumsize

        self.checksum_data = self.f.read(checksumsize)
        #block_header = self.f.read(24)
        #(appversion, blockcount, blocksize, self.firstblockoffset, blocksused, checksum) = struct.unpack("<LLLLLL", block_header)

        #print hex(self.firstblockoffset)
    
    def get_file(self, dirid) :
        if self.manifest.dir_entries[dirid].fileid == 0xffffffff :
            print "Tried to read directory file", dirid
            sys.exit()

        #print "extracting", self.dirmap_entries[dirid], self.manifest.dir_entries[dirid].fullfilename, self.manifest.dir_entries[dirid].itemsize
        nextblock = self.dirmap_entries[dirid]

        while nextblock < self.blockcount :
            #(dummy, offset, length, blockindex, nextindex, previndex, fileid) = block_entries[nextblock]
            b = self.block_entries[nextblock]

            nextdata = b.first_data_block_index
            datasize = b.file_data_size
            while True :
                index = self.firstblockoffset + nextdata * self.blocksize
                self.f.seek(index)

                nextdata = self.frag_entries[nextdata]
                if nextdata < self.blockcount :
                    datasize -= self.blocksize
                    yield self.f.read(self.blocksize)
                else :
                    yield self.f.read(datasize)
                    break
            nextblock = b.next_block_entry_index
