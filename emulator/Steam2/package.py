import struct, zlib

class Package(object) :
    def __init__(self, pkg = None) :
        self.pkg = pkg
        self.filenames = []
        self.file_chunks = {}
        self.file_unpacked_sizes = {}
        self.pkg_ver = 0
        self.compress_level = 0
        if self.pkg :
            self.unpack()
        
    def unpack(self) :
        (self.pkg_ver, self.compress_level, num_files) = struct.unpack("<BLL", self.pkg[-9:])

        index = len(self.pkg) - (9 + 16)
        for i in xrange(num_files) :
            (unpacked_size, packed_size, file_start, filename_len) = struct.unpack("<LLLL", self.pkg[index:index+16])
            filename = self.pkg[index-filename_len:index-1]
            index = index - (filename_len + 16)
            file = []
            while packed_size > 0 :
                compressed_len = struct.unpack("<L", self.pkg[file_start:file_start+4])[0]
                compressed_start = file_start+4
                compressed_end   = compressed_start + compressed_len
                file.append(self.pkg[compressed_start:compressed_end])
                file_start = compressed_end
                packed_size = packed_size - compressed_len
            self.file_chunks[filename] = file
            self.file_unpacked_sizes[filename] = unpacked_size
            self.filenames.append(filename)
        
    def get_file(self, filename) :
        if filename not in self.filenames :
            return
            
        file = []
        for chunk in self.file_chunks[filename] :
            file.append(zlib.decompress(chunk))
        
        return "".join(file)

    def put_file(self, filename, filedata) :
        chunks = []
        for i in xrange(0, len(filedata), 0x8000) :
            chunks.append(zlib.compress(filedata[i:i+0x8000], self.compress_level))
        self.file_chunks[filename] = chunks
        self.file_unpacked_sizes[filename] = len(filedata)
        if filename not in self.filenames :
            self.filenames.append(filename)
    
    def pack(self) :
        datasection = []
        datasection_length = 0
        indexsection = []
        number_of_files = 0
        for filename in self.filenames :
            packedbytes = 0
            outfileoffset = datasection_length
            number_of_files += 1
            for chunk in self.file_chunks[filename] :
                chunk_length = len(chunk)
                datasection.append(struct.pack("<L", chunk_length))
                datasection_length += 4
                datasection.append(chunk)
                datasection_length += chunk_length
                packedbytes += chunk_length

            indexsection.insert(0, filename + "\x00" + struct.pack("<LLLL", self.file_unpacked_sizes[filename], packedbytes, outfileoffset, len(filename) + 1))

        return "".join(datasection) + "".join(indexsection) + struct.pack("<BLL", self.pkg_ver, self.compress_level, number_of_files)
