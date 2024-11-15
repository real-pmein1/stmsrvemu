import hashlib
import os
import struct
import sys
import zlib


def package_unpack(infilename, outpath):
    if not os.path.exists(outpath):
        os.makedirs(outpath)

    infile = open(infilename, "rb")
    package = infile.read()
    infile.close()

    header = package[-9:]

    (pkg_ver, compress_level, numfiles) = struct.unpack("<BLL", package[-9:])

    index = len(package) - (9 + 16)

    for i in range(numfiles):

        (unpacked_size, packed_size, file_start, filename_len) = struct.unpack("<LLLL", package[index:index + 16])

        filename = package[index - filename_len:index - 1]

        (filepath, basename) = os.path.split(filename)

        index = index - (filename_len + 16)

        file = ""

        while packed_size > 0:
            compressed_len = struct.unpack("<L", package[file_start:file_start + 4])[0]

            compressed_start = file_start + 4
            compressed_end = compressed_start + compressed_len

            compressed_data = package[compressed_start:compressed_end]

            file += zlib.decompress(compressed_data)

            file_start = compressed_end
            packed_size = packed_size - compressed_len

        outsubpath = os.path.join(outpath, filepath)

        if not os.path.exists(outsubpath):
            os.makedirs(outsubpath)

        outfullfilename = os.path.join(outpath, filename)

        outfile = open(outfullfilename, "wb")
        outfile.write(file)
        outfile.close()

        # print filename, "written"


def package_unpack2(infilename, outpath, version, pkg_name):
    if not os.path.exists(outpath):
        os.makedirs(outpath)

    infile = open(infilename, "rb")
    package = infile.read()
    infile.close()

    header = package[-9:]

    (pkg_ver, compress_level, numfiles) = struct.unpack("<BLL", package[-9:])

    index = len(package) - (9 + 16)

    filenames = []

    for i in range(numfiles):

        (unpacked_size, packed_size, file_start, filename_len) = struct.unpack("<LLLL", package[index:index + 16])

        filename = package[index - filename_len:index - 1]

        (filepath, basename) = os.path.split(filename)

        index = index - (filename_len + 16)

        file = b""

        while packed_size > 0:
            compressed_len = struct.unpack("<L", package[file_start:file_start + 4])[0]

            compressed_start = file_start + 4
            compressed_end = compressed_start + compressed_len

            compressed_data = package[compressed_start:compressed_end]

            file += zlib.decompress(compressed_data)

            file_start = compressed_end
            packed_size = packed_size - compressed_len

        outsubpath = os.path.join(outpath, filepath.decode())

        if not os.path.exists(outsubpath):
            os.makedirs(outsubpath)

        outfullfilename = os.path.join(outpath, filename.decode())

        outfile = open(outfullfilename, "wb")
        outfile.write(file)
        outfile.close()

        filenames.append(outfullfilename)

        # print(filename, "written")
    if infilename.endswith(".pkg"):
        with open(pkg_name + "_" + version + ".mst", "w") as f:
            for filename in filenames:
                f.writelines(filename + "\n")
    print("")


def package_pack(directory, outfilename):
    filenames = []

    for root, dirs, files in os.walk(directory):
        for name in files:
            if directory != root[0:len(directory)]:
                print("ERROR!!!!!!")
                sys.exit()

            filename = os.path.join(root, name)
            filename = filename[len(directory):]  # crop off the basepath part of the filename

            filenames.append(filename)

    # print filenames

    outfileoffset = 0

    datasection = ""
    indexsection = ""
    numberoffiles = 0

    for filename in filenames:

        infile = open(directory + filename, "rb")
        filedata = infile.read()
        infile.close()

        index = 0
        packedbytes = 0

        for i in range(0, len(filedata), 0x8000):
            chunk = filedata[i:i + 0x8000]

            packedchunk = zlib.compress(chunk, 9)

            packedlen = len(packedchunk)

            datasection = datasection + struct.pack("<L", packedlen) + packedchunk

            packedbytes += packedlen

        indexsection = indexsection + filename + b"\x00" + struct.pack("<LLLL", len(filedata), packedbytes, outfileoffset, len(filename) + 1)

        outfileoffset = len(datasection)

        numberoffiles += 1

        # print filename

    fulloutfile = datasection + indexsection + struct.pack("<BLL", 0, 9, numberoffiles)

    outfile = open(outfilename, "wb")
    outfile.write(fulloutfile)
    outfile.close()


class Package(object):
    def __init__(self, pkg = None):
        self.pkg = pkg
        self.filenames = []
        self.file_chunks = {}
        self.file_unpacked_sizes = {}
        self.pkg_ver = 0
        self.compress_level = 0
        if self.pkg:
            self.unpack()

    def unpack(self):
        (self.pkg_ver, self.compress_level, num_files) = struct.unpack("<BLL", self.pkg[-9:])

        index = len(self.pkg) - (9 + 16)
        for i in range(num_files):
            (unpacked_size, packed_size, file_start, filename_len) = struct.unpack("<LLLL", self.pkg[index:index + 16])
            filename = self.pkg[index - filename_len:index - 1]
            index = index - (filename_len + 16)
            file = []
            while packed_size > 0:
                compressed_len = struct.unpack("<L", self.pkg[file_start:file_start + 4])[0]
                compressed_start = file_start + 4
                compressed_end = compressed_start + compressed_len
                file.append(self.pkg[compressed_start:compressed_end])
                file_start = compressed_end
                packed_size = packed_size - compressed_len
            self.file_chunks[filename] = file
            self.file_unpacked_sizes[filename] = unpacked_size
            self.filenames.append(filename)  # print(filename)

    def get_file(self, filename):
        if filename not in self.filenames:
            return

        file = []
        for chunk in self.file_chunks[filename]:
            file.append(zlib.decompress(chunk))

        return b"".join(file)

    def put_file(self, filename, filedata):
        chunks = []
        for i in range(0, len(filedata), 0x8000):
            chunks.append(zlib.compress(filedata[i:i + 0x8000], self.compress_level))
        self.file_chunks[filename] = chunks
        self.file_unpacked_sizes[filename] = len(filedata)
        if filename not in self.filenames:
            self.filenames.append(filename)

    def pack(self):
        datasection = []
        datasection_length = 0
        indexsection = []
        number_of_files = 0
        for filename in self.filenames:
            packedbytes = 0
            outfileoffset = datasection_length
            number_of_files += 1
            for chunk in self.file_chunks[filename]:
                chunk_length = len(chunk)
                datasection.append(struct.pack("<L", chunk_length))
                datasection_length += 4
                datasection.append(chunk)
                datasection_length += chunk_length
                packedbytes += chunk_length
            filename_bytes = filename.encode() if isinstance(filename, str) else filename
            indexsection.insert(0, filename_bytes + b"\x00" + struct.pack("<LLLL", self.file_unpacked_sizes[filename], packedbytes, outfileoffset, len(filename) + 1))

        return b"".join(datasection) + b"".join(indexsection) + struct.pack("<BLL", self.pkg_ver, self.compress_level, number_of_files)


def check_pkgs(db_row):
    from config import get_config
    config = get_config()

    if db_row[21] == "MISSING" or db_row[22] == "MISSING":
        return "missing"

    def get_crc(file_path):
        with open(file_path, 'rb') as file:
            return hashlib.md5(file.read()).hexdigest()

    steam_pkg_path = 'Steam_' + str(db_row[2]) + '.pkg'
    steamui_pkg_path = 'SteamUI_' + str(db_row[3]) + '.pkg'

    if db_row[1] == 1:
        steam_crc = get_crc(config["packagedir"] + 'betav2/' + steam_pkg_path)
        steamui_crc = get_crc(config["packagedir"] + 'betav2/PLATFORM_' + steamui_pkg_path)
    elif os.path.isfile(config["packagedir"] + steam_pkg_path) and os.path.isfile(config["packagedir"] + steamui_pkg_path):
        steam_crc = get_crc(config["packagedir"] + steam_pkg_path)
        steamui_crc = get_crc(config["packagedir"] + steamui_pkg_path)
    else:
        return "missing"

    if steam_crc != str(db_row[21]) or steamui_crc != str(db_row[22]):
        return "failed"

    return "ok"