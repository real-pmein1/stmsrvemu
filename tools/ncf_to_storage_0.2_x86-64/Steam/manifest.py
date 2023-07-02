import struct

class DirectoryEntry :
    pass

class Manifest :
    def __init__(self, manifestdata = "") :
        if len(manifestdata) :
            self.manifestdata = manifestdata
            self.initialize()
            
    def load_from_file(self, filename) :
        f = open(filename, "rb")
        self.manifestdata = f.read()
        f.close()

        self.initialize()

    def initialize(self) :
        (self.dummy1,
         self.stored_appid,
         self.stored_appver,
         self.num_items,
         self.num_files,
         self.blocksize,
         self.dirsize,
         self.dirnamesize,
         self.info1count,
         self.copycount,
         self.localcount,
         self.dummy2,
         self.dummy3,
         self.checksum) = struct.unpack("<LLLLLLLLLLLLLL", self.manifestdata[0:56])

        self.dirnames_start = 56 + self.num_items * 28

        self.dir_entries = {}
        for i in range(self.num_items) :
            index = 56 + i * 28
            d = DirectoryEntry()
            (d.nameoffset, d.itemsize, d.fileid, d.dirtype, d.parentindex, d.nextindex, d.firstindex) = struct.unpack("<LLLLLLL", self.manifestdata[index:index+28])
            filename_start = self.dirnames_start + d.nameoffset
            filename_end = self.manifestdata.index("\x00", filename_start)
            d.filename = self.manifestdata[filename_start:filename_end]
            self.dir_entries[i] = d

        for i in range(self.num_items) :
            d = self.dir_entries[i]
            fullfilename = d.filename
            while d.parentindex != 0xffffffff :
                d = self.dir_entries[d.parentindex]

                fullfilename = d.filename + "/" + fullfilename
            
            d = self.dir_entries[i]
            d.fullfilename = fullfilename
            
